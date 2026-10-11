import os
import json
import secrets
import sqlite3
import re
import time
from datetime import datetime, date, timedelta
from functools import wraps

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from flask import (
    Flask, render_template, request, redirect, url_for, flash,
    session, jsonify, g, abort, make_response
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

try:
    import qrcode
    import qrcode.image.svg
except ImportError:
    qrcode = None

import database
import copilot_service

import io
try:
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.pdfgen import canvas
    from reportlab.lib import colors
except ImportError:
    canvas = None

app = Flask(__name__)

# Upload and QR configuration
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}
ALLOWED_IMAGE_MIMES = {'image/png', 'image/jpeg', 'image/webp', 'image/gif'}
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB


def generate_qr_svg(content):
    """Generate an SVG string for a QR code."""
    if qrcode is not None:
        factory = qrcode.image.svg.SvgPathImage
        img = qrcode.make(content, image_factory=factory, box_size=10, border=2)
        return img.to_string().decode('utf-8')
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="160" height="160" viewBox="0 0 160 160"><rect width="160" height="160" fill="#f8fafc"/><text x="80" y="80" font-family="monospace" font-size="12" text-anchor="middle" fill="#0f172a">{content}</text></svg>'


def save_event_poster(file_storage):
    """
    Validate and securely save an event poster image.
    Returns relative static path like 'uploads/events/<filename>' or raises ValueError.
    """
    if not file_storage or not getattr(file_storage, 'filename', None) or file_storage.filename.strip() == '':
        return None

    filename = file_storage.filename.strip()
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError(f"Invalid image format '.{ext}'. Allowed formats: {', '.join(sorted(ALLOWED_IMAGE_EXTENSIONS))}.")

    if file_storage.mimetype and file_storage.mimetype not in ALLOWED_IMAGE_MIMES:
        raise ValueError("Uploaded file content does not match allowed image types.")

    file_storage.seek(0, os.SEEK_END)
    size = file_storage.tell()
    file_storage.seek(0)
    if size > MAX_IMAGE_SIZE:
        raise ValueError("Image file size exceeds the 5MB limit.")

    upload_dir = os.path.join(app.root_path, 'static', 'uploads', 'events')
    os.makedirs(upload_dir, exist_ok=True)

    safe_name = f"poster_{int(time.time())}_{secrets.token_hex(4)}_{secure_filename(filename)}"
    dest_path = os.path.join(upload_dir, safe_name)
    file_storage.save(dest_path)
    return f"uploads/events/{safe_name}"

# Configure Secret Key
SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    secret_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance', 'secret_key.txt')
    if os.path.exists(secret_file):
        try:
            with open(secret_file, 'r', encoding='utf-8') as f:
                SECRET_KEY = f.read().strip()
        except Exception:
            SECRET_KEY = secrets.token_hex(32)
    else:
        SECRET_KEY = secrets.token_hex(32)
        try:
            os.makedirs(os.path.dirname(secret_file), exist_ok=True)
            with open(secret_file, 'w', encoding='utf-8') as f:
                f.write(SECRET_KEY)
        except Exception:
            pass

demo_db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance', 'clubsphere_demo.db')
app.secret_key = SECRET_KEY
app.config['DATABASE'] = os.environ.get('CLUB_SPHERE_DB') or (demo_db_path if os.path.exists(demo_db_path) else database.DEFAULT_DB_PATH)


# Database connection management per request
def get_db():
    if 'db' not in g:
        effective_db = app.config.get('DATABASE') or os.environ.get('CLUB_SPHERE_DB') or database.DEFAULT_DB_PATH
        g.db = database.get_db(effective_db)
    return g.db


@app.teardown_appcontext
def close_db(exception):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def get_event_poster_url(poster_path):
    """
    Robust resolver for event poster paths. Handles:
    - 'images/pic 1.jpg' -> url_for('static', filename='images/pic 1.jpg')
    - 'pic 1.jpg' -> url_for('static', filename='images/pic 1.jpg')
    - 'static/images/pic 1.jpg' -> url_for('static', filename='images/pic 1.jpg')
    - 'uploads/events/xxx.png' -> url_for('static', filename='uploads/events/xxx.png')
    - None / '' -> url_for('static', filename='images/event-placeholder.svg')
    """
    if not poster_path:
        return url_for('static', filename='images/event-placeholder.svg')
    p = str(poster_path).strip().replace('\\', '/').lstrip('/')
    if p.startswith('static/'):
        p = p[7:]
    if not p.startswith('images/') and not p.startswith('uploads/'):
        p = f"images/{p}"
    return url_for('static', filename=p)


# Context processor to expose logged-in user, roles, and helper functions to Jinja2 templates
@app.context_processor
def inject_globals():
    today_str = date.today().isoformat()
    current_user = None
    if 'user_id' in session:
        current_user = {
            'id': session.get('user_id'),
            'username': session.get('username'),
            'full_name': session.get('full_name'),
            'role': session.get('role')
        }
    is_demo_mode = os.environ.get('CLUB_SPHERE_DEMO') == '1' or 'demo' in str(app.config.get('DATABASE', '')).lower()
    success_modal = session.pop('success_modal', None)
    return {
        'current_user': current_user,
        'today_str': today_str,
        'now_year': datetime.now().year,
        'is_demo_mode': is_demo_mode,
        'event_poster_url': get_event_poster_url,
        'generate_qr_svg': generate_qr_svg,
        'success_modal': success_modal
    }


# Template filters
@app.template_filter('event_poster_url')
def event_poster_url_filter(poster_path):
    return get_event_poster_url(poster_path)


@app.template_filter('currency')
def currency_filter(value):
    try:
        val = float(value or 0)
        return f"₹{val:,.2f}"
    except (ValueError, TypeError):
        return "₹0.00"


@app.template_filter('format_date')
def format_date_filter(val_str):
    if not val_str:
        return "-"
    try:
        # Handles YYYY-MM-DD or YYYY-MM-DD HH:MM:SS
        clean_str = str(val_str).split()[0]
        dt = datetime.strptime(clean_str, '%Y-%m-%d')
        return dt.strftime('%d %b %Y')
    except Exception:
        return str(val_str)


# -------------------------------------------------------------------------
# AUTHENTICATION & ACCESS CONTROL
# -------------------------------------------------------------------------

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please sign in to access this page.', 'warning')
            return redirect(url_for('login', next=request.path))
        return f(*args, **kwargs)
    return decorated_function


def role_required(*allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please sign in to access this page.', 'warning')
                return redirect(url_for('login', next=request.path))
            user_role = session.get('role')
            if user_role not in allowed_roles and user_role != 'Administrator':
                flash('Access denied. You do not have permission to view this section.', 'danger')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


@app.before_request
def check_initial_setup():
    """
    If no admin exists in the system, redirect any request to the safe setup wizard.
    Allows static files and setup endpoint to proceed.
    """
    if request.path.startswith('/static') or request.path == '/setup':
        return
    db = get_db()
    if not database.has_admin_user(db):
        return redirect(url_for('setup'))

    # If logged in user has been deactivated or deleted, terminate session immediately
    if 'user_id' in session:
        user_row = db.execute("SELECT is_active FROM users WHERE id = ?", (session['user_id'],)).fetchone()
        if not user_row or not user_row['is_active']:
            session.clear()
            flash('Your account has been deactivated. Please sign in with an active account.', 'danger')
            return redirect(url_for('login'))


@app.route('/setup', methods=['GET', 'POST'])
def setup():
    """
    Safe First-Time Administrator Setup.
    Accessible ONLY when no Administrator account exists.
    """
    db = get_db()
    if database.has_admin_user(db):
        flash('Administrator setup has already been completed.', 'info')
        return redirect(url_for('login'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        # Validations
        errors = []
        if not username or len(username) < 3:
            errors.append('Username must be at least 3 characters.')
        if not full_name:
            errors.append('Full name is required.')
        if not email or not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            errors.append('A valid email address is required.')
        if not password or len(password) < 6:
            errors.append('Password must be at least 6 characters long.')
        if password != confirm_password:
            errors.append('Passwords do not match.')

        if errors:
            for err in errors:
                flash(err, 'danger')
            return render_template('setup.html', username=username, full_name=full_name, email=email)

        password_hash = generate_password_hash(password)
        try:
            db.execute("""
                INSERT INTO users (username, email, password_hash, full_name, role, is_active)
                VALUES (?, ?, ?, ?, 'Administrator', 1)
            """, (username, email, password_hash, full_name))
            db.commit()

            user_row = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
            session['user_id'] = user_row['id']
            session['username'] = user_row['username']
            session['full_name'] = user_row['full_name']
            session['role'] = user_row['role']

            flash('Welcome to ClubSphere! Administrator account created successfully.', 'success')
            return redirect(url_for('dashboard'))
        except sqlite3.IntegrityError as e:
            db.rollback()
            flash(f'An account with that username or email already exists. {str(e)}', 'danger')

    return render_template('setup.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    """
    Self-service registration for club Members only.
    Only grants 'Member' role. Never grants admin, treasurer, organizer, or volunteer privileges.
    """
    if request.method == 'GET' and 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        errors = []
        if not username or len(username) < 3:
            errors.append('Username must be at least 3 characters.')
        if not full_name:
            errors.append('Full name is required.')
        if not email or not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            errors.append('A valid email address is required.')
        if not password or len(password) < 6:
            errors.append('Password must be at least 6 characters long.')
        if password != confirm_password:
            errors.append('Passwords do not match.')

        if errors:
            for err in errors:
                flash(err, 'danger')
            return render_template('register.html', username=username, full_name=full_name, email=email)

        db = get_db()
        existing_user = db.execute(
            "SELECT id FROM users WHERE LOWER(username) = LOWER(?) OR LOWER(email) = LOWER(?)",
            (username, email)
        ).fetchone()
        if existing_user:
            flash('A user with that username or email already exists.', 'danger')
            return render_template('register.html', username=username, full_name=full_name, email=email)

        password_hash = generate_password_hash(password)
        try:
            db.execute("""
                INSERT INTO users (username, email, password_hash, full_name, role, is_active)
                VALUES (?, ?, ?, ?, 'Member', 1)
            """, (username, email, password_hash, full_name))
            user_id = db.execute("SELECT last_insert_rowid() AS id").fetchone()['id']

            # If an existing member record exists with this email, link to this user account
            member_row = db.execute("SELECT id FROM members WHERE LOWER(email) = LOWER(?)", (email,)).fetchone()
            if member_row:
                db.execute("UPDATE members SET user_id = ? WHERE id = ?", (user_id, member_row['id']))

            db.commit()
            flash(f"Member account '{username}' created successfully! Please sign in through User Login.", 'success')
            return redirect(url_for('login', type='user'))
        except sqlite3.IntegrityError:
            db.rollback()
            flash('A user with that username or email already exists.', 'danger')
            return render_template('register.html', username=username, full_name=full_name, email=email)

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET' and 'user_id' in session:
        return redirect(url_for('dashboard'))

    # Determine login_type option (defaults to 'admin' unless 'user' requested)
    login_type = request.args.get('type', 'admin').strip().lower()
    if login_type not in ('admin', 'user'):
        login_type = 'admin'

    if request.method == 'POST':
        login_id = request.form.get('login_id', '').strip()
        password = request.form.get('password', '')

        # Check submitted login_type from form
        submitted_type = request.form.get('login_type', '').strip().lower()
        if submitted_type in ('admin', 'user'):
            login_type = submitted_type

        if not login_id or not password:
            flash('Please enter both your username/email and password.', 'warning')
            return render_template('login.html', login_id=login_id, login_type=login_type)

        db = get_db()
        prefix_alias = f"demo_{login_id}" if not login_id.lower().startswith('demo_') else login_id
        unprefix_alias = login_id[5:] if login_id.lower().startswith('demo_') else login_id

        user = db.execute("""
            SELECT * FROM users
            WHERE (LOWER(username) = LOWER(?)
                OR LOWER(username) = LOWER(?)
                OR LOWER(username) = LOWER(?)
                OR LOWER(email) = LOWER(?)) AND is_active = 1
        """, (login_id, prefix_alias, unprefix_alias, login_id)).fetchone()

        # Step 1: Verify credentials and account active status
        if not user or not check_password_hash(user['password_hash'], password):
            flash('Invalid credentials or account deactivated. Please try again.', 'danger')
            return render_template('login.html', login_id=login_id, login_type=login_type)

        # Step 2: Server-side validation of selected login option
        is_admin = (user['role'] == 'Administrator')
        if login_type == 'admin':
            if not is_admin:
                flash('Access denied: Non-admin accounts cannot sign in through Admin Login. Please use User Login.', 'danger')
                return render_template('login.html', login_id=login_id, login_type=login_type)
        elif login_type == 'user':
            if is_admin:
                flash('Access denied: Administrator accounts must sign in through Admin Login.', 'danger')
                return render_template('login.html', login_id=login_id, login_type=login_type)

        # Step 3: Establish authenticated session
        session.clear()
        session['user_id'] = user['id']
        session['username'] = user['username']
        session['full_name'] = user['full_name']
        session['role'] = user['role']
        flash(f"Welcome back, {user['full_name']}! Signed in as {user['role']}.", 'success')
        next_url = request.args.get('next')
        if next_url and next_url.startswith('/'):
            return redirect(next_url)
        return redirect(url_for('dashboard'))

    return render_template('login.html', login_type=login_type)


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been signed out successfully.', 'info')
    return redirect(url_for('login'))


@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],)).fetchone()
    if not user:
        abort(404)

    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'update_info':
            full_name = request.form.get('full_name', '').strip()
            email = request.form.get('email', '').strip().lower()
            phone = request.form.get('phone', '').strip()
            department = request.form.get('department', '').strip()
            academic_year = request.form.get('academic_year', '').strip()
            student_id = request.form.get('student_id', '').strip()
            bio = request.form.get('bio', '').strip()

            if not full_name or not email:
                flash('Full name and email are required.', 'danger')
            else:
                try:
                    db.execute("""
                        UPDATE users
                        SET full_name = ?, email = ?, phone = ?, department = ?,
                            academic_year = ?, student_id = ?, bio = ?
                        WHERE id = ?
                    """, (full_name, email, phone, department, academic_year, student_id, bio, session['user_id']))
                    db.commit()
                    session['full_name'] = full_name
                    flash('Profile information updated successfully.', 'success')
                except sqlite3.IntegrityError:
                    db.rollback()
                    flash('Email address is already in use by another user.', 'danger')
        elif action == 'update_preferences':
            notif_prefs = {
                'email': bool(request.form.get('notif_email')),
                'announcements': bool(request.form.get('notif_announcements')),
                'events': bool(request.form.get('notif_events'))
            }
            privacy_settings = {
                'show_on_leaderboard': bool(request.form.get('privacy_leaderboard')),
                'show_badges': bool(request.form.get('privacy_badges'))
            }
            db.execute("""
                UPDATE users
                SET notification_preferences = ?, privacy_settings = ?
                WHERE id = ?
            """, (json.dumps(notif_prefs), json.dumps(privacy_settings), session['user_id']))
            db.commit()
            flash('Preferences and privacy settings updated successfully.', 'success')
        elif action == 'change_password':
            current_pwd = request.form.get('current_password', '')
            new_pwd = request.form.get('new_password', '')
            confirm_new_pwd = request.form.get('confirm_new_password', '')

            if not check_password_hash(user['password_hash'], current_pwd):
                flash('Current password entered is incorrect.', 'danger')
            elif len(new_pwd) < 6:
                flash('New password must be at least 6 characters long.', 'danger')
            elif new_pwd != confirm_new_pwd:
                flash('New passwords do not match.', 'danger')
            else:
                db.execute("UPDATE users SET password_hash = ? WHERE id = ?",
                           (generate_password_hash(new_pwd), session['user_id']))
                db.commit()
                flash('Password changed successfully.', 'success')

        return redirect(url_for('profile'))

    # Parse notification & privacy preferences with sensible defaults
    notif_prefs = {"email": True, "announcements": True, "events": True}
    if user['notification_preferences']:
        try:
            notif_prefs.update(json.loads(user['notification_preferences']))
        except Exception:
            pass

    privacy_settings = {"show_on_leaderboard": True, "show_badges": True}
    if user['privacy_settings']:
        try:
            privacy_settings.update(json.loads(user['privacy_settings']))
        except Exception:
            pass

    return render_template('profile.html', user=user, notif_prefs=notif_prefs, privacy_settings=privacy_settings)


# -------------------------------------------------------------------------
# USER MANAGEMENT (ADMINISTRATOR ONLY)
# -------------------------------------------------------------------------

@app.route('/users')
@login_required
@role_required('Administrator')
def users_list():
    db = get_db()
    users = db.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
    return render_template('users/list.html', users=users)


@app.route('/users/new', methods=['GET', 'POST'])
@login_required
@role_required('Administrator')
def users_new():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        role = request.form.get('role', '')
        password = request.form.get('password', '')

        errors = []
        if not username or len(username) < 3:
            errors.append('Username must be at least 3 characters.')
        if not full_name:
            errors.append('Full name is required.')
        if not email or not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            errors.append('Valid email address is required.')
        if role not in ('Administrator', 'Treasurer', 'Event Organizer', 'Volunteer', 'Member'):
            errors.append('Invalid role selected.')
        if not password or len(password) < 6:
            errors.append('Password must be at least 6 characters.')

        if errors:
            for err in errors:
                flash(err, 'danger')
            return render_template('users/form.html', username=username, full_name=full_name, email=email, role=role)

        db = get_db()
        try:
            db.execute("""
                INSERT INTO users (username, email, password_hash, full_name, role, is_active)
                VALUES (?, ?, ?, ?, ?, 1)
            """, (username, email, generate_password_hash(password), full_name, role))
            db.commit()
            flash(f"User account '{username}' ({role}) created successfully.", 'success')
            return redirect(url_for('users_list'))
        except sqlite3.IntegrityError:
            db.rollback()
            flash('A user with that username or email already exists.', 'danger')

    return render_template('users/form.html')


@app.route('/users/<int:user_id>/toggle', methods=['POST'])
@login_required
@role_required('Administrator')
def users_toggle(user_id):
    if user_id == session['user_id']:
        flash('You cannot deactivate your own active account.', 'warning')
        return redirect(url_for('users_list'))

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        abort(404)

    new_status = 0 if user['is_active'] else 1
    db.execute("UPDATE users SET is_active = ? WHERE id = ?", (new_status, user_id))
    db.commit()
    status_text = 'activated' if new_status else 'deactivated'
    flash(f"User '{user['username']}' has been {status_text}.", 'info')
    return redirect(url_for('users_list'))


# -------------------------------------------------------------------------
# DASHBOARD
# -------------------------------------------------------------------------

@app.route('/')
@app.route('/dashboard')
@login_required
def dashboard():
    db = get_db()
    today = date.today().isoformat()

    # 1. Members metrics
    total_members_row = db.execute("SELECT COUNT(*) AS count FROM members").fetchone()
    total_members = total_members_row['count'] if total_members_row else 0

    active_members_row = db.execute("""
        SELECT COUNT(*) AS count FROM members
        WHERE status = 'Active' AND expiry_date >= ?
    """, (today,)).fetchone()
    active_members = active_members_row['count'] if active_members_row else 0

    # Outstanding dues
    dues_row = db.execute("""
        SELECT COALESCE(SUM(MAX(membership_fee - amount_paid, 0)), 0) AS dues
        FROM members
        WHERE status IN ('Active', 'Pending')
    """).fetchone()
    outstanding_dues = dues_row['dues'] if dues_row else 0.0

    # 2. Events and Tickets metrics
    upcoming_events_row = db.execute("""
        SELECT COUNT(*) AS count FROM events
        WHERE event_date >= ? AND status != 'Cancelled'
    """, (today,)).fetchone()
    upcoming_events = upcoming_events_row['count'] if upcoming_events_row else 0

    tickets_sold_row = db.execute("""
        SELECT COUNT(*) AS count FROM tickets
        WHERE payment_status = 'Confirmed'
    """).fetchone()
    total_tickets_sold = tickets_sold_row['count'] if tickets_sold_row else 0

    # Available seats across upcoming events
    events_seat_stats = db.execute("""
        SELECT e.id, e.title, e.capacity,
               COUNT(t.id) AS sold,
               (e.capacity - COUNT(t.id)) AS remaining
        FROM events e
        LEFT JOIN tickets t ON e.id = t.event_id AND t.payment_status = 'Confirmed'
        WHERE e.event_date >= ? AND e.status != 'Cancelled'
        GROUP BY e.id
    """, (today,)).fetchall()

    total_capacity = sum(row['capacity'] for row in events_seat_stats)
    total_available_seats = sum(max(row['remaining'], 0) for row in events_seat_stats)

    # 3. Financial Metrics from Ledger
    income_row = db.execute("""
        SELECT COALESCE(SUM(amount), 0) AS total
        FROM financial_transactions
        WHERE transaction_type = 'Income'
    """).fetchone()
    recorded_income = income_row['total'] if income_row else 0.0

    expenses_row = db.execute("""
        SELECT COALESCE(SUM(amount), 0) AS total
        FROM financial_transactions
        WHERE transaction_type = 'Expense'
    """).fetchone()
    paid_expenses = expenses_row['total'] if expenses_row else 0.0

    net_cash_movement = recorded_income - paid_expenses

    # Pending Expense requests
    pending_expenses_row = db.execute("""
        SELECT COUNT(*) AS count, COALESCE(SUM(amount), 0) AS amount
        FROM expense_requests
        WHERE status = 'Pending'
    """).fetchone()
    pending_expenses_count = pending_expenses_row['count'] if pending_expenses_row else 0
    pending_expenses_amount = pending_expenses_row['amount'] if pending_expenses_row else 0.0

    # 4. Merchandise Stock Alerts (low stock or zero stock)
    stock_alerts = db.execute("""
        SELECT v.id, v.sku, v.size, v.stock_quantity, v.low_stock_threshold,
               m.name AS item_name, m.category
        FROM merchandise_variants v
        JOIN merchandise_items m ON v.item_id = m.id
        WHERE v.stock_quantity <= v.low_stock_threshold AND m.is_active = 1
        ORDER BY v.stock_quantity ASC
    """).fetchall()

    # 5. Top 5 Upcoming Events with sold count
    upcoming_events_list = db.execute("""
        SELECT e.*, COUNT(t.id) AS sold_count
        FROM events e
        LEFT JOIN tickets t ON e.id = t.event_id AND t.payment_status = 'Confirmed'
        WHERE e.event_date >= ? AND e.status != 'Cancelled'
        GROUP BY e.id
        ORDER BY e.event_date ASC, e.event_time ASC
        LIMIT 5
    """, (today,)).fetchall()

    # 6. Recent Financial Transactions
    recent_transactions = db.execute("""
        SELECT * FROM financial_transactions
        ORDER BY transaction_date DESC, id DESC
        LIMIT 5
    """).fetchall()

    # 7. Recent Announcements
    user_role = session.get('role', 'Member')
    announcements_audience = ['All']
    if user_role in ('Member', 'Administrator', 'Treasurer', 'Event Organizer', 'Volunteer'):
        announcements_audience.append('Members')
    if user_role in ('Volunteer', 'Administrator', 'Event Organizer'):
        announcements_audience.append('Volunteers')
    if user_role in ('Administrator', 'Treasurer', 'Event Organizer'):
        announcements_audience.append('Executive')

    placeholders = ','.join('?' for _ in announcements_audience)
    recent_announcements = db.execute(f"""
        SELECT a.*, u.full_name AS publisher_name
        FROM announcements a
        JOIN users u ON a.published_by = u.id
        WHERE a.audience IN ({placeholders})
        ORDER BY a.created_at DESC
        LIMIT 4
    """, announcements_audience).fetchall()

    return render_template(
        'dashboard.html',
        total_members=total_members,
        active_members=active_members,
        outstanding_dues=outstanding_dues,
        upcoming_events=upcoming_events,
        total_tickets_sold=total_tickets_sold,
        total_capacity=total_capacity,
        total_available_seats=total_available_seats,
        recorded_income=recorded_income,
        paid_expenses=paid_expenses,
        net_cash_movement=net_cash_movement,
        pending_expenses_count=pending_expenses_count,
        pending_expenses_amount=pending_expenses_amount,
        stock_alerts=stock_alerts,
        upcoming_events_list=upcoming_events_list,
        recent_transactions=recent_transactions,
        recent_announcements=recent_announcements
    )


# -------------------------------------------------------------------------
# BUSINESS ANALYTICS
# -------------------------------------------------------------------------

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
# -------------------------------------------------------------------------

@app.route('/members')
@login_required
@role_required('Administrator', 'Treasurer', 'Event Organizer')
def members_list():
    db = get_db()
    search = request.args.get('search', '').strip()
    status_filter = request.args.get('status', '').strip()
    type_filter = request.args.get('type', '').strip()
    view_mode = request.args.get('view', 'cards').strip().lower()
    today_iso = date.today().isoformat()

    # 1. Summary Cards (Live database calculations, single source of truth)
    total_members_count = db.execute("SELECT COUNT(*) AS count FROM members").fetchone()['count']
    active_members_count = db.execute("""
        SELECT COUNT(*) AS count FROM members
        WHERE status = 'Active' AND expiry_date >= ?
    """, (today_iso,)).fetchone()['count']
    expired_members_count = db.execute("""
        SELECT COUNT(*) AS count FROM members
        WHERE status = 'Expired' OR expiry_date < ?
    """, (today_iso,)).fetchone()['count']
    dues_row = db.execute("""
        SELECT COALESCE(SUM(MAX(membership_fee - amount_paid, 0)), 0) AS dues
        FROM members
        WHERE status IN ('Active', 'Pending')
    """).fetchone()
    outstanding_dues = dues_row['dues'] if dues_row else 0.0

    summary_stats = {
        'total': total_members_count,
        'active': active_members_count,
        'expired': expired_members_count,
        'outstanding_dues': outstanding_dues
    }

    # 2. Member records with calculated status and non-negative dues
    query = """
        SELECT m.*,
               MAX(m.membership_fee - m.amount_paid, 0) AS balance_dues,
               CASE
                   WHEN m.expiry_date < ? THEN 'Expired'
                   ELSE m.status
               END AS calculated_status
        FROM members m
        WHERE 1=1
    """
    params = [today_iso]

    if search:
        query += """ AND (
            m.full_name LIKE ? OR
            m.member_code LIKE ? OR
            m.email LIKE ? OR
            m.phone LIKE ? OR
            m.student_id LIKE ? OR
            m.department LIKE ?
        )"""
        term = f"%{search}%"
        params.extend([term, term, term, term, term, term])

    if status_filter:
        if status_filter == 'Expired':
            query += " AND (m.expiry_date < ? OR m.status = 'Expired')"
            params.append(today_iso)
        elif status_filter == 'Active':
            query += " AND (m.expiry_date >= ? AND m.status = 'Active')"
            params.append(today_iso)
        else:
            query += " AND m.status = ?"
            params.append(status_filter)

    if type_filter:
        query += " AND m.membership_type = ?"
        params.append(type_filter)

    query += " ORDER BY m.created_at DESC"
    members = db.execute(query, params).fetchall()

    return render_template(
        'members/list.html',
        members=members,
        search=search,
        status_filter=status_filter,
        type_filter=type_filter,
        view_mode=view_mode,
        summary_stats=summary_stats
    )


@app.route('/members/new', methods=['GET', 'POST'])
@login_required
@role_required('Administrator', 'Treasurer')
def members_new():
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        phone = request.form.get('phone', '').strip()
        student_id = request.form.get('student_id', '').strip()
        department = request.form.get('department', '').strip()
        join_date = request.form.get('join_date', '').strip()
        expiry_date = request.form.get('expiry_date', '').strip()
        membership_type = request.form.get('membership_type', 'Annual')
        notes = request.form.get('notes', '').strip()

        # Fee & initial payment validation
        try:
            membership_fee = float(request.form.get('membership_fee', 0))
            if membership_fee < 0:
                raise ValueError()
        except ValueError:
            membership_fee = 0.0

        try:
            initial_payment = float(request.form.get('initial_payment', 0))
            if initial_payment < 0:
                raise ValueError()
        except ValueError:
            initial_payment = 0.0

        payment_method = request.form.get('payment_method', 'Cash')
        payment_ref = request.form.get('payment_ref', '').strip()

        errors = []
        if not full_name:
            errors.append('Full name is required.')
        if not email or not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            errors.append('A valid email address is required.')
        if not join_date:
            errors.append('Membership start date is required.')
        if not expiry_date:
            errors.append('Membership expiry date is required.')
        if join_date and expiry_date and expiry_date < join_date:
            errors.append('Expiry date cannot be earlier than the start date.')
        if initial_payment > membership_fee and membership_fee > 0:
            errors.append('Initial payment cannot exceed the total membership fee.')

        if errors:
            for err in errors:
                flash(err, 'danger')
            return render_template('members/form.html', form_data=request.form)

        db = get_db()
        # Prevent duplicate email
        existing_email = db.execute("SELECT id FROM members WHERE LOWER(email) = LOWER(?)", (email,)).fetchone()
        if existing_email:
            flash(f"A member with email '{email}' is already registered.", 'danger')
            return render_template('members/form.html', form_data=request.form)

        # Generate unique member code: CS-MEM-YYYY-XXXX
        year_str = datetime.now().year
        last_member = db.execute("SELECT id FROM members ORDER BY id DESC LIMIT 1").fetchone()
        next_num = (last_member['id'] + 1) if last_member else 1
        member_code = f"CS-MEM-{year_str}-{next_num:04d}"

        # Determine initial status
        today_iso = date.today().isoformat()
        if expiry_date < today_iso:
            initial_status = 'Expired'
        elif initial_payment >= membership_fee:
            initial_status = 'Active'
        elif initial_payment > 0:
            initial_status = 'Active'
        else:
            initial_status = 'Pending'

        try:
            # Begin atomic transaction
            cursor = db.cursor()
            cursor.execute("""
                INSERT INTO members (
                    member_code, full_name, email, phone, student_id,
                    department, join_date, expiry_date, membership_type,
                    membership_fee, amount_paid, status, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                member_code, full_name, email, phone, student_id,
                department, join_date, expiry_date, membership_type,
                membership_fee, initial_payment, initial_status, notes
            ))
            member_id = cursor.lastrowid

            # Record initial payment in ledger if > 0
            if initial_payment > 0:
                cursor.execute("""
                    INSERT INTO membership_payments (
                        member_id, amount, payment_date, payment_method, reference_no, notes, created_by
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    member_id, initial_payment, join_date, payment_method,
                    payment_ref, 'Initial registration payment', session.get('user_id')
                ))
                payment_id = cursor.lastrowid

                # Financial ledger entry
                cursor.execute("""
                    INSERT INTO financial_transactions (
                        transaction_type, category, amount, description,
                        source_type, source_id, payment_method, transaction_date, recorded_by
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    'Income', 'Membership Fee', initial_payment,
                    f"Membership Fee for {full_name} ({member_code})",
                    'membership_payment', payment_id, payment_method, join_date, session.get('user_id')
                ))

            db.commit()
            session['success_modal'] = {
                'title': 'Member Registered Successfully!',
                'subtitle': f"{full_name} is now registered in the ClubSphere directory.",
                'badge': 'REGISTRATION CONFIRMED',
                'details': [
                    {'label': 'Member Code', 'value': member_code, 'is_code': True, 'highlight': True},
                    {'label': 'Full Name', 'value': full_name},
                    {'label': 'Department', 'value': department or 'General'},
                    {'label': 'Membership Type', 'value': membership_type},
                    {'label': 'Status', 'value': initial_status, 'is_badge': True, 'badge_class': 'badge-active' if initial_status == 'Active' else 'badge-pending'},
                    {'label': 'Amount Paid', 'value': currency_filter(initial_payment), 'is_success': True} if initial_payment > 0 else None,
                    {'label': 'Valid Until', 'value': format_date_filter(expiry_date)},
                ],
                'actions': [
                    {'label': 'View Member Profile', 'url': url_for('member_view', member_id=member_id), 'primary': True},
                    {'label': 'Membership Directory', 'url': url_for('members_list'), 'secondary': True}
                ]
            }
            session['success_modal']['details'] = [d for d in session['success_modal']['details'] if d is not None]
            flash(f"Member {full_name} ({member_code}) registered successfully!", 'success')
            return redirect(url_for('member_view', member_id=member_id))
        except sqlite3.IntegrityError as e:
            db.rollback()
            flash(f"Database error during registration: {str(e)}", 'danger')

    today_val = date.today().isoformat()
    # default expiry: 1 year from today
    next_year_val = date.today().replace(year=date.today().year + 1).isoformat()
    return render_template('members/form.html', default_join=today_val, default_expiry=next_year_val)


@app.route('/members/<int:member_id>')
@login_required
def member_view(member_id):
    db = get_db()
    member = db.execute("SELECT * FROM members WHERE id = ?", (member_id,)).fetchone()
    if not member:
        abort(404)

    # Payments history
    payments = db.execute("""
        SELECT mp.*, u.full_name AS recorder_name
        FROM membership_payments mp
        LEFT JOIN users u ON mp.created_by = u.id
        WHERE mp.member_id = ?
        ORDER BY mp.payment_date DESC, mp.id DESC
    """, (member_id,)).fetchall()

    # Event tickets purchased
    tickets = db.execute("""
        SELECT t.*, e.title AS event_title, e.event_date
        FROM tickets t
        JOIN events e ON t.event_id = e.id
        WHERE t.member_id = ? OR LOWER(t.purchaser_email) = LOWER(?)
        ORDER BY t.created_at DESC
    """, (member_id, member['email'])).fetchall()

    # Calculate current effective status
    today_iso = date.today().isoformat()
    is_expired = str(member['expiry_date']) < today_iso
    outstanding_dues = max(member['membership_fee'] - member['amount_paid'], 0.0)

    return render_template(
        'members/view.html',
        member=member,
        payments=payments,
        tickets=tickets,
        is_expired=is_expired,
        outstanding_dues=outstanding_dues
    )


@app.route('/members/<int:member_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('Administrator', 'Treasurer')
def members_edit(member_id):
    db = get_db()
    member = db.execute("SELECT * FROM members WHERE id = ?", (member_id,)).fetchone()
    if not member:
        abort(404)

    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        phone = request.form.get('phone', '').strip()
        student_id = request.form.get('student_id', '').strip()
        department = request.form.get('department', '').strip()
        join_date = request.form.get('join_date', '').strip()
        expiry_date = request.form.get('expiry_date', '').strip()
        membership_type = request.form.get('membership_type', member['membership_type'])
        status = request.form.get('status', member['status'])
        notes = request.form.get('notes', '').strip()

        try:
            membership_fee = float(request.form.get('membership_fee', member['membership_fee']))
            if membership_fee < 0:
                raise ValueError()
        except ValueError:
            membership_fee = member['membership_fee']

        errors = []
        if not full_name:
            errors.append('Full name is required.')
        if not email or not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            errors.append('Valid email is required.')
        if not join_date or not expiry_date:
            errors.append('Join date and expiry date are required.')
        if join_date and expiry_date and expiry_date < join_date:
            errors.append('Expiry date cannot precede join date.')

        # Check unique email excluding this member
        dup = db.execute("SELECT id FROM members WHERE LOWER(email) = LOWER(?) AND id != ?", (email, member_id)).fetchone()
        if dup:
            errors.append('Email is already registered to another member.')

        if errors:
            for err in errors:
                flash(err, 'danger')
            return render_template('members/edit.html', member=member)

        # Update member record
        db.execute("""
            UPDATE members SET
                full_name = ?, email = ?, phone = ?, student_id = ?,
                department = ?, join_date = ?, expiry_date = ?,
                membership_type = ?, membership_fee = ?, status = ?, notes = ?
            WHERE id = ?
        """, (
            full_name, email, phone, student_id, department,
            join_date, expiry_date, membership_type, membership_fee, status, notes, member_id
        ))
        db.commit()
        flash('Member profile updated successfully.', 'success')
        return redirect(url_for('member_view', member_id=member_id))

    return render_template('members/edit.html', member=member)


@app.route('/members/<int:member_id>/pay', methods=['POST'])
@login_required
@role_required('Administrator', 'Treasurer')
def members_record_payment(member_id):
    db = get_db()
    member = db.execute("SELECT * FROM members WHERE id = ?", (member_id,)).fetchone()
    if not member:
        abort(404)

    try:
        amount = float(request.form.get('amount', 0))
        if amount <= 0:
            flash('Payment amount must be greater than zero.', 'danger')
            return redirect(url_for('member_view', member_id=member_id))
    except ValueError:
        flash('Invalid payment amount format.', 'danger')
        return redirect(url_for('member_view', member_id=member_id))

    outstanding_dues = max(member['membership_fee'] - member['amount_paid'], 0.0)
    if outstanding_dues <= 0:
        flash('This member has no outstanding dues to settle.', 'info')
        return redirect(url_for('member_view', member_id=member_id))

    if amount > outstanding_dues:
        flash(f'Payment amount ({currency_filter(amount)}) cannot exceed outstanding dues ({currency_filter(outstanding_dues)}).', 'danger')
        return redirect(url_for('member_view', member_id=member_id))

    # Prevent duplicate payment submission within 10 seconds
    recent_dup = db.execute("""
        SELECT id FROM membership_payments
        WHERE member_id = ? AND amount = ? AND created_at >= DATETIME('now', '-10 seconds')
    """, (member_id, amount)).fetchone()
    if recent_dup:
        flash('Duplicate payment submission detected and ignored.', 'warning')
        return redirect(url_for('member_view', member_id=member_id))

    payment_date = request.form.get('payment_date', date.today().isoformat())
    payment_method = request.form.get('payment_method', 'Cash')
    reference_no = request.form.get('reference_no', '').strip()
    notes = request.form.get('notes', '').strip()

    try:
        cursor = db.cursor()
        # 1. Insert payment record
        cursor.execute("""
            INSERT INTO membership_payments (
                member_id, amount, payment_date, payment_method, reference_no, notes, created_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            member_id, amount, payment_date, payment_method, reference_no, notes, session.get('user_id')
        ))
        payment_id = cursor.lastrowid

        # 2. Update member paid amount and status
        new_paid = member['amount_paid'] + amount
        new_status = member['status']
        if new_paid >= member['membership_fee'] and str(member['expiry_date']) >= date.today().isoformat():
            new_status = 'Active'

        cursor.execute("""
            UPDATE members SET amount_paid = ?, status = ? WHERE id = ?
        """, (new_paid, new_status, member_id))

        # 3. Insert into financial transactions ledger
        cursor.execute("""
            INSERT INTO financial_transactions (
                transaction_type, category, amount, description,
                source_type, source_id, payment_method, transaction_date, recorded_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            'Income', 'Membership Fee', amount,
            f"Dues Payment for {member['full_name']} ({member['member_code']})",
            'membership_payment', payment_id, payment_method, payment_date, session.get('user_id')
        ))

        db.commit()
        remaining_dues = max(member['membership_fee'] - new_paid, 0.0)
        session['success_modal'] = {
            'title': 'Dues Payment Recorded!',
            'subtitle': f"Payment for {member['full_name']} has been posted to the financial ledger.",
            'badge': 'PAYMENT RECORDED',
            'details': [
                {'label': 'Member Code', 'value': member['member_code'], 'is_code': True},
                {'label': 'Member Name', 'value': member['full_name']},
                {'label': 'Amount Settled', 'value': currency_filter(amount), 'is_success': True},
                {'label': 'Payment Method', 'value': payment_method},
                {'label': 'Transaction Ref', 'value': reference_no, 'is_code': True} if reference_no else None,
                {'label': 'Total Paid to Date', 'value': currency_filter(new_paid)},
                {'label': 'Remaining Dues', 'value': currency_filter(remaining_dues), 'highlight': (remaining_dues > 0)},
            ],
            'actions': [
                {'label': 'Done', 'dismiss': True, 'primary': True},
                {'label': 'View Financial Ledger', 'url': url_for('finance_ledger'), 'secondary': True}
            ]
        }
        session['success_modal']['details'] = [d for d in session['success_modal']['details'] if d is not None]
        flash(f"Payment of {currency_filter(amount)} recorded successfully.", 'success')
    except Exception as e:
        db.rollback()
        flash(f"Failed to record payment: {str(e)}", 'danger')

    return redirect(url_for('member_view', member_id=member_id))


@app.route('/members/<int:member_id>/renew', methods=['POST'])
@login_required
@role_required('Administrator', 'Treasurer')
def members_renew(member_id):
    db = get_db()
    member = db.execute("SELECT * FROM members WHERE id = ?", (member_id,)).fetchone()
    if not member:
        abort(404)

    new_expiry_date = request.form.get('new_expiry_date', '').strip()
    try:
        renewal_fee = float(request.form.get('renewal_fee', 0))
        if renewal_fee < 0:
            raise ValueError()
    except ValueError:
        renewal_fee = 0.0

    try:
        payment_amount = float(request.form.get('payment_amount', 0))
        if payment_amount < 0:
            raise ValueError()
    except ValueError:
        payment_amount = 0.0

    payment_method = request.form.get('payment_method', 'Cash')
    reference_no = request.form.get('reference_no', '').strip()

    if not new_expiry_date or str(new_expiry_date) <= str(member['expiry_date']):
        flash('New expiry date must be later than current expiry date.', 'danger')
        return redirect(url_for('member_view', member_id=member_id))

    if renewal_fee > 0 and payment_amount > renewal_fee:
        flash(f'Payment amount ({currency_filter(payment_amount)}) cannot exceed the renewal fee ({currency_filter(renewal_fee)}).', 'danger')
        return redirect(url_for('member_view', member_id=member_id))

    try:
        cursor = db.cursor()
        new_total_fee = member['membership_fee'] + renewal_fee
        new_total_paid = member['amount_paid'] + payment_amount
        new_status = 'Active'

        cursor.execute("""
            UPDATE members SET
                expiry_date = ?,
                membership_fee = ?,
                amount_paid = ?,
                status = ?
            WHERE id = ?
        """, (new_expiry_date, new_total_fee, new_total_paid, new_status, member_id))

        if payment_amount > 0:
            today_iso = date.today().isoformat()
            cursor.execute("""
                INSERT INTO membership_payments (
                    member_id, amount, payment_date, payment_method, reference_no, notes, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                member_id, payment_amount, today_iso, payment_method, reference_no,
                f"Renewal payment (extended to {new_expiry_date})", session.get('user_id')
            ))
            payment_id = cursor.lastrowid

            cursor.execute("""
                INSERT INTO financial_transactions (
                    transaction_type, category, amount, description,
                    source_type, source_id, payment_method, transaction_date, recorded_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                'Income', 'Membership Fee', payment_amount,
                f"Membership Renewal for {member['full_name']} ({member['member_code']})",
                'membership_payment', payment_id, payment_method, today_iso, session.get('user_id')
            ))

        db.commit()
        session['success_modal'] = {
            'title': 'Membership Renewed Successfully!',
            'subtitle': f"Membership for {member['full_name']} has been extended.",
            'badge': 'RENEWAL COMPLETED',
            'details': [
                {'label': 'Member Code', 'value': member['member_code'], 'is_code': True},
                {'label': 'Member Name', 'value': member['full_name']},
                {'label': 'Extended Until', 'value': format_date_filter(new_expiry_date)},
                {'label': 'Renewal Fee', 'value': currency_filter(renewal_fee)},
                {'label': 'Amount Paid', 'value': currency_filter(payment_amount), 'is_success': True} if payment_amount > 0 else None,
                {'label': 'Payment Ref', 'value': reference_no, 'is_code': True} if reference_no else None,
            ],
            'actions': [
                {'label': 'Done', 'dismiss': True, 'primary': True},
                {'label': 'Membership Directory', 'url': url_for('members_list'), 'secondary': True}
            ]
        }
        session['success_modal']['details'] = [d for d in session['success_modal']['details'] if d is not None]
        flash(f"Membership for {member['full_name']} renewed until {format_date_filter(new_expiry_date)}.", 'success')
    except Exception as e:
        db.rollback()
        flash(f"Failed to renew membership: {str(e)}", 'danger')

    return redirect(url_for('member_view', member_id=member_id))


# -------------------------------------------------------------------------
# EVENT AND TICKET MANAGEMENT
# -------------------------------------------------------------------------

@app.route('/events')
@login_required
def events_list():
    db = get_db()
    status_filter = request.args.get('status', '').strip()
    search = request.args.get('search', '').strip()

    query = """
        SELECT e.*,
               COUNT(t.id) AS tickets_sold,
               (e.capacity - COUNT(t.id)) AS remaining_seats,
               COALESCE(SUM(t.price_paid), 0) AS total_revenue
        FROM events e
        LEFT JOIN tickets t ON e.id = t.event_id AND t.payment_status = 'Confirmed'
        WHERE 1=1
    """
    params = []

    if search:
        query += " AND (e.title LIKE ? OR e.venue LIKE ? OR e.description LIKE ?)"
        term = f"%{search}%"
        params.extend([term, term, term])

    if status_filter:
        query += " AND e.status = ?"
        params.append(status_filter)

    query += " GROUP BY e.id ORDER BY e.event_date ASC, e.event_time ASC"
    events = db.execute(query, params).fetchall()
    view_mode = request.args.get('view', 'cards').strip()

    return render_template(
        'events/list.html',
        events=events,
        status_filter=status_filter,
        search=search,
        view_mode=view_mode
    )


@app.route('/events/new', methods=['GET', 'POST'])
@login_required
@role_required('Administrator', 'Event Organizer')
def events_new():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        event_date = request.form.get('event_date', '').strip()
        event_time = request.form.get('event_time', '').strip()
        venue = request.form.get('venue', '').strip()

        try:
            capacity = int(request.form.get('capacity', 0))
            if capacity <= 0:
                raise ValueError()
        except ValueError:
            capacity = 0

        try:
            member_price = float(request.form.get('member_price', 0))
            if member_price < 0:
                raise ValueError()
        except ValueError:
            member_price = 0.0

        try:
            non_member_price = float(request.form.get('non_member_price', 0))
            if non_member_price < 0:
                raise ValueError()
        except ValueError:
            non_member_price = 0.0

        errors = []
        if not title:
            errors.append('Event title is required.')
        if not event_date:
            errors.append('Event date is required.')
        if not event_time:
            errors.append('Event time is required.')
        if not venue:
            errors.append('Venue is required.')
        if capacity <= 0:
            errors.append('Capacity must be a positive number of seats.')

        poster_path = None
        poster_file = request.files.get('poster_image')
        if poster_file and poster_file.filename:
            try:
                poster_path = save_event_poster(poster_file)
            except ValueError as ve:
                errors.append(str(ve))

        if errors:
            for err in errors:
                flash(err, 'danger')
            return render_template('events/form.html', form_data=request.form)

        db = get_db()
        cursor = db.cursor()
        cursor.execute("""
            INSERT INTO events (
                title, description, event_date, event_time, venue,
                capacity, member_price, non_member_price, status, poster_image, created_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Upcoming', ?, ?)
        """, (
            title, description, event_date, event_time, venue,
            capacity, member_price, non_member_price, poster_path, session.get('user_id')
        ))
        db.commit()
        event_id = cursor.lastrowid
        flash(f"Event '{title}' created successfully!", 'success')
        return redirect(url_for('event_view', event_id=event_id))

    return render_template('events/form.html')


@app.route('/events/<int:event_id>')
@login_required
def event_view(event_id):
    db = get_db()
    event = db.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    if not event:
        abort(404)

    # Tickets list
    tickets = db.execute("""
        SELECT t.*, u.full_name AS checkin_by_name
        FROM tickets t
        LEFT JOIN users u ON t.checked_in_by = u.id
        WHERE t.event_id = ?
        ORDER BY t.created_at DESC
    """, (event_id,)).fetchall()

    tickets_sold = len([t for t in tickets if t['payment_status'] == 'Confirmed'])
    tickets_checked_in = len([t for t in tickets if t['checked_in'] == 1])
    remaining_seats = max(event['capacity'] - tickets_sold, 0)
    event_revenue = sum(t['price_paid'] for t in tickets if t['payment_status'] == 'Confirmed')

    # Associated expenses
    expenses = db.execute("""
        SELECT * FROM expense_requests
        WHERE event_id = ?
        ORDER BY created_at DESC
    """, (event_id,)).fetchall()
    paid_expenses = sum(e['amount'] for e in expenses if e['status'] == 'Paid')
    net_event_profit = event_revenue - paid_expenses

    # Volunteer tasks for this event
    tasks = db.execute("""
        SELECT vt.*, u.full_name AS assignee_name
        FROM volunteer_tasks vt
        LEFT JOIN users u ON vt.assigned_to = u.id
        WHERE vt.event_id = ?
        ORDER BY vt.deadline ASC, vt.id DESC
    """, (event_id,)).fetchall()

    return render_template(
        'events/view.html',
        event=event,
        tickets=tickets,
        tickets_sold=tickets_sold,
        tickets_checked_in=tickets_checked_in,
        remaining_seats=remaining_seats,
        event_revenue=event_revenue,
        paid_expenses=paid_expenses,
        net_event_profit=net_event_profit,
        expenses=expenses,
        tasks=tasks
    )


@app.route('/events/<int:event_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('Administrator', 'Event Organizer')
def events_edit(event_id):
    db = get_db()
    event = db.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    if not event:
        abort(404)

    # Tickets sold
    sold_row = db.execute("SELECT COUNT(*) AS count FROM tickets WHERE event_id = ? AND payment_status = 'Confirmed'", (event_id,)).fetchone()
    tickets_sold = sold_row['count'] if sold_row else 0

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        event_date = request.form.get('event_date', '').strip()
        event_time = request.form.get('event_time', '').strip()
        venue = request.form.get('venue', '').strip()
        status = request.form.get('status', event['status'])

        errors = []
        if not title:
            errors.append('Event title is required.')
        if not event_date:
            errors.append('Event date is required.')
        if not event_time:
            errors.append('Event time is required.')
        if not venue:
            errors.append('Venue is required.')

        try:
            capacity = int(request.form.get('capacity', event['capacity']))
            if capacity <= 0:
                errors.append('Capacity must be a positive number of seats.')
            elif capacity < tickets_sold:
                errors.append(f"Capacity cannot be reduced below already sold tickets ({tickets_sold}).")
        except ValueError:
            capacity = event['capacity']

        try:
            member_price = float(request.form.get('member_price', event['member_price']))
            if member_price < 0:
                errors.append('Member price cannot be negative.')
            non_member_price = float(request.form.get('non_member_price', event['non_member_price']))
            if non_member_price < 0:
                errors.append('Non-member price cannot be negative.')
        except ValueError:
            member_price = event['member_price']
            non_member_price = event['non_member_price']

        poster_path = event['poster_image']
        poster_file = request.files.get('poster_image')
        if poster_file and poster_file.filename:
            try:
                poster_path = save_event_poster(poster_file)
            except ValueError as ve:
                errors.append(str(ve))

        if errors:
            for err in errors:
                flash(err, 'danger')
            return render_template('events/edit.html', event=event, tickets_sold=tickets_sold)

        db.execute("""
            UPDATE events SET
                title = ?, description = ?, event_date = ?, event_time = ?,
                venue = ?, capacity = ?, member_price = ?, non_member_price = ?,
                status = ?, poster_image = ?
            WHERE id = ?
        """, (
            title, description, event_date, event_time, venue,
            capacity, member_price, non_member_price, status, poster_path, event_id
        ))
        db.commit()
        flash('Event updated successfully.', 'success')
        return redirect(url_for('event_view', event_id=event_id))

    return render_template('events/edit.html', event=event, tickets_sold=tickets_sold)


@app.route('/events/<int:event_id>/sell', methods=['GET', 'POST'])
@login_required
@role_required('Administrator', 'Event Organizer', 'Treasurer')
def events_sell_ticket(event_id):
    db = get_db()
    event = db.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    if not event:
        abort(404)

    if request.method == 'POST':
        purchaser_name = request.form.get('purchaser_name', '').strip()
        purchaser_email = request.form.get('purchaser_email', '').strip().lower()
        purchaser_phone = request.form.get('purchaser_phone', '').strip()
        member_lookup = request.form.get('member_lookup', '').strip()
        payment_method = request.form.get('payment_method', 'Cash')

        errors = []
        if not purchaser_name:
            errors.append('Attendee / purchaser name is required.')
        if not purchaser_email or not re.match(r"[^@]+@[^@]+\.[^@]+", purchaser_email):
            errors.append('A valid purchaser email address is required.')

        if errors:
            for err in errors:
                flash(err, 'danger')
            return render_template('tickets/sell.html', event=event)

        # -------------------------------------------------------------
        # TRANSACTION & OVERSELLING PREVENTION
        # -------------------------------------------------------------
        try:
            cursor = db.cursor()
            # Explicit write transaction to prevent race conditions
            cursor.execute("BEGIN IMMEDIATE")

            # Verify capacity
            cap_row = cursor.execute("""
                SELECT e.capacity,
                       (SELECT COUNT(*) FROM tickets t WHERE t.event_id = e.id AND t.payment_status = 'Confirmed') AS sold
                FROM events e
                WHERE e.id = ?
            """, (event_id,)).fetchone()

            if not cap_row:
                cursor.execute("ROLLBACK")
                flash('Event not found.', 'danger')
                return redirect(url_for('events_list'))

            if cap_row['sold'] >= cap_row['capacity']:
                cursor.execute("ROLLBACK")
                flash(f"Overselling rejected: Event '{event['title']}' is completely full ({cap_row['sold']}/{cap_row['capacity']} seats).", 'danger')
                return redirect(url_for('event_view', event_id=event_id))

            # Check membership eligibility
            member_id = None
            is_member_rate = 0
            ticket_price = event['non_member_price']

            if member_lookup:
                member_row = cursor.execute("""
                    SELECT * FROM members
                    WHERE (LOWER(member_code) = LOWER(?) OR LOWER(email) = LOWER(?))
                """, (member_lookup, member_lookup)).fetchone()

                if member_row:
                    today_iso = date.today().isoformat()
                    # Eligible if Active and not expired on event date (or today)
                    if member_row['status'] == 'Active' and str(member_row['expiry_date']) >= min(today_iso, str(event['event_date'])):
                        member_id = member_row['id']
                        is_member_rate = 1
                        ticket_price = event['member_price']
                        # Auto-fill name/email if empty
                        if not purchaser_name:
                            purchaser_name = member_row['full_name']
                        if not purchaser_email:
                            purchaser_email = member_row['email']
                    else:
                        flash(f"Member {member_row['member_code']} is expired or inactive. Non-member pricing ({currency_filter(event['non_member_price'])}) applied.", 'warning')
                else:
                    flash(f"No member found matching '{member_lookup}'. Non-member pricing applied.", 'warning')

            # Generate unique ticket reference: CS-TKT-<event_id>-<random_hex>
            ticket_ref = f"CS-TKT-{event_id}-{secrets.token_hex(4).upper()}"
            payment_ref = f"DEMO-TXN-{int(time.time())}-{secrets.token_hex(4).upper()}"
            qr_payload = f"CLUBSPERE:{ticket_ref}:{event_id}:{secrets.token_hex(6)}"

            cursor.execute("""
                INSERT INTO tickets (
                    ticket_ref, event_id, purchaser_name, purchaser_email, purchaser_phone,
                    member_id, price_paid, is_member_rate, payment_method, payment_status,
                    payment_ref, qr_data, checked_in
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Confirmed', ?, ?, 0)
            """, (
                ticket_ref, event_id, purchaser_name, purchaser_email, purchaser_phone,
                member_id, ticket_price, is_member_rate, payment_method,
                payment_ref, qr_payload
            ))
            ticket_id = cursor.lastrowid

            # If paid ticket, post to financial ledger
            if ticket_price > 0:
                cursor.execute("""
                    INSERT INTO financial_transactions (
                        transaction_type, category, amount, description,
                        source_type, source_id, event_id, payment_method,
                        transaction_date, recorded_by
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    'Income', 'Ticket Sale', ticket_price,
                    f"Ticket {ticket_ref} for {event['title']} ({purchaser_name})",
                    'ticket_sale', ticket_id, event_id, payment_method,
                    date.today().isoformat(), session.get('user_id')
                ))

            cursor.execute("COMMIT")
            flash(f"Ticket {ticket_ref} confirmed successfully for {purchaser_name}! Price: {currency_filter(ticket_price)}", 'success')
            return redirect(url_for('ticket_badge', ticket_ref=ticket_ref, success='1'))

        except Exception as e:
            try:
                db.rollback()
            except Exception:
                pass
            flash(f"Error selling ticket: {str(e)}", 'danger')

    # Available seats
    sold_count = db.execute("SELECT COUNT(*) AS count FROM tickets WHERE event_id = ? AND payment_status = 'Confirmed'", (event_id,)).fetchone()['count']
    remaining = max(event['capacity'] - sold_count, 0)
    return render_template('tickets/sell.html', event=event, remaining=remaining, sold_count=sold_count)


# -------------------------------------------------------------------------
# EVENT REGISTRATION & DEMO PAYMENT PROCESSOR
# -------------------------------------------------------------------------

def process_event_registration(db, event_id, attendee_name, attendee_email, attendee_phone='', payment_simulation='demo_success', idempotency_key=None, user_id=None):
    """
    Core business logic for attendee registration and demo payment processing:
    1. Locks and queries event inside BEGIN IMMEDIATE transaction.
    2. Enforces seat capacity check (rejects overselling).
    3. Strictly validates membership pricing on server (never trusts browser-provided price).
    4. Handles demo payment simulation (records demo transaction; handles simulated failure).
    5. Enforces idempotency to prevent duplicate bookings.
    6. Generates unique Ticket Code, Payment Ref, and QR payload.
    7. Atomically records ticket and financial ledger entry.
    """
    attendee_name = (attendee_name or '').strip()
    attendee_email = (attendee_email or '').strip().lower()
    attendee_phone = (attendee_phone or '').strip()

    if not attendee_name:
        return {'success': False, 'message': 'Attendee name is required.'}, 400
    if not attendee_email or not re.match(r"[^@]+@[^@]+\.[^@]+", attendee_email):
        return {'success': False, 'message': 'A valid attendee email address is required.'}, 400

    cursor = db.cursor()
    cursor.execute("BEGIN IMMEDIATE")

    try:
        event = cursor.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
        if not event:
            cursor.execute("ROLLBACK")
            return {'success': False, 'message': 'Event not found.'}, 404

        if event['status'] == 'Cancelled':
            cursor.execute("ROLLBACK")
            return {'success': False, 'message': f"Registration rejected: Event '{event['title']}' has been cancelled."}, 400

        # Idempotency check: if key provided and ticket exists, return existing ticket
        if idempotency_key:
            existing = cursor.execute("SELECT * FROM tickets WHERE payment_ref = ?", (idempotency_key,)).fetchone()
            if existing:
                cursor.execute("COMMIT")
                qr_svg = generate_qr_svg(existing['ticket_ref'])
                return {
                    'success': True,
                    'is_replay': True,
                    'message': 'Registration retrieved (Idempotent request).',
                    'ticket': {
                        'ticket_ref': existing['ticket_ref'],
                        'event_id': event['id'],
                        'event_title': event['title'],
                        'event_date': event['event_date'],
                        'event_time': event['event_time'],
                        'venue': event['venue'],
                        'purchaser_name': existing['purchaser_name'],
                        'purchaser_email': existing['purchaser_email'],
                        'amount': existing['price_paid'],
                        'payment_ref': existing['payment_ref'],
                        'payment_method': existing['payment_method'],
                        'status': existing['payment_status'],
                        'qr_svg': qr_svg,
                        'is_demo': True
                    }
                }, 200

        # Check sold tickets
        sold_row = cursor.execute(
            "SELECT COUNT(*) AS count FROM tickets WHERE event_id = ? AND payment_status = 'Confirmed'",
            (event_id,)
        ).fetchone()
        sold_count = sold_row['count'] if sold_row else 0
        if sold_count >= event['capacity']:
            cursor.execute("ROLLBACK")
            return {
                'success': False,
                'message': f"Registration rejected: Event '{event['title']}' is completely full ({sold_count}/{event['capacity']} seats taken)."
            }, 400

        # Handle simulated failure requested by test/user
        if payment_simulation == 'simulate_failure':
            cursor.execute("ROLLBACK")
            return {
                'success': False,
                'message': 'Demo payment declined: Simulated transaction failed as requested by test parameter.'
            }, 400

        # Server-side membership price verification
        is_member_rate = 0
        member_id = None
        ticket_price = float(event['non_member_price'])

        # Check membership by user_id or email
        member_row = None
        if user_id:
            member_row = cursor.execute("SELECT * FROM members WHERE user_id = ?", (user_id,)).fetchone()
        if not member_row and attendee_email:
            member_row = cursor.execute("SELECT * FROM members WHERE LOWER(email) = LOWER(?)", (attendee_email,)).fetchone()

        if member_row:
            today_iso = date.today().isoformat()
            if member_row['status'] == 'Active' and str(member_row['expiry_date']) >= min(today_iso, str(event['event_date'])):
                is_member_rate = 1
                member_id = member_row['id']
                ticket_price = float(event['member_price'])

        # Unique Ticket Ref and Payment Ref
        ticket_ref = f"CS-TKT-{event_id}-{secrets.token_hex(4).upper()}"
        payment_ref = idempotency_key or f"DEMO-TXN-{int(time.time())}-{secrets.token_hex(4).upper()}"
        qr_payload = f"CLUBSPERE:{ticket_ref}:{event_id}:{secrets.token_hex(6)}"

        cursor.execute("""
            INSERT INTO tickets (
                ticket_ref, event_id, purchaser_name, purchaser_email, purchaser_phone,
                member_id, price_paid, is_member_rate, payment_method, payment_status,
                payment_ref, qr_data, checked_in
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Confirmed', ?, ?, 0)
        """, (
            ticket_ref, event_id, attendee_name, attendee_email, attendee_phone,
            member_id, ticket_price, is_member_rate, 'Demo Payment (Simulated)',
            payment_ref, qr_payload
        ))
        ticket_id = cursor.lastrowid

        # Financial ledger record for paid ticket
        if ticket_price > 0:
            cursor.execute("""
                INSERT INTO financial_transactions (
                    transaction_type, category, amount, description,
                    source_type, source_id, event_id, payment_method,
                    transaction_date, recorded_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                'Income', 'Ticket Sale', ticket_price,
                f"Ticket {ticket_ref} for {event['title']} ({attendee_name}) [Demo Payment]",
                'ticket_sale_demo', ticket_id, event_id, 'Demo Payment (Simulated)',
                date.today().isoformat(), user_id
            ))

        cursor.execute("COMMIT")

        qr_svg = generate_qr_svg(ticket_ref)
        return {
            'success': True,
            'message': f"Demo payment confirmed! Ticket {ticket_ref} issued successfully.",
            'ticket': {
                'ticket_ref': ticket_ref,
                'event_id': event['id'],
                'event_title': event['title'],
                'event_date': event['event_date'],
                'event_time': event['event_time'],
                'venue': event['venue'],
                'purchaser_name': attendee_name,
                'purchaser_email': attendee_email,
                'amount': ticket_price,
                'payment_ref': payment_ref,
                'payment_method': 'Demo Payment (Simulated)',
                'status': 'Confirmed',
                'qr_svg': qr_svg,
                'is_demo': True
            }
        }, 200

    except Exception as e:
        try:
            cursor.execute("ROLLBACK")
        except Exception:
            pass
        return {'success': False, 'message': f"Registration error: {str(e)}"}, 500


@app.route('/events/<int:event_id>/register', methods=['GET', 'POST'])
@login_required
def event_register(event_id):
    db = get_db()
    event = db.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    if not event:
        abort(404)

    sold_count = db.execute("SELECT COUNT(*) AS count FROM tickets WHERE event_id = ? AND payment_status = 'Confirmed'", (event_id,)).fetchone()['count']
    remaining_seats = max(event['capacity'] - sold_count, 0)

    user_id = session.get('user_id')
    current_user_row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone() if user_id else None
    member_row = db.execute("SELECT * FROM members WHERE user_id = ?", (user_id,)).fetchone() if user_id else None

    is_active_member = False
    if member_row and member_row['status'] == 'Active' and str(member_row['expiry_date']) >= date.today().isoformat():
        is_active_member = True

    calculated_price = event['member_price'] if is_active_member else event['non_member_price']

    if request.method == 'POST':
        attendee_name = request.form.get('attendee_name', '').strip()
        attendee_email = request.form.get('attendee_email', '').strip()
        attendee_phone = request.form.get('attendee_phone', '').strip()
        payment_simulation = request.form.get('payment_simulation', 'demo_success')
        idempotency_key = request.form.get('idempotency_key', '').strip() or None

        res, status_code = process_event_registration(
            db, event_id, attendee_name, attendee_email, attendee_phone,
            payment_simulation=payment_simulation,
            idempotency_key=idempotency_key,
            user_id=user_id
        )

        if res['success']:
            session['success_modal'] = {
                'title': 'Payment Confirmed and Ticket Issued!',
                'subtitle': f"Registration for '{event['title']}' is confirmed.",
                'badge': 'DEMO PAYMENT SETTLED' if res['ticket'].get('is_demo') else 'CONFIRMED',
                'is_demo': bool(res['ticket'].get('is_demo')),
                'demo_notice': 'Simulated Demo Payment: Saved reliably to database ledger. Present your ticket pass at the gate.',
                'details': [
                    {'label': 'Event', 'value': res['ticket']['event_title']},
                    {'label': 'Date & Venue', 'value': f"{format_date_filter(res['ticket']['event_date'])} at {res['ticket']['event_time']} • {res['ticket']['venue']}"},
                    {'label': 'Attendee', 'value': f"{res['ticket']['purchaser_name']} ({res['ticket']['purchaser_email']})"},
                    {'label': 'Amount Settled', 'value': currency_filter(res['ticket']['amount']), 'is_success': True},
                    {'label': 'Payment Ref', 'value': res['ticket']['payment_ref'], 'is_code': True},
                    {'label': 'Ticket ID', 'value': res['ticket']['ticket_ref'], 'is_code': True, 'highlight': True},
                    {'label': 'Registration Status', 'value': 'CONFIRMED', 'is_badge': True, 'badge_class': 'badge-confirmed'}
                ],
                'qr_ticket_ref': res['ticket']['ticket_ref'],
                'actions': [
                    {'label': '⬇️ Download Ticket', 'url': url_for('ticket_download', ticket_ref=res['ticket']['ticket_ref']), 'primary': True},
                    {'label': 'View Ticket Pass', 'dismiss': True, 'secondary': True}
                ]
            }
            session['success_modal']['details'] = [d for d in session['success_modal']['details'] if d is not None]
            flash(res['message'], 'success')
            return redirect(url_for('ticket_badge', ticket_ref=res['ticket']['ticket_ref']))
        else:
            flash(res['message'], 'danger')
            return render_template(
                'events/register.html',
                event=event,
                remaining_seats=remaining_seats,
                current_user_row=current_user_row,
                is_active_member=is_active_member,
                calculated_price=calculated_price,
                form_data=request.form
            ), status_code

    return render_template(
        'events/register.html',
        event=event,
        remaining_seats=remaining_seats,
        current_user_row=current_user_row,
        is_active_member=is_active_member,
        calculated_price=calculated_price
    )


@app.route('/api/events/<int:event_id>/register', methods=['POST'])
@login_required
def api_event_register(event_id):
    db = get_db()
    data = request.get_json(silent=True) or request.form.to_dict()

    attendee_name = data.get('attendee_name', '').strip()
    attendee_email = data.get('attendee_email', '').strip()
    attendee_phone = data.get('attendee_phone', '').strip()
    payment_simulation = data.get('payment_simulation', 'demo_success')
    idempotency_key = (data.get('idempotency_key') or '').strip() or None

    res, status_code = process_event_registration(
        db, event_id, attendee_name, attendee_email, attendee_phone,
        payment_simulation=payment_simulation,
        idempotency_key=idempotency_key,
        user_id=session.get('user_id')
    )
    return jsonify(res), status_code


@app.route('/tickets/badge/<ticket_ref>')
@login_required
def ticket_badge(ticket_ref):
    db = get_db()
    ticket = db.execute("""
        SELECT t.*, e.title AS event_title, e.event_date, e.event_time, e.venue, e.description AS event_description
        FROM tickets t
        JOIN events e ON t.event_id = e.id
        WHERE t.ticket_ref = ?
    """, (ticket_ref,)).fetchone()
    if not ticket:
        abort(404)
    qr_svg = generate_qr_svg(ticket['ticket_ref'])
    # Success feedback is handled uniformly and non-repeating via universal success_modal
    show_success_modal = False
    return render_template('tickets/badge.html', ticket=ticket, qr_svg=qr_svg, show_success_modal=show_success_modal)


@app.route('/tickets/download/<ticket_ref>')
@login_required
def ticket_download(ticket_ref):
    db = get_db()
    ticket = db.execute("""
        SELECT t.*, e.title AS event_title, e.event_date, e.event_time, e.venue, e.description AS event_description
        FROM tickets t
        JOIN events e ON t.event_id = e.id
        WHERE t.ticket_ref = ?
    """, (ticket_ref,)).fetchone()
    if not ticket:
        abort(404)
    qr_svg = generate_qr_svg(ticket['ticket_ref'])
    rendered = render_template('tickets/download.html', ticket=ticket, qr_svg=qr_svg)
    response = make_response(rendered)
    response.headers['Content-Type'] = 'text/html; charset=utf-8'
    response.headers['Content-Disposition'] = f'attachment; filename="ticket_{ticket_ref}.html"'
    return response


# -------------------------------------------------------------------------
# TICKET CHECK-IN (LIVE ATTENDANCE CONSOLE)
# -------------------------------------------------------------------------

def ensure_gate_logs_table(db):
    """
    Ensure the gate_checkin_logs audit table exists in the active SQLite database.
    """
    db.execute("""
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
    db.execute("CREATE INDEX IF NOT EXISTS idx_gate_logs_event ON gate_checkin_logs(event_id);")
    db.execute("CREATE INDEX IF NOT EXISTS idx_gate_logs_status ON gate_checkin_logs(status);")


def log_gate_verification(db, ticket_ref, event_id, status, message, user_id):
    """
    Log every ticket verification attempt (success or rejection) for live gate analytics.
    """
    try:
        ensure_gate_logs_table(db)
        db.execute("""
            INSERT INTO gate_checkin_logs (ticket_ref, event_id, status, message, verifier_id)
            VALUES (?, ?, ?, ?, ?)
        """, (ticket_ref, event_id, status, message, user_id))
        db.commit()
    except Exception:
        pass


def get_gate_attendance_stats(db, event_id=None):
    """
    Calculate live attendance metrics from actual database records:
    - checked_in: Count of Confirmed tickets checked in (checked_in = 1)
    - remaining: Count of Confirmed tickets awaiting check-in (checked_in = 0)
    - rejected: Count of failed verification attempts logged in gate_checkin_logs
    """
    ensure_gate_logs_table(db)
    if event_id:
        checked_in = db.execute(
            "SELECT COUNT(*) AS cnt FROM tickets WHERE event_id = ? AND checked_in = 1 AND payment_status = 'Confirmed'",
            (event_id,)
        ).fetchone()['cnt']
        remaining = db.execute(
            "SELECT COUNT(*) AS cnt FROM tickets WHERE event_id = ? AND checked_in = 0 AND payment_status = 'Confirmed'",
            (event_id,)
        ).fetchone()['cnt']
        rejected = db.execute(
            "SELECT COUNT(*) AS cnt FROM gate_checkin_logs WHERE (event_id = ? OR event_id IS NULL) AND status != 'VALID'",
            (event_id,)
        ).fetchone()['cnt']
    else:
        checked_in = db.execute(
            """SELECT COUNT(*) AS cnt FROM tickets t 
               JOIN events e ON t.event_id = e.id 
               WHERE t.checked_in = 1 AND t.payment_status = 'Confirmed' AND e.status != 'Cancelled'"""
        ).fetchone()['cnt']
        remaining = db.execute(
            """SELECT COUNT(*) AS cnt FROM tickets t 
               JOIN events e ON t.event_id = e.id 
               WHERE t.checked_in = 0 AND t.payment_status = 'Confirmed' AND e.status != 'Cancelled'"""
        ).fetchone()['cnt']
        rejected = db.execute(
            "SELECT COUNT(*) AS cnt FROM gate_checkin_logs WHERE status != 'VALID'"
        ).fetchone()['cnt']

    return {
        'checked_in': int(checked_in or 0),
        'remaining': int(remaining or 0),
        'rejected': int(rejected or 0)
    }


@app.route('/tickets/checkin', methods=['GET', 'POST'])
@login_required
@role_required('Administrator', 'Event Organizer', 'Volunteer')
def ticket_checkin():
    db = get_db()
    ensure_gate_logs_table(db)
    selected_event_id = request.args.get('event_id', type=int)
    events = db.execute("SELECT id, title, event_date FROM events WHERE status != 'Cancelled' ORDER BY event_date ASC").fetchall()

    checkin_result = None

    if request.method == 'POST':
        ticket_ref = request.form.get('ticket_ref', '').strip().upper()
        event_filter_id = request.form.get('event_id', type=int)
        if event_filter_id is not None:
            selected_event_id = event_filter_id

        if not ticket_ref:
            flash('Please enter or scan a valid ticket reference code.', 'warning')
        else:
            checkin_result = process_ticket_checkin(db, ticket_ref, selected_event_id, session.get('user_id'))
            if checkin_result['success']:
                flash(checkin_result['message'], 'success')
            else:
                flash(checkin_result['message'], 'danger')

    attendance_stats = get_gate_attendance_stats(db, selected_event_id)

    # Recent check-ins
    recent_checkins_query = """
        SELECT t.*, e.title AS event_title, u.full_name AS verifier_name
        FROM tickets t
        JOIN events e ON t.event_id = e.id
        LEFT JOIN users u ON t.checked_in_by = u.id
        WHERE t.checked_in = 1
    """
    params = []
    if selected_event_id:
        recent_checkins_query += " AND t.event_id = ?"
        params.append(selected_event_id)
    recent_checkins_query += " ORDER BY t.check_in_time DESC LIMIT 15"
    recent_checkins = db.execute(recent_checkins_query, params).fetchall()

    recent_attempt = None
    if checkin_result and not checkin_result.get('success') and checkin_result.get('ticket'):
        # Only show as separate attempt row if not already in recent_checkins
        already_in_table = any(r['ticket_ref'] == checkin_result['ticket']['ticket_ref'] for r in recent_checkins)
        if not already_in_table:
            recent_attempt = checkin_result['ticket']

    return render_template(
        'tickets/checkin.html',
        events=events,
        selected_event_id=selected_event_id,
        attendance_stats=attendance_stats,
        recent_checkins=recent_checkins,
        checkin_result=checkin_result,
        recent_attempt=recent_attempt
    )


@app.route('/api/tickets/checkin', methods=['POST'])
@login_required
@role_required('Administrator', 'Event Organizer', 'Volunteer')
def api_ticket_checkin():
    """
    AJAX endpoint for instant barcode scanner or live ticket check-in.
    """
    data = request.get_json(silent=True) or request.form
    ticket_ref = data.get('ticket_ref', '').strip().upper()
    event_id = data.get('event_id')
    event_id = int(event_id) if (event_id is not None and str(event_id).strip() != '') else None

    db = get_db()
    if not ticket_ref:
        stats = get_gate_attendance_stats(db, event_id)
        return jsonify({'success': False, 'status': 'WARNING', 'message': 'Ticket reference code is required.', 'stats': stats}), 400

    result = process_ticket_checkin(db, ticket_ref, event_id, session.get('user_id'))
    result['stats'] = get_gate_attendance_stats(db, event_id)
    status_code = 200 if result['success'] else 400
    return jsonify(result), status_code


def process_ticket_checkin(db, ticket_ref, event_id, user_id):
    """
    Business logic for ticket verification and check-in:
    - Verifies ticket exists (returns 'Ticket not found')
    - Verifies event eligibility (blocks Cancelled events)
    - Verifies ticket matches event (if specific event_id specified; 'All Active Events' accepts any active event)
    - Verifies ticket is Confirmed (not cancelled/refunded)
    - Rejects duplicate check-in with exact timestamp and verifier
    - Marks ticket checked_in = 1 atomically with timestamp
    - Returns structured ticket payload for recent verifications history
    - Logs every attempt for live gate attendance analytics
    """
    # Fetch current verifier staff name
    staff_row = db.execute("SELECT full_name FROM users WHERE id = ?", (user_id,)).fetchone() if user_id else None
    staff_name = staff_row['full_name'] if staff_row else (session.get('full_name') or "Staff")

    query = """
        SELECT t.*, e.title AS event_title, e.event_date, e.event_time, e.venue AS event_venue, e.status AS event_status,
               u.full_name AS prev_verifier
        FROM tickets t
        JOIN events e ON t.event_id = e.id
        LEFT JOIN users u ON t.checked_in_by = u.id
        WHERE UPPER(t.ticket_ref) = UPPER(?)
    """
    ticket = db.execute(query, (ticket_ref,)).fetchone()

    # 1. Ticket not found
    if not ticket:
        log_gate_verification(db, ticket_ref, event_id, 'INVALID', f"Ticket reference '{ticket_ref}' was not found in the system.", user_id)
        return {
            'success': False,
            'status': 'INVALID',
            'ticket': {
                'ticket_ref': ticket_ref,
                'purchaser_name': 'Unknown Attendee',
                'event_title': '—',
                'event_date': '—',
                'event_time': '—',
                'status': 'Rejected: Not Found',
                'check_in_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'verifier_name': staff_name
            },
            'message': f"Ticket not found: Ticket reference '{ticket_ref}' was not found in the system."
        }

    # 2. Inactive / Cancelled event
    if ticket['event_status'] == 'Cancelled':
        log_gate_verification(db, ticket['ticket_ref'], ticket['event_id'], 'CANCELLED_EVENT', f"Event '{ticket['event_title']}' has been cancelled.", user_id)
        return {
            'success': False,
            'status': 'CANCELLED_EVENT',
            'ticket': {
                'ticket_ref': ticket['ticket_ref'],
                'purchaser_name': ticket['purchaser_name'] or 'Unknown Attendee',
                'event_title': ticket['event_title'] or 'Cancelled Event',
                'event_date': ticket['event_date'] or '—',
                'event_time': ticket['event_time'] or '—',
                'status': 'Rejected: Event Cancelled',
                'check_in_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'verifier_name': staff_name
            },
            'message': f"Event Cancelled: Event '{ticket['event_title']}' has been cancelled. Ticket '{ticket_ref}' cannot be admitted."
        }

    # 3. Wrong event (if specific event selected)
    if event_id and ticket['event_id'] != event_id:
        target_event = db.execute("SELECT title FROM events WHERE id = ?", (event_id,)).fetchone()
        target_title = target_event['title'] if target_event else f"Event #{event_id}"
        log_gate_verification(db, ticket['ticket_ref'], event_id, 'WRONG_EVENT', f"Ticket for '{ticket['event_title']}' scanned at '{target_title}' gate.", user_id)
        return {
            'success': False,
            'status': 'WRONG_EVENT',
            'ticket': {
                'ticket_ref': ticket['ticket_ref'],
                'purchaser_name': ticket['purchaser_name'] or 'Unknown Attendee',
                'event_title': ticket['event_title'],
                'event_date': ticket['event_date'] or '—',
                'event_time': ticket['event_time'] or '—',
                'expected_event_title': target_title,
                'status': 'Rejected: Wrong Event',
                'check_in_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'verifier_name': staff_name
            },
            'message': f"Wrong Event! Ticket '{ticket_ref}' is for '{ticket['event_title']}', not selected event."
        }

    # 4. Payment status ineligible
    if ticket['payment_status'] != 'Confirmed':
        log_gate_verification(db, ticket['ticket_ref'], ticket['event_id'], 'CANCELLED', f"Payment status '{ticket['payment_status']}'", user_id)
        return {
            'success': False,
            'status': 'CANCELLED',
            'ticket': {
                'ticket_ref': ticket['ticket_ref'],
                'purchaser_name': ticket['purchaser_name'] or 'Unknown Attendee',
                'event_title': ticket['event_title'],
                'event_date': ticket['event_date'] or '—',
                'event_time': ticket['event_time'] or '—',
                'status': f"Rejected: {ticket['payment_status']}",
                'check_in_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'verifier_name': staff_name
            },
            'message': f"Rejected: Ticket '{ticket_ref}' has payment status '{ticket['payment_status']}' and cannot be admitted."
        }

    # 5. Duplicate check-in rejection
    if ticket['checked_in'] == 1:
        prev_time = ticket['check_in_time'] or "earlier"
        verifier = ticket['prev_verifier'] or "Staff"
        log_gate_verification(db, ticket['ticket_ref'], ticket['event_id'], 'ALREADY_CHECKED_IN', f"Duplicate check-in. Previously scanned on {prev_time} by {verifier}.", user_id)
        return {
            'success': False,
            'status': 'ALREADY_CHECKED_IN',
            'ticket': {
                'ticket_ref': ticket['ticket_ref'],
                'purchaser_name': ticket['purchaser_name'],
                'event_title': ticket['event_title'],
                'event_date': ticket['event_date'] or '—',
                'event_time': ticket['event_time'] or '—',
                'status': 'Duplicate / Already Checked In',
                'check_in_time': prev_time,
                'verifier_name': verifier
            },
            'message': f"Duplicate Check-In Alert! Ticket '{ticket_ref}' was ALREADY checked in on {prev_time} by {verifier}."
        }

    # 6. Perform Check-In (atomic CAS to prevent concurrent double-scans)
    now_iso = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor = db.cursor()
    cursor.execute("""
        UPDATE tickets SET
            checked_in = 1,
            check_in_time = ?,
            checked_in_by = ?
        WHERE id = ? AND checked_in = 0
    """, (now_iso, user_id, ticket['id']))
    db.commit()

    if cursor.rowcount == 0:
        fresh_ticket = db.execute("""
            SELECT t.*, e.title AS event_title, e.event_date, e.event_time, u.full_name AS prev_verifier
            FROM tickets t
            JOIN events e ON t.event_id = e.id
            LEFT JOIN users u ON t.checked_in_by = u.id
            WHERE t.id = ?
        """, (ticket['id'],)).fetchone()
        prev_time = (fresh_ticket['check_in_time'] if fresh_ticket else None) or "earlier"
        verifier = (fresh_ticket['prev_verifier'] if fresh_ticket else None) or "Staff"
        log_gate_verification(db, ticket['ticket_ref'], ticket['event_id'], 'ALREADY_CHECKED_IN', f"Duplicate scan on {prev_time} by {verifier}.", user_id)
        return {
            'success': False,
            'status': 'ALREADY_CHECKED_IN',
            'ticket': {
                'ticket_ref': ticket['ticket_ref'],
                'purchaser_name': ticket['purchaser_name'],
                'event_title': ticket['event_title'],
                'event_date': ticket['event_date'] or '—',
                'event_time': ticket['event_time'] or '—',
                'status': 'Duplicate / Already Checked In',
                'check_in_time': prev_time,
                'verifier_name': verifier
            },
            'message': f"Duplicate Check-In Alert! Ticket '{ticket_ref}' was ALREADY checked in on {prev_time} by {verifier}."
        }

    log_gate_verification(db, ticket['ticket_ref'], ticket['event_id'], 'VALID', f"Valid check-in for {ticket['purchaser_name']}.", user_id)

    # Auto-award engagement points for verified event attendance
    try:
        attendee_user_id = None
        if ticket['member_id']:
            mem_user = db.execute("SELECT user_id FROM members WHERE id = ?", (ticket['member_id'],)).fetchone()
            if mem_user and mem_user['user_id']:
                attendee_user_id = mem_user['user_id']
        if not attendee_user_id and ticket['purchaser_email']:
            u_row = db.execute("SELECT id FROM users WHERE LOWER(email) = LOWER(?)", (ticket['purchaser_email'].strip(),)).fetchone()
            if u_row:
                attendee_user_id = u_row['id']

        if attendee_user_id:
            award_achievement_points(
                attendee_user_id,
                points=25,
                reason=f"Event Attendance: {ticket['event_title']}",
                source_type='ticket_checkin',
                source_id=ticket['id'],
                awarded_by=user_id,
                db=db
            )
    except Exception as e:
        print(f"Engagement points tracking notice: {e}")

    return {
        'success': True,
        'status': 'VALID',
        'ticket': {
            'ticket_ref': ticket['ticket_ref'],
            'purchaser_name': ticket['purchaser_name'],
            'event_title': ticket['event_title'],
            'event_date': ticket['event_date'] or '—',
            'event_time': ticket['event_time'] or '—',
            'venue': ticket['event_venue'] or '—',
            'status': 'Checked In',
            'check_in_time': now_iso,
            'verifier_name': staff_name
        },
        'message': f"Check-In Successful: {ticket['purchaser_name']} for '{ticket['event_title']}'."
    }


# -------------------------------------------------------------------------
# FINANCIAL MANAGEMENT & LEDGER
# -------------------------------------------------------------------------

@app.route('/finance')
@login_required
@role_required('Administrator', 'Treasurer')
def finance_ledger():
    db = get_db()
    cat_filter = request.args.get('category', '').strip()
    type_filter = request.args.get('type', '').strip()
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    q = request.args.get('q', '').strip()

    try:
        page = int(request.args.get('page', 1))
        if page < 1:
            page = 1
    except (ValueError, TypeError):
        page = 1
    per_page = 10

    # 1. Core financial totals calculated from ledger
    income_row = db.execute("SELECT COALESCE(SUM(amount), 0) AS val FROM financial_transactions WHERE transaction_type = 'Income'").fetchone()
    expense_row = db.execute("SELECT COALESCE(SUM(amount), 0) AS val FROM financial_transactions WHERE transaction_type = 'Expense'").fetchone()
    total_income = income_row['val'] if income_row else 0.0
    total_expenses = expense_row['val'] if expense_row else 0.0
    net_cash = total_income - total_expenses

    # Outstanding membership dues
    dues_row = db.execute("""
        SELECT COALESCE(SUM(MAX(membership_fee - amount_paid, 0)), 0) AS dues
        FROM members WHERE status IN ('Active', 'Pending')
    """).fetchone()
    outstanding_dues = dues_row['dues'] if dues_row else 0.0

    # Event financial breakdown
    events_breakdown = db.execute("""
        SELECT e.id, e.title, e.event_date,
               COUNT(t.id) AS tickets_sold,
               COALESCE(SUM(t.price_paid), 0) AS ticket_revenue,
               (
                   SELECT COALESCE(SUM(er.amount), 0)
                   FROM expense_requests er
                   WHERE er.event_id = e.id AND er.status = 'Paid'
               ) AS paid_expenses
        FROM events e
        LEFT JOIN tickets t ON e.id = t.event_id AND t.payment_status = 'Confirmed'
        GROUP BY e.id
        ORDER BY e.event_date DESC
    """).fetchall()

    # Ledger entries
    base_where = " WHERE 1=1"
    params = []
    if type_filter:
        base_where += " AND ft.transaction_type = ?"
        params.append(type_filter)
    if cat_filter:
        base_where += " AND ft.category = ?"
        params.append(cat_filter)
    if start_date:
        base_where += " AND ft.transaction_date >= ?"
        params.append(start_date)
    if end_date:
        base_where += " AND ft.transaction_date <= ?"
        params.append(end_date)
    if q:
        base_where += " AND (ft.description LIKE ? OR ft.category LIKE ? OR ft.payment_method LIKE ? OR ft.source_type LIKE ? OR ft.source_id LIKE ?)"
        term = f"%{q}%"
        params.extend([term, term, term, term, term])

    # Count total matching entries across full database
    count_query = f"SELECT COUNT(*) AS total FROM financial_transactions ft{base_where}"
    count_row = db.execute(count_query, params).fetchone()
    total_matching = count_row['total'] if count_row else 0

    import math
    total_pages = max(1, math.ceil(total_matching / per_page))
    if page > total_pages:
        page = total_pages
    offset = (page - 1) * per_page

    data_query = f"""
        SELECT ft.*, u.full_name AS recorder_name
        FROM financial_transactions ft
        LEFT JOIN users u ON ft.recorded_by = u.id
        {base_where}
        ORDER BY ft.transaction_date DESC, ft.id DESC
        LIMIT ? OFFSET ?
    """
    page_params = list(params) + [per_page, offset]
    transactions = db.execute(data_query, page_params).fetchall()

    categories = [
        'Membership Fee', 'Ticket Sale', 'Merchandise Sale',
        'Fundraising Income', 'Sponsorship', 'Donation',
        'Expense Reimbursement', 'Event Operation', 'Other'
    ]

    start_index = offset + 1 if total_matching > 0 else 0
    end_index = min(offset + len(transactions), total_matching)

    return render_template(
        'finance/ledger.html',
        transactions=transactions,
        total_income=total_income,
        total_expenses=total_expenses,
        net_cash=net_cash,
        outstanding_dues=outstanding_dues,
        events_breakdown=events_breakdown,
        categories=categories,
        cat_filter=cat_filter,
        type_filter=type_filter,
        start_date=start_date,
        end_date=end_date,
        q=q,
        page=page,
        total_pages=total_pages,
        total_matching=total_matching,
        per_page=per_page,
        start_index=start_index,
        end_index=end_index,
        today_str=date.today().isoformat()
    )


@app.route('/finance/income/new', methods=['POST'])
@login_required
@role_required('Administrator', 'Treasurer')
def finance_record_income():
    category = request.form.get('category', 'Fundraising Income')
    try:
        amount = float(request.form.get('amount', 0))
        if amount <= 0:
            flash('Amount must be positive.', 'danger')
            return redirect(url_for('finance_ledger'))
    except ValueError:
        flash('Invalid amount format.', 'danger')
        return redirect(url_for('finance_ledger'))

    description = request.form.get('description', '').strip()
    payment_method = request.form.get('payment_method', 'Bank Transfer')
    transaction_date = request.form.get('transaction_date', date.today().isoformat())
    event_id = request.form.get('event_id')
    event_id = int(event_id) if event_id else None

    if not description:
        flash('Transaction description is required.', 'danger')
        return redirect(url_for('finance_ledger'))

    db = get_db()
    recent_dup = db.execute("""
        SELECT id FROM financial_transactions
        WHERE source_type = 'manual_income'
          AND transaction_type = 'Income'
          AND category = ?
          AND amount = ?
          AND description = ?
          AND transaction_date = ?
          AND recorded_by = ?
          AND created_at >= DATETIME('now', '-10 seconds')
    """, (category, amount, description, transaction_date, session.get('user_id'))).fetchone()
    if recent_dup:
        flash('Duplicate income transaction submission detected and ignored.', 'warning')
        return redirect(url_for('finance_ledger'))

    db.execute("""
        INSERT INTO financial_transactions (
            transaction_type, category, amount, description,
            source_type, source_id, event_id, payment_method, transaction_date, recorded_by
        ) VALUES (?, ?, ?, ?, 'manual_income', NULL, ?, ?, ?, ?)
    """, (
        'Income', category, amount, description,
        event_id, payment_method, transaction_date, session.get('user_id')
    ))
    db.commit()
    flash(f"Recorded income of {currency_filter(amount)} ({category}) in ledger.", 'success')
    return redirect(url_for('finance_ledger'))


# -------------------------------------------------------------------------
# EXPENSE REQUESTS, APPROVALS, & REIMBURSEMENTS
# -------------------------------------------------------------------------

@app.route('/expenses')
@login_required
def expenses_list():
    db = get_db()
    status_filter = request.args.get('status', '').strip()

    query = """
        SELECT er.*,
               req.full_name AS requester_name,
               appr.full_name AS approver_name,
               p.full_name AS payer_name,
               e.title AS event_title
        FROM expense_requests er
        JOIN users req ON er.requested_by = req.id
        LEFT JOIN users appr ON er.approved_by = appr.id
        LEFT JOIN users p ON er.paid_by = p.id
        LEFT JOIN events e ON er.event_id = e.id
        WHERE 1=1
    """
    params = []
    if status_filter:
        query += " AND er.status = ?"
        params.append(status_filter)

    query += " ORDER BY er.created_at DESC"
    expenses = db.execute(query, params).fetchall()
    events = db.execute("SELECT id, title FROM events WHERE status != 'Cancelled' ORDER BY title ASC").fetchall()

    count_rows = db.execute("SELECT status, COUNT(*) AS count FROM expense_requests GROUP BY status").fetchall()
    counts_map = {r['status']: r['count'] for r in count_rows}
    status_counts = {
        'all': sum(counts_map.values()),
        'Pending': counts_map.get('Pending', 0),
        'Approved': counts_map.get('Approved', 0),
        'Paid': counts_map.get('Paid', 0),
        'Rejected': counts_map.get('Rejected', 0),
    }

    return render_template(
        'finance/expenses.html',
        expenses=expenses,
        status_filter=status_filter,
        events=events,
        status_counts=status_counts,
        today_str=date.today().isoformat()
    )


@app.route('/expenses/new', methods=['GET', 'POST'])
@login_required
def expenses_new():
    db = get_db()
    events = db.execute("SELECT id, title FROM events WHERE status != 'Cancelled' ORDER BY title ASC").fetchall()

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        category = request.form.get('category', 'Event Logistics')
        description = request.form.get('description', '').strip()
        receipt_ref = request.form.get('receipt_ref', '').strip()
        event_id = request.form.get('event_id')
        event_id = int(event_id) if event_id else None

        try:
            amount = float(request.form.get('amount', 0))
            if amount <= 0:
                raise ValueError()
        except ValueError:
            amount = 0.0

        errors = []
        if not title:
            errors.append('Expense title is required.')
        if amount <= 0:
            errors.append('Amount must be greater than zero.')
        if not description:
            errors.append('Description / justification is required.')

        if errors:
            for err in errors:
                flash(err, 'danger')
            return render_template('finance/expense_form.html', events=events, form_data=request.form)

        # Check for rapid duplicate submission within 10 seconds
        recent_dup = db.execute("""
            SELECT id FROM expense_requests
            WHERE requested_by = ? AND title = ? AND amount = ? AND created_at >= DATETIME('now', '-10 seconds')
        """, (session.get('user_id'), title, amount)).fetchone()
        if recent_dup:
            flash('Duplicate expense request submission detected and ignored.', 'warning')
            return redirect(url_for('expenses_list'))

        db.execute("""
            INSERT INTO expense_requests (
                title, category, amount, requested_by, description,
                receipt_ref, event_id, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'Pending')
        """, (
            title, category, amount, session.get('user_id'),
            description, receipt_ref, event_id
        ))
        db.commit()
        flash(f"Expense request '{title}' submitted for approval.", 'success')
        return redirect(url_for('expenses_list'))

    return render_template('finance/expense_form.html', events=events)


@app.route('/expenses/<int:expense_id>/approve', methods=['POST'])
@login_required
@role_required('Administrator', 'Treasurer')
def expenses_approve(expense_id):
    db = get_db()
    expense = db.execute("SELECT * FROM expense_requests WHERE id = ?", (expense_id,)).fetchone()
    if not expense:
        abort(404)

    if expense['status'] != 'Pending':
        flash(f"Cannot approve expense with status '{expense['status']}'.", 'warning')
        return redirect(url_for('expenses_list'))

    now_iso = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    db.execute("""
        UPDATE expense_requests SET
            status = 'Approved',
            approved_by = ?,
            approved_date = ?
        WHERE id = ?
    """, (session.get('user_id'), now_iso, expense_id))
    db.commit()
    flash(f"Expense request #{expense_id} ('{expense['title']}') approved.", 'success')
    return redirect(url_for('expenses_list'))


@app.route('/expenses/<int:expense_id>/reject', methods=['POST'])
@login_required
@role_required('Administrator', 'Treasurer')
def expenses_reject(expense_id):
    db = get_db()
    expense = db.execute("SELECT * FROM expense_requests WHERE id = ?", (expense_id,)).fetchone()
    if not expense:
        abort(404)

    if expense['status'] != 'Pending':
        flash(f"Cannot reject expense with status '{expense['status']}'.", 'warning')
        return redirect(url_for('expenses_list'))

    reason = request.form.get('rejection_reason', 'Rejected by administrator/treasurer').strip()
    db.execute("""
        UPDATE expense_requests SET
            status = 'Rejected',
            approved_by = ?,
            rejection_reason = ?
        WHERE id = ?
    """, (session.get('user_id'), reason, expense_id))
    db.commit()
    flash(f"Expense request #{expense_id} rejected.", 'info')
    return redirect(url_for('expenses_list'))


@app.route('/expenses/<int:expense_id>/pay', methods=['POST'])
@login_required
@role_required('Administrator', 'Treasurer')
def expenses_pay(expense_id):
    """
    Pay an Approved expense.
    Hits financial ledger ONLY once paid. Avoids double-counting.
    """
    db = get_db()
    expense = db.execute("SELECT * FROM expense_requests WHERE id = ?", (expense_id,)).fetchone()
    if not expense:
        abort(404)

    if expense['status'] != 'Approved':
        flash("Only Approved expenses can be marked as Paid.", 'warning')
        return redirect(url_for('expenses_list'))

    payment_method = request.form.get('payment_method', 'Bank Transfer')
    payment_ref = request.form.get('payment_ref', '').strip()
    paid_date = request.form.get('paid_date', date.today().isoformat())

    try:
        cursor = db.cursor()
        cursor.execute("BEGIN IMMEDIATE")

        now_iso = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute("""
            UPDATE expense_requests SET
                status = 'Paid',
                paid_by = ?,
                paid_date = ?,
                payment_method = ?,
                payment_ref = ?
            WHERE id = ? AND status = 'Approved'
        """, (session.get('user_id'), now_iso, payment_method, payment_ref, expense_id))

        if cursor.rowcount == 0:
            cursor.execute("ROLLBACK")
            flash("Expense has already been paid or is no longer in Approved status.", 'warning')
            return redirect(url_for('expenses_list'))

        # Financial ledger posting
        cursor.execute("""
            INSERT INTO financial_transactions (
                transaction_type, category, amount, description,
                source_type, source_id, event_id, payment_method,
                transaction_date, recorded_by
            ) VALUES (?, ?, ?, ?, 'expense_request', ?, ?, ?, ?, ?)
        """, (
            'Expense', 'Expense Reimbursement', expense['amount'],
            f"Paid Expense #{expense['id']}: {expense['title']} ({expense['category']})",
            expense['id'], expense['event_id'], payment_method,
            paid_date, session.get('user_id')
        ))

        cursor.execute("COMMIT")
        flash(f"Expense #{expense_id} paid ({currency_filter(expense['amount'])}) and posted to ledger.", 'success')
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        flash(f"Failed to process payment: {str(e)}", 'danger')

    return redirect(url_for('expenses_list'))


# -------------------------------------------------------------------------
# MERCHANDISE MANAGEMENT
# -------------------------------------------------------------------------

@app.route('/merchandise')
@login_required
def merchandise_list():
    db = get_db()

    # Get items with variants and stock summary
    items_raw = db.execute("""
        SELECT m.*,
               COUNT(v.id) AS variant_count,
               COALESCE(SUM(v.stock_quantity), 0) AS total_stock,
               SUM(CASE WHEN v.stock_quantity <= v.low_stock_threshold THEN 1 ELSE 0 END) AS low_stock_count
        FROM merchandise_items m
        LEFT JOIN merchandise_variants v ON m.id = v.item_id
        WHERE m.is_active = 1
        GROUP BY m.id
        ORDER BY m.created_at DESC
    """).fetchall()

    variants = db.execute("""
        SELECT v.*, m.name AS item_name
        FROM merchandise_variants v
        JOIN merchandise_items m ON v.item_id = m.id
        WHERE m.is_active = 1
        ORDER BY m.name ASC, v.size ASC
    """).fetchall()

    items = []
    total_units_in_stock = 0
    low_stock_variants_count = 0

    for it in items_raw:
        it_dict = dict(it)
        it_variants = [dict(v) for v in variants if v['item_id'] == it['id']]
        it_dict['variants'] = it_variants

        # Calculate item-level stock status
        if it_dict['total_stock'] == 0:
            it_dict['stock_status'] = 'Out of Stock'
            it_dict['stock_status_badge'] = 'badge-expired'
        elif any(v['stock_quantity'] <= v['low_stock_threshold'] for v in it_variants) or it_dict['low_stock_count'] > 0:
            it_dict['stock_status'] = 'Low Stock'
            it_dict['stock_status_badge'] = 'badge-pending'
        else:
            it_dict['stock_status'] = 'In Stock'
            it_dict['stock_status_badge'] = 'badge-active'

        items.append(it_dict)

    for v in variants:
        total_units_in_stock += int(v['stock_quantity'] or 0)
        if v['stock_quantity'] <= v['low_stock_threshold']:
            low_stock_variants_count += 1

    rev_row = db.execute("""
        SELECT COALESCE(SUM(total_amount), 0) AS total 
        FROM merchandise_orders 
        WHERE payment_status = 'Paid'
    """).fetchone()
    total_merch_revenue = rev_row['total'] if rev_row else 0.0

    # Recent customer orders
    orders = db.execute("""
        SELECT o.*,
               COUNT(oi.id) AS item_count,
               u.full_name AS recorder_name
        FROM merchandise_orders o
        LEFT JOIN merchandise_order_items oi ON o.id = oi.order_id
        LEFT JOIN users u ON o.created_by = u.id
        GROUP BY o.id
        ORDER BY o.created_at DESC
        LIMIT 20
    """).fetchall()

    return render_template(
        'merchandise/list.html',
        items=items,
        variants=variants,
        orders=orders,
        total_units_in_stock=total_units_in_stock,
        low_stock_variants_count=low_stock_variants_count,
        total_merch_revenue=total_merch_revenue
    )


@app.route('/merchandise/new', methods=['GET', 'POST'])
@login_required
@role_required('Administrator', 'Treasurer')
def merchandise_new():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        category = request.form.get('category', 'Apparel')
        description = request.form.get('description', '').strip()

        try:
            base_price = float(request.form.get('base_price', 0))
            if base_price < 0:
                raise ValueError()
        except ValueError:
            base_price = 0.0

        if not name:
            flash('Product name is required.', 'danger')
            return render_template('merchandise/form.html')

        db = get_db()
        cursor = db.cursor()
        cursor.execute("""
            INSERT INTO merchandise_items (name, category, description, base_price)
            VALUES (?, ?, ?, ?)
        """, (name, category, description, base_price))
        item_id = cursor.lastrowid

        # Initial variants creation if provided
        sizes = ['S', 'M', 'L', 'XL']
        slug = re.sub(r'[^A-Z0-9]', '', name.upper())[:6]
        for size in sizes:
            qty_field = f"qty_{size}"
            try:
                qty = int(request.form.get(qty_field, 0))
                qty = max(qty, 0)
            except ValueError:
                qty = 0
            sku = f"{slug}-{size}"
            cursor.execute("""
                INSERT INTO merchandise_variants (item_id, size, sku, stock_quantity, low_stock_threshold)
                VALUES (?, ?, ?, ?, 5)
            """, (item_id, size, sku, qty))

        db.commit()
        flash(f"Merchandise '{name}' created with size variants.", 'success')
        return redirect(url_for('merchandise_list'))

    return render_template('merchandise/form.html')


@app.route('/merchandise/variants/<int:variant_id>/restock', methods=['POST'])
@login_required
@role_required('Administrator', 'Treasurer')
def merchandise_restock(variant_id):
    try:
        qty_add = int(request.form.get('quantity', 0))
        if qty_add <= 0:
            flash('Quantity to add must be positive.', 'danger')
            return redirect(url_for('merchandise_list'))
    except ValueError:
        flash('Invalid quantity.', 'danger')
        return redirect(url_for('merchandise_list'))

    db = get_db()
    variant = db.execute("SELECT * FROM merchandise_variants WHERE id = ?", (variant_id,)).fetchone()
    if not variant:
        abort(404)

    db.execute("""
        UPDATE merchandise_variants
        SET stock_quantity = stock_quantity + ?
        WHERE id = ?
    """, (qty_add, variant_id))
    db.commit()
    flash(f"Restocked {qty_add} units for {variant['sku']}. New stock: {variant['stock_quantity'] + qty_add}.", 'success')
    return redirect(url_for('merchandise_list'))


@app.route('/merchandise/order', methods=['GET', 'POST'])
@login_required
def merchandise_order():
    db = get_db()
    variants = db.execute("""
        SELECT v.*, m.name AS item_name, m.base_price,
               COALESCE(v.price_override, m.base_price) AS effective_price
        FROM merchandise_variants v
        JOIN merchandise_items m ON v.item_id = m.id
        WHERE m.is_active = 1
        ORDER BY m.name ASC, v.size ASC
    """).fetchall()

    if request.method == 'POST':
        customer_name = request.form.get('customer_name', '').strip()
        customer_email = request.form.get('customer_email', '').strip().lower()
        customer_phone = request.form.get('customer_phone', '').strip()
        variant_id = request.form.get('variant_id', type=int)
        payment_method = request.form.get('payment_method', 'Cash')

        try:
            quantity = int(request.form.get('quantity', 1))
            if quantity <= 0:
                raise ValueError()
        except ValueError:
            flash('Quantity must be at least 1.', 'danger')
            return render_template('merchandise/order.html', variants=variants)

        if not customer_name or not customer_email:
            flash('Customer name and email are required.', 'danger')
            return render_template('merchandise/order.html', variants=variants)

        # -------------------------------------------------------------
        # TRANSACTION & STOCK DEDUCTION / OVERSELLING PREVENTION
        # -------------------------------------------------------------
        try:
            cursor = db.cursor()
            cursor.execute("BEGIN IMMEDIATE")

            # Check stock
            var_row = cursor.execute("""
                SELECT v.*, m.name AS item_name, m.base_price,
                       COALESCE(v.price_override, m.base_price) AS effective_price
                FROM merchandise_variants v
                JOIN merchandise_items m ON v.item_id = m.id
                WHERE v.id = ?
            """, (variant_id,)).fetchone()

            if not var_row:
                cursor.execute("ROLLBACK")
                flash('Selected variant does not exist.', 'danger')
                return render_template('merchandise/order.html', variants=variants)

            if var_row['stock_quantity'] < quantity:
                cursor.execute("ROLLBACK")
                flash(f"Insufficient stock for {var_row['item_name']} (Size {var_row['size']}). Available: {var_row['stock_quantity']}, Requested: {quantity}.", 'danger')
                return render_template('merchandise/order.html', variants=variants)

            unit_price = var_row['effective_price']
            total_amount = unit_price * quantity

            # Prevent accidental duplicate order submissions within 10 seconds
            recent_dup = cursor.execute("""
                SELECT id FROM merchandise_orders
                WHERE customer_email = ? AND total_amount = ? AND created_at >= DATETIME('now', '-10 seconds')
            """, (customer_email, total_amount)).fetchone()
            if recent_dup:
                cursor.execute("ROLLBACK")
                flash('Duplicate order submission detected and ignored.', 'warning')
                return redirect(url_for('merchandise_list'))

            # Deduct stock
            cursor.execute("""
                UPDATE merchandise_variants
                SET stock_quantity = stock_quantity - ?
                WHERE id = ?
            """, (quantity, variant_id))

            # Check if customer is a registered club member
            member_row = cursor.execute("SELECT id FROM members WHERE LOWER(email) = LOWER(?)", (customer_email,)).fetchone()
            member_id = member_row['id'] if member_row else None

            # Create Order
            order_ref = f"CS-ORD-{secrets.token_hex(4).upper()}"
            cursor.execute("""
                INSERT INTO merchandise_orders (
                    order_ref, customer_name, customer_email, customer_phone,
                    member_id, total_amount, payment_status, payment_method, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, 'Paid', ?, ?)
            """, (
                order_ref, customer_name, customer_email, customer_phone,
                member_id, total_amount, payment_method, session.get('user_id')
            ))
            order_id = cursor.lastrowid

            # Create Order Item
            cursor.execute("""
                INSERT INTO merchandise_order_items (
                    order_id, variant_id, quantity, unit_price, subtotal
                ) VALUES (?, ?, ?, ?, ?)
            """, (order_id, variant_id, quantity, unit_price, total_amount))

            # Record in financial ledger if > 0
            if total_amount > 0:
                cursor.execute("""
                    INSERT INTO financial_transactions (
                        transaction_type, category, amount, description,
                        source_type, source_id, payment_method, transaction_date, recorded_by
                    ) VALUES (?, ?, ?, ?, 'merchandise_order', ?, ?, ?, ?)
                """, (
                    'Income', 'Merchandise Sale', total_amount,
                    f"Merchandise Order {order_ref}: {quantity}x {var_row['item_name']} ({var_row['size']}) for {customer_name}",
                    order_id, payment_method, date.today().isoformat(), session.get('user_id')
                ))

            cursor.execute("COMMIT")
            remaining_stock = var_row['stock_quantity'] - quantity
            session['success_modal'] = {
                'title': 'Merchandise Order Confirmed!',
                'subtitle': f"Order for {customer_name} has been processed and inventory updated.",
                'badge': 'ORDER PLACED',
                'details': [
                    {'label': 'Order Reference', 'value': order_ref, 'is_code': True, 'highlight': True},
                    {'label': 'Customer', 'value': f"{customer_name} ({customer_email})"},
                    {'label': 'Item & Size', 'value': f"{quantity}x {var_row['item_name']} (Size {var_row['size']})"},
                    {'label': 'Total Amount', 'value': currency_filter(total_amount), 'is_success': True},
                    {'label': 'Payment Method', 'value': payment_method},
                    {'label': 'Inventory Status', 'value': f"{remaining_stock} units remaining in stock"},
                ],
                'actions': [
                    {'label': 'Done', 'dismiss': True, 'primary': True},
                    {'label': 'Place Another Order', 'url': url_for('merchandise_order'), 'secondary': True}
                ]
            }
            session['success_modal']['details'] = [d for d in session['success_modal']['details'] if d is not None]
            flash(f"Order {order_ref} confirmed! Deducted {quantity} units. Total: {currency_filter(total_amount)}.", 'success')
            return redirect(url_for('merchandise_list'))

        except Exception as e:
            try:
                db.rollback()
            except Exception:
                pass
            flash(f"Failed to process merchandise order: {str(e)}", 'danger')

    return render_template('merchandise/order.html', variants=variants)


# -------------------------------------------------------------------------
# VOLUNTEER TASKS & ANNOUNCEMENTS
# -------------------------------------------------------------------------

@app.route('/tasks')
@login_required
def tasks_list():
    db = get_db()
    status_filter = request.args.get('status', '').strip()
    my_tasks = request.args.get('my_tasks', '').strip()

    query = """
        SELECT vt.*,
               assignee.full_name AS assignee_name,
               creator.full_name AS creator_name,
               e.title AS event_title
        FROM volunteer_tasks vt
        LEFT JOIN users assignee ON vt.assigned_to = assignee.id
        LEFT JOIN users creator ON vt.created_by = creator.id
        LEFT JOIN events e ON vt.event_id = e.id
        WHERE 1=1
    """
    params = []
    if status_filter:
        query += " AND vt.status = ?"
        params.append(status_filter)
    if my_tasks:
        query += " AND vt.assigned_to = ?"
        params.append(session.get('user_id'))

    query += " ORDER BY vt.deadline ASC, vt.priority DESC"
    tasks = db.execute(query, params).fetchall()

    volunteers = db.execute("SELECT id, full_name, role FROM users WHERE is_active = 1 ORDER BY full_name ASC").fetchall()
    events = db.execute("SELECT id, title FROM events WHERE status != 'Cancelled' ORDER BY title ASC").fetchall()

    return render_template(
        'tasks/list.html',
        tasks=tasks,
        volunteers=volunteers,
        events=events,
        status_filter=status_filter,
        my_tasks=my_tasks
    )


@app.route('/tasks/new', methods=['POST'])
@login_required
@role_required('Administrator', 'Event Organizer')
def tasks_new():
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    assigned_to = request.form.get('assigned_to', type=int)
    event_id = request.form.get('event_id')
    event_id = int(event_id) if event_id else None
    priority = request.form.get('priority', 'Medium')
    deadline = request.form.get('deadline', '').strip()

    if not title:
        flash('Task title is required.', 'danger')
        return redirect(url_for('tasks_list'))

    db = get_db()
    db.execute("""
        INSERT INTO volunteer_tasks (
            title, description, event_id, assigned_to, priority, deadline, status, created_by
        ) VALUES (?, ?, ?, ?, ?, ?, 'Pending', ?)
    """, (title, description, event_id, assigned_to, priority, deadline, session.get('user_id')))
    db.commit()
    flash(f"Task '{title}' created and assigned.", 'success')
    return redirect(url_for('tasks_list'))


@app.route('/tasks/<int:task_id>/status', methods=['POST'])
@login_required
def tasks_update_status(task_id):
    new_status = request.form.get('status', 'Completed')
    if new_status not in ('Pending', 'In Progress', 'Completed', 'Cancelled'):
        flash('Invalid status.', 'danger')
        return redirect(url_for('tasks_list'))

    db = get_db()
    task = db.execute("SELECT * FROM volunteer_tasks WHERE id = ?", (task_id,)).fetchone()
    if not task:
        abort(404)

    # Permission check: Admin, Organizer, or the assigned volunteer
    curr_user_id = session.get('user_id')
    curr_role = session.get('role')
    if curr_role not in ('Administrator', 'Event Organizer') and task['assigned_to'] != curr_user_id:
        flash('You can only update tasks assigned to you.', 'danger')
        return redirect(url_for('tasks_list'))

    now_iso = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    db.execute("""
        UPDATE volunteer_tasks
        SET status = ?, updated_at = ?
        WHERE id = ?
    """, (new_status, now_iso, task_id))
    db.commit()

    if new_status == 'Completed' and task['assigned_to']:
        try:
            award_achievement_points(
                task['assigned_to'],
                points=30,
                reason=f"Volunteer Task Completed: {task['title']}",
                source_type='task_completed',
                source_id=task['id'],
                awarded_by=curr_user_id,
                db=db
            )
        except Exception as e:
            print(f"Volunteer points award notice: {e}")

    flash(f"Task status updated to '{new_status}'.", 'info')
    return redirect(url_for('tasks_list'))


@app.route('/announcements')
@login_required
def announcements_list():
    db = get_db()
    user_role = session.get('role', 'Member')

    # Allowed audiences based on role
    allowed = ['All']
    if user_role in ('Member', 'Administrator', 'Treasurer', 'Event Organizer', 'Volunteer'):
        allowed.append('Members')
    if user_role in ('Volunteer', 'Administrator', 'Event Organizer'):
        allowed.append('Volunteers')
    if user_role in ('Administrator', 'Treasurer', 'Event Organizer'):
        allowed.append('Executive')

    placeholders = ','.join('?' for _ in allowed)
    announcements = db.execute(f"""
        SELECT a.*, u.full_name AS publisher_name
        FROM announcements a
        JOIN users u ON a.published_by = u.id
        WHERE a.audience IN ({placeholders})
        ORDER BY a.created_at DESC
    """, allowed).fetchall()

    return render_template('announcements/list.html', announcements=announcements)


@app.route('/announcements/new', methods=['POST'])
@login_required
@role_required('Administrator', 'Event Organizer')
def announcements_new():
    title = request.form.get('title', '').strip()
    content = request.form.get('content', '').strip()
    audience = request.form.get('audience', 'All')
    priority = request.form.get('priority', 'Normal')

    if not title or not content:
        flash('Title and content are required for announcements.', 'danger')
        return redirect(url_for('announcements_list'))

    db = get_db()
    db.execute("""
        INSERT INTO announcements (title, content, audience, priority, published_by)
        VALUES (?, ?, ?, ?, ?)
    """, (title, content, audience, priority, session.get('user_id')))
    db.commit()
    flash('Announcement published successfully to club noticeboard.', 'success')
    return redirect(url_for('announcements_list'))


# -------------------------------------------------------------------------
# STUDENT ENGAGEMENT, ACHIEVEMENTS, CERTIFICATES & FEEDBACK
# -------------------------------------------------------------------------

def award_achievement_points(user_id, points, reason, source_type, source_id=None, awarded_by=None, db=None):
    """
    Safely awards engagement points to a student/user.
    Respects UNIQUE(user_id, source_type, source_id) so duplicate awards for the same action are ignored.
    Returns True if points were newly awarded, False if duplicate or invalid.
    """
    if not user_id or points == 0:
        return False
    if db is None:
        db = get_db()
    try:
        db.execute("""
            INSERT INTO achievement_points (user_id, points, reason, source_type, source_id, awarded_by)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, points, reason, source_type, source_id, awarded_by))
        db.commit()
        return True
    except sqlite3.IntegrityError:
        # Already awarded for this source_type and source_id
        return False
    except Exception as e:
        print(f"Notice awarding points: {e}")
        return False


def calculate_user_badges(user_id, db=None):
    """
    Evaluates and returns engagement badges for a student:
    - Welcome / Rookie: Joined the club system
    - Event Attendee: Checked into at least 1 event
    - Event Enthusiast: Checked into 2 or more events
    - Community Voice: Submitted at least 1 constructive feedback
    - Dedicated Volunteer: Completed at least 1 volunteer task
    - Certified Achiever: Earned 1 or more certificates
    - Point Master: Earned 50+ achievement points
    - Campus Legend: Earned 150+ achievement points
    """
    if db is None:
        db = get_db()

    total_row = db.execute("SELECT COALESCE(SUM(points), 0) AS total FROM achievement_points WHERE user_id = ?", (user_id,)).fetchone()
    total_points = total_row['total'] if total_row else 0

    user_row = db.execute("SELECT email FROM users WHERE id = ?", (user_id,)).fetchone()
    user_email = user_row['email'] if user_row else ''
    member_row = db.execute("SELECT id FROM members WHERE user_id = ? OR LOWER(email) = LOWER(?)", (user_id, user_email)).fetchone()
    member_id = member_row['id'] if member_row else None

    if member_id:
        attended_count = db.execute("""
            SELECT COUNT(*) AS c FROM tickets WHERE checked_in = 1 AND (member_id = ? OR LOWER(purchaser_email) = LOWER(?))
        """, (member_id, user_email)).fetchone()['c']
    else:
        attended_count = db.execute("""
            SELECT COUNT(*) AS c FROM tickets WHERE checked_in = 1 AND LOWER(purchaser_email) = LOWER(?)
        """, (user_email,)).fetchone()['c']

    feedback_count = db.execute("SELECT COUNT(*) AS c FROM student_feedback WHERE user_id = ?", (user_id,)).fetchone()['c']
    tasks_count = db.execute("SELECT COUNT(*) AS c FROM volunteer_tasks WHERE assigned_to = ? AND status = 'Completed'", (user_id,)).fetchone()['c']
    cert_count = db.execute("SELECT COUNT(*) AS c FROM student_certificates WHERE user_id = ? AND status = 'Issued'", (user_id,)).fetchone()['c']

    badges = [
        {
            'id': 'rookie',
            'title': 'Rookie Explorer',
            'icon': '🌱',
            'description': 'Joined the ClubSphere student community platform.',
            'unlocked': True,
            'criterion': 'Account active'
        },
        {
            'id': 'attendee',
            'title': 'Active Attendee',
            'icon': '🎟️',
            'description': 'Attended and verified check-in for your first campus event.',
            'unlocked': attended_count >= 1,
            'criterion': f'{min(attended_count, 1)}/1 events attended'
        },
        {
            'id': 'enthusiast',
            'title': 'Event Enthusiast',
            'icon': '🌟',
            'description': 'Checked in and participated in 2 or more campus events.',
            'unlocked': attended_count >= 2,
            'criterion': f'{min(attended_count, 2)}/2 events attended'
        },
        {
            'id': 'voice',
            'title': 'Community Voice',
            'icon': '💬',
            'description': 'Submitted constructive feedback or suggestions to club organizers.',
            'unlocked': feedback_count >= 1,
            'criterion': f'{min(feedback_count, 1)}/1 feedback submitted'
        },
        {
            'id': 'volunteer',
            'title': 'Dedicated Volunteer',
            'icon': '🤝',
            'description': 'Successfully completed volunteer tasks for the student organization.',
            'unlocked': tasks_count >= 1,
            'criterion': f'{min(tasks_count, 1)}/1 tasks completed'
        },
        {
            'id': 'certified',
            'title': 'Certified Achiever',
            'icon': '🎓',
            'description': 'Earned an official ClubSphere credential or certificate of participation.',
            'unlocked': cert_count >= 1,
            'criterion': f'{min(cert_count, 1)}/1 certificates earned'
        },
        {
            'id': 'point_master',
            'title': 'Point Master',
            'icon': '⚡',
            'description': 'Accumulated 50 or more engagement points.',
            'unlocked': total_points >= 50,
            'criterion': f'{min(total_points, 50)}/50 points'
        },
        {
            'id': 'campus_legend',
            'title': 'Campus Legend',
            'icon': '👑',
            'description': 'Reached top-tier extracurricular engagement with 150+ points.',
            'unlocked': total_points >= 150,
            'criterion': f'{min(total_points, 150)}/150 points'
        }
    ]
    return badges


def issue_certificate(user_id, title, activity_type, event_id=None, recipient_name=None, issuing_org="ClubSphere — Student Organization", issued_by=None, db=None):
    """
    Issues a verified certificate to a student.
    Generates a unique reference code and records the issue.
    """
    if db is None:
        db = get_db()

    if not recipient_name:
        user = db.execute("SELECT full_name FROM users WHERE id = ?", (user_id,)).fetchone()
        recipient_name = user['full_name'] if user else "Student Participant"

    year = datetime.now().year
    rand_suffix = secrets.token_hex(3).upper()
    cert_ref = f"CERT-{year}-{rand_suffix}"

    issue_date = date.today().isoformat()
    qr_data = f"CLUBSPHERE-CERT:{cert_ref}:{recipient_name}:{issue_date}"

    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO student_certificates (
            certificate_ref, user_id, title, activity_type, event_id,
            issuing_org, recipient_name, issue_date, status, issued_by, qr_data
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Issued', ?, ?)
    """, (cert_ref, user_id, title, activity_type, event_id, issuing_org, recipient_name, issue_date, issued_by, qr_data))
    cert_id = cursor.lastrowid
    db.commit()

    # Award points for certificate achievement
    award_achievement_points(user_id, 50, f"Earned Certificate: {title[:30]}", 'certificate', cert_id, issued_by, db=db)

    return cert_ref


def generate_certificate_pdf(cert):
    """
    Generates a high-quality, professional landscape PDF certificate using ReportLab.
    Returns raw bytes of the PDF.
    """
    if canvas is None:
        raise RuntimeError("ReportLab is not installed or available.")

    if hasattr(cert, 'keys'):
        cert = dict(cert)

    buf = io.BytesIO()
    # Landscape Letter: 792 wide x 612 tall
    width, height = landscape(letter)
    c = canvas.Canvas(buf, pagesize=(width, height))

    # Background tint
    c.setFillColor(colors.HexColor('#f8fafc'))
    c.rect(0, 0, width, height, fill=True, stroke=False)

    # Outer Decorative Border (Navy)
    c.setStrokeColor(colors.HexColor('#0f172a'))
    c.setLineWidth(3.5)
    c.rect(24, 24, width - 48, height - 48, fill=False, stroke=True)

    # Inner Decorative Border (Gold / Amber Accent)
    c.setStrokeColor(colors.HexColor('#d97706'))
    c.setLineWidth(1.5)
    c.rect(32, 32, width - 64, height - 64, fill=False, stroke=True)

    # Thin innermost border
    c.setStrokeColor(colors.HexColor('#e2e8f0'))
    c.setLineWidth(0.75)
    c.rect(36, 36, width - 72, height - 72, fill=False, stroke=True)

    # Top Brand Header
    c.setFillColor(colors.HexColor('#64748b'))
    c.setFont('Helvetica-Bold', 11)
    c.drawCentredString(width / 2.0, height - 62, "CLUBSPHERE STUDENT ORGANIZATION SYSTEM")

    c.setFillColor(colors.HexColor('#0f172a'))
    c.setFont('Helvetica-Bold', 26)
    c.drawCentredString(width / 2.0, height - 96, "CERTIFICATE OF ACHIEVEMENT")

    # Decorative divider
    c.setStrokeColor(colors.HexColor('#d97706'))
    c.setLineWidth(2)
    c.line(width / 2.0 - 90, height - 108, width / 2.0 + 90, height - 108)

    # Subtitle
    c.setFillColor(colors.HexColor('#475569'))
    c.setFont('Helvetica-Oblique', 12)
    c.drawCentredString(width / 2.0, height - 134, "This credential is proudly awarded to")

    # Recipient Name
    c.setFillColor(colors.HexColor('#1e293b'))
    c.setFont('Helvetica-Bold', 26)
    recipient = cert.get('recipient_name') or "Student Achiever"
    c.drawCentredString(width / 2.0, height - 180, recipient)

    # Underline for recipient
    name_width = c.stringWidth(recipient, 'Helvetica-Bold', 26)
    c.setStrokeColor(colors.HexColor('#cbd5e1'))
    c.setLineWidth(1)
    c.line(width / 2.0 - max(name_width / 2.0 + 20, 140), height - 188, width / 2.0 + max(name_width / 2.0 + 20, 140), height - 188)

    # Recognition text
    c.setFillColor(colors.HexColor('#334155'))
    c.setFont('Helvetica', 13)
    c.drawCentredString(width / 2.0, height - 222, "in recognition of meritorious contribution and distinguished participation in")

    # Activity / Title
    title_text = cert.get('title') or "Campus Student Engagement"
    c.setFillColor(colors.HexColor('#0284c7'))
    c.setFont('Helvetica-Bold', 16)
    c.drawCentredString(width / 2.0, height - 250, title_text)

    # Event context if available
    event_title = cert.get('event_title')
    if event_title and event_title != title_text:
        c.setFillColor(colors.HexColor('#64748b'))
        c.setFont('Helvetica-Oblique', 11)
        c.drawCentredString(width / 2.0, height - 274, f"Organized under: {event_title}")

    # Official verification statement
    c.setFillColor(colors.HexColor('#64748b'))
    c.setFont('Helvetica', 10)
    c.drawCentredString(width / 2.0, height - 310, "This digital certificate has been officially validated and permanently recorded on the ClubSphere ledger.")

    # Seal in center-bottom
    seal_x = width / 2.0
    seal_y = height - 410
    c.setStrokeColor(colors.HexColor('#d97706'))
    c.setFillColor(colors.HexColor('#fef3c7'))
    c.setLineWidth(2)
    c.circle(seal_x, seal_y, 32, fill=True, stroke=True)
    c.setFillColor(colors.HexColor('#92400e'))
    c.setFont('Helvetica-Bold', 8)
    c.drawCentredString(seal_x, seal_y + 8, "CLUBSPHERE")
    c.setFont('Helvetica-Bold', 7)
    c.drawCentredString(seal_x, seal_y - 2, "VERIFIED")
    c.setFont('Helvetica', 6)
    c.drawCentredString(seal_x, seal_y - 12, "SEAL")

    # Left signatory block
    left_x = 90
    bottom_y = 110
    c.setStrokeColor(colors.HexColor('#94a3b8'))
    c.setLineWidth(1)
    c.line(left_x, bottom_y + 35, left_x + 180, bottom_y + 35)

    c.setFillColor(colors.HexColor('#1e293b'))
    c.setFont('Helvetica-Bold', 11)
    c.drawString(left_x, bottom_y + 20, cert.get('issuing_org') or "ClubSphere Executive Council")
    c.setFillColor(colors.HexColor('#64748b'))
    c.setFont('Helvetica', 9)
    c.drawString(left_x, bottom_y + 6, f"Issue Date: {cert.get('issue_date') or date.today().isoformat()}")
    c.drawString(left_x, bottom_y - 6, f"Activity: {cert.get('activity_type') or 'Student Involvement'}")

    # Right signatory block / Certificate ID
    right_x = width - 270
    c.line(right_x, bottom_y + 35, right_x + 180, bottom_y + 35)
    c.setFillColor(colors.HexColor('#1e293b'))
    c.setFont('Helvetica-Bold', 11)
    c.drawString(right_x, bottom_y + 20, "Credential Verification")
    c.setFillColor(colors.HexColor('#64748b'))
    c.setFont('Helvetica-Bold', 9)
    c.drawString(right_x, bottom_y + 6, f"ID: {cert.get('certificate_ref')}")
    c.setFont('Helvetica', 9)
    c.drawString(right_x, bottom_y - 6, f"Status: {str(cert.get('status', 'Issued')).upper()}")

    # Bottom watermark footer
    c.setFillColor(colors.HexColor('#94a3b8'))
    c.setFont('Helvetica', 8)
    c.drawCentredString(width / 2.0, 44, "ClubSphere Student Organization System — Extracurricular Achievement Registry")

    c.save()
    buf.seek(0)
    return buf.getvalue()


# -------------------------------------------------------------------------
# ROUTES: STUDENT FEEDBACK & SUGGESTIONS
# -------------------------------------------------------------------------

@app.route('/feedback', methods=['GET', 'POST'])
@login_required
def feedback_center():
    db = get_db()
    user_id = session['user_id']
    user_role = session.get('role', 'Member')

    if request.method == 'POST':
        feedback_type = request.form.get('feedback_type', '').strip()
        event_id = request.form.get('event_id', type=int)
        rating = request.form.get('rating', type=int)
        subject = request.form.get('subject', '').strip()
        message = request.form.get('message', '').strip()
        is_anonymous = 1 if request.form.get('is_anonymous') in ['1', 'true', 'on'] else 0

        errors = []
        if feedback_type not in ('Event', 'Club Activity', 'Workshop', 'Membership', 'General Suggestion'):
            errors.append('Please select a valid feedback category.')
        if not subject or len(subject) < 3:
            errors.append('Subject must be at least 3 characters long.')
        if not message or len(message) < 5:
            errors.append('Message must be at least 5 characters long.')
        if rating is not None and (rating < 1 or rating > 5):
            errors.append('Rating must be between 1 and 5.')

        if errors:
            for e in errors:
                flash(e, 'danger')
        else:
            cursor = db.cursor()
            cursor.execute("""
                INSERT INTO student_feedback (user_id, feedback_type, event_id, rating, subject, message, is_anonymous, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'Submitted')
            """, (user_id, feedback_type, event_id, rating, subject, message, is_anonymous))
            db.commit()
            feedback_id = cursor.lastrowid

            # Award engagement points for constructive community feedback
            award_achievement_points(user_id, 15, f"Feedback submitted: {subject[:30]}", 'feedback', feedback_id, db=db)

            flash('Thank you! Your feedback has been submitted successfully (+15 engagement points awarded).', 'success')
            return redirect(url_for('feedback_center'))

    # GET: fetch events, my submissions, and admin dashboard if staff
    events = db.execute("SELECT id, title FROM events ORDER BY event_date DESC").fetchall()
    my_feedbacks = db.execute("""
        SELECT f.*, e.title AS event_title
        FROM student_feedback f
        LEFT JOIN events e ON f.event_id = e.id
        WHERE f.user_id = ?
        ORDER BY f.created_at DESC
    """, (user_id,)).fetchall()

    admin_feedbacks = []
    is_staff = user_role in ('Administrator', 'Event Organizer')
    if is_staff:
        admin_feedbacks = db.execute("""
            SELECT f.*, e.title AS event_title, u.username, u.full_name, u.email,
                   reviewer.full_name AS reviewer_name
            FROM student_feedback f
            JOIN users u ON f.user_id = u.id
            LEFT JOIN events e ON f.event_id = e.id
            LEFT JOIN users reviewer ON f.reviewed_by = reviewer.id
            ORDER BY f.created_at DESC
        """).fetchall()

    return render_template(
        'feedback/index.html',
        events=events,
        my_feedbacks=my_feedbacks,
        admin_feedbacks=admin_feedbacks,
        is_staff=is_staff
    )


@app.route('/feedback/<int:feedback_id>/status', methods=['POST'])
@login_required
@role_required('Administrator', 'Event Organizer')
def feedback_update_status(feedback_id):
    db = get_db()
    new_status = request.form.get('status', 'Reviewed')
    admin_notes = request.form.get('admin_notes', '').strip()
    if new_status not in ('Submitted', 'Reviewed', 'Actioned', 'Closed'):
        flash('Invalid status selected.', 'danger')
        return redirect(url_for('feedback_center'))

    now_iso = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    db.execute("""
        UPDATE student_feedback
        SET status = ?, admin_notes = ?, reviewed_by = ?, reviewed_at = ?
        WHERE id = ?
    """, (new_status, admin_notes, session['user_id'], now_iso, feedback_id))
    db.commit()
    flash(f"Feedback status updated to '{new_status}'.", 'success')
    return redirect(url_for('feedback_center'))


# -------------------------------------------------------------------------
# ROUTES: ACHIEVEMENT POINTS & CREDITS
# -------------------------------------------------------------------------

@app.route('/achievements')
@login_required
def achievements_dashboard():
    db = get_db()
    user_id = session['user_id']

    total_row = db.execute("SELECT COALESCE(SUM(points), 0) AS total FROM achievement_points WHERE user_id = ?", (user_id,)).fetchone()
    total_points = total_row['total'] if total_row else 0

    history = db.execute("""
        SELECT ap.*, u.full_name AS awarded_by_name
        FROM achievement_points ap
        LEFT JOIN users u ON ap.awarded_by = u.id
        WHERE ap.user_id = ?
        ORDER BY ap.created_at DESC
    """, (user_id,)).fetchall()

    badges = calculate_user_badges(user_id, db)
    unlocked_count = sum(1 for b in badges if b['unlocked'])

    raw_leaderboard = db.execute("""
        SELECT u.id, u.username, u.full_name, u.role, u.department, u.privacy_settings,
               COALESCE(SUM(ap.points), 0) AS total_points
        FROM users u
        JOIN achievement_points ap ON u.id = ap.user_id
        WHERE u.is_active = 1
        GROUP BY u.id
        HAVING total_points > 0
        ORDER BY total_points DESC
        LIMIT 15
    """).fetchall()

    leaderboard = []
    rank = 1
    for row in raw_leaderboard:
        is_me = (row['id'] == user_id)
        privacy = {}
        if row['privacy_settings']:
            try:
                privacy = json.loads(row['privacy_settings'])
            except Exception:
                privacy = {}
        show_on_board = privacy.get('show_on_leaderboard', True)

        display_name = row['full_name']
        display_username = f"@{row['username']}"
        if not show_on_board and not is_me:
            display_name = "Anonymous Student"
            display_username = "@hidden"

        leaderboard.append({
            'rank': rank,
            'user_id': row['id'],
            'display_name': display_name,
            'display_username': display_username,
            'role': row['role'],
            'department': row['department'] or 'General Campus',
            'total_points': row['total_points'],
            'is_me': is_me
        })
        rank += 1

    return render_template(
        'achievements/index.html',
        total_points=total_points,
        history=history,
        badges=badges,
        unlocked_count=unlocked_count,
        leaderboard=leaderboard
    )


# -------------------------------------------------------------------------
# ROUTES: CERTIFICATES & ACHIEVEMENT WALLET
# -------------------------------------------------------------------------

@app.route('/certificates')
@login_required
def certificates_wallet():
    db = get_db()
    user_id = session['user_id']
    user_role = session.get('role')

    my_certs = db.execute("""
        SELECT c.*, e.title AS event_title, u.full_name AS issuer_name
        FROM student_certificates c
        LEFT JOIN events e ON c.event_id = e.id
        LEFT JOIN users u ON c.issued_by = u.id
        WHERE c.user_id = ?
        ORDER BY c.issue_date DESC, c.id DESC
    """, (user_id,)).fetchall()

    is_staff = user_role in ('Administrator', 'Event Organizer')
    all_certs = []
    active_users = []
    events = []
    if is_staff:
        all_certs = db.execute("""
            SELECT c.*, e.title AS event_title, u.full_name AS recipient_user_name, u.email AS recipient_email
            FROM student_certificates c
            JOIN users u ON c.user_id = u.id
            LEFT JOIN events e ON c.event_id = e.id
            ORDER BY c.created_at DESC
        """).fetchall()
        active_users = db.execute("SELECT id, full_name, email, role FROM users WHERE is_active = 1 ORDER BY full_name ASC").fetchall()
        events = db.execute("SELECT id, title FROM events ORDER BY event_date DESC").fetchall()

    return render_template(
        'certificates/index.html',
        my_certs=my_certs,
        all_certs=all_certs,
        active_users=active_users,
        events=events,
        is_staff=is_staff
    )


@app.route('/certificates/<cert_ref>')
def certificate_view(cert_ref):
    db = get_db()
    cert = db.execute("""
        SELECT c.*, e.title AS event_title, u.full_name AS user_full_name, u.email AS user_email,
               u.department, u.student_id, issuer.full_name AS issuer_name
        FROM student_certificates c
        JOIN users u ON c.user_id = u.id
        LEFT JOIN events e ON c.event_id = e.id
        LEFT JOIN users issuer ON c.issued_by = issuer.id
        WHERE UPPER(c.certificate_ref) = UPPER(?)
    """, (cert_ref,)).fetchone()

    if not cert:
        abort(404)

    qr_svg = generate_qr_svg(url_for('certificate_view', cert_ref=cert['certificate_ref'], _external=True))
    return render_template('certificates/view.html', cert=cert, qr_svg=qr_svg)


@app.route('/certificates/<cert_ref>/pdf')
def certificate_pdf_download(cert_ref):
    db = get_db()
    cert = db.execute("""
        SELECT c.*, e.title AS event_title
        FROM student_certificates c
        LEFT JOIN events e ON c.event_id = e.id
        WHERE UPPER(c.certificate_ref) = UPPER(?)
    """, (cert_ref,)).fetchone()

    if not cert:
        abort(404)

    try:
        pdf_bytes = generate_certificate_pdf(cert)
    except Exception as e:
        flash(f"Error generating certificate PDF: {e}", 'danger')
        return redirect(url_for('certificate_view', cert_ref=cert_ref))

    response = make_response(pdf_bytes)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename="certificate_{cert["certificate_ref"]}.pdf"'
    return response


@app.route('/certificates/issue', methods=['POST'])
@login_required
@role_required('Administrator', 'Event Organizer')
def certificates_issue():
    db = get_db()
    user_id = request.form.get('user_id', type=int)
    title = request.form.get('title', '').strip()
    activity_type = request.form.get('activity_type', 'Event Participation').strip()
    event_id = request.form.get('event_id', type=int)
    recipient_name = request.form.get('recipient_name', '').strip()
    issuing_org = request.form.get('issuing_org', 'ClubSphere — Student Organization').strip()

    if not user_id or not title:
        flash('Recipient user and certificate title are required.', 'danger')
        return redirect(url_for('certificates_wallet'))

    target_user = db.execute("SELECT full_name FROM users WHERE id = ?", (user_id,)).fetchone()
    if not target_user:
        flash('Selected user account was not found.', 'danger')
        return redirect(url_for('certificates_wallet'))

    if not recipient_name:
        recipient_name = target_user['full_name']

    cert_ref = issue_certificate(
        user_id=user_id,
        title=title,
        activity_type=activity_type,
        event_id=event_id,
        recipient_name=recipient_name,
        issuing_org=issuing_org,
        issued_by=session['user_id'],
        db=db
    )

    flash(f"Certificate '{cert_ref}' successfully issued to {recipient_name} (+50 points awarded).", 'success')
    return redirect(url_for('certificates_wallet'))


# -------------------------------------------------------------------------
# ROUTES: STUDENT CLUB MEMBERSHIP PROFILES
# -------------------------------------------------------------------------

@app.route('/my-memberships')
@login_required
def my_memberships():
    db = get_db()
    user_id = session['user_id']
    current_user_row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    user_email = current_user_row['email'] if current_user_row else ''

    member = db.execute("""
        SELECT * FROM members
        WHERE user_id = ? OR LOWER(email) = LOWER(?)
        ORDER BY id DESC LIMIT 1
    """, (user_id, user_email)).fetchone()

    attended_events_count = 0
    if member:
        attended_events_count = db.execute("""
            SELECT COUNT(*) AS c FROM tickets WHERE checked_in = 1 AND (member_id = ? OR LOWER(purchaser_email) = LOWER(?))
        """, (member['id'], user_email)).fetchone()['c']
    else:
        attended_count_row = db.execute("""
            SELECT COUNT(*) AS c FROM tickets WHERE checked_in = 1 AND LOWER(purchaser_email) = LOWER(?)
        """, (user_email,)).fetchone()
        attended_events_count = attended_count_row['c'] if attended_count_row else 0

    volunteer_tasks_count = db.execute("""
        SELECT COUNT(*) AS c FROM volunteer_tasks WHERE assigned_to = ? AND status = 'Completed'
    """, (user_id,)).fetchone()['c']

    points_row = db.execute("SELECT COALESCE(SUM(points), 0) AS total FROM achievement_points WHERE user_id = ?", (user_id,)).fetchone()
    total_points = points_row['total'] if points_row else 0

    certificates_count = db.execute("SELECT COUNT(*) AS c FROM student_certificates WHERE user_id = ? AND status = 'Issued'", (user_id,)).fetchone()['c']

    days_remaining = None
    is_expiring_soon = False
    is_expired = False
    if member and member['expiry_date']:
        try:
            exp_date = datetime.strptime(member['expiry_date'], '%Y-%m-%d').date()
            days_remaining = (exp_date - date.today()).days
            if days_remaining <= 0:
                is_expired = True
            elif days_remaining <= 30:
                is_expiring_soon = True
        except Exception:
            pass

    my_tickets = db.execute("""
        SELECT t.*, e.title AS event_title, e.event_date, e.event_time, e.venue
        FROM tickets t
        JOIN events e ON t.event_id = e.id
        WHERE (t.purchaser_email = ? OR (t.member_id IS NOT NULL AND t.member_id = ?))
        ORDER BY t.created_at DESC LIMIT 5
    """, (user_email, member['id'] if member else -1)).fetchall()

    return render_template(
        'members/my_memberships.html',
        member=member,
        user=current_user_row,
        days_remaining=days_remaining,
        is_expiring_soon=is_expiring_soon,
        is_expired=is_expired,
        attended_events_count=attended_events_count,
        volunteer_tasks_count=volunteer_tasks_count,
        total_points=total_points,
        certificates_count=certificates_count,
        my_tickets=my_tickets
    )


# -------------------------------------------------------------------------
# AI CLUB COPILOT / USER AI ASSISTANT ROUTES
# -------------------------------------------------------------------------

PERMITTED_COPILOT_ROLES = ('Treasurer', 'Event Organizer', 'Volunteer', 'Member')


@app.route('/copilot', methods=['GET'])
@login_required
def copilot_chat():
    user_role = session.get('role')
    if user_role not in PERMITTED_COPILOT_ROLES:
        flash('Access denied. The AI Assistant is available on student and member portals.', 'warning')
        return redirect(url_for('dashboard'))

    prompt = request.args.get('prompt', '').strip()
    initial_response = None
    if prompt:
        db = get_db()
        current_user = {
            'id': session.get('user_id'),
            'username': session.get('username'),
            'full_name': session.get('full_name'),
            'role': session.get('role')
        }
        initial_response = copilot_service.ask_copilot(db, current_user, prompt)
        if initial_response.get('status') == 'ok' and initial_response.get('response'):
            session['copilot_history'] = [
                {'role': 'user', 'content': prompt},
                {'role': 'assistant', 'content': initial_response['response']}
            ]
            session.modified = True
    else:
        # Clear previous transient history if visiting chat fresh without prompt
        session.setdefault('copilot_history', [])

    ai_config = copilot_service.get_ai_config()
    return render_template(
        'copilot.html',
        ai_config=ai_config,
        initial_prompt=prompt,
        initial_response=initial_response
    )


@app.route('/copilot/ask', methods=['POST'])
@login_required
def copilot_ask():
    user_role = session.get('role')
    if user_role not in PERMITTED_COPILOT_ROLES:
        return jsonify({
            'status': 'error',
            'message': 'Access denied. The AI Assistant is available for member and student accounts.'
        }), 403

    data = request.get_json(silent=True) or request.form
    message = data.get('message', '').strip()
    if not message:
        return jsonify({'status': 'error', 'message': 'Message is required.'}), 400

    raw_history = data.get('history')
    if not isinstance(raw_history, list):
        raw_history = session.get('copilot_history', [])

    clean_history = []
    for turn in raw_history[-8:]:
        if isinstance(turn, dict) and 'role' in turn and 'content' in turn:
            role = 'user' if turn.get('role') == 'user' else 'assistant'
            content = str(turn.get('content', '')).strip()
            if content:
                clean_history.append({'role': role, 'content': content[:2500]})

    db = get_db()
    current_user = {
        'id': session.get('user_id'),
        'username': session.get('username'),
        'full_name': session.get('full_name'),
        'role': session.get('role')
    }
    result = copilot_service.ask_copilot(db, current_user, message, history=clean_history)

    # Persist turns in user session
    hist = session.get('copilot_history', [])
    hist.append({'role': 'user', 'content': message})
    if result.get('status') == 'ok' and result.get('response'):
        hist.append({'role': 'assistant', 'content': result['response']})
    session['copilot_history'] = hist[-16:]
    session.modified = True

    return jsonify(result), 200


@app.route('/copilot/clear', methods=['POST'])
@login_required
def copilot_clear():
    user_role = session.get('role')
    if user_role not in PERMITTED_COPILOT_ROLES:
        return jsonify({'status': 'error', 'message': 'Access denied.'}), 403

    session.pop('copilot_history', None)
    session.modified = True
    return jsonify({'status': 'ok', 'message': 'Conversation history cleared.'}), 200


# -------------------------------------------------------------------------
# CLI & APPLICATION ENTRY POINT
# -------------------------------------------------------------------------


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="ClubSphere - Student Organization Management System")
    parser.add_argument('--demo', action='store_true', help="Run with isolated demo database (instance/clubsphere_demo.db)")
    parser.add_argument('--prod', action='store_true', help="Run with production database (instance/clubsphere.db)")
    parser.add_argument('--db', type=str, default=None, help="Custom SQLite database path")
    parser.add_argument('--port', type=int, default=5000, help="Port to listen on (default: 5000)")
    parser.add_argument('--host', type=str, default='127.0.0.1', help="Host to bind to (default: 127.0.0.1)")
    args, _ = parser.parse_known_args()

    demo_db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance', 'clubsphere_demo.db')

    if args.demo:
        app.config['DATABASE'] = demo_db_path
        os.environ['CLUB_SPHERE_DB'] = demo_db_path
    elif args.prod:
        app.config['DATABASE'] = database.DEFAULT_DB_PATH
        os.environ['CLUB_SPHERE_DB'] = database.DEFAULT_DB_PATH
    elif args.db:
        app.config['DATABASE'] = args.db
        os.environ['CLUB_SPHERE_DB'] = args.db
    elif os.environ.get('CLUB_SPHERE_DB'):
        app.config['DATABASE'] = os.environ['CLUB_SPHERE_DB']
    elif os.path.exists(demo_db_path):
        app.config['DATABASE'] = demo_db_path
        os.environ['CLUB_SPHERE_DB'] = demo_db_path

    effective_db = app.config['DATABASE']
    database.init_db(effective_db)

    is_demo = os.path.abspath(effective_db) == os.path.abspath(demo_db_path)

    if is_demo:
        conn = database.get_db(effective_db)
        user_count = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()['c']
        conn.close()
        if user_count == 0:
            import seed_demo
            seed_demo.seed_demo_database(effective_db, verbose=True)

    print("=" * 68)
    print("  ClubSphere - Student Organization Management System")
    print(f"  [*] Effective Database: {effective_db}")
    if is_demo:
        print("  [*] Mode: DEMO ENVIRONMENT (pre-seeded with demo records)")
        print("  [*] Demo Accounts: demo_admin, demo_treasurer, demo_organizer,")
        print("                     demo_volunteer, demo_member")
        print("  [*] Demo Password: Password123!")
    else:
        print("  [*] Mode: PRIMARY / PRODUCTION (instance/clubsphere.db)")
        print("  [*] Tip: To launch demo mode, run: python app.py --demo")
        print("           Or set $env:CLUB_SPHERE_DB=\"instance\\clubsphere_demo.db\"")
    print(f"  [*] Web Server: http://{args.host}:{args.port}")
    print("=" * 68)

    app.run(host=args.host, port=args.port, debug=True)
