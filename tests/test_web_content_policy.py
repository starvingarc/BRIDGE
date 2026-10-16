from __future__ import annotations

import hashlib
import json

import pytest

from bridge.web.provider import Action
from web_support import client, new_session, settle


def _provider():
    from bridge.web import provider

    return provider


def _state(**updates):
    state = {
        "status": "idle",
        "error": None,
        "messages": [{
            "id": "u1",
            "role": "user",
            "content": "What do the current results mean?",
            "created_at": "now",
            "source": "user_input",
        }],
        "artifacts": [],
        "input_review_required": False,
        "pending_input_change": None,
        "_assessment": None,
        "private_path": "/private/must-not-leak/result.json",
    }
    state.update(updates)
    return state


def _summary():
    return {
        "state": "available",
        "evidence_ref": "E1",
        "n_observations": 96,
        "independence_state": "unknown",
        "n_independent_replicates": None,
        "state_review_status": "pending",
        "score_state": "unavailable",
        "domain_score": None,
        "reason_codes": ["independent_replicates_unknown"],
    }


@pytest.mark.parametrize(
    "name,state,summary,expected_reason,expected_correction",
    [
        ("start", _state(), {"state": "not_available"}, "results_not_available", "current"),
        ("confirmation", _state(input_review_required=True), {"state": "not_available"},
         "input_correction_pending", "review_required"),
        ("running", _state(status="running"), {"state": "not_available"},
         "work_in_progress", "current"),
        ("partial", _state(status="failed", error="execution_failed", artifacts=[{"id": "a"}]),
         _summary(), "execution_incomplete", "current"),
        ("failure_recovery", _state(status="failed", error="execution_failed"),
         {"state": "not_available"}, "execution_incomplete", "current"),
        ("result_explanation", _state(_assessment={"status": "stopped", "stop_reason": "explanation_complete"}),
         _summary(), "scientific_question_open", "current"),
        ("follow_up", _state(messages=[{"id": "u2", "role": "user", "content": "Why is that unknown?",
                                        "created_at": "now", "source": "user_input"}]),
         _summary(), "scientific_question_open", "current"),
        ("correction", _state(pending_input_change={"id": "change"}), _summary(),
         "input_correction_pending", "pending_change"),
    ],
)
def test_research_context_covers_conversation_states_without_private_values(
    name, state, summary, expected_reason, expected_correction,
) -> None:
    provider = _provider()

    context = provider.build_research_context(
        state,
        confirmed_input_state=[{
            "upload_id": "u" * 32,
            "state": "confirmed",
            "missing_fields": ["culture_batch_column"],
        }],
        analyses_attempted=[{"tool_id": "P0-02", "state": "partial"}],
        result_summary=summary,
    )
    encoded = json.dumps(context, ensure_ascii=False)

    assert set(context) == {
        "current_question",
        "confirmed_input_state",
        "analyses_attempted",
        "admitted_results",
        "limitations",
        "unresolved_reason",
        "user_correction_state",
    }
    assert context["unresolved_reason"] == expected_reason, name
    assert context["user_correction_state"] == expected_correction, name
    assert context["admitted_results"]["state"] == summary["state"]
    assert "/private/" not in encoded
    assert "must-not-leak" not in encoded


def test_result_reply_uses_structured_observation_and_rejects_legacy_cited_prose() -> None:
    provider = _provider()
    context = {
        "results_sent_to_model": True,
        "result_summary": _summary(),
        "research_context": {"current_question": "What do the results mean?"},
    }

    for text in [
        "目前独立重复数仍是未知，因此这里只能描述这批数据中的观察。[E1]",
        "这套方法尚未通过本次身份判断所需的验证；这不等于样本本身不合格。[E1]",
        "评分当前不可用，所以不能据此排名或判断哪一个更强。[E1]",
        "本次共有 96 个观测；其可重复性仍未知。[E1]",
    ]:
        assert provider.admit_provider_text(text, context) == (
            "解释尚未通过核对",
            "server_template",
        )

    choices = provider.result_observation_choices(context)
    summary = next(row for row in choices if row["evidence_ref"] == "E1"
                   and row["record"].get("n_observations") == 96)
    text, source = provider.admit_provider_text(
        "独立性仍未解决，因此这里只提出待检验的解释。",
        context,
        observation_aliases=[summary["observation_alias"]],
    )
    assert source == "provider_admitted"
    assert text.startswith("观察（E1）：")
    assert "n_observations=96" in text
    assert "independence_state=unknown" in text
    assert text.endswith("解释（未验证假设）：独立性仍未解决，因此这里只提出待检验的解释。")


def test_method_follow_up_stays_natural_without_result_evidence() -> None:
    provider = _provider()
    context = {
        "results_sent_to_model": False,
        "research_context": {"current_question": "这个方法如何处理分母？"},
    }

    method = "这个方法会先固定分析单位和分母，再计算相应指标。"
    assert provider.admit_provider_text(method, context) == (
        method,
        "provider_admitted",
    )
    clarification = "请问有多少个独立重复？"
    assert provider.admit_provider_text(clarification, context) == (
        clarification,
        "provider_admitted",
    )
    unsupported = "结果显示样本已经通过。"
    assert provider.admit_provider_text(unsupported, context) == (
        unsupported,
        "provider_admitted",
    )


def test_unselected_result_text_keeps_source_without_body_boilerplate() -> None:
    provider = _provider()
    context = {
        "results_sent_to_model": True,
        "result_summary": {
            "state": "available",
            "evidence_ref": "E1",
            "measurements": [{
                "metric_name": "g2m_score",
                "method_id": "method_a",
                "value": 0.0185,
                "unit": "score",
                "evidence_state": "measured",
            }],
        },
    }

    for raw in (
        "method_a 的 g2m_score 为 -0.0185 score。",
        "这次观察提示技术混杂是主因。",
    ):
        assert provider.admit_provider_text(raw, context) == (
            raw,
            "provider_admitted",
        )

    method = "这个方法会先固定分析单位和分母，再计算相应指标。"
    text, source = provider.admit_provider_text(method, context)
    assert source == "provider_admitted"
    assert text == method
    assert "假设" not in text


def test_scientific_boundary_statement_is_not_rejected_by_keyword_matching() -> None:
    provider = _provider()
    boundary = "这些结果不能用于判断临床疗效。"

    assert provider.admit_provider_text(boundary, {"results_sent_to_model": False}) == (
        boundary,
        "provider_admitted",
    )
    assert provider.proposed_hypothesis_text_is_unbound(boundary)


def test_hypothesis_rendering_keeps_each_statement_and_evidence_role_separate() -> None:
    provider = _provider()
    rendered = provider.render_assessment_hypotheses([
        {"statement": "Candidate signal A", "evidence_aliases": ["E-source#record:A@1"],
         "opposing_evidence_aliases": ["E-source#record:B@1"],
         "missing_evidence_aliases": ["E-source#record:C@1"],
         "competing_explanation": "Alternative A", "expected_observation": "Prediction A",
         "discriminating_check": None},
        {"statement": "Candidate signal D", "evidence_aliases": ["E-source#record:D@2"],
         "opposing_evidence_aliases": [], "missing_evidence_aliases": [],
         "competing_explanation": "Alternative D", "expected_observation": None,
         "discriminating_check": "P0-06"},
        {"statement": "This run is unavailable", "evidence_aliases": [],
         "opposing_evidence_aliases": [], "missing_evidence_aliases": ["E-source#missing@2"],
         "competing_explanation": "Not a negative observation", "expected_observation": None,
         "discriminating_check": None},
    ])
    first, second, gap = rendered.split("\n\n")
    assert first.startswith("1. 待检验解释：Candidate signal A")
    assert "相关观察或支持记录：[E-source#record:A@1]" in first
    assert "相反证据：[E-source#record:B@1]" in first
    assert "缺失证据记录：[E-source#record:C@1]" in first
    assert "竞争解释（未验证）：Alternative A" in first
    assert "预期观察（未测量）：Prediction A" in first
    assert "鉴别检查：尚未确定" in first
    assert "E-source#record:D@2" not in first
    assert second.startswith("2. 待检验解释：Candidate signal D")
    assert "相关观察或支持记录：[E-source#record:D@2]" in second
    assert "相反证据" not in second and "缺失证据记录" not in second
    assert "E-source#record:A@1" not in second
    assert "鉴别检查：P0-06" in second
    assert gap.startswith("3. 证据缺口说明：This run is unavailable")
    assert "限制说明：Not a negative observation" in gap
    assert "缺失证据记录：[E-source#missing@2]" in gap
    assert all(label not in gap for label in ("竞争解释", "鉴别检查", "待检验解释", "预期观察"))


def test_result_admission_distinguishes_method_explanation_from_unbound_interpretation() -> None:
    provider = _provider()
    context = {
        "results_sent_to_model": True,
        "result_summary": {
            "state": "available",
            "evidence_ref": "E1",
            "measurements": [
                {"value": 0.0185, "unit": "u1"},
                {"value": 3.563, "unit": "u2"},
            ],
        },
    }

    for text in (
        "主要差异最可能来自技术混杂。[E1]",
        "Technical confounding caused the result. [E1]",
        "两个 G2M 指标方向相反。[E1]",
    ):
        assert provider.admit_provider_text(text, context) == (
            "解释尚未通过核对",
            "server_template",
        )

    method = "评分用于概括某项测量。"
    assert provider.admit_provider_text(method, context) == (
        method,
        "provider_admitted",
    )


def test_structured_observation_keeps_method_value_sign_unit_and_source_in_one_record() -> None:
    provider = _provider()
    context = {
        "results_sent_to_model": True,
        "result_summary": {
            "state": "available",
            "evidence_ref": "E1",
            "tool_version": "1.2.3",
            "comparison_eligibility": "strictly_comparable",
            "measurements": [
                {"metric_name": "g2m_score", "method_id": "method_a",
                 "value": 0.0185, "unit": "score", "evidence_state": "measured"},
                {"metric_name": "g2m_score", "method_id": "method_b",
                 "value": 0.03563, "unit": "score", "evidence_state": "measured"},
            ],
        },
    }
    rejected = (
        "method_a 的 g2m_score 为 0.03563 score。[E1]",
        "method_a 的 g2m_score 为 -0.0185 score。[E1]",
        "这次观察提示技术混杂是主因；method_a 的 g2m_score 为 0.0185 score。[E1]",
    )
    for text in rejected:
        assert provider.admit_provider_text(text, context) == (
            "解释尚未通过核对", "server_template")

    choices = provider.result_observation_choices(context)
    method_a = next(row for row in choices
                    if row["record"].get("method_id") == "method_a")
    text, source = provider.admit_provider_text(
        "技术混杂是一项仍需区分的假设。",
        context,
        observation_aliases=[method_a["observation_alias"]],
    )
    assert source == "provider_admitted"
    assert "method_id=method_a" in text
    assert "metric_name=g2m_score" in text
    assert "value=0.0185" in text
    assert "unit=score" in text
    assert "tool_version=1.2.3" in text
    assert "0.03563" not in text
    assert text.endswith("解释（未验证假设）：技术混杂是一项仍需区分的假设。")

    negative = json.loads(json.dumps(context))
    negative["result_summary"]["measurements"][0]["value"] = -0.0185
    choice = next(row for row in provider.result_observation_choices(negative)
                  if row["record"].get("method_id") == "method_a")
    text, _ = provider.admit_provider_text(
        "方向需要结合独立检查解释。",
        negative,
        observation_aliases=[choice["observation_alias"]],
    )
    assert "value=-0.0185" in text


def test_native_reply_can_select_only_current_structured_observation_aliases() -> None:
    from jsonschema import Draft202012Validator
    from bridge.web.provider import action_tools, parse_action

    parameters = next(row for row in action_tools(observation_aliases=["O0"])
                      if row["function"]["name"] == "reply")["function"]["parameters"]
    payload = {"text": "This remains an unverified interpretation.",
               "observation_aliases": ["O0"]}
    Draft202012Validator.check_schema(parameters)
    assert Draft202012Validator(parameters).is_valid(payload)
    assert not Draft202012Validator(parameters).is_valid({**payload,
        "observation_aliases": ["O9"]})

    action = parse_action({"content": None, "tool_calls": [{
        "type": "function", "function": {
            "name": "reply", "arguments": json.dumps(payload),
        }}]}, protocol="deepseek_tools")
    assert action.observation_aliases == ["O0"]


def test_public_message_sources_and_legacy_warning(client, monkeypatch) -> None:
    monkeypatch.setattr(
        "bridge.web.service.converse",
        lambda *args: Action.model_validate({
            "action": "reply",
            "text": "我可以先解释方法，再根据证据回答结果问题。",
        }),
    )
    sid = new_session(client)["id"]
    initial = client.get(f"/api/sessions/{sid}").json()
    assert initial["messages"][0]["source"] == "server_template"

    client.post(f"/api/sessions/{sid}/messages", json={"text": "先解释一下方法。"})
    replied = settle(client, sid)
    assert replied["messages"][-2]["source"] == "user_input"
    assert replied["messages"][-1]["source"] == "provider_admitted"

    service = client.app.state.service
    state = service.load(sid)
    state["messages"].append({
        "id": "legacy",
        "role": "assistant",
        "content": "historical text",
        "created_at": "before-source-contract",
    })
    service.sessions.save(state)
    legacy = client.get(f"/api/sessions/{sid}").json()["messages"][-1]
    assert "source" not in legacy
    assert legacy["provenance_warning"] == "legacy_unclassified"


def test_rejected_provider_text_is_not_persisted(client, monkeypatch) -> None:
    private = "内部草稿 PRIVATE_RAW_PROVIDER_TEXT [E1]"
    monkeypatch.setattr(
        "bridge.web.service.converse",
        lambda *args: Action.model_validate({"action": "reply", "text": private}),
    )
    sid = new_session(client)["id"]
    client.post(f"/api/sessions/{sid}/messages", json={"text": "结果说明样本通过了吗？"})
    value = settle(client, sid)

    assert value["messages"][-1]["content"] == "解释尚未通过核对"
    assert value["messages"][-1]["source"] == "server_template"
    assert private not in json.dumps(client.app.state.service.load(sid), ensure_ascii=False)


def _install_policy_artifact(
    client,
    sid: str,
    *,
    name: str,
    data: bytes,
    content_class: str | None,
    source_kind: str,
    report_binding: dict | None = None,
) -> tuple[str, object]:
    from bridge.web.sessions import write_file

    service = client.app.state.service
    aid = hashlib.sha256((name + source_kind).encode()).hexdigest()[:32]
    stored = service.directory(sid) / "artifacts" / (aid + ".bin")
    write_file(stored, data)
    checksum = hashlib.sha256(data).hexdigest()
    state = service.load(sid)
    public = {
        "id": aid,
        "name": name,
        "kind": "download",
        "media_type": "text/html",
        "url": f"/api/sessions/{sid}/artifacts/{aid}",
        "tool_id": "P0-10",
    }
    if report_binding is not None:
        public["research_report"] = dict(report_binding)
    state["artifacts"].append(public)
    internal = {
        "file": stored.name,
        "sha256": checksum,
        "source_artifact_id": "source:" + aid,
        "source_sha256": checksum,
        "projection": "identity",
        "source_kind": source_kind,
    }
    if content_class is not None:
        internal["content_class"] = content_class
    if report_binding is not None:
        internal["report_binding"] = dict(report_binding)
    state["_artifacts"][aid] = internal
    service.sessions.save(state)
    return aid, stored


def _report_binding(state: dict, graph_sha256: str) -> dict:
    return {
        "input_revision": str(state["_input_revision"]),
        "graph_id": "graph-current",
        "graph_version": 3,
        "graph_manifest_sha256": graph_sha256,
        "snapshot_sha256": "2" * 64,
        "renderer_id": "BRIDGE-RESEARCH-REPORT-RENDERER-v0.2",
        "snapshot_object_version": "0.3.0",
    }


def test_current_and_historical_reports_keep_original_bytes_and_require_acknowledgement(
    client, monkeypatch,
) -> None:
    sid = new_session(client)["id"]
    service = client.app.state.service
    graph_sha256 = "1" * 64
    state = service.load(sid)
    state.setdefault("_input_objects", {})["graph-current"] = {
        "path": "/private/not-read-by-test/graph.json",
        "sha256": graph_sha256,
        "schema_ref": "bridge://schemas/case-evidence-graph-manifest/v0.1",
        "object_version": "0.1.0",
        "source": "tool_output",
        "producer_tool_id": "P0-09",
        "receipt_file": "graph-receipt.json",
        "receipt_sha256": "3" * 64,
    }
    state.setdefault("_invalidated_receipts", {})
    service.sessions.save(state)
    original_verify = service.inputs.verify

    def verify(current, record):
        if record.get("sha256") == graph_sha256:
            return {"graph_id": "graph-current", "graph_version": 3}
        return original_verify(current, record)

    monkeypatch.setattr(service.inputs, "verify", verify)
    binding = _report_binding(service.load(sid), graph_sha256)
    original = b"<html><body>immutable report bytes</body></html>"
    aid, stored = _install_policy_artifact(
        client,
        sid,
        name="renamed-report.payload",
        data=original,
        content_class="research_report",
        source_kind="research_report",
        report_binding=binding,
    )
    url = f"/api/sessions/{sid}/artifacts/{aid}"

    current = client.get(f"/api/sessions/{sid}").json()
    item = next(row for row in current["artifacts"] if row["id"] == aid)
    assert item["content_class"] == "research_report"
    assert item["access_state"] == "current"
    assert item["acknowledgement_required"] is False
    assert client.get(url).content == original

    changed = service.load(sid)
    changed["_input_revision"] += 1
    service.sessions.save(changed)
    historical = client.get(f"/api/sessions/{sid}").json()
    item = next(row for row in historical["artifacts"] if row["id"] == aid)
    assert item["access_state"] == "historical_unreviewed"
    assert item["acknowledgement_required"] is True
    assert "当前" in item["warning"] and "原始文件" in item["warning"]
    assert client.get(url).status_code == 409
    assert client.get(url + "/preview").status_code == 409
    assert stored.read_bytes() == original

    acknowledged = client.post(url + "/acknowledge", json={})
    assert acknowledged.status_code == 200
    assert acknowledged.json()["acknowledged"] is True
    downloaded = client.get(url)
    assert downloaded.status_code == 200 and downloaded.content == original
    assert stored.read_bytes() == original


def test_verified_report_registration_carries_complete_snapshot_binding(client) -> None:
    from test_p0_09_evidence_compiler import _run
    from test_research_report_delivery import execute, make_draft, request_for, research

    sid = new_session(client)["id"]
    service = client.app.state.service
    root = service.directory(sid) / "runs" / "content-policy-report"
    graph_run = _run(root / "graph")
    assert graph_run.execution_state.value == "succeeded"
    graph_path = (
        graph_run.request.output_dir
        / graph_run.run_id
        / "case_evidence_graph_manifest.json"
    )
    outcome = execute(request_for(root / "verification", graph_path, make_draft(graph_path)))
    assert outcome.execution_state.value == "succeeded"
    snapshot_path = next(
        item.path for item in outcome.artifacts
        if item.path.name == "research_snapshot.json"
    )
    snapshot = research().ResearchAnalysisSnapshot.model_validate_json(
        snapshot_path.read_bytes()
    )
    expected = {
        "input_revision": snapshot.input_revision,
        "graph_id": snapshot.graph_id,
        "graph_version": snapshot.graph_version,
        "graph_manifest_sha256": snapshot.graph_manifest_sha256,
        "snapshot_sha256": snapshot.snapshot_sha256,
        "renderer_id": snapshot.renderer_id,
        "snapshot_object_version": snapshot.object_version,
    }
    state = service.load(sid)
    state["_tool_runs"].append({
        "file": "content-policy-report-receipt.json",
        "sha256": "6" * 64,
        "tool_id": "P0-10",
        "state": "succeeded",
        "plan_id": "content-policy-report-plan",
    })
    service.artifacts.register(state, outcome)

    stored = service.load(sid)
    reports = [
        item for item in stored["artifacts"]
        if item.get("content_class") == "research_report"
    ]
    assert len(reports) == 4
    assert {item["name"] for item in reports} == {
        "research_report.html",
        "research_report.json",
        "research_report.csv",
        "research_report.svg",
    }
    for item in reports:
        assert item["research_report"] == expected
        assert stored["_artifacts"][item["id"]]["report_binding"] == expected
    assert not any(
        item["id"] in {row["id"] for row in service.public(stored)["artifacts"]}
        for item in stored["artifacts"]
        if stored["_artifacts"][item["id"]]["source_kind"] == "artifact_manifest"
    )


def test_legacy_report_is_historical_and_diagnostic_provenance_cannot_be_renamed_public(
    client,
) -> None:
    sid = new_session(client)["id"]
    service = client.app.state.service
    legacy_binding = {
        "input_revision": str(service.load(sid)["_input_revision"]),
        "graph_version": 1,
        "snapshot_sha256": "4" * 64,
    }
    legacy_id, _ = _install_policy_artifact(
        client,
        sid,
        name="legacy-report.html",
        data=b"legacy report",
        content_class=None,
        source_kind="research_report",
        report_binding=legacy_binding,
    )
    diagnostic_id, _ = _install_policy_artifact(
        client,
        sid,
        name="research_report.html",
        data=b"developer trace renamed as report",
        content_class="user_result",
        source_kind="artifact_manifest",
        report_binding=_report_binding(service.load(sid), "5" * 64),
    )

    public = client.get(f"/api/sessions/{sid}").json()
    legacy = next(row for row in public["artifacts"] if row["id"] == legacy_id)
    assert legacy["content_class"] == "research_report"
    assert legacy["access_state"] == "historical_unreviewed"
    assert diagnostic_id not in {row["id"] for row in public["artifacts"]}

    diagnostic_url = f"/api/sessions/{sid}/artifacts/{diagnostic_id}"
    assert client.get(diagnostic_url).status_code == 404
    assert client.get(diagnostic_url + "/preview").status_code == 404
    assert client.post(diagnostic_url + "/acknowledge", json={}).status_code == 404


def _install_legacy_receipt_report(client, sid, *, source_kind="research_report"):
    from bridge.web.sessions import write_file

    service = client.app.state.service
    original = b"<html><body>historical source-backed report</body></html>"
    binding = {"input_revision": str(service.load(sid)["_input_revision"]),
        "graph_version": 1, "snapshot_sha256": "4" * 64}
    aid, stored = _install_policy_artifact(client, sid, name="renamed-history.payload",
        data=original, content_class=None, source_kind=source_kind, report_binding=binding)
    state = service.load(sid)
    root = service.directory(sid)
    source = root / "runs" / (aid + ".html")
    write_file(source, original)
    source_hash = hashlib.sha256(original).hexdigest()
    source_id = state["_artifacts"][aid]["source_artifact_id"]
    receipt = {"request": {"tool_id": "P0-10", "mode_id": "default"},
        "execution_state": "succeeded", "artifacts": [{
            "artifact_id": source_id, "path": str(source),
            "sha256": source_hash, "kind": source_kind}]}
    raw = json.dumps(receipt).encode()
    receipt_file = aid + ".json"
    write_file(root / "receipts" / receipt_file, raw)
    receipt_hash = hashlib.sha256(raw).hexdigest()
    state["_tool_runs"].append({"file": receipt_file, "sha256": receipt_hash,
        "tool_id": "P0-10", "state": "succeeded", "plan_id": "historical-plan"})
    state["_canonical_artifacts"][aid] = {"path": str(source), "sha256": source_hash,
        "artifact_id": source_id, "receipt_file": receipt_file,
        "receipt_sha256": receipt_hash}
    state["_artifacts"][aid].pop("source_kind")
    state.setdefault("_invalidated_receipts", {})[receipt_file] = "product_name_changed"
    state["_input_revision"] += 1
    service.sessions.save(state)
    return aid, stored, receipt_file


def test_registered_legacy_report_survives_name_revision_without_reusing_receipt(client):
    sid = new_session(client)["id"]
    service = client.app.state.service
    aid, stored, _ = _install_legacy_receipt_report(client, sid)
    state = service.load(sid)
    with pytest.raises(ValueError, match="input_revision_invalidated_output"):
        service.inputs.receipt_artifacts(state, state["_canonical_artifacts"][aid])

    url = f"/api/sessions/{sid}/artifacts/{aid}"
    item = next(row for row in client.get(f"/api/sessions/{sid}").json()["artifacts"]
        if row["id"] == aid)
    assert item["content_class"] == "research_report"
    assert item["access_state"] == "historical_unreviewed"
    assert item["acknowledgement_required"] is True
    assert client.get(url).status_code == 409
    assert client.post(url + "/acknowledge", json={}).status_code == 200
    assert client.get(url).content == stored.read_bytes()


@pytest.mark.parametrize("fault", ["missing_origin", "wrong_source_hash", "tampered_receipt", "developer_source"])
def test_unverified_legacy_report_source_stays_private(client, fault):
    sid = new_session(client)["id"]
    service = client.app.state.service
    aid, _, receipt_file = _install_legacy_receipt_report(
        client, sid, source_kind="artifact_manifest" if fault == "developer_source" else "research_report")
    state = service.load(sid)
    if fault == "missing_origin":
        state["_canonical_artifacts"].pop(aid)
    elif fault == "wrong_source_hash":
        state["_artifacts"][aid]["source_sha256"] = "0" * 64
    elif fault == "tampered_receipt":
        receipt = service.directory(sid) / "receipts" / receipt_file
        from bridge.web.sessions import write_file
        write_file(receipt, receipt.read_bytes() + b" ")
    service.sessions.save(state)

    url = f"/api/sessions/{sid}/artifacts/{aid}"
    assert aid not in {row["id"] for row in client.get(f"/api/sessions/{sid}").json()["artifacts"]}
    assert client.get(url).status_code == 404
    assert client.post(url + "/acknowledge", json={}).status_code == 404


def test_transcript_uses_admitted_public_message_projection(client) -> None:
    sid = new_session(client)["id"]
    service = client.app.state.service
    state = service.load(sid)
    state["messages"].extend([
        {"id": "legacy-user", "role": "user", "content": "LEGACY_USER_QUESTION", "created_at": "then"},
        {"id": "legacy-assistant", "role": "assistant", "content": "UNCLASSIFIED_ASSISTANT", "created_at": "then"},
        {"id": "admitted", "role": "assistant", "content": "ADMITTED_METHOD", "created_at": "now", "source": "provider_admitted"},
        {"id": "rejected", "role": "assistant", "content": "REJECTED_RAW_PROVIDER", "created_at": "now", "source": "provider_rejected"},
    ])
    service.sessions.save(state)

    public = client.get(f"/api/sessions/{sid}").json()
    legacy = next(row for row in public["messages"] if row["id"] == "legacy-assistant")
    assert legacy["provenance_warning"] == "legacy_unclassified"
    transcript = client.get(f"/api/sessions/{sid}/transcript")
    assert transcript.status_code == 200
    assert "LEGACY_USER_QUESTION" in transcript.text
    assert "ADMITTED_METHOD" in transcript.text
    assert "UNCLASSIFIED_ASSISTANT" not in transcript.text
    assert "REJECTED_RAW_PROVIDER" not in transcript.text


@pytest.mark.parametrize("role,source,raw,expected", [
    ("assistant", "provider_admitted", "模型说明（未经结构化事实核验）：旧回答", "旧回答"),
    ("assistant", "provider_admitted", "模型说明（未经结构化事实核验）：模型说明（未经结构化事实核验）：旧回答", "旧回答"),
    ("user", "user_input", "模型说明（未经结构化事实核验）：这是我引用的文字", "模型说明（未经结构化事实核验）：这是我引用的文字"),
    ("assistant", "provider_admitted", "你提到的‘模型说明（未经结构化事实核验）：’是旧标签。", "你提到的‘模型说明（未经结构化事实核验）：’是旧标签。"),
    ("assistant", None, "模型说明（未经结构化事实核验）：来源不明", "模型说明（未经结构化事实核验）：来源不明"),
])
def test_legacy_prefix_projection_preserves_source_and_original(role, source, raw, expected):
    from copy import deepcopy

    stored = [{"role": role, "source": source, "content": raw}]
    original = deepcopy(stored)
    projected = _provider().project_public_messages(stored)
    assert projected[0]["content"] == expected
    assert stored == original
    if source is None:
        assert projected[0]["provenance_warning"] == "legacy_unclassified"
    else:
        assert projected[0]["source"] == source


def test_legacy_prefix_is_removed_from_api_transcript_and_next_turn_only(client, monkeypatch):
    sid = new_session(client)["id"]
    service = client.app.state.service
    state = service.load(sid)
    old_text = "模型说明（未经结构化事实核验）：先确认独立培养关系。"
    state["messages"].append({"id": "old-admitted", "role": "assistant", "content": old_text,
                              "created_at": "then", "source": "provider_admitted"})
    service.sessions.save(state)
    assert client.get(f"/api/sessions/{sid}").json()["messages"][-1]["content"] == "先确认独立培养关系。"
    transcript = client.get(f"/api/sessions/{sid}/transcript")
    assert "先确认独立培养关系。" in transcript.text
    assert "模型说明（未经结构化事实核验）：" not in transcript.text

    captured = []
    def answer(settings, messages, context):
        captured.extend(messages)
        return Action(action="reply", text="先按描述性结果解释。")
    monkeypatch.setattr("bridge.web.service.converse", answer)
    question = "模型说明（未经结构化事实核验）：这个标签是什么意思？"
    assert client.post(f"/api/sessions/{sid}/messages", json={"text": question}).status_code == 200
    public = settle(client, sid)
    assert {"role": "assistant", "content": "先确认独立培养关系。"} in captured
    assert captured[-1] == {"role": "user", "content": question}
    assert public["messages"][-1]["content"] == "先按描述性结果解释。"
    assert public["messages"][-1]["source"] == "provider_admitted"
    stored = service.load(sid)
    assert next(row for row in stored["messages"] if row["id"] == "old-admitted")["content"] == old_text


@pytest.mark.parametrize("sharing", [False, True])
def test_followup_receives_only_allowed_report_versions_when_sharing_enabled(client, monkeypatch, sharing):
    from dataclasses import replace
    service = client.app.state.service
    service.model_configuration.default = replace(service.model_configuration.default, share_result_summaries=sharing)
    sid = new_session(client)["id"]
    projected = [
        {"content_class": "research_report", "media_type": "text/html", "access_state": "current",
         "research_report": {"input_revision": "2", "graph_version": 3, "private": "/private/must-not-leak"},
         "name": "private-name.html", "url": "/private/must-not-leak"},
        {"content_class": "research_report", "media_type": "application/json", "access_state": "current",
         "research_report": {"input_revision": "2", "graph_version": 3}},
        {"content_class": "research_report", "media_type": "text/html", "access_state": "historical_unreviewed",
         "research_report": {"input_revision": "1", "graph_version": 1}},
        {"content_class": "research_report", "media_type": "text/html", "access_state": "denied",
         "research_report": {"input_revision": "99", "graph_version": 99}},
        {"content_class": "research_report", "media_type": "text/html", "access_state": "historical_unreviewed",
         "research_report": {"input_revision": "/private/must-not-leak", "graph_version": 1}},
    ]
    monkeypatch.setattr(service.artifacts, "public", lambda state: projected)
    captured = []
    def action(settings, messages, context):
        captured.append(context)
        return Action(action="reply", text="报告生成与科学验证资格分别判断。")
    monkeypatch.setattr("bridge.web.service.converse", action)
    client.post(f"/api/sessions/{sid}/messages", json={"text": "已有报告是哪一版？不要重新分析。"}).raise_for_status()
    state = settle(client, sid)
    assert state["status"] == "idle" and not state["error"]
    assert len(captured) == 1
    if not sharing:
        assert "report_context" not in captured[0]
        return
    expected = {"reports": [
        {"input_revision": "2", "graph_version": 3, "access_state": "current"},
        {"input_revision": "1", "graph_version": 1, "access_state": "historical_unreviewed"},
    ]}
    assert captured[0]["report_context"] == expected
    encoded = json.dumps(captured[0]["report_context"])
    assert "must-not-leak" not in encoded and "private-name" not in encoded
    saved = service.sessions.load(sid)
    record = list(saved["_result_contexts"].values())[-1]
    assert record["report_context"] == expected
