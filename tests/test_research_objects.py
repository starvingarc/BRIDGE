"""M1 object persistence, immutable protocol editions and authenticated HTTP."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date
import json

import pytest
from fastapi.testclient import TestClient

from account_support import create_test_app, login_test_account
from multiuser_support import multi_clients
from bridge.web.runtime import Settings


@pytest.fixture
def client(tmp_path):
    settings = Settings(storage_root=tmp_path / "objects", origin="http://testserver",
                        model_base_url="https://provider.invalid/v1", model="test-model", model_api_key="test-key")
    with TestClient(create_test_app(settings)) as value:
        login_test_account(value)
        yield value


def request(client, method, url, payload=None, status=200):
    result = client.request(method, url, **({"json": payload} if payload is not None else {}))
    assert result.status_code == status, result.text
    return result.json()


def research(client):
    return request(client, "POST", "/api/researches", {"name": "Synthetic object research"})["id"]


def base(rid):
    return f"/api/researches/{rid}"


def protocol(client, rid):
    return request(client, "POST", base(rid) + "/protocols",
                   {"name": "Synthetic manual protocol", "origin": "lab", "expected_version": 0})


def edition_url(rid, p, v):
    return base(rid) + f"/protocols/{p['id']}/versions/{v['id']}"


def ready_protocol(client, rid):
    p = protocol(client, rid)
    v = request(client, "PATCH", edition_url(rid, p, p["latest"]),
                {"expected_version": 1, "total_days": 28})
    v = request(client, "POST", edition_url(rid, p, v) + "/confirm",
                {"expected_version": v["revision"]})
    return p, v


def run(client, rid, v, **changes):
    return request(client, "POST", base(rid) + "/runs", {
        "name": "Synthetic round", "protocol_version_id": v["id"],
        "expected_version": 0, "state": "differentiating", "start_date": "2026-10-01", **changes,
    })


def sample(client, rid, r, day=5, **changes):
    return request(client, "POST", base(rid) + f"/runs/{r['id']}/samples", {
        "expected_version": r["revision"], "day": day, "assay": "scRNA-seq", **changes,
    })


def test_empty_protocol_only_and_sample_workbenches_persist(client):
    rid = research(client)
    url = base(rid)
    empty = request(client, "GET", url + "/workbench")
    assert empty == {key: [] for key in ("protocols", "runs", "samples", "assessments", "leads", "actions")}
    p, v = ready_protocol(client, rid)
    listing = request(client, "GET", url + "/workbench")
    assert listing["protocols"][0]["latest"]["id"] == v["id"]
    assert listing["runs"] == []
    r = run(client, rid, v)
    s = sample(client, rid, r)
    listing = request(client, "GET", url + "/workbench")
    assert listing["runs"][0]["protocol_version_id"] == v["id"]
    assert listing["samples"][0]["id"] == s["id"]
    assert listing["samples"][0]["assessment_id"] is None
    assert s["assessment_request"] is None
    assert listing["samples"][0]["assessment_request"] is None
    assert listing["assessments"] == listing["actions"] == []
    service = client.app.state.service
    with TestClient(create_test_app(service.settings)) as restarted:
        login_test_account(restarted)
        assert request(restarted, "GET", url + "/workbench") == listing
    stored = json.loads((service.researches.directory(rid) / "objects.json").read_text())
    assert "day" not in stored["runs"][r["id"]]
    assert "today" not in stored["runs"][r["id"]]
    assert not (service.researches.directory(rid) / "materials").exists()


def test_version_label_is_shown_kept_through_edits_and_not_inherited(client, tmp_path):
    """A display name such as a published variant (Boost+) set on a stored version is returned and kept."""
    rid = research(client)
    p = protocol(client, rid)
    store = next((tmp_path / "objects").rglob(f"researches/{rid}/objects.json"))
    state = json.loads(store.read_text())
    vid = p["latest"]["id"]
    state["versions"][vid]["label"] = "Boost+"
    store.write_text(json.dumps(state))
    version = next(v for v in request(client, "GET", base(rid) + "/workbench")["protocols"][0]["versions"] if v["id"] == vid)
    assert version["label"] == "Boost+"
    edited = request(client, "PATCH", edition_url(rid, p, version), {"expected_version": version["revision"], "total_days": 28})
    assert edited["label"] == "Boost+"
    draft = request(client, "POST", base(rid) + f"/protocols/{p['id']}/versions",
                    {"expected_version": request(client, "GET", base(rid) + f"/protocols/{p['id']}")["revision"],
                     "based_on_version_id": vid, "changes": {}})
    assert "label" not in draft


def test_confirmed_version_cannot_change_and_run_stays_bound_to_old_edition(client):
    rid = research(client)
    p, v1 = ready_protocol(client, rid)
    r = run(client, rid, v1)
    old = request(client, "GET", base(rid) + f"/protocols/{p['id']}")
    request(client, "PATCH", edition_url(rid, p, v1),
            {"expected_version": v1["revision"], "total_days": 30}, status=409)
    request(client, "POST", edition_url(rid, p, v1) + "/confirm",
            {"expected_version": v1["revision"]}, status=409)
    v2 = request(client, "POST", base(rid) + f"/protocols/{p['id']}/versions", {
        "expected_version": old["revision"], "based_on_version_id": v1["id"],
        "changes": {"total_days": 35, "change_note": "A new manual edition"},
    })
    assert v2["version"] == 2 and v2["status"] == "draft"
    assert v2["confirmed_at"] is None and v2["based_on_version_id"] == v1["id"]
    listing = request(client, "GET", base(rid) + "/workbench")
    assert listing["runs"][0]["id"] == r["id"]
    assert listing["runs"][0]["protocol_version_id"] == v1["id"]
    assert listing["protocols"][0]["latest"]["id"] == v2["id"]
    assert listing["protocols"][0]["versions"][0] == v1
    request(client, "POST", base(rid) + "/runs", {
        "expected_version": 0, "protocol_version_id": v2["id"], "name": "Not confirmed", "state": "planned",
    }, status=409)


def test_unconfirmed_fields_and_unset_duration_block_confirmation(client):
    rid = research(client)
    p = protocol(client, rid)
    url = edition_url(rid, p, p["latest"])
    request(client, "POST", url + "/confirm", {"expected_version": 1}, status=409)
    v = request(client, "PATCH", url, {"expected_version": 1, "total_days": 28, "reagents": [{
        "name": "Synthetic factor", "short": "SF", "pathway": "other", "kind": "protein",
        "dose_text": "", "start_day": 0, "end_day": 4, "catalog_id": None, "unconfirmed": ["dose_text"],
    }]})
    assert len(v["reagents"][0]["id"]) == 32
    request(client, "POST", url + "/confirm", {"expected_version": v["revision"]}, status=409)
    checked = {**v["reagents"][0], "dose_text": "recorded synthetic dose", "unconfirmed": []}
    v = request(client, "PATCH", url, {"expected_version": v["revision"], "reagents": [checked]})
    confirmed = request(client, "POST", url + "/confirm", {"expected_version": v["revision"]})
    assert confirmed["status"] == "confirmed" and confirmed["confirmed_at"]
    assert confirmed["provenance"] == {"material_id": None, "formalization_version_id": None}


def test_stale_revision_loses_race_without_partial_writes(client):
    rid = research(client)
    p = protocol(client, rid)
    url = edition_url(rid, p, p["latest"])
    with ThreadPoolExecutor(max_workers=2) as pool:
        replies = list(pool.map(lambda days: client.patch(url, json={"expected_version": 1, "total_days": days}), (20, 40)))
    assert sorted(r.status_code for r in replies) == [200, 409]
    winner = next(r.json() for r in replies if r.status_code == 200)
    current = request(client, "GET", base(rid) + f"/protocols/{p['id']}")
    assert current["latest"] == winner
    assert current["revision"] == 2
    stale = request(client, "POST", base(rid) + f"/protocols/{p['id']}/versions", {
        "expected_version": 1, "based_on_version_id": winner["id"], "changes": {},
    }, status=409)
    assert stale["detail"] == "object_version_conflict"
    assert len(request(client, "GET", base(rid) + f"/protocols/{p['id']}")["versions"]) == 1


@pytest.mark.parametrize("day, stage, labels", [
    ("2026-10-01", 1, ["加入 SF"]),
    ("2026-10-05", 1, []),
    ("2026-10-06", 2, ["撤除 SF", "换液：Synthetic feed"]),
    ("2026-10-11", 2, []),
    ("2026-10-12", 3, []),
    ("2026-10-17", 3, []),
    ("2026-10-18", 4, []),
    ("2026-09-30", None, []),
    ("2026-10-30", None, []),
])
def test_calendar_derived_stages_and_inclusive_reagent_windows(client, monkeypatch, day, stage, labels):
    # Boundary cases are hand-derived from the published day windows.
    rid = research(client)
    p = protocol(client, rid)
    url = edition_url(rid, p, p["latest"])
    v = request(client, "PATCH", url, {"expected_version": 1, "total_days": 28, "reagents": [{
        "name": "Synthetic factor", "short": "SF", "pathway": "other", "kind": "protein",
        "dose_text": "synthetic dose", "start_day": 0, "end_day": 4, "catalog_id": None,
    }], "operations": [{"day": 5, "kind": "feed", "note": "Synthetic feed"}]})
    v = request(client, "POST", url + "/confirm", {"expected_version": v["revision"]})
    run(client, rid, v)
    monkeypatch.setattr("bridge.web.research_objects.local_today", lambda: date.fromisoformat(day))
    view = request(client, "GET", base(rid) + "/workbench")["runs"][0]
    assert view["stage_index"] == stage
    assert [item["label"] for item in view["today"]] == labels


def test_custom_stages_null_dates_and_frozen_rounds(client, monkeypatch):
    rid = research(client)
    p = protocol(client, rid)
    url = edition_url(rid, p, p["latest"])
    v = request(client, "PATCH", url, {"expected_version": 1, "total_days": 28,
        "stages": [{"index": 1, "start_day": 0, "end_day": 8}, {"index": 2, "start_day": 9, "end_day": 28}]})
    v = request(client, "POST", url + "/confirm", {"expected_version": v["revision"]})
    monkeypatch.setattr("bridge.web.research_objects.local_today", lambda: date(2026, 10, 8))
    r = run(client, rid, v)
    assert r["day"] == 7 and r["stage_index"] == 1
    frozen = request(client, "PATCH", base(rid) + f"/runs/{r['id']}",
                     {"expected_version": r["revision"], "state": "frozen"})
    assert frozen["day"] == 7 and frozen["stage_index"] is None and frozen["today"] == []
    undated = run(client, rid, v, start_date=None, state="planned")
    assert undated["day"] is None and undated["stage_index"] is None


def test_assessment_request_and_decision_do_not_execute_or_invent_results(client):
    rid = research(client)
    _, v = ready_protocol(client, rid)
    r = run(client, rid, v)
    s = sample(client, rid, r)
    url = base(rid)
    action = request(client, "POST", url + f"/samples/{s['id']}/assessments", {"expected_version": 1})
    assert action["kind"] == "atlas_assessment" and action["status"] == "pending"
    assert action["result_ref"] is None
    before = request(client, "GET", url + "/workbench")
    assert before["actions"] == [action] and before["assessments"] == []
    assert before["samples"][0]["assessment_id"] is None
    request(client, "POST", url + f"/samples/{s['id']}/assessments", {"expected_version": 2}, status=409)
    request(client, "POST", url + f"/actions/{action['id']}/approve", {"expected_version": 9}, status=409)
    approved = request(client, "POST", url + f"/actions/{action['id']}/approve", {})
    assert approved["status"] == "approved" and approved["result_ref"] is None
    for decision in ("approve", "decline"):
        request(client, "POST", url + f"/actions/{action['id']}/{decision}", {}, status=409)
    after = request(client, "GET", url + "/workbench")
    assert after["actions"] == after["assessments"] == []
    assert before["samples"][0]["assessment_request"] == {"action_id": action["id"], "status": "pending"}
    assert after["samples"][0]["assessment_request"] == {"action_id": action["id"], "status": "approved"}
    assert after["samples"][0]["assessment_id"] is None
    assert after["samples"][0]["revision"] == before["samples"][0]["revision"]
    duplicate = request(client, "POST", url + f"/samples/{s['id']}/assessments", {"expected_version": 2}, status=409)
    assert duplicate["detail"] == "assessment_request_active"
    with TestClient(create_test_app(client.app.state.service.settings)) as restarted:
        login_test_account(restarted)
        assert request(restarted, "GET", url + "/workbench")["samples"] == after["samples"]
    assert request(client, "GET", "/api/sessions")["sessions"] == []
    missing = request(client, "GET", url + "/assessments/" + "f" * 32, status=404)
    assert missing["detail"] == "assessment_not_found"


def test_decline_can_be_followed_by_new_request(client):
    rid = research(client)
    _, v = ready_protocol(client, rid)
    s = sample(client, rid, run(client, rid, v))
    url = base(rid)
    action = request(client, "POST", url + f"/samples/{s['id']}/assessments", {"expected_version": 1})
    request(client, "POST", url + f"/actions/{action['id']}/decline", {})
    assert request(client, "GET", url + "/workbench")["samples"][0]["assessment_request"] == {"action_id": action["id"], "status": "declined"}
    again = request(client, "POST", url + f"/samples/{s['id']}/assessments", {"expected_version": 2})
    assert again["id"] != action["id"]
    assert request(client, "GET", url + "/workbench")["samples"][0]["assessment_request"] == {"action_id": again["id"], "status": "pending"}


def test_foreign_research_objects_are_hidden_even_from_admin(tmp_path):
    with multi_clients(tmp_path) as (_, alice, bob, admin):
        rid = research(alice)
        p, v = ready_protocol(alice, rid)
        r = run(alice, rid, v)
        s = sample(alice, rid, r)
        a = request(alice, "POST", base(rid) + f"/samples/{s['id']}/assessments", {"expected_version": 1})
        calls = [
            ("GET", "/workbench", None), ("GET", f"/protocols/{p['id']}", None),
            ("POST", "/protocols", {"name": "intrusion", "origin": "lab", "expected_version": 0}),
            ("PATCH", f"/runs/{r['id']}", {"state": "ended", "expected_version": 2}),
            ("POST", f"/runs/{r['id']}/samples", {"day": 3, "assay": "scRNA-seq", "expected_version": 2}),
            ("POST", f"/actions/{a['id']}/approve", {}),
        ]
        for other in (bob, admin):
            for method, suffix, payload in calls:
                result = request(other, method, base(rid) + suffix, payload, status=404)
                assert result["detail"] == "research_not_found"
                assert "Synthetic" not in json.dumps(result)
        # Same account, wrong research is forbidden too.
        second = research(alice)
        request(alice, "POST", base(second) + "/runs", {
            "expected_version": 0, "protocol_version_id": v["id"], "name": "wrong", "state": "planned",
        }, status=404)
        request(alice, "GET", base(second) + f"/protocols/{p['id']}", status=404)


@pytest.mark.parametrize("changes", [
    {"expected_version": None}, {"expected_version": True}, {"expected_version": "1"},
    {"status": "confirmed"}, {"provenance": {"material_id": "f" * 32}},
    {"total_days": -1}, {"total_days": True}, {"operations": [{"day": -1, "kind": "feed", "note": ""}]},
    {"stages": [{"index": 1, "start_day": 0, "end_day": 5}, {"index": 2, "start_day": 5, "end_day": 8}]},
])
def test_invalid_or_forged_drafts_never_mutate_state(client, changes):
    rid = research(client)
    p = protocol(client, rid)
    request(client, "PATCH", edition_url(rid, p, p["latest"]),
            {"expected_version": 1, **changes}, status=422)
    assert request(client, "GET", base(rid) + f"/protocols/{p['id']}") == p


def test_material_references_stay_in_research_and_do_not_copy_bytes(client, tmp_path):
    from web_support import h5ad
    rid = research(client)
    foreign = research(client)
    _, v = ready_protocol(client, rid)
    r = run(client, rid, v)
    def upload(where, name, raw):
        response = client.post(base(where) + "/uploads", files={"file": (name, raw)})
        assert response.status_code == 200, response.text
        return response.json()["id"]
    text = upload(rid, "synthetic.txt", b"Synthetic protocol")
    other = upload(foreign, "synthetic.h5ad", h5ad(tmp_path))
    for mid, status in ((text, 422), (other, 404)):
        request(client, "POST", base(rid) + f"/runs/{r['id']}/samples", {
            "expected_version": 1, "day": 2, "assay": "scRNA-seq", "material_id": mid,
        }, status=status)
    mid = upload(rid, "synthetic.h5ad", h5ad(tmp_path))
    directory = client.app.state.service.researches.directory(rid)
    files_before = sorted(str(p.relative_to(directory)) for p in directory.rglob("*"))
    s = sample(client, rid, r, material_id=mid)
    assert s["material_id"] == mid and s["session_id"] is not None
    assert s["workflow"]["status"] == "needs_input"
    assert sorted(str(p.relative_to(directory)) for p in directory.rglob("*")) == files_before
    request(client, "POST", base(rid) + "/protocols", {"expected_version": 0, "material_id": mid}, status=422)


def test_lead_resolution_is_persistent_and_never_crosses_research(client):
    rid = research(client)
    _, v = ready_protocol(client, rid)
    r = run(client, rid, v)
    s = sample(client, rid, r)
    store = client.app.state.service.research_objects
    owner = request(client, "GET", "/api/me")["user"]["id"]
    lead = store.create_lead(owner, rid, run_id=r["id"], sample_id=s["id"], chain_level=3,
                             summary="Synthetic follow-up", created_by="system")
    assert request(client, "GET", base(rid) + "/workbench")["leads"] == [lead]
    request(client, "PATCH", base(rid) + f"/leads/{lead['id']}",
            {"expected_version": 4, "status": "resolved"}, status=409)
    resolved = request(client, "PATCH", base(rid) + f"/leads/{lead['id']}",
                        {"expected_version": 1, "status": "resolved"})
    assert resolved["status"] == "resolved" and resolved["revision"] == 2
    assert request(client, "GET", base(rid) + "/workbench")["leads"] == []


def test_conflicting_decisions_are_atomic(client):
    rid = research(client)
    _, v = ready_protocol(client, rid)
    s = sample(client, rid, run(client, rid, v))
    a = request(client, "POST", base(rid) + f"/samples/{s['id']}/assessments", {"expected_version": 1})
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda decision: client.post(
            base(rid) + f"/actions/{a['id']}/{decision}", json={}), ("approve", "decline")))
    assert sorted(r.status_code for r in responses) == [200, 409]
    winner = next(r.json() for r in responses if r.status_code == 200)
    service = client.app.state.service
    persisted = json.loads((service.researches.directory(rid) / "objects.json").read_text())
    assert persisted["actions"][a["id"]]["status"] == winner["status"]
    assert persisted["actions"][a["id"]]["revision"] == 2
    assert persisted["assessments"] == {}


def test_all_sampling_days_are_returned_and_parent_revision_protects_append(client):
    rid = research(client)
    _, v = ready_protocol(client, rid)
    r = run(client, rid, v)
    first = sample(client, rid, r, day=10)
    request(client, "POST", base(rid) + f"/runs/{r['id']}/samples",
            {"expected_version": 1, "day": 7, "assay": "scRNA-seq"}, status=409)
    r = request(client, "GET", base(rid) + "/workbench")["runs"][0]
    second = sample(client, rid, r, day=5)
    view = request(client, "GET", base(rid) + "/workbench")
    assert [s["id"] for s in view["samples"]] == [second["id"], first["id"]]
    assert view["runs"][0]["revision"] == 3
    assert [s["day"] for s in view["samples"]] == [5, 10]


def test_unknown_catalog_links_are_not_silently_accepted(client, monkeypatch, tmp_path):
    rid = research(client)
    p = protocol(client, rid)
    url = edition_url(rid, p, p["latest"])
    reagent = {"name": "CHIR99021", "short": "CHIR", "pathway": "wnt", "kind": "molecule",
               "dose_text": "synthetic dose", "start_day": 0, "end_day": 4, "catalog_id": "invented-reagent"}
    bad = request(client, "PATCH", url, {"expected_version": 1, "total_days": 28, "reagents": [reagent]}, status=422)
    assert bad["detail"] == "reagent_catalog_id_unknown"
    good = request(client, "PATCH", url, {"expected_version": 1, "total_days": 28,
                                        "reagents": [{**reagent, "catalog_id": "chir99021"}]})
    assert good["reagents"][0]["catalog_id"] == "chir99021"
    monkeypatch.setattr("bridge.web.research_objects.CATALOG_PATH", tmp_path / "absent-catalog.json")
    request(client, "PATCH", url, {"expected_version": 2, "change_note": "unavailable catalog"}, status=409)
    unlinked = request(client, "PATCH", url, {"expected_version": 2,
                          "reagents": [{**good["reagents"][0], "catalog_id": None}]})
    assert unlinked["reagents"][0]["catalog_id"] is None


@pytest.mark.parametrize("corruption", ["malformed", "future-schema", "symlink"])
def test_invalid_store_is_never_reset_to_empty_or_followed(client, tmp_path, corruption):
    from bridge.web.sessions import write_file
    rid = research(client)
    p = protocol(client, rid)
    service = client.app.state.service
    target = service.researches.directory(rid) / "objects.json"
    original = target.read_bytes()
    if corruption == "malformed":
        write_file(target, b"{bad json")
    elif corruption == "future-schema":
        state = json.loads(original)
        state["schema_version"] = 999
        write_file(target, json.dumps(state).encode())
    else:
        elsewhere = tmp_path / "private-original.json"
        elsewhere.write_bytes(original)
        target.unlink()
        target.symlink_to(elsewhere)
    error = request(client, "GET", base(rid) + "/workbench", status=409)
    assert error["detail"] == "object_store_unavailable"
    request(client, "PATCH", edition_url(rid, p, p["latest"]),
            {"expected_version": 1, "total_days": 28}, status=409)
    if corruption == "symlink":
        assert target.is_symlink() and elsewhere.read_bytes() == original
    elif corruption == "malformed":
        assert target.read_bytes() == b"{bad json"
    else:
        assert json.loads(target.read_bytes())["schema_version"] == 999


def test_atomic_write_failure_preserves_previous_version(client, monkeypatch):
    import bridge.web.sessions as sessions
    rid = research(client)
    p = protocol(client, rid)
    target = client.app.state.service.researches.directory(rid) / "objects.json"
    before = target.read_bytes()
    replace = sessions.os.replace
    def fail_object_replace(source, destination):
        if destination == target:
            raise OSError("synthetic write failure")
        return replace(source, destination)
    with monkeypatch.context() as patch:
        patch.setattr(sessions.os, "replace", fail_object_replace)
        failed = request(client, "PATCH", edition_url(rid, p, p["latest"]),
                         {"expected_version": 1, "total_days": 28}, status=500)
    assert "synthetic write failure" not in json.dumps(failed)
    assert target.read_bytes() == before
    assert request(client, "GET", base(rid) + f"/protocols/{p['id']}") == p
    assert not list(target.parent.glob("*.tmp"))
    assert target.stat().st_mode & 0o777 == 0o600


def test_store_limit_failure_does_not_add_partial_protocol(client, monkeypatch):
    rid = research(client)
    p = protocol(client, rid)
    monkeypatch.setattr("bridge.web.research_objects.OBJECT_COUNT_LIMIT", 3)
    request(client, "POST", base(rid) + "/protocols",
            {"name": "Will not fit both objects", "origin": "lab", "expected_version": 0}, status=409)
    assert request(client, "GET", base(rid) + "/workbench")["protocols"] == [p]


def test_authentication_origin_and_missing_resource_errors(client):
    rid = research(client)
    p = protocol(client, rid)
    _, v = ready_protocol(client, rid)
    r = run(client, rid, v)
    # A version from another protocol cannot be addressed through p.
    request(client, "PATCH", edition_url(rid, p, v),
            {"expected_version": v["revision"], "total_days": 29}, status=404)
    missing = request(client, "GET", base("f" * 32) + "/workbench", status=404)
    assert missing["detail"] == "research_not_found"
    request(client, "PATCH", base(rid) + f"/runs/{r['id']}", {"state": "ended"}, status=422)
    request(client, "PATCH", base(rid) + f"/runs/{r['id']}",
            {"expected_version": 1, "protocol_version_id": p["latest"]["id"]}, status=422)
    denied = client.post(base(rid) + "/protocols", json={
        "expected_version": 0, "name": "Cross origin", "origin": "lab",
    }, headers={"Origin": "https://foreign.invalid"})
    assert denied.status_code == 403
    client.cookies.clear()
    request(client, "GET", base(rid) + "/workbench", status=401)


def uploaded_sample_material(client, rid, tmp_path):
    from web_support import h5ad
    response = client.post(base(rid) + "/uploads", files={"file": ("synthetic.h5ad", h5ad(tmp_path))})
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_attach_sample_material_persists_without_false_mapping(client, tmp_path):
    rid = research(client)
    _, v = ready_protocol(client, rid)
    s = sample(client, rid, run(client, rid, v))
    assert s["status"] == "collected" and s["assessment_availability"] is None
    mid = uploaded_sample_material(client, rid, tmp_path)
    directory = client.app.state.service.researches.directory(rid)
    before = sorted(str(p.relative_to(directory)) for p in directory.rglob("*"))
    attached = request(client, "PATCH", base(rid) + f"/samples/{s['id']}",
                       {"expected_version": 1, "material_id": mid})
    assert attached["revision"] == 2 and attached["status"] == "data_attached"
    assert attached["material_id"] == mid and attached["assessment_id"] is None
    assert attached["assessment_availability"] == {"status": "unavailable", "code": "standard_mapping_not_configured"}
    assert sorted(str(p.relative_to(directory)) for p in directory.rglob("*")) == before
    from test_sample_workflow import wait_workflow
    attached = wait_workflow(client, rid, s["id"])
    with TestClient(create_test_app(client.app.state.service.settings)) as restarted:
        login_test_account(restarted)
        wb = request(restarted, "GET", base(rid) + "/workbench")
        assert wb["samples"] == [attached]
        assert wb["assessments"] == wb["actions"] == []
    assert request(client, "PATCH", base(rid) + f"/samples/{s['id']}",
                   {"expected_version": 2, "material_id": mid}, status=409)["detail"] == "sample_has_material"


def test_sample_attachment_rejects_foreign_corrupt_and_missing_files(client, tmp_path):
    rid = research(client)
    _, v = ready_protocol(client, rid)
    s = sample(client, rid, run(client, rid, v))
    url = base(rid) + f"/samples/{s['id']}"
    foreign = uploaded_sample_material(client, research(client), tmp_path)
    assert request(client, "PATCH", url, {"expected_version": 1, "material_id": foreign}, status=404)["detail"] == "material_not_found"
    text = client.post(base(rid) + "/uploads", files={"file": ("synthetic.txt", b"text")}).json()["id"]
    assert request(client, "PATCH", url, {"expected_version": 1, "material_id": text}, status=422)["detail"] == "sample_material_requires_h5ad"
    mid = uploaded_sample_material(client, rid, tmp_path)
    path = client.app.state.service.researches.directory(rid) / "materials" / (mid + ".bin")
    path.write_bytes(b"changed")
    for missing in (False, True):
        if missing:
            path.unlink()
        assert request(client, "PATCH", url, {"expected_version": 1, "material_id": mid}, status=409)["detail"] == "research_material_unavailable"
    assert request(client, "GET", base(rid) + "/workbench")["samples"] == [s]


def test_concurrent_sample_attachment_has_single_winner(client, tmp_path):
    rid = research(client)
    _, v = ready_protocol(client, rid)
    s = sample(client, rid, run(client, rid, v))
    mids = [uploaded_sample_material(client, rid, tmp_path) for _ in range(2)]
    url = base(rid) + f"/samples/{s['id']}"
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda mid: client.patch(url, json={"expected_version": 1, "material_id": mid}), mids))
    assert sorted(r.status_code for r in responses) == [200, 409]
    winner = next(r.json() for r in responses if r.status_code == 200)
    assert request(client, "GET", base(rid) + "/workbench")["samples"] == [winner]


def test_sample_attachment_hides_foreign_research(tmp_path):
    with multi_clients(tmp_path) as (_, alice, bob, admin):
        rid = research(alice)
        _, v = ready_protocol(alice, rid)
        s = sample(alice, rid, run(alice, rid, v))
        mid = uploaded_sample_material(alice, rid, tmp_path)
        for client in (bob, admin):
            assert request(client, "PATCH", base(rid) + f"/samples/{s['id']}",
                           {"expected_version": 1, "material_id": mid}, status=404)["detail"] == "research_not_found"


def test_legacy_sample_status_is_derived_and_scope_is_not_ignored(client, tmp_path):
    rid = research(client)
    _, v = ready_protocol(client, rid)
    mid = uploaded_sample_material(client, rid, tmp_path)
    s = sample(client, rid, run(client, rid, v), material_id=mid)
    assert s["status"] == "data_attached"
    request(client, "PATCH", base(rid) + f"/samples/{s['id']}",
            {"expected_version": s["revision"], "material_id": mid, "scope": {"obs_column": "sample", "value": "A"}}, status=422)
    stored = json.loads((client.app.state.service.researches.directory(rid) / "objects.json").read_text())
    assert "status" not in stored["samples"][s["id"]]
    assert request(client, "GET", base(rid) + "/workbench")["samples"] == [s]

@pytest.mark.parametrize("start,end", [(None, 4), (0, None), (None, None)])
def test_unknown_reagent_days_persist_but_block_confirmation_and_run(client, start, end):
    rid = research(client)
    p = protocol(client, rid)
    url = edition_url(rid, p, p["latest"])
    v = request(client, "PATCH", url, {"expected_version": 1, "total_days": 28, "reagents": [{
        "name": "Synthetic factor", "short": "SF", "pathway": "other", "kind": "protein",
        "dose_text": "synthetic dose", "start_day": start, "end_day": end,
    }]})
    restored = request(client, "GET", base(rid) + "/workbench")["protocols"][0]["latest"]
    assert restored["reagents"][0]["start_day"] == start
    assert restored["reagents"][0]["end_day"] == end
    failure = request(client, "POST", url + "/confirm", {"expected_version": v["revision"]}, status=409)
    assert failure["detail"] == "protocol_incomplete"
    request(client, "POST", base(rid) + "/runs", {"name": "Blocked", "protocol_version_id": v["id"],
            "state": "differentiating", "expected_version": 0}, status=409)
    for window in ((29, None), (None, 29), (5, 4)):
        request(client, "PATCH", url, {"expected_version": v["revision"], "reagents": [
            {**v["reagents"][0], "start_day": window[0], "end_day": window[1]}]}, status=422)
    v = request(client, "PATCH", url, {"expected_version": v["revision"], "reagents": [
        {**v["reagents"][0], "start_day": 0, "end_day": 4}]})
    v = request(client, "POST", url + "/confirm", {"expected_version": v["revision"]})
    assert run(client, rid, v)["protocol_version_id"] == v["id"]
