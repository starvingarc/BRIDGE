"""Choice cards exercise private state and real controls; only the model is replaced."""
from __future__ import annotations
from copy import deepcopy
import json

import pytest

from bridge.web.provider import parse_action
from test_web_service import client, confirm_change, new_session, settle
from test_web_intake import uploaded


def question_set(aid, *, field="assay", multiple=False):
    options = [
        {"id": "scRNA-seq", "label": "单细胞 RNA 测序", "description": "整细胞"},
        {"id": "snRNA-seq", "label": "单核 RNA 测序", "description": "细胞核"},
    ]
    if field == "assessment_focus":
        options = [
            {"id": "composition", "label": "细胞组成", "description": "参考支持"},
            {"id": "development", "label": "发育阶段", "description": "预期窗口"},
        ]
    return {"upload_id": aid, "questions": [{
        "field": field, "title": "这份数据使用哪种测序？",
        "reason": "用于选择兼容的数据检查。", "multiple": multiple, "options": options,
    }]}


def native(payload):
    return {"tool_calls": [{"type": "function", "function": {
        "name": payload["action"],
        "arguments": json.dumps({key: value for key, value in payload.items() if key != "action"}),
    }}]}


@pytest.mark.parametrize("protocol", ["json", "deepseek_tools"])
def test_question_action_is_parsed_in_both_configured_transports(protocol):
    payload = {"action": "ask_user_input", "questions": question_set("a" * 32)}
    try:
        action = parse_action(native(payload) if protocol == "deepseek_tools" else
                              {"content": json.dumps(payload)}, protocol)
    except ValueError:
        action = None
    assert action is not None, "the current provider rejects conversational choice questions"
    assert action.action == "ask_user_input"
    assert action.questions.questions[0].field == "assay"


def ask(client, monkeypatch, sid, aid, **kwargs):
    payload = {"action": "ask_user_input", "questions": question_set(aid, **kwargs)}
    monkeypatch.setattr("bridge.web.app.converse",
                        lambda *args: parse_action({"content": json.dumps(payload)}))
    assert client.post(f"/api/sessions/{sid}/messages", json={"text": "请用选项核对"}).status_code == 200
    state = settle(client, sid)
    assert state["error"] is None, "a choice action must create a card, not provider_unavailable"
    assert state.get("clarifications"), "the question is absent from the Web session"
    return state["clarifications"][-1]


def answer(card, *, selected=None, text="", unknown=False):
    return {"card_id": card["id"], "card_digest": card["digest"], "answers": [{
        "field": card["questions"][0]["field"], "selected": selected or [],
        "text": text, "unknown": unknown,
    }]}


def test_choice_answer_stages_unconfirmed_facts_without_running_a_tool(client, tmp_path, monkeypatch):
    sid, aid = uploaded(client, tmp_path)
    card = ask(client, monkeypatch, sid, aid)
    assert card["status"] == "pending"
    url = f"/api/sessions/{sid}"
    body = answer(card, selected=["scRNA-seq"])
    response = client.post(url + "/clarification/answer", json=body)
    assert response.status_code == 200, response.json()
    state = response.json()
    assert state["clarifications"][-1]["status"] == "answered"
    assert state["pending_input_change"]["kind"] == "intake"
    assert state["input_review_required"]
    assert state["plan"] is None
    service = client.app.state.service
    assert service.load(sid)["_tool_runs"] == []
    assert client.get(url + "/intake", params={"upload_id": aid}).json()["facts"]["assay"] == "unknown"
    assert client.post(url + "/clarification/answer", json=body).status_code == 200
    changed = deepcopy(body)
    changed["answers"][0]["selected"] = ["snRNA-seq"]
    assert client.post(url + "/clarification/answer", json=changed).status_code == 409
    confirm_change(client, sid, state)
    assert client.get(url + "/intake", params={"upload_id": aid}).json()["facts"]["assay"] == "scRNA-seq"


def test_private_answer_and_supplement_are_excluded_from_model_history(client, tmp_path, monkeypatch):
    sid, aid = uploaded(client, tmp_path)
    card = ask(client, monkeypatch, sid, aid)
    marker = "PRIVATE_ANSWER_SENTINEL"
    response = client.post(f"/api/sessions/{sid}/clarification/answer",
                           json=answer(card, selected=["scRNA-seq"], text=marker))
    assert response.status_code == 200
    assert marker in json.dumps(response.json()["clarifications"])
    captured = []
    def reply(settings, messages, context):
        captured.append({"messages": messages, "context": context})
        return parse_action({"content": '{"action":"reply","text":"请核对草稿。"}'})
    monkeypatch.setattr("bridge.web.app.converse", reply)
    client.post(f"/api/sessions/{sid}/messages", json={"text": "继续"})
    assert settle(client, sid)["error"] is None
    assert marker not in json.dumps(captured)
    assert "scRNA-seq" not in json.dumps(captured[0]["messages"])
    assert captured[0]["context"]["clarification_context"][-1]["fields"] == ["assay"]


@pytest.mark.parametrize("mutation", ["unknown_option", "multiple", "unknown_and_selected", "wrong_field", "duplicate_field"])
def test_invalid_answers_cannot_mutate_the_session(client, tmp_path, monkeypatch, mutation):
    sid, aid = uploaded(client, tmp_path)
    card = ask(client, monkeypatch, sid, aid)
    body = answer(card, selected=["scRNA-seq"])
    if mutation == "unknown_option":
        body["answers"][0]["selected"] = ["invented"]
    elif mutation == "multiple":
        body["answers"][0]["selected"] = ["scRNA-seq", "snRNA-seq"]
    elif mutation == "unknown_and_selected":
        body["answers"][0]["unknown"] = True
    elif mutation == "wrong_field":
        body["answers"][0]["field"] = "count_semantics"
    else:
        body["answers"].append(deepcopy(body["answers"][0]))
    service = client.app.state.service
    before = service.load(sid)
    response = client.post(f"/api/sessions/{sid}/clarification/answer", json=body)
    assert response.status_code == 422
    assert service.load(sid) == before


def test_unknown_answer_is_persisted_and_not_reasked(client, tmp_path, monkeypatch):
    sid, aid = uploaded(client, tmp_path)
    card = ask(client, monkeypatch, sid, aid)
    response = client.post(f"/api/sessions/{sid}/clarification/answer", json=answer(card, unknown=True))
    assert response.status_code == 200
    state = response.json()
    assert state["clarifications"][-1]["answers"][0]["unknown"] is True
    # Unknown retains missingness; it does not create a pointless confirmation.
    assert state["pending_input_change"] is None
    again = ask(client, monkeypatch, sid, aid)
    assert again["id"] == card["id"]
    assert again["status"] == "answered"
    assert len(client.get(f"/api/sessions/{sid}").json()["clarifications"]) == 1


def test_stale_and_cross_session_answers_are_rejected(client, tmp_path, monkeypatch):
    sid, aid = uploaded(client, tmp_path)
    card = ask(client, monkeypatch, sid, aid)
    body = answer(card, selected=["scRNA-seq"])
    other = new_session(client)["id"]
    assert client.post(f"/api/sessions/{other}/clarification/answer", json=body).status_code == 409
    url = f"/api/sessions/{sid}"
    staged = client.post(url + "/intake", json={"upload_id": aid, "facts": {"assay": "snRNA-seq"}}).json()
    confirm_change(client, sid, staged)
    assert client.post(url + "/clarification/answer", json=body).status_code == 409
    assert client.get(url).json()["clarifications"][-1]["status"] == "stale"


def test_cancel_and_explicit_revision_do_not_grant_default_answers(client, tmp_path, monkeypatch):
    sid, aid = uploaded(client, tmp_path)
    card = ask(client, monkeypatch, sid, aid)
    url = f"/api/sessions/{sid}"
    identity = {"card_id": card["id"], "card_digest": card["digest"]}
    cancelled = client.post(url + "/clarification/cancel", json=identity)
    assert cancelled.status_code == 200
    assert cancelled.json()["clarifications"][-1]["status"] == "cancelled"
    assert cancelled.json()["pending_input_change"] is None
    reopened = client.post(url + "/clarification/revise", json=identity)
    assert reopened.status_code == 200
    new = reopened.json()["clarifications"][-1]
    assert new["id"] != card["id"] and new["status"] == "pending"
    assert client.app.state.service.load(sid)["_tool_runs"] == []


def test_multi_select_focus_is_a_preference_not_a_scientific_fact(client, tmp_path, monkeypatch):
    sid, aid = uploaded(client, tmp_path)
    card = ask(client, monkeypatch, sid, aid, field="assessment_focus", multiple=True)
    response = client.post(f"/api/sessions/{sid}/clarification/answer",
                          json=answer(card, selected=["composition", "development"]))
    assert response.status_code == 200
    state = response.json()
    assert state["clarifications"][-1]["answers"][0]["selected"] == ["composition", "development"]
    assert state["pending_input_change"] is None and state["plan"] is None
    assert client.app.state.service.load(sid)["_tool_runs"] == []


def test_free_text_answer_is_reviewed_not_executed(client, tmp_path, monkeypatch):
    sid, aid = uploaded(client, tmp_path)
    card = ask(client, monkeypatch, sid, aid, field="target_cell_type")
    response = client.post(f"/api/sessions/{sid}/clarification/answer",
                          json=answer(card, text="研究目标由用户补充"))
    assert response.status_code == 200
    state = response.json()
    change = next(item for item in state["pending_input_change"]["changes"] if item["field"] == "target_cell_type")
    assert change["after"] == "研究目标由用户补充"
    assert state["plan"] is None

def test_native_question_schema_can_validate_the_actual_function_arguments():
    from bridge.web.provider import action_tools
    from jsonschema import Draft202012Validator
    tool = next((item for item in action_tools() if item["function"]["name"] == "ask_user_input"), None)
    assert tool is not None
    try:
        Draft202012Validator(tool["function"]["parameters"]).validate({"questions": question_set("a" * 32)})
    except Exception as exc:
        pytest.fail("native question schema cannot resolve its argument definitions: " + type(exc).__name__)


@pytest.mark.parametrize("protocol", ["json", "deepseek_tools"])
def test_actual_provider_wire_creates_a_card_without_a_tool_run(client, tmp_path, monkeypatch, protocol):
    import httpx
    from dataclasses import replace
    from bridge.web.provider import converse
    sid, aid = uploaded(client, tmp_path)
    service = client.app.state.service
    service.settings = replace(service.settings, model_action_protocol=protocol)
    original = httpx.Client
    # Capture the wire through the real provider parser; preserve the HTTP boundary.
    def wire(request):
        payload = json.loads(request.content)
        assert payload["messages"][0]["role"] == "system"
        action = {"action": "ask_user_input", "questions": question_set(aid)}
        message = native(action) if protocol == "deepseek_tools" else {"content": json.dumps(action)}
        return httpx.Response(200, json={"choices": [{"message": message}]})
    monkeypatch.setattr("bridge.web.provider.httpx.Client",
        lambda **kwargs: original(**({**kwargs, "transport": httpx.MockTransport(wire)})))
    client.post(f"/api/sessions/{sid}/messages", json={"text": "用选项确认实验类型"})
    state = settle(client, sid)
    assert state["error"] is None
    assert state["clarifications"][-1]["questions"][0]["field"] == "assay"
    assert service.load(sid)["_tool_runs"] == []

@pytest.mark.parametrize("protocol", ["json", "deepseek_tools"])
def test_provider_reserved_unknown_option_is_owned_by_application(protocol):
    payload = {"action": "ask_user_input", "questions": question_set("a" * 32)}
    payload["questions"]["questions"][0]["options"].append(
        {"id": "unknown", "label": "不确定", "description": "模型重复提供的保留选项"})
    try:
        action = parse_action(native(payload) if protocol == "deepseek_tools" else
                              {"content": json.dumps(payload)}, protocol)
    except ValueError:
        action = None
    assert action is not None, "the actual provider duplicates the app-owned unknown option"
    assert [row.id for row in action.questions.questions[0].options] == ["scRNA-seq", "snRNA-seq"]
    # Unknown is not a replacement for two real choices, and other invalid IDs remain rejected.
    payload["questions"]["questions"][0]["options"][0]["id"] = "invented-assay"
    with pytest.raises(ValueError):
        parse_action(native(payload) if protocol == "deepseek_tools" else
                     {"content": json.dumps(payload)}, protocol)
