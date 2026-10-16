#!/usr/bin/env python3
from __future__ import annotations

from bridge.tool_packages.p0_03_target_regional.saved_roles import PUBLIC_SCHEMA_MODELS as SAVED_ROLE_SCHEMAS

import argparse
import hashlib
import json
from pathlib import Path

from bridge.toolkit.schemas import SCHEMA_REFS

from bridge.tool_packages.p0_02_cell_state.expression_figures import PUBLIC_SCHEMA_MODELS as EXPRESSION_SCHEMA_MODELS
from bridge.tool_packages.p0_02_cell_state.scientific_review import CellStateDevelopmentReview, CellStateDevelopmentReviewV11
from bridge.tool_packages.p0_02_cell_state.celltypist_runtime import OODCalibration
from bridge.tool_packages.p0_02_cell_state.candidate_runtime import CandidateRuntimeBinding, CellStateCandidateProfile
from bridge.toolkit.contracts import (
    AnnotationVocabulary,
    ArtifactManifest,
    BenchmarkSplitManifest,
    BiologicalReviewRecord,
    CellStateBenchmarkSpec,
    CellStateEvidenceProfile,
    CellStateEvidenceProfileV2,
    CellStateEvidenceProfileV3,
    CellStateReleaseManifest,
    EligibilityResult,
    FreezeGateSpec,
    KnowledgeHit,
    MarkerProgramCard,
    MeasurementResult,
    MeasurementResultV2,
    MeasurementSpec,
    MeasurementSpecV2,
    MeasurementSpecV3,
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
    BiologicalUnitAttestationReceipt,
    ProductCase,
    ProductDefinitionCard,
)
from bridge.tool_packages._input_contracts import ToolInputContract
from bridge.tool_packages.p0_01_input_qc.io import (
    P001_VISUALIZATION_SCHEMA_MODELS,
    P001StructuredOutputIndex,
    P001StructuredOutputIndexV2,
)
from bridge.tool_packages.p0_02_cell_state.hierarchical_composition import (
    PUBLIC_SCHEMA_MODELS as P0_02_HIERARCHY_SCHEMA_MODELS,
)
from bridge.tool_packages.p0_02_cell_state.visualization_data import (
    PUBLIC_SCHEMA_MODELS as P0_02_SCHEMA_MODELS,
)
from bridge.tool_packages.p0_03_target_regional.models import (
    PUBLIC_SCHEMA_MODELS as P0_03_SCHEMA_MODELS,
)
from bridge.tool_packages.p0_03_target_regional.exploratory_models import (
    PUBLIC_EXPLORATORY_SCHEMA_MODELS as P0_03_EXPLORATORY_SCHEMA_MODELS,
)
from bridge.tool_packages.p0_03_target_regional.visualization_data import (
    PUBLIC_VISUALIZATION_SCHEMA_MODELS as P0_03_VISUALIZATION_SCHEMA_MODELS,
)
from bridge.tool_packages.p0_07_product_comparison_stability.models import (
    PUBLIC_SCHEMA_MODELS as P0_07_SCHEMA_MODELS,
)
from bridge.tool_packages.p0_07_product_comparison_stability.visualization_data import (
    PUBLIC_VISUALIZATION_SCHEMA_MODELS as P0_07_VISUALIZATION_SCHEMA_MODELS,
)
from bridge.tool_packages.p0_08_evidence_sufficiency.models import (
    PUBLIC_SCHEMA_MODELS as P0_08_SCHEMA_MODELS,
)
from bridge.tool_packages.p0_08_evidence_sufficiency.visualization_data import (
    PUBLIC_VISUALIZATION_SCHEMA_MODELS as P0_08_VISUALIZATION_SCHEMA_MODELS,
)
from bridge.tool_packages.p0_04_developmental_compatibility.models import (
    PUBLIC_SCHEMA_MODELS as P0_04_SCHEMA_MODELS,
)
from bridge.tool_packages.p0_04_developmental_compatibility.native_models import PUBLIC_SCHEMA_MODELS as P004_NATIVE_SCHEMAS
from bridge.tool_packages.p0_05_off_target_control.native_models import PUBLIC_SCHEMA_MODELS as P005_NATIVE_SCHEMAS
from bridge.tool_packages.p0_04_developmental_compatibility.visualization_data import (
    PUBLIC_VISUALIZATION_SCHEMA_MODELS as P0_04_VISUALIZATION_SCHEMA_MODELS,
)
from bridge.tool_packages.p0_05_off_target_control.models import (
    PUBLIC_SCHEMA_MODELS as P0_05_SCHEMA_MODELS,
)
from bridge.tool_packages.p0_05_off_target_control.visualization_data import (
    PUBLIC_VISUALIZATION_SCHEMA_MODELS as P0_05_VISUALIZATION_SCHEMA_MODELS,
)
from bridge.tool_packages.p0_06_proliferation_stress_response.exploratory_models import (
    PUBLIC_EXPLORATORY_SCHEMA_MODELS,
)
from bridge.tool_packages.p0_06_proliferation_stress_response.candidate_programs import (
    PUBLIC_SCHEMA_MODELS as P006_PROGRAM_SCHEMA_MODELS,
)
from bridge.tool_packages.p0_06_proliferation_stress_response.models import (
    PUBLIC_SCHEMA_MODELS as P0_06_SCHEMA_MODELS,
)
from bridge.tool_packages.p0_06_proliferation_stress_response.method_models import (
    PUBLIC_METHOD_SCHEMA_MODELS as P0_06_METHOD_SCHEMA_MODELS,
)
from bridge.tool_packages.p0_06_proliferation_stress_response.visualization_data import (
    PUBLIC_VISUALIZATION_SCHEMA_MODELS as P0_06_VISUALIZATION_SCHEMA_MODELS,
)
from bridge.tool_packages.p0_09_evidence_compiler.models import (
    PUBLIC_SCHEMA_MODELS as P0_09_SCHEMA_MODELS,
)
from bridge.tool_packages.p0_09_evidence_compiler.visualization_data import (
    PUBLIC_VISUALIZATION_SCHEMA_MODELS as P0_09_VISUALIZATION_SCHEMA_MODELS,
)
from bridge.tool_packages.p0_10_claim_verifier.models import (
    PUBLIC_SCHEMA_MODELS as P0_10_SCHEMA_MODELS,
)
from bridge.tool_packages.p0_10_claim_verifier.visualization_data import (
    PUBLIC_VISUALIZATION_SCHEMA_MODELS as P0_10_VISUALIZATION_SCHEMA_MODELS,
)
from bridge.tool_packages.p0_12_graft_assessment.run_models import (
    PUBLIC_SCHEMA_MODELS as P0_12_SCHEMA_MODELS,
)
from bridge.tool_packages.p0_12_graft_assessment.visualization_data import (
    PUBLIC_VISUALIZATION_SCHEMA_MODELS as P0_12_VISUALIZATION_SCHEMA_MODELS,
)
from bridge.tool_packages.p0_11_public_safe_export.models import (
    PUBLIC_SCHEMA_MODELS as P0_11_SCHEMA_MODELS,
)
from bridge.tool_packages.p0_11_public_safe_export.visualization_data import (
    PUBLIC_VISUALIZATION_SCHEMA_MODELS as P0_11_VISUALIZATION_SCHEMA_MODELS,
)
from bridge.toolkit.integration import AgentIntegrationProfile
from bridge.toolkit.visualization import (
    FigureRegistrySnapshot,
    VisualizationArtifactV2,
)


from bridge.tool_packages.p0_10_claim_verifier.research import (
    ResearchClaimVerificationResult, ResearchStatementRegistry, ResearchAnalysisSnapshot,
    ResearchAnalysisSnapshotV03, ResearchReportContext, ResearchAnalysisSnapshotV04, ResearchReportContextV04,
    ResearchAnalysisSnapshotV05, ResearchReportContextV05,
)

MODELS = {
    "cell_state_development_review_v1_1": ("bridge://schemas/cell-state-development-review/v1.1", CellStateDevelopmentReviewV11),
    "cell_state_development_review": ("bridge://schemas/cell-state-development-review/v1.0", CellStateDevelopmentReview),
    "cell_state_ood_calibration": ("bridge://schemas/cell-state-ood-calibration/v1.0", OODCalibration),
    "cell_state_candidate_runtime": ("bridge://schemas/cell-state-candidate-runtime/v1.0", CandidateRuntimeBinding),
    "cell_state_candidate_profile": ("bridge://schemas/cell-state-candidate-profile/v1.0", CellStateCandidateProfile),
    "agent_integration_profile": (
        "bridge://schemas/agent-integration-profile/v0.1",
        AgentIntegrationProfile,
    ),
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
    "biological_unit_attestation_receipt": (
        "bridge://schemas/biological-unit-attestation-receipt/v0.1",
        BiologicalUnitAttestationReceipt,
    ),
    "cell_state_benchmark_spec": ("bridge://schemas/cell-state-benchmark-spec/v0.2", CellStateBenchmarkSpec),
    "cell_state_evidence_profile": ("bridge://schemas/cell-state-evidence-profile/v0.1", CellStateEvidenceProfile),
    "cell_state_evidence_profile_v2": (
        "bridge://schemas/cell-state-evidence-profile/v0.2",
        CellStateEvidenceProfileV2,
    ),
    "cell_state_evidence_profile_v3": (
        "bridge://schemas/cell-state-evidence-profile/v0.3",
        CellStateEvidenceProfileV3,
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
    "measurement_spec_v3": ("bridge://schemas/measurement-spec/v0.3", MeasurementSpecV3),
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
    "p0_01_structured_output_index_v2": (
        "bridge://schemas/p0-01-structured-output-index/v0.2",
        P001StructuredOutputIndexV2,
    ),
    "qc_readiness_profile": ("bridge://schemas/qc-readiness-profile/v0.1", QCReadinessProfile),
    "qc_readiness_profile_v2": (
        "bridge://schemas/qc-readiness-profile/v0.2",
        QCReadinessProfileV2,
    ),
    "research_claim_verification_result_v2": ("bridge://schemas/research-claim-verification-result/v0.2", ResearchClaimVerificationResult),
    "research_statement_registry_v2": ("bridge://schemas/research-statement-registry/v0.2", ResearchStatementRegistry),
    "research_analysis_snapshot_v2": ("bridge://schemas/research-analysis-snapshot/v0.2", ResearchAnalysisSnapshot),
    "research_analysis_snapshot_v3": ("bridge://schemas/research-analysis-snapshot/v0.3", ResearchAnalysisSnapshotV03),
    "research_report_context_v3": ("bridge://schemas/research-report-context/v0.3", ResearchReportContext),
    "research_report_context_v4": ("bridge://schemas/research-report-context/v0.4", ResearchReportContextV04),
    "research_report_context_v5": ("bridge://schemas/research-report-context/v0.5", ResearchReportContextV05),
    "research_analysis_snapshot_v4": ("bridge://schemas/research-analysis-snapshot/v0.4", ResearchAnalysisSnapshotV04),
    "research_analysis_snapshot_v5": ("bridge://schemas/research-analysis-snapshot/v0.5", ResearchAnalysisSnapshotV05),
    "reference_manifest": ("bridge://schemas/reference-manifest/v0.1", ReferenceManifest),
    "reference_profile": ("bridge://schemas/reference-profile/v0.1", ReferenceProfile),
    "structured_input_ref": ("bridge://schemas/structured-input-ref/v0.1", StructuredInputRef),
    "tool_input_contract": (
        "bridge://schemas/tool-input-contract/v0.1",
        ToolInputContract,
    ),
    "tool_package_spec": ("bridge://schemas/tool-package-spec/v0.1", ToolPackageSpec),
    "tool_package_spec_v2": ("bridge://schemas/tool-package-spec/v0.2", ToolPackageSpecV2),
    "tool_request": ("bridge://schemas/tool-request/v0.1", ToolRequest),
    "tool_request_v2": ("bridge://schemas/tool-request/v0.2", ToolRequestV2),
    "tool_run": ("bridge://schemas/tool-run/v0.1", ToolRun),
    "tool_run_v2": ("bridge://schemas/tool-run/v0.2", ToolRunV2),
    "visualization_artifact": ("bridge://schemas/visualization-artifact/v0.1", VisualizationArtifact),
    "visualization_artifact_v2": (
        "bridge://schemas/visualization-artifact/v0.2",
        VisualizationArtifactV2,
    ),
    "figure_registry": ("bridge://schemas/figure-registry/v0.1", FigureRegistrySnapshot),
}


def _schema_filename(schema_id: str) -> str:
    slug, version = schema_id.removeprefix("bridge://schemas/").rsplit("/v", 1)
    stem = slug.replace("-", "_")
    if version == "0.1":
        return stem
    major, minor = version.split(".", 1)
    suffix = minor if major == "0" else major
    return f"{stem}_v{suffix}"


for schema_models in (
    P001_VISUALIZATION_SCHEMA_MODELS,
    P0_02_HIERARCHY_SCHEMA_MODELS,
    P0_02_SCHEMA_MODELS,
    EXPRESSION_SCHEMA_MODELS,
    P0_03_SCHEMA_MODELS,
    SAVED_ROLE_SCHEMAS,
    P0_03_EXPLORATORY_SCHEMA_MODELS,
    P0_03_VISUALIZATION_SCHEMA_MODELS,
    P0_04_SCHEMA_MODELS,
    P004_NATIVE_SCHEMAS,
    P005_NATIVE_SCHEMAS,
    P0_04_VISUALIZATION_SCHEMA_MODELS,
    P0_05_SCHEMA_MODELS,
    P0_05_VISUALIZATION_SCHEMA_MODELS,
    P0_06_SCHEMA_MODELS,
    P0_06_METHOD_SCHEMA_MODELS,
    PUBLIC_EXPLORATORY_SCHEMA_MODELS,
    P006_PROGRAM_SCHEMA_MODELS,
    P0_06_VISUALIZATION_SCHEMA_MODELS,
    P0_07_SCHEMA_MODELS,
    P0_07_VISUALIZATION_SCHEMA_MODELS,
    P0_08_SCHEMA_MODELS,
    P0_08_VISUALIZATION_SCHEMA_MODELS,
    P0_09_SCHEMA_MODELS,
    P0_09_VISUALIZATION_SCHEMA_MODELS,
    P0_10_SCHEMA_MODELS,
    P0_10_VISUALIZATION_SCHEMA_MODELS,
    P0_11_SCHEMA_MODELS,
    P0_11_VISUALIZATION_SCHEMA_MODELS,
    P0_12_SCHEMA_MODELS,
    P0_12_VISUALIZATION_SCHEMA_MODELS,
):
    for schema_id, model in schema_models.items():
        filename = _schema_filename(schema_id)
        if filename in MODELS:
            raise ValueError(f"duplicate public schema filename: {filename}")
        MODELS[filename] = (schema_id, model)

# Existing published snapshots stay unchanged. New versions reuse these exact
# schema fragments instead of copying their definitions and constraints.
SCHEMA_LINKS = {
    "bridge://schemas/research-report-context/v0.4": ("bridge://schemas/research-report-context/v0.3",),
    "bridge://schemas/research-report-context/v0.5": ("bridge://schemas/research-report-context/v0.4",),
    "bridge://schemas/research-analysis-snapshot/v0.4": ("bridge://schemas/research-analysis-snapshot/v0.3",),
    "bridge://schemas/research-analysis-snapshot/v0.5": ("bridge://schemas/research-analysis-snapshot/v0.4",),
    "bridge://schemas/saved-target-role-profile/v0.1": ("bridge://schemas/native-cell-state-context-profile/v0.2",),
    "bridge://schemas/target-regional-result/v0.2": ("bridge://schemas/target-regional-result/v0.1", "bridge://schemas/saved-target-role-profile/v0.1"),
    "bridge://schemas/p0-02-visualization-artifact-set/v0.2": ("bridge://schemas/visualization-artifact/v0.2",),
    "bridge://schemas/native-cell-state-context-profile/v0.2": (
        "bridge://schemas/native-cell-state-context-profile/v0.1",
        "bridge://schemas/hierarchical-cell-state-composition-data/v0.1",
    ),
    "bridge://schemas/off-target-hard-count-profile/v0.3": (
        "bridge://schemas/off-target-hard-count-profile/v0.2",
    ),
    "bridge://schemas/off-target-control-result/v0.4": (
        "bridge://schemas/off-target-control-profile/v0.2",
        "bridge://schemas/off-target-hard-count-profile/v0.3",
        "bridge://schemas/native-cell-state-context-profile/v0.2",
    ),
}


def _local_definitions(value):
    if isinstance(value, dict):
        ref = value.get("$ref", "")
        if ref.startswith("#/$defs/"):
            yield ref.removeprefix("#/$defs/")
        for item in value.values():
            yield from _local_definitions(item)
    elif isinstance(value, list):
        for item in value:
            yield from _local_definitions(item)


def _compact_schema(schema, sources):
    """Reuse equal subschemas only when their referenced definitions also agree."""
    candidates = {}
    def fingerprint(value):
        return json.dumps(value, sort_keys=True)

    for uri, source in sources.items():
        parts = [("", {k: v for k, v in source.items() if k not in {"$id", "$defs"}})]
        for group in ("$defs", "properties", "allOf"):
            values = source.get(group, {})
            items = enumerate(values) if isinstance(values, list) else values.items()
            parts.extend((f"/{group}/{key}", value) for key, value in items)
        for pointer, value in parts:
            if len(json.dumps(value, indent=2).splitlines()) > 4:
                candidates.setdefault(fingerprint(value), []).append((uri + ("#" + pointer if pointer else ""), source))

    def compatible(value, source):
        pending = list(_local_definitions(value))
        seen = set()
        while pending:
            name = pending.pop()
            if name in seen:
                continue
            seen.add(name)
            definition = schema.get("$defs", {}).get(name)
            if definition is None or definition != source.get("$defs", {}).get(name):
                return False
            pending.extend(_local_definitions(definition))
        return True

    def compact(value):
        if isinstance(value, dict):
            for ref, source in candidates.get(fingerprint(value), []):
                if compatible(value, source):
                    return {"$ref": ref}
            return {key: compact(item) for key, item in value.items()}
        if isinstance(value, list):
            return [compact(item) for item in value]
        return value

    result = compact(schema)
    definitions = result.pop("$defs", {})
    pending = list(_local_definitions(result))
    kept = {}
    while pending:
        name = pending.pop()
        if name not in kept:
            kept[name] = definitions[name]
            pending.extend(_local_definitions(definitions[name]))
    if kept:
        result["$defs"] = kept
    return result


# Published legacy contracts without a current Python producer. Their exact
# bytes remain immutable and registered; these are not blanket version skips.
HISTORICAL_SNAPSHOTS = {
    "developmental_compatibility_result.schema.json":
        "dc555a83aeeaee8fa928ed1709dbdb38449b35a1a0f76a7a5991baaa2bbc24ab",
    "target_regional_evidence_result.schema.json":
        "637043c1601044f002a245661150af7eab04d21c6312399188ff10814202983b",
}


def render_schemas() -> dict[str, bytes]:
    """One deterministic renderer shared by writing and read-only checking."""
    schemas = {schema_id: {**model.model_json_schema(), "$id": schema_id}
               for schema_id, model in MODELS.values()}
    if len(schemas) != len(MODELS):
        raise ValueError("duplicate generated schema ID")
    rendered = {}
    for filename, (schema_id, _) in MODELS.items():
        schema = schemas[schema_id]
        if schema_id in SCHEMA_LINKS:
            schema = _compact_schema(schema, {ref: schemas[ref] for ref in SCHEMA_LINKS[schema_id]})
        encoded = json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        rendered[f"{filename}.schema.json"] = encoded.encode("utf-8")
    return rendered


def check_schemas(output_dir: Path) -> list[str]:
    """Check registry, producers and bytes in both directions; never write."""
    rendered = render_schemas()
    registered = set(SCHEMA_REFS.values())
    actual = {path.name for path in output_dir.glob("*.json")}
    historical = set(HISTORICAL_SNAPSHOTS)
    problems = []
    if len(registered) != len(SCHEMA_REFS):
        problems.append("multiple schema IDs register the same file")
    for stem, (schema_id, _) in MODELS.items():
        filename = f"{stem}.schema.json"
        if SCHEMA_REFS.get(schema_id) != filename:
            problems.append(f"generated schema ID/filename not registered: {schema_id}: {filename}")
    for filename in sorted(registered - actual):
        problems.append(f"registered schema file missing: {filename}")
    for filename in sorted(actual - registered):
        problems.append(f"unregistered schema file: {filename}")
    for filename in sorted(registered - rendered.keys() - historical):
        problems.append(f"registered schema has no producer or historical pin: {filename}")
    for filename in sorted(historical - registered):
        problems.append(f"historical pin is not registered: {filename}")
    for filename in sorted(historical & rendered.keys()):
        problems.append(f"historical schema also has a model producer: {filename}")
    for filename in sorted(registered & actual):
        path = output_dir / filename
        try:
            content = path.read_bytes()
        except OSError as exc:
            problems.append(f"cannot read schema file: {filename}: {exc.strerror}")
            continue
        if filename in rendered and content != rendered[filename]:
            problems.append(f"generated schema bytes differ: {filename}")
        if filename in historical and hashlib.sha256(content).hexdigest() != HISTORICAL_SNAPSHOTS[filename]:
            problems.append(f"historical schema bytes differ: {filename}")
        try:
            schema_id = json.loads(content).get("$id")
        except (ValueError, AttributeError):
            problems.append(f"invalid schema JSON object: {filename}")
            continue
        if not isinstance(schema_id, str) or SCHEMA_REFS.get(schema_id) != filename:
            problems.append(f"schema file ID does not match registry: {filename}")
    return sorted(problems)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Generate or check packaged JSON schemas.")
    parser.add_argument("--check", action="store_true",
                        help="compare generated bytes and registrations without writing")
    parser.add_argument("--output-dir", type=Path,
                        default=Path(__file__).resolve().parents[1] / "src/bridge/resources/schemas",
                        help="schema directory (defaults to packaged resources)")
    args = parser.parse_args(argv)
    if args.check:
        problems = check_schemas(args.output_dir)
        if problems:
            print("\n".join(problems))
            return 1
        print(f"Schema check passed: {len(MODELS)} generated, "
              f"{len(HISTORICAL_SNAPSHOTS)} pinned historical snapshots")
        return 0
    rendered = render_schemas()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for filename, content in rendered.items():
        (args.output_dir / filename).write_bytes(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
