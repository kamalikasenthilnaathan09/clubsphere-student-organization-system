import pytest
from datetime import date
from tests.conftest import create_user, login


def test_expense_lifecycle_and_payment(client, db):
    """
    Validate expense request -> approval -> payment lifecycle.
    Verify expenses hit the cash ledger ONLY when marked Paid.
    """
    create_user(db, 'admin', 'Administrator')
    create_user(db, 'organizer', 'Event Organizer')
    create_user(db, 'treasurer', 'Treasurer')

    # 1. Organizer submits expense request
    login(client, 'organizer')
    res_req = client.post('/expenses/new', data={
        'title': 'Sound System Rental',
        'category': 'Equipment & Tech',
        'amount': '2500.00',
        'description': 'Microphones and PA system for auditorium',
        'receipt_ref': 'BILL-PA-991'
    }, follow_redirects=True)

    assert res_req.status_code == 200
    assert b"submitted for approval" in res_req.data

    expense = db.execute("SELECT * FROM expense_requests WHERE title = 'Sound System Rental'").fetchone()
    assert expense is not None
    assert expense['status'] == 'Pending'
    assert expense['amount'] == 2500.0

    # Verify NOT in financial ledger yet!
    ftx_count = db.execute("SELECT COUNT(*) AS count FROM financial_transactions WHERE transaction_type = 'Expense'").fetchone()['count']
    assert ftx_count == 0

    # 2. Treasurer Approves Expense
    login(client, 'treasurer')
    res_appr = client.post(f'/expenses/{expense["id"]}/approve', follow_redirects=True)
    assert res_appr.status_code == 200
    assert b"approved" in res_appr.data

    updated_exp = db.execute("SELECT * FROM expense_requests WHERE id = ?", (expense['id'],)).fetchone()
    assert updated_exp['status'] == 'Approved'
    assert updated_exp['approved_by'] is not None

    # Still NOT in financial ledger!
    ftx_count_appr = db.execute("SELECT COUNT(*) AS count FROM financial_transactions WHERE transaction_type = 'Expense'").fetchone()['count']
    assert ftx_count_appr == 0

    # 3. Treasurer Pays Expense
    res_pay = client.post(f'/expenses/{expense["id"]}/pay', data={
        'payment_method': 'Bank Transfer',
        'payment_ref': 'UTR-NEFT-8899',
        'paid_date': date.today().isoformat()
    }, follow_redirects=True)

    assert res_pay.status_code == 200
    assert b"paid" in res_pay.data and b"posted to ledger" in res_pay.data

    paid_exp = db.execute("SELECT * FROM expense_requests WHERE id = ?", (expense['id'],)).fetchone()
    assert paid_exp['status'] == 'Paid'
    assert paid_exp['paid_by'] is not None
    assert paid_exp['payment_ref'] == 'UTR-NEFT-8899'

    # Now DOES appear in financial ledger!
    ftx_paid = db.execute("SELECT * FROM financial_transactions WHERE source_type = 'expense_request'").fetchone()
    assert ftx_paid is not None
    assert ftx_paid['amount'] == 2500.0
    assert ftx_paid['transaction_type'] == 'Expense'


def test_expense_rejection(client, db):
    """Rejected expenses cannot be approved or paid."""
    create_user(db, 'admin', 'Administrator')
    create_user(db, 'organizer', 'Event Organizer')
    create_user(db, 'treasurer', 'Treasurer')

    # Submit expense
    login(client, 'organizer')
    client.post('/expenses/new', data={
        'title': 'Fancy Catering Request',
        'category': 'Refreshments',
        'amount': '8000.00',
        'description': 'Luxury buffet'
    }, follow_redirects=True)

    expense = db.execute("SELECT * FROM expense_requests WHERE title = 'Fancy Catering Request'").fetchone()

    # Reject
    login(client, 'treasurer')
    res_rej = client.post(f'/expenses/{expense["id"]}/reject', data={
        'rejection_reason': 'Budget exceeded, not permitted'
    }, follow_redirects=True)

    assert b"rejected" in res_rej.data

    exp_rejected = db.execute("SELECT * FROM expense_requests WHERE id = ?", (expense['id'],)).fetchone()
    assert exp_rejected['status'] == 'Rejected'
    assert exp_rejected['rejection_reason'] == 'Budget exceeded, not permitted'

    # Attempting to pay rejected expense fails
    res_pay_fail = client.post(f'/expenses/{expense["id"]}/pay', data={
        'payment_method': 'Cash'
    }, follow_redirects=True)
    assert b"Only Approved expenses can be marked as Paid" in res_pay_fail.data


def test_financial_ledger_totals_and_no_double_counting(client, db):
    """
    Test direct income recording and financial balance calculation:
    Total Income, Total Expenses, Net Cash.
    """
    create_user(db, 'admin', 'Administrator')
    create_user(db, 'treasurer', 'Treasurer')
    login(client, 'treasurer')

    today = date.today().isoformat()

    # 1. Record direct fundraising income
    client.post('/finance/income/new', data={
        'category': 'Fundraising Income',
        'amount': '15000.00',
        'description': 'Alumni Annual Contribution Drive',
        'payment_method': 'Bank Transfer',
        'transaction_date': today
    }, follow_redirects=True)

    # 2. Record corporate sponsorship
    client.post('/finance/income/new', data={
        'category': 'Sponsorship',
        'amount': '25000.00',
        'description': 'Tech Corp Title Sponsor',
        'payment_method': 'Bank Transfer',
        'transaction_date': today
    }, follow_redirects=True)

    # 3. Create and pay an expense of 10000
    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO expense_requests (title, category, amount, requested_by, description, status)
        VALUES ('Auditorium Stage Decor', 'Decorations', 10000.00, 1, 'Stage banner', 'Approved')
    """)
    exp_id = cursor.lastrowid
    db.commit()

    client.post(f'/expenses/{exp_id}/pay', data={
        'payment_method': 'Bank Transfer',
        'payment_ref': 'UTR-10000',
        'paid_date': today
    }, follow_redirects=True)

    # Ledger totals:
    # Income: 15000 + 25000 = 40000
    # Expenses: 10000
    # Net: 30000
    res_ledger = client.get('/finance')
    assert res_ledger.status_code == 200
    assert b"40,000.00" in res_ledger.data
    assert b"10,000.00" in res_ledger.data
    assert b"30,000.00" in res_ledger.data


def test_expense_double_payment_prevention(client, db):
    """
    Ensure an expense cannot be paid twice and exactly one ledger entry is posted.
    """
    create_user(db, 'admin', 'Administrator')
    create_user(db, 'treasurer', 'Treasurer')
    login(client, 'treasurer')

    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO expense_requests (title, category, amount, requested_by, description, status)
        VALUES ('Brochure Printing', 'Marketing', 1500.00, 1, 'Event flyers', 'Approved')
    """)
    exp_id = cursor.lastrowid
    db.commit()

    # First payment succeeds
    res1 = client.post(f'/expenses/{exp_id}/pay', data={
        'payment_method': 'Bank Transfer',
        'payment_ref': 'UTR-PRINT-01',
        'paid_date': date.today().isoformat()
    }, follow_redirects=True)
    assert res1.status_code == 200
    assert b"posted to ledger" in res1.data

    # Check ledger has exactly 1 entry for this expense
    count1 = db.execute("SELECT COUNT(*) AS c FROM financial_transactions WHERE source_type = 'expense_request' AND source_id = ?", (exp_id,)).fetchone()['c']
    assert count1 == 1

    # Second payment attempt must be rejected
    res2 = client.post(f'/expenses/{exp_id}/pay', data={
        'payment_method': 'Bank Transfer',
        'payment_ref': 'UTR-PRINT-02',
        'paid_date': date.today().isoformat()
    }, follow_redirects=True)
    assert res2.status_code == 200
    assert b"Only Approved expenses can be marked as Paid" in res2.data or b"already been paid" in res2.data

    # Ledger must STILL have exactly 1 entry
    count2 = db.execute("SELECT COUNT(*) AS c FROM financial_transactions WHERE source_type = 'expense_request' AND source_id = ?", (exp_id,)).fetchone()['c']
    assert count2 == 1


def test_financial_ledger_ui_hierarchy_and_search(client, db):
    """
    Verify upgraded Financial Ledger UI hierarchy:
    - 4 KPI stat cards
    - Collapsible Event Financial Overview
    - General Financial Ledger with search & filtering
    - Direct income modal triggers intact
    """
    create_user(db, 'admin', 'Administrator')
    create_user(db, 'treasurer', 'Treasurer')
    login(client, 'treasurer')

    today = date.today().isoformat()

    # Seed transactions with different descriptions & categories
    client.post('/finance/income/new', data={
        'category': 'Sponsorship',
        'amount': '50000.00',
        'description': 'Global Tech Title Sponsorship 2026',
        'payment_method': 'Bank Transfer',
        'transaction_date': today
    }, follow_redirects=True)

    client.post('/finance/income/new', data={
        'category': 'Donation',
        'amount': '12000.00',
        'description': 'Alumni Patron Gift from Class of 2020',
        'payment_method': 'UPI',
        'transaction_date': today
    }, follow_redirects=True)

    # 1. Main ledger page renders properly
    res = client.get('/finance')
    assert res.status_code == 200
    html = res.data.decode('utf-8')

    # Header and Actions
    assert "Financial Ledger &amp; Cash Flow" in html or "Financial Ledger & Cash Flow" in html
    assert "Record Direct Income" in html
    assert "Manage Expenses" in html

    # 4 KPI cards
    assert "Total Recorded Income" in html
    assert "Total Paid Expenses" in html
    assert "Net Cash Movement" in html
    assert "Outstanding Member Dues" in html
    assert "62,000.00" in html

    # Collapsible Event Financial Overview
    assert "eventFinancialOverview" in html
    assert "<details" in html
    assert "Event Financial Overview" in html
    assert "View Breakdown" in html

    # General Financial Ledger table & search
    assert "General Financial Ledger" in html
    assert "ledgerFilterForm" in html
    assert "ledgerSearchInput" in html
    assert "record-income-modal" in html

    # 2. Search filtering via q
    res_search = client.get('/finance?q=Global+Tech')
    assert res_search.status_code == 200
    html_search = res_search.data.decode('utf-8')
    assert "Global Tech Title Sponsorship 2026" in html_search
    assert "Alumni Patron Gift" not in html_search

    # 3. Flow type filter
    res_income = client.get('/finance?type=Income')
    assert res_income.status_code == 200
    assert "62,000.00" in res_income.data.decode('utf-8')

    # 4. Search with no matches
    res_empty = client.get('/finance?q=NonExistentTransactionXYZ')
    assert res_empty.status_code == 200
    assert "No transactions found" in res_empty.data.decode('utf-8')


def test_expense_ui_hierarchy_filters_and_permissions(client, db):
    """
    Validate upgraded Expense Requests & Approvals page:
    - Header and actions
    - Lifecycle workflow guide
    - Status filter navigation tabs and record counts
    - 7-column table layout
    - Role-based action security (Admin/Treasurer can approve/reject, others cannot)
    """
    create_user(db, 'admin', 'Administrator')
    create_user(db, 'organizer', 'Event Organizer')
    create_user(db, 'treasurer', 'Treasurer')

    cursor = db.cursor()
    # 1. Seed sample expense requests with different statuses
    cursor.execute("""
        INSERT INTO expense_requests (title, category, amount, requested_by, description, receipt_ref, status)
        VALUES ('Stage PA Audio Gear', 'Equipment & Tech', 4500.00, 2, 'Speakers and mixer', 'REC-PA-101', 'Pending')
    """)
    cursor.execute("""
        INSERT INTO expense_requests (title, category, amount, requested_by, description, receipt_ref, status, approved_by)
        VALUES ('Brochure Prints', 'Marketing', 1200.00, 2, 'Event programs', 'EST-PRN-02', 'Approved', 1)
    """)
    cursor.execute("""
        INSERT INTO expense_requests (title, category, amount, requested_by, description, receipt_ref, status, approved_by, paid_by, payment_method)
        VALUES ('Snacks & Tea', 'Refreshments', 800.00, 2, 'Volunteer tea', 'RCPT-FOD-03', 'Paid', 1, 3, 'UPI')
    """)
    db.commit()

    # Test as Treasurer
    login(client, 'treasurer')
    res = client.get('/expenses')
    assert res.status_code == 200
    html = res.data.decode('utf-8')

    # Header and Actions
    assert "Expense Requests &amp; Approvals" in html or "Expense Requests & Approvals" in html
    assert "Review requests, track approvals, and manage reimbursements." in html
    assert "Submit Expense Request" in html
    assert "Financial Ledger" in html

    # Lifecycle workflow guide
    assert "Request Submitted" in html
    assert "Pending Review" in html
    assert "Approved / Rejected" in html
    assert "Disbursement (Paid)" in html

    # Status filter tabs and counts
    assert "All" in html
    assert "Pending Review" in html
    assert "Approved (Unpaid)" in html
    assert "Paid" in html
    assert "Rejected" in html

    # 7 Table columns
    assert "Expense" in html
    assert "Event" in html
    assert "Amount" in html
    assert "Requested By" in html
    assert "Receipt / Reference" in html
    assert "Status" in html
    assert "Actions" in html

    # Currency format check
    assert "4,500.00" in html
    assert "1,200.00" in html
    assert "800.00" in html

    # Actions for Treasurer on Pending (Approve & Reject) and Approved (Disburse / Pay)
    assert "Approve" in html
    assert "Reject" in html
    assert "Disburse / Pay" in html

    # Status filter query test
    res_paid = client.get('/expenses?status=Paid')
    assert res_paid.status_code == 200
    html_paid = res_paid.data.decode('utf-8')
    assert "Snacks &amp; Tea" in html_paid or "Snacks & Tea" in html_paid
    assert "Stage PA Audio Gear" not in html_paid

    # Test as Event Organizer (non-admin, non-treasurer)
    login(client, 'organizer')
    res_org = client.get('/expenses')
    assert res_org.status_code == 200
    html_org = res_org.data.decode('utf-8')

    # Organizer CAN submit expense requests
    assert "Submit Expense Request" in html_org
    # Organizer CANNOT see financial ledger link or approval/rejection actions
    assert "Financial Ledger" not in html_org
    assert ">Approve<" not in html_org
    assert ">Disburse / Pay<" not in html_org



