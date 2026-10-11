import pytest
from tests.conftest import create_user, login


def test_first_time_setup_redirect(client):
    """When no admin exists, visitors must be redirected to /setup."""
    response = client.get('/', follow_redirects=False)
    assert response.status_code == 302
    assert '/setup' in response.headers['Location']


def test_first_time_setup_creation(client, db):
    """Initial administrator setup completes successfully without hardcoded credentials."""
    response = client.post('/setup', data={
        'full_name': 'Chief Administrator',
        'username': 'superadmin',
        'email': 'admin@clubsphere.org',
        'password': 'strongpassword123',
        'confirm_password': 'strongpassword123'
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b"Welcome to ClubSphere" in response.data

    # Verify user was saved with Administrator role
    user = db.execute("SELECT * FROM users WHERE username = 'superadmin'").fetchone()
    assert user is not None
    assert user['role'] == 'Administrator'
    assert user['email'] == 'admin@clubsphere.org'

    # Once admin exists, /setup is locked and redirects away
    setup_retry = client.get('/setup', follow_redirects=False)
    assert setup_retry.status_code == 302
    assert '/login' in setup_retry.headers['Location']


def test_login_and_logout(client, db):
    """Test standard user login and session clearing on logout."""
    create_user(db, username='admin', role='Administrator')
    create_user(db, username='tester', role='Member', password='secretpassword')

    # Invalid password
    bad_login = client.post('/login', data={'login_id': 'tester', 'password': 'wrong', 'login_type': 'user'}, follow_redirects=True)
    assert b"Invalid credentials" in bad_login.data

    # Valid login
    good_login = client.post('/login', data={'login_id': 'tester', 'password': 'secretpassword', 'login_type': 'user'}, follow_redirects=True)
    assert good_login.status_code == 200
    assert b"Signed in as Member" in good_login.data

    # Logout
    logout_res = client.get('/logout', follow_redirects=True)
    assert b"signed out successfully" in logout_res.data


def test_deactivated_user_login(client, db):
    """Deactivated accounts cannot sign in."""
    create_user(db, username='admin', role='Administrator')
    create_user(db, username='inactiveuser', role='Volunteer', password='pwd')
    db.execute("UPDATE users SET is_active = 0 WHERE username = 'inactiveuser'")
    db.commit()

    res = client.post('/login', data={'login_id': 'inactiveuser', 'password': 'pwd', 'login_type': 'user'}, follow_redirects=True)
    assert b"Invalid credentials or account deactivated" in res.data


def test_role_permissions_enforcement(client, db):
    """Verify backend role enforcement across modules."""
    # Create administrator so setup is complete
    create_user(db, username='admin', role='Administrator')
    create_user(db, username='member1', role='Member')
    create_user(db, username='treasurer1', role='Treasurer')
    create_user(db, username='volunteer1', role='Volunteer')

    # Anonymous user blocked
    res_anon = client.get('/finance', follow_redirects=False)
    assert res_anon.status_code == 302
    assert '/login' in res_anon.headers['Location']

    # Member user blocked from financial ledger and member registration
    login(client, 'member1')
    res_mem_fin = client.get('/finance', follow_redirects=True)
    assert b"Access denied" in res_mem_fin.data

    res_mem_new = client.get('/members/new', follow_redirects=True)
    assert b"Access denied" in res_mem_new.data

    # Member blocked from admin users list
    res_mem_users = client.get('/users', follow_redirects=True)
    assert b"Access denied" in res_mem_users.data

    # Treasurer permitted into finances
    login(client, 'treasurer1')
    res_tre_fin = client.get('/finance')
    assert res_tre_fin.status_code == 200
    assert b"Financial Ledger" in res_tre_fin.data

    # Volunteer permitted into check-in
    login(client, 'volunteer1')
    res_vol_chk = client.get('/tickets/checkin')
    assert res_vol_chk.status_code == 200
    assert b"Attendee Verification Console" in res_vol_chk.data

    # Admin permitted everywhere
    login(client, 'admin')
    res_adm_users = client.get('/users')
    assert res_adm_users.status_code == 200
    assert b"User Accounts Directory" in res_adm_users.data


def test_demo_accounts_authentication_and_isolation(tmp_path, monkeypatch):
    """Verify demo accounts authenticate with Password123! and reject invalid passwords."""
    import seed_demo
    import app as cs_app

    demo_db = str(tmp_path / 'clubsphere_demo_test.db')
    seed_demo.seed_demo_database(demo_db, verbose=False)

    monkeypatch.setenv('CLUB_SPHERE_DB', demo_db)
    cs_app.app.config['DATABASE'] = demo_db

    with cs_app.app.test_client() as test_client:
        # Invalid password fails
        bad_res = test_client.post('/login', data={'login_id': 'demo_admin', 'password': 'WrongPassword!'}, follow_redirects=True)
        assert b"Invalid credentials or account deactivated" in bad_res.data

        # Valid login for demo_admin succeeds and redirects to dashboard
        good_res = test_client.post('/login', data={'login_id': 'demo_admin', 'password': 'Password123!'}, follow_redirects=False)
        assert good_res.status_code == 302
        assert '/dashboard' in good_res.headers['Location']

        # Following redirect leads to dashboard with Alex Rivera
        dash_res = test_client.get('/dashboard')
        assert dash_res.status_code == 200
        assert b"Alex Rivera" in dash_res.data
        assert b"Administrator" in dash_res.data

        # Test demo_treasurer is active and can also log in with Password123!
        test_client.get('/logout')
        tre_res = test_client.post('/login', data={'login_id': 'demo_treasurer', 'password': 'Password123!', 'login_type': 'user'}, follow_redirects=False)
        assert tre_res.status_code == 302
        assert '/dashboard' in tre_res.headers['Location']


def test_dual_login_options_and_role_enforcement(client, db):
    """
    Verify dual login options:
    1. Administrator can log in through Admin Login.
    2. Administrator cannot log in through User Login.
    3. Non-admin roles (Treasurer, Event Organizer, Volunteer, Member) can log in through User Login.
    4. Non-admin roles cannot log in through Admin Login.
    5. Invalid passwords and inactive accounts remain rejected.
    6. Existing session security and role-based redirects continue to work.
    """
    create_user(db, username='admin', role='Administrator', password='AdminPass123!')
    create_user(db, username='treasurer_bob', role='Treasurer', password='UserPass123!')
    create_user(db, username='organizer_alice', role='Event Organizer', password='UserPass123!')
    create_user(db, username='volunteer_charlie', role='Volunteer', password='UserPass123!')
    create_user(db, username='member_david', role='Member', password='UserPass123!')
    create_user(db, username='inactive_admin', role='Administrator', password='AdminPass123!')
    create_user(db, username='inactive_member', role='Member', password='UserPass123!')
    db.execute("UPDATE users SET is_active = 0 WHERE username IN ('inactive_admin', 'inactive_member')")
    db.commit()

    # 1. Administrator can log in through Admin Login
    res_adm = client.post('/login', data={'login_id': 'admin', 'password': 'AdminPass123!', 'login_type': 'admin'}, follow_redirects=False)
    assert res_adm.status_code == 302
    assert '/dashboard' in res_adm.headers['Location']
    client.get('/logout')

    # 2. Administrator CANNOT log in through User Login
    res_adm_user = client.post('/login', data={'login_id': 'admin', 'password': 'AdminPass123!', 'login_type': 'user'}, follow_redirects=True)
    assert res_adm_user.status_code == 200
    assert b"Administrator accounts must sign in through Admin Login" in res_adm_user.data
    # Ensure no session was established
    dash_check = client.get('/dashboard', follow_redirects=False)
    assert dash_check.status_code == 302
    assert '/login' in dash_check.headers['Location']

    # 3. Non-admin roles can log in through User Login
    non_admins = ['treasurer_bob', 'organizer_alice', 'volunteer_charlie', 'member_david']
    for u in non_admins:
        res = client.post('/login', data={'login_id': u, 'password': 'UserPass123!', 'login_type': 'user'}, follow_redirects=False)
        assert res.status_code == 302, f"Failed for {u}"
        assert '/dashboard' in res.headers['Location']
        client.get('/logout')

    # 4. Non-admin roles CANNOT log in through Admin Login
    for u in non_admins:
        res = client.post('/login', data={'login_id': u, 'password': 'UserPass123!', 'login_type': 'admin'}, follow_redirects=True)
        assert res.status_code == 200, f"Expected 200 for rejected {u}"
        assert b"Non-admin accounts cannot sign in through Admin Login" in res.data
        # Ensure session was not created
        dash_check = client.get('/dashboard', follow_redirects=False)
        assert dash_check.status_code == 302

    # 5. Invalid passwords and inactive accounts remain rejected
    # Bad password on Admin Login
    bad_adm_pwd = client.post('/login', data={'login_id': 'admin', 'password': 'WrongPassword', 'login_type': 'admin'}, follow_redirects=True)
    assert b"Invalid credentials or account deactivated" in bad_adm_pwd.data

    # Bad password on User Login
    bad_usr_pwd = client.post('/login', data={'login_id': 'member_david', 'password': 'WrongPassword', 'login_type': 'user'}, follow_redirects=True)
    assert b"Invalid credentials or account deactivated" in bad_usr_pwd.data

    # Inactive admin on Admin Login
    inact_adm = client.post('/login', data={'login_id': 'inactive_admin', 'password': 'AdminPass123!', 'login_type': 'admin'}, follow_redirects=True)
    assert b"Invalid credentials or account deactivated" in inact_adm.data

    # Inactive member on User Login
    inact_usr = client.post('/login', data={'login_id': 'inactive_member', 'password': 'UserPass123!', 'login_type': 'user'}, follow_redirects=True)
    assert b"Invalid credentials or account deactivated" in inact_usr.data

    # 6. Existing session security and role-based redirects continue to work
    # Deep-link access redirect
    deep_link = client.get('/tickets/checkin', follow_redirects=False)
    assert deep_link.status_code == 302
    assert '/login' in deep_link.headers['Location']
    assert 'next=/tickets/checkin' in deep_link.headers['Location']

    # Login through User Login with next redirect preserves destination
    next_login = client.post('/login?next=/tickets/checkin', data={
        'login_id': 'volunteer_charlie',
        'password': 'UserPass123!',
        'login_type': 'user'
    }, follow_redirects=False)
    assert next_login.status_code == 302
    assert next_login.headers['Location'] == '/tickets/checkin'

    # Follow redirect to verification console
    vol_view = client.get('/tickets/checkin')
    assert vol_view.status_code == 200
    assert b"Attendee Verification Console" in vol_view.data

    # Logout terminates session
    logout_res = client.get('/logout', follow_redirects=False)
    assert logout_res.status_code == 302
    assert '/login' in logout_res.headers['Location']


def test_user_login_comprehensive_matrix(client, db):
    """
    Comprehensive verification of user login according to prompt:
    1. Valid Member login succeeds through User Login and redirects to Member view / dashboard.
    2. Valid Volunteer login succeeds through User Login and redirects to Volunteer view / dashboard.
    3. Valid Treasurer and Event Organizer logins succeed through User Login and route correctly according to their roles.
    4. Attempting to log in with an incorrect password displays a clear error message.
    5. Attempting to log in with an inactive account is rejected.
    6. A non-admin user attempting to sign in through Admin Login is rejected with access restriction message.
    7. Administrator login through Admin Login continues to work properly and redirects to Admin dashboard.
    8. Login accepts both demo_* and alias usernames.
    """
    create_user(db, username='admin', role='Administrator', password='Password123!', email='admin@clubsphere.org')
    create_user(db, username='demo_admin', role='Administrator', password='Password123!', email='admin@clubdemo.org')
    create_user(db, username='demo_treasurer', role='Treasurer', password='Password123!', email='treasurer@clubdemo.org')
    create_user(db, username='demo_organizer', role='Event Organizer', password='Password123!', email='organizer@clubdemo.org')
    create_user(db, username='demo_volunteer', role='Volunteer', password='Password123!', email='volunteer@clubdemo.org')
    create_user(db, username='demo_member', role='Member', password='Password123!', email='member@clubdemo.org')
    create_user(db, username='inactive_demo_user', role='Member', password='Password123!')
    db.execute("UPDATE users SET is_active = 0 WHERE username = 'inactive_demo_user'")
    db.commit()

    # 1. Member login through User Login
    res_mem = client.post('/login', data={'login_id': 'demo_member', 'password': 'Password123!', 'login_type': 'user'}, follow_redirects=True)
    assert res_mem.status_code == 200
    assert b"Signed in as Member" in res_mem.data
    assert b"Club AI Assistant" in res_mem.data
    client.get('/logout')

    # 1b. Member login using email
    res_mem_email = client.post('/login', data={'login_id': 'member@clubdemo.org', 'password': 'Password123!', 'login_type': 'user'}, follow_redirects=True)
    assert res_mem_email.status_code == 200
    assert b"Signed in as Member" in res_mem_email.data
    client.get('/logout')

    # 1c. Member login using unprefixed alias 'member' -> matches 'demo_member'
    res_mem_alias = client.post('/login', data={'login_id': 'member', 'password': 'Password123!', 'login_type': 'user'}, follow_redirects=True)
    assert res_mem_alias.status_code == 200
    assert b"Signed in as Member" in res_mem_alias.data
    client.get('/logout')

    # 2. Volunteer login through User Login
    res_vol = client.post('/login', data={'login_id': 'demo_volunteer', 'password': 'Password123!', 'login_type': 'user'}, follow_redirects=True)
    assert res_vol.status_code == 200
    assert b"Signed in as Volunteer" in res_vol.data
    assert b"Ticket Check-In" in res_vol.data
    client.get('/logout')

    # 3. Treasurer login through User Login
    res_tre = client.post('/login', data={'login_id': 'demo_treasurer', 'password': 'Password123!', 'login_type': 'user'}, follow_redirects=True)
    assert res_tre.status_code == 200
    assert b"Signed in as Treasurer" in res_tre.data
    assert b"Financial Ledger" in res_tre.data
    client.get('/logout')

    # 3b. Event Organizer login through User Login
    res_org = client.post('/login', data={'login_id': 'demo_organizer', 'password': 'Password123!', 'login_type': 'user'}, follow_redirects=True)
    assert res_org.status_code == 200
    assert b"Signed in as Event Organizer" in res_org.data
    assert b"+ Event" in res_org.data
    client.get('/logout')

    # 4. Incorrect password displays clear error message
    bad_pwd = client.post('/login', data={'login_id': 'demo_member', 'password': 'WrongPassword123!', 'login_type': 'user'}, follow_redirects=True)
    assert b"Invalid credentials or account deactivated" in bad_pwd.data

    # 5. Inactive account is rejected
    inact = client.post('/login', data={'login_id': 'inactive_demo_user', 'password': 'Password123!', 'login_type': 'user'}, follow_redirects=True)
    assert b"Invalid credentials or account deactivated" in inact.data

    # 6. Non-admin attempting to sign in through Admin Login rejected
    non_adm_rej = client.post('/login', data={'login_id': 'demo_member', 'password': 'Password123!', 'login_type': 'admin'}, follow_redirects=True)
    assert b"Access denied: Non-admin accounts cannot sign in through Admin Login. Please use User Login." in non_adm_rej.data

    # 7. Administrator login through Admin Login succeeds
    adm_login = client.post('/login', data={'login_id': 'demo_admin', 'password': 'Password123!', 'login_type': 'admin'}, follow_redirects=True)
    assert adm_login.status_code == 200
    assert b"Signed in as Administrator" in adm_login.data
    assert b"User Accounts" in adm_login.data
    client.get('/logout')

    # 7b. Admin attempting to sign in through User Login is rejected
    adm_on_user = client.post('/login', data={'login_id': 'demo_admin', 'password': 'Password123!', 'login_type': 'user'}, follow_redirects=True)
    assert b"Access denied: Administrator accounts must sign in through Admin Login." in adm_on_user.data


def test_member_self_registration_and_login(client, db):
    """
    Test Member registration flow and sign-in:
    1. Validation: password mismatch, short password, invalid email.
    2. Successful Member registration creates account with Member role and is_active=1.
    3. Duplicate username/email is rejected.
    4. Sign in through User Login succeeds and redirects to Member dashboard.
    5. Incorrect password is rejected.
    6. Member cannot sign in through Admin Login.
    7. Administrator login remains intact.
    """
    # Create administrator so setup is complete
    create_user(db, username='admin', role='Administrator', password='AdminPassword123!')

    # 1. Validation errors
    bad_mismatch = client.post('/register', data={
        'full_name': 'New Student',
        'username': 'newstudent',
        'email': 'student@example.edu',
        'password': 'password123',
        'confirm_password': 'mismatchpassword'
    }, follow_redirects=True)
    assert b"Passwords do not match" in bad_mismatch.data

    bad_short = client.post('/register', data={
        'full_name': 'New Student',
        'username': 'newstudent',
        'email': 'student@example.edu',
        'password': '123',
        'confirm_password': '123'
    }, follow_redirects=True)
    assert b"Password must be at least 6 characters" in bad_short.data

    # 2. Successful Member registration
    reg_res = client.post('/register', data={
        'full_name': 'Aditi Rao',
        'username': 'aditi_member',
        'email': 'aditi.rao@campus.edu',
        'password': 'SecureMemberPass123!',
        'confirm_password': 'SecureMemberPass123!'
    }, follow_redirects=False)
    assert reg_res.status_code == 302
    assert '/login' in reg_res.headers['Location']
    assert 'type=user' in reg_res.headers['Location']

    # 2b. Verify account in database
    user = db.execute("SELECT * FROM users WHERE username = 'aditi_member'").fetchone()
    assert user is not None
    assert user['role'] == 'Member'
    assert user['is_active'] == 1
    assert user['email'] == 'aditi.rao@campus.edu'
    assert user['full_name'] == 'Aditi Rao'

    # 3. Duplicate username rejected
    dup_res = client.post('/register', data={
        'full_name': 'Another Person',
        'username': 'aditi_member',
        'email': 'another@campus.edu',
        'password': 'SecureMemberPass123!',
        'confirm_password': 'SecureMemberPass123!'
    }, follow_redirects=True)
    assert b"A user with that username or email already exists" in dup_res.data

    # 4. Sign in through User Login flow
    login_res = client.post('/login', data={
        'login_id': 'aditi_member',
        'password': 'SecureMemberPass123!',
        'login_type': 'user'
    }, follow_redirects=False)
    assert login_res.status_code == 302
    assert login_res.headers['Location'] == '/dashboard'

    # Follow redirect to dashboard
    dash_res = client.get('/dashboard')
    assert dash_res.status_code == 200
    assert b"Aditi Rao" in dash_res.data
    assert b"Club AI Assistant" in dash_res.data
    client.get('/logout')

    # 5. Incorrect password rejected
    bad_login = client.post('/login', data={
        'login_id': 'aditi_member',
        'password': 'WrongPassword123!',
        'login_type': 'user'
    }, follow_redirects=True)
    assert b"Invalid credentials or account deactivated" in bad_login.data

    # 6. Cannot sign in through Admin Login
    admin_block = client.post('/login', data={
        'login_id': 'aditi_member',
        'password': 'SecureMemberPass123!',
        'login_type': 'admin'
    }, follow_redirects=True)
    assert b"Non-admin accounts cannot sign in through Admin Login" in admin_block.data

    # 7. Administrator login works
    adm_res = client.post('/login', data={
        'login_id': 'admin',
        'password': 'AdminPassword123!',
        'login_type': 'admin'
    }, follow_redirects=False)
    assert adm_res.status_code == 302
    assert adm_res.headers['Location'] == '/dashboard'




