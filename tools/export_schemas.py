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
    ToolPackageSpec,
    ToolRequest,
    ToolRun,
    VisualizationArtifact,
)


MODELS = {
    "annotation_vocabulary": ("bridge://schemas/annotation-vocabulary/v0.1", AnnotationVocabulary),
    "artifact_manifest": ("bridge://schemas/artifact-manifest/v0.1", ArtifactManifest),
    "benchmark_split_manifest": ("bridge://schemas/benchmark-split-manifest/v0.2", BenchmarkSplitManifest),
    "biological_review_record": ("bridge://schemas/biological-review-record/v0.1", BiologicalReviewRecord),
    "cell_state_benchmark_spec": ("bridge://schemas/cell-state-benchmark-spec/v0.2", CellStateBenchmarkSpec),
    "cell_state_evidence_profile": ("bridge://schemas/cell-state-evidence-profile/v0.1", CellStateEvidenceProfile),
    "cell_state_release_manifest": ("bridge://schemas/cell-state-release-manifest/v0.1", CellStateReleaseManifest),
    "eligibility_result": ("bridge://schemas/eligibility-result/v0.1", EligibilityResult),
    "freeze_gate_spec": ("bridge://schemas/freeze-gate-spec/v0.2", FreezeGateSpec),
    "knowledge_hit": ("bridge://schemas/knowledge-hit/v0.1", KnowledgeHit),
    "marker_program_card": ("bridge://schemas/marker-program-card/v0.1", MarkerProgramCard),
    "measurement_result": ("bridge://schemas/measurement-result/v0.1", MeasurementResult),
    "measurement_spec": ("bridge://schemas/measurement-spec/v0.1", MeasurementSpec),
    "qc_readiness_profile": ("bridge://schemas/qc-readiness-profile/v0.1", QCReadinessProfile),
    "reference_manifest": ("bridge://schemas/reference-manifest/v0.1", ReferenceManifest),
    "reference_profile": ("bridge://schemas/reference-profile/v0.1", ReferenceProfile),
    "tool_package_spec": ("bridge://schemas/tool-package-spec/v0.1", ToolPackageSpec),
    "tool_request": ("bridge://schemas/tool-request/v0.1", ToolRequest),
    "tool_run": ("bridge://schemas/tool-run/v0.1", ToolRun),
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
