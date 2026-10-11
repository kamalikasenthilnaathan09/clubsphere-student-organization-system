# Engagement features extracted from app.py: achievements, badges, certificates, feedback, my-memberships.
# Reference extract - needs the imports/helpers from app.py (get_db, login_required, role_required...) to run.
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

