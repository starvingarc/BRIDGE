"""Research ownership, durable originals and independent scientific bindings."""
from __future__ import annotations

import hashlib
import json

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from account_support import create_test_app
from multiuser_support import multi_clients
from web_support import client, h5ad, login, settle


def research(client, name="合成研究"):
    response = client.post("/api/researches", json={"name": name, "description": "synthetic research only"})
    assert response.status_code == 200, response.text
    return response.json()


def conversation(client, rid=None):
    response = client.post("/api/sessions", json={"research_id": rid} if rid else {})
    assert response.status_code == 200, response.text
    return response.json()


def material(client, rid, name, content):
    response = client.post(f"/api/researches/{rid}/uploads", files={"file": (name, content)})
    assert response.status_code == 200, response.text
    return response.json()


def select(client, sid, mid, **kwargs):
    return client.post(f"/api/sessions/{sid}/research-materials", json={"material_id": mid, **kwargs})


def test_research_and_conversations_survive_restart_without_sharing_history(client):
    login(client)
    rid = research(client)["id"]
    first, second = conversation(client, rid), conversation(client, rid)
    service = client.app.state.service
    state = service.load(first["id"])
    service.message(state, "user", "Only the first conversation contains this question.", source="user_input")
    service.sessions.save(state)
    assert second["research_id"] == rid
    assert all("Only the first" not in m["content"] for m in second["messages"])
    listing = client.get("/api/researches").json()["researches"]
    assert [(r["id"], r["session_count"], r["material_count"]) for r in listing] == [(rid, 2, 0)]
    with TestClient(create_test_app(service.settings)) as restarted:
        restarted.headers["Origin"] = "http://testserver"
        login(restarted)
        assert restarted.get(f"/api/researches/{rid}").json()["name"] == "合成研究"
        assert restarted.get(f"/api/sessions/{first['id']}").json()["messages"][-1]["content"].startswith("Only the first")
        assert len(restarted.get(f"/api/sessions/{second['id']}").json()["messages"]) == len(second["messages"])


def test_research_ids_and_material_bytes_never_cross_accounts(tmp_path):
    with multi_clients(tmp_path) as (_, alice, bob, admin):
        rid = research(alice, "Private research name")["id"]
        mid = material(alice, rid, "plan.txt", b"Private source text")["id"]
        foreign_sid = conversation(bob)["id"]
        assert bob.get("/api/researches").json()["researches"] == []
        for other in (bob, admin):
            for method, suffix, payload in (
                ("GET", "", None), ("PATCH", "", {"name": "changed"}),
                ("GET", f"/materials/{mid}", None), ("POST", "/uploads", {}),
            ):
                response = other.request(method, f"/api/researches/{rid}{suffix}", **({"json": payload} if payload is not None else {}))
                assert response.status_code == 404, response.text
                assert "Private" not in response.text
            assert other.post("/api/sessions", json={"research_id": rid}).status_code == 404
        assert bob.post(f"/api/sessions/{foreign_sid}/research", json={"research_id": rid}).status_code == 404
        assert research(alice)["id"] != rid
        assert alice.post("/api/researches", json={"name": "x"}, headers={"Origin": "https://other.invalid"}).status_code == 403


def test_shared_h5ad_selection_is_independent_idempotent_and_outlives_session(client, tmp_path):
    login(client)
    rid = research(client)["id"]
    first, second = conversation(client, rid), conversation(client, rid)
    raw = h5ad(tmp_path)
    item = material(client, rid, "synthetic.h5ad", raw)
    before = client.get(f"/api/sessions/{second['id']}").json()
    assert before["uploads"] == []  # Visibility never silently binds an analysis input.
    response = select(client, first["id"], item["id"])
    assert response.status_code == 200, response.text
    upload = response.json()["uploads"][0]
    assert upload["material_id"] == item["id"]
    assert select(client, first["id"], item["id"]).json()["uploads"] == [upload]
    service = client.app.state.service
    private = service.load(first["id"])
    assert private["_uploads"][upload["id"]]["sha256"] == hashlib.sha256(raw).hexdigest()
    assert (service.directory(first["id"]) / "uploads" / (upload["id"] + ".h5ad")).read_bytes() == raw
    assert client.request("DELETE", f"/api/sessions/{first['id']}", json={}).status_code == 200
    assert client.get(f"/api/researches/{rid}/materials/{item['id']}").content == raw
    response = select(client, second["id"], item["id"])
    assert response.status_code == 200, response.text
    assert response.json()["plan"] is None
    assert service.load(second["id"]).get("_intakes", {}) == {}
    assert client.get(f"/api/researches/{rid}").json()["material_count"] == 1


def test_legacy_assignment_preserves_scientific_state_and_title_can_change(client):
    login(client)
    legacy = conversation(client)
    assert legacy.get("research_id") is None
    rid = research(client)["id"]
    response = client.post(f"/api/sessions/{legacy['id']}/research", json={"research_id": rid})
    assert response.status_code == 200, response.text
    assert response.json()["messages"] == legacy["messages"]
    assert response.json()["research_id"] == rid
    response = client.patch(f"/api/sessions/{legacy['id']}/title", json={"title": "我的自由讨论"})
    assert response.status_code == 200
    assert response.json()["title"] == "我的自由讨论"
    assert client.get("/api/sessions").json()["sessions"][0]["research_id"] == rid
    other = research(client)["id"]
    assert client.post(f"/api/sessions/{legacy['id']}/research", json={"research_id": other}).status_code == 409


def test_library_upload_validates_types_counts_and_quota(client, tmp_path):
    login(client)
    rid = research(client)["id"]
    for name, raw in (("../a.txt", b"text"), ("a.exe", b"bad"), ("bad.h5ad", b"not hdf"), ("bad.txt", b"\xff\x00")):
        assert client.post(f"/api/researches/{rid}/uploads", files={"file": (name, raw)}).status_code in {400, 422}
    assert client.get(f"/api/researches/{rid}").json()["materials"] == []
    raw = b"condition,value\nA,1\n"
    item = material(client, rid, "metadata.csv", raw)
    assert item["kind"] == "metadata"
    assert client.get(f"/api/researches/{rid}/materials/{item['id']}").content == raw
    service = client.app.state.service
    owner = client.get("/api/me").json()["user"]["id"]
    assert service.quotas.usage()[owner] == len(raw)
    # All declared transfer reservations count existing research bytes as well.
    with pytest.raises(HTTPException) as error:
        with service.quotas.reserve_upload(owner, service.settings.user_storage_bytes - len(raw) + 1):
            pass
    assert error.value.status_code == 429


def test_material_selection_rejects_other_research_and_busy_session(client, tmp_path):
    login(client)
    left, right = research(client)["id"], research(client)["id"]
    item = material(client, left, "synthetic.h5ad", h5ad(tmp_path))
    sid = conversation(client, right)["id"]
    assert select(client, sid, item["id"]).status_code == 404
    sid = conversation(client, left)["id"]
    service = client.app.state.service
    with service.lock:
        state = service.load(sid)
        state["status"] = "running"
        service.sessions.save(state)
    assert select(client, sid, item["id"]).status_code == 409
    assert service.load(sid)["uploads"] == []


def test_protocol_original_can_be_used_by_two_conversations_without_confirmation_copy(client, tmp_path):
    login(client)
    rid = research(client)["id"]
    data = material(client, rid, "synthetic.h5ad", h5ad(tmp_path))
    protocol = material(client, rid, "protocol.txt", b"Day 0: start neural differentiation.\nDay 7: collect cells.")
    for _ in range(2):
        sid = conversation(client, rid)["id"]
        aid = select(client, sid, data["id"]).json()["uploads"][0]["id"]
        assert select(client, sid, protocol["id"]).status_code == 422
        response = select(client, sid, protocol["id"], upload_id=aid)
        assert response.status_code == 200, response.text
        settle(client, sid)
        state = client.app.state.service.load(sid)
        assert len(state["_intake_autofill"][aid]["protocols"]) == 1
        assert state.get("_intakes", {}) == {}


def test_corrupt_shared_bytes_cannot_be_downloaded_or_bound(client, tmp_path):
    from bridge.web.sessions import write_file
    login(client)
    rid = research(client)["id"]
    item = material(client, rid, "synthetic.h5ad", h5ad(tmp_path))
    sid = conversation(client, rid)["id"]
    service = client.app.state.service
    path = service.researches.directory(rid) / "materials" / (item["id"] + ".bin")
    original = path.read_bytes()
    write_file(path, b"X" + original[1:])
    assert client.get(f"/api/researches/{rid}/materials/{item['id']}").status_code == 409
    assert select(client, sid, item["id"]).status_code == 409
    assert service.load(sid)["uploads"] == []
    directory = service.directory(sid) / "uploads"
    assert not directory.exists() or not list(directory.iterdir())


def test_legacy_original_can_be_shared_explicitly_without_approval_state(client, tmp_path):
    login(client)
    sid = conversation(client)["id"]
    raw = h5ad(tmp_path)
    response = client.post(f"/api/sessions/{sid}/uploads", files={"file": ("synthetic.h5ad", raw)})
    assert response.status_code == 200
    aid = response.json()["uploads"][0]["id"]
    rid = research(client)["id"]
    assert client.post(f"/api/sessions/{sid}/research", json={"research_id": rid}).status_code == 200
    original = client.get(f"/api/sessions/{sid}").json()
    response = client.post(f"/api/sessions/{sid}/share-material", json={"upload_id": aid})
    assert response.status_code == 200, response.text
    mid = response.json()["id"]
    assert client.post(f"/api/sessions/{sid}/share-material", json={"upload_id": aid}).json()["id"] == mid
    assert client.get(f"/api/researches/{rid}").json()["material_count"] == 1
    assert client.get(f"/api/sessions/{sid}").json()["messages"] == original["messages"]
    assert client.request("DELETE", f"/api/sessions/{sid}", json={}).status_code == 200
    assert client.get(f"/api/researches/{rid}/materials/{mid}").content == raw


@pytest.mark.parametrize("payload", [{"name": "  "}, {"name": "x", "owner_id": "a" * 32}, {"name": "x\x00"}])
def test_research_creation_rejects_invalid_identity_and_empty_names(client, payload):
    login(client)
    assert client.post("/api/researches", json=payload).status_code == 422
    assert client.get("/api/researches").json()["researches"] == []


@pytest.mark.parametrize("operation", ["select", "share"])
def test_material_file_io_does_not_block_other_conversations(client, tmp_path, monkeypatch, operation):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    login(client)
    rid = research(client)["id"]
    first, second = conversation(client, rid), conversation(client, rid)
    raw = h5ad(tmp_path)
    service = client.app.state.service
    if operation == "select":
        item = material(client, rid, "synthetic.h5ad", raw)
        endpoint = f"/api/sessions/{first['id']}/research-materials"
        payload, method = {"material_id": item["id"]}, "copy_to"
    else:
        uploaded = client.post(f"/api/sessions/{first['id']}/uploads", files={"file": ("synthetic.h5ad", raw)}).json()
        endpoint = f"/api/sessions/{first['id']}/share-material"
        payload, method = {"upload_id": uploaded["uploads"][0]["id"]}, "put"
    entered, release = Event(), Event()
    original = getattr(service.researches, method)

    def paused_file_io(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        return original(*args, **kwargs)

    monkeypatch.setattr(service.researches, method, paused_file_io)
    with ThreadPoolExecutor(max_workers=2) as workers:
        transfer = workers.submit(client.post, endpoint, json=payload)
        try:
            assert entered.wait(2)
            other = workers.submit(client.get, f"/api/sessions/{second['id']}")
            assert other.result(timeout=2).status_code == 200
            assert client.patch(f"/api/sessions/{first['id']}/title", json={"title": "while copying"}).status_code == 409
        finally:
            release.set()
        assert transfer.result(timeout=5).status_code == 200


def test_document_upload_obeys_smaller_deployment_file_limit(client):
    from dataclasses import replace

    login(client)
    rid = research(client)["id"]
    settings = replace(client.app.state.service.settings, max_upload_bytes=128)
    with TestClient(create_test_app(settings)) as limited:
        limited.headers["Origin"] = "http://testserver"
        login(limited)
        accepted = limited.post(f"/api/researches/{rid}/uploads", files={"file": ("exact.txt", b"x" * 128)})
        rejected = limited.post(f"/api/researches/{rid}/uploads", files={"file": ("over.txt", b"x" * 129)})
        assert accepted.status_code == 200
        assert rejected.status_code == 413
        assert [item["name"] for item in limited.get(f"/api/researches/{rid}").json()["materials"]] == ["exact.txt"]


def test_material_matrix_locations_reach_upload_list_and_restart(client, tmp_path):
    login(client)
    rid = research(client)["id"]
    item = material(client, rid, "synthetic.h5ad", h5ad(tmp_path, layer=True))
    assert item["locations"] == ["X", "layers/counts"]
    assert set(item) == {"id", "name", "kind", "size", "created_at", "locations"}
    expected = client.get(f"/api/researches/{rid}").json()["materials"]
    assert expected == [item]
    service = client.app.state.service
    with TestClient(create_test_app(service.settings)) as restarted:
        restarted.headers["Origin"] = "http://testserver"
        login(restarted)
        assert restarted.get(f"/api/researches/{rid}").json()["materials"] == expected
    # Older metadata with no inspected locations remains readable without invented choices.
    state = service.researches.load(rid)
    del state["materials"][0]["locations"]
    service.researches.save(state)
    legacy = client.get(f"/api/researches/{rid}").json()["materials"][0]
    assert "locations" not in legacy
