from __future__ import annotations

import json
from threading import Event

import pytest
from fastapi.testclient import TestClient

from account_support import create_test_app as create_app
from bridge.web.sessions import write_file
from web_support import client as client, login, new_session


def _delete(client, url, **kwargs):
    return client.request('DELETE', url, json={}, **kwargs)


def test_archive_restore_and_restart_keep_session_contents(client):
    state = new_session(client)
    sid = state['id']
    other = new_session(client)['id']
    url = f'/api/sessions/{sid}'
    original = client.get(url).json()['messages']
    response = client.patch(url, json={'archived': True})
    assert response.status_code == 200
    assert response.json()['archived'] is True
    assert {s['id'] for s in client.get('/api/sessions?archived=false').json()['sessions']} == {other}
    assert [s['id'] for s in client.get('/api/sessions?archived=true').json()['sessions']] == [sid]
    assert client.get(url).json()['messages'] == original
    with TestClient(create_app(client.app.state.service.settings)) as restarted:
        restarted.headers['Origin'] = 'http://testserver'
        login(restarted)
        assert restarted.get(url).json()['archived'] is True
        assert restarted.patch(url, json={'archived': False}).status_code == 200
        assert {s['id'] for s in restarted.get('/api/sessions').json()['sessions']} == {sid, other}
        assert restarted.get('/api/sessions?archived=true').json()['sessions'] == []


def test_delete_removes_only_own_files_and_never_follows_links(client, tmp_path):
    sid = new_session(client)['id']
    other = new_session(client)['id']
    service = client.app.state.service
    directory = service.directory(sid)
    write_file(directory / 'uploads' / 'synthetic.h5ad', b'synthetic uploaded copy')
    write_file(directory / 'results' / 'report.html', b'synthetic report')
    outside = tmp_path / 'original.txt'
    outside.write_text('external original remains')
    (directory / 'external-link').symlink_to(outside)
    response = _delete(client, f'/api/sessions/{sid}')
    assert response.status_code == 200
    assert response.json() == {'deleted': True}
    assert not directory.exists()
    assert outside.read_text() == 'external original remains'
    assert client.get(f'/api/sessions/{sid}').status_code == 404
    assert client.get(f'/api/sessions/{other}').status_code == 200
    assert [s['id'] for s in client.get('/api/sessions').json()['sessions']] == [other]
    assert service.sessions.root.joinpath('events.sqlite3').exists()
    with TestClient(create_app(service.settings)) as restarted:
        restarted.headers['Origin'] = 'http://testserver'
        login(restarted)
        assert restarted.get(f'/api/sessions/{sid}').status_code == 404
        assert restarted.get(f'/api/sessions/{other}').status_code == 200


@pytest.mark.parametrize('method,payload', [('patch', {'archived': True}), ('delete', {})])
def test_session_management_blocks_live_worker_even_after_status_settles(client, method, payload):
    sid = new_session(client)['id']
    service = client.app.state.service
    entered, release = Event(), Event()

    def work(sid, epoch):
        with service.lock:
            state = service.load(sid)
            state['status'] = 'idle'
            service.sessions.save(state)
        entered.set()
        assert release.wait(10)

    with service.lock:
        service.execution.schedule(service.load(sid), 'thinking', work)
    assert entered.wait(5)
    try:
        response = client.request(method.upper(), f'/api/sessions/{sid}', json=payload)
        assert response.status_code == 409
        assert service.directory(sid).exists()
    finally:
        release.set()
    service.execution.shutdown()
    assert client.request(method.upper(), f'/api/sessions/{sid}', json=payload).status_code == 200


@pytest.mark.parametrize('operation', ['archive', 'delete'])
@pytest.mark.parametrize('busy', ['thinking', 'running', 'stopping', 'upload'])
def test_busy_session_management_is_rejected(client, operation, busy):
    sid = new_session(client)['id']
    service = client.app.state.service
    with service.lock:
        state = service.load(sid)
        if busy == 'upload':
            service.uploads_in_progress.add(sid)
        else:
            state['status'] = busy
            service.sessions.save(state)
    try:
        response = (client.patch(f'/api/sessions/{sid}', json={'archived': True})
                    if operation == 'archive' else _delete(client, f'/api/sessions/{sid}'))
        assert response.status_code == 409
        assert client.get(f'/api/sessions/{sid}').json().get('archived') is False
    finally:
        service.uploads_in_progress.discard(sid)


def test_management_requires_login_origin_and_valid_fields(client):
    sid = new_session(client)['id']
    url = f'/api/sessions/{sid}'
    for body in ({'archived': 'yes'}, {'archived': True, 'title': 'changed'}, {}):
        assert client.patch(url, json=body).status_code == 422
    assert client.patch(url, json={'archived': True}, headers={'Origin': 'https://other.invalid'}).status_code == 403
    assert _delete(client, url, headers={'Origin': 'https://other.invalid'}).status_code == 403
    client.cookies.clear()
    assert client.patch(url, json={'archived': True}).status_code == 401
    assert _delete(client, url).status_code == 401


def test_legacy_session_defaults_to_unarchived(client):
    sid = new_session(client)['id']
    path = client.app.state.service.directory(sid) / 'session.json'
    stored = json.loads(path.read_text())
    stored.pop('archived', None)
    write_file(path, json.dumps(stored).encode())
    assert client.get(f'/api/sessions/{sid}').json()['archived'] is False
    assert [s['id'] for s in client.get('/api/sessions').json()['sessions']] == [sid]


def test_delete_rejects_missing_or_symlink_session_directory(client, tmp_path):
    login(client)
    sid = 'f' * 32
    target = tmp_path / 'outside'
    target.mkdir()
    (target / 'keep').write_text('keep')
    link = client.app.state.service.root / sid
    link.symlink_to(target, target_is_directory=True)
    assert _delete(client, f'/api/sessions/{sid}').status_code == 404
    assert (target / 'keep').read_text() == 'keep'
    assert _delete(client, '/api/sessions/' + 'e' * 32).status_code == 404


def test_failed_cleanup_can_be_retried_without_exposing_partial_session(client, monkeypatch):
    import shutil
    sid = new_session(client)['id']
    directory = client.app.state.service.directory(sid)
    with monkeypatch.context() as patch:
        patch.setattr(shutil, 'rmtree', lambda *a, **k: (_ for _ in ()).throw(OSError('private path')))
        response = _delete(client, f'/api/sessions/{sid}')
        assert response.status_code == 503
        assert 'private path' not in response.text
        assert client.get('/api/sessions').json()['sessions'] == []
        assert client.get(f'/api/sessions/{sid}').status_code == 404
    assert _delete(client, f'/api/sessions/{sid}').status_code == 200
    assert not directory.exists()
    assert not list(directory.parent.glob('.deleted-*'))
