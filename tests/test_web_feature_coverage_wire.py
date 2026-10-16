"""Coverage membership reaches the provider; private source bindings stay local."""
from copy import deepcopy
import json

import httpx
import pytest

from bridge.web import provider
from test_web_interpretation_review import settings, proposal, review_context
from test_web_interpretation_revision import revision_context, PATCH


@pytest.mark.parametrize("protocol", ["json", "deepseek_tools"])
@pytest.mark.parametrize("operation", ["generation", "review", "repair"])
def test_feature_coverage_wire_excludes_private_bindings(monkeypatch, protocol, operation):
    context = revision_context() if operation == "repair" else review_context()
    context.update(purpose="assessment", options=[], allowed_modes=[])
    public = {
        "object_version": "1.0.0", "complete": True, "feature_count": 3,
        "semantics": "exact_identifier_membership_not_expression_or_biological_absence",
        "results": [{"identifier": "FOXA2", "state": "present"},
                    {"identifier": "TH", "state": "not_found"},
                    {"identifier": "EN1", "state": "unknown"}],
    }
    context["feature_coverage"] = {
        **deepcopy(public), "upload_sha256": "PRIVATE_UPLOAD_HASH",
        "input_revision": 827364, "matrix_location": "PRIVATE_MATRIX",
        "identifier_column": "PRIVATE_COLUMN", "future_private": "PRIVATE_FUTURE",
    }
    context["feature_coverage"]["results"][0]["future_private"] = "PRIVATE_ROW"
    before = deepcopy(context)
    calls = []
    client_cls = httpx.Client
    body = ({"issues": []} if operation == "review" else
            {"patches": [PATCH]} if operation == "repair" else
            {"decision": {"action": "stop", "reason": "no_discriminating_check"}})
    function = {"generation": "assessment", "review": "review_interpretation",
                "repair": "revise_interpretation"}[operation]

    def respond(request):
        calls.append(json.loads(request.content))
        response = {**body, **({"action": "assessment"} if operation == "generation" else {})}
        message = ({"content": json.dumps(response)} if protocol == "json" else
                   {"content": None, "tool_calls": [{"id": "coverage", "type": "function",
                    "function": {"name": function, "arguments": json.dumps(body)}}]})
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": message}]})

    monkeypatch.setattr(provider.httpx, "Client",
                        lambda **kw: client_cls(transport=httpx.MockTransport(respond), **kw))
    if operation == "review":
        provider.review_interpretation(settings(protocol), proposal(), context)
    else:
        provider.converse(settings(protocol), [{"role": "user", "content": "Interpret."}], context)
    assert len(calls) == 1 and context == before
    wire = json.dumps(calls[0])
    for value in ("PRIVATE_UPLOAD_HASH", "827364", "PRIVATE_MATRIX",
                  "PRIVATE_COLUMN", "PRIVATE_FUTURE", "PRIVATE_ROW"):
        assert value not in wire
    content = calls[0]["messages"][0 if operation == "generation" else 1]["content"]
    if operation == "generation":
        content = content.split("\nSafe execution context: ", 1)[1]
        sent, _ = json.JSONDecoder().raw_decode(content)
    else:
        sent = json.loads(content)
    assert sent["feature_coverage"] == public
