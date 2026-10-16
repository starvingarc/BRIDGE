"""Synthetic multi-user fixtures shared by Web authorization tests."""
from contextlib import contextmanager

from fastapi.testclient import TestClient
from bridge.web.accounts import NOTICE_VERSION
from account_support import create_test_app as create_app
from bridge.web.runtime import Settings

PASSWORD = "correct horse battery staple"


@contextmanager
def multi_clients(tmp_path, **options):
    settings = Settings(storage_root=tmp_path / "web",
                        origin="http://testserver", model="shared-model",
                        model_base_url="https://provider.invalid/v1",
                        model_api_key="shared-secret", **options)
    app = create_app(settings)
    app.state.service.accounts.bootstrap_admin("operator", PASSWORD)
    with TestClient(app) as alice, TestClient(app) as bob, TestClient(app) as admin:
        for client in (alice, bob, admin):
            client.headers["Origin"] = settings.origin
        for client, name in ((alice, "alice"), (bob, "bob")):
            response = client.post("/api/register", json={"username": name, "password": PASSWORD,
                                                         "notice_version": NOTICE_VERSION})
            assert response.status_code == 200, response.text
        assert admin.post("/api/login", json={"username": "operator", "password": PASSWORD}).status_code == 200
        yield app.state.service, alice, bob, admin
