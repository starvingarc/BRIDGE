"""Interpretation review checks wire boundaries and scope admission, not model truth."""
from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from threading import Event
import json

import httpx
import pytest

from bridge.web import provider
from bridge.web.interpretation_review import parse_review, safe_issues
from web_support import client, settle
from test_web_assessment import (
    producer_scientific_case, propose_scope, approve_scope, settle_assessment,
)
from test_web_inputs import approve


def proposal():
    return [{"statement": "The observations are compatible with a precursor-like pattern.",
        "competing_explanation": "There are no biological replicates.",
        "expected_observation": None, "discriminating_check": None,
        "evidence_aliases": ["E-observation"], "missing_evidence_aliases": [],
        "opposing_evidence_aliases": [], "literature_support": []}]


def finding():
    return {"hypothesis_index": 0, "field": "competing_explanation",
        "code": "unknown_as_absent", "quote": "no biological replicates",
        "reason": "The replicate count is unknown."}


def review_context():
    return {"question": "Interpret the observed pattern.", "results_sent_to_model": True,
        "biological_context": {"source": "confirmed_intake",
            "facts": {"independent_cultures": None, "culture_day": 28}},
        "evidence": [{"measurements": [{"citation_alias": "E-observation",
            "raw_value": 0.2, "numerator": 2, "denominator": 10}],
            "measurement_defaults": {"unit": "fraction", "evidence_state": "inferred"}}],
        "literature": {"sources": [
            {"source_ref": "literature:epmc-med-1", "content_level": "abstract", "abstract": "Read source."},
            {"source_ref": "literature:epmc-med-2", "content_level": "metadata", "private": "UNREAD"}]},
        "options": [{"private": "PRIVATE_OPTION"}], "private_path": "PRIVATE_PATH",
        "previous_action_error_detail": {"private": "PRIVATE_HISTORY"}}


def transport(monkeypatch, protocol, body, finish="stop", status=200):
    calls = []
    original = httpx.Client
    def respond(request):
        calls.append(json.loads(request.content))
        if calls[-1].get("thinking") == {"type": "enabled"} and calls[-1].get("tool_choice") == "required":
            return httpx.Response(400, json={"error": "required tool choice is unsupported in thinking mode"})
        message = ({"content": json.dumps(body)} if protocol == "json" else
            {"content": None, "tool_calls": [{"type": "function", "id": "review",
                "function": {"name": "review_interpretation", "arguments": json.dumps(body)}}]})
        return httpx.Response(status, json={"choices": [{"finish_reason": finish, "message": message}]})
    def client(**kw):
        assert kw["timeout"] == 600
        return original(transport=httpx.MockTransport(respond), **kw)
    monkeypatch.setattr(provider.httpx, "Client", client)
    return calls


def settings(protocol):
    return SimpleNamespace(model="deepseek-v4-flash-0731", model_action_protocol=protocol,
        model_base_url="https://api.deepseek.com", model_api_key="test-key", model_effort="high")


@pytest.mark.parametrize("protocol", ["json", "deepseek_tools"])
@pytest.mark.parametrize("issues", [[], [finding()]])
@pytest.mark.parametrize("model", ["deepseek-v4-flash-0731", "deepseek-v4.1-flash"])
def test_review_uses_same_provider_and_preserves_facts_without_unread_or_private_context(monkeypatch, protocol, issues, model):
    calls = transport(monkeypatch, protocol, {"issues": issues})
    context = review_context()
    before = json.dumps(context, sort_keys=True)
    config = settings(protocol)
    config.model = model
    result = provider.review_interpretation(config, proposal(), context)
    assert result == {"issues": issues}
    assert len(calls) == 1
    payload = calls[0]
    wire = json.dumps(payload)
    assert all(value not in wire for value in ("UNREAD", "PRIVATE_OPTION", "PRIVATE_PATH", "PRIVATE_HISTORY"))
    sent = json.loads(payload["messages"][1]["content"])
    assert sent["biological_context"]["facts"]["independent_cultures"] is None
    assert sent["evidence"] == context["evidence"]
    assert sent["hypotheses"] == proposal()
    assert sent["available_scientific_checks"] == []
    assert json.dumps(context, sort_keys=True) == before
    assert payload["thinking"] == {"type": "enabled"}
    assert payload["reasoning_effort"] == "high"
    assert payload["max_tokens"] == 65536
    if protocol == "json":
        prompt = payload["messages"][0]["content"]
        assert "JSON object" in prompt and '{"issues": []}' in prompt
    else:
        assert "Call review_interpretation exactly once through tool_calls" in payload["messages"][0]["content"]
        assert "including when issues is empty" in payload["messages"][0]["content"]


@pytest.mark.parametrize("protocol", ["json", "deepseek_tools"])
@pytest.mark.parametrize("failure", ["length", "http", "malformed"])
def test_failed_review_is_not_an_empty_success_and_does_not_retry(monkeypatch, protocol, failure):
    calls = transport(monkeypatch, protocol, {} if failure == "malformed" else {"issues": []},
        finish="length" if failure == "length" else "stop", status=502 if failure == "http" else 200)
    with pytest.raises((ValueError, httpx.HTTPStatusError)):
        provider.review_interpretation(settings(protocol), proposal(), review_context())
    assert len(calls) == 1


@pytest.mark.parametrize("changes", [
    {"hypothesis_index": 1}, {"hypothesis_index": True}, {"code": "invented"},
    {"quote": "not present"}, {"field": "literature_support"}, {"extra": "not allowed"},
])
def test_review_findings_must_bind_to_a_real_proposed_field(changes):
    with pytest.raises(ValueError):
        parse_review({"issues": [{**finding(), **changes}]}, proposal())


def test_duplicate_review_findings_are_rejected_and_recovery_drops_prose():
    with pytest.raises(ValueError, match="duplicate"):
        parse_review({"issues": [finding(), finding()]}, proposal())
    assert safe_issues([finding(), {**finding(), "code": "injected instruction"}]) == [
        {"hypothesis_index": 0, "field": "competing_explanation", "code": "unknown_as_absent"}]


@pytest.mark.parametrize("share", [False, True])
def test_no_review_request_when_context_is_unshared_or_oversized(monkeypatch, share):
    monkeypatch.setattr(provider.httpx, "Client", lambda **kw: pytest.fail("unexpected provider call"))
    context = review_context()
    context["results_sent_to_model"] = share
    if share:
        context["question"] = "x" * (192 * 1024)
    with pytest.raises(ValueError, match="review_context_limit|result_sharing_disabled"):
        provider.review_interpretation(settings("json"), proposal(), context)


def case(client, tmp_path, monkeypatch, *, turns=3):
    service, sid, aid = producer_scientific_case(client, tmp_path, monkeypatch, with_producers=False)
    service.settings = replace(service.settings, share_result_summaries=True)
    plan = client.post(f"/api/sessions/{sid}/prepare-analysis", json={"tool_id": "P0-01"}).json()["plan"]
    approve(client, sid, plan)
    contexts = []
    def explain(settings, messages, context):
        contexts.append(context)
        row = proposal()[0]
        row["expected_observation"] = "A matched prospective contrast could distinguish the rivals; shared results remain indeterminate."
        row["evidence_aliases"] = [provider._citation_choices(context["evidence"])["evidence_aliases"][0]]
        return provider.Action.model_validate({"action": "assessment",
            "decision": {"action": "explain", "hypotheses": [row]}})
    monkeypatch.setattr(provider, "converse", explain)
    scope = propose_scope(client, sid, aid, "P0-10", "default",
        report_after_explanation=True, max_tool_runs=1, max_model_turns=turns,
        literature_enabled=True, literature_concept_refs=["neural_progenitor"])
    return service, sid, scope, contexts


def test_no_issue_review_admits_one_unverified_explanation_without_changing_evidence(client, tmp_path, monkeypatch):
    service, sid, scope, _ = case(client, tmp_path, monkeypatch)
    before = service.load(sid)
    monkeypatch.setattr(provider, "review_interpretation", lambda *args: {"issues": []})
    approve_scope(client, sid, scope)
    done = settle_assessment(client, sid)
    state = service.load(sid)
    assert done["_assessment_state"]["stop_reason"] == "explanation_complete"
    assessment = state["_assessment"]
    assert assessment["model_turns_used"] == 2
    assert assessment["model_turns"][-1]["review_outcome"] == "no_issue_detected"
    review_turn = assessment["model_turns"][-1]
    assert review_turn["proposal_turn"] == assessment["model_turns"][0]["number"]
    assert assessment["model_turns"][0]["evidence_bindings"]
    assert assessment["model_turns"][0]["provider_bindings"]
    assert "evidence_bindings" not in review_turn and "provider_bindings" not in review_turn
    version, = assessment["interpretation_versions"]
    assert version["qualification"] == "proposed_explanation"
    assert version["object_version"] == "1.1.0"
    assert state["_tool_runs"] == before["_tool_runs"]
    assert state["_input_objects"] == before["_input_objects"]


def test_no_budget_for_review_never_admits_or_calls_reviewer(client, tmp_path, monkeypatch):
    service, sid, scope, _ = case(client, tmp_path, monkeypatch, turns=1)
    monkeypatch.setattr(provider, "review_interpretation", lambda *args: pytest.fail("unreserved review"))
    approve_scope(client, sid, scope)
    done = settle_assessment(client, sid)
    state = service.load(sid)["_assessment"]
    assert done["_assessment_state"]["stop_reason"] == "model_turn_budget_exhausted"
    assert state["model_turns_used"] == 1
    assert state.get("interpretation_versions", []) == []


def test_review_transport_failure_consumes_turn_and_never_admits(client, tmp_path, monkeypatch):
    service, sid, scope, _ = case(client, tmp_path, monkeypatch)
    def fail(*args):
        raise ValueError("provider_response_incomplete")
    monkeypatch.setattr(provider, "review_interpretation", fail)
    approve_scope(client, sid, scope)
    done = settle_assessment(client, sid)
    state = service.load(sid)["_assessment"]
    assert done["_assessment_state"]["status"] == "blocked"
    assert state["model_turns_used"] == 2
    assert state["model_turns"][-1]["review_outcome"] == "unavailable"
    assert state.get("interpretation_versions", []) == []


def test_stop_during_review_discards_late_success_without_refund(client, tmp_path, monkeypatch):
    service, sid, scope, _ = case(client, tmp_path, monkeypatch)
    entered, release = Event(), Event()
    def review(*args):
        entered.set()
        assert release.wait(10)
        return {"issues": []}
    monkeypatch.setattr(provider, "review_interpretation", review)
    approve_scope(client, sid, scope)
    assert entered.wait(8)
    try:
        assert service.load(sid)["_assessment"]["model_turns_used"] == 2
        assert client.post(f"/api/sessions/{sid}/stop", json={}).status_code == 200
    finally:
        release.set()
    settle(client, sid)
    state = service.load(sid)["_assessment"]
    assert state["stop_reason"] == "user_stopped"
    assert state["model_turns_used"] == 2
    assert state.get("interpretation_versions", []) == []


def test_explicit_resume_receives_only_safe_review_feedback_and_spends_new_turn(client, tmp_path, monkeypatch):
    service, sid, scope, contexts = case(client, tmp_path, monkeypatch, turns=4)
    monkeypatch.setattr(provider, "review_interpretation", lambda *args: {"issues": [finding()]})
    approve_scope(client, sid, scope)
    settle_assessment(client, sid)
    response = client.post(f"/api/sessions/{sid}/assessment/resume",
        json={"scope_id": scope["scope_id"], "scope_digest": scope["scope_digest"]})
    assert response.status_code == 200
    done = settle_assessment(client, sid)
    assert contexts[-1]["previous_action_error_detail"] == {
        "category": "interpretation_review", "issues": [
            {"hypothesis_index": 0, "field": "competing_explanation", "code": "unknown_as_absent"}]}
    state = service.load(sid)["_assessment"]
    assert state["model_turns_used"] == 4
    assert done["_assessment_state"]["stop_reason"] == "provider_action_invalid_or_unavailable"
    assert state.get("interpretation_versions", []) == []

def test_repair_with_one_remaining_turn_preserves_draft_without_spending(client, tmp_path, monkeypatch):
    service, sid, scope, contexts = case(client, tmp_path, monkeypatch, turns=3)
    monkeypatch.setattr(provider, "review_interpretation", lambda *args: {"issues": [finding()]})
    approve_scope(client, sid, scope)
    settle_assessment(client, sid)
    before = service.load(sid)["_assessment"]
    response = client.post(f"/api/sessions/{sid}/assessment/resume",
        json={"scope_id": scope["scope_id"], "scope_digest": scope["scope_digest"]})
    assert response.status_code == 409
    assert response.json()["error_id"] == "execution_incomplete"
    assert "两轮模型额度" in response.json()["user_message"]
    assert response.json()["results_state"] == "preserved"
    after = service.load(sid)["_assessment"]
    assert after["model_turns_used"] == before["model_turns_used"] == 2
    assert after["pending_revision"] == before["pending_revision"]
    assert after.get("interpretation_versions", []) == []


def test_literature_explain_without_evidence_cannot_bypass_review_with_free_prose(client, tmp_path, monkeypatch):
    from test_web_assessment import science_case
    service, sid, aid = science_case(client, tmp_path)
    scope = propose_scope(client, sid, aid, "P0-01", None, max_model_turns=1,
        literature_enabled=True, literature_concept_refs=["neuron"])
    def explain(settings, messages, context):
        assert context["evidence"] == [] and context["options"]
        return provider.Action.model_validate({"action": "assessment", "decision": {
            "action": "explain", "text": "There are no biological replicates."}})
    monkeypatch.setattr(provider, "converse", explain)
    monkeypatch.setattr(provider, "review_interpretation", lambda *args: pytest.fail("no structured proposal"))
    approve_scope(client, sid, scope)
    done = settle_assessment(client, sid)
    state = service.load(sid)
    assert done["_assessment_state"]["status"] == "blocked"
    assert state["_assessment"]["model_turns_used"] == 1
    assert state["_assessment"]["model_turns"][-1]["provider_error_code"] == "structured_hypotheses_required"
    assert "There are no biological replicates." not in json.dumps(state["messages"])


def test_review_projection_preserves_cited_roles_defaults_and_limits_without_mutating_source(monkeypatch):
    calls = transport(monkeypatch, "json", {"issues": []})
    context = review_context()
    row = context["evidence"][0]
    row["summary"] = {"n_independent_replicates": None, "independence_state": "unknown",
        "reason_codes": ["reference_not_validated"], "record_defaults": {"unit": "fraction"},
        "marker_observations": [{"gene": "UNUSED_SUMMARY_RECORD"}],
        "program_summaries": [
            {"program_family": "oxidative_stress", "signature_scope": "observed_feature_subset",
             "gene_coverage_fraction": 0.4, "direction_definition": "sign-of-source-logFC",
             "unresolved_member_count": 6, "reason_codes": ["partial_gene_coverage"]},
            {"program_family": "hypoxia", "signature_scope": "full_signature",
             "gene_coverage_fraction": 1.0, "direction_definition": "plus-one",
             "unresolved_member_count": 0, "reason_codes": []}]}
    support = dict(row["measurements"][0])
    opposition = {"citation_alias": "E-opposition", "citation_role": "opposition", "raw_value": 0.1}
    missing = {"citation_alias": "E-missing", "citation_role": "missing", "raw_value": None,
        "reason_codes": ["missing_gene"]}
    row["measurements"] += [opposition, missing,
        {"citation_alias": "E-unrelated", "raw_value": 9, "metric_name": "UNUSED_MEASUREMENT"}]
    hypotheses = proposal()
    hypotheses[0].update(opposing_evidence_aliases=["E-opposition"], missing_evidence_aliases=["E-missing"])
    before = json.dumps(context, sort_keys=True)
    provider.review_interpretation(settings("json"), hypotheses, context)
    sent = json.loads(calls[0]["messages"][1]["content"])
    evidence = sent["evidence"][0]
    assert evidence["measurements"] == [support, opposition, missing]
    assert evidence["measurement_defaults"] == row["measurement_defaults"]
    assert evidence["summary"] == {k: v for k, v in row["summary"].items() if k != "marker_observations"}
    assert evidence["review_projection"] == {"uncited_measurements_omitted": 1,
        "summary_tables_omitted": ["marker_observations"]}
    assert "not absent or negative" in sent["review_scope"]
    assert "UNUSED_SUMMARY_RECORD" not in json.dumps(sent) and "UNUSED_MEASUREMENT" not in json.dumps(sent)
    assert json.dumps(context, sort_keys=True) == before


def test_revision_survives_provider_failure_rebinds_citations_and_only_admits_reviewed_result(client, tmp_path, monkeypatch):
    service, sid, scope, contexts = case(client, tmp_path, monkeypatch, turns=5)
    before = service.load(sid)
    monkeypatch.setattr(provider, "review_interpretation", lambda *args: {"issues": [finding()]})
    approve_scope(client, sid, scope)
    first = settle_assessment(client, sid)
    assert "no biological replicates" not in json.dumps(client.get(f"/api/sessions/{sid}").json())
    assert service.load(sid)["_assessment"].get("interpretation_versions", []) == []
    def fail(settings, messages, context):
        contexts.append(context)
        raise ValueError("provider_native_call_missing")
    monkeypatch.setattr(provider, "converse", fail)
    body = {"scope_id": scope["scope_id"], "scope_digest": scope["scope_digest"]}
    assert client.post(f"/api/sessions/{sid}/assessment/resume", json=body).status_code == 200
    settle_assessment(client, sid)
    assert contexts[-1]["revision"]["issues"] == [finding()]
    def revise(settings, messages, context):
        contexts.append(context)
        draft = context["revision"]["hypotheses"]
        assert draft[0]["competing_explanation"] == "There are no biological replicates."
        aliases = provider._citation_choices(context["evidence"])["evidence_aliases"]
        assert draft[0]["evidence_aliases"][0] in aliases
        assert draft[0]["evidence_aliases"] != contexts[-2]["revision"]["hypotheses"][0]["evidence_aliases"]
        draft[0]["competing_explanation"] = "Independent replication is not documented."
        return provider.Action.model_validate({"action": "assessment", "decision": {"action": "explain", "hypotheses": draft}})
    monkeypatch.setattr(provider, "converse", revise)
    monkeypatch.setattr(provider, "review_interpretation", lambda *args: {"issues": []})
    assert client.post(f"/api/sessions/{sid}/assessment/resume", json=body).status_code == 200
    done = settle_assessment(client, sid)
    state = service.load(sid)
    assert done["_assessment_state"]["stop_reason"] == "explanation_complete"
    assert state["_assessment"]["model_turns_used"] == 5
    version, = state["_assessment"]["interpretation_versions"]
    assert version["hypotheses"][0]["competing_explanation"] == "Independent replication is not documented."
    assert not state["_assessment"].get("pending_revision")
    assert state["_tool_runs"] == before["_tool_runs"]
    assert "no biological replicates" not in json.dumps(done)


def test_revision_drops_stale_citations_and_does_not_mutate_private_draft():
    from bridge.web.interpretation_review import revision_context
    pending = {"hypotheses": proposal(), "issues": [finding()]}
    before = json.dumps(pending, sort_keys=True)
    assert revision_context(pending, {"evidence": {}, "citation_roles": {}}) is None
    result = revision_context(pending, {"evidence": {"E-new": "E-observation"},
        "citation_roles": {"E-new": "support"}})
    assert result["hypotheses"][0]["evidence_aliases"] == ["E-new"]
    result["hypotheses"][0]["statement"] = "Changed by provider preparation"
    assert json.dumps(pending, sort_keys=True) == before


def test_unavailable_review_preserves_latest_revision_instead_of_reverting_to_old_draft(client, tmp_path, monkeypatch):
    service, sid, scope, _ = case(client, tmp_path, monkeypatch, turns=6)
    monkeypatch.setattr(provider, "review_interpretation", lambda *args: {"issues": [finding()]})
    approve_scope(client, sid, scope)
    settle_assessment(client, sid)
    def revised(settings, messages, context):
        draft = context["revision"]["hypotheses"]
        draft[0]["competing_explanation"] = "Independent replication is not documented."
        return provider.Action.model_validate({"action": "assessment", "decision": {
            "action": "explain", "hypotheses": draft}})
    monkeypatch.setattr(provider, "converse", revised)
    reserved = []
    def unavailable(*args):
        # This is the durable state a restart during network I/O will recover.
        reserved.append(service.load(sid)["_assessment"]["pending_revision"])
        raise ValueError("review_quote_not_in_proposal")
    monkeypatch.setattr(provider, "review_interpretation", unavailable)
    body = {"scope_id": scope["scope_id"], "scope_digest": scope["scope_digest"]}
    client.post(f"/api/sessions/{sid}/assessment/resume", json=body).raise_for_status()
    settle_assessment(client, sid)
    assert reserved[0]["hypotheses"][0]["competing_explanation"] == "Independent replication is not documented."
    assert reserved[0]["issues"] == []
    pending = service.load(sid)["_assessment"]["pending_revision"]
    assert pending["hypotheses"][0]["competing_explanation"] == "Independent replication is not documented."
    assert pending["issues"] == []
    assert not service.load(sid)["_assessment"].get("interpretation_versions")
    def keep_latest(settings, messages, context):
        pytest.fail("An unavailable review must retry the saved draft without generation.")
    monkeypatch.setattr(provider, "converse", keep_latest)
    monkeypatch.setattr(provider, "review_interpretation", lambda *args: {"issues": []})
    client.post(f"/api/sessions/{sid}/assessment/resume", json=body).raise_for_status()
    done = settle_assessment(client, sid)
    assert done["_assessment_state"]["stop_reason"] == "explanation_complete"
    assert done["_assessment_state"]["model_turns_used"] == 5


@pytest.mark.parametrize("protocol", ["json", "deepseek_tools"])
@pytest.mark.parametrize("revising", [False, True])
def test_revision_wire_limits_evidence_and_choices_without_changing_source_or_initial_analysis(
        monkeypatch, protocol, revising):
    from test_research_skills import connect, response_message
    context = review_context()
    context.update(purpose="assessment", options=[])
    source = context["evidence"][0]
    source["measurement_defaults"]["citation_role"] = "observation"
    source["measurements"].extend([
        {"citation_alias": "E-gap", "citation_role": "missing",
         "raw_value": None, "evidence_state": "unavailable"},
        {"citation_alias": "E-unrelated", "raw_value": 0.9, "numerator": 9, "denominator": 10},
    ])
    source["summary"] = {"marker_observations": ["UNRELATED_TABLE"], "scope": "descriptive_only"}
    draft = proposal()
    draft[0]["missing_evidence_aliases"] = ["E-gap"]
    if revising:
        context["revision"] = {"hypotheses": draft, "issues": []}
    before = json.dumps(context, sort_keys=True)
    requests = connect(monkeypatch, [response_message(protocol, "assessment",
        decision={"action": "explain", "hypotheses": draft})])
    config = settings(protocol)
    config.model = "deepseek-v4.1-flash"
    action = provider.converse(config, [{"role": "user", "content": "Continue."}], context)
    assert action.decision.action == "explain"
    payload = requests[0]
    assert payload["thinking"] == {"type": "enabled"}
    assert payload["reasoning_effort"] == "high"
    wire = json.dumps(payload)
    sent = json.JSONDecoder().raw_decode(
        payload["messages"][0]["content"].split("\nSafe execution context: ", 1)[1])[0]
    if revising:
        assert "E-unrelated" not in wire and "UNRELATED_TABLE" not in wire
        assert "UNREAD" not in wire
        assert [row["citation_alias"] for row in sent["evidence"][0]["measurements"]] == [
            "E-observation", "E-gap"]
        assert sent["evidence"][0]["measurements"][0] == {
            "citation_alias": "E-observation", "raw_value": 0.2, "numerator": 2, "denominator": 10}
        assert sent["evidence"][0]["measurement_defaults"] == {
            "unit": "fraction", "evidence_state": "inferred", "citation_role": "observation"}
        assert sent["evidence"][0]["summary"] == {"scope": "descriptive_only"}
        assert sent["revision"] == {"hypotheses": draft, "issues": []}
        assert "omitted" in sent["revision_evidence_scope"]
        assert [row["source_ref"] for row in sent["literature"]["sources"]] == ["literature:epmc-med-1"]
    else:
        assert "E-unrelated" in wire and "UNRELATED_TABLE" in wire and "UNREAD" in wire
        assert "revision_evidence_scope" not in sent
    assert json.dumps(context, sort_keys=True) == before


@pytest.mark.parametrize("retry_unavailable", [False, True])
def test_unavailable_review_retries_saved_draft_with_one_remaining_turn_without_regeneration(
        client, tmp_path, monkeypatch, retry_unavailable):
    service, sid, scope, _ = case(client, tmp_path, monkeypatch, turns=3)
    def unavailable(*args):
        raise ValueError("provider_response_incomplete")
    monkeypatch.setattr(provider, "review_interpretation", unavailable)
    approve_scope(client, sid, scope)
    settle_assessment(client, sid)
    before = service.load(sid)["_assessment"]
    assert before["model_turns_used"] == 2
    pending = before["pending_revision"]["hypotheses"]
    generated, reviewed = [], []
    def must_not_regenerate(*args):
        generated.append(True)
        raise RuntimeError("unexpected_generation")
    def retry(settings, hypotheses, context):
        reviewed.append(hypotheses)
        assert service.load(sid)["_assessment"]["model_turns_used"] == 3
        if retry_unavailable:
            raise ValueError("provider_response_incomplete")
        return {"issues": []}
    monkeypatch.setattr(provider, "converse", must_not_regenerate)
    monkeypatch.setattr(provider, "review_interpretation", retry)
    client.post(f"/api/sessions/{sid}/assessment/resume", json={
        "scope_id": scope["scope_id"], "scope_digest": scope["scope_digest"]}).raise_for_status()
    done = settle_assessment(client, sid)
    after = service.load(sid)["_assessment"]
    assert generated == []
    assert len(reviewed) == 1
    assert done["_assessment_state"]["stop_reason"] == (
        "provider_action_invalid_or_unavailable" if retry_unavailable else "explanation_complete")
    assert after["model_turns_used"] == 3
    assert after["model_turns"][:2] == before["model_turns"]
    turn = after["model_turns"][-1]
    assert turn["phase"] == "interpretation_review" and turn["review_retry"] is True
    assert turn["proposal_turn"] == 1
    assert turn["provider_bindings"] and turn["evidence_bindings"]
    if retry_unavailable:
        assert after["pending_revision"]["hypotheses"] == pending
        assert not after.get("interpretation_versions")
        assert turn["review_outcome"] == "unavailable"
    else:
        assert after["interpretation_versions"][0]["hypotheses"] == pending
        assert "pending_revision" not in after


def test_evidence_wire_tables_roundtrip_missing_null_and_all_citations():
    from bridge.web.provider import _compact_evidence_wire
    original = [{"measurements": [
        {"citation_alias": f"E-{i}", "raw_value": i / 10, "unit": "fraction",
         "denominator": 10, "evidence_state": "unknown" if i == 2 else "measured",
         **({"numerator": None} if i % 2 else {})} for i in range(20)]}]
    before = json.dumps(original, sort_keys=True)
    wire = _compact_evidence_wire(original)
    from web_support import decode_evidence_tables
    assert decode_evidence_tables(wire) == original
    assert len(json.dumps(wire)) < len(before) * .65
    assert json.dumps(original, sort_keys=True) == before


def test_review_excludes_uncited_sources_but_keeps_cited_gap_and_defaults():
    from bridge.web.interpretation_review import review_evidence
    context = review_context()
    context["evidence"].append({"summary": {"program_summaries": [{"label": "UNRELATED"}]},
        "measurements": [{"citation_alias": "E-other", "raw_value": 7}]})
    context["evidence"][0]["summary"] = {"runtime_mode": "saved", "n_independent_replicates": None,
        "program_summaries": [{"label": "REPEATED_TABLE"}]}
    sent = review_evidence(context["evidence"], proposal())
    assert len(sent) == 1
    assert sent[0]["measurement_defaults"] == context["evidence"][0]["measurement_defaults"]
    assert sent[0]["summary"]["n_independent_replicates"] is None
    assert sent[0]["summary"]["program_summaries"] == context["evidence"][0]["summary"]["program_summaries"]
    assert "UNRELATED" not in json.dumps(sent)


def test_missing_validation_is_exact_deterministic_finding_and_gap_is_exempt():
    from bridge.web.interpretation_review import completeness_issues
    draft = proposal()
    issues = completeness_issues(draft)
    assert len(issues) == 1
    assert issues[0]["field"] == "expected_observation"
    assert parse_review({"issues": issues}, draft)["issues"] == issues
    draft[0]["expected_observation"] = "Compare matched conditions; either shared outcome remains indeterminate."
    assert completeness_issues(draft) == []
    with pytest.raises(ValueError):
        parse_review({"issues": issues}, draft)
    draft[0].update(expected_observation=None, evidence_aliases=[], missing_evidence_aliases=["E-gap"])
    assert completeness_issues(draft) == []


def test_incomplete_draft_repairs_before_paid_review_and_preserves_turns(client, tmp_path, monkeypatch):
    service, sid, scope, contexts = case(client, tmp_path, monkeypatch, turns=3)
    explain = provider.converse
    def incomplete(*args):
        action = explain(*args)
        action.decision.hypotheses[0].expected_observation = None
        return action
    monkeypatch.setattr(provider, "converse", incomplete)
    monkeypatch.setattr(provider, "review_interpretation", lambda *args: pytest.fail("incomplete paid review"))
    approve_scope(client, sid, scope)
    settle_assessment(client, sid)
    first = service.load(sid)["_assessment"]
    assert first["model_turns_used"] == 1
    assert first.get("interpretation_versions", []) == []
    assert first["pending_revision"]["issues"][0]["code"] == "missing_validation_design"
    def repair(settings, messages, context):
        assert context["revision"]["issues"][0]["code"] == "missing_validation_design"
        rows = context["revision"]["hypotheses"]
        rows[0]["expected_observation"] = "A matched contrast distinguishes the rivals; shared outcomes remain indeterminate."
        return provider.Action.model_validate({"action": "assessment", "decision": {"action": "explain", "hypotheses": rows}})
    monkeypatch.setattr(provider, "converse", repair)
    monkeypatch.setattr(provider, "review_interpretation", lambda *args: {"issues": []})
    client.post(f"/api/sessions/{sid}/assessment/resume", json={"scope_id": scope["scope_id"], "scope_digest": scope["scope_digest"]}).raise_for_status()
    done = settle_assessment(client, sid)
    assert done["_assessment_state"]["stop_reason"] == "explanation_complete"
    final = service.load(sid)["_assessment"]
    assert final["model_turns_used"] == 3
    assert len(final["interpretation_versions"]) == 1
    assert len(final["model_turns"]) == 3


def test_pending_review_keeps_twelve_findings_plus_three_completion_requirements():
    from bridge.web.interpretation_review import revision_context
    draft = [dict(proposal()[0]) for _ in range(3)]
    codes = ["unknown_as_absent", "unsupported_observation", "numerical_restatement", "stage_conflation"]
    issues = [{**finding(), "hypothesis_index": i, "code": code} for i in range(3) for code in codes]
    assert len(parse_review({"issues": issues}, draft)["issues"]) == 12
    bindings = {"evidence": {"E-new": "E-observation"}, "citation_roles": {"E-new": "support"}}
    pending = revision_context({"hypotheses": draft, "issues": issues}, bindings)
    assert len(pending["issues"]) == 15
    assert parse_review({"issues": pending["issues"]}, pending["hypotheses"])["issues"] == pending["issues"]
    too_many_model_findings = issues + [{**finding(), "code": "aggregate_as_cell_identity"}]
    with pytest.raises(ValueError):
        parse_review({"issues": too_many_model_findings}, draft)


@pytest.mark.parametrize("protocol", ["json", "deepseek_tools"])
def test_semantic_reviewer_cannot_emit_system_completeness_codes(monkeypatch, protocol):
    calls = transport(monkeypatch, protocol, {"issues": []})
    provider.review_interpretation(settings(protocol), proposal(), review_context())
    payload = calls[0]
    if protocol == "json":
        schema = json.loads(payload["messages"][0]["content"].split("Review schema: ", 1)[1])
    else:
        schema = payload["tools"][0]["function"]["parameters"]
    assert schema["properties"]["issues"]["maxItems"] == 12
    assert "missing_validation_design" not in schema["$defs"]["ReviewIssue"]["properties"]["code"]["enum"]
    assert schema["$defs"]["ReviewIssue"]["properties"]["quote"]["minLength"] == 1
    assert "missing_validation_design:" not in payload["messages"][0]["content"]


def test_large_uncited_history_does_not_block_bounded_text_revision(client, tmp_path, monkeypatch):
    from bridge.web import evidence as module
    service, sid, scope, contexts = case(client, tmp_path, monkeypatch, turns=4)
    monkeypatch.setattr(provider, 'review_interpretation', lambda *args: {'issues': [finding()]})
    approve_scope(client, sid, scope)
    settle_assessment(client, sid)
    pending = json.loads(json.dumps(service.load(sid)['_assessment']['pending_revision']))
    original = module.assessment_model_evidence
    def with_uncited_history(evidence):
        rows, bindings = original(evidence)
        rows.append({'alias': 'R-uncited', 'state': 'available', 'summary': {},
                     'measurements': [{'raw_value': 1, 'unknown_scope': 'x' * (130 * 1024)}]})
        return rows, bindings
    monkeypatch.setattr(module, 'assessment_model_evidence', with_uncited_history)
    dispatched = []
    def revise(settings, messages, context):
        dispatched.append(context)
        draft = json.loads(json.dumps(context['revision']['hypotheses']))
        draft[0]['competing_explanation'] = 'Independent replication is not documented.'
        return provider.Action.model_validate({'action': 'assessment', 'decision': {
            'action': 'explain', 'hypotheses': draft}})
    monkeypatch.setattr(provider, 'converse', revise)
    monkeypatch.setattr(provider, 'review_interpretation', lambda *args: {'issues': []})
    client.post(f'/api/sessions/{sid}/assessment/resume', json={
        'scope_id': scope['scope_id'], 'scope_digest': scope['scope_digest']}).raise_for_status()
    done = settle_assessment(client, sid)
    assert dispatched, done['_assessment_state']['stop_reason']
    assert done['_assessment_state']['stop_reason'] == 'explanation_complete'
    assert dispatched[0]['revision']['issues'] == pending['issues']
    assert dispatched[0]['revision']['hypotheses'][0]['statement'] == pending['hypotheses'][0]['statement']


@pytest.mark.parametrize("protocol", ["json", "deepseek_tools"])
def test_consistency_review_honors_explicit_low_effort_with_the_same_findings_and_contract(monkeypatch, protocol):
    from bridge.web.interpretation_review import PROMPT
    calls = transport(monkeypatch, protocol, {"issues": [finding()]})
    config = settings(protocol)
    config.model = "deepseek-v4-flash"
    config.model_effort = "low"
    config.model_base_url = "https://api.deepseek.com"
    result = provider.review_interpretation(config, proposal(), review_context())
    assert result == {"issues": [finding()]}
    assert len(calls) == 1
    assert calls[0]["reasoning_effort"] == "low"
    assert calls[0]["thinking"] == {"type": "enabled"}
    assert calls[0]["max_tokens"] == 65536
    assert calls[0]["messages"][0]["content"].startswith(PROMPT)
    assert json.loads(calls[0]["messages"][1]["content"])["hypotheses"] == proposal()


def test_native_review_plain_json_is_a_protocol_failure_even_for_a_valid_empty_review(monkeypatch):
    calls = transport(monkeypatch, "json", {"issues": []})
    with pytest.raises(ValueError, match="provider_review_invalid") as caught:
        provider.review_interpretation(settings("deepseek_tools"), proposal(), review_context())
    assert provider.failure_detail(caught.value) == {"category": "action_protocol"}
    assert len(calls) == 1


@pytest.mark.parametrize("literature_enabled", [False, True])
@pytest.mark.parametrize("graph_bound", [False, True])
def test_semantic_relations_and_checked_feature_facts_survive_review_and_session_reload(client, tmp_path, monkeypatch, literature_enabled, graph_bound):
    from test_interpretation_graph import hypothesis
    from bridge.tool_packages.p0_10_claim_verifier.research import parse_research_explanation
    service, sid, scope, _ = case(client, tmp_path, monkeypatch)
    if not literature_enabled:
        aid = service.load(sid)["_assessment"]["scope"]["upload_id"]
        scope = propose_scope(client, sid, aid, "P0-10", "default", report_after_explanation=True, max_tool_runs=1, max_model_turns=3)
    graph_ref = {"graph_id": "graph-test", "graph_version": 1, "graph_manifest_sha256": "a" * 64}
    if graph_bound:
        monkeypatch.setattr(type(service.assessment), "_interpretation_graph_ref", lambda *args: graph_ref)
    before = service.load(sid)
    sent = []
    def explain(settings, messages, context):
        h = hypothesis()
        alias = provider._citation_choices(context["evidence"])["evidence_aliases"][0]
        h["evidence_aliases"] = [alias]
        h["evidence_relations"][0]["evidence_alias"] = alias
        return provider.Action.model_validate({"action": "assessment", "decision": {"action": "explain", "hypotheses": [h]}})
    def review(settings, hypotheses, context):
        sent.append(context["feature_coverage"])
        assert context["feature_coverage"]["complete"]
        return {"issues": []}
    monkeypatch.setattr(provider, "converse", explain)
    monkeypatch.setattr(provider, "review_interpretation", review)
    approve_scope(client, sid, scope)
    done = settle_assessment(client, sid)
    state = service.load(sid)
    if not graph_bound:
        assert done["_assessment_state"]["stop_reason"] == "interpretation_graph_binding_unavailable"
        assert "解释与证据图的对应关系未能核实" in done["presentation"]["issue"]["user_message"]
        assert done["presentation"]["issue"]["results_state"] == "preserved"
        from bridge.web.runtime import build_session_diagnostics
        assert build_session_diagnostics(service.settings, state).model_dump()["degradations"] == [
            {"code": "interpretation_graph_binding_unavailable", "count": 1}]
        assert done["_assessment_state"]["status"] == "blocked"
        assert not state["_assessment"].get("interpretation_versions")
        assert state["_assessment"]["pending_revision"]["hypotheses"][0]["evidence_relations"]
        assert state["_tool_runs"] == before["_tool_runs"]
        assert not any(message.get("interpretation_ref") for message in state["messages"])
        return
    assert done["_assessment_state"]["stop_reason"] == "explanation_complete"
    version, = state["_assessment"]["interpretation_versions"]
    assert version["object_version"] == "1.2.0"
    assert version["graph_ref"] == graph_ref
    assert version["feature_coverage"] == sent[0]
    parse_research_explanation(version)
    h = version["hypotheses"][0]
    assert h["evidence_relations"][0]["evidence_alias"] == h["evidence_aliases"][0]
    assert h["evidence_relations"][0]["relation"] == "limits"
    assert state["_tool_runs"] == before["_tool_runs"]


@pytest.mark.parametrize('protocol', ['json', 'deepseek_tools'])
def test_review_keeps_a_bounded_detailed_reason_without_losing_the_finding(monkeypatch, protocol):
    issue = finding()
    issue['reason'] = ('The supplied intake leaves the count of independent biological cultures unknown. '
        'The quoted draft turns that missing metadata into a claim that no replicates exist. '
        'A single pooled expression matrix cannot resolve how many cultures contributed to it, '
        'and an absent replicate field is not an observation of zero cultures. '
        'Keep the count described as not documented in the competing explanation, '
        'while preserving the cited measurement and the possibility of either sampling design.')
    assert 300 < len(issue['reason']) < 1200
    transport(monkeypatch, protocol, {'issues': [issue]})
    assert provider.review_interpretation(settings(protocol), proposal(), review_context()) == {'issues': [issue]}
    assert parse_review({'issues': [issue]}, proposal())['issues'][0]['reason'] == issue['reason']
    issue['reason'] = 'x' * 1201
    with pytest.raises(ValueError) as failure:
        parse_review({'issues': [issue]}, proposal())
    assert provider.failure_detail(failure.value)['issues'] == [{'path': 'issues[].reason', 'type': 'string_too_long'}]

def test_report_producer_mismatch_candidate_is_counted_and_persisted(client, tmp_path, monkeypatch):
    from bridge.web.assessment import AssessmentScope
    from bridge.web.runtime import build_session_diagnostics
    service, sid, _, _ = case(client, tmp_path, monkeypatch)
    state = service.load(sid)
    scope = AssessmentScope.model_validate(state["_assessment"]["scope"])
    original = service.report_inputs.assessment_selection
    def unavailable(state, scope, allowed, selection):
        if allowed.tool_id == "P0-10":
            raise ValueError("report_context_producer_identity_mismatch")
        return original(state, scope, allowed, selection)
    monkeypatch.setattr(service.report_inputs, "assessment_selection", unavailable)
    candidates = service.inputs.assessment_candidates(state, scope)
    assert any("report_context_producer_identity_mismatch" in row["blockers"] for row in candidates)
    service.assessment._candidate_state(state["_assessment"], candidates)
    service.assessment._finish(state, "report_candidate_unavailable", status="blocked")
    reloaded = service.load(sid)
    assert build_session_diagnostics(service.settings, reloaded).model_dump()["degradations"] == [
        {"code": "report_context_producer_identity_mismatch", "count": 1}]
    assert "测量来源与证据图不一致" in service.public(reloaded)["presentation"]["issue"]["user_message"]
