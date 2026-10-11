import pytest
from datetime import date, timedelta
from tests.conftest import create_user, login


def test_member_registration_and_duplicate_prevention(client, db):
    """Register member and prevent duplicates with same email."""
    create_user(db, 'admin', 'Administrator')
    login(client, 'admin')

    today = date.today().isoformat()
    expiry = (date.today() + timedelta(days=365)).isoformat()

    # 1. Register valid member
    res = client.post('/members/new', data={
        'full_name': 'Rohan Gupta',
        'email': 'rohan.g@example.com',
        'phone': '9876543210',
        'student_id': '1NT23CS101',
        'department': 'Computer Science',
        'join_date': today,
        'expiry_date': expiry,
        'membership_type': 'Annual',
        'membership_fee': '500.00',
        'initial_payment': '500.00',
        'payment_method': 'UPI',
        'payment_ref': 'UPI-REF-001'
    }, follow_redirects=True)

    assert res.status_code == 200
    assert b"registered successfully" in res.data

    member = db.execute("SELECT * FROM members WHERE email = 'rohan.g@example.com'").fetchone()
    assert member is not None
    assert member['full_name'] == 'Rohan Gupta'
    assert member['amount_paid'] == 500.0
    assert member['status'] == 'Active'

    # Check financial ledger entry was created for the initial payment
    ftx = db.execute("""
        SELECT * FROM financial_transactions
        WHERE source_type = 'membership_payment' AND transaction_type = 'Income'
    """).fetchone()
    assert ftx is not None
    assert ftx['amount'] == 500.0
    assert ftx['category'] == 'Membership Fee'

    # 2. Duplicate registration attempt with same email must be rejected
    dup_res = client.post('/members/new', data={
        'full_name': 'Rohan Imposter',
        'email': 'rohan.g@example.com',
        'join_date': today,
        'expiry_date': expiry,
        'membership_type': 'Annual',
        'membership_fee': '500.00',
        'initial_payment': '0'
    }, follow_redirects=True)

    assert b"already registered" in dup_res.data


def test_member_date_and_fee_validation(client, db):
    """Validation of invalid dates and excessive initial payments."""
    create_user(db, 'admin', 'Administrator')
    login(client, 'admin')

    today = date.today().isoformat()
    past_date = (date.today() - timedelta(days=10)).isoformat()

    # Expiry before join date
    res = client.post('/members/new', data={
        'full_name': 'Invalid Dates',
        'email': 'invalid.dates@example.com',
        'join_date': today,
        'expiry_date': past_date,
        'membership_type': 'Annual',
        'membership_fee': '500.00',
        'initial_payment': '500.00'
    }, follow_redirects=True)

    assert b"Expiry date cannot be earlier than the start date" in res.data

    # Initial payment exceeding total fee
    res_fee = client.post('/members/new', data={
        'full_name': 'Overpaying',
        'email': 'overpay@example.com',
        'join_date': today,
        'expiry_date': (date.today() + timedelta(days=365)).isoformat(),
        'membership_type': 'Annual',
        'membership_fee': '500.00',
        'initial_payment': '800.00'
    }, follow_redirects=True)

    assert b"Initial payment cannot exceed the total membership fee" in res_fee.data


def test_membership_dues_payment(client, db):
    """Track partial payments and record subsequent dues settlements."""
    create_user(db, 'admin', 'Administrator')
    login(client, 'admin')

    today = date.today().isoformat()
    expiry = (date.today() + timedelta(days=365)).isoformat()

    # Register member with partial payment (fee: 1000, paid: 400, dues: 600)
    client.post('/members/new', data={
        'full_name': 'Ananya Sen',
        'email': 'ananya@example.com',
        'join_date': today,
        'expiry_date': expiry,
        'membership_type': 'Annual',
        'membership_fee': '1000.00',
        'initial_payment': '400.00',
        'payment_method': 'Cash'
    }, follow_redirects=True)

    member = db.execute("SELECT * FROM members WHERE email = 'ananya@example.com'").fetchone()
    assert member['amount_paid'] == 400.0

    # Pay remaining dues of 600
    pay_res = client.post(f'/members/{member["id"]}/pay', data={
        'amount': '600.00',
        'payment_method': 'UPI',
        'reference_no': 'UPI-DUES-123'
    }, follow_redirects=True)

    assert pay_res.status_code == 200
    assert b"Payment of" in pay_res.data

    # Verify updated member status and total paid
    updated = db.execute("SELECT * FROM members WHERE id = ?", (member['id'],)).fetchone()
    assert updated['amount_paid'] == 1000.0
    assert updated['status'] == 'Active'


def test_membership_renewal(client, db):
    """Renewing expired or active membership extends expiry and tracks renewal fees."""
    create_user(db, 'admin', 'Administrator')
    login(client, 'admin')

    today = date.today().isoformat()
    past_expiry = (date.today() - timedelta(days=5)).isoformat()

    # Create expired member
    client.post('/members/new', data={
        'full_name': 'Karan Mehta',
        'email': 'karan@example.com',
        'join_date': (date.today() - timedelta(days=370)).isoformat(),
        'expiry_date': past_expiry,
        'membership_type': 'Annual',
        'membership_fee': '500.00',
        'initial_payment': '500.00'
    }, follow_redirects=True)

    member = db.execute("SELECT * FROM members WHERE email = 'karan@example.com'").fetchone()
    new_expiry = (date.today() + timedelta(days=360)).isoformat()

    # Renew membership
    renew_res = client.post(f'/members/{member["id"]}/renew', data={
        'new_expiry_date': new_expiry,
        'renewal_fee': '500.00',
        'payment_amount': '500.00',
        'payment_method': 'Bank Transfer',
        'reference_no': 'NEFT-RENEW-99'
    }, follow_redirects=True)

    assert renew_res.status_code == 200
    assert b"renewed until" in renew_res.data

    renewed = db.execute("SELECT * FROM members WHERE id = ?", (member['id'],)).fetchone()
    assert renewed['expiry_date'] == new_expiry
    assert renewed['membership_fee'] == 1000.0
    assert renewed['amount_paid'] == 1000.0
    assert renewed['status'] == 'Active'


def test_membership_directory_kpi_cards(client, db):
    """Verify live KPI summary cards reflect exact database calculations."""
    create_user(db, 'admin', 'Administrator')
    login(client, 'admin')

    today = date.today().isoformat()
    future = (date.today() + timedelta(days=180)).isoformat()
    past = (date.today() - timedelta(days=30)).isoformat()

    # Active member, fully paid
    db.execute("""
        INSERT INTO members (member_code, full_name, email, phone, student_id, department, join_date, expiry_date, membership_type, membership_fee, amount_paid, status)
        VALUES ('CS-MEM-KPI-01', 'Alice Green', 'alice@test.com', '1111111111', 'STU001', 'Computer Science', ?, ?, 'Annual', 500.0, 500.0, 'Active')
    """, (today, future))

    # Active member with pending dues (fee: 1000, paid: 400 -> dues: 600)
    db.execute("""
        INSERT INTO members (member_code, full_name, email, phone, student_id, department, join_date, expiry_date, membership_type, membership_fee, amount_paid, status)
        VALUES ('CS-MEM-KPI-02', 'Bob White', 'bob@test.com', '2222222222', 'STU002', 'Electrical', ?, ?, 'Semester', 1000.0, 400.0, 'Active')
    """, (today, future))

    # Expired member
    db.execute("""
        INSERT INTO members (member_code, full_name, email, phone, student_id, department, join_date, expiry_date, membership_type, membership_fee, amount_paid, status)
        VALUES ('CS-MEM-KPI-03', 'Charlie Brown', 'charlie@test.com', '3333333333', 'STU003', 'Mechanical', ?, ?, 'Annual', 500.0, 500.0, 'Expired')
    """, (past, past))
    db.commit()

    res = client.get('/members')
    assert res.status_code == 200
    html = res.data.decode('utf-8')

    # Verify KPI card headers
    assert "Total Members" in html
    assert "Active Members" in html
    assert "Outstanding Dues" in html
    assert "Expired Members" in html

    # Verify KPI values: Total = 3, Active = 2, Expired = 1, Outstanding Dues = 600.00
    assert ">3<" in html
    assert ">2<" in html
    assert ">1<" in html
    assert "600.00" in html


def test_membership_directory_card_and_table_view(client, db):
    """Verify card grid and table view structure, initials avatar, and action menu."""
    create_user(db, 'admin', 'Administrator')
    login(client, 'admin')

    today = date.today().isoformat()
    future = (date.today() + timedelta(days=200)).isoformat()

    db.execute("""
        INSERT INTO members (member_code, full_name, email, phone, student_id, department, join_date, expiry_date, membership_type, membership_fee, amount_paid, status)
        VALUES ('CS-MEM-CARD-01', 'Priya Sharma', 'priya.s@example.com', '9876543210', 'STU-PS-99', 'Biotechnology', ?, ?, 'Lifetime', 1200.0, 800.0, 'Active')
    """, (today, future))
    db.commit()

    res = client.get('/members')
    assert res.status_code == 200
    html = res.data.decode('utf-8')

    # Card view container & Table view container
    assert 'id="membersCardsView"' in html
    assert 'id="membersTableView"' in html

    # Initials avatar for 'Priya Sharma' -> 'PS'
    assert 'PS' in html
    assert 'Priya Sharma' in html
    assert 'CS-MEM-CARD-01' in html
    assert 'STU-PS-99' in html
    assert 'Biotechnology' in html
    assert 'Lifetime' in html
    assert 'btn-three-dots' in html
    assert 'View Profile' in html
    assert 'Edit Profile' in html
    assert 'Settle Dues' in html

    # Dues balance displayed
    assert "400.00" in html


def test_membership_directory_search_and_filters(client, db):
    """Verify search across name, ID, department, and status / type filter pills."""
    create_user(db, 'admin', 'Administrator')
    login(client, 'admin')

    today = date.today().isoformat()
    future = (date.today() + timedelta(days=100)).isoformat()
    past = (date.today() - timedelta(days=20)).isoformat()

    db.execute("""
        INSERT INTO members (member_code, full_name, email, phone, student_id, department, join_date, expiry_date, membership_type, membership_fee, amount_paid, status)
        VALUES ('CS-MEM-F1', 'Ananya Sen', 'ananya.s@example.com', '111', 'CSE-001', 'Computer Science', ?, ?, 'Annual', 500.0, 500.0, 'Active')
    """, (today, future))
    db.execute("""
        INSERT INTO members (member_code, full_name, email, phone, student_id, department, join_date, expiry_date, membership_type, membership_fee, amount_paid, status)
        VALUES ('CS-MEM-F2', 'Vikram Patel', 'vikram.p@example.com', '222', 'ECE-002', 'Electronics', ?, ?, 'Semester', 500.0, 500.0, 'Expired')
    """, (past, past))
    db.commit()

    # Search by department
    res_dept = client.get('/members?search=Computer+Science')
    assert res_dept.status_code == 200
    assert b"Ananya Sen" in res_dept.data
    assert b"Vikram Patel" not in res_dept.data

    # Search by student ID
    res_stu = client.get('/members?search=ECE-002')
    assert res_stu.status_code == 200
    assert b"Vikram Patel" in res_stu.data
    assert b"Ananya Sen" not in res_stu.data

    # Status filter: Active
    res_act = client.get('/members?status=Active')
    assert res_act.status_code == 200
    assert b"Ananya Sen" in res_act.data
    assert b"Vikram Patel" not in res_act.data

    # Status filter: Expired
    res_exp = client.get('/members?status=Expired')
    assert res_exp.status_code == 200
    assert b"Vikram Patel" in res_exp.data
    assert b"Ananya Sen" not in res_exp.data

    # Type filter: Semester
    res_type = client.get('/members?type=Semester')
    assert res_type.status_code == 200
    assert b"Vikram Patel" in res_type.data
    assert b"Ananya Sen" not in res_type.data

    # Search with no matching result
    res_none = client.get('/members?search=NonExistentQueryXYZ')
    assert res_none.status_code == 200
    assert b"No members found" in res_none.data
    assert b"No member records match your search query" in res_none.data


def test_membership_directory_role_permissions(client, db):
    """Verify role permissions for viewing the directory."""
    create_user(db, 'admin', 'Administrator')
    create_user(db, 'treasurer', 'Treasurer')
    create_user(db, 'organizer', 'Event Organizer')
    create_user(db, 'member_user', 'Member')

    # Administrator can access
    login(client, 'admin')
    res_admin = client.get('/members')
    assert res_admin.status_code == 200

    # Treasurer can access
    login(client, 'treasurer')
    res_treasurer = client.get('/members')
    assert res_treasurer.status_code == 200

    # Event Organizer can access
    login(client, 'organizer')
    res_organizer = client.get('/members')
    assert res_organizer.status_code == 200

    # Regular Member role is forbidden
    login(client, 'member_user', login_type='user')
    res_member = client.get('/members')
    assert res_member.status_code in (302, 403)

