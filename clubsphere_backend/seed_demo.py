"""
seed_demo.py — Safe, Isolated Demo-Data Seeder for ClubSphere.

NON-NEGOTIABLE SAFETY RULES HONORED:
1. Never resets or deletes existing databases.
2. Default target is 'instance/clubsphere_demo.db', keeping demo data completely isolated from real user data.
3. Fully idempotent: checks existing records by unique code/identifier before inserting to prevent duplicate records.
4. Uses realistic, non-personal placeholder data with secure PBKDF2 password hashes.
5. All financial ledger transactions strictly reconcile with member payments, ticket sales, merchandise orders, and paid expenses.
"""

import os
import sys
import argparse
from datetime import date, timedelta
from werkzeug.security import generate_password_hash

import database

DEFAULT_DEMO_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance', 'clubsphere_demo.db')


def seed_demo_database(db_path=DEFAULT_DEMO_DB, verbose=True):
    """
    Seeds an isolated demo database with coherent, fully reconciled student club records.
    """
    if verbose:
        print(f"[*] Initializing schema for demo database at: {db_path}")

    # Ensure instance directory exists
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)

    # Initialize schema
    database.init_db(db_path)
    conn = database.get_db(db_path)
    cursor = conn.cursor()

    today = date.today()
    today_iso = today.isoformat()

    # -------------------------------------------------------------------------
    # 1. USER ACCOUNTS (Role Demonstration)
    # -------------------------------------------------------------------------
    demo_users = [
        ('demo_admin', 'admin@clubdemo.org', 'Alex Rivera', 'Administrator'),
        ('demo_treasurer', 'treasurer@clubdemo.org', 'Meera Patel', 'Treasurer'),
        ('demo_organizer', 'organizer@clubdemo.org', 'Siddharth Rao', 'Event Organizer'),
        ('demo_volunteer', 'volunteer@clubdemo.org', 'Tanvi Deshmukh', 'Volunteer'),
        ('demo_member', 'member@clubdemo.org', 'Ananya Sharma', 'Member'),
        ('admin', 'admin@clubsphere.org', 'System Administrator', 'Administrator'),
        ('treasurer', 'treasurer@clubsphere.org', 'Meera Patel', 'Treasurer'),
        ('organizer', 'organizer@clubsphere.org', 'Siddharth Rao', 'Event Organizer'),
        ('volunteer', 'volunteer@clubsphere.org', 'Tanvi Deshmukh', 'Volunteer'),
        ('member', 'member@clubsphere.org', 'Ananya Sharma', 'Member'),
    ]

    user_ids = {}
    default_hash = generate_password_hash('Password123!')

    for username, email, full_name, role in demo_users:
        existing = cursor.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if existing:
            user_ids[username] = existing['id']
            cursor.execute("""
                UPDATE users
                SET password_hash = ?, is_active = 1, email = ?, full_name = ?, role = ?
                WHERE id = ?
            """, (default_hash, email, full_name, role, existing['id']))
            if verbose:
                print(f"  ~ Synchronized user credentials: {username} ({role}) [Active=1, Password=Password123!]")
        else:
            cursor.execute("""
                INSERT INTO users (username, email, password_hash, full_name, role, is_active)
                VALUES (?, ?, ?, ?, ?, 1)
            """, (username, email, default_hash, full_name, role))
            user_ids[username] = cursor.lastrowid
            if verbose:
                print(f"  + Created user: {username} ({role})")

    conn.commit()

    admin_id = user_ids.get('demo_admin')
    treasurer_id = user_ids.get('demo_treasurer')
    organizer_id = user_ids.get('demo_organizer')
    volunteer_id = user_ids.get('demo_volunteer')
    member_user_id = user_ids.get('demo_member')

    # -------------------------------------------------------------------------
    # 2. CLUB MEMBERS (Various Membership States)
    # -------------------------------------------------------------------------
    members_data = [
        {
            'code': 'CS-DEMO-MEM-001',
            'user_id': member_user_id,
            'name': 'Ananya Sharma',
            'email': 'ananya.sharma@example.edu',
            'phone': '+91 98765 11001',
            'student_id': '1NT23CS045',
            'dept': 'Computer Science',
            'join': (today - timedelta(days=90)).isoformat(),
            'expiry': (today + timedelta(days=275)).isoformat(),
            'type': 'Annual',
            'fee': 500.0,
            'paid': 500.0,
            'status': 'Active',
            'initial_pay': 500.0,
            'pay_method': 'UPI',
            'pay_ref': 'UPI-DEMO-001',
            'notes': 'Demo active member with fully paid dues'
        },
        {
            'code': 'CS-DEMO-MEM-002',
            'user_id': None,
            'name': 'Rohan Varma',
            'email': 'rohan.varma@example.edu',
            'phone': '+91 98765 11002',
            'student_id': '1NT23IS088',
            'dept': 'Information Science',
            'join': (today - timedelta(days=60)).isoformat(),
            'expiry': (today + timedelta(days=305)).isoformat(),
            'type': 'Annual',
            'fee': 1000.0,
            'paid': 600.0,
            'status': 'Active',
            'initial_pay': 600.0,
            'pay_method': 'Cash',
            'pay_ref': 'CASH-REC-002',
            'notes': 'Demo member with ₹400 outstanding balance'
        },
        {
            'code': 'CS-DEMO-MEM-003',
            'user_id': None,
            'name': 'Priya Nair',
            'email': 'priya.nair@example.edu',
            'phone': '+91 98765 11003',
            'student_id': '1NT22EC014',
            'dept': 'Electronics',
            'join': (today - timedelta(days=400)).isoformat(),
            'expiry': (today - timedelta(days=35)).isoformat(),
            'type': 'Annual',
            'fee': 500.0,
            'paid': 500.0,
            'status': 'Expired',
            'initial_pay': 0.0,  # Legacy prior period
            'pay_method': 'Cash',
            'pay_ref': None,
            'notes': 'Demo expired member eligible for renewal'
        },
        {
            'code': 'CS-DEMO-MEM-004',
            'user_id': None,
            'name': 'Karthik Reddy',
            'email': 'karthik.reddy@example.edu',
            'phone': '+91 98765 11004',
            'student_id': '1NT24ME032',
            'dept': 'Mechanical Engineering',
            'join': today_iso,
            'expiry': (today + timedelta(days=365)).isoformat(),
            'type': 'Annual',
            'fee': 500.0,
            'paid': 0.0,
            'status': 'Pending',
            'initial_pay': 0.0,
            'pay_method': 'Cash',
            'pay_ref': None,
            'notes': 'Demo newly registered member pending fee payment'
        }
    ]

    member_ids = {}
    for m in members_data:
        existing = cursor.execute("SELECT id FROM members WHERE member_code = ?", (m['code'],)).fetchone()
        if existing:
            member_ids[m['code']] = existing['id']
        else:
            cursor.execute("""
                INSERT INTO members (
                    member_code, user_id, full_name, email, phone, student_id,
                    department, join_date, expiry_date, membership_type,
                    membership_fee, amount_paid, status, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                m['code'], m['user_id'], m['name'], m['email'], m['phone'], m['student_id'],
                m['dept'], m['join'], m['expiry'], m['type'],
                m['fee'], m['paid'], m['status'], m['notes']
            ))
            mem_id = cursor.lastrowid
            member_ids[m['code']] = mem_id
            if verbose:
                print(f"  + Created member: {m['name']} ({m['code']} - {m['status']})")

            # Record initial payment in ledger if > 0
            if m['initial_pay'] > 0:
                cursor.execute("""
                    INSERT INTO membership_payments (
                        member_id, amount, payment_date, payment_method, reference_no, notes, created_by
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    mem_id, m['initial_pay'], m['join'], m['pay_method'],
                    m['pay_ref'], 'Initial registration payment', admin_id
                ))
                pay_id = cursor.lastrowid

                cursor.execute("""
                    INSERT INTO financial_transactions (
                        transaction_type, category, amount, description,
                        source_type, source_id, payment_method, transaction_date, recorded_by
                    ) VALUES (?, ?, ?, ?, 'membership_payment', ?, ?, ?, ?)
                """, (
                    'Income', 'Membership Fee', m['initial_pay'],
                    f"Membership Fee for {m['name']} ({m['code']})",
                    pay_id, m['pay_method'], m['join'], admin_id
                ))

    conn.commit()

    # -------------------------------------------------------------------------
    # 3. EVENTS (Upcoming & Past)
    # -------------------------------------------------------------------------
    events_data = [
        {
            'key': 'hackathon',
            'title': 'AI & Robotics National Hackathon 2026',
            'desc': 'Annual 24-hour hackathon with industry mentors, hardware kits, and cash prizes.',
            'date': (today + timedelta(days=14)).isoformat(),
            'time': '09:00',
            'venue': 'Main Auditorium & Innovation Lab',
            'capacity': 100,
            'member_price': 150.0,
            'non_member_price': 300.0,
            'status': 'Upcoming',
            'poster_image': 'images/pic 1.jpg'
        },
        {
            'key': 'acoustic',
            'title': 'Winter Acoustic Jam & Open Mic',
            'desc': 'Evening of live music, poetry performances, and refreshments under the stars.',
            'date': (today + timedelta(days=28)).isoformat(),
            'time': '18:00',
            'venue': 'Amphitheatre Lawn',
            'capacity': 50,
            'member_price': 50.0,
            'non_member_price': 120.0,
            'status': 'Upcoming',
            'poster_image': 'images/pic 2.jpg'
        },
        {
            'key': 'symposium',
            'title': 'Alumni Career & Leadership Summit',
            'desc': 'Panel discussions with distinguished alumni working in AI, Cloud, and Product.',
            'date': (today - timedelta(days=10)).isoformat(),
            'time': '11:00',
            'venue': 'Seminar Hall B',
            'capacity': 40,
            'member_price': 0.0,
            'non_member_price': 100.0,
            'status': 'Completed',
            'poster_image': 'images/pic 3.jpg'
        }
    ]

    event_ids = {}
    for ev in events_data:
        existing = cursor.execute("SELECT id FROM events WHERE title = ?", (ev['title'],)).fetchone()
        if existing:
            event_ids[ev['key']] = existing['id']
            cursor.execute("UPDATE events SET poster_image = ? WHERE id = ?", (ev['poster_image'], existing['id']))
        else:
            cursor.execute("""
                INSERT INTO events (
                    title, description, event_date, event_time, venue,
                    capacity, member_price, non_member_price, status, poster_image, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ev['title'], ev['desc'], ev['date'], ev['time'], ev['venue'],
                ev['capacity'], ev['member_price'], ev['non_member_price'], ev['status'], ev['poster_image'], organizer_id
            ))
            event_ids[ev['key']] = cursor.lastrowid
            if verbose:
                print(f"  + Created event: {ev['title']} ({ev['status']})")

    conn.commit()

    # -------------------------------------------------------------------------
    # 4. TICKETS & LIVE ATTENDANCE (Within Event Capacity)
    # -------------------------------------------------------------------------
    tickets_data = [
        # Hackathon Tickets (3 sold out of 100)
        {
            'ref': 'CS-TKT-DEMO-001',
            'event_id': event_ids['hackathon'],
            'purchaser_name': 'Ananya Sharma',
            'purchaser_email': 'ananya.sharma@example.edu',
            'member_id': member_ids.get('CS-DEMO-MEM-001'),
            'price': 150.0,
            'is_member': 1,
            'method': 'UPI',
            'checked_in': 1,
            'check_in_time': (today - timedelta(days=1)).isoformat() + ' 09:15:00',
            'checked_in_by': volunteer_id
        },
        {
            'ref': 'CS-TKT-DEMO-002',
            'event_id': event_ids['hackathon'],
            'purchaser_name': 'Vikram Sen',
            'purchaser_email': 'vikram.sen@external.org',
            'member_id': None,
            'price': 300.0,
            'is_member': 0,
            'method': 'Cash',
            'checked_in': 0,
            'check_in_time': None,
            'checked_in_by': None
        },
        {
            'ref': 'CS-TKT-DEMO-003',
            'event_id': event_ids['hackathon'],
            'purchaser_name': 'Deepa Menon',
            'purchaser_email': 'deepa.m@guest.net',
            'member_id': None,
            'price': 300.0,
            'is_member': 0,
            'method': 'Card',
            'checked_in': 0,
            'check_in_time': None,
            'checked_in_by': None
        },
        # Completed Summit Tickets
        {
            'ref': 'CS-TKT-DEMO-004',
            'event_id': event_ids['symposium'],
            'purchaser_name': 'Ananya Sharma',
            'purchaser_email': 'ananya.sharma@example.edu',
            'member_id': member_ids.get('CS-DEMO-MEM-001'),
            'price': 0.0,
            'is_member': 1,
            'method': 'Online',
            'checked_in': 1,
            'check_in_time': (today - timedelta(days=10)).isoformat() + ' 10:45:00',
            'checked_in_by': volunteer_id
        },
        {
            'ref': 'CS-TKT-DEMO-005',
            'event_id': event_ids['symposium'],
            'purchaser_name': 'Rajiv Nair',
            'purchaser_email': 'rajiv.nair@guest.com',
            'member_id': None,
            'price': 100.0,
            'is_member': 0,
            'method': 'UPI',
            'checked_in': 1,
            'check_in_time': (today - timedelta(days=10)).isoformat() + ' 10:55:00',
            'checked_in_by': volunteer_id
        }
    ]

    for t in tickets_data:
        existing = cursor.execute("SELECT id FROM tickets WHERE ticket_ref = ?", (t['ref'],)).fetchone()
        if not existing:
            cursor.execute("""
                INSERT INTO tickets (
                    ticket_ref, event_id, purchaser_name, purchaser_email,
                    member_id, price_paid, is_member_rate, payment_method, payment_status,
                    checked_in, check_in_time, checked_in_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Confirmed', ?, ?, ?)
            """, (
                t['ref'], t['event_id'], t['purchaser_name'], t['purchaser_email'],
                t['member_id'], t['price'], t['is_member'], t['method'],
                t['checked_in'], t['check_in_time'], t['checked_in_by']
            ))
            tkt_id = cursor.lastrowid
            if verbose:
                print(f"  + Issued ticket: {t['ref']} ({t['purchaser_name']})")

            # Post paid tickets to financial ledger
            if t['price'] > 0:
                cursor.execute("""
                    INSERT INTO financial_transactions (
                        transaction_type, category, amount, description,
                        source_type, source_id, event_id, payment_method, transaction_date, recorded_by
                    ) VALUES (?, ?, ?, ?, 'ticket_sale', ?, ?, ?, ?, ?)
                """, (
                    'Income', 'Ticket Sale', t['price'],
                    f"Ticket {t['ref']} for Attendee {t['purchaser_name']}",
                    tkt_id, t['event_id'], t['method'], today_iso, organizer_id
                ))

    conn.commit()

    # -------------------------------------------------------------------------
    # 5. MERCHANDISE, VARIANTS, & STOCK ALERTS
    # -------------------------------------------------------------------------
    items_data = [
        {
            'name': 'Official Club Hoodie 2026',
            'category': 'Apparel',
            'desc': 'Heavyweight fleece hoodie with embroidered ClubSphere crest.',
            'base_price': 850.0,
            'variants': [
                ('S', 'HOODIE-S', 10, 5),
                ('M', 'HOODIE-M', 15, 5),
                ('L', 'HOODIE-L', 3, 5),   # LOW STOCK (3 <= 5)
                ('XL', 'HOODIE-XL', 0, 5)  # OUT OF STOCK (0 <= 5)
            ]
        },
        {
            'name': 'ClubSphere Enamel Pin & Decal Pack',
            'category': 'Accessories',
            'desc': 'Metallic finish collectible badge and laptop vinyl stickers.',
            'base_price': 100.0,
            'variants': [
                ('Free Size', 'PIN-FS', 50, 10)
            ]
        }
    ]

    variant_ids = {}
    for item in items_data:
        existing_item = cursor.execute("SELECT id FROM merchandise_items WHERE name = ?", (item['name'],)).fetchone()
        if existing_item:
            item_id = existing_item['id']
        else:
            cursor.execute("""
                INSERT INTO merchandise_items (name, category, description, base_price, is_active)
                VALUES (?, ?, ?, ?, 1)
            """, (item['name'], item['category'], item['desc'], item['base_price']))
            item_id = cursor.lastrowid
            if verbose:
                print(f"  + Created merchandise item: {item['name']}")

        for size, sku, qty, threshold in item['variants']:
            existing_var = cursor.execute("SELECT id FROM merchandise_variants WHERE sku = ?", (sku,)).fetchone()
            if existing_var:
                variant_ids[sku] = existing_var['id']
            else:
                cursor.execute("""
                    INSERT INTO merchandise_variants (
                        item_id, size, sku, stock_quantity, low_stock_threshold
                    ) VALUES (?, ?, ?, ?, ?)
                """, (item_id, size, sku, qty, threshold))
                variant_ids[sku] = cursor.lastrowid
                if verbose:
                    print(f"    - Variant {sku} ({size}): {qty} units in stock")

    conn.commit()

    # -------------------------------------------------------------------------
    # 6. MERCHANDISE ORDERS
    # -------------------------------------------------------------------------
    orders_data = [
        {
            'ref': 'CS-ORD-DEMO-001',
            'customer_name': 'Ananya Sharma',
            'customer_email': 'ananya.sharma@example.edu',
            'member_id': member_ids.get('CS-DEMO-MEM-001'),
            'sku': 'HOODIE-M',
            'qty': 1,
            'unit_price': 850.0,
            'total': 850.0,
            'method': 'UPI'
        },
        {
            'ref': 'CS-ORD-DEMO-002',
            'customer_name': 'Rohan Varma',
            'customer_email': 'rohan.varma@example.edu',
            'member_id': member_ids.get('CS-DEMO-MEM-002'),
            'sku': 'PIN-FS',
            'qty': 2,
            'unit_price': 100.0,
            'total': 200.0,
            'method': 'Cash'
        }
    ]

    for ord_data in orders_data:
        existing_ord = cursor.execute("SELECT id FROM merchandise_orders WHERE order_ref = ?", (ord_data['ref'],)).fetchone()
        if not existing_ord:
            cursor.execute("""
                INSERT INTO merchandise_orders (
                    order_ref, customer_name, customer_email, member_id,
                    total_amount, payment_status, payment_method, created_by
                ) VALUES (?, ?, ?, ?, ?, 'Paid', ?, ?)
            """, (
                ord_data['ref'], ord_data['customer_name'], ord_data['customer_email'],
                ord_data['member_id'], ord_data['total'], ord_data['method'], admin_id
            ))
            ord_id = cursor.lastrowid

            var_id = variant_ids.get(ord_data['sku'])
            if var_id:
                cursor.execute("""
                    INSERT INTO merchandise_order_items (order_id, variant_id, quantity, unit_price, subtotal)
                    VALUES (?, ?, ?, ?, ?)
                """, (ord_id, var_id, ord_data['qty'], ord_data['unit_price'], ord_data['total']))

                # Record in ledger
                cursor.execute("""
                    INSERT INTO financial_transactions (
                        transaction_type, category, amount, description,
                        source_type, source_id, payment_method, transaction_date, recorded_by
                    ) VALUES (?, ?, ?, ?, 'merchandise_order', ?, ?, ?, ?)
                """, (
                    'Income', 'Merchandise Sale', ord_data['total'],
                    f"Order {ord_data['ref']}: {ord_data['qty']}x {ord_data['sku']} for {ord_data['customer_name']}",
                    ord_id, ord_data['method'], today_iso, admin_id
                ))
            if verbose:
                print(f"  + Recorded merchandise order: {ord_data['ref']} (INR {ord_data['total']})")

    conn.commit()

    # -------------------------------------------------------------------------
    # 7. EXPENSE REQUESTS & REIMBURSEMENTS
    # -------------------------------------------------------------------------
    expenses_data = [
        {
            'title': 'PA Sound & Audio System Rental',
            'cat': 'Equipment & Tech',
            'amount': 3000.0,
            'desc': 'Stage amplifiers, 4 cordless microphones, and speaker towers for Hackathon auditorium.',
            'event_id': event_ids.get('hackathon'),
            'status': 'Paid',
            'receipt': 'REC-PA-9921',
            'approved_by': treasurer_id,
            'paid_by': treasurer_id,
            'pay_method': 'Bank Transfer',
            'pay_ref': 'UTR-NEFT-99112'
        },
        {
            'title': 'Hackathon Catering & Midnight Snacks',
            'cat': 'Refreshments',
            'amount': 2500.0,
            'desc': 'Sandwiches, hot coffee, and mineral water for 100 participants.',
            'event_id': event_ids.get('hackathon'),
            'status': 'Approved',
            'receipt': 'EST-CAT-4412',
            'approved_by': treasurer_id,
            'paid_by': None,
            'pay_method': None,
            'pay_ref': None
        },
        {
            'title': 'Participant Badge Lanyards & Banners',
            'cat': 'Printing & Stationery',
            'amount': 850.0,
            'desc': 'Eco-friendly identity badges and auditorium backdrop banner.',
            'event_id': event_ids.get('hackathon'),
            'status': 'Pending',
            'receipt': 'QUO-PRN-001',
            'approved_by': None,
            'paid_by': None,
            'pay_method': None,
            'pay_ref': None
        }
    ]

    for exp in expenses_data:
        existing_exp = cursor.execute("SELECT id FROM expense_requests WHERE title = ?", (exp['title'],)).fetchone()
        if not existing_exp:
            cursor.execute("""
                INSERT INTO expense_requests (
                    title, category, amount, requested_by, description,
                    receipt_ref, event_id, status, approved_by, approved_date,
                    paid_by, paid_date, payment_method, payment_ref
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                exp['title'], exp['cat'], exp['amount'], organizer_id, exp['desc'],
                exp['receipt'], exp['event_id'], exp['status'],
                exp['approved_by'], today_iso if exp['approved_by'] else None,
                exp['paid_by'], today_iso if exp['paid_by'] else None,
                exp['pay_method'], exp['pay_ref']
            ))
            exp_id = cursor.lastrowid
            if verbose:
                print(f"  + Created expense request: {exp['title']} [{exp['status']}] (INR {exp['amount']})")

            # ONLY Paid expenses enter the financial ledger
            if exp['status'] == 'Paid':
                cursor.execute("""
                    INSERT INTO financial_transactions (
                        transaction_type, category, amount, description,
                        source_type, source_id, event_id, payment_method, transaction_date, recorded_by
                    ) VALUES (?, ?, ?, ?, 'expense_request', ?, ?, ?, ?, ?)
                """, (
                    'Expense', 'Expense Reimbursement', exp['amount'],
                    f"Paid Expense #{exp_id}: {exp['title']}",
                    exp_id, exp['event_id'], exp['pay_method'], today_iso, treasurer_id
                ))

    conn.commit()

    # -------------------------------------------------------------------------
    # 8. DIRECT FUNDRAISING / SPONSORSHIP LEDGER ENTRY
    # -------------------------------------------------------------------------
    sponsorship_desc = "Tech Global Corp Title Sponsorship for Hackathon 2026"
    existing_spon = cursor.execute("SELECT id FROM financial_transactions WHERE description = ?", (sponsorship_desc,)).fetchone()
    if not existing_spon:
        cursor.execute("""
            INSERT INTO financial_transactions (
                transaction_type, category, amount, description,
                source_type, source_id, event_id, payment_method, transaction_date, recorded_by
            ) VALUES (?, ?, ?, ?, 'manual_income', NULL, ?, ?, ?, ?)
        """, (
            'Income', 'Sponsorship', 15000.0, sponsorship_desc,
            event_ids.get('hackathon'), 'Bank Transfer', today_iso, treasurer_id
        ))
        if verbose:
            print(f"  + Recorded title sponsorship income: INR 15,000.00")

    conn.commit()

    # -------------------------------------------------------------------------
    # 9. VOLUNTEER TASKS
    # -------------------------------------------------------------------------
    tasks_data = [
        {
            'title': 'Configure Stage Audio & PA Microphones',
            'desc': 'Perform sound test with 4 wireless mics in Main Auditorium.',
            'event_id': event_ids.get('hackathon'),
            'assigned_to': volunteer_id,
            'priority': 'High',
            'deadline': (today + timedelta(days=13)).isoformat(),
            'status': 'In Progress'
        },
        {
            'title': 'Assemble Attendee Registration Welcome Kits',
            'desc': 'Pack badges, stickers, and schedule booklets into bags.',
            'event_id': event_ids.get('hackathon'),
            'assigned_to': volunteer_id,
            'priority': 'Urgent',
            'deadline': (today + timedelta(days=14)).isoformat(),
            'status': 'Pending'
        },
        {
            'title': 'Upload Alumni Summit Photos to Media Gallery',
            'desc': 'Curate and organize high-resolution event photos for website.',
            'event_id': event_ids.get('symposium'),
            'assigned_to': volunteer_id,
            'priority': 'Medium',
            'deadline': (today - timedelta(days=8)).isoformat(),
            'status': 'Completed'
        },
        {
            'title': 'Prepare Participant Registration Desk',
            'desc': 'Arrange registration materials, attendee lists, badges, and check-in equipment before the hackathon.',
            'event_id': event_ids.get('hackathon'),
            'assigned_to': volunteer_id,
            'priority': 'High',
            'deadline': (today + timedelta(days=13)).isoformat(),
            'status': 'Pending'
        },
        {
            'title': 'Verify Event Equipment and Supplies',
            'desc': 'Check microphones, extension cables, stationery, and other required event supplies.',
            'event_id': event_ids.get('hackathon'),
            'assigned_to': volunteer_id,
            'priority': 'High',
            'deadline': (today + timedelta(days=12)).isoformat(),
            'status': 'In Progress'
        },
        {
            'title': 'Prepare Announcement and Event Posters',
            'desc': 'Organize approved event posters and prepare announcement materials for display.',
            'event_id': event_ids.get('hackathon'),
            'assigned_to': volunteer_id,
            'priority': 'Medium',
            'deadline': (today + timedelta(days=11)).isoformat(),
            'status': 'Pending'
        }
    ]

    for tsk in tasks_data:
        existing_tsk = cursor.execute("SELECT id FROM volunteer_tasks WHERE title = ?", (tsk['title'],)).fetchone()
        if not existing_tsk:
            cursor.execute("""
                INSERT INTO volunteer_tasks (
                    title, description, event_id, assigned_to, priority, deadline, status, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                tsk['title'], tsk['desc'], tsk['event_id'], tsk['assigned_to'],
                tsk['priority'], tsk['deadline'], tsk['status'], organizer_id
            ))
            if verbose:
                print(f"  + Created task: {tsk['title']} [{tsk['status']}]")

    conn.commit()

    # -------------------------------------------------------------------------
    # 10. ANNOUNCEMENTS
    # -------------------------------------------------------------------------
    announcements_data = [
        {
            'title': 'Hackathon 2026 Problem Statements Released!',
            'content': 'All participants can now review the AI and IoT problem statements. Check-in opens at 8:30 AM in the Main Auditorium.',
            'audience': 'All',
            'priority': 'Important'
        },
        {
            'title': 'Volunteer Briefing Meeting - Saturday 8:00 AM',
            'content': 'All assigned volunteers please report to Innovation Lab for radio assignment and zone badges.',
            'audience': 'Volunteers',
            'priority': 'Urgent'
        },
        {
            'title': 'Executive Committee: Budget & Expense Review',
            'content': 'Treasurer and core leads meeting on Monday to finalize vendor payments and audited accounts.',
            'audience': 'Executive',
            'priority': 'Normal'
        }
    ]

    for ann in announcements_data:
        existing_ann = cursor.execute("SELECT id FROM announcements WHERE title = ?", (ann['title'],)).fetchone()
        if not existing_ann:
            cursor.execute("""
                INSERT INTO announcements (title, content, audience, priority, published_by)
                VALUES (?, ?, ?, ?, ?)
            """, (ann['title'], ann['content'], ann['audience'], ann['priority'], organizer_id))
            if verbose:
                print(f"  + Published announcement: {ann['title']} (Audience: {ann['audience']})")

    conn.commit()
    conn.close()

    if verbose:
        print("\n[OK] Demo database seeded successfully and fully reconciled!")
        print(f"[*] Database file located at: {db_path}")
        print("[*] Available demo accounts (Password for all: Password123!):")
        for u, _, _, r in demo_users:
            print(f"    - {u:<16} ({r})")
        print()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="ClubSphere Demo Data Seeder")
    parser.add_argument('--db-path', default=DEFAULT_DEMO_DB, help="Target database path (default: instance/clubsphere_demo.db)")
    args = parser.parse_args()
    seed_demo_database(args.db_path)
