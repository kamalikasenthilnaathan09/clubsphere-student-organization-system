import pytest
from datetime import date, timedelta
from tests.conftest import create_user, login


def test_dashboard_empty_states(client, db):
    """Dashboard handles empty database state gracefully without crashing."""
    create_user(db, 'admin', 'Administrator')
    login(client, 'admin')

    res = client.get('/dashboard')
    assert res.status_code == 200
    assert b"Organization Dashboard" in res.data
    assert b"No upcoming events scheduled" in res.data
    assert b"No financial transactions recorded yet" in res.data


def test_dashboard_dynamic_calculations_and_alerts(client, db):
    """Verify dynamic calculations and stock alerts on dashboard."""
    create_user(db, 'admin', 'Administrator')
    login(client, 'admin')

    today = date.today().isoformat()
    future_date = (date.today() + timedelta(days=30)).isoformat()
    future_expiry = (date.today() + timedelta(days=365)).isoformat()

    # 1. Add active member
    db.execute("""
        INSERT INTO members (member_code, full_name, email, join_date, expiry_date, membership_type, membership_fee, amount_paid, status)
        VALUES ('CS-MEM-10', 'Active Student', 'student@club.org', ?, ?, 'Annual', 500, 500, 'Active')
    """, (today, future_expiry))

    # 2. Add upcoming event with capacity 100
    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO events (title, event_date, event_time, venue, capacity, member_price, non_member_price, status)
        VALUES ('Mega Tech Fest', ?, '10:00', 'Auditorium', 100, 50, 100, 'Upcoming')
    """, (future_date,))
    event_id = cursor.lastrowid

    # 3. Add confirmed ticket
    cursor.execute("""
        INSERT INTO tickets (ticket_ref, event_id, purchaser_name, purchaser_email, price_paid, payment_status, checked_in)
        VALUES ('CS-TKT-DASH-1', ?, 'Ticket Buyer', 'buyer@mail.com', 100, 'Confirmed', 0)
    """, (event_id,))

    # 4. Add financial ledger income
    cursor.execute("""
        INSERT INTO financial_transactions (transaction_type, category, amount, description, source_type, payment_method, transaction_date)
        VALUES ('Income', 'Ticket Sale', 100, 'Ticket CS-TKT-DASH-1', 'ticket_sale', 'Cash', ?)
    """, (today,))

    # 5. Add pending expense
    cursor.execute("""
        INSERT INTO expense_requests (title, category, amount, requested_by, description, status)
        VALUES ('Stage Flowers', 'Decorations', 450, 1, 'Stage flowers', 'Pending')
    """)

    # 6. Add low stock merchandise variant (stock 2, threshold 5)
    cursor.execute("INSERT INTO merchandise_items (name, base_price) VALUES ('Official Club T-Shirt', 350)")
    item_id = cursor.lastrowid
    cursor.execute("""
        INSERT INTO merchandise_variants (item_id, size, sku, stock_quantity, low_stock_threshold)
        VALUES (?, 'L', 'TSHIRT-L', 2, 5)
    """, (item_id,))
    db.commit()

    # Visit dashboard
    res = client.get('/dashboard')
    assert res.status_code == 200

    # Verify dynamic metrics
    assert b"Active" in res.data
    assert b"Mega Tech Fest" in res.data
    assert b"100.00" in res.data  # Recorded Income
    assert b"Pending Review" in res.data  # Pending expense
    assert b"Merchandise Low Stock Alerts" in res.data  # Stock alert triggered
    assert b"TSHIRT-L" in res.data
    assert b"2 units" in res.data
