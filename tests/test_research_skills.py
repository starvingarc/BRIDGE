"""Research workflows are loaded through the real provider boundary, not a fake router."""
from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import pytest

from bridge.web import provider
from web_support import client, declare_counts, h5ad, new_session, settle

WORKFLOWS = (
    "case-understanding", "expression-exploration", "reference-and-target-definition",
    "product-assessment", "evidence-reasoning", "research-reporting",
    "product-comparison", "graft-followup",
)


def test_catalog_contains_all_eight_workflows_with_packaged_examples_and_provenance():
    from importlib.resources import files
    from bridge.skills import catalog, load_skill
    root = files("bridge.skills")
    assert {row["name"] for row in catalog()} == set(WORKFLOWS)
    sources = json.loads(root.joinpath("sources.json").read_text())
    assert set(sources["workflows"]) == set(WORKFLOWS)
    for name in WORKFLOWS:
        assert load_skill(name).description.startswith("Use when")
        assert root.joinpath(name, "EXAMPLES.md").read_text().strip()
        assert sources["workflows"][name]["sources"]
    for source in sources["sources"].values():
        assert len(source["commit"]) == 40 and len(source["sha256"]) == 64
        assert root.joinpath(source["license_file"]).read_text().strip()


def settings(protocol):
    return SimpleNamespace(model="test-model", model_action_protocol=protocol,
                           model_base_url="https://provider.invalid/v1", model_api_key="test-key")


def response_message(protocol, action, **arguments):
    if protocol == "json":
        return {"content": json.dumps({"action": action, **arguments})}
    return {"content": None, "tool_calls": [{"id": "call-test", "type": "function",
        "function": {"name": action, "arguments": json.dumps(arguments)}}]}


def connect(monkeypatch, messages):
    requests = []
    original = httpx.Client

    def respond(request):
        requests.append(json.loads(request.content))
        assert len(requests) <= len(messages), "provider exceeded the bounded invocation"
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop",
            "message": messages[len(requests) - 1]}]})

    monkeypatch.setattr(provider.httpx, "Client",
        lambda **kwargs: original(transport=httpx.MockTransport(respond), **kwargs))
    return requests


@pytest.mark.parametrize("protocol", ["json", "deepseek_tools"])
@pytest.mark.parametrize("skill", WORKFLOWS)
def test_model_reads_only_selected_skill_before_returning_existing_action(monkeypatch, protocol, skill):
    requests = connect(monkeypatch, [
        response_message(protocol, "load_skill", name=skill),
        response_message(protocol, "reply", text="请先确认当前输入。"),
    ])
    action = provider.converse(settings(protocol), [{"role": "user", "content": "说明下一步。"}], {})
    assert action.action == "reply"
    assert action.text == "请先确认当前输入。"
    assert len(requests) == 2
    from bridge.skills import load_skill
    selected = load_skill(skill)
    other = load_skill("product-assessment" if skill == "expression-exploration" else "expression-exploration")
    assert selected.content not in requests[0]["messages"][0]["content"]
    selected_message = next(item["content"] for item in requests[1]["messages"]
                            if selected.content in (item.get("content") or ""))
    assert selected.content in selected_message
    assert other.content not in requests[1]["messages"][0]["content"]
    assert requests[1]["messages"][-1] == {"role": "user", "content": "说明下一步。"}
    assert action._skill_receipts == [{"name": skill, "sha256": selected.sha256, "selection": "model"}]
    assert "skill" not in json.dumps(action.model_dump())
    assert action._provider_calls == 2
    if protocol == "deepseek_tools":
        assert "load_skill" in [t["function"]["name"] for t in requests[0]["tools"]]
        assert "prepare_qc" not in [t["function"]["name"] for t in requests[0]["tools"]]
        assert "prepare_qc" in [t["function"]["name"] for t in requests[1]["tools"]]
        assert "load_skill" not in [t["function"]["name"] for t in requests[1]["tools"]]
        call = requests[1]["messages"][-3]["tool_calls"][0]
        result = requests[1]["messages"][-2]
        assert result["role"] == "tool" and result["tool_call_id"] == call["id"]
        assert call["function"]["name"] == "load_skill"
        assert selected.content in result["content"]


@pytest.mark.parametrize("protocol", ["json", "deepseek_tools"])
@pytest.mark.parametrize("name", ["../../web/provider.py", "unregistered", "", 42])
def test_skill_request_cannot_load_arbitrary_resources(monkeypatch, protocol, name):
    requests = connect(monkeypatch, [response_message(protocol, "load_skill", name=name)])
    with pytest.raises(ValueError, match="invalid_model_skill_request"):
        provider.converse(settings(protocol), [{"role": "user", "content": "请读取。"}], {})
    assert len(requests) == 1


@pytest.mark.parametrize("protocol", ["json", "deepseek_tools"])
def test_repeated_skill_read_stops_without_third_provider_call(monkeypatch, protocol):
    messages = [response_message(protocol, "load_skill", name="expression-exploration")] * 2
    requests = connect(monkeypatch, messages)
    with pytest.raises(ValueError, match="model_skill_read_limit"):
        provider.converse(settings(protocol), [{"role": "user", "content": "继续。"}], {})
    assert len(requests) == 2


@pytest.mark.parametrize("protocol", ["json", "deepseek_tools"])
def test_model_cannot_bypass_skill_stage_to_prepare_analysis(monkeypatch, protocol):
    connect(monkeypatch, [response_message(protocol, "prepare_analysis", tool_id="P0-02")])
    with pytest.raises(ValueError, match="model_skill_required"):
        provider.converse(settings(protocol), [{"role": "user", "content": "分析表达谱。"}], {})


@pytest.mark.parametrize("protocol", ["json", "deepseek_tools"])
def test_unmatched_chat_preserves_single_call_fallback(monkeypatch, protocol):
    requests = connect(monkeypatch, [response_message(protocol, "reply", text="你好。")])
    action = provider.converse(settings(protocol), [{"role": "user", "content": "你好。"}], {})
    assert action.text == "你好。" and len(requests) == 1
    assert action._skill_receipts == []


@pytest.mark.parametrize("protocol", ["json", "deepseek_tools"])
def test_approved_assessment_loads_scope_skill_without_extra_model_turn(monkeypatch, protocol):
    requests = connect(monkeypatch, [response_message(protocol, "assessment",
        decision={"action": "stop", "reason": "no_discriminating_check"})])
    action = provider.converse(settings(protocol), [{"role": "user", "content": "选择下一步。"}],
                              {"purpose": "assessment", "evidence": [], "options": []})
    assert action.action == "assessment" and len(requests) == 1
    assert action._skill_receipts[0]["name"] == "evidence-reasoning"
    assert action._skill_receipts[0]["selection"] == "scope"
    assert action._provider_calls == 1
    if protocol == "deepseek_tools":
        assert [t["function"]["name"] for t in requests[0]["tools"]] == ["assessment"]


@pytest.mark.parametrize("protocol", ["json", "deepseek_tools"])
@pytest.mark.parametrize("extra,expected", [
    ({}, ["evidence-reasoning"]),
    ({"options": [{"id": "x", "tool_id": "P0-01", "kind": "check"}]}, ["product-assessment"]),
    ({"report_after_explanation": True, "report_preparation": {"state": "graph_required"}},
     ["product-assessment"]),
    ({"workflow_handoff": {"state": "report_ready_after_current_explanation"}},
     ["research-reporting"]),
])
def test_assessment_loads_only_current_phase_workflow(monkeypatch, protocol, extra, expected):
    from bridge.skills import load_skill
    requests = connect(monkeypatch, [response_message(protocol, "assessment",
        decision={"action": "stop", "reason": "no_discriminating_check"})])
    action = provider.converse(settings(protocol), [{"role": "user", "content": "选择下一步。"}],
                              {"purpose": "assessment", "evidence": [], "options": [], **extra})
    assert len(requests) == action._provider_calls == 1
    assert [row["name"] for row in action._skill_receipts] == expected
    prompt = requests[0]["messages"][0]["content"]
    # Bound the serialized prompt including action schema and interpretation guardrails.
    assert len(prompt) < 16_000
    for name in WORKFLOWS:
        assert (load_skill(name).content in prompt) == (name in expected)


@pytest.mark.parametrize("protocol", ["json", "deepseek_tools"])
def test_scientific_input_scope_loads_reference_workflow_in_one_call(monkeypatch, protocol):
    candidate = {"label_level": "L1", "roles": [], "development": [],
                 "regional_denominator_state_ids": [], "regional_target_state_ids": []}
    requests = connect(monkeypatch, [response_message(protocol, "propose_scientific_inputs",
        upload_id="a" * 32, candidate=candidate)])
    action = provider.converse(settings(protocol), [{"role": "user", "content": "选择候选。"}],
                              {"purpose": "scientific_input_draft"})
    assert action.action == "propose_scientific_inputs" and len(requests) == 1
    assert [row["name"] for row in action._skill_receipts] == ["reference-and-target-definition"]


def test_conversation_scope_is_not_expanded_by_mentioning_approved_modes(monkeypatch):
    requests = connect(monkeypatch, [response_message("json", "load_skill", name="product-comparison"),
        response_message("json", "reply", text="请先确认可比性。")])
    action = provider.converse(settings("json"), [{"role": "user", "content": "比较两批产品。"}],
                              {"allowed_modes": [{"tool_id": "P0-12"}]})
    assert len(requests) == 2
    assert [row["name"] for row in action._skill_receipts] == ["product-comparison"]


def test_composed_skill_receipts_persist_privately_and_reject_invalid_lists(client):
    from bridge.skills import load_skill
    sid = new_session(client)["id"]
    service = client.app.state.service
    state = service.load(sid)
    names = ["product-assessment", "evidence-reasoning", "product-comparison", "graft-followup", "research-reporting"]
    receipts = [{"name": name, "sha256": load_skill(name).sha256, "selection": "scope"} for name in names]
    service.sessions.record_skill_usage(state, receipts, action="assessment", purpose="assessment", provider_calls=1)
    assert service.load(sid)["_skill_invocations"][0]["skills"] == receipts
    public = client.get(f"/api/sessions/{sid}").json()
    assert "_skill_invocations" not in public
    for receipt in receipts:
        assert receipt["sha256"] not in json.dumps(public)
    for invalid in (receipts + [receipts[0]], [receipts[0], receipts[0]],
                    [{**receipts[0], "sha256": "0" * 64}],
                    [{**receipts[0], "name": "../../unregistered"}]):
        with pytest.raises(ValueError):
            service.sessions.record_skill_usage(state, invalid, action="assessment", purpose="assessment", provider_calls=1)
    assert len(service.load(sid)["_skill_invocations"]) == 1


def test_model_selected_skill_prepares_qc_with_private_provenance_but_no_execution(
        client, tmp_path, monkeypatch):
    sid = new_session(client)["id"]
    url = f"/api/sessions/{sid}"
    uploaded = client.post(url + "/uploads", files={"file": ("synthetic.h5ad", h5ad(tmp_path))}).json()
    aid = uploaded["uploads"][0]["id"]
    declare_counts(client, sid, aid)
    connect(monkeypatch, [response_message("json", "load_skill", name="expression-exploration"),
        response_message("json", "prepare_qc", upload_id=aid, matrix_location="X")])
    client.post(url + "/messages", json={"text": "只准备输入质控计划。"})
    public = settle(client, sid)
    assert public["status"] == "awaiting_approval"
    service = client.app.state.service
    state = service.load(sid)
    assert state["_tool_runs"] == []
    use, = state["_skill_invocations"]
    assert use["action"] == "prepare_qc" and use["purpose"] == "conversation"
    assert use["provider_calls"] == 2
    assert use["skills"][0]["name"] == "expression-exploration"
    assert use["skills"][0]["selection"] == "model"
    assert len(use["skills"][0]["sha256"]) == 64
    assert set(use["skills"][0]) == {"name", "sha256", "selection"}
    assert "_skill_invocations" not in public
    assert use["skills"][0]["sha256"] not in json.dumps(public)


@pytest.mark.parametrize("protocol", ["json", "deepseek_tools"])
@pytest.mark.parametrize("case_id,option,expected_skill", [
    ("assessment-option", "b", "product-assessment"),
    ("assessment-comparison", "c", "product-assessment"),
    ("assessment-graft", "c", "product-assessment"),
    ("report-resume", "c", "research-reporting"),
])
@pytest.mark.parametrize("wrong_phase", [False, True])
def test_live_evaluator_checks_current_phase_with_offline_transport(
        monkeypatch, protocol, case_id, option, expected_skill, wrong_phase):
    import runpy
    from pathlib import Path
    evaluator = runpy.run_path(str(Path(__file__).resolve().parents[1]
                                  / "scripts/check_research_skills_model.py"))
    if wrong_phase:
        # Simulate a routing regression, keeping the provider and evaluator real.
        monkeypatch.setattr(provider, "_scope_skill_names", lambda context: ("case-understanding",))
    requests = connect(monkeypatch, [response_message(protocol, "assessment",
        decision={"action": "check", "option_id": option * 64})])
    results, _ = evaluator["run_cases"](settings(protocol), [case_id])
    assert len(results) == len(requests) == 1
    assert results[0]["skills"][0]["name"] == (
        "case-understanding" if wrong_phase else expected_skill)
    assert results[0]["passed"] is not wrong_phase
    assert results[0]["errors"] == (["skill_not_selected"] if wrong_phase else [])


@pytest.mark.parametrize("has_evidence", [False, True])
@pytest.mark.parametrize("literature_enabled", [False, True])
def test_json_prompt_schema_preserves_available_and_forbidden_actions(
        monkeypatch, has_evidence, literature_enabled):
    from copy import deepcopy
    from jsonschema import Draft202012Validator
    context = {"purpose": "assessment", "options": [], "evidence": ([{
        "measurements": [{"citation_alias": "E-record", "citation_role": "observation"}]
    }] if has_evidence else [])}
    if literature_enabled:
        context["literature"] = {
            "search_concept_refs": ["neuron"], "searches_remaining": 1,
            "readable_source_refs": ["literature:epmc-med-12345"], "reads_remaining": 1,
            "sources": [{"source_ref": "literature:epmc-med-67890", "content_level": "abstract"}],
        }
    requests = connect(monkeypatch, [response_message("json", "assessment",
        decision={"action": "stop", "reason": "no_discriminating_check"})])
    provider.converse(settings("json"), [{"role": "user", "content": "Explain or stop."}], context)
    prompt = requests[0]["messages"][0]["content"]
    schema, _ = json.JSONDecoder().raw_decode(prompt.split("Assessment action schema: ", 1)[1])
    advertised = Draft202012Validator(schema)
    native = Draft202012Validator(provider.action_tools("assessment",
        assessment_choices=provider._assessment_choices(context))[0]["function"]["parameters"])
    hypothesis = {"statement": "An observation.", "evidence_aliases": ["E-record"],
        "competing_explanation": "A rival.", "discriminating_check": None, "feature_queries": []}
    trials = [
        ({"action": "stop", "reason": "no_discriminating_check"}, True),
        ({"action": "explain", "hypotheses": []}, False),
        ({"action": "explain", "hypotheses": [hypothesis]}, has_evidence),
        ({"action": "explain", "hypotheses": [{**hypothesis, "feature_queries": "GENE"}]}, False),
        ({"action": "explain", "hypotheses": [{**hypothesis, "evidence_aliases": ["unknown"]}]}, False),
        ({"action": "explain", "hypotheses": [{**hypothesis, "invented": True}]}, False),
        ({"action": "check", "option_id": "invented"}, False),
        ({"action": "search_literature", "concept_refs": ["neuron"], "focus": "identity"}, literature_enabled),
        ({"action": "read_literature", "source_ref": "literature:epmc-med-12345"}, literature_enabled),
        ({"action": "explain", "hypotheses": [{**hypothesis, "literature_support": [{}]}]}, False),
    ]
    use = {"source_ref": "literature:epmc-med-67890", "rationale": "Biological background.",
           "species": "unknown", "lineage": "unknown", "stage": "unknown", "experimental_context": "unknown"}
    trials.append(({"action": "explain", "hypotheses": [{**hypothesis, "literature_support": [use]}]},
                   has_evidence and literature_enabled))
    legacy = deepcopy(hypothesis)
    legacy.pop("feature_queries")
    trials.append(({"action": "explain", "hypotheses": [legacy]}, False))
    for decision, allowed in trials:
        assert advertised.is_valid({"action": "assessment", "decision": decision}) is allowed
        assert native.is_valid({"decision": decision}) is allowed
    # Storage compatibility is separate from the stricter current request schema.
    assert provider.AssessmentHypothesis.model_validate(legacy).feature_queries == []
