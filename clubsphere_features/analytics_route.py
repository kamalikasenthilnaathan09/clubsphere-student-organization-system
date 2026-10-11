# Analytics dashboard route extracted from app.py
@app.route('/analytics')
@login_required
@role_required('Administrator', 'Treasurer', 'Event Organizer')
def analytics_dashboard():
    """
    Business Analytics dashboard with financial ledger reconciliation,
    event ticketing performance, attendance rates, merchandise sales,
    inventory alerts, membership metrics, and accurate date-range filtering.
    """
    db = get_db()
    today_dt = date.today()
    today = today_dt.isoformat()
    today_minus_30 = (today_dt - timedelta(days=30)).isoformat()
    start_of_month = today_dt.replace(day=1).isoformat()
    start_of_year = today_dt.replace(month=1, day=1).isoformat()

    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()

    date_regex = r'^\d{4}-\d{2}-\d{2}$'
    if start_date and not re.match(date_regex, start_date):
        start_date = ''
    if end_date and not re.match(date_regex, end_date):
        end_date = ''

    if start_date and end_date and start_date > end_date:
        start_date, end_date = end_date, start_date

    is_date_filtered = bool(start_date or end_date)

    # 1. Financial Ledger Metrics (Single Source of Truth, No Double-Counting)
    fin_where = "1=1"
    fin_params = []
    if start_date:
        fin_where += " AND transaction_date >= ?"
        fin_params.append(start_date)
    if end_date:
        fin_where += " AND transaction_date <= ?"
        fin_params.append(end_date)

    income_row = db.execute(f"""
        SELECT COALESCE(SUM(amount), 0) AS total
        FROM financial_transactions
        WHERE transaction_type = 'Income' AND {fin_where}
    """, fin_params).fetchone()
    total_income = income_row['total'] if income_row else 0.0

    expense_row = db.execute(f"""
        SELECT COALESCE(SUM(amount), 0) AS total
        FROM financial_transactions
        WHERE transaction_type = 'Expense' AND {fin_where}
    """, fin_params).fetchone()
    paid_expenses = expense_row['total'] if expense_row else 0.0

    net_cash = total_income - paid_expenses

    income_categories = db.execute(f"""
        SELECT category, COALESCE(SUM(amount), 0) AS total, COUNT(*) as tx_count
        FROM financial_transactions
        WHERE transaction_type = 'Income' AND {fin_where}
        GROUP BY category
        ORDER BY total DESC
    """, fin_params).fetchall()

    expense_categories = db.execute(f"""
        SELECT category, COALESCE(SUM(amount), 0) AS total, COUNT(*) as tx_count
        FROM financial_transactions
        WHERE transaction_type = 'Expense' AND {fin_where}
        GROUP BY category
        ORDER BY total DESC
    """, fin_params).fetchall()

    # 2. Event Performance, Ticketing & Attendance
    event_where = "e.status != 'Cancelled'"
    event_params = []
    if start_date:
        event_where += " AND e.event_date >= ?"
        event_params.append(start_date)
    if end_date:
        event_where += " AND e.event_date <= ?"
        event_params.append(end_date)

    events_perf = db.execute(f"""
        SELECT e.id, e.title, e.event_date, e.capacity, e.status,
               COUNT(t.id) AS tickets_sold,
               COALESCE(SUM(t.price_paid), 0) AS revenue,
               COALESCE(SUM(CASE WHEN t.checked_in = 1 THEN 1 ELSE 0 END), 0) AS attendees
        FROM events e
        LEFT JOIN tickets t ON e.id = t.event_id AND t.payment_status = 'Confirmed'
        WHERE {event_where}
        GROUP BY e.id
        ORDER BY e.event_date DESC
    """, event_params).fetchall()

    events_analytics = []
    total_event_revenue = 0.0
    total_tickets_sold = 0
    total_attendees = 0
    for ep in events_perf:
        sold = ep['tickets_sold'] or 0
        att = ep['attendees'] or 0
        rev = ep['revenue'] or 0.0
        rate = round((att / sold * 100.0), 1) if sold > 0 else 0.0
        events_analytics.append({
            'id': ep['id'],
            'title': ep['title'],
            'event_date': ep['event_date'],
            'capacity': ep['capacity'],
            'status': ep['status'],
            'tickets_sold': sold,
            'revenue': rev,
            'attendees': att,
            'attendance_rate': rate
        })
        total_event_revenue += rev
        total_tickets_sold += sold
        total_attendees += att

    overall_attendance_rate = round((total_attendees / total_tickets_sold * 100.0), 1) if total_tickets_sold > 0 else 0.0

    # 3. Merchandise Sales & Inventory Alerts
    merch_where = "mo.payment_status = 'Paid'"
    merch_params = []
    if start_date:
        merch_where += " AND DATE(mo.created_at) >= ?"
        merch_params.append(start_date)
    if end_date:
        merch_where += " AND DATE(mo.created_at) <= ?"
        merch_params.append(end_date)

    merch_orders_summary = db.execute(f"""
        SELECT COUNT(id) AS total_orders,
               COALESCE(SUM(total_amount), 0) AS total_revenue
        FROM merchandise_orders mo
        WHERE {merch_where}
    """, merch_params).fetchone()
    total_merch_orders = merch_orders_summary['total_orders'] if merch_orders_summary else 0
    total_merch_revenue = merch_orders_summary['total_revenue'] if merch_orders_summary else 0.0

    merch_items_sales = db.execute(f"""
        SELECT m.name AS item_name, m.category,
               COALESCE(SUM(moi.quantity), 0) AS units_sold,
               COALESCE(SUM(moi.subtotal), 0) AS item_revenue
        FROM merchandise_order_items moi
        JOIN merchandise_orders mo ON moi.order_id = mo.id
        JOIN merchandise_variants mv ON moi.variant_id = mv.id
        JOIN merchandise_items m ON mv.item_id = m.id
        WHERE {merch_where}
        GROUP BY m.id
        ORDER BY item_revenue DESC
    """, merch_params).fetchall()
    total_units_sold = sum(r['units_sold'] for r in merch_items_sales)

    low_stock_items = db.execute("""
        SELECT v.id, v.size, v.sku, v.stock_quantity, v.low_stock_threshold,
               m.name AS item_name, m.category
        FROM merchandise_variants v
        JOIN merchandise_items m ON v.item_id = m.id
        WHERE v.stock_quantity <= v.low_stock_threshold AND m.is_active = 1
        ORDER BY v.stock_quantity ASC, m.name ASC
    """).fetchall()

    # 4. Membership Metrics
    total_members_count = db.execute("SELECT COUNT(*) AS count FROM members").fetchone()['count']

    mem_reg_where = "1=1"
    mem_reg_params = []
    if start_date:
        mem_reg_where += " AND join_date >= ?"
        mem_reg_params.append(start_date)
    if end_date:
        mem_reg_where += " AND join_date <= ?"
        mem_reg_params.append(end_date)

    new_members_count = db.execute(f"""
        SELECT COUNT(*) AS count FROM members WHERE {mem_reg_where}
    """, mem_reg_params).fetchone()['count']

    active_members_count = db.execute("""
        SELECT COUNT(*) AS count FROM members
        WHERE status = 'Active' AND expiry_date >= ?
    """, (today,)).fetchone()['count']

    dues_row = db.execute("""
        SELECT COALESCE(SUM(MAX(membership_fee - amount_paid, 0)), 0) AS dues
        FROM members
        WHERE status IN ('Active', 'Pending')
    """).fetchone()
    outstanding_dues = dues_row['dues'] if dues_row else 0.0

    dues_collected_row = db.execute(f"""
        SELECT COALESCE(SUM(amount), 0) AS total
        FROM financial_transactions
        WHERE source_type = 'membership_payment' AND {fin_where}
    """, fin_params).fetchone()
    dues_collected = dues_collected_row['total'] if dues_collected_row else 0.0

    renewal_where = "LOWER(notes) LIKE '%renewal%'"
    renewal_params = []
    if start_date:
        renewal_where += " AND payment_date >= ?"
        renewal_params.append(start_date)
    if end_date:
        renewal_where += " AND payment_date <= ?"
        renewal_params.append(end_date)

    renewals_row = db.execute(f"""
        SELECT COUNT(*) AS count
        FROM membership_payments
        WHERE {renewal_where}
    """, renewal_params).fetchone()
    renewals_count = renewals_row['count'] if renewals_row else 0

    # 5. Interactive Visualizations Data Aggregation
    # Graph 1: Monthly Financial Performance (reconciled with single source of truth)
    monthly_fin_rows = db.execute(f"""
        SELECT strftime('%Y-%m', transaction_date) AS month,
               COALESCE(SUM(CASE WHEN transaction_type = 'Income' THEN amount ELSE 0 END), 0) AS income,
               COALESCE(SUM(CASE WHEN transaction_type = 'Expense' THEN amount ELSE 0 END), 0) AS expense
        FROM financial_transactions
        WHERE {fin_where}
        GROUP BY month
        ORDER BY month ASC
    """, fin_params).fetchall()

    monthly_financial_data = {
        'labels': [],
        'income': [],
        'expense': [],
        'net': []
    }
    for r in monthly_fin_rows:
        if r['month']:
            monthly_financial_data['labels'].append(r['month'])
            inc = float(r['income'] or 0.0)
            exp = float(r['expense'] or 0.0)
            monthly_financial_data['income'].append(round(inc, 2))
            monthly_financial_data['expense'].append(round(exp, 2))
            monthly_financial_data['net'].append(round(inc - exp, 2))

    # Graph 2: Event Attendance & Turnout (from events_analytics, safe against zero-division)
    events_chart_data = {
        'labels': [e['title'] for e in events_analytics],
        'tickets_sold': [int(e['tickets_sold']) for e in events_analytics],
        'attendees': [int(e['attendees']) for e in events_analytics],
        'attendance_rates': [float(e['attendance_rate']) for e in events_analytics],
        'capacities': [int(e['capacity']) for e in events_analytics]
    }

    # Graph 3: Membership Status Distribution
    mem_status_rows = db.execute(f"""
        SELECT status, COUNT(*) AS count
        FROM members
        WHERE {mem_reg_where}
        GROUP BY status
        ORDER BY count DESC
    """, mem_reg_params).fetchall()

    membership_status_data = {
        'labels': [r['status'] for r in mem_status_rows if r['status']],
        'counts': [int(r['count']) for r in mem_status_rows if r['status']]
    }

    # Graph 4: Merchandise Performance (item sales & monthly trend, strictly paid)
    merch_chart_data = {
        'labels': [r['item_name'] for r in merch_items_sales],
        'categories': [r['category'] for r in merch_items_sales],
        'units_sold': [int(r['units_sold']) for r in merch_items_sales],
        'revenues': [round(float(r['item_revenue']), 2) for r in merch_items_sales]
    }

    merch_trend_rows = db.execute(f"""
        SELECT strftime('%Y-%m', mo.created_at) AS month,
               COALESCE(SUM(moi.quantity), 0) AS units_sold,
               COALESCE(SUM(moi.subtotal), 0) AS total_revenue
        FROM merchandise_order_items moi
        JOIN merchandise_orders mo ON moi.order_id = mo.id
        WHERE {merch_where}
        GROUP BY month
        ORDER BY month ASC
    """, merch_params).fetchall()

    merch_trend_data = {
        'labels': [r['month'] for r in merch_trend_rows if r['month']],
        'units_sold': [int(r['units_sold']) for r in merch_trend_rows if r['month']],
        'revenues': [round(float(r['total_revenue']), 2) for r in merch_trend_rows if r['month']]
    }

    analytics_charts = {
        'financial': monthly_financial_data,
        'events': events_chart_data,
        'membership': membership_status_data,
        'merchandise': merch_chart_data,
        'merch_trend': merch_trend_data
    }

    return render_template(
        'analytics/index.html',
        start_date=start_date,
        end_date=end_date,
        is_date_filtered=is_date_filtered,
        total_income=total_income,
        paid_expenses=paid_expenses,
        net_cash=net_cash,
        income_categories=income_categories,
        expense_categories=expense_categories,
        events_analytics=events_analytics,
        total_event_revenue=total_event_revenue,
        total_tickets_sold=total_tickets_sold,
        total_attendees=total_attendees,
        overall_attendance_rate=overall_attendance_rate,
        total_merch_orders=total_merch_orders,
        total_merch_revenue=total_merch_revenue,
        total_units_sold=total_units_sold,
        merch_items_sales=merch_items_sales,
        low_stock_items=low_stock_items,
        total_members_count=total_members_count,
        new_members_count=new_members_count,
        active_members_count=active_members_count,
        outstanding_dues=outstanding_dues,
        dues_collected=dues_collected,
        renewals_count=renewals_count,
        today=today,
        today_minus_30=today_minus_30,
        start_of_month=start_of_month,
        start_of_year=start_of_year,
        analytics_charts=analytics_charts
    )


# -------------------------------------------------------------------------
# MEMBERSHIP MANAGEMENT
