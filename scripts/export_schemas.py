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
    CellStateEvidenceProfileV2,
    CellStateReleaseManifest,
    EligibilityResult,
    FreezeGateSpec,
    KnowledgeHit,
    MarkerProgramCard,
    MeasurementResult,
    MeasurementResultV2,
    MeasurementSpec,
    MeasurementSpecV2,
    QCReadinessProfile,
    QCReadinessProfileV2,
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
from bridge.tool_packages._configurable_contracts import (
    BiologicalUnitAssignmentArtifact,
    BiologicalUnitManifest,
    ProductCase,
    ProductDefinitionCard,
)
from bridge.tool_packages.p0_01_input_qc.io import P001StructuredOutputIndex
from bridge.tool_packages.p0_08_evidence_sufficiency.models import (
    PUBLIC_SCHEMA_MODELS as P0_08_SCHEMA_MODELS,
)
from bridge.tool_packages.p0_04_developmental_compatibility.models import (
    PUBLIC_SCHEMA_MODELS as P0_04_SCHEMA_MODELS,
)
from bridge.tool_packages.p0_09_evidence_compiler.models import (
    PUBLIC_SCHEMA_MODELS as P0_09_SCHEMA_MODELS,
)
from bridge.tool_packages.p0_10_claim_verifier.models import (
    PUBLIC_SCHEMA_MODELS as P0_10_SCHEMA_MODELS,
)


MODELS = {
    "annotation_vocabulary": ("bridge://schemas/annotation-vocabulary/v0.1", AnnotationVocabulary),
    "artifact_manifest": ("bridge://schemas/artifact-manifest/v0.1", ArtifactManifest),
    "benchmark_split_manifest": ("bridge://schemas/benchmark-split-manifest/v0.2", BenchmarkSplitManifest),
    "biological_review_record": ("bridge://schemas/biological-review-record/v0.1", BiologicalReviewRecord),
    "biological_unit_assignment": (
        "bridge://schemas/biological-unit-assignment/v0.1",
        BiologicalUnitAssignmentArtifact,
    ),
    "biological_unit_manifest": (
        "bridge://schemas/biological-unit-manifest/v0.1",
        BiologicalUnitManifest,
    ),
    "cell_state_benchmark_spec": ("bridge://schemas/cell-state-benchmark-spec/v0.2", CellStateBenchmarkSpec),
    "cell_state_evidence_profile": ("bridge://schemas/cell-state-evidence-profile/v0.1", CellStateEvidenceProfile),
    "cell_state_evidence_profile_v2": (
        "bridge://schemas/cell-state-evidence-profile/v0.2",
        CellStateEvidenceProfileV2,
    ),
    "cell_state_release_manifest": ("bridge://schemas/cell-state-release-manifest/v0.1", CellStateReleaseManifest),
    "eligibility_result": ("bridge://schemas/eligibility-result/v0.1", EligibilityResult),
    "freeze_gate_spec": ("bridge://schemas/freeze-gate-spec/v0.2", FreezeGateSpec),
    "knowledge_hit": ("bridge://schemas/knowledge-hit/v0.1", KnowledgeHit),
    "marker_program_card": ("bridge://schemas/marker-program-card/v0.1", MarkerProgramCard),
    "measurement_result": ("bridge://schemas/measurement-result/v0.1", MeasurementResult),
    "measurement_result_v2": (
        "bridge://schemas/measurement-result/v0.2",
        MeasurementResultV2,
    ),
    "measurement_spec": ("bridge://schemas/measurement-spec/v0.1", MeasurementSpec),
    "measurement_spec_v2": (
        "bridge://schemas/measurement-spec/v0.2",
        MeasurementSpecV2,
    ),
    "product_case": ("bridge://schemas/product-case/v0.1", ProductCase),
    "product_definition_card": (
        "bridge://schemas/product-definition-card/v0.1",
        ProductDefinitionCard,
    ),
    "p0_01_structured_output_index": (
        "bridge://schemas/p0-01-structured-output-index/v0.1",
        P001StructuredOutputIndex,
    ),
    "qc_readiness_profile": ("bridge://schemas/qc-readiness-profile/v0.1", QCReadinessProfile),
    "qc_readiness_profile_v2": (
        "bridge://schemas/qc-readiness-profile/v0.2",
        QCReadinessProfileV2,
    ),
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


def _schema_filename(schema_id: str) -> str:
    slug = schema_id.removeprefix("bridge://schemas/").rsplit("/v", 1)[0]
    return slug.replace("-", "_")


for schema_models in (
    P0_04_SCHEMA_MODELS,
    P0_08_SCHEMA_MODELS,
    P0_09_SCHEMA_MODELS,
    P0_10_SCHEMA_MODELS,
):
    for schema_id, model in schema_models.items():
        filename = _schema_filename(schema_id)
        if filename in MODELS:
            raise ValueError(f"duplicate public schema filename: {filename}")
        MODELS[filename] = (schema_id, model)

def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    output_dir = repo / "src/bridge/resources/schemas"
    output_dir.mkdir(parents=True, exist_ok=True)
    for filename, (schema_id, model) in MODELS.items():
        schema = model.model_json_schema()
        schema["$id"] = schema_id
        encoded = json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        (output_dir / f"{filename}.schema.json").write_text(encoded, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
