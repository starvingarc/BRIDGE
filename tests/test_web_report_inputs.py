"""Web-owned missingness inputs still run only through explicit P0-08 approval."""
from __future__ import annotations

import json
import pytest

from test_web_service import client, settle
from test_web_scientific_inputs import science_case, propose, candidate
from test_web_intake import stage, stated_facts
from test_web_service import confirm_change

def confirmed_case(client, tmp_path):
    service, sid, aid = science_case(client, tmp_path)
    draft = propose(service, sid, aid)
    body = {"draft_id": draft["id"], "draft_digest": draft["digest"]}
    assert client.post(f"/api/sessions/{sid}/scientific-inputs/confirm", json=body).status_code == 200
    return service, sid, aid, body

def test_missingness_preparation_uses_real_case_and_packaged_gate_without_execution(client, tmp_path):
    service, sid, aid, body = confirmed_case(client, tmp_path)
    before = service.load(sid)
    response = client.post(f"/api/sessions/{sid}/report-inputs/prepare", json=body)
    assert response.status_code == 200, response.json()
    value = response.json()
    assert value["status"] == "awaiting_approval"
    assert value["plan"]["steps"][0]["tool_id"] == "P0-08"
    assert value["plan"]["steps"][0]["status"] == "pending"
    assert "未评估" in value["plan"]["summary"]
    state = service.load(sid)
    assert state["_tool_runs"] == before["_tool_runs"] == []
    request = json.loads(state["_plan"]["steps"][0]["approved_request_json"])
    assert request["assets"] == []
    assert len(request["object_inputs"]) == 7
    assert {row["role"] for row in request["object_inputs"]} == {"product_case", "gate_rule_spec", "domain_gate_input"}
    inputs = [service.inputs.verify(state, state["_input_objects"][row["input_id"]])
              for row in request["object_inputs"] if row["role"] == "domain_gate_input"]
    assert len({row["domain_id"] for row in inputs}) == 5
    for row in inputs:
        assert row["measurement_result_input_ids"] == [] and row["qc_profile_input_id"] is None
        assert row["method_requirement"] == row["prior_requirement"] == "not_assessed"
        assert row["task_validation_state"] == "not_assessed"
    first_objects = state["_input_objects"]
    again = client.post(f"/api/sessions/{sid}/report-inputs/prepare", json=body)
    assert again.status_code == 200
    assert service.load(sid)["_input_objects"] == first_objects

def test_actual_approved_missingness_tool_retains_five_unassessed_domains(client, tmp_path):
    service, sid, aid, body = confirmed_case(client, tmp_path)
    response = client.post(f"/api/sessions/{sid}/report-inputs/prepare", json=body)
    assert response.status_code == 200, response.json()
    plan = response.json()["plan"]
    assert client.post(f"/api/sessions/{sid}/approve",
        json={"plan_id": plan["id"], "plan_digest": plan["digest"]}).status_code == 200
    done = settle(client, sid)
    assert done["plan"]["status"] == "completed", done
    state = service.load(sid)
    outputs = [record for record in state["_input_objects"].values()
        if record["source"] == "tool_output" and record["schema_ref"] == "bridge://schemas/evidence-sufficiency-run-result/v0.2"]
    assert len(outputs) == 1
    result = service.inputs.verify(state, outputs[0])
    assert len(result["profiles"]) == 5
    for profile in result["profiles"]:
        assert profile["evidence_sufficiency_state"] == "not_assessed"
        assert profile["domain_score"] is None
        assert profile["score_state"] == "unavailable"
    stages = {row["tool_id"]: row for row in done["scientific_drafts"][-1]["stages"]}
    assert stages["P0-08"]["state"] == "available"
    assert stages["P0-09"]["state"] == "ready"
    assert stages["P0-09"]["reason_codes"] == ["candidate_missingness_policy"]
    assert stages["P0-10"]["state"] == stages["P0-11"]["state"] == "blocked"

def run_stage(client, sid, body, tool_id):
    response = client.post(f"/api/sessions/{sid}/report-inputs/prepare", json={**body, "tool_id": tool_id})
    assert response.status_code == 200, response.json()
    plan = response.json()["plan"]
    assert plan["steps"][0]["tool_id"] == tool_id
    assert client.post(f"/api/sessions/{sid}/approve",
        json={"plan_id": plan["id"], "plan_digest": plan["digest"]}).status_code == 200
    done = settle(client, sid)
    assert done["plan"]["status"] == "completed", done
    return done

def test_candidate_graph_requires_canonical_missingness_and_separate_approval(client, tmp_path):
    service, sid, aid, body = confirmed_case(client, tmp_path)
    before = service.load(sid)
    blocked = client.post(f"/api/sessions/{sid}/report-inputs/prepare", json={**body, "tool_id": "P0-09"})
    assert blocked.status_code == 409
    assert service.load(sid) == before
    run_stage(client, sid, body, "P0-08")
    before = service.load(sid)
    response = client.post(f"/api/sessions/{sid}/report-inputs/prepare", json={**body, "tool_id": "P0-09"})
    assert response.status_code == 200, response.json()
    plan = response.json()["plan"]
    assert plan["steps"][0]["tool_id"] == "P0-09"
    assert service.load(sid)["_tool_runs"] == before["_tool_runs"]
    assert "候选" in plan["summary"]
    original_objects = service.load(sid)["_input_objects"]
    again = client.post(f"/api/sessions/{sid}/report-inputs/prepare", json={**body, "tool_id": "P0-09"})
    assert again.status_code == 200
    assert service.load(sid)["_input_objects"] == original_objects
    assert service.load(sid)["_tool_runs"] == before["_tool_runs"]
    plan = again.json()["plan"]
    selected = service.load(sid)
    from copy import deepcopy
    intact = deepcopy(selected)
    selected["_input_selections"]["P0-09"]["object_inputs"] = [row for row in selected["_input_selections"]["P0-09"]["object_inputs"] if row["role"] != "evidence_sufficiency_run_result"]
    service.save(selected)
    assert client.post(f"/api/sessions/{sid}/approve", json={"plan_id": plan["id"], "plan_digest": plan["digest"]}).status_code == 409
    assert service.load(sid)["_tool_runs"] == before["_tool_runs"]
    service.save(intact)
    assert client.post(f"/api/sessions/{sid}/approve",
        json={"plan_id": plan["id"], "plan_digest": plan["digest"]}).status_code == 200
    done = settle(client, sid)
    assert done["plan"]["status"] == "completed", done
    state = service.load(sid)
    outputs = [record for record in state["_input_objects"].values()
        if record["source"] == "tool_output" and record["schema_ref"] == "bridge://schemas/evidence-record-set/v0.1"]
    assert len(outputs) == 1
    records = service.inputs.verify(state, outputs[0])
    assert records["records"] == []
    requirements = next(service.inputs.verify(state, row) for row in state["_input_objects"].values()
        if row["source"] == "tool_output" and row["schema_ref"] == "bridge://schemas/evidence-requirement-set/v0.1")["requirements"]
    assert len(requirements) == 5
    assert all(row["state"] == "open" and row["satisfying_evidence_refs"] == [] for row in requirements)
    from pathlib import Path
    artifacts = service.inputs.receipt_artifacts(state, outputs[0])
    reconciliation = next(json.loads(Path(row["path"]).read_text()) for row in artifacts.values()
        if Path(row["path"]).name == "reconciliation_records.json")
    assert len(reconciliation["records"]) == 5
    assert all(row["eligibility"] == "not_assessed" for row in reconciliation["records"])
    stages = {row["tool_id"]: row for row in done["scientific_drafts"][-1]["stages"]}
    assert stages["P0-09"]["state"] == "available"
    assert stages["P0-10"]["state"] == "ready"
    assert stages["P0-07"]["reason_codes"] == ["comparison_inputs_not_bound"]
    assert stages["P0-11"]["state"] == "blocked"

def test_new_scientific_draft_cannot_borrow_previous_draft_missingness_receipt(client, tmp_path):
    service, sid, aid, body = confirmed_case(client, tmp_path)
    run_stage(client, sid, body, "P0-08")
    original = service.load(sid)["_scientific_drafts"][-1]
    revised = client.post(f"/api/sessions/{sid}/scientific-inputs/revise", json={**body, "candidate": original["candidate"]})
    assert revised.status_code == 200, revised.json()
    current = revised.json()["scientific_drafts"][-1]
    new_body = {"draft_id": current["id"], "draft_digest": current["digest"]}
    assert current["id"] != body["draft_id"]
    assert client.post(f"/api/sessions/{sid}/scientific-inputs/confirm", json=new_body).status_code == 200
    before = service.load(sid)
    response = client.post(f"/api/sessions/{sid}/report-inputs/prepare", json={**new_body, "tool_id": "P0-09"})
    assert response.status_code == 409
    assert service.load(sid) == before

def test_internal_report_runs_real_verifier_and_keeps_release_blocked(client, tmp_path):
    service, sid, aid, body = confirmed_case(client, tmp_path)
    run_stage(client, sid, body, "P0-08")
    run_stage(client, sid, body, "P0-09")
    before = service.load(sid)
    response = client.post(f"/api/sessions/{sid}/report-inputs/prepare", json={**body, "tool_id": "P0-10"})
    assert response.status_code == 200, response.json()
    plan = response.json()["plan"]
    assert plan["steps"][0]["tool_id"] == "P0-10"
    assert service.load(sid)["_tool_runs"] == before["_tool_runs"]
    prepared = response.json()["scientific_drafts"][-1]["internal_report"]
    assert prepared["verification"] is None
    assert len(prepared["sections"]) == 5
    assert prepared["boundaries"] == ["本次核对不能证明安全性。"]
    assert all(row["evidence_state"] == "not_assessed" for row in prepared["sections"])
    assert client.post(f"/api/sessions/{sid}/approve",
        json={"plan_id": plan["id"], "plan_digest": plan["digest"]}).status_code == 200
    done = settle(client, sid)
    assert done["plan"]["status"] == "completed", done
    report = done["scientific_drafts"][-1]["internal_report"]
    assert report["verification"]["release_state"] == "release_blocked"
    assert report["verification"]["public_export_eligibility"] == "ineligible"
    assert "claim_type_policy_missing" in report["verification"]["reason_codes"]
    assert report["sections"] == prepared["sections"]
    assert report["next_actions"]
    assert str(tmp_path) not in json.dumps(report)
    assert client.get(f"/api/sessions/{sid}").json()["scientific_drafts"][-1]["internal_report"] == report
    stages = {row["tool_id"]: row for row in done["scientific_drafts"][-1]["stages"]}
    assert stages["P0-10"]["state"] == "available"
    assert stages["P0-11"]["state"] == "blocked"


@pytest.mark.parametrize("tool_id, corruption", [
    ("P0-09", "receipt"), ("P0-09", "policy"), ("P0-10", "upstream"), ("P0-10", "report"),
])
def test_report_approval_rejects_corruption_without_running_or_displaying_stale_report(client, tmp_path, tool_id, corruption):
    from pathlib import Path
    service, sid, aid, body = confirmed_case(client, tmp_path)
    run_stage(client, sid, body, "P0-08")
    if tool_id == "P0-10":
        run_stage(client, sid, body, "P0-09")
    response = client.post(f"/api/sessions/{sid}/report-inputs/prepare", json={**body, "tool_id": tool_id})
    assert response.status_code == 200, response.json()
    plan = response.json()["plan"]
    state = service.load(sid)
    if corruption == "receipt":
        path = service.directory(sid) / "receipts" / state["_tool_runs"][0]["file"]
    else:
        schema = {"policy": "claim-registry/v0.1", "upstream": "evidence-sufficiency-run-result/v0.2",
                  "report": "report-draft/v0.1"}[corruption]
        record = next(row for row in state["_input_objects"].values() if row["schema_ref"] == "bridge://schemas/" + schema)
        path = Path(record["path"])
    original = path.read_bytes()
    try:
        path.write_bytes(original + b" ")
        before = service.load(sid)
        response = client.post(f"/api/sessions/{sid}/approve", json={"plan_id": plan["id"], "plan_digest": plan["digest"]})
        assert response.status_code == 409
        assert service.load(sid) == before
        public = client.get(f"/api/sessions/{sid}").json()["scientific_drafts"][-1]
        assert public["internal_report"] is None
    finally:
        path.write_bytes(original)

def test_candidate_factory_is_unreviewed_case_bound_and_never_converts_measured_evidence_to_missing(client, tmp_path):
    from datetime import datetime, timezone
    from bridge.tool_packages._configurable_contracts import ProductCase, ProductDefinitionCard
    from bridge.tool_packages.p0_08_evidence_sufficiency.models import EvidenceSufficiencyRunResultV2
    from bridge.tool_packages.p0_09_evidence_compiler.candidate_policy import build_missingness_policy
    service, sid, aid, body = confirmed_case(client, tmp_path)
    run_stage(client, sid, body, "P0-08")
    state = service.load(sid)
    draft = state["_scientific_drafts"][-1]
    def payload(identifier): return service.inputs.verify(state, state["_input_objects"][identifier])
    case = ProductCase.model_validate(payload(draft["object_ids"]["product_case"]))
    definition = ProductDefinitionCard.model_validate(payload(draft["object_ids"]["product_definition_card"]))
    result = EvidenceSufficiencyRunResultV2.model_validate(next(payload(key) for key, row in state["_input_objects"].items()
        if row["schema_ref"] == "bridge://schemas/evidence-sufficiency-run-result/v0.2"))
    stamp = datetime.now(timezone.utc)
    policy = build_missingness_policy(case, definition, result, created_at=stamp)
    assert policy == build_missingness_policy(case, definition, result, created_at=stamp)
    assert policy["compilation_bundle"].candidate_records == []
    assert len(policy["compilation_bundle"].missing_observations) == 5
    assert policy["claim_registry"].status == "candidate"
    assert all(row.status == "candidate" and row.reviewer_ref is None for row in policy["claim_registry"].claims)
    family = policy["evidence_family_registry"].families[0]
    assert family.status == "unreviewed" and family.reviewer_ref is None
    assert family.shared_source_refs == [case.sample_or_preparation_ref.ref]
    assert policy["reconciliation_spec_registry"].specs[0].minimum_independent_families_by_role == {"canonical_measurement": 1}
    for invalid_case, invalid_result in (
        (case.model_copy(update={"product_case_id": "product-case:other"}), result),
        (case, result.model_copy(update={"profiles": result.profiles[:-1]})),
        (case, result.model_copy(update={"profiles": [*result.profiles[:4], result.profiles[0]]})),
        (case, result.model_copy(update={"profiles": [result.profiles[0].model_copy(
            update={"measurement_result_refs": [case.ref]}), *result.profiles[1:]]})),
    ):
        with pytest.raises(ValueError):
            build_missingness_policy(invalid_case, definition, invalid_result, created_at=stamp)

@pytest.mark.parametrize("invalid", ["unconfirmed", "digest", "intake", "source"])
def test_report_preparation_rejects_unconfirmed_or_stale_draft_without_writes(client, tmp_path, monkeypatch, invalid):
    service, sid, aid = science_case(client, tmp_path)
    draft = propose(service, sid, aid)
    body = {"draft_id": draft["id"], "draft_digest": draft["digest"]}
    if invalid != "unconfirmed":
        assert client.post(f"/api/sessions/{sid}/scientific-inputs/confirm", json=body).status_code == 200
    if invalid == "digest":
        body["draft_digest"] = "0" * 64
    elif invalid == "intake":
        confirm_change(client, sid, stage(client, sid, aid, stated_facts(target_stage="changed")))
    elif invalid == "source":
        original = service.scientific_inputs._catalog
        def changed(state):
            context, binding, spec = original(state)
            return context, {**binding, "biological": "changed"}, spec
        monkeypatch.setattr(service.scientific_inputs, "_catalog", changed)
    before = service.load(sid)
    response = client.post(f"/api/sessions/{sid}/report-inputs/prepare", json=body)
    assert response.status_code == 409
    assert service.load(sid) == before

def test_report_source_changed_after_plan_proposal_cannot_be_approved(client, tmp_path, monkeypatch):
    service, sid, aid, body = confirmed_case(client, tmp_path)
    response = client.post(f"/api/sessions/{sid}/report-inputs/prepare", json=body)
    plan = response.json()["plan"]
    original = service.scientific_inputs._catalog
    def changed(state):
        context, binding, spec = original(state)
        return context, {**binding, "biological": "changed"}, spec
    monkeypatch.setattr(service.scientific_inputs, "_catalog", changed)
    before = service.load(sid)
    response = client.post(f"/api/sessions/{sid}/approve",
        json={"plan_id": plan["id"], "plan_digest": plan["digest"]})
    assert response.status_code == 409
    assert service.load(sid) == before

def test_owned_report_selection_cannot_drop_current_case_binding(client, tmp_path):
    service, sid, aid, body = confirmed_case(client, tmp_path)
    assert client.post(f"/api/sessions/{sid}/report-inputs/prepare", json=body).status_code == 200
    state = service.load(sid)
    state["_input_selections"]["P0-08"]["object_inputs"] = [
        item for item in state["_input_selections"]["P0-08"]["object_inputs"] if item["role"] != "product_case"]
    service.save(state)
    result = client.post(f"/api/sessions/{sid}/prepare-analysis", json={"tool_id": "P0-08"})
    assert result.status_code == 200
    assert result.json()["error"] == "report_draft_selection_mismatch"
    assert service.load(sid)["_tool_runs"] == []
