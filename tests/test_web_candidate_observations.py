"""One actual QC-to-candidate-to-evidence flow, without scientific promotion."""
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import pytest

from web_support import client
from test_cell_state_candidate_runtime import _rig
from test_web_assessment import (
    producer_scientific_case, approve_scope, settle_assessment, next_check_or_stop,
)


@pytest.mark.parametrize("identity", [None, ""])
def test_native_missing_sample_identity_is_a_structured_gap_not_a_server_error(monkeypatch, identity):
    from copy import deepcopy
    from types import SimpleNamespace
    from bridge.web import native_evidence
    profile = {"input_data_view": {"sample_or_preparation_ref": identity,
                                   "parent_asset_sha256": "a" * 64}}
    original = deepcopy(profile)
    # The already-verified producer is isolated; no measurement is run here.
    run = SimpleNamespace(request=SimpleNamespace(assets=[SimpleNamespace(assay="scRNA-seq")]))
    monkeypatch.setattr(native_evidence, "_source", lambda *args: (run, "profile", profile, [], "spec", {}))
    reports = SimpleNamespace(service=SimpleNamespace(inputs=SimpleNamespace(assessment_pool=lambda *args: {})),
                              _canonical_outputs=lambda *args: [])
    scope = SimpleNamespace(binding={"intake": {"facts": {}}})
    state = {}
    with pytest.raises(ValueError, match="^native_sample_identity_required$"):
        native_evidence.selection(reports, state, scope, SimpleNamespace(tool_id="P0-08"))
    assert profile == original and state == {}


def test_native_missing_sample_identity_message_preserves_unknowns():
    from bridge.web.presentation import public_error
    issue = public_error("native_sample_identity_required", results_state="preserved")
    assert issue.error_id == "input_required"
    assert "样本标识列" in issue.user_message
    assert "独立重复" in issue.user_message
    assert "未知" in issue.user_message


def test_new_graph_scope_reuses_explicitly_approved_native_sufficiency(client, tmp_path, monkeypatch):
    from bridge.web.assessment import AssessmentScope
    from test_web_inputs import approve

    _rig(tmp_path, monkeypatch)
    service, sid, aid = producer_scientific_case(
        client, tmp_path, monkeypatch, with_producers=False, with_lineage=False)
    service.settings = replace(service.settings,
        cell_state_measurement_spec_ref="CELLSTATE-scRNA-celltypist-candidate-v0.1",
        cell_state_candidate_runtime_ref="fixture-celltypist-v1")
    url = f"/api/sessions/{sid}"
    for tool_id in ("P0-01", "P0-02"):
        proposal = client.post(url + "/prepare-analysis", json={"tool_id": tool_id})
        assert proposal.status_code == 200, proposal.json()
        assert approve(client, sid, proposal.json()["plan"])["plan"]["status"] == "completed"

    response = client.post(url + "/assessment/propose", json={
        "question": "Check native evidence sufficiency.", "upload_id": aid,
        "allowed_modes": [{"tool_id": "P0-08", "mode_id": "default"}],
        "max_tool_runs": 1, "max_model_turns": 1})
    assert response.status_code == 200, response.json()
    state = service.load(sid)
    scope = AssessmentScope.model_validate(state["_assessment"]["scope"])
    candidate, = service.inputs.assessment_candidates(state, scope)
    assert candidate["request"] is not None and not candidate["blockers"]
    service.sessions.save(state)
    selection = {"tool_id": "P0-08", "mode_id": "default", "asset_ids": [],
        "measurement_spec_ref": None,
        "object_inputs": [{"role": ref.role, "input_id": ref.input_id}
                          for ref in candidate["request"].object_inputs]}
    chosen = client.post(url + "/analysis-inputs", json=selection)
    assert chosen.status_code == 200, chosen.json()
    proposal = client.post(url + "/prepare-analysis", json={"tool_id": "P0-08"})
    assert proposal.status_code == 200, proposal.json()
    assert approve(client, sid, proposal.json()["plan"])["plan"]["status"] == "completed"
    state = service.load(sid)
    receipt = state["_tool_runs"][-1]
    assert receipt["tool_id"] == "P0-08" and receipt["state"] == "succeeded"
    result_id = next(identifier for identifier, record in state["_input_objects"].items()
        if record.get("receipt_file") == receipt["file"]
        and record["schema_ref"].startswith("bridge://schemas/evidence-sufficiency-run-result/"))

    response = client.post(url + "/assessment/propose", json={
        "question": "Compile the matching native evidence graph.", "upload_id": aid,
        "allowed_modes": [{"tool_id": "P0-09", "mode_id": "case_initial_v2"}],
        "max_tool_runs": 1, "max_model_turns": 1})
    assert response.status_code == 200, response.json()
    state = service.load(sid)
    assert result_id in state["_assessment"]["scope"]["binding"]["resources"]
    assert response.json()["assessment"]["candidates"][0]["runnable"] is True


def test_pending_native_source_is_a_new_approved_selection_not_a_correction(client, tmp_path, monkeypatch):
    from bridge.web.assessment import AssessmentScope
    from bridge.web.inputs import Selection
    from web_support import confirm_change
    from test_web_inputs import approve

    _rig(tmp_path, monkeypatch)
    service, sid, aid = producer_scientific_case(
        client, tmp_path, monkeypatch, with_producers=False, with_lineage=False)
    service.settings = replace(service.settings,
        cell_state_measurement_spec_ref="CELLSTATE-scRNA-celltypist-candidate-v0.1",
        cell_state_candidate_runtime_ref="fixture-celltypist-v1")
    url = f"/api/sessions/{sid}"
    for tool_id in ("P0-01", "P0-02"):
        plan = client.post(url + "/prepare-analysis", json={"tool_id": tool_id}).json()["plan"]
        assert approve(client, sid, plan)["plan"]["status"] == "completed"

    for tool_id, mode_id in (("P0-08", "default"), ("P0-09", "case_initial_v2")):
        response = client.post(url + "/assessment/propose", json={
            "question": "Record the first native source.", "upload_id": aid,
            "allowed_modes": [{"tool_id": tool_id, "mode_id": mode_id}],
            "max_tool_runs": 1, "max_model_turns": 1})
        assert response.status_code == 200, response.json()
        state = service.load(sid)
        scope = AssessmentScope.model_validate(state["_assessment"]["scope"])
        candidate, = service.inputs.assessment_candidates(state, scope)
        assert candidate["request"] is not None and not candidate["blockers"]
        service.sessions.save(state)
        selection = {"tool_id": tool_id, "mode_id": mode_id, "asset_ids": [],
            "measurement_spec_ref": None,
            "object_inputs": [{"role": ref.role, "input_id": ref.input_id}
                              for ref in candidate["request"].object_inputs]}
        assert client.post(url + "/analysis-inputs", json=selection).status_code == 200
        plan = client.post(url + "/prepare-analysis", json={"tool_id": tool_id}).json()["plan"]
        assert approve(client, sid, plan)["plan"]["status"] == "completed"

    state = service.load(sid)
    old = state["_input_selections"]["P0-08"]
    old_receipts = {row["file"] for row in state["_tool_runs"]}
    source_id = next(row["input_id"] for row in old["object_inputs"]
                     if row["role"] == "domain_gate_input")
    source = state["_input_objects"][source_id]
    payload = service.inputs.verify(state, source)
    payload["domain_gate_input_id"] = "domain-gate-input:fixture-next-source"
    next_id = service.inputs.add_derived_object(state, tool_id="P0-08", mode_id="default",
        role="domain_gate_input", schema_ref=source["schema_ref"], payload=payload,
        dependencies=[source_id])
    after = {**old, "object_inputs": [
        {**row, "input_id": next_id} if row["input_id"] == source_id else row
        for row in old["object_inputs"]]}
    service.sessions.save(state)
    monkeypatch.setattr("bridge.web.native_evidence.selection",
        lambda reports, state, scope, allowed: Selection.model_validate(after))

    response = client.post(url + "/assessment/propose", json={
        "question": "Append a different native source.", "upload_id": aid,
        "allowed_modes": [{"tool_id": "P0-08", "mode_id": "default"}],
        "max_tool_runs": 1, "max_model_turns": 1})
    assert response.status_code == 200, response.json()
    state = service.load(sid)
    assert state["_input_selections"]["P0-08"] == old
    assert state["_assessment"]["scope"]["binding"]["append_p008"]["selection"] == after
    assert response.json()["assessment"]["candidates"][0]["runnable"] is True
    changed = client.post(url + "/analysis-inputs", json=after)
    assert changed.status_code == 200, changed.json()
    assert changed.json()["pending_input_change"]["impact"]["affected"] == []
    confirm_change(client, sid, changed.json())
    state = service.load(sid)
    assert state["_input_selections"]["P0-08"] == after
    assert not old_receipts.intersection(state["_invalidated_receipts"])
    proposal = client.post(url + "/prepare-analysis", json={"tool_id": "P0-08"})
    assert proposal.status_code == 200, proposal.json()
    assert proposal.json()["plan"]["status"] == "proposed"


@pytest.mark.parametrize("evidence_state,reason", [
    ("unknown", "required_channel_not_provided"),
    ("alert", "required_channel_not_provided"),
    ("unavailable", "measurement_unavailable"),
    ("measured", "required_channel_not_provided"),
])
def test_native_domain_coverage_keeps_tool_states_and_deduplicates_gap_revisions(evidence_state, reason):
    from types import SimpleNamespace
    from bridge.tool_packages.p0_09_evidence_compiler.models import VersionedObjectRef
    from bridge.web.native_evidence import _domain_coverage, _coverage_changed
    case = SimpleNamespace(ref=VersionedObjectRef(object_id="product-case:test", object_version="0.1.0"))
    definition = SimpleNamespace(ref=VersionedObjectRef(object_id="product-definition:test", object_version="0.1.0"))
    measurement = {"raw_value": 0 if evidence_state == "measured" else None, "evidence_state": evidence_state}
    source = (None, "profile", {}, [("measurement", measurement)], "spec", {})
    claims, observations = _domain_coverage(case, definition,
        [(source, "target_identity", "METHOD-TEST")], "2026-09-22T00:00:00Z")
    target = next(row for row in observations if row["claim_ref"]["object_id"].endswith(":target_identity"))
    assert target["reason_code"] == reason
    assert len(claims) == len(observations) == 5
    assert sum(row["reason_code"] == "measurement_not_provided" for row in observations) == 4
    assert measurement["evidence_state"] == evidence_state
    assert _coverage_changed(observations, [])
    history = [{"claim_ref": row["claim_ref"], "requirement_key": row["requirement_key"],
                "reason_codes": [row["reason_code"]], "requirement_version": 2} for row in observations]
    assert not _coverage_changed(observations, history)
    old_target = {**next(row for row in history if row["claim_ref"] == target["claim_ref"]),
                  "requirement_version": 1, "reason_codes": ["measurement_not_provided"]}
    assert _coverage_changed(observations, [old_target])
    assert not _coverage_changed(observations, [*history, old_target])


def test_candidate_runtime_is_bound_and_visible_as_research_evidence(client, tmp_path, monkeypatch):
    _, catalog, _ = _rig(tmp_path, monkeypatch)
    service, sid, aid = producer_scientific_case(client, tmp_path, monkeypatch, with_producers=False, with_lineage=False)
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
    assert "interpretation_versions" not in done
    versions = state["_assessment"].get("interpretation_versions", [])
    assert versions == []  # Check/query turns do not manufacture explanation versions.

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


def _candidate_citation(evidence):
    from bridge.web.provider import _citation_choices
    for row in reversed(evidence):
        # Candidate measurements are observations; unqualified graph containers are not support.
        if row["tool_id"] == "P0-02" and row["state"] == "available":
            choices = _citation_choices([row])["evidence_aliases"]
            if choices:
                return choices[0]
    raise AssertionError("A candidate measurement citation is required for the explanation.")


def test_early_explanation_resumes_graph_then_requires_current_explanation_for_report(
        client, tmp_path, monkeypatch):
    from bridge.web.provider import Action, _citation_choices
    _rig(tmp_path, monkeypatch)
    service, sid, aid = producer_scientific_case(
        client, tmp_path, monkeypatch, with_producers=False, with_lineage=False)
    service.settings = replace(service.settings,
        cell_state_measurement_spec_ref="CELLSTATE-scRNA-celltypist-candidate-v0.1",
        cell_state_candidate_runtime_ref="fixture-celltypist-v1")
    response = client.post(f"/api/sessions/{sid}/assessment/propose", json={
        "question": "Explain observations, then finish the graph-backed private report.",
        "upload_id": aid, "allowed_modes": [
            {"tool_id": "P0-01", "mode_id": None}, {"tool_id": "P0-02", "mode_id": None},
            {"tool_id": "P0-08", "mode_id": "default"},
            {"tool_id": "P0-09", "mode_id": "case_initial_v2"},
            {"tool_id": "P0-10", "mode_id": "default"}],
        "max_tool_runs": 6, "max_model_turns": 7, "report_after_explanation": True})
    assert response.status_code == 200, response.json()
    scope = response.json()["assessment"]
    phase = {"explained": False}

    def planner(settings, messages, context):
        ready = any(row["tool_id"] == "P0-02" and row["state"] == "available"
                    for row in context["evidence"])
        if ready and (not phase["explained"] or not context["options"]):
            phase["explained"] = True
            alias = _citation_choices(context["evidence"])["evidence_aliases"][0]
            return Action.model_validate({"action": "assessment", "decision": {
                "action": "explain", "text": f"A bounded observation [{alias}]",
                "hypotheses": [{"statement": "The available observations remain exploratory.",
                    "evidence_aliases": [alias], "competing_explanation": "An unmeasured cause remains possible.",
                    "discriminating_check": None}]}})
        return _next_check_or_query(settings, messages, context)

    monkeypatch.setattr("bridge.web.provider.converse", planner)
    approve_scope(client, sid, scope)
    first = settle_assessment(client, sid, timeout=240)["_assessment_state"]
    assert first["stop_reason"] == "explanation_complete"
    initial_version = first["interpretation_versions"][0]
    assert [row["tool_id"] for row in service.load(sid)["_tool_runs"]] == ["P0-01", "P0-02"]
    resumed = client.post(f"/api/sessions/{sid}/assessment/resume", json={
        "scope_id": scope["scope_id"], "scope_digest": scope["scope_digest"]})
    assert resumed.status_code == 200, resumed.json()
    second = settle_assessment(client, sid, timeout=240)["_assessment_state"]
    assert second["stop_reason"] == "explanation_complete"
    assert second["interpretation_versions"][0] == initial_version
    current = second["interpretation_versions"][-1]
    assert current["version"] == 2
    assert current["evidence_snapshot_sha256"] != initial_version["evidence_snapshot_sha256"]
    assert [row["tool_id"] for row in service.load(sid)["_tool_runs"]] == ["P0-01", "P0-02", "P0-08", "P0-09"]
    turns = second["model_turns_used"]
    resumed = client.post(f"/api/sessions/{sid}/assessment/resume", json={
        "scope_id": scope["scope_id"], "scope_digest": scope["scope_digest"]})
    assert resumed.status_code == 200, resumed.json()
    done = settle_assessment(client, sid, timeout=180)["_assessment_state"]
    state = service.load(sid)
    assert done["stop_reason"] == "report_complete"
    assert done["model_turns_used"] == turns
    assert [row["tool_id"] for row in state["_tool_runs"]] == ["P0-01", "P0-02", "P0-08", "P0-09", "P0-10"]
    report = next(row for row in state["artifacts"] if row.get("research_report") and row["name"].endswith(".json"))
    snapshot = client.get(report["url"]).json()
    context = json.loads(snapshot["report_context_json"])
    assert context["explanation_versions"][-1]["content_sha256"] == current["content_sha256"]
    # The one genuine measured domain must coexist with four explicit gaps;
    # scope visibility does not authorize any additional scientific tool.
    from bridge.tool_packages.p0_08_evidence_sufficiency.models import P0DomainId
    suff = [service.inputs.verify(state, row) for row in state["_input_objects"].values()
            if row["schema_ref"] == "bridge://schemas/evidence-sufficiency-run-result/v0.3"][-1]
    profiles = {row["domain_id"]: row for row in suff["profiles"]}
    assert set(profiles) == {domain.value for domain in P0DomainId}
    assert profiles["target_identity"]["measurement_result_refs"]
    assert all(row["domain_score"] is None for row in profiles.values())
    for domain, profile in profiles.items():
        if domain != "target_identity":
            assert profile["measurement_result_refs"] == []
            assert profile["evidence_sufficiency_state"] == "not_assessed"
    requirements = json.loads(snapshot["evidence_requirement_set_json"])["requirements"]
    coverage = [row for row in requirements if row["claim_ref"]["object_id"].startswith("claim:native-domain-")]
    assert len(coverage) == 5
    for row in coverage:
        if row["claim_ref"]["object_id"].endswith(":target_identity"):
            assert row["reason_codes"] == ["required_channel_not_provided"]
        else:
            assert row["reason_codes"] == ["measurement_not_provided"]
    assert snapshot["scientific_validation"] == "not_qualified" and snapshot["domain_score"] is None
    assert state["_assessment"]["scope"]["allowed_modes"] == response.json()["assessment"]["allowed_modes"]
    repeated = client.post(f"/api/sessions/{sid}/assessment/resume", json={
        "scope_id": scope["scope_id"], "scope_digest": scope["scope_digest"]})
    assert repeated.status_code == 409
    assert service.load(sid)["_tool_runs"] == state["_tool_runs"]


@pytest.mark.parametrize("with_literature", [False, True])
def test_explicit_report_scope_reuses_graph_and_hands_off_without_model_reselection(
        client, tmp_path, monkeypatch, with_literature):
    _rig(tmp_path, monkeypatch)
    service, sid, aid = producer_scientific_case(
        client, tmp_path, monkeypatch, with_producers=False, with_lineage=False)
    service.settings = replace(service.settings,
        cell_state_measurement_spec_ref="CELLSTATE-scRNA-celltypist-candidate-v0.1",
        cell_state_candidate_runtime_ref="fixture-celltypist-v1")
    earlier = client.post(f"/api/sessions/{sid}/assessment/propose", json={
        "question": "Build the source-backed graph from existing observations.",
        "upload_id": aid, "allowed_modes": [
            {"tool_id": "P0-01", "mode_id": None},
            {"tool_id": "P0-02", "mode_id": None},
            {"tool_id": "P0-06", "mode_id": "exploratory_process"},
            {"tool_id": "P0-08", "mode_id": "default"},
            {"tool_id": "P0-09", "mode_id": "case_initial_v2"}],
        "max_tool_runs": 7, "max_model_turns": 9})
    assert earlier.status_code == 200, earlier.json()
    monkeypatch.setattr("bridge.web.provider.converse", _next_check_or_query)
    approve_scope(client, sid, earlier.json()["assessment"])
    settle_assessment(client, sid, timeout=180)
    before = service.load(sid)
    assert any(row["tool_id"] == "P0-09" and row["state"] == "succeeded"
        for row in before["_tool_runs"])
    assert any(row["tool_id"] == "P0-06" and row["state"] in {"succeeded", "partial"}
        for row in before["_tool_runs"])

    proposed = client.post(f"/api/sessions/{sid}/assessment/propose", json={
        "question": "复用已有测量和证据图，先查询、再给有来源的解释；图查询和报告核验不是生物学鉴别实验。解释后等待继续生成私有报告。",
        "upload_id": aid, "allowed_modes": [
            {"tool_id": "P0-09", "mode_id": "case_query"},
            {"tool_id": "P0-10", "mode_id": "default"}],
        "max_tool_runs": 2, "max_model_turns": 5 if with_literature else 2,
        "literature_enabled": with_literature,
        "literature_concept_refs": ["neuron"] if with_literature else [],
        "max_literature_searches": 1, "max_literature_reads": 1,
        "report_after_explanation": True})
    assert proposed.status_code == 200, proposed.json()
    scope = proposed.json()["assessment"]
    assert next(row for row in scope["candidates"] if row["tool_id"] == "P0-10")["runnable"]

    if not with_literature:
        from copy import deepcopy
        from bridge.web.assessment import AssessmentScope
        from bridge.web.research_context import build_research_context
        state = service.load(sid)
        snapshot = deepcopy(state)
        typed = AssessmentScope.model_validate(state["_assessment"]["scope"])
        with service.qc.catalog():
            pool = service.inputs.assessment_pool(state, typed)
            graphs = [key for key, row in pool.items() if row["schema_ref"] ==
                "bridge://schemas/case-evidence-graph-manifest/v0.1"]
            assert len(graphs) == 1
            graph_path = Path(pool[graphs[0]]["path"])
            graph_files = {path: path.read_bytes() for path in graph_path.parent.iterdir() if path.is_file()}
            context, dependencies = build_research_context(service.report_inputs, state, typed, pool,
                graph_manifest_input_id=graphs[0])
            profiles = {key for key, row in pool.items() if row["schema_ref"] ==
                "bridge://schemas/cell-state-candidate-profile/v1.0"}
            assert profiles and profiles <= set(dependencies)
            assert context.composition_mapping and context.process_means
            incomplete_pool = {key: row for key, row in pool.items() if key not in profiles}
            with pytest.raises(ValueError, match="^report_context_native_profile_missing$"):
                build_research_context(service.report_inputs, state, typed, incomplete_pool,
                    graph_manifest_input_id=graphs[0])
        assert state == snapshot
        assert service.load(sid) == snapshot
        assert all(path.read_bytes() == content for path, content in graph_files.items())

    if with_literature:
        from test_web_literature import transport, article, response
        literature_calls = transport(monkeypatch, [response([article()]), response([article()])])

    def query_then_explain(settings, messages, context):
        from bridge.web.provider import Action
        assert all(row["tool_id"] != "P0-10" for row in context["options"])
        literature = context["literature"]
        if literature["searches_remaining"]:
            return Action.model_validate({"action":"assessment", "decision":{
                "action":"search_literature", "concept_refs":["neuron"], "focus":"identity"}})
        if literature["reads_remaining"] and literature["readable_source_refs"]:
            return Action.model_validate({"action":"assessment", "decision":{
                "action":"read_literature", "source_ref":literature["readable_source_refs"][0]}})
        pending_query = next((row for row in context["options"]
            if (row["tool_id"], row["mode_id"]) == ("P0-09", "case_query")), None)
        if pending_query is not None:
            return Action.model_validate({"action": "assessment", "decision": {
                "action": "query", "option_id": pending_query["id"]}})
        citation = _candidate_citation(context["evidence"])
        return Action.model_validate({"action": "assessment", "decision": {
            "action": "explain", "text": "The candidate measurements allow only a bounded hypothesis.",
            "hypotheses": [{"statement": "The candidate measurements may reflect a signal.",
                "evidence_aliases": [citation],
                "competing_explanation": "An unresolved process could account for it.",
                "expected_observation": "A matched prospective comparison could distinguish the rivals; shared outcomes remain indeterminate.",
                "discriminating_check": None,
                "literature_support": ([{"source_ref": literature["sources"][0]["source_ref"],
                    "rationale": "A public research background for the proposed mechanism.",
                    "species": "Not established from this synthetic abstract.", "lineage": "Neural context",
                    "stage": "Stage applicability remains unresolved.",
                    "experimental_context": "This paper does not measure the current sample."}]
                    if literature["sources"] else [])}]}})

    monkeypatch.setattr("bridge.web.provider.converse", query_then_explain)
    # The literature explanation reserves its own consistency-review turn.
    review_calls = []
    def review(settings, hypotheses, context):
        review_calls.append(hypotheses)
        return {"issues": []}
    monkeypatch.setattr("bridge.web.provider.review_interpretation", review)
    approve_scope(client, sid, scope)
    explained = settle_assessment(client, sid, timeout=180)["_assessment_state"]
    assert explained["stop_reason"] == "explanation_complete"
    assert len(review_calls) == int(with_literature)
    assert len(explained["interpretation_versions"]) == 1
    before_resume = service.load(sid)
    assert [row["tool_id"] for row in before_resume["_tool_runs"][len(before["_tool_runs"]):]] == ["P0-09"]
    turns = explained["model_turns_used"]
    assert turns == (5 if with_literature else 2)

    from copy import deepcopy
    from bridge.web.assessment import AssessmentScope
    from bridge.web.evidence import assessment_evidence
    bound_scope = AssessmentScope.model_validate(before_resume["_assessment"]["scope"])
    with service.qc.catalog():
        report = next(row for row in service.inputs.assessment_candidates(before_resume, bound_scope)
            if row["tool_id"] == "P0-10")
        evidence, _ = assessment_evidence(service.inputs, before_resume, before_resume["_assessment"])
    offered = {"report": report}
    selected, reason = service.assessment._report_resume_candidate(
        before_resume, before_resume["_assessment"], bound_scope, offered, evidence)
    assert selected is report and reason is None
    stale = deepcopy(before_resume)
    stale["_assessment"]["interpretation_versions"][-1]["evidence_snapshot_sha256"] = "0" * 64
    assert service.assessment._report_resume_candidate(
        stale, stale["_assessment"], bound_scope, offered, evidence)[1] == "report_handoff_stale"
    stale = deepcopy(before_resume)
    stale["_assessment"]["model_turns"][-1]["decision"]["action"] = "check"
    assert service.assessment._report_resume_candidate(
        stale, stale["_assessment"], bound_scope, offered, evidence)[1] == "report_handoff_stale"
    stale = deepcopy(before_resume)
    graph_ref = next(ref for ref in report["request"].object_inputs
        if ref.role == "evidence_graph_manifest")
    stale["_input_objects"][graph_ref.input_id]["sha256"] = "0" * 64
    assert service.assessment._report_resume_candidate(
        stale, stale["_assessment"], bound_scope, offered, evidence)[1] == "report_handoff_stale"
    stale = deepcopy(before_resume)
    stale["_input_revision"] += 1
    assert service.assessment.check(stale) == "input_revision_changed"

    # Stress the remaining handoff at the 103/128 object count observed in
    # the isolated operator run. These valid but unpinned package records
    # consume capacity without adding a producer, vote or reusable result.
    capacity_baseline = 103
    assert len(before_resume["_input_objects"]) <= capacity_baseline
    capacity_record = next(row for row in before_resume["_input_objects"].values()
        if row.get("source") == "package_resource")
    for index in range(capacity_baseline - len(before_resume["_input_objects"])):
        identifier = f"f{index:031x}"
        assert identifier not in before_resume["_input_objects"]
        before_resume["_input_objects"][identifier] = {**capacity_record, "label": "capacity-fixture"}
    service.sessions.save(before_resume)
    assert len(service.load(sid)["_input_objects"]) == capacity_baseline

    resumed = client.post(f"/api/sessions/{sid}/assessment/resume", json={
        "scope_id": scope["scope_id"], "scope_digest": scope["scope_digest"]})
    assert resumed.status_code == 200, resumed.json()
    done = settle_assessment(client, sid, timeout=180)["_assessment_state"]
    after = service.load(sid)
    assert done["stop_reason"] == "report_complete"
    assert done["model_turns_used"] == turns
    assert [row["tool_id"] for row in after["_tool_runs"][len(before["_tool_runs"]):]] == ["P0-09", "P0-10"]
    from bridge.tool_packages.p0_10_claim_verifier.research import ResearchAnalysisSnapshotV03, ResearchAnalysisSnapshotV04
    snapshot_type = ResearchAnalysisSnapshotV04 if with_literature else ResearchAnalysisSnapshotV03
    report_json = next(row for row in after["artifacts"]
        if row.get("research_report") and row["name"].endswith(".json"))
    snapshot = snapshot_type.model_validate_json(client.get(report_json["url"]).content)
    context = json.loads(snapshot.report_context_json)
    # A historical run ID is not a receipt identity: legacy reruns could reuse
    # that ID. Only the exact producer content compiled into the graph belongs
    # in this report, even when a later receipt has the same ID and values.
    from bridge.web.research_context import build_research_context
    typed_scope = AssessmentScope.model_validate(after["_assessment"]["scope"])
    pool = service.inputs.assessment_pool(after, typed_scope)
    canonical_outputs = service.report_inputs._canonical_outputs
    def with_colliding_producer(state, pool, tool_id, schema):
        rows = canonical_outputs(state, pool, tool_id, schema)
        if tool_id == "P0-06" and rows:
            identifier, value, producer = rows[0]
            rows = [*rows, (identifier, value, producer.model_copy(update={
                "warnings": [*producer.warnings, "synthetic-distinct-execution"]}))]
        return rows
    monkeypatch.setattr(service.report_inputs, "_canonical_outputs", with_colliding_producer)
    rebuilt, _ = build_research_context(service.report_inputs, after, typed_scope, pool,
        graph_manifest_input_id=graph_ref.input_id)
    assert rebuilt.model_dump(mode="json") == context
    monkeypatch.setattr(service.report_inputs, "_canonical_outputs", canonical_outputs)
    if with_literature:
        assert len(literature_calls) == 2
        version = context["explanation_versions"][-1]
        assert version["object_version"] == "1.1.0"
        assert version["literature"]["sources"][0]["abstract"] == "A public abstract."
        assert version["hypotheses"][0]["literature_support"][0]["source_ref"] == "literature:epmc-med-12345"
        public = client.get(f"/api/sessions/{sid}").json()["assessment"]
        assert public["hypotheses"][0]["qualification"] == "proposed_explanation"
        assert public["hypotheses"][0]["literature_support"][0]["qualification"] == "unverified_applicability"

    assert context["explanation_versions"][-1]["content_sha256"] == (
        done["interpretation_versions"][-1]["content_sha256"])
    assert context["explanation_versions"][-1]["hypotheses"][0]["discriminating_check"] is None
    duplicate = client.post(f"/api/sessions/{sid}/assessment/resume", json={
        "scope_id": scope["scope_id"], "scope_digest": scope["scope_digest"]})
    assert duplicate.status_code == 409
    assert len(service.load(sid)["_tool_runs"]) == len(after["_tool_runs"])

    from hashlib import sha256
    from test_web_intake import stage
    from web_support import confirm_change
    first_reports = [row for row in after["artifacts"] if row.get("research_report")]
    assert len(first_reports) == 4
    assert {row["name"].rsplit(".", 1)[-1] for row in first_reports} == {"html", "json", "csv", "svg"}
    first_report_hashes = {}
    for artifact in first_reports:
        response = client.get(artifact["url"])
        assert response.status_code == 200
        first_report_hashes[artifact["id"]] = sha256(response.content).hexdigest()
        assert first_report_hashes[artifact["id"]] == after["_canonical_artifacts"][artifact["id"]]["sha256"]
    first_receipts = {row["file"]: sha256(
        (service.directory(sid) / "receipts" / row["file"]).read_bytes()).hexdigest()
        for row in after["_tool_runs"]}
    old_runs = list(after["_tool_runs"])
    assert len(after["_input_objects"]) <= 128

    facts = service.intake.current_facts(after, aid, include_draft=False).model_dump(mode="json")
    facts["product_name"] = "Corrected research product"
    pending = stage(client, sid, aid, facts)
    impact = pending["pending_input_change"]["impact"]
    assert {row["tool_id"] for row in impact["affected"]} == {"P0-10"}
    assert {"P0-01", "P0-02", "P0-06", "P0-09"} <= {
        row["tool_id"] for row in impact["reusable"]}
    confirm_change(client, sid, pending)
    corrected = service.load(sid)
    assert service.assessment.check(corrected) == "input_revision_changed"
    assert corrected["_tool_runs"] == old_runs

    corrected_question = "仅修正产品名称；复用已锁定的证据图，不重跑测量或查询。图查询和报告核验不是生物学鉴别实验。"
    proposed_again = client.post(f"/api/sessions/{sid}/assessment/propose", json={
        "question": corrected_question, "upload_id": aid, "allowed_modes": [
            {"tool_id": "P0-09", "mode_id": "case_query"},
            {"tool_id": "P0-10", "mode_id": "default"}],
        "max_tool_runs": 1, "max_model_turns": 1,
        "report_after_explanation": True})
    assert proposed_again.status_code == 200, proposed_again.json()
    new_scope = proposed_again.json()["assessment"]
    assert new_scope["input_revision"] == corrected["_input_revision"]
    assert "interpretation_versions" not in new_scope
    assert service.load(sid)["_assessment"].get("interpretation_versions", []) == []
    archived = service.load(sid)["_assessment_history"][-1]
    assert archived["scope"]["scope_id"] == scope["scope_id"]
    assert archived["stop_reason"] == "report_complete"
    assert len(archived["interpretation_versions"]) == 1

    def explain_reused_sources(settings, messages, current):
        from bridge.web.provider import Action
        assert current["question"] == corrected_question
        assert all(row["tool_id"] != "P0-10" for row in current["options"])
        sources = {row["tool_id"] for row in current["evidence"] if row["state"] == "available"}
        assert {"P0-01", "P0-02", "P0-06", "P0-09"} <= sources
        citation = _candidate_citation(current["evidence"])
        return Action.model_validate({"action": "assessment", "decision": {
            "action": "explain", "text": "The corrected product name changes display context, not measurements.",
            "hypotheses": [{"statement": "The pinned candidate measurements may reflect a signal.",
                "evidence_aliases": [citation],
                "competing_explanation": "The unresolved process may account for the observation.",
                "discriminating_check": None}]}})

    monkeypatch.setattr("bridge.web.provider.converse", explain_reused_sources)
    approve_scope(client, sid, new_scope)
    explained_again = settle_assessment(client, sid, timeout=180)["_assessment_state"]
    assert explained_again["stop_reason"] == "explanation_complete"
    assert explained_again["tool_runs_used"] == 0 and explained_again["model_turns_used"] == 1
    assert len(explained_again["interpretation_versions"]) == 1
    assert explained_again["interpretation_versions"][0]["scope_digest"] == new_scope["scope_digest"]
    assert service.load(sid)["_tool_runs"] == old_runs
    resumed_again = client.post(f"/api/sessions/{sid}/assessment/resume", json={
        "scope_id": new_scope["scope_id"], "scope_digest": new_scope["scope_digest"]})
    assert resumed_again.status_code == 200, resumed_again.json()
    completed_again = settle_assessment(client, sid, timeout=180)["_assessment_state"]
    revised = service.load(sid)
    assert completed_again["stop_reason"] == "report_complete"
    assert completed_again["model_turns_used"] == 1
    assert [row["tool_id"] for row in revised["_tool_runs"][len(old_runs):]] == ["P0-10"]
    assert revised["_tool_runs"][:len(old_runs)] == old_runs
    assert len(revised["_input_objects"]) <= 128
    for receipt_file, checksum in first_receipts.items():
        assert sha256((service.directory(sid) / "receipts" / receipt_file).read_bytes()).hexdigest() == checksum
    for artifact in first_reports:
        assert client.get(artifact["url"]).status_code == 409
        acknowledged = client.post(artifact["url"] + "/acknowledge", json={})
        assert acknowledged.status_code == 200
        assert acknowledged.json()["access_state"] == "historical_unreviewed"
        response = client.get(artifact["url"])
        assert response.status_code == 200
        assert sha256(response.content).hexdigest() == first_report_hashes[artifact["id"]]
    revised_reports = [row for row in revised["artifacts"] if row.get("research_report")]
    assert len(revised_reports) == 8
    new_reports = [row for row in revised_reports if row["id"] not in first_report_hashes]
    assert {row["name"].rsplit(".", 1)[-1] for row in new_reports} == {"html", "json", "csv", "svg"}
    newest_json = next(row for row in new_reports if row["name"].endswith(".json"))
    new_snapshot = snapshot_type.model_validate_json(client.get(newest_json["url"]).content)
    new_context = json.loads(new_snapshot.report_context_json)
    assert new_context["confirmed_product_facts"]["product_name"] == "Corrected research product"
    assert len(new_context["explanation_versions"]) == 2
    assert new_context["explanation_versions"][0]["scope_digest"] == scope["scope_digest"]
    assert new_context["explanation_versions"][-1]["scope_digest"] == new_scope["scope_digest"]
    assert new_context["explanation_versions"][-1]["content_sha256"] == (
        completed_again["interpretation_versions"][0]["content_sha256"])
    assert new_context["explanation_versions"][-1]["hypotheses"][0]["discriminating_check"] is None
    assert new_snapshot.graph_version == snapshot.graph_version
    assert new_snapshot.snapshot_sha256 != snapshot.snapshot_sha256


@pytest.mark.parametrize("with_feedback", [False, True])
def test_candidate_measurements_reach_the_canonical_graph_and_query(client, tmp_path, monkeypatch, with_feedback):
    _rig(tmp_path, monkeypatch)
    service, sid, aid = producer_scientific_case(client, tmp_path, monkeypatch, with_producers=False, with_lineage=False)
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
    scope = response.json()["assessment"]
    phase = {"first_explanation": False, "append_gate_seen": False}

    def explain_after_reports(settings, messages, context):
        from bridge.web.provider import Action
        evidence = context["evidence"]
        first_report = any(row["tool_id"] == "P0-10" and row["state"] == "available" for row in evidence)
        append_gate = any(row["tool_id"] == "P0-10"
            and "current_scope_explanation_required" in row["reason_codes"]
            for row in context["blockers"])
        if append_gate:
            phase["append_gate_seen"] = True
            assert not any(row["tool_id"] == "P0-10" for row in context["options"])
            pending_query = next((row for row in context["options"]
                if row["tool_id"] == "P0-09" and row["mode_id"] == "case_query"), None)
            if pending_query is not None:
                return Action.model_validate({"action": "assessment", "decision": {
                    "action": "query", "option_id": pending_query["id"]}})
        if (first_report and not phase["first_explanation"]) or append_gate:
            phase["first_explanation"] = True
            citation = _candidate_citation(evidence)
            return Action.model_validate({"action": "assessment", "decision": {
                "action": "explain", "text": "The current candidate observations allow a bounded hypothesis.",
                "hypotheses": [{"statement": "The candidate measurements may reflect the proposed signal.",
                    "evidence_aliases": [citation],
                    "competing_explanation": "An unresolved process may account for the observation.",
                    "discriminating_check": None}]}})
        if phase["first_explanation"] and not phase["append_gate_seen"]:
            # A changed explanation legitimately offers a revised v1 report;
            # this run prioritizes the still-unexecuted measurement path.
            option = next((row for row in context["options"] if row["tool_id"] != "P0-10"), None)
            assert option is not None
            return Action.model_validate({"action": "assessment", "decision": {
                "action": "query" if option["mode_id"] == "case_query" else "check",
                "option_id": option["id"]}})
        return _next_check_or_query(settings, messages, context)

    monkeypatch.setattr("bridge.web.provider.converse",
        explain_after_reports if with_feedback else _next_check_or_query)
    approve_scope(client, sid, scope)
    done = settle_assessment(client, sid, timeout=360)["_assessment_state"]
    if with_feedback:
        assert done["stop_reason"] == "explanation_complete"
        state = service.load(sid)
        assert len(state["_assessment"]["interpretation_versions"]) == 1
        # A previously selected same-graph context cannot mask a new explanation.
        from bridge.web.assessment import AssessmentScope
        old_context = next(iter(state["_selected_report_contexts"].values()))
        typed = AssessmentScope.model_validate(state["_assessment"]["scope"])
        current = next(row for row in service.inputs.assessment_candidates(state, typed)
            if row["tool_id"] == "P0-10")
        assert current["blockers"] == []
        new_context = next(ref.input_id for ref in current["request"].object_inputs
            if ref.role == "research_report_context")
        assert new_context != old_context
        for expected_versions in (1, 2):
            if expected_versions == 2:
                # This provider has no memory of earlier calls. It can finish
                # the report handoff only from the current deterministic context.
                def stateless_report(settings, messages, context):
                    from bridge.web.provider import Action
                    if not context["options"]:
                        return Action.model_validate({"action": "assessment", "decision": {
                            "action": "stop", "reason": "no_discriminating_check"}})
                    handoff = context.get("workflow_handoff")
                    if handoff != {"state": "report_ready_after_current_explanation",
                            "explanation_version": 2,
                            "prior_report_state": "not_bound_to_current_explanation"}:
                        return Action.model_validate({"action": "assessment", "decision": {
                            "action": "stop", "reason": "no_discriminating_check"}})
                    option = next(row for row in context["options"] if row["tool_id"] == "P0-10")
                    return Action.model_validate({"action": "assessment", "decision": {
                        "action": "check", "option_id": option["id"]}})
                monkeypatch.setattr("bridge.web.provider.converse", stateless_report)
            response = client.post(f"/api/sessions/{sid}/assessment/resume", json={
                "scope_id": scope["scope_id"], "scope_digest": scope["scope_digest"]})
            assert response.status_code == 200, response.json()
            done = settle_assessment(client, sid, timeout=360)["_assessment_state"]
            if expected_versions == 1:
                assert phase["append_gate_seen"] and done["stop_reason"] == "explanation_complete"
                assert len(done["interpretation_versions"]) == 2
                assert done["interpretation_versions"][-1]["hypotheses"][0]["discriminating_check"] is None
        assert done["status"] == "stopped"
    state = service.load(sid)
    expected = ["P0-01", "P0-02", "P0-08", "P0-09", "P0-09"]
    if with_feedback:
        expected.insert(4, "P0-08")
        expected += ["P0-10", "P0-06", "P0-08", "P0-09", "P0-09", "P0-10"]
        sufficiency_runs = [json.loads((service.directory(sid) / "receipts" / row["file"]).read_bytes())
            for row in state["_tool_runs"] if row["tool_id"] == "P0-08"]
        # Distinct candidate and consensus measurement bindings are not a replay of one request.
        assert len({run["input_hash"] for run in sufficiency_runs}) == 3
        measurement_inputs = [[row for row in run["request"]["object_inputs"]
            if row["role"] == "measurement_result"] for run in sufficiency_runs]
        assert len({frozenset(row["sha256"] for row in rows) for rows in measurement_inputs}) == 3
        candidate_metrics, consensus_metrics = [
            {json.loads(Path(row["path"]).read_bytes())["metric_name"] for row in rows}
            for rows in measurement_inputs[:2]]
        assert len(candidate_metrics) == 2 and "candidate_assignment_fraction" in candidate_metrics
        assert any(metric.startswith("candidate_composition_fraction_") for metric in candidate_metrics)
        assert consensus_metrics == {"consensus_supported_fraction", "source_conflict_fraction"}
        assert candidate_metrics.isdisjoint(consensus_metrics)
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
        from bridge.tool_packages.p0_10_claim_verifier.research import ResearchAnalysisSnapshotV03 as ResearchAnalysisSnapshot
        reports = [row for row in state["artifacts"] if row.get("research_report")]
        assert len(reports) == 8
        assert {row["research_report"]["graph_version"] for row in reports} == {1, 2}
        snapshots = []
        for artifact in reports:
            public = next(row for row in client.get(f"/api/sessions/{sid}").json()["artifacts"]
                if row["id"] == artifact["id"])
            if public["acknowledgement_required"]:
                assert client.get(artifact["url"]).status_code == 409
                assert client.post(artifact["url"] + "/acknowledge", json={}).status_code == 200
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
        first_context = json.loads(snapshots[0].report_context_json)
        second_context = json.loads(snapshots[1].report_context_json)
        assert first_context["explanation_versions"] == []
        assert len(second_context["explanation_versions"]) == 2
        assert second_context["explanation_versions"][-1]["scope_digest"] == scope["scope_digest"]
        assert second_context["explanation_versions"][-1]["hypotheses"] == done["interpretation_versions"][-1]["hypotheses"]

        # A display-only correction reuses biological evidence, but creates a new report.
        from test_web_intake import stage
        from web_support import confirm_change
        facts = service.intake.current_facts(state, aid, include_draft=False).model_dump(mode="json")
        facts["product_name"] = "Corrected research product"
        pending = stage(client, sid, aid, facts)
        impact = pending["pending_input_change"]["impact"]
        assert {row["tool_id"] for row in impact["affected"]} == {"P0-10"}
        assert {"P0-01", "P0-02", "P0-06", "P0-09"} <= {row["tool_id"] for row in impact["reusable"]}
        confirm_change(client, sid, pending)
        before_runs = list(state["_tool_runs"])
        def independent_report(settings, messages, context):
            assert "workflow_handoff" not in context
            return _next_check_or_query(settings, messages, context)
        monkeypatch.setattr("bridge.web.provider.converse", independent_report)
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
            public = next(row for row in client.get(f"/api/sessions/{sid}").json()["artifacts"]
                if row["id"] == artifact["id"])
            if public["acknowledgement_required"]:
                assert client.get(artifact["url"]).status_code == 409
                assert client.post(artifact["url"] + "/acknowledge", json={}).status_code == 200
            response = client.get(artifact["url"])
            assert response.status_code == 200
            assert sha256(response.content).hexdigest() == state["_canonical_artifacts"][artifact["id"]]["sha256"]
        newest = next(row for row in reversed(new_reports) if row["name"].endswith(".json"))
        snapshot = ResearchAnalysisSnapshot.model_validate_json(client.get(newest["url"]).content)
        context = json.loads(snapshot.report_context_json)
        assert context["confirmed_product_facts"]["product_name"] == "Corrected research product"
        assert context["candidate_development"][0]["development_gate_state"] == "failed"
        assert context["composition_mapping"][0]["label"]
        assert all(row["n_observations"] == 4 for row in context["process_means"])
        assert snapshot.graph_version == 2
        assert snapshot.snapshot_sha256 not in {item.snapshot_sha256 for item in snapshots}


@pytest.mark.parametrize("tools", [("P0-05",), ("P0-03",), ("P0-03", "P0-04", "P0-05")])
def test_whole_product_context_is_visible_and_reaches_the_existing_graph(client, tmp_path, monkeypatch, tools):
    tool_id = tools[0]
    _rig(tmp_path, monkeypatch)
    service, sid, aid = producer_scientific_case(
        client, tmp_path, monkeypatch, with_producers=False, with_lineage=False)
    service.settings = replace(service.settings,
        cell_state_measurement_spec_ref="CELLSTATE-scRNA-celltypist-candidate-v0.1",
        cell_state_candidate_runtime_ref="fixture-celltypist-v1")
    url = f"/api/sessions/{sid}"
    monkeypatch.setattr("bridge.web.provider.converse", next_check_or_stop)
    response = client.post(url + "/assessment/propose", json={
        "question": "Inspect whole-product candidate composition without role promotion.", "upload_id": aid,
        "allowed_modes": [{"tool_id": "P0-01", "mode_id": None}, {"tool_id": "P0-02", "mode_id": None}],
        "max_tool_runs": 3, "max_model_turns": 5})
    assert response.status_code == 200, response.json()
    approve_scope(client, sid, response.json()["assessment"])
    done = settle_assessment(client, sid, timeout=180)["assessment"]
    # Native context consent freezes an existing receipt, not a future producer.
    response = client.post(url + "/assessment/propose", json={
        "question": "Inspect the saved whole-product counts.", "upload_id": aid,
        "allowed_modes": [{"tool_id": tool, "mode_id": "saved_cell_state_context"} for tool in tools],
        "max_tool_runs": len(tools), "max_model_turns": len(tools) + 1})
    assert response.status_code == 200, response.json()
    approve_scope(client, sid, response.json()["assessment"])
    done = settle_assessment(client, sid, timeout=180)["assessment"]
    context, = [row for row in done["evidence"] if row["tool_id"] == tool_id]
    assert context["state"] == "available", context
    assert context["navigation"]["tool_run_ref"]["object_id"].startswith("tool-run:")
    assert context["navigation"]["tool_run_ref"]["object_version"] == context["tool_version"]
    from bridge.web.evidence import assessment_evidence
    state = service.load(sid)
    canonical, _ = assessment_evidence(service.inputs, state, state["_assessment"])
    assert canonical == [{key: value for key, value in row.items() if key != "navigation"} for row in done["evidence"]]
    assert all(row["object_version"] == "0.2.0" for row in context["navigation"]["measurements"].values())
    artifact_links = context["navigation"]["measurement_artifacts"]
    assert artifact_links.keys() == context["navigation"]["measurements"].keys()
    for alias, ref in artifact_links.items():
        matching = [row for row in state["_input_objects"].values()
                    if row.get("artifact_id") == ref["object_id"]
                    and "M-" + row["sha256"][:16] == alias]
        assert len(matching) == 1
        assert ref["object_version"] == context["tool_version"]

    rows = context["summary"]["whole_product_composition"]
    assert sum(row["count"] for row in rows) == 4
    assert context["summary"]["target_fraction"] is None
    if tool_id == "P0-03":
        target = next(axis for axis in done["portrait"] if axis["id"] == "target_identity")
        assert context["alias"] in target["context_evidence_aliases"]
    state = service.load(sid)
    assert any(row["schema_ref"] == ("bridge://schemas/saved-target-role-profile/v0.1" if tool_id == "P0-03" else "bridge://schemas/native-cell-state-context-profile/v0.2")
               for row in state["_input_objects"].values())
    original_receipts = [(row["file"], row["sha256"]) for row in state["_tool_runs"]]
    expected_measurements = {
        service.inputs.verify(state, row)["measurement_id"]
        for row in state["_input_objects"].values()
        if row["schema_ref"] == "bridge://schemas/measurement-result/v0.2"
        and row.get("producer_tool_id") in tools
    }
    assert expected_measurements

    monkeypatch.setattr("bridge.web.provider.converse", _next_check_or_query)
    response = client.post(url + "/assessment/propose", json={
        "question": "Trace the saved whole-product counts into evidence.", "upload_id": aid,
        "allowed_modes": [{"tool_id": "P0-08", "mode_id": "default"},
                          {"tool_id": "P0-09", "mode_id": "case_initial_v2"},
                          {"tool_id": "P0-09", "mode_id": "case_query"}],
        "max_tool_runs": 6, "max_model_turns": 8})
    assert response.status_code == 200, response.json()
    assert response.json()["assessment"]["candidates"][0]["runnable"], response.json()["assessment"]["candidates"]
    approve_scope(client, sid, response.json()["assessment"])
    # Compiling and rechecking the saved graph can exceed three minutes on shared hosts.
    settle_assessment(client, sid, timeout=300)
    state = service.load(sid)
    assert [(row["file"], row["sha256"]) for row in state["_tool_runs"][:len(original_receipts)]] == original_receipts
    records = [service.inputs.verify(state, row) for row in state["_input_objects"].values()
               if row["schema_ref"] == "bridge://schemas/evidence-record-set/v0.1"]
    assert any("whole_product_fraction_" in json.dumps(record) for record in records)
    compiled_measurements = {row["measurement_result_ref"]["object_id"]
                             for record in records for row in record["records"]}
    assert expected_measurements <= compiled_measurements

    assert any(row["tool_id"] == "P0-09" and row["state"] == "succeeded" for row in state["_tool_runs"])


def test_saved_graph_selection_continues_after_same_scope_sufficiency(client, tmp_path, monkeypatch):
    """A saved append must consume the new admitted result, not freeze its old blocker."""
    from hashlib import sha256
    from bridge.web.assessment import AssessmentScope

    _rig(tmp_path, monkeypatch)
    service, sid, aid = producer_scientific_case(
        client, tmp_path, monkeypatch, with_producers=False, with_lineage=False)
    service.settings = replace(service.settings,
        cell_state_measurement_spec_ref="CELLSTATE-scRNA-celltypist-candidate-v0.1",
        cell_state_candidate_runtime_ref="fixture-celltypist-v1")
    url = f"/api/sessions/{sid}"
    monkeypatch.setattr("bridge.web.provider.converse", _next_check_or_query)

    def run_scope(modes, budget):
        response = client.post(url + "/assessment/propose", json={
            "question": "Continue the saved product evidence without repeating measurements.",
            "upload_id": aid, "allowed_modes": [
                {"tool_id": tool, "mode_id": mode} for tool, mode in modes],
            "max_tool_runs": budget, "max_model_turns": budget + 2})
        assert response.status_code == 200, response.json()
        proposed = response.json()["assessment"]
        approve_scope(client, sid, proposed)
        settle_assessment(client, sid, timeout=360)
        return proposed

    run_scope([("P0-01", None), ("P0-02", None), ("P0-08", "default"),
               ("P0-09", "case_initial_v2"), ("P0-09", "case_append_v2")], 8)
    state = service.load(sid)
    # Restore actual prior selections as a manually configured session would.
    # These are real successful requests, not invented compiler fixtures.
    for tool_id, mode_id in (("P0-08", "default"), ("P0-09", "case_append_v2")):
        receipt = next(row for row in reversed(state["_tool_runs"]) if row["tool_id"] == tool_id)
        run, _ = service.inputs.producer_objects(state, receipt, tool_id, set())
        assert run.execution_state.value == "succeeded"
        if tool_id == "P0-09":
            assert any(ref.role == "base_graph_manifest" for ref in run.request.object_inputs)
        state["_input_selections"][tool_id] = {"tool_id": tool_id, "mode_id": mode_id,
            "asset_ids": [], "measurement_spec_ref": None,
            "object_inputs": [{"role": ref.role, "input_id": ref.input_id}
                              for ref in run.request.object_inputs]}
    service.sessions.save(state)
    run_scope([("P0-04", "saved_cell_state_context")], 1)
    before = service.load(sid)
    old_runs = list(before["_tool_runs"])
    old_selections = json.loads(json.dumps(before["_input_selections"]))
    old_hashes = {row["file"]: sha256((service.directory(sid) / "receipts" / row["file"]).read_bytes()).hexdigest()
                  for row in old_runs}
    graphs = [service.inputs.verify(before, row) for row in before["_input_objects"].values()
              if row["schema_ref"] == "bridge://schemas/case-evidence-graph-manifest/v0.1"]
    old_version = max(row["graph_version"] for row in graphs)

    proposed = run_scope([("P0-08", "default"), ("P0-09", "case_append_v2"),
                          ("P0-09", "case_query")], 4)
    after = service.load(sid)
    new_runs = after["_tool_runs"][len(old_runs):]
    assert [row["tool_id"] for row in new_runs] == ["P0-08", "P0-09", "P0-09"]
    assert all(row["state"] == "succeeded" for row in new_runs)
    assert after["_assessment"]["scope_digest"] == proposed["scope_digest"]
    assert after["_input_revision"] == before["_input_revision"]
    assert after["_input_selections"] == old_selections
    assert after["_tool_runs"][:len(old_runs)] == old_runs
    assert not after.get("_invalidated_receipts")
    for name, checksum in old_hashes.items():
        assert sha256((service.directory(sid) / "receipts" / name).read_bytes()).hexdigest() == checksum
    appended, _ = service.inputs.producer_objects(after, new_runs[1], "P0-09", set())
    suff = next(ref for ref in appended.request.object_inputs if ref.role == "evidence_sufficiency_run_result")
    assert after["_input_objects"][suff.input_id]["receipt_file"] == new_runs[0]["file"]
    result = appended.result.model_dump(mode="json") if hasattr(appended.result, "model_dump") else appended.result
    assert result["graph_version"] == old_version + 1
    records = [service.inputs.verify(after, row) for row in after["_input_objects"].values()
               if row.get("receipt_file") == new_runs[1]["file"]
               and row["schema_ref"] == "bridge://schemas/evidence-record-set/v0.1"]
    assert any(row["domain_id"] == "developmental_compatibility" for row in records[0]["records"])
    # Successful but unadmitted receipts cannot satisfy this scope's dependency.
    after["_assessment"]["admissions"] = []
    typed = AssessmentScope.model_validate(after["_assessment"]["scope"])
    append = next(row for row in service.inputs.assessment_candidates(after, typed)
                  if row["mode_id"] == "case_append_v2")
    assert append["request"] is None and append["blockers"]


@pytest.mark.parametrize("native_continuation,expected", [
    (False, ["measured_claim_binding_required"]), (True, []),
])
def test_native_continuation_does_not_report_gaps_from_old_manual_claims(monkeypatch, native_continuation, expected):
    from types import SimpleNamespace
    from bridge.web.report_inputs import ReportInputs

    case = {"object_id": "product-case:fixture", "object_version": "0.1.0"}
    # Verified storage values: the manual template covers the old measurement;
    # the new native observation is compiled by its own source-backed policy.
    template = {"product_case_ref": case, "candidate_records": [
        {"measurement_result_ref": {"object_id": "old-measurement", "object_version": "0.2.0"}}]}
    sufficiency = {"case_summary": {"product_case_ref": case}, "profiles": [
        {"measurement_result_refs": [{"object_id": "new-measurement", "object_version": "0.2.0"}]}]}
    inputs = SimpleNamespace(assessment_pool=lambda *args: {"template": template},
                             verify=lambda state, record: record)
    reports = ReportInputs(SimpleNamespace(inputs=inputs))
    monkeypatch.setattr(reports, "_canonical_outputs", lambda *args: [("sufficiency", sufficiency, None)])
    scope = SimpleNamespace(binding={"selections": {"P0-09": {"object_inputs": [
        {"role": "compilation_bundle", "input_id": "template"}]}},
        "append_p009": {"after_sufficiency": native_continuation}})
    assert reports.assessment_gaps({}, scope, SimpleNamespace(
        tool_id="P0-09", mode_id="case_append_v2")) == expected


@pytest.mark.parametrize("state,revision,foreign_case,expected", [
    ("measured", None, False, "required_channel_not_provided"),
    ("unknown", None, False, "required_channel_not_provided"),
    ("alert", None, False, "required_channel_not_provided"),
    ("unavailable", None, False, "measurement_unavailable"),
    ("measured", "supersede", False, "measurement_unavailable"),
    ("measured", "invalidate", False, "measurement_not_provided"),
    ("measured", None, True, "measurement_not_provided"),
])
def test_appending_another_domain_retains_only_effective_same_case_coverage(state, revision, foreign_case, expected):
    from copy import deepcopy
    from types import SimpleNamespace
    from bridge.tool_packages.p0_09_evidence_compiler.models import VersionedObjectRef
    from bridge.web.native_evidence import _domain_coverage
    from test_p0_09_evidence_compiler import _source_record_for_external

    case = SimpleNamespace(ref=VersionedObjectRef(object_id="product-case:test", object_version="0.1.0"))
    definition = SimpleNamespace(ref=VersionedObjectRef(object_id="product-definition:test", object_version="0.1.0"))
    record = _source_record_for_external(
        {"product_case_ref": {"object_id": "product-case:other" if foreign_case else "product-case:test",
                              "object_version": "0.1.0"}, "relation": "supports"},
        {"profile_id": "sufficiency-profile:fixture", "profile_version": "0.1.0"})
    record.update(evidence_state=state, value=0 if state == "measured" else None)
    history = [record]
    if revision:
        history.append({**record, "evidence_version": 2, "revision_action": revision,
            "predecessor_ref": record["evidence_id"] + "@1",
            "lifecycle_state": "invalidated" if revision == "invalidate" else "active",
            "evidence_state": "unavailable", "value": None})
    before = deepcopy(history)
    development = (SimpleNamespace(run_id="development"), "profile", {},
        [("measurement", {"measurement_id": "measurement:development", "evidence_state": "unknown", "raw_value": None})],
        "spec", {})
    sources = [(development, "developmental_compatibility", "METHOD-TEST")]
    if revision:
        saved_target = (SimpleNamespace(run_id="test"), "profile", {},
            [("measurement", {"measurement_id": "measurement-result:target", "evidence_state": "measured", "raw_value": 0})],
            "spec", {})
        sources.append((saved_target, "target_identity", "METHOD-TEST"))
    claims, observations = _domain_coverage(case, definition, sources,
        "2026-09-22T00:00:00Z", prior_records=history)
    reasons = {row["claim_ref"]["object_id"].rsplit(":", 1)[-1]: row["reason_code"] for row in observations}
    assert reasons == {"target_identity": expected, "developmental_compatibility": "required_channel_not_provided",
        "regional_fidelity": "measurement_not_provided", "off_target_control": "measurement_not_provided",
        "proliferation_stress_response": "measurement_not_provided"}
    assert all(row["status"] == "candidate" and
               row["requirement_specs"][0]["requirement_key"] == "independent_validation" for row in claims)
    assert history == before


def test_native_rerun_uses_explicit_revision_and_preserves_previous_evidence(tmp_path):
    from copy import deepcopy
    from test_p0_09_evidence_compiler import _run, _candidate
    from bridge.web.native_evidence import _continuation_candidates
    first = _run(tmp_path / 'initial')
    records = json.loads((first.request.output_dir / first.run_id / 'evidence_records.json').read_text())['records']
    before = deepcopy(records)
    candidate = _candidate(value=0.8)
    candidate['measurement_result_ref']['object_id'] += ':retry'
    candidate['tool_run_ref']['object_id'] += ':retry'
    result = _continuation_candidates([candidate], records)
    assert result[0]['revision_action'] == 'supersede'
    assert result[0]['predecessor_ref'] == f"{records[0]['evidence_id']}@1"
    assert result[0]['measurement_result_ref'] == candidate['measurement_result_ref']
    assert records == before and candidate['revision_action'] == 'create'
    replay = _candidate()
    assert _continuation_candidates([replay], records) == []
    unrelated = deepcopy(candidate)
    unrelated['measurement_spec_ref']['object_id'] += ':different-contract'
    assert _continuation_candidates([unrelated], records)[0]['revision_action'] == 'create'
