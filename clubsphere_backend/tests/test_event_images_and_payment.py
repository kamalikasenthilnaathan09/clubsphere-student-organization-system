import io
import pytest
from datetime import date, timedelta
from tests.conftest import create_user, login


def test_events_with_and_without_images(client, db):
    """
    Verify event listing renders both:
    1. Events with uploaded custom poster images.
    2. Events without posters using the default placeholder fallback.
    """
    create_user(db, 'admin_img', 'Administrator')
    login(client, 'admin_img')

    # Event 1: with poster image
    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO events (title, event_date, event_time, venue, capacity, member_price, non_member_price, status, poster_image)
        VALUES ('AI Hackathon', '2026-11-20', '09:00', 'Hall A', 100, 50, 150, 'Upcoming', 'images/posters/hackathon.svg')
    """)
    ev1_id = cursor.lastrowid

    # Event 2: without poster image (NULL)
    cursor.execute("""
        INSERT INTO events (title, event_date, event_time, venue, capacity, member_price, non_member_price, status, poster_image)
        VALUES ('Poetry Night', '2026-11-25', '18:00', 'Cafe Corner', 50, 0, 50, 'Upcoming', NULL)
    """)
    ev2_id = cursor.lastrowid
    db.commit()

    # 1. Test Card Grid View (default)
    res_cards = client.get('/events?view=cards')
    assert res_cards.status_code == 200
    html_cards = res_cards.data.decode('utf-8')
    assert 'AI Hackathon' in html_cards
    assert 'Poetry Night' in html_cards
    assert 'images/posters/hackathon.svg' in html_cards
    assert 'event-placeholder.svg' in html_cards
    assert 'Register Now' in html_cards
    assert 'View Details' in html_cards

    # 2. Test Table View
    res_table = client.get('/events?view=table')
    assert res_table.status_code == 200
    html_table = res_table.data.decode('utf-8')
    assert 'AI Hackathon' in html_table
    assert 'Poetry Night' in html_table


def test_authorized_and_unauthorized_image_uploads(client, db):
    """
    Verify RBAC on image uploads:
    - Administrator and Event Organizer can upload poster images.
    - Regular Member / Volunteer are rejected (HTTP 403 / redirect).
    """
    create_user(db, 'admin_upl', 'Administrator')
    create_user(db, 'organizer_upl', 'Event Organizer')
    create_user(db, 'member_upl', 'Member')

    fake_png = (io.BytesIO(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDRfakecontent'), 'poster.png')

    # 1. Organizer uploads event poster -> Allowed
    login(client, 'organizer_upl')
    res_org = client.post('/events/new', data={
        'title': 'Organizer Expo',
        'event_date': '2026-12-01',
        'event_time': '10:00',
        'venue': 'Tech Lab 1',
        'capacity': '60',
        'member_price': '0',
        'non_member_price': '100',
        'poster_image': fake_png
    }, content_type='multipart/form-data', follow_redirects=True)
    assert res_org.status_code == 200

    ev = db.execute("SELECT * FROM events WHERE title = 'Organizer Expo'").fetchone()
    assert ev is not None
    assert ev['poster_image'] is not None
    assert 'poster_' in ev['poster_image']

    # 2. Member tries to create event with poster -> Rejected (403 or redirect)
    login(client, 'member_upl')
    fake_png2 = (io.BytesIO(b'\x89PNG\r\n\x1a\nfake'), 'hack.png')
    res_mem = client.post('/events/new', data={
        'title': 'Hacker Event',
        'event_date': '2026-12-05',
        'event_time': '12:00',
        'venue': 'Room 1',
        'capacity': '10',
        'poster_image': fake_png2
    }, content_type='multipart/form-data', follow_redirects=True)

    # Member cannot create events
    ev_bad = db.execute("SELECT * FROM events WHERE title = 'Hacker Event'").fetchone()
    assert ev_bad is None


def test_image_file_type_and_size_validation(client, db):
    """
    Validate that invalid extensions (e.g. .exe, .sh) or oversized files are rejected.
    """
    create_user(db, 'admin_val', 'Administrator')
    login(client, 'admin_val')

    # 1. Invalid file extension (.sh) -> Rejected
    bad_file = (io.BytesIO(b'#!/bin/bash\necho bad'), 'script.sh')
    res_bad_ext = client.post('/events/new', data={
        'title': 'Malicious Event',
        'event_date': '2026-12-10',
        'event_time': '11:00',
        'venue': 'Room 2',
        'capacity': '20',
        'poster_image': bad_file
    }, content_type='multipart/form-data', follow_redirects=True)
    assert b"Invalid image format" in res_bad_ext.data

    # Confirm event was NOT created
    assert db.execute("SELECT * FROM events WHERE title = 'Malicious Event'").fetchone() is None

    # 2. Oversized file (> 5MB) -> Rejected
    oversized_data = b'A' * (6 * 1024 * 1024)
    oversized_file = (io.BytesIO(oversized_data), 'huge.png')
    res_huge = client.post('/events/new', data={
        'title': 'Huge Event',
        'event_date': '2026-12-11',
        'event_time': '11:00',
        'venue': 'Room 3',
        'capacity': '20',
        'poster_image': oversized_file
    }, content_type='multipart/form-data', follow_redirects=True)
    assert b"exceeds the 5MB limit" in res_huge.data
    assert db.execute("SELECT * FROM events WHERE title = 'Huge Event'").fetchone() is None


def test_successful_and_failed_demo_payments(client, db):
    """
    Verify Feature B:
    1. Successful demo payment creates confirmed ticket, QR code, payment ref, and ledger entry.
    2. Simulated payment decline correctly fails without issuing ticket or taking seat.
    """
    create_user(db, 'admin_pay', 'Administrator')
    member_user_id = create_user(db, 'student_pay', 'Member', full_name='Student Pay')

    # Create active member record for student_pay
    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO members (user_id, member_code, full_name, email, join_date, expiry_date, membership_type, membership_fee, amount_paid, status)
        VALUES (?, 'CS-MEM-P1', 'Student Pay', 'student_pay@college.edu', '2026-01-01', '2027-01-01', 'Annual', 500, 500, 'Active')
    """, (member_user_id,))

    cursor.execute("""
        INSERT INTO events (title, event_date, event_time, venue, capacity, member_price, non_member_price, status)
        VALUES ('Cyber Security Workshop', '2026-12-15', '14:00', 'Lab 4', 5, 40, 120, 'Upcoming')
    """)
    event_id = cursor.lastrowid
    db.commit()

    # Login as student_pay (Member)
    login(client, 'student_pay')

    # 1. Test simulated failure requested by test
    res_fail = client.post(f'/api/events/{event_id}/register', json={
        'attendee_name': 'Student Pay',
        'attendee_email': 'student_pay@college.edu',
        'payment_simulation': 'simulate_failure'
    })
    assert res_fail.status_code == 400
    data_fail = res_fail.get_json()
    assert data_fail['success'] is False
    assert 'declined' in data_fail['message'].lower()

    # Verify no tickets issued and capacity untouched
    sold_after_fail = db.execute("SELECT COUNT(*) AS count FROM tickets WHERE event_id = ?", (event_id,)).fetchone()['count']
    assert sold_after_fail == 0

    # 2. Test successful demo payment
    res_succ = client.post(f'/api/events/{event_id}/register', json={
        'attendee_name': 'Student Pay',
        'attendee_email': 'student_pay@college.edu',
        'attendee_phone': '9876543210',
        'payment_simulation': 'demo_success'
    })
    assert res_succ.status_code == 200
    data_succ = res_succ.get_json()
    assert data_succ['success'] is True
    tkt_data = data_succ['ticket']
    assert tkt_data['ticket_ref'].startswith('CS-TKT-')
    assert tkt_data['payment_ref'].startswith('DEMO-TXN-')
    assert tkt_data['status'] == 'Confirmed'
    assert tkt_data['amount'] == 40.0  # Member discount automatically verified on server!
    assert '<svg' in tkt_data['qr_svg']

    # Verify DB record
    tkt_db = db.execute("SELECT * FROM tickets WHERE ticket_ref = ?", (tkt_data['ticket_ref'],)).fetchone()
    assert tkt_db is not None
    assert tkt_db['price_paid'] == 40.0
    assert tkt_db['is_member_rate'] == 1
    assert tkt_db['payment_method'] == 'Demo Payment (Simulated)'
    assert tkt_db['payment_ref'] == tkt_data['payment_ref']

    # Verify Financial ledger entry
    fin = db.execute("SELECT * FROM financial_transactions WHERE source_id = ?", (tkt_db['id'],)).fetchone()
    assert fin is not None
    assert fin['amount'] == 40.0
    assert 'Demo Payment' in fin['description']


def test_duplicate_payment_prevention_and_overselling(client, db):
    """
    1. Verify capacity enforcement: cannot register when event is completely full.
    2. Verify idempotency replay returns existing booking without double issuing tickets.
    """
    create_user(db, 'admin_dup', 'Administrator')
    login(client, 'admin_dup')

    # Create event with capacity 1
    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO events (title, event_date, event_time, venue, capacity, member_price, non_member_price, status)
        VALUES ('Exclusive Masterclass', '2026-12-20', '15:00', 'Executive Boardroom', 1, 100, 200, 'Upcoming')
    """)
    event_id = cursor.lastrowid
    db.commit()

    # 1. Register attendee 1 with idempotency key
    idemp_key = "IDEMP-TEST-KEY-001"
    res1 = client.post(f'/api/events/{event_id}/register', json={
        'attendee_name': 'Attendee First',
        'attendee_email': 'first@domain.com',
        'payment_simulation': 'demo_success',
        'idempotency_key': idemp_key
    })
    assert res1.status_code == 200
    data1 = res1.get_json()
    first_ticket_ref = data1['ticket']['ticket_ref']

    # 2. Repeat request with same idempotency key (repeated callback / accidental double click)
    res_repeat = client.post(f'/api/events/{event_id}/register', json={
        'attendee_name': 'Attendee First',
        'attendee_email': 'first@domain.com',
        'payment_simulation': 'demo_success',
        'idempotency_key': idemp_key
    })
    assert res_repeat.status_code == 200
    data_rep = res_repeat.get_json()
    assert data_rep['ticket']['ticket_ref'] == first_ticket_ref

    # Confirm only 1 ticket in database
    tickets_count = db.execute("SELECT COUNT(*) AS count FROM tickets WHERE event_id = ?", (event_id,)).fetchone()['count']
    assert tickets_count == 1

    # 3. Attempt to register attendee 2 (event is full -> must be rejected)
    res_full = client.post(f'/api/events/{event_id}/register', json={
        'attendee_name': 'Attendee Second',
        'attendee_email': 'second@domain.com',
        'payment_simulation': 'demo_success'
    })
    assert res_full.status_code == 400
    assert 'completely full' in res_full.get_json()['message'].lower()


def test_download_ticket_and_view_pass(client, db):
    """
    Verify View Ticket (/tickets/badge/<ref>) and Download Ticket (/tickets/download/<ref>).
    """
    create_user(db, 'admin_down', 'Administrator')
    login(client, 'admin_down')

    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO events (title, event_date, event_time, venue, capacity, member_price, non_member_price, status)
        VALUES ('Spring Concert', '2026-12-22', '19:00', 'Amphitheatre', 50, 0, 50, 'Upcoming')
    """)
    event_id = cursor.lastrowid
    db.commit()

    # Book ticket
    reg_res = client.post(f'/api/events/{event_id}/register', json={
        'attendee_name': 'Rhea Kapoor',
        'attendee_email': 'rhea@domain.com',
        'payment_simulation': 'demo_success'
    })
    ticket_ref = reg_res.get_json()['ticket']['ticket_ref']

    # 1. View Ticket Badge
    badge_res = client.get(f'/tickets/badge/{ticket_ref}')
    assert badge_res.status_code == 200
    badge_html = badge_res.data.decode('utf-8')
    assert ticket_ref in badge_html
    assert 'Rhea Kapoor' in badge_html
    assert 'Spring Concert' in badge_html
    assert '<svg' in badge_html  # Embedded QR SVG

    # 2. Download Ticket file
    down_res = client.get(f'/tickets/download/{ticket_ref}')
    assert down_res.status_code == 200
    assert 'attachment;' in down_res.headers.get('Content-Disposition', '')
    down_html = down_res.data.decode('utf-8')
    assert ticket_ref in down_html
    assert 'Spring Concert' in down_html
    assert '<svg' in down_html
