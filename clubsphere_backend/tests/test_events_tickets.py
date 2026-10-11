import pytest
from datetime import date, timedelta
from tests.conftest import create_user, login


def test_event_creation_and_member_pricing_eligibility(client, db):
    """Event creation and applying member discount only to active eligible members."""
    create_user(db, 'admin', 'Administrator')
    create_user(db, 'organizer', 'Event Organizer')
    login(client, 'organizer')

    today = date.today().isoformat()
    future_date = (date.today() + timedelta(days=14)).isoformat()
    future_expiry = (date.today() + timedelta(days=180)).isoformat()
    past_expiry = (date.today() - timedelta(days=10)).isoformat()

    # 1. Create Event with capacity 50, member_price = 100, non_member_price = 250
    client.post('/events/new', data={
        'title': 'HackFest 2026',
        'description': '24-hour hackathon',
        'event_date': future_date,
        'event_time': '09:00',
        'venue': 'Main Auditorium',
        'capacity': '50',
        'member_price': '100.00',
        'non_member_price': '250.00'
    }, follow_redirects=True)

    event = db.execute("SELECT * FROM events WHERE title = 'HackFest 2026'").fetchone()
    assert event is not None
    assert event['capacity'] == 50

    # 2. Register Active Member
    db.execute("""
        INSERT INTO members (member_code, full_name, email, join_date, expiry_date, membership_type, membership_fee, amount_paid, status)
        VALUES ('CS-MEM-ACT-1', 'Active Student', 'active@college.edu', ?, ?, 'Annual', 500, 500, 'Active')
    """, (today, future_expiry))

    # 3. Register Expired Member
    db.execute("""
        INSERT INTO members (member_code, full_name, email, join_date, expiry_date, membership_type, membership_fee, amount_paid, status)
        VALUES ('CS-MEM-EXP-1', 'Expired Student', 'expired@college.edu', ?, ?, 'Annual', 500, 500, 'Expired')
    """, (today, past_expiry))
    db.commit()

    # Sell ticket to active member -> Gets member price 100
    res_mem = client.post(f'/events/{event["id"]}/sell', data={
        'purchaser_name': 'Active Student',
        'purchaser_email': 'active@college.edu',
        'member_lookup': 'CS-MEM-ACT-1',
        'payment_method': 'UPI'
    }, follow_redirects=True)
    assert res_mem.status_code == 200

    ticket_mem = db.execute("SELECT * FROM tickets WHERE purchaser_email = 'active@college.edu'").fetchone()
    assert ticket_mem is not None
    assert ticket_mem['price_paid'] == 100.0
    assert ticket_mem['is_member_rate'] == 1

    # Sell ticket to non-member / guest -> Gets standard price 250
    res_guest = client.post(f'/events/{event["id"]}/sell', data={
        'purchaser_name': 'Guest Visitor',
        'purchaser_email': 'guest@external.com',
        'payment_method': 'Cash'
    }, follow_redirects=True)
    assert res_guest.status_code == 200

    ticket_guest = db.execute("SELECT * FROM tickets WHERE purchaser_email = 'guest@external.com'").fetchone()
    assert ticket_guest['price_paid'] == 250.0
    assert ticket_guest['is_member_rate'] == 0

    # Sell ticket to expired member -> Denied discount, charged non-member price 250
    res_exp = client.post(f'/events/{event["id"]}/sell', data={
        'purchaser_name': 'Expired Student',
        'purchaser_email': 'expired@college.edu',
        'member_lookup': 'CS-MEM-EXP-1',
        'payment_method': 'Cash'
    }, follow_redirects=True)
    assert res_exp.status_code == 200

    ticket_exp = db.execute("SELECT * FROM tickets WHERE purchaser_email = 'expired@college.edu'").fetchone()
    assert ticket_exp['price_paid'] == 250.0
    assert ticket_exp['is_member_rate'] == 0


def test_ticket_capacity_and_overselling_prevention(client, db):
    """Enforce strict capacity limit and reject sales when event is full."""
    create_user(db, 'admin', 'Administrator')
    login(client, 'admin')

    # Create small event with capacity of 2
    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO events (title, event_date, event_time, venue, capacity, member_price, non_member_price, status)
        VALUES ('VIP Masterclass', '2026-11-15', '14:00', 'Lab 1', 2, 50, 100, 'Upcoming')
    """)
    event_id = cursor.lastrowid
    db.commit()

    # Sell Ticket 1 (Capacity 1/2) -> Success
    res1 = client.post(f'/events/{event_id}/sell', data={
        'purchaser_name': 'Attendee One',
        'purchaser_email': 'one@example.com'
    }, follow_redirects=True)
    assert b"confirmed successfully" in res1.data

    # Sell Ticket 2 (Capacity 2/2) -> Success
    res2 = client.post(f'/events/{event_id}/sell', data={
        'purchaser_name': 'Attendee Two',
        'purchaser_email': 'two@example.com'
    }, follow_redirects=True)
    assert b"confirmed successfully" in res2.data

    # Attempt to Sell Ticket 3 (Event is full) -> Must be rejected!
    res3 = client.post(f'/events/{event_id}/sell', data={
        'purchaser_name': 'Attendee Three',
        'purchaser_email': 'three@example.com'
    }, follow_redirects=True)

    assert b"Overselling rejected" in res3.data or b"completely full" in res3.data

    # Ensure exactly 2 tickets exist in database
    sold_count = db.execute("SELECT COUNT(*) AS count FROM tickets WHERE event_id = ?", (event_id,)).fetchone()['count']
    assert sold_count == 2


def test_ticket_checkin_and_duplicate_prevention(client, db):
    """Validate check-in workflow and strictly reject duplicate check-ins."""
    create_user(db, 'admin', 'Administrator')
    create_user(db, 'volunteer', 'Volunteer')
    login(client, 'volunteer')

    # Create event and confirmed ticket
    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO events (title, event_date, event_time, venue, capacity, member_price, non_member_price, status)
        VALUES ('Robotics Expo', '2026-11-20', '11:00', 'Hall A', 100, 0, 50, 'Upcoming')
    """)
    event_id = cursor.lastrowid

    ticket_code = "CS-TKT-TEST-9999"
    cursor.execute("""
        INSERT INTO tickets (ticket_ref, event_id, purchaser_name, purchaser_email, price_paid, payment_status, checked_in)
        VALUES (?, ?, 'Priya Rao', 'priya@example.com', 50, 'Confirmed', 0)
    """, (ticket_code, event_id))
    db.commit()

    # 1. First Check-In Attempt -> Valid
    checkin_1 = client.post('/api/tickets/checkin', json={
        'ticket_ref': ticket_code,
        'event_id': event_id
    })
    assert checkin_1.status_code == 200
    data_1 = checkin_1.get_json()
    assert data_1['success'] is True
    assert data_1['status'] == 'VALID'
    assert "Check-In Successful" in data_1['message']

    # Verify database state
    tkt = db.execute("SELECT * FROM tickets WHERE ticket_ref = ?", (ticket_code,)).fetchone()
    assert tkt['checked_in'] == 1
    assert tkt['check_in_time'] is not None

    # 2. Duplicate Check-In Attempt -> Must be rejected!
    checkin_2 = client.post('/api/tickets/checkin', json={
        'ticket_ref': ticket_code,
        'event_id': event_id
    })
    assert checkin_2.status_code == 400
    data_2 = checkin_2.get_json()
    assert data_2['success'] is False
    assert data_2['status'] == 'ALREADY_CHECKED_IN'
    assert "Duplicate Check-In Alert" in data_2['message']

    # 3. Invalid Ticket Reference -> Must be rejected with clear 'Ticket not found' message!
    checkin_invalid = client.post('/api/tickets/checkin', json={
        'ticket_ref': 'NON-EXISTENT-CODE-1234'
    })
    assert checkin_invalid.status_code == 400
    data_inv = checkin_invalid.get_json()
    assert data_inv['success'] is False
    assert data_inv['status'] == 'INVALID'
    assert "Ticket not found" in data_inv['message']


def test_event_gate_verification_workflow_and_filters(client, db):
    """
    Comprehensive verification workflow test:
    1. Valid unchecked ticket checked in successfully.
    2. Already-checked-in ticket rejected with original timestamp and verifier name.
    3. Invalid ticket reference rejected with 'Ticket not found'.
    4. Ticket from a different event than the selected event rejected with 'Wrong Event'.
    5. 'All Active Events' allows verification of tickets across active events.
    6. Ticket for a cancelled event rejected with event cancellation message.
    """
    create_user(db, 'gate_admin', 'Administrator')
    staff_id = create_user(db, 'gate_staff', 'Event Organizer', full_name='Rohan Mehta')
    login(client, 'gate_staff')

    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO events (title, event_date, event_time, venue, capacity, member_price, non_member_price, status)
        VALUES ('AI Summit 2026', '2026-11-25', '10:00', 'Hall 1', 200, 0, 100, 'Upcoming')
    """)
    event_1_id = cursor.lastrowid

    cursor.execute("""
        INSERT INTO events (title, event_date, event_time, venue, capacity, member_price, non_member_price, status)
        VALUES ('Music Fest 2026', '2026-11-28', '18:00', 'Open Grounds', 500, 50, 150, 'Upcoming')
    """)
    event_2_id = cursor.lastrowid

    cursor.execute("""
        INSERT INTO events (title, event_date, event_time, venue, capacity, member_price, non_member_price, status)
        VALUES ('Cancelled Seminar', '2026-11-30', '14:00', 'Room 101', 50, 0, 0, 'Cancelled')
    """)
    event_cancelled_id = cursor.lastrowid

    # Tickets:
    # 1. Unchecked ticket for Event 1
    tkt_unchecked = "CS-TKT-GATE-001"
    cursor.execute("""
        INSERT INTO tickets (ticket_ref, event_id, purchaser_name, purchaser_email, price_paid, payment_status, checked_in)
        VALUES (?, ?, 'Aarav Sharma', 'aarav@example.com', 100, 'Confirmed', 0)
    """, (tkt_unchecked, event_1_id))

    # 2. Already checked-in ticket for Event 1
    tkt_already_in = "CS-TKT-GATE-002"
    cursor.execute("""
        INSERT INTO tickets (ticket_ref, event_id, purchaser_name, purchaser_email, price_paid, payment_status, checked_in, check_in_time, checked_in_by)
        VALUES (?, ?, 'Neha Gupta', 'neha@example.com', 100, 'Confirmed', 1, '2026-10-09 10:15:00', ?)
    """, (tkt_already_in, event_1_id, staff_id))

    # 3. Unchecked ticket for Event 2 (Music Fest)
    tkt_event_2 = "CS-TKT-GATE-003"
    cursor.execute("""
        INSERT INTO tickets (ticket_ref, event_id, purchaser_name, purchaser_email, price_paid, payment_status, checked_in)
        VALUES (?, ?, 'Sameer Joshi', 'sameer@example.com', 150, 'Confirmed', 0)
    """, (tkt_event_2, event_2_id))

    # 4. Ticket for cancelled event
    tkt_cancelled = "CS-TKT-GATE-004"
    cursor.execute("""
        INSERT INTO tickets (ticket_ref, event_id, purchaser_name, purchaser_email, price_paid, payment_status, checked_in)
        VALUES (?, ?, 'Kiran Patel', 'kiran@example.com', 0, 'Confirmed', 0)
    """, (tkt_cancelled, event_cancelled_id))
    db.commit()

    # Step 1: Valid unchecked ticket -> check in successfully
    res_valid = client.post('/api/tickets/checkin', json={
        'ticket_ref': tkt_unchecked,
        'event_id': event_1_id
    })
    assert res_valid.status_code == 200
    data_valid = res_valid.get_json()
    assert data_valid['success'] is True
    assert data_valid['status'] == 'VALID'
    assert 'Aarav Sharma' in data_valid['message']
    assert data_valid['ticket']['purchaser_name'] == 'Aarav Sharma'
    assert data_valid['ticket']['verifier_name'] == 'Rohan Mehta'
    assert data_valid['ticket']['check_in_time'] is not None

    # Step 2: Already checked in ticket -> rejected as duplicate with original time & verifier
    res_dup = client.post('/api/tickets/checkin', json={
        'ticket_ref': tkt_already_in,
        'event_id': event_1_id
    })
    assert res_dup.status_code == 400
    data_dup = res_dup.get_json()
    assert data_dup['success'] is False
    assert data_dup['status'] == 'ALREADY_CHECKED_IN'
    assert '2026-10-09 10:15:00' in data_dup['message']
    assert 'Rohan Mehta' in data_dup['message']
    assert data_dup['ticket']['check_in_time'] == '2026-10-09 10:15:00'
    assert data_dup['ticket']['verifier_name'] == 'Rohan Mehta'

    # Step 3: Invalid ticket reference -> rejected with 'Ticket not found'
    res_inv = client.post('/api/tickets/checkin', json={
        'ticket_ref': 'CS-TKT-NONEXISTENT'
    })
    assert res_inv.status_code == 400
    data_inv = res_inv.get_json()
    assert data_inv['success'] is False
    assert data_inv['status'] == 'INVALID'
    assert 'Ticket not found' in data_inv['message']

    # Step 4: Ticket from different event than selected -> rejected with 'Wrong Event'
    res_wrong = client.post('/api/tickets/checkin', json={
        'ticket_ref': tkt_event_2,
        'event_id': event_1_id
    })
    assert res_wrong.status_code == 400
    data_wrong = res_wrong.get_json()
    assert data_wrong['success'] is False
    assert data_wrong['status'] == 'WRONG_EVENT'
    assert 'Wrong Event' in data_wrong['message']
    assert 'Music Fest 2026' in data_wrong['message']

    # Step 5: 'All Active Events' (event_id=None or empty) -> accepts ticket for Music Fest
    res_all_events = client.post('/api/tickets/checkin', json={
        'ticket_ref': tkt_event_2,
        'event_id': None
    })
    assert res_all_events.status_code == 200
    data_all = res_all_events.get_json()
    assert data_all['success'] is True
    assert data_all['status'] == 'VALID'
    assert 'Sameer Joshi' in data_all['message']

    # Step 6: Ticket for Cancelled Event -> rejected
    res_canc = client.post('/api/tickets/checkin', json={
        'ticket_ref': tkt_cancelled
    })
    assert res_canc.status_code == 400
    data_canc = res_canc.get_json()
    assert data_canc['success'] is False
    assert data_canc['status'] == 'CANCELLED_EVENT'
    assert 'cancelled' in data_canc['message'].lower()


def test_event_gate_ui_page_rendering(client, db):
    """Verify Event Gate page loads and displays recent checkins and dropdown options."""
    create_user(db, 'gate_admin2', 'Administrator')
    login(client, 'gate_admin2')

    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO events (title, event_date, event_time, venue, capacity, member_price, non_member_price, status)
        VALUES ('Active Symposium', '2026-12-01', '09:00', 'Auditorium', 150, 0, 75, 'Upcoming')
    """)
    ev_id = cursor.lastrowid
    cursor.execute("""
        INSERT INTO tickets (ticket_ref, event_id, purchaser_name, purchaser_email, price_paid, payment_status, checked_in, check_in_time)
        VALUES ('CS-TKT-VIEW-1', ?, 'Maya Roy', 'maya@example.com', 75, 'Confirmed', 1, '2026-10-10 12:00:00')
    """, (ev_id,))
    db.commit()

    res = client.get('/tickets/checkin')
    assert res.status_code == 200
    html = res.data.decode('utf-8')
    assert 'Gate Verification' in html
    assert 'Live attendance monitoring' in html
    assert 'Attendee Verification Console' in html
    assert 'Event Gate' in html
    assert 'Active Symposium' in html
    assert 'CS-TKT-VIEW-1' in html
    assert 'Maya Roy' in html
    assert 'gate-stat-checked' in html
    assert 'gate-stat-remaining' in html
    assert 'gate-stat-rejected' in html
    assert 'Verify Ticket' in html


def test_gate_verification_console_kpi_stats_and_audit_logging(client, db):
    """Verify Gate Verification Console calculates live KPIs and tracks failed attempts in audit log."""
    create_user(db, 'gate_admin_kpi', 'Administrator')
    login(client, 'gate_admin_kpi')

    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO events (title, event_date, event_time, venue, capacity, member_price, non_member_price, status)
        VALUES ('Design Sprint 2026', '2026-11-20', '11:00', 'Studio 2', 50, 0, 100, 'Upcoming')
    """)
    ev_id = cursor.lastrowid

    # Add 2 tickets for Design Sprint: 1 already checked-in, 1 unchecked
    cursor.execute("""
        INSERT INTO tickets (ticket_ref, event_id, purchaser_name, purchaser_email, price_paid, payment_status, checked_in, check_in_time)
        VALUES ('CS-TKT-DS-01', ?, 'Rina Sen', 'rina@example.com', 100, 'Confirmed', 1, '2026-10-10 10:00:00')
    """, (ev_id,))
    cursor.execute("""
        INSERT INTO tickets (ticket_ref, event_id, purchaser_name, purchaser_email, price_paid, payment_status, checked_in)
        VALUES ('CS-TKT-DS-02', ?, 'Kabir Das', 'kabir@example.com', 100, 'Confirmed', 0)
    """, (ev_id,))
    db.commit()

    # 1. Initial SSR stats for the event
    res_page = client.get(f'/tickets/checkin?event_id={ev_id}')
    assert res_page.status_code == 200
    page_html = res_page.data.decode('utf-8')
    assert 'id="gate-stat-checked">1</div>' in page_html
    assert 'id="gate-stat-remaining">1</div>' in page_html
    assert 'id="gate-stat-rejected">0</div>' in page_html

    # 2. Check-in Kabir Das (CS-TKT-DS-02) via API
    res_check = client.post('/api/tickets/checkin', json={
        'ticket_ref': 'CS-TKT-DS-02',
        'event_id': ev_id
    })
    assert res_check.status_code == 200
    data_check = res_check.get_json()
    assert data_check['success'] is True
    assert data_check['stats']['checked_in'] == 2
    assert data_check['stats']['remaining'] == 0
    assert data_check['stats']['rejected'] == 0

    # 3. Duplicate scan attempt for Kabir Das -> returns 400 and increments rejected count in stats
    res_dup = client.post('/api/tickets/checkin', json={
        'ticket_ref': 'CS-TKT-DS-02',
        'event_id': ev_id
    })
    assert res_dup.status_code == 400
    data_dup = res_dup.get_json()
    assert data_dup['success'] is False
    assert data_dup['stats']['checked_in'] == 2
    assert data_dup['stats']['remaining'] == 0
    assert data_dup['stats']['rejected'] == 1

    # 4. Invalid ticket scan -> increments rejected count to 2
    res_inv = client.post('/api/tickets/checkin', json={
        'ticket_ref': 'CS-TKT-FAKE-999',
        'event_id': ev_id
    })
    assert res_inv.status_code == 400
    data_inv = res_inv.get_json()
    assert data_inv['success'] is False
    assert data_inv['stats']['rejected'] == 2


