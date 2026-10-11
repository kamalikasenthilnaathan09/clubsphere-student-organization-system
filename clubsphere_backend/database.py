import os
import sqlite3
from datetime import datetime

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance', 'clubsphere.db')


def get_db_path(custom_path=None):
    if custom_path:
        return custom_path
    env_path = os.environ.get('CLUB_SPHERE_DB')
    if env_path:
        return env_path
    # Ensure instance directory exists
    instance_dir = os.path.dirname(DEFAULT_DB_PATH)
    os.makedirs(instance_dir, exist_ok=True)
    return DEFAULT_DB_PATH


def get_db(db_path=None):
    """
    Connect to the SQLite database.
    Enables foreign keys, WAL mode, and returns sqlite3.Row objects.
    """
    path = get_db_path(db_path)
    if path != ':memory:' and not os.path.isabs(path):
        instance_dir = os.path.dirname(DEFAULT_DB_PATH)
        os.makedirs(instance_dir, exist_ok=True)

    conn = sqlite3.connect(path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    if path != ':memory:':
        try:
            conn.execute("PRAGMA journal_mode = WAL;")
        except sqlite3.OperationalError:
            pass
    return conn


def init_db(db_path=None):
    """
    Initialize database schema with tables and indexes.
    """
    conn = get_db(db_path)
    cursor = conn.cursor()

    # 1. Users Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        full_name TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('Administrator', 'Treasurer', 'Event Organizer', 'Volunteer', 'Member')),
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 2. Members Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE REFERENCES users(id) ON DELETE SET NULL,
        member_code TEXT UNIQUE NOT NULL,
        full_name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        phone TEXT,
        student_id TEXT,
        department TEXT,
        join_date DATE NOT NULL,
        expiry_date DATE NOT NULL,
        membership_type TEXT NOT NULL DEFAULT 'Annual' CHECK(membership_type IN ('Annual', 'Semester', 'Lifetime')),
        membership_fee REAL NOT NULL DEFAULT 0.0 CHECK(membership_fee >= 0),
        amount_paid REAL NOT NULL DEFAULT 0.0 CHECK(amount_paid >= 0),
        status TEXT NOT NULL DEFAULT 'Active' CHECK(status IN ('Active', 'Expired', 'Pending', 'Suspended')),
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 3. Membership Payments Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS membership_payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        member_id INTEGER NOT NULL REFERENCES members(id) ON DELETE CASCADE,
        amount REAL NOT NULL CHECK(amount > 0),
        payment_date DATE NOT NULL,
        payment_method TEXT NOT NULL DEFAULT 'Cash' CHECK(payment_method IN ('Cash', 'UPI', 'Card', 'Bank Transfer')),
        reference_no TEXT,
        notes TEXT,
        created_by INTEGER REFERENCES users(id),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 4. Events Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        event_date DATE NOT NULL,
        event_time TEXT NOT NULL,
        venue TEXT NOT NULL,
        capacity INTEGER NOT NULL CHECK(capacity > 0),
        member_price REAL NOT NULL DEFAULT 0.0 CHECK(member_price >= 0),
        non_member_price REAL NOT NULL DEFAULT 0.0 CHECK(non_member_price >= 0),
        status TEXT NOT NULL DEFAULT 'Upcoming' CHECK(status IN ('Upcoming', 'Ongoing', 'Completed', 'Cancelled')),
        poster_image TEXT,
        created_by INTEGER REFERENCES users(id),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Dynamic column migration for existing events tables
    cursor.execute("PRAGMA table_info(events);")
    event_cols = [col[1] for col in cursor.fetchall()]
    if 'poster_image' not in event_cols:
        cursor.execute("ALTER TABLE events ADD COLUMN poster_image TEXT;")

    # 5. Tickets Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_ref TEXT UNIQUE NOT NULL,
        event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
        purchaser_name TEXT NOT NULL,
        purchaser_email TEXT NOT NULL,
        purchaser_phone TEXT,
        member_id INTEGER REFERENCES members(id) ON DELETE SET NULL,
        price_paid REAL NOT NULL DEFAULT 0.0 CHECK(price_paid >= 0),
        is_member_rate INTEGER NOT NULL DEFAULT 0,
        payment_method TEXT DEFAULT 'Cash',
        payment_status TEXT NOT NULL DEFAULT 'Confirmed' CHECK(payment_status IN ('Confirmed', 'Refunded', 'Cancelled')),
        payment_ref TEXT,
        qr_data TEXT,
        checked_in INTEGER NOT NULL DEFAULT 0 CHECK(checked_in IN (0, 1)),
        check_in_time TIMESTAMP,
        checked_in_by INTEGER REFERENCES users(id),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Dynamic column migration for existing tickets tables
    cursor.execute("PRAGMA table_info(tickets);")
    ticket_cols = [col[1] for col in cursor.fetchall()]
    if 'payment_ref' not in ticket_cols:
        cursor.execute("ALTER TABLE tickets ADD COLUMN payment_ref TEXT;")
    if 'qr_data' not in ticket_cols:
        cursor.execute("ALTER TABLE tickets ADD COLUMN qr_data TEXT;")

    # 6. Merchandise Items Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS merchandise_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        category TEXT NOT NULL DEFAULT 'Apparel',
        description TEXT,
        base_price REAL NOT NULL CHECK(base_price >= 0),
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 7. Merchandise Variants Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS merchandise_variants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id INTEGER NOT NULL REFERENCES merchandise_items(id) ON DELETE CASCADE,
        size TEXT NOT NULL,
        sku TEXT UNIQUE NOT NULL,
        stock_quantity INTEGER NOT NULL DEFAULT 0 CHECK(stock_quantity >= 0),
        price_override REAL,
        low_stock_threshold INTEGER NOT NULL DEFAULT 5 CHECK(low_stock_threshold >= 0),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(item_id, size)
    );
    """)

    # 8. Merchandise Orders Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS merchandise_orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_ref TEXT UNIQUE NOT NULL,
        customer_name TEXT NOT NULL,
        customer_email TEXT NOT NULL,
        customer_phone TEXT,
        member_id INTEGER REFERENCES members(id) ON DELETE SET NULL,
        total_amount REAL NOT NULL CHECK(total_amount >= 0),
        payment_status TEXT NOT NULL DEFAULT 'Paid' CHECK(payment_status IN ('Paid', 'Pending', 'Cancelled')),
        payment_method TEXT DEFAULT 'Cash',
        notes TEXT,
        created_by INTEGER REFERENCES users(id),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 9. Merchandise Order Items Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS merchandise_order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL REFERENCES merchandise_orders(id) ON DELETE CASCADE,
        variant_id INTEGER NOT NULL REFERENCES merchandise_variants(id) ON DELETE RESTRICT,
        quantity INTEGER NOT NULL CHECK(quantity > 0),
        unit_price REAL NOT NULL CHECK(unit_price >= 0),
        subtotal REAL NOT NULL CHECK(subtotal >= 0)
    );
    """)

    # 10. Expense Requests Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS expense_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        category TEXT NOT NULL,
        amount REAL NOT NULL CHECK(amount > 0),
        requested_by INTEGER NOT NULL REFERENCES users(id),
        description TEXT NOT NULL,
        receipt_ref TEXT,
        event_id INTEGER REFERENCES events(id) ON DELETE SET NULL,
        status TEXT NOT NULL DEFAULT 'Pending' CHECK(status IN ('Pending', 'Approved', 'Rejected', 'Paid')),
        approved_by INTEGER REFERENCES users(id),
        approved_date TIMESTAMP,
        rejection_reason TEXT,
        paid_by INTEGER REFERENCES users(id),
        paid_date TIMESTAMP,
        payment_method TEXT,
        payment_ref TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 11. Financial Transactions (Ledger) Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS financial_transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        transaction_type TEXT NOT NULL CHECK(transaction_type IN ('Income', 'Expense')),
        category TEXT NOT NULL,
        amount REAL NOT NULL CHECK(amount > 0),
        description TEXT NOT NULL,
        source_type TEXT NOT NULL,
        source_id INTEGER,
        event_id INTEGER REFERENCES events(id) ON DELETE SET NULL,
        payment_method TEXT DEFAULT 'Cash',
        transaction_date DATE NOT NULL,
        recorded_by INTEGER REFERENCES users(id),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 12. Volunteer Tasks Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS volunteer_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        event_id INTEGER REFERENCES events(id) ON DELETE SET NULL,
        assigned_to INTEGER REFERENCES users(id) ON DELETE SET NULL,
        priority TEXT NOT NULL DEFAULT 'Medium' CHECK(priority IN ('Low', 'Medium', 'High', 'Urgent')),
        deadline DATE,
        status TEXT NOT NULL DEFAULT 'Pending' CHECK(status IN ('Pending', 'In Progress', 'Completed', 'Cancelled')),
        created_by INTEGER REFERENCES users(id),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 13. Announcements Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS announcements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        audience TEXT NOT NULL DEFAULT 'All' CHECK(audience IN ('All', 'Members', 'Volunteers', 'Executive')),
        priority TEXT NOT NULL DEFAULT 'Normal' CHECK(priority IN ('Normal', 'Important', 'Urgent')),
        published_by INTEGER NOT NULL REFERENCES users(id),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 14. Gate Check-in Logs Table (Audit Trail)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS gate_checkin_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_ref TEXT NOT NULL,
        event_id INTEGER REFERENCES events(id) ON DELETE SET NULL,
        status TEXT NOT NULL,
        message TEXT,
        verifier_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 15. Student Feedback & Suggestions Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS student_feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        feedback_type TEXT NOT NULL CHECK(feedback_type IN ('Event', 'Club Activity', 'Workshop', 'Membership', 'General Suggestion')),
        event_id INTEGER REFERENCES events(id) ON DELETE SET NULL,
        rating INTEGER CHECK(rating IS NULL OR (rating >= 1 AND rating <= 5)),
        subject TEXT NOT NULL,
        message TEXT NOT NULL,
        is_anonymous INTEGER NOT NULL DEFAULT 0 CHECK(is_anonymous IN (0, 1)),
        status TEXT NOT NULL DEFAULT 'Submitted' CHECK(status IN ('Submitted', 'Reviewed', 'Actioned', 'Closed')),
        admin_notes TEXT,
        reviewed_by INTEGER REFERENCES users(id),
        reviewed_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 16. Achievement Points & Activity History Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS achievement_points (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        points INTEGER NOT NULL CHECK(points != 0),
        reason TEXT NOT NULL,
        source_type TEXT NOT NULL,
        source_id INTEGER,
        awarded_by INTEGER REFERENCES users(id),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, source_type, source_id)
    );
    """)

    # 17. Student Certificates & Achievement Wallet Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS student_certificates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        certificate_ref TEXT UNIQUE NOT NULL,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        title TEXT NOT NULL,
        activity_type TEXT NOT NULL,
        event_id INTEGER REFERENCES events(id) ON DELETE SET NULL,
        issuing_org TEXT NOT NULL DEFAULT 'ClubSphere — Student Organization',
        recipient_name TEXT NOT NULL,
        issue_date DATE NOT NULL,
        status TEXT NOT NULL DEFAULT 'Issued' CHECK(status IN ('Issued', 'Revoked')),
        issued_by INTEGER REFERENCES users(id),
        qr_data TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 18. Clubs Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS clubs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        code TEXT UNIQUE NOT NULL,
        description TEXT,
        category TEXT DEFAULT 'General',
        email TEXT,
        faculty_advisor TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 19. Club Memberships / Attendee Registrations Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS club_members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        club_id INTEGER NOT NULL REFERENCES clubs(id) ON DELETE CASCADE,
        member_id INTEGER REFERENCES members(id) ON DELETE CASCADE,
        user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
        full_name TEXT NOT NULL,
        email TEXT NOT NULL,
        student_id TEXT,
        department TEXT,
        membership_type TEXT DEFAULT 'Annual',
        status TEXT NOT NULL DEFAULT 'Active' CHECK(status IN ('Active', 'Expired', 'Pending', 'Suspended', 'Inactive')),
        join_date DATE NOT NULL DEFAULT (DATE('now')),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(club_id, email)
    );
    """)

    # Dynamic column migrations for users table (academic & contact info, preferences)
    cursor.execute("PRAGMA table_info(users);")
    user_cols = [col[1] for col in cursor.fetchall()]
    new_user_cols = [
        ('phone', 'TEXT'),
        ('department', 'TEXT'),
        ('academic_year', 'TEXT'),
        ('student_id', 'TEXT'),
        ('notification_preferences', 'TEXT DEFAULT \'{"email": true, "announcements": true, "events": true}\''),
        ('privacy_settings', 'TEXT DEFAULT \'{"show_on_leaderboard": true, "show_badges": true}\''),
        ('bio', 'TEXT')
    ]
    for col_name, col_type in new_user_cols:
        if col_name not in user_cols:
            cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type};")

    # Dynamic column migrations for announcements table (club targeting & email dispatch audit)
    cursor.execute("PRAGMA table_info(announcements);")
    ann_cols = [col[1] for col in cursor.fetchall()]
    new_ann_cols = [
        ('club_id', 'INTEGER REFERENCES clubs(id)'),
        ('email_sent_count', 'INTEGER DEFAULT 0'),
        ('email_status', 'TEXT'),
        ('email_summary', 'TEXT')
    ]
    for col_name, col_type in new_ann_cols:
        if col_name not in ann_cols:
            cursor.execute(f"ALTER TABLE announcements ADD COLUMN {col_name} {col_type};")

    # Dynamic column migrations for members table
    cursor.execute("PRAGMA table_info(members);")
    mem_cols = [col[1] for col in cursor.fetchall()]
    if 'club_id' not in mem_cols:
        cursor.execute("ALTER TABLE members ADD COLUMN club_id INTEGER REFERENCES clubs(id);")

    # Create Indexes for performance
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_members_code ON members(member_code);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_members_email ON members(email);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_members_status ON members(status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tickets_ref ON tickets(ticket_ref);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tickets_event ON tickets(event_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_gate_logs_event ON gate_checkin_logs(event_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_gate_logs_status ON gate_checkin_logs(status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_variants_sku ON merchandise_variants(sku);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_variants_item ON merchandise_variants(item_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_expenses_status ON expense_requests(status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_fin_type ON financial_transactions(transaction_type);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_fin_date ON financial_transactions(transaction_date);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON volunteer_tasks(status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_assigned ON volunteer_tasks(assigned_to);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_feedback_user ON student_feedback(user_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_feedback_status ON student_feedback(status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_points_user ON achievement_points(user_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_points_source ON achievement_points(source_type, source_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cert_ref ON student_certificates(certificate_ref);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cert_user ON student_certificates(user_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_clubs_code ON clubs(code);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_club_members_club ON club_members(club_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_club_members_email ON club_members(email);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_club_members_status ON club_members(status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_announcements_club ON announcements(club_id);")

    conn.commit()
    seed_default_clubs_if_empty(conn)
    conn.commit()
    conn.close()


def seed_default_clubs_if_empty(conn):
    """
    Safely seeds default campus clubs and maps existing demo members
    if the clubs table is currently empty. Non-destructive and idempotent.
    """
    cursor = conn.cursor()
    row = cursor.execute("SELECT COUNT(*) AS c FROM clubs").fetchone()
    if row and row['c'] > 0:
        return

    default_clubs = [
        ('Robotics & AI Club', 'ROBOTICS', 'Designing autonomous systems, competitive robotics, and machine learning models.', 'Technology & Robotics', 'robotics@clubsphere.org', 'Dr. Arun Kumar'),
        ('Coding & Open Source Society', 'DEV-SOC', 'Full-stack engineering, open-source software, competitive programming, and hackathons.', 'Software & Computing', 'devsoc@clubsphere.org', 'Prof. Sunita Rao'),
        ('Music & Cultural Arts Club', 'CULTURAL', 'Campus concerts, acoustic jams, theatrical performances, and creative student arts.', 'Arts & Culture', 'cultural@clubsphere.org', 'Dr. Vikram Malhotra'),
        ('Mechanical & Mobility Society', 'MECH-MOB', 'Motorsport engineering, electric vehicle prototyping, and CAD innovation.', 'Engineering & Design', 'mobility@clubsphere.org', 'Prof. Harish Nair')
    ]

    for name, code, desc, cat, email, advisor in default_clubs:
        cursor.execute("""
            INSERT OR IGNORE INTO clubs (name, code, description, category, email, faculty_advisor)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (name, code, desc, cat, email, advisor))

    conn.commit()

    # Link existing demo members to clubs if club_members is empty
    cm_count = cursor.execute("SELECT COUNT(*) AS c FROM club_members").fetchone()
    if cm_count and cm_count['c'] == 0:
        clubs_by_code = {r['code']: r['id'] for r in cursor.execute("SELECT id, code FROM clubs").fetchall()}
        existing_members = cursor.execute("SELECT * FROM members").fetchall()
        for m in existing_members:
            email = m['email']
            name = m['full_name']
            sid = m['student_id']
            status = m['status']
            jdate = m['join_date'] or datetime.now().date().isoformat()
            uid = m['user_id']
            mid = m['id']

            # Logical club affiliations for rich realistic demonstration
            assigned_clubs = []
            if 'ananya' in name.lower():
                assigned_clubs = ['ROBOTICS', 'DEV-SOC']
            elif 'rohan' in name.lower():
                assigned_clubs = ['DEV-SOC', 'ROBOTICS']
            elif 'priya' in name.lower():
                assigned_clubs = ['CULTURAL']
            elif 'karthik' in name.lower():
                assigned_clubs = ['MECH-MOB']
            elif 'mech' in (m['department'] or '').lower():
                assigned_clubs = ['MECH-MOB']
            elif any(k in (m['department'] or '').lower() for k in ('cs', 'info', 'is')):
                assigned_clubs = ['DEV-SOC']
            else:
                assigned_clubs = ['ROBOTICS']

            for ccode in assigned_clubs:
                cid = clubs_by_code.get(ccode)
                if cid:
                    cursor.execute("""
                        INSERT OR IGNORE INTO club_members (
                            club_id, member_id, user_id, full_name, email,
                            student_id, department, status, join_date
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (cid, mid, uid, name, email, sid, m['department'], status, jdate))
        conn.commit()


def has_admin_user(conn=None, db_path=None):
    """
    Check if at least one Administrator account exists in the database.
    """
    should_close = False
    if conn is None:
        conn = get_db(db_path)
        should_close = True
    try:
        row = conn.execute("SELECT COUNT(*) AS count FROM users WHERE role = 'Administrator' AND is_active = 1").fetchone()
        return bool(row and row['count'] > 0)
    finally:
        if should_close:
            conn.close()


if __name__ == '__main__':
    init_db()
    print("Database initialized successfully at:", get_db_path())
