"""Scientific intent is projected only for a reviewed draft request."""
from __future__ import annotations
from copy import deepcopy
from dataclasses import replace
import json

import pytest
from fastapi import HTTPException

from bridge.web.provider import parse_action
from test_web_service import client, confirm_change, new_session, settle
from test_web_intake import uploaded, stage, stated_facts


def science_case(client, tmp_path):
    sid, aid = uploaded(client, tmp_path)
    facts = stated_facts(product_name="PRIVATE_NAME", source_family_id="PRIVATE_SOURCE",
                         target_cell_type="dopaminergic neurons", target_stage="early neuronal state")
    confirm_change(client, sid, stage(client, sid, aid, facts))
    service = client.app.state.service
    service.settings = replace(service.settings, cell_state_measurement_spec_ref="CELLSTATE-scRNA-shadow-v0.1")
    assert hasattr(service, "scientific_inputs"), "scientific input construction is not connected"
    return service, sid, aid


def candidate():
    return {"label_level": "L1", "roles": [{
        "state_id": "L1:Neuron_DA", "product_role": "target",
        "source_ids": ["state-review:L1:Neuron_DA"],
        "rationale": "The local review defines a dopaminergic neuronal state; product-role suitability remains a candidate."
    }], "development": [], "regional_denominator_state_ids": [], "regional_target_state_ids": []}


def propose(service, sid, aid, value=None):
    from bridge.web.scientific_inputs import ScienceCandidate
    state = service.load(sid)
    draft = service.scientific_inputs.propose(state, aid, ScienceCandidate.model_validate(value or candidate()))
    service.save(state)
    return draft


def test_scientific_context_projects_only_confirmed_three_field_intent(client, tmp_path):
    service, sid, aid = science_case(client, tmp_path)
    context = service.scientific_inputs.context(service.load(sid), aid)
    assert context["purpose"] == "scientific_input_draft"
    assert context["product_intent"] == {"product_family": "hpsc_mda",
        "target_cell_type": "dopaminergic neurons", "target_stage": "early neuronal state"}
    wire = json.dumps(context)
    for secret in ("PRIVATE_NAME", "PRIVATE_SOURCE", "private-cell-a", "MT-ND1", str(tmp_path)):
        assert secret not in wire
    assert context["sources"]
    assert "n_observations" not in wire and "sha256" not in wire


@pytest.mark.parametrize("change", ["pending", "stale"])
def test_unconfirmed_or_stale_intent_cannot_enter_draft_context(client, tmp_path, change):
    service, sid, aid = science_case(client, tmp_path)
    state = service.load(sid)
    if change == "pending":
        state["input_review_required"] = True
    else:
        state["_uploads"][aid]["source_family_id"] = "changed"
    with pytest.raises((ValueError, HTTPException)):
        service.scientific_inputs.context(state, aid)


def test_scientific_confirmation_registers_drafts_without_independence_or_tool_run(client, tmp_path):
    service, sid, aid = science_case(client, tmp_path)
    before = service.load(sid)
    draft = propose(service, sid, aid)
    assert draft["status"] == "pending"
    assert service.load(sid)["_input_objects"] == before["_input_objects"]
    response = client.post(f"/api/sessions/{sid}/scientific-inputs/confirm",
        json={"draft_id": draft["id"], "draft_digest": draft["digest"]})
    assert response.status_code == 200, response.json()
    current = service.load(sid)
    saved = current["_scientific_drafts"][-1]
    objects = {role: service.inputs.verify(current, current["_input_objects"][identifier])
               for role, identifier in saved["object_ids"].items()}
    assert {"product_case", "product_definition_card", "state_role_map"} <= set(objects)
    case = objects["product_case"]
    assert case["independence_group_refs"] == [] and case["biological_unit_manifest_ref"] is None
    assert objects["product_definition_card"]["review_state"] == "draft"
    roles = objects["state_role_map"]["assignments"]
    assert next(row for row in roles if row["state_id"] == "L1:Neuron_DA")["product_role"] == "target"
    assert all(row["product_role"] == "role_unresolved" for row in roles if row["state_id"] != "L1:Neuron_DA")
    assert saved["attestation_state"] == "not_confirmed"
    assert current["_tool_runs"] == before["_tool_runs"] and current["plan"] is None
    again = client.post(f"/api/sessions/{sid}/scientific-inputs/confirm",
        json={"draft_id": draft["id"], "draft_digest": draft["digest"]})
    assert again.status_code == 200
    assert service.load(sid)["_input_objects"] == current["_input_objects"]


@pytest.mark.parametrize("invalid", ["source", "state", "foreign_source"])
def test_scientific_candidate_requires_matching_local_source(client, tmp_path, invalid):
    service, sid, aid = science_case(client, tmp_path)
    proposed = candidate()
    if invalid == "state":
        proposed["roles"][0]["state_id"] = "L1:invented"
    else:
        proposed["roles"][0]["source_ids"] = [
            "SOURCE-INVENTED" if invalid == "source" else "state-review:L1:Astrocyte"]
    before = service.load(sid)
    with pytest.raises((ValueError, HTTPException)):
        propose(service, sid, aid, proposed)
    assert service.load(sid) == before


def test_stale_and_cross_session_confirmation_do_not_publish_objects(client, tmp_path):
    service, sid, aid = science_case(client, tmp_path)
    draft = propose(service, sid, aid)
    body = {"draft_id": draft["id"], "draft_digest": draft["digest"]}
    other = new_session(client)["id"]
    assert client.post(f"/api/sessions/{other}/scientific-inputs/confirm", json=body).status_code == 409
    confirm_change(client, sid, stage(client, sid, aid, stated_facts(target_stage="changed")))
    before = service.load(sid)
    assert client.post(f"/api/sessions/{sid}/scientific-inputs/confirm", json=body).status_code == 409
    assert service.load(sid) == before


@pytest.mark.parametrize("protocol", ["json", "deepseek_tools"])
def test_scientific_actions_are_closed_and_supported_in_both_transports(protocol):
    payload = {"action": "propose_scientific_inputs", "upload_id": "a" * 32, "candidate": candidate()}
    def message(value):
        if protocol == "json":
            return {"content": json.dumps(value)}
        return {"tool_calls": [{"type": "function", "function": {
            "name": value["action"], "arguments": json.dumps({k: v for k, v in value.items() if k != "action"})}}]}
    try:
        action = parse_action(message(payload), protocol)
    except ValueError:
        action = None
    assert action is not None, "provider cannot propose constrained scientific candidates"
    assert action.candidate.roles[0].state_id == "L1:Neuron_DA"
    payload["candidate"]["measurement_value"] = 1.0
    with pytest.raises(ValueError):
        parse_action(message(payload), protocol)


def test_draft_request_uses_separate_purpose_and_private_reply_never_leaks_to_chat(client, tmp_path, monkeypatch):
    service, sid, aid = science_case(client, tmp_path)
    captured = []
    def reply(settings, messages, context):
        captured.append({"messages": messages, "context": context})
        if context.get("purpose") == "scientific_input_draft":
            return parse_action({"content": json.dumps({
                "action": "propose_scientific_inputs", "upload_id": aid, "candidate": candidate()})})
        return parse_action({"content": '{"action":"reply","text":"Next steps."}'})
    monkeypatch.setattr("bridge.web.app.converse", reply)
    assert client.post(f"/api/sessions/{sid}/scientific-inputs/draft", json={"upload_id": aid}).status_code == 200
    done = settle(client, sid)
    assert done["error"] is None and done["scientific_drafts"][-1]["status"] == "pending"
    assert captured[0]["context"]["product_intent"]["target_stage"] == "early neuronal state"
    client.post(f"/api/sessions/{sid}/messages", json={"text": "What remains?"})
    assert settle(client, sid)["error"] is None
    wire = json.dumps(captured[-1])
    assert "early neuronal state" not in wire and "dopaminergic neurons" not in wire
    assert "product_intent" not in captured[-1]["context"] and "candidate" not in captured[-1]["context"]

@pytest.mark.parametrize("protocol", ["json", "deepseek_tools"])
def test_actual_provider_wire_constructs_scientific_draft(client, tmp_path, monkeypatch, protocol):
    import httpx
    from jsonschema import Draft202012Validator
    service, sid, aid = science_case(client, tmp_path)
    service.settings = replace(service.settings, model_action_protocol=protocol)
    original, calls = httpx.Client, []
    def wire(request):
        value = json.loads(request.content)
        calls.append(value)
        context = json.loads(value["messages"][0]["content"].split("Safe execution context: ", 1)[1])
        assert context["purpose"] == "scientific_input_draft"
        assert "PRIVATE_NAME" not in json.dumps(value) and "PRIVATE_SOURCE" not in json.dumps(value)
        payload = {"action": "propose_scientific_inputs", "upload_id": aid, "candidate": candidate()}
        if protocol == "deepseek_tools":
            function = next(row["function"] for row in value["tools"]
                            if row["function"]["name"] == "propose_scientific_inputs")
            arguments = {key: item for key, item in payload.items() if key != "action"}
            Draft202012Validator(function["parameters"]).validate(arguments)
            message = {"tool_calls": [{"type": "function", "function": {
                "name": payload["action"], "arguments": json.dumps(arguments)}}]}
        else:
            message = {"content": json.dumps(payload)}
        return httpx.Response(200, json={"choices": [{"message": message}]})
    monkeypatch.setattr("bridge.web.provider.httpx.Client",
        lambda **kwargs: original(**{**kwargs, "transport": httpx.MockTransport(wire)}))
    assert client.post(f"/api/sessions/{sid}/scientific-inputs/draft", json={"upload_id": aid}).status_code == 200
    result = settle(client, sid)
    assert result["error"] is None and len(calls) == 1
    assert result["scientific_drafts"][-1]["candidate"]["roles"][0]["product_role"] == "target"


def test_supported_regional_and_development_candidates_materialize_without_review_promotion(client, tmp_path):
    service, sid, aid = science_case(client, tmp_path)
    value = candidate()
    value["development"] = [{"state_id": "L1:Neuron_DA", "stage_role": "within_window",
        "source_ids": ["state-review:L1:Neuron_DA"], "rationale": "Candidate neuronal window, not fetal-age equivalence."}]
    value["regional_denominator_state_ids"] = ["L1:Neuron_DA"]
    value["regional_target_state_ids"] = ["L1:Neuron_DA"]
    draft = propose(service, sid, aid, value)
    response = client.post(f"/api/sessions/{sid}/scientific-inputs/confirm",
        json={"draft_id": draft["id"], "draft_digest": draft["digest"]})
    assert response.status_code == 200
    state = service.load(sid)
    saved = state["_scientific_drafts"][-1]
    objects = {role: service.inputs.verify(state, state["_input_objects"][identifier])
               for role, identifier in saved["object_ids"].items()}
    assert objects["development_window_spec"]["review_state"] == "candidate"
    assert objects["development_window_spec"]["confirmed_at"] is None
    assert objects["target_regional_assessment_spec"]["status"] == "candidate"
    assert "scientific_source_review_pending" in saved["unknowns"]
    attempted = client.post(f"/api/sessions/{sid}/prepare-analysis", json={"tool_id": "P0-03"})
    assert attempted.status_code == 200
    assert attempted.json()["error"] == "scientific_source_review_pending"
    assert state["_tool_runs"] == []


def test_changed_scientific_source_invalidates_pending_confirmation(client, tmp_path, monkeypatch):
    service, sid, aid = science_case(client, tmp_path)
    draft = propose(service, sid, aid)
    original = service.scientific_inputs._catalog
    def changed(state):
        context, binding, spec = original(state)
        return context, {**binding, "biological": "changed"}, spec
    monkeypatch.setattr(service.scientific_inputs, "_catalog", changed)
    before = service.load(sid)
    response = client.post(f"/api/sessions/{sid}/scientific-inputs/confirm",
        json={"draft_id": draft["id"], "draft_digest": draft["digest"]})
    assert response.status_code == 409
    assert service.load(sid) == before

@pytest.mark.parametrize("confirmed", [False, True])
def test_scientific_revision_is_new_pending_version_without_registration(client, tmp_path, confirmed):
    service, sid, aid = science_case(client, tmp_path)
    draft = propose(service, sid, aid)
    identity = {"draft_id": draft["id"], "draft_digest": draft["digest"]}
    if confirmed:
        assert client.post(f"/api/sessions/{sid}/scientific-inputs/confirm", json=identity).status_code == 200
    before = service.load(sid)
    revised = candidate()
    revised["roles"][0]["product_role"] = "role_unresolved"
    result = client.post(f"/api/sessions/{sid}/scientific-inputs/revise", json={**identity, "candidate": revised})
    assert result.status_code == 200, result.json()
    state = service.load(sid)
    assert state["_scientific_drafts"][-1]["id"] != draft["id"]
    assert state["_scientific_drafts"][-1]["status"] == "pending"
    assert state["_scientific_drafts"][-1]["candidate"] == revised
    assert state["_scientific_drafts"][0]["status"] == ("confirmed" if confirmed else "superseded")
    for key in ("_input_objects", "_tool_runs", "_input_selections"):
        assert state[key] == before[key]
    assert state["plan"] is None


@pytest.mark.parametrize("invalid", ["digest", "cross_session", "intake", "source"])
def test_scientific_revision_rejects_stale_or_foreign_identity(client, tmp_path, monkeypatch, invalid):
    service, sid, aid = science_case(client, tmp_path)
    draft = propose(service, sid, aid)
    body = {"draft_id": draft["id"], "draft_digest": draft["digest"], "candidate": candidate()}
    target = sid
    if invalid == "digest":
        body["draft_digest"] = "0" * 64
    elif invalid == "cross_session":
        target = new_session(client)["id"]
    elif invalid == "intake":
        confirm_change(client, sid, stage(client, sid, aid, stated_facts(target_stage="changed")))
    else:
        original = service.scientific_inputs._catalog
        def changed(state):
            context, binding, spec = original(state)
            return context, {**binding, "biological": "changed"}, spec
        monkeypatch.setattr(service.scientific_inputs, "_catalog", changed)
    before = service.load(target)
    result = client.post(f"/api/sessions/{target}/scientific-inputs/revise", json=body)
    assert result.status_code == 409
    assert service.load(target) == before

@pytest.mark.parametrize("protocol", ["json", "deepseek_tools"])
@pytest.mark.parametrize("repeated_invalid", [False, True])
@pytest.mark.parametrize("invalid_kind", ["source", "shape"])
def test_draft_correction_is_bounded_and_never_registers_invalid_sources(client, tmp_path, monkeypatch, protocol, repeated_invalid, invalid_kind):
    import httpx
    service, sid, aid = science_case(client, tmp_path)
    service.settings = replace(service.settings, model_action_protocol=protocol)
    original, requests = httpx.Client, []
    def wire(request):
        payload = json.loads(request.content)
        requests.append(payload)
        value = candidate()
        if len(requests) == 1 or repeated_invalid:
            if invalid_kind == "source":
                value["roles"][0]["source_ids"] = ["state-review:L1:Astrocyte"]
            else:
                value["label_level"] = "L2"
        arguments = {"upload_id": aid, "candidate": value}
        if protocol == "deepseek_tools":
            message = {"tool_calls": [{"type": "function", "function": {
                "name": "propose_scientific_inputs", "arguments": json.dumps(arguments)}}]}
        else:
            message = {"content": json.dumps({"action": "propose_scientific_inputs", **arguments})}
        return httpx.Response(200, json={"choices": [{"message": message}]})
    monkeypatch.setattr("bridge.web.provider.httpx.Client",
        lambda **kwargs: original(**{**kwargs, "transport": httpx.MockTransport(wire)}))
    before = service.load(sid)
    assert client.post(f"/api/sessions/{sid}/scientific-inputs/draft", json={"upload_id": aid}).status_code == 200
    done = settle(client, sid)
    assert len(requests) == 2, "a source mismatch needs one bounded correction, not an unhandled worker failure"
    corrected_context = json.loads(requests[1]["messages"][0]["content"].split("Safe execution context: ", 1)[1])
    assert corrected_context["validation_feedback"] == ("scientific_source_not_supported" if invalid_kind == "source" else "scientific_candidate_shape_invalid")
    assert "PRIVATE_NAME" not in json.dumps(requests) and "PRIVATE_SOURCE" not in json.dumps(requests)
    state = service.load(sid)
    assert state["_tool_runs"] == before["_tool_runs"]
    assert state["_input_objects"] == before["_input_objects"]
    if repeated_invalid:
        assert done["status"] == "idle" and done["error"] == "scientific_candidate_invalid"
        assert done["scientific_drafts"] == []
    else:
        assert done["error"] is None and done["scientific_drafts"][-1]["status"] == "pending"
