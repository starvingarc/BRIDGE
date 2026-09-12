from __future__ import annotations

import hashlib
from pathlib import Path

from bridge.tool_packages._structured_runtime import (
    LoadedInputs,
    StructuredInputError,
    canonical_json_bytes,
    failed_v2_run,
    inputs_unchanged,
    load_structured_inputs,
    read_regular_bytes,
    single_object,
)
from bridge.tool_packages.p0_09_evidence_compiler.models import (
    CaseEvidenceGraphManifest,
    ComparisonEvidenceGraphManifest,
    EvidenceGraphQuery,
    EvidenceGraphQueryResult,
)
from bridge.tool_packages.p0_09_evidence_compiler.queries import EvidenceGraphQueries
from bridge.toolkit.contracts import (
    EligibilityResult,
    ExecutionState,
    StructuredInputRef,
    ToolPackageSpecV2,
    ToolRequestV2,
    ToolRunV2,
)

RESULT_SCHEMA_REF = "bridge://schemas/evidence-compiler-result/v0.2"
_QUERY_SCHEMA = "bridge://schemas/evidence-graph-query/v0.1"
_MANIFEST_MODELS = {
    "bridge://schemas/case-evidence-graph-manifest/v0.1": CaseEvidenceGraphManifest,
    "bridge://schemas/comparison-evidence-graph-manifest/v0.1": ComparisonEvidenceGraphManifest,
}
QUERY_ROLES = {"evidence_graph_manifest", "evidence_graph_query"}
GraphManifest = CaseEvidenceGraphManifest | ComparisonEvidenceGraphManifest


def is_query_request(request: ToolRequestV2) -> bool:
    return any(ref.role in QUERY_ROLES for ref in request.object_inputs)


def _model_for(
    ref: StructuredInputRef,
) -> type[EvidenceGraphQuery] | type[GraphManifest] | None:
    if ref.role == "evidence_graph_query" and ref.schema_ref == _QUERY_SCHEMA:
        return EvidenceGraphQuery
    if ref.role == "evidence_graph_manifest":
        return _MANIFEST_MODELS.get(ref.schema_ref)
    return None


def _validate_version(
    ref: StructuredInputRef, value: EvidenceGraphQuery | GraphManifest
) -> None:
    version = (
        value.root.object_version
        if isinstance(value, EvidenceGraphQuery)
        else str(value.graph_version)
    )
    if ref.object_version != version:
        raise StructuredInputError("structured_input_version_mismatch")


def _has_symlink(path: Path) -> bool:
    return any(item.is_symlink() for item in (path, *path.parents))


def _load(
    request: ToolRequestV2, spec: ToolPackageSpecV2
) -> tuple[LoadedInputs | None, list[str]]:
    reasons = []
    roles = [ref.role for ref in request.object_inputs]
    if sorted(roles) != sorted(QUERY_ROLES):
        reasons.append("exact_query_input_roles_required")
    if request.tool_version is not None and request.tool_version != spec.version:
        reasons.append("tool_version_mismatch")
    if request.assets:
        reasons.append("p0_09_expression_assets_forbidden")
    if request.parameters:
        reasons.append("p0_09_parameters_forbidden")
    if request.measurement_spec_ref is not None:
        reasons.append("p0_09_top_level_measurement_spec_forbidden")
    if any(_model_for(ref) is None for ref in request.object_inputs):
        reasons.append("object_input_schema_mismatch")
    if reasons:
        return None, sorted(set(reasons))
    try:
        if _has_symlink(request.output_dir):
            reasons.append("output_path_invalid")
        elif request.output_dir.exists() and not request.output_dir.is_dir():
            reasons.append("output_path_invalid")
        output = request.output_dir.resolve()
        for ref in request.object_inputs:
            if _has_symlink(ref.path):
                reasons.append("structured_input_not_regular_file")
            source = ref.path.resolve()
            if source == output or source.is_relative_to(output):
                reasons.append("output_dir_overlaps_structured_input")
            if (
                ref.role == "evidence_graph_manifest"
                and output.is_relative_to(source.parent)
            ):
                reasons.append("output_dir_overlaps_structured_input")
    except (OSError, RuntimeError):
        reasons.append("output_dir_preflight_failed")
    if reasons:
        return None, sorted(set(reasons))
    return load_structured_inputs(
        request.object_inputs, model_for=_model_for, validate_model=_validate_version
    )


def _query(
    request: ToolRequestV2, loaded: LoadedInputs
) -> tuple[EvidenceGraphQuery, StructuredInputRef, GraphManifest, EvidenceGraphQueryResult]:
    query = single_object(request, loaded, "evidence_graph_query", EvidenceGraphQuery)
    manifest_ref = next(
        ref for ref in request.object_inputs if ref.role == "evidence_graph_manifest"
    )
    manifest = loaded.objects_by_input_id[manifest_ref.input_id]
    if (
        query.root.query_name == "get_case_evidence_subgraph"
        and not isinstance(manifest, CaseEvidenceGraphManifest)
        or query.root.query_name == "compare_evidence_paths"
        and not isinstance(manifest, ComparisonEvidenceGraphManifest)
    ):
        raise StructuredInputError("graph_kind_mismatch")
    # Existing open owns all integrity validation and traversal; no query graph is built.
    queries = EvidenceGraphQueries.open(manifest_ref.path)
    arguments = query.root.model_dump(
        mode="python", exclude={"object_version", "query_name"}
    )
    result = getattr(queries, query.root.query_name)(**arguments)
    if "query_parameter_invalid" in result.reason_codes:
        raise StructuredInputError("query_parameter_invalid")
    if not inputs_unchanged(request.object_inputs):
        raise StructuredInputError("structured_input_modified_during_run")
    # Bind this snapshot to the caller's exact manifest and authoritative sidecars.
    for artifact in (
        manifest.evidence_records,
        manifest.evidence_requirements,
        manifest.reconciliation_records,
        manifest.graph_nodes,
        manifest.graph_edges,
    ):
        raw = read_regular_bytes(manifest_ref.path.parent / artifact.filename)
        if hashlib.sha256(raw).hexdigest() != artifact.sha256:
            raise StructuredInputError("manifest_integrity_failed")
    if (
        result.graph_id != manifest.graph_id
        or result.graph_version != manifest.graph_version
    ):
        raise StructuredInputError("manifest_integrity_failed")
    return query, manifest_ref, manifest, result


def check_query_eligibility(
    request: ToolRequestV2, spec: ToolPackageSpecV2
) -> EligibilityResult:
    loaded, reasons = _load(request, spec)
    if loaded is not None:
        try:
            _query(request, loaded)
        except StructuredInputError as exc:
            reasons.append(exc.reason_code)
        except (ValueError, OSError, RuntimeError):
            reasons.append("manifest_integrity_failed")
    return EligibilityResult(
        tool_id=request.tool_id,
        eligible=not reasons,
        reason_codes=sorted(set(reasons)),
    )


def run_query(request: ToolRequestV2, spec: ToolPackageSpecV2) -> ToolRunV2:
    loaded, reasons = _load(request, spec)
    if loaded is not None:
        try:
            query, manifest_ref, manifest, result = _query(request, loaded)
        except StructuredInputError as exc:
            reasons.append(exc.reason_code)
        except (ValueError, OSError, RuntimeError):
            reasons.append("manifest_integrity_failed")
    if reasons or loaded is None:
        return failed_v2_run(
            request,
            spec,
            reasons,
            result_schema_ref=RESULT_SCHEMA_REF,
            fingerprint_input_key="query_inputs",
        )
    input_hash = hashlib.sha256(
        canonical_json_bytes(
            {
                "operation": "evidence_graph_query",
                "tool_id": spec.tool_id,
                "tool_version": spec.version,
                "environment_spec_id": spec.environment_spec_id,
                "manifest_sha256": manifest_ref.sha256,
                "manifest_schema_ref": manifest_ref.schema_ref,
                "query": query.model_dump(mode="json"),
            }
        )
    ).hexdigest()
    # The canonical ToolRun is the receipt. A read-only query creates no output directory.
    return ToolRunV2(
        run_id=f"run-query-{input_hash[:16]}",
        request=request,
        implementation_state=spec.implementation_state,
        execution_state=ExecutionState.SUCCEEDED,
        tool_version=spec.version,
        environment_spec_id=spec.environment_spec_id,
        input_hash=input_hash,
        created_at=manifest.created_at,
        measurements=[],
        artifacts=[],
        visualizations=[],
        result_schema_ref=RESULT_SCHEMA_REF,
        result=result.model_dump(mode="json"),
        reason_codes=result.reason_codes,
        warnings=[],
    )
