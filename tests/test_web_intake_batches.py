"""Dataset-bound culture questions; synthetic labels are not biological evidence."""
import json
import pytest
from test_web_intake_autofill import client, upload_metadata, intake
from test_web_service import confirm_change


def answer(client, sid, aid, field, value, other=False):
    current = intake(client, sid, aid)
    return client.post(f"/api/sessions/{sid}/intake/answer", json={
        "upload_id": aid, "revision": current["autofill"]["revision"],
        "field": field, "value": value, "other": other})


def batch_question(value):
    return next(q for q in value["autofill"]["questions"] if q["field"].startswith("culture_batch"))


def test_batch_question_names_actual_column_without_deriving_count(client, tmp_path):
    sid, aid = upload_metadata(client, tmp_path)
    value = intake(client, sid, aid)
    q = batch_question(value)
    assert "sample_id" in q["title"] and "PRIVATE_SAMPLE_A" in q["title"]
    assert q["field"] == "culture_batch_role" and q["input_type"] == "text"
    assert [o["value"] for o in q["options"]] == ["independent_culture", "not_culture", "unsure", "__other__"]
    assert value["facts"]["independent_cultures"] is None
    assert "independent_cultures" not in [q["field"] for q in value["autofill"]["questions"]]


def test_explicit_independence_derives_count_and_preserves_upload_binding(client, tmp_path):
    sid, aid = upload_metadata(client, tmp_path, samples=("A", "B"))
    response = answer(client, sid, aid, "culture_batch_role", "independent_culture")
    assert response.status_code == 200, response.json()
    value = intake(client, sid, aid)
    assert value["facts"]["independent_cultures"] == 2
    assert value["facts"]["culture_batch_column"] == "sample_id"
    assert value["facts"]["culture_batch_role"] == "independent_culture"
    origin = value["autofill"]["field_sources"]["independent_cultures"]
    assert origin["kind"] == "user" and "sample_id" in origin["quote"]
    assert value["autofill"]["batch_binding"]["upload_sha256"] == client.app.state.service.load(sid)["_uploads"][aid]["sha256"]
    assert value["autofill"]["batch_binding"]["column"] == "sample_id"
    assert not any(q["field"].startswith("culture_batch") for q in value["autofill"]["questions"])
    state = client.get(f"/api/sessions/{sid}").json()
    assert state["plan"] is None and not state["input_review_required"]
    staged = client.post(f"/api/sessions/{sid}/intake", json={"upload_id": aid, "facts": value["facts"]})
    assert staged.status_code == 200, staged.json()
    confirm_change(client, sid, staged.json())
    record = client.app.state.service.load(sid)["_intakes"][aid]
    assert record["facts"]["culture_batch_column"] == "sample_id"
    assert "sample_id" in record["source_facts"]["culture_batch_binding"]


def test_rejected_identifier_requests_mapping_and_skips_identical_capture(client, tmp_path):
    sid, aid = upload_metadata(client, tmp_path)
    response = answer(client, sid, aid, "culture_batch_role", "not_culture")
    assert response.status_code == 200, response.json()
    value = intake(client, sid, aid)
    q = batch_question(value)
    assert q["field"] == "culture_batch_column"
    assert "capture_id" not in [o["value"] for o in q["options"]]
    assert value["facts"]["independent_cultures"] is None
    assert answer(client, sid, aid, "culture_batch_column", "One sample pools cultures; mapping unavailable", True).status_code == 200
    value = intake(client, sid, aid)
    assert value["facts"]["independent_cultures"] is None
    assert value["autofill"]["other_answers"]["culture_batch_column"].startswith("One sample")
    assert not any(q["field"].startswith("culture_batch") for q in value["autofill"]["questions"])


def test_selected_alternate_column_still_requires_semantic_confirmation(client, tmp_path):
    sid, aid = upload_metadata(client, tmp_path, samples=("A", "B"), extra_obs={"run_group": ("r", "r")})
    assert answer(client, sid, aid, "culture_batch_role", "not_culture").status_code == 200
    assert answer(client, sid, aid, "culture_batch_column", "run_group", True).status_code == 200
    value = intake(client, sid, aid)
    assert "run_group" in batch_question(value)["title"]
    assert value["facts"]["independent_cultures"] is None
    assert answer(client, sid, aid, "culture_batch_role", "independent_culture").status_code == 200
    assert intake(client, sid, aid)["facts"]["independent_cultures"] == 1
    assert answer(client, sid, aid, "culture_batch_role", "unsure").status_code == 200
    assert intake(client, sid, aid)["facts"]["independent_cultures"] is None


@pytest.mark.parametrize("samples", [("A", None), ("A", ""), ("A", "   ")])
def test_missing_batch_rows_cannot_become_complete_replication_count(client, tmp_path, samples):
    sid, aid = upload_metadata(client, tmp_path, samples=samples)
    assert answer(client, sid, aid, "culture_batch_role", "independent_culture").status_code == 200
    value = intake(client, sid, aid)
    assert value["facts"]["independent_cultures"] is None
    assert value["autofill"]["batch_binding"]["missing"] == 1


def test_batch_profiles_stay_out_of_model_context_and_upgrade_old_draft(client, tmp_path):
    sid, aid = upload_metadata(client, tmp_path, extra_obs={"culture_batch": ("PRIVATE_BATCH_1", "PRIVATE_BATCH_2")})
    from bridge.web.intake_autofill import model_context
    assert answer(client, sid, aid, "target_stage", "progenitor").status_code == 200
    service = client.app.state.service
    state = service.load(sid)
    state["_intake_autofill"][aid].pop("batch_columns", None)
    service.save(state)
    value = intake(client, sid, aid)
    assert "culture_batch" in batch_question(value)["title"]
    assert value["facts"]["target_stage"] == "progenitor"
    context = model_context(service, service.load(sid), aid)
    assert "PRIVATE_" not in json.dumps(context)
    assert not {"culture_batch_column", "culture_batch_role"} & set(context["allowed_fields"])


@pytest.mark.parametrize("text", ["This sample pools three cultures; mapping unknown", "independent_culture"])
def test_other_role_stays_uninterpreted_and_retains_column_source(client, tmp_path, text):
    sid, aid = upload_metadata(client, tmp_path, samples=("A", "B"))
    assert answer(client, sid, aid, "culture_batch_role", "independent_culture").status_code == 200
    response = answer(client, sid, aid, "culture_batch_role", text, True)
    assert response.status_code == 200, response.json()
    value = intake(client, sid, aid)
    assert value["facts"]["culture_batch_column"] == "sample_id"
    assert value["facts"]["culture_batch_role"] == "unknown"
    assert value["facts"]["independent_cultures"] is None
    assert value["autofill"]["other_answers"]["culture_batch_role"] == text
    assert value["autofill"]["batch_binding"]["role"] == "unknown"
    assert text in value["autofill"]["field_sources"]["culture_batch_role"]["quote"]
    assert not any(q["field"].startswith("culture_batch") for q in value["autofill"]["questions"])
    service = client.app.state.service
    assert text in service.intake.confirmation_sources(service.load(sid), aid)["culture_batch_role_note"]
    session = client.get(f"/api/sessions/{sid}").json()
    assert session["plan"] is None and not session["input_review_required"]


def test_rechecking_column_clears_other_role_before_reconfirmation(client, tmp_path):
    sid, aid = upload_metadata(client, tmp_path)
    assert answer(client, sid, aid, "culture_batch_role", "Sample pools cultures", True).status_code == 200
    assert answer(client, sid, aid, "culture_batch_column", "sample_id").status_code == 200
    value = intake(client, sid, aid)
    assert "culture_batch_role" not in value["autofill"]["other_answers"]
    assert batch_question(value)["field"] == "culture_batch_role"
    assert value["facts"]["independent_cultures"] is None
    assert answer(client, sid, aid, "culture_batch_role", "independent_culture").status_code == 200
    assert intake(client, sid, aid)["facts"]["independent_cultures"] == 1


def test_explicit_role_replaces_custom_supplement_without_stale_text(client, tmp_path):
    sid, aid = upload_metadata(client, tmp_path)
    assert answer(client, sid, aid, "culture_batch_role", "Mixed batches", True).status_code == 200
    assert answer(client, sid, aid, "culture_batch_role", "not_culture").status_code == 200
    value = intake(client, sid, aid)
    assert "culture_batch_role" not in value["autofill"]["other_answers"]
    assert batch_question(value)["field"] == "culture_batch_column"
    assert "culture_batch_role_note" not in client.app.state.service.intake.confirmation_sources(
        client.app.state.service.load(sid), aid)


def test_confirmation_keeps_custom_note_separate_from_role_and_shows_its_removal(client, tmp_path):
    sid, aid = upload_metadata(client, tmp_path)
    assert answer(client, sid, aid, "culture_batch_role", "independent_culture").status_code == 200
    staged = client.post(f"/api/sessions/{sid}/intake", json={"upload_id": aid, "facts": intake(client, sid, aid)["facts"]})
    assert staged.status_code == 200
    confirm_change(client, sid, staged.json())
    assert answer(client, sid, aid, "culture_batch_role", "Mixed cultures", True).status_code == 200
    staged = client.post(f"/api/sessions/{sid}/intake", json={"upload_id": aid, "facts": intake(client, sid, aid)["facts"]})
    assert staged.status_code == 200
    changes = {item["field"]: item for item in staged.json()["pending_input_change"]["changes"]}
    assert changes["culture_batch_role"]["after"] == "unknown"
    assert changes["culture_batch_role_note"]["after"] == "Mixed cultures"
    confirm_change(client, sid, staged.json())
    assert answer(client, sid, aid, "culture_batch_role", "independent_culture").status_code == 200
    staged = client.post(f"/api/sessions/{sid}/intake", json={"upload_id": aid, "facts": intake(client, sid, aid)["facts"]})
    assert staged.status_code == 200
    changes = {item["field"]: item for item in staged.json()["pending_input_change"]["changes"]}
    assert changes["culture_batch_role"]["after"] == "independent_culture"
    assert changes["culture_batch_role_note"] == {
        "field": "culture_batch_role_note", "before": "Mixed cultures", "after": ""}
    confirm_change(client, sid, staged.json())
    assert intake(client, sid, aid)["state"] == "confirmed"


def test_tampered_bound_count_is_rejected_at_confirmation(client, tmp_path):
    sid, aid = upload_metadata(client, tmp_path)
    assert answer(client, sid, aid, "culture_batch_role", "independent_culture").status_code == 200
    facts = intake(client, sid, aid)["facts"]
    facts["independent_cultures"] = 99
    response = client.post(f"/api/sessions/{sid}/intake", json={"upload_id": aid, "facts": facts})
    assert response.status_code == 422
