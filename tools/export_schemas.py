#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from bridge.toolkit.contracts import (
    ArtifactManifest,
    EligibilityResult,
    KnowledgeHit,
    MeasurementResult,
    MeasurementSpec,
    QCReadinessProfile,
    ToolPackageSpec,
    ToolRequest,
    ToolRun,
    VisualizationArtifact,
)


MODELS = {
    "artifact_manifest": ("bridge://schemas/artifact-manifest/v0.1", ArtifactManifest),
    "eligibility_result": ("bridge://schemas/eligibility-result/v0.1", EligibilityResult),
    "knowledge_hit": ("bridge://schemas/knowledge-hit/v0.1", KnowledgeHit),
    "measurement_result": ("bridge://schemas/measurement-result/v0.1", MeasurementResult),
    "measurement_spec": ("bridge://schemas/measurement-spec/v0.1", MeasurementSpec),
    "qc_readiness_profile": ("bridge://schemas/qc-readiness-profile/v0.1", QCReadinessProfile),
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
