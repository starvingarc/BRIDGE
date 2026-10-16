"""Synthetic initialized accounts for Web integration tests."""
from bridge.web.account_admin import initialize, MARKER
from bridge.web.app import create_app

PASSWORD = "correct horse battery staple"
USERNAME = "operator"
LOGIN = {"username": USERNAME, "password": PASSWORD}


def create_test_app(settings):
    if not (settings.storage_root / MARKER).exists():
        initialize(settings.storage_root, USERNAME, PASSWORD, settings.runtime_environment)
    return create_app(settings)


def login_test_account(client):
    client.headers["Origin"] = client.app.state.service.settings.origin
    if client.get("/api/me").status_code != 200:
        response = client.post("/api/login", json=LOGIN)
        assert response.status_code == 200, response.text
