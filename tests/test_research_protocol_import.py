"""Synthetic document import through the authenticated research API."""
import json
from dataclasses import replace

import pytest

from bridge.web import protocol_formalization as pf
from test_research_objects import client, research, base, request, edition_url
from test_web_protocol_formalization import bpl_python

pf_generate = pf.generate

TEXT = "Days 0 to 4: culture with CHIR99021 at 2 uM. On day 5, passage cells. Total duration 5 days."


@pytest.fixture
def imported(client, monkeypatch, bpl_python):
    service = client.app.state.service
    service.settings = replace(service.settings, protocol_compiler_python=bpl_python)
    payload = {
        "steps": [
            {"id": "culture", "label": "培养", "operations": "Days 0 to 4: CHIR99021 2 uM", "source_ids": ["S1"],
             "bpl_fragment": 'culture(factors: {"CHIR99021": 2 uM}, timing: "Days 0 to 4")'},
            {"id": "passage", "label": "传代", "operations": "On day 5, passage cells", "source_ids": ["S1"],
             "bpl_fragment": 'passage(timing: "On day 5")'},
        ], "questions": [], "excluded_sources": [],
        "content": {"total_days": {"value": 5, "quote": "Total duration 5 days.", "source_ids": ["S1"]},
                    "stages": [{"start_day": 0, "end_day": 4, "quote": TEXT, "source_ids": ["S1"]}],
                    "reagents": [{"name": "CHIR99021", "dose_text": "2 uM", "start_day": 0, "end_day": 4,
                                  "quote": TEXT, "source_ids": ["S1"]}],
                    "operations": [{"day": 5, "kind": "passage", "note": "On day 5, passage cells.",
                                    "quote": TEXT, "source_ids": ["S1"]}]},
    }
    def generate(settings, context, **kwargs):
        proposal = kwargs["proposal_model"].model_validate(payload)
        draft = pf._assemble_draft(proposal)
        draft._proposal = proposal.model_dump(mode="json")
        return draft
    monkeypatch.setattr(pf, "generate", generate)
    rid = research(client)
    response = client.post(base(rid) + "/uploads", files={"file": ("synthetic.txt", TEXT.encode())})
    assert response.status_code == 200
    return rid, response.json()["id"], payload


def do_import(client, imported, status=200):
    rid, mid, _ = imported
    return request(client, "POST", base(rid) + "/protocols", {"material_id": mid, "expected_version": 0}, status)


def test_import_persists_source_bound_draft_without_dataset(client, imported):
    p = do_import(client, imported)
    v = p["latest"]
    assert v["status"] == "draft" and v["confirmed_at"] is None
    assert v["total_days"] == 5 and v["stages"][0]["end_day"] == 4
    reagent = v["reagents"][0]
    assert (reagent["name"], reagent["dose_text"], reagent["start_day"], reagent["end_day"]) == ("CHIR99021", "2 uM", 0, 4)
    assert reagent["catalog_id"] == "chir99021" and reagent["source_locator"]
    assert reagent["unconfirmed"] and v["unconfirmed"]
    assert v["operations"][0]["day"] == 5
    url = edition_url(imported[0], p, v)
    request(client, "POST", url + "/confirm", {"expected_version": 1}, status=409)
    source = request(client, "GET", url + "/formalization")
    assert source["id"] == v["provenance"]["formalization_version_id"]
    assert source["steps"][0]["sources"][0]["text"] == TEXT
    assert source["compiler_state"] == "passed"
    assert "provider_response" not in json.dumps(source)
    assert request(client, "GET", base(imported[0]) + "/workbench")["protocols"][0] == p


def test_missing_fields_are_not_filled_from_catalog(client, imported):
    imported[2]["content"]["reagents"][0].update(dose_text=None, start_day=None, end_day=None)
    imported[2]["content"]["total_days"] = None
    imported[2]["content"]["operations"][0]["day"] = None
    v = do_import(client, imported)["latest"]
    assert v["total_days"] is None and v["operations"][0]["day"] is None
    assert v["operations"][0]["note"] == "On day 5, passage cells."
    assert v["operations"][0]["timing_text"] == TEXT
    assert v["operations"][0]["source_locator"]
    assert v["reagents"][0]["timing_text"] == TEXT
    assert v["reagents"][0]["dose_text"] == ""
    assert v["reagents"][0]["start_day"] is None and v["reagents"][0]["end_day"] is None
    assert {"dose_text", "start_day", "end_day"} <= set(v["reagents"][0]["unconfirmed"])


@pytest.mark.parametrize("change", ["dose", "quote", "unknown_source", "coverage"])
def test_unbacked_projection_and_omissions_leave_no_protocol(client, imported, change):
    payload = imported[2]
    if change == "dose":
        payload["content"]["reagents"][0]["dose_text"] = "99 uM"
    elif change == "quote":
        payload["content"]["reagents"][0]["quote"] = "Invented source"
    elif change == "unknown_source":
        payload["content"]["reagents"][0]["source_ids"] = ["S99"]
    else:
        payload["steps"] = []
    do_import(client, imported, 422)
    assert request(client, "GET", base(imported[0]) + "/workbench")["protocols"] == []


def test_integrity_failure_and_cross_research_material(client, imported):
    rid, mid, _ = imported
    other = research(client)
    request(client, "POST", base(other) + "/protocols", {"expected_version": 0, "material_id": mid}, 404)
    root = client.app.state.service.researches.directory(rid)
    (root / "materials" / (mid + ".bin")).write_text("tampered")
    do_import(client, imported, 422)


def test_review_clear_restart_derived_version_and_source_tampering(client, imported):
    from fastapi.testclient import TestClient
    from account_support import create_test_app, login_test_account
    p = do_import(client, imported)
    rid = imported[0]
    v = p["latest"]
    url = edition_url(rid, p, v)
    # Clearing only reagent questions cannot bypass document-wide review.
    checked = [{**r, "unconfirmed": []} for r in v["reagents"]]
    v = request(client, "PATCH", url, {"expected_version": v["revision"], "reagents": checked})
    request(client, "POST", url + "/confirm", {"expected_version": v["revision"]}, 409)
    v = request(client, "PATCH", url, {"expected_version": v["revision"], "unconfirmed": []})
    v = request(client, "POST", url + "/confirm", {"expected_version": v["revision"]})
    created_run = request(client, "POST", base(rid) + "/runs", {
        "expected_version": 0, "name": "Synthetic reviewed round", "state": "differentiating",
        "protocol_version_id": v["id"], "start_date": "2026-10-12"})
    assert created_run["protocol_version_id"] == v["id"]
    conversation_url = base(rid) + f"/runs/{created_run['id']}/conversation"
    conversation = request(client, "POST", conversation_url, {})
    assert conversation["research_id"] == rid and conversation["run_id"] == created_run["id"]
    assert conversation["conversation_kind"] == "run"
    current = request(client, "GET", base(rid) + f"/protocols/{p['id']}")
    derived = request(client, "POST", base(rid) + f"/protocols/{p['id']}/versions", {
        "expected_version": current["revision"], "based_on_version_id": v["id"], "changes": {"total_days": 8}})
    derived_url = edition_url(rid, p, derived)
    source = request(client, "GET", derived_url + "/formalization")
    assert source["projected_content"]["total_days"] == 5
    service = client.app.state.service
    with TestClient(create_test_app(service.settings)) as restarted:
        login_test_account(restarted)
        assert request(restarted, "GET", derived_url + "/formalization") == source
        restored = request(restarted, "GET", conversation_url)
        assert restored["id"] == conversation["id"]
        board = request(restarted, "GET", base(rid) + "/workbench")
        assert board["runs"][0]["protocol_version_id"] == v["id"]
        assert board["protocols"][0]["latest"]["id"] == derived["id"]
        assert request(restarted, "GET", url + "/formalization") == source
    path = service.researches.directory(rid) / "protocol-formalizations" / (source["id"] + ".json")
    path.write_text("{}")
    response = request(client, "GET", url + "/formalization", status=409)
    assert response["detail"] == "protocol_formalization_unavailable"


def test_model_failure_and_unavailable_compiler_leave_no_protocol(client, imported, monkeypatch):
    service = client.app.state.service
    service.settings = replace(service.settings, protocol_compiler_python=None)
    result = do_import(client, imported, 503)
    assert result["detail"] == "protocol_compiler_unavailable"
    def unavailable(*args, **kwargs):
        raise pf.ProtocolResponseError("protocol_provider_unavailable", {"private": "receipt"}, "remote-model")
    monkeypatch.setattr(pf, "generate", unavailable)
    result = do_import(client, imported, 502)
    assert result["detail"] == "protocol_provider_unavailable"
    assert "receipt" not in json.dumps(result)
    assert request(client, "GET", base(imported[0]) + "/workbench")["protocols"] == []


def test_generation_does_not_hold_store_lock(client, imported, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    original = pf.generate
    started, release = Event(), Event()
    def paused(*args, **kwargs):
        started.set()
        assert release.wait(10)
        return original(*args, **kwargs)
    monkeypatch.setattr(pf, "generate", paused)
    with ThreadPoolExecutor(max_workers=2) as pool:
        future = pool.submit(do_import, client, imported)
        assert started.wait(5)
        try:
            listing = pool.submit(request, client, "GET", base(imported[0]) + "/workbench").result(timeout=3)
            assert listing["protocols"] == []
        finally:
            release.set()
        assert future.result(timeout=10)["latest"]["status"] == "draft"


def test_import_uses_selected_account_model_and_real_response_parser(client, imported, monkeypatch):
    import httpx
    from bridge.web import protocol_import
    personal = {"base_url": "https://personal.invalid/v1", "model": "my-model",
                "api_key": "my-private-secret", "action_protocol": "json"}
    assert client.put("/api/me/model-settings", json=personal).status_code == 200
    seen = []
    def provider(settings, **kwargs):
        seen.append((settings.model, settings.model_api_key))
        def respond(req):
            body = json.loads(req.content)
            assert body["model"] == "my-model"
            assert "ImportContent" in body["messages"][0]["content"]
            return httpx.Response(200, json={"model": "my-model", "choices": [
                {"message": {"content": json.dumps(imported[2])}}]})
        return httpx.Client(transport=httpx.MockTransport(respond))
    monkeypatch.setattr(pf, "provider_client", provider)
    monkeypatch.setattr(protocol_import.formal, "generate", pf_generate)
    assert do_import(client, imported)["latest"]["status"] == "draft"
    assert seen == [("my-model", "my-private-secret")]


def test_source_endpoint_is_owner_scoped(client, imported):
    from fastapi.testclient import TestClient
    from bridge.web.accounts import NOTICE_VERSION
    p = do_import(client, imported)
    url = edition_url(imported[0], p, p["latest"]) + "/formalization"
    with TestClient(client.app) as outsider:
        outsider.headers["Origin"] = "http://testserver"
        registered = outsider.post("/api/register", json={
            "username": "other-reader", "password": "synthetic long test password", "notice_version": NOTICE_VERSION})
        assert registered.status_code == 200, registered.text
        result = outsider.get(url)
        assert result.status_code == 404
        assert TEXT not in result.text


def test_legacy_manual_version_without_review_field_remains_editable(client):
    from test_research_objects import protocol
    rid = research(client)
    p = protocol(client, rid)
    path = client.app.state.service.researches.directory(rid) / "objects.json"
    stored = json.loads(path.read_text())
    del stored["versions"][p["latest"]["id"]]["unconfirmed"]
    path.write_text(json.dumps(stored))
    loaded = request(client, "GET", base(rid) + f"/protocols/{p['id']}")
    assert loaded["latest"]["unconfirmed"] == []
    url = edition_url(rid, p, p["latest"])
    edited = request(client, "PATCH", url, {"expected_version": 1, "total_days": 5})
    assert edited["unconfirmed"] == []
    request(client, "GET", url + "/formalization", status=404)


def test_projection_cannot_reintroduce_excluded_source(client, imported):
    rid, _, payload = imported
    extra = "Editorial note: UnusedFactor 20 nM."
    response = client.post(base(rid) + "/uploads", files={"file": ("extra.txt", (TEXT + "\n\n" + extra).encode())})
    assert response.status_code == 200
    payload["excluded_sources"] = [{"source_id": "S2", "reason": "Editorial note outside the protocol"}]
    payload["content"]["reagents"].append({"name": "UnusedFactor", "dose_text": "20 nM", "start_day": None,
        "end_day": None, "quote": extra, "source_ids": ["S2"]})
    do_import(client, (rid, response.json()["id"], payload), 422)


def test_oversized_source_record_is_not_saved_as_a_success(client, imported, monkeypatch):
    from bridge.web import protocol_import
    monkeypatch.setattr(protocol_import, "FORMALIZATION_LIMIT", 128)
    response = do_import(client, imported, 413)
    assert response["detail"] == "protocol_formalization_limit"
    root = client.app.state.service.researches.directory(imported[0])
    assert not (root / "protocol-formalizations").exists()
    assert request(client, "GET", base(imported[0]) + "/workbench")["protocols"] == []


def test_unknown_window_stays_null_and_cannot_be_confirmed_by_clearing_flags(client, imported):
    imported[2]["content"]["reagents"][0]["start_day"] = None
    p = do_import(client, imported)
    v = p["latest"]
    assert v["reagents"][0]["start_day"] is None
    assert v["reagents"][0]["end_day"] == 4
    url = edition_url(imported[0], p, v)
    changed = request(client, "PATCH", url, {"expected_version": v["revision"], "unconfirmed": [],
        "reagents": [{**r, "unconfirmed": []} for r in v["reagents"]]})
    response = request(client, "POST", url + "/confirm", {"expected_version": changed["revision"]}, 409)
    assert response["detail"] == "protocol_incomplete"


@pytest.mark.parametrize("stale", [False, True], ids=["selected-effort", "stale-capability"])
def test_import_preserves_recent_effort_or_rejects_stale_capability(client, imported, monkeypatch, stale):
    import httpx
    provider = {"id": "lab", "base_url": "https://personal.invalid/v1",
                "api_key": "synthetic-key", "models": ["my-model"], "action_protocol": "json"}
    request(client, "PUT", "/api/models/providers", provider)
    def catalog(settings, **kwargs):
        return httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(200, json={
            "data": [{"id": "my-model", "effort": {
                "supported_levels": ["low", "high"], "default_level": "high"}}]})))
    monkeypatch.setattr("bridge.web.model_settings.provider_client", catalog)
    request(client, "POST", "/api/models/providers/lab/capabilities", {})
    sid = request(client, "POST", "/api/sessions", {})["id"]
    request(client, "PUT", f"/api/sessions/{sid}/model-selection",
            {"provider_id": "lab", "model": "my-model", "effort": "low"})
    if stale:
        request(client, "PUT", "/api/models/providers", {**provider, "api_key": "rotated-key"})
    sent = []
    def transport(settings, **kwargs):
        def respond(req):
            sent.append(json.loads(req.content))
            return httpx.Response(200, json={"model": "my-model", "choices": [
                {"message": {"content": json.dumps(imported[2])}}]})
        return httpx.Client(transport=httpx.MockTransport(respond))
    monkeypatch.setattr(pf, "provider_client", transport)
    monkeypatch.setattr(pf, "generate", pf_generate)
    result = do_import(client, imported, 409 if stale else 200)
    if stale:
        assert result["detail"] == "model_effort_unavailable"
        assert sent == []
        assert request(client, "GET", base(imported[0]) + "/workbench")["protocols"] == []
    else:
        assert len(sent) == 1
        assert sent[0]["model"] == "my-model"
        assert sent[0].get("reasoning_effort") == "low"
        assert result["latest"]["status"] == "draft"


@pytest.mark.parametrize("source_unit,bpl_unit,bpl_value,status", [
    ("ng/ml", "ng/mL", 12, 200),
    ("ug/ml", "ug/mL", 12, 200),
    ("ml", "mL", 12, 200),
    ("ng/L", "ng/mL", 12, 422),
    ("mg/ml", "ng/mL", 12, 422),
    ("mM", "uM", 12, 422),
    ("ng/ml_extra", "ng/mL", 12, 422),
    ("ng/ml", "ng/mL", 13, 422),
])
def test_import_millilitre_alias_preserves_source_dose_and_rejects_changes(
    client, imported, source_unit, bpl_unit, bpl_value, status
):
    # The external model alone is replaced; HTTP, source validation, compiler
    # and persistence remain real. l/L may vary, but prefixes and values may not.
    rid, _, payload = imported
    text = TEXT.replace("2 uM", "12 " + source_unit)
    for step in payload["steps"]:
        step["operations"] = step["operations"].replace("2 uM", "12 " + source_unit)
    payload["steps"][0]["bpl_fragment"] = (
        'culture(factors: {"CHIR99021": ' + str(bpl_value) + " " + bpl_unit
        + '}, timing: "Days 0 to 4")'
    )
    for rows in payload["content"].values():
        if isinstance(rows, list):
            for row in rows:
                row["quote"] = row["quote"].replace("2 uM", "12 " + source_unit)
    payload["content"]["reagents"][0]["dose_text"] = "12 " + source_unit
    material = client.post(base(rid) + "/uploads",
                          files={"file": ("synthetic-litre-alias.txt", text.encode())})
    assert material.status_code == 200
    p = do_import(client, (rid, material.json()["id"], payload), status)
    if status == 200:
        assert p["latest"]["reagents"][0]["dose_text"] == "12 " + source_unit
        assert p["latest"]["status"] == "draft"
        source = request(client, "GET", edition_url(rid, p, p["latest"]) + "/formalization")
        assert source["compiler_state"] == "passed"
        assert source["steps"][0]["sources"][0]["text"] == text
    else:
        assert request(client, "GET", base(rid) + "/workbench")["protocols"] == []


@pytest.mark.parametrize("day_text,supported", [
    ("16.", True),
    ("16. Next step follows.", True),
    ("16.5", False),
    ("116", False),
    ("1.16", False),
    ("16_extra", False),
    ("16e2", False),
])
def test_project_day_accepts_sentence_period_without_matching_partial_numbers(day_text, supported):
    from bridge.web.protocol_import import ImportContent, project
    from bridge.web.research_objects import CATALOG_PATH

    quote = "Culture with Factor A at 2 uM until day " + day_text
    content = ImportContent.model_validate({"reagents": [{
        "name": "Factor A", "dose_text": "2 uM", "end_day": 16,
        "quote": quote, "source_ids": ["S1"],
    }]})
    sources = {"S1": {"text": quote, "location": "synthetic paragraph"}}
    if supported:
        result = project(content, sources, CATALOG_PATH)
        assert result["reagents"][0]["end_day"] == 16
        assert result["reagents"][0]["unconfirmed"]
    else:
        with pytest.raises(ValueError, match="unsupported_projection_day"):
            project(content, sources, CATALOG_PATH)


@pytest.mark.parametrize("tamper", ["material", "formalization"])
def test_source_review_rejects_changed_source_without_partial_state(client, imported, tamper):
    p = do_import(client, imported)
    rid, mid, _ = imported
    v = p["latest"]
    url = edition_url(rid, p, v)
    root = client.app.state.service.researches.directory(rid)
    path = (root / "materials" / (mid + ".bin") if tamper == "material" else
            root / "protocol-formalizations" / (v["provenance"]["formalization_version_id"] + ".json"))
    path.write_text("changed")
    response = request(client, "POST", url + "/source-review", {
        "expected_version": v["revision"], "note": "Checked source"}, 409)
    assert response["detail"] == ("research_material_unavailable" if tamper == "material" else
                                  "protocol_formalization_unavailable")
    assert request(client, "GET", base(rid) + f"/protocols/{p['id']}")["latest"] == v


def test_import_source_review_preserves_missing_fields_and_remaining_review(client, imported):
    imported[2]["content"]["total_days"] = None
    imported[2]["content"]["operations"][0]["day"] = None
    p = do_import(client, imported)
    v = p["latest"]
    url = edition_url(imported[0], p, v)
    checked = request(client, "POST", url + "/source-review", {
        "expected_version": v["revision"], "note": "Source reviewed; duration remains unknown."})
    assert checked["source_review"]["status"] == "reviewed"
    assert checked["status"] == "draft" and checked["total_days"] is None
    assert checked["operations"][0]["day"] is None
    assert checked["unconfirmed"] == ["total_days", "stages", "operations"]
    assert checked["reagents"] == v["reagents"]
    request(client, "POST", url + "/confirm", {"expected_version": checked["revision"]}, 409)
