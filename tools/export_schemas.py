#!/usr/bin/env python3
from __future__ import annotations

import hashlib
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

LEGACY_SCHEMAS = {
    "benchmark_split_manifest_v0.1.schema.json": (
        "bridge://schemas/benchmark-split-manifest/v0.1",
        "c0ab446bb30e5c74caf3f2a0c5483794c95f175a12c0722413564ab2416c11db",
    ),
    "cell_state_benchmark_spec_v0.1.schema.json": (
        "bridge://schemas/cell-state-benchmark-spec/v0.1",
        "84ff10b4fa9955236be07d47a231f2edc799922dd3332a47e14e78e5425e170f",
    ),
    "freeze_gate_spec_v0.1.schema.json": (
        "bridge://schemas/freeze-gate-spec/v0.1",
        "d3f186375f5eacaa2d433523d74d1d8e1467cba8578d51c54755c78569ed1b46",
    ),
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
    for output_dir in output_dirs:
        for filename, (schema_id, expected_sha256) in LEGACY_SCHEMAS.items():
            path = output_dir / filename
            if (
                not path.is_file()
                or json.loads(path.read_text(encoding="utf-8")).get("$id") != schema_id
                or hashlib.sha256(path.read_bytes()).hexdigest() != expected_sha256
            ):
                raise RuntimeError(f"Legacy schema is missing or invalid: {filename}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
