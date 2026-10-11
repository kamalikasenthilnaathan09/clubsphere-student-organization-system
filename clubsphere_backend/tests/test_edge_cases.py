import pytest
from datetime import date, timedelta
from tests.conftest import create_user, login


def test_deactivated_session_immediate_invalidation(client, db):
    """If an active user is deactivated by admin, their active session is invalidated on next request."""
    admin_id = create_user(db, 'admin', 'Administrator')
    user_id = create_user(db, 'volunteer1', 'Volunteer')

    # Log in as volunteer1
    login(client, 'volunteer1')
    res = client.get('/tasks')
    assert res.status_code == 200

    # Admin deactivates volunteer1
    db.execute("UPDATE users SET is_active = 0 WHERE id = ?", (user_id,))
    db.commit()

    # Next request from volunteer1 must be blocked and redirected to login
    res2 = client.get('/tasks', follow_redirects=True)
    assert b"deactivated" in res2.data.lower() or b"sign in" in res2.data.lower()
    # Confirm session is cleared
    with client.session_transaction() as sess:
        assert 'user_id' not in sess


def test_payment_cannot_exceed_dues(client, db):
    """Membership dues payment cannot exceed the remaining outstanding balance."""
    create_user(db, 'admin', 'Administrator')
    login(client, 'admin')

    today = date.today().isoformat()
    expiry = (date.today() + timedelta(days=365)).isoformat()

    # Member with fee 500, initial payment 300, remaining dues = 200
    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO members (member_code, full_name, email, join_date, expiry_date, membership_type, membership_fee, amount_paid, status)
        VALUES ('CS-MEM-DUES-1', 'Dues Student', 'dues@test.com', ?, ?, 'Annual', 500, 300, 'Active')
    """, (today, expiry))
    member_id = cursor.lastrowid
    db.commit()

    # Attempt to pay 300 (exceeds outstanding dues of 200) -> Rejected
    res = client.post(f'/members/{member_id}/pay', data={
        'amount': '300.00',
        'payment_method': 'Cash'
    }, follow_redirects=True)

    assert b"cannot exceed outstanding dues" in res.data.lower()

    # Ensure amount_paid did NOT increase
    member = db.execute("SELECT amount_paid FROM members WHERE id = ?", (member_id,)).fetchone()
    assert member['amount_paid'] == 300.0


def test_duplicate_dues_payment_prevention(client, db):
    """Prevent duplicate payment records on rapid duplicate submission."""
    create_user(db, 'admin', 'Administrator')
    login(client, 'admin')

    today = date.today().isoformat()
    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO members (member_code, full_name, email, join_date, expiry_date, membership_type, membership_fee, amount_paid, status)
        VALUES ('CS-MEM-DUPP', 'Dup Pay', 'dup@test.com', ?, ?, 'Annual', 500, 200, 'Active')
    """, (today, today))
    member_id = cursor.lastrowid
    db.commit()

    # Pay 100
    res1 = client.post(f'/members/{member_id}/pay', data={'amount': '100.00'}, follow_redirects=True)
    assert b"recorded successfully" in res1.data.lower()

    # Immediate second submission of 100
    res2 = client.post(f'/members/{member_id}/pay', data={'amount': '100.00'}, follow_redirects=True)
    assert b"duplicate" in res2.data.lower()

    # Only 1 payment record created
    pay_count = db.execute("SELECT COUNT(*) AS count FROM membership_payments WHERE member_id = ?", (member_id,)).fetchone()['count']
    assert pay_count == 1


def test_renewal_payment_cannot_exceed_fee(client, db):
    """Renewal payment amount cannot exceed renewal fee."""
    create_user(db, 'admin', 'Administrator')
    login(client, 'admin')

    today = date.today().isoformat()
    future = (date.today() + timedelta(days=100)).isoformat()
    new_future = (date.today() + timedelta(days=400)).isoformat()

    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO members (member_code, full_name, email, join_date, expiry_date, membership_type, membership_fee, amount_paid, status)
        VALUES ('CS-MEM-RNW', 'Renew User', 'rnw@test.com', ?, ?, 'Annual', 500, 500, 'Active')
    """, (today, future))
    member_id = cursor.lastrowid
    db.commit()

    # Renewal fee 300, payment amount 500 -> Rejected
    res = client.post(f'/members/{member_id}/renew', data={
        'new_expiry_date': new_future,
        'renewal_fee': '300.00',
        'payment_amount': '500.00'
    }, follow_redirects=True)

    assert b"cannot exceed the renewal fee" in res.data.lower()


def test_event_edit_validation(client, db):
    """Event edit must validate required fields."""
    create_user(db, 'admin', 'Administrator')
    login(client, 'admin')

    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO events (title, event_date, event_time, venue, capacity, member_price, non_member_price, status)
        VALUES ('Original Title', '2026-12-01', '10:00', 'Hall 1', 50, 0, 50, 'Upcoming')
    """)
    event_id = cursor.lastrowid
    db.commit()

    # Submit empty title in edit form
    res = client.post(f'/events/{event_id}/edit', data={
        'title': '',
        'event_date': '2026-12-01',
        'event_time': '10:00',
        'venue': 'Hall 1',
        'capacity': '50',
        'member_price': '0',
        'non_member_price': '50'
    }, follow_redirects=True)

    assert b"Event title is required" in res.data
    # Event title must remain unchanged
    ev = db.execute("SELECT title FROM events WHERE id = ?", (event_id,)).fetchone()
    assert ev['title'] == 'Original Title'


def test_duplicate_income_entry_prevention(client, db):
    """Prevent duplicate financial entries caused by repeated form submissions."""
    create_user(db, 'admin', 'Administrator')
    create_user(db, 'treasurer', 'Treasurer')
    login(client, 'treasurer')

    today = date.today().isoformat()
    # First submission
    res1 = client.post('/finance/income/new', data={
        'category': 'Donation',
        'amount': '5000.00',
        'description': 'Alumnus Gift for Lab Kits',
        'payment_method': 'Bank Transfer',
        'transaction_date': today
    }, follow_redirects=True)
    assert b"Recorded income" in res1.data

    # Repeated identical submission immediately
    res2 = client.post('/finance/income/new', data={
        'category': 'Donation',
        'amount': '5000.00',
        'description': 'Alumnus Gift for Lab Kits',
        'payment_method': 'Bank Transfer',
        'transaction_date': today
    }, follow_redirects=True)

    assert b"duplicate" in res2.data.lower()

    # Exactly 1 financial transaction should exist
    count = db.execute("SELECT COUNT(*) AS count FROM financial_transactions WHERE description = 'Alumnus Gift for Lab Kits'").fetchone()['count']
    assert count == 1


def test_duplicate_expense_request_prevention(client, db):
    """Prevent duplicate expense requests from repeated submissions."""
    create_user(db, 'admin', 'Administrator')
    login(client, 'admin')

    res1 = client.post('/expenses/new', data={
        'title': 'Projector Bulbs',
        'category': 'Equipment & Tech',
        'amount': '1200.00',
        'description': 'Replacement bulbs for Seminar Hall'
    }, follow_redirects=True)
    assert b"submitted for approval" in res1.data

    # Repeated submission
    res2 = client.post('/expenses/new', data={
        'title': 'Projector Bulbs',
        'category': 'Equipment & Tech',
        'amount': '1200.00',
        'description': 'Replacement bulbs for Seminar Hall'
    }, follow_redirects=True)
    assert b"duplicate" in res2.data.lower()

    count = db.execute("SELECT COUNT(*) AS count FROM expense_requests WHERE title = 'Projector Bulbs'").fetchone()['count']
    assert count == 1


def test_merchandise_order_member_linkage(client, db):
    """Merchandise order links member_id when customer email matches a registered member."""
    create_user(db, 'admin', 'Administrator')
    login(client, 'admin')

    today = date.today().isoformat()
    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO members (member_code, full_name, email, join_date, expiry_date, membership_type, membership_fee, amount_paid, status)
        VALUES ('CS-MEM-M1', 'Sam Member', 'sam@student.org', ?, ?, 'Annual', 500, 500, 'Active')
    """, (today, today))
    member_id = cursor.lastrowid

    cursor.execute("INSERT INTO merchandise_items (name, base_price) VALUES ('Polo Shirt', 600)")
    item_id = cursor.lastrowid
    cursor.execute("INSERT INTO merchandise_variants (item_id, size, sku, stock_quantity) VALUES (?, 'L', 'POLO-L', 10)", (item_id,))
    var_id = cursor.lastrowid
    db.commit()

    # Order by member
    res = client.post('/merchandise/order', data={
        'customer_name': 'Sam Member',
        'customer_email': 'sam@student.org',
        'variant_id': str(var_id),
        'quantity': '1',
        'payment_method': 'UPI'
    }, follow_redirects=True)
    assert res.status_code == 200

    order = db.execute("SELECT * FROM merchandise_orders WHERE customer_email = 'sam@student.org'").fetchone()
    assert order is not None
    assert order['member_id'] == member_id
