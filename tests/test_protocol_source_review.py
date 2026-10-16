"""Source verification must never silently authorize an incomplete recipe."""
import json

import pytest

from fastapi.testclient import TestClient

from account_support import create_test_app, login_test_account
from test_research_objects import client, request, research, base, edition_url


def literature(client, rid):
    p = request(client, "POST", base(rid) + "/protocols", {
        "name": "Synthetic published protocol", "origin": "literature", "expected_version": 0,
        "citation": {"title": "Synthetic source", "doi": "10.0000/synthetic"},
    })
    url = edition_url(rid, p, p["latest"])
    v = request(client, "PATCH", url, {"expected_version": 1, "total_days": None,
        "unconfirmed": ["source_review", "total_days"], "reagents": [{
            "name": "Synthetic factor", "short": "SF", "pathway": "other", "kind": "protein",
            "dose_text": "20 ng/mL", "start_day": 11, "end_day": None,
            "timing_text": "After replating until the assay",
            "field_provenance": [{"field": "dose_text", "kind": "recipe_reference",
                "source_ref": "doi:10.0000/synthetic", "source_locator": "Methods, day 11",
                "recipe_locator": "Methods, day 10 medium"}],
        }], "operations": [{"day": None, "kind": "passage", "note": "After maturation",
                              "timing_text": "After maturation", "source_locator": "Methods"}]})
    return p, v, url


def review(client, url, v):
    return request(client, "POST", url + "/source-review", {
        "expected_version": v["revision"], "note": "Source checked; endpoint and operation day remain unknown."})


def test_reviewed_incomplete_recipe_allows_only_explicit_retrospective_samples(client):
    rid = research(client)
    p, v, url = literature(client, rid)
    payload = {"expected_version": 0, "protocol_version_id": v["id"], "name": "Historical round",
               "state": "differentiating", "start_date": "2026-10-01", "purpose": "retrospective"}
    assert request(client, "POST", base(rid) + "/runs", payload, 409)["detail"] == "protocol_source_not_reviewed"
    v = review(client, url, v)
    assert v["source_review"]["status"] == "reviewed" and v["source_review"]["reviewed_at"]
    assert v["status"] == "draft" and v["total_days"] is None
    assert v["unconfirmed"] == ["total_days"]
    assert v["execution_readiness"]["status"] == "incomplete"
    assert request(client, "POST", url + "/confirm", {"expected_version": v["revision"]}, 409)["detail"] == "protocol_incomplete"
    request(client, "POST", base(rid) + "/runs", {k: val for k, val in payload.items() if k != "purpose"}, 409)
    r = request(client, "POST", base(rid) + "/runs", payload)
    assert r["purpose"] == "retrospective" and r["day"] is None
    assert r["stage_index"] is None and r["today"] == []
    s = request(client, "POST", base(rid) + f"/runs/{r['id']}/samples", {
        "expected_version": r["revision"], "day": 60, "assay": "scRNA-seq"})
    assert s["day"] == 60 and s["status"] == "collected" and s["assessment_id"] is None
    request(client, "PATCH", base(rid) + f"/runs/{r['id']}", {"expected_version": 2, "purpose": "execution"}, 422)
    with TestClient(create_test_app(client.app.state.service.settings)) as restarted:
        login_test_account(restarted)
        board = request(restarted, "GET", base(rid) + "/workbench")
        assert board["protocols"][0]["latest"] == v
        assert board["samples"][0]["day"] == 60 and board["runs"][0]["today"] == []


def test_review_freezes_content_and_new_version_requires_new_review(client):
    rid = research(client)
    p, v, url = literature(client, rid)
    v = review(client, url, v)
    for method, suffix, body in [("PATCH", "", {"total_days": 60}), ("POST", "/source-review", {"note": "Again"})]:
        assert request(client, method, url + suffix, {"expected_version": v["revision"], **body}, 409)["detail"] == "protocol_version_immutable"
    current = request(client, "GET", base(rid) + f"/protocols/{p['id']}")
    child = request(client, "POST", base(rid) + f"/protocols/{p['id']}/versions", {
        "expected_version": current["revision"], "based_on_version_id": v["id"], "changes": {"total_days": 60}})
    assert child["source_review"]["status"] == "pending"
    assert child["reagents"][0]["field_provenance"] == v["reagents"][0]["field_provenance"]
    request(client, "POST", url + "/source-review", {"expected_version": 1, "note": "Stale"}, 409)


@pytest.mark.parametrize("change", ["dose", "new_row_identity", "reagent_name"])
def test_changed_value_cannot_reuse_inherited_evidence_silently(client, change):
    rid = research(client)
    p, v, url = literature(client, rid)
    changed = {**v["reagents"][0], "dose_text": "40 ng/mL"}
    if change == "new_row_identity":
        changed.pop("id")
    if change == "reagent_name":
        changed.update(name="Another factor", dose_text="20 ng/mL")
    request(client, "PATCH", url, {"expected_version": v["revision"], "reagents": [changed]}, 422)
    assert request(client, "GET", base(rid) + f"/protocols/{p['id']}")["latest"] == v
    changed["field_provenance"] = []
    updated = request(client, "PATCH", url, {"expected_version": v["revision"], "reagents": [changed]})
    assert updated["reagents"][0]["dose_text"] == changed["dose_text"]
    assert updated["reagents"][0]["field_provenance"] == []


def test_recipe_reference_requires_locator_and_known_value(client):
    rid = research(client)
    _, v, url = literature(client, rid)
    for change in ({"recipe_locator": None}, {"field": "end_day"}):
        reagent = {**v["reagents"][0], "field_provenance": [{**v["reagents"][0]["field_provenance"][0], **change}]}
        request(client, "PATCH", url, {"expected_version": v["revision"], "reagents": [reagent]}, 422)
    request(client, "PATCH", url, {"expected_version": v["revision"], "source_review": {"status": "reviewed"}}, 422)


def test_unknown_operation_blocks_execution_even_after_flags_are_cleared(client):
    rid = research(client)
    _, v, url = literature(client, rid)
    r = {**v["reagents"][0], "end_day": 16}
    v = request(client, "PATCH", url, {"expected_version": v["revision"], "total_days": 60,
                                      "unconfirmed": [], "reagents": [r]})
    request(client, "POST", url + "/confirm", {"expected_version": v["revision"]}, 409)
    v = request(client, "PATCH", url, {"expected_version": v["revision"], "operations": []})
    v = review(client, url, v)
    assert v["execution_readiness"]["status"] == "ready"
    v = request(client, "POST", url + "/confirm", {"expected_version": v["revision"]})
    assert v["status"] == "confirmed" and v["source_review"]["status"] == "reviewed"


def test_legacy_zero_remains_unknown_without_manufacturing_source_review(client):
    rid = research(client)
    p, v, _ = literature(client, rid)
    path = client.app.state.service.researches.directory(rid) / "objects.json"
    state = json.loads(path.read_text())
    state["versions"][v["id"]]["total_days"] = 0
    state["versions"][v["id"]].pop("source_review", None)
    path.write_text(json.dumps(state))
    legacy = request(client, "GET", base(rid) + f"/protocols/{p['id']}")["latest"]
    assert legacy["total_days"] is None and legacy["source_review"]["status"] == "pending"


def test_source_review_cannot_cross_accounts_or_exist_without_a_source(tmp_path):
    from multiuser_support import multi_clients
    from test_research_objects import protocol
    with multi_clients(tmp_path) as (_, alice, bob, admin):
        rid = research(alice)
        p, v, url = literature(alice, rid)
        for outsider in (bob, admin):
            assert request(outsider, "POST", url + "/source-review", {
                "expected_version": v["revision"], "note": "Intrusion"}, 404)["detail"] == "research_not_found"
        request(alice, "POST", url + "/source-review", {"expected_version": v["revision"], "note": " "}, 422)
        manual = protocol(alice, rid)
        request(alice, "POST", edition_url(rid, manual, manual["latest"]) + "/source-review", {
            "expected_version": 1, "note": "No source"}, 409)
        assert request(alice, "GET", base(rid) + f"/protocols/{p['id']}")["latest"] == v


def test_retrospective_data_attachment_and_context_keep_independent_gates(client, tmp_path):
    from bridge.web.workbench_context import build_workbench_context
    from model_wire_contract import assert_model_context
    from web_support import h5ad
    rid = research(client)
    _, v, url = literature(client, rid)
    v = review(client, url, v)
    r = request(client, "POST", base(rid) + "/runs", {
        "expected_version": 0, "name": "Historical", "protocol_version_id": v["id"],
        "purpose": "retrospective", "state": "ended"})
    s = request(client, "POST", base(rid) + f"/runs/{r['id']}/samples", {
        "expected_version": 1, "day": 60, "assay": "scRNA-seq"})
    uploaded = client.post(base(rid) + "/uploads", files={"file": ("synthetic.h5ad", h5ad(tmp_path))})
    assert uploaded.status_code == 200
    s = request(client, "PATCH", base(rid) + f"/samples/{s['id']}", {
        "expected_version": s["revision"], "material_id": uploaded.json()["id"]})
    assert s["status"] == "data_attached" and s["assessment_id"] is None
    assert s["assessment_availability"]["code"] == "standard_mapping_not_configured"
    service = client.app.state.service
    owner = request(client, "GET", "/api/me")["user"]["id"]
    snapshot = build_workbench_context(service.researches, service.research_objects, {
        "owner_id": owner, "research_id": rid, "run_id": r["id"], "conversation_kind": "run"})
    assert_model_context("workbench", snapshot)
    assert snapshot["runs"][0]["purpose"] == "retrospective"
    pv = snapshot["protocol_versions"][0]
    assert pv["source_review"] == {"status": "reviewed"}
    assert pv["execution_readiness"]["status"] == "incomplete" and pv["total_days"] is None
    assert pv["reagents"][0]["timing_text"] == "After replating until the assay"
    assert "source_locator" not in json.dumps(snapshot) and "recipe_locator" not in json.dumps(snapshot)
    assert "Source checked; endpoint" not in json.dumps(snapshot)
