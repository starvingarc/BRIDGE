"""Scope consent admits exact registered requests; it is not a science attestation."""
from __future__ import annotations

from dataclasses import replace
import importlib
import json

import pytest

from web_support import client, settle
from test_web_scientific_inputs import science_case
from test_web_inputs import upload_request, choice


def registered_case(client, tmp_path, tool="P0-05", mode="legacy_aggregation"):
    service, sid, aid = science_case(client, tmp_path)
    module = importlib.import_module({
        "P0-05": "test_p0_05_off_target_control",
        "P0-06": "test_p0_06_proliferation_stress_response",
    }[tool])
    supplied = tmp_path / "supplied"
    supplied.mkdir()
    request = module._request(supplied)
    objects = upload_request(client, sid, request, mode)
    selected = client.post(f"/api/sessions/{sid}/analysis-inputs", json=choice(tool, mode, objects))
    assert selected.status_code == 200, selected.json()
    return service, sid, aid


def propose_scope(client, sid, aid, tool="P0-05", mode="legacy_aggregation", **limits):
    response = client.post(f"/api/sessions/{sid}/assessment/propose", json={
        "question": "Describe the registered product evidence and its unresolved denominator.",
        "upload_id": aid, "allowed_modes": [{"tool_id": tool, "mode_id": mode}],
        "max_tool_runs": 3, "max_model_turns": 4, **limits,
    })
    assert response.status_code == 200, response.json()
    return response.json()["assessment"]


def expanded_model_rows(summary, group):
    """Read model-only graph rows with their shared, inherited fields."""
    defaults = summary.get("record_defaults", {}).get(group, {})
    return [{**defaults, **row} for row in summary[group]]


def live_hypothesis(row):
    """Current provider fixtures explicitly author every cited relation."""
    return {**row, "feature_queries": [], "evidence_relations": [
        {"evidence_alias": alias, "relation": relation,
         "rationale": "The cited record constrains this proposed explanation.",
         "applicability": "Only this registered input; not scientific qualification."}
        for field, relation in (("evidence_aliases", "limits"),
                                ("opposing_evidence_aliases", "contradicts"),
                                ("missing_evidence_aliases", "missing_for"))
        for alias in row.get(field, [])]}


def test_report_after_explanation_requires_explicit_scope_intent(client, tmp_path):
    service, sid, aid = science_case(client, tmp_path)
    body = {"question": "Explain the graph, then prepare a private research report.",
        "upload_id": aid, "allowed_modes": [{"tool_id": "P0-10", "mode_id": "default"}],
        "max_tool_runs": 2, "max_model_turns": 3, "report_after_explanation": True}
    response = client.post(f"/api/sessions/{sid}/assessment/propose", json=body)
    assert response.status_code == 200, response.json()
    scope = response.json()["assessment"]
    assert scope["report_after_explanation"] is True
    state = service.load(sid)
    assert state["_assessment"]["scope"]["report_after_explanation"] is True
    assert service.assessment.check(state) is None
    without_report = client.post(f"/api/sessions/{sid}/assessment/propose", json={
        **body, "allowed_modes": [{"tool_id": "P0-01", "mode_id": None}]})
    assert without_report.status_code == 422


def test_report_intent_reuses_observations_and_explains_a_valid_stop(
        client, tmp_path, monkeypatch):
    from test_web_inputs import approve
    from bridge.web.provider import Action, _citation_choices

    service, sid, aid = producer_scientific_case(
        client, tmp_path, monkeypatch, with_producers=False)
    plan = client.post(f"/api/sessions/{sid}/prepare-analysis", json={"tool_id": "P0-01"}).json()["plan"]
    assert approve(client, sid, plan)["plan"]["status"] == "completed"
    before = service.load(sid)
    scope = propose_scope(client, sid, aid, "P0-10", "default",
        question="Explain existing measurements before a private report.",
        report_after_explanation=True, max_tool_runs=1, max_model_turns=1)
    seen = []

    def stop_without_hypothesis(settings, messages, context):
        seen.append(context)
        return Action.model_validate({"action": "assessment", "decision": {
            "action": "stop", "reason": "no_discriminating_check"}})

    monkeypatch.setattr("bridge.web.provider.converse", stop_without_hypothesis)
    approve_scope(client, sid, scope)
    done = settle_assessment(client, sid)
    state = service.load(sid)
    assert len(seen) == 1
    assert seen[0]["report_after_explanation"] is True
    background = seen[0]["biological_context"]
    assert background["source"] == "confirmed_intake"
    assert background["facts"]["target_stage"] == before["_intakes"][aid]["facts"]["target_stage"]
    assert "product_name" not in background["facts"]
    assert "source_family_id" not in background["facts"]
    assert "cell_line" not in background["facts"]
    assert seen[0]["options"] == []
    assert _citation_choices(seen[0]["evidence"])["evidence_aliases"]
    assert done["_assessment_state"]["stop_reason"] == "no_discriminating_check"
    assert done["_assessment_state"]["tool_runs_used"] == 0
    assert state["_tool_runs"] == before["_tool_runs"]
    assert state["_assessment"].get("interpretation_versions", []) == []
    assert state["messages"][-1]["role"] == "assistant"
    assert state["messages"][-1]["source"] == "server_template"
    assert "解释" in state["messages"][-1]["content"]
    assert "报告" in state["messages"][-1]["content"]
    assert done["messages"][-1]["content"] == state["messages"][-1]["content"]


def test_legacy_scope_without_report_intent_keeps_original_digest(client, tmp_path):
    from bridge.web.scientific_inputs import digest
    service, sid, aid = science_case(client, tmp_path)
    scope = propose_scope(client, sid, aid, "P0-01", None)
    assert scope["report_after_explanation"] is False
    state = service.load(sid)
    state["_assessment"]["scope"].pop("report_after_explanation")
    state["_assessment"]["scope_digest"] = digest(state["_assessment"]["scope"])
    service.sessions.save(state)
    assert service.assessment.check(service.load(sid)) is None


def test_interrupted_report_admission_cannot_be_retried_in_the_same_scope(client, tmp_path):
    service, sid, aid = science_case(client, tmp_path)
    response = client.post(f"/api/sessions/{sid}/assessment/propose", json={
        "question": "Prepare a private report after a cited explanation.",
        "upload_id": aid, "allowed_modes": [{"tool_id": "P0-10", "mode_id": "default"}],
        "max_tool_runs": 2, "max_model_turns": 3, "report_after_explanation": True})
    assert response.status_code == 200, response.json()
    scope = response.json()["assessment"]
    state = service.load(sid)
    assessment = state["_assessment"]
    assessment["status"], assessment["stop_reason"] = "interrupted", "execution_interrupted"
    assessment["authorization"] = {"scope_id": scope["scope_id"], "scope_sha256": scope["scope_digest"],
        "approver_id": "test", "authority_ref": "test", "approved_at": "2026-09-16T00:00:00Z"}
    assessment["tool_runs_used"] = 1
    assessment["admissions"] = [{"fingerprint": "a" * 64, "plan_id": "interrupted-plan",
        "plan_sha256": "b" * 64, "tool_id": "P0-10", "mode_id": "default", "state": "dispatched"}]
    service.sessions.save(state)
    resumed = client.post(f"/api/sessions/{sid}/assessment/resume", json={
        "scope_id": scope["scope_id"], "scope_digest": scope["scope_digest"]})
    assert resumed.status_code == 409
    assert service.load(sid)["_assessment"]["tool_runs_used"] == 1


def settle_assessment(client, sid, *, timeout=90):
    import time
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        value = client.get(f"/api/sessions/{sid}").json()
        assert "assessment" in value, value
        if value["assessment"]["status"] != "running":
            # Orchestration tests inspect private bookkeeping explicitly; the
            # researcher-facing response intentionally omits these fields.
            private = client.app.state.service.load(sid)["_assessment"]
            value["_assessment_state"] = {**value["assessment"], **private}
            return value
        time.sleep(.05)
    pytest.fail("assessment did not finish")


def approve_scope(client, sid, scope):
    response = client.post(f"/api/sessions/{sid}/assessment/approve", json={
        "scope_id": scope["scope_id"], "scope_digest": scope["scope_digest"],
    })
    assert response.status_code == 200, response.json()
    return response.json()


def test_scope_cell_state_uses_confirmed_upload_without_manual_selection(client, tmp_path, monkeypatch):
    from test_cell_state import _build_snapshot
    from test_web_inputs import approve
    from bridge.web.assessment import AssessmentScope
    service, sid, aid = producer_scientific_case(client, tmp_path, monkeypatch, with_producers=False)
    plan = client.post(f"/api/sessions/{sid}/prepare-analysis", json={"tool_id": "P0-01"}).json()["plan"]
    assert approve(client, sid, plan)["plan"]["status"] == "completed"
    _build_snapshot(tmp_path, monkeypatch)
    service.settings = replace(service.settings, cell_state_measurement_spec_ref="CELLSTATE-scRNA-shadow-v0.1")
    scope = propose_scope(client, sid, aid, "P0-02", None)
    state = service.load(sid)
    before = state["_input_revision"]
    assert "P0-02" not in state["_input_selections"]
    with service.qc.catalog():
        row, = service.inputs.assessment_candidates(state, AssessmentScope.model_validate(state["_assessment"]["scope"]))
    assert row["blockers"] == []
    assert row["request"].measurement_spec_ref == "CELLSTATE-scRNA-shadow-v0.1"
    assert row["request"].assets[0].asset_id == aid
    assert row["request"].assets[0].metadata["parent_asset_sha256"] == state["_uploads"][aid]["sha256"]
    assert state["_input_revision"] == before
    monkeypatch.setattr("bridge.web.provider.converse", next_check_or_stop)
    approve_scope(client, sid, scope)
    settle_assessment(client, sid)
    runs = [row for row in service.load(sid)["_tool_runs"] if row["tool_id"] == "P0-02"]
    assert len(runs) == 1 and runs[0]["state"] == "succeeded"


def test_completed_qc_scope_binds_exact_v2_artifact_not_legacy_schema_match(
        client, tmp_path, monkeypatch):
    from pathlib import Path
    from test_web_inputs import selected_p002_context
    from test_web_intake import stage, stated_facts
    from web_support import confirm_change
    sid, aid, _, selection = selected_p002_context(client, tmp_path, monkeypatch, panel=True)
    confirm_change(client, sid, stage(client, sid, aid, stated_facts(
        source_family_id="source-family:selected-input")))
    assert client.post(f"/api/sessions/{sid}/analysis-inputs", json=selection).status_code == 200
    scope = propose_scope(client, sid, aid, "P0-02", None)
    state = client.app.state.service.load(sid)
    binding = state["_assessment"]["scope"]["binding"]
    receipt = next(row for row in state["_tool_runs"] if row["tool_id"] == "P0-01")
    raw = json.loads((client.app.state.service.directory(sid) / "receipts" / receipt["file"]).read_bytes())
    actual = next(row for row in raw["artifacts"] if row["kind"] == "qc_profile_v2")
    selected_view = json.loads(Path(actual["path"]).read_bytes())["selected_data_view"]
    assert binding["data_view"] == selected_view
    assert scope["data_view"]["n_observations"] == 4
    assert binding["data_view_receipt"] == {"file": receipt["file"], "sha256": receipt["sha256"]}
    assert len(state["_tool_runs"]) == 1
    assert client.app.state.service.assessment.check(state) is None



def producer_scientific_case(client, tmp_path, monkeypatch, *, with_producers=True, with_lineage=True):
    """One synthetic upload and real QC/cell-state producers; no backend request fixture."""
    import anndata as ad
    from test_cell_state import _write_query, _build_snapshot
    from test_input_qc import _lineage_metadata, _versioned_ref
    from web_support import new_session, confirm_change
    from test_web_intake import stage, stated_facts
    from test_web_inputs import approve
    path = _write_query(tmp_path / "producer-query.h5ad")
    data = ad.read_h5ad(path)
    data.obs["sample_id"] = "sample-a"
    data.obs["capture_id"] = "capture-a"
    data.write_h5ad(path)
    sid = new_session(client)["id"]
    url = f"/api/sessions/{sid}"
    aid = client.post(url + "/uploads", files={"file": ("synthetic.h5ad", path.read_bytes())}).json()["uploads"][0]["id"]
    lineage = _lineage_metadata()
    lineage["observation_ref_columns"] = {}
    lineage["constant_unit_refs"] = {
        "capture": _versioned_ref("capture:capture-a@1.0.0"),
        "preparation": _versioned_ref("preparation:product-a@1.0.0"),
        "donor": _versioned_ref("donor:donor-a@1.0.0"),
    }
    declared = client.post(url + "/analysis-inputs/assets", json={
        "upload_id": aid, "assay": "scRNA-seq", "matrix_location": "X",
        "matrix_semantics": "raw_counts", "input_level": "count_ready",
        "metadata": {"sample_id_column": "sample_id", "capture_id_column": "capture_id",
                     **({"biological_unit_lineage": lineage} if with_lineage else {})}})
    assert declared.status_code == 200, declared.json()
    confirm_change(client, sid, declared.json())
    confirm_change(client, sid, stage(client, sid, aid, stated_facts(
        source_family_id="source-family:synthetic-assessment",
        sample_id_column="sample_id", capture_id_column="capture_id")))
    assert client.post(url + "/analysis-inputs", json=choice("P0-01", None, assets=[aid])).status_code == 200
    if not with_producers:
        service = client.app.state.service
        service.settings = replace(service.settings, share_result_summaries=True)
        return service, sid, aid
    plan = client.post(url + "/prepare-analysis", json={"tool_id": "P0-01"}).json()["plan"]
    assert approve(client, sid, plan)["plan"]["status"] == "completed"
    _build_snapshot(tmp_path, monkeypatch)
    service = client.app.state.service
    service.settings = replace(service.settings,
        cell_state_measurement_spec_ref="CELLSTATE-scRNA-shadow-v0.1", share_result_summaries=True)
    selected = {**choice("P0-02", None, assets=[aid]),
                "measurement_spec_ref": "CELLSTATE-scRNA-shadow-v0.1"}
    assert client.post(url + "/analysis-inputs", json=selected).status_code == 200
    plan = client.post(url + "/prepare-analysis", json={"tool_id": "P0-02"}).json()["plan"]
    assert approve(client, sid, plan)["plan"]["status"] == "completed"
    state = service.load(sid)
    refs = [record for record in state["_input_objects"].values()
            if record["schema_ref"] == "bridge://schemas/cell-state-evidence-profile/v0.3"]
    assert len(refs) == 1
    profile = service.inputs.verify(state, refs[0])
    assert profile["n_observations"] == 4
    assert profile["input_data_view"]["parent_asset_id"] == aid
    return service, sid, aid


def select_target_roots(client, sid):
    """Reviewed synthetic role/region resources, not a constructed scientific request."""
    from test_p0_03_target_regional import _base_payloads, ROLE_SCHEMAS, ROLE_VERSIONS
    from bridge.web.scientific_inputs import encoded, digest
    values = _base_payloads()
    role_map = values["state_role_map"]
    role_map["review_state"] = "reviewed"
    role_map["assignments"] = [
        {"state_id": "L1:Neuron_DA", "product_role": "target", "role_evidence_class": "synthetic",
         "evidence_direction": "supports", "source_refs": ["review:synthetic-only"]},
        {"state_id": "L1:Astrocyte", "product_role": "role_unresolved", "role_evidence_class": "unresolved",
         "evidence_direction": "descriptive_only", "source_refs": ["review:synthetic-only"]},
    ]
    assessment = values["target_regional_assessment_spec"]
    assessment.update(status="frozen", state_role_map_sha256=digest(role_map),
        regional_denominator_state_ids=["L1:Neuron_DA"], regional_target_numerator_state_ids=["L1:Neuron_DA"],
        whole_product_target_region_state_ids=["L1:Neuron_DA"])
    values["measurement_spec"].update(independence_group_kind="donor",
        reference_refs=["REF-PD-vMB-CELLSTATE-v0.2"])
    service = client.app.state.service
    state = service.load(sid)
    objects = []
    for role in ("product_definition_card", "state_role_map", "target_regional_assessment_spec", "measurement_spec"):
        identifier = service.inputs.add_object(state, tool_id="P0-03", mode_id="default", role=role,
            schema_ref=ROLE_SCHEMAS[role], object_version=ROLE_VERSIONS[role], data=encoded(values[role]))
        objects.append({"role": role, "input_id": identifier})
    service.sessions.save(state)
    response = client.post(f"/api/sessions/{sid}/analysis-inputs", json=choice("P0-03", "default", objects))
    assert response.status_code == 200, response.json()
    return objects


def test_registered_producers_materialize_target_request_without_backend_injection(
        client, tmp_path, monkeypatch):
    from bridge.web.assessment import AssessmentScope
    service, sid, aid = producer_scientific_case(client, tmp_path, monkeypatch)
    selected = select_target_roots(client, sid)
    scope = propose_scope(client, sid, aid, "P0-03", "default")
    state = service.load(sid)
    before = json.loads(json.dumps(state))
    typed = AssessmentScope.model_validate(state["_assessment"]["scope"])
    row, = service.inputs.assessment_candidates(state, typed)
    assert row["blockers"] == [], row["blockers"]
    assert row["request"] is not None
    inputs = {ref.role: (ref, service.inputs.verify(state, state["_input_objects"][ref.input_id]))
              for ref in row["request"].object_inputs}
    assert len(inputs) == 11
    case_ref, case = inputs["product_case"]
    assert case["source_unit_kind"] == "preparation"
    assert case["sample_or_preparation_ref"] == {"object_id": "preparation:product-a", "object_version": "1.0.0"}
    assert case["biological_unit_manifest_sha256"] == inputs["biological_unit_manifest"][0].sha256
    assert case["measurement_spec_ref"]["object_id"] == "CELLSTATE-scRNA-shadow-v0.1"
    view = inputs["cell_state_evidence_profile"][1]["input_data_view"]
    assert view == inputs["qc_readiness_profile"][1]["selected_data_view"] == typed.binding["data_view"]
    assert view["n_observations"] == 4 and view["parent_asset_id"] == aid
    assert inputs["biological_unit_assignment"][1]["observation_ids_sha256"] == view["observation_ids_sha256"]
    assert inputs["state_role_map"][0].input_id == next(item["input_id"] for item in selected if item["role"] == "state_role_map")
    assert state["_input_objects"][case_ref.input_id]["source"] == "agent_constructed"
    assert state["_input_selections"] == before["_input_selections"]
    assert state["_input_revision"] == before["_input_revision"]
    again, = service.inputs.assessment_candidates(state, typed)
    assert again["fingerprint"] == row["fingerprint"]
    assert next(ref.input_id for ref in again["request"].object_inputs if ref.role == "product_case") == case_ref.input_id
    assert service.assessment.check(state) is None
    service.sessions.save(state)
    monkeypatch.setattr("bridge.web.provider.converse", next_check_or_stop)
    approve_scope(client, sid, scope)
    done = settle_assessment(client, sid)
    assert done["_assessment_state"]["tool_runs_used"] == 1
    assert done["_assessment_state"]["stop_reason"] == "no_discriminating_check"
    after = service.load(sid)
    receipt = after["_tool_runs"][-1]
    run = json.loads((service.directory(sid) / "receipts" / receipt["file"]).read_bytes())
    assert run["execution_state"] == "partial"
    ratios = run["result"]["channels"][0]
    assert ratios["reason_codes"] == ["state_role_mapping_unresolved"]
    assert ratios["target_identity_fraction"] is None
    assert ratios["regional_fidelity_fraction"] is None
    assert ratios["whole_product_target_region_fraction"] is None
    assert len(run["measurements"]) == 3
    assert all(row["raw_value"] is None and row["evidence_state"] == "unknown"
               for row in run["measurements"])
    evidence = done["_assessment_state"]["evidence"][0]
    assert len(evidence["measurements"]) == 3
    assert all(row["unit"] == "fraction"
               and row["measurement_class"] == "gate_input_measurement"
               and row["domain_score"] is None
               for row in evidence["measurements"])
    assert evidence["summary"]["channels"][0]["target_identity_fraction"] is None
    assert evidence["summary"]["channels"][0]["regional_fidelity_fraction"] is None



def test_product_case_version_tracks_real_producer_and_manifest_content(
        client, tmp_path, monkeypatch):
    from bridge.web.assessment import AssessmentScope
    from test_web_inputs import approve
    from web_support import confirm_change
    service, sid, aid = producer_scientific_case(client, tmp_path, monkeypatch)
    select_target_roots(client, sid)

    def prepared_case():
        propose_scope(client, sid, aid, "P0-03", "default")
        state = service.load(sid)
        scope = AssessmentScope.model_validate(state["_assessment"]["scope"])
        row, = service.inputs.assessment_candidates(state, scope)
        assert row["blockers"] == [], row["blockers"]
        reference = next(item for item in row["request"].object_inputs if item.role == "product_case")
        value = service.inputs.verify(state, state["_input_objects"][reference.input_id])
        count = len(state["_input_objects"])
        again, = service.inputs.assessment_candidates(state, scope)
        repeated = next(item for item in again["request"].object_inputs if item.role == "product_case")
        assert repeated == reference
        assert service.inputs.verify(state, state["_input_objects"][repeated.input_id]) == value
        assert len(state["_input_objects"]) == count
        service.sessions.save(state)
        return value, scope.binding["data_view"]

    original, original_view = prepared_case()
    url = f"/api/sessions/{sid}"
    plan = client.post(url + "/prepare-analysis", json={"tool_id": "P0-02"}).json()["plan"]
    assert approve(client, sid, plan)["plan"]["status"] == "completed"
    rerun, rerun_view = prepared_case()
    assert rerun_view == original_view
    assert rerun["measurement_spec_ref"] == original["measurement_spec_ref"]
    assert rerun["biological_unit_manifest_sha256"] == original["biological_unit_manifest_sha256"]
    assert rerun["provenance_refs"] != original["provenance_refs"]
    assert rerun["created_at"] != original["created_at"]
    assert rerun["case_version"] != original["case_version"]

    # A new explicit lineage declaration must become a real new QC manifest.
    metadata = json.loads(json.dumps(service.load(sid)["_asset_declarations"][aid]["metadata"]))
    metadata["biological_unit_lineage"]["independence_scope_ref"]["object_version"] = "2.0.0"
    declared = client.post(url + "/analysis-inputs/assets", json={
        "upload_id": aid, "assay": "scRNA-seq", "matrix_location": "X",
        "matrix_semantics": "raw_counts", "input_level": "count_ready", "metadata": metadata})
    assert declared.status_code == 200, declared.json()
    confirm_change(client, sid, declared.json())
    from test_web_intake import stage, stated_facts
    confirm_change(client, sid, stage(client, sid, aid, stated_facts(
        source_family_id="source-family:synthetic-assessment",
        sample_id_column="sample_id", capture_id_column="capture_id")))
    for tool in ("P0-01", "P0-02"):
        plan = client.post(url + "/prepare-analysis", json={"tool_id": tool}).json()["plan"]
        assert approve(client, sid, plan)["plan"]["status"] == "completed"
    changed, changed_view = prepared_case()
    assert changed_view["sha256"] == original_view["sha256"]
    assert changed["biological_unit_manifest_sha256"] != rerun["biological_unit_manifest_sha256"]
    assert changed["independence_scope_ref"] == {
        "object_id": "independence-scope:study-a", "object_version": "2.0.0"}
    assert original["product_case_id"] == rerun["product_case_id"] == changed["product_case_id"]
    assert len({original["case_version"], rerun["case_version"], changed["case_version"]}) == 3


def select_development_roots(client, sid):
    from test_p0_04_developmental_compatibility import _base_payloads, ROLE_SCHEMAS, ROLE_VERSIONS
    from bridge.web.scientific_inputs import encoded
    service = client.app.state.service
    state = service.load(sid)
    values = _base_payloads()
    service.inputs.system_options(state)
    values["development_window_spec"]["label_level"] = "L1"
    vocabulary_id = next(service.inputs.verify(state, record)["vocabulary_id"]
                         for record in state["_input_objects"].values()
                         if record["source"] == "system_resource" and record["label"] == "annotation_vocabulary")
    state_map = values["development_state_map"]
    state_map.update(annotation_vocabulary_ref=vocabulary_id, assignments=[
        {"state_id": "L1:Neuron_DA", "label_level": "L1", "stage_role": "within_window",
         "target_related": True, "provenance_refs": [{"object_id": "review:synthetic-development", "object_version": "1"}]},
        {"state_id": "L1:Astrocyte", "label_level": "L1", "stage_role": "unresolved",
         "target_related": False, "provenance_refs": [{"object_id": "review:synthetic-development", "object_version": "1"}]},
    ])
    values["measurement_spec"].update(independence_group_kind="donor",
        reference_refs=["REF-PD-vMB-CELLSTATE-v0.2"])
    objects = []
    for role in ("development_window_spec", "development_state_map", "measurement_spec"):
        identifier = service.inputs.add_object(state, tool_id="P0-04", mode_id="default", role=role,
            schema_ref=ROLE_SCHEMAS[role], object_version=ROLE_VERSIONS[role], data=encoded(values[role]))
        objects.append({"role": role, "input_id": identifier})
    service.sessions.save(state)
    response = client.post(f"/api/sessions/{sid}/analysis-inputs", json=choice("P0-04", "default", objects))
    assert response.status_code == 200, response.json()
    return objects


def select_off_target_roots(client, sid):
    from bridge.web.scientific_inputs import encoded
    from test_p0_06_real_methods import _attestation_receipt
    service = client.app.state.service
    state = service.load(sid)
    role_id = next(row["input_id"] for row in state["_input_selections"]["P0-03"]["object_inputs"]
                   if row["role"] == "state_role_map")
    role_map = service.inputs.verify(state, state["_input_objects"][role_id])
    manifest_id, manifest = next((identifier, service.inputs.verify(state, record))
        for identifier, record in state["_input_objects"].items()
        if record["source"] == "tool_output" and record["schema_ref"] == "bridge://schemas/biological-unit-manifest/v0.1")
    profile = next(service.inputs.verify(state, record) for record in state["_input_objects"].values()
                   if record["schema_ref"] == "bridge://schemas/cell-state-evidence-profile/v0.3")
    resources = {
        "off_target_assessment_spec": ("off-target-assessment-spec/v0.1", {
            "object_version": "0.1.0", "assessment_spec_id": "off-target-assessment-spec:synthetic-selected",
            "spec_version": "1.0.0", "product_definition_ref": role_map["product_definition_ref"],
            "state_role_map_ref": {"object_id": role_map["state_role_map_id"], "object_version": role_map["map_version"]},
            "state_role_map_sha256": state["_input_objects"][role_id]["sha256"],
            "primary_denominator_id": "denominator:whole-selected-view",
            "allowed_unknown_reason_ids": ["unknown", "unresolved", "unavailable", "ood", "source_conflict"],
            "rare_state_rules": [], "active": True}),
        "biological_unit_attestation_receipt": ("biological-unit-attestation-receipt/v0.1",
            _attestation_receipt(manifest, state["_input_objects"][manifest_id]["sha256"], profile["input_data_view"])),
    }
    objects = []
    for role, (schema, payload) in resources.items():
        identifier = service.inputs.add_object(state, tool_id="P0-05", mode_id="hard_count_accounting", role=role,
            schema_ref="bridge://schemas/" + schema, object_version="0.1.0", data=encoded(payload))
        objects.append({"role": role, "input_id": identifier})
    service.sessions.save(state)
    response = client.post(f"/api/sessions/{sid}/analysis-inputs",
                           json=choice("P0-05", "hard_count_accounting", objects))
    assert response.status_code == 200, response.json()
    return objects


@pytest.mark.parametrize("tool,mode,drift", [
    ("P0-03", "default", "scope_view"),
    ("P0-05", "hard_count_accounting", "scope_view"),
    ("P0-05", "hard_count_accounting", "state_role_map"),
    ("P0-05", "hard_count_accounting", "product_definition_card"),
])
def test_complete_manual_assessment_selection_keeps_shared_roots_and_qc_view(
        client, tmp_path, monkeypatch, tool, mode, drift):
    from bridge.web.assessment import AssessmentScope
    from bridge.web.inputs import ObjectChoice, Selection
    from bridge.web.scientific_inputs import encoded

    service, sid, aid = producer_scientific_case(client, tmp_path, monkeypatch)
    select_target_roots(client, sid)
    if tool == "P0-05":
        select_off_target_roots(client, sid)
    propose_scope(client, sid, aid, tool, mode)
    state = service.load(sid)
    scope = AssessmentScope.model_validate(state["_assessment"]["scope"])
    candidate, = service.inputs.assessment_candidates(state, scope)
    assert candidate["blockers"] == []
    selection = Selection.model_validate(choice(tool, mode, [
        {"role": item.role, "input_id": item.input_id}
        for item in candidate["request"].object_inputs]))
    assert service.scientific_inputs.assessment_selection(
        state, scope, scope.allowed_modes[0], selection) == selection

    expected = ("canonical_source_binding_mismatch" if tool == "P0-03"
        else "canonical_source_required:qc_readiness_profile")
    if drift == "scope_view":
        changed = {**scope.binding["data_view"], "view_id": "view:another-qc-selection"}
        scope = scope.model_copy(update={"binding": {**scope.binding, "data_view": changed}})
    else:
        expected = "shared_scientific_resource_mismatch"
        original = next(item for item in selection.object_inputs if item.role == drift)
        record = state["_input_objects"][original.input_id]
        duplicate = service.inputs.add_object(state, tool_id=tool, mode_id=mode, role=drift,
            schema_ref=record["schema_ref"], object_version=record["object_version"],
            data=encoded(service.inputs.verify(state, record)))
        selection = selection.model_copy(update={"object_inputs": [
            ObjectChoice(role=item.role, input_id=duplicate if item.role == drift else item.input_id)
            for item in selection.object_inputs]})
    with pytest.raises(ValueError, match=expected):
        service.scientific_inputs.assessment_selection(state, scope, scope.allowed_modes[0], selection)


@pytest.mark.parametrize("tool,mode,select_roots", [
    ("P0-04", "default", select_development_roots),
    ("P0-05", "hard_count_accounting", select_off_target_roots),
])
def test_source_join_reuses_product_case_view_and_shared_roles(
        client, tmp_path, monkeypatch, tool, mode, select_roots):
    from bridge.web.assessment import AssessmentScope
    service, sid, aid = producer_scientific_case(client, tmp_path, monkeypatch)
    target_roots = select_target_roots(client, sid)
    select_roots(client, sid)
    scope = propose_scope(client, sid, aid, tool, mode)
    state = service.load(sid)
    typed = AssessmentScope.model_validate(state["_assessment"]["scope"])
    original = json.loads(json.dumps(state["_input_selections"]))
    row, = service.inputs.assessment_candidates(state, typed)
    assert row["blockers"] == [], row["blockers"]
    values = {ref.role: service.inputs.verify(state, state["_input_objects"][ref.input_id])
              for ref in row["request"].object_inputs}
    view = values["cell_state_evidence_profile"]["input_data_view"]
    assert view["n_observations"] == 4 and view["parent_asset_id"] == aid
    assert values["product_case"]["sample_or_preparation_ref"]["object_id"] == "preparation:product-a"
    if tool == "P0-05":
        role_id = next(item["input_id"] for item in target_roots if item["role"] == "state_role_map")
        assert next(ref.input_id for ref in row["request"].object_inputs if ref.role == "state_role_map") == role_id
    assert state["_input_selections"] == original
    assert set(item["input_id"] for item in target_roots) <= set(typed.binding["resources"])
    service.sessions.save(state)
    wires = []
    service.settings = replace(service.settings, share_result_summaries=True)
    def capture(settings, messages, context):
        wires.append(json.loads(json.dumps(context)))
        return next_check_or_stop(settings, messages, context)
    monkeypatch.setattr("bridge.web.provider.converse", capture)
    approve_scope(client, sid, scope)
    done = settle_assessment(client, sid)
    assert done["_assessment_state"]["tool_runs_used"] == 1
    assert done["_assessment_state"]["stop_reason"] == "no_discriminating_check"
    after = service.load(sid)
    receipt = after["_tool_runs"][-1]
    run = json.loads((service.directory(sid) / "receipts" / receipt["file"]).read_bytes())
    assert run["execution_state"] == "succeeded"
    if tool == "P0-05":
        assert run["result"]["accounting"]["n_observations"] == 4
        roles = {row["product_role"]: row["consensus_supported_count"]
                 for row in run["result"]["accounting"]["role_counts"]}
        assert roles["target"] == 2 and roles["role_unresolved"] == 2
        assert run["result"]["accounting"]["total_soft_mass"] is None
        assert run["measurements"] == []
        local = next(row for row in done["_assessment_state"]["portrait"] if row["id"] == "composition")["summary"]
        model = wires[-1]["evidence"][0]["summary"]
        for summary in (local, model):
            accounting = summary["accounting"]
            assert accounting["n_observations"] == 4
            assert {row["product_role"]: (row["consensus_supported_count"], row["fraction_of_selected_view"])
                    for row in accounting["role_counts"]} == {
                        "target": (2, 0.5), "known_off_target": (0, 0.0),
                        "acceptable_adjacent": (0, 0.0), "role_unresolved": (2, 0.5)}
            assert accounting["mass_state"] == "unavailable"
            assert accounting["total_soft_mass"] is None
            assert accounting["reason_codes"] == run["result"]["accounting"]["reason_codes"]
            assert accounting["producer_composition"]["state"] == "shadow"
            assert [{key: row[key] for key in ("view", "count", "fraction", "denominator", "state_evidence_state")}
                    for row in accounting["producer_composition"]["records"]] == [
                        {key: row[key] for key in ("view", "count", "fraction", "denominator", "state_evidence_state")}
                        for row in run["result"]["accounting"]["producer_composition"]["records"]]
        assert local["accounting"] == run["result"]["accounting"]
        assert model["accounting"]["primary_denominator_id"] != local["accounting"]["primary_denominator_id"]
    else:
        assert run["result"]["domain_score"] is None
        assert run["result"]["score_state"] == "unavailable"
        assert run["result"]["evidence_state"] == "shadow"
        whole = run["result"]["whole_product_profile"]
        assert whole["denominator"] == 4
        assert {row["role"]: row["fraction"] for row in whole["role_fractions"]} == {
            "earlier": 0.0, "within_window": 0.5, "later": 0.0, "branch_shift": 0.0, "unresolved": 0.5}
        assert run["result"]["target_related_profile"]["denominator"] == 2
        assert len(run["measurements"]) == 10



def select_process_roots(client, sid, tmp_path, case, view):
    """Select only caller-owned method/program/protocol roots, never a backend request."""
    from test_p0_06_real_methods import _method_request, _attestation_receipt, ROLE_CONTRACTS
    from bridge.web.scientific_inputs import encoded
    root = tmp_path / "process-roots"
    root.mkdir()
    fixture = _method_request(root, raw_counts=True)
    roots = {item.role: json.loads(item.path.read_bytes()) for item in fixture.object_inputs
             if item.role in {"program_spec", "protocol_ir", "measurement_spec", "process_method_spec"}}
    roots["protocol_ir"].update(product_case_ref={
        "object_id": case["product_case_id"], "object_version": case["case_version"]},
        metadata_state="not_provided", batch_confounding_state="not_assessed",
        independent_replicate_count=0, comparable_group_count=0, declared_process_step_ids=[])
    roots["process_method_spec"].update(expression_asset_id=view["artifact_id"], gene_symbol_column=None)
    roots["measurement_spec"].update(independence_group_kind="donor",
        applicable_product_cards=[case["product_definition_ref"]["object_id"]])
    service = client.app.state.service
    state = service.load(sid)
    manifest_id, manifest = next((identifier, service.inputs.verify(state, record))
        for identifier, record in state["_input_objects"].items()
        if record["source"] == "tool_output" and record["schema_ref"] == "bridge://schemas/biological-unit-manifest/v0.1")
    roots["biological_unit_attestation_receipt"] = _attestation_receipt(
        manifest, state["_input_objects"][manifest_id]["sha256"], view)
    objects = []
    for role, value in roots.items():
        schema, version = ROLE_CONTRACTS[role]
        identifier = service.inputs.add_object(state, tool_id="P0-06", mode_id="method_runtime_source_bound",
            role=role, schema_ref=schema, object_version=version, data=encoded(value))
        objects.append({"role": role, "input_id": identifier})
    service.sessions.save(state)
    response = client.post(f"/api/sessions/{sid}/analysis-inputs",
        json=choice("P0-06", "method_runtime_source_bound", objects))
    assert response.status_code == 200, response.json()
    return objects


def test_source_bound_process_descriptor_uses_real_producer_without_observation_invention(
        client, tmp_path, monkeypatch):
    from bridge.web.assessment import AssessmentScope
    service, sid, aid = producer_scientific_case(client, tmp_path, monkeypatch)
    select_target_roots(client, sid)
    select_development_roots(client, sid)
    propose_scope(client, sid, aid, "P0-03", "default")
    state = service.load(sid)
    target, = service.inputs.assessment_candidates(state, AssessmentScope.model_validate(state["_assessment"]["scope"]))
    assert target["blockers"] == []
    refs = {item.role: item for item in target["request"].object_inputs}
    case = service.inputs.verify(state, state["_input_objects"][refs["product_case"].input_id])
    view = state["_assessment"]["scope"]["binding"]["data_view"]
    service.sessions.save(state)
    explicit = select_process_roots(client, sid, tmp_path, case, view)
    before_proposal = service.load(sid)["_input_objects"]
    original_count = len(before_proposal)
    scope = propose_scope(client, sid, aid, "P0-06", "method_runtime_source_bound")
    state = service.load(sid)
    created_ids = set(state["_input_objects"]) - set(before_proposal)
    assert len(created_ids) == 1
    assert len(state["_input_objects"]) == original_count + 1
    proposal_objects = dict(state["_input_objects"])
    row, = service.inputs.assessment_candidates(state, AssessmentScope.model_validate(state["_assessment"]["scope"]))
    assert row["blockers"] == [], row["blockers"]
    refs = {item.role: item for item in row["request"].object_inputs}
    actual_case = service.inputs.verify(state, state["_input_objects"][refs["product_case"].input_id])
    assert actual_case == case
    assert created_ids == {refs["process_method_input"].input_id}
    assert state["_input_objects"] == proposal_objects
    descriptor = service.inputs.verify(state, state["_input_objects"][refs["process_method_input"].input_id])
    assert descriptor["object_version"] == "0.2.0"
    assert "observation_states" not in descriptor
    assert descriptor["observation_ids_sha256"] == view["observation_ids_sha256"]
    source = descriptor["source_observations"]
    assert source["producer_tool_id"] == "P0-02"
    assert source["label_level"] == "L1"
    assert source["evidence_path"].endswith("cell_state_evidence.parquet")
    assert source["artifact_manifest_path"].endswith("artifact_manifest.json")
    assert row["request"].assets[0].checksum == view["sha256"]
    assert row["request"].assets[0].asset_id == view["artifact_id"]
    assert len(state["_input_objects"]) == original_count + 1
    again, = service.inputs.assessment_candidates(state, AssessmentScope.model_validate(state["_assessment"]["scope"]))
    assert again["fingerprint"] == row["fingerprint"]
    assert [(item.role, item.input_id, item.sha256) for item in again["request"].object_inputs] == [
        (item.role, item.input_id, item.sha256) for item in row["request"].object_inputs]
    assert state["_input_objects"] == proposal_objects
    assert len(state["_input_objects"]) == original_count + 1
    assert refs["protocol_ir"].input_id == next(item["input_id"] for item in explicit if item["role"] == "protocol_ir")
    service.sessions.save(state)
    monkeypatch.setattr("bridge.web.provider.converse", next_check_or_stop)
    approve_scope(client, sid, scope)
    done = settle_assessment(client, sid)
    assert done["_assessment_state"]["tool_runs_used"] == 1
    assert done["_assessment_state"]["stop_reason"] == "no_discriminating_check"
    after = service.load(sid)
    receipt = after["_tool_runs"][-1]
    run = json.loads((service.directory(sid) / "receipts" / receipt["file"]).read_bytes())
    assert run["execution_state"] == "partial"
    assert run["result"]["domain_score"] is None
    assert run["result"]["score_state"] == "unavailable"
    assert run["result"]["reason_codes"] == [
        "cell_cycle_gene_coverage_insufficient", "process_batch_confounding_unresolved",
        "process_metadata_incomplete", "process_replication_insufficient",
        "program_gene_coverage_insufficient"]
    assert run["result"]["analysis_mode"] == "descriptive_only"
    assert run["result"]["process_attribution_state"] == "cannot_attribute"
    assert run["result"]["untriggered_interpretation"] == "not_evidence_of_safety"
    assert run["result"]["program_results"] == []
    from collections import Counter
    from pathlib import Path
    import hashlib
    artifacts = [item for item in run["artifacts"] if item["kind"] == "measurement_result_v2"]
    assert len(artifacts) == 5
    measurements = []
    for artifact in artifacts:
        raw = Path(artifact["path"]).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == artifact["sha256"]
        measurements.append(json.loads(raw))
    assert Counter(item["metric_name"] for item in measurements) == {
        "program_score_mean": 4, "cell_cycle_cycling_fraction": 1}
    projections = run["result"]["measurement_artifacts"]
    assert Counter((item["source_method_id"], item["program_id"]) for item in projections) == {
        ("PROC-SCORE-DECOUPLER", "program:proliferation"): 1,
        ("PROC-SCORE-DECOUPLER", "program:stress"): 1,
        ("PROC-SCORE-SCANPY", "program:proliferation"): 1,
        ("PROC-SCORE-SCANPY", "program:stress"): 1,
        ("PROC-CYCLE-AGG", "program:cell-cycle"): 1}
    assert {item["artifact_id"] for item in projections} == {item["artifact_id"] for item in artifacts}
    assert {item["measurement_id"] for item in projections} == {item["measurement_id"] for item in measurements}
    assert all(item["n_observations"] == 4 and item["assessment_state"] == "not_assessed"
               and item["analysis_unit_ref"] == "preparation:product-a@1.0.0"
               and item["independence_group_ref"] == "donor:donor-a@1.0.0"
               for item in projections)
    for measurement in measurements:
        assert all(measurement[field] is None for field in (
            "raw_value", "unit", "numerator", "denominator", "interval", "domain_score"))
        assert measurement["evidence_state"] == "unavailable"
        assert measurement["score_state"] == "unavailable"
        assert measurement["source_execution_state"] == "partial"
        assert measurement["source_run_ref"] == f"tool-run:{run['run_id']}@{run['tool_version']}"
        assert view["view_id"] in measurement["provenance_refs"]


def test_scope_admitted_qc_unlocks_exploratory_input_without_extra_authority(
        client, tmp_path, monkeypatch):
    service, sid, aid = producer_scientific_case(client, tmp_path, monkeypatch, with_producers=False)
    response = client.post(f"/api/sessions/{sid}/assessment/propose", json={
        "question": "Describe QC and authorized exploratory cycle coverage, retaining missing genes.",
        "upload_id": aid,
        "allowed_modes": [{"tool_id": "P0-01", "mode_id": None},
                          {"tool_id": "P0-06", "mode_id": "exploratory_process"}],
        "max_tool_runs": 3, "max_model_turns": 4})
    assert response.status_code == 200, response.json()
    scope = response.json()["assessment"]
    assert scope["data_view"]["state"] == "not_available"
    monkeypatch.setattr("bridge.web.provider.converse", next_check_or_stop)
    approve_scope(client, sid, scope)
    done = settle_assessment(client, sid)
    assert done["_assessment_state"]["tool_runs_used"] == 2, done["_assessment_state"]
    assert done["_assessment_state"]["stop_reason"] == "no_discriminating_check"
    state = service.load(sid)
    assert [row["tool_id"] for row in state["_tool_runs"]] == ["P0-01", "P0-06"]
    assert state["_assessment"]["scope"]["binding"]["data_view"] is None
    receipt = state["_tool_runs"][-1]
    run = json.loads((service.directory(sid) / "receipts" / receipt["file"]).read_bytes())
    view = run["result"]["input_contract"]["data_view"]
    assert view["parent_asset_id"] == aid and view["n_observations"] == 4
    assert len(run["measurements"]) == 5
    assert all(row["raw_value"] is None and row["evidence_state"] == "unavailable"
               and row["domain_score"] is None for row in run["measurements"])


@pytest.mark.parametrize("protocol", ["json", "deepseek_tools"])
def test_assessment_http_options_after_qc_describe_unexecuted_actions_and_exact_mode_blockers(
        client, tmp_path, monkeypatch, protocol):
    import httpx
    from test_cell_state import _build_snapshot
    service, sid, aid = producer_scientific_case(client, tmp_path, monkeypatch, with_producers=False)
    _build_snapshot(tmp_path, monkeypatch)
    service.settings = replace(service.settings, model_action_protocol=protocol,
        cell_state_measurement_spec_ref="CELLSTATE-scRNA-shadow-v0.1")
    response = client.post(f"/api/sessions/{sid}/assessment/propose", json={
        "question": "Inspect the authorized cell-state and exploratory process evidence, keeping unresolved science explicit.",
        "upload_id": aid, "allowed_modes": [
            {"tool_id": "P0-01", "mode_id": None}, {"tool_id": "P0-02", "mode_id": None},
            {"tool_id": "P0-06", "mode_id": "method_runtime_source_bound"},
            {"tool_id": "P0-06", "mode_id": "exploratory_process"}],
        "max_tool_runs": 4, "max_model_turns": 5})
    assert response.status_code == 200, response.json()
    scope = response.json()["assessment"]
    before = service.load(sid)
    payloads, contexts = [], []
    original_client = httpx.Client
    def provider_response(request):
        payload = json.loads(request.content)
        from model_wire_contract import assert_model_request
        assert_model_request("generation", payload)
        system = payload["messages"][0]["content"]
        # The prompt can repeat output constraints after the context object.
        context, _ = json.JSONDecoder().raw_decode(system.split("Safe execution context: ", 1)[1])
        from web_support import decode_evidence_tables
        context["evidence"] = decode_evidence_tables(context["evidence"])
        payloads.append(payload)
        contexts.append(context)
        # Only the external HTTP response is fake; actual eligibility, QC, tools and consent remain real.
        selected = next((row for row in context["options"] if row["tool_id"] == "P0-01"), None)
        selected = selected or next((row for row in context["options"]
            if (row["tool_id"], row["mode_id"]) == ("P0-06", "exploratory_process")), None)
        if selected:
            decision = {"action": "check", "option_id": selected["id"]}
        else:
            from bridge.web.provider import _citation_choices
            alias = _citation_choices(context["evidence"])["evidence_aliases"][0]
            record = next(item for evidence in context["evidence"]
                for field in ("measurements", "records") for item in evidence.get(field, [])
                if item.get("citation_alias") == alias)
            statement = f"{record['metric_name']} 的 evidence_state 为 {record['evidence_state']}。"
            decision = {"action": "explain", "text": f"{statement} [{alias}]",
                "hypotheses": [{
                    "statement": statement,
                    "evidence_aliases": [alias],
                    "competing_explanation": "A registered cell-state check could change the interpretation.",
                    "discriminating_check": "P0-02",
                }]}
        if protocol == "json":
            message = {"content": json.dumps({"action": "assessment", "decision": decision})}
        else:
            message = {"content": None, "tool_calls": [{"id": "call-scoped", "type": "function",
                "function": {"name": "assessment", "arguments": json.dumps({"decision": decision})}}]}
        return httpx.Response(200, json={"choices": [{"message": message}]})
    monkeypatch.setattr("bridge.web.provider.httpx.Client",
        lambda **kwargs: original_client(**({"transport": httpx.MockTransport(provider_response)} | kwargs)))
    approve_scope(client, sid, scope)
    done = settle_assessment(client, sid, timeout=180)["_assessment_state"]
    state = service.load(sid)
    assert [row["tool_id"] for row in state["_tool_runs"]] == ["P0-01", "P0-06"]
    assert done["tool_runs_used"] == 2 and done["model_turns_used"] == 3
    skill_uses = [row for row in state["_skill_invocations"] if row["purpose"] == "assessment"]
    assert len(skill_uses) == 3
    assert all(row["purpose"] == "assessment" and row["provider_calls"] == 1
               and [skill["name"] for skill in row["skills"]] == ["product-assessment"]
               and all(skill["selection"] == "scope" for skill in row["skills"]) for row in skill_uses)
    assert done["max_tool_runs"] == 4 and done["max_model_turns"] == 5
    assert done["status"] == "stopped" and done["stop_reason"] == "explanation_complete"
    assert done["scope_grants_scientific_approval"] is False
    assert state["_assessment"]["scope"] == before["_assessment"]["scope"]
    assert state["_input_revision"] == before["_input_revision"]
    approval = state["_plan"]["approval_receipt"]
    assert approval["authorization_kind"] == "scope_derived"
    assert approval["scope_id"] == scope["scope_id"] and approval["scope_sha256"] == scope["scope_digest"]
    assert approval["approved_at"] == state["_assessment"]["authorization"]["approved_at"]
    assert len(contexts) == 3
    assert {(row["tool_id"], row["mode_id"]) for row in contexts[0]["options"]} == {("P0-01", None)}
    post_qc = contexts[1]
    assert {(row["tool_id"], row["mode_id"]) for row in post_qc["options"]} == {
        ("P0-02", None), ("P0-06", "exploratory_process")}
    assert post_qc["blockers"] == [{"tool_id": "P0-06", "mode_id": "method_runtime_source_bound",
                                  "reason_codes": ["scientific_resource_required:product_definition_card"]}]
    assert post_qc["interpretation_gaps"] == []
    assert {(row["tool_id"], row["mode_id"]) for row in contexts[-1]["options"]} == {("P0-02", None)}
    assert any(row["tool_id"] == "P0-02" and row["runnable"] for row in done["candidates"])
    qc, = post_qc["evidence"]
    assert qc["tool_id"] == "P0-01" and qc["score_state"] == "unavailable"
    assert any(type(row["raw_value"]) in {int, float} for row in qc["measurements"])
    for context, payload in zip(contexts, payloads):
        assert set(context) == {"purpose", "question", "allowed_modes", "options", "evidence", "results_sent_to_model",
                                "blockers", "interpretation_gaps", "biological_context", "literature",
                                "evidence_table_encoding"}
        for option in context["options"]:
            spec = service.registry.describe(option["tool_id"])
            assert set(option) == {"id", "tool_id", "mode_id", "kind", "name", "summary", "scientific_status",
                                   "execution_state", "prerequisites_state"}
            assert (option["name"], option["summary"], option["scientific_status"]) == (
                spec.name, spec.summary, spec.scientific_status)
            assert option["execution_state"] == "not_executed_in_scope"
            assert option["prerequisites_state"] == "satisfied_this_turn"
        system = payload["messages"][0]["content"]
        if protocol == "json":
            assert payload["response_format"] == {"type": "json_object"}
            assert "tools" not in payload and "tool_choice" not in payload
        else:
            assert [tool["function"]["name"] for tool in payload["tools"]] == ["assessment"]
            # Undeclared defaults may enable DeepSeek thinking, which rejects forced choice.
            assert "tool_choice" not in payload and "response_format" not in payload
        assert "thinking" not in payload and "reasoning_effort" not in payload
        wire = json.dumps(payload)
        for private in (sid, aid, str(tmp_path), "private-key", "source-family:synthetic-assessment",
                        before["_uploads"][aid]["sha256"], scope["scope_id"], scope["scope_digest"]):
            assert private not in wire
        for turn in state["_assessment"]["model_turns"]:
            assert all(fingerprint not in wire for fingerprint in turn["provider_bindings"]["options"].values())
        assert all(receipt["sha256"] not in wire and receipt["file"] not in wire for receipt in state["_tool_runs"])


@pytest.mark.parametrize("with_unavailable", [False, True])
def test_assessment_tool_parameters_bind_citations_to_current_record_roles(
        monkeypatch, with_unavailable):
    from types import SimpleNamespace
    import httpx
    from jsonschema import Draft202012Validator
    from bridge.web import provider

    evidence = [
        {"alias": "E-container-a", "state": "available", "measurements": [
            {"citation_alias": "E-support-a", "citation_role": "support",
             "metric_name": "metric_a", "raw_value": 0.25, "unit": "fraction",
             "evidence_state": "measured"},
            {"citation_alias": "E-opposition-a", "citation_role": "opposition",
             "metric_name": "negative_control", "raw_value": 0.5, "unit": "fraction",
             "evidence_state": "negative"}]},
        {"alias": "E-container-b", "state": "available", "measurements": [
            {"citation_alias": "E-support-b", "citation_role": "support",
             "metric_name": "metric_b", "raw_value": 0.75, "unit": "fraction",
             "evidence_state": "inferred"}]},
    ]
    if with_unavailable:
        evidence[0]["measurements"].append(
            {"citation_alias": "E-missing-a", "citation_role": "missing",
             "metric_name": "metric_missing", "raw_value": None, "unit": "fraction",
             "evidence_state": "not_estimable"})
    context = {"purpose": "assessment", "question": "Explain only the supplied evidence.",
        "options": [], "evidence": evidence, "results_sent_to_model": True,
        "blockers": [], "interpretation_gaps": []}
    captured = []
    original_client = httpx.Client

    def provider_response(request):
        payload = json.loads(request.content)
        captured.append(payload)
        parameters = payload["tools"][0]["function"]["parameters"]
        fields = parameters["properties"]["decision"]["properties"]["hypotheses"]["items"]["properties"]
        support = fields["evidence_aliases"]["items"].get("enum", ["E-support-a"])[0]
        missing_rule = fields["missing_evidence_aliases"]
        missing = ([] if missing_rule.get("maxItems") == 0 else
            [missing_rule["items"].get("enum", ["E-missing-a"])[0]])
        decision = {"action": "explain", "text": f"metric_a has evidence_state measured. [{support}]",
            "hypotheses": [{"statement": "metric_a has evidence_state measured.",
                "evidence_aliases": [support], "opposing_evidence_aliases": [],
                "missing_evidence_aliases": missing,
                "competing_explanation": "An unresolved process remains possible.",
                "discriminating_check": "P0-09"}]}
        message = {"content": None, "tool_calls": [{"type": "function",
            "function": {"name": "assessment", "arguments": json.dumps({"decision": decision})}}]}
        return httpx.Response(200, json={"choices": [{"message": message}]})

    monkeypatch.setattr(provider.httpx, "Client",
        lambda **kwargs: original_client(transport=httpx.MockTransport(provider_response), **kwargs))
    settings = SimpleNamespace(model="test-model", model_action_protocol="deepseek_tools",
        model_base_url="https://provider.invalid/v1", model_api_key="test-key")
    action = provider.converse(settings, [{"role": "user", "content": "Select the next action."}], context)

    parameters = captured[0]["tools"][0]["function"]["parameters"]
    assert [tool["function"]["name"] for tool in captured[0]["tools"]] == ["assessment"]
    Draft202012Validator.check_schema(parameters)
    fields = parameters["properties"]["decision"]["properties"]["hypotheses"]["items"]["properties"]
    assert fields["evidence_aliases"]["items"]["enum"] == ["E-support-a", "E-support-b"]
    assert fields["opposing_evidence_aliases"]["items"]["enum"] == ["E-opposition-a"]
    missing_rule = fields["missing_evidence_aliases"]
    if with_unavailable:
        assert missing_rule["items"]["enum"] == ["E-missing-a"]
    else:
        assert missing_rule["maxItems"] == 0
        assert "enum" not in missing_rule["items"]
    assert action.decision.hypotheses[0].missing_evidence_aliases == (
        ["E-missing-a"] if with_unavailable else [])
    invalid = action.decision.model_dump(mode="json")
    invalid["hypotheses"][0]["missing_evidence_aliases"] = ["E-support-a"]
    assert not Draft202012Validator(parameters).is_valid({"decision": invalid})


@pytest.mark.parametrize("with_unavailable", [False, True])
def test_json_assessment_wire_names_current_citation_candidates(monkeypatch, with_unavailable):
    from types import SimpleNamespace
    import httpx
    from bridge.web import provider

    evidence = [{"alias": "E-container-a", "state": "available", "measurements": [
        {"citation_alias": "E-support-a", "citation_role": "support",
         "metric_name": "metric_a", "raw_value": 0.25, "unit": "fraction",
         "evidence_state": "measured"},
        {"citation_alias": "E-opposition-a", "citation_role": "opposition",
         "metric_name": "negative_control", "raw_value": 0.5, "unit": "fraction",
         "evidence_state": "negative"}]}]
    if with_unavailable:
        evidence[0]["measurements"].append(
            {"citation_alias": "E-missing-a", "citation_role": "missing",
             "metric_name": "metric_missing", "raw_value": None, "unit": "fraction",
             "evidence_state": "unknown"})
    context = {"purpose": "assessment", "question": "Explain only the supplied evidence.",
        "options": [], "evidence": evidence, "results_sent_to_model": True,
        "blockers": [], "interpretation_gaps": []}
    captured = []
    original_client = httpx.Client

    def provider_response(request):
        payload = json.loads(request.content)
        captured.append(payload)
        system = payload["messages"][0]["content"]
        schema = json.loads(system.split("Assessment action schema: ", 1)[1].split("\n", 1)[0])
        fields = schema["properties"]["decision"]["properties"]["hypotheses"]["items"]["properties"]
        choices = {key: fields[key].get("items", {}).get("enum", []) for key in (
            "evidence_aliases", "opposing_evidence_aliases", "missing_evidence_aliases")}
        decision = {"action": "explain",
            "hypotheses": [{"statement": "metric_a has evidence_state measured.",
                "evidence_aliases": [choices["evidence_aliases"][0]],
                "opposing_evidence_aliases": [],
                "missing_evidence_aliases": choices["missing_evidence_aliases"][:1],
                "competing_explanation": "An unresolved process remains possible.",
                "discriminating_check": None}]}
        decision["hypotheses"] = [live_hypothesis(row) for row in decision["hypotheses"]]
        return httpx.Response(200, json={"choices": [{"message": {
            "content": json.dumps({"action": "assessment", "decision": decision})}}]})

    monkeypatch.setattr(provider.httpx, "Client",
        lambda **kwargs: original_client(transport=httpx.MockTransport(provider_response), **kwargs))
    settings = SimpleNamespace(model="test-model", model_action_protocol="json",
        model_base_url="https://provider.invalid/v1", model_api_key="test-key")
    action = provider.converse(settings, [{"role": "user", "content": "Select the next action."}], context)
    payload = captured[0]
    assert payload["max_tokens"] == 6000
    assert payload["response_format"] == {"type": "json_object"}
    from jsonschema import Draft202012Validator
    schema = json.loads(payload["messages"][0]["content"].split("Assessment action schema: ", 1)[1].split("\n", 1)[0])
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    decision = action.decision.model_dump(mode="json")
    decision["hypotheses"] = [live_hypothesis(row) for row in decision["hypotheses"]]
    wire = {"action": "assessment", "decision": decision}
    assert validator.is_valid(wire)
    assert not validator.is_valid(decision)
    assert not validator.is_valid({**wire, "action": "explain"})
    assert not validator.is_valid({**wire, "text": "misplaced"})
    assert not validator.is_valid({"action": "assessment"})
    assert not validator.is_valid({**wire, "decision": {**decision, "hypotheses": decision["hypotheses"] * 4}})
    for field, invalid in (("statement", "x" * 601), ("evidence_aliases", ["E-support-a"] * 9),
                           ("evidence_aliases", ["E-container-a"]),
                           ("evidence_aliases", ["E-opposition-a"]),
                           ("opposing_evidence_aliases", ["E-support-a"]),
                           ("missing_evidence_aliases", ["E-support-a"]),
                           ("discriminating_check", "P0-09")):
        assert not validator.is_valid({**wire, "decision": {**decision,
            "hypotheses": [{**decision["hypotheses"][0], field: invalid}]}})
    assert "tools" not in payload and "tool_choice" not in payload
    fields = schema["properties"]["decision"]["properties"]["hypotheses"]["items"]["properties"]
    choices = {key: fields[key].get("items", {}).get("enum", []) for key in (
        "evidence_aliases", "opposing_evidence_aliases", "missing_evidence_aliases")}
    if not with_unavailable:
        assert fields["missing_evidence_aliases"]["maxItems"] == 0
    assert choices == {"evidence_aliases": ["E-support-a"],
        "opposing_evidence_aliases": ["E-opposition-a"],
        "missing_evidence_aliases": ["E-missing-a"] if with_unavailable else []}
    assert action.decision.hypotheses[0].missing_evidence_aliases == (
        ["E-missing-a"] if with_unavailable else [])


def test_assessment_tool_parameters_allow_only_bound_limitations_without_available_evidence():
    from jsonschema import Draft202012Validator
    from bridge.web.provider import AssessmentHypothesis, action_tools

    parameters = action_tools("assessment", assessment_evidence=[
        {"alias": "E-container", "state": "available", "measurements": [{
            "citation_alias": "E-only-missing", "citation_role": "missing",
            "metric_name": "metric_missing", "raw_value": None, "unit": "fraction",
            "evidence_state": "not_estimable"}]}])[0]["function"]["parameters"]
    Draft202012Validator.check_schema(parameters)
    hypotheses = parameters["properties"]["decision"]["properties"]["hypotheses"]
    assert hypotheses["maxItems"] == 3
    assert hypotheses["items"]["properties"]["missing_evidence_aliases"]["items"]["enum"] == [
        "E-only-missing"]
    gap = {"statement": "This run cannot estimate this program.", "evidence_aliases": [],
        "opposing_evidence_aliases": [], "missing_evidence_aliases": ["E-only-missing"],
        "expected_observation": None, "competing_explanation": "Missing is not negative.",
        "discriminating_check": None}
    gap = live_hypothesis(gap)
    validator = Draft202012Validator(parameters)
    wire = lambda row: {"decision": {"action": "explain", "hypotheses": [row]}}
    assert validator.is_valid(wire(gap))
    AssessmentHypothesis.model_validate(gap)
    for changes in ({"missing_evidence_aliases": []}, {"opposing_evidence_aliases": ["E-other"]},
                    {"expected_observation": "An unmeasured mechanism"},
                    {"discriminating_check": "P0-06"}):
        assert not validator.is_valid(wire({**gap, **changes}))
        with pytest.raises(ValueError):
            AssessmentHypothesis.model_validate({**gap, **changes})
    assert not validator.is_valid(wire({**gap, "evidence_aliases": ["E-only-missing"]}))
    empty = action_tools("assessment", assessment_evidence=[])[0]["function"]["parameters"]
    assert empty["properties"]["decision"]["properties"]["hypotheses"]["maxItems"] == 0


@pytest.mark.parametrize("protocol", ["json", "deepseek_tools"])
def test_query_report_only_assessment_can_explain_without_pretending_a_scientific_check(
        monkeypatch, protocol):
    from types import SimpleNamespace
    import httpx
    from jsonschema import Draft202012Validator
    from bridge.web import provider

    option_id = "a" * 64
    context = {"purpose": "assessment",
        "question": "Query the graph, then explain it; graph queries and reports are not biological tests.",
        "allowed_modes": [{"tool_id": "P0-09", "mode_id": "case_query"},
                          {"tool_id": "P0-10", "mode_id": "default"}],
        "options": [{"id": option_id, "tool_id": "P0-09", "mode_id": "case_query", "kind": "query"}],
        "evidence": [{"alias": "E-container", "state": "available", "measurements": [{
            "citation_alias": "E-current", "citation_role": "support",
            "metric_name": "metric_current", "raw_value": 0.25, "unit": "fraction",
            "evidence_state": "measured"}]}],
        "results_sent_to_model": True, "blockers": [], "interpretation_gaps": []}
    captured = []
    original_client = httpx.Client

    def provider_response(request):
        payload = json.loads(request.content)
        captured.append(payload)
        decision = {"action": "explain", "text": "metric_current has evidence_state measured. [E-current]",
            "hypotheses": [{"statement": "metric_current has evidence_state measured.",
                "evidence_aliases": ["E-current"], "competing_explanation": "A technical state effect remains.",
                "discriminating_check": None}]}
        decision["hypotheses"] = [live_hypothesis(row) for row in decision["hypotheses"]]
        message = ({"content": json.dumps({"action": "assessment", "decision": decision})}
            if protocol == "json" else {"content": None, "tool_calls": [{"type": "function",
                "function": {"name": "assessment", "arguments": json.dumps({"decision": decision})}}]})
        return httpx.Response(200, json={"choices": [{"message": message}]})

    monkeypatch.setattr(provider.httpx, "Client",
        lambda **kwargs: original_client(transport=httpx.MockTransport(provider_response), **kwargs))
    settings = SimpleNamespace(model="test-model", model_action_protocol=protocol,
        model_base_url="https://provider.invalid/v1", model_api_key="test-key")
    action = provider.converse(settings, [{"role": "user", "content": "Select the next action."}], context)
    assert action.decision.hypotheses[0].discriminating_check is None
    wire = captured[0]
    system = wire["messages"][0]["content"]
    parameters = (wire["tools"][0]["function"]["parameters"] if protocol == "deepseek_tools" else
        json.loads(system.split("Assessment action schema: ", 1)[1].split("\n", 1)[0]))
    fields = parameters["properties"]["decision"]["properties"]
    assert fields["option_id"]["anyOf"][0]["enum"] == [option_id]
    assert fields["hypotheses"]["items"]["properties"]["discriminating_check"] == {"type": "null"}
    if protocol == "deepseek_tools":
        parameters = wire["tools"][0]["function"]["parameters"]
        Draft202012Validator.check_schema(parameters)
        decision = parameters["properties"]["decision"]["properties"]
        assert decision["reason"]["anyOf"][0]["enum"] == ["no_discriminating_check", "necessary_fact_required"]
        assert decision["hypotheses"]["items"]["properties"]["discriminating_check"] == {
            "type": "null"}
        assert Draft202012Validator(parameters).is_valid({"decision": {
            "action": "explain", "text": None, "hypotheses": [live_hypothesis({
                "statement": "Candidate signal", "evidence_aliases": ["E-current"],
                "competing_explanation": "Technical effect", "discriminating_check": None})]}})
        assert not Draft202012Validator(parameters).is_valid({"decision": {
            "action": "explain", "text": None, "hypotheses": [live_hypothesis({
                "statement": "Candidate signal", "evidence_aliases": ["E-current"],
                "competing_explanation": "Technical effect", "discriminating_check": "P0-09"})]}})
        assert not Draft202012Validator(parameters).is_valid({"decision": {
            "action": "query", "option_id": "b" * 64}})


def test_native_assessment_choices_keep_real_check_id_and_null_but_exclude_graph_and_report():
    from jsonschema import Draft202012Validator
    from bridge.web.provider import _assessment_choices, action_tools
    context = {"options": [
        {"id": "a" * 64, "tool_id": "P0-05", "kind": "check"},
        {"id": "b" * 64, "tool_id": "P0-09", "kind": "query"}],
        "evidence": [{"alias": "E-container", "state": "available", "measurements": [{
            "citation_alias": "E-current", "citation_role": "support",
            "metric_name": "metric_current", "raw_value": 0.25, "unit": "fraction",
            "evidence_state": "measured"}]}],
        "allowed_modes": [{"tool_id": "P0-05", "mode_id": "hard_count_accounting"},
                          {"tool_id": "P0-08", "mode_id": "default"},
                          {"tool_id": "P0-09", "mode_id": "case_query"},
                          {"tool_id": "P0-10", "mode_id": "default"}]}
    choices = _assessment_choices(context)
    assert choices["discriminating_check_ids"] == ["P0-05"]
    parameters = action_tools("assessment", assessment_choices=choices)[0]["function"]["parameters"]
    Draft202012Validator.check_schema(parameters)
    fields = parameters["properties"]["decision"]["properties"]
    assert fields["option_id"]["anyOf"][0]["enum"] == ["a" * 64, "b" * 64]
    check = fields["hypotheses"]["items"]["properties"]["discriminating_check"]
    assert check["anyOf"][0]["enum"] == ["P0-05"] and check["anyOf"][1] == {"type": "null"}
    for value, accepted in [("P0-05", True), (None, True), ("P0-06", False), ("P0-09", False)]:
        candidate = {"decision": {"action": "explain", "text": None,
            "hypotheses": [live_hypothesis({"statement": "Candidate signal", "evidence_aliases": ["E-current"],
                "competing_explanation": "Unresolved alternative", "discriminating_check": value})]}}
        assert Draft202012Validator(parameters).is_valid(candidate) is accepted


def test_discriminating_check_requires_a_current_scientific_option():
    from bridge.web.provider import _assessment_choices
    context = {"options": [
        {"id": "a" * 64, "tool_id": "P0-08", "kind": "check"},
        {"id": "b" * 64, "tool_id": "P0-09", "kind": "query"}],
        "evidence": [], "allowed_modes": [
            {"tool_id": "P0-05", "mode_id": "hard_count_accounting"},
            {"tool_id": "P0-08", "mode_id": "default"},
            {"tool_id": "P0-09", "mode_id": "case_query"}]}
    assert _assessment_choices(context)["discriminating_check_ids"] == []
    context["options"].append({"id": "c" * 64, "tool_id": "P0-05", "kind": "check"})
    assert _assessment_choices(context)["discriminating_check_ids"] == ["P0-05"]
    context["options"].extend([
        {"id": "d" * 64, "tool_id": "P0-07", "kind": "check"},
        {"id": "e" * 64, "tool_id": "P0-12", "kind": "check"}])
    assert _assessment_choices(context)["discriminating_check_ids"] == ["P0-05", "P0-07", "P0-12"]


def test_exploratory_resource_is_packaged_and_scope_bound(client, tmp_path, monkeypatch):
    from hashlib import sha256
    from importlib.resources import files
    from bridge.web.assessment import AssessmentScope
    resource = files("bridge.tool_packages.p0_06_proliferation_stress_response").joinpath(
        "resources/seurat-cell-cycle-v5.5.1-candidate.json")
    raw = resource.read_bytes()
    assert sha256(raw).hexdigest() == "0a5c8381d7fab6f2d7ab97bbf95af45953be4c8f49df6ec578bf2c70c75dff73"
    service, sid, aid = producer_scientific_case(client, tmp_path, monkeypatch)
    scope = propose_scope(client, sid, aid, "P0-06", "exploratory_process")
    resource_ref = "bridge://resources/seurat-cell-cycle-candidate/v5.5.1"
    public_resource, = [row for row in scope["resources"] if row.get("resource_ref") == resource_ref]
    assert public_resource["schema_ref"] is None
    assert public_resource["source"] == "package_resource"
    assert public_resource["object_version"] == "0.1.0"
    assert public_resource["sha256"] == sha256(raw).hexdigest()
    state = service.load(sid)
    typed = AssessmentScope.model_validate(state["_assessment"]["scope"])
    row, = service.inputs.assessment_candidates(state, typed)
    assert row["blockers"] == [], row["blockers"]
    request = row["request"]
    assert len(request.assets) == 1
    obj, = request.object_inputs
    value = service.inputs.verify(state, state["_input_objects"][obj.input_id])
    assert value["data_view"] == typed.binding["data_view"]
    assert value["data_view"]["n_observations"] == 4
    assert value["data_view"]["parent_asset_id"] == aid
    assert value["resource_sha256"] == sha256(raw).hexdigest()
    assert value["s_genes"] == json.loads(raw)["lists"]["s.genes"]["genes"]
    assert value["g2m_genes"] == json.loads(raw)["lists"]["g2m.genes"]["genes"]
    assert request.assets[0].checksum == value["data_view"]["sha256"]
    assert request.assets[0].metadata["parent_asset_id"] == aid
    assert request.assets[0].metadata["data_view_id"] == value["data_view"]["view_id"]
    count = len(state["_input_objects"])
    again, = service.inputs.assessment_candidates(state, typed)
    assert again["fingerprint"] == row["fingerprint"]
    assert len(state["_input_objects"]) == count
    try:
        resource.write_bytes(raw + b"\n")
        assert service.assessment.check(state) == "scope_resource_changed"
        changed, = service.inputs.assessment_candidates(state, typed)
        assert changed["blockers"] == ["exploratory_resource_changed"]
        assert len(state["_input_objects"]) == count
        rejected = client.post(f"/api/sessions/{sid}/assessment/approve", json={
            "scope_id": scope["scope_id"], "scope_digest": scope["scope_digest"]})
        assert rejected.status_code == 409
        assert rejected.json()["error_id"] == "request_failed"
        assert "detail" not in rejected.json()
    finally:
        resource.write_bytes(raw)
    assert service.assessment.check(state) is None
    assert len([item for item in state["_input_objects"].values() if item["source"] == "agent_constructed"]) == 1
    service.sessions.save(state)
    monkeypatch.setattr("bridge.web.provider.converse", next_check_or_stop)
    approve_scope(client, sid, scope)
    done = settle_assessment(client, sid)
    assert done["_assessment_state"]["tool_runs_used"] == 1
    assert done["_assessment_state"]["stop_reason"] == "no_discriminating_check"
    after = service.load(sid)
    receipt = after["_tool_runs"][-1]
    run = json.loads((service.directory(sid) / "receipts" / receipt["file"]).read_bytes())
    assert run["result"]["runtime_mode"] == "exploratory_process"
    assert run["result"]["domain_score"] is None
    assert run["result"]["interpretation_scope"] == "descriptive_only"
    assert run["result"]["n_independent_replicates"] is None
    assert len(run["measurements"]) == 5
    assert all(row["raw_value"] is None and row["evidence_state"] == "unavailable"
               and row["domain_score"] is None for row in run["measurements"])


def test_scientific_root_review_unit_and_program_gaps_are_explicit(client, tmp_path, monkeypatch):
    from bridge.web.assessment import AssessmentScope
    from bridge.web.scientific_inputs import encoded
    service, sid, aid = producer_scientific_case(client, tmp_path, monkeypatch)
    select_target_roots(client, sid)
    select_development_roots(client, sid)
    select_off_target_roots(client, sid)
    baseline = service.load(sid)["_input_selections"]
    cases = [
        ("P0-03", "state_role_map", {"review_state": "draft"}, "state_role_review_required"),
        ("P0-03", "target_regional_assessment_spec", {"status": "candidate"}, "regional_definition_review_required"),
        ("P0-04", "development_state_map", {"review_state": "draft"}, "development_state_review_required"),
        ("P0-04", "development_window_spec", {"review_state": "candidate", "reviewer_ref": None, "confirmed_at": None},
         "development_window_review_required"),
    ]
    for tool, role, changes, reason in cases:
        state = service.load(sid)
        selected = json.loads(json.dumps(baseline[tool]))
        original = next(item["input_id"] for item in selected["object_inputs"] if item["role"] == role)
        record = state["_input_objects"][original]
        payload = service.inputs.verify(state, record)
        payload.update(changes)
        identifier = service.inputs.add_object(state, tool_id=tool, mode_id="default", role=role,
            schema_ref=record["schema_ref"], object_version=record["object_version"], data=encoded(payload))
        selected["object_inputs"] = [{"role": item["role"], "input_id": identifier if item["role"] == role else item["input_id"]}
                                     for item in selected["object_inputs"]]
        service.sessions.save(state)
        assert client.post(f"/api/sessions/{sid}/analysis-inputs", json=selected).status_code == 200
        propose_scope(client, sid, aid, tool, "default")
        state = service.load(sid)
        count = len(state["_input_objects"])
        row, = service.inputs.assessment_candidates(state, AssessmentScope.model_validate(state["_assessment"]["scope"]))
        assert row["blockers"] == [reason]
        assert row["request"] is None and len(state["_input_objects"]) == count
        assert client.post(f"/api/sessions/{sid}/analysis-inputs", json=baseline[tool]).status_code == 200
    selected = json.loads(json.dumps(baseline["P0-05"]))
    selected["object_inputs"] = [item for item in selected["object_inputs"] if item["role"] != "biological_unit_attestation_receipt"]
    assert client.post(f"/api/sessions/{sid}/analysis-inputs", json=selected).status_code == 200
    for tool, mode, reason in [
        ("P0-05", "hard_count_accounting", "scientific_resource_required:biological_unit_attestation_receipt"),
        ("P0-06", "method_runtime_source_bound", "scientific_resource_required:program_spec")]:
        propose_scope(client, sid, aid, tool, mode)
        state = service.load(sid)
        row, = service.inputs.assessment_candidates(state, AssessmentScope.model_validate(state["_assessment"]["scope"]))
        assert row["blockers"] == [reason]
        assert row["request"] is None
    assert len(service.load(sid)["_tool_runs"]) == 2


def test_each_product_domain_exposes_all_missing_reviewed_inputs(client, tmp_path, monkeypatch):
    from bridge.web.assessment import AssessmentScope
    service, sid, aid = producer_scientific_case(client, tmp_path, monkeypatch)
    expected = {
        ("P0-03", "default"): {
            "scientific_resource_required:product_definition_card",
            "scientific_resource_required:state_role_map",
            "scientific_resource_required:target_regional_assessment_spec",
            "scientific_resource_required:measurement_spec",
        },
        ("P0-04", "default"): {
            "scientific_resource_required:product_definition_card",
            "scientific_resource_required:development_state_map",
            "scientific_resource_required:development_window_spec",
            "scientific_resource_required:measurement_spec",
        },
        ("P0-05", "hard_count_accounting"): {
            "scientific_resource_required:product_definition_card",
            "scientific_resource_required:state_role_map",
            "scientific_resource_required:off_target_assessment_spec",
            "scientific_resource_required:biological_unit_attestation_receipt",
        },
    }
    for (tool, mode), missing in expected.items():
        propose_scope(client, sid, aid, tool, mode)
        state = service.load(sid)
        row, = service.inputs.assessment_candidates(
            state, AssessmentScope.model_validate(state["_assessment"]["scope"]))
        assert missing <= set(row["blockers"])
        assert row["request"] is None


def test_other_domain_modes_do_not_inherit_reviewed_root_blockers():
    from types import SimpleNamespace
    from bridge.web.scientific_inputs import ScientificInputs

    scientific = ScientificInputs(SimpleNamespace(inputs=None))
    scope = SimpleNamespace(binding={"selections": {}, "intake": {"facts": {"sampling_context": "unknown"}}})
    for tool, mode in (("P0-03", "reference_similarity_exploratory"),
                       ("P0-03", "saved_reference_similarity_projection"),
                       ("P0-05", "method_runtime"), ("P0-05", "legacy_aggregation")):
        assert scientific.assessment_blockers({}, scope, SimpleNamespace(tool_id=tool, mode_id=mode)) == []


def test_complete_manual_domain_selection_keeps_package_eligibility():
    from types import SimpleNamespace
    from bridge.toolkit.registry import ToolRegistry
    from bridge.web.scientific_inputs import ScientificInputs

    registry = ToolRegistry.load_default()
    contract = registry.describe_input("P0-05")
    mode = next(item for item in contract.object_input_modes if item.mode_id == "hard_count_accounting")
    assets = mode.asset_input or contract.asset_input
    selection = {"object_inputs": [{"role": role.role, "input_id": "manual"}
                                   for role in mode.roles for _ in range(role.min_count)],
                 "asset_ids": ["upload"] if assets and assets.min_count else []}
    inputs = SimpleNamespace(contract_mode=lambda tool, chosen: (contract, mode))
    scientific = ScientificInputs(SimpleNamespace(inputs=inputs))
    scope = SimpleNamespace(binding={"selections": {"P0-05": selection},
                                     "intake": {"facts": {"sampling_context": "unknown"}}})
    allowed = SimpleNamespace(tool_id="P0-05", mode_id="hard_count_accounting")
    assert scientific.assessment_blockers({}, scope, allowed) == []


def test_raw_similarity_uses_original_counts_bound_to_qc_view(client, tmp_path, monkeypatch):
    service, sid, aid = producer_scientific_case(client, tmp_path, monkeypatch)
    state = service.load(sid)
    asset = service.inputs.selected_asset(state, "P0-03", aid, raw_similarity=True)
    qc = next(value for row in state["_input_objects"].values()
              if row.get("schema_ref") == "bridge://schemas/qc-readiness-profile/v0.2"
              for value in [service.inputs.verify(state, row)] if value.get("selected_data_view"))
    view = qc["selected_data_view"]
    assert asset.asset_id == aid
    assert asset.checksum == view["parent_asset_sha256"]
    assert asset.matrix_location == view["matrix_location"]
    assert asset.metadata["data_view_id"] == view["view_id"]


@pytest.mark.parametrize("technical", [False, True])
def test_native_policy_links_each_measurement_only_to_its_verified_artifact(tmp_path, technical):
    import hashlib
    from types import SimpleNamespace
    from bridge.tool_packages._configurable_contracts import ProductCase, ProductDefinitionCard
    from bridge.web.native_evidence import _policy
    from test_p0_03_target_regional import _base_payloads

    values = _base_payloads()
    values["product_case"]["source_unit_kind"] = "preparation"
    case = ProductCase.model_validate(values["product_case"])
    definition = ProductDefinitionCard.model_validate(values["product_definition_card"])
    rows = [{"measurement_id": f"measurement:synthetic:{index}",
             "measurement_spec_id": "measurement-spec:synthetic", "measurement_spec_version": "0.1.0",
             "metric_name": f"synthetic_metric_{index}", "raw_value": (index + 1) / 4,
             "numerator": index + 1, "denominator": 4, "unit": "fraction", "interval": None,
             "interval_confidence_level": None, "interval_method_ref": None,
             "unknown_scope": None, "evidence_state": "inferred", "score_state": "unavailable",
             "domain_score": None, "source_run_ref": "tool-run:synthetic@0.1.0",
             "source_execution_state": "succeeded", "provenance_refs": ["source:synthetic"]}
            for index in range(2)]
    artifacts = []
    for kind, payload in [("reference_result", {"state": "candidate", "measurement_id": "not-a-measurement"}),
                          ("measurement_spec", {"measurement_spec_id": "measurement-spec:synthetic"}),
                          *((f"native_measurement_{index}", row) for index, row in enumerate(rows))]:
        path = tmp_path / (kind + ".json")
        path.write_text(json.dumps(payload, sort_keys=True))
        artifacts.append(SimpleNamespace(kind=kind, path=path,
            artifact_id="artifact:synthetic:" + kind,
            sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    run = SimpleNamespace(run_id="synthetic", tool_version="0.1.0", artifacts=artifacts,
        request=SimpleNamespace(object_inputs=[], output_dir=tmp_path),
        execution_state=SimpleNamespace(value="succeeded"),
        model_dump=lambda mode: {"run_id": "synthetic", "tool_version": "0.1.0"})
    policy = _policy(case, definition, None, run, {"input_data_view": {}},
        [(str(index), row) for index, row in enumerate(rows)],
        {"measurement_spec_id": "measurement-spec:synthetic", "version": "0.1.0",
         "analysis_unit_kind": "whole_view_technical_aggregate" if technical else "preparation"},
        "sufficiency", {}, "evidence-family:synthetic", "2026-09-23T00:00:00Z")
    candidates = policy["compilation_bundle"].candidate_records
    assert next(row.schema_ref for row in policy["compilation_bundle"].object_catalog
                if row.node_type == "MeasurementSpec") == (
                    "bridge://schemas/measurement-spec/v0.3" if technical
                    else "bridge://schemas/measurement-spec/v0.2")
    for index, candidate in enumerate(candidates):
        assert {ref["object_id"] for ref in candidate["artifact_refs"]} == {
            "artifact:synthetic:reference_result", "artifact:synthetic:measurement_spec",
            f"artifact:synthetic:native_measurement_{index}"}


def test_canonical_source_drift_invalidates_derived_case_and_scope(client, tmp_path, monkeypatch):
    from pathlib import Path
    from bridge.web.assessment import AssessmentScope
    service, sid, aid = producer_scientific_case(client, tmp_path, monkeypatch)
    select_target_roots(client, sid)
    propose_scope(client, sid, aid, "P0-03", "default")
    state = service.load(sid)
    typed = AssessmentScope.model_validate(state["_assessment"]["scope"])
    row, = service.inputs.assessment_candidates(state, typed)
    case = next(item for item in row["request"].object_inputs if item.role == "product_case")
    source = next(item for item in row["request"].object_inputs if item.role == "cell_state_evidence_profile")
    path = Path(source.path)
    raw = path.read_bytes()
    try:
        path.write_bytes(raw + b"\n")
        assert service.assessment.check(state) == "scope_resource_changed"
        with pytest.raises(ValueError):
            service.inputs.verify(state, state["_input_objects"][case.input_id])
        blocked, = service.inputs.assessment_candidates(state, typed)
        assert blocked["blockers"] and blocked["request"] is None
    finally:
        path.write_bytes(raw)
    assert service.assessment.check(state) is None


def test_empty_evidence_cannot_complete_on_provider_assertion(client, tmp_path, monkeypatch):
    service, sid, aid = registered_case(client, tmp_path)
    scope = propose_scope(client, sid, aid)
    before = service.load(sid)
    def model(settings, messages, context):
        from bridge.web.provider import Action
        assert context["options"] and context["evidence"] == []
        return Action.model_validate({"action": "assessment", "decision": {
            "action": "stop", "reason": "evidence_requirements_reached"}})
    monkeypatch.setattr("bridge.web.provider.converse", model)
    approve_scope(client, sid, scope)
    done = settle(client, sid)
    assert done["_assessment_state"]["status"] == "blocked"
    assert done["_assessment_state"]["stop_reason"] == "completion_contract_unavailable"
    assert done["_assessment_state"]["model_turns_used"] == 1
    assert done["_assessment_state"]["tool_runs_used"] == 0
    assert done["_assessment_state"]["evidence"] == []
    after = service.load(sid)
    assert after["_tool_runs"] == before["_tool_runs"] == []
    assert after["_input_objects"] == before["_input_objects"]
    assert after["_input_revision"] == before["_input_revision"]
    assert after["_assessment"]["model_turns"][-1]["decision"]["reason"] == "evidence_requirements_reached"
    assert "evidence_requirements_reached" not in json.dumps(done["assessment"])


@pytest.mark.parametrize("tool", ["P0-05", "P0-06"])
def test_scope_runs_real_registered_check_then_reads_result_without_new_human_approval(
        client, tmp_path, monkeypatch, tool):
    service, sid, aid = registered_case(client, tmp_path, tool)
    service.settings = replace(service.settings, share_result_summaries=True)
    scope = propose_scope(client, sid, aid, tool)
    before = service.load(sid)
    assert before["_tool_runs"] == []
    assert scope["status"] == "proposed"

    def model(settings, messages, context):
        from bridge.web.provider import Action
        assert context["purpose"] == "assessment"
        assert messages == [{"role": "user", "content": "Select the next authorized evidence action."}]
        if not context["evidence"]:
            return Action.model_validate({"action": "assessment", "decision": {
                "action": "check", "option_id": context["options"][0]["id"]}})
        assert context["options"] == []
        return Action.model_validate({"action": "assessment", "decision": {
            "action": "stop", "reason": "no_discriminating_check"}})

    monkeypatch.setattr("bridge.web.provider.converse", model)
    approve_scope(client, sid, scope)
    done = settle(client, sid)
    assert done["_assessment_state"]["status"] == "stopped", done
    assert done["_assessment_state"]["stop_reason"] == "no_discriminating_check"
    assert done["_assessment_state"]["tool_runs_used"] == 1
    assert done["_assessment_state"]["model_turns_used"] == 2
    state = service.load(sid)
    assert state["_input_revision"] == before["_input_revision"]
    assert len(state["_tool_runs"]) == 1
    assert state["_tool_runs"][0]["tool_id"] == tool
    authorization = state["_assessment"]["authorization"]
    receipt = state["_plan"]["approval_receipt"]
    assert receipt["authorization_kind"] == "scope_derived"
    assert receipt["scope_id"] == scope["scope_id"]
    assert receipt["scope_sha256"] == scope["scope_digest"]
    assert receipt["approver_id"] == authorization["approver_id"] == "private-operator"
    assert receipt["approved_at"] == authorization["approved_at"]
    assert receipt["plan_sha256"] == done["plan"]["digest"]
    assert done["plan"]["status"] == "completed"
    evidence = done["_assessment_state"]["evidence"][0]
    assert evidence["tool_id"] == tool
    assert evidence["domain_score"] is None
    assert evidence["score_state"] == "unavailable"
    assert evidence["state"] == "available"
    assert str(tmp_path) not in json.dumps(done["assessment"])
    if tool == "P0-05":
        assert evidence["summary"]["primary_denominator"]["n_observations"] == 10
        assert evidence["summary"]["role_composition"][0]["product_role"] == "target"
    else:
        assert evidence["summary"]["analysis_mode"] == "descriptive_only"
        assert len(evidence["summary"]["program_results"]) == 2
        assert evidence["summary"]["program_results"][1]["value"] == 0.9
        assert evidence["summary"]["program_results"][1]["unit"] == "relative-score"
        assert evidence["summary"]["program_results"][1]["numerator"] == 9
        assert evidence["summary"]["program_results"][1]["denominator"] == 10


def next_check_or_stop(settings, messages, context):
    from bridge.web.provider import Action
    decision = ({"action": "check", "option_id": context["options"][0]["id"]}
                if context["options"] else {"action": "stop", "reason": "no_discriminating_check"})
    return Action.model_validate({"action": "assessment", "decision": decision})


@pytest.mark.parametrize("limits,reason", [
    ({"max_tool_runs": 1}, "tool_run_budget_exhausted"),
    ({"max_model_turns": 1}, "model_turn_budget_exhausted"),
])
def test_durable_budget_cannot_be_refunded_by_resume(client, tmp_path, monkeypatch, limits, reason):
    service, sid, aid = registered_case(client, tmp_path)
    service.settings = replace(service.settings, share_result_summaries=True)
    scope = propose_scope(client, sid, aid, **limits)
    monkeypatch.setattr("bridge.web.provider.converse", next_check_or_stop)
    approve_scope(client, sid, scope)
    done = settle(client, sid)["_assessment_state"]
    assert done["stop_reason"] == reason
    assert done["tool_runs_used"] == done["model_turns_used"] == 1
    response = client.post(f"/api/sessions/{sid}/assessment/resume",
                          json={"scope_id": scope["scope_id"], "scope_digest": scope["scope_digest"]})
    assert response.status_code == 409
    assert response.json()["error_id"] == "execution_incomplete"
    assert "detail" not in response.json()
    assert len(service.load(sid)["_tool_runs"]) == 1


def test_repeated_scientific_request_ignores_new_random_request_ids(client, tmp_path, monkeypatch):
    service, sid, aid = registered_case(client, tmp_path)
    service.settings = replace(service.settings, share_result_summaries=True)
    scope = propose_scope(client, sid, aid)
    option = []
    def repeat(settings, messages, context):
        from bridge.web.provider import Action
        if not option:
            option.append(context["options"][0]["id"])
        return Action.model_validate({"action": "assessment", "decision": {
            "action": "check", "option_id": option[0]}})
    monkeypatch.setattr("bridge.web.provider.converse", repeat)
    approve_scope(client, sid, scope)
    done = settle(client, sid)["_assessment_state"]
    assert done["stop_reason"] == "unavailable_or_repeated_action"
    assert done["candidates"][0]["already_admitted"] is True
    assert done["candidates"][0]["runnable"] is False
    assert done["tool_runs_used"] == 1 and done["model_turns_used"] == 2
    assert len(service.load(sid)["_tool_runs"]) == 1


def test_new_scope_reads_only_pinned_valid_prior_measurement(client, tmp_path, monkeypatch):
    from copy import deepcopy
    from bridge.web.evidence import assessment_evidence
    from test_web_inputs import approve
    service, sid, aid = producer_scientific_case(client, tmp_path, monkeypatch, with_producers=False)
    plan = client.post(f"/api/sessions/{sid}/prepare-analysis", json={"tool_id": "P0-01"}).json()["plan"]
    assert approve(client, sid, plan)["plan"]["status"] == "completed"
    propose_scope(client, sid, aid, "P0-02", None)
    state = service.load(sid)
    assessment = state["_assessment"]
    assert assessment["admissions"] == []
    rows, bindings = assessment_evidence(service.inputs, state, assessment)
    assert [(row["tool_id"], row["state"]) for row in rows] == [("P0-01", "available")]
    assert len(bindings) == 1
    assert len(state["_tool_runs"]) == 1
    unbound = deepcopy(assessment)
    unbound["scope"]["binding"]["resources"] = {}
    assert assessment_evidence(service.inputs, state, unbound) == ([], {})
    receipt = state["_tool_runs"][0]
    state["_invalidated_receipts"] = {receipt["file"]: {"reason": "input_changed"}}
    assert assessment_evidence(service.inputs, state, assessment) == ([], {})
    service.sessions.save(state)
    fresh = propose_scope(client, sid, aid, "P0-01", None)
    assert fresh["data_view"]["state"] == "not_available"


def test_long_native_explanation_is_rejected_and_resume_gets_safe_feedback(client, tmp_path, monkeypatch):
    import json
    from bridge.web.provider import parse_action, Action
    service, sid, aid = registered_case(client, tmp_path)
    scope = propose_scope(client, sid, aid)
    rejected = "DO_NOT_STORE" + "字" * 2401
    def too_long(*args):
        return parse_action({"content": None, "tool_calls": [{"type": "function", "function": {
            "name": "assessment", "arguments": json.dumps({"decision": {"action": "explain", "text": rejected}})}}]},
            protocol="deepseek_tools")
    monkeypatch.setattr("bridge.web.provider.converse", too_long)
    approve_scope(client, sid, scope)
    first = settle_assessment(client, sid)["_assessment_state"]
    assert first["stop_reason"] == "provider_explanation_too_long"
    assert first["model_turns_used"] == 1 and first["tool_runs_used"] == 0
    assert "DO_NOT_STORE" not in json.dumps(service.load(sid))
    def shortened(settings, messages, context):
        assert context["previous_action_error"] == "provider_explanation_too_long"
        return Action.model_validate({"action":"assessment","decision":{"action":"explain","text":"解释过长，已缩短；尚未运行检查。"}})
    monkeypatch.setattr("bridge.web.provider.converse", shortened)
    response = client.post(f"/api/sessions/{sid}/assessment/resume",
        json={"scope_id": scope["scope_id"], "scope_digest": scope["scope_digest"]})
    assert response.status_code == 200
    done = settle_assessment(client, sid)["_assessment_state"]
    assert done["stop_reason"] == "explanation_complete"
    assert done["model_turns_used"] == 2 and done["tool_runs_used"] == 0
    assert service.load(sid)["_tool_runs"] == []



@pytest.mark.parametrize("protocol", ["json", "deepseek_tools"])
def test_schema_failure_details_preserve_only_declared_paths_and_types(protocol):
    from bridge.web.provider import parse_action, failure_detail
    sentinel = "PRIVATE_KEY_AND_VALUE"
    decision = {"action": "explain", "text": "x" * 2401, "hypotheses": [{
        "statement": sentinel, "evidence_aliases": [sentinel],
        "competing_explanation": sentinel, sentinel: sentinel, "literature_support": [{
            "source_ref": sentinel, "rationale": sentinel, "species": sentinel, "lineage": sentinel,
            "stage": sentinel, "experimental_context": sentinel}]}]}
    message = ({"content": json.dumps({"action": "assessment", "decision": decision})}
        if protocol == "json" else {"content": None, "tool_calls": [{"type": "function",
            "function": {"name": "assessment", "arguments": json.dumps({"decision": decision})}}]})
    with pytest.raises(ValueError) as caught:
        parse_action(message, protocol=protocol)
    detail = failure_detail(caught.value)
    assert detail == {"category": "action_schema", "issues": [
        {"path": "decision.hypotheses[].literature_support[].source_ref", "type": "string_pattern_mismatch"},
        {"path": "decision.hypotheses[].discriminating_check", "type": "missing"},
        {"path": "$", "type": "extra_forbidden"},
        {"path": "decision.text", "type": "string_too_long"}]}
    assert sentinel not in json.dumps(detail)


@pytest.mark.parametrize("failure,expected", [
    ("timeout", {"category": "transport_timeout"}),
    ("network", {"category": "transport_error"}),
    ("http", {"category": "http_status", "status_code": 429}),
    ("envelope", {"category": "response_envelope"}),
    ("json", {"category": "action_json"}),
    ("schema", {"category": "action_schema", "issues": [{"path": "action", "type": "literal_error"}]}),
    ("truncated", {"category": "response_incomplete"}),
    ("empty", {"category": "empty_response"}),
    ("unknown", {"category": "unexpected"}),
    ("result_sharing_disabled", {"category": "result_sharing_disabled"}),
    ("review_context_limit", {"category": "review_context_limit"}),
])
def test_provider_failure_classification_is_private_and_resume_is_explicit(
        client, tmp_path, monkeypatch, failure, expected):
    import httpx
    from bridge.web.provider import Action
    service, sid, aid = registered_case(client, tmp_path)
    service.settings = replace(service.settings, model_action_protocol="json")
    scope = propose_scope(client, sid, aid)
    sentinel = "PRIVATE_PROVIDER_BODY_AND_ID"
    def respond(request):
        if failure in {"result_sharing_disabled", "review_context_limit"}:
            raise ValueError(failure, sentinel)
        if failure == "timeout":
            raise httpx.ReadTimeout(sentinel, request=request)
        if failure == "network":
            raise httpx.ConnectError(sentinel, request=request)
        if failure == "unknown":
            raise RuntimeError(sentinel)
        if failure == "http":
            return httpx.Response(429, text=sentinel)
        if failure == "envelope":
            return httpx.Response(200, json={"choices": [], "private": sentinel})
        content = {"json": sentinel, "schema": json.dumps({"action": sentinel}),
                   "truncated": '{"action":"assessment",', "empty": ""}[failure]
        return httpx.Response(200, json={"choices": [{"finish_reason":
            "length" if failure == "truncated" else "stop", "message": {"content": content}}]})
    original = httpx.Client
    monkeypatch.setattr("bridge.web.provider.httpx.Client",
        lambda **kwargs: original(transport=httpx.MockTransport(respond), **kwargs))
    approve_scope(client, sid, scope)
    first = settle_assessment(client, sid)
    saved = service.load(sid)
    turn = saved["_assessment"]["model_turns"][-1]
    assert turn["provider_error_detail"] == expected
    assert saved["_assessment"]["model_turns_used"] == 1
    assert saved["_assessment"]["tool_runs_used"] == 0
    assert saved["_tool_runs"] == []
    assert sentinel not in json.dumps(saved)
    assert "provider_error_detail" not in json.dumps(first["assessment"])
    seen = []
    def resumed(settings, messages, context):
        seen.append(context)
        return Action.model_validate({"action": "assessment", "decision": {
            "action": "stop", "reason": "no_discriminating_check"}})
    monkeypatch.setattr("bridge.web.provider.converse", resumed)
    response = client.post(f"/api/sessions/{sid}/assessment/resume",
        json={"scope_id": scope["scope_id"], "scope_digest": scope["scope_digest"]})
    assert response.status_code == 200
    done = settle_assessment(client, sid)["_assessment_state"]
    assert seen[0]["previous_action_error_detail"] == expected
    assert sentinel not in json.dumps(seen)
    assert done["model_turns_used"] == 2 and done["tool_runs_used"] == 0


@pytest.mark.parametrize("failure", ["provider_action_invalid_or_unavailable", "invalid_evidence_alias"])
def test_explicit_resume_reports_safe_last_rejection_without_repeating_raw_output(client, tmp_path, monkeypatch, failure):
    from bridge.web.provider import Action, parse_action
    service, sid, aid = registered_case(client, tmp_path)
    scope = propose_scope(client, sid, aid)
    def rejected(*args):
        if failure == "provider_action_invalid_or_unavailable":
            return parse_action({"content": "PRIVATE_REJECTED_RESPONSE"})
        return Action.model_validate({"action": "assessment", "decision": {
            "action": "explain", "text": "Unaccepted explanation.",
            "hypotheses": [{"statement": "Unaccepted interpretation",
                "evidence_aliases": ["PRIVATE_REJECTED_RESPONSE"],
                "competing_explanation": "Unresolved alternative", "discriminating_check": "P0-05"}]}})
    monkeypatch.setattr("bridge.web.provider.converse", rejected)
    approve_scope(client, sid, scope)
    first = settle_assessment(client, sid)["_assessment_state"]
    assert first["stop_reason"] == failure
    assert first["model_turns_used"] == 1 and first["tool_runs_used"] == 0
    assert "PRIVATE_REJECTED_RESPONSE" not in json.dumps(service.load(sid))
    contexts = []
    def corrected(settings, messages, context):
        contexts.append(context)
        return Action.model_validate({"action": "assessment", "decision": {
            "action": "explain", "text": "Evidence remains unresolved; no checks executed."}})
    monkeypatch.setattr("bridge.web.provider.converse", corrected)
    response = client.post(f"/api/sessions/{sid}/assessment/resume",
        json={"scope_id": scope["scope_id"], "scope_digest": scope["scope_digest"]})
    assert response.status_code == 200
    done = settle_assessment(client, sid)["_assessment_state"]
    assert contexts[0].get("previous_action_error") == failure
    assert "PRIVATE_REJECTED_RESPONSE" not in json.dumps(contexts)
    assert done["stop_reason"] == "explanation_complete"
    assert done["model_turns_used"] == 2 and done["tool_runs_used"] == 0
    assert service.load(sid)["_tool_runs"] == []
    response = client.post(f"/api/sessions/{sid}/assessment/resume",
        json={"scope_id": scope["scope_id"], "scope_digest": scope["scope_digest"]})
    assert response.status_code == 200
    done = settle_assessment(client, sid)["_assessment_state"]
    assert "previous_action_error" not in contexts[-1]
    assert done["model_turns_used"] == 3 and done["tool_runs_used"] == 0


@pytest.mark.parametrize("invalid_kind,category", [
    ("support", "support_not_available"),
    ("opposition", "opposition_not_available"),
    ("missing", "missing_not_unavailable"),
    ("overlap", "support_opposition_overlap"),
])
def test_invalid_hypothesis_citations_record_only_safe_detail_for_resume(
        client, tmp_path, monkeypatch, invalid_kind, category):
    from bridge.web.provider import Action, _citation_choices
    service, sid, aid = producer_scientific_case(
        client, tmp_path, monkeypatch, with_producers=False)
    service.settings = replace(service.settings, share_result_summaries=True)
    scope = propose_scope(client, sid, aid, "P0-01", None)

    def invalid(settings, messages, context):
        if not context["evidence"]:
            return Action.model_validate({"action": "assessment", "decision": {
                "action": "check", "option_id": context["options"][0]["id"]}})
        available = _citation_choices(context["evidence"])["evidence_aliases"][0]
        hypothesis = {"statement": "n_observations has evidence_state measured.",
            "evidence_aliases": [available], "opposing_evidence_aliases": [],
            "missing_evidence_aliases": [], "competing_explanation": "An alternative remains.",
            "discriminating_check": None}
        if invalid_kind == "support":
            hypothesis["evidence_aliases"] = ["PRIVATE_REJECTED_ALIAS"]
        elif invalid_kind == "opposition":
            hypothesis["opposing_evidence_aliases"] = ["PRIVATE_REJECTED_ALIAS"]
        elif invalid_kind == "missing":
            hypothesis["missing_evidence_aliases"] = [available]
        else:
            hypothesis["opposing_evidence_aliases"] = [available]
        return Action.model_validate({"action": "assessment", "decision": {
            "action": "explain", "text": "Do not retain this rejected action.",
            "hypotheses": [hypothesis]}})

    monkeypatch.setattr("bridge.web.provider.converse", invalid)
    approve_scope(client, sid, scope)
    rejected = settle_assessment(client, sid)["_assessment_state"]
    assert rejected["status"] == "blocked" and rejected["stop_reason"] == "invalid_evidence_alias"
    state = service.load(sid)
    turn = state["_assessment"]["model_turns"][-1]
    assert turn["state"] == "received" and "decision" not in turn
    assert turn["provider_error_code"] == "invalid_evidence_alias"
    assert turn["provider_error_detail"] == {"category": category, "count": 1}
    assert "PRIVATE_REJECTED_ALIAS" not in json.dumps(state)
    receipts = list(state["_tool_runs"])

    contexts = []
    def corrected(settings, messages, context):
        contexts.append(context)
        return Action.model_validate({"action": "assessment", "decision": {
            "action": "stop", "reason": "no_discriminating_check"}})

    monkeypatch.setattr("bridge.web.provider.converse", corrected)
    response = client.post(f"/api/sessions/{sid}/assessment/resume", json={
        "scope_id": scope["scope_id"], "scope_digest": scope["scope_digest"]})
    assert response.status_code == 200
    settle_assessment(client, sid)
    assert contexts[0]["previous_action_error"] == "invalid_evidence_alias"
    assert contexts[0]["previous_action_error_detail"] == {"category": category, "count": 1}
    assert "PRIVATE_REJECTED_ALIAS" not in json.dumps(contexts[0])
    assert service.load(sid)["_tool_runs"] == receipts

def test_malformed_provider_turn_is_consumed_without_dispatch(client, tmp_path, monkeypatch):
    service, sid, aid = registered_case(client, tmp_path)
    scope = propose_scope(client, sid, aid)
    def malformed(*args):
        from bridge.web.provider import parse_action
        return parse_action({"content": '{"action":"assessment","decision":{"action":"check","option_id":"not-valid"}}'})
    monkeypatch.setattr("bridge.web.provider.converse", malformed)
    approve_scope(client, sid, scope)
    done = settle(client, sid)["_assessment_state"]
    assert done["stop_reason"] == "provider_action_invalid_or_unavailable"
    assert done["model_turns_used"] == 1 and done["tool_runs_used"] == 0
    assert service.load(sid)["_tool_runs"] == []


def test_scope_reports_actual_missing_selection_and_scientific_review_blocker(client, tmp_path):
    from test_web_report_inputs import confirmed_case
    service, sid, aid, _ = confirmed_case(client, tmp_path)
    before = service.load(sid)
    scope = propose_scope(client, sid, aid, "P0-03", "default")
    expected_blockers = ["scientific_resource_required:measurement_spec",
        "scientific_resource_required:target_regional_assessment_spec",
        "state_role_review_required"]
    assert scope["candidates"] == [{"tool_id": "P0-03", "mode_id": "default", "runnable": False, "already_admitted": False,
        "blockers": expected_blockers, "gaps": []}]
    assert scope["blockers"][0]["reason_codes"] == expected_blockers
    after = service.load(sid)
    for key in ("_input_revision", "_input_selections", "_intakes", "_tool_runs"):
        assert after[key] == before[key]
    assert after["_assessment"]["authorization"] is None
    assert "tool_runs_used" not in scope and "model_turns_used" not in scope
    assert after["_assessment"]["tool_runs_used"] == 0
    assert after["_assessment"]["model_turns_used"] == 0
    approve_scope(client, sid, scope)
    done = settle(client, sid)["_assessment_state"]
    assert done["stop_reason"] == "no_eligible_check"
    assert done["blockers"] == [{"tool_id": "P0-03", "mode_id": "default",
                                "reason_codes": expected_blockers}]
    assert done["tool_runs_used"] == done["model_turns_used"] == 0
    assert service.load(sid)["_tool_runs"] == []
    scope = propose_scope(client, sid, aid, "P0-06", "method_runtime")
    approve_scope(client, sid, scope)
    done = settle(client, sid)["_assessment_state"]
    assert done["blockers"][0]["reason_codes"] == ["registered_selection_required"]


def test_disabled_sharing_does_not_send_result_or_private_facts_and_requires_opt_in(client, tmp_path, monkeypatch):
    service, sid, aid = registered_case(client, tmp_path)
    assert service.settings.share_result_summaries is False
    scope = propose_scope(client, sid, aid)
    def model(settings, messages, context):
        from bridge.web.provider import assessment_wire_context
        from model_wire_contract import assert_model_context
        assert_model_context("generation", assessment_wire_context(context), shared=False)
        wire = json.dumps([messages, context])
        for secret in ("PRIVATE_NAME", "PRIVATE_SOURCE", "dopaminergic neurons", "private-cell-a", str(tmp_path)):
            assert secret not in wire
        assert context["evidence"] == [] and context["results_sent_to_model"] is False
        return next_check_or_stop(settings, messages, context)
    monkeypatch.setattr("bridge.web.provider.converse", model)
    approve_scope(client, sid, scope)
    done = settle(client, sid)["_assessment_state"]
    assert done["stop_reason"] == "result_sharing_disabled"
    assert done["tool_runs_used"] == done["model_turns_used"] == 1
    assert done["evidence"][0]["summary"]["primary_denominator"]["n_observations"] == 10


@pytest.mark.parametrize("change", ["revision", "object", "reference"])
def test_scope_fences_drift_before_approval(client, tmp_path, change):
    from pathlib import Path
    from bridge.web.sessions import write_file
    service, sid, aid = registered_case(client, tmp_path)
    scope = propose_scope(client, sid, aid)
    state = service.load(sid)
    if change == "revision":
        state["_input_revision"] += 1
        service.sessions.save(state)
    elif change == "reference":
        service.settings = replace(service.settings, cell_state_measurement_spec_ref=None)
    else:
        resource_id = next(iter(state["_assessment"]["scope"]["binding"]["resources"]))
        record = state["_input_objects"][resource_id]
        path = Path(record["path"])
        write_file(path, path.read_bytes() + b" ")
    response = client.post(f"/api/sessions/{sid}/assessment/approve", json={
        "scope_id": scope["scope_id"], "scope_digest": scope["scope_digest"]})
    assert response.status_code == 409
    assert "detail" not in response.json()
    assert service.assessment.check(service.load(sid)) in {
        "input_revision_changed", "scope_resource_changed",
    }
    assert service.load(sid)["_tool_runs"] == []


def test_stop_and_resume_keep_original_consent_and_dispatched_model_counter(client, tmp_path, monkeypatch):
    from threading import Event
    entered, released = Event(), Event()
    service, sid, aid = registered_case(client, tmp_path)
    scope = propose_scope(client, sid, aid)
    def slow(settings, messages, context):
        entered.set()
        assert released.wait(10)
        return next_check_or_stop(settings, messages, context)
    monkeypatch.setattr("bridge.web.provider.converse", slow)
    approve_scope(client, sid, scope)
    assert entered.wait(5)
    before = service.load(sid)["_assessment"]
    assert before["model_turns_used"] == 1 and before["tool_runs_used"] == 0
    try:
        stopped = client.post(f"/api/sessions/{sid}/stop", json={})
        assert stopped.status_code == 200
        assert "stop_reason" not in stopped.json()["assessment"]
        assert service.load(sid)["_assessment"]["stop_reason"] == "user_stopped"
    finally:
        released.set()
    done = settle(client, sid)
    assert done["_assessment_state"]["status"] == "stopped"
    assert service.load(sid)["_tool_runs"] == []
    monkeypatch.setattr("bridge.web.provider.converse", next_check_or_stop)
    resumed = client.post(f"/api/sessions/{sid}/assessment/resume", json={
        "scope_id": scope["scope_id"], "scope_digest": scope["scope_digest"]})
    assert resumed.status_code == 200
    done = settle(client, sid)
    after = service.load(sid)["_assessment"]
    assert after["authorization"] == before["authorization"]
    assert after["model_turns_used"] == 2 and after["tool_runs_used"] == 1


def test_provider_native_and_json_assessment_have_same_purpose_limited_action():
    from bridge.web.provider import action_tools, parse_action
    payload = {"decision": {"action": "stop", "reason": "no_discriminating_check"}}
    json_action = parse_action({"content": json.dumps({"action": "assessment", **payload})})
    native_action = parse_action({"content": None, "tool_calls": [{
        "type": "function", "function": {"name": "assessment", "arguments": json.dumps(payload)}}]},
        protocol="deepseek_tools")
    assert json_action == native_action
    assert [row["function"]["name"] for row in action_tools("assessment")] == ["assessment"]
    assert "assessment" not in [row["function"]["name"] for row in action_tools()]
    with pytest.raises(ValueError):
        parse_action({"content": '{"action":"assessment","decision":{"action":"check","option_id":"' + "0" * 64 + '","value":0.9}}'})


@pytest.mark.parametrize("action", ["check", "query", "question", "stop"])
def test_only_explain_can_carry_hypotheses_in_model_and_native_schema(action):
    from jsonschema import Draft202012Validator
    from bridge.web.provider import AssessmentDecision, action_tools

    hypothesis = {
        "statement": "A proposed interpretation.",
        "evidence_aliases": ["E-current"],
        "competing_explanation": "An alternative remains possible.",
        "discriminating_check": None,
    }
    decision = {"action": action, "hypotheses": [hypothesis]}
    if action in {"check", "query"}:
        decision["option_id"] = "a" * 64
    elif action == "question":
        decision["text"] = "Which consequential fact is missing?"
    else:
        decision["reason"] = "no_discriminating_check"

    with pytest.raises(ValueError):
        AssessmentDecision.model_validate(decision)

    parameters = action_tools("assessment", assessment_evidence=[{
        "citation_alias": "E-current", "citation_role": "support",
    }])[0]["function"]["parameters"]
    Draft202012Validator.check_schema(parameters)
    assert not Draft202012Validator(parameters).is_valid({"decision": decision})


@pytest.mark.parametrize("decision,valid", [
    ({"action": "check", "option_id": "a" * 64}, True),
    ({"action": "query", "option_id": "a" * 64, "text": None}, True),
    ({"action": "question", "text": "Which sample is being assessed?"}, True),
    ({"action": "explain", "text": "The required measurement is unavailable."}, True),
    ({"action": "stop", "reason": "no_discriminating_check"}, True),
    ({"action": "check"}, False),
    ({"action": "query", "option_id": "a" * 64, "text": "Run this."}, False),
    ({"action": "check", "option_id": "a" * 64, "reason": "necessary_fact_required"}, False),
    ({"action": "question", "text": None}, False),
    ({"action": "question", "text": "Which sample?", "option_id": "a" * 64}, False),
    ({"action": "explain", "hypotheses": []}, False),
    ({"action": "explain", "text": "A limitation.", "reason": "no_discriminating_check"}, False),
    ({"action": "stop", "reason": None}, False),
    ({"action": "stop", "reason": "no_discriminating_check", "text": "Done."}, False),
])
def test_outbound_decision_schemas_match_action_field_constraints(decision, valid):
    """A model following the wire schema must not hit a hidden action-shape rule."""
    from jsonschema import Draft202012Validator
    from bridge.web.provider import AssessmentDecision, action_tools

    json_schema = AssessmentDecision.model_json_schema()
    native_schema = action_tools("assessment")[0]["function"]["parameters"]
    assert Draft202012Validator(json_schema).is_valid(decision) is valid
    assert Draft202012Validator(native_schema).is_valid({"decision": decision}) is valid
    if valid:
        AssessmentDecision.model_validate(decision)
    else:
        with pytest.raises(ValueError):
            AssessmentDecision.model_validate(decision)


def test_unattributed_explanation_cannot_claim_a_hypothesis(client, tmp_path, monkeypatch):
    service, sid, aid = registered_case(client, tmp_path)
    scope = propose_scope(client, sid, aid)
    def unsupported(*args):
        from bridge.web.provider import Action
        return Action.model_validate({"action": "assessment", "decision": {
            "action": "explain", "text": "Target identity is established.",
            "hypotheses": [{"statement": "Target identity is established", "evidence_aliases": ["E-invented"],
                "competing_explanation": "Off-target mixture", "discriminating_check": "P0-05"}]}})
    monkeypatch.setattr("bridge.web.provider.converse", unsupported)
    approve_scope(client, sid, scope)
    done = settle(client, sid)["_assessment_state"]
    assert done["stop_reason"] == "invalid_evidence_alias"
    assert service.load(sid)["_tool_runs"] == []


def test_assessment_causal_text_is_retained_only_as_a_proposed_explanation(
        client, tmp_path, monkeypatch):
    from bridge.web.provider import Action, _citation_choices
    service, sid, aid = producer_scientific_case(
        client, tmp_path, monkeypatch, with_producers=False)
    service.settings = replace(service.settings, share_result_summaries=True)
    scope = propose_scope(client, sid, aid, "P0-01", None)
    proposed_text = "主要差异可能来自技术混杂；这仍是待检验解释。"

    def proposed(settings, messages, context):
        if context["options"]:
            return Action.model_validate({"action": "assessment", "decision": {
                "action": "check", "option_id": context["options"][0]["id"]}})
        alias = _citation_choices(context["evidence"])["evidence_aliases"][0]
        return Action.model_validate({"action": "assessment", "decision": {
            "action": "explain", "text": f"{proposed_text} [{alias}]",
            "hypotheses": [{
                "statement": proposed_text,
                "evidence_aliases": [alias],
                "competing_explanation": "另一个未测量机制仍可能存在。",
                "discriminating_check": None,
            }]}})

    monkeypatch.setattr("bridge.web.provider.converse", proposed)
    approve_scope(client, sid, scope)
    done = settle_assessment(client, sid)["_assessment_state"]
    state = service.load(sid)

    assert done["status"] == "stopped"
    assert done["stop_reason"] == "explanation_complete"
    version = state["_assessment"]["interpretation_versions"][-1]
    message = state["messages"][-1]
    assert version["qualification"] == "proposed_explanation"
    assert message["qualification"] == "proposed_explanation"
    assert version["hypotheses"][0]["statement"] == proposed_text
    assert "verified" not in version and "scientific_validation" not in version


@pytest.mark.parametrize("failure", ["statement", "competing_explanation", "expected_observation"])
def test_rejected_assessment_text_has_precise_private_resume_feedback(
        client, tmp_path, monkeypatch, failure):
    from bridge.web.provider import Action, _citation_choices
    service, sid, aid = producer_scientific_case(
        client, tmp_path, monkeypatch, with_producers=False)
    service.settings = replace(service.settings, share_result_summaries=True)
    scope = propose_scope(client, sid, aid, "P0-01", None)

    def cited_competing_explanation(settings, messages, context):
        if context["options"]:
            return Action.model_validate({"action": "assessment", "decision": {
                "action": "check", "option_id": context["options"][0]["id"]}})
        alias = _citation_choices(context["evidence"])["evidence_aliases"][0]
        record = next(item for evidence in context["evidence"]
            for item in evidence.get("measurements", [])
            if item.get("citation_alias") == alias)
        statement = f"{record['metric_name']} 的 evidence_state 为 {record['evidence_state']}。"
        hypothesis = {
                "statement": statement,
                "evidence_aliases": [alias],
                "competing_explanation": "An alternative remains unresolved.",
                "expected_observation": "A future test may distinguish the alternative.",
                "discriminating_check": None,
        }
        text = f"{statement} [{alias}]"
        hypothesis[failure] = f"PRIVATE_REJECTED_TEXT [{alias}]"
        return Action.model_validate({"action": "assessment", "decision": {
            "action": "explain", "text": text, "hypotheses": [hypothesis]}})

    monkeypatch.setattr("bridge.web.provider.converse", cited_competing_explanation)
    approve_scope(client, sid, scope)
    done = settle_assessment(client, sid)["_assessment_state"]
    state = service.load(sid)

    assert done["status"] == "blocked"
    assert done["stop_reason"] == "provider_action_invalid_or_unavailable"
    assert done.get("interpretation_versions", []) == []
    assert done.get("hypotheses", []) == []
    assert "decision" not in state["_assessment"]["model_turns"][-1]
    expected = {"category": "hypothesis_text_citations", "fields": {failure: 1}}
    assert state["_assessment"]["model_turns"][-1]["provider_error_detail"] == expected
    assert "PRIVATE_REJECTED_TEXT" not in json.dumps(state)
    assert "E-PRIVATE-REJECTED-TEXT" not in json.dumps(state)
    receipts = list(state["_tool_runs"])
    contexts = []
    def corrected(settings, messages, context):
        contexts.append(context)
        return Action.model_validate({"action": "assessment", "decision": {
            "action": "stop", "reason": "no_discriminating_check"}})
    monkeypatch.setattr("bridge.web.provider.converse", corrected)
    response = client.post(f"/api/sessions/{sid}/assessment/resume", json={
        "scope_id": scope["scope_id"], "scope_digest": scope["scope_digest"]})
    assert response.status_code == 200
    resumed = settle_assessment(client, sid)["_assessment_state"]
    assert contexts[0]["previous_action_error"] == "provider_text_unverified"
    assert contexts[0]["previous_action_error_detail"] == expected
    assert resumed["model_turns_used"] == done["model_turns_used"] + 1
    assert service.load(sid)["_tool_runs"] == receipts


def test_assessment_question_cannot_embed_unbound_evidence_citations(
        client, tmp_path, monkeypatch):
    from bridge.web.provider import Action
    service, sid, aid = registered_case(client, tmp_path)
    scope = propose_scope(client, sid, aid)
    rejected_text = "请解释这个结果 [E-PRIVATE-REJECTED-QUESTION]。"
    monkeypatch.setattr("bridge.web.provider.converse", lambda *args: Action.model_validate({
        "action": "assessment", "decision": {"action": "question", "text": rejected_text}}))

    approve_scope(client, sid, scope)
    done = settle_assessment(client, sid)["_assessment_state"]
    state = service.load(sid)

    assert done["status"] == "blocked"
    assert done["stop_reason"] == "provider_action_invalid_or_unavailable"
    assert "decision" not in state["_assessment"]["model_turns"][-1]
    assert rejected_text not in json.dumps(state, ensure_ascii=False)
    assert service.load(sid)["_tool_runs"] == []
    assert state["_assessment"]["model_turns"][-1]["provider_error_detail"] == {
        "category": "question_text_unverified"}


@pytest.mark.parametrize("prose", [None, "UNBOUND_PRIVATE_PROSE [E-invented]"])
def test_admitted_assessment_explanation_binds_message_and_report_version_to_same_records(
        client, tmp_path, monkeypatch, prose):
    from bridge.web.provider import Action, _citation_choices
    service, sid, aid = producer_scientific_case(
        client, tmp_path, monkeypatch, with_producers=False)
    service.settings = replace(service.settings, share_result_summaries=True)
    scope = propose_scope(client, sid, aid, "P0-01", None)
    provider_aliases = []
    provider_records = []

    def supported(settings, messages, context):
        if context["options"]:
            return Action.model_validate({"action": "assessment", "decision": {
                "action": "check", "option_id": context["options"][0]["id"]}})
        alias = _citation_choices(context["evidence"])["evidence_aliases"][0]
        provider_aliases.append(alias)
        provider_records.extend(item for evidence in context["evidence"]
            for item in evidence["measurements"]
            if isinstance(item.get("metric_name"), str)
            and item.get("evidence_state") == "measured")
        if not provider_records:
            return Action.model_validate({"action": "assessment", "decision": {
                "action": "stop", "reason": "no_discriminating_check"}})
        measurement = provider_records[0]
        statement = f"{measurement['metric_name']} 的 evidence_state 为 measured。"
        return Action.model_validate({"action": "assessment", "decision": {
            "action": "explain", "text": prose,
            "hypotheses": [{
                "statement": statement,
                "evidence_aliases": [alias],
                "competing_explanation": "其他尚未测量的机制仍可能存在。",
                "discriminating_check": None,
            }]}})

    monkeypatch.setattr("bridge.web.provider.converse", supported)
    approve_scope(client, sid, scope)
    done = settle_assessment(client, sid)["_assessment_state"]
    state = service.load(sid)

    assert provider_records, done["evidence"][0]["measurements"]
    assert done["status"] == "stopped", (done["status"], done["stop_reason"])
    assert done["stop_reason"] == "explanation_complete", done["stop_reason"]
    version = state["_assessment"]["interpretation_versions"][-1]
    message = state["messages"][-1]
    stable_refs = version["hypotheses"][0]["evidence_aliases"]
    assert stable_refs and all(ref.endswith("@1") for ref in stable_refs)
    assert message["source"] == "provider_admitted"
    assert message["qualification"] == "proposed_explanation"
    assert message["evidence_refs"] == stable_refs
    assert version["hypotheses"][0]["statement"] in message["content"]
    assert all(ref in message["content"] for ref in stable_refs)
    assert "UNBOUND_PRIVATE_PROSE" not in json.dumps(state)
    assert "E-invented" not in json.dumps(state)
    assert message["interpretation_ref"] == {
        "scope_digest": version["scope_digest"],
        "version": version["version"],
        "content_sha256": version["content_sha256"],
    }
    admitted_state = json.dumps({
        "message": message,
        "decision": state["_assessment"]["model_turns"][-1]["decision"],
        "version": version,
    }, ensure_ascii=False)
    assert provider_aliases[0] not in admitted_state
    assert state["_assessment"]["model_turns"][-1]["decision"]["hypotheses"][0][
        "evidence_aliases"] == stable_refs
    assert state["_assessment"]["model_turns"][-1]["decision"]["text"] == message["content"]


def test_report_handoff_accepts_the_same_record_bound_version_and_rejects_missing_as_support():
    from types import SimpleNamespace
    from bridge.web.assessment import AssessmentCoordinator
    from bridge.web.scientific_inputs import digest
    from bridge.tool_packages.p0_10_claim_verifier.research import seal_research_context

    receipt_sha = "c" * 64
    graph_sha = "b" * 64
    evidence_alias = "E-" + receipt_sha[:16]
    measurement_alias = "M-observations"
    stable_ref = f"{evidence_alias}#measurement:{measurement_alias}@1"
    evidence = [{
        "alias": evidence_alias, "state": "available", "tool_id": "P0-01",
        "summary": {}, "measurements": [{
            "alias": measurement_alias, "metric_name": "n_observations",
            "raw_value": 4, "unit": "observations", "evidence_state": "measured"}],
    }]
    scope_digest = "a" * 64

    def version_for(rows, discriminating_check=None):
        content = {
            "object_version": "1.0.0", "scope_digest": scope_digest,
            "input_revision": 7, "hypotheses": [{
                "statement": "n_observations has evidence_state measured.",
                "evidence_aliases": [stable_ref], "opposing_evidence_aliases": [],
                "missing_evidence_aliases": [], "expected_observation": None,
                "competing_explanation": "Another unmeasured mechanism remains possible.",
                "discriminating_check": discriminating_check,
            }],
            "evidence_snapshot_sha256": digest(rows),
            "qualification": "proposed_explanation",
        }
        return {**content, "version": 1, "content_sha256": digest(content),
            "predecessor_sha256": None, "created_at": "2026-09-22T00:00:00Z"}

    version = version_for(evidence)
    context = seal_research_context({
        "context_id": "research-context:synthetic-handoff",
        "input_revision": "7", "graph_id": "case-graph:synthetic",
        "graph_version": 1, "graph_manifest_sha256": graph_sha,
        "product_case_ref": {"object_id": "product-case:synthetic", "object_version": "0.1.0"},
        "confirmed_product_facts": {}, "intake_source_ref": "source:intake",
        "data_view": {"view_id": "data-view:synthetic", "view_kind": "all_observations",
            "artifact_id": "artifact:synthetic", "sha256": "d" * 64,
            "parent_asset_id": "asset:synthetic", "parent_asset_sha256": "e" * 64,
            "matrix_location": "X", "matrix_semantics": "raw_counts", "n_observations": 4,
            "observation_ids_sha256": "f" * 64},
        "data_view_source_ref": "source:view",
        "sources": [
            {"source_ref": "source:intake", "schema_ref": "bridge://schemas/intake/v0.1",
             "sha256": "1" * 64},
            {"source_ref": "source:view", "schema_ref": "bridge://schemas/data-view/v0.1",
             "sha256": "2" * 64},
        ],
        "explanation_versions": [version],
    }).model_dump(mode="json")

    class Inputs:
        @staticmethod
        def verify(state, record):
            return record["payload"]

    coordinator = AssessmentCoordinator(SimpleNamespace(inputs=Inputs()))
    graph_ref = SimpleNamespace(role="evidence_graph_manifest", input_id="graph", sha256=graph_sha)
    context_ref = SimpleNamespace(role="research_report_context", input_id="context", sha256=context["context_sha256"])
    report = {"tool_id": "P0-10", "mode_id": "default",
        "request": SimpleNamespace(object_inputs=[graph_ref, context_ref])}
    state = {"_input_objects": {
            "graph": {"sha256": graph_sha, "receipt_file": "graph.json",
                      "receipt_sha256": receipt_sha},
            "context": {"payload": context},
        },
        "_tool_runs": [{"file": "graph.json", "sha256": receipt_sha,
                        "tool_id": "P0-09", "state": "succeeded"}],
    }
    assessment = {"scope_digest": scope_digest, "model_turns_used": 2, "tool_runs_used": 2,
        "stop_events": [{"reason": "explanation_complete", "model_turns_used": 2,
                         "tool_runs_used": 2}],
        "model_turns": [{"number": 2, "state": "received", "decision": {"action": "explain"}}],
        "interpretation_versions": [version],
        "admissions": [{"plan_id": "graph-plan", "tool_id": "P0-09",
                        "mode_id": "case_append_v2", "state": "completed"}]}
    scope = SimpleNamespace(report_after_explanation=True, input_revision=7,
        allowed_modes=[SimpleNamespace(tool_id="P0-01"), SimpleNamespace(tool_id="P0-10")])

    selected, error = coordinator._report_resume_candidate(
        state, assessment, scope, {"report": report}, evidence)
    assert selected is report and error is None

    graph_check = version_for(evidence, "P0-09")
    assessment["interpretation_versions"] = [graph_check]
    state["_input_objects"]["context"]["payload"] = seal_research_context({
        **{key: value for key, value in context.items() if key != "context_sha256"},
        "explanation_versions": [graph_check],
    }).model_dump(mode="json")
    scope.allowed_modes.append(SimpleNamespace(tool_id="P0-09"))
    selected, error = coordinator._report_resume_candidate(
        state, assessment, scope, {"report": report}, evidence)
    assert selected is None and error == "report_handoff_stale"

    missing = json.loads(json.dumps(evidence))
    missing[0]["measurements"][0].update(raw_value=None, evidence_state="unknown")
    assessment["interpretation_versions"] = [version_for(missing)]
    selected, error = coordinator._report_resume_candidate(
        state, assessment, scope, {"report": report}, missing)
    assert selected is None and error == "report_handoff_stale"


    # A real observation plus a bound limitation can hand off; gaps alone cannot.
    mixed = json.loads(json.dumps(evidence))
    mixed[0]["measurements"].append({"alias": "M-missing", "metric_name": "program_unavailable",
        "raw_value": None, "unit": "score", "evidence_state": "unavailable"})
    gap = {"statement": "The program cannot be estimated in this run.", "evidence_aliases": [],
        "opposing_evidence_aliases": [], "missing_evidence_aliases": [f"{evidence_alias}#measurement:M-missing@1"],
        "expected_observation": None, "competing_explanation": "This is not a negative signal.",
        "discriminating_check": None}
    for gaps_only in (False, True):
        updated = version_for(mixed)
        updated["hypotheses"] = ([gap] if gaps_only else updated["hypotheses"] + [gap])
        updated["content_sha256"] = digest({key: value for key, value in updated.items()
            if key not in {"version", "content_sha256", "predecessor_sha256", "created_at"}})
        assessment["interpretation_versions"] = [updated]
        state["_input_objects"]["context"]["payload"] = seal_research_context({
            **{key: value for key, value in context.items() if key != "context_sha256"},
            "explanation_versions": [updated]}).model_dump(mode="json")
        selected, error = coordinator._report_resume_candidate(
            state, assessment, scope, {"report": report}, mixed)
        assert (selected, error) == ((None, "report_handoff_stale") if gaps_only else (report, None))


def test_nonnull_discriminating_check_remains_bound_to_approved_scope(client, tmp_path, monkeypatch):
    from bridge.web.provider import Action, _citation_choices
    service, sid, aid = producer_scientific_case(
        client, tmp_path, monkeypatch, with_producers=False)
    service.settings = replace(service.settings, share_result_summaries=True)
    scope = propose_scope(client, sid, aid, "P0-01", None)

    def outside_scope(settings, messages, context):
        if not context["evidence"]:
            return Action.model_validate({"action": "assessment", "decision": {
                "action": "check", "option_id": context["options"][0]["id"]}})
        available = _citation_choices(context["evidence"])["evidence_aliases"][0]
        return Action.model_validate({"action": "assessment", "decision": {
            "action": "explain", "text": f"n_observations has evidence_state measured. [{available}]",
            "hypotheses": [{"statement": "n_observations has evidence_state measured.",
                "evidence_aliases": [available], "competing_explanation": "A biological cause remains.",
                "discriminating_check": "P0-06"}]}})

    monkeypatch.setattr("bridge.web.provider.converse", outside_scope)
    approve_scope(client, sid, scope)
    done = settle_assessment(client, sid)["_assessment_state"]
    assert done["status"] == "blocked" and done["stop_reason"] == "hypothesis_check_outside_scope"
    assert done["tool_runs_used"] == 1 and done["model_turns_used"] == 2
    assert done.get("interpretation_versions", []) == []
    assert [row["tool_id"] for row in service.load(sid)["_tool_runs"]] == ["P0-01"]


def test_approved_graph_query_is_not_a_scientific_discriminating_check(client, tmp_path, monkeypatch):
    from bridge.web.provider import Action, _citation_choices
    service, sid, aid = producer_scientific_case(
        client, tmp_path, monkeypatch, with_producers=False)
    service.settings = replace(service.settings, share_result_summaries=True)
    scope = propose_scope(client, sid, aid, "P0-01", None,
        allowed_modes=[{"tool_id": "P0-01", "mode_id": None},
                       {"tool_id": "P0-09", "mode_id": "case_query"}])

    def graph_as_check(settings, messages, context):
        if not context["evidence"]:
            return Action.model_validate({"action": "assessment", "decision": {
                "action": "check", "option_id": context["options"][0]["id"]}})
        citation = _citation_choices(context["evidence"])["evidence_aliases"][0]
        return Action.model_validate({"action": "assessment", "decision": {
            "action": "explain", "hypotheses": [{
                "statement": "An observed QC signal is present.",
                "evidence_aliases": [citation],
                "competing_explanation": "A technical effect remains possible.",
                "discriminating_check": "P0-09"}]}})

    monkeypatch.setattr("bridge.web.provider.converse", graph_as_check)
    approve_scope(client, sid, scope)
    done = settle_assessment(client, sid)["_assessment_state"]
    assert done["status"] == "blocked" and done["stop_reason"] == "hypothesis_check_outside_scope"
    assert [row["tool_id"] for row in service.load(sid)["_tool_runs"]] == ["P0-01"]


@pytest.mark.parametrize("uncited_hypotheses", [
    pytest.param(None, id="missing"),
    pytest.param([], id="empty"),
])
def test_evidence_backed_explanation_requires_structured_hypothesis_citations(
        client, tmp_path, monkeypatch, uncited_hypotheses):
    service, sid, aid = producer_scientific_case(
        client, tmp_path, monkeypatch, with_producers=False)
    service.settings = replace(service.settings, share_result_summaries=True)
    scope = propose_scope(client, sid, aid, "P0-01", None)

    def uncited(settings, messages, context):
        from bridge.web.provider import Action
        if not context["evidence"]:
            return Action.model_validate({"action": "assessment", "decision": {
                "action": "check", "option_id": context["options"][0]["id"]}})
        decision = {"action": "explain", "text": "The result supports a candidate interpretation."}
        if uncited_hypotheses is not None:
            decision["hypotheses"] = uncited_hypotheses
        return Action.model_validate({"action": "assessment", "decision": decision})

    monkeypatch.setattr("bridge.web.provider.converse", uncited)
    approve_scope(client, sid, scope)
    rejected = settle_assessment(client, sid)["_assessment_state"]
    assert rejected["status"] == "blocked"
    assert rejected["stop_reason"] == "provider_action_invalid_or_unavailable"
    state = service.load(sid)
    original_authorization = state["_assessment"]["authorization"]
    original_receipts = state["_tool_runs"]
    assert state["_assessment"]["tool_runs_used"] == 1
    assert state["_assessment"]["model_turns_used"] == 2
    assert state["_assessment"]["stop_events"][-1]["reason"] == "provider_action_invalid_or_unavailable"
    assert len(state["_tool_runs"]) == 1
    assert state["_assessment"].get("interpretation_versions", []) == []
    assert state["_assessment"]["model_turns"][-1]["provider_error_code"] == "structured_hypotheses_required"

    contexts = []

    def cited(settings, messages, context):
        from bridge.web.provider import Action, _citation_choices
        contexts.append(context)
        alias = _citation_choices(context["evidence"])["evidence_aliases"][0]
        record = next(item for evidence in context["evidence"]
            for item in evidence.get("measurements", []) if item.get("citation_alias") == alias)
        statement = f"{record['metric_name']} 的 evidence_state 为 {record['evidence_state']}。"
        return Action.model_validate({"action": "assessment", "decision": {
            "action": "explain", "text": f"{statement} [{alias}]",
            "hypotheses": [{
                "statement": statement,
                "evidence_aliases": [alias],
                "competing_explanation": "The same result may reflect an unresolved off-target signal.",
                "discriminating_check": None,
            }]}})

    monkeypatch.setattr("bridge.web.provider.converse", cited)
    response = client.post(f"/api/sessions/{sid}/assessment/resume", json={
        "scope_id": scope["scope_id"], "scope_digest": scope["scope_digest"]})
    assert response.status_code == 200
    completed = settle_assessment(client, sid)["_assessment_state"]
    assert contexts[0]["previous_action_error"] == "structured_hypotheses_required"
    assert completed["status"] == "stopped" and completed["stop_reason"] == "explanation_complete"
    assert len(completed["hypotheses"]) == 1
    assert completed["interpretation_versions"][-1]["hypotheses"] == completed["hypotheses"]
    state = service.load(sid)
    assert state["_tool_runs"] == original_receipts
    assert state["_assessment"]["authorization"] == original_authorization
    assert state["_assessment"]["tool_runs_used"] == 1
    assert state["_assessment"]["model_turns_used"] == 3
    assert [row["reason"] for row in state["_assessment"]["stop_events"][-2:]] == [
        "provider_action_invalid_or_unavailable", "explanation_complete"]


@pytest.mark.parametrize("requested_reason,expected_reason,expected_status,historical", [
    pytest.param("no_discriminating_check", "no_discriminating_check", "stopped", False, id="read_only_query"),
    pytest.param("no_discriminating_check", "no_discriminating_check", "stopped", True, id="baseline_receipt"),
    pytest.param("evidence_requirements_reached", "completion_contract_unavailable", "blocked", False,
                 id="open_requirements_completion_requested"),
])
def test_registered_graph_query_reuses_version_and_has_receipt_without_new_artifacts(
        client, tmp_path, monkeypatch, requested_reason, expected_reason, expected_status, historical):
    from test_web_report_inputs import confirmed_case, run_stage
    service, sid, aid, body = confirmed_case(client, tmp_path)
    run_stage(client, sid, body, "P0-08")
    if historical:
        # Real registered producer, using the exact supported pre-upgrade contract.
        # No receipt, graph, measurement or artifact is rewritten after production.
        module = importlib.import_module("bridge.tool_packages.p0_09_evidence_compiler.adapter")
        legacy = service.registry.describe("P0-09").model_copy(update={
            "version": "0.4.2", "result_schema_ref": "bridge://schemas/evidence-compiler-run-result/v0.1"})
        with monkeypatch.context() as legacy_contract:
            legacy_contract.setitem(service.registry._specs, "P0-09", legacy)
            legacy_contract.setattr(module, "RESULT_SCHEMA_REF", legacy.result_schema_ref)
            legacy_contract.setattr(type(service.registry), "load_default", classmethod(lambda cls: service.registry))
            run_stage(client, sid, body, "P0-09")
    else:
        run_stage(client, sid, body, "P0-09")
    state = service.load(sid)
    original_receipts = {row["file"]: (service.directory(sid) / "receipts" / row["file"]).read_bytes()
                         for row in state["_tool_runs"]}
    if historical:
        from bridge.toolkit.contracts import ToolRunV2
        old_run = ToolRunV2.model_validate_json(original_receipts[state["_tool_runs"][-1]["file"]])
        assert old_run.tool_version == "0.4.2"
        assert old_run.result_schema_ref == "bridge://schemas/evidence-compiler-run-result/v0.1"
        with pytest.raises(ValueError, match="mismatched tool version"):
            service.registry.validate_result(old_run, old_run.request)
        for update in ({"tool_version": "0.4.1"}, {"environment_spec_id": "ENV-WRONG"}, {"result": {}}):
            with pytest.raises(ValueError):
                service.registry.validate_historical_result(old_run.model_copy(update=update), old_run.request)
        wrong_request = old_run.request.model_copy(update={"request_id": "different-request"})
        with pytest.raises(ValueError, match="mismatched tool or request"):
            service.registry.validate_historical_result(old_run, wrong_request)
    from pathlib import Path
    original_artifacts = {item["path"]: Path(item["path"]).read_bytes()
                          for raw_receipt in original_receipts.values()
                          for item in json.loads(raw_receipt)["artifacts"]}
    graph_id, graph_record = next((identifier, row) for identifier, row in state["_input_objects"].items()
        if row["source"] == "tool_output" and row["schema_ref"] == "bridge://schemas/case-evidence-graph-manifest/v0.1")
    graph = service.inputs.verify(state, graph_record)
    query = {"object_version": "0.1.0", "query_name": "get_case_evidence_subgraph",
             "product_case_id": graph["product_case_ref"]["object_id"],
             "evidence_tiers": ["formal", "shadow", "exploratory"], "max_depth": 2, "max_nodes": 100}
    response = client.post(f"/api/sessions/{sid}/analysis-inputs/objects",
        params={"tool_id": "P0-09", "mode_id": "case_query", "role": "evidence_graph_query",
                "schema_ref": "bridge://schemas/evidence-graph-query/v0.1", "object_version": "0.1.0"},
        files={"file": ("query.json", json.dumps(query).encode(), "application/json")})
    assert response.status_code == 200, response.json()
    state = service.load(sid)
    query_id = next(reversed(state["_input_objects"]))
    selected = client.post(f"/api/sessions/{sid}/analysis-inputs", json=choice("P0-09", "case_query", [
        {"role": "evidence_graph_manifest", "input_id": graph_id},
        {"role": "evidence_graph_query", "input_id": query_id}]))
    assert selected.status_code == 200
    from web_support import confirm_change
    if selected.json()["pending_input_change"]:
        confirm_change(client, sid, selected.json())
    service.settings = replace(service.settings, share_result_summaries=True)
    scope = propose_scope(client, sid, aid, "P0-09", "case_query")
    before = service.load(sid)
    def query_then_stop(settings, messages, context):
        from bridge.web.provider import Action
        if context["options"]:
            assert context["options"][0]["kind"] == "query"
            return Action.model_validate({"action": "assessment", "decision": {
                "action": "query", "option_id": context["options"][0]["id"]}})
        assert context["evidence"][0]["summary"]["graph_version"] == 1
        wire = json.dumps(context)
        from bridge.web.evidence import assessment_evidence
        current = service.load(sid)
        local, _ = assessment_evidence(service.inputs, current, current["_assessment"])
        for row in local:
            assert row["alias"] not in wire
            if "query_name" not in row["summary"]:
                continue
            assert row["summary"]["graph_alias"] not in wire
            for node in row["summary"]["nodes"]:
                assert node["alias"] not in wire
            for private in row["provenance"].values():
                if isinstance(private, str):
                    assert private not in wire
        requirements = expanded_model_rows(context["evidence"][0]["summary"], "requirements")
        assert len(requirements) == 5
        assert all(item["state"] == "open" for item in requirements)
        return Action.model_validate({"action": "assessment", "decision": {
            "action": "stop", "reason": requested_reason}})
    monkeypatch.setattr("bridge.web.provider.converse", query_then_stop)
    approve_scope(client, sid, scope)
    done = settle(client, sid)
    assert done["_assessment_state"]["stop_reason"] == expected_reason, done["_assessment_state"]
    assert done["_assessment_state"]["status"] == expected_status
    assert done["_assessment_state"]["tool_runs_used"] == 1
    assert done["_assessment_state"]["evidence"][0]["summary"]["graph_version"] == 1
    assert len(done["_assessment_state"]["evidence"][0]["summary"]["requirements"]) == 5
    assert all(row["state"] == "open" for row in done["_assessment_state"]["evidence"][0]["summary"]["requirements"])
    after = service.load(sid)
    assert after["_input_revision"] == before["_input_revision"]
    assert len(after["_tool_runs"]) == len(before["_tool_runs"]) + 1
    assert after["_input_objects"] == before["_input_objects"]
    assert after["_artifacts"] == before["_artifacts"]
    assert after["_assessment"]["model_turns"][-1]["decision"]["reason"] == requested_reason
    assert all((service.directory(sid) / "receipts" / name).read_bytes() == data
               for name, data in original_receipts.items())
    assert all(Path(path).read_bytes() == data for path, data in original_artifacts.items())
    assert "evidence_requirements_reached" not in json.dumps(done["assessment"])
    receipt = json.loads((service.directory(sid) / "receipts" / after["_tool_runs"][-1]["file"]).read_bytes())
    assert receipt["artifacts"] == [] and receipt["measurements"] == []
    assert receipt["result"]["graph_id"] == graph["graph_id"]
    assert receipt["result"]["graph_version"] == 1
    local = done["_assessment_state"]["evidence"][0]
    assert local["artifact_ids"]
    assert local["provenance"]["source_receipt_sha256"] == graph_record["receipt_sha256"]
    assert local["provenance"]["graph_version"] == 1
    for identifier in local["artifact_ids"]:
        assert after["_canonical_artifacts"][identifier]["receipt_sha256"] == graph_record["receipt_sha256"]
    # A different run, even from the same tool, cannot acquire this graph version.
    wrong_id = local["artifact_ids"][0]
    after["_canonical_artifacts"][wrong_id]["receipt_sha256"] = "f" * 64
    from bridge.web.evidence import assessment_evidence
    reread, _ = assessment_evidence(service.inputs, after, after["_assessment"])
    assert wrong_id not in reread[0]["artifact_ids"]


@pytest.mark.parametrize("tool,module", [("P0-03", "test_p0_03_target_regional"),
                                          ("P0-04", "test_p0_04_developmental_compatibility")])
def test_imported_assessment_inputs_respect_review_and_measurement_contracts(
        client, tmp_path, monkeypatch, tool, module):
    from bridge.web.sessions import write_file
    from bridge.tool_packages.p0_02_cell_state.measurement_specs import load_measurement_spec
    from bridge.tool_packages.p0_02_cell_state.reference import DENIED_SOURCE_FAMILIES
    import hashlib
    source = importlib.import_module(module)
    spec = load_measurement_spec("CELLSTATE-scRNA-shadow-v0.1")
    values = source._base_payloads()
    values["measurement_spec"]["reference_refs"] = [spec.reference_refs[0] + "@1.0.0"]
    values["reference_manifest"].update(snapshot_id=spec.reference_refs[0],
        marker_program_sha256=hashlib.sha256(b"{}").hexdigest(),
        measurement_spec_ids=[*values["reference_manifest"]["measurement_spec_ids"], spec.measurement_spec_id],
        prohibited_source_families=sorted(DENIED_SOURCE_FAMILIES))
    supplied = tmp_path / "supplied"
    supplied.mkdir()
    request = source._request(supplied, values)
    reference_root = tmp_path / "references"
    snapshot = reference_root / spec.reference_refs[0]
    snapshot.mkdir(parents=True, mode=0o700)
    for ref in request.object_inputs:
        if ref.role in {"reference_manifest", "annotation_vocabulary"}:
            write_file(snapshot / (ref.role + ".json"), ref.path.read_bytes())
    write_file(snapshot / "marker_programs.json", b"{}")
    monkeypatch.setenv("BRIDGE_REFERENCE_ROOT", str(reference_root))
    monkeypatch.setenv("BRIDGE_ALLOW_CANDIDATE_REFERENCES", "1")
    service, sid, aid = science_case(client, tmp_path)
    service.settings = replace(service.settings, share_result_summaries=True)
    catalog = client.get(f"/api/sessions/{sid}/analysis-inputs").json()
    resources = {item["label"]: item["id"] for item in catalog["objects"] if item["source"] == "system_resource"}
    objects = upload_request(client, sid, request.model_copy(update={"object_inputs": [
        ref for ref in request.object_inputs if ref.role not in resources]}), "default")
    objects.extend({"role": role, "input_id": identifier} for role, identifier in resources.items())
    assert client.post(f"/api/sessions/{sid}/analysis-inputs", json=choice(tool, "default", objects)).status_code == 200
    scope = propose_scope(client, sid, aid, tool, "default")
    monkeypatch.setattr("bridge.web.provider.converse", next_check_or_stop)
    approve_scope(client, sid, scope)
    done = settle(client, sid)["_assessment_state"]
    if tool == "P0-03":
        # Complete imported inputs still have draft roles; their fixture ratios
        # must not become evidence for this upload. Actual producer results are
        # covered by the registered-producers test above.
        assert scope["candidates"][0]["blockers"] == ["state_role_review_required"]
        assert done["stop_reason"] == "no_eligible_check"
        assert done["tool_runs_used"] == done["model_turns_used"] == 0
        assert done["evidence"] == []
        assert service.load(sid)["_tool_runs"] == []
        return
    assert done["tool_runs_used"] == 1 and done["stop_reason"] == "no_discriminating_check", done
    evidence = done["evidence"][0]
    assert evidence["state"] == "available"
    measurements = evidence["measurements"]
    assert len(measurements) == 10
    assert all(item["unit"] == "fraction" for item in measurements)
    assert all(item["measurement_class"] == "gate_input_measurement" for item in measurements)
    assert all(item["domain_score"] is None for item in measurements)
    assert evidence["summary"]["whole_product_profile"]["denominator"] == 12
    assert evidence["summary"]["target_related_profile"]["denominator"] == 11


def test_restart_interruption_retains_durable_budget_and_does_not_execute(client, tmp_path, monkeypatch):
    from bridge.web.service import Service
    from bridge.web.assessment import ScopeIdentity
    from threading import Event
    entered, release = Event(), Event()
    service, sid, aid = registered_case(client, tmp_path)
    scope = propose_scope(client, sid, aid)
    def pending(settings, messages, context):
        entered.set()
        assert release.wait(10)
        raise RuntimeError("external connection lost")
    monkeypatch.setattr("bridge.web.provider.converse", pending)
    approve_scope(client, sid, scope)
    assert entered.wait(5)
    # Capture actual durable in-flight state, then finish the original worker.
    dispatched = service.load(sid)
    release.set()
    settle(client, sid)
    service.sessions.save(dispatched)
    restored = Service(service.settings)
    try:
        state = restored.load(sid)
        assert state["_assessment"]["status"] == "interrupted"
        assert state["_assessment"]["stop_reason"] == "restart_interrupted"
        assert state["_assessment"]["model_turns_used"] == 1
        assert state["_assessment"]["authorization"] == dispatched["_assessment"]["authorization"]
        assert state["_tool_runs"] == []
    finally:
        restored.execution.pool.shutdown(wait=True)


def test_scope_data_view_and_approval_limits_are_visible_but_resources_remain_private(client, tmp_path):
    service, sid, aid = registered_case(client, tmp_path)
    scope = propose_scope(client, sid, aid)
    assert scope["data_view"]["state"] == "not_available"
    assert "stop_conditions" not in scope
    assert scope["resources"] and all(set(row) == {"alias", "schema_ref", "object_version", "sha256", "source"}
                                      for row in scope["resources"])
    assert scope["max_tool_runs"] == 3 and scope["max_model_turns"] == 4
    assert "PRIVATE_NAME" not in json.dumps(scope)


def test_registered_graph_feedback_preserves_missing_domains_conflict_interval_and_private_aliases(
        client, tmp_path, monkeypatch):
    from bridge.toolkit.contracts import ToolRunV2
    from test_web_inputs import approve
    from web_support import confirm_change
    from test_p0_09_evidence_compiler import (
        _request, _bundle, _candidate, _claim_registry, _reconciliation_registry,
        _family_registry, _profile, _missing_observation)
    service, sid, aid = registered_case(client, tmp_path)
    service.settings = replace(service.settings, share_result_summaries=True)
    claims = _claim_registry(orthogonal_required=True)
    claims["claims"][0]["claim_type"] = "descriptive_domain_observation"
    claims["claims"][0]["requirement_specs"][0].update(
        requirement_key="canonical_measurement", channel_role="canonical_measurement")
    regional = json.loads(json.dumps(claims["claims"][0]))
    regional.update(claim_id="claim:regional", domain_id="regional_fidelity", claim_type="private_patient_type")
    regional["requirement_specs"] = [{
        "requirement_key": "private_patient_requirement", "channel_role": "private_patient_channel",
        "required_modality": "scRNA-seq", "required_experiment": None,
        "blocking_scope": "claim", "required": True}]
    claims["claims"].append(regional)
    missing = _missing_observation()
    regional_missing = {**missing, "observation_id": "missing-evidence:regional",
        "claim_ref": {"object_id": "claim:regional", "object_version": "1.0.0"},
        "requirement_key": "private_patient_requirement", "reason_code": "measurement_unavailable",
        "source_contract_ref": {"object_id": "claim:regional", "object_version": "1.0.0"}}
    reconciliations = _reconciliation_registry(orthogonal_required=True)
    reconciliations["specs"][0]["claim_type"] = "descriptive_domain_observation"
    candidates = [
        _candidate(metric_id="target_identity_fraction", relation="supports"),
        _candidate(candidate_id="evidence-candidate:opposite", metric_id="regional_fidelity_fraction",
            relation="contradicts", family_id="evidence-family:orthogonal"),
        {**_candidate(candidate_id="evidence-candidate:private", metric_id="private_patient_metric"),
            "unit": "private_patient_unit"},
    ]
    request = _request(tmp_path / "canonical-graph",
        bundle=_bundle(candidates=candidates, missing=[missing, regional_missing]),
        claim_registry=claims, reconciliation_registry=reconciliations,
        family_registry=_family_registry(second_family=True),
        profile={**_profile(), "deduplicated_evidence_family_ids": [
            "evidence-family:transcriptomic", "evidence-family:orthogonal"]})
    # Historical graphs must retain their registered, exact compiler inputs.
    objects = upload_request(client, sid, request, "case_initial")
    url = f"/api/sessions/{sid}"
    selected = client.post(url + "/analysis-inputs", json=choice("P0-09", "case_initial", objects))
    assert selected.status_code == 200, selected.json()
    plan = client.post(url + "/prepare-analysis", json={"tool_id": "P0-09"}).json()["plan"]
    assert approve(client, sid, plan)["plan"]["status"] == "completed"
    state = service.load(sid)
    receipt = state["_tool_runs"][-1]
    raw = (service.directory(sid) / "receipts" / receipt["file"]).read_bytes()
    compiled = ToolRunV2.model_validate_json(raw)
    graph_id = next(identifier for identifier, record in state["_input_objects"].items()
        if record.get("receipt_file") == receipt["file"]
        and record["schema_ref"] == "bridge://schemas/case-evidence-graph-manifest/v0.1")
    query = {"object_version": "0.1.0", "query_name": "get_case_evidence_subgraph",
        "product_case_id": "product-case:synthetic-001", "evidence_tiers": ["formal", "shadow", "exploratory"],
        "max_depth": 4, "max_nodes": 100}
    query_id = service.inputs.add_object(state, tool_id="P0-09", mode_id="case_query",
        role="evidence_graph_query", schema_ref="bridge://schemas/evidence-graph-query/v0.1",
        object_version="0.1.0", data=json.dumps(query).encode())
    service.sessions.save(state)
    selected = client.post(f"/api/sessions/{sid}/analysis-inputs", json=choice("P0-09", "case_query", [
        {"role": "evidence_graph_manifest", "input_id": graph_id},
        {"role": "evidence_graph_query", "input_id": query_id}]))
    assert selected.status_code == 200, selected.json()
    if selected.json()["pending_input_change"]:
        confirm_change(client, sid, selected.json())
    scope = propose_scope(client, sid, aid, "P0-09", "case_query")
    wires = []
    def model(settings, messages, context):
        from bridge.web.provider import Action
        wires.append(json.loads(json.dumps(context)))
        if context["options"]:
            return Action.model_validate({"action": "assessment", "decision": {
                "action": "query", "option_id": context["options"][0]["id"]}})
        return next_check_or_stop(settings, messages, context)
    monkeypatch.setattr("bridge.web.provider.converse", model)
    approve_scope(client, sid, scope)
    done = settle_assessment(client, sid)["_assessment_state"]
    assert done["stop_reason"] == "no_discriminating_check", done
    summary = next(row["summary"] for row in wires[-1]["evidence"]
        if row.get("summary", {}).get("query_name") == "get_case_evidence_subgraph")
    requirements = expanded_model_rows(summary, "requirements")
    claims = expanded_model_rows(summary, "claims")
    reconciliations = expanded_model_rows(summary, "reconciliations")
    assert {(row["domain_id"], reason) for row in requirements for reason in row["reason_codes"]} >= {
        ("target_identity", "required_experiment_not_performed"),
        ("regional_fidelity", "measurement_unavailable")}
    assert any(row.get("requirement_key") == "canonical_measurement" for row in requirements)
    assert any(row.get("claim_type") == "descriptive_domain_observation" for row in claims)
    assert {row["relation"] for row in summary["records"]} == {"supports", "contradicts"}
    known = next(row for row in expanded_model_rows(summary, "records") if row.get("metric_name") == "target_identity_fraction")
    assert (known["value"], known["numerator"], known["denominator"], known["unit"]) == (0.75, 75, 100, "fraction")
    assert known["interval"] == {"lower": 0.65, "upper": 0.82, "confidence_level": 0.95}
    assert any(row["eligibility"] == "insufficient_evidence" and row["state"] is None
               and "lower_tier_excluded" in row["reason_codes"] for row in reconciliations)
    assert any(row.get("metric_semantics_state") == "unavailable" for row in summary["records"])
    wire = json.dumps(wires[-1])
    assert "private_patient" not in wire
    assert compiled.result["graph_id"] not in wire
    assert receipt["sha256"] not in wire
    assert not any("provenance" in row for row in summary["records"])
    local = next(row["summary"] for row in done["evidence"]
        if row.get("summary", {}).get("query_name") == "get_case_evidence_subgraph")
    assert any(row["requirement_key"] == "private_patient_requirement" for row in local["requirements"])
    assert all(row["alias"] not in wire for row in local["nodes"])
    assert (service.directory(sid) / "receipts" / receipt["file"]).read_bytes() == raw


def test_query_only_scope_proposal_returns_blocker_without_consuming_authority(client, tmp_path, monkeypatch):
    service, sid, aid = registered_case(client, tmp_path)
    query = {"object_version": "0.1.0", "query_name": "get_case_evidence_subgraph",
        "product_case_id": "product-case:synthetic", "evidence_tiers": ["shadow"]}
    response = client.post(f"/api/sessions/{sid}/analysis-inputs/objects",
        params={"tool_id": "P0-09", "mode_id": "case_query", "role": "evidence_graph_query",
            "schema_ref": "bridge://schemas/evidence-graph-query/v0.1", "object_version": "0.1.0"},
        files={"file": ("query.json", json.dumps(query).encode(), "application/json")})
    assert response.status_code == 200, response.json()
    query_id = next(reversed(service.load(sid)["_input_objects"]))
    selected = client.post(f"/api/sessions/{sid}/analysis-inputs", json=choice("P0-09", "case_query", [
        {"role": "evidence_graph_query", "input_id": query_id}]))
    assert selected.status_code == 200
    before = service.load(sid)
    monkeypatch.setattr("bridge.web.provider.converse", lambda *args: pytest.fail("proposal called provider"))
    scope = propose_scope(client, sid, aid, "P0-09", "case_query")
    assert scope["candidates"][0]["blockers"] == ["canonical_case_graph_required"]
    assert "tool_runs_used" not in scope and "model_turns_used" not in scope
    assert service.load(sid)["_assessment"]["tool_runs_used"] == 0
    assert service.load(sid)["_assessment"]["model_turns_used"] == 0
    after = service.load(sid)
    for key in ("_input_revision", "_input_objects", "_tool_runs", "_intakes"):
        assert after[key] == before[key]
    assert after["_assessment"]["authorization"] is None


@pytest.mark.parametrize("mode", ["comparison_initial_v2", "invented"])
def test_disallowed_or_unknown_mode_never_starts_scope(client, tmp_path, mode):
    service, sid, aid = registered_case(client, tmp_path)
    response = client.post(f"/api/sessions/{sid}/assessment/propose", json={
        "question": "Check evidence", "upload_id": aid, "allowed_modes": [{"tool_id": "P0-09", "mode_id": mode}],
        "max_tool_runs": 3, "max_model_turns": 4})
    assert response.status_code == 422
    assert service.load(sid).get("_assessment") is None


def test_result_bound_hypothesis_is_stored_without_changing_scientific_objects(client, tmp_path, monkeypatch):
    service, sid, aid = producer_scientific_case(
        client, tmp_path, monkeypatch, with_producers=False)
    service.settings = replace(service.settings, share_result_summaries=True)
    scope = propose_scope(client, sid, aid, "P0-01", None)
    objects = service.load(sid)["_input_objects"]
    wires = []
    def model(settings, messages, context):
        from bridge.web.assessment import AssessmentScope
        state = service.load(sid)
        wires.append(json.dumps(context))
        candidates = service.inputs.assessment_candidates(state, AssessmentScope.model_validate(state["_assessment"]["scope"]))
        for candidate in candidates:
            if candidate["fingerprint"]:
                assert candidate["fingerprint"] not in wires[-1]
        for receipt in state["_tool_runs"]:
            for private in (receipt["sha256"], receipt["sha256"][:16], receipt["plan_id"], receipt["file"]):
                assert private not in wires[-1]
        for binding in state["_canonical_artifacts"].values():
            for private in (binding["sha256"], binding["sha256"][:16], binding["path"], binding["artifact_id"]):
                assert private not in wires[-1]
        assert "/api/sessions/" not in wires[-1]
        assert "provenance" not in wires[-1]
        from bridge.web.provider import Action, _citation_choices
        assert context["question"] == scope["question"]
        if not context["evidence"]:
            return next_check_or_stop(settings, messages, context)
        alias = _citation_choices(context["evidence"])["evidence_aliases"][0]
        record = next(item for evidence in context["evidence"]
            for item in evidence.get("measurements", []) if item.get("citation_alias") == alias)
        statement = f"{record['metric_name']} 的 evidence_state 为 {record['evidence_state']}。"
        return Action.model_validate({"action": "assessment", "decision": {
            "action": "explain", "text": f"{statement} [{alias}]",
            "hypotheses": [{"statement": statement,
                "evidence_aliases": [alias],
                "competing_explanation": "An unresolved role assignment may also explain it.",
                "discriminating_check": None}]}})
    monkeypatch.setattr("bridge.web.provider.converse", model)
    approve_scope(client, sid, scope)
    done = settle(client, sid)
    assert done["_assessment_state"]["stop_reason"] == "explanation_complete"
    assert len(done["_assessment_state"]["hypotheses"]) == 1
    stable_refs = done["_assessment_state"]["hypotheses"][0]["evidence_aliases"]
    assert stable_refs and all(ref.endswith("@1") for ref in stable_refs)
    current = service.load(sid)
    assert all(current["_input_objects"][key] == value for key, value in objects.items())
    assert current["_input_revision"] == scope["input_revision"]
    assert done["_assessment_state"]["scope_grants_scientific_approval"] is False
    evidence = done["_assessment_state"]["evidence"][0]
    assert evidence["artifact_ids"]
    assert isinstance(evidence["dependencies"], list)
    for dependency in evidence["dependencies"]:
        assert dependency["role"] and dependency["object_version"] and dependency["sha256"]
        assert dependency["sha256"] not in wires[-1]
    assert set(evidence["artifact_ids"]) <= {row["id"] for row in done["artifacts"]}
    turn = current["_assessment"]["model_turns"][-1]
    assert evidence["alias"] in turn["evidence_bindings"]
    assert stable_refs[0] in turn["provider_bindings"]["evidence"].values()
    assert evidence["provenance"]["receipt_sha256"] == current["_tool_runs"][-1]["sha256"]



@pytest.mark.parametrize("confirm", [True, False])
def test_assessment_freshness_tracks_confirmed_correction_without_rewriting_stop(client, tmp_path, monkeypatch, confirm):
    from web_support import confirm_change
    service, sid, aid = registered_case(client, tmp_path)
    service.settings = replace(service.settings, share_result_summaries=True)
    monkeypatch.setattr("bridge.web.provider.converse", next_check_or_stop)
    scope = propose_scope(client, sid, aid)
    approve_scope(client, sid, scope)
    done = settle(client, sid)
    assert done["_assessment_state"]["stop_reason"] == "no_discriminating_check"
    before = service.load(sid)
    staged = client.post(f"/api/sessions/{sid}/inputs",
        json={"upload_id": aid, "source_family_id": "corrected-source"}).json()
    assert staged["assessment"]["freshness"]["state"] == "review_pending"
    assert "stop_reason" not in staged["assessment"]
    assert "stop_events" not in staged["assessment"]
    staged_private = service.load(sid)["_assessment"]
    assert staged_private["stop_reason"] == "no_discriminating_check"
    assert staged_private["stop_events"] == done["_assessment_state"]["stop_events"]
    assert staged["assessment"]["freshness"]["current_input_revision"] == scope["input_revision"]
    if confirm:
        current = confirm_change(client, sid, staged)
        assert current["assessment"]["freshness"]["state"] == "historical"
        assert "reason_code" not in current["assessment"]["freshness"]
        assert current["assessment"]["freshness"]["current_input_revision"] > scope["input_revision"]
        refused = client.post(f"/api/sessions/{sid}/assessment/resume", json={
            "scope_id": scope["scope_id"], "scope_digest": scope["scope_digest"]})
        assert refused.status_code == 409
    else:
        change = staged["pending_input_change"]
        client.post(f"/api/sessions/{sid}/input-change/discard",
            json={"change_id": change["id"], "change_digest": change["digest"]})
        current = client.post(f"/api/sessions/{sid}/input-review/keep", json={}).json()
        assert current["assessment"]["freshness"]["state"] == "current"
    after = service.load(sid)
    assert after["_tool_runs"] == before["_tool_runs"]
    assert after["_assessment"]["scope"] == before["_assessment"]["scope"]
    assert "stop_reason" not in current["assessment"]
    assert "stop_events" not in current["assessment"]
    assert "tool_runs_used" not in current["assessment"]
    assert after["_assessment"]["stop_reason"] == "no_discriminating_check"
    assert after["_assessment"]["stop_events"] == done["_assessment_state"]["stop_events"]
    assert after["_assessment"]["tool_runs_used"] == done["_assessment_state"]["tool_runs_used"]
    if not confirm:
        resumed = client.post(f"/api/sessions/{sid}/assessment/resume", json={
            "scope_id": scope["scope_id"], "scope_digest": scope["scope_digest"]})
        assert resumed.status_code == 200, resumed.json()
        settled = settle_assessment(client, sid)["_assessment_state"]
        assert settled["stop_events"][0] == done["_assessment_state"]["stop_events"][0]
        assert len(settled["stop_events"]) == 2
        assert settled["model_turns_used"] >= done["_assessment_state"]["model_turns_used"]
        assert settled["tool_runs_used"] == done["_assessment_state"]["tool_runs_used"]


def test_reference_drift_during_model_turn_blocks_before_admission(client, tmp_path, monkeypatch):
    service, sid, aid = registered_case(client, tmp_path)
    scope = propose_scope(client, sid, aid)
    def model(settings, messages, context):
        service.settings = replace(service.settings, cell_state_measurement_spec_ref=None)
        return next_check_or_stop(settings, messages, context)
    monkeypatch.setattr("bridge.web.provider.converse", model)
    approve_scope(client, sid, scope)
    done = settle(client, sid)
    assert done["_assessment_state"]["stop_reason"] == "scope_resource_changed"
    assert done["_assessment_state"]["tool_runs_used"] == 0
    assert done["_assessment_state"]["model_turns_used"] == 1
    assert service.load(sid)["_tool_runs"] == []


def test_worker_capacity_rejection_keeps_scope_authorization_resumable(client, tmp_path, monkeypatch):
    service, sid, aid = registered_case(client, tmp_path)
    scope = propose_scope(client, sid, aid)
    held = 0
    while service.execution.capacity.acquire(blocking=False):
        held += 1
    try:
        response = client.post(f"/api/sessions/{sid}/assessment/approve", json={
            "scope_id": scope["scope_id"], "scope_digest": scope["scope_digest"]})
        assert response.status_code == 429
        state = service.load(sid)
        assert state["_assessment"]["status"] == "blocked"
        assert state["_assessment"]["stop_reason"] == "worker_busy"
        assert state["_assessment"]["authorization"] is not None
        assert state["_assessment"]["model_turns_used"] == 0
    finally:
        for _ in range(held):
            service.execution.capacity.release()
    monkeypatch.setattr("bridge.web.provider.converse", next_check_or_stop)
    response = client.post(f"/api/sessions/{sid}/assessment/resume", json={
        "scope_id": scope["scope_id"], "scope_digest": scope["scope_digest"]})
    assert response.status_code == 200, response.json()
    assert settle(client, sid)["_assessment_state"]["tool_runs_used"] == 1


def test_new_in_scope_qc_output_is_not_an_input_revision(client, tmp_path, monkeypatch):
    service, sid, aid = science_case(client, tmp_path)
    service.settings = replace(service.settings, share_result_summaries=True)
    selected = client.post(f"/api/sessions/{sid}/analysis-inputs",
                           json=choice("P0-01", None, assets=[aid]))
    assert selected.status_code == 200, selected.json()
    scope = propose_scope(client, sid, aid, "P0-01", None)
    monkeypatch.setattr("bridge.web.provider.converse", next_check_or_stop)
    approve_scope(client, sid, scope)
    done = settle(client, sid)
    assert done["_assessment_state"]["stop_reason"] == "no_discriminating_check", done
    assert done["_assessment_state"]["tool_runs_used"] == 1
    assert done["_assessment_state"]["model_turns_used"] == 2
    assert service.load(sid)["_input_revision"] == scope["input_revision"]


def test_real_exploratory_missing_gene_keeps_partial_and_all_96_cells(client, tmp_path, monkeypatch):
    from test_p0_06_exploratory import _request, _payload, _with_input
    from web_support import new_session, confirm_change
    from test_web_intake import stage, stated_facts
    request = _request(tmp_path, missing_gene=True)
    sid = new_session(client)["id"]
    response = client.post(f"/api/sessions/{sid}/uploads",
        files={"file": ("synthetic.h5ad", request.assets[0].path.read_bytes())})
    assert response.status_code == 200
    aid = response.json()["uploads"][0]["id"]
    confirm_change(client, sid, stage(client, sid, aid, stated_facts(
        source_family_id="synthetic-test-only", gene_symbol_column="gene_symbol")))
    payload = _payload(request)
    payload["data_view"]["artifact_id"] = aid
    payload["data_view"]["parent_asset_id"] = aid
    request = _with_input(request, payload)
    objects = upload_request(client, sid, request, "exploratory_process")
    selected = client.post(f"/api/sessions/{sid}/analysis-inputs",
        json=choice("P0-06", "exploratory_process", objects, [aid]))
    assert selected.status_code == 200, selected.json()
    service = client.app.state.service
    service.settings = replace(service.settings, share_result_summaries=True)
    scope = propose_scope(client, sid, aid, "P0-06", "exploratory_process")
    monkeypatch.setattr("bridge.web.provider.converse", next_check_or_stop)
    approve_scope(client, sid, scope)
    done = settle(client, sid)
    evidence = done["_assessment_state"]["evidence"][0]
    assert evidence["state"] == "available", evidence
    assert evidence["execution_state"] == "partial"
    assert evidence["interpretation_scope"] == "exploratory"
    assert len(evidence["measurements"]) == 5
    assert all(row["domain_score"] is None for row in evidence["measurements"])
    assert evidence["measurements"][0]["raw_value"] is None
    assert evidence["measurements"][0]["evidence_state"] == "unavailable"
    result = evidence["summary"]
    assert result["runtime_mode"] == "exploratory_process"
    assert result["n_observations"] == 96
    assert result["independence_state"] == "unknown"
    assert result["state_review_status"] == "pending"
    assert result["n_independent_replicates"] is None
    assert result["cell_cycle"]["phase_counts"] is None
    assert result["cell_cycle"]["s_g2m_fraction"] is None
    assert result["cell_cycle"]["n_observations"] == 96
    missing = [row for row in result["program_summaries"] if row["program_id"] == "S"]
    assert len(missing) == 2
    assert all(row["assessment_state"] == "not_assessed" and row["mean"] is None for row in missing)
    # Authenticated evidence retains exact gene coverage; the model projection withholds gene labels.
    assert "observation_id" not in json.dumps(result)
    assert all(row["missing_genes"] == ["ABSENT"] for row in missing)
    from bridge.web.evidence import assessment_model_evidence
    model_evidence, _ = assessment_model_evidence([evidence])
    assert "ABSENT" not in json.dumps(model_evidence)
    # A caller changes the registered DataView descriptor: this is a new fact/input
    # revision even when its underlying matrix checksum remains unchanged.
    next_scope = propose_scope(client, sid, aid, "P0-06", "exploratory_process")
    before_change = service.load(sid)
    pending = before_change["_assessment"]
    assert pending["authorization"] is None
    assert pending["tool_runs_used"] == pending["model_turns_used"] == 0
    payload["data_view"]["view_id"] = "view:user-selected-revision"
    changed = _with_input(request, payload)
    new_objects = upload_request(client, sid, changed, "exploratory_process")
    after_upload = service.load(sid)
    first_terminal = after_upload["_assessment"]
    assert first_terminal["status"] == "blocked"
    first_event, = first_terminal["stop_events"]
    assert first_terminal["stop_reason"] == first_event["reason"]
    assert first_event["reason"] and first_event["status"] == "blocked"
    assert first_event["tool_runs_used"] == first_event["model_turns_used"] == 0
    selected = client.post(f"/api/sessions/{sid}/analysis-inputs",
        json=choice("P0-06", "exploratory_process", new_objects, [aid]))
    assert selected.status_code == 200
    historical = selected.json()["assessment"]
    # Freshness describes the later input revision; it cannot rewrite the first
    # terminal reason or create another stop event for this already blocked scope.
    assert historical["status"] == "blocked"
    assert "stop_reason" not in historical and "stop_events" not in historical
    assert historical["freshness"]["state"] == "historical"
    assert "reason_code" not in historical["freshness"]
    assert historical["freshness"]["scope_input_revision"] == next_scope["input_revision"]
    assert historical["freshness"]["current_input_revision"] > next_scope["input_revision"]
    after_selection = service.load(sid)
    assert after_selection["_assessment"]["stop_reason"] == first_terminal["stop_reason"]
    assert after_selection["_assessment"]["stop_events"] == first_terminal["stop_events"]
    rejected = client.post(f"/api/sessions/{sid}/assessment/approve", json={
        "scope_id": next_scope["scope_id"], "scope_digest": next_scope["scope_digest"]})
    assert rejected.status_code == 409
    after_rejection = service.load(sid)
    for state in (after_upload, after_selection, after_rejection):
        assessment = state["_assessment"]
        assert assessment["status"] == "blocked"
        assert assessment["stop_reason"] == first_terminal["stop_reason"]
        assert assessment["stop_events"] == first_terminal["stop_events"]
        for key in ("scope", "scope_digest", "authorization", "tool_runs_used",
                    "model_turns_used", "admissions", "model_turns"):
            assert assessment[key] == pending[key], key
        assert state["_tool_runs"] == before_change["_tool_runs"]
    assert len(after_rejection["_tool_runs"]) == 1


def test_unrelated_manual_selection_is_not_opened_or_bound_to_scope(client, tmp_path):
    from pathlib import Path
    from bridge.web.sessions import write_file
    service, sid, aid = registered_case(client, tmp_path)
    import test_p0_06_proliferation_stress_response as p006
    extra = tmp_path / "unrelated"
    extra.mkdir()
    refs = upload_request(client, sid, p006._request(extra), "legacy_aggregation")
    assert client.post(f"/api/sessions/{sid}/analysis-inputs",
                       json=choice("P0-06", "legacy_aggregation", refs)).status_code == 200
    state = service.load(sid)
    unrelated_id = refs[0]["input_id"]
    path = Path(state["_input_objects"][unrelated_id]["path"])
    write_file(path, path.read_bytes() + b" ")
    scope = propose_scope(client, sid, aid, "P0-05")
    assert scope["status"] == "proposed"
    assert unrelated_id not in service.load(sid)["_assessment"]["scope"]["binding"]["resources"]


def test_literature_consent_defaults_disabled_and_requires_public_concepts(client, tmp_path):
    service, sid, aid = science_case(client, tmp_path)
    scope = propose_scope(client, sid, aid, "P0-01", None)
    assert scope["literature"]["enabled"] is False
    assert scope["literature"]["searches_used"] == 0
    body = {"question": "Interpret this product.", "upload_id": aid,
        "allowed_modes": [{"tool_id": "P0-01", "mode_id": None}],
        "max_tool_runs": 1, "max_model_turns": 5, "literature_enabled": True}
    assert client.post(f"/api/sessions/{sid}/assessment/propose", json=body).status_code == 422
    response = client.post(f"/api/sessions/{sid}/assessment/propose", json={
        **body, "literature_concept_refs": ["neural_progenitor"]})
    assert response.status_code == 200
    assert response.json()["assessment"]["literature"]["concept_refs"] == ["neural_progenitor"]


def test_assessment_search_and_read_preserve_source_and_consume_separate_budgets(client, tmp_path, monkeypatch):
    from bridge.web import provider, literature
    from test_web_inputs import approve
    from test_web_literature import transport, article, response
    service, sid, aid = producer_scientific_case(client, tmp_path, monkeypatch, with_producers=False)
    plan = client.post(f"/api/sessions/{sid}/prepare-analysis", json={"tool_id": "P0-01"}).json()["plan"]
    approve(client, sid, plan)
    scope = propose_scope(client, sid, aid, "P0-10", "default",
        report_after_explanation=True, max_tool_runs=1, max_model_turns=5,
        literature_enabled=True, literature_concept_refs=["neural_progenitor"],
        max_literature_searches=1, max_literature_reads=1)
    calls = transport(monkeypatch, [response([article()]), response([article()])])
    contexts = []
    def next_action(settings, messages, context):
        contexts.append(context)
        if len(contexts) == 1:
            decision = {"action":"search_literature", "concept_refs":["neural_progenitor"], "focus":"proliferation"}
        elif len(contexts) == 2:
            decision = {"action":"read_literature", "source_ref":context["literature"]["readable_source_refs"][0]}
        else:
            assert context["literature"]["sources"][0]["abstract"] == "A public abstract."
            decision = {"action":"stop", "reason":"no_discriminating_check"}
        return provider.Action.model_validate({"action":"assessment", "decision":decision})
    monkeypatch.setattr(provider, "converse", next_action)
    approve_scope(client, sid, scope)
    done = settle_assessment(client, sid)
    state = service.load(sid)["_assessment"]
    assert len(calls) == 2
    assert state["tool_runs_used"] == 0
    assert state["literature"]["searches_used"] == state["literature"]["reads_used"] == 1
    assert contexts[1]["literature"]["searches_remaining"] == 0
    assert contexts[2]["literature"]["reads_remaining"] == 0
    assert done["assessment"]["literature"]["sources"][0]["metadata"]["pmid"] == "12345"


def test_stop_during_literature_io_drops_response_without_refunding_budget(client, tmp_path, monkeypatch):
    from threading import Event
    from bridge.web import provider, literature
    entered, release = Event(), Event()
    service, sid, aid = registered_case(client, tmp_path)
    scope = propose_scope(client, sid, aid, literature_enabled=True, literature_concept_refs=["neuron"])
    monkeypatch.setattr(provider, "converse", lambda *args: provider.Action.model_validate({
        "action":"assessment", "decision":{"action":"search_literature", "concept_refs":["neuron"], "focus":"identity"}}))
    def slow(reservation):
        entered.set()
        assert release.wait(10)
        return {"state":"no_results", "query":"public-only", "hit_count":0, "sources":[]}
    monkeypatch.setattr(literature, "execute", slow)
    approve_scope(client, sid, scope)
    assert entered.wait(5)
    try:
        assert service.load(sid)["_assessment"]["literature"]["searches_used"] == 1
        assert client.post(f"/api/sessions/{sid}/stop", json={}).status_code == 200
    finally:
        release.set()
    settle(client, sid)
    state = service.load(sid)["_assessment"]
    assert state["stop_reason"] == "user_stopped"
    assert state["literature"]["requests"][0]["state"] == "reserved"
    assert state["literature"]["searches_used"] == 1
    assert state["literature"]["discovered"] == []


@pytest.mark.parametrize("enabled,refs", [(False, []), (True, ["neuron"])])
def test_unapproved_literature_action_makes_no_external_request(client, tmp_path, monkeypatch, enabled, refs):
    from bridge.web import provider, literature
    service, sid, aid = registered_case(client, tmp_path)
    scope = propose_scope(client, sid, aid, literature_enabled=enabled, literature_concept_refs=refs)
    monkeypatch.setattr(literature, "execute", lambda *_: pytest.fail("unapproved external request"))
    monkeypatch.setattr(provider, "converse", lambda *args: provider.Action.model_validate({
        "action":"assessment", "decision":{"action":"search_literature", "concept_refs":["astrocyte"], "focus":"identity"}}))
    approve_scope(client, sid, scope)
    done = settle_assessment(client, sid)
    assert done["_assessment_state"]["stop_reason"] == "unavailable_or_repeated_action"


def test_duplicate_literature_support_blocks_without_saving_interpretation(client, tmp_path, monkeypatch):
    from bridge.web import provider
    service, sid, aid = registered_case(client, tmp_path)
    scope = propose_scope(client, sid, aid, literature_enabled=True, literature_concept_refs=["neuron"])
    use = {"source_ref": "literature:epmc-med-12345", "rationale": "Public context",
        "species": "unknown", "lineage": "unknown", "stage": "unknown", "experimental_context": "unknown"}
    monkeypatch.setattr(provider, "converse", lambda *args: provider.Action.model_validate({
        "action": "assessment", "decision": {"action": "explain", "hypotheses": [{
            "statement": "A proposed explanation.", "evidence_aliases": ["E-record"],
            "competing_explanation": "A rival.", "discriminating_check": None,
            "literature_support": [use, use]}]}}))
    approve_scope(client, sid, scope)
    done = settle_assessment(client, sid)
    stored = service.load(sid)["_assessment"]
    assert done["_assessment_state"]["status"] == "blocked"
    assert stored["stop_reason"] == "provider_action_invalid_or_unavailable"
    assert stored.get("interpretation_versions", []) == []
    assert stored["model_turns"][-1]["provider_error_detail"]["category"] == "action_schema"

def test_literature_explanation_review_blocks_admission_and_spends_approved_turn(client, tmp_path, monkeypatch):
    from bridge.web import provider
    from test_web_inputs import approve
    service, sid, aid = producer_scientific_case(client, tmp_path, monkeypatch, with_producers=False)
    plan = client.post(f"/api/sessions/{sid}/prepare-analysis", json={"tool_id": "P0-01"}).json()["plan"]
    approve(client, sid, plan)
    before = service.load(sid)
    scope = propose_scope(client, sid, aid, "P0-10", "default",
        report_after_explanation=True, max_tool_runs=1, max_model_turns=3,
        literature_enabled=True, literature_concept_refs=["neural_progenitor"])
    def explain(settings, messages, context):
        alias = provider._citation_choices(context["evidence"])["evidence_aliases"][0]
        return provider.Action.model_validate({"action": "assessment", "decision": {
            "action": "explain", "hypotheses": [{
                "statement": "The observations are compatible with a precursor-like pattern.",
                "evidence_aliases": [alias], "competing_explanation": "There are no biological replicates.",
                "expected_observation": "A matched prospective comparison could distinguish the rivals; shared outcomes remain indeterminate.",
                "discriminating_check": None}]}})
    monkeypatch.setattr(provider, "converse", explain)
    monkeypatch.setattr(provider, "review_interpretation", lambda *args: {"issues": [{
        "hypothesis_index": 0, "field": "competing_explanation", "code": "unknown_as_absent",
        "quote": "no biological replicates", "reason": "The replicate count is unknown."}]}, raising=False)
    approve_scope(client, sid, scope)
    done = settle_assessment(client, sid)
    stored = service.load(sid)
    assert done["_assessment_state"]["status"] == "blocked"
    assert stored["_assessment"]["stop_reason"] == "provider_action_invalid_or_unavailable"
    assert stored["_assessment"]["model_turns_used"] == 2
    assert stored["_assessment"].get("interpretation_versions", []) == []
    assert stored["_tool_runs"] == before["_tool_runs"]
    assert stored["_input_objects"] == before["_input_objects"]
    assert stored["_assessment"]["model_turns"][-1]["provider_error_detail"] == {
        "category": "interpretation_review", "issues": [{
            "hypothesis_index": 0, "field": "competing_explanation", "code": "unknown_as_absent"}]}
    assert "no biological replicates" not in json.dumps(stored["_assessment"]["model_turns"])


def test_removed_conversation_model_keeps_assessment_resumable(client, tmp_path, monkeypatch):
    service, sid, aid = registered_case(client, tmp_path)
    scope = propose_scope(client, sid, aid)
    state = service.load(sid)
    previous = state["model_selection"]
    state["model_selection"] = {"provider_id": "removed-service", "model": "removed", "effort": None}
    service.sessions.save(state)
    response = client.post(f"/api/sessions/{sid}/assessment/approve", json={
        "scope_id": scope["scope_id"], "scope_digest": scope["scope_digest"]})
    assert response.status_code == 409
    assert response.json()["detail"] == "model_selection_unavailable"
    state = service.load(sid)
    assert state["_assessment"]["status"] == "blocked"
    assert state["_assessment"]["stop_reason"] == "model_selection_unavailable"
    assert state["_assessment"]["authorization"] is not None
    assert state["_assessment"]["model_turns_used"] == 0
    assert not service.execution.has_pending(sid)
    state["model_selection"] = previous
    service.sessions.save(state)
    monkeypatch.setattr("bridge.web.provider.converse", next_check_or_stop)
    response = client.post(f"/api/sessions/{sid}/assessment/resume", json={
        "scope_id": scope["scope_id"], "scope_digest": scope["scope_digest"]})
    assert response.status_code == 200, response.json()
    assert settle(client, sid)["_assessment_state"]["tool_runs_used"] == 1
