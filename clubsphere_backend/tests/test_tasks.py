import pytest
from tests.conftest import create_user, login


def test_volunteer_task_workflow(client, db):
    """Test task assignment, permission checks, and status lifecycle."""
    create_user(db, 'admin', 'Administrator')
    volunteer_id = create_user(db, 'volunteer1', 'Volunteer')
    organizer_id = create_user(db, 'organizer1', 'Event Organizer')

    # Organizer creates a task assigned to volunteer1
    login(client, 'organizer1')
    res_create = client.post('/tasks/new', data={
        'title': 'Setup Stage Microphones',
        'description': 'Connect 4 wireless mics and test sound levels',
        'assigned_to': str(volunteer_id),
        'priority': 'High',
        'deadline': '2026-11-01'
    }, follow_redirects=True)

    assert res_create.status_code == 200
    assert b"created and assigned" in res_create.data

    task = db.execute("SELECT * FROM volunteer_tasks WHERE title = 'Setup Stage Microphones'").fetchone()
    assert task is not None
    assert task['status'] == 'Pending'
    assert task['assigned_to'] == volunteer_id
    assert task['priority'] == 'High'

    # Assigned volunteer updates status to In Progress
    login(client, 'volunteer1')
    res_prog = client.post(f'/tasks/{task["id"]}/status', data={
        'status': 'In Progress'
    }, follow_redirects=True)
    assert res_prog.status_code == 200

    task_updated = db.execute("SELECT * FROM volunteer_tasks WHERE id = ?", (task['id'],)).fetchone()
    assert task_updated['status'] == 'In Progress'

    # Assigned volunteer marks completed
    res_done = client.post(f'/tasks/{task["id"]}/status', data={
        'status': 'Completed'
    }, follow_redirects=True)
    assert res_done.status_code == 200

    task_done = db.execute("SELECT * FROM volunteer_tasks WHERE id = ?", (task['id'],)).fetchone()
    assert task_done['status'] == 'Completed'

    # Reopening task back to In Progress
    res_reopen = client.post(f'/tasks/{task["id"]}/status', data={
        'status': 'In Progress'
    }, follow_redirects=True)
    assert res_reopen.status_code == 200
    task_reopened = db.execute("SELECT * FROM volunteer_tasks WHERE id = ?", (task['id'],)).fetchone()
    assert task_reopened['status'] == 'In Progress'

    # Another unassigned volunteer cannot update this task
    volunteer2_id = create_user(db, 'volunteer2', 'Volunteer')
    login(client, 'volunteer2')
    res_unauth = client.post(f'/tasks/{task["id"]}/status', data={
        'status': 'Completed'
    }, follow_redirects=True)
    assert b"You can only update tasks assigned to you" in res_unauth.data
    task_unchanged = db.execute("SELECT * FROM volunteer_tasks WHERE id = ?", (task['id'],)).fetchone()
    assert task_unchanged['status'] == 'In Progress'
