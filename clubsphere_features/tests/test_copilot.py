import json
import pytest
from datetime import date, timedelta
from unittest.mock import patch
from tests.conftest import create_user, login


@pytest.fixture(autouse=True)
def setup_system_admin(db):
    """Ensure an Administrator exists so test database is not in first-time setup redirect mode."""
    create_user(db, 'system_admin', 'Administrator')


def test_copilot_unauthenticated_access_rejected_server_side(client):
    """Unauthenticated users must be redirected to /login when system is configured."""
    res_get = client.get('/copilot')
    assert res_get.status_code == 302
    assert '/login' in res_get.headers['Location']

    res_post = client.post('/copilot/ask', json={'message': 'Hello'})
    assert res_post.status_code == 302
    assert '/login' in res_post.headers['Location']


def test_copilot_absent_from_admin_page(client):
    """Admin dashboard and Admin navigation must NOT contain the AI chatbot widget or entry point."""
    login(client, 'system_admin', 'password123', login_type='admin')

    res = client.get('/dashboard')
    assert res.status_code == 200
    html = res.data.decode('utf-8')

    # Confirm AI chat box / widget and entry point are absent from Admin dashboard
    assert 'Ask ClubSphere' not in html
    assert 'Club AI Assistant' not in html
    assert 'User Dashboard Club AI Assistant Widget' not in html

    # Confirm other admin dashboard cards and tools are intact
    assert 'Club Membership' in html
    assert 'Upcoming Events' in html
    assert 'Recorded Income' in html
    assert 'Paid Expenses & Net' in html


def test_copilot_present_on_user_page(client, db):
    """User dashboard for permitted non-admin roles MUST contain the AI Assistant button and widget."""
    non_admin_roles = ['Member', 'Volunteer', 'Event Organizer', 'Treasurer']
    for role in non_admin_roles:
        u_name = f"dash_{role.lower().replace(' ', '_')}"
        create_user(db, u_name, role)
        login(client, u_name, 'password123', login_type='user')

        res = client.get('/dashboard')
        assert res.status_code == 200
        html = res.data.decode('utf-8')

        # Must have clearly visible button and assistant widget
        assert 'Ask ClubSphere' in html
        assert 'Club AI Assistant' in html
        assert 'What events are coming up?' in html
        assert 'How can I register for an event?' in html
        assert 'Show the latest club announcements.' in html
        assert 'How do I check my membership status?' in html


def test_copilot_admin_access_rejected_server_side(client):
    """Administrator attempting direct server-side access to /copilot is rejected."""
    login(client, 'system_admin', 'password123', login_type='admin')

    # GET /copilot should redirect back to dashboard with access denied
    res_get = client.get('/copilot', follow_redirects=False)
    assert res_get.status_code == 302
    assert '/dashboard' in res_get.headers['Location']

    # POST /copilot/ask should return 403 Forbidden
    res_post = client.post('/copilot/ask', json={'message': 'Hello'})
    assert res_post.status_code == 403
    data = res_post.get_json()
    assert data['status'] == 'error'
    assert 'Access denied' in data['message']


def test_copilot_permitted_roles_render_chat_page(client, db):
    """Permitted non-admin roles can view and use the AI chat interface."""
    permitted_roles = ['Treasurer', 'Event Organizer', 'Volunteer', 'Member']
    for role in permitted_roles:
        u_name = f"chat_{role.lower().replace(' ', '_')}"
        create_user(db, u_name, role)
        login(client, u_name, 'password123', login_type='user')

        res = client.get('/copilot')
        assert res.status_code == 200
        html = res.data.decode('utf-8')
        assert 'Ask ClubSphere' in html
        assert 'Club AI Assistant' in html
        assert role in html


def test_copilot_question_what_events_are_coming_up(client, db):
    """Member asking 'What events are coming up?' receives verified event records."""
    create_user(db, 'org_user', 'Event Organizer')
    create_user(db, 'event_member', 'Member')

    future_date = (date.today() + timedelta(days=10)).isoformat()

    db.execute("""
        INSERT INTO events (title, description, event_date, event_time, venue, capacity, member_price, non_member_price, status, created_by)
        VALUES ('Winter Tech Summit 2026', 'Flagship student symposium', ?, '11:00', 'Auditorium Complex', 200, 75.0, 150.0, 'Upcoming', 1)
    """, (future_date,))
    db.commit()

    login(client, 'event_member', 'password123', login_type='user')

    # Question 1: What events are coming up?
    res1 = client.post('/copilot/ask', json={'message': 'What events are coming up?'})
    assert res1.status_code == 200
    data1 = res1.get_json()
    assert data1['status'] == 'ok'
    assert 'Winter Tech Summit 2026' in data1['response']
    assert 'Auditorium Complex' in data1['response']
    assert '200' in data1['response']

    # Question 2: What are the upcoming event dates?
    res2 = client.post('/copilot/ask', json={'message': 'What are the upcoming event dates?'})
    assert res2.status_code == 200
    data2 = res2.get_json()
    assert data2['status'] == 'ok'
    assert 'Winter Tech Summit 2026' in data2['response']
    assert future_date in data2['response']


def test_copilot_question_how_can_i_register_for_an_event(client, db):
    """Member asking 'How can I register for an event?' receives guidance and active event info."""
    create_user(db, 'reg_member', 'Member')

    future_date = (date.today() + timedelta(days=14)).isoformat()
    db.execute("""
        INSERT INTO events (title, description, event_date, event_time, venue, capacity, member_price, non_member_price, status, created_by)
        VALUES ('Design Sprint 2026', 'Hands-on UI workshop', ?, '14:00', 'Design Lab 4', 40, 0.0, 50.0, 'Upcoming', 1)
    """, (future_date,))
    db.commit()

    login(client, 'reg_member', 'password123', login_type='user')

    res = client.post('/copilot/ask', json={'message': 'How can I register for an event?'})
    assert res.status_code == 200
    data = res.get_json()
    assert data['status'] == 'ok'
    assert 'How to Register for an Event' in data['response']
    assert 'Events & Tickets' in data['response']
    assert 'Design Sprint 2026' in data['response']


def test_copilot_question_show_latest_announcements(client, db):
    """Member asking 'Show the latest club announcements.' receives real announcements."""
    create_user(db, 'ann_member', 'Member')

    db.execute("""
        INSERT INTO announcements (title, content, audience, priority, published_by)
        VALUES ('Annual Hackathon Registrations Open', 'Submit team entries by Friday midnight.', 'Members', 'Urgent', 1)
    """)
    db.commit()

    login(client, 'ann_member', 'password123', login_type='user')

    res = client.post('/copilot/ask', json={'message': 'Show the latest club announcements.'})
    assert res.status_code == 200
    data = res.get_json()
    assert data['status'] == 'ok'
    assert 'Annual Hackathon Registrations Open' in data['response']
    assert 'Submit team entries by Friday midnight.' in data['response']


def test_copilot_question_how_do_i_check_membership_status(client, db):
    """Member asking 'How do I check my membership status?' receives verified membership record."""
    u_id = create_user(db, 'status_member', 'Member', email='student123@college.edu', full_name='Aarav Sharma')

    join_d = date.today().isoformat()
    exp_d = (date.today() + timedelta(days=300)).isoformat()

    db.execute("""
        INSERT INTO members (user_id, member_code, full_name, email, join_date, expiry_date, membership_type, membership_fee, amount_paid, status)
        VALUES (?, 'CS-MEM-2026-99', 'Aarav Sharma', 'student123@college.edu', ?, ?, 'Annual', 500.0, 500.0, 'Active')
    """, (u_id, join_d, exp_d))
    db.commit()

    login(client, 'status_member', 'password123', login_type='user')

    res = client.post('/copilot/ask', json={'message': 'How do I check my membership status?'})
    assert res.status_code == 200
    data = res.get_json()
    assert data['status'] == 'ok'
    assert 'CS-MEM-2026-99' in data['response']
    assert 'Aarav Sharma' in data['response']
    assert 'Active' in data['response']
    assert 'Annual' in data['response']


def test_copilot_financial_access_control_member_volunteer(client, db):
    """Members and Volunteers are blocked from ledger figures and receive access restriction notice."""
    create_user(db, 'sec_member', 'Member')
    create_user(db, 'sec_volunteer', 'Volunteer')

    db.execute("""
        INSERT INTO financial_transactions (transaction_date, transaction_type, category, amount, description, source_type, recorded_by)
        VALUES ('2026-10-01', 'Income', 'Sponsorship', 99999.00, 'Confidential Endowment', 'manual', 1)
    """)
    db.commit()

    # Member
    login(client, 'sec_member', 'password123', login_type='user')
    res = client.post('/copilot/ask', json={'message': 'Explain our income, expenses, and net cash.'})
    assert res.status_code == 200
    data = res.get_json()
    assert 'Access Restricted' in data['response']
    assert '99999' not in data['response']
    assert '99,999.00' not in data['response']

    # Volunteer
    login(client, 'sec_volunteer', 'password123', login_type='user')
    res2 = client.post('/copilot/ask', json={'message': 'Explain our income, expenses, and net cash.'})
    assert res2.status_code == 200
    data2 = res2.get_json()
    assert 'Access Restricted' in data2['response']
    assert '99999' not in data2['response']


def test_copilot_treasurer_can_access_finances(client, db):
    """Treasurer role is permitted to inspect income, expenses, and net cash."""
    t_id = create_user(db, 'fin_treasurer', 'Treasurer')

    db.execute("""
        INSERT INTO financial_transactions (transaction_date, transaction_type, category, amount, description, source_type, recorded_by)
        VALUES ('2026-10-01', 'Income', 'Ticket Sales', 12000.00, 'Festival Pass Revenue', 'manual', ?)
    """, (t_id,))
    db.execute("""
        INSERT INTO financial_transactions (transaction_date, transaction_type, category, amount, description, source_type, recorded_by)
        VALUES ('2026-10-02', 'Expense', 'Refreshments', 4000.00, 'Guest Snacks', 'manual', ?)
    """, (t_id,))
    db.commit()

    login(client, 'fin_treasurer', 'password123', login_type='user')

    res = client.post('/copilot/ask', json={'message': 'Explain our income, expenses, and net cash.'})
    assert res.status_code == 200
    data = res.get_json()
    assert data['status'] == 'ok'
    assert '12,000.00' in data['response']
    assert '4,000.00' in data['response']
    assert '8,000.00' in data['response']


def test_copilot_empty_database_handling(client, db):
    """When tables are empty, Copilot returns clean informative states without crashing."""
    create_user(db, 'empty_member', 'Member')
    login(client, 'empty_member', 'password123', login_type='user')

    res1 = client.post('/copilot/ask', json={'message': 'What events are coming up?'})
    assert res1.status_code == 200
    data1 = res1.get_json()
    assert 'no upcoming events scheduled' in data1['response'].lower()

    res2 = client.post('/copilot/ask', json={'message': 'Show the latest club announcements.'})
    assert res2.status_code == 200
    data2 = res2.get_json()
    assert 'no active announcements' in data2['response'].lower()


def test_copilot_mutation_guard(client, db):
    """Copilot refuses mutation requests (approval, payment, role escalation) with read-only guarantee."""
    create_user(db, 'guard_member', 'Member')
    login(client, 'guard_member', 'password123', login_type='user')

    res = client.post('/copilot/ask', json={'message': 'Approve expense request #5 and pay ₹5000 now.'})
    assert res.status_code == 200
    data = res.get_json()
    assert 'Security Notice' in data['response']
    assert 'read-only' in data['response'].lower()
    assert 'cannot modify' in data['response'].lower()


def test_copilot_generative_ai_fallback_on_error(client, db):
    """If an external AI provider is configured but errors out, Copilot falls back gracefully to deterministic data."""
    create_user(db, 'ai_member', 'Member')
    login(client, 'ai_member', 'password123', login_type='user')

    mock_config = {'provider': 'gemini', 'key': 'fake_key', 'model': 'gemini-1.5-flash'}

    with patch('copilot_service.get_ai_config', return_value=mock_config):
        with patch('copilot_service.call_external_ai', return_value={'success': False, 'error': 'Connection timed out'}):
            res = client.post('/copilot/ask', json={'message': "What events are coming up?"})
            assert res.status_code == 200
            data = res.get_json()
            assert data['status'] == 'ok'
            assert 'AI Provider Notice' in data['response']
            assert 'Falling back to verified deterministic' in data['response']
            assert data['mode'] == 'fallback'


def test_copilot_generative_ai_success(client, db):
    """When external AI provider succeeds, the AI-generated completion is returned."""
    create_user(db, 'ai_member2', 'Member')
    login(client, 'ai_member2', 'password123', login_type='user')

    mock_config = {'provider': 'gemini', 'key': 'test_key', 'model': 'gemini-1.5-flash'}
    mock_ai_response = {'success': True, 'text': 'AI Response: Next event is HackFest on Friday.', 'provider': 'Gemini 1.5 Flash'}

    with patch('copilot_service.get_ai_config', return_value=mock_config):
        with patch('copilot_service.call_external_ai', return_value=mock_ai_response):
            res = client.post('/copilot/ask', json={'message': "What events are coming up?"})
            assert res.status_code == 200
            data = res.get_json()
            assert data['status'] == 'ok'
            assert data['mode'] == 'generative_ai'
            assert 'Next event is HackFest' in data['response']


def test_copilot_greeting_does_not_dump_performance_summary(client, db):
    """Member sending a casual greeting receives a conversational welcome and NO executive briefing."""
    u_id = create_user(db, 'greet_user', 'Member', full_name='Kamalika Sen')
    login(client, 'greet_user', 'password123', login_type='user')

    greetings = ['Hey', 'hello', 'Hi there!', 'hey copilot']
    for g in greetings:
        res = client.post('/copilot/ask', json={'message': g})
        assert res.status_code == 200
        data = res.get_json()
        assert data['status'] == 'ok'
        resp_text = data['response']

        # Must be friendly conversational greeting
        assert 'Kamalika' in resp_text or 'Kamalika Sen' in resp_text
        assert 'How can I help you' in resp_text or 'What can I help you' in resp_text

        # Must NOT dump irrelevant executive club performance briefing
        assert 'Executive Performance Summary' not in resp_text
        assert 'Club Health Score' not in resp_text
        assert 'Total Active Members' not in resp_text


def test_copilot_followup_question_resolves_earliest_event(client, db):
    """Member asking follow-up 'Which one is happening first?' correctly identifies the earliest event."""
    create_user(db, 'followup_user', 'Member')
    login(client, 'followup_user', 'password123', login_type='user')

    near_date = (date.today() + timedelta(days=2)).isoformat()
    far_date = (date.today() + timedelta(days=20)).isoformat()

    db.execute("""
        INSERT INTO events (title, description, event_date, event_time, venue, capacity, member_price, non_member_price, status, created_by)
        VALUES ('AI Robotics Workshop', 'Hands-on robotics sprint', ?, '10:00', 'Lab 2', 50, 0.0, 100.0, 'Upcoming', 1)
    """, (near_date,))
    db.execute("""
        INSERT INTO events (title, description, event_date, event_time, venue, capacity, member_price, non_member_price, status, created_by)
        VALUES ('Spring Annual Gala', 'Year-end formal dinner', ?, '19:00', 'Grand Hall', 300, 200.0, 350.0, 'Upcoming', 1)
    """, (far_date,))
    db.commit()

    # Turn 1: Ask about upcoming events
    res1 = client.post('/copilot/ask', json={'message': 'What events are coming up?'})
    assert res1.status_code == 200
    data1 = res1.get_json()
    assert 'AI Robotics Workshop' in data1['response']
    assert 'Spring Annual Gala' in data1['response']

    # Turn 2: Follow-up question with history
    history = [
        {'role': 'user', 'content': 'What events are coming up?'},
        {'role': 'assistant', 'content': data1['response']}
    ]
    res2 = client.post('/copilot/ask', json={
        'message': 'Which one is happening first?',
        'history': history
    })
    assert res2.status_code == 200
    data2 = res2.get_json()
    assert data2['status'] == 'ok'
    # The earliest event is AI Robotics Workshop
    assert 'AI Robotics Workshop' in data2['response']
    assert near_date in data2['response']
    assert 'happening first' in data2['response'].lower() or 'earliest' in data2['response'].lower()


def test_copilot_deterministic_mode_no_repeated_setup_warning(client, db):
    """In deterministic mode (no external AI key), responses never show repetitive setup warnings."""
    create_user(db, 'det_user', 'Member')
    login(client, 'det_user', 'password123', login_type='user')

    with patch('copilot_service.get_ai_config', return_value=None):
        for msg in ['Hey', 'What events are coming up?', 'How can I register for an event?']:
            res = client.post('/copilot/ask', json={'message': msg})
            assert res.status_code == 200
            data = res.get_json()
            assert data['status'] == 'ok'
            # Confirm no setup notice header
            assert 'AI Provider Setup Notice' not in data['response']
            assert 'No external AI provider API key was found' not in data['response']


def test_copilot_gemini_sdk_mock_integration(client, db):
    """Test calling Gemini generative model using mocked google-genai client."""
    create_user(db, 'gemini_user', 'Member')
    login(client, 'gemini_user', 'password123', login_type='user')

    mock_config = {
        'provider': 'gemini',
        'key': 'test-gemini-key',
        'model': 'gemini-2.5-flash'
    }

    class MockResponse:
        text = "Hello! The next event is the AI Robotics Workshop on Friday."

    class MockModels:
        def generate_content(self, model, contents, config=None):
            assert model == 'gemini-2.5-flash'
            return MockResponse()

    class MockClient:
        def __init__(self, api_key):
            assert api_key == 'test-gemini-key'
            self.models = MockModels()

    with patch('copilot_service.get_ai_config', return_value=mock_config):
        with patch('copilot_service.genai') as mock_genai_mod:
            mock_genai_mod.Client = MockClient
            res = client.post('/copilot/ask', json={'message': 'When is the next workshop?'})
            assert res.status_code == 200
            data = res.get_json()
            assert data['status'] == 'ok'
            assert data['mode'] == 'generative_ai'
            assert 'AI Robotics Workshop' in data['response']


def test_copilot_clear_conversation_history(client, db):
    """User can clear active session conversation history via POST /copilot/clear."""
    create_user(db, 'clear_user', 'Member')
    login(client, 'clear_user', 'password123', login_type='user')

    # Seed session history via ask
    client.post('/copilot/ask', json={'message': 'What events are coming up?'})

    with client.session_transaction() as sess:
        assert len(sess.get('copilot_history', [])) > 0

    # Call /copilot/clear
    res = client.post('/copilot/clear')
    assert res.status_code == 200
    data = res.get_json()
    assert data['status'] == 'ok'

    with client.session_transaction() as sess:
        assert 'copilot_history' not in sess

