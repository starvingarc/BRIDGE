import json
import re
import shutil

from multiuser_support import multi_clients


def test_cross_user_route_matrix_denied(tmp_path):
    with multi_clients(tmp_path) as (service, alice, bob, admin):
        own = alice.post("/api/sessions", json={}).json()
        sid = own["id"]
        other = bob.post("/api/sessions", json={}).json()["id"]
        assert [s["id"] for s in alice.get("/api/sessions").json()["sessions"]] == [sid]
        assert [s["id"] for s in bob.get("/api/sessions").json()["sessions"]] == [other]
        state_file = service.directory(sid) / "session.json"
        original = state_file.read_bytes()
        # Exercise every registered resource route, including validation errors.
        for route in alice.app.routes:
            if not getattr(route, "path", "").startswith("/api/sessions/{sid}"):
                continue
            url = re.sub(r"\{[^}]+\}", "a" * 32, route.path.replace("{sid}", sid))
            for method in route.methods - {"OPTIONS", "HEAD"}:
                for client in (bob, admin):
                    response = client.request(method, url, **({"json": {}} if method != "GET" else {}))
                    assert response.status_code == 404, (method, url, response.text)
                    assert sid not in response.text and own["title"] not in response.text
        assert state_file.read_bytes() == original
        assert alice.get("/api/sessions/" + sid).status_code == 200
        assert bob.get("/api/sessions/" + other).status_code == 200


def test_unowned_records_are_hidden_and_owner_cannot_be_supplied(tmp_path):
    with multi_clients(tmp_path) as (service, alice, bob, admin):
        sid = alice.post("/api/sessions", json={}).json()["id"]
        state = service.load(sid)
        owner = state.pop("owner_id")
        service.sessions.save(state)
        assert alice.get("/api/sessions").json()["sessions"] == []
        assert alice.get("/api/sessions/" + sid).status_code == 404
        assert admin.get("/api/admin/sessions/" + sid).status_code == 404
        # A client cannot assign its newly created data to another account.
        response = bob.post("/api/sessions", json={"owner_id": owner})
        assert response.status_code == 422


def test_delete_retry_preserves_owner(tmp_path, monkeypatch):
    with multi_clients(tmp_path) as (service, alice, bob, admin):
        sid = alice.post("/api/sessions", json={}).json()["id"]
        original = shutil.rmtree
        def partially_remove(path):
            (path / "session.json").unlink()
            raise OSError("synthetic cleanup interruption")
        monkeypatch.setattr("bridge.web.sessions.shutil.rmtree", partially_remove)
        assert alice.request("DELETE", "/api/sessions/" + sid, json={}).status_code == 503
        assert bob.request("DELETE", "/api/sessions/" + sid, json={}).status_code == 404
        monkeypatch.setattr("bridge.web.sessions.shutil.rmtree", original)
        assert alice.request("DELETE", "/api/sessions/" + sid, json={}).status_code == 200
        assert not (service.root / (".deleted-" + sid)).exists()
