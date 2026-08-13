#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from bridge.toolkit.contracts import (
    AnnotationVocabulary,
    ArtifactManifest,
    BenchmarkSplitManifest,
    BiologicalReviewRecord,
    CellStateBenchmarkSpec,
    CellStateEvidenceProfile,
    CellStateReleaseManifest,
    EligibilityResult,
    FreezeGateSpec,
    KnowledgeHit,
    MarkerProgramCard,
    MeasurementResult,
    MeasurementSpec,
    QCReadinessProfile,
    ReferenceManifest,
    ReferenceProfile,
    StructuredInputRef,
    ToolPackageSpec,
    ToolPackageSpecV2,
    ToolRequest,
    ToolRequestV2,
    ToolRun,
    ToolRunV2,
    VisualizationArtifact,
)
from bridge.tool_packages.p0_08_evidence_sufficiency.models import (
    CaseEvidenceReadinessSummary,
    DomainGateInput,
    EvidenceSensitivityRecord,
    EvidenceSufficiencyProfile,
    EvidenceSufficiencyRunResult,
    EvidenceValidationRecord,
    GateRuleSpec,
    PriorApplicabilityRecord,
    ReasonCodeCatalog,
)


MODELS = {
    "annotation_vocabulary": ("bridge://schemas/annotation-vocabulary/v0.1", AnnotationVocabulary),
    "artifact_manifest": ("bridge://schemas/artifact-manifest/v0.1", ArtifactManifest),
    "benchmark_split_manifest": ("bridge://schemas/benchmark-split-manifest/v0.2", BenchmarkSplitManifest),
    "biological_review_record": ("bridge://schemas/biological-review-record/v0.1", BiologicalReviewRecord),
    "cell_state_benchmark_spec": ("bridge://schemas/cell-state-benchmark-spec/v0.2", CellStateBenchmarkSpec),
    "cell_state_evidence_profile": ("bridge://schemas/cell-state-evidence-profile/v0.1", CellStateEvidenceProfile),
    "cell_state_release_manifest": ("bridge://schemas/cell-state-release-manifest/v0.1", CellStateReleaseManifest),
    "case_evidence_readiness_summary": ("bridge://schemas/case-evidence-readiness-summary/v0.1", CaseEvidenceReadinessSummary),
    "domain_gate_input": ("bridge://schemas/domain-gate-input/v0.1", DomainGateInput),
    "eligibility_result": ("bridge://schemas/eligibility-result/v0.1", EligibilityResult),
    "evidence_sensitivity_record": ("bridge://schemas/evidence-sensitivity-record/v0.1", EvidenceSensitivityRecord),
    "evidence_sufficiency_gate_rule_spec": ("bridge://schemas/evidence-sufficiency-gate-rule-spec/v0.1", GateRuleSpec),
    "evidence_sufficiency_profile": ("bridge://schemas/evidence-sufficiency-profile/v0.1", EvidenceSufficiencyProfile),
    "evidence_sufficiency_reason_code_catalog": ("bridge://schemas/evidence-sufficiency-reason-code-catalog/v0.1", ReasonCodeCatalog),
    "evidence_sufficiency_run_result": ("bridge://schemas/evidence-sufficiency-run-result/v0.1", EvidenceSufficiencyRunResult),
    "evidence_validation_record": ("bridge://schemas/evidence-validation-record/v0.1", EvidenceValidationRecord),
    "freeze_gate_spec": ("bridge://schemas/freeze-gate-spec/v0.2", FreezeGateSpec),
    "knowledge_hit": ("bridge://schemas/knowledge-hit/v0.1", KnowledgeHit),
    "marker_program_card": ("bridge://schemas/marker-program-card/v0.1", MarkerProgramCard),
    "measurement_result": ("bridge://schemas/measurement-result/v0.1", MeasurementResult),
    "measurement_spec": ("bridge://schemas/measurement-spec/v0.1", MeasurementSpec),
    "qc_readiness_profile": ("bridge://schemas/qc-readiness-profile/v0.1", QCReadinessProfile),
    "prior_applicability_record": ("bridge://schemas/prior-applicability-record/v0.1", PriorApplicabilityRecord),
    "reference_manifest": ("bridge://schemas/reference-manifest/v0.1", ReferenceManifest),
    "reference_profile": ("bridge://schemas/reference-profile/v0.1", ReferenceProfile),
    "structured_input_ref": ("bridge://schemas/structured-input-ref/v0.1", StructuredInputRef),
    "tool_package_spec": ("bridge://schemas/tool-package-spec/v0.1", ToolPackageSpec),
    "tool_package_spec_v2": ("bridge://schemas/tool-package-spec/v0.2", ToolPackageSpecV2),
    "tool_request": ("bridge://schemas/tool-request/v0.1", ToolRequest),
    "tool_request_v2": ("bridge://schemas/tool-request/v0.2", ToolRequestV2),
    "tool_run": ("bridge://schemas/tool-run/v0.1", ToolRun),
    "tool_run_v2": ("bridge://schemas/tool-run/v0.2", ToolRunV2),
    "visualization_artifact": ("bridge://schemas/visualization-artifact/v0.1", VisualizationArtifact),
}

def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    output_dirs = [repo / "schemas", repo / "src/bridge/resources/schemas"]
    for output_dir in output_dirs:
        output_dir.mkdir(parents=True, exist_ok=True)
    for filename, (schema_id, model) in MODELS.items():
        schema = model.model_json_schema()
        schema["$id"] = schema_id
        encoded = json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        for output_dir in output_dirs:
            (output_dir / f"{filename}.schema.json").write_text(encoded, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
