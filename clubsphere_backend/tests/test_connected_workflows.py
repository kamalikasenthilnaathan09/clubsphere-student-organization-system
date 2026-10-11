import pytest
from datetime import date, timedelta
from tests.conftest import create_user, login
import seed_demo


def test_sequence_a_member_registration_payment_and_renewal(client, db):
    """
    Sequence A:
    Register a member -> record membership payment -> renew membership -> verify status and dates.
    """
    create_user(db, 'admin', 'Administrator')
    login(client, 'admin')

    today = date.today().isoformat()
    expiry_initial = (date.today() + timedelta(days=365)).isoformat()
    expiry_extended = (date.today() + timedelta(days=730)).isoformat()

    # 1. Register Member with partial fee payment
    res_reg = client.post('/members/new', data={
        'full_name': 'Kavya Sen',
        'email': 'kavya.sen@college.edu',
        'phone': '9876500001',
        'student_id': '1NT23CS099',
        'department': 'Computer Science',
        'join_date': today,
        'expiry_date': expiry_initial,
        'membership_type': 'Annual',
        'membership_fee': '600.00',
        'initial_payment': '400.00',
        'payment_method': 'UPI',
        'payment_ref': 'UPI-INIT-01'
    }, follow_redirects=True)
    assert res_reg.status_code == 200

    member = db.execute("SELECT * FROM members WHERE email = 'kavya.sen@college.edu'").fetchone()
    assert member is not None
    assert member['membership_fee'] == 600.0
    assert member['amount_paid'] == 400.0
    assert member['status'] == 'Active'

    # Verify initial payment in ledger
    ftx_init = db.execute("SELECT * FROM financial_transactions WHERE source_type = 'membership_payment'").fetchone()
    assert ftx_init['amount'] == 400.0

    # 2. Record remaining dues payment (₹200)
    res_pay = client.post(f'/members/{member["id"]}/pay', data={
        'amount': '200.00',
        'payment_method': 'Cash',
        'reference_no': 'CASH-REC-01'
    }, follow_redirects=True)
    assert res_pay.status_code == 200

    member_paid = db.execute("SELECT * FROM members WHERE id = ?", (member['id'],)).fetchone()
    assert member_paid['amount_paid'] == 600.0
    assert (member_paid['membership_fee'] - member_paid['amount_paid']) == 0.0

    # 3. Renew membership for next year (renewal fee: ₹600, payment: ₹600)
    res_renew = client.post(f'/members/{member["id"]}/renew', data={
        'new_expiry_date': expiry_extended,
        'renewal_fee': '600.00',
        'payment_amount': '600.00',
        'payment_method': 'UPI',
        'reference_no': 'UPI-RNW-01'
    }, follow_redirects=True)
    assert res_renew.status_code == 200

    member_renewed = db.execute("SELECT * FROM members WHERE id = ?", (member['id'],)).fetchone()
    assert member_renewed['expiry_date'] == expiry_extended
    assert member_renewed['membership_fee'] == 1200.0
    assert member_renewed['amount_paid'] == 1200.0
    assert member_renewed['status'] == 'Active'


def test_sequence_b_event_pricing_ticketing_and_attendance(client, db):
    """
    Sequence B:
    Create an event -> configure prices and capacity -> sell a ticket ->
    validate check-in -> verify remaining capacity, attendance, and revenue.
    """
    create_user(db, 'admin', 'Administrator')
    create_user(db, 'organizer', 'Event Organizer')
    create_user(db, 'volunteer', 'Volunteer')

    # 1. Organizer creates event (capacity 10, member price 50, non-member price 150)
    login(client, 'organizer')
    future_date = (date.today() + timedelta(days=20)).isoformat()
    client.post('/events/new', data={
        'title': 'Autonomous Drone Workshop',
        'description': 'Hands-on assembly of quadcopters',
        'event_date': future_date,
        'event_time': '10:00',
        'venue': 'Engineering Hall 3',
        'capacity': '10',
        'member_price': '50.00',
        'non_member_price': '150.00'
    }, follow_redirects=True)

    event = db.execute("SELECT * FROM events WHERE title = 'Autonomous Drone Workshop'").fetchone()
    assert event['capacity'] == 10

    # 2. Sell a non-member ticket
    res_sell = client.post(f'/events/{event["id"]}/sell', data={
        'purchaser_name': 'Aarav Patel',
        'purchaser_email': 'aarav@dronefan.com',
        'payment_method': 'UPI'
    }, follow_redirects=True)
    assert res_sell.status_code == 200

    ticket = db.execute("SELECT * FROM tickets WHERE event_id = ?", (event['id'],)).fetchone()
    assert ticket['price_paid'] == 150.0
    assert ticket['is_member_rate'] == 0
    assert ticket['checked_in'] == 0

    # Verify event revenue and remaining capacity before check-in
    ev_view_res = client.get(f'/events/{event["id"]}')
    assert b"150.00" in ev_view_res.data
    assert b"9" in ev_view_res.data  # 10 - 1 = 9 remaining

    # 3. Volunteer checks in attendee
    login(client, 'volunteer')
    checkin_res = client.post('/api/tickets/checkin', json={
        'ticket_ref': ticket['ticket_ref'],
        'event_id': event['id']
    })
    assert checkin_res.status_code == 200
    assert checkin_res.get_json()['success'] is True

    tkt_updated = db.execute("SELECT * FROM tickets WHERE id = ?", (ticket['id'],)).fetchone()
    assert tkt_updated['checked_in'] == 1
    assert tkt_updated['check_in_time'] is not None


def test_sequence_c_merchandise_variants_ordering_and_stock(client, db):
    """
    Sequence C:
    Create merchandise variants -> place an order -> verify order totals and stock deduction.
    """
    create_user(db, 'admin', 'Administrator')
    login(client, 'admin')

    # 1. Create product with sizes S (10), M (10), L (10), XL (10)
    client.post('/merchandise/new', data={
        'name': 'ClubSphere Varsity Jacket',
        'category': 'Apparel',
        'description': 'Wool and leather varsity jacket',
        'base_price': '1200.00',
        'qty_S': '10',
        'qty_M': '10',
        'qty_L': '10',
        'qty_XL': '10'
    }, follow_redirects=True)

    item = db.execute("SELECT * FROM merchandise_items WHERE name = 'ClubSphere Varsity Jacket'").fetchone()
    variant_l = db.execute("SELECT * FROM merchandise_variants WHERE item_id = ? AND size = 'L'", (item['id'],)).fetchone()
    assert variant_l['stock_quantity'] == 10

    # 2. Place order for 3 units of size L
    res_order = client.post('/merchandise/order', data={
        'customer_name': 'Megha Gupta',
        'customer_email': 'megha@example.com',
        'variant_id': str(variant_l['id']),
        'quantity': '3',
        'payment_method': 'UPI'
    }, follow_redirects=True)
    assert res_order.status_code == 200

    # 3. Verify stock deduction: 10 - 3 = 7
    var_after = db.execute("SELECT * FROM merchandise_variants WHERE id = ?", (variant_l['id'],)).fetchone()
    assert var_after['stock_quantity'] == 7

    # 4. Verify order total: 1200 * 3 = 3600
    order = db.execute("SELECT * FROM merchandise_orders WHERE customer_email = 'megha@example.com'").fetchone()
    assert order['total_amount'] == 3600.0

    # Verify ledger entry
    ftx = db.execute("SELECT * FROM financial_transactions WHERE source_type = 'merchandise_order'").fetchone()
    assert ftx['amount'] == 3600.0


def test_sequence_d_income_expense_and_ledger_reconciliation(client, db):
    """
    Sequence D:
    Record income and an expense -> verify ledger entries, total income, total expenses, and net balance.
    """
    create_user(db, 'admin', 'Administrator')
    create_user(db, 'treasurer', 'Treasurer')
    login(client, 'treasurer')

    today = date.today().isoformat()

    # 1. Record direct income of 20,000
    client.post('/finance/income/new', data={
        'category': 'Fundraising Income',
        'amount': '20000.00',
        'description': 'Annual Student Fest Stall Sales',
        'payment_method': 'Bank Transfer',
        'transaction_date': today
    }, follow_redirects=True)

    # 2. Submit, approve, and pay expense of 6,500
    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO expense_requests (title, category, amount, requested_by, description, status)
        VALUES ('Auditorium Banner & Stage Props', 'Decorations', 6500.00, 1, 'Event staging', 'Pending')
    """)
    exp_id = cursor.lastrowid
    db.commit()

    # Approve
    client.post(f'/expenses/{exp_id}/approve', follow_redirects=True)
    # Pay
    client.post(f'/expenses/{exp_id}/pay', data={
        'payment_method': 'Bank Transfer',
        'payment_ref': 'UTR-PROPS-01',
        'paid_date': today
    }, follow_redirects=True)

    # 3. Verify ledger calculation:
    # Income = 20,000
    # Expenses = 6,500
    # Net Balance = 13,500
    ledger_res = client.get('/finance')
    assert b"20,000.00" in ledger_res.data
    assert b"6,500.00" in ledger_res.data
    assert b"13,500.00" in ledger_res.data


def test_sequence_e_volunteer_task_assignment_and_lifecycle(client, db):
    """
    Sequence E:
    Create and assign a volunteer task -> update its status -> verify the change persists.
    """
    create_user(db, 'admin', 'Administrator')
    organizer_id = create_user(db, 'organizer', 'Event Organizer')
    volunteer_id = create_user(db, 'volunteer', 'Volunteer')

    # Organizer creates task
    login(client, 'organizer')
    res_tsk = client.post('/tasks/new', data={
        'title': 'Prepare Hackathon Badges',
        'description': 'Print and sort 100 name tags',
        'assigned_to': str(volunteer_id),
        'priority': 'High',
        'deadline': '2026-11-20'
    }, follow_redirects=True)
    assert res_tsk.status_code == 200

    task = db.execute("SELECT * FROM volunteer_tasks WHERE title = 'Prepare Hackathon Badges'").fetchone()
    assert task['status'] == 'Pending'
    assert task['assigned_to'] == volunteer_id

    # Volunteer updates status to Completed
    login(client, 'volunteer')
    res_update = client.post(f'/tasks/{task["id"]}/status', data={
        'status': 'Completed'
    }, follow_redirects=True)
    assert res_update.status_code == 200

    task_done = db.execute("SELECT * FROM volunteer_tasks WHERE id = ?", (task['id'],)).fetchone()
    assert task_done['status'] == 'Completed'


def test_sequence_f_announcement_publishing_and_audience_visibility(client, db):
    """
    Sequence F:
    Publish an announcement -> verify it appears for the intended audience.
    """
    create_user(db, 'admin', 'Administrator')
    create_user(db, 'organizer', 'Event Organizer')
    create_user(db, 'member1', 'Member')

    # Organizer posts Members-only announcement
    login(client, 'organizer')
    client.post('/announcements/new', data={
        'title': 'Internal Club Elections Announcement',
        'content': 'Nominations for Secretary and Treasurer open on Monday.',
        'audience': 'Members',
        'priority': 'Normal'
    }, follow_redirects=True)

    # Member logs in -> Sees the announcement
    login(client, 'member1')
    res_mem = client.get('/announcements')
    assert b"Internal Club Elections Announcement" in res_mem.data

    # Anonymous visitor cannot access
    client.get('/logout')
    res_anon = client.get('/announcements', follow_redirects=False)
    assert res_anon.status_code == 302
    assert '/login' in res_anon.headers['Location']


def test_demo_seeder_isolated_execution(tmp_path):
    """
    Verify seed_demo runs completely and reconciles in an isolated database without errors.
    """
    test_db = str(tmp_path / 'demo_test.db')
    seed_demo.seed_demo_database(test_db, verbose=False)

    conn = seed_demo.database.get_db(test_db)
    # Check members count
    mem_count = conn.execute("SELECT COUNT(*) AS count FROM members").fetchone()['count']
    assert mem_count == 4

    # Check events count
    ev_count = conn.execute("SELECT COUNT(*) AS count FROM events").fetchone()['count']
    assert ev_count == 3

    # Check tickets count
    tkt_count = conn.execute("SELECT COUNT(*) AS count FROM tickets").fetchone()['count']
    assert tkt_count == 5

    # Check financial ledger totals:
    income = conn.execute("SELECT SUM(amount) AS s FROM financial_transactions WHERE transaction_type = 'Income'").fetchone()['s']
    expense = conn.execute("SELECT SUM(amount) AS s FROM financial_transactions WHERE transaction_type = 'Expense'").fetchone()['s']
    # Total Income: 500+600(members) + 150+300+300+100(tickets) + 850+200(merch) + 15000(sponsorship) = 18000
    assert income == 18000.0
    # Paid Expenses: 3000
    assert expense == 3000.0
    conn.close()
