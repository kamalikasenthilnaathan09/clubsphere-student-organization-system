import pytest
from datetime import date, timedelta
from tests.conftest import create_user, login


def test_analytics_access_permissions(client, db):
    """
    Ensure Analytics is restricted to authorized roles only:
    - Administrator, Treasurer, Event Organizer: ALLOWED (200 OK)
    - Volunteer, Member: FORBIDDEN (Redirect with Access Denied)
    - Unauthenticated: FORBIDDEN (Redirect to Login)
    """
    create_user(db, 'admin_user', 'Administrator')
    create_user(db, 'treasurer_user', 'Treasurer')
    create_user(db, 'organizer_user', 'Event Organizer')
    create_user(db, 'volunteer_user', 'Volunteer')
    create_user(db, 'member_user', 'Member')

    # 1. Unauthenticated request
    res_anon = client.get('/analytics')
    assert res_anon.status_code == 302
    assert '/login' in res_anon.headers['Location']

    # 2. Member request -> Denied
    login(client, 'member_user')
    res_mem = client.get('/analytics', follow_redirects=True)
    assert res_mem.status_code == 200
    assert b"Access denied" in res_mem.data

    # 3. Volunteer request -> Denied
    login(client, 'volunteer_user')
    res_vol = client.get('/analytics', follow_redirects=True)
    assert res_vol.status_code == 200
    assert b"Access denied" in res_vol.data

    # 4. Event Organizer -> Allowed
    login(client, 'organizer_user')
    res_org = client.get('/analytics')
    assert res_org.status_code == 200
    assert b"Business Analytics" in res_org.data

    # 5. Treasurer -> Allowed
    login(client, 'treasurer_user')
    res_tre = client.get('/analytics')
    assert res_tre.status_code == 200
    assert b"Business Analytics" in res_tre.data

    # 6. Administrator -> Allowed
    login(client, 'admin_user')
    res_adm = client.get('/analytics')
    assert res_adm.status_code == 200
    assert b"Business Analytics" in res_adm.data


def test_analytics_empty_states(client, db):
    """
    Ensure Analytics renders cleanly without errors when database is empty.
    Checks helpful empty-state messages for ledger, events, and merchandise.
    """
    create_user(db, 'admin', 'Administrator')
    login(client, 'admin')

    res = client.get('/analytics')
    assert res.status_code == 200
    assert b"Business Analytics" in res.data
    assert b"No Ledger Transactions" in res.data
    assert b"No Events Found in Selected Period" in res.data
    assert b"No Merchandise Sales Recorded" in res.data
    assert b"Optimal Stock" in res.data
    assert b"0.0%" in res.data


def test_analytics_dynamic_calculations_and_reconciliation(client, db):
    """
    Test that Analytics calculations accurately reflect source records
    and reconcile with the financial ledger with zero double-counting.
    """
    create_user(db, 'admin', 'Administrator')
    login(client, 'admin')

    today = date.today().isoformat()
    future_expiry = (date.today() + timedelta(days=180)).isoformat()

    # 1. Add Member with partial payment
    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO members (member_code, full_name, email, join_date, expiry_date, membership_type, membership_fee, amount_paid, status)
        VALUES ('CS-MEM-99', 'Priya Sharma', 'priya@college.edu', ?, ?, 'Annual', 800.0, 500.0, 'Active')
    """, (today, future_expiry))
    mem_id = cursor.lastrowid

    # Post membership payment to ledger
    cursor.execute("""
        INSERT INTO financial_transactions (transaction_type, category, amount, description, source_type, source_id, transaction_date)
        VALUES ('Income', 'Membership Fee', 500.0, 'Dues payment for Priya', 'membership_payment', ?, ?)
    """, (mem_id, today))

    # 2. Add Event with 2 tickets (1 checked in, 1 not)
    cursor.execute("""
        INSERT INTO events (title, event_date, event_time, venue, capacity, member_price, non_member_price, status)
        VALUES ('AI Research Symposium', ?, '14:00', 'Seminar Hall', 60, 150.0, 200.0, 'Upcoming')
    """, (today,))
    event_id = cursor.lastrowid

    # Ticket 1 (Checked in)
    cursor.execute("""
        INSERT INTO tickets (ticket_ref, event_id, purchaser_name, purchaser_email, price_paid, payment_status, checked_in)
        VALUES ('CS-TKT-AN-1', ?, 'Rohan Verma', 'rohan@college.edu', 150.0, 'Confirmed', 1)
    """, (event_id,))
    # Ticket 2 (Not checked in)
    cursor.execute("""
        INSERT INTO tickets (ticket_ref, event_id, purchaser_name, purchaser_email, price_paid, payment_status, checked_in)
        VALUES ('CS-TKT-AN-2', ?, 'Ananya Sen', 'ananya@college.edu', 150.0, 'Confirmed', 0)
    """, (event_id,))

    # Post ticket sales to ledger (₹300.00 total)
    cursor.execute("""
        INSERT INTO financial_transactions (transaction_type, category, amount, description, source_type, source_id, transaction_date)
        VALUES ('Income', 'Event Ticket Sales', 300.0, 'Tickets for Symposium', 'ticket_sale', ?, ?)
    """, (event_id, today))

    # 3. Add Merchandise Item, Variant, and Order
    cursor.execute("INSERT INTO merchandise_items (name, category, base_price) VALUES ('Club Hoodie', 'Apparel', 800.0)")
    item_id = cursor.lastrowid
    cursor.execute("""
        INSERT INTO merchandise_variants (item_id, size, sku, stock_quantity, low_stock_threshold)
        VALUES (?, 'L', 'HOODIE-L', 3, 5)
    """, (item_id,))
    var_id = cursor.lastrowid

    cursor.execute("""
        INSERT INTO merchandise_orders (order_ref, customer_name, customer_email, total_amount, payment_status)
        VALUES ('ORD-AN-01', 'Arjun Das', 'arjun@college.edu', 800.0, 'Paid')
    """)
    order_id = cursor.lastrowid

    cursor.execute("""
        INSERT INTO merchandise_order_items (order_id, variant_id, quantity, unit_price, subtotal)
        VALUES (?, ?, 1, 800.0, 800.0)
    """, (order_id, var_id))

    # Post merchandise to ledger
    cursor.execute("""
        INSERT INTO financial_transactions (transaction_type, category, amount, description, source_type, source_id, transaction_date)
        VALUES ('Income', 'Merchandise Sales', 800.0, 'Hoodie order ORD-AN-01', 'merchandise_order', ?, ?)
    """, (order_id, today))

    # 4. Add Paid Expense to ledger
    cursor.execute("""
        INSERT INTO expense_requests (title, category, amount, requested_by, description, status)
        VALUES ('Symposium Banners', 'Printing', 400.0, 1, 'Event banners', 'Paid')
    """)
    exp_id = cursor.lastrowid

    cursor.execute("""
        INSERT INTO financial_transactions (transaction_type, category, amount, description, source_type, source_id, transaction_date)
        VALUES ('Expense', 'Printing & Stationery', 400.0, 'Banners for Symposium', 'expense_request', ?, ?)
    """, (exp_id, today))

    db.commit()

    # Total Income = 500 (dues) + 300 (tickets) + 800 (merch) = 1,600.00
    # Paid Expenses = 400.00
    # Net Cash = 1,200.00
    # Tickets Sold = 2, Attendees = 1, Attendance Rate = 50.0%
    # Outstanding Dues = 800 - 500 = 300.00

    res = client.get('/analytics')
    assert res.status_code == 200

    # Financial Reconciliation Check
    assert b"1,600.00" in res.data  # Total Income
    assert b"400.00" in res.data    # Paid Expenses
    assert b"1,200.00" in res.data  # Net Cash Flow

    # Event Attendance Check
    assert b"AI Research Symposium" in res.data
    assert b"50.0%" in res.data     # 1 of 2 attended = 50.0%
    assert b"300.00" in res.data    # Event ticket revenue

    # Merchandise & Low Stock Check
    assert b"Club Hoodie" in res.data
    assert b"HOODIE-L" in res.data
    assert b"Low Stock" in res.data  # stock 3 <= threshold 5

    # Membership Check
    assert b"300.00" in res.data    # Pending dues


def test_analytics_date_range_filtering(client, db):
    """
    Test date-range filtering on financial ledger, events, and merchandise.
    Transactions outside the filter window must be excluded.
    """
    create_user(db, 'admin', 'Administrator')
    login(client, 'admin')

    cursor = db.cursor()

    # January 2026 transaction
    cursor.execute("""
        INSERT INTO financial_transactions (transaction_type, category, amount, description, source_type, transaction_date)
        VALUES ('Income', 'Sponsorship', 10000.0, 'Annual Sponsor', 'manual_income', '2026-01-15')
    """)

    # July 2026 transaction
    cursor.execute("""
        INSERT INTO financial_transactions (transaction_type, category, amount, description, source_type, transaction_date)
        VALUES ('Income', 'Sponsorship', 5000.0, 'Mid-Year Sponsor', 'manual_income', '2026-07-20')
    """)

    # January 2026 Event
    cursor.execute("""
        INSERT INTO events (title, event_date, event_time, venue, capacity, status)
        VALUES ('Winter Bootcamp', '2026-01-20', '09:00', 'Lab 1', 40, 'Completed')
    """)

    # July 2026 Event
    cursor.execute("""
        INSERT INTO events (title, event_date, event_time, venue, capacity, status)
        VALUES ('Summer Hackathon', '2026-07-25', '09:00', 'Main Hall', 80, 'Upcoming')
    """)

    db.commit()

    # 1. All-time view: Total Income = 15,000.00, both events present
    res_all = client.get('/analytics')
    assert res_all.status_code == 200
    assert b"15,000.00" in res_all.data
    assert b"Winter Bootcamp" in res_all.data
    assert b"Summer Hackathon" in res_all.data

    # 2. Filter for July only: Income = 5,000.00, only Summer Hackathon present
    res_july = client.get('/analytics?start_date=2026-07-01&end_date=2026-07-31')
    assert res_july.status_code == 200
    assert b"5,000.00" in res_july.data
    assert b"10,000.00" not in res_july.data
    assert b"Summer Hackathon" in res_july.data
    assert b"Winter Bootcamp" not in res_july.data
    assert b"Filtered Period Active" in res_july.data

    # 3. Filter for window with zero records: Income = 0.00, empty states present
    res_none = client.get('/analytics?start_date=2025-05-01&end_date=2025-05-31')
    assert res_none.status_code == 200
    assert b"No Ledger Transactions" in res_none.data
    assert b"No Events Found in Selected Period" in res_none.data
    assert b"0.00" in res_none.data


def test_analytics_charts_payload_and_reconciliation(client, db):
    """
    Test that the 4 charts receive accurate, reconciled JSON payloads:
    1. Financial performance monthly aggregation equals KPI totals without double-counting
    2. Event attendance turnout and capacity calculations
    3. Membership health real statuses
    4. Merchandise performance strictly excludes non-paid orders
    """
    import json
    import re
    from datetime import date, timedelta

    create_user(db, 'admin', 'Administrator')
    login(client, 'admin')

    today = date.today().isoformat()
    future_date = (date.today() + timedelta(days=90)).isoformat()
    cursor = db.cursor()

    # Financial transactions across two months (e.g. 2026-06 and 2026-07)
    cursor.execute("""
        INSERT INTO financial_transactions (transaction_type, category, amount, description, source_type, transaction_date)
        VALUES ('Income', 'Sponsorship', 2500.0, 'June Sponsor', 'manual', '2026-06-10')
    """)
    cursor.execute("""
        INSERT INTO financial_transactions (transaction_type, category, amount, description, source_type, transaction_date)
        VALUES ('Expense', 'Equipment', 700.0, 'June Cables', 'manual', '2026-06-15')
    """)
    cursor.execute("""
        INSERT INTO financial_transactions (transaction_type, category, amount, description, source_type, transaction_date)
        VALUES ('Income', 'Ticket Sales', 1200.0, 'July Tickets', 'manual', '2026-07-05')
    """)
    cursor.execute("""
        INSERT INTO financial_transactions (transaction_type, category, amount, description, source_type, transaction_date)
        VALUES ('Expense', 'Refreshments', 400.0, 'July Snacks', 'manual', '2026-07-08')
    """)

    # Events: 1 completed with attendance, 1 upcoming with no checkins
    cursor.execute("""
        INSERT INTO events (title, event_date, event_time, venue, capacity, status)
        VALUES ('Annual Hackathon', '2026-06-20', '10:00', 'Hall A', 100, 'Completed')
    """)
    ev1_id = cursor.lastrowid
    cursor.execute("""
        INSERT INTO tickets (ticket_ref, event_id, purchaser_name, purchaser_email, price_paid, payment_status, checked_in)
        VALUES ('TKT-HACK-1', ?, 'Dev One', 'dev1@test.com', 200.0, 'Confirmed', 1)
    """, (ev1_id,))
    cursor.execute("""
        INSERT INTO tickets (ticket_ref, event_id, purchaser_name, purchaser_email, price_paid, payment_status, checked_in)
        VALUES ('TKT-HACK-2', ?, 'Dev Two', 'dev2@test.com', 200.0, 'Confirmed', 0)
    """, (ev1_id,))

    # Members: Active, Expired, Pending
    cursor.execute("""
        INSERT INTO members (member_code, full_name, email, join_date, expiry_date, membership_type, membership_fee, amount_paid, status)
        VALUES ('M-01', 'Alice', 'alice@test.com', '2026-06-01', ?, 'Annual', 500.0, 500.0, 'Active')
    """, (future_date,))
    cursor.execute("""
        INSERT INTO members (member_code, full_name, email, join_date, expiry_date, membership_type, membership_fee, amount_paid, status)
        VALUES ('M-02', 'Bob', 'bob@test.com', '2026-06-01', '2026-06-30', 'Annual', 500.0, 500.0, 'Expired')
    """)
    cursor.execute("""
        INSERT INTO members (member_code, full_name, email, join_date, expiry_date, membership_type, membership_fee, amount_paid, status)
        VALUES ('M-03', 'Charlie', 'charlie@test.com', '2026-07-01', ?, 'Annual', 500.0, 0.0, 'Pending')
    """, (future_date,))

    # Merchandise: 1 Paid order and 1 Cancelled/Pending order (must be excluded)
    cursor.execute("INSERT INTO merchandise_items (name, category, base_price) VALUES ('Polo Shirt', 'Apparel', 600.0)")
    shirt_id = cursor.lastrowid
    cursor.execute("INSERT INTO merchandise_variants (item_id, size, sku, stock_quantity, low_stock_threshold) VALUES (?, 'M', 'POLO-M', 10, 2)", (shirt_id,))
    v_id = cursor.lastrowid

    # Paid order (created in June 2026)
    cursor.execute("""
        INSERT INTO merchandise_orders (order_ref, customer_name, customer_email, total_amount, payment_status, created_at)
        VALUES ('ORD-PAID-1', 'Buyer One', 'b1@test.com', 1200.0, 'Paid', '2026-06-25 14:00:00')
    """)
    o_paid_id = cursor.lastrowid
    cursor.execute("INSERT INTO merchandise_order_items (order_id, variant_id, quantity, unit_price, subtotal) VALUES (?, ?, 2, 600.0, 1200.0)", (o_paid_id, v_id))

    # Pending/Unpaid order (must NOT be counted)
    cursor.execute("""
        INSERT INTO merchandise_orders (order_ref, customer_name, customer_email, total_amount, payment_status, created_at)
        VALUES ('ORD-UNPAID-1', 'Buyer Two', 'b2@test.com', 600.0, 'Pending', '2026-06-26 14:00:00')
    """)
    o_unpaid_id = cursor.lastrowid
    cursor.execute("INSERT INTO merchandise_order_items (order_id, variant_id, quantity, unit_price, subtotal) VALUES (?, ?, 1, 600.0, 600.0)", (o_unpaid_id, v_id))

    db.commit()

    res = client.get('/analytics')
    assert res.status_code == 200

    # Extract JSON payload from script tag
    match = re.search(r'<script id="analytics-chart-payload" type="application/json">\s*(\{.*?\})\s*</script>', res.data.decode('utf-8'), re.DOTALL)
    assert match is not None, "Chart payload JSON script tag not found"
    payload = json.loads(match.group(1))

    # 1. Monthly Financials Check
    fin = payload['financial']
    assert '2026-06' in fin['labels']
    assert '2026-07' in fin['labels']
    idx_jun = fin['labels'].index('2026-06')
    idx_jul = fin['labels'].index('2026-07')
    assert fin['income'][idx_jun] == 2500.0
    assert fin['expense'][idx_jun] == 700.0
    assert fin['net'][idx_jun] == 1800.0
    assert fin['income'][idx_jul] == 1200.0
    assert fin['expense'][idx_jul] == 400.0
    assert fin['net'][idx_jul] == 800.0
    # Total check
    assert sum(fin['income']) == 3700.0
    assert sum(fin['expense']) == 1100.0
    assert sum(fin['net']) == 2600.0

    # 2. Event Attendance Check
    ev = payload['events']
    assert 'Annual Hackathon' in ev['labels']
    idx_ev = ev['labels'].index('Annual Hackathon')
    assert ev['tickets_sold'][idx_ev] == 2
    assert ev['attendees'][idx_ev] == 1
    assert ev['attendance_rates'][idx_ev] == 50.0

    # 3. Membership Health Check
    mem = payload['membership']
    mem_map = dict(zip(mem['labels'], mem['counts']))
    assert mem_map.get('Active') == 1
    assert mem_map.get('Expired') == 1
    assert mem_map.get('Pending') == 1

    # 4. Merchandise Check (Strictly excludes non-paid)
    merch = payload['merchandise']
    assert 'Polo Shirt' in merch['labels']
    idx_m = merch['labels'].index('Polo Shirt')
    assert merch['units_sold'][idx_m] == 2  # Only 2 from paid order, 1 from unpaid excluded!
    assert merch['revenues'][idx_m] == 1200.0

    merch_trend = payload['merch_trend']
    assert '2026-06' in merch_trend['labels']
    idx_mt = merch_trend['labels'].index('2026-06')
    assert merch_trend['units_sold'][idx_mt] == 2
    assert merch_trend['revenues'][idx_mt] == 1200.0


def test_analytics_charts_date_filtering_and_empty_states(client, db):
    """
    Test that charts dynamically update when date filters are applied,
    and display empty states when no records exist.
    """
    import json
    import re

    create_user(db, 'admin', 'Administrator')
    login(client, 'admin')

    cursor = db.cursor()
    # Transaction in March 2026
    cursor.execute("""
        INSERT INTO financial_transactions (transaction_type, category, amount, description, source_type, transaction_date)
        VALUES ('Income', 'Donation', 5000.0, 'March Donation', 'manual', '2026-03-15')
    """)
    # Transaction in August 2026
    cursor.execute("""
        INSERT INTO financial_transactions (transaction_type, category, amount, description, source_type, transaction_date)
        VALUES ('Income', 'Grant', 10000.0, 'August Grant', 'manual', '2026-08-10')
    """)
    db.commit()

    # Filter for March 2026 only
    res_mar = client.get('/analytics?start_date=2026-03-01&end_date=2026-03-31')
    assert res_mar.status_code == 200
    match_mar = re.search(r'<script id="analytics-chart-payload" type="application/json">\s*(\{.*?\})\s*</script>', res_mar.data.decode('utf-8'), re.DOTALL)
    payload_mar = json.loads(match_mar.group(1))

    assert payload_mar['financial']['labels'] == ['2026-03']
    assert payload_mar['financial']['income'] == [5000.0]
    assert '2026-08' not in payload_mar['financial']['labels']

    # Filter for completely empty window (2024)
    res_empty = client.get('/analytics?start_date=2024-01-01&end_date=2024-01-31')
    assert res_empty.status_code == 200
    match_empty = re.search(r'<script id="analytics-chart-payload" type="application/json">\s*(\{.*?\})\s*</script>', res_empty.data.decode('utf-8'), re.DOTALL)
    payload_empty = json.loads(match_empty.group(1))

    assert payload_empty['financial']['labels'] == []
    assert payload_empty['events']['labels'] == []
    assert payload_empty['merchandise']['labels'] == []
    assert b"No Financial Ledger Data" in res_empty.data
    assert b"No Event Attendance Records" in res_empty.data
    assert b"No Paid Merchandise Orders" in res_empty.data


def test_analytics_redesigned_hierarchy_and_tabs(client, db):
    """
    Test the redesigned page structure:
    1. Primary 4-KPI row (Income, Expenses, Net Cash, Active Members)
    2. Prominent responsive chart grid (Financial, Events, Membership, Merchandise)
    3. Secondary metrics row (Ticket Sales, Turnout Rate, Merch Volume, Pending Dues)
    4. Tabbed details container with 6 tabs & collapsible expand-all toggle
    """
    create_user(db, 'admin', 'Administrator')
    login(client, 'admin')

    res = client.get('/analytics')
    assert res.status_code == 200
    html = res.data.decode('utf-8')

    # Primary 4 KPIs
    assert 'primary-kpis-grid' in html
    assert 'Recorded Income' in html
    assert 'Paid Expenses' in html
    assert 'Net Cash Flow' in html
    assert 'Active Members' in html

    # Prominent Chart Grid
    assert 'analytics-charts-grid' in html
    assert 'Monthly Financial Performance' in html
    assert 'Event Attendance &amp; Turnout' in html
    assert 'Membership Status Health' in html
    assert 'Merchandise Performance' in html

    # Secondary Metrics Row
    assert 'secondary-kpis-strip' in html
    assert 'Ticket Sales' in html
    assert 'Turnout Rate' in html
    assert 'Merch Volume' in html
    assert 'Pending Dues' in html

    # Tabbed Details Container
    assert 'details-section-card' in html
    assert 'details-tabs-nav' in html
    assert 'data-tab="tab-cashflow"' in html
    assert 'data-tab="tab-incomestreams"' in html
    assert 'data-tab="tab-events"' in html
    assert 'data-tab="tab-merchandise"' in html
    assert 'data-tab="tab-inventory"' in html
    assert 'data-tab="tab-membership"' in html

    # Tab Panes
    assert 'id="tab-cashflow"' in html
    assert 'id="tab-incomestreams"' in html
    assert 'id="tab-events"' in html
    assert 'id="tab-merchandise"' in html
    assert 'id="tab-inventory"' in html
    assert 'id="tab-membership"' in html

    # View Controls & Actions
    assert 'btnToggleAllDetails' in html
    assert 'focusDetailsTab' in html
    assert 'switchDetailsTab' in html
