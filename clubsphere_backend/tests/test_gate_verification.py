import pytest
import threading
from tests.conftest import create_user, login


@pytest.fixture(autouse=True)
def ensure_admin(db):
    """Ensure an administrator exists so the first-time setup redirect to /setup does not trigger."""
    row = db.execute("SELECT id FROM users WHERE role = 'Administrator'").fetchone()
    if not row:
        create_user(db, 'system_admin', 'Administrator')


def create_test_event(db, title='Annual Hackathon 2026', created_by=None, status='Upcoming'):
    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO events (title, description, event_date, event_time, venue, capacity, member_price, non_member_price, status, created_by)
        VALUES (?, 'Test event description', '2026-11-20', '10:00', 'Auditorium Hall', 200, 0, 50, ?, ?)
    """, (title, status, created_by))
    db.commit()
    return cursor.lastrowid


def create_test_ticket(db, event_id, ticket_ref='CS-TKT-GATE-001', name='Alex Attendee', email='alex@example.com', payment_status='Confirmed', checked_in=0):
    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO tickets (ticket_ref, event_id, purchaser_name, purchaser_email, price_paid, payment_status, checked_in)
        VALUES (?, ?, ?, ?, 50.0, ?, ?)
    """, (ticket_ref, event_id, name, email, payment_status, checked_in))
    db.commit()
    return cursor.lastrowid


# -------------------------------------------------------------------------
# 1. Administrator Full Access
# -------------------------------------------------------------------------
def test_admin_access_gate_verification(client, db):
    """Administrator has full access to Gate Verification, all aliases, and sidebar link."""
    admin_id = create_user(db, 'gate_admin', 'Administrator')
    login(client, 'gate_admin')

    event_id = create_test_event(db, 'Robotics Showcase', created_by=admin_id)

    # 1. Primary route
    res_primary = client.get('/tickets/checkin')
    assert res_primary.status_code == 200
    assert b"Gate Verification" in res_primary.data
    assert b"Robotics Showcase" in res_primary.data
    assert b"Gate Verification" in res_primary.data  # In navigation sidebar

    # 2. Route aliases
    res_alias1 = client.get('/gate/verify')
    assert res_alias1.status_code == 200
    assert b"Gate Verification" in res_alias1.data

    res_alias2 = client.get('/gate-verification')
    assert res_alias2.status_code == 200
    assert b"Gate Verification" in res_alias2.data


# -------------------------------------------------------------------------
# 2. Event Organizer Scoped Access
# -------------------------------------------------------------------------
def test_event_organizer_access_for_authorized_event(client, db):
    """Event Organizer can verify their own events, but is denied for events created by other users."""
    org1_id = create_user(db, 'organizer_one', 'Event Organizer')
    org2_id = create_user(db, 'organizer_two', 'Event Organizer')

    event1_id = create_test_event(db, 'Org One Event', created_by=org1_id)
    event2_id = create_test_event(db, 'Org Two Event', created_by=org2_id)

    ticket1 = 'CS-TKT-ORG1-01'
    ticket2 = 'CS-TKT-ORG2-02'
    create_test_ticket(db, event1_id, ticket1, name='User One')
    create_test_ticket(db, event2_id, ticket2, name='User Two')

    # Organizer One logs in
    login(client, 'organizer_one')

    # 1. Organizer One accesses gate console
    res = client.get('/tickets/checkin')
    assert res.status_code == 200
    assert b"Org One Event" in res.data
    # Event 2 should not appear in their authorized event options
    assert b"Org Two Event" not in res.data

    # 2. Organizer One verifies ticket for their event -> SUCCESS
    verify_res1 = client.post('/api/tickets/checkin', json={
        'ticket_ref': ticket1,
        'event_id': event1_id
    })
    assert verify_res1.status_code == 200
    assert verify_res1.get_json()['success'] is True

    # 3. Organizer One attempts to verify ticket for Event 2 -> FORBIDDEN (403)
    verify_res2 = client.post('/api/tickets/checkin', json={
        'ticket_ref': ticket2,
        'event_id': event2_id
    })
    assert verify_res2.status_code == 403
    assert verify_res2.get_json()['status'] == 'UNAUTHORIZED'


# -------------------------------------------------------------------------
# 3. Volunteer Authorized vs. Unauthorized Access
# -------------------------------------------------------------------------
def test_volunteer_authorized_vs_unauthorized_access(client, db):
    """Authorized gate-duty Volunteer has access; unauthorized Volunteer is denied."""
    vol_auth_id = create_user(db, 'vol_authorized', 'Volunteer')
    vol_unauth_id = create_user(db, 'vol_unauthorized', 'Volunteer')

    event1_id = create_test_event(db, 'Hackathon 2026')
    event2_id = create_test_event(db, 'Seminar 2026')

    # Assign vol_authorized to Hackathon in volunteer_tasks
    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO volunteer_tasks (title, description, event_id, assigned_to, priority, status)
        VALUES ('Gate Check-in Desk', 'Check attendee tickets at main gate', ?, ?, 'High', 'Pending')
    """, (event1_id, vol_auth_id))
    # Assign vol_unauthorized ONLY to Seminar (not Hackathon)
    cursor.execute("""
        INSERT INTO volunteer_tasks (title, description, event_id, assigned_to, priority, status)
        VALUES ('Set up Chairs', 'Prepare seminar seating', ?, ?, 'Low', 'Pending')
    """, (event2_id, vol_unauth_id))
    db.commit()

    tkt_hackathon = 'CS-TKT-HACK-01'
    create_test_ticket(db, event1_id, tkt_hackathon, name='Student Alice')

    # A. vol_authorized logs in
    login(client, 'vol_authorized')
    res_auth = client.get('/tickets/checkin')
    assert res_auth.status_code == 200
    assert b"Hackathon 2026" in res_auth.data

    # vol_authorized can verify ticket for Hackathon
    checkin_auth = client.post('/api/tickets/checkin', json={
        'ticket_ref': tkt_hackathon,
        'event_id': event1_id
    })
    assert checkin_auth.status_code == 200
    assert checkin_auth.get_json()['success'] is True

    # B. vol_unauthorized logs in
    login(client, 'vol_unauthorized')
    # vol_unauthorized attempts to verify ticket for Hackathon -> Denied (403)
    checkin_unauth = client.post('/api/tickets/checkin', json={
        'ticket_ref': tkt_hackathon,
        'event_id': event1_id
    })
    assert checkin_unauth.status_code == 403
    assert checkin_unauth.get_json()['status'] == 'UNAUTHORIZED'


# -------------------------------------------------------------------------
# 4. Treasurer and Member Denied by Default
# -------------------------------------------------------------------------
def test_treasurer_and_member_denied_gate_access(client, db):
    """Treasurer and Member accounts cannot access Gate Verification."""
    create_user(db, 'gate_treasurer', 'Treasurer')
    create_user(db, 'gate_member', 'Member')

    event_id = create_test_event(db, 'Gala Night')
    ticket_code = 'CS-TKT-GALA-01'
    create_test_ticket(db, event_id, ticket_code)

    # 1. Treasurer
    login(client, 'gate_treasurer')
    res_tre = client.get('/tickets/checkin', follow_redirects=True)
    assert b"Access denied" in res_tre.data

    api_tre = client.post('/api/tickets/checkin', json={'ticket_ref': ticket_code})
    assert api_tre.status_code == 403

    # 2. Member
    login(client, 'gate_member')
    res_mem = client.get('/tickets/checkin', follow_redirects=True)
    assert b"Access denied" in res_mem.data

    api_mem = client.post('/api/tickets/checkin', json={'ticket_ref': ticket_code})
    assert api_mem.status_code == 403


# -------------------------------------------------------------------------
# 5. Unauthenticated Access Denied
# -------------------------------------------------------------------------
def test_unauthenticated_user_denied_gate_access(client, db):
    """Unauthenticated users are redirected to login."""
    client.get('/logout')
    res_get = client.get('/tickets/checkin', follow_redirects=False)
    assert res_get.status_code == 302
    assert '/login' in res_get.headers['Location']

    res_alias = client.get('/gate/verify', follow_redirects=False)
    assert res_alias.status_code == 302
    assert '/login' in res_alias.headers['Location']

    res_api = client.post('/api/tickets/checkin', json={'ticket_ref': 'CS-TKT-TEST'})
    assert res_api.status_code == 302
    assert '/login' in res_api.headers['Location']


# -------------------------------------------------------------------------
# 6. Ticket Verification Rules: Valid, Invalid, Wrong Event, Duplicate
# -------------------------------------------------------------------------
def test_ticket_verification_validation_rules(client, db):
    """Comprehensive test for valid, invalid, wrong event, and duplicate ticket verification."""
    admin_id = create_user(db, 'gate_tester_admin', 'Administrator')
    login(client, 'gate_tester_admin')

    event1_id = create_test_event(db, 'AI Summit 2026')
    event2_id = create_test_event(db, 'Design Fest 2026')

    ticket_code = 'CS-TKT-VALID-01'
    create_test_ticket(db, event1_id, ticket_code, name='Rohan Mehta')

    # A. Invalid ticket ref
    res_inv = client.post('/api/tickets/checkin', json={
        'ticket_ref': 'NON-EXISTENT-CODE',
        'event_id': event1_id
    })
    assert res_inv.status_code == 400
    data_inv = res_inv.get_json()
    assert data_inv['success'] is False
    assert data_inv['status'] == 'INVALID'

    # B. Wrong event
    res_wrong = client.post('/api/tickets/checkin', json={
        'ticket_ref': ticket_code,
        'event_id': event2_id  # Ticket belongs to event1
    })
    assert res_wrong.status_code == 400
    data_wrong = res_wrong.get_json()
    assert data_wrong['success'] is False
    assert data_wrong['status'] == 'WRONG_EVENT'

    # C. Valid Check-in
    res_valid = client.post('/api/tickets/checkin', json={
        'ticket_ref': ticket_code,
        'event_id': event1_id
    })
    assert res_valid.status_code == 200
    data_valid = res_valid.get_json()
    assert data_valid['success'] is True
    assert data_valid['status'] == 'VALID'
    assert data_valid['ticket']['purchaser_name'] == 'Rohan Mehta'

    # Verify database state
    row = db.execute("SELECT checked_in, check_in_time, checked_in_by FROM tickets WHERE ticket_ref = ?", (ticket_code,)).fetchone()
    assert row['checked_in'] == 1
    assert row['check_in_time'] is not None
    assert row['checked_in_by'] == admin_id

    # D. Duplicate Check-in Rejected
    res_dup = client.post('/api/tickets/checkin', json={
        'ticket_ref': ticket_code,
        'event_id': event1_id
    })
    assert res_dup.status_code == 400
    data_dup = res_dup.get_json()
    assert data_dup['success'] is False
    assert data_dup['status'] == 'ALREADY_CHECKED_IN'
    assert 'Duplicate Check-In Alert' in data_dup['message']


# -------------------------------------------------------------------------
# 7. Persistence Across Refresh and Audit Trail
# -------------------------------------------------------------------------
def test_gate_checkin_persistence_and_audit_log(client, db):
    """Check-in persists across page refresh and records in gate_checkin_logs."""
    admin_id = create_user(db, 'audit_admin', 'Administrator')
    login(client, 'audit_admin')

    event_id = create_test_event(db, 'Cloud Computing Workshop')
    ticket_code = 'CS-TKT-AUDIT-01'
    create_test_ticket(db, event_id, ticket_code, name='Samantha Wu')

    # Perform check-in
    res = client.post('/api/gate/verify', json={
        'ticket_ref': ticket_code,
        'event_id': event_id
    })
    assert res.status_code == 200

    # Page refresh (GET request)
    page_res = client.get(f'/gate/verify?event_id={event_id}')
    assert page_res.status_code == 200
    html = page_res.data.decode('utf-8')
    assert ticket_code in html
    assert 'Samantha Wu' in html
    assert 'Checked In' in html

    # Audit log check
    log_row = db.execute("""
        SELECT * FROM gate_checkin_logs 
        WHERE ticket_ref = ? AND status = 'VALID'
    """, (ticket_code,)).fetchone()
    assert log_row is not None
    assert log_row['verifier_id'] == admin_id
    assert log_row['event_id'] == event_id


# -------------------------------------------------------------------------
# 8. Event Registration and Ticket Generation Intact
# -------------------------------------------------------------------------
def test_event_registration_and_immediate_gate_verification(client, db):
    """Existing event registration produces a confirmed ticket that can immediately be verified at the gate."""
    admin_id = create_user(db, 'reg_admin', 'Administrator')
    login(client, 'reg_admin')

    event_id = create_test_event(db, 'Cybersecurity Bootcamp')

    # Sell a ticket using existing event registration endpoint
    sell_res = client.post(f'/events/{event_id}/sell', data={
        'purchaser_name': 'Devin Vance',
        'purchaser_email': 'devin@example.com'
    }, follow_redirects=True)
    assert sell_res.status_code == 200
    assert b"confirmed successfully" in sell_res.data

    # Retrieve generated ticket reference
    new_ticket = db.execute("SELECT ticket_ref FROM tickets WHERE event_id = ? AND purchaser_email = 'devin@example.com'", (event_id,)).fetchone()
    assert new_ticket is not None
    gen_code = new_ticket['ticket_ref']

    # Gate verification verifies the newly generated ticket
    gate_res = client.post('/api/gate/verify', json={
        'ticket_ref': gen_code,
        'event_id': event_id
    })
    assert gate_res.status_code == 200
    data = gate_res.get_json()
    assert data['success'] is True
    assert data['status'] == 'VALID'
    assert data['ticket']['purchaser_name'] == 'Devin Vance'
