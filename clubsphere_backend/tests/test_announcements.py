import pytest
from tests.conftest import create_user, login


def test_announcements_publishing_and_audience(client, db):
    """Test publishing announcements and audience permission filtering."""
    create_user(db, 'admin', 'Administrator')
    create_user(db, 'organizer', 'Event Organizer')
    create_user(db, 'member1', 'Member')

    # Organizer posts general announcement
    login(client, 'organizer')
    res_pub = client.post('/announcements/new', data={
        'title': 'Hackathon Opening Ceremony',
        'content': 'All participants please assemble in Hall A at 9:00 AM sharp.',
        'audience': 'All',
        'priority': 'Important'
    }, follow_redirects=True)

    assert res_pub.status_code == 200
    assert b"published successfully" in res_pub.data

    # Executive-only announcement
    client.post('/announcements/new', data={
        'title': 'Core Committee Budget Review',
        'content': 'Meeting tomorrow with Faculty Advisor.',
        'audience': 'Executive',
        'priority': 'Normal'
    }, follow_redirects=True)

    # Member views announcements board
    login(client, 'member1')
    res_mem = client.get('/announcements')
    assert res_mem.status_code == 200
    assert b"Hackathon Opening Ceremony" in res_mem.data
    # Member cannot see Executive-only announcement
    assert b"Core Committee Budget Review" not in res_mem.data

    # Administrator can view Executive-only announcement
    login(client, 'admin')
    res_adm = client.get('/announcements')
    assert res_adm.status_code == 200
    assert b"Core Committee Budget Review" in res_adm.data
