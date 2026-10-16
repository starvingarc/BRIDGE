"""Method-native observations enter the existing graph without identity qualification."""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from math import isclose
from pathlib import Path
import re

from bridge.tool_packages._configurable_contracts import ProductCase, ProductDefinitionCard, StateRoleMap
from bridge.tool_packages._structured_runtime import read_regular_bytes, strict_json_loads
from bridge.tool_packages.p0_02_cell_state.candidate_runtime import AUXILIARY_SPEC
from bridge.tool_packages.p0_02_cell_state.measurement_specs import load_measurement_spec
from bridge.tool_packages.p0_02_cell_state.scientific_review import load_development_review, development_review_sha256
from bridge.tool_packages.p0_08_evidence_sufficiency.models import DomainGateInput, EvidenceValidationRecord, P0DomainId
from bridge.tool_packages.p0_09_evidence_compiler.compiler import effective_records, evidence_logical_key
from bridge.tool_packages.p0_09_evidence_compiler.models import (
    ClaimRegistry, EvidenceCandidate, EvidenceCompilationBundle, EvidenceFamilyRegistry, EvidenceRecord, ReconciliationSpecRegistry,
)
from bridge.toolkit.contracts import MeasurementResultV2, MeasurementSpecV2, ToolRun, ToolRunV2
from .inputs import ObjectChoice, Selection, checked_bytes, strict_json
from .report_inputs import SUFFICIENCY_SCHEMAS
from .scientific_inputs import digest


def _ref(identifier, version):
    return {"object_id": identifier, "object_version": version}


def case_context_key(view, facts):
    # A display-name edit does not change the scientific case or its measurements.
    return digest({"view": view, "facts": {key: value for key, value in facts.items() if key != "product_name"},
                   "review": development_review_sha256()})


def _program_validation_method(source):
    summaries = source[0].result["program_summaries"]
    available = {row["method_id"] for row in summaries if row["assessment_state"] == "available"}
    signed = bool(summaries) and all(row.get("direction_definition") == "sign_of_source_logFC"
                                     for row in summaries)
    return ("METHOD-DECOUPLER" if signed or ("PROC-SCORE-SCANPY" not in available
            and "PROC-SCORE-DECOUPLER" in available) else "METHOD-SCANPY-SCORE-GENES")


def _domain_coverage(case, definition, sources, created_at, *, prior_records=()):
    """Describe cumulative coverage, not domain validity or independent validation."""
    history = [record for row in prior_records
               if (record := EvidenceRecord.model_validate(row)).product_case_ref.ref == case.ref.ref]
    compiled = {(row.measurement_result_ref.object_id, row.tool_run_ref.object_id) for row in history}
    values = {}
    for record in effective_records(history):
        values.setdefault(record.domain_id.value, []).append({"evidence_state": record.evidence_state.value})
    for source, domain, _ in sources:
        # A saved producer cannot revive an invalidated or superseded record.
        values.setdefault(domain, []).extend(value for _, value in source[3]
            if not compiled or (value["measurement_id"], "tool-run:" + source[0].run_id) not in compiled)
    claims, observations = [], []
    for domain in P0DomainId:
        claim_ref = _ref("claim:native-domain-" + digest(case.ref.ref)[:24] + ":" + domain.value, "0.1.0")
        claims.append({"claim_id": claim_ref["object_id"], "version": "0.1.0",
            "claim_type": "native_method_output", "domain_id": domain.value,
            "claim_target_ref": case.ref.ref, "biological_context_ref": definition.ref.model_dump(mode="json"),
            "allowed_relations": ["supports"], "status": "candidate",
            "reconciliation_spec_ref": _ref("reconciliation-spec:native-method-output", "0.1.0"),
            "requirement_specs": [{"requirement_key": "independent_validation", "channel_role": "independent_validation",
                "blocking_scope": "domain_interpretation", "required": True}]})
        measurements = values.get(domain.value, [])
        reason = ("measurement_not_provided" if not measurements else
                  "measurement_unavailable" if all(row["evidence_state"] == "unavailable" for row in measurements) else
                  "required_channel_not_provided")
        observations.append({"observation_id": "missing-evidence:native-domain-" + digest(case.ref.ref)[:24] + ":" + domain.value,
            "product_case_ref": case.ref.model_dump(mode="json"), "claim_ref": claim_ref,
            "requirement_key": "independent_validation", "reason_code": reason,
            "source_contract_ref": claim_ref, "provenance_refs": [case.ref.ref], "observed_at": created_at})
    return claims, observations


def _coverage_changed(observations, requirements):
    latest = {}
    for row in sorted(requirements, key=lambda item: item["requirement_version"]):
        latest[(row["claim_ref"]["object_id"], row["claim_ref"]["object_version"], row["requirement_key"])] = row
    return any((prior := latest.get((row["claim_ref"]["object_id"], row["claim_ref"]["object_version"],
                                    row["requirement_key"]))) is None
               or prior["reason_codes"] != [row["reason_code"]] for row in observations)


def _auxiliary_projection(inputs, state, pool, source):
    """Verify the saved auxiliary receipt before projecting its two V1 fractions."""
    main, source_id, profile, _, _, _ = source
    if profile.get("auxiliary_state") != "available":
        return None
    artifact = next((item for item in main.artifacts
        if item.artifact_id == f"artifact:{main.run_id}:auxiliary-run"), None)
    if artifact is None:
        raise ValueError("native_auxiliary_artifact_required")
    parent = pool[source_id]
    dependency = {"receipt_file": parent["receipt_file"], "receipt_sha256": parent["receipt_sha256"],
                  "artifact_id": artifact.artifact_id, "path": str(artifact.path), "sha256": artifact.sha256}
    raw = checked_bytes(inputs.service, state, artifact.path, artifact.sha256,
                        root=inputs.service.directory(state["id"]) / "runs")
    aux = ToolRun.model_validate(strict_json(raw))
    view = profile["input_data_view"]
    if (aux.run_id != profile.get("auxiliary_run_ref")
            or aux.execution_state.value != "succeeded"
            or aux.request.tool_id != "P0-02"
            or aux.request.measurement_spec_ref != AUXILIARY_SPEC
            or aux.input_hash != main.input_hash
            or aux.request.assets != main.request.assets
            or len(aux.request.assets) != 1
            or aux.request.assets[0].metadata.get("data_view_id") != view["view_id"]
            or aux.result.get("measurement_spec_id") != AUXILIARY_SPEC
            or aux.result.get("n_observations") != view["n_observations"]):
        raise ValueError("native_auxiliary_source_binding_invalid")
    source_spec = load_measurement_spec(AUXILIARY_SPEC)
    if source_spec is None:
        raise ValueError("native_auxiliary_measurement_spec_required")
    spec = MeasurementSpecV2(**source_spec.model_dump(mode="json"),
        analysis_unit_kind="capture", independence_group_kind="sample",
        observation_unit_kind="cell" if aux.request.assets[0].assay == "scRNA-seq" else "nucleus",
        applicable_contexts=["candidate_method_observation"])
    counts = aux.result.get("prediction_sets", {}).get("state_counts", {})
    denominator = view["n_observations"]
    if (not isinstance(counts, dict) or not all(type(value) is int and value >= 0 for value in counts.values())
            or sum(counts.values()) != denominator):
        raise ValueError("native_auxiliary_state_counts_invalid")
    rows = []
    for metric, state_name in (("consensus_supported_fraction", "consensus_supported"),
                               ("source_conflict_fraction", "source_conflict")):
        original = next((row for row in aux.measurements if row.metric_name == metric), None)
        if (original is None or original.measurement_spec_id != AUXILIARY_SPEC
                or original.denominator != denominator or original.evidence_state.value != "inferred"
                or original.score_state.value != "shadow" or type(original.raw_value) is not float
                or not isclose(original.raw_value, counts.get(state_name, 0) / denominator,
                               rel_tol=0, abs_tol=1e-12)):
            raise ValueError("native_auxiliary_measurement_mismatch")
        rows.append(MeasurementResultV2.model_validate({**original.model_dump(mode="json"),
            "measurement_spec_version": spec.version, "numerator": counts.get(state_name, 0),
            "denominator": denominator, "unit": "fraction",
            "source_run_ref": f"tool-run:{aux.run_id}@{aux.tool_version}",
            "source_execution_state": "succeeded",
            "provenance_refs": [*original.provenance_refs, artifact.artifact_id]}))
    metadata = {"input_data_view": view,
                "evidence_ids": [f"evidence:{aux.run_id}:source-reconciliation"],
                "model_sha256": artifact.sha256, "verification_sha256": artifact.sha256,
                "parent_artifact": {"artifact_id": artifact.artifact_id,
                                    "sha256": artifact.sha256, "version": main.tool_version}}
    return aux, source_id, metadata, rows, spec, dependency


def selection(reports, state, scope, allowed):
    """Materialize only source-backed declarations inside this approved assessment."""
    if allowed.tool_id not in {"P0-08", "P0-09", "P0-10"}:
        return None
    inputs = reports.service.inputs
    pool = inputs.assessment_pool(state, scope)
    source = _source(reports, state, scope, pool)
    if source is None:
        raise ValueError("native_observation_source_required")
    run, profile_id, profile, measurements, spec_id, spec = source
    view = profile["input_data_view"]
    if not view.get("sample_or_preparation_ref"):
        raise ValueError("native_sample_identity_required")
    sources = [(source, "target_identity", "METHOD-CELLTYPIST-CUSTOM-CLASSIFIER")]
    process = _process_source(reports, state, pool, view)
    if process is not None:
        sources.append((process, "proliferation_stress_response", "METHOD-NATIVE-CELL-CYCLE"))
    programs = _program_sources(reports, state, pool, view)
    if process is None and programs:
        sources.append((programs[0], "proliferation_stress_response", _program_validation_method(programs[0])))
    context_key = case_context_key(view, scope.binding["intake"]["facts"])
    contexts = state.setdefault("_native_evidence_contexts", {})
    created_at = contexts.setdefault(context_key, datetime.now(timezone.utc).isoformat())
    case_id = "product-case:native-" + context_key[:24]
    family_id = "evidence-family:query-" + digest({"sha256": view["parent_asset_sha256"]})[:24]
    review = load_development_review()
    review_ref = _ref("cell-state-development-review:" + development_review_sha256()[:24], "1.1.0")
    definition_ref = _ref("product-definition:native-unmapped-" + context_key[:24], "0.1.0")
    role_ref = _ref("state-role-map:native-unmapped-" + context_key[:24], "0.1.0")
    role_map = StateRoleMap(object_version="0.1.0", state_role_map_id=role_ref["object_id"],
        map_version="0.1.0", product_definition_ref=definition_ref, review_state="draft",
        assignments=[{"state_id": row.state_id, "product_role": "role_unresolved",
                      "role_evidence_class": "native-method-output", "evidence_direction": "not-assessed",
                      "source_refs": [review_ref["object_id"]]} for row in review.state_reviews],
        provenance_refs=[review_ref])
    definition = ProductDefinitionCard(object_version="0.1.0", product_definition_id=definition_ref["object_id"],
        definition_version="0.1.0", state_role_map_ref=role_ref, supported_assays=[run.request.assets[0].assay],
        review_state="draft", provenance_refs=[review_ref])
    specimen_id, specimen_version = view["sample_or_preparation_ref"].rsplit("@", 1)
    unit_binding = {}
    if view.get("biological_unit_manifest_ref"):
        manifests = [(identifier, inputs.verify(state, row)) for identifier, row in pool.items()
                     if row["schema_ref"] == "bridge://schemas/biological-unit-manifest/v0.1"
                     and row.get("sha256") == view["biological_unit_manifest_sha256"]]
        if len(manifests) != 1:
            raise ValueError("native_biological_unit_manifest_required")
        _, manifest = manifests[0]
        manifest_id, manifest_version = view["biological_unit_manifest_ref"].rsplit("@", 1)
        if (manifest["manifest_id"], manifest["manifest_version"]) != (manifest_id, manifest_version):
            raise ValueError("native_biological_unit_manifest_mismatch")
        unit_binding = {
            "biological_unit_manifest_ref": _ref(manifest_id, manifest_version),
            "biological_unit_manifest_sha256": view["biological_unit_manifest_sha256"],
            "independence_scope_ref": manifest["independence_scope_ref"],
        }
    case = ProductCase(**unit_binding,object_version="0.1.0", product_case_id=case_id, case_version="0.1.0",
        product_definition_ref=definition_ref, source_unit_kind="preparation" if specimen_id.startswith("preparation:") else "sample",
        sample_or_preparation_ref=_ref(specimen_id, specimen_version),
        measurement_spec_ref=_ref(spec["measurement_spec_id"], spec["version"]),
        assay=run.request.assets[0].assay,
        provenance_refs=[_ref(profile["profile_id"], profile["object_version"])], created_at=created_at)
    base_dependencies = [key for src, _, _ in sources for key in [src[1], src[4]]]
    def add(role, schema, payload, dependencies=(), tool=None, mode=None, artifacts=()):
        return inputs.add_derived_object(state, tool_id=tool or allowed.tool_id,
            mode_id=mode or allowed.mode_id, role=role, schema_ref="bridge://schemas/" + schema,
            payload=payload.model_dump(mode="json") if hasattr(payload, "model_dump") else payload,
            dependencies=[*base_dependencies, *dependencies], artifact_dependencies=artifacts)
    # Unresolved declarations are context, not reviewed role or window decisions.
    add("state_role_map", "state-role-map/v0.1", role_map, tool="P0-03", mode="default")
    add("product_definition_card", "product-definition-card/v0.1", definition, tool="P0-03", mode="default")
    case_input = add("product_case", "product-case/v0.1", case, tool="P0-08", mode="default")
    qc_rows = [(identifier, inputs.verify(state, row)) for identifier, row in pool.items()
               if row.get("producer_tool_id") == "P0-01"
               and row["schema_ref"] == "bridge://schemas/qc-readiness-profile/v0.2"]
    qc = [(identifier, value) for identifier, value in qc_rows if value.get("selected_data_view") == view]
    if len(qc) != 1:
        raise ValueError("native_observation_qc_binding_required")
    qc_id = qc[0][0]
    latest = reports._latest_graph(state, pool, (case_id, "0.1.0"))
    prior_measurements = set()
    prior_records = []
    prior_requirements = []
    if latest is not None:
        graph_record = pool[latest[0]]
        prior_sets = [inputs.verify(state, row) for row in pool.values()
                      if row.get("receipt_file") == graph_record["receipt_file"]
                      and row["schema_ref"] == "bridge://schemas/evidence-record-set/v0.1"]
        if len(prior_sets) != 1:
            raise ValueError("canonical_graph_history_required")
        prior_records = prior_sets[0]["records"]
        prior_measurements = {(row["measurement_result_ref"]["object_id"], row["tool_run_ref"]["object_id"])
                              for row in prior_records}
        requirement_sets = [inputs.verify(state, row) for row in pool.values()
            if row.get("receipt_file") == graph_record["receipt_file"]
            and row["schema_ref"] == "bridge://schemas/evidence-requirement-set/v0.1"]
        if len(requirement_sets) != 1:
            raise ValueError("canonical_graph_history_required")
        prior_requirements = requirement_sets[0]["requirements"]
    similarity = _similarity_source(reports, state, scope, pool, view)
    if similarity is not None and latest is not None and any(
            (value["measurement_id"], "tool-run:" + similarity[0].run_id) not in prior_measurements
            for _, value in similarity[3]):
        sources = [(similarity, "target_identity", "METHOD-BRIDGE-PSEUDOBULK-CORRELATION")]
        base_dependencies.extend([similarity[1], similarity[4],
                                  *similarity[2]["source_input_ids"]])
    def previously_compiled(src):
        source_run, _, _, values, _, _ = src
        return all((value["measurement_id"], "tool-run:" + source_run.run_id) in prior_measurements
                   for _, value in values)
    pending_program = next((program for program in programs if not previously_compiled(program)), None)
    if (latest is not None and pending_program is not None
            and not (similarity is not None and sources[0][0] is similarity)):
        # One P0-06 domain gate per pass; the old cycle source remains in graph history.
        sources = [(pending_program, "proliferation_stress_response", _program_validation_method(pending_program))]
        base_dependencies.extend([pending_program[1], pending_program[4]])
    native_contexts = []
    for tool_id, domain_id, method_id in (
            ("P0-03", "target_identity", "METHOD-BRIDGE-DETERMINISTIC-STATEROLEMAP"),
            ("P0-04", "developmental_compatibility", "METHOD-BRIDGE-DETERMINISTIC-EVIDENCE-COORDINATOR"),
            ("P0-05", "off_target_control", "METHOD-HARD-LABEL-COMPOSITION")):
        context = _saved_context_source(reports, state, pool, view, tool_id)
        if context is not None:
            native_contexts.append((context, domain_id, method_id))
    if latest is None:
        # One gate per domain: the checked target-role projection already carries
        # the original candidate counts and provenance, not an independent vote.
        projected_domains = {domain for _, domain, _ in native_contexts}
        sources = [item for item in sources if item[1] not in projected_domains]
        sources.extend(native_contexts)
    elif native_contexts and all(previously_compiled(src) for src, _, _ in sources):
        pending_context = next((item for item in native_contexts
                                if not previously_compiled(item[0])), None)
        if pending_context is not None:
            sources = [pending_context]
            base_dependencies.extend([pending_context[0][1], pending_context[0][4]])
    coverage_sources = list(sources)
    append_authorized = any(mode.tool_id == "P0-09" and mode.mode_id == "case_append_v2"
                            for mode in scope.allowed_modes)
    if (latest is not None and append_authorized and allowed.tool_id in {"P0-08", "P0-09"}
            and allowed.mode_id != "case_query"):
        auxiliary = _auxiliary_projection(inputs, state, pool, source)
        if auxiliary is not None and all(previously_compiled(src) for src, _, _ in sources):
            aux_run, aux_parent_id, aux_profile, aux_rows, aux_spec, artifact_dependency = auxiliary
            if any((row.measurement_id, "tool-run:" + aux_run.run_id) not in prior_measurements
                   for row in aux_rows):
                aux_spec_id = add("measurement_spec", "measurement-spec/v0.2", aux_spec,
                                  dependencies=[aux_parent_id], tool="P0-08", mode="default",
                                  artifacts=[artifact_dependency])
                aux_values = [(add("measurement_result", "measurement-result/v0.2", row,
                                   dependencies=[aux_parent_id, aux_spec_id], tool="P0-08", mode="default",
                                   artifacts=[artifact_dependency]), row.model_dump(mode="json")) for row in aux_rows]
                sources = [((aux_run, aux_parent_id, aux_profile, aux_values,
                             aux_spec_id, aux_spec.model_dump(mode="json")), "target_identity",
                            "METHOD-BRIDGE-PSEUDOBULK-REFERENCE-CORRELATION-68029D")]
                coverage_sources.extend(sources)
    coverage_claims, coverage_observations = _domain_coverage(
        case, definition, coverage_sources, created_at, prior_records=prior_records)
    validations, domains, all_measurements = [], [], []
    for src, domain_id, method_id in sources:
        source_run, source_id, source_profile, values, source_spec_id, source_spec = src
        provenance = source_profile["evidence_ids"]
        validation = EvidenceValidationRecord(
            validation_record_id="validation-record:native-" + digest([source_run.run_id, domain_id])[:24],
            object_version="0.1.0", created_at=created_at,
            measurement_spec_ref=source_spec["measurement_spec_id"], method_id=method_id,
            method_version=source_profile["model_sha256"], tool_ref=source_run.request.tool_id,
            environment_spec_ref=source_run.environment_spec_id, evidence_family_id=family_id,
            required_for_interpretation=False, method_kind="learned" if method_id == "METHOD-CELLTYPIST-CUSTOM-CLASSIFIER" else "deterministic",
            validation_state="not_assessed", environment_state="not_assessed",
            context_of_use_ref=case.ref.ref, context_of_use_state="not_assessed",
            source_family_ref="source-sha256:" + view["parent_asset_sha256"],
            source_holdout_state="not_assessed", modality=case.assay, modality_holdout_state="not_assessed",
            calibration_state="not_assessed", ood_state="not_assessed",
            validation_refs=["verification-sha256:" + source_profile["verification_sha256"]],
            evidence_refs=provenance, provenance_refs=provenance)
        validation_id = add("validation_record", "evidence-validation-record/v0.1", validation,
                            tool="P0-08", mode="default")
        validations.append(validation_id)
        if allowed.tool_id == "P0-08":
            domain = DomainGateInput(
                domain_gate_input_id="domain-gate-input:native-" + digest([context_key, domain_id])[:24],
                object_version="0.1.0", created_at=created_at, domain_id=domain_id,
                product_case={**case.ref.model_dump(mode="json"),
                              "provenance_refs": [item.object_id for item in case.provenance_refs]},
                measurement_spec_input_id=source_spec_id, qc_profile_input_id=qc_id,
                measurement_result_input_ids=[identifier for identifier, _ in values],
                validation_record_input_ids=[validation_id], method_requirement="required", prior_requirement="required",
                evidence_refs=provenance, provenance_refs=provenance)
            domain_input = add("domain_gate_input", "domain-gate-input/v0.1", domain,
                dependencies=[case_input, qc_id, validation_id, *(key for key, _ in values)])
            domains.extend([("domain_gate_input", domain_input), ("measurement_spec", source_spec_id),
                            ("validation_record", validation_id)])
            all_measurements.extend(("measurement_result", key) for key, _ in values)
    if allowed.tool_id == "P0-08":
        if (all(previously_compiled(src) for src, _, _ in sources)
                and not _coverage_changed(coverage_observations, prior_requirements)):
            raise ValueError("canonical_graph_inputs_unchanged")
        present = {domain for _, domain, _ in sources}
        for domain_id in P0DomainId:
            if domain_id.value in present:
                continue
            domain = DomainGateInput(
                domain_gate_input_id="domain-gate-input:native-" + digest([context_key, domain_id.value])[:24],
                object_version="0.1.0", created_at=created_at, domain_id=domain_id,
                product_case={**case.ref.model_dump(mode="json"),
                              "provenance_refs": [item.object_id for item in case.provenance_refs]},
                product_definition={**definition.ref.model_dump(mode="json"), "provenance_refs": [case.product_case_id]},
                provenance_refs=[case.product_case_id])
            domain_input = add("domain_gate_input", "domain-gate-input/v0.1", domain, dependencies=[case_input])
            domains.append(("domain_gate_input", domain_input))
        inputs.package_options(state)
        gate_id = next(key for key, row in state["_input_objects"].items()
                       if row["source"] == "package_resource" and row["label"] == "gate_rule_spec")
        choices = [("product_case", case_input), ("gate_rule_spec", gate_id),
                   ("qc_readiness_profile", qc_id), *domains, *all_measurements]
        return Selection(tool_id="P0-08", mode_id="default", asset_ids=[], measurement_spec_ref=None,
                         object_inputs=[ObjectChoice(role=role, input_id=key) for role, key in choices])
    latest = reports._latest_graph(state, pool, (case_id, "0.1.0"))
    if allowed.tool_id == "P0-10":
        if latest is not None and _coverage_changed(coverage_observations, prior_requirements):
            raise ValueError("canonical_graph_domain_coverage_required")
        return reports.research_selection(state, scope, pool, latest)
    if allowed.mode_id == "case_query":
        if latest is None:
            raise ValueError("canonical_case_graph_required")
        query = {"object_version": "0.1.0", "query_name": "get_case_evidence_subgraph",
                 "product_case_id": case_id, "evidence_tiers": ["exploratory"], "max_depth": 3, "max_nodes": 100}
        query_id = add("evidence_graph_query", "evidence-graph-query/v0.1", query, dependencies=[latest[0]])
        return Selection(tool_id="P0-09", mode_id="case_query", asset_ids=[], measurement_spec_ref=None,
            object_inputs=[ObjectChoice(role="evidence_graph_query", input_id=query_id),
                           ObjectChoice(role="evidence_graph_manifest", input_id=latest[0])])
    if allowed.mode_id == "case_initial_v2" and latest is not None:
        raise ValueError("canonical_graph_append_required")
    if allowed.mode_id == "case_append_v2" and latest is None:
        raise ValueError("canonical_base_graph_required")
    results = [row for row in reports._canonical_outputs(state, pool, "P0-08",
               SUFFICIENCY_SCHEMAS)
               if row[1]["case_summary"]["product_case_ref"] == case.ref.model_dump(mode="json")]
    if not results:
        raise ValueError("canonical_sufficiency_result_required")
    suff_id, sufficiency, _ = results[-1]
    profiles = {row["domain_id"]: row for row in sufficiency["profiles"]}
    if set(profiles) != {domain.value for domain in P0DomainId}:
        raise ValueError("canonical_five_domain_sufficiency_required")
    present = {domain for _, domain, _ in sources}
    if any(profiles[domain.value]["measurement_result_refs"] or profiles[domain.value]["domain_score"] is not None
           for domain in P0DomainId if domain.value not in present):
        raise ValueError("native_sufficiency_binding_invalid")
    policies = []
    for src, domain_id, method_id in sources:
        source_run, _, source_profile, values, _, source_spec = src
        suff_profile = profiles.get(domain_id)
        if not previously_compiled(src) and (suff_profile is None
                or {row["object_id"] for row in suff_profile["measurement_result_refs"]}
                   != {value["measurement_id"] for _, value in values}
                or family_id not in suff_profile["deduplicated_evidence_family_ids"]
                or suff_profile["domain_score"] is not None):
            raise ValueError("native_sufficiency_binding_invalid")
        policies.append(_policy(case, definition, role_map, source_run, source_profile, values, source_spec,
                                suff_id, suff_profile, family_id, created_at, domain_id, method_id))
    objects = {key: value.model_dump(mode="json") for key, value in policies[0].items()}
    for policy in policies[1:]:
        other = {key: value.model_dump(mode="json") for key, value in policy.items()}
        objects["compilation_bundle"]["candidate_records"].extend(other["compilation_bundle"]["candidate_records"])
        catalog = objects["compilation_bundle"]["object_catalog"]
        existing = {(row["object_id"], row["object_version"]): row for row in catalog}
        for row in other["compilation_bundle"]["object_catalog"]:
            key = (row["object_id"], row["object_version"])
            if key in existing and existing[key] != row:
                raise ValueError("native_object_catalog_identity_conflict")
            if key not in existing:
                catalog.append(row)
                existing[key] = row
        objects["claim_registry"]["claims"].extend(other["claim_registry"]["claims"])
        family = objects["evidence_family_registry"]["families"][0]
        extra = other["evidence_family_registry"]["families"][0]
        for key in ("shared_algorithm_refs", "shared_reference_or_prior_refs"):
            family[key] = sorted(set(family[key] + extra[key]))
    bundle = objects["compilation_bundle"]
    objects["claim_registry"]["claims"].extend(coverage_claims)
    bundle["missing_observations"] = coverage_observations
    choices = [("evidence_sufficiency_run_result", suff_id)]
    dependencies = [case_input, suff_id, *validations,
                    *(key for src, _, _ in sources for key, _ in src[3])]
    if latest is not None:
        _append_history(inputs, state, pool, latest, bundle, objects, choices, dependencies)
    bundle["bundle_id"] = "evidence-compilation-bundle:native-" + digest({
        "case": case.ref.ref, "runs": [src[0].run_id for src, _, _ in sources],
        "sufficiency": suff_id, "base": bundle.get("base_graph_ref")})[:24]
    schemas = {"compilation_bundle": "evidence-compilation-bundle/v0.1",
               "evidence_family_registry": "evidence-family-registry/v0.1",
               "claim_registry": "claim-registry/v0.1",
               "reconciliation_spec_registry": "reconciliation-spec-registry/v0.1"}
    for role, payload in objects.items():
        identifier = add(role, schemas[role], payload, dependencies=dependencies)
        choices.append((role, identifier))
    return Selection(tool_id="P0-09", mode_id=allowed.mode_id, asset_ids=[], measurement_spec_ref=None,
                     object_inputs=[ObjectChoice(role=role, input_id=key) for role, key in choices])


def _source(reports, state, scope, pool):
    inputs = reports.service.inputs
    profiles = reports._canonical_outputs(state, pool, "P0-02", "bridge://schemas/cell-state-candidate-profile/v1.0")
    for identifier, profile, run in reversed(profiles):
        view = profile["input_data_view"]
        if (view["parent_asset_id"] != scope.upload_id
                or view["parent_asset_sha256"] != scope.binding["upload"]["sha256"]):
            continue
        if run.result != profile or len(run.request.assets) != 1:
            raise ValueError("native_source_profile_mismatch")
        record = pool[identifier]
        outputs = [(key, row) for key, row in pool.items()
                   if row.get("receipt_file") == record["receipt_file"]
                   and row.get("receipt_sha256") == record["receipt_sha256"]]
        specs = [(key, inputs.verify(state, row)) for key, row in outputs
                 if row["schema_ref"] == "bridge://schemas/measurement-spec/v0.2"]
        measurements = [(key, inputs.verify(state, row)) for key, row in outputs
                        if row["schema_ref"] == "bridge://schemas/measurement-result/v0.2"]
        if len(specs) != 1 or not measurements:
            raise ValueError("native_canonical_measurements_required")
        raw = {row.measurement_id: row.model_dump(mode="json") for row in run.measurements}
        if len(raw) != len(measurements):
            raise ValueError("native_measurement_receipt_mismatch")
        for _, value in measurements:
            original = raw.get(value["measurement_id"])
            if (original is None or any(value[key] != item for key, item in original.items())
                    or value["source_run_ref"] != "tool-run:" + run.run_id + "@" + run.tool_version
                    or value["measurement_spec_id"] != profile["measurement_spec_ref"]
                    or value["source_execution_state"] != run.execution_state.value):
                raise ValueError("native_measurement_receipt_mismatch")
        return run, identifier, profile, measurements, specs[0][0], specs[0][1]
    return None


def _similarity_source(reports, state, scope, pool, view):
    """Use only this scope's selected P0-03 technical observation and its saved producer."""
    modes = {("P0-03", "reference_similarity_exploratory"),
             ("P0-03", "saved_reference_similarity_projection")}
    authorized = {(row.tool_id, row.mode_id) for row in scope.allowed_modes} & modes
    selected = scope.binding["selections"].get("P0-03")
    if not authorized or not selected or ("P0-03", selected["mode_id"]) not in authorized:
        return None
    inputs = reports.service.inputs
    receipts = {(row["receipt_file"], row["receipt_sha256"]) for row in pool.values()
                if row.get("producer_tool_id") == "P0-03"
                and row.get("schema_ref") == "bridge://schemas/measurement-result/v0.2"}
    candidates = []
    for receipt in state.get("_tool_runs", []):
        if ((receipt["file"], receipt["sha256"]) not in receipts
                or receipt["file"] in state.get("_invalidated_receipts", {})
                or receipt["tool_id"] != "P0-03" or receipt["state"] not in {"succeeded", "partial"}):
            continue
        run, _ = inputs.producer_objects(state, receipt, "P0-03", set())
        roles = {ref.role for ref in run.request.object_inputs}
        mode = ("saved_reference_similarity_projection" if roles == {"saved_reference_similarity_run"}
                else "reference_similarity_exploratory" if roles == {"reference_similarity_input", "reference_manifest"}
                else None)
        if mode != selected["mode_id"]:
            continue
        expected = {(item["role"], item["input_id"]) for item in selected["object_inputs"]}
        actual = {(ref.role, ref.input_id) for ref in run.request.object_inputs}
        if expected != actual or len(actual) != len(run.request.object_inputs):
            raise ValueError("native_similarity_scope_inputs_mismatch")
        for ref in run.request.object_inputs:
            record = pool.get(ref.input_id)
            if (record is None or record["path"] != str(ref.path)
                    or any(record[key] != getattr(ref, key)
                    for key in ("sha256", "schema_ref", "object_version"))):
                raise ValueError("native_similarity_scope_inputs_mismatch")
            inputs.verify(state, record)
        if mode == "reference_similarity_exploratory":
            if (selected.get("asset_ids") != [scope.upload_id] or len(run.request.assets) != 1
                    or run.request.assets[0].asset_id != scope.upload_id
                    or run.request.assets[0].checksum != view["parent_asset_sha256"]
                    or run.request.assets[0].metadata.get("data_view_id") != view["view_id"]):
                raise ValueError("native_similarity_asset_binding_mismatch")
            source = inputs.verify(state, pool[next(ref.input_id for ref in run.request.object_inputs
                if ref.role == "reference_similarity_input")])
            refs = {ref.role: ref for ref in run.request.object_inputs}
            if (source["data_view"] != view
                    or refs["reference_similarity_input"].sha256 != run.result.get("input_sha256")
                    or refs["reference_manifest"].sha256 != run.result.get("reference_manifest_sha256")
                    or run.result.get("source_run_ref") != "tool-run:" + run.run_id + "@" + run.tool_version):
                raise ValueError("native_similarity_view_mismatch")
            original = run
            original_receipt_sha = receipt["sha256"]
        else:
            from bridge.tool_packages.p0_03_target_regional.technical_view import read_saved_source
            if selected.get("asset_ids") or run.request.assets:
                raise ValueError("native_similarity_asset_binding_mismatch")
            saved_ref = run.request.object_inputs[0]
            original, original_result, _, _ = read_saved_source(saved_ref)
            if original_result.data_view.model_dump(mode="json") != view:
                raise ValueError("native_similarity_view_mismatch")
            original_receipt_sha = saved_ref.sha256
        result = run.result
        if (result.get("data_view") != view or result.get("source_asset_id") != scope.upload_id
                or result.get("source_asset_sha256") != view["parent_asset_sha256"]
                or result.get("analysis_scope") != "whole_view_technical_aggregate"
                or result.get("biological_independence") != "unknown"
                or result.get("n_independent_biological_replicates") is not None
                or result.get("domain_score") is not None):
            raise ValueError("native_similarity_view_mismatch")
        artifacts = {artifact.kind: artifact for artifact in run.artifacts}
        if len(artifacts) != len(run.artifacts):
            raise ValueError("native_similarity_artifact_ambiguous")
        result_artifact = artifacts.get("reference_similarity_exploratory_result")
        if result_artifact is None or strict_json(checked_bytes(inputs.service, state,
                result_artifact.path, result_artifact.sha256,
                root=inputs.service.directory(state["id"]) / "runs")) != result:
            raise ValueError("native_similarity_result_artifact_mismatch")
        kinds = {"native_measurement_spec", *(artifact.kind for artifact in run.artifacts
                 if re.fullmatch(r"native_measurement_[0-9]+", artifact.kind))}
        _, outputs = inputs.producer_objects(state, receipt, "P0-03", kinds)
        specs = outputs.get("native_measurement_spec", [])
        values = [item for kind, rows in outputs.items() if re.fullmatch(r"native_measurement_[0-9]+", kind)
                  for item in rows]
        if len(specs) != 1 or len(values) != len(run.measurements) or not values:
            raise ValueError("native_similarity_measurements_required")
        spec_id, spec = specs[0]
        contract = spec.get("input_contract", {})
        if (spec.get("analysis_unit_kind") != "whole_view_technical_aggregate"
                or spec.get("data_view") != view or spec.get("assay") != original.request.assets[0].assay
                or spec.get("biological_independence") != "unknown"
                or spec.get("n_independent_biological_replicates") is not None
                or contract.get("original_producer_ref") != result["source_run_ref"]
                or contract.get("input_sha256") != result["input_sha256"]
                or contract.get("reference_manifest_sha256") != result["reference_manifest_sha256"]
                or (mode == "saved_reference_similarity_projection"
                    and contract.get("original_receipt_sha256") != original_receipt_sha)):
            raise ValueError("native_similarity_spec_binding_mismatch")
        summary = {row.measurement_id: row.model_dump(mode="json") for row in run.measurements}
        if (len(summary) != len(values) or any(value["measurement_id"] not in summary
                or any(value.get(key) != item for key, item in summary[value["measurement_id"]].items())
                or value["measurement_spec_id"] != spec["measurement_spec_id"]
                or value["measurement_spec_version"] != spec["version"]
                or value["source_run_ref"] != "tool-run:" + run.run_id + "@" + run.tool_version
                or value["source_execution_state"] != receipt["state"]
                for _, value in values)):
            raise ValueError("native_similarity_measurement_binding_mismatch")
        profile = {"input_data_view": view,
                   "evidence_ids": [result["result_id"], result["source_run_ref"],
                                    "source-receipt-sha256:" + original_receipt_sha],
                   "model_sha256": result_artifact.sha256,
                   "verification_sha256": receipt["sha256"],
                   "source_input_ids": [ref.input_id for ref in run.request.object_inputs]}
        if mode == "saved_reference_similarity_projection":
            profile["parent_artifact"] = {"artifact_id": contract["original_result_artifact_id"],
                                          "sha256": contract["original_result_sha256"],
                                          "version": original.tool_version}
        candidates.append((run, spec_id, profile, values, spec_id, spec))
    if len(candidates) > 1:
        raise ValueError("native_similarity_source_ambiguous")
    return candidates[0] if candidates else None


def _process_source(reports, state, pool, expected_view):
    return _p006_source(reports, state, pool, expected_view,
        "bridge://schemas/exploratory-process-profile/v0.1",
        {"bridge://schemas/measurement-spec/v0.2", "bridge://schemas/measurement-spec/v0.3"})


def _saved_context_source(reports, state, pool, expected_view, tool_id):
    inputs = reports.service.inputs
    profiles = reports._canonical_outputs(state, pool, tool_id,
        {"bridge://schemas/native-cell-state-context-profile/v0.1",
         "bridge://schemas/native-cell-state-context-profile/v0.2",
         "bridge://schemas/saved-target-role-profile/v0.1"})
    for identifier, profile, run in reversed(profiles):
        if profile["data_view"] != expected_view:
            continue
        refs = [ref for ref in run.request.object_inputs if ref.role == "saved_cell_state_run"]
        if (run.result != profile or len(refs) != 1
                or refs[0].sha256 != profile["source_receipt_sha256"]):
            raise ValueError("native_context_profile_mismatch")
        record = pool[identifier]
        outputs = [(key, row) for key, row in pool.items()
                   if row.get("receipt_file") == record["receipt_file"]
                   and row.get("receipt_sha256") == record["receipt_sha256"]]
        specs = [(key, inputs.verify(state, row)) for key, row in outputs
                 if row["schema_ref"] == "bridge://schemas/measurement-spec/v0.3"]
        measurements = [(key, inputs.verify(state, row)) for key, row in outputs
                        if row["schema_ref"] == "bridge://schemas/measurement-result/v0.2"]
        if len(specs) != 1 or not measurements:
            raise ValueError("native_context_measurements_required")
        raw = {value.measurement_id: value.model_dump(mode="json") for value in run.measurements}
        if (len(raw) != len(measurements) or any(value["measurement_id"] not in raw
                or any(value.get(key) != item for key, item in raw[value["measurement_id"]].items())
                or value["source_run_ref"] != "tool-run:" + run.run_id + "@" + run.tool_version
                or value["source_execution_state"] != run.execution_state.value
                or value["measurement_spec_id"] != specs[0][1]["measurement_spec_id"]
                for _, value in measurements)):
            raise ValueError("native_context_receipt_mismatch")
        metadata = {"input_data_view": expected_view, "evidence_ids": [profile["profile_id"]],
                    "model_sha256": profile["source_receipt_sha256"],
                    "verification_sha256": record["receipt_sha256"]}
        return run, identifier, metadata, measurements, specs[0][0], specs[0][1]
    return None


def _program_sources(reports, state, pool, expected_view):
    rows = _p006_sources(reports, state, pool, expected_view,
        {"bridge://schemas/exploratory-program-profile/v0.1",
         "bridge://schemas/exploratory-program-profile/v0.2"},
        {"bridge://schemas/measurement-spec/v0.3"})
    seen, latest = set(), []
    for row in rows:
        sets = tuple(sorted(program["source_gene_set"] for program in row[0].result["input_contract"]["programs"]))
        if sets not in seen:
            seen.add(sets)
            latest.append(row)
    return list(reversed(latest))


def _p006_source(reports, state, pool, expected_view, profile_schema, spec_schema):
    return next(iter(_p006_sources(reports, state, pool, expected_view, profile_schema, spec_schema)), None)


def _p006_sources(reports, state, pool, expected_view, profile_schema, spec_schema):
    inputs = reports.service.inputs
    profiles = reports._canonical_outputs(state, pool, "P0-06", profile_schema)
    found = []
    for identifier, profile, run in reversed(profiles):
        if profile["input_contract"]["data_view"] != expected_view:
            continue
        if run.result != profile or len(run.request.assets) != 1:
            raise ValueError("native_process_profile_mismatch")
        record = pool[identifier]
        outputs = [(key, row) for key, row in pool.items()
                   if row.get("receipt_file") == record["receipt_file"]]
        specs = [(key, inputs.verify(state, row)) for key, row in outputs
                 if row["schema_ref"] in spec_schema]
        measurements = [(key, inputs.verify(state, row)) for key, row in outputs
                        if row["schema_ref"] == "bridge://schemas/measurement-result/v0.2"]
        if len(specs) != 1 or not measurements:
            raise ValueError("native_process_measurements_required")
        raw = {value.measurement_id: value.model_dump(mode="json") for value in run.measurements}
        if (len(raw) != len(measurements) or any(value["measurement_id"] not in raw
                or any(value.get(key) != item for key, item in raw[value["measurement_id"]].items())
                for _, value in measurements)):
            raise ValueError("native_process_receipt_mismatch")
        for _, value in measurements:
            if (value["source_run_ref"] != "tool-run:" + run.run_id + "@" + run.tool_version
                    or value["source_execution_state"] != run.execution_state.value
                    or value["measurement_spec_id"] != specs[0][1]["measurement_spec_id"]):
                raise ValueError("native_process_receipt_mismatch")
        resource_hash = (profile["input_contract"]["resource"]["sha256"]
                         if "resource" in profile["input_contract"]
                         else profile["input_contract"]["resource_sha256"])
        metadata = {"input_data_view": expected_view, "evidence_ids": [profile["profile_id"]],
                    "model_sha256": resource_hash,
                    "verification_sha256": record["receipt_sha256"]}
        found.append((run, identifier, metadata, measurements, specs[0][0], specs[0][1]))
    return found


def _append_history(inputs, state, pool, latest, bundle, objects, choices, dependencies):
    graph_id, graph, _ = latest
    graph_record = pool[graph_id]
    receipt = ToolRunV2.model_validate(strict_json(checked_bytes(
        inputs.service, state,
        inputs.service.directory(state["id"]) / "receipts" / graph_record["receipt_file"],
        graph_record["receipt_sha256"],
        root=inputs.service.directory(state["id"]) / "receipts")))
    if (receipt.request.tool_id != "P0-09" or receipt.execution_state.value not in {"succeeded", "partial"}
            or not any(item.artifact_id == graph_record["artifact_id"] and item.sha256 == graph_record["sha256"]
                       for item in receipt.artifacts)):
        raise ValueError("canonical_graph_history_mismatch")
    previous = {}
    for role in ("compilation_bundle", "claim_registry", "evidence_family_registry"):
        refs = [item for item in receipt.request.object_inputs if item.role == role]
        if len(refs) != 1 or refs[0].input_id not in pool:
            raise ValueError("canonical_graph_history_required")
        record = pool[refs[0].input_id]
        if record["sha256"] != refs[0].sha256 or record["schema_ref"] != refs[0].schema_ref:
            raise ValueError("canonical_graph_history_mismatch")
        previous[role] = inputs.verify(state, record)
    catalog = {(row["object_id"], row["object_version"]): row for row in bundle["object_catalog"]}
    for row in previous["compilation_bundle"]["object_catalog"]:
        key = (row["object_id"], row["object_version"])
        if key in catalog and catalog[key] != row:
            raise ValueError("native_object_catalog_identity_conflict")
        catalog[key] = row
    bundle["object_catalog"] = list(catalog.values())
    claims = {(row["claim_id"], row["version"]): row for row in objects["claim_registry"]["claims"]}
    for row in previous["claim_registry"]["claims"]:
        key = (row["claim_id"], row["version"])
        if key in claims and claims[key] != row:
            raise ValueError("native_claim_identity_conflict")
        claims[key] = row
    objects["claim_registry"]["claims"] = list(claims.values())
    families = objects["evidence_family_registry"]["families"]
    old_families = previous["evidence_family_registry"]["families"]
    if len(families) != 1 or len(old_families) != 1:
        raise ValueError("native_family_history_invalid")
    family, old_family = families[0], old_families[0]
    for key in ("evidence_family_id", "version"):
        if family[key] != old_family[key]:
            raise ValueError("native_family_history_invalid")
    for key in ("shared_algorithm_refs", "shared_reference_or_prior_refs"):
        family[key] = sorted(set(family[key] + old_family[key]))
    same_receipt = {key: row for key, row in pool.items()
                    if row.get("receipt_file") == graph_record["receipt_file"]}
    for role, schema, field in (
        ("base_evidence_record_set", "evidence-record-set", "records"),
        ("base_evidence_requirement_set", "evidence-requirement-set", "requirements")):
        found = [(key, inputs.verify(state, row)) for key, row in same_receipt.items()
                 if row["schema_ref"] == "bridge://schemas/" + schema + "/v0.1"]
        if len(found) != 1:
            raise ValueError("canonical_graph_history_required")
        key, value = found[0]
        if (value["graph_id"], value["graph_version"]) != (graph["graph_id"], graph["graph_version"]):
            raise ValueError("canonical_graph_history_mismatch")
        choices.append((role, key))
        dependencies.append(key)
        bundle["prior_evidence_records" if field == "records" else "prior_requirements"] = value[field]
    choices.append(("base_graph_manifest", graph_id))
    dependencies.append(graph_id)
    bound = dict(choices)
    bundle["base_graph_ref"] = {"graph_id": graph["graph_id"], "graph_version": graph["graph_version"],
        "manifest_sha256": graph_record["sha256"], "manifest_input_id": graph_id,
        "record_set_input_id": bound["base_evidence_record_set"],
        "requirement_set_input_id": bound["base_evidence_requirement_set"]}
    prior = bundle["prior_evidence_records"]
    bundle["candidate_records"] = _continuation_candidates(bundle["candidate_records"], prior)
    if not bundle["candidate_records"] and not _coverage_changed(bundle.get("missing_observations", []), bundle["prior_requirements"]):
        raise ValueError("canonical_graph_inputs_unchanged")


def _continuation_candidates(candidates, prior):
    """Link a new producer to the latest record of the exact same contract."""
    history = [EvidenceRecord.model_validate(row) for row in prior]
    compiled = {(row.measurement_result_ref.ref, row.tool_run_ref.ref) for row in history}
    latest = {row.logical_key: row for row in sorted(history, key=lambda row: row.evidence_version)}
    result = []
    for value in candidates:
        candidate = EvidenceCandidate.model_validate(value)
        if (candidate.measurement_result_ref.ref, candidate.tool_run_ref.ref) in compiled:
            continue
        predecessor = latest.get(evidence_logical_key(candidate))
        if predecessor is None:
            result.append(value)
            continue
        if predecessor.lifecycle_state.value != "active":
            raise ValueError("native_invalidated_evidence_revision_requires_review")
        result.append({**value, "revision_action": "supersede", "predecessor_ref": predecessor.ref})
    return result


def _policy(case, definition, role_map, run, profile, measurements, spec, suff_id, sufficiency, family_id, created_at,
            domain_id="target_identity", method_id="METHOD-CELLTYPIST-CUSTOM-CLASSIFIER"):
    case_ref = case.ref.model_dump(mode="json")
    context_ref = definition.ref.model_dump(mode="json")
    family_ref = _ref(family_id, "0.1.0")
    recon_ref = _ref("reconciliation-spec:native-method-output", "0.1.0")
    provenance = [case.ref.ref, "tool-run:" + run.run_id + "@" + run.tool_version,
                  *profile.get("evidence_ids", [])]
    catalog = []
    def obj(ref, kind, schema, value):
        catalog.append({**ref, "node_type": kind, "schema_ref": schema, "content_hash": digest(value)})
    obj(case_ref, "ProductCase", "bridge://schemas/product-case/v0.1", case.model_dump(mode="json"))
    obj(context_ref, "ProductDefinitionCard", "bridge://schemas/product-definition-card/v0.1", definition.model_dump(mode="json"))
    obj(case.sample_or_preparation_ref.model_dump(mode="json"), "Sample" if case.source_unit_kind == "sample" else "Preparation",
        "bridge://schemas/" + case.source_unit_kind + "/v0.1",
        {"identity": case.sample_or_preparation_ref.model_dump(mode="json"), "data_view": profile["input_data_view"]})
    technical = spec.get("analysis_unit_kind") == "whole_view_technical_aggregate"
    obj(_ref(spec["measurement_spec_id"], spec["version"]), "MeasurementSpec",
        "bridge://schemas/measurement-spec/v0.3" if technical else "bridge://schemas/measurement-spec/v0.2", spec)
    obj(_ref("tool-run:" + run.run_id, run.tool_version), "ToolRun", "bridge://schemas/tool-run/v0.2" if hasattr(run.request, "object_inputs") else "bridge://schemas/tool-run/v0.1",
        run.model_dump(mode="json"))
    artifacts = []
    measurement_artifacts = {}
    measurement_ids = {value["measurement_id"] for _, value in measurements}
    output_root = Path(run.request.output_dir).resolve(strict=True)
    for artifact in run.artifacts:
        ref = _ref(artifact.artifact_id, run.tool_version)
        catalog.append({**ref, "node_type": "Artifact", "schema_ref": "bridge://schemas/artifact/v0.1",
                        "content_hash": artifact.sha256})
        if artifact.kind == "measurement_result_v2" or re.fullmatch(r"native_measurement_[0-9]+", artifact.kind):
            path = Path(artifact.path)
            resolved = path.resolve(strict=True)
            if not resolved.is_relative_to(output_root):
                raise ValueError("native_artifact_path_invalid")
            raw = read_regular_bytes(path)
            if sha256(raw).hexdigest() != artifact.sha256:
                raise ValueError("native_artifact_hash_mismatch")
            payload = MeasurementResultV2.model_validate(strict_json_loads(raw))
            measurement_id = payload.measurement_id
            if measurement_id not in measurement_ids or measurement_id in measurement_artifacts:
                raise ValueError("native_measurement_artifact_mismatch")
            measurement = next(value for _, value in measurements if value["measurement_id"] == measurement_id)
            if any(measurement.get(key) != value for key, value in
                    payload.model_dump(mode="json", exclude_unset=True).items()):
                raise ValueError("native_measurement_artifact_mismatch")
            measurement_artifacts[measurement_id] = ref
        else:
            artifacts.append(ref)
    if measurement_artifacts and set(measurement_artifacts) != measurement_ids:
        raise ValueError("native_measurement_artifact_required")
    if parent := profile.get("parent_artifact"):
        ref = _ref(parent["artifact_id"], parent["version"])
        catalog.append({**ref, "node_type": "Artifact", "schema_ref": "bridge://schemas/artifact/v0.1",
                        "content_hash": parent["sha256"]})
        artifacts.append(ref)
    claims, candidates = [], []
    for _, measurement in measurements:
        key = digest([domain_id, measurement["metric_name"]])[:24]
        claim_ref = _ref("claim:native-" + key, "0.1.0")
        claims.append({"claim_id": claim_ref["object_id"], "version": "0.1.0", "claim_type": "native_method_output",
            "domain_id": domain_id, "claim_target_ref": case.ref.ref, "biological_context_ref": context_ref,
            "allowed_relations": ["supports"], "reconciliation_spec_ref": recon_ref, "status": "candidate",
            "requirement_specs": [{"requirement_key": "independent_validation", "channel_role": "independent_validation",
                                  "blocking_scope": "biological_identity", "required": True}]})
        measurement_ref = _ref(measurement["measurement_id"], "0.2.0")
        obj(measurement_ref, "MeasurementResult", "bridge://schemas/measurement-result/v0.2", measurement)
        candidates.append({
            "candidate_id": "evidence-candidate:native-" + digest(measurement)[:24],
            "product_case_ref": case_ref, "sample_or_preparation_ref": case.sample_or_preparation_ref.model_dump(mode="json"),
            "domain_id": domain_id, "measurement_result_ref": measurement_ref,
            "measurement_spec_ref": _ref(spec["measurement_spec_id"], spec["version"]),
            "metric_id": measurement["metric_name"], "value": measurement["raw_value"], "unit": measurement["unit"],
            "numerator": measurement["numerator"], "denominator": measurement["denominator"],
            "claim_ref": claim_ref, "biological_context": {"context_id": context_ref["object_id"],
                "context_version": context_ref["object_version"], "assay": case.assay},
            "relation": "supports", "evidence_state": measurement["evidence_state"], "evidence_tier": "exploratory",
            "applicability": "applicable", "evidence_family_ref": family_ref,
            "sufficiency_profile_input_id": suff_id,
            "tool_run_ref": _ref("tool-run:" + run.run_id, run.tool_version),
            "tool_run_execution_state": run.execution_state.value,
            "artifact_refs": [*artifacts, *([measurement_artifacts[measurement["measurement_id"]]]
                if measurement_artifacts else [])],
            "provenance_refs": sorted(set(provenance + measurement["provenance_refs"])), "revision_action": "create", "created_at": created_at})
    common = {"registry_version": "0.1.0", "created_at": created_at, "status": "candidate"}
    return {
        "compilation_bundle": EvidenceCompilationBundle(
            bundle_id="evidence-compilation-bundle:native-" + digest([case_ref, run.run_id])[:24],
            bundle_version="0.1.0", graph_kind="case", product_case_ref=case_ref, object_catalog=catalog,
            candidate_records=candidates, created_at=created_at, provenance_refs=provenance),
        "evidence_family_registry": EvidenceFamilyRegistry.model_validate({**common,
            "registry_id": "BRIDGE-EVIDENCE-FAMILY-REGISTRY-v0.1", "families": [{
                "evidence_family_id": family_id, "version": "0.1.0", "family_type": "shared_data",
                "channel_role": "native_method_output", "shared_source_refs": [case.sample_or_preparation_ref.ref],
                "shared_algorithm_refs": [],
                "shared_reference_or_prior_refs": [],
                "independence_scope": "Shared query RNA; no independent biological confirmation.",
                "rationale": "Describes native outputs only; validation metadata is not a second measurement.",
                "status": "unreviewed"}]}),
        "claim_registry": ClaimRegistry.model_validate({**common, "registry_id": "BRIDGE-CLAIM-REGISTRY-v0.1", "claims": claims}),
        "reconciliation_spec_registry": ReconciliationSpecRegistry.model_validate({**common,
            "registry_id": "BRIDGE-RECONCILIATION-SPEC-REGISTRY-v0.1", "specs": [{
                "reconciliation_spec_id": recon_ref["object_id"], "version": "0.1.0", "claim_type": "native_method_output",
                "required_channel_roles": ["independent_validation"], "optional_channel_roles": ["native_method_output"],
                "primary_channel_roles": ["native_method_output"],
                "minimum_independent_families_by_role": {"independent_validation": 1},
                "allowed_evidence_states": ["measured", "inferred", "unavailable", "unknown"], "conflict_rule": "family_dedup_then_channel_resolution",
                "consensus_rule": "unanimous_independent_confirmation",
                "integration_sensitivity_rule": "integration_role_disagrees_with_resolved_direction",
                "missing_behavior": "insufficient_evidence", "status": "candidate"}]}),
    }
