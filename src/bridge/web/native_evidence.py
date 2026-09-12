"""Method-native observations enter the existing graph without identity qualification."""
from __future__ import annotations

from datetime import datetime, timezone

from bridge.tool_packages._configurable_contracts import ProductCase, ProductDefinitionCard, StateRoleMap
from bridge.tool_packages.p0_02_cell_state.scientific_review import load_development_review, development_review_sha256
from bridge.tool_packages.p0_08_evidence_sufficiency.models import DomainGateInput, EvidenceValidationRecord
from bridge.tool_packages.p0_09_evidence_compiler.models import (
    ClaimRegistry, EvidenceCompilationBundle, EvidenceFamilyRegistry, ReconciliationSpecRegistry,
)
from .inputs import ObjectChoice, Selection
from .scientific_inputs import digest


def _ref(identifier, version):
    return {"object_id": identifier, "object_version": version}


def case_context_key(view, facts):
    # A display-name edit does not change the scientific case or its measurements.
    return digest({"view": view, "facts": {key: value for key, value in facts.items() if key != "product_name"},
                   "review": development_review_sha256()})


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
    sources = [(source, "target_identity", "METHOD-CELLTYPIST-CUSTOM-CLASSIFIER")]
    process = _process_source(reports, state, pool, view)
    if process is not None:
        sources.append((process, "proliferation_stress_response", "METHOD-NATIVE-CELL-CYCLE"))
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
    def add(role, schema, payload, dependencies=(), tool=None, mode=None):
        return inputs.add_derived_object(state, tool_id=tool or allowed.tool_id,
            mode_id=mode or allowed.mode_id, role=role, schema_ref="bridge://schemas/" + schema,
            payload=payload.model_dump(mode="json") if hasattr(payload, "model_dump") else payload,
            dependencies=[*base_dependencies, *dependencies])
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
    if latest is not None:
        graph_record = pool[latest[0]]
        prior_sets = [inputs.verify(state, row) for row in pool.values()
                      if row.get("receipt_file") == graph_record["receipt_file"]
                      and row["schema_ref"] == "bridge://schemas/evidence-record-set/v0.1"]
        if len(prior_sets) != 1:
            raise ValueError("canonical_graph_history_required")
        prior_measurements = {(row["measurement_result_ref"]["object_id"], row["tool_run_ref"]["object_id"])
                              for row in prior_sets[0]["records"]}
    def previously_compiled(src):
        source_run, _, _, values, _, _ = src
        return all((value["measurement_id"], "tool-run:" + source_run.run_id) in prior_measurements
                   for _, value in values)
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
            required_for_interpretation=False, method_kind="learned" if domain_id == "target_identity" else "deterministic",
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
        if allowed.tool_id == "P0-08" and not previously_compiled(src):
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
        if not domains:
            raise ValueError("canonical_graph_inputs_unchanged")
        inputs.package_options(state)
        gate_id = next(key for key, row in state["_input_objects"].items()
                       if row["source"] == "package_resource" and row["label"] == "gate_rule_spec")
        choices = [("product_case", case_input), ("gate_rule_spec", gate_id),
                   ("qc_readiness_profile", qc_id), *domains, *all_measurements]
        return Selection(tool_id="P0-08", mode_id="default", asset_ids=[], measurement_spec_ref=None,
                         object_inputs=[ObjectChoice(role=role, input_id=key) for role, key in choices])
    latest = reports._latest_graph(state, pool, (case_id, "0.1.0"))
    if allowed.tool_id == "P0-10":
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
               "bridge://schemas/evidence-sufficiency-run-result/v0.2")
               if row[1]["case_summary"]["product_case_ref"] == case.ref.model_dump(mode="json")]
    if not results:
        raise ValueError("canonical_sufficiency_result_required")
    suff_id, sufficiency, _ = results[-1]
    profiles = {row["domain_id"]: row for row in sufficiency["profiles"]}
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
    choices = [("evidence_sufficiency_run_result", suff_id)]
    dependencies = [case_input, suff_id, *validations,
                    *(key for src, _, _ in sources for key, _ in src[3])]
    if latest is not None:
        _append_history(inputs, state, pool, latest, bundle, choices, dependencies)
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


def _process_source(reports, state, pool, expected_view):
    inputs = reports.service.inputs
    profiles = reports._canonical_outputs(state, pool, "P0-06", "bridge://schemas/exploratory-process-profile/v0.1")
    for identifier, profile, run in reversed(profiles):
        if profile["input_contract"]["data_view"] != expected_view:
            continue
        if run.result != profile or len(run.request.assets) != 1:
            raise ValueError("native_process_profile_mismatch")
        record = pool[identifier]
        outputs = [(key, row) for key, row in pool.items()
                   if row.get("receipt_file") == record["receipt_file"]]
        specs = [(key, inputs.verify(state, row)) for key, row in outputs
                 if row["schema_ref"] == "bridge://schemas/measurement-spec/v0.2"]
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
        metadata = {"input_data_view": expected_view, "evidence_ids": [profile["profile_id"]],
                    "model_sha256": profile["input_contract"]["resource_sha256"],
                    "verification_sha256": record["receipt_sha256"]}
        return run, identifier, metadata, measurements, specs[0][0], specs[0][1]
    return None


def _append_history(inputs, state, pool, latest, bundle, choices, dependencies):
    graph_id, graph, _ = latest
    graph_record = pool[graph_id]
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
    # Identical source observations retain their original immutable profile association.
    bundle["candidate_records"] = [row for row in bundle["candidate_records"]
        if not any(old["measurement_result_ref"] == row["measurement_result_ref"]
                   and old["tool_run_ref"] == row["tool_run_ref"] for old in prior)]
    if not bundle["candidate_records"]:
        raise ValueError("canonical_graph_inputs_unchanged")


def _policy(case, definition, role_map, run, profile, measurements, spec, suff_id, sufficiency, family_id, created_at,
            domain_id="target_identity", method_id="METHOD-CELLTYPIST-CUSTOM-CLASSIFIER"):
    case_ref = case.ref.model_dump(mode="json")
    context_ref = definition.ref.model_dump(mode="json")
    family_ref = _ref(family_id, "0.1.0")
    recon_ref = _ref("reconciliation-spec:native-method-output", "0.1.0")
    provenance = [case.ref.ref, "tool-run:" + run.run_id + "@" + run.tool_version]
    catalog = []
    def obj(ref, kind, schema, value):
        catalog.append({**ref, "node_type": kind, "schema_ref": schema, "content_hash": digest(value)})
    obj(case_ref, "ProductCase", "bridge://schemas/product-case/v0.1", case.model_dump(mode="json"))
    obj(context_ref, "ProductDefinitionCard", "bridge://schemas/product-definition-card/v0.1", definition.model_dump(mode="json"))
    obj(case.sample_or_preparation_ref.model_dump(mode="json"), "Sample" if case.source_unit_kind == "sample" else "Preparation",
        "bridge://schemas/" + case.source_unit_kind + "/v0.1",
        {"identity": case.sample_or_preparation_ref.model_dump(mode="json"), "data_view": profile["input_data_view"]})
    obj(_ref(spec["measurement_spec_id"], spec["version"]), "MeasurementSpec", "bridge://schemas/measurement-spec/v0.2", spec)
    obj(_ref("tool-run:" + run.run_id, run.tool_version), "ToolRun", "bridge://schemas/tool-run/v0.2" if hasattr(run.request, "object_inputs") else "bridge://schemas/tool-run/v0.1",
        run.model_dump(mode="json"))
    artifacts = []
    for artifact in run.artifacts:
        ref = _ref(artifact.artifact_id, run.tool_version)
        catalog.append({**ref, "node_type": "Artifact", "schema_ref": "bridge://schemas/artifact/v0.1",
                        "content_hash": artifact.sha256})
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
            "tool_run_execution_state": run.execution_state.value, "artifact_refs": artifacts,
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
