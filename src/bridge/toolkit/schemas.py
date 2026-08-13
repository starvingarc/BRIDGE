from __future__ import annotations

import json
from importlib.resources import files


SCHEMA_REFS = {
    "bridge://schemas/annotation-vocabulary/v0.1": "annotation_vocabulary.schema.json",
    "bridge://schemas/artifact-manifest/v0.1": "artifact_manifest.schema.json",
    "bridge://schemas/benchmark-split-manifest/v0.2": "benchmark_split_manifest.schema.json",
    "bridge://schemas/biological-review-record/v0.1": "biological_review_record.schema.json",
    "bridge://schemas/cell-state-benchmark-spec/v0.2": "cell_state_benchmark_spec.schema.json",
    "bridge://schemas/cell-state-evidence-profile/v0.1": "cell_state_evidence_profile.schema.json",
    "bridge://schemas/cell-state-release-manifest/v0.1": "cell_state_release_manifest.schema.json",
    "bridge://schemas/eligibility-result/v0.1": "eligibility_result.schema.json",
    "bridge://schemas/freeze-gate-spec/v0.2": "freeze_gate_spec.schema.json",
    "bridge://schemas/knowledge-hit/v0.1": "knowledge_hit.schema.json",
    "bridge://schemas/marker-program-card/v0.1": "marker_program_card.schema.json",
    "bridge://schemas/measurement-result/v0.1": "measurement_result.schema.json",
    "bridge://schemas/measurement-spec/v0.1": "measurement_spec.schema.json",
    "bridge://schemas/qc-readiness-profile/v0.1": "qc_readiness_profile.schema.json",
    "bridge://schemas/reference-manifest/v0.1": "reference_manifest.schema.json",
    "bridge://schemas/reference-profile/v0.1": "reference_profile.schema.json",
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
