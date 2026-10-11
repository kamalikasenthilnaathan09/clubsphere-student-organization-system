import os
import tempfile
import pytest
from werkzeug.security import generate_password_hash

import database
from app import app as flask_app


@pytest.fixture
def app():
    # Create temporary database file for test isolation
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(db_fd)

    flask_app.config.update({
        'TESTING': True,
        'DATABASE': db_path,
        'SECRET_KEY': 'test-secret-key-clubsphere'
    })

    with flask_app.app_context():
        database.init_db(db_path)

    yield flask_app

    # Teardown
    try:
        if os.path.exists(db_path):
            os.remove(db_path)
    except Exception:
        pass


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def runner(app):
    return app.test_cli_runner()


@pytest.fixture
def db(app):
    with app.app_context():
        conn = database.get_db(app.config['DATABASE'])
        yield conn
        conn.close()


def create_user(db, username, role, password='password123', email=None, full_name=None):
    email = email or f"{username}@example.com"
    full_name = full_name or f"{username.capitalize()} User"
    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO users (username, email, password_hash, full_name, role, is_active)
        VALUES (?, ?, ?, ?, ?, 1)
    """, (username, email, generate_password_hash(password), full_name, role))
    db.commit()
    return cursor.lastrowid


def login(client, login_id='admin', password='password123', login_type=None):
    if login_type is None:
        login_type = 'admin' if 'admin' in login_id.lower() else 'user'
    return client.post('/login', data={
        'login_id': login_id,
        'password': password,
        'login_type': login_type
    }, follow_redirects=True)
