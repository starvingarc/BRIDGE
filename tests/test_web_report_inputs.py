"""Web-owned missingness inputs still run only through explicit P0-08 approval."""
from __future__ import annotations

import json
import pytest

from test_web_service import client, settle
from test_web_scientific_inputs import science_case, propose, candidate
from test_web_intake import stage, stated_facts
from test_web_service import confirm_change


def measured_development_case(client, tmp_path, monkeypatch):
    from test_web_assessment import (producer_scientific_case, select_target_roots,
        select_development_roots, propose_scope, approve_scope, settle_assessment, next_check_or_stop)
    service, sid, aid = producer_scientific_case(client, tmp_path, monkeypatch)
    select_target_roots(client, sid)
    select_development_roots(client, sid)
    scope = propose_scope(client, sid, aid, "P0-04", "default")
    monkeypatch.setattr("bridge.web.provider.converse", next_check_or_stop)
    approve_scope(client, sid, scope)
    settle_assessment(client, sid)
    state = service.load(sid)
    receipt = state["_tool_runs"][-1]
    assert receipt["tool_id"] == "P0-04" and receipt["state"] == "succeeded"
    run, outputs = service.inputs.producer_objects(state, receipt, "P0-04", {"measurement_result_v2"})
    assert len(outputs["measurement_result_v2"]) == 10
    return service, sid, aid, run, outputs["measurement_result_v2"]


def select_measured_requirements(client, sid, run, *, explicit=None, domain="developmental_compatibility", with_family=False):
    from bridge.web.scientific_inputs import encoded
    from bridge.tool_packages.p0_08_evidence_sufficiency.models import DomainGateInput
    service = client.app.state.service
    state = service.load(sid)
    refs = {row.role: row for row in run.request.object_inputs}
    case = service.inputs.verify(state, state["_input_objects"][refs["product_case"].input_id])
    validation_id = None
    if with_family:
        from test_p0_08_evidence_sufficiency import _validation
        spec = service.inputs.verify(state, state["_input_objects"][refs["measurement_spec"].input_id])
        validation = _validation(measurement_spec_ref=spec["measurement_spec_id"], tool_ref="P0-04",
            evidence_family_id="evidence-family:synthetic-development", required_for_interpretation=False,
            validation_state="not_assessed", environment_state="not_assessed",
            context_of_use_state="not_assessed", source_family_ref="source-family:synthetic-assessment",
            source_holdout_state="not_assessed", modality_holdout_state="not_assessed",
            calibration_state="not_assessed", ood_state="not_assessed")
        validation_id = service.inputs.add_object(state, tool_id="P0-08", mode_id="default", role="validation_record",
            schema_ref="bridge://schemas/evidence-validation-record/v0.1", object_version="0.1.0", data=encoded(validation))
    template = DomainGateInput(domain_gate_input_id="domain-gate-input:synthetic-development",
        object_version="0.1.0", created_at="2026-09-01T00:00:00Z",
        product_case={"object_id": case["product_case_id"], "object_version": case["case_version"],
                      "provenance_refs": [row["object_id"] for row in case["provenance_refs"]]},
        product_definition={**case["product_definition_ref"], "provenance_refs": ["source:synthetic-requirements-only"]}, domain_id=domain,
        measurement_spec_input_id=refs["measurement_spec"].input_id,
        measurement_result_input_ids=explicit or [], validation_record_input_ids=[validation_id] if validation_id else [],
        method_requirement="required", prior_requirement="required",
        required_sensitivity_kinds=["reference"], task_validation_state="not_assessed",
        evidence_refs=["evidence:synthetic-requirements"],
        provenance_refs=["source:synthetic-requirements-only"])
    tid = service.inputs.add_object(state, tool_id="P0-08", mode_id="default",
        role="domain_gate_input", schema_ref="bridge://schemas/domain-gate-input/v0.1",
        object_version="0.1.0", data=encoded(template.model_dump(mode="json")))
    service.inputs.package_options(state)
    gate_id = next(identifier for identifier, row in state["_input_objects"].items()
                  if row["source"] == "package_resource" and row["label"] == "gate_rule_spec")
    choices = [{"role": "domain_gate_input", "input_id": tid},
               {"role": "gate_rule_spec", "input_id": gate_id},
               {"role": "measurement_spec", "input_id": refs["measurement_spec"].input_id}]
    if validation_id:
        choices.append({"role": "validation_record", "input_id": validation_id})
    service.save(state)
    from test_web_inputs import choice
    response = client.post(f"/api/sessions/{sid}/analysis-inputs", json=choice("P0-08", "default", choices))
    assert response.status_code == 200, response.json()
    return tid


def test_measured_domain_candidate_binds_real_values_and_preserves_requirements(client, tmp_path, monkeypatch):
    from bridge.web.assessment import AssessmentScope
    from test_web_assessment import propose_scope, approve_scope, settle_assessment, next_check_or_stop
    service, sid, aid, run, measurements = measured_development_case(client, tmp_path, monkeypatch)
    template_id = select_measured_requirements(client, sid, run)
    scope = propose_scope(client, sid, aid, "P0-08", "default")
    state = service.load(sid)
    before_revision, before_selection = state["_input_revision"], json.loads(json.dumps(state["_input_selections"]))
    typed = AssessmentScope.model_validate(state["_assessment"]["scope"])
    row, = service.inputs.assessment_candidates(state, typed)
    assert row["blockers"] == [], row["blockers"]
    assert {identifier for identifier, _ in measurements} <= set(typed.binding["resources"])
    refs = {ref.role: ref for ref in row["request"].object_inputs if ref.role != "measurement_result"}
    domain = service.inputs.verify(state, state["_input_objects"][refs["domain_gate_input"].input_id])
    assert domain["method_requirement"] == domain["prior_requirement"] == "required"
    assert domain["required_sensitivity_kinds"] == ["reference"]
    assert domain["task_validation_state"] == "not_assessed"
    assert domain["evidence_refs"] == ["evidence:synthetic-requirements"]
    bound = {ref.input_id: service.inputs.verify(state, state["_input_objects"][ref.input_id])
             for ref in row["request"].object_inputs if ref.role == "measurement_result"}
    assert bound == dict(measurements)
    assert {value["denominator"] for value in bound.values()} == {2, 4}
    assert all(value["unit"] == "fraction" and value["evidence_state"] == "inferred" for value in bound.values())
    assert any(value["raw_value"] == 0.5 and value["numerator"] == 2 and value["denominator"] == 4 for value in bound.values())
    again, = service.inputs.assessment_candidates(state, typed)
    assert again["fingerprint"] == row["fingerprint"]
    assert state["_input_revision"] == before_revision and state["_input_selections"] == before_selection
    assert template_id in state["_input_objects"][refs["domain_gate_input"].input_id]["derivation_inputs"]
    from bridge.web.inputs import Selection
    template = service.inputs.verify(state, state["_input_objects"][template_id])
    saved = Selection.model_validate(state["_input_selections"]["P0-08"])
    mutations = [
        ("case", {"product_case": {**template["product_case"], "object_id": "product-case:other"}}, "applicable_measured_source_required"),
        ("definition", {"product_definition": {**template["product_definition"], "object_id": "product-definition:other"}}, "applicable_measured_source_required"),
        ("spec", {"measurement_spec_input_id": "0" * 32}, "measured_measurement_spec_required"),
        ("subset", {"measurement_result_input_ids": ["0" * 32]}, "canonical_measurement_subset_mismatch"),
        ("domain", {"domain_id": "off_target_control"}, "measured_producer_domain_mismatch"),
        ("qc", {"qc_profile_input_id": "0" * 32}, "measured_qc_binding_mismatch"),
    ]
    for label, change, reason in mutations:
        clone, bound_scope, supplied = rebound_test_input(service, state, typed, saved,
            "domain_gate_input", {**template, **change})
        with pytest.raises(ValueError, match=reason):
            service.report_inputs.assessment_selection(clone, bound_scope, typed.allowed_modes[0], supplied)
    clone, bound_scope, supplied = rebound_test_input(service, state, typed, saved,
        "domain_gate_input", {**template, "measurement_result_input_ids": [measurements[0][0]]})
    subset = service.report_inputs.assessment_selection(clone, bound_scope, typed.allowed_modes[0], supplied)
    assert [ref.input_id for ref in subset.object_inputs if ref.role == "measurement_result"] == [measurements[0][0]]
    with pytest.raises(ValueError, match="measured_domain_requirements_required"):
        service.report_inputs.assessment_selection(state, typed, typed.allowed_modes[0],
            saved.model_copy(update={"object_inputs": []}))
    service.save(state)
    monkeypatch.setattr("bridge.web.provider.converse", next_check_or_stop)
    approve_scope(client, sid, scope)
    done = settle_assessment(client, sid)
    assert done["assessment"]["tool_runs_used"] == 1
    after = service.load(sid)
    receipt = after["_tool_runs"][-1]
    assert receipt["tool_id"] == "P0-08" and receipt["state"] == "succeeded"
    result = json.loads((service.directory(sid) / "receipts" / receipt["file"]).read_bytes())["result"]
    profile, = result["profiles"]
    assert profile["measurement_evidence_state_counts"]["inferred"] == 10
    assert profile["domain_score"] is None and profile["score_state"] == "unavailable"



def select_measured_graph_assertions(client, sid, run, measurements, *, numerical=True, domains=("developmental_compatibility",)):
    """Explicit synthetic assertions/registries; no Web-owned metric-to-claim rule."""
    from bridge.web.scientific_inputs import encoded
    from bridge.tool_packages.p0_09_evidence_compiler.models import (
        EvidenceCompilationBundle, ClaimRegistry, EvidenceFamilyRegistry, ReconciliationSpecRegistry)
    from test_web_inputs import choice
    service = client.app.state.service
    state = service.load(sid)
    refs = {row.role: row for row in run.request.object_inputs}
    case = service.inputs.verify(state, state["_input_objects"][refs["product_case"].input_id])
    definition = service.inputs.verify(state, state["_input_objects"][refs["product_definition_card"].input_id])
    case_ref = {"object_id": case["product_case_id"], "object_version": case["case_version"]}
    definition_ref = case["product_definition_ref"]
    catalog = []
    def entry(identity, node_type, schema, checksum):
        catalog.append({**identity, "node_type": node_type, "schema_ref": schema, "content_hash": checksum})
    entry(case_ref, "ProductCase", refs["product_case"].schema_ref, refs["product_case"].sha256)
    entry(definition_ref, "ProductDefinitionCard", refs["product_definition_card"].schema_ref, refs["product_definition_card"].sha256)
    # The preparation catalog assertion is caller-supplied synthetic metadata, not a Web-created biological unit.
    from hashlib import sha256
    entry(case["sample_or_preparation_ref"], "Preparation", "bridge://schemas/preparation/v0.1",
          sha256(b"synthetic preparation product-a, donor-a; no independent replicate claimed").hexdigest())
    source_ref = {"object_id": "tool-run:" + run.run_id, "object_version": run.tool_version}
    receipt = next(row for row in state["_tool_runs"] if row["tool_id"] == "P0-04")
    entry(source_ref, "ToolRun", "bridge://schemas/tool-run/v0.2", receipt["sha256"])
    spec = service.inputs.verify(state, state["_input_objects"][refs["measurement_spec"].input_id])
    spec_ref = {"object_id": spec["measurement_spec_id"], "object_version": spec["version"]}
    entry(spec_ref, "MeasurementSpec", refs["measurement_spec"].schema_ref, refs["measurement_spec"].sha256)
    common = {"registry_version": "0.1.0", "status": "candidate", "created_at": "2026-09-01T00:00:00Z"}
    claims, missing, candidates = [], [], []
    reconciliation_ref = {"object_id": "reconciliation-spec:synthetic-description", "object_version": "0.1.0"}
    for domain in domains:
        claim_ref = {"object_id": "claim:synthetic-" + domain, "object_version": "0.1.0"}
        claims.append({"claim_id": claim_ref["object_id"], "version": "0.1.0",
            "claim_type": "descriptive_domain_observation", "domain_id": domain,
            "claim_target_ref": case["product_case_id"] + "@" + case["case_version"],
            "biological_context_ref": definition_ref, "allowed_relations": ["supports", "contradicts"],
            "reconciliation_spec_ref": reconciliation_ref, "status": "candidate",
            "requirement_specs": [{"requirement_key": "interpreted_measurement", "channel_role": "interpreted_transcriptomic",
                                  "required_modality": "scRNA-seq", "blocking_scope": "claim", "required": True}]})
        missing.append({"observation_id": "missing-evidence:synthetic-" + domain,
            "product_case_ref": case_ref, "claim_ref": claim_ref, "requirement_key": "interpreted_measurement",
            "reason_code": "required_channel_not_provided", "source_contract_ref": claim_ref,
            "provenance_refs": ["source:synthetic-interpretation-policy"], "observed_at": common["created_at"]})
    if numerical:
        for identifier, measurement in measurements:
            record = state["_input_objects"][identifier]
            measurement_ref = {"object_id": measurement["measurement_id"], "object_version": record["object_version"]}
            artifact_ref = {"object_id": record["artifact_id"], "object_version": record["object_version"]}
            entry(measurement_ref, "MeasurementResult", record["schema_ref"], record["sha256"])
            entry(artifact_ref, "Artifact", "bridge://schemas/artifact/v0.1", record["sha256"])
            observation_claim = {**claims[0], "claim_id": "claim:synthetic-observation-" + identifier}
            claims.append(observation_claim)
            candidates.append({"candidate_id": "evidence-candidate:" + identifier,
                "product_case_ref": case_ref, "sample_or_preparation_ref": case["sample_or_preparation_ref"],
                "domain_id": "developmental_compatibility", "measurement_result_ref": measurement_ref,
                "measurement_spec_ref": spec_ref, "metric_id": measurement["metric_name"],
                "value": measurement["raw_value"], "unit": measurement["unit"],
                "numerator": measurement["numerator"], "denominator": measurement["denominator"], "interval": None,
                "claim_ref": {"object_id": observation_claim["claim_id"], "object_version": "0.1.0"},
                "biological_context": {"context_id": definition_ref["object_id"], "context_version": definition_ref["object_version"]},
                "relation": "supports", "evidence_state": measurement["evidence_state"], "evidence_tier": "shadow",
                "applicability": "applicable", "evidence_family_ref": {"object_id": "evidence-family:synthetic-development", "object_version": "0.1.0"},
                "sufficiency_profile_input_id": "bind-current-canonical-sufficiency",
                "tool_run_ref": source_ref, "tool_run_execution_state": run.execution_state.value,
                "artifact_refs": [artifact_ref], "provenance_refs": measurement["provenance_refs"],
                "revision_action": "create", "created_at": common["created_at"]})
    models = {
        "compilation_bundle": EvidenceCompilationBundle(bundle_id="evidence-compilation-bundle:synthetic-measured",
            bundle_version="0.1.0", graph_kind="case", product_case_ref=case_ref, object_catalog=catalog,
            candidate_records=candidates, missing_observations=missing, created_at=common["created_at"],
            provenance_refs=["source:synthetic-assertions-not-reusable-policy"]),
        "claim_registry": ClaimRegistry(**common, registry_id="BRIDGE-CLAIM-REGISTRY-v0.1", claims=claims),
        "evidence_family_registry": EvidenceFamilyRegistry(**common, registry_id="BRIDGE-EVIDENCE-FAMILY-REGISTRY-v0.1",
            families=[{"evidence_family_id": "evidence-family:synthetic-development", "version": "0.1.0", "family_type": "shared_data",
                "channel_role": "transcriptomic", "shared_source_refs": [case["sample_or_preparation_ref"]["object_id"] + "@1.0.0"],
                "independence_scope": "one_preparation_no_replication", "known_dependencies": [],
                "rationale": "All ten fractions share one four-cell source; not ten independent votes.", "status": "unreviewed"}]),
        "reconciliation_spec_registry": ReconciliationSpecRegistry(**common, registry_id="BRIDGE-RECONCILIATION-SPEC-REGISTRY-v0.1",
            specs=[{"reconciliation_spec_id": reconciliation_ref["object_id"], "version": "0.1.0",
                "claim_type": "descriptive_domain_observation", "required_channel_roles": ["transcriptomic"],
                "primary_channel_roles": ["transcriptomic"], "minimum_independent_families_by_role": {"transcriptomic": 1},
                "allowed_evidence_states": ["measured", "inferred"], "conflict_rule": "family_dedup_then_channel_resolution",
                "consensus_rule": "unanimous_independent_confirmation",
                "integration_sensitivity_rule": "integration_role_disagrees_with_resolved_direction",
                "missing_behavior": "insufficient_evidence", "status": "candidate"}]),
    }
    schemas = {"compilation_bundle": "evidence-compilation-bundle", "claim_registry": "claim-registry",
               "evidence_family_registry": "evidence-family-registry", "reconciliation_spec_registry": "reconciliation-spec-registry"}
    choices = []
    for role, model in models.items():
        identifier = service.inputs.add_object(state, tool_id="P0-09", mode_id="case_initial_v2", role=role,
            schema_ref="bridge://schemas/" + schemas[role] + "/v0.1", object_version="0.1.0",
            data=encoded(model.model_dump(mode="json")))
        choices.append({"role": role, "input_id": identifier})
    service.save(state)
    response = client.post(f"/api/sessions/{sid}/analysis-inputs", json=choice("P0-09", "case_initial_v2", choices))
    assert response.status_code == 200, response.json()
    return choices


def measured_graph_case(client, tmp_path, monkeypatch):
    from bridge.web.assessment import AssessmentScope
    from test_web_assessment import propose_scope, approve_scope, settle_assessment, next_check_or_stop
    service, sid, aid, run, measurements = measured_development_case(client, tmp_path, monkeypatch)
    select_measured_requirements(client, sid, run, with_family=True)
    select_measured_graph_assertions(client, sid, run, measurements)
    scope = propose_scope(client, sid, aid, allowed_modes=[
        {"tool_id": "P0-08", "mode_id": "default"},
        {"tool_id": "P0-09", "mode_id": "case_initial_v2"},
        {"tool_id": "P0-09", "mode_id": "case_query"}], max_tool_runs=5, max_model_turns=6)
    def check_query_or_stop(settings, messages, context):
        from bridge.web.provider import Action
        option = next(iter(context["options"]), None)
        decision = ({"action": "query" if option["kind"] == "query" else "check", "option_id": option["id"]}
                    if option else {"action": "stop", "reason": "no_discriminating_check"})
        return Action.model_validate({"action": "assessment", "decision": decision})
    monkeypatch.setattr("bridge.web.provider.converse", check_query_or_stop)
    approve_scope(client, sid, scope)
    done = settle_assessment(client, sid)
    assert done["assessment"]["tool_runs_used"] == 3, done["assessment"]
    state = service.load(sid)
    graph_receipt = next(row for row in reversed(state["_tool_runs"]) if row["tool_id"] == "P0-09" and row["state"] == "succeeded")
    query = json.loads((service.directory(sid) / "receipts" / graph_receipt["file"]).read_bytes())
    assert query["artifacts"] == [] and query["measurements"] == []
    assert query["result"]["graph_version"] == 1
    records = next(service.inputs.verify(state, record) for record in state["_input_objects"].values()
        if record["source"] == "tool_output" and record["schema_ref"] == "bridge://schemas/evidence-record-set/v0.1")["records"]
    assert len(records) == 10
    assert {row["evidence_family_ref"]["object_id"] for row in records} == {"evidence-family:synthetic-development"}
    assert {row["evidence_tier"] for row in records} == {"shadow"}
    assert {row["denominator"] for row in records} == {2, 4}
    assert any(row["value"] == 0.5 and row["numerator"] == 2 and row["denominator"] == 4 for row in records)
    assert done["assessment"]["stop_reason"] == "no_discriminating_check"
    return service, sid, aid, run, measurements



def check_query_or_stop(settings, messages, context):
    from bridge.web.provider import Action
    option = next(iter(context["options"]), None)
    decision = ({"action": "query" if option["kind"] == "query" else "check", "option_id": option["id"]}
                if option else {"action": "stop", "reason": "no_discriminating_check"})
    return Action.model_validate({"action": "assessment", "decision": decision})


def rebound_test_input(service, state, scope, selection, role, payload):
    """Register an explicit alternate caller object against cloned scope roots."""
    from copy import deepcopy
    from bridge.web.scientific_inputs import encoded
    from bridge.web.inputs import ObjectChoice
    clone, bound_scope = deepcopy(state), scope.model_copy(deep=True)
    old = next(ref.input_id for ref in selection.object_inputs if ref.role == role)
    record = state["_input_objects"][old]
    identifier = service.inputs.add_object(clone, tool_id=selection.tool_id, mode_id=selection.mode_id,
        role=role, schema_ref=record["schema_ref"], object_version=record["object_version"], data=encoded(payload))
    supplied = selection.model_copy(update={"object_inputs": [
        ObjectChoice(role=ref.role, input_id=identifier if ref.role == role else ref.input_id)
        for ref in selection.object_inputs]})
    bound_scope.binding["resources"][identifier] = clone["_input_objects"][identifier]
    bound_scope.binding["selections"][selection.tool_id] = supplied.model_dump(mode="json")
    return clone, bound_scope, supplied


def test_measured_graph_candidate_accepts_only_exact_supplied_assertions(client, tmp_path, monkeypatch):
    from copy import deepcopy
    from bridge.web.assessment import AssessmentScope, AllowedMode
    from bridge.web.inputs import Selection
    service, sid, _, _, _ = measured_graph_case(client, tmp_path, monkeypatch)
    state = service.load(sid)
    scope = AssessmentScope.model_validate(state["_assessment"]["scope"])
    selection = Selection.model_validate(state["_input_selections"]["P0-09"])
    allowed = AllowedMode(tool_id="P0-09", mode_id="case_append_v2")
    bid = next(ref.input_id for ref in selection.object_inputs if ref.role == "compilation_bundle")
    template = service.inputs.verify(state, state["_input_objects"][bid])
    mutations = [
        ("value", 0.375, "measured_assertion_value_or_source_mismatch"),
        ("unit", "arbitrary", "measured_assertion_value_or_source_mismatch"),
        ("denominator", 999, "measured_assertion_value_or_source_mismatch"),
        ("numerator", 999, "measured_assertion_value_or_source_mismatch"),
        ("evidence_state", "unavailable", "measured_assertion_value_or_source_mismatch"),
        ("tool_run_execution_state", "partial", "measured_assertion_value_or_source_mismatch"),
        ("measurement_result_ref", {"object_id": "measurement:another", "object_version": "0.2.0"}, "measured_claim_binding_required"),
        ("tool_run_ref", {"object_id": "tool-run:another", "object_version": "0.1.0"}, "measured_assertion_value_or_source_mismatch"),
        ("evidence_family_ref", {"object_id": "evidence-family:another", "object_version": "0.1.0"}, "measured_assertion_family_mismatch"),
        ("artifact_refs", [], "measured_assertion_artifact_binding_required"),
        ("provenance_refs", ["source:other"], "measured_assertion_provenance_mismatch"),
    ]
    for field, value, reason in mutations:
        changed = deepcopy(template)
        changed["candidate_records"][0][field] = value
        clone, bound_scope, supplied = rebound_test_input(service, state, scope, selection, "compilation_bundle", changed)
        with pytest.raises(ValueError, match=reason):
            service.report_inputs.assessment_selection(clone, bound_scope, allowed, supplied)
    changed = deepcopy(template)
    changed["object_catalog"][0]["content_hash"] = "0" * 64
    clone, bound_scope, supplied = rebound_test_input(service, state, scope, selection, "compilation_bundle", changed)
    with pytest.raises(ValueError, match="measured_assertion_catalog_mismatch"):
        service.report_inputs.assessment_selection(clone, bound_scope, allowed, supplied)
    # Same assertions re-registered with another bundle ID are not a new graph check.
    changed = {**template, "bundle_id": "evidence-compilation-bundle:another-registration"}
    clone, bound_scope, supplied = rebound_test_input(service, state, scope, selection, "compilation_bundle", changed)
    with pytest.raises(ValueError, match="canonical_graph_inputs_unchanged"):
        service.report_inputs.assessment_selection(clone, bound_scope, allowed, supplied)
    missing = selection.model_copy(update={"object_inputs": []})
    clone, bound_scope = deepcopy(state), scope.model_copy(deep=True)
    bound_scope.binding["selections"]["P0-09"] = missing.model_dump(mode="json")
    with pytest.raises(ValueError, match="measured_graph_assertions_required"):
        service.report_inputs.assessment_selection(clone, bound_scope, allowed, missing)


def test_measured_graph_feedback_appends_after_real_discriminating_check(client, tmp_path, monkeypatch):
    from bridge.web.assessment import AssessmentScope
    from bridge.web.scientific_inputs import encoded
    from bridge.tool_packages.p0_08_evidence_sufficiency.models import DomainGateInput
    from test_web_assessment import select_process_roots, propose_scope, approve_scope, settle_assessment
    from test_web_inputs import choice
    service, sid, aid, source_run, measurements = measured_graph_case(client, tmp_path, monkeypatch)
    before = service.load(sid)
    old_records = next(service.inputs.verify(before, record)["records"] for record in before["_input_objects"].values()
        if record["source"] == "tool_output" and record["schema_ref"] == "bridge://schemas/evidence-record-set/v0.1")
    refs = {ref.role: ref for ref in source_run.request.object_inputs}
    case = service.inputs.verify(before, before["_input_objects"][refs["product_case"].input_id])
    view = service.inputs.verify(before, before["_input_objects"][refs["qc_readiness_profile"].input_id])["selected_data_view"]
    process_roots = select_process_roots(client, sid, tmp_path, case, view)
    state = service.load(sid)
    spec_id = next(row["input_id"] for row in process_roots if row["role"] == "measurement_spec")
    domain = DomainGateInput(domain_gate_input_id="domain-gate-input:synthetic-process",
        object_version="0.1.0", created_at="2026-09-01T00:00:00Z",
        product_case={"object_id": case["product_case_id"], "object_version": case["case_version"],
                      "provenance_refs": [row["object_id"] for row in case["provenance_refs"]]},
        product_definition={**case["product_definition_ref"], "provenance_refs": ["source:synthetic-requirements-only"]},
        domain_id="proliferation_stress_response", measurement_spec_input_id=spec_id,
        method_requirement="required", prior_requirement="required", required_sensitivity_kinds=["reference"],
        task_validation_state="not_assessed", provenance_refs=["source:synthetic-process-requirements"])
    domain_id = service.inputs.add_object(state, tool_id="P0-08", mode_id="default", role="domain_gate_input",
        schema_ref="bridge://schemas/domain-gate-input/v0.1", object_version="0.1.0", data=encoded(domain.model_dump(mode="json")))
    domains = [*state["_input_selections"]["P0-08"]["object_inputs"],
               {"role": "domain_gate_input", "input_id": domain_id}, {"role": "measurement_spec", "input_id": spec_id}]
    service.save(state)
    assert client.post(f"/api/sessions/{sid}/analysis-inputs", json=choice("P0-08", "default", domains)).status_code == 200
    roots = select_measured_graph_assertions(client, sid, source_run, measurements,
        domains=("developmental_compatibility", "proliferation_stress_response"))
    state = service.load(sid)
    for role, schema in (("base_graph_manifest", "case-evidence-graph-manifest"),
                        ("base_evidence_record_set", "evidence-record-set"),
                        ("base_evidence_requirement_set", "evidence-requirement-set")):
        identifier = next(identifier for identifier, record in state["_input_objects"].items()
            if record["source"] == "tool_output" and record["schema_ref"] == "bridge://schemas/" + schema + "/v0.1")
        roots.append({"role": role, "input_id": identifier})
    assert client.post(f"/api/sessions/{sid}/analysis-inputs", json=choice("P0-09", "case_append_v2", roots)).status_code == 200
    scope = propose_scope(client, sid, aid, allowed_modes=[
        {"tool_id": "P0-09", "mode_id": "case_query"},
        {"tool_id": "P0-06", "mode_id": "method_runtime_source_bound"},
        {"tool_id": "P0-08", "mode_id": "default"},
        {"tool_id": "P0-09", "mode_id": "case_append_v2"}], max_tool_runs=7, max_model_turns=8)
    monkeypatch.setattr("bridge.web.provider.converse", check_query_or_stop)
    approve_scope(client, sid, scope)
    done = settle_assessment(client, sid, timeout=180)
    state = service.load(sid)
    assert done["assessment"]["tool_runs_used"] == 5, done["assessment"]
    assert_measured_feedback_artifacts(service.directory(sid), state, len(before["_tool_runs"]),
        old_records, scope["input_revision"])


def assert_measured_feedback_artifacts(directory, state, before_run_count, old_records, input_revision):
    """Verify already-produced canonical evidence; this never executes a tool."""
    from hashlib import sha256
    from pathlib import Path
    def read(path, checksum):
        raw = Path(path).read_bytes()
        assert sha256(raw).hexdigest() == checksum
        return json.loads(raw)
    receipts = state["_tool_runs"][before_run_count:]
    assert [row["tool_id"] for row in receipts] == ["P0-09", "P0-06", "P0-08", "P0-09", "P0-09"]
    runs = [read(directory / "receipts" / row["file"], row["sha256"]) for row in receipts]
    assert [row["state"] for row in receipts] == ["succeeded", "partial", "succeeded", "succeeded", "succeeded"]
    assert runs[0]["result"]["graph_version"] == 1 and runs[-1]["result"]["graph_version"] == 2
    assert len(runs[1]["measurements"]) == 5 and all(row["raw_value"] is None for row in runs[1]["measurements"])
    assert runs[0]["measurements"] == runs[0]["artifacts"] == runs[-1]["measurements"] == runs[-1]["artifacts"] == []
    assert {profile["domain_id"] for profile in runs[2]["result"]["profiles"]} == {
        "developmental_compatibility", "proliferation_stress_response"}
    for run in runs:
        for artifact in run["artifacts"]:
            assert sha256(Path(artifact["path"]).read_bytes()).hexdigest() == artifact["sha256"]
    def objects(schema):
        return [read(record["path"], record["sha256"]) for record in state["_input_objects"].values()
            if record["source"] == "tool_output" and record["schema_ref"] == "bridge://schemas/" + schema + "/v0.1"]
    record_sets = sorted(objects("evidence-record-set"), key=lambda row: row["graph_version"])
    assert len(record_sets) == 2 and record_sets[-1]["graph_version"] == 2
    assert record_sets[-1]["records"] == old_records
    requirement_sets = sorted(objects("evidence-requirement-set"), key=lambda row: row["graph_version"])
    assert requirement_sets[-1]["requirements"] and all(row["state"] == "open" for row in requirement_sets[-1]["requirements"])
    manifests = sorted(objects("case-evidence-graph-manifest"), key=lambda row: row["graph_version"])
    from bridge.tool_packages.p0_09_evidence_compiler.queries import EvidenceGraphQueries
    for record in state["_input_objects"].values():
        if record["source"] == "tool_output" and record["schema_ref"] == "bridge://schemas/case-evidence-graph-manifest/v0.1":
            EvidenceGraphQueries.open(Path(record["path"]))
    assert manifests[0]["product_case_ref"] == manifests[-1]["product_case_ref"]
    assert manifests[-1]["base_graph_ref"]["graph_version"] == 1
    append_refs = {ref["role"]: ref for ref in runs[3]["request"]["object_inputs"]}
    assert read(append_refs["evidence_sufficiency_run_result"]["path"],
        append_refs["evidence_sufficiency_run_result"]["sha256"]) == runs[2]["result"]
    old_profiles = {json.dumps(row["sufficiency_profile_ref"], sort_keys=True) for row in old_records}
    current_profiles = {json.dumps({"object_id": row["profile_id"], "object_version": row["profile_version"]}, sort_keys=True)
                        for row in runs[2]["result"]["profiles"]}
    assert not old_profiles & current_profiles
    assert state["_input_revision"] == input_revision
    assessment = state["_assessment"]
    assert assessment["tool_runs_used"] == 5 and assessment["stop_reason"] == "no_discriminating_check"
    reasons = {reason for row in assessment["blockers"] for reason in row["reason_codes"]}
    assert {"measured_claim_binding_required", "canonical_graph_inputs_unchanged"} <= reasons
    summary = {"case": manifests[-1]["product_case_ref"], "graph": runs[-1]["result"]["graph_id"],
        "versions": [1, 2], "records": len(old_records), "requirements": [len(row["requirements"]) for row in requirement_sets],
        "sequence": [row["tool_id"] for row in receipts], "stop_reason": assessment["stop_reason"]}
    print("FEEDBACK", json.dumps(summary, sort_keys=True))
    return summary


def confirmed_case(client, tmp_path):
    service, sid, aid = science_case(client, tmp_path)
    draft = propose(service, sid, aid)
    body = {"draft_id": draft["id"], "draft_digest": draft["digest"]}
    assert client.post(f"/api/sessions/{sid}/scientific-inputs/confirm", json=body).status_code == 200
    return service, sid, aid, body

def test_missingness_preparation_uses_real_case_and_packaged_gate_without_execution(client, tmp_path):
    service, sid, aid, body = confirmed_case(client, tmp_path)
    before = service.load(sid)
    response = client.post(f"/api/sessions/{sid}/report-inputs/prepare", json=body)
    assert response.status_code == 200, response.json()
    value = response.json()
    assert value["status"] == "awaiting_approval"
    assert value["plan"]["steps"][0]["tool_id"] == "P0-08"
    assert value["plan"]["steps"][0]["status"] == "pending"
    assert "未评估" in value["plan"]["summary"]
    state = service.load(sid)
    assert state["_tool_runs"] == before["_tool_runs"] == []
    request = json.loads(state["_plan"]["steps"][0]["approved_request_json"])
    assert request["assets"] == []
    assert len(request["object_inputs"]) == 7
    assert {row["role"] for row in request["object_inputs"]} == {"product_case", "gate_rule_spec", "domain_gate_input"}
    inputs = [service.inputs.verify(state, state["_input_objects"][row["input_id"]])
              for row in request["object_inputs"] if row["role"] == "domain_gate_input"]
    assert len({row["domain_id"] for row in inputs}) == 5
    for row in inputs:
        assert row["measurement_result_input_ids"] == [] and row["qc_profile_input_id"] is None
        assert row["method_requirement"] == row["prior_requirement"] == "not_assessed"
        assert row["task_validation_state"] == "not_assessed"
    first_objects = state["_input_objects"]
    again = client.post(f"/api/sessions/{sid}/report-inputs/prepare", json=body)
    assert again.status_code == 200
    assert service.load(sid)["_input_objects"] == first_objects

def test_actual_approved_missingness_tool_retains_five_unassessed_domains(client, tmp_path):
    service, sid, aid, body = confirmed_case(client, tmp_path)
    response = client.post(f"/api/sessions/{sid}/report-inputs/prepare", json=body)
    assert response.status_code == 200, response.json()
    plan = response.json()["plan"]
    assert client.post(f"/api/sessions/{sid}/approve",
        json={"plan_id": plan["id"], "plan_digest": plan["digest"]}).status_code == 200
    done = settle(client, sid)
    assert done["plan"]["status"] == "completed", done
    state = service.load(sid)
    outputs = [record for record in state["_input_objects"].values()
        if record["source"] == "tool_output" and record["schema_ref"] == "bridge://schemas/evidence-sufficiency-run-result/v0.2"]
    assert len(outputs) == 1
    result = service.inputs.verify(state, outputs[0])
    assert len(result["profiles"]) == 5
    for profile in result["profiles"]:
        assert profile["evidence_sufficiency_state"] == "not_assessed"
        assert profile["domain_score"] is None
        assert profile["score_state"] == "unavailable"
    stages = {row["tool_id"]: row for row in done["scientific_drafts"][-1]["stages"]}
    assert stages["P0-08"]["state"] == "available"
    assert stages["P0-09"]["state"] == "ready"
    assert stages["P0-09"]["reason_codes"] == ["candidate_missingness_policy"]
    assert stages["P0-10"]["state"] == stages["P0-11"]["state"] == "blocked"

def run_stage(client, sid, body, tool_id):
    response = client.post(f"/api/sessions/{sid}/report-inputs/prepare", json={**body, "tool_id": tool_id})
    assert response.status_code == 200, response.json()
    plan = response.json()["plan"]
    assert plan["steps"][0]["tool_id"] == tool_id
    assert client.post(f"/api/sessions/{sid}/approve",
        json={"plan_id": plan["id"], "plan_digest": plan["digest"]}).status_code == 200
    done = settle(client, sid)
    assert done["plan"]["status"] == "completed", done
    return done

def test_candidate_graph_requires_canonical_missingness_and_separate_approval(client, tmp_path):
    service, sid, aid, body = confirmed_case(client, tmp_path)
    before = service.load(sid)
    blocked = client.post(f"/api/sessions/{sid}/report-inputs/prepare", json={**body, "tool_id": "P0-09"})
    assert blocked.status_code == 409
    assert service.load(sid) == before
    run_stage(client, sid, body, "P0-08")
    before = service.load(sid)
    response = client.post(f"/api/sessions/{sid}/report-inputs/prepare", json={**body, "tool_id": "P0-09"})
    assert response.status_code == 200, response.json()
    plan = response.json()["plan"]
    assert plan["steps"][0]["tool_id"] == "P0-09"
    assert service.load(sid)["_tool_runs"] == before["_tool_runs"]
    assert "候选" in plan["summary"]
    original_objects = service.load(sid)["_input_objects"]
    again = client.post(f"/api/sessions/{sid}/report-inputs/prepare", json={**body, "tool_id": "P0-09"})
    assert again.status_code == 200
    assert service.load(sid)["_input_objects"] == original_objects
    assert service.load(sid)["_tool_runs"] == before["_tool_runs"]
    plan = again.json()["plan"]
    selected = service.load(sid)
    from copy import deepcopy
    intact = deepcopy(selected)
    selected["_input_selections"]["P0-09"]["object_inputs"] = [row for row in selected["_input_selections"]["P0-09"]["object_inputs"] if row["role"] != "evidence_sufficiency_run_result"]
    service.save(selected)
    assert client.post(f"/api/sessions/{sid}/approve", json={"plan_id": plan["id"], "plan_digest": plan["digest"]}).status_code == 409
    assert service.load(sid)["_tool_runs"] == before["_tool_runs"]
    service.save(intact)
    assert client.post(f"/api/sessions/{sid}/approve",
        json={"plan_id": plan["id"], "plan_digest": plan["digest"]}).status_code == 200
    done = settle(client, sid)
    assert done["plan"]["status"] == "completed", done
    state = service.load(sid)
    outputs = [record for record in state["_input_objects"].values()
        if record["source"] == "tool_output" and record["schema_ref"] == "bridge://schemas/evidence-record-set/v0.1"]
    assert len(outputs) == 1
    records = service.inputs.verify(state, outputs[0])
    assert records["records"] == []
    requirements = next(service.inputs.verify(state, row) for row in state["_input_objects"].values()
        if row["source"] == "tool_output" and row["schema_ref"] == "bridge://schemas/evidence-requirement-set/v0.1")["requirements"]
    assert len(requirements) == 5
    assert all(row["state"] == "open" and row["satisfying_evidence_refs"] == [] for row in requirements)
    from pathlib import Path
    artifacts = service.inputs.receipt_artifacts(state, outputs[0])
    reconciliation = next(json.loads(Path(row["path"]).read_text()) for row in artifacts.values()
        if Path(row["path"]).name == "reconciliation_records.json")
    assert len(reconciliation["records"]) == 5
    assert all(row["eligibility"] == "not_assessed" for row in reconciliation["records"])
    stages = {row["tool_id"]: row for row in done["scientific_drafts"][-1]["stages"]}
    assert stages["P0-09"]["state"] == "available"
    assert stages["P0-10"]["state"] == "ready"
    assert stages["P0-07"]["reason_codes"] == ["comparison_inputs_not_bound"]
    assert stages["P0-11"]["state"] == "blocked"

def test_new_scientific_draft_cannot_borrow_previous_draft_missingness_receipt(client, tmp_path):
    service, sid, aid, body = confirmed_case(client, tmp_path)
    run_stage(client, sid, body, "P0-08")
    original = service.load(sid)["_scientific_drafts"][-1]
    revised = client.post(f"/api/sessions/{sid}/scientific-inputs/revise", json={**body, "candidate": original["candidate"]})
    assert revised.status_code == 200, revised.json()
    current = revised.json()["scientific_drafts"][-1]
    new_body = {"draft_id": current["id"], "draft_digest": current["digest"]}
    assert current["id"] != body["draft_id"]
    assert client.post(f"/api/sessions/{sid}/scientific-inputs/confirm", json=new_body).status_code == 200
    before = service.load(sid)
    response = client.post(f"/api/sessions/{sid}/report-inputs/prepare", json={**new_body, "tool_id": "P0-09"})
    assert response.status_code == 409
    assert service.load(sid) == before

def test_internal_report_runs_real_verifier_and_keeps_release_blocked(client, tmp_path):
    service, sid, aid, body = confirmed_case(client, tmp_path)
    run_stage(client, sid, body, "P0-08")
    run_stage(client, sid, body, "P0-09")
    before = service.load(sid)
    response = client.post(f"/api/sessions/{sid}/report-inputs/prepare", json={**body, "tool_id": "P0-10"})
    assert response.status_code == 200, response.json()
    plan = response.json()["plan"]
    assert plan["steps"][0]["tool_id"] == "P0-10"
    assert service.load(sid)["_tool_runs"] == before["_tool_runs"]
    prepared = response.json()["scientific_drafts"][-1]["internal_report"]
    assert prepared["verification"] is None
    assert len(prepared["sections"]) == 5
    assert prepared["boundaries"] == ["本次核对不能证明安全性。"]
    assert all(row["evidence_state"] == "not_assessed" for row in prepared["sections"])
    assert client.post(f"/api/sessions/{sid}/approve",
        json={"plan_id": plan["id"], "plan_digest": plan["digest"]}).status_code == 200
    done = settle(client, sid)
    assert done["plan"]["status"] == "completed", done
    report = done["scientific_drafts"][-1]["internal_report"]
    assert report["verification"]["release_state"] == "release_blocked"
    assert report["verification"]["public_export_eligibility"] == "ineligible"
    assert "claim_type_policy_missing" in report["verification"]["reason_codes"]
    assert report["sections"] == prepared["sections"]
    assert report["next_actions"]
    assert str(tmp_path) not in json.dumps(report)
    assert client.get(f"/api/sessions/{sid}").json()["scientific_drafts"][-1]["internal_report"] == report
    stages = {row["tool_id"]: row for row in done["scientific_drafts"][-1]["stages"]}
    assert stages["P0-10"]["state"] == "available"
    assert stages["P0-11"]["state"] == "blocked"


@pytest.mark.parametrize("tool_id, corruption", [
    ("P0-09", "receipt"), ("P0-09", "policy"), ("P0-10", "upstream"), ("P0-10", "report"),
])
def test_report_approval_rejects_corruption_without_running_or_displaying_stale_report(client, tmp_path, tool_id, corruption):
    from pathlib import Path
    service, sid, aid, body = confirmed_case(client, tmp_path)
    run_stage(client, sid, body, "P0-08")
    if tool_id == "P0-10":
        run_stage(client, sid, body, "P0-09")
    response = client.post(f"/api/sessions/{sid}/report-inputs/prepare", json={**body, "tool_id": tool_id})
    assert response.status_code == 200, response.json()
    plan = response.json()["plan"]
    state = service.load(sid)
    if corruption == "receipt":
        path = service.directory(sid) / "receipts" / state["_tool_runs"][0]["file"]
    else:
        schema = {"policy": "claim-registry/v0.1", "upstream": "evidence-sufficiency-run-result/v0.2",
                  "report": "report-draft/v0.1"}[corruption]
        record = next(row for row in state["_input_objects"].values() if row["schema_ref"] == "bridge://schemas/" + schema)
        path = Path(record["path"])
    original = path.read_bytes()
    try:
        path.write_bytes(original + b" ")
        before = service.load(sid)
        response = client.post(f"/api/sessions/{sid}/approve", json={"plan_id": plan["id"], "plan_digest": plan["digest"]})
        assert response.status_code == 409
        assert service.load(sid) == before
        public = client.get(f"/api/sessions/{sid}").json()["scientific_drafts"][-1]
        assert public["internal_report"] is None
    finally:
        path.write_bytes(original)

def test_candidate_factory_is_unreviewed_case_bound_and_never_converts_measured_evidence_to_missing(client, tmp_path):
    from datetime import datetime, timezone
    from bridge.tool_packages._configurable_contracts import ProductCase, ProductDefinitionCard
    from bridge.tool_packages.p0_08_evidence_sufficiency.models import EvidenceSufficiencyRunResultV2
    from bridge.tool_packages.p0_09_evidence_compiler.candidate_policy import build_missingness_policy
    service, sid, aid, body = confirmed_case(client, tmp_path)
    run_stage(client, sid, body, "P0-08")
    state = service.load(sid)
    draft = state["_scientific_drafts"][-1]
    def payload(identifier): return service.inputs.verify(state, state["_input_objects"][identifier])
    case = ProductCase.model_validate(payload(draft["object_ids"]["product_case"]))
    definition = ProductDefinitionCard.model_validate(payload(draft["object_ids"]["product_definition_card"]))
    result = EvidenceSufficiencyRunResultV2.model_validate(next(payload(key) for key, row in state["_input_objects"].items()
        if row["schema_ref"] == "bridge://schemas/evidence-sufficiency-run-result/v0.2"))
    stamp = datetime.now(timezone.utc)
    policy = build_missingness_policy(case, definition, result, created_at=stamp)
    assert policy == build_missingness_policy(case, definition, result, created_at=stamp)
    assert policy["compilation_bundle"].candidate_records == []
    assert len(policy["compilation_bundle"].missing_observations) == 5
    assert policy["claim_registry"].status == "candidate"
    assert all(row.status == "candidate" and row.reviewer_ref is None for row in policy["claim_registry"].claims)
    family = policy["evidence_family_registry"].families[0]
    assert family.status == "unreviewed" and family.reviewer_ref is None
    assert family.shared_source_refs == [case.sample_or_preparation_ref.ref]
    assert policy["reconciliation_spec_registry"].specs[0].minimum_independent_families_by_role == {"canonical_measurement": 1}
    for invalid_case, invalid_result in (
        (case.model_copy(update={"product_case_id": "product-case:other"}), result),
        (case, result.model_copy(update={"profiles": result.profiles[:-1]})),
        (case, result.model_copy(update={"profiles": [*result.profiles[:4], result.profiles[0]]})),
        (case, result.model_copy(update={"profiles": [result.profiles[0].model_copy(
            update={"measurement_result_refs": [case.ref]}), *result.profiles[1:]]})),
    ):
        with pytest.raises(ValueError):
            build_missingness_policy(invalid_case, definition, invalid_result, created_at=stamp)

@pytest.mark.parametrize("invalid", ["unconfirmed", "digest", "intake", "source"])
def test_report_preparation_rejects_unconfirmed_or_stale_draft_without_writes(client, tmp_path, monkeypatch, invalid):
    service, sid, aid = science_case(client, tmp_path)
    draft = propose(service, sid, aid)
    body = {"draft_id": draft["id"], "draft_digest": draft["digest"]}
    if invalid != "unconfirmed":
        assert client.post(f"/api/sessions/{sid}/scientific-inputs/confirm", json=body).status_code == 200
    if invalid == "digest":
        body["draft_digest"] = "0" * 64
    elif invalid == "intake":
        confirm_change(client, sid, stage(client, sid, aid, stated_facts(target_stage="changed")))
    elif invalid == "source":
        original = service.scientific_inputs._catalog
        def changed(state):
            context, binding, spec = original(state)
            return context, {**binding, "biological": "changed"}, spec
        monkeypatch.setattr(service.scientific_inputs, "_catalog", changed)
    before = service.load(sid)
    response = client.post(f"/api/sessions/{sid}/report-inputs/prepare", json=body)
    assert response.status_code == 409
    assert service.load(sid) == before

def test_report_source_changed_after_plan_proposal_cannot_be_approved(client, tmp_path, monkeypatch):
    service, sid, aid, body = confirmed_case(client, tmp_path)
    response = client.post(f"/api/sessions/{sid}/report-inputs/prepare", json=body)
    plan = response.json()["plan"]
    original = service.scientific_inputs._catalog
    def changed(state):
        context, binding, spec = original(state)
        return context, {**binding, "biological": "changed"}, spec
    monkeypatch.setattr(service.scientific_inputs, "_catalog", changed)
    before = service.load(sid)
    response = client.post(f"/api/sessions/{sid}/approve",
        json={"plan_id": plan["id"], "plan_digest": plan["digest"]})
    assert response.status_code == 409
    assert service.load(sid) == before

def test_owned_report_selection_cannot_drop_current_case_binding(client, tmp_path):
    service, sid, aid, body = confirmed_case(client, tmp_path)
    assert client.post(f"/api/sessions/{sid}/report-inputs/prepare", json=body).status_code == 200
    state = service.load(sid)
    state["_input_selections"]["P0-08"]["object_inputs"] = [
        item for item in state["_input_selections"]["P0-08"]["object_inputs"] if item["role"] != "product_case"]
    service.save(state)
    result = client.post(f"/api/sessions/{sid}/prepare-analysis", json={"tool_id": "P0-08"})
    assert result.status_code == 200
    assert result.json()["error"] == "report_draft_selection_mismatch"
    assert service.load(sid)["_tool_runs"] == []
