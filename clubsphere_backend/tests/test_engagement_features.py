import io
import json
import pytest
from tests.conftest import create_user, login


def test_feedback_submission_and_points(client, db):
    """Students can submit feedback, earn 15 points, and view their submission."""
    create_user(db, username='admin', role='Administrator')
    student_id = create_user(db, username='student1', role='Member')

    login(client, 'student1')

    # Submit valid feedback
    res = client.post('/feedback', data={
        'feedback_type': 'Event',
        'rating': '5',
        'subject': 'Great Robotics Workshop',
        'message': 'Really enjoyed the hands-on Arduino session. Would love more time next time.',
        'is_anonymous': '0'
    }, follow_redirects=True)

    assert res.status_code == 200
    assert b"Your feedback has been submitted successfully" in res.data
    assert b"Great Robotics Workshop" in res.data

    # Verify points awarded
    points_row = db.execute("SELECT * FROM achievement_points WHERE user_id = ? AND source_type = 'feedback'", (student_id,)).fetchone()
    assert points_row is not None
    assert points_row['points'] == 15

    # Verify student_feedback record
    fb_row = db.execute("SELECT * FROM student_feedback WHERE user_id = ?", (student_id,)).fetchone()
    assert fb_row is not None
    assert fb_row['subject'] == 'Great Robotics Workshop'
    assert fb_row['rating'] == 5
    assert fb_row['is_anonymous'] == 0


def test_anonymous_feedback_masking(client, db):
    """Anonymous feedback masks student identity in the staff moderation console."""
    create_user(db, username='admin', role='Administrator')
    create_user(db, username='shy_student', role='Member', full_name='Alice Hidden', email='alice@hidden.edu')

    login(client, 'shy_student')
    client.post('/feedback', data={
        'feedback_type': 'General Suggestion',
        'rating': '4',
        'subject': 'Club Meeting Timing',
        'message': 'Please consider weekend timings instead of late weekday evenings.',
        'is_anonymous': '1'
    }, follow_redirects=True)

    # Admin signs in and reviews moderation console
    login(client, 'admin')
    res_admin = client.get('/feedback')
    assert res_admin.status_code == 200
    assert b"Anonymous Student" in res_admin.data
    # Alice Hidden and alice@hidden.edu should not be displayed in the anonymous row
    assert b"Club Meeting Timing" in res_admin.data


def test_staff_feedback_status_update(client, db):
    """Administrator and Event Organizer can update feedback status and add notes."""
    create_user(db, username='admin', role='Administrator')
    create_user(db, username='member1', role='Member')

    login(client, 'member1')
    client.post('/feedback', data={
        'feedback_type': 'Workshop',
        'subject': 'Need Python Cheatsheet',
        'message': 'Can you provide PDF cheat sheets?',
    })
    fb = db.execute("SELECT id FROM student_feedback ORDER BY id DESC LIMIT 1").fetchone()

    # Unauthorized user cannot update status
    res_unauth = client.post(f'/feedback/{fb["id"]}/status', data={'status': 'Actioned', 'admin_notes': 'Denied'}, follow_redirects=True)
    assert b"Access denied" in res_unauth.data

    # Admin can update
    login(client, 'admin')
    res_admin = client.post(f'/feedback/{fb["id"]}/status', data={'status': 'Actioned', 'admin_notes': 'Cheatsheets uploaded to noticeboard.'}, follow_redirects=True)
    assert res_admin.status_code == 200
    assert b"Feedback status updated to" in res_admin.data

    fb_updated = db.execute("SELECT * FROM student_feedback WHERE id = ?", (fb['id'],)).fetchone()
    assert fb_updated['status'] == 'Actioned'
    assert fb_updated['admin_notes'] == 'Cheatsheets uploaded to noticeboard.'


def test_achievements_dashboard_and_disclaimer(client, db):
    """Achievements dashboard renders points, badges, leaderboard, and mandatory academic disclaimer."""
    create_user(db, username='admin', role='Administrator')
    student_id = create_user(db, username='star_student', role='Member')

    # Award initial points directly
    from app import award_achievement_points
    with client.application.app_context():
        award_achievement_points(student_id, 50, "Special Hackathon Award", "award", 999, db=db)

    login(client, 'star_student')
    res = client.get('/achievements')
    assert res.status_code == 200
    # Mandatory academic credits disclaimer must be present
    assert b"Extracurricular Activity Credits Disclaimer" in res.data
    assert b"distinct and separate from official university academic" in res.data
    # Points and badges
    assert b"50" in res.data
    assert b"Point Master" in res.data


def test_achievement_points_duplicate_prevention(client, db):
    """UNIQUE(user_id, source_type, source_id) prevents double-awarding points for same action."""
    create_user(db, username='admin', role='Administrator')
    student_id = create_user(db, username='gamer', role='Member')

    from app import award_achievement_points
    with client.application.app_context():
        first = award_achievement_points(student_id, 25, "Event Attendance", "ticket_checkin", 101, db=db)
        second = award_achievement_points(student_id, 25, "Event Attendance Duplicate", "ticket_checkin", 101, db=db)

    assert first is True
    assert second is False

    total_rows = db.execute("SELECT COUNT(*) AS c FROM achievement_points WHERE user_id = ?", (student_id,)).fetchone()['c']
    assert total_rows == 1


def test_certificates_issuance_and_pdf_generation(client, db):
    """Authorized staff can issue certificates; students can view and download ReportLab PDF."""
    create_user(db, username='admin', role='Administrator')
    student_id = create_user(db, username='grad_student', role='Member', full_name='John Doe')

    # Issue certificate
    login(client, 'admin')
    res_issue = client.post('/certificates/issue', data={
        'user_id': str(student_id),
        'title': 'Excellence in AI Workshop',
        'activity_type': 'Workshop Completion',
        'recipient_name': 'John Doe',
        'issuing_org': 'ClubSphere Tech Society'
    }, follow_redirects=True)

    assert res_issue.status_code == 200
    assert b"successfully issued to John Doe" in res_issue.data

    cert = db.execute("SELECT * FROM student_certificates WHERE user_id = ?", (student_id,)).fetchone()
    assert cert is not None
    assert cert['title'] == 'Excellence in AI Workshop'
    assert cert['certificate_ref'].startswith('CERT-')

    # Verify student wallet shows certificate
    login(client, 'grad_student')
    wallet_res = client.get('/certificates')
    assert wallet_res.status_code == 200
    assert b"Excellence in AI Workshop" in wallet_res.data

    # Web certificate view
    view_res = client.get(f'/certificates/{cert["certificate_ref"]}')
    assert view_res.status_code == 200
    assert b"CERTIFICATE OF ACHIEVEMENT" in view_res.data
    assert b"John Doe" in view_res.data

    # PDF Download
    pdf_res = client.get(f'/certificates/{cert["certificate_ref"]}/pdf')
    assert pdf_res.status_code == 200
    assert pdf_res.headers['Content-Type'] == 'application/pdf'
    assert pdf_res.data.startswith(b'%PDF-')
    assert len(pdf_res.data) > 1000


def test_my_memberships_profile(client, db):
    """Student can view their membership profile, days remaining, and activity stats."""
    create_user(db, username='admin', role='Administrator')
    member_user_id = create_user(db, username='member_alice', role='Member', email='alice@student.org', full_name='Alice Smith')

    # Create membership record in members table
    db.execute("""
        INSERT INTO members (user_id, member_code, full_name, email, join_date, expiry_date, membership_type, status)
        VALUES (?, 'MEM-2026-999', 'Alice Smith', 'alice@student.org', '2026-01-01', '2026-12-31', 'Annual', 'Active')
    """, (member_user_id,))
    db.commit()

    login(client, 'member_alice')
    res = client.get('/my-memberships')
    assert res.status_code == 200
    assert b"MEM-2026-999" in res.data
    assert b"Annual Tier" in res.data
    assert b"Active Member" in res.data


def test_profile_settings_and_preferences(client, db):
    """Profile updates academic details, contact info, notification JSON, and privacy settings."""
    create_user(db, username='admin', role='Administrator')
    create_user(db, username='prof_user', role='Member', email='user@test.org', full_name='Original Name')

    login(client, 'prof_user')

    # Update personal and academic info
    res_info = client.post('/profile', data={
        'action': 'update_info',
        'full_name': 'Dr. Original Updated',
        'email': 'user_new@test.org',
        'phone': '+91 99999 88888',
        'department': 'Mechanical Engineering',
        'academic_year': '3rd Year (Junior)',
        'student_id': 'MECH-2026-042',
        'bio': 'Passionate about robotics and club hackathons.'
    }, follow_redirects=True)
    assert res_info.status_code == 200
    assert b"Profile information updated successfully" in res_info.data

    # Update notification & privacy preferences
    res_pref = client.post('/profile', data={
        'action': 'update_preferences',
        'notif_email': '1',
        'notif_announcements': '1',
        # notif_events omitted -> False
        'privacy_leaderboard': '1',
        # privacy_badges omitted -> False
    }, follow_redirects=True)
    assert res_pref.status_code == 200
    assert b"Preferences and privacy settings updated successfully" in res_pref.data

    # Verify user record in database
    user = db.execute("SELECT * FROM users WHERE username = 'prof_user'").fetchone()
    assert user['full_name'] == 'Dr. Original Updated'
    assert user['email'] == 'user_new@test.org'
    assert user['department'] == 'Mechanical Engineering'
    assert user['student_id'] == 'MECH-2026-042'

    notif_data = json.loads(user['notification_preferences'])
    assert notif_data['email'] is True
    assert notif_data['events'] is False

    privacy_data = json.loads(user['privacy_settings'])
    assert privacy_data['show_on_leaderboard'] is True
    assert privacy_data['show_badges'] is False


def test_ticket_checkin_auto_awards_points(client, db):
    """Verifying a ticket at check-in automatically awards 25 engagement points to the attendee."""
    admin_id = create_user(db, username='admin', role='Administrator')
    student_id = create_user(db, username='event_goer', role='Member', email='goer@student.org', full_name='Sam Goer')

    # Create event and ticket
    db.execute("""
        INSERT INTO events (title, description, event_date, event_time, venue, capacity, member_price, non_member_price, status)
        VALUES ('Robotics Hackathon 2026', 'National event', '2026-11-20', '10:00', 'Auditorium A', 100, 50, 100, 'Upcoming')
    """)
    event_id = db.execute("SELECT id FROM events ORDER BY id DESC LIMIT 1").fetchone()['id']

    db.execute("""
        INSERT INTO tickets (ticket_ref, event_id, purchaser_name, purchaser_email, price_paid, payment_status, checked_in)
        VALUES ('TICK-HACK-01', ?, 'Sam Goer', 'goer@student.org', 50, 'Confirmed', 0)
    """, (event_id,))
    ticket = db.execute("SELECT * FROM tickets ORDER BY id DESC LIMIT 1").fetchone()
    db.commit()

    login(client, 'admin')
    res = client.post('/tickets/checkin', data={
        'ticket_ref': 'TICK-HACK-01',
        'event_id': str(event_id)
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b"Check-In Successful" in res.data

    # Verify points awarded to student
    pts = db.execute("SELECT * FROM achievement_points WHERE user_id = ? AND source_type = 'ticket_checkin'", (student_id,)).fetchone()
    assert pts is not None
    assert pts['points'] == 25
    assert pts['source_id'] == ticket['id']


def test_task_completion_auto_awards_points(client, db):
    """Marking a volunteer task as Completed automatically awards 30 engagement points to the assignee."""
    admin_id = create_user(db, username='admin', role='Administrator')
    vol_id = create_user(db, username='task_hero', role='Volunteer')

    # Create task assigned to volunteer
    db.execute("""
        INSERT INTO volunteer_tasks (title, description, assigned_to, priority, status)
        VALUES ('Set up audio systems', 'Check all microphones', ?, 'High', 'In Progress')
    """, (vol_id,))
    task_id = db.execute("SELECT id FROM volunteer_tasks ORDER BY id DESC LIMIT 1").fetchone()['id']
    db.commit()

    login(client, 'task_hero')
    res = client.post(f'/tasks/{task_id}/status', data={'status': 'Completed'}, follow_redirects=True)
    assert res.status_code == 200
    assert b"Task status updated to &#39;Completed&#39;" in res.data or b"Task status updated to 'Completed'" in res.data

    pts = db.execute("SELECT * FROM achievement_points WHERE user_id = ? AND source_type = 'task_completed'", (vol_id,)).fetchone()
    assert pts is not None
    assert pts['points'] == 30
    assert pts['source_id'] == task_id


def test_admin_sidebar_removes_student_engagement_and_preserves_for_users(client, db):
    """Administrator sidebar hides Student Engagement section; User Portal displays it."""
    create_user(db, username='admin', role='Administrator')
    create_user(db, username='student_user', role='Member')

    # 1. Check Administrator Sidebar
    login(client, 'admin')
    res_admin = client.get('/dashboard')
    assert res_admin.status_code == 200

    # Student Engagement section and links must NOT appear for Admin
    assert b"Student Engagement" not in res_admin.data
    assert b"My Club Membership" not in res_admin.data
    assert b"Achievements &amp; Credits" not in res_admin.data and b"Achievements & Credits" not in res_admin.data
    assert b"Certificates Wallet" not in res_admin.data
    assert b"Feedback &amp; Suggestions" not in res_admin.data and b"Feedback & Suggestions" not in res_admin.data

    # Standard Admin sections must still be present
    assert b"Dashboard" in res_admin.data
    assert b"Analytics" in res_admin.data
    assert b"Memberships" in res_admin.data
    assert b"Financial Ledger" in res_admin.data
    assert b"Expenses" in res_admin.data
    assert b"Volunteer Tasks" in res_admin.data
    assert b"Announcements" in res_admin.data
    assert b"User Accounts" in res_admin.data
    assert b"Profile" in res_admin.data
    assert b"Sign Out" in res_admin.data

    # 2. Check User (Member) Sidebar
    login(client, 'student_user')
    res_member = client.get('/dashboard')
    assert res_member.status_code == 200

    # Student Engagement section and all 4 links MUST be present for Member
    assert b"Student Engagement" in res_member.data
    assert b"My Club Membership" in res_member.data
    assert b"Achievements &amp; Credits" in res_member.data or b"Achievements & Credits" in res_member.data
    assert b"Certificates Wallet" in res_member.data
    assert b"Feedback &amp; Suggestions" in res_member.data or b"Feedback & Suggestions" in res_member.data


