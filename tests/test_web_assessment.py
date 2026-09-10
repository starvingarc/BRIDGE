"""Scope consent admits exact registered requests; it is not a science attestation."""
from __future__ import annotations

from dataclasses import replace
import importlib
import json

import pytest

from test_web_service import client, settle
from test_web_scientific_inputs import science_case
from test_web_inputs import upload_request, choice


def registered_case(client, tmp_path, tool="P0-05", mode="legacy_aggregation"):
    service, sid, aid = science_case(client, tmp_path)
    module = importlib.import_module({
        "P0-05": "test_p0_05_off_target_control",
        "P0-06": "test_p0_06_proliferation_stress_response",
    }[tool])
    supplied = tmp_path / "supplied"
    supplied.mkdir()
    request = module._request(supplied)
    objects = upload_request(client, sid, request, mode)
    selected = client.post(f"/api/sessions/{sid}/analysis-inputs", json=choice(tool, mode, objects))
    assert selected.status_code == 200, selected.json()
    return service, sid, aid


def propose_scope(client, sid, aid, tool="P0-05", mode="legacy_aggregation", **limits):
    response = client.post(f"/api/sessions/{sid}/assessment/propose", json={
        "question": "Describe the registered product evidence and its unresolved denominator.",
        "upload_id": aid, "allowed_modes": [{"tool_id": tool, "mode_id": mode}],
        "max_tool_runs": 3, "max_model_turns": 4, **limits,
    })
    assert response.status_code == 200, response.json()
    return response.json()["assessment"]


def approve_scope(client, sid, scope):
    response = client.post(f"/api/sessions/{sid}/assessment/approve", json={
        "scope_id": scope["scope_id"], "scope_digest": scope["scope_digest"],
    })
    assert response.status_code == 200, response.json()
    return response.json()


@pytest.mark.parametrize("tool", ["P0-05", "P0-06"])
def test_scope_runs_real_registered_check_then_reads_result_without_new_human_approval(
        client, tmp_path, monkeypatch, tool):
    service, sid, aid = registered_case(client, tmp_path, tool)
    service.settings = replace(service.settings, share_result_summaries=True)
    scope = propose_scope(client, sid, aid, tool)
    before = service.load(sid)
    assert before["_tool_runs"] == []
    assert scope["status"] == "proposed"

    def model(settings, messages, context):
        from bridge.web.provider import Action
        assert context["purpose"] == "assessment"
        assert messages == [{"role": "user", "content": "Select the next authorized evidence action."}]
        if not context["evidence"]:
            return Action.model_validate({"action": "assessment", "decision": {
                "action": "check", "option_id": context["options"][0]["id"]}})
        return Action.model_validate({"action": "assessment", "decision": {
            "action": "stop", "reason": "evidence_requirements_reached"}})

    monkeypatch.setattr("bridge.web.provider.converse", model)
    approve_scope(client, sid, scope)
    done = settle(client, sid)
    assert done["assessment"]["status"] == "stopped", done
    assert done["assessment"]["stop_reason"] == "evidence_requirements_reached"
    assert done["assessment"]["tool_runs_used"] == 1
    assert done["assessment"]["model_turns_used"] == 2
    state = service.load(sid)
    assert state["_input_revision"] == before["_input_revision"]
    assert len(state["_tool_runs"]) == 1
    assert state["_tool_runs"][0]["tool_id"] == tool
    authorization = state["_assessment"]["authorization"]
    receipt = state["_plan"]["approval_receipt"]
    assert receipt["authorization_kind"] == "scope_derived"
    assert receipt["scope_id"] == scope["scope_id"]
    assert receipt["scope_sha256"] == scope["scope_digest"]
    assert receipt["approver_id"] == authorization["approver_id"] == "private-operator"
    assert receipt["approved_at"] == authorization["approved_at"]
    assert receipt["plan_sha256"] == done["plan"]["digest"]
    assert done["plan"]["status"] == "completed"
    evidence = done["assessment"]["evidence"][0]
    assert evidence["tool_id"] == tool
    assert evidence["domain_score"] is None
    assert evidence["score_state"] == "unavailable"
    assert evidence["state"] == "available"
    assert str(tmp_path) not in json.dumps(done["assessment"])
    if tool == "P0-05":
        assert evidence["summary"]["primary_denominator"]["n_observations"] == 10
        assert evidence["summary"]["role_composition"][0]["product_role"] == "target"
    else:
        assert evidence["summary"]["analysis_mode"] == "descriptive_only"
        assert len(evidence["summary"]["program_results"]) == 2
        assert evidence["summary"]["program_results"][1]["value"] == 0.9
        assert evidence["summary"]["program_results"][1]["unit"] == "relative-score"
        assert evidence["summary"]["program_results"][1]["numerator"] == 9
        assert evidence["summary"]["program_results"][1]["denominator"] == 10


def next_check_or_stop(settings, messages, context):
    from bridge.web.provider import Action
    decision = ({"action": "check", "option_id": context["options"][0]["id"]}
                if context["options"] else {"action": "stop", "reason": "no_discriminating_check"})
    return Action.model_validate({"action": "assessment", "decision": decision})


@pytest.mark.parametrize("limits,reason", [
    ({"max_tool_runs": 1}, "tool_run_budget_exhausted"),
    ({"max_model_turns": 1}, "model_turn_budget_exhausted"),
])
def test_durable_budget_cannot_be_refunded_by_resume(client, tmp_path, monkeypatch, limits, reason):
    service, sid, aid = registered_case(client, tmp_path)
    service.settings = replace(service.settings, share_result_summaries=True)
    scope = propose_scope(client, sid, aid, **limits)
    monkeypatch.setattr("bridge.web.provider.converse", next_check_or_stop)
    approve_scope(client, sid, scope)
    done = settle(client, sid)["assessment"]
    assert done["stop_reason"] == reason
    assert done["tool_runs_used"] == done["model_turns_used"] == 1
    response = client.post(f"/api/sessions/{sid}/assessment/resume",
                          json={"scope_id": scope["scope_id"], "scope_digest": scope["scope_digest"]})
    assert response.status_code == 409 and response.json()["detail"] == reason
    assert len(service.load(sid)["_tool_runs"]) == 1


def test_repeated_scientific_request_ignores_new_random_request_ids(client, tmp_path, monkeypatch):
    service, sid, aid = registered_case(client, tmp_path)
    service.settings = replace(service.settings, share_result_summaries=True)
    scope = propose_scope(client, sid, aid)
    option = []
    def repeat(settings, messages, context):
        from bridge.web.provider import Action
        if not option:
            option.append(context["options"][0]["id"])
        return Action.model_validate({"action": "assessment", "decision": {
            "action": "check", "option_id": option[0]}})
    monkeypatch.setattr("bridge.web.provider.converse", repeat)
    approve_scope(client, sid, scope)
    done = settle(client, sid)["assessment"]
    assert done["stop_reason"] == "unavailable_or_repeated_action"
    assert done["tool_runs_used"] == 1 and done["model_turns_used"] == 2
    assert len(service.load(sid)["_tool_runs"]) == 1


def test_malformed_provider_turn_is_consumed_without_dispatch(client, tmp_path, monkeypatch):
    service, sid, aid = registered_case(client, tmp_path)
    scope = propose_scope(client, sid, aid)
    def malformed(*args):
        from bridge.web.provider import parse_action
        return parse_action({"content": '{"action":"assessment","decision":{"action":"check","option_id":"not-valid"}}'})
    monkeypatch.setattr("bridge.web.provider.converse", malformed)
    approve_scope(client, sid, scope)
    done = settle(client, sid)["assessment"]
    assert done["stop_reason"] == "provider_action_invalid_or_unavailable"
    assert done["model_turns_used"] == 1 and done["tool_runs_used"] == 0
    assert service.load(sid)["_tool_runs"] == []


def test_scope_reports_actual_missing_selection_and_scientific_review_blocker(client, tmp_path):
    from test_web_report_inputs import confirmed_case
    service, sid, aid, _ = confirmed_case(client, tmp_path)
    scope = propose_scope(client, sid, aid, "P0-03", "default")
    approve_scope(client, sid, scope)
    done = settle(client, sid)["assessment"]
    assert done["stop_reason"] == "no_eligible_check"
    assert done["blockers"] == [{"tool_id": "P0-03", "mode_id": "default",
                                "reason_codes": ["scientific_source_review_pending"]}]
    assert done["tool_runs_used"] == done["model_turns_used"] == 0
    assert service.load(sid)["_tool_runs"] == []
    scope = propose_scope(client, sid, aid, "P0-06", "method_runtime")
    approve_scope(client, sid, scope)
    done = settle(client, sid)["assessment"]
    assert done["blockers"][0]["reason_codes"] == ["registered_selection_required"]


def test_disabled_sharing_does_not_send_result_or_private_facts_and_requires_opt_in(client, tmp_path, monkeypatch):
    service, sid, aid = registered_case(client, tmp_path)
    assert service.settings.share_result_summaries is False
    scope = propose_scope(client, sid, aid)
    def model(settings, messages, context):
        wire = json.dumps([messages, context])
        for secret in ("PRIVATE_NAME", "PRIVATE_SOURCE", "dopaminergic neurons", "private-cell-a", str(tmp_path)):
            assert secret not in wire
        assert context["evidence"] == [] and context["results_sent_to_model"] is False
        return next_check_or_stop(settings, messages, context)
    monkeypatch.setattr("bridge.web.provider.converse", model)
    approve_scope(client, sid, scope)
    done = settle(client, sid)["assessment"]
    assert done["stop_reason"] == "result_sharing_disabled"
    assert done["tool_runs_used"] == done["model_turns_used"] == 1
    assert done["evidence"][0]["summary"]["primary_denominator"]["n_observations"] == 10


@pytest.mark.parametrize("change", ["revision", "object", "reference"])
def test_scope_fences_drift_before_approval(client, tmp_path, change):
    from pathlib import Path
    from bridge.web.app import write_file
    service, sid, aid = registered_case(client, tmp_path)
    scope = propose_scope(client, sid, aid)
    state = service.load(sid)
    if change == "revision":
        state["_input_revision"] += 1
        service.save(state)
    elif change == "reference":
        service.settings = replace(service.settings, cell_state_measurement_spec_ref=None)
    else:
        resource_id = next(iter(state["_assessment"]["scope"]["binding"]["resources"]))
        record = state["_input_objects"][resource_id]
        path = Path(record["path"])
        write_file(path, path.read_bytes() + b" ")
    response = client.post(f"/api/sessions/{sid}/assessment/approve", json={
        "scope_id": scope["scope_id"], "scope_digest": scope["scope_digest"]})
    assert response.status_code == 409
    assert response.json()["detail"] in {"input_revision_changed", "scope_resource_changed"}
    assert service.load(sid)["_tool_runs"] == []


def test_stop_and_resume_keep_original_consent_and_dispatched_model_counter(client, tmp_path, monkeypatch):
    from threading import Event
    entered, released = Event(), Event()
    service, sid, aid = registered_case(client, tmp_path)
    scope = propose_scope(client, sid, aid)
    def slow(settings, messages, context):
        entered.set()
        assert released.wait(10)
        return next_check_or_stop(settings, messages, context)
    monkeypatch.setattr("bridge.web.provider.converse", slow)
    approve_scope(client, sid, scope)
    assert entered.wait(5)
    before = service.load(sid)["_assessment"]
    assert before["model_turns_used"] == 1 and before["tool_runs_used"] == 0
    try:
        stopped = client.post(f"/api/sessions/{sid}/stop", json={})
        assert stopped.status_code == 200
        assert stopped.json()["assessment"]["stop_reason"] == "user_stopped"
    finally:
        released.set()
    done = settle(client, sid)
    assert done["assessment"]["status"] == "stopped"
    assert service.load(sid)["_tool_runs"] == []
    monkeypatch.setattr("bridge.web.provider.converse", next_check_or_stop)
    resumed = client.post(f"/api/sessions/{sid}/assessment/resume", json={
        "scope_id": scope["scope_id"], "scope_digest": scope["scope_digest"]})
    assert resumed.status_code == 200
    done = settle(client, sid)
    after = service.load(sid)["_assessment"]
    assert after["authorization"] == before["authorization"]
    assert after["model_turns_used"] == 2 and after["tool_runs_used"] == 1


def test_provider_native_and_json_assessment_have_same_purpose_limited_action():
    from bridge.web.provider import action_tools, parse_action
    payload = {"decision": {"action": "stop", "reason": "no_discriminating_check"}}
    json_action = parse_action({"content": json.dumps({"action": "assessment", **payload})})
    native_action = parse_action({"content": None, "tool_calls": [{
        "type": "function", "function": {"name": "assessment", "arguments": json.dumps(payload)}}]},
        protocol="deepseek_tools")
    assert json_action == native_action
    assert [row["function"]["name"] for row in action_tools("assessment")] == ["assessment"]
    assert "assessment" not in [row["function"]["name"] for row in action_tools()]
    with pytest.raises(ValueError):
        parse_action({"content": '{"action":"assessment","decision":{"action":"check","option_id":"' + "0" * 64 + '","value":0.9}}'})


def test_unattributed_explanation_cannot_claim_a_hypothesis(client, tmp_path, monkeypatch):
    service, sid, aid = registered_case(client, tmp_path)
    scope = propose_scope(client, sid, aid)
    def unsupported(*args):
        from bridge.web.provider import Action
        return Action.model_validate({"action": "assessment", "decision": {
            "action": "explain", "text": "Target identity is established.",
            "hypotheses": [{"statement": "Target identity is established", "evidence_aliases": ["E-invented"],
                "competing_explanation": "Off-target mixture", "discriminating_check": "P0-05"}]}})
    monkeypatch.setattr("bridge.web.provider.converse", unsupported)
    approve_scope(client, sid, scope)
    done = settle(client, sid)["assessment"]
    assert done["stop_reason"] == "invalid_evidence_alias"
    assert service.load(sid)["_tool_runs"] == []


def test_registered_graph_query_reuses_version_and_has_receipt_without_new_artifacts(client, tmp_path, monkeypatch):
    from test_web_report_inputs import confirmed_case, run_stage
    service, sid, aid, body = confirmed_case(client, tmp_path)
    run_stage(client, sid, body, "P0-08")
    run_stage(client, sid, body, "P0-09")
    state = service.load(sid)
    graph_id, graph_record = next((identifier, row) for identifier, row in state["_input_objects"].items()
        if row["source"] == "tool_output" and row["schema_ref"] == "bridge://schemas/case-evidence-graph-manifest/v0.1")
    graph = service.inputs.verify(state, graph_record)
    query = {"object_version": "0.1.0", "query_name": "get_case_evidence_subgraph",
             "product_case_id": graph["product_case_ref"]["object_id"],
             "evidence_tiers": ["formal", "shadow", "exploratory"], "max_depth": 2, "max_nodes": 100}
    response = client.post(f"/api/sessions/{sid}/analysis-inputs/objects",
        params={"tool_id": "P0-09", "mode_id": "case_query", "role": "evidence_graph_query",
                "schema_ref": "bridge://schemas/evidence-graph-query/v0.1", "object_version": "0.1.0"},
        files={"file": ("query.json", json.dumps(query).encode(), "application/json")})
    assert response.status_code == 200, response.json()
    state = service.load(sid)
    query_id = next(reversed(state["_input_objects"]))
    selected = client.post(f"/api/sessions/{sid}/analysis-inputs", json=choice("P0-09", "case_query", [
        {"role": "evidence_graph_manifest", "input_id": graph_id},
        {"role": "evidence_graph_query", "input_id": query_id}]))
    assert selected.status_code == 200
    service.settings = replace(service.settings, share_result_summaries=True)
    scope = propose_scope(client, sid, aid, "P0-09", "case_query")
    before = service.load(sid)
    def query_then_stop(settings, messages, context):
        from bridge.web.provider import Action
        if context["options"]:
            assert context["options"][0]["kind"] == "query"
            return Action.model_validate({"action": "assessment", "decision": {
                "action": "query", "option_id": context["options"][0]["id"]}})
        assert context["evidence"][0]["summary"]["graph_version"] == 1
        assert len(context["evidence"][0]["summary"]["requirements"]) == 5
        assert all(item["state"] == "open" for item in context["evidence"][0]["summary"]["requirements"])
        return Action.model_validate({"action": "assessment", "decision": {
            "action": "stop", "reason": "no_discriminating_check"}})
    monkeypatch.setattr("bridge.web.provider.converse", query_then_stop)
    approve_scope(client, sid, scope)
    done = settle(client, sid)
    assert done["assessment"]["stop_reason"] == "no_discriminating_check", done["assessment"]
    assert done["assessment"]["tool_runs_used"] == 1
    assert done["assessment"]["evidence"][0]["summary"]["graph_version"] == 1
    after = service.load(sid)
    assert after["_input_revision"] == before["_input_revision"]
    assert len(after["_tool_runs"]) == len(before["_tool_runs"]) + 1
    assert after["_input_objects"] == before["_input_objects"]
    assert after["_artifacts"] == before["_artifacts"]
    receipt = json.loads((service.directory(sid) / "receipts" / after["_tool_runs"][-1]["file"]).read_bytes())
    assert receipt["artifacts"] == [] and receipt["measurements"] == []
    assert receipt["result"]["graph_id"] == graph["graph_id"]
    assert receipt["result"]["graph_version"] == 1


@pytest.mark.parametrize("tool,module", [("P0-03", "test_p0_03_target_regional"),
                                          ("P0-04", "test_p0_04_developmental_compatibility")])
def test_real_target_and_development_results_expose_canonical_units_and_denominators(
        client, tmp_path, monkeypatch, tool, module):
    from bridge.web.app import write_file
    from bridge.tool_packages.p0_02_cell_state.measurement_specs import load_measurement_spec
    from bridge.tool_packages.p0_02_cell_state.reference import DENIED_SOURCE_FAMILIES
    import hashlib
    source = importlib.import_module(module)
    spec = load_measurement_spec("CELLSTATE-scRNA-shadow-v0.1")
    values = source._base_payloads()
    values["measurement_spec"]["reference_refs"] = [spec.reference_refs[0] + "@1.0.0"]
    values["reference_manifest"].update(snapshot_id=spec.reference_refs[0],
        marker_program_sha256=hashlib.sha256(b"{}").hexdigest(),
        measurement_spec_ids=[*values["reference_manifest"]["measurement_spec_ids"], spec.measurement_spec_id],
        prohibited_source_families=sorted(DENIED_SOURCE_FAMILIES))
    supplied = tmp_path / "supplied"
    supplied.mkdir()
    request = source._request(supplied, values)
    reference_root = tmp_path / "references"
    snapshot = reference_root / spec.reference_refs[0]
    snapshot.mkdir(parents=True, mode=0o700)
    for ref in request.object_inputs:
        if ref.role in {"reference_manifest", "annotation_vocabulary"}:
            write_file(snapshot / (ref.role + ".json"), ref.path.read_bytes())
    write_file(snapshot / "marker_programs.json", b"{}")
    monkeypatch.setenv("BRIDGE_REFERENCE_ROOT", str(reference_root))
    monkeypatch.setenv("BRIDGE_ALLOW_CANDIDATE_REFERENCES", "1")
    service, sid, aid = science_case(client, tmp_path)
    service.settings = replace(service.settings, share_result_summaries=True)
    catalog = client.get(f"/api/sessions/{sid}/analysis-inputs").json()
    resources = {item["label"]: item["id"] for item in catalog["objects"] if item["source"] == "system_resource"}
    objects = upload_request(client, sid, request.model_copy(update={"object_inputs": [
        ref for ref in request.object_inputs if ref.role not in resources]}), "default")
    objects.extend({"role": role, "input_id": identifier} for role, identifier in resources.items())
    assert client.post(f"/api/sessions/{sid}/analysis-inputs", json=choice(tool, "default", objects)).status_code == 200
    scope = propose_scope(client, sid, aid, tool, "default")
    monkeypatch.setattr("bridge.web.provider.converse", next_check_or_stop)
    approve_scope(client, sid, scope)
    done = settle(client, sid)["assessment"]
    assert done["tool_runs_used"] == 1 and done["stop_reason"] == "no_discriminating_check", done
    evidence = done["evidence"][0]
    assert evidence["state"] == "available"
    measurements = evidence["measurements"]
    assert len(measurements) == (3 if tool == "P0-03" else 10)
    assert all(item["unit"] == "fraction" for item in measurements)
    assert all(item["measurement_class"] == "gate_input_measurement" for item in measurements)
    assert all(item["domain_score"] is None for item in measurements)
    if tool == "P0-03":
        channel = evidence["summary"]["channels"][0]
        assert channel["target_identity_fraction"] == {"role": "configured_target_identity", "numerator": 60, "denominator": 100, "fraction": 0.6}
        assert channel["regional_fidelity_fraction"] == {"role": "configured_regional_fidelity", "numerator": 60, "denominator": 80, "fraction": 0.75}
    else:
        assert evidence["summary"]["whole_product_profile"]["denominator"] == 12
        assert evidence["summary"]["target_related_profile"]["denominator"] == 11


def test_restart_interruption_retains_durable_budget_and_does_not_execute(client, tmp_path, monkeypatch):
    from bridge.web.app import Service
    from bridge.web.assessment import ScopeIdentity
    from threading import Event
    entered, release = Event(), Event()
    service, sid, aid = registered_case(client, tmp_path)
    scope = propose_scope(client, sid, aid)
    def pending(settings, messages, context):
        entered.set()
        assert release.wait(10)
        raise RuntimeError("external connection lost")
    monkeypatch.setattr("bridge.web.provider.converse", pending)
    approve_scope(client, sid, scope)
    assert entered.wait(5)
    # Capture actual durable in-flight state, then finish the original worker.
    dispatched = service.load(sid)
    release.set()
    settle(client, sid)
    service.save(dispatched)
    restored = Service(service.settings)
    try:
        state = restored.load(sid)
        assert state["_assessment"]["status"] == "interrupted"
        assert state["_assessment"]["stop_reason"] == "restart_interrupted"
        assert state["_assessment"]["model_turns_used"] == 1
        assert state["_assessment"]["authorization"] == dispatched["_assessment"]["authorization"]
        assert state["_tool_runs"] == []
    finally:
        restored.pool.shutdown(wait=True)


def test_scope_data_view_and_approval_limits_are_visible_but_resources_remain_private(client, tmp_path):
    service, sid, aid = registered_case(client, tmp_path)
    scope = propose_scope(client, sid, aid)
    assert scope["data_view"]["state"] == "not_available"
    assert scope["stop_conditions"] == ["input_or_resource_change", "explicit_stop", "finite_budgets",
                                        "no_eligible_check", "necessary_fact", "result_sharing_disabled"]
    assert scope["resources"] and all(set(row) == {"alias", "schema_ref", "object_version", "sha256", "source"}
                                      for row in scope["resources"])
    assert scope["max_tool_runs"] == 3 and scope["max_model_turns"] == 4
    assert "PRIVATE_NAME" not in json.dumps(scope)


@pytest.mark.parametrize("mode", ["comparison_initial_v2", "invented"])
def test_disallowed_or_unknown_mode_never_starts_scope(client, tmp_path, mode):
    service, sid, aid = registered_case(client, tmp_path)
    response = client.post(f"/api/sessions/{sid}/assessment/propose", json={
        "question": "Check evidence", "upload_id": aid, "allowed_modes": [{"tool_id": "P0-09", "mode_id": mode}],
        "max_tool_runs": 3, "max_model_turns": 4})
    assert response.status_code == 422
    assert service.load(sid).get("_assessment") is None


def test_result_bound_hypothesis_is_stored_without_changing_scientific_objects(client, tmp_path, monkeypatch):
    service, sid, aid = registered_case(client, tmp_path)
    service.settings = replace(service.settings, share_result_summaries=True)
    scope = propose_scope(client, sid, aid)
    objects = service.load(sid)["_input_objects"]
    def model(settings, messages, context):
        from bridge.web.provider import Action
        assert context["question"] == scope["question"]
        if not context["evidence"]:
            return next_check_or_stop(settings, messages, context)
        return Action.model_validate({"action": "assessment", "decision": {
            "action": "explain", "text": "This candidate interpretation still needs discriminating evidence.",
            "hypotheses": [{"statement": "The registered target composition may explain this signal.",
                "evidence_aliases": [context["evidence"][0]["alias"]],
                "competing_explanation": "An unresolved role assignment may also explain it.",
                "discriminating_check": "P0-05"}]}})
    monkeypatch.setattr("bridge.web.provider.converse", model)
    approve_scope(client, sid, scope)
    done = settle(client, sid)
    assert done["assessment"]["stop_reason"] == "explanation_complete"
    assert len(done["assessment"]["hypotheses"]) == 1
    assert done["assessment"]["hypotheses"][0]["evidence_aliases"] == [
        done["assessment"]["evidence"][0]["alias"]]
    current = service.load(sid)
    assert all(current["_input_objects"][key] == value for key, value in objects.items())
    assert current["_input_revision"] == scope["input_revision"]
    assert done["assessment"]["scope_grants_scientific_approval"] is False


def test_reference_drift_during_model_turn_blocks_before_admission(client, tmp_path, monkeypatch):
    service, sid, aid = registered_case(client, tmp_path)
    scope = propose_scope(client, sid, aid)
    def model(settings, messages, context):
        service.settings = replace(service.settings, cell_state_measurement_spec_ref=None)
        return next_check_or_stop(settings, messages, context)
    monkeypatch.setattr("bridge.web.provider.converse", model)
    approve_scope(client, sid, scope)
    done = settle(client, sid)
    assert done["assessment"]["stop_reason"] == "scope_resource_changed"
    assert done["assessment"]["tool_runs_used"] == 0
    assert done["assessment"]["model_turns_used"] == 1
    assert service.load(sid)["_tool_runs"] == []


def test_worker_capacity_rejection_keeps_scope_authorization_resumable(client, tmp_path, monkeypatch):
    service, sid, aid = registered_case(client, tmp_path)
    scope = propose_scope(client, sid, aid)
    held = 0
    while service.capacity.acquire(blocking=False):
        held += 1
    try:
        response = client.post(f"/api/sessions/{sid}/assessment/approve", json={
            "scope_id": scope["scope_id"], "scope_digest": scope["scope_digest"]})
        assert response.status_code == 429
        state = service.load(sid)
        assert state["_assessment"]["status"] == "blocked"
        assert state["_assessment"]["stop_reason"] == "worker_busy"
        assert state["_assessment"]["authorization"] is not None
        assert state["_assessment"]["model_turns_used"] == 0
    finally:
        for _ in range(held):
            service.capacity.release()
    monkeypatch.setattr("bridge.web.provider.converse", next_check_or_stop)
    response = client.post(f"/api/sessions/{sid}/assessment/resume", json={
        "scope_id": scope["scope_id"], "scope_digest": scope["scope_digest"]})
    assert response.status_code == 200, response.json()
    assert settle(client, sid)["assessment"]["tool_runs_used"] == 1


def test_new_in_scope_qc_output_is_not_an_input_revision(client, tmp_path, monkeypatch):
    service, sid, aid = science_case(client, tmp_path)
    service.settings = replace(service.settings, share_result_summaries=True)
    selected = client.post(f"/api/sessions/{sid}/analysis-inputs",
                           json=choice("P0-01", None, assets=[aid]))
    assert selected.status_code == 200, selected.json()
    scope = propose_scope(client, sid, aid, "P0-01", None)
    monkeypatch.setattr("bridge.web.provider.converse", next_check_or_stop)
    approve_scope(client, sid, scope)
    done = settle(client, sid)
    assert done["assessment"]["stop_reason"] == "no_discriminating_check", done
    assert done["assessment"]["tool_runs_used"] == 1
    assert done["assessment"]["model_turns_used"] == 2
    assert service.load(sid)["_input_revision"] == scope["input_revision"]


def test_real_exploratory_missing_gene_keeps_partial_and_all_96_cells(client, tmp_path, monkeypatch):
    from test_p0_06_exploratory import _request, _payload, _with_input
    from test_web_service import new_session, confirm_change
    from test_web_intake import stage, stated_facts
    request = _request(tmp_path, missing_gene=True)
    sid = new_session(client)["id"]
    response = client.post(f"/api/sessions/{sid}/uploads",
        files={"file": ("synthetic.h5ad", request.assets[0].path.read_bytes())})
    assert response.status_code == 200
    aid = response.json()["uploads"][0]["id"]
    confirm_change(client, sid, stage(client, sid, aid, stated_facts(
        source_family_id="synthetic-test-only", gene_symbol_column="gene_symbol")))
    payload = _payload(request)
    payload["data_view"]["artifact_id"] = aid
    payload["data_view"]["parent_asset_id"] = aid
    request = _with_input(request, payload)
    objects = upload_request(client, sid, request, "exploratory_process")
    selected = client.post(f"/api/sessions/{sid}/analysis-inputs",
        json=choice("P0-06", "exploratory_process", objects, [aid]))
    assert selected.status_code == 200, selected.json()
    service = client.app.state.service
    service.settings = replace(service.settings, share_result_summaries=True)
    scope = propose_scope(client, sid, aid, "P0-06", "exploratory_process")
    monkeypatch.setattr("bridge.web.provider.converse", next_check_or_stop)
    approve_scope(client, sid, scope)
    done = settle(client, sid)
    evidence = done["assessment"]["evidence"][0]
    assert evidence["state"] == "available", evidence
    assert evidence["execution_state"] == "partial"
    assert evidence["interpretation_scope"] == "exploratory"
    assert evidence["measurements"] == []
    result = evidence["summary"]
    assert result["runtime_mode"] == "exploratory_process"
    assert result["n_observations"] == 96
    assert result["independence_state"] == "unknown"
    assert result["state_review_status"] == "pending"
    assert result["n_independent_replicates"] is None
    assert result["cell_cycle"]["phase_counts"] is None
    assert result["cell_cycle"]["s_g2m_fraction"] is None
    assert result["cell_cycle"]["n_observations"] == 96
    missing = [row for row in result["program_summaries"] if row["program_id"] == "S"]
    assert len(missing) == 2
    assert all(row["assessment_state"] == "not_assessed" and row["mean"] is None for row in missing)
    assert "observation_id" not in json.dumps(result) and "ABSENT" not in json.dumps(result)
    # A caller changes the registered DataView descriptor: this is a new fact/input
    # revision even when its underlying matrix checksum remains unchanged.
    next_scope = propose_scope(client, sid, aid, "P0-06", "exploratory_process")
    payload["data_view"]["view_id"] = "view:user-selected-revision"
    changed = _with_input(request, payload)
    new_objects = upload_request(client, sid, changed, "exploratory_process")
    selected = client.post(f"/api/sessions/{sid}/analysis-inputs",
        json=choice("P0-06", "exploratory_process", new_objects, [aid]))
    assert selected.status_code == 200
    assert selected.json()["assessment"]["status"] == "blocked"
    assert selected.json()["assessment"]["stop_reason"] == "input_revision_changed"
    rejected = client.post(f"/api/sessions/{sid}/assessment/approve", json={
        "scope_id": next_scope["scope_id"], "scope_digest": next_scope["scope_digest"]})
    assert rejected.status_code == 409
    assert len(service.load(sid)["_tool_runs"]) == 1


def test_unrelated_manual_selection_is_not_opened_or_bound_to_scope(client, tmp_path):
    from pathlib import Path
    from bridge.web.app import write_file
    service, sid, aid = registered_case(client, tmp_path)
    import test_p0_06_proliferation_stress_response as p006
    extra = tmp_path / "unrelated"
    extra.mkdir()
    refs = upload_request(client, sid, p006._request(extra), "legacy_aggregation")
    assert client.post(f"/api/sessions/{sid}/analysis-inputs",
                       json=choice("P0-06", "legacy_aggregation", refs)).status_code == 200
    state = service.load(sid)
    unrelated_id = refs[0]["input_id"]
    path = Path(state["_input_objects"][unrelated_id]["path"])
    write_file(path, path.read_bytes() + b" ")
    scope = propose_scope(client, sid, aid, "P0-05")
    assert scope["status"] == "proposed"
    assert unrelated_id not in service.load(sid)["_assessment"]["scope"]["binding"]["resources"]
