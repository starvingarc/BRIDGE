"""Text repair cannot alter measurements, citations or bypass final review."""
from __future__ import annotations

import copy
import json
import httpx
import pytest

from bridge.web import provider
from test_web_interpretation_review import settings, proposal, finding, review_context


def revision_context():
    context = review_context()
    context.update(purpose="assessment", options=[])
    context["revision"] = {"hypotheses": proposal(), "issues": [finding()]}
    context["evidence"][0]["measurement_defaults"]["citation_role"] = "observation"
    context["evidence"][0]["measurements"].append({
        "citation_alias": "E-unrelated", "raw_value": 100, "citation_role": "observation"})
    return context


def patch_transport(monkeypatch, protocol, patches, *, finish="stop"):
    requests = []
    client_cls = httpx.Client
    def respond(request):
        requests.append(json.loads(request.content))
        body = {"patches": patches}
        message = ({"content": json.dumps(body)} if protocol == "json" else
            {"content": None, "tool_calls": [{"id": "repair", "type": "function",
                "function": {"name": "revise_interpretation", "arguments": json.dumps(body)}}]})
        return httpx.Response(200, json={"choices": [{"finish_reason": finish, "message": message}]})
    def client(**kwargs):
        assert kwargs["timeout"] == 600
        return client_cls(transport=httpx.MockTransport(respond), **kwargs)
    monkeypatch.setattr(provider.httpx, "Client", client)
    return requests


@pytest.mark.parametrize("protocol", ["json", "deepseek_tools"])
def test_text_repair_reassembles_existing_action_without_rewriting_citations_or_unchanged_fields(
        monkeypatch, protocol):
    context = revision_context()
    original = copy.deepcopy(context)
    calls = patch_transport(monkeypatch, protocol, [
        {"hypothesis_index": 0, "field": "competing_explanation",
         "text": "Independent replication is not documented."}])
    result = provider.converse(settings(protocol), [{"role": "user", "content": "Revise."}], context)
    assert result.action == "assessment" and result.decision.action == "explain"
    expected = proposal()
    expected[0]["competing_explanation"] = "Independent replication is not documented."
    assert result.decision.model_dump(mode="json")["hypotheses"] == expected
    assert context == original
    assert result._provider_calls == 1 and len(calls) == 1
    assert result._skill_receipts[0]["name"] == "evidence-reasoning"
    wire = json.dumps(calls[0])
    assert "E-unrelated" not in wire and "UNREAD" not in wire
    assert "E-observation" in wire
    assert calls[0]["thinking"] == {"type": "enabled"}
    assert calls[0]["reasoning_effort"] == "high"
    if protocol == "deepseek_tools":
        assert [t["function"]["name"] for t in calls[0]["tools"]] == ["revise_interpretation"]
        assert "tool_choice" not in calls[0]


PATCH = {"hypothesis_index": 0, "field": "competing_explanation",
         "text": "Independent replication is not documented."}


@pytest.mark.parametrize("patches", [
    [], [PATCH, PATCH], [{**PATCH, "hypothesis_index": True}],
    [{**PATCH, "hypothesis_index": 1}], [{**PATCH, "field": "evidence_aliases"}],
    [{**PATCH, "field": "literature_support"}], [{**PATCH, "text": ""}],
    [{**PATCH, "text": "x" * 601}], [{**PATCH, "extra": "hidden"}],
])
def test_malformed_or_out_of_scope_text_repair_never_changes_draft_or_retries(monkeypatch, patches):
    context = revision_context()
    original = copy.deepcopy(context)
    calls = patch_transport(monkeypatch, "json", patches)
    with pytest.raises(ValueError):
        provider.converse(settings("json"), [{"role": "user", "content": "Revise."}], context)
    assert len(calls) == 1 and context == original


def test_incomplete_repair_is_not_used_even_if_its_partial_json_parses(monkeypatch):
    context = revision_context()
    calls = patch_transport(monkeypatch, "json", [PATCH], finish="length")
    with pytest.raises(ValueError, match="incomplete"):
        provider.converse(settings("json"), [{"role": "user", "content": "Revise."}], context)
    assert len(calls) == 1



def test_unchanged_repair_does_not_spend_another_review_call(monkeypatch):
    context = revision_context()
    patch = {**PATCH, "text": context["revision"]["hypotheses"][0]["competing_explanation"]}
    calls = patch_transport(monkeypatch, "json", [patch])
    with pytest.raises(ValueError, match="unchanged"):
        provider.converse(settings("json"), [{"role": "user", "content": "Revise."}], context)
    assert len(calls) == 1


def test_unshared_revision_is_blocked_before_request(monkeypatch):
    context = revision_context()
    context["results_sent_to_model"] = False
    monkeypatch.setattr(provider.httpx, "Client", lambda **kwargs: pytest.fail("unexpected request"))
    with pytest.raises(ValueError, match="result_sharing_disabled"):
        provider.converse(settings("json"), [{"role": "user", "content": "Revise."}], context)


@pytest.mark.parametrize("protocol", ["json", "deepseek_tools"])
def test_literature_repair_preserves_source_binding_hypotheses_and_validation(monkeypatch, protocol):
    context = revision_context()
    draft = context["revision"]["hypotheses"]
    draft[0]["expected_observation"] = "A matched prospective contrast separates the rivals."
    draft[0]["literature_support"] = [{"source_ref": "literature:epmc-med-1",
        "rationale": "Developmental markers changed by stage.", "species": "human",
        "lineage": "neural", "stage": "differentiation", "experimental_context": "In vitro",
        "qualification": "unverified_applicability"}]
    context["revision"]["issues"] = [{"hypothesis_index": 0, "field": "literature_support",
        "code": "literature_overreach", "quote": "Developmental markers changed by stage.",
        "reason": "The abstract says the markers were monitored, without reporting their results."}]
    before = copy.deepcopy(context)
    replacement = "The abstract reports receptor subtype changes; developmental marker results are not reported."
    calls = patch_transport(monkeypatch, protocol, [{"hypothesis_index": 0,
        "literature_index": 0, "field": "literature_support.rationale", "text": replacement}])
    action = provider.converse(settings(protocol), [{"role": "user", "content": "Revise."}], context)
    expected = copy.deepcopy(draft)
    expected[0]["literature_support"][0]["rationale"] = replacement
    assert action.decision.model_dump(mode="json")["hypotheses"] == expected
    assert context == before and len(calls) == action._provider_calls == 1


@pytest.mark.parametrize("patch", [
    {"field": "literature_support.rationale", "literature_index": 0},
    {"field": "literature_support.source_ref", "literature_index": 0},
    {"field": "literature_support.qualification", "literature_index": 0},
])
def test_literature_patch_cannot_create_uses_or_change_source_identity(patch):
    from bridge.web.interpretation_review import apply_text_revision
    original = proposal()
    with pytest.raises(ValueError):
        apply_text_revision({"patches": [{"hypothesis_index": 0, "text": "Replacement", **patch}]}, original)
    assert original == proposal()


def test_literature_patch_schema_never_advertises_invalid_canonical_field_lengths():
    from jsonschema import Draft202012Validator
    from bridge.web.interpretation_review import InterpretationRevision
    validator = Draft202012Validator(InterpretationRevision.model_json_schema())
    for field, maximum in {"rationale": 600, "species": 240, "lineage": 240,
                           "stage": 240, "experimental_context": 400}.items():
        patch = {"hypothesis_index": 0, "literature_index": 0,
                 "field": "literature_support." + field, "text": "x" * 240}
        assert validator.is_valid({"patches": [patch]})
        assert not validator.is_valid({"patches": [{**patch, "text": "x" * (maximum + 1)}]})


@pytest.mark.parametrize("operation", ["review", "repair"])
@pytest.mark.parametrize("reasoning_bytes", [300_000, 1_100_000])
def test_bounded_reasoning_response_preserves_structured_result_only(monkeypatch, operation, reasoning_bytes):
    context = revision_context()
    original = copy.deepcopy(context)
    calls = []
    client_cls = httpx.Client
    body = {"issues": []} if operation == "review" else {"patches": [PATCH]}
    function = "review_interpretation" if operation == "review" else "revise_interpretation"
    def respond(request):
        calls.append(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"finish_reason": "tool_calls", "message": {
            "content": None, "reasoning_content": "x" * reasoning_bytes,
            "tool_calls": [{"id": "bounded", "type": "function", "function": {
                "name": function, "arguments": json.dumps(body)}}]}}]})
    monkeypatch.setattr(provider.httpx, "Client", lambda **kw:
        client_cls(transport=httpx.MockTransport(respond), **kw))
    def invoke():
        if operation == "review":
            return provider.review_interpretation(settings("deepseek_tools"), proposal(), context)
        return provider.converse(settings("deepseek_tools"), [{"role": "user", "content": "Revise."}], context)
    if reasoning_bytes > 1024 * 1024:
        with pytest.raises(ValueError, match="provider_response_too_large"):
            invoke()
    else:
        result = invoke()
        value = result if operation == "review" else result.model_dump(mode="json")
        assert "reasoning_content" not in json.dumps(value)
        if operation == "review":
            assert result == {"issues": []}
        else:
            assert result.decision.hypotheses[0].competing_explanation == PATCH["text"]
    assert len(calls) == 1 and context == original
    assert calls[0]["max_tokens"] == 65536
    assert calls[0]["reasoning_effort"] == "high"
