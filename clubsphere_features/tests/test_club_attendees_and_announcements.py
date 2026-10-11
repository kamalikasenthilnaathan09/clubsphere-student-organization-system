import pytest
from datetime import date
from tests.conftest import create_user, login
import email_service


def test_admin_club_directory_listing_and_authorization(client, db):
    """
    FEATURE 1 Test:
    - Administrator can view /admin/clubs with registered member counts.
    - Non-administrators (Treasurer, Event Organizer, Volunteer, Member) are denied.
    """
    admin_id = create_user(db, 'admin_user', 'Administrator')
    treasurer_id = create_user(db, 'treasurer_user', 'Treasurer')
    organizer_id = create_user(db, 'organizer_user', 'Event Organizer')
    volunteer_id = create_user(db, 'volunteer_user', 'Volunteer')
    member_id = create_user(db, 'member_user', 'Member')

    # Non-admin access should be denied
    for non_admin in ['treasurer_user', 'organizer_user', 'volunteer_user', 'member_user']:
        login(client, non_admin)
        res = client.get('/admin/clubs')
        assert res.status_code == 302, f"Expected redirect for role {non_admin}"
        # Check redirected away from /admin/clubs
        assert '/admin/clubs' not in res.location

    # Admin access should succeed
    login(client, 'admin_user')
    res_admin = client.get('/admin/clubs')
    assert res_admin.status_code == 200
    assert b"Club Directory" in res_admin.data
    assert b"Robotics &amp; AI Club" in res_admin.data or b"Robotics & AI Club" in res_admin.data
    assert b"Coding &amp; Open Source Society" in res_admin.data or b"Coding & Open Source Society" in res_admin.data
    assert b"View Members" in res_admin.data


def test_club_attendee_filtering_and_separation(client, db):
    """
    FEATURE 1 Test:
    - Viewing /admin/clubs/<id>/members displays ONLY members registered in that club.
    - Search and status filtering work accurately.
    - Membership is based on actual club registration relationship, not global user role.
    """
    create_user(db, 'admin_user', 'Administrator')
    login(client, 'admin_user')

    # Query two distinct clubs
    c_robotics = db.execute("SELECT * FROM clubs WHERE code = 'ROBOTICS'").fetchone()
    c_cultural = db.execute("SELECT * FROM clubs WHERE code = 'CULTURAL'").fetchone()
    assert c_robotics is not None
    assert c_cultural is not None

    # Register member A in Robotics (Active)
    db.execute("""
        INSERT OR REPLACE INTO club_members (club_id, full_name, email, student_id, department, status, join_date)
        VALUES (?, 'Aarav Patel', 'aarav.patel@robotics.edu', '1NT23CS011', 'Computer Science', 'Active', '2026-01-15')
    """, (c_robotics['id'],))
    # Register member B in Cultural (Expired)
    db.execute("""
        INSERT OR REPLACE INTO club_members (club_id, full_name, email, student_id, department, status, join_date)
        VALUES (?, 'Diya Sen', 'diya.sen@cultural.edu', '1NT22EC088', 'Electronics', 'Expired', '2025-05-10')
    """, (c_cultural['id'],))
    db.commit()

    # 1. View Robotics attendees
    res_rob = client.get(f"/admin/clubs/{c_robotics['id']}/members")
    assert res_rob.status_code == 200
    assert b"Aarav Patel" in res_rob.data
    assert b"aarav.patel@robotics.edu" in res_rob.data
    # Diya Sen must NOT appear in Robotics
    assert b"Diya Sen" not in res_rob.data

    # 2. View Cultural attendees
    res_cult = client.get(f"/admin/clubs/{c_cultural['id']}/members")
    assert res_cult.status_code == 200
    assert b"Diya Sen" in res_cult.data
    assert b"diya.sen@cultural.edu" in res_cult.data
    # Aarav Patel must NOT appear in Cultural
    assert b"Aarav Patel" not in res_cult.data

    # 3. Status filter in Cultural: Active should return empty state for Diya Sen
    res_cult_active = client.get(f"/admin/clubs/{c_cultural['id']}/members?status=Active")
    assert res_cult_active.status_code == 200
    assert b"Diya Sen" not in res_cult_active.data

    # Status filter: Expired should display Diya Sen
    res_cult_expired = client.get(f"/admin/clubs/{c_cultural['id']}/members?status=Expired")
    assert res_cult_expired.status_code == 200
    assert b"Diya Sen" in res_cult_expired.data

    # 4. Search filter in Robotics
    res_search = client.get(f"/admin/clubs/{c_robotics['id']}/members?search=Aarav")
    assert res_search.status_code == 200
    assert b"Aarav Patel" in res_search.data

    res_search_none = client.get(f"/admin/clubs/{c_robotics['id']}/members?search=NonExistentStudent")
    assert res_search_none.status_code == 200
    assert b"No matching attendees found" in res_search_none.data


def test_admin_club_register_member_and_duplicate_prevention(client, db):
    """
    FEATURE 1 Test:
    - Admin can register an attendee into a club.
    - Prevents duplicate registration within the same club.
    - Allows the same student to register in multiple distinct clubs.
    """
    create_user(db, 'admin_user', 'Administrator')
    login(client, 'admin_user')

    c_robotics = db.execute("SELECT * FROM clubs WHERE code = 'ROBOTICS'").fetchone()
    c_devsoc = db.execute("SELECT * FROM clubs WHERE code = 'DEV-SOC'").fetchone()

    # 1. Register student in Robotics
    res_reg1 = client.post(f"/admin/clubs/{c_robotics['id']}/register-member", data={
        'full_name': 'Neha Kapoor',
        'email': 'neha.kapoor@example.edu',
        'student_id': '1NT23IS055',
        'department': 'Information Science',
        'status': 'Active',
        'join_date': '2026-02-01'
    }, follow_redirects=True)

    assert res_reg1.status_code == 200
    assert b"successfully registered with" in res_reg1.data
    assert b"Neha Kapoor" in res_reg1.data

    # 2. Duplicate registration in Robotics should be prevented
    res_dup = client.post(f"/admin/clubs/{c_robotics['id']}/register-member", data={
        'full_name': 'Neha Duplicate',
        'email': 'neha.kapoor@example.edu',
        'status': 'Active'
    }, follow_redirects=True)

    assert b"already registered" in res_dup.data

    # 3. Same student CAN register in a different club (DEV-SOC)
    res_reg2 = client.post(f"/admin/clubs/{c_devsoc['id']}/register-member", data={
        'full_name': 'Neha Kapoor',
        'email': 'neha.kapoor@example.edu',
        'student_id': '1NT23IS055',
        'department': 'Information Science',
        'status': 'Active'
    }, follow_redirects=True)

    assert res_reg2.status_code == 200
    assert b"successfully registered with" in res_reg2.data

    # Verify database has 2 distinct club registrations for Neha
    count_neha = db.execute("SELECT COUNT(*) AS c FROM club_members WHERE email = 'neha.kapoor@example.edu'").fetchone()['c']
    assert count_neha == 2


def test_club_specific_announcement_email_dispatch_and_isolation(client, db):
    """
    FEATURE 2 Test:
    - Announcement with club_id dispatches emails ONLY to eligible active members of that club.
    - Members of unrelated clubs do NOT receive emails.
    - Clear result counts displayed (eligible, sent, failed, skipped).
    """
    create_user(db, 'admin_user', 'Administrator')
    login(client, 'admin_user')

    c_robotics = db.execute("SELECT * FROM clubs WHERE code = 'ROBOTICS'").fetchone()
    c_cultural = db.execute("SELECT * FROM clubs WHERE code = 'CULTURAL'").fetchone()

    # Clear test club members to create clean controlled test set
    db.execute("DELETE FROM club_members WHERE club_id IN (?, ?)", (c_robotics['id'], c_cultural['id']))

    # Robotics active members (2)
    db.execute("""
        INSERT INTO club_members (club_id, full_name, email, status)
        VALUES (?, 'Robotics Student 1', 'rob1@example.edu', 'Active'),
               (?, 'Robotics Student 2', 'rob2@example.edu', 'Active')
    """, (c_robotics['id'], c_robotics['id']))

    # Cultural active member (1)
    db.execute("""
        INSERT INTO club_members (club_id, full_name, email, status)
        VALUES (?, 'Cultural Student 1', 'cult1@example.edu', 'Active')
    """, (c_cultural['id'],))
    db.commit()

    # Post announcement targeting Robotics club
    res = client.post('/announcements/new', data={
        'title': 'Autonomous Navigation Workshop',
        'content': 'Workshop starts at 10 AM on Saturday in the Innovation Lab.',
        'audience': 'All',
        'priority': 'Important',
        'club_id': str(c_robotics['id']),
        'send_email': '1'
    }, follow_redirects=True)

    assert res.status_code == 200
    assert b"Autonomous Navigation Workshop" in res.data
    # Verify result flash message
    assert b"2 emails sent successfully" in res.data or b"2 eligible" in res.data

    # Verify announcement in database has email audit details
    ann = db.execute("SELECT * FROM announcements WHERE title = 'Autonomous Navigation Workshop'").fetchone()
    assert ann is not None
    assert ann['club_id'] == c_robotics['id']
    assert ann['email_sent_count'] == 2
    assert ann['email_status'] == 'Delivered'
    assert 'Eligible: 2' in ann['email_summary']


def test_recipient_deduplication_and_ineligible_skipping(client, db):
    """
    FEATURE 2 Test:
    - Deduplicates recipients if the same email appears multiple times.
    - Skips members with status != 'Active' (Expired, Pending).
    - Skips members with invalid or missing emails.
    """
    create_user(db, 'admin', 'Administrator')
    create_user(db, 'organizer_user', 'Event Organizer')
    login(client, 'organizer_user')

    c_devsoc = db.execute("SELECT * FROM clubs WHERE code = 'DEV-SOC'").fetchone()
    db.execute("DELETE FROM club_members WHERE club_id = ?", (c_devsoc['id'],))

    # Add 1 active valid member
    db.execute("INSERT INTO club_members (club_id, full_name, email, status) VALUES (?, 'Valid Active', 'valid@example.edu', 'Active')", (c_devsoc['id'],))
    # Add duplicate email with different casing/name
    db.execute("INSERT INTO club_members (club_id, full_name, email, status) VALUES (?, 'Valid Duplicate', 'VALID@EXAMPLE.EDU', 'Active')", (c_devsoc['id'],))
    # Add expired member
    db.execute("INSERT INTO club_members (club_id, full_name, email, status) VALUES (?, 'Expired Student', 'expired@example.edu', 'Expired')", (c_devsoc['id'],))
    # Add pending member
    db.execute("INSERT INTO club_members (club_id, full_name, email, status) VALUES (?, 'Pending Student', 'pending@example.edu', 'Pending')", (c_devsoc['id'],))
    # Add member with invalid email
    db.execute("INSERT INTO club_members (club_id, full_name, email, status) VALUES (?, 'Bad Email', 'not-an-email', 'Active')", (c_devsoc['id'],))
    db.commit()

    res = client.post('/announcements/new', data={
        'title': 'Git & Open Source Sprint',
        'content': 'Join us to contribute to open source repositories.',
        'audience': 'All',
        'priority': 'Normal',
        'club_id': str(c_devsoc['id']),
        'send_email': '1'
    }, follow_redirects=True)

    assert res.status_code == 200
    # Exactly 1 email should be sent (the unique valid active recipient)
    # The duplicate, expired, pending, and invalid email must all be skipped
    assert b"1 emails sent successfully" in res.data or b"1 eligible" in res.data

    ann = db.execute("SELECT * FROM announcements WHERE title = 'Git & Open Source Sprint'").fetchone()
    assert ann is not None
    assert ann['email_sent_count'] == 1


def test_empty_club_recipient_list_handling(client, db):
    """
    FEATURE 2 Test:
    - When club has zero members or zero eligible members, sending handles cleanly.
    - 0 sent, 0 failed, informative feedback shown.
    """
    create_user(db, 'admin_user', 'Administrator')
    login(client, 'admin_user')

    # Create empty test club
    db.execute("INSERT INTO clubs (name, code, description) VALUES ('Empty Test Club', 'EMPTY-CLUB', 'No members yet')")
    db.commit()
    c_empty = db.execute("SELECT * FROM clubs WHERE code = 'EMPTY-CLUB'").fetchone()

    res = client.post('/announcements/new', data={
        'title': 'Welcome to Empty Club',
        'content': 'First announcement for empty club.',
        'audience': 'All',
        'priority': 'Normal',
        'club_id': str(c_empty['id']),
        'send_email': '1'
    }, follow_redirects=True)

    assert res.status_code == 200
    assert b"No eligible active members found" in res.data

    ann = db.execute("SELECT * FROM announcements WHERE title = 'Welcome to Empty Club'").fetchone()
    assert ann is not None
    assert ann['email_sent_count'] == 0


def test_partial_smtp_delivery_failure_handling(client, db, monkeypatch):
    """
    FEATURE 2 Test:
    - When an SMTP delivery failure occurs for one recipient, the remaining recipients still receive their email.
    - Sent count and failed count are recorded accurately.
    """
    create_user(db, 'admin_user', 'Administrator')
    login(client, 'admin_user')

    c_robotics = db.execute("SELECT * FROM clubs WHERE code = 'ROBOTICS'").fetchone()
    db.execute("DELETE FROM club_members WHERE club_id = ?", (c_robotics['id'],))

    # Add 2 active members
    db.execute("""
        INSERT INTO club_members (club_id, full_name, email, status)
        VALUES (?, 'Success Student', 'success@example.edu', 'Active'),
               (?, 'Failing Student', 'fail@example.edu', 'Active')
    """, (c_robotics['id'], c_robotics['id']))
    db.commit()

    # Configure simulated failure for fail@example.edu
    monkeypatch.setattr(email_service, 'TEST_SMTP_FAIL_EMAILS', {'fail@example.edu'})

    res = client.post('/announcements/new', data={
        'title': 'Hardware Kit Distribution',
        'content': 'Kits ready for pickup.',
        'audience': 'All',
        'priority': 'Urgent',
        'club_id': str(c_robotics['id']),
        'send_email': '1'
    }, follow_redirects=True)

    assert res.status_code == 200
    # Should report partial delivery: 1 sent, 1 failed
    assert b"partial email delivery" in res.data or (b"1 sent" in res.data and b"1 failed" in res.data)

    ann = db.execute("SELECT * FROM announcements WHERE title = 'Hardware Kit Distribution'").fetchone()
    assert ann is not None
    assert ann['email_sent_count'] == 1
    assert ann['email_status'] == 'Partial'


def test_announcement_duplicate_submission_prevention(client, db):
    """
    FEATURE 2 Test:
    - Repeated submission with the same idempotency token is rejected as a duplicate.
    """
    create_user(db, 'admin_user', 'Administrator')
    login(client, 'admin_user')

    token = "test-token-unique-12345"
    res1 = client.post('/announcements/new', data={
        'form_token': token,
        'title': 'Unique Notice',
        'content': 'First submission of this notice.',
        'audience': 'All',
        'priority': 'Normal'
    }, follow_redirects=True)
    assert res1.status_code == 200
    assert b"published successfully" in res1.data

    # Immediate second submission with the SAME token
    res2 = client.post('/announcements/new', data={
        'form_token': token,
        'title': 'Unique Notice',
        'content': 'First submission of this notice.',
        'audience': 'All',
        'priority': 'Normal'
    }, follow_redirects=True)
    assert res2.status_code == 200
    assert b"Duplicate submission detected" in res2.data
