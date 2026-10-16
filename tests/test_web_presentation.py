from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from bridge.web.app import Settings
from account_support import create_test_app as create_app, LOGIN




def _presentation():
    try:
        return importlib.import_module("bridge.web.presentation")
    except ModuleNotFoundError:
        pytest.fail("bridge.web.presentation is required")


def _state(**updates):
    value = {
        "id": "a" * 32,
        "title": "Question",
        "updated_at": "2026-09-21T00:00:00+00:00",
        "status": "idle",
        "messages": [],
        "uploads": [{"id": "b" * 32}],
        "plan": None,
        "artifacts": [],
        "error": None,
        "plan_history": [],
        "capabilities": [],
        "input_review_required": False,
        "pending_input_change": None,
        "_assessment": None,
        "_tool_runs": [],
        "_control_epoch": 0,
        "_input_revision": 1,
    }
    value.update(updates)
    return value


def _service(*, environment="production", diagnostics=False, resumable=False):
    return SimpleNamespace(
        settings=SimpleNamespace(
            runtime_environment=environment,
            diagnostics_enabled=diagnostics,
        ),
        assessment=SimpleNamespace(
            resume_eligibility=lambda state: (
                resumable,
                None if resumable else "assessment_not_resumable",
            ),
        ),
    )


def _settings(
    root: Path,
    *,
    environment: str = "production",
    diagnostics: bool = False,
) -> Settings:
    return Settings(
        storage_root=root,
        model_base_url="http://provider.invalid/v1",
        model="test-model",
        model_api_key="test-key",
        origin="http://testserver",
        runtime_environment=environment,
        diagnostics_enabled=diagnostics,
    )


def _login(client: TestClient) -> None:
    response = client.post(
        "/api/login",
        json=LOGIN,
        headers={"Origin": "http://testserver"},
    )
    assert response.status_code == 200
    client.headers["Origin"] = "http://testserver"


def test_working_stage_and_stop_take_precedence_over_pending_input() -> None:
    presentation = _presentation()
    state = _state(
        status="running",
        input_review_required=True,
        pending_input_change={"id": "change"},
        plan={"id": "plan", "digest": "d" * 64, "status": "proposed", "steps": []},
    )

    result = presentation.build_session_presentation(_service(), state)

    assert result.stage == "working"
    assert [item.id for item in result.next_actions] == ["stop"]


def test_assessment_approval_is_distinct_from_plan_approval() -> None:
    presentation = _presentation()
    assessment = {
        "status": "proposed",
        "authorization": None,
        "scope": {"scope_id": "scope"},
    }
    state = _state(
        status="awaiting_approval",
        _assessment=assessment,
        plan={"id": "plan", "digest": "d" * 64, "status": "proposed", "steps": []},
    )

    result = presentation.build_session_presentation(_service(), state)

    assert result.stage == "needs_approval"
    assert [item.id for item in result.next_actions] == ["approve_assessment"]


def test_report_failure_derives_result_preservation_from_actual_artifacts() -> None:
    presentation = _presentation()
    no_result = _state(status="failed", error="report_handoff_stale")
    with_result = _state(
        status="failed",
        error="report_handoff_stale",
        artifacts=[{"id": "c" * 32, "kind": "evidence"}],
    )

    absent = presentation.build_session_presentation(_service(), no_result)
    preserved = presentation.build_session_presentation(_service(), with_result)

    assert absent.issue.results_state == "not_available"
    assert "保留" not in absent.issue.user_message
    assert preserved.issue.results_state == "preserved"
    assert "仍保留" in preserved.issue.user_message
    assert [item.id for item in preserved.next_actions] == ["view_results"]

    admitted = _state(
        status="idle",
        _assessment={
            "status": "stopped",
            "stop_reason": "no_discriminating_check",
            "hypotheses": [],
            "admissions": [{"state": "completed"}],
        },
    )
    assert presentation.derive_results_state(admitted) == "preserved"


def test_results_ready_offers_resume_only_when_current_assessment_is_eligible() -> None:
    presentation = _presentation()
    state = _state(
        _assessment={
            "status": "stopped",
            "stop_reason": "explanation_complete",
            "authorization": {"scope_id": "scope"},
        },
        artifacts=[{
            "id": "c" * 32,
            "content_class": "research_report",
            "access_state": "current",
        }],
    )

    eligible = presentation.build_session_presentation(
        _service(resumable=True), state,
    )
    ineligible = presentation.build_session_presentation(
        _service(resumable=False), state,
    )

    assert eligible.stage == "results_ready"
    assert [item.id for item in eligible.next_actions] == [
        "view_results", "download_report", "resume_assessment",
    ]
    assert ineligible.stage == "results_ready"
    assert [item.id for item in ineligible.next_actions] == [
        "view_results", "download_report",
    ]


def test_idle_error_is_blocked_instead_of_presented_as_ready() -> None:
    presentation = _presentation()

    result = presentation.build_session_presentation(
        _service(),
        _state(status="idle", error="no_graft_declaration_required"),
    )

    assert result.stage == "blocked"
    assert result.issue.error_id == "request_failed"


def test_unknown_internal_error_is_not_exposed() -> None:
    presentation = _presentation()
    internal = "provider_private_failure_123"

    result = presentation.build_session_presentation(
        _service(), _state(status="failed", error=internal),
    )
    encoded = result.model_dump_json()

    assert result.issue.error_id == "request_failed"
    assert internal not in encoded


def test_user_assessment_projection_keeps_bindings_and_removes_diagnostics() -> None:
    presentation = _presentation()
    raw = {
        "scope_id": "scope",
        "scope_digest": "d" * 64,
        "question": "What changed?",
        "upload_id": "u" * 32,
        "input_revision": 3,
        "allowed_modes": [{"tool_id": "P0-02", "mode_id": "default"}],
        "report_after_explanation": True,
        "max_tool_runs": 4,
        "max_model_turns": 5,
        "status": "stopped",
        "tool_runs_used": 2,
        "model_turns_used": 3,
        "stop_reason": "explanation_complete",
        "stop_events": [{"reason": "explanation_complete"}],
        "blockers": [],
        "evidence": [{"alias": "E-1", "state": "available"}],
        "candidates": [],
        "freshness": {
            "state": "current",
            "reason_code": None,
            "current_input_revision": 3,
            "scope_input_revision": 3,
            "pending_review": None,
        },
        "portrait": {"state": "partial"},
        "result_summaries_enabled": True,
        "history": [{
            "scope_id": "old",
            "question": "Earlier?",
            "input_revision": 2,
            "status": "stopped",
            "stop_reason": "private_reason",
            "stop_events": [{"reason": "private_reason"}],
        }],
        "hypotheses": [{"statement": "Candidate"}],
        "interpretation_versions": [{"content_sha256": "f" * 64}],
        "data_view": {"state": "available"},
        "resources": [{"alias": "R-1"}],
        "stop_conditions": ["finite_budgets"],
        "question_sent_to_model": True,
        "scope_authorized": True,
        "scope_grants_scientific_approval": False,
    }

    public = presentation.project_user_assessment(raw)

    assert public["scope_id"] == "scope"
    assert public["scope_digest"] == "d" * 64
    assert public["max_tool_runs"] == 4
    assert public["history"] == [{
        "scope_id": "old",
        "question": "Earlier?",
        "input_revision": 2,
        "status": "stopped",
    }]
    assert "reason_code" not in public["freshness"]
    assert {
        "tool_runs_used", "model_turns_used", "stop_reason", "stop_events",
        "interpretation_versions", "result_summaries_enabled",
        "question_sent_to_model", "stop_conditions",
    }.isdisjoint(public)


def test_hypothesis_provenance_requires_an_exact_version_binding() -> None:
    presentation = _presentation()
    hypothesis = {
        "statement": "Candidate interpretation",
        "evidence_aliases": ["E-one#measurement:1@1"],
        "opposing_evidence_aliases": ["E-two#record:2@1"],
        "missing_evidence_aliases": [],
        "expected_observation": None,
        "competing_explanation": "Alternative",
        "discriminating_check": None,
    }
    version = {
        "object_version": "1.0.0",
        "scope_digest": "d" * 64,
        "input_revision": 2,
        "hypotheses": [hypothesis],
        "evidence_snapshot_sha256": "e" * 64,
        "qualification": "proposed_explanation",
        "version": 3,
        "content_sha256": "54b05756a7706bb312e57961e64839023d06cd84db1922cffd0d1ec60505b89d",
    }
    raw = {
        "scope_digest": "d" * 64,
        "input_revision": 2,
        "hypotheses": [hypothesis],
        "interpretation_versions": [version],
    }

    bound = presentation.project_user_assessment(raw)
    assert bound["hypotheses"] == [{**hypothesis,
        "qualification": "proposed_explanation",
        "interpretation_ref": {
            "scope_digest": "d" * 64,
            "version": 3,
            "content_sha256": version["content_sha256"],
        }}]
    assert "interpretation_versions" not in bound

    for unbound in (
        {**raw, "interpretation_versions": []},
        {**raw, "scope_digest": "f" * 64},
        {**raw, "hypotheses": [{**hypothesis, "evidence_aliases": ["E-other"]}]},
        {**raw, "interpretation_versions": [{**version, "content_sha256": "0" * 64}]},
    ):
        projected = presentation.project_user_assessment(unbound)
        assert projected["hypotheses"] == [{**unbound["hypotheses"][0],
            "provenance_warning": "legacy_unclassified"}]


def test_safe_http_error_envelope_replaces_internal_detail(tmp_path: Path) -> None:
    client = TestClient(create_app(_settings(tmp_path / "state")))
    _login(client)

    response = client.get("/api/sessions/not-a-session-id")

    assert response.status_code == 404
    assert response.json() == {
        "error_version": 1,
        "error_id": "request_failed",
        "user_message": "没有找到请求的内容。",
        "results_state": "unknown",
        "details": [],
    }
    assert "detail" not in response.json()


def test_diagnostics_are_authenticated_development_only_and_redacted(
    tmp_path: Path,
) -> None:
    enabled = TestClient(create_app(_settings(
        tmp_path / "enabled", environment="development", diagnostics=True,
    )))
    assert enabled.get("/api/sessions/" + "a" * 32 + "/diagnostics").status_code == 401
    _login(enabled)
    created = enabled.post("/api/sessions").json()
    sid = created["id"]
    service = enabled.app.state.service
    state = service.load(sid)
    state["error"] = "private_provider_error"
    state["_control_epoch"] = 7
    state["_assessment"] = {
        "scope": {
            "scope_id": "scope-id",
            "max_tool_runs": 4,
            "max_model_turns": 5,
        },
        "status": "blocked",
        "stop_reason": "private_stop_reason",
        "tool_runs_used": 2,
        "model_turns_used": 3,
        "model_turns": [{
            "number": 3,
            "state": "rejected",
            "provider_error_code": "invalid_alias",
            "decision": {"text": "must-not-leak"},
        }],
    }
    state["_tool_runs"] = [{
        "tool_id": "P0-02",
        "state": "succeeded",
        "plan_id": "plan-id",
        "file": "/private/receipt.json",
        "sha256": "e" * 64,
    }]
    state["messages"].append({
        "id": "m",
        "role": "user",
        "content": "secret message",
        "created_at": "now",
    })
    service.sessions.save(state)

    response = enabled.get(f"/api/sessions/{sid}/diagnostics")
    encoded = json.dumps(response.json(), ensure_ascii=False)

    assert response.status_code == 200
    assert response.json()["runtime"]["environment"] == "development"
    assert response.json()["session"]["internal_error_code"] == "private_provider_error"
    assert response.json()["assessment"]["model_turns"] == [{
        "number": 3,
        "state": "rejected",
        "provider_error_code": "invalid_alias",
    }]
    assert "must-not-leak" not in encoded
    assert "secret message" not in encoded
    assert "/private/" not in encoded
    assert "receipt.json" not in encoded
    assert "eeeeeeee" not in encoded

    disabled = TestClient(create_app(_settings(
        tmp_path / "disabled", environment="development", diagnostics=False,
    )))
    _login(disabled)
    disabled_sid = disabled.post("/api/sessions").json()["id"]
    for suffix in ("", "?diagnostics=1"):
        refused = disabled.get(
            f"/api/sessions/{disabled_sid}/diagnostics{suffix}",
            headers={"X-BRIDGE-DIAGNOSTICS": "1"},
        )
        assert refused.status_code == 404
        assert refused.json()["error_id"] == "request_failed"


def test_acceptance_and_production_have_identical_user_projection() -> None:
    presentation = _presentation()
    state = _state(status="idle")

    acceptance = presentation.build_session_presentation(
        _service(environment="acceptance"), state,
    )
    production = presentation.build_session_presentation(
        _service(environment="production"), state,
    )

    assert acceptance == production
    assert acceptance.diagnostics_available is False


def test_resume_eligibility_is_pure_and_keeps_direct_report_exception() -> None:
    from bridge.web.assessment import AssessmentCoordinator

    coordinator = AssessmentCoordinator(SimpleNamespace())
    coordinator.check = lambda state: None
    state = {
        "status": "idle",
        "input_review_required": False,
        "_assessment": {
            "status": "stopped",
            "authorization": {"scope_id": "scope"},
            "stop_reason": "explanation_complete",
            "scope": {
                "report_after_explanation": True,
                "max_tool_runs": 2,
                "max_model_turns": 1,
            },
            "admissions": [],
            "tool_runs_used": 0,
            "model_turns_used": 1,
        },
    }
    before = json.loads(json.dumps(state))

    assert coordinator.resume_eligibility(state) == (True, None)
    assert state == before

    state["_assessment"]["admissions"].append({"tool_id": "P0-10"})
    assert coordinator.resume_eligibility(state) == (
        False,
        "assessment_report_already_admitted",
    )

@pytest.mark.parametrize("results", ["preserved", "not_available", "unknown"])
@pytest.mark.parametrize("code, phrase", [
    ("interpretation_graph_binding_unavailable", "解释与证据图的对应关系未能核实"),
    ("report_context_producer_identity_mismatch", "测量来源与证据图不一致"),
    ("graph_display_unavailable", "解释图叠加层当前不可用"),
])
def test_degradation_issues_preserve_result_state_without_generic_message(code, phrase, results):
    issue = _presentation().public_error(code, results_state=results)
    assert phrase in issue.user_message
    assert issue.results_state == results
    assert code not in issue.user_message


def test_missing_producer_blocker_is_visible_but_historical_counts_are_not_active_errors():
    state = _state(artifacts=[{"id": "result"}], _assessment={
        "status": "blocked", "stop_reason": "report_candidate_unavailable",
        "blockers": [{"tool_id": "P0-10", "reason_codes": ["report_context_producer_identity_mismatch"]}]})
    shown = _presentation().build_session_presentation(_service(), state)
    assert "测量来源与证据图不一致" in shown.issue.user_message
    assert shown.issue.results_state == "preserved"
    state["_assessment"] = None
    state["_degradation_counts"] = {"report_context_producer_identity_mismatch": 1}
    assert _presentation().build_session_presentation(_service(), state).issue is None


def test_diagnostic_counts_are_closed_and_persisted_without_source_details(tmp_path):
    from bridge.web.runtime import record_degradation
    client = TestClient(create_app(_settings(tmp_path / "counts", environment="development", diagnostics=True)))
    _login(client)
    sid = client.post("/api/sessions").json()["id"]
    service = client.app.state.service
    state = service.load(sid)
    for _ in range(2):
        record_degradation(state, "graph_display_unavailable")
    record_degradation(state, "PRIVATE/path/receipt")
    state["_degradation_counts"].update({"PRIVATE/path/receipt": 4,
        "report_context_producer_identity_mismatch": {"private_hash": "secret"},
        "interpretation_graph_binding_unavailable": True})
    service.sessions.save(state)
    payload = client.get(f"/api/sessions/{sid}/diagnostics").json()
    assert payload["degradations"] == [{"code": "graph_display_unavailable", "count": 2}]
    assert "PRIVATE" not in json.dumps(payload) and "secret" not in json.dumps(payload)

def test_failed_graph_preview_is_counted_and_safe_while_recovery_does_not_increment(tmp_path, monkeypatch):
    from bridge.web import research_context
    client = TestClient(create_app(_settings(tmp_path / "preview", environment="development", diagnostics=True)))
    _login(client)
    sid = client.post("/api/sessions").json()["id"]
    service = client.app.state.service
    monkeypatch.setattr(service.artifacts, "read", lambda *args, **kwargs: (
        {"tool_id": "P0-09", "media_type": "application/json", "name": "cytoscape_elements.json"}, b"{}"))
    def reject(*args):
        raise ValueError("PRIVATE/path/receipt: " + "f" * 64)
    monkeypatch.setattr(research_context, "graph_composition_display", reject)
    for expected in (1, 2):
        response = client.get(f"/api/sessions/{sid}/artifacts/graph/preview")
        assert response.status_code == 422
        assert "解释图叠加层当前不可用" in response.json()["user_message"]
        assert "PRIVATE" not in response.text and "ffffffff" not in response.text
        assert client.get(f"/api/sessions/{sid}/diagnostics").json()["degradations"] == [
            {"code": "graph_display_unavailable", "count": expected}]
    monkeypatch.setattr(research_context, "graph_composition_display", lambda *args: {"valid": True})
    assert client.get(f"/api/sessions/{sid}/artifacts/graph/preview").json() == {"valid": True}
    assert client.get(f"/api/sessions/{sid}/diagnostics").json()["degradations"] == [
        {"code": "graph_display_unavailable", "count": 2}]


def test_interpretation_findings_explain_fields_and_repairs_without_private_prose():
    state = _state(_assessment={
        'status': 'blocked', 'stop_reason': 'provider_action_invalid_or_unavailable',
        'model_turns': [{'phase': 'interpretation_review', 'provider_error_detail': {
            'category': 'interpretation_review', 'issues': [
                {'hypothesis_index': 1, 'field': 'statement', 'code': 'numerical_restatement',
                 'quote': 'private draft', 'reason': 'private model reason'},
                {'hypothesis_index': 1, 'field': 'evidence_relations', 'code': 'unsupported_observation'},
                {'hypothesis_index': 999, 'field': 'private field', 'code': 'unknown'},
            ]}}],
    })
    result = _presentation().build_session_presentation(_service(resumable=True), state)
    assert '需要修改' in result.issue.user_message
    assert len(result.issue.details) == 2
    assert '解释 2 · 主要解释' in result.issue.details[0]
    assert '生物学含义' in result.issue.details[0]
    assert '证据关系' in result.issue.details[1]
    assert '删除' in result.issue.details[1]
    assert 'private' not in result.model_dump_json()
    assert result.next_actions[-1].label == '按意见修订并重新核查'


@pytest.mark.parametrize('category, expected', [
    ('action_protocol', '格式'), ('transport_timeout', '超时'),
    ('http_status', '模型服务'), ('action_schema', '字段'),
])
def test_review_unavailable_has_specific_retry_guidance(category, expected):
    state = _state(_assessment={
        'status': 'blocked', 'stop_reason': 'provider_action_invalid_or_unavailable',
        'model_turns': [{'phase': 'interpretation_review', 'review_outcome': 'unavailable',
            'provider_error_detail': {'category': category}}],
    })
    result = _presentation().build_session_presentation(_service(resumable=True), state)
    assert expected in result.issue.user_message
    assert '核查未完成' in result.issue.user_message
    assert result.next_actions[-1].label == '重新核查已有解释'


@pytest.mark.parametrize('status, reason', [
    ('running', None), ('stopped', 'explanation_complete'),
    ('blocked', 'scope_resource_changed'),
])
def test_old_review_findings_do_not_survive_a_new_assessment_state(status, reason):
    state = _state(status='running' if status == 'running' else 'idle', _assessment={
        'status': status, 'stop_reason': reason,
        'model_turns': [{'phase': 'interpretation_review', 'provider_error_detail': {
            'category': 'interpretation_review', 'issues': [
                {'hypothesis_index': 0, 'field': 'statement', 'code': 'numerical_restatement'}]}}],
    })
    result = _presentation().build_session_presentation(_service(), state)
    assert result.issue is None or not result.issue.details
