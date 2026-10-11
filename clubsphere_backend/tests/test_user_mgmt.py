import pytest
from tests.conftest import create_user, login


def test_admin_user_creation_and_status_toggle(client, db):
    """Admin can create new role accounts and activate/deactivate accounts."""
    create_user(db, 'admin', 'Administrator')
    login(client, 'admin')

    # Create new Treasurer account
    res_create = client.post('/users/new', data={
        'full_name': 'Divya Treasurer',
        'username': 'divya_fin',
        'email': 'divya@clubsphere.org',
        'role': 'Treasurer',
        'password': 'password123'
    }, follow_redirects=True)

    assert res_create.status_code == 200
    assert b"created successfully" in res_create.data

    user = db.execute("SELECT * FROM users WHERE username = 'divya_fin'").fetchone()
    assert user is not None
    assert user['role'] == 'Treasurer'
    assert user['is_active'] == 1

    # Deactivate account
    res_deact = client.post(f'/users/{user["id"]}/toggle', follow_redirects=True)
    assert res_deact.status_code == 200
    assert b"deactivated" in res_deact.data

    user_deact = db.execute("SELECT * FROM users WHERE id = ?", (user['id'],)).fetchone()
    assert user_deact['is_active'] == 0

    # Reactivate account
    res_react = client.post(f'/users/{user["id"]}/toggle', follow_redirects=True)
    assert res_react.status_code == 200
    assert b"activated" in res_react.data

    user_react = db.execute("SELECT * FROM users WHERE id = ?", (user['id'],)).fetchone()
    assert user_react['is_active'] == 1
