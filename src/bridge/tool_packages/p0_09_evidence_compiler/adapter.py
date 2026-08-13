from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
from typing import Any, Mapping
from uuid import uuid4

from pydantic import ValidationError

from bridge.tool_packages.p0_08_evidence_sufficiency.models import EvidenceSufficiencyProfile
from bridge.tool_packages.p0_09_evidence_compiler.compiler import (
    CompilationInvariantError,
    canonical_input_hash,
    canonical_json_bytes,
    compile_evidence_graph,
    normalize_identity_payload,
    validate_prior_history,
)
from bridge.tool_packages.p0_09_evidence_compiler.graph import (
    cytoscape_projection,
    object_counts,
    read_parquet_rows,
    validate_graph_rows,
    write_parquet,
)
from bridge.tool_packages.p0_09_evidence_compiler.models import (
    CANONICALIZATION_ID,
    CaseEvidenceGraphManifest,
    ClaimRegistry,
    ComparisonEvidenceGraphManifest,
    EvidenceCompilationBundle,
    EvidenceCompilerRunResult,
    EvidenceFamilyRegistry,
    ExternalCaseEvidenceRef,
    GraphArtifactRef,
    GraphKind,
    ReconciliationSpecRegistry,
    contains_unsafe_reference,
)
from bridge.toolkit.contracts import (
    ArtifactManifest,
    EligibilityResult,
    ExecutionState,
    FrozenModel,
    StructuredInputRef,
    ToolPackageSpecV2,
    ToolRequest,
    ToolRequestV2,
    ToolRunV2,
)


RESULT_SCHEMA_REF = "bridge://schemas/evidence-compiler-run-result/v0.1"
ROLE_SCHEMAS = {
    "compilation_bundle": "bridge://schemas/evidence-compilation-bundle/v0.1",
    "evidence_sufficiency_profile": "bridge://schemas/evidence-sufficiency-profile/v0.1",
    "evidence_family_registry": "bridge://schemas/evidence-family-registry/v0.1",
    "claim_registry": "bridge://schemas/claim-registry/v0.1",
    "reconciliation_spec_registry": "bridge://schemas/reconciliation-spec-registry/v0.1",
}
ROLE_MODELS: dict[str, type[FrozenModel]] = {
    "compilation_bundle": EvidenceCompilationBundle,
    "evidence_sufficiency_profile": EvidenceSufficiencyProfile,
    "evidence_family_registry": EvidenceFamilyRegistry,
    "claim_registry": ClaimRegistry,
    "reconciliation_spec_registry": ReconciliationSpecRegistry,
}
LEGACY_KEYS = {
    "_".join(("integrated", "score")),
    "_".join(("evidence", "confidence", "score")),
    "_".join(("potency", "proxy")),
    "_".join(("overall", "score")),
    "_".join(("overall", "rank")),
    "_".join(("product", "pass")),
    "_".join(("negative", "pass")),
}
EXPECTED_ARTIFACTS = {
    "evidence_records.json",
    "evidence_requirements.json",
    "reconciliation_records.json",
    "graph_nodes.parquet",
    "graph_edges.parquet",
    "cytoscape_elements.json",
    "rejected_records.json",
    "evidence_compiler_run_result.json",
    "artifact_manifest.json",
}
ARTIFACT_FILENAME = re.compile(r"^[a-z0-9_]+(?:\.[a-z0-9]+)+$")


class StructuredInputError(ValueError):
    def __init__(self, reason_code: str, detail: str = "") -> None:
        super().__init__(detail or reason_code)
        self.reason_code = reason_code
        self.detail = detail


@dataclass(frozen=True)
class LoadedInputs:
    objects_by_input_id: dict[str, FrozenModel]
    bytes_by_input_id: dict[str, bytes]


@dataclass(frozen=True)
class EvidenceCompilerAdapter:
    def check_eligibility(
        self, request: ToolRequestV2, spec: ToolPackageSpecV2
    ) -> EligibilityResult:
        if not isinstance(request, ToolRequestV2):
            tool_id = request.tool_id if isinstance(request, ToolRequest) else "P0-09"
            return EligibilityResult(
                tool_id=tool_id,
                eligible=False,
                reason_codes=["tool_request_v2_required"],
            )
        reasons = self._envelope_reasons(request, spec)
        loaded, loading_reasons = _load_structured_inputs(request.object_inputs)
        reasons.extend(loading_reasons)
        if loaded is not None:
            reasons.extend(_binding_reasons(request, loaded))
        reason_codes = sorted(set(reasons))
        return EligibilityResult(
            tool_id=request.tool_id,
            eligible=not reason_codes,
            reason_codes=reason_codes,
        )

    def run(self, request: ToolRequestV2, spec: ToolPackageSpecV2) -> ToolRunV2:
        eligibility = self.check_eligibility(request, spec)
        if not eligibility.eligible:
            return _failed_run(request, spec, eligibility.reason_codes)
        loaded, reasons = _load_structured_inputs(request.object_inputs)
        if loaded is None or reasons:
            return _failed_run(request, spec, reasons)
        bundle = _single_object(request, loaded, "compilation_bundle", EvidenceCompilationBundle)
        family_registry = _single_object(
            request, loaded, "evidence_family_registry", EvidenceFamilyRegistry
        )
        claim_registry = _single_object(request, loaded, "claim_registry", ClaimRegistry)
        reconciliation_registry = _single_object(
            request,
            loaded,
            "reconciliation_spec_registry",
            ReconciliationSpecRegistry,
        )
        profiles = {
            ref.input_id: loaded.objects_by_input_id[ref.input_id]
            for ref in request.object_inputs
            if ref.role == "evidence_sufficiency_profile"
        }
        if not all(isinstance(item, EvidenceSufficiencyProfile) for item in profiles.values()):
            return _failed_run(request, spec, ["structured_input_schema_invalid"])
        typed_profiles: dict[str, EvidenceSufficiencyProfile] = {
            key: value for key, value in profiles.items() if isinstance(value, EvidenceSufficiencyProfile)
        }
        input_hash = canonical_input_hash(
            request=request,
            spec=spec,
            objects_by_input_id=loaded.objects_by_input_id,
        )
        run_id = f"run-{input_hash[:16]}"
        try:
            compiled = compile_evidence_graph(
                request=request,
                spec=spec,
                bundle=bundle,
                profiles_by_input_id=typed_profiles,
                family_registry=family_registry,
                claim_registry=claim_registry,
                reconciliation_registry=reconciliation_registry,
            )
        except CompilationInvariantError as exc:
            return _failed_run(request, spec, [exc.reason_code], input_hash=input_hash)
        except ValueError as exc:
            reason = str(exc).split(":", 1)[0]
            if reason not in {
                "graph_invariant_failed",
                "parquet_projection_failed",
                "artifact_checksum_verification_failed",
            }:
                reason = "graph_invariant_failed"
            return _failed_run(request, spec, [reason], input_hash=input_hash)

        output_root = request.output_dir.resolve()
        output_root.mkdir(parents=True, exist_ok=True)
        staging = output_root / f".{run_id}.staging-{uuid4().hex}"
        staging.mkdir(mode=0o700)
        try:
            result, artifact_specs = _write_bundle(
                staging=staging,
                request=request,
                spec=spec,
                bundle=bundle,
                compiled=compiled,
                run_id=run_id,
                objects_by_input_id=loaded.objects_by_input_id,
            )
            if not _inputs_unchanged(request.object_inputs):
                shutil.rmtree(staging)
                return _failed_run(
                    request,
                    spec,
                    ["structured_input_modified_during_run"],
                    input_hash=input_hash,
                )
            final = output_root / run_id
            if final.exists():
                if not _bundles_match(staging, final):
                    shutil.rmtree(staging)
                    return _failed_run(
                        request,
                        spec,
                        ["existing_run_bundle_hash_mismatch"],
                        input_hash=input_hash,
                    )
                shutil.rmtree(staging)
            else:
                os.replace(staging, final)
        except Exception as exc:
            if staging.exists():
                shutil.rmtree(staging)
            reason = (
                str(exc).split(":", 1)[0]
                if str(exc).split(":", 1)[0]
                in {
                    "graph_invariant_failed",
                    "parquet_projection_failed",
                    "artifact_checksum_verification_failed",
                }
                else "artifact_checksum_verification_failed"
            )
            return _failed_run(request, spec, [reason], input_hash=input_hash)

        rejected = len(compiled.rejected_records.records)
        execution_state = ExecutionState.PARTIAL if rejected else ExecutionState.SUCCEEDED
        return ToolRunV2(
            run_id=run_id,
            request=request,
            implementation_state=spec.implementation_state,
            execution_state=execution_state,
            tool_version=spec.version,
            environment_spec_id=spec.environment_spec_id,
            input_hash=input_hash,
            created_at=compiled.created_at,
            measurements=[],
            artifacts=_runtime_artifacts(final, run_id, compiled.record_set.records),
            visualizations=[],
            result_schema_ref=RESULT_SCHEMA_REF,
            result=result.model_dump(mode="json"),
            reason_codes=["individual_records_rejected"] if rejected else [],
            warnings=[],
        )

    @staticmethod
    def _envelope_reasons(
        request: ToolRequestV2, spec: ToolPackageSpecV2
    ) -> list[str]:
        reasons: list[str] = []
        if request.tool_version is not None and request.tool_version != spec.version:
            reasons.append("tool_version_mismatch")
        if request.assets:
            reasons.append("p0_09_expression_assets_forbidden")
        if request.measurement_spec_ref is not None:
            reasons.append("p0_09_top_level_measurement_spec_forbidden")
        if request.parameters:
            reasons.append("p0_09_parameters_forbidden")
        roles = [item.role for item in request.object_inputs]
        if roles.count("compilation_bundle") != 1:
            reasons.append("exactly_one_compilation_bundle_required")
        if roles.count("evidence_family_registry") != 1:
            reasons.append("exactly_one_evidence_family_registry_required")
        if roles.count("claim_registry") != 1:
            reasons.append("exactly_one_claim_registry_required")
        if roles.count("reconciliation_spec_registry") != 1:
            reasons.append("exactly_one_reconciliation_registry_required")
        if any(role not in ROLE_SCHEMAS for role in roles):
            reasons.append("unsupported_object_input_role")
        for ref in request.object_inputs:
            if ref.role in ROLE_SCHEMAS and ref.schema_ref != ROLE_SCHEMAS[ref.role]:
                reasons.append("object_input_schema_mismatch")
        if len({item.input_id for item in request.object_inputs}) != len(request.object_inputs):
            reasons.append("duplicate_object_input_id")
        return reasons


adapter = EvidenceCompilerAdapter()


def _load_structured_inputs(
    refs: list[StructuredInputRef],
) -> tuple[LoadedInputs | None, list[str]]:
    objects: dict[str, FrozenModel] = {}
    bytes_by_input: dict[str, bytes] = {}
    reasons: list[str] = []
    seen: set[str] = set()
    for ref in refs:
        if ref.input_id in seen:
            reasons.append("duplicate_object_input_id")
            continue
        seen.add(ref.input_id)
        model = ROLE_MODELS.get(ref.role)
        if model is None:
            continue
        if ref.media_type != "application/json":
            reasons.append("structured_input_media_type_unsupported")
        try:
            raw = _read_verified_bytes(ref)
        except StructuredInputError as exc:
            reasons.append(exc.reason_code)
            continue
        bytes_by_input[ref.input_id] = raw
        try:
            payload = _loads_json(raw)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            reasons.append("structured_input_json_invalid")
            continue
        if _contains_legacy_contract(payload):
            reasons.append("legacy_evidence_contract_rejected")
            continue
        if contains_unsafe_reference(_top_level_raw_payload(ref.role, payload)):
            reasons.append("unsafe_structured_input_reference")
            continue
        try:
            value = model.model_validate(payload)
            _validate_declared_version(ref, value)
        except (ValidationError, ValueError):
            reasons.append("structured_input_schema_invalid")
            continue
        if contains_unsafe_reference(_top_level_payload(ref.role, value)):
            reasons.append("unsafe_structured_input_reference")
            continue
        objects[ref.input_id] = value
    if reasons:
        return None, sorted(set(reasons))
    return LoadedInputs(objects_by_input_id=objects, bytes_by_input_id=bytes_by_input), []


def _read_verified_bytes(ref: StructuredInputRef) -> bytes:
    path = ref.path
    try:
        raw = _read_regular_bytes(path)
    except FileNotFoundError as exc:
        raise StructuredInputError("structured_input_not_found") from exc
    except OSError as exc:
        raise StructuredInputError("structured_input_not_regular_file") from exc
    if hashlib.sha256(raw).hexdigest() != ref.sha256:
        raise StructuredInputError("structured_input_checksum_mismatch")
    return raw


def _loads_json(raw: bytes) -> Any:
    def reject_constant(value: str) -> None:
        raise ValueError(f"non-finite JSON constant: {value}")

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    return json.loads(
        raw.decode("utf-8"),
        parse_constant=reject_constant,
        object_pairs_hook=unique_object,
    )


def _validate_declared_version(ref: StructuredInputRef, value: FrozenModel) -> None:
    for field in ("object_version", "bundle_version", "profile_version", "registry_version", "version"):
        actual = getattr(value, field, None)
        if actual is not None:
            if str(actual) != ref.object_version:
                raise ValueError("declared object version mismatch")
            return


def _top_level_payload(role: str, value: FrozenModel) -> dict[str, Any]:
    payload = value.model_dump(mode="json")
    if role == "compilation_bundle":
        # These are explicitly record-level partial-failure surfaces.
        payload.pop("candidate_records", None)
        payload.pop("missing_observations", None)
        payload.pop("external_case_evidence_refs", None)
    return payload


def _top_level_raw_payload(role: str, value: Any) -> Any:
    if role != "compilation_bundle" or not isinstance(value, dict):
        return value
    return {
        key: item
        for key, item in value.items()
        if key
        not in {
            "candidate_records",
            "missing_observations",
            "external_case_evidence_refs",
        }
    }


def _binding_reasons(request: ToolRequestV2, loaded: LoadedInputs) -> list[str]:
    reasons: list[str] = []
    bundles = _objects_for_role(request, loaded, "compilation_bundle", EvidenceCompilationBundle)
    if len(bundles) != 1:
        return ["exactly_one_compilation_bundle_required"]
    bundle = bundles[0]
    profiles = {
        ref.input_id: loaded.objects_by_input_id[ref.input_id]
        for ref in request.object_inputs
        if ref.role == "evidence_sufficiency_profile"
    }
    profile_count = len(profiles)
    if bundle.graph_kind is GraphKind.CASE:
        if not 1 <= profile_count <= 5:
            reasons.append("sufficiency_profile_cardinality_invalid")
        bound_ids = {
            item.get("sufficiency_profile_input_id")
            for item in bundle.candidate_records
            if isinstance(item, dict)
            and isinstance(item.get("sufficiency_profile_input_id"), str)
        }
    else:
        if not 2 <= profile_count <= 25:
            reasons.append("sufficiency_profile_cardinality_invalid")
        bound_ids = {
            value
            for item in bundle.external_case_evidence_refs
            if isinstance(value := _external_profile_input_id(item), str)
        }
    if set(profiles) != bound_ids:
        reasons.append("unbound_sufficiency_profile")
    profile_ids = [
        item.profile_id
        for item in profiles.values()
        if isinstance(item, EvidenceSufficiencyProfile)
    ]
    if len(profile_ids) != len(set(profile_ids)):
        reasons.append("duplicate_sufficiency_profile_id")
    try:
        validate_prior_history(bundle)
    except CompilationInvariantError as exc:
        reasons.append(exc.reason_code)
    resolved_output = request.output_dir.resolve()
    for ref in request.object_inputs:
        resolved_input = ref.path.resolve()
        if resolved_input == resolved_output or resolved_input.is_relative_to(resolved_output):
            reasons.append("output_dir_overlaps_structured_input")
    return sorted(set(reasons))


def _external_profile_input_id(
    item: ExternalCaseEvidenceRef | dict[str, Any],
) -> str | None:
    if isinstance(item, ExternalCaseEvidenceRef):
        return item.sufficiency_profile_input_id
    value = item.get("sufficiency_profile_input_id")
    return value if isinstance(value, str) else None


def _contains_legacy_contract(value: object) -> bool:
    if isinstance(value, dict):
        if set(map(str, value)) & LEGACY_KEYS:
            return True
        return any(_contains_legacy_contract(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_legacy_contract(item) for item in value)
    return False


def _objects_for_role(
    request: ToolRequestV2,
    loaded: LoadedInputs,
    role: str,
    model: type[Any],
) -> list[Any]:
    values = [
        loaded.objects_by_input_id[ref.input_id]
        for ref in request.object_inputs
        if ref.role == role and ref.input_id in loaded.objects_by_input_id
    ]
    if not all(isinstance(item, model) for item in values):
        raise TypeError(f"loaded {role} object has wrong model")
    return values


def _single_object(
    request: ToolRequestV2,
    loaded: LoadedInputs,
    role: str,
    model: type[Any],
) -> Any:
    values = _objects_for_role(request, loaded, role, model)
    if len(values) != 1:
        raise ValueError(f"expected exactly one {role}")
    return values[0]


def _write_bundle(
    *,
    staging: Path,
    request: ToolRequestV2,
    spec: ToolPackageSpecV2,
    bundle: EvidenceCompilationBundle,
    compiled: Any,
    run_id: str,
    objects_by_input_id: Mapping[str, FrozenModel],
) -> tuple[EvidenceCompilerRunResult, list[dict[str, Any]]]:
    _write_json(staging / "evidence_records.json", compiled.record_set.model_dump(mode="json"))
    _write_json(
        staging / "evidence_requirements.json", compiled.requirement_set.model_dump(mode="json")
    )
    _write_json(
        staging / "reconciliation_records.json",
        compiled.reconciliation_set.model_dump(mode="json"),
    )
    try:
        write_parquet(
            staging / "graph_nodes.parquet",
            staging / "graph_edges.parquet",
            compiled.nodes,
            compiled.edges,
        )
        roundtrip_nodes, roundtrip_edges = read_parquet_rows(
            staging / "graph_nodes.parquet", staging / "graph_edges.parquet"
        )
        if roundtrip_nodes != compiled.nodes or roundtrip_edges != compiled.edges:
            raise ValueError("parquet row mismatch")
        root_ref = bundle.product_case_ref or bundle.comparison_ref
        assert root_ref is not None
        root_type = (
            "ProductCase" if bundle.graph_kind is GraphKind.CASE else "ComparisonRecord"
        )
        root_node = next(
            item.node_id
            for item in compiled.nodes
            if item.node_type.value == root_type
            and item.object_id == root_ref.object_id
            and item.object_version == root_ref.object_version
        )
        validate_graph_rows(
            roundtrip_nodes,
            roundtrip_edges,
            root_id=root_node,
            root_type=next(item.node_type for item in compiled.nodes if item.node_id == root_node),
        )
    except Exception as exc:
        raise ValueError("parquet_projection_failed") from exc

    first_five = {
        "evidence_records": _artifact_ref(staging / "evidence_records.json", "application/json"),
        "evidence_requirements": _artifact_ref(
            staging / "evidence_requirements.json", "application/json"
        ),
        "reconciliation_records": _artifact_ref(
            staging / "reconciliation_records.json", "application/json"
        ),
        "graph_nodes": _artifact_ref(
            staging / "graph_nodes.parquet",
            "application/vnd.apache.parquet",
            row_count=len(compiled.nodes),
        ),
        "graph_edges": _artifact_ref(
            staging / "graph_edges.parquet",
            "application/vnd.apache.parquet",
            row_count=len(compiled.edges),
        ),
    }
    manifest_common = dict(
        graph_id=compiled.graph_id,
        graph_version=compiled.graph_version,
        canonicalization_id=CANONICALIZATION_ID,
        node_count=len(compiled.nodes),
        edge_count=len(compiled.edges),
        object_counts=object_counts(compiled.nodes),
        source_input_hash=compiled.input_hash,
        base_graph_ref=bundle.base_graph_ref,
        created_at=compiled.created_at,
        **first_five,
    )
    if bundle.graph_kind is GraphKind.CASE:
        assert bundle.product_case_ref is not None
        manifest = CaseEvidenceGraphManifest(
            **manifest_common, product_case_ref=bundle.product_case_ref
        )
        manifest_name = "case_evidence_graph_manifest.json"
        manifest_schema = "bridge://schemas/case-evidence-graph-manifest/v0.1"
    else:
        assert bundle.comparison_ref is not None
        manifest = ComparisonEvidenceGraphManifest(
            **manifest_common,
            comparison_ref=bundle.comparison_ref,
            case_graph_refs=bundle.case_graph_refs,
        )
        manifest_name = "comparison_evidence_graph_manifest.json"
        manifest_schema = "bridge://schemas/comparison-evidence-graph-manifest/v0.1"
    _write_json(staging / manifest_name, manifest.model_dump(mode="json"))
    try:
        from bridge.tool_packages.p0_09_evidence_compiler.queries import (
            EvidenceGraphQueries,
        )

        EvidenceGraphQueries.open(staging / manifest_name)
    except ValueError as exc:
        raise ValueError("graph_invariant_failed: public graph preflight failed") from exc
    cytoscape = cytoscape_projection(
        graph_id=compiled.graph_id,
        graph_version=compiled.graph_version,
        nodes=compiled.nodes,
        edges=compiled.edges,
    )
    _write_json(staging / "cytoscape_elements.json", cytoscape.model_dump(mode="json"))
    _write_json(
        staging / "rejected_records.json", compiled.rejected_records.model_dump(mode="json")
    )
    created_count = sum(
        item.disposition.value in {"created", "appended"}
        for item in compiled.record_set.dispositions
    )
    unchanged_count = sum(
        item.disposition.value == "unchanged" for item in compiled.record_set.dispositions
    )
    rejected_count = len(compiled.rejected_records.records)
    result = EvidenceCompilerRunResult(
        result_id=f"evidence-compiler-result:{compiled.input_hash[:16]}",
        result_version="0.1.0",
        graph_kind=bundle.graph_kind,
        graph_id=compiled.graph_id,
        graph_version=compiled.graph_version,
        record_set_ref=compiled.record_set.record_set_id,
        requirement_set_ref=compiled.requirement_set.requirement_set_id,
        reconciliation_refs=[item.ref for item in compiled.reconciliation_set.records],
        graph_manifest_schema_ref=manifest_schema,
        graph_manifest_ref=manifest_name,
        cytoscape_export_ref="cytoscape_elements.json",
        rejected_record_count=rejected_count,
        accepted_record_count=created_count,
        unchanged_record_count=unchanged_count,
        reason_codes=["individual_records_rejected"] if rejected_count else [],
    )
    _write_json(
        staging / "evidence_compiler_run_result.json", result.model_dump(mode="json")
    )
    preceding = sorted(
        [
            "evidence_records.json",
            "evidence_requirements.json",
            "reconciliation_records.json",
            "graph_nodes.parquet",
            "graph_edges.parquet",
            manifest_name,
            "cytoscape_elements.json",
            "rejected_records.json",
            "evidence_compiler_run_result.json",
        ]
    )
    artifact_specs = [
        {
            "filename": filename,
            "media_type": (
                "application/vnd.apache.parquet" if filename.endswith(".parquet") else "application/json"
            ),
            "sha256": hashlib.sha256((staging / filename).read_bytes()).hexdigest(),
            "size_bytes": (staging / filename).stat().st_size,
        }
        for filename in preceding
    ]
    artifact_manifest = {
        "run_id": run_id,
        "tool_id": spec.tool_id,
        "tool_version": spec.version,
        "environment_spec_id": spec.environment_spec_id,
        "result_schema_ref": spec.result_schema_ref,
        "input_hash": compiled.input_hash,
        "structured_inputs": [
            {
                "input_id": ref.input_id,
                "role": ref.role,
                "schema_ref": ref.schema_ref,
                "object_version": ref.object_version,
                "semantic_sha256": hashlib.sha256(
                    canonical_json_bytes(
                        normalize_identity_payload(objects_by_input_id[ref.input_id])
                    )
                ).hexdigest(),
                "media_type": ref.media_type,
            }
            for ref in sorted(request.object_inputs, key=lambda item: (item.role, item.input_id))
        ],
        "artifacts": artifact_specs,
    }
    _write_json(staging / "artifact_manifest.json", artifact_manifest)
    _verify_artifacts(staging, artifact_specs)
    return result, artifact_specs


def _artifact_ref(path: Path, media_type: str, row_count: int | None = None) -> GraphArtifactRef:
    return GraphArtifactRef(
        filename=path.name,
        media_type=media_type,
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        row_count=row_count,
    )


def _verify_artifacts(root: Path, specs: list[dict[str, Any]]) -> None:
    filenames = [item.get("filename") for item in specs]
    if len(filenames) != len(set(filenames)):
        raise ValueError("artifact_checksum_verification_failed")
    for item in specs:
        filename = item.get("filename")
        if not isinstance(filename, str) or not _safe_artifact_filename(filename):
            raise ValueError("artifact_checksum_verification_failed")
        try:
            raw = _read_regular_bytes(root / filename)
        except OSError as exc:
            raise ValueError("artifact_checksum_verification_failed") from exc
        if (
            hashlib.sha256(raw).hexdigest() != item.get("sha256")
            or item.get("size_bytes") != len(raw)
        ):
            raise ValueError("artifact_checksum_verification_failed")


def _inputs_unchanged(refs: list[StructuredInputRef]) -> bool:
    for ref in refs:
        try:
            if hashlib.sha256(_read_regular_bytes(ref.path)).hexdigest() != ref.sha256:
                return False
        except OSError:
            return False
    return True


def _bundles_match(staging: Path, final: Path) -> bool:
    if not final.is_dir() or final.is_symlink():
        return False
    staging_names = {path.name for path in staging.iterdir()}
    final_names = {path.name for path in final.iterdir()}
    if staging_names != final_names:
        return False
    if not (
        {"case_evidence_graph_manifest.json", "comparison_evidence_graph_manifest.json"}
        & staging_names
    ):
        return False
    try:
        manifest = _loads_json(_read_regular_bytes(final / "artifact_manifest.json"))
        specs = manifest["artifacts"]
        expected_specs = final_names - {"artifact_manifest.json"}
        if {item.get("filename") for item in specs} != expected_specs:
            return False
        _verify_artifacts(final, specs)
    except Exception:
        return False
    try:
        return all(
            _read_regular_bytes(staging / name) == _read_regular_bytes(final / name)
            for name in staging_names
        )
    except OSError:
        return False


def _safe_artifact_filename(filename: str) -> bool:
    path = Path(filename)
    return (
        bool(ARTIFACT_FILENAME.fullmatch(filename))
        and not path.is_absolute()
        and path.name == filename
        and "/" not in filename
        and "\\" not in filename
    )


def _read_regular_bytes(path: Path) -> bytes:
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or path.is_symlink():
        raise OSError("not a regular file")
    raw = path.read_bytes()
    after = path.lstat()
    if (
        not stat.S_ISREG(after.st_mode)
        or before.st_dev != after.st_dev
        or before.st_ino != after.st_ino
        or before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
        or len(raw) != after.st_size
    ):
        raise OSError("file changed while reading")
    return raw


def _runtime_artifacts(
    final: Path, run_id: str, records: list[Any]
) -> list[ArtifactManifest]:
    evidence_ids = sorted({record.evidence_id for record in records})
    items = []
    for path in sorted(final.iterdir(), key=lambda item: item.name):
        if not path.is_file():
            continue
        suffix = path.stem
        kind = suffix
        media_type = (
            "application/vnd.apache.parquet" if path.suffix == ".parquet" else "application/json"
        )
        items.append(
            ArtifactManifest(
                artifact_id=f"artifact:{run_id}:{suffix}",
                kind=kind,
                path=path.resolve(),
                media_type=media_type,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                evidence_ids=evidence_ids,
            )
        )
    return sorted(items, key=lambda item: item.artifact_id)


def _write_json(path: Path, payload: object) -> None:
    path.write_bytes(canonical_json_bytes(payload, indent=2))


def _failed_run(
    request: ToolRequestV2,
    spec: ToolPackageSpecV2,
    reason_codes: list[str],
    *,
    input_hash: str | None = None,
) -> ToolRunV2:
    reasons = sorted(set(reason_codes))
    failure_hash = hashlib.sha256(
        canonical_json_bytes(
            {
                "tool_id": request.tool_id,
                "tool_version": spec.version,
                "reason_codes": reasons,
                "object_inputs": [
                    {
                        "input_id": ref.input_id,
                        "role": ref.role,
                        "schema_ref": ref.schema_ref,
                        "object_version": ref.object_version,
                        "sha256": ref.sha256,
                        "media_type": ref.media_type,
                    }
                    for ref in sorted(request.object_inputs, key=lambda item: (item.role, item.input_id))
                ],
            }
        )
    ).hexdigest()
    return ToolRunV2(
        run_id=f"run-{failure_hash[:16]}",
        request=request,
        implementation_state=spec.implementation_state,
        execution_state=ExecutionState.FAILED,
        tool_version=spec.version,
        environment_spec_id=spec.environment_spec_id,
        input_hash=input_hash,
        created_at=datetime(1970, 1, 1, tzinfo=timezone.utc),
        measurements=[],
        artifacts=[],
        visualizations=[],
        result_schema_ref=RESULT_SCHEMA_REF,
        result=None,
        reason_codes=reasons,
        warnings=[],
    )
