import pytest
from datetime import date, timedelta
from tests.conftest import create_user, login


def test_member_registration_success_modal_and_failure(client, db):
    """
    Test Member Registration:
    - Success shows centered success modal with saved details (code, name, fee).
    - Page reload does NOT repeat the modal.
    - Validation failure shows error and does NOT show success modal.
    """
    create_user(db, 'admin_reg', 'Administrator')
    login(client, 'admin_reg')

    today = date.today().isoformat()
    expiry = (date.today() + timedelta(days=365)).isoformat()

    # 1. Successful member registration
    res = client.post('/members/new', data={
        'full_name': 'Meera Krishnan',
        'email': 'meera.k@example.com',
        'phone': '9876543219',
        'student_id': '1NT23CS999',
        'department': 'Computer Science',
        'join_date': today,
        'expiry_date': expiry,
        'membership_type': 'Annual',
        'membership_fee': '600.00',
        'initial_payment': '600.00',
        'payment_method': 'UPI',
        'payment_ref': 'UPI-REG-101'
    }, follow_redirects=True)

    assert res.status_code == 200
    html = res.data.decode('utf-8')

    # Verify modal exists on initial redirect render
    assert 'id="cs-universal-success-modal"' in html
    assert 'Member Registered Successfully!' in html
    assert 'Meera Krishnan' in html
    assert 'CS-MEM-' in html
    assert 'Computer Science' in html
    assert '600.00' in html
    assert 'REGISTRATION CONFIRMED' in html

    # 2. Refresh / reload the page -> modal must NOT repeat!
    member = db.execute("SELECT id FROM members WHERE email = 'meera.k@example.com'").fetchone()
    reload_res = client.get(f'/members/{member["id"]}')
    assert reload_res.status_code == 200
    reload_html = reload_res.data.decode('utf-8')
    assert 'id="cs-universal-success-modal"' not in reload_html

    # 3. Duplicate registration attempt -> failure, NO success modal
    dup_res = client.post('/members/new', data={
        'full_name': 'Meera Duplicate',
        'email': 'meera.k@example.com',
        'join_date': today,
        'expiry_date': expiry,
        'membership_type': 'Annual',
        'membership_fee': '600.00',
        'initial_payment': '0'
    }, follow_redirects=True)

    dup_html = dup_res.data.decode('utf-8')
    assert 'id="cs-universal-success-modal"' not in dup_html
    assert 'already registered' in dup_html


def test_dues_payment_success_modal_and_failure(client, db):
    """
    Test Membership Fee Payment:
    - Success shows modal with amount, member code, remaining dues.
    - Page reload does NOT repeat the modal.
    - Invalid payment shows error, does NOT show modal.
    - Duplicate payment within 10 seconds is prevented.
    """
    create_user(db, 'admin_pay', 'Administrator')
    login(client, 'admin_pay')

    today = date.today().isoformat()
    future = (date.today() + timedelta(days=180)).isoformat()

    # Create member with 500 outstanding dues (fee 1000, paid 500)
    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO members (member_code, full_name, email, phone, student_id, department, join_date, expiry_date, membership_type, membership_fee, amount_paid, status)
        VALUES ('CS-MEM-DUES-01', 'Rahul Deshmukh', 'rahul.d@example.com', '1234567890', 'STU-RD-01', 'Electronics', ?, ?, 'Annual', 1000.0, 500.0, 'Active')
    """, (today, future))
    member_id = cursor.lastrowid
    db.commit()

    # 1. Settle 300 of the 500 dues
    pay_res = client.post(f'/members/{member_id}/pay', data={
        'amount': '300.00',
        'payment_method': 'Bank Transfer',
        'reference_no': 'IMPS-REF-300'
    }, follow_redirects=True)

    assert pay_res.status_code == 200
    html = pay_res.data.decode('utf-8')
    assert 'id="cs-universal-success-modal"' in html
    assert 'Dues Payment Recorded!' in html
    assert 'Rahul Deshmukh' in html
    assert 'CS-MEM-DUES-01' in html
    assert '300.00' in html
    assert 'IMPS-REF-300' in html
    assert '200.00' in html  # Remaining dues: 1000 - 800 = 200

    # 2. Reload page -> modal must NOT repeat
    reload_res = client.get(f'/members/{member_id}')
    assert 'id="cs-universal-success-modal"' not in reload_res.data.decode('utf-8')

    # 3. Invalid payment (amount exceeds remaining dues of 200)
    over_res = client.post(f'/members/{member_id}/pay', data={
        'amount': '999.00',
        'payment_method': 'Cash'
    }, follow_redirects=True)

    over_html = over_res.data.decode('utf-8')
    assert 'id="cs-universal-success-modal"' not in over_html
    assert 'cannot exceed outstanding dues' in over_html

    # 4. Duplicate prevention test: attempting identical payment immediately
    # Remaining dues is 200. Pay 100 first:
    pay_dup1 = client.post(f'/members/{member_id}/pay', data={
        'amount': '100.00',
        'payment_method': 'Cash'
    }, follow_redirects=True)
    assert 'Dues Payment Recorded!' in pay_dup1.data.decode('utf-8')

    # Immediately submit the same payment again -> duplicate detected
    pay_dup2 = client.post(f'/members/{member_id}/pay', data={
        'amount': '100.00',
        'payment_method': 'Cash'
    }, follow_redirects=True)
    dup2_html = pay_dup2.data.decode('utf-8')
    assert 'Duplicate payment submission detected and ignored' in dup2_html
    assert 'id="cs-universal-success-modal"' not in dup2_html


def test_membership_renewal_success_modal_and_failure(client, db):
    """
    Test Membership Renewal:
    - Success shows modal with renewal fee, new expiry date.
    - Page reload does NOT repeat modal.
    - Invalid date shows error, does NOT show modal.
    """
    create_user(db, 'admin_renew', 'Administrator')
    login(client, 'admin_renew')

    today = date.today().isoformat()
    old_expiry = (date.today() + timedelta(days=10)).isoformat()

    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO members (member_code, full_name, email, phone, student_id, department, join_date, expiry_date, membership_type, membership_fee, amount_paid, status)
        VALUES ('CS-MEM-RN-01', 'Sunita Rao', 'sunita.r@example.com', '9898989898', 'STU-SR-01', 'Civil', ?, ?, 'Annual', 500.0, 500.0, 'Active')
    """, (today, old_expiry))
    member_id = cursor.lastrowid
    db.commit()

    # 1. Invalid renewal date (earlier than current expiry)
    bad_res = client.post(f'/members/{member_id}/renew', data={
        'new_expiry_date': (date.today() - timedelta(days=5)).isoformat(),
        'renewal_fee': '500.00',
        'payment_amount': '500.00'
    }, follow_redirects=True)

    bad_html = bad_res.data.decode('utf-8')
    assert 'id="cs-universal-success-modal"' not in bad_html
    assert 'New expiry date must be later than current expiry date' in bad_html

    # 2. Valid renewal
    new_expiry = (date.today() + timedelta(days=365)).isoformat()
    renew_res = client.post(f'/members/{member_id}/renew', data={
        'new_expiry_date': new_expiry,
        'renewal_fee': '500.00',
        'payment_amount': '500.00',
        'payment_method': 'UPI',
        'reference_no': 'UPI-RN-77'
    }, follow_redirects=True)

    assert renew_res.status_code == 200
    renew_html = renew_res.data.decode('utf-8')
    assert 'id="cs-universal-success-modal"' in renew_html
    assert 'Membership Renewed Successfully!' in renew_html
    assert 'Sunita Rao' in renew_html
    assert 'CS-MEM-RN-01' in renew_html
    assert 'UPI-RN-77' in renew_html

    # 3. Reload page -> modal does NOT repeat
    reload_res = client.get(f'/members/{member_id}')
    assert 'id="cs-universal-success-modal"' not in reload_res.data.decode('utf-8')


def test_event_ticket_registration_success_modal_and_failure(client, db):
    """
    Test Event Ticket Registration:
    - Success shows modal with event name, attendee, ticket reference, demo label, QR svg.
    - Page reload of badge does NOT repeat modal.
    - Overcapacity / failure does NOT show modal.
    """
    create_user(db, 'admin_event', 'Administrator')
    login(client, 'admin_event')

    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO events (title, event_date, event_time, venue, capacity, member_price, non_member_price, status)
        VALUES ('Robotics Hackathon 2026', '2026-11-15', '10:00', 'Tech Hall B', 1, 100, 200, 'Upcoming')
    """)
    event_id = cursor.lastrowid
    db.commit()

    # 1. Register for seat
    reg_res = client.post(f'/events/{event_id}/register', data={
        'attendee_name': 'Divya Nair',
        'attendee_email': 'divya.n@example.com',
        'attendee_phone': '9123456780',
        'payment_simulation': 'demo_success'
    }, follow_redirects=True)

    assert reg_res.status_code == 200
    reg_html = reg_res.data.decode('utf-8')
    assert 'id="cs-universal-success-modal"' in reg_html
    assert 'Payment Confirmed and Ticket Issued!' in reg_html
    assert 'Robotics Hackathon 2026' in reg_html
    assert 'Divya Nair' in reg_html
    assert 'CS-TKT-' in reg_html
    assert 'Simulated Demo Payment' in reg_html

    # 2. Reload badge page -> modal does NOT repeat
    ticket = db.execute("SELECT ticket_ref FROM tickets WHERE purchaser_email = 'divya.n@example.com'").fetchone()
    reload_res = client.get(f'/tickets/badge/{ticket["ticket_ref"]}')
    reload_html = reload_res.data.decode('utf-8')
    assert 'id="cs-universal-success-modal"' not in reload_html

    # 3. Capacity full attempt (capacity was 1, now full)
    full_res = client.post(f'/events/{event_id}/register', data={
        'attendee_name': 'Extra User',
        'attendee_email': 'extra@example.com',
        'payment_simulation': 'demo_success'
    }, follow_redirects=True)

    full_html = full_res.data.decode('utf-8')
    assert 'id="cs-universal-success-modal"' not in full_html
    assert 'completely full' in full_html

    # 4. Simulated failure parameter declined
    cursor.execute("UPDATE events SET capacity = 10 WHERE id = ?", (event_id,))
    db.commit()

    fail_res = client.post(f'/events/{event_id}/register', data={
        'attendee_name': 'Declined Test',
        'attendee_email': 'declined@example.com',
        'payment_simulation': 'simulate_failure'
    }, follow_redirects=True)

    fail_html = fail_res.data.decode('utf-8')
    assert 'id="cs-universal-success-modal"' not in fail_html
    assert 'Demo payment declined' in fail_html


def test_merchandise_order_success_modal_and_failure(client, db):
    """
    Test Merchandise Order:
    - Success shows modal with order ref, customer, item, quantity, total amount.
    - Page reload does NOT repeat modal.
    - Insufficient stock shows error, does NOT show modal.
    - Duplicate order within 10s is prevented.
    """
    create_user(db, 'admin_merch', 'Administrator')
    login(client, 'admin_merch')

    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO merchandise_items (name, category, description, base_price, is_active)
        VALUES ('ClubSphere Tech Hoodie', 'Apparel', 'Comfortable hoodie', 800.0, 1)
    """)
    item_id = cursor.lastrowid
    cursor.execute("""
        INSERT INTO merchandise_variants (item_id, size, sku, stock_quantity, low_stock_threshold)
        VALUES (?, 'L', 'HOOD-L-01', 5, 2)
    """, (item_id,))
    variant_id = cursor.lastrowid
    db.commit()

    # 1. Successful order
    order_res = client.post('/merchandise/order', data={
        'customer_name': 'Amit Verma',
        'customer_email': 'amit.v@example.com',
        'customer_phone': '9988776655',
        'variant_id': str(variant_id),
        'quantity': '2',
        'payment_method': 'UPI'
    }, follow_redirects=True)

    assert order_res.status_code == 200
    order_html = order_res.data.decode('utf-8')
    assert 'id="cs-universal-success-modal"' in order_html
    assert 'Merchandise Order Confirmed!' in order_html
    assert 'CS-ORD-' in order_html
    assert 'Amit Verma' in order_html
    assert 'ClubSphere Tech Hoodie' in order_html
    assert '1,600.00' in order_html  # 2 x 800 = 1600
    assert '3 units remaining' in order_html  # 5 - 2 = 3

    # 2. Reload merchandise page -> modal does NOT repeat
    reload_res = client.get('/merchandise')
    assert 'id="cs-universal-success-modal"' not in reload_res.data.decode('utf-8')

    # 3. Insufficient stock (3 units left, requested 10)
    stock_res = client.post('/merchandise/order', data={
        'customer_name': 'Greedy Buyer',
        'customer_email': 'greedy@example.com',
        'variant_id': str(variant_id),
        'quantity': '10',
        'payment_method': 'Cash'
    }, follow_redirects=True)

    stock_html = stock_res.data.decode('utf-8')
    assert 'id="cs-universal-success-modal"' not in stock_html
    assert 'Insufficient stock' in stock_html

    # 4. Duplicate prevention within 10s
    dup_res = client.post('/merchandise/order', data={
        'customer_name': 'Amit Verma',
        'customer_email': 'amit.v@example.com',
        'variant_id': str(variant_id),
        'quantity': '2',
        'payment_method': 'UPI'
    }, follow_redirects=True)

    dup_html = dup_res.data.decode('utf-8')
    assert 'Duplicate order submission detected and ignored' in dup_html
    assert 'id="cs-universal-success-modal"' not in dup_html
