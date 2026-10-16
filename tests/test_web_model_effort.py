"""Assert emitted provider requests, including reasoning-enabled tool continuation."""
import json
from types import SimpleNamespace

import httpx
import pytest

from bridge.web import provider, intake_autofill, protocol_formalization


def config(protocol, effort):
    return SimpleNamespace(model="deepseek-v4-flash", model_action_protocol=protocol,
        model_base_url="https://api.deepseek.com", model_api_key="synthetic-key", model_effort=effort)


def reply(protocol, action, body, **extra):
    message = ({"content": json.dumps({"action": action, **body} if action == "reply" else body)}
               if protocol == "json" else {"content": None, "tool_calls": [{"id": "remote-call", "type": "function",
                   "function": {"name": action, "arguments": json.dumps(body)}}]})
    return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {**message, **extra}}]})


@pytest.mark.parametrize("effort", ["max", None])
@pytest.mark.parametrize("protocol", ["json", "deepseek_tools"])
@pytest.mark.parametrize("operation", ["conversation", "intake", "formalization", "review", "revision"])
def test_task_effort_reaches_every_model_call_without_workflow_overrides(monkeypatch, protocol, operation, effort):
    calls = []
    original = httpx.Client
    body = {"text": "Ready."}
    action = "reply"
    module = provider
    context = {"question": "Describe observations", "results_sent_to_model": True,
               "biological_context": {}, "evidence": [], "literature": {"sources": []}}
    hypothesis = {"statement": "An initial explanation.", "competing_explanation": "An alternative remains.",
                  "expected_observation": None, "discriminating_check": None, "evidence_aliases": ["E1"],
                  "missing_evidence_aliases": [], "opposing_evidence_aliases": [], "literature_support": []}
    settings = config(protocol, effort)
    if operation == "intake":
        module, action, body = intake_autofill, "extract_intake", {"fields": [], "protocol_stages": []}
        run = lambda: intake_autofill.extract_intake(settings, {"sources": [], "allowed_fields": []})
    elif operation == "formalization":
        module, action = protocol_formalization, "formalize_protocol"
        body = {"steps": [{"id": "wait", "label": "Wait", "operations": "Wait for 2 h.",
                          "bpl_fragment": "wait(duration: 2 h)", "source_ids": ["S1"]}],
                "questions": [], "excluded_sources": []}
        run = lambda: protocol_formalization.generate(settings, {"sources": [{"id": "S1", "text": "Wait for 2 h."}], "supplements": []})
    elif operation == "review":
        action, body = "review_interpretation", {"issues": []}
        run = lambda: provider.review_interpretation(settings, [hypothesis], context)
    elif operation == "revision":
        action = "revise_interpretation"
        body = {"patches": [{"hypothesis_index": 0, "field": "statement", "text": "A bounded explanation."}]}
        context.update(revision={"hypotheses": [hypothesis], "issues": []}, revision_evidence_scope={})
        run = lambda: provider._revise_interpretation_text(settings, context)
    else:
        run = lambda: provider.converse(settings, [{"role": "user", "content": "Hello"}], {})
    def respond(request):
        calls.append(json.loads(request.content))
        return reply(protocol, action, body)
    monkeypatch.setattr(module, "provider_client", lambda *args, **kwargs: original(transport=httpx.MockTransport(respond)))
    assert run() is not None
    assert len(calls) == 1
    assert calls[0]["model"] == "deepseek-v4-flash"
    if effort is None:
        assert "reasoning_effort" not in calls[0]
        assert "thinking" not in calls[0]
    else:
        assert calls[0].get("reasoning_effort") == effort
        assert calls[0].get("thinking") == {"type": "enabled"}
    assert "tool_choice" not in calls[0]


@pytest.mark.parametrize("effort", ["high", None])
def test_native_skill_continuation_preserves_required_reasoning_without_exposing_it(monkeypatch, effort):
    calls = []
    original = httpx.Client
    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        if len(calls) == 1:
            return reply("deepseek_tools", "load_skill", {"name": "case-understanding"}, reasoning_content="private reasoning for this tool call")
        assistant = next(item for item in body["messages"] if item["role"] == "assistant")
        if assistant.get("reasoning_content") != "private reasoning for this tool call":
            return httpx.Response(400, json={"error": "reasoning_content required"})
        return reply("deepseek_tools", "reply", {"text": "Please describe the sample."})
    monkeypatch.setattr(provider, "provider_client", lambda *args, **kwargs: original(transport=httpx.MockTransport(respond)))
    result = provider.converse(config("deepseek_tools", effort), [{"role": "user", "content": "Discuss samples"}], {})
    assert result.action == "reply" and result.text == "Please describe the sample."
    assert "private reasoning" not in result.model_dump_json()
    assert len(calls) == 2
    assert calls[1].get("reasoning_effort") == effort
    tool = next(item for item in calls[1]["messages"] if item["role"] == "tool")
    assistant = next(item for item in calls[1]["messages"] if item["role"] == "assistant")
    assert tool["tool_call_id"] == assistant["tool_calls"][0]["id"]


def test_compatible_provider_effort_does_not_add_deepseek_switch(monkeypatch):
    calls = []
    original = httpx.Client
    settings = config("json", "medium")
    settings.model_base_url, settings.model = "https://compatible.invalid/v1", "reasoning-model"
    def respond(request):
        calls.append(json.loads(request.content))
        return reply("json", "reply", {"text": "Ready."})
    monkeypatch.setattr(provider, "provider_client", lambda *args, **kwargs: original(transport=httpx.MockTransport(respond)))
    assert provider.converse(settings, [{"role": "user", "content": "Hello"}], {}).action == "reply"
    assert calls[0]["reasoning_effort"] == "medium"
    assert "thinking" not in calls[0]
