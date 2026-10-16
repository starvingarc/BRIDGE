import json
import httpx
from multiuser_support import multi_clients
from bridge.web.model_settings import ModelConfiguration

PROVIDER = {"id": "gateway", "name": "Lab gateway", "base_url": "https://personal.invalid/v1",
            "api_key": "private-one", "models": ["first", "second"], "action_protocol": "json"}


def test_providers_selection_isolation_restart_and_snapshot(tmp_path):
    with multi_clients(tmp_path) as (service, alice, bob, admin):
        uid = alice.get('/api/me').json()['user']['id']
        conf = service.model_configuration
        assert alice.put('/api/models/providers', json=PROVIDER).status_code == 200
        other = {**PROVIDER, 'id': 'other', 'api_key': 'private-two'}
        assert alice.put('/api/models/providers', json=other).status_code == 200
        result = alice.post('/api/models/select', json={'provider_id': 'gateway', 'model': 'second'})
        assert result.status_code == 200
        assert len(result.json()['providers']) == 3
        assert alice.get('/api/me/model-settings').json()['personal']['model'] == 'second'
        assert 'private-one' not in result.text and 'shared-secret' not in result.text
        assert len(bob.get('/api/models').json()['providers']) == 1
        assert bob.post('/api/models/select', json={'provider_id': 'gateway', 'model': 'second'}).status_code == 422
        context = conf.task_context(uid)
        assert alice.post('/api/models/select', json={'provider_id': 'other', 'model': 'first'}).status_code == 200
        with context:
            assert conf.current.model == 'second' and conf.current.model_api_key == 'private-one'
        restarted = ModelConfiguration(service.root, conf.default)
        assert restarted.snapshot_for(uid).model_api_key == 'private-two'
        assert alice.request('DELETE', '/api/models/providers/other', json={}).status_code == 200
        assert conf.snapshot_for(uid).model == 'shared-model'
        assert len(alice.get('/api/models').json()['providers']) == 2


def test_credentials_are_bound_to_account_provider_and_endpoint(tmp_path):
    with multi_clients(tmp_path) as (service, alice, bob, admin):
        assert alice.put('/api/models/providers', json=PROVIDER).status_code == 200
        assert alice.put('/api/models/providers', json={**PROVIDER, 'api_key': ''}).status_code == 200
        for value in ({**PROVIDER, 'id': 'new', 'api_key': ''},
                      {**PROVIDER, 'base_url': 'https://other.invalid', 'api_key': ''},
                      {**PROVIDER, 'base_url': 'https://127.0.0.1'},
                      {**PROVIDER, 'models': ['same', 'same']}):
            assert alice.put('/api/models/providers', json=value).status_code == 422
        assert bob.put('/api/models/providers', json={**PROVIDER, 'api_key': ''}).status_code == 422
        shared = {**PROVIDER, 'id': 'default', 'name': 'Shared', 'api_key': 'shared-new'}
        assert alice.put('/api/models/providers', json=shared).status_code == 403
        assert alice.post('/api/models/catalog', json=shared).status_code == 403
        assert admin.put('/api/models/providers', json=shared).status_code == 200
        result = alice.get('/api/models').json()
        assert result['providers'][0]['editable'] is False
        assert result['providers'][0]['models'] == ['first', 'second']
        assert alice.post('/api/models/select', json={'provider_id': 'default', 'model': 'second'}).status_code == 200
        uid = alice.get('/api/me').json()['user']['id']
        assert service.model_configuration.snapshot_for(uid).model == 'second'
        assert service.model_configuration.default.model == 'first'
        assert alice.request('DELETE', '/api/models/providers/default', json={}).status_code == 403


def test_catalog_is_bounded_redacted_read_only_and_uses_restricted_transport(tmp_path, monkeypatch):
    with multi_clients(tmp_path) as (service, alice, bob, admin):
        assert alice.put('/api/models/providers', json=PROVIDER).status_code == 200
        original = httpx.Client
        calls = []
        def client(settings, *, timeout, trust_env):
            assert settings.model_endpoint_restricted and trust_env is False
            def reply(request):
                calls.append(request)
                return httpx.Response(200, json={'data': [{'id': 'remote'}, {'id': 'remote'}, {'id': 'another'}]})
            return original(transport=httpx.MockTransport(reply), timeout=timeout)
        monkeypatch.setattr('bridge.web.model_settings.provider_client', client)
        before = alice.get('/api/models').json()
        response = alice.post('/api/models/catalog', json={**PROVIDER, 'api_key': '', 'models': []})
        assert response.status_code == 200 and response.json()['models'] == ['remote', 'another']
        assert calls[0].method == 'GET' and str(calls[0].url).endswith('/models')
        assert calls[0].headers['Authorization'] == 'Bearer private-one'
        assert alice.get('/api/models').json() == before
        def failed(settings, **kw):
            return original(transport=httpx.MockTransport(lambda r: httpx.Response(401, text='private-one')), timeout=1)
        monkeypatch.setattr('bridge.web.model_settings.provider_client', failed)
        response = alice.post('/api/models/catalog', json=PROVIDER)
        assert response.json()['ok'] is False and 'private-one' not in response.text


def test_legacy_personal_settings_are_read_without_rewriting(tmp_path):
    with multi_clients(tmp_path) as (service, alice, bob, admin):
        uid = alice.get('/api/me').json()['user']['id']
        from bridge.web.sessions import write_file
        path = service.root / 'models' / (uid + '.json')
        old = {'source': 'personal', 'version': 'b' * 32, 'settings': {
            'base_url': PROVIDER['base_url'], 'model': 'legacy', 'api_key': 'legacy-key', 'action_protocol': 'json'}}
        write_file(path, json.dumps(old).encode())
        original = path.read_bytes()
        response = alice.get('/api/models')
        assert response.status_code == 200 and response.json()['selected']['model'] == 'legacy'
        assert path.read_bytes() == original
        assert service.model_configuration.snapshot_for(uid).model_api_key == 'legacy-key'


def test_catalog_rejects_oversized_response_and_redirect(tmp_path, monkeypatch):
    with multi_clients(tmp_path) as (service, alice, bob, admin):
        original = httpx.Client
        for response in (httpx.Response(200, content=b' ' * (1024 * 1024 + 1)),
                         httpx.Response(302, headers={'location': 'https://127.0.0.1/secret'})):
            monkeypatch.setattr('bridge.web.model_settings.provider_client',
                lambda settings, **kwargs: original(transport=httpx.MockTransport(lambda request: response)))
            result = alice.post('/api/models/catalog', json=PROVIDER)
            assert result.status_code == 200 and result.json()['ok'] is False


def test_account_directory_selection_and_shared_metadata_restart(tmp_path):
    from fastapi.testclient import TestClient
    from test_web_model_settings import settings, login
    from account_support import create_test_app as create_app
    config = settings(tmp_path)
    with TestClient(create_app(config)) as client:
        login(client)
        owner_id = client.get("/api/me").json()["user"]["id"]
        conf = client.app.state.service.model_configuration
        assert client.put('/api/models/providers', json=PROVIDER).status_code == 200
        assert client.post('/api/models/select', json={'provider_id': 'gateway', 'model': 'second'}).status_code == 200
        with conf.task_context(owner_id):
            assert conf.current.model == 'second'
            second_version = conf.current.model_configuration_id
        assert client.post('/api/models/select', json={'provider_id': 'gateway', 'model': 'first'}).status_code == 200
        with conf.task_context(owner_id):
            assert conf.current.model_configuration_id != second_version
        assert client.put('/api/models/providers', json={**PROVIDER, 'id': 'default', 'name': 'Lab shared'}).status_code == 200
    with TestClient(create_app(config)) as client:
        login(client)
        data = client.get('/api/models').json()
        assert data['providers'][0]['name'] == 'Lab shared'
        assert data['providers'][0]['models'] == ['first', 'second']
        assert data['selected'] == {'provider_id': 'gateway', 'model': 'first'}


def test_legacy_probe_does_not_hold_directory_lock(tmp_path, monkeypatch):
    from threading import Event, Thread
    from bridge.web.model_settings import ModelSettingsInput
    with multi_clients(tmp_path) as (service, alice, bob, admin):
        conf = service.model_configuration
        uid = alice.get('/api/me').json()['user']['id']
        entered, release, read = Event(), Event(), Event()
        def slow_probe(settings):
            entered.set()
            release.wait(5)
            return {'ok': True}
        monkeypatch.setattr(conf, 'probe', slow_probe)
        def read_directory():
            conf.providers_for(uid)
            read.set()
        probe = Thread(target=lambda: conf.test_for(uid, ModelSettingsInput(
            base_url=PROVIDER['base_url'], model='first', api_key='synthetic-key')))
        reader = Thread(target=read_directory)
        probe.start()
        try:
            assert entered.wait(2)
            reader.start()
            completed_while_probe_blocked = read.wait(1)
        finally:
            release.set()
            probe.join(3)
            reader.join(3)
        assert completed_while_probe_blocked
