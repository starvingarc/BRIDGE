from __future__ import annotations

import json
from importlib.resources import files

SCHEMA_REFS = {
    "bridge://schemas/developmental-compatibility-visualization-data/v0.1": "developmental_compatibility_visualization_data.schema.json",
    "bridge://schemas/evidence-compiler-visualization-data/v0.1": "evidence_compiler_visualization_data.schema.json",
    "bridge://schemas/p0-03-visualization-artifact-set/v0.1": "p0_03_visualization_artifact_set.schema.json",
    "bridge://schemas/p0-04-visualization-artifact-set/v0.1": "p0_04_visualization_artifact_set.schema.json",
    "bridge://schemas/p0-09-visualization-artifact-set/v0.1": "p0_09_visualization_artifact_set.schema.json",
    "bridge://schemas/target-regional-visualization-data/v0.1": "target_regional_visualization_data.schema.json",
    "bridge://schemas/native-cell-state-context-profile/v0.2": "native_cell_state_context_profile_v2.schema.json",
    "bridge://schemas/off-target-hard-count-profile/v0.3": "off_target_hard_count_profile_v3.schema.json",
    "bridge://schemas/off-target-control-result/v0.4": "off_target_control_result_v4.schema.json",
    "bridge://schemas/exploratory-process-input/v0.3": "exploratory_process_input_v3.schema.json",
    "bridge://schemas/exploratory-program-profile/v0.2": "exploratory_program_profile_v2.schema.json",
    "bridge://schemas/proliferation-stress-response-result/v0.3": "proliferation_stress_response_result_v3.schema.json",
    "bridge://schemas/off-target-hard-count-profile/v0.2": "off_target_hard_count_profile_v2.schema.json",
    "bridge://schemas/off-target-control-result/v0.3": "off_target_control_result_v3.schema.json",
    "bridge://schemas/native-cell-state-context-profile/v0.1": "native_cell_state_context_profile.schema.json",
    "bridge://schemas/developmental-compatibility-result/v0.4": "developmental_compatibility_result_v4.schema.json",
    "bridge://schemas/off-target-control-result/v0.2": "off_target_control_result_v2.schema.json",
    "bridge://schemas/cell-state-development-review/v1.1": "cell_state_development_review_v1_1.schema.json",
    "bridge://schemas/cell-state-development-review/v1.0": "cell_state_development_review.schema.json",
    "bridge://schemas/cell-state-ood-calibration/v1.0": "cell_state_ood_calibration.schema.json",
    "bridge://schemas/cell-state-candidate-runtime/v1.0": "cell_state_candidate_runtime.schema.json",
    "bridge://schemas/cell-state-candidate-profile/v1.0": "cell_state_candidate_profile.schema.json",
    "bridge://schemas/exploratory-process-input/v0.1": "exploratory_process_input.schema.json",
    "bridge://schemas/exploratory-process-input/v0.2": "exploratory_process_input_v2.schema.json",
    "bridge://schemas/exploratory-program-profile/v0.1": "exploratory_program_profile.schema.json",
    "bridge://schemas/proliferation-stress-response-result/v0.2": "proliferation_stress_response_result_v2.schema.json",
    "bridge://schemas/exploratory-process-profile/v0.1": "exploratory_process_profile.schema.json",
    "bridge://schemas/proliferation-stress-response-result/v0.1": "proliferation_stress_response_result.schema.json",
    "bridge://schemas/agent-integration-profile/v0.1": "agent_integration_profile.schema.json",
    "bridge://schemas/annotation-vocabulary/v0.1": "annotation_vocabulary.schema.json",
    "bridge://schemas/artifact-manifest/v0.1": "artifact_manifest.schema.json",
    "bridge://schemas/benchmark-split-manifest/v0.2": "benchmark_split_manifest.schema.json",
    "bridge://schemas/biological-review-record/v0.1": "biological_review_record.schema.json",
    "bridge://schemas/biological-unit-assignment/v0.1": "biological_unit_assignment.schema.json",
    "bridge://schemas/biological-unit-manifest/v0.1": "biological_unit_manifest.schema.json",
    "bridge://schemas/biological-unit-attestation-receipt/v0.1": "biological_unit_attestation_receipt.schema.json",
    "bridge://schemas/cell-state-benchmark-spec/v0.2": "cell_state_benchmark_spec.schema.json",
    "bridge://schemas/cell-state-evidence-profile/v0.1": "cell_state_evidence_profile.schema.json",
    "bridge://schemas/cell-state-evidence-profile/v0.2": "cell_state_evidence_profile_v2.schema.json",
    "bridge://schemas/cell-state-evidence-profile/v0.3": "cell_state_evidence_profile_v3.schema.json",
    "bridge://schemas/cell-state-evidence-matrix-data/v0.1": "cell_state_evidence_matrix_data.schema.json",
    "bridge://schemas/cell-state-evidence-matrix-data/v0.2": "cell_state_evidence_matrix_data_v2.schema.json",
    "bridge://schemas/hierarchical-cell-state-visualization-data/v0.1": "hierarchical_cell_state_visualization_data.schema.json",
    "bridge://schemas/p0-02-visualization-artifact-set/v0.2": "p0_02_visualization_artifact_set_v2.schema.json",
    "bridge://schemas/expression-plot-data/v0.1": "expression_plot_data.schema.json",
    "bridge://schemas/p0-02-visualization-artifact-set/v0.1": "p0_02_visualization_artifact_set.schema.json",
    "bridge://schemas/hierarchical-cell-state-composition-data/v0.1": "hierarchical_cell_state_composition_data.schema.json",
    "bridge://schemas/cell-state-release-manifest/v0.1": "cell_state_release_manifest.schema.json",
    "bridge://schemas/case-evidence-readiness-summary/v0.1": "case_evidence_readiness_summary.schema.json",
    "bridge://schemas/case-evidence-graph-manifest/v0.1": "case_evidence_graph_manifest.schema.json",
    "bridge://schemas/claim-registry/v0.1": "claim_registry.schema.json",
    "bridge://schemas/claim-policy-spec/v0.1": "claim_policy_spec.schema.json",
    "bridge://schemas/research-claim-verification-result/v0.2": "research_claim_verification_result_v2.schema.json",
    "bridge://schemas/research-statement-registry/v0.2": "research_statement_registry_v2.schema.json",
    "bridge://schemas/research-analysis-snapshot/v0.2": "research_analysis_snapshot_v2.schema.json",
    "bridge://schemas/research-analysis-snapshot/v0.3": "research_analysis_snapshot_v3.schema.json",
    "bridge://schemas/research-report-context/v0.3": "research_report_context_v3.schema.json",
    "bridge://schemas/research-report-context/v0.4": "research_report_context_v4.schema.json",
    "bridge://schemas/research-report-context/v0.5": "research_report_context_v5.schema.json",
    "bridge://schemas/research-analysis-snapshot/v0.4": "research_analysis_snapshot_v4.schema.json",
    "bridge://schemas/research-analysis-snapshot/v0.5": "research_analysis_snapshot_v5.schema.json",
    "bridge://schemas/claim-verification-result/v0.1": "claim_verification_result.schema.json",
    "bridge://schemas/claim-verifier-visualization-data/v0.1": "claim_verifier_visualization_data.schema.json",
    "bridge://schemas/comparison-evidence-graph-manifest/v0.1": "comparison_evidence_graph_manifest.schema.json",
    "bridge://schemas/comparison-case-manifest/v0.1": "comparison_case_manifest.schema.json",
    "bridge://schemas/comparison-stability-spec/v0.1": "comparison_stability_spec.schema.json",
    "bridge://schemas/cytoscape-evidence-elements/v0.1": "cytoscape_evidence_elements.schema.json",
    "bridge://schemas/domain-gate-input/v0.1": "domain_gate_input.schema.json",
    "bridge://schemas/development-method-bundle/v0.1": "development_method_bundle.schema.json",
    "bridge://schemas/development-method-spec/v0.1": "development_method_spec.schema.json",
    "bridge://schemas/development-state-map/v0.1": "development_state_map.schema.json",
    "bridge://schemas/development-timepoint-series/v0.1": "development_timepoint_series.schema.json",
    "bridge://schemas/development-window-spec/v0.1": "development_window_spec.schema.json",
    "bridge://schemas/developmental-compatibility-result/v0.1": "developmental_compatibility_result.schema.json",
    "bridge://schemas/developmental-compatibility-result/v0.2": "developmental_compatibility_result_v2.schema.json",
    "bridge://schemas/developmental-compatibility-result/v0.3": "developmental_compatibility_result_v3.schema.json",
    "bridge://schemas/eligibility-result/v0.1": "eligibility_result.schema.json",
    "bridge://schemas/evidence-compilation-bundle/v0.1": "evidence_compilation_bundle.schema.json",
    "bridge://schemas/evidence-compiler-run-result/v0.1": "evidence_compiler_run_result.schema.json",
    "bridge://schemas/evidence-family-registry/v0.1": "evidence_family_registry.schema.json",
    "bridge://schemas/evidence-graph-query-result/v0.1": "evidence_graph_query_result.schema.json",
    "bridge://schemas/evidence-graph-query/v0.1": "evidence_graph_query.schema.json",
    "bridge://schemas/evidence-compiler-result/v0.2": "evidence_compiler_result_v2.schema.json",
    "bridge://schemas/evidence-record/v0.1": "evidence_record.schema.json",
    "bridge://schemas/evidence-record-set/v0.1": "evidence_record_set.schema.json",
    "bridge://schemas/evidence-rejected-record-list/v0.1": "evidence_rejected_record_list.schema.json",
    "bridge://schemas/evidence-requirement/v0.1": "evidence_requirement.schema.json",
    "bridge://schemas/evidence-requirement-set/v0.1": "evidence_requirement_set.schema.json",
    "bridge://schemas/evidence-sensitivity-record/v0.1": "evidence_sensitivity_record.schema.json",
    "bridge://schemas/evidence-sufficiency-gate-rule-spec/v0.1": "evidence_sufficiency_gate_rule_spec.schema.json",
    "bridge://schemas/evidence-sufficiency-gate-rule-spec/v0.2": "evidence_sufficiency_gate_rule_spec_v2.schema.json",
    "bridge://schemas/evidence-sufficiency-profile/v0.1": "evidence_sufficiency_profile.schema.json",
    "bridge://schemas/evidence-sufficiency-profile/v0.2": "evidence_sufficiency_profile_v2.schema.json",
    "bridge://schemas/evidence-sufficiency-reason-code-catalog/v0.1": "evidence_sufficiency_reason_code_catalog.schema.json",
    "bridge://schemas/evidence-sufficiency-reason-code-catalog/v0.2": "evidence_sufficiency_reason_code_catalog_v2.schema.json",
    "bridge://schemas/evidence-sufficiency-run-result/v0.1": "evidence_sufficiency_run_result.schema.json",
    "bridge://schemas/evidence-sufficiency-run-result/v0.2": "evidence_sufficiency_run_result_v2.schema.json",
    "bridge://schemas/evidence-sufficiency-run-result/v0.3": "evidence_sufficiency_run_result_v3.schema.json",
    "bridge://schemas/evidence-sufficiency-visualization-data/v0.1": "evidence_sufficiency_visualization_data.schema.json",
    "bridge://schemas/evidence-validation-record/v0.1": "evidence_validation_record.schema.json",
    "bridge://schemas/freeze-gate-spec/v0.2": "freeze_gate_spec.schema.json",
    "bridge://schemas/figure-registry/v0.1": "figure_registry.schema.json",
    "bridge://schemas/program-spec/v0.1": "program_spec.schema.json",
    "bridge://schemas/protocol-ir/v0.1": "protocol_ir.schema.json",
    "bridge://schemas/program-evidence-bundle/v0.1": "program_evidence_bundle.schema.json",
    "bridge://schemas/transcriptomic-review-flag/v0.1": "transcriptomic_review_flag.schema.json",
    "bridge://schemas/proliferation-stress-response-profile/v0.1": "proliferation_stress_response_profile.schema.json",
    "bridge://schemas/proliferation-stress-response-profile/v0.2": "proliferation_stress_response_profile_v2.schema.json",
    "bridge://schemas/proliferation-stress-response-profile/v0.3": "proliferation_stress_response_profile_v3.schema.json",
    "bridge://schemas/proliferation-stress-visualization-data/v0.1": "proliferation_stress_visualization_data.schema.json",
    "bridge://schemas/process-method-spec/v0.1": "process_method_spec.schema.json",
    "bridge://schemas/process-method-input/v0.1": "process_method_input.schema.json",
    "bridge://schemas/process-method-input/v0.2": "process_method_input_v2.schema.json",
    "bridge://schemas/process-method-bundle/v0.1": "process_method_bundle.schema.json",
    "bridge://schemas/process-method-bundle/v0.2": "process_method_bundle_v2.schema.json",
    "bridge://schemas/graft-assessment-result/v0.1": "graft_assessment_result.schema.json",
    "bridge://schemas/graft-assessment-run-result/v0.1": "graft_assessment_run_result.schema.json",
    "bridge://schemas/graft-assessment-visualization-data/v0.1": "graft_assessment_visualization_data.schema.json",
    "bridge://schemas/p0-12-visualization-artifact-set/v0.1": "p0_12_visualization_artifact_set.schema.json",
    "bridge://schemas/comparison-method-spec/v0.1": "comparison_method_spec.schema.json",
    "bridge://schemas/comparison-method-input/v0.1": "comparison_method_input.schema.json",
    "bridge://schemas/comparison-method-bundle/v0.1": "comparison_method_bundle.schema.json",
    "bridge://schemas/graft-assessment-spec/v0.1": "graft_assessment_spec.schema.json",
    "bridge://schemas/graft-case/v0.1": "graft_case.schema.json",
    "bridge://schemas/graft-evidence-bundle/v0.1": "graft_evidence_bundle.schema.json",
    "bridge://schemas/graft-expression-analysis-result/v0.1": "graft_expression_analysis_result.schema.json",
    "bridge://schemas/graft-expression-analysis-spec/v0.1": "graft_expression_analysis_spec.schema.json",
    "bridge://schemas/graft-expression-asset/v0.1": "graft_expression_asset.schema.json",
    "bridge://schemas/graft-marker-program-collection/v0.1": "graft_marker_program_collection.schema.json",
    "bridge://schemas/graft-reference-panel/v0.1": "graft_reference_panel.schema.json",
    "bridge://schemas/knowledge-hit/v0.1": "knowledge_hit.schema.json",
    "bridge://schemas/marker-program-card/v0.1": "marker_program_card.schema.json",
    "bridge://schemas/measurement-result/v0.1": "measurement_result.schema.json",
    "bridge://schemas/measurement-result/v0.2": "measurement_result_v2.schema.json",
    "bridge://schemas/measurement-spec/v0.1": "measurement_spec.schema.json",
    "bridge://schemas/measurement-spec/v0.2": "measurement_spec_v2.schema.json",
    "bridge://schemas/measurement-spec/v0.3": "measurement_spec_v3.schema.json",
    "bridge://schemas/off-target-assessment-spec/v0.1": "off_target_assessment_spec.schema.json",
    "bridge://schemas/off-target-control-profile/v0.1": "off_target_control_profile.schema.json",
    "bridge://schemas/off-target-control-profile/v0.2": "off_target_control_profile_v2.schema.json",
    "bridge://schemas/off-target-hard-count-profile/v0.1": "off_target_hard_count_profile.schema.json",
    "bridge://schemas/off-target-control-result/v0.1": "off_target_control_result.schema.json",
    "bridge://schemas/off-target-control-visualization-data/v0.1": "off_target_control_visualization_data.schema.json",
    "bridge://schemas/off-target-evidence-bundle/v0.1": "off_target_evidence_bundle.schema.json",
    "bridge://schemas/off-target-method-bundle/v0.1": "off_target_method_bundle.schema.json",
    "bridge://schemas/off-target-method-input/v0.1": "off_target_method_input.schema.json",
    "bridge://schemas/off-target-method-spec/v0.1": "off_target_method_spec.schema.json",
    "bridge://schemas/p0-05-visualization-artifact-set/v0.1": "p0_05_visualization_artifact_set.schema.json",
    "bridge://schemas/p0-06-visualization-artifact-set/v0.1": "p0_06_visualization_artifact_set.schema.json",
    "bridge://schemas/p0-01-structured-output-index/v0.1": "p0_01_structured_output_index.schema.json",
    "bridge://schemas/p0-01-structured-output-index/v0.2": "p0_01_structured_output_index_v2.schema.json",
    "bridge://schemas/p0-01-visualization-artifact-set/v0.1": "p0_01_visualization_artifact_set.schema.json",
    "bridge://schemas/product-case/v0.1": "product_case.schema.json",
    "bridge://schemas/product-definition-card/v0.1": "product_definition_card.schema.json",
    "bridge://schemas/product-evidence-bundle/v0.1": "product_evidence_bundle.schema.json",
    "bridge://schemas/product-comparison-stability-profile/v0.1": "product_comparison_stability_profile.schema.json",
    "bridge://schemas/product-comparison-stability-profile/v0.2": "product_comparison_stability_profile_v2.schema.json",
    "bridge://schemas/product-comparison-visualization-data/v0.1": "product_comparison_visualization_data.schema.json",
    "bridge://schemas/p0-07-visualization-artifact-set/v0.1": "p0_07_visualization_artifact_set.schema.json",
    "bridge://schemas/p0-08-visualization-artifact-set/v0.1": "p0_08_visualization_artifact_set.schema.json",
    "bridge://schemas/p0-10-visualization-artifact-set/v0.1": "p0_10_visualization_artifact_set.schema.json",
    "bridge://schemas/qc-readiness-profile/v0.1": "qc_readiness_profile.schema.json",
    "bridge://schemas/qc-visualization-data/v0.1": "qc_visualization_data.schema.json",
    "bridge://schemas/qc-readiness-profile/v0.2": "qc_readiness_profile_v2.schema.json",
    "bridge://schemas/prior-applicability-record/v0.1": "prior_applicability_record.schema.json",
    "bridge://schemas/reference-manifest/v0.1": "reference_manifest.schema.json",
    "bridge://schemas/reference-profile/v0.1": "reference_profile.schema.json",
    "bridge://schemas/reconciliation-record/v0.1": "reconciliation_record.schema.json",
    "bridge://schemas/reconciliation-record-set/v0.1": "reconciliation_record_set.schema.json",
    "bridge://schemas/reconciliation-spec-registry/v0.1": "reconciliation_spec_registry.schema.json",
    "bridge://schemas/public-export-manifest/v0.1": "public_export_manifest.schema.json",
    "bridge://schemas/public-export-policy-spec/v0.1": "public_export_policy_spec.schema.json",
    "bridge://schemas/public-export-request/v0.1": "public_export_request.schema.json",
    "bridge://schemas/public-export-result/v0.1": "public_export_result.schema.json",
    "bridge://schemas/public-artifact-audit-policy/v0.1": "public_artifact_audit_policy.schema.json",
    "bridge://schemas/public-artifact-manifest/v0.1": "public_artifact_manifest.schema.json",
    "bridge://schemas/public-artifact-audit-result/v0.1": "public_artifact_audit_result.schema.json",
    "bridge://schemas/public-safe-export-visualization-data/v0.1": "public_safe_export_visualization_data.schema.json",
    "bridge://schemas/p0-11-visualization-artifact-set/v0.1": "p0_11_visualization_artifact_set.schema.json",
    "bridge://schemas/public-safe-export-run-result/v0.1": "public_safe_export_run_result.schema.json",
    "bridge://schemas/public-safe-report/v0.1": "public_safe_report.schema.json",
    "bridge://schemas/report-draft/v0.1": "report_draft.schema.json",
    "bridge://schemas/statement-registry/v0.1": "statement_registry.schema.json",
    "bridge://schemas/state-role-map/v0.1": "state_role_map.schema.json",
    "bridge://schemas/target-regional-assessment-spec/v0.1": "target_regional_assessment_spec.schema.json",
    "bridge://schemas/target-regional-evidence-result/v0.1": "target_regional_evidence_result.schema.json",
    "bridge://schemas/target-regional-evidence-result/v0.2": "target_regional_evidence_result_v2.schema.json",
    "bridge://schemas/saved-target-role-profile/v0.1": "saved_target_role_profile.schema.json",
    "bridge://schemas/target-regional-result/v0.2": "target_regional_result_v2.schema.json",
    "bridge://schemas/target-regional-result/v0.1": "target_regional_result.schema.json",
    "bridge://schemas/reference-similarity-exploratory-input/v0.1": "reference_similarity_exploratory_input.schema.json",
    "bridge://schemas/target-regional-method-bundle/v0.1": "target_regional_method_bundle.schema.json",
    "bridge://schemas/target-regional-method-spec/v0.1": "target_regional_method_spec.schema.json",
    "bridge://schemas/structured-input-ref/v0.1": "structured_input_ref.schema.json",
    "bridge://schemas/tool-input-contract/v0.1": "tool_input_contract.schema.json",
    "bridge://schemas/tool-package-spec/v0.1": "tool_package_spec.schema.json",
    "bridge://schemas/tool-package-spec/v0.2": "tool_package_spec_v2.schema.json",
    "bridge://schemas/tool-request/v0.1": "tool_request.schema.json",
    "bridge://schemas/tool-request/v0.2": "tool_request_v2.schema.json",
    "bridge://schemas/tool-run/v0.1": "tool_run.schema.json",
    "bridge://schemas/tool-run/v0.2": "tool_run_v2.schema.json",
    "bridge://schemas/visualization-artifact/v0.1": "visualization_artifact.schema.json",
    "bridge://schemas/visualization-artifact/v0.2": "visualization_artifact_v2.schema.json",
}


def _read_schema(schema_ref: str) -> dict:
    try:
        filename = SCHEMA_REFS[schema_ref]
    except KeyError as exc:
        raise KeyError(f"Unknown schema reference: {schema_ref}") from exc
    resource = files("bridge.resources.schemas").joinpath(filename)
    if not resource.is_file():
        raise FileNotFoundError(f"Packaged schema is missing: {filename}")
    return json.loads(resource.read_text(encoding="utf-8"))


def load_schema(schema_ref: str) -> dict:
    """Bundle referenced package fragments into an offline, standalone schema."""
    schema = _read_schema(schema_ref)
    documents = {schema_ref: schema}
    references, imported = {}, {}

    def bundle(value, base):
        if isinstance(value, list):
            return [bundle(item, base) for item in value]
        if not isinstance(value, dict):
            return value
        result = {key: bundle(item, base) for key, item in value.items() if key != "$ref"}
        if "$ref" in value:
            uri, _, fragment = value["$ref"].partition("#")
            uri = uri or base
            if uri == schema_ref:
                result["$ref"] = "#" + fragment
            else:
                identity = (uri, fragment)
                if identity not in references:
                    if uri not in documents:
                        documents[uri] = _read_schema(uri)  # Registered files only; never fetch URLs.
                    target = documents[uri]
                    if fragment:
                        if not fragment.startswith("/"):
                            raise ValueError("Packaged schema references must use JSON pointers")
                        for part in fragment[1:].split("/"):
                            key = part.replace("~1", "/").replace("~0", "~")
                            target = target[int(key)] if isinstance(target, list) else target[key]
                    key = f"linked_schema_{len(references)}"
                    if key in schema.get("$defs", {}):
                        raise ValueError(f"Schema definition collision: {key}")
                    references[identity] = "#/$defs/" + key
                    # Import only the referenced fragment; resolve its dependencies on demand.
                    if isinstance(target, dict):
                        target = {k: v for k, v in target.items() if k not in {"$id", "$defs"}}
                    imported[key] = bundle(target, uri)
                result["$ref"] = references[identity]
        return result

    schema = bundle(schema, schema_ref)
    if imported:
        schema.setdefault("$defs", {}).update(imported)
    return schema
