"""Scope consent admits exact registered requests; it is not a science attestation."""
from __future__ import annotations

from dataclasses import replace
import importlib
import json

import pytest

from test_web_service import client, settle
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


def settle_assessment(client, sid):
    import time
    until = time.monotonic() + 90
    while time.monotonic() < until:
        value = client.get(f"/api/sessions/{sid}").json()
        if value["assessment"]["status"] != "running":
            return value
        time.sleep(.05)
    pytest.fail("assessment did not finish")


def approve_scope(client, sid, scope):
    response = client.post(f"/api/sessions/{sid}/assessment/approve", json={
        "scope_id": scope["scope_id"], "scope_digest": scope["scope_digest"],
    })
    assert response.status_code == 200, response.json()
    return response.json()


def test_completed_qc_scope_binds_exact_v2_artifact_not_legacy_schema_match(
        client, tmp_path, monkeypatch):
    from pathlib import Path
    from test_web_inputs import selected_p002_context
    from test_web_intake import stage, stated_facts
    from test_web_service import confirm_change
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



def producer_scientific_case(client, tmp_path, monkeypatch, *, with_producers=True):
    """One synthetic upload and real QC/cell-state producers; no backend request fixture."""
    import anndata as ad
    from test_cell_state import _write_query, _build_snapshot
    from test_input_qc import _lineage_metadata, _versioned_ref
    from test_web_service import new_session, confirm_change
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
                     "biological_unit_lineage": lineage}})
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
    service.save(state)
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
    service.save(state)
    monkeypatch.setattr("bridge.web.provider.converse", next_check_or_stop)
    approve_scope(client, sid, scope)
    done = settle_assessment(client, sid)
    assert done["assessment"]["tool_runs_used"] == 1
    assert done["assessment"]["stop_reason"] == "no_discriminating_check"
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



def test_product_case_version_tracks_real_producer_and_manifest_content(
        client, tmp_path, monkeypatch):
    from bridge.web.assessment import AssessmentScope
    from test_web_inputs import approve
    from test_web_service import confirm_change
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
        service.save(state)
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
    service.save(state)
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
    service.save(state)
    response = client.post(f"/api/sessions/{sid}/analysis-inputs",
                           json=choice("P0-05", "hard_count_accounting", objects))
    assert response.status_code == 200, response.json()
    return objects


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
    service.save(state)
    monkeypatch.setattr("bridge.web.provider.converse", next_check_or_stop)
    approve_scope(client, sid, scope)
    done = settle_assessment(client, sid)
    assert done["assessment"]["tool_runs_used"] == 1
    assert done["assessment"]["stop_reason"] == "no_discriminating_check"
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
    roots["measurement_spec"].update(independence_group_kind="donor")
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
    service.save(state)
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
    service.save(state)
    explicit = select_process_roots(client, sid, tmp_path, case, view)
    scope = propose_scope(client, sid, aid, "P0-06", "method_runtime_source_bound")
    state = service.load(sid)
    original_count = len(state["_input_objects"])
    row, = service.inputs.assessment_candidates(state, AssessmentScope.model_validate(state["_assessment"]["scope"]))
    assert row["blockers"] == [], row["blockers"]
    refs = {item.role: item for item in row["request"].object_inputs}
    actual_case = service.inputs.verify(state, state["_input_objects"][refs["product_case"].input_id])
    assert actual_case == case
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
    assert len(state["_input_objects"]) == original_count + 1
    assert refs["protocol_ir"].input_id == next(item["input_id"] for item in explicit if item["role"] == "protocol_ir")
    service.save(state)
    monkeypatch.setattr("bridge.web.provider.converse", next_check_or_stop)
    approve_scope(client, sid, scope)
    done = settle_assessment(client, sid)
    assert done["assessment"]["tool_runs_used"] == 1
    assert done["assessment"]["stop_reason"] == "no_discriminating_check"
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
    assert done["assessment"]["tool_runs_used"] == 2, done["assessment"]
    assert done["assessment"]["stop_reason"] == "no_discriminating_check"
    state = service.load(sid)
    assert [row["tool_id"] for row in state["_tool_runs"]] == ["P0-01", "P0-06"]
    assert state["_assessment"]["scope"]["binding"]["data_view"] is None
    receipt = state["_tool_runs"][-1]
    run = json.loads((service.directory(sid) / "receipts" / receipt["file"]).read_bytes())
    view = run["result"]["input_contract"]["data_view"]
    assert view["parent_asset_id"] == aid and view["n_observations"] == 4
    assert run["measurements"] == []


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
        assert rejected.status_code == 409 and rejected.json()["detail"] == "scope_resource_changed"
    finally:
        resource.write_bytes(raw)
    assert service.assessment.check(state) is None
    assert len([item for item in state["_input_objects"].values() if item["source"] == "agent_constructed"]) == 1
    service.save(state)
    monkeypatch.setattr("bridge.web.provider.converse", next_check_or_stop)
    approve_scope(client, sid, scope)
    done = settle_assessment(client, sid)
    assert done["assessment"]["tool_runs_used"] == 1
    assert done["assessment"]["stop_reason"] == "no_discriminating_check"
    after = service.load(sid)
    receipt = after["_tool_runs"][-1]
    run = json.loads((service.directory(sid) / "receipts" / receipt["file"]).read_bytes())
    assert run["result"]["runtime_mode"] == "exploratory_process"
    assert run["result"]["domain_score"] is None
    assert run["result"]["interpretation_scope"] == "descriptive_only"
    assert run["result"]["n_independent_replicates"] is None
    assert run["measurements"] == []


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
        service.save(state)
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
    assert done["assessment"]["status"] == "blocked"
    assert done["assessment"]["stop_reason"] == "completion_contract_unavailable"
    assert done["assessment"]["model_turns_used"] == 1
    assert done["assessment"]["tool_runs_used"] == 0
    assert done["assessment"]["evidence"] == []
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
    assert done["assessment"]["status"] == "stopped", done
    assert done["assessment"]["stop_reason"] == "no_discriminating_check"
    assert done["assessment"]["tool_runs_used"] == 1
    assert done["assessment"]["model_turns_used"] == 2
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
    evidence = done["assessment"]["evidence"][0]
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
    done = settle(client, sid)["assessment"]
    assert done["stop_reason"] == reason
    assert done["tool_runs_used"] == done["model_turns_used"] == 1
    response = client.post(f"/api/sessions/{sid}/assessment/resume",
                          json={"scope_id": scope["scope_id"], "scope_digest": scope["scope_digest"]})
    assert response.status_code == 409 and response.json()["detail"] == reason
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
    done = settle(client, sid)["assessment"]
    assert done["stop_reason"] == "unavailable_or_repeated_action"
    assert done["tool_runs_used"] == 1 and done["model_turns_used"] == 2
    assert len(service.load(sid)["_tool_runs"]) == 1


def test_malformed_provider_turn_is_consumed_without_dispatch(client, tmp_path, monkeypatch):
    service, sid, aid = registered_case(client, tmp_path)
    scope = propose_scope(client, sid, aid)
    def malformed(*args):
        from bridge.web.provider import parse_action
        return parse_action({"content": '{"action":"assessment","decision":{"action":"check","option_id":"not-valid"}}'})
    monkeypatch.setattr("bridge.web.provider.converse", malformed)
    approve_scope(client, sid, scope)
    done = settle(client, sid)["assessment"]
    assert done["stop_reason"] == "provider_action_invalid_or_unavailable"
    assert done["model_turns_used"] == 1 and done["tool_runs_used"] == 0
    assert service.load(sid)["_tool_runs"] == []


def test_scope_reports_actual_missing_selection_and_scientific_review_blocker(client, tmp_path):
    from test_web_report_inputs import confirmed_case
    service, sid, aid, _ = confirmed_case(client, tmp_path)
    scope = propose_scope(client, sid, aid, "P0-03", "default")
    approve_scope(client, sid, scope)
    done = settle(client, sid)["assessment"]
    assert done["stop_reason"] == "no_eligible_check"
    assert done["blockers"] == [{"tool_id": "P0-03", "mode_id": "default",
                                "reason_codes": ["scientific_source_review_pending"]}]
    assert done["tool_runs_used"] == done["model_turns_used"] == 0
    assert service.load(sid)["_tool_runs"] == []
    scope = propose_scope(client, sid, aid, "P0-06", "method_runtime")
    approve_scope(client, sid, scope)
    done = settle(client, sid)["assessment"]
    assert done["blockers"][0]["reason_codes"] == ["registered_selection_required"]


def test_disabled_sharing_does_not_send_result_or_private_facts_and_requires_opt_in(client, tmp_path, monkeypatch):
    service, sid, aid = registered_case(client, tmp_path)
    assert service.settings.share_result_summaries is False
    scope = propose_scope(client, sid, aid)
    def model(settings, messages, context):
        wire = json.dumps([messages, context])
        for secret in ("PRIVATE_NAME", "PRIVATE_SOURCE", "dopaminergic neurons", "private-cell-a", str(tmp_path)):
            assert secret not in wire
        assert context["evidence"] == [] and context["results_sent_to_model"] is False
        return next_check_or_stop(settings, messages, context)
    monkeypatch.setattr("bridge.web.provider.converse", model)
    approve_scope(client, sid, scope)
    done = settle(client, sid)["assessment"]
    assert done["stop_reason"] == "result_sharing_disabled"
    assert done["tool_runs_used"] == done["model_turns_used"] == 1
    assert done["evidence"][0]["summary"]["primary_denominator"]["n_observations"] == 10


@pytest.mark.parametrize("change", ["revision", "object", "reference"])
def test_scope_fences_drift_before_approval(client, tmp_path, change):
    from pathlib import Path
    from bridge.web.app import write_file
    service, sid, aid = registered_case(client, tmp_path)
    scope = propose_scope(client, sid, aid)
    state = service.load(sid)
    if change == "revision":
        state["_input_revision"] += 1
        service.save(state)
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
    assert response.json()["detail"] in {"input_revision_changed", "scope_resource_changed"}
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
        assert stopped.json()["assessment"]["stop_reason"] == "user_stopped"
    finally:
        released.set()
    done = settle(client, sid)
    assert done["assessment"]["status"] == "stopped"
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
    done = settle(client, sid)["assessment"]
    assert done["stop_reason"] == "invalid_evidence_alias"
    assert service.load(sid)["_tool_runs"] == []


@pytest.mark.parametrize("requested_reason,expected_reason,expected_status", [
    pytest.param("no_discriminating_check", "no_discriminating_check", "stopped", id="read_only_query"),
    pytest.param("evidence_requirements_reached", "completion_contract_unavailable", "blocked",
                 id="open_requirements_completion_requested"),
])
def test_registered_graph_query_reuses_version_and_has_receipt_without_new_artifacts(
        client, tmp_path, monkeypatch, requested_reason, expected_reason, expected_status):
    from test_web_report_inputs import confirmed_case, run_stage
    service, sid, aid, body = confirmed_case(client, tmp_path)
    run_stage(client, sid, body, "P0-08")
    run_stage(client, sid, body, "P0-09")
    state = service.load(sid)
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
        assert len(context["evidence"][0]["summary"]["requirements"]) == 5
        assert all(item["state"] == "open" for item in context["evidence"][0]["summary"]["requirements"])
        return Action.model_validate({"action": "assessment", "decision": {
            "action": "stop", "reason": requested_reason}})
    monkeypatch.setattr("bridge.web.provider.converse", query_then_stop)
    approve_scope(client, sid, scope)
    done = settle(client, sid)
    assert done["assessment"]["stop_reason"] == expected_reason, done["assessment"]
    assert done["assessment"]["status"] == expected_status
    assert done["assessment"]["tool_runs_used"] == 1
    assert done["assessment"]["evidence"][0]["summary"]["graph_version"] == 1
    assert len(done["assessment"]["evidence"][0]["summary"]["requirements"]) == 5
    assert all(row["state"] == "open" for row in done["assessment"]["evidence"][0]["summary"]["requirements"])
    after = service.load(sid)
    assert after["_input_revision"] == before["_input_revision"]
    assert len(after["_tool_runs"]) == len(before["_tool_runs"]) + 1
    assert after["_input_objects"] == before["_input_objects"]
    assert after["_artifacts"] == before["_artifacts"]
    assert after["_assessment"]["model_turns"][-1]["decision"]["reason"] == requested_reason
    assert "evidence_requirements_reached" not in json.dumps(done["assessment"])
    receipt = json.loads((service.directory(sid) / "receipts" / after["_tool_runs"][-1]["file"]).read_bytes())
    assert receipt["artifacts"] == [] and receipt["measurements"] == []
    assert receipt["result"]["graph_id"] == graph["graph_id"]
    assert receipt["result"]["graph_version"] == 1


@pytest.mark.parametrize("tool,module", [("P0-03", "test_p0_03_target_regional"),
                                          ("P0-04", "test_p0_04_developmental_compatibility")])
def test_real_target_and_development_results_expose_canonical_units_and_denominators(
        client, tmp_path, monkeypatch, tool, module):
    from bridge.web.app import write_file
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
    done = settle(client, sid)["assessment"]
    assert done["tool_runs_used"] == 1 and done["stop_reason"] == "no_discriminating_check", done
    evidence = done["evidence"][0]
    assert evidence["state"] == "available"
    measurements = evidence["measurements"]
    assert len(measurements) == (3 if tool == "P0-03" else 10)
    assert all(item["unit"] == "fraction" for item in measurements)
    assert all(item["measurement_class"] == "gate_input_measurement" for item in measurements)
    assert all(item["domain_score"] is None for item in measurements)
    if tool == "P0-03":
        channel = evidence["summary"]["channels"][0]
        assert channel["target_identity_fraction"] == {"role": "configured_target_identity", "numerator": 60, "denominator": 100, "fraction": 0.6}
        assert channel["regional_fidelity_fraction"] == {"role": "configured_regional_fidelity", "numerator": 60, "denominator": 80, "fraction": 0.75}
    else:
        assert evidence["summary"]["whole_product_profile"]["denominator"] == 12
        assert evidence["summary"]["target_related_profile"]["denominator"] == 11


def test_restart_interruption_retains_durable_budget_and_does_not_execute(client, tmp_path, monkeypatch):
    from bridge.web.app import Service
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
    service.save(dispatched)
    restored = Service(service.settings)
    try:
        state = restored.load(sid)
        assert state["_assessment"]["status"] == "interrupted"
        assert state["_assessment"]["stop_reason"] == "restart_interrupted"
        assert state["_assessment"]["model_turns_used"] == 1
        assert state["_assessment"]["authorization"] == dispatched["_assessment"]["authorization"]
        assert state["_tool_runs"] == []
    finally:
        restored.pool.shutdown(wait=True)


def test_scope_data_view_and_approval_limits_are_visible_but_resources_remain_private(client, tmp_path):
    service, sid, aid = registered_case(client, tmp_path)
    scope = propose_scope(client, sid, aid)
    assert scope["data_view"]["state"] == "not_available"
    assert scope["stop_conditions"] == ["input_or_resource_change", "explicit_stop", "finite_budgets",
                                        "no_eligible_check", "necessary_fact", "result_sharing_disabled"]
    assert scope["resources"] and all(set(row) == {"alias", "schema_ref", "object_version", "sha256", "source"}
                                      for row in scope["resources"])
    assert scope["max_tool_runs"] == 3 and scope["max_model_turns"] == 4
    assert "PRIVATE_NAME" not in json.dumps(scope)


@pytest.mark.parametrize("mode", ["comparison_initial_v2", "invented"])
def test_disallowed_or_unknown_mode_never_starts_scope(client, tmp_path, mode):
    service, sid, aid = registered_case(client, tmp_path)
    response = client.post(f"/api/sessions/{sid}/assessment/propose", json={
        "question": "Check evidence", "upload_id": aid, "allowed_modes": [{"tool_id": "P0-09", "mode_id": mode}],
        "max_tool_runs": 3, "max_model_turns": 4})
    assert response.status_code == 422
    assert service.load(sid).get("_assessment") is None


def test_result_bound_hypothesis_is_stored_without_changing_scientific_objects(client, tmp_path, monkeypatch):
    service, sid, aid = registered_case(client, tmp_path)
    service.settings = replace(service.settings, share_result_summaries=True)
    scope = propose_scope(client, sid, aid)
    objects = service.load(sid)["_input_objects"]
    def model(settings, messages, context):
        from bridge.web.provider import Action
        assert context["question"] == scope["question"]
        if not context["evidence"]:
            return next_check_or_stop(settings, messages, context)
        return Action.model_validate({"action": "assessment", "decision": {
            "action": "explain", "text": "This candidate interpretation still needs discriminating evidence.",
            "hypotheses": [{"statement": "The registered target composition may explain this signal.",
                "evidence_aliases": [context["evidence"][0]["alias"]],
                "competing_explanation": "An unresolved role assignment may also explain it.",
                "discriminating_check": "P0-05"}]}})
    monkeypatch.setattr("bridge.web.provider.converse", model)
    approve_scope(client, sid, scope)
    done = settle(client, sid)
    assert done["assessment"]["stop_reason"] == "explanation_complete"
    assert len(done["assessment"]["hypotheses"]) == 1
    assert done["assessment"]["hypotheses"][0]["evidence_aliases"] == [
        done["assessment"]["evidence"][0]["alias"]]
    current = service.load(sid)
    assert all(current["_input_objects"][key] == value for key, value in objects.items())
    assert current["_input_revision"] == scope["input_revision"]
    assert done["assessment"]["scope_grants_scientific_approval"] is False


def test_reference_drift_during_model_turn_blocks_before_admission(client, tmp_path, monkeypatch):
    service, sid, aid = registered_case(client, tmp_path)
    scope = propose_scope(client, sid, aid)
    def model(settings, messages, context):
        service.settings = replace(service.settings, cell_state_measurement_spec_ref=None)
        return next_check_or_stop(settings, messages, context)
    monkeypatch.setattr("bridge.web.provider.converse", model)
    approve_scope(client, sid, scope)
    done = settle(client, sid)
    assert done["assessment"]["stop_reason"] == "scope_resource_changed"
    assert done["assessment"]["tool_runs_used"] == 0
    assert done["assessment"]["model_turns_used"] == 1
    assert service.load(sid)["_tool_runs"] == []


def test_worker_capacity_rejection_keeps_scope_authorization_resumable(client, tmp_path, monkeypatch):
    service, sid, aid = registered_case(client, tmp_path)
    scope = propose_scope(client, sid, aid)
    held = 0
    while service.capacity.acquire(blocking=False):
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
            service.capacity.release()
    monkeypatch.setattr("bridge.web.provider.converse", next_check_or_stop)
    response = client.post(f"/api/sessions/{sid}/assessment/resume", json={
        "scope_id": scope["scope_id"], "scope_digest": scope["scope_digest"]})
    assert response.status_code == 200, response.json()
    assert settle(client, sid)["assessment"]["tool_runs_used"] == 1


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
    assert done["assessment"]["stop_reason"] == "no_discriminating_check", done
    assert done["assessment"]["tool_runs_used"] == 1
    assert done["assessment"]["model_turns_used"] == 2
    assert service.load(sid)["_input_revision"] == scope["input_revision"]


def test_real_exploratory_missing_gene_keeps_partial_and_all_96_cells(client, tmp_path, monkeypatch):
    from test_p0_06_exploratory import _request, _payload, _with_input
    from test_web_service import new_session, confirm_change
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
    evidence = done["assessment"]["evidence"][0]
    assert evidence["state"] == "available", evidence
    assert evidence["execution_state"] == "partial"
    assert evidence["interpretation_scope"] == "exploratory"
    assert evidence["measurements"] == []
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
    assert "observation_id" not in json.dumps(result) and "ABSENT" not in json.dumps(result)
    # A caller changes the registered DataView descriptor: this is a new fact/input
    # revision even when its underlying matrix checksum remains unchanged.
    next_scope = propose_scope(client, sid, aid, "P0-06", "exploratory_process")
    payload["data_view"]["view_id"] = "view:user-selected-revision"
    changed = _with_input(request, payload)
    new_objects = upload_request(client, sid, changed, "exploratory_process")
    selected = client.post(f"/api/sessions/{sid}/analysis-inputs",
        json=choice("P0-06", "exploratory_process", new_objects, [aid]))
    assert selected.status_code == 200
    assert selected.json()["assessment"]["status"] == "blocked"
    assert selected.json()["assessment"]["stop_reason"] == "input_revision_changed"
    rejected = client.post(f"/api/sessions/{sid}/assessment/approve", json={
        "scope_id": next_scope["scope_id"], "scope_digest": next_scope["scope_digest"]})
    assert rejected.status_code == 409
    assert len(service.load(sid)["_tool_runs"]) == 1


def test_unrelated_manual_selection_is_not_opened_or_bound_to_scope(client, tmp_path):
    from pathlib import Path
    from bridge.web.app import write_file
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
