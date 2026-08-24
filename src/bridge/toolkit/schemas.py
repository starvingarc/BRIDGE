from __future__ import annotations

import json
from importlib.resources import files


SCHEMA_REFS = {
    "bridge://schemas/annotation-vocabulary/v0.1": "annotation_vocabulary.schema.json",
    "bridge://schemas/artifact-manifest/v0.1": "artifact_manifest.schema.json",
    "bridge://schemas/benchmark-split-manifest/v0.2": "benchmark_split_manifest.schema.json",
    "bridge://schemas/biological-review-record/v0.1": "biological_review_record.schema.json",
    "bridge://schemas/biological-unit-assignment/v0.1": "biological_unit_assignment.schema.json",
    "bridge://schemas/biological-unit-manifest/v0.1": "biological_unit_manifest.schema.json",
    "bridge://schemas/cell-state-benchmark-spec/v0.2": "cell_state_benchmark_spec.schema.json",
    "bridge://schemas/cell-state-evidence-profile/v0.1": "cell_state_evidence_profile.schema.json",
    "bridge://schemas/cell-state-evidence-profile/v0.2": "cell_state_evidence_profile_v2.schema.json",
    "bridge://schemas/cell-state-release-manifest/v0.1": "cell_state_release_manifest.schema.json",
    "bridge://schemas/case-evidence-readiness-summary/v0.1": "case_evidence_readiness_summary.schema.json",
    "bridge://schemas/case-evidence-graph-manifest/v0.1": "case_evidence_graph_manifest.schema.json",
    "bridge://schemas/claim-registry/v0.1": "claim_registry.schema.json",
    "bridge://schemas/claim-policy-spec/v0.1": "claim_policy_spec.schema.json",
    "bridge://schemas/claim-verification-result/v0.1": "claim_verification_result.schema.json",
    "bridge://schemas/claim-verifier-benchmark/v0.1": "claim_verifier_benchmark.schema.json",
    "bridge://schemas/comparison-evidence-graph-manifest/v0.1": "comparison_evidence_graph_manifest.schema.json",
    "bridge://schemas/cytoscape-evidence-elements/v0.1": "cytoscape_evidence_elements.schema.json",
    "bridge://schemas/domain-gate-input/v0.1": "domain_gate_input.schema.json",
    "bridge://schemas/eligibility-result/v0.1": "eligibility_result.schema.json",
    "bridge://schemas/evidence-compilation-bundle/v0.1": "evidence_compilation_bundle.schema.json",
    "bridge://schemas/evidence-compiler-run-result/v0.1": "evidence_compiler_run_result.schema.json",
    "bridge://schemas/evidence-family-registry/v0.1": "evidence_family_registry.schema.json",
    "bridge://schemas/evidence-graph-query-result/v0.1": "evidence_graph_query_result.schema.json",
    "bridge://schemas/evidence-record/v0.1": "evidence_record.schema.json",
    "bridge://schemas/evidence-record-set/v0.1": "evidence_record_set.schema.json",
    "bridge://schemas/evidence-rejected-record-list/v0.1": "evidence_rejected_record_list.schema.json",
    "bridge://schemas/evidence-requirement/v0.1": "evidence_requirement.schema.json",
    "bridge://schemas/evidence-requirement-set/v0.1": "evidence_requirement_set.schema.json",
    "bridge://schemas/evidence-sensitivity-record/v0.1": "evidence_sensitivity_record.schema.json",
    "bridge://schemas/evidence-sufficiency-gate-rule-spec/v0.1": "evidence_sufficiency_gate_rule_spec.schema.json",
    "bridge://schemas/evidence-sufficiency-profile/v0.1": "evidence_sufficiency_profile.schema.json",
    "bridge://schemas/evidence-sufficiency-reason-code-catalog/v0.1": "evidence_sufficiency_reason_code_catalog.schema.json",
    "bridge://schemas/evidence-sufficiency-run-result/v0.1": "evidence_sufficiency_run_result.schema.json",
    "bridge://schemas/evidence-validation-record/v0.1": "evidence_validation_record.schema.json",
    "bridge://schemas/freeze-gate-spec/v0.2": "freeze_gate_spec.schema.json",
    "bridge://schemas/knowledge-hit/v0.1": "knowledge_hit.schema.json",
    "bridge://schemas/marker-program-card/v0.1": "marker_program_card.schema.json",
    "bridge://schemas/measurement-result/v0.1": "measurement_result.schema.json",
    "bridge://schemas/measurement-result/v0.2": "measurement_result_v2.schema.json",
    "bridge://schemas/measurement-spec/v0.1": "measurement_spec.schema.json",
    "bridge://schemas/measurement-spec/v0.2": "measurement_spec_v2.schema.json",
    "bridge://schemas/product-case/v0.1": "product_case.schema.json",
    "bridge://schemas/product-definition-card/v0.1": "product_definition_card.schema.json",
    "bridge://schemas/qc-readiness-profile/v0.1": "qc_readiness_profile.schema.json",
    "bridge://schemas/qc-readiness-profile/v0.2": "qc_readiness_profile_v2.schema.json",
    "bridge://schemas/prior-applicability-record/v0.1": "prior_applicability_record.schema.json",
    "bridge://schemas/reference-manifest/v0.1": "reference_manifest.schema.json",
    "bridge://schemas/reference-profile/v0.1": "reference_profile.schema.json",
    "bridge://schemas/reconciliation-record/v0.1": "reconciliation_record.schema.json",
    "bridge://schemas/reconciliation-record-set/v0.1": "reconciliation_record_set.schema.json",
    "bridge://schemas/reconciliation-spec-registry/v0.1": "reconciliation_spec_registry.schema.json",
    "bridge://schemas/report-draft/v0.1": "report_draft.schema.json",
    "bridge://schemas/statement-registry/v0.1": "statement_registry.schema.json",
    "bridge://schemas/structured-input-ref/v0.1": "structured_input_ref.schema.json",
    "bridge://schemas/tool-package-spec/v0.1": "tool_package_spec.schema.json",
    "bridge://schemas/tool-package-spec/v0.2": "tool_package_spec_v2.schema.json",
    "bridge://schemas/tool-request/v0.1": "tool_request.schema.json",
    "bridge://schemas/tool-request/v0.2": "tool_request_v2.schema.json",
    "bridge://schemas/tool-run/v0.1": "tool_run.schema.json",
    "bridge://schemas/tool-run/v0.2": "tool_run_v2.schema.json",
    "bridge://schemas/visualization-artifact/v0.1": "visualization_artifact.schema.json",
}


def load_schema(schema_ref: str) -> dict:
    try:
        filename = SCHEMA_REFS[schema_ref]
    except KeyError as exc:
        raise KeyError(f"Unknown schema reference: {schema_ref}") from exc
    resource = files("bridge.resources.schemas").joinpath(filename)
    if not resource.is_file():
        raise FileNotFoundError(f"Packaged schema is missing: {filename}")
    return json.loads(resource.read_text(encoding="utf-8"))
