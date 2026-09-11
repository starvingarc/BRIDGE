"""One actual QC-to-candidate-to-evidence flow, without scientific promotion."""
from __future__ import annotations

from dataclasses import replace
import json

import pytest

from test_web_service import client
from test_cell_state_candidate_runtime import _rig
from test_web_assessment import (
    producer_scientific_case, approve_scope, settle_assessment, next_check_or_stop,
)


def test_candidate_runtime_is_bound_and_visible_as_research_evidence(client, tmp_path, monkeypatch):
    _, catalog, _ = _rig(tmp_path, monkeypatch)
    service, sid, aid = producer_scientific_case(client, tmp_path, monkeypatch, with_producers=False)
    service.settings = replace(service.settings,
        cell_state_measurement_spec_ref="CELLSTATE-scRNA-celltypist-candidate-v0.1",
        cell_state_candidate_runtime_ref="fixture-celltypist-v1")
    body = {"question": "Inspect candidate method outputs without asserting biological identity.",
        "upload_id": aid, "allowed_modes": [
            {"tool_id": "P0-01", "mode_id": None}, {"tool_id": "P0-02", "mode_id": None}],
        "max_tool_runs": 3, "max_model_turns": 4}
    response = client.post(f"/api/sessions/{sid}/assessment/propose", json=body)
    assert response.status_code == 200, response.json()
    scope = response.json()["assessment"]
    monkeypatch.setattr("bridge.web.provider.converse", next_check_or_stop)
    approve_scope(client, sid, scope)
    done = settle_assessment(client, sid, timeout=180)["assessment"]
    state = service.load(sid)
    assert [row["tool_id"] for row in state["_tool_runs"]] == ["P0-01", "P0-02"]
    candidate, = [row for row in done["evidence"] if row["tool_id"] == "P0-02"]
    assert candidate["state"] == "available", candidate
    assert candidate["summary"]["analysis_scope"] == "candidate_method_observation"
    assert candidate["summary"]["state_review_status"] == "not_established"
    assert candidate["summary"]["n_observations"] == 4
    assert sum(row["count"] for row in candidate["summary"]["composition"]) == 4
    assert candidate["summary"]["domain_score"] is None
    assert candidate["summary"]["n_independent_replicates"] is None
    receipt = state["_tool_runs"][-1]
    run = json.loads((service.directory(sid) / "receipts" / receipt["file"]).read_bytes())
    assert run["request"]["parameters"]["candidate_binding_sha256"] == (
        state["_assessment"]["scope"]["binding"]["science"]["cell-state-candidate-binding"])
    assert any(record["schema_ref"] == "bridge://schemas/cell-state-candidate-profile/v1.0"
        for record in state["_input_objects"].values())
    versions = done["interpretation_versions"]
    assert len(versions) >= 2
    for index, version in enumerate(versions):
        assert version["version"] == index + 1
        assert version["predecessor_sha256"] == (versions[index - 1]["content_sha256"] if index else None)
        assert version["qualification"] == "proposed_explanation"
        assert version["input_revision"] == scope["input_revision"]

    # Changed controlled model metadata cannot silently inherit the old scope.
    response = client.post(f"/api/sessions/{sid}/assessment/propose", json=body)
    assert response.status_code == 200, response.json()
    proposed = response.json()["assessment"]
    bindings = json.loads(catalog.read_text())
    bindings["fixture-celltypist-v1"]["model_manifest_sha256"] = "f" * 64
    catalog.write_text(json.dumps(bindings))
    response = client.post(f"/api/sessions/{sid}/assessment/approve",
        json={"scope_id": proposed["scope_id"], "scope_digest": proposed["scope_digest"]})
    assert response.status_code == 409

def _next_check_or_query(settings, messages, context):
    from bridge.web.provider import Action
    if not context["options"]:
        return Action.model_validate({"action": "assessment", "decision": {
            "action": "stop", "reason": "no_discriminating_check"}})
    option = context["options"][0]
    return Action.model_validate({"action": "assessment", "decision": {
        "action": "query" if option["mode_id"] == "case_query" else "check",
        "option_id": option["id"]}})


@pytest.mark.parametrize("with_feedback", [False, True])
def test_candidate_measurements_reach_the_canonical_graph_and_query(client, tmp_path, monkeypatch, with_feedback):
    _rig(tmp_path, monkeypatch)
    service, sid, aid = producer_scientific_case(client, tmp_path, monkeypatch, with_producers=False)
    service.settings = replace(service.settings,
        cell_state_measurement_spec_ref="CELLSTATE-scRNA-celltypist-candidate-v0.1",
        cell_state_candidate_runtime_ref="fixture-celltypist-v1")
    body = {"question": "Record native observations, then inspect their remaining validation gaps.",
        "upload_id": aid, "allowed_modes": [
            {"tool_id": "P0-01", "mode_id": None}, {"tool_id": "P0-02", "mode_id": None},
            {"tool_id": "P0-08", "mode_id": "default"}, {"tool_id": "P0-09", "mode_id": "case_initial_v2"},
            {"tool_id": "P0-09", "mode_id": "case_query"}],
        "max_tool_runs": 12 if with_feedback else 6, "max_model_turns": 14 if with_feedback else 7}
    if with_feedback:
        body["allowed_modes"].extend([
            {"tool_id": "P0-10", "mode_id": "default"},
            {"tool_id": "P0-06", "mode_id": "exploratory_process"},
            {"tool_id": "P0-09", "mode_id": "case_append_v2"}])
    response = client.post(f"/api/sessions/{sid}/assessment/propose", json=body)
    assert response.status_code == 200, response.json()
    monkeypatch.setattr("bridge.web.provider.converse", _next_check_or_query)
    approve_scope(client, sid, response.json()["assessment"])
    done = settle_assessment(client, sid, timeout=360)["assessment"]
    state = service.load(sid)
    expected = ["P0-01", "P0-02", "P0-08", "P0-09", "P0-09"]
    if with_feedback:
        expected += ["P0-10", "P0-06", "P0-08", "P0-09", "P0-09", "P0-10"]
    assert [row["tool_id"] for row in state["_tool_runs"]] == expected, done
    assert all(row["state"] in {"succeeded", "partial"} for row in state["_tool_runs"])
    records = [service.inputs.verify(state, row) for row in state["_input_objects"].values()
               if row["schema_ref"] == "bridge://schemas/evidence-record-set/v0.1"]
    assert len(records) == (2 if with_feedback else 1) and len(records[0]["records"]) >= 2
    assert all(row["evidence_tier"] == "exploratory" for row in records[0]["records"])
    assert all(row["denominator"] == 4 for row in records[0]["records"])
    assert all(row["score_contract_ref"] is None for row in records[0]["records"])
    assert len({row["evidence_family_ref"]["object_id"] for row in records[0]["records"]}) == 1
    candidate, = [row for row in done["evidence"] if row["tool_id"] == "P0-02"]
    assert candidate["state"] == "available", candidate
    graph_evidence = [row for row in done["evidence"] if row["tool_id"] == "P0-09"]
    assert len(graph_evidence) == (4 if with_feedback else 2)
    assert all(row["state"] == "available" for row in graph_evidence), graph_evidence
    if with_feedback:
        assert graph_evidence[-1]["summary"]["display_omitted_edges"] > 0
        assert len(graph_evidence[-1]["summary"]["records"]) == len(records[1]["records"])
        assert records[1]["graph_id"] == records[0]["graph_id"]
        assert records[1]["graph_version"] == 2
        old = {row["evidence_id"]: row for row in records[0]["records"]}
        assert all(row == old[row["evidence_id"]] for row in records[1]["records"] if row["evidence_id"] in old)
        assert len(records[1]["records"]) == len(records[0]["records"]) + 5
        assert len({row["evidence_family_ref"]["object_id"] for row in records[1]["records"]}) == 1
        from hashlib import sha256
        from bridge.tool_packages.p0_10_claim_verifier.research import ResearchAnalysisSnapshot
        reports = [row for row in state["artifacts"] if row.get("research_report")]
        assert len(reports) == 8
        assert {row["research_report"]["graph_version"] for row in reports} == {1, 2}
        snapshots = []
        for artifact in reports:
            response = client.get(artifact["url"])
            assert response.status_code == 200
            assert response.headers["content-disposition"].startswith("attachment") or artifact["name"].endswith(".svg")
            original = state["_canonical_artifacts"][artifact["id"]]
            assert sha256(response.content).hexdigest() == original["sha256"]
            if artifact["name"].endswith(".json"):
                snapshot = ResearchAnalysisSnapshot.model_validate_json(response.content)
                assert snapshot.snapshot_sha256 == artifact["research_report"]["snapshot_sha256"]
                snapshots.append(snapshot)
        assert len(snapshots) == 2 and snapshots[0].snapshot_sha256 != snapshots[1].snapshot_sha256

        # A display-only correction reuses biological evidence, but creates a new report.
        from test_web_intake import stage
        from test_web_service import confirm_change
        facts = service.intake.current_facts(state, aid, include_draft=False).model_dump(mode="json")
        facts["product_name"] = "Corrected research product"
        pending = stage(client, sid, aid, facts)
        impact = pending["pending_input_change"]["impact"]
        assert {row["tool_id"] for row in impact["affected"]} == {"P0-10"}
        assert {"P0-01", "P0-02", "P0-06", "P0-09"} <= {row["tool_id"] for row in impact["reusable"]}
        confirm_change(client, sid, pending)
        before_runs = list(state["_tool_runs"])
        response = client.post(f"/api/sessions/{sid}/assessment/propose", json={
            **body, "allowed_modes": [{"tool_id": "P0-10", "mode_id": "default"}],
            "max_tool_runs": 1, "max_model_turns": 2})
        assert response.status_code == 200, response.json()
        approve_scope(client, sid, response.json()["assessment"])
        settle_assessment(client, sid, timeout=180)
        revised = service.load(sid)
        assert revised["_tool_runs"][:-1] == before_runs
        assert revised["_tool_runs"][-1]["tool_id"] == "P0-10"
        assert revised["_tool_runs"][-1]["state"] == "succeeded"
        new_reports = [row for row in revised["artifacts"] if row.get("research_report")]
        assert len(new_reports) == 12
        for artifact in reports:
            response = client.get(artifact["url"])
            assert response.status_code == 200
            assert sha256(response.content).hexdigest() == state["_canonical_artifacts"][artifact["id"]]["sha256"]
        newest = next(row for row in reversed(new_reports) if row["name"].endswith(".json"))
        snapshot = ResearchAnalysisSnapshot.model_validate_json(client.get(newest["url"]).content)
        assert snapshot.graph_version == 2
        assert snapshot.snapshot_sha256 not in {item.snapshot_sha256 for item in snapshots}
