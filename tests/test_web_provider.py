from __future__ import annotations

import json

import pytest

pytest.importorskip("httpx")
pytest.importorskip("fastapi")
from bridge.web.provider import parse_action


def test_provider_accepts_only_complete_typed_json_actions():
    qc = {"action": "prepare_qc", "upload_id": "a" * 32, "matrix_location": "X"}
    assert parse_action({"content": json.dumps(qc)}).action == "prepare_qc"
    assert (
        parse_action({"content": '{"action":"reply","text":"Please upload a file."}'}).text
        == "Please upload a file."
    )
    assert (
        parse_action({"content": '{"action":"prepare_analysis","tool_id":"P0-02"}'}).tool_id
        == "P0-02"
    )
    invalid = [
        {"content": "Please upload a file."},
        {
            "content": '<｜DSML｜function_calls><｜DSML｜invoke name="prepare_analysis">P0-02</｜DSML｜invoke>'
        },
        {"content": '{"action":"reply"}'},
        {"content": '{"action":"prepare_qc","upload_id":"a"}'},
        {"content": '{"action":"prepare_analysis"}'},
        {"content": '{"action":"shell","command":"ls"}'},
        {"content": '{"action":"prepare_qc","upload_id":"abc","matrix_location":"../../secret"}'},
        {
            "content": json.dumps(qc),
            "tool_calls": [{"function": {"name": "prepare_qc", "arguments": "{}"}}],
        },
    ]
    for message in invalid:
        with pytest.raises(ValueError):
            parse_action(message)


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        (
            {
                "content": "",
                "tool_calls": [
                    {
                        "type": "function",
                        "function": {"name": "reply", "arguments": '{"text":"Ready."}'},
                    }
                ],
            },
            {"action": "reply", "text": "Ready."},
        ),
        (
            {
                "content": " \n\t",
                "tool_calls": [
                    {
                        "type": "function",
                        "function": {
                            "name": "review_inputs",
                            "arguments": '{"text":"Review the panel."}',
                        },
                    }
                ],
            },
            {"action": "review_inputs", "text": "Review the panel."},
        ),
        (
            {
                "content": None,
                "tool_calls": [
                    {
                        "type": "function",
                        "function": {
                            "name": "prepare_qc",
                            "arguments": '{"upload_id":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","matrix_location":"layers/counts"}',
                        },
                    }
                ],
            },
            {
                "action": "prepare_qc",
                "upload_id": "a" * 32,
                "matrix_location": "layers/counts",
            },
        ),
        (
            {
                "content": "",
                "tool_calls": [
                    {
                        "type": "function",
                        "function": {
                            "name": "prepare_analysis",
                            "arguments": '{"tool_id":"P0-02"}',
                        },
                    }
                ],
            },
            {"action": "prepare_analysis", "tool_id": "P0-02"},
        ),
    ],
)
def test_provider_accepts_each_complete_native_action(message, expected):
    action = parse_action(message, protocol="deepseek_tools")
    assert action.model_dump(exclude_none=True) == {**expected, "observation_aliases": []}


@pytest.mark.parametrize(
    ("message", "error"),
    [
        ({"content": ""}, "invalid_model_tool_call_count"),
        ({"content": "plain prose"}, "unexpected_model_content"),
        (
            {
                "content": "",
                "tool_calls": [
                    {
                        "type": "function",
                        "function": {"name": "reply", "arguments": '{"text":"one"}'},
                    },
                    {
                        "type": "function",
                        "function": {"name": "reply", "arguments": '{"text":"two"}'},
                    },
                ],
            },
            "invalid_model_tool_call_count",
        ),
        (
            {
                "content": "outside",
                "tool_calls": [
                    {
                        "type": "function",
                        "function": {"name": "reply", "arguments": '{"text":"inside"}'},
                    }
                ],
            },
            "unexpected_model_content",
        ),
        (
            {
                "content": "",
                "tool_calls": [
                    {
                        "type": "function",
                        "function": {"name": "shell", "arguments": '{"command":"ls"}'},
                    }
                ],
            },
            "unknown_model_action",
        ),
        (
            {
                "content": "",
                "tool_calls": [
                    {
                        "type": "function",
                        "function": {"name": "reply", "arguments": {"text": "not a string"}},
                    }
                ],
            },
            "invalid_model_action_arguments",
        ),
        (
            {
                "content": "",
                "tool_calls": [
                    {
                        "type": "function",
                        "function": {"name": "reply", "arguments": '"not an object"'},
                    }
                ],
            },
            "invalid_model_action_arguments",
        ),
        (
            {
                "content": "",
                "tool_calls": [
                    {
                        "type": "function",
                        "function": {
                            "name": "prepare_analysis",
                            "arguments": '{"action":"prepare_analysis","tool_id":"P0-02"}',
                        },
                    }
                ],
            },
            "invalid_model_action_fields",
        ),
        (
            {
                "content": "",
                "tool_calls": [
                    {
                        "type": "function",
                        "function": {
                            "name": "prepare_analysis",
                            "arguments": '{"tool_id":"P0-02","text":null}',
                        },
                    }
                ],
            },
            "invalid_model_action_fields",
        ),
        (
            {
                "content": "",
                "tool_calls": [
                    {
                        "type": "function",
                        "function": {
                            "name": "prepare_analysis",
                            "arguments": '{"tool_id":"P0-13"}',
                        },
                    }
                ],
            },
            "invalid_model_action",
        ),
        (
            {
                "content": "",
                "tool_calls": [
                    {
                        "type": "function",
                        "function": {"name": "reply", "arguments": "{}"},
                    }
                ],
            },
            "invalid_model_action_fields",
        ),
        (
            {
                "content": "",
                "tool_calls": [
                    {
                        "type": "function",
                        "function": {"name": "reply", "arguments": "{"},
                    }
                ],
            },
            "invalid_model_action_arguments",
        ),
        (
            {
                "content": "",
                "tool_calls": [
                    {
                        "type": "custom",
                        "function": {"name": "reply", "arguments": '{"text":"Ready."}'},
                    }
                ],
            },
            "invalid_model_tool_call",
        ),
    ],
)
def test_provider_rejects_invalid_native_action_shapes_with_stable_codes(message, error):
    with pytest.raises(ValueError, match=f"^{error}$"):
        parse_action(message, protocol="deepseek_tools")


def test_provider_rejects_unknown_action_protocol():
    with pytest.raises(ValueError, match="^invalid_model_action_protocol$"):
        parse_action({"content": '{"action":"reply","text":"Ready."}'}, protocol="automatic")


@pytest.mark.parametrize("model,switchable", [
    ("deepseek-v4-flash", True), ("deepseek-v4-pro-test", True),
    ("deepseek-v4.1-flash", True),
    ("deepseek-flash", True), ("deepseek-pro", True),
    ("deepseek-reasoner", False), ("other-json-model", False),
])
@pytest.mark.parametrize("protocol", ["json", "deepseek_tools"])
@pytest.mark.parametrize("assessment", [False, True])
def test_unspecified_effort_never_infers_a_level_from_model_name_or_workflow(
        monkeypatch, model, switchable, protocol, assessment):
    from types import SimpleNamespace
    import httpx
    from bridge.web import provider

    requests, timeouts = [], []
    original = httpx.Client
    def respond(request):
        requests.append(json.loads(request.content))
        if requests[-1].get("thinking") == {"type": "enabled"} and requests[-1].get("tool_choice") == "required":
            return httpx.Response(400, json={"error": "required tool choice is unsupported in thinking mode"})
        action = ({"action": "assessment", "decision": {"action": "stop",
            "reason": "no_discriminating_check"}} if assessment else
            {"action": "reply", "text": "Hello."})
        message = {"content": json.dumps(action)}
        if protocol == "deepseek_tools":
            message = {"content": None, "tool_calls": [{"type": "function", "function": {
                "name": action["action"], "arguments": json.dumps({
                    key: value for key, value in action.items() if key != "action"})}}]}
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": message}]})
    def client(**kwargs):
        timeouts.append(kwargs["timeout"])
        return original(transport=httpx.MockTransport(respond), **kwargs)
    monkeypatch.setattr(provider.httpx, "Client", client)
    settings = SimpleNamespace(model=model, model_action_protocol=protocol,
        model_base_url="https://provider.invalid/v1", model_api_key="synthetic")
    context = ({"purpose": "assessment", "evidence": [], "options": [], "allowed_modes": []}
               if assessment else {})
    action = provider.converse(settings, [{"role": "user", "content": "Review evidence."}], context)
    assert action.action == ("assessment" if assessment else "reply")
    assert len(requests) == 1
    payload = requests[0]
    assert "thinking" not in payload and "reasoning_effort" not in payload
    if protocol == "deepseek_tools":
        assert payload["max_tokens"] == 32768
        assert timeouts == [600]
        assert "tool_choice" not in payload
    else:
        assert payload["max_tokens"] == (6000 if assessment else 3000)
        assert timeouts == [90]


def test_citation_choices_honor_measurement_defaults_and_explicit_role_overrides():
    from bridge.web.provider import _citation_choices

    choices = _citation_choices([{
        "measurement_defaults": {"citation_role": "observation"},
        "measurements": [
            {"citation_alias": "E-observed"},
            {"citation_alias": "E-missing", "citation_role": "missing"},
            {"citation_alias": "E-null", "citation_role": None},
        ],
    }])
    assert choices == {"evidence_aliases": ["E-observed"],
                       "opposing_evidence_aliases": [],
                       "missing_evidence_aliases": ["E-missing"]}
