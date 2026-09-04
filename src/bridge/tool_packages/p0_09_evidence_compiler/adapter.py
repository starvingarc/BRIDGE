from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
import shutil
from typing import Any, Mapping
from uuid import uuid4

from bridge.tool_packages._structured_runtime import (
    LoadedInputs,
    StructuredInputError,
    failed_v2_run,
    inputs_unchanged as _inputs_unchanged,
    load_structured_inputs,
    objects_for_role as _objects_for_role,
    read_regular_bytes as _read_regular_bytes,
    single_object as _single_object,
    strict_json_loads as _loads_json,
    write_json as _write_json,
)
from bridge.tool_packages.p0_08_evidence_sufficiency.models import (
    EvidenceSufficiencyProfile,
    EvidenceSufficiencyProfileV2,
    EvidenceSufficiencyRunResultV2,
)
from bridge.tool_packages.p0_09_evidence_compiler.compiler import (
    CompilationInvariantError,
    canonical_input_hash,
    compile_evidence_graph,
    semantic_input_projection,
    evidence_record_content_hash,
    logical_key_hash,
    validate_prior_history,
)
from bridge.tool_packages.p0_09_evidence_compiler.graph import (
    cytoscape_projection,
    object_counts,
    read_parquet_bytes,
    validate_graph_rows,
    write_parquet,
)
from bridge.tool_packages.p0_09_evidence_compiler.models import (
    BaseGraphRef,
    CANONICALIZATION_ID,
    CaseGraphRef,
    CaseEvidenceGraphManifest,
    ClaimRegistry,
    ComparisonEvidenceGraphManifest,
    EvidenceCompilationBundle,
    EvidenceCompilerRunResult,
    EvidenceFamilyRegistry,
    ExternalCaseEvidenceBinding,
    EvidenceRecordSet,
    EvidenceRequirementSet,
    EvidenceLifecycleState,
    ExternalCaseEvidenceRef,
    GraphArtifactRef,
    GraphKind,
    GraphNodeType,
    GraphRecordMode,
    MissingEvidenceObservation,
    ReconciliationSpecRegistry,
    VersionedObjectRef,
    contains_unsafe_reference,
    is_prohibited_conclusion_key,
)
from bridge.tool_packages.p0_09_evidence_compiler.visualization import (
    PreparedEvidenceCompilerVisualizations,
    prepare_evidence_compiler_visualizations,
)
from bridge.tool_packages.p0_09_evidence_compiler.visualization_data import (
    build_evidence_compiler_visualization_data,
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
    "compilation_bundle": {"bridge://schemas/evidence-compilation-bundle/v0.1"},
    "evidence_sufficiency_profile": {
        "bridge://schemas/evidence-sufficiency-profile/v0.1",
        "bridge://schemas/evidence-sufficiency-profile/v0.2",
    },
    "evidence_sufficiency_run_result": {
        "bridge://schemas/evidence-sufficiency-run-result/v0.2"
    },
    "evidence_family_registry": {"bridge://schemas/evidence-family-registry/v0.1"},
    "claim_registry": {"bridge://schemas/claim-registry/v0.1"},
    "reconciliation_spec_registry": {"bridge://schemas/reconciliation-spec-registry/v0.1"},
    "base_graph_manifest": {
        "bridge://schemas/case-evidence-graph-manifest/v0.1",
        "bridge://schemas/comparison-evidence-graph-manifest/v0.1",
    },
    "base_evidence_record_set": {"bridge://schemas/evidence-record-set/v0.1"},
    "base_evidence_requirement_set": {"bridge://schemas/evidence-requirement-set/v0.1"},
    "source_case_graph_manifest": {
        "bridge://schemas/case-evidence-graph-manifest/v0.1"
    },
    "source_case_evidence_record_set": {
        "bridge://schemas/evidence-record-set/v0.1"
    },
}
ROLE_MODELS: dict[str, type[FrozenModel]] = {
    "compilation_bundle": EvidenceCompilationBundle,
    "evidence_sufficiency_profile": EvidenceSufficiencyProfile,
    "evidence_sufficiency_run_result": EvidenceSufficiencyRunResultV2,
    "evidence_family_registry": EvidenceFamilyRegistry,
    "claim_registry": ClaimRegistry,
    "reconciliation_spec_registry": ReconciliationSpecRegistry,
    "base_evidence_record_set": EvidenceRecordSet,
    "base_evidence_requirement_set": EvidenceRequirementSet,
    "source_case_evidence_record_set": EvidenceRecordSet,
}
ARTIFACT_FILENAME = re.compile(r"^[a-z0-9_]+(?:\.[a-z0-9]+)+$")


@dataclass(frozen=True)
class VerifiedGraphInputs:
    base_manifest: CaseEvidenceGraphManifest | ComparisonEvidenceGraphManifest | None
    source_manifests: dict[str, CaseEvidenceGraphManifest]
    source_record_sets: dict[str, EvidenceRecordSet]
    source_effective_lifecycle: dict[
        str, dict[str, EvidenceLifecycleState]
    ]


@dataclass(frozen=True)
class ResolvedSufficiencyInputs:
    bundle: EvidenceCompilationBundle
    profiles_by_input_id: dict[str, EvidenceSufficiencyProfile]
    objects_by_input_id: dict[str, FrozenModel]


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
            try:
                reasons.extend(_binding_reasons(request, loaded))
            except (OSError, RuntimeError):
                reasons.append("output_dir_preflight_failed")
        reason_codes = sorted(set(reasons))
        return EligibilityResult(
            tool_id=request.tool_id,
            eligible=not reason_codes,
            reason_codes=reason_codes,
        )

    def run(self, request: ToolRequestV2, spec: ToolPackageSpecV2) -> ToolRunV2:
        if not isinstance(request, ToolRequestV2):
            return _failed_v1_request(request, spec)
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
        try:
            verified_graph_inputs = _verify_graph_inputs(request, loaded, bundle)
            resolved = _resolve_sufficiency_inputs(
                request, loaded, bundle, verified_graph_inputs
            )
        except CompilationInvariantError as exc:
            return _failed_run(request, spec, [exc.reason_code])
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
                bundle=resolved.bundle,
                profiles_by_input_id=resolved.profiles_by_input_id,
                family_registry=family_registry,
                claim_registry=claim_registry,
                reconciliation_registry=reconciliation_registry,
                verified_graph_inputs=verified_graph_inputs,
                objects_by_input_id=resolved.objects_by_input_id,
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

        try:
            visualization_profile = build_evidence_compiler_visualization_data(
                compiled=compiled,
                claim_registry=claim_registry,
                family_registry=family_registry,
                run_id=run_id,
                tool_version=spec.version,
            )
        except (TypeError, ValueError):
            return _failed_run(
                request,
                spec,
                ["visualization_data_invalid"],
                input_hash=input_hash,
            )
        try:
            prepared_visualizations = prepare_evidence_compiler_visualizations(
                profile=visualization_profile,
                output_dir=request.output_dir.resolve(),
                run_id=run_id,
                tool_version=spec.version,
            )
        except Exception:
            return _failed_run(
                request,
                spec,
                ["visualization_render_failed"],
                input_hash=input_hash,
            )

        output_root: Path | None = None
        staging: Path | None = None
        staging_created = False
        try:
            output_root = request.output_dir.resolve()
            output_root.mkdir(parents=True, exist_ok=True)
            staging = output_root / f".{run_id}.staging-{uuid4().hex}"
            staging.mkdir(mode=0o700)
            staging_created = True
            result = _write_bundle(
                staging=staging,
                request=request,
                spec=spec,
                bundle=resolved.bundle,
                compiled=compiled,
                run_id=run_id,
                objects_by_input_id=resolved.objects_by_input_id,
                prepared_visualizations=prepared_visualizations,
            )
            if not _inputs_unchanged(request.object_inputs):
                shutil.rmtree(staging)
                staging_created = False
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
                    staging_created = False
                    return _failed_run(
                        request,
                        spec,
                        ["existing_run_bundle_hash_mismatch"],
                        input_hash=input_hash,
                    )
                shutil.rmtree(staging)
                staging_created = False
            else:
                os.replace(staging, final)
                staging_created = False
        except Exception as exc:
            if staging_created and staging is not None:
                shutil.rmtree(staging, ignore_errors=True)
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
        assert output_root is not None
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
            artifacts=_runtime_artifacts(
                final,
                run_id,
                visualization_profile.evidence_ids,
                prepared_visualizations.artifacts,
            ),
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
        if (
            "evidence_sufficiency_profile" in roles
            and "evidence_sufficiency_run_result" in roles
        ):
            reasons.append("mixed_sufficiency_input_modes")
        if not any(
            role in {"evidence_sufficiency_profile", "evidence_sufficiency_run_result"}
            for role in roles
        ):
            reasons.append("sufficiency_input_required")
        if any(role not in ROLE_SCHEMAS for role in roles):
            reasons.append("unsupported_object_input_role")
        for ref in request.object_inputs:
            if ref.role in ROLE_SCHEMAS and ref.schema_ref not in ROLE_SCHEMAS[ref.role]:
                reasons.append("object_input_schema_mismatch")
        if len({item.input_id for item in request.object_inputs}) != len(request.object_inputs):
            reasons.append("duplicate_object_input_id")
        return reasons


adapter = EvidenceCompilerAdapter()


def _load_structured_inputs(
    refs: list[StructuredInputRef],
) -> tuple[LoadedInputs | None, list[str]]:
    return load_structured_inputs(
        refs,
        model_for=_role_model,
        validate_payload=_validate_input_payload,
        validate_model=_validate_input_model,
    )


def _role_model(ref: StructuredInputRef) -> type[FrozenModel] | None:
    if ref.role == "evidence_sufficiency_profile":
        return (
            EvidenceSufficiencyProfileV2
            if ref.schema_ref
            == "bridge://schemas/evidence-sufficiency-profile/v0.2"
            else EvidenceSufficiencyProfile
        )
    if ref.role == "evidence_sufficiency_run_result":
        return EvidenceSufficiencyRunResultV2
    if ref.role in {"base_graph_manifest", "source_case_graph_manifest"}:
        if ref.schema_ref == "bridge://schemas/case-evidence-graph-manifest/v0.1":
            return CaseEvidenceGraphManifest
        if ref.schema_ref == "bridge://schemas/comparison-evidence-graph-manifest/v0.1":
            return ComparisonEvidenceGraphManifest
        return None
    return ROLE_MODELS.get(ref.role)


def _validate_input_payload(ref: StructuredInputRef, payload: Any) -> None:
    # The compilation bundle owns the only intentionally open record-level
    # JSON surfaces. Leave those entries to the compiler's sanitized sibling
    # rejection path while validating the surrounding envelope here.
    no_score_payload = (
        _top_level_raw_payload(ref.role, payload)
        if ref.role == "compilation_bundle"
        else payload
    )
    if (
        ref.role
        not in {"evidence_sufficiency_profile", "evidence_sufficiency_run_result"}
        and _contains_legacy_contract(no_score_payload)
    ):
        raise StructuredInputError("legacy_evidence_contract_rejected")
    if contains_unsafe_reference(_top_level_raw_payload(ref.role, payload)):
        raise StructuredInputError("unsafe_structured_input_reference")


def _validate_input_model(ref: StructuredInputRef, value: FrozenModel) -> None:
    _validate_declared_version(ref, value)
    if contains_unsafe_reference(_top_level_payload(ref.role, value)):
        raise StructuredInputError("unsafe_structured_input_reference")


def _validate_declared_version(ref: StructuredInputRef, value: FrozenModel) -> None:
    for field in (
        "object_version",
        "bundle_version",
        "profile_version",
        "registry_version",
        "record_set_version",
        "requirement_set_version",
        "result_version",
        "graph_version",
        "version",
    ):
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
    bundles = _objects_for_role(
        request, loaded, "compilation_bundle", EvidenceCompilationBundle
    )
    if len(bundles) != 1:
        return ["exactly_one_compilation_bundle_required"]
    bundle = bundles[0]
    verified_graph_inputs: VerifiedGraphInputs | None = None
    try:
        verified_graph_inputs = _verify_graph_inputs(request, loaded, bundle)
    except CompilationInvariantError as exc:
        reasons.append(exc.reason_code)
    if verified_graph_inputs is not None:
        try:
            resolved = _resolve_sufficiency_inputs(
                request, loaded, bundle, verified_graph_inputs
            )
            claims = _objects_for_role(request, loaded, "claim_registry", ClaimRegistry)
            family_registries = _objects_for_role(
                request, loaded, "evidence_family_registry", EvidenceFamilyRegistry
            )
            validate_prior_history(
                resolved.bundle,
                profiles_by_input_id=resolved.profiles_by_input_id,
                claims=(
                    {
                        (item.claim_id, item.version): item
                        for item in claims[0].claims
                    }
                    if len(claims) == 1
                    else None
                ),
                families=(
                    {
                        (item.evidence_family_id, item.version): item
                        for item in family_registries[0].families
                    }
                    if len(family_registries) == 1
                    else None
                ),
            )
        except CompilationInvariantError as exc:
            reasons.append(exc.reason_code)
    resolved_output = request.output_dir.resolve()
    for ref in request.object_inputs:
        resolved_input = ref.path.resolve()
        if resolved_input == resolved_output or resolved_input.is_relative_to(
            resolved_output
        ):
            reasons.append("output_dir_overlaps_structured_input")
    return sorted(set(reasons))


def _resolve_sufficiency_inputs(
    request: ToolRequestV2,
    loaded: LoadedInputs,
    bundle: EvidenceCompilationBundle,
    verified_graph_inputs: VerifiedGraphInputs,
) -> ResolvedSufficiencyInputs:
    profile_refs = [
        ref
        for ref in request.object_inputs
        if ref.role == "evidence_sufficiency_profile"
    ]
    run_refs = [
        ref
        for ref in request.object_inputs
        if ref.role == "evidence_sufficiency_run_result"
    ]
    if profile_refs and run_refs:
        raise CompilationInvariantError("mixed_sufficiency_input_modes")
    if profile_refs:
        profiles = {
            ref.input_id: loaded.objects_by_input_id[ref.input_id]
            for ref in profile_refs
        }
        if not all(
            isinstance(item, EvidenceSufficiencyProfile)
            for item in profiles.values()
        ):
            raise CompilationInvariantError("structured_input_schema_invalid")
        typed_profiles = {
            key: value
            for key, value in profiles.items()
            if isinstance(value, EvidenceSufficiencyProfile)
        }
        expected = (1, 5) if bundle.graph_kind is GraphKind.CASE else (2, 25)
        if not expected[0] <= len(typed_profiles) <= expected[1]:
            raise CompilationInvariantError("sufficiency_profile_cardinality_invalid")
        if bundle.graph_kind is GraphKind.CASE:
            bound_ids = {
                item.get("sufficiency_profile_input_id")
                for item in bundle.candidate_records
                if isinstance(item, dict)
                and isinstance(item.get("sufficiency_profile_input_id"), str)
            }
            profile_input_by_ref = {
                f"{profile.profile_id}@{profile.profile_version}": input_id
                for input_id, profile in typed_profiles.items()
            }
            bound_ids.update(
                profile_input_by_ref[record.sufficiency_profile_ref.ref]
                for record in bundle.prior_evidence_records
                if record.sufficiency_profile_ref.ref in profile_input_by_ref
            )
        else:
            bound_ids = {
                value
                for item in bundle.external_case_evidence_refs
                if isinstance(value := _external_profile_input_id(item), str)
            }
        if set(typed_profiles) != bound_ids:
            raise CompilationInvariantError("unbound_sufficiency_profile")
        if len({item.profile_id for item in typed_profiles.values()}) != len(
            typed_profiles
        ):
            raise CompilationInvariantError("duplicate_sufficiency_profile_id")
        return ResolvedSufficiencyInputs(
            bundle=bundle,
            profiles_by_input_id=typed_profiles,
            objects_by_input_id=dict(loaded.objects_by_input_id),
        )
    if not run_refs:
        raise CompilationInvariantError("sufficiency_input_required")
    runs = {
        ref.input_id: loaded.objects_by_input_id[ref.input_id]
        for ref in run_refs
    }
    if not all(
        isinstance(item, EvidenceSufficiencyRunResultV2)
        for item in runs.values()
    ):
        raise CompilationInvariantError("structured_input_schema_invalid")
    typed_runs = {
        key: value
        for key, value in runs.items()
        if isinstance(value, EvidenceSufficiencyRunResultV2)
    }
    if (
        bundle.graph_kind is GraphKind.CASE
        and len(typed_runs) != 1
    ) or (
        bundle.graph_kind is GraphKind.COMPARISON
        and not 2 <= len(typed_runs) <= 5
    ):
        raise CompilationInvariantError("sufficiency_run_cardinality_invalid")
    run_identities = [
        (result.result_id, result.result_version)
        for result in typed_runs.values()
    ]
    if len(run_identities) != len(set(run_identities)):
        raise CompilationInvariantError("duplicate_sufficiency_run_id")

    run_case_refs = {
        input_id: _object_ref_key(result.case_summary.product_case_ref)
        for input_id, result in typed_runs.items()
    }
    if any(ref is None for ref in run_case_refs.values()):
        raise CompilationInvariantError("sufficiency_run_case_binding_invalid")
    if bundle.graph_kind is GraphKind.CASE:
        if set(run_case_refs.values()) != {_object_ref_key(bundle.product_case_ref)}:
            raise CompilationInvariantError("sufficiency_run_case_binding_invalid")
    else:
        expected_cases = {
            _object_ref_key(item.product_case_ref) for item in bundle.case_graph_refs
        }
        if (
            len(run_case_refs.values()) != len(set(run_case_refs.values()))
            or set(run_case_refs.values()) != expected_cases
        ):
            raise CompilationInvariantError("sufficiency_run_case_binding_invalid")

    profiles_by_key: dict[str, EvidenceSufficiencyProfileV2] = {}
    profiles_by_run: dict[str, list[tuple[str, EvidenceSufficiencyProfileV2]]] = {}
    profile_refs_seen: set[str] = set()
    for run_input_id, result in typed_runs.items():
        for profile in result.profiles:
            profile_ref = f"{profile.profile_id}@{profile.profile_version}"
            if profile_ref in profile_refs_seen:
                raise CompilationInvariantError("duplicate_sufficiency_profile_id")
            profile_refs_seen.add(profile_ref)
            key_digest = hashlib.sha256(
                (
                    f"{result.result_id}@{result.result_version}|"
                    f"{profile_ref}"
                ).encode("utf-8")
            ).hexdigest()[:24]
            key = f"sufficiency-profile-binding:{key_digest}"
            if key in profiles_by_key:
                raise CompilationInvariantError("duplicate_sufficiency_profile_id")
            profiles_by_key[key] = profile
            profiles_by_run.setdefault(run_input_id, []).append((key, profile))

    if set(profiles_by_key) & set(loaded.objects_by_input_id):
        raise CompilationInvariantError(
            "sufficiency_profile_binding_id_collision"
        )

    claims = _objects_for_role(request, loaded, "claim_registry", ClaimRegistry)
    claim_by_ref = (
        {
            (item.claim_id, item.version): item
            for item in claims[0].claims
        }
        if len(claims) == 1
        else {}
    )
    bound_profile_keys: set[str] = set()
    rewritten_candidates: list[dict[str, Any]] = []
    for raw in bundle.candidate_records:
        run_input_id = raw.get("sufficiency_profile_input_id")
        if not isinstance(run_input_id, str):
            rewritten_candidates.append(raw)
            continue
        choices = profiles_by_run.get(run_input_id)
        if choices is None:
            raise CompilationInvariantError("sufficiency_run_profile_binding_invalid")
        claim = claim_by_ref.get(_object_ref_key(raw.get("claim_ref")))
        domain_id = (
            claim.domain_id
            if claim is not None
            else raw.get("domain_id")
            if isinstance(raw.get("domain_id"), str)
            else None
        )
        profile_key, _ = _select_embedded_profile(
            choices,
            product_case_ref=bundle.product_case_ref,
            domain_id=domain_id,
            allow_single_profile_fallback=True,
        )
        bound_profile_keys.add(profile_key)
        rewritten_candidates.append(
            {**raw, "sufficiency_profile_input_id": profile_key}
        )

    for record in bundle.prior_evidence_records:
        profile_key, _ = _select_embedded_profile(
            list(profiles_by_key.items()),
            product_case_ref=bundle.product_case_ref,
            profile_ref=_object_ref_key(record.sufficiency_profile_ref),
        )
        bound_profile_keys.add(profile_key)

    case_choices = next(iter(profiles_by_run.values()), [])
    for raw in bundle.missing_observations:
        try:
            observation = MissingEvidenceObservation.model_validate(raw)
        except ValueError:
            continue
        claim = claim_by_ref.get(_object_ref_key(observation.claim_ref))
        if claim is None:
            continue
        profile_key, _ = _select_embedded_profile(
            case_choices,
            product_case_ref=bundle.product_case_ref,
            domain_id=claim.domain_id,
            measurement_spec_ref=_object_ref_key(
                observation.source_contract_ref
            ),
        )
        bound_profile_keys.add(profile_key)

    rewritten_externals: list[ExternalCaseEvidenceRef | dict[str, Any]] = []
    for raw_item in bundle.external_case_evidence_refs:
        raw = (
            raw_item.model_dump(mode="json")
            if isinstance(raw_item, ExternalCaseEvidenceRef)
            else raw_item
        )
        run_input_id = raw.get("sufficiency_profile_input_id")
        if not isinstance(run_input_id, str):
            rewritten_externals.append(raw)
            continue
        choices = profiles_by_run.get(run_input_id)
        if choices is None:
            raise CompilationInvariantError("sufficiency_run_profile_binding_invalid")
        try:
            external = ExternalCaseEvidenceRef.model_validate(raw)
        except ValueError:
            external = None
        source_set = (
            verified_graph_inputs.source_record_sets.get(
                external.source_case_graph_ref.graph_id
            )
            if external is not None
            else None
        )
        source_record = next(
            (
                item
                for item in (source_set.records if source_set is not None else [])
                if external is not None and item.ref == external.evidence_ref
            ),
            None,
        )
        comparison_claim = claim_by_ref.get(
            _object_ref_key(
                external.comparison_claim_ref
                if external is not None
                else raw.get("comparison_claim_ref")
            )
        )
        domain_id = (
            comparison_claim.domain_id
            if comparison_claim is not None
            else source_record.domain_id
            if source_record is not None
            else None
        )
        profile_key, _ = _select_embedded_profile(
            choices,
            product_case_ref=typed_runs[run_input_id].case_summary.product_case_ref,
            domain_id=domain_id,
            allow_single_profile_fallback=True,
        )
        bound_profile_keys.add(profile_key)
        rewritten_externals.append(
            external.model_copy(update={"sufficiency_profile_input_id": profile_key})
            if external is not None
            else {**raw, "sufficiency_profile_input_id": profile_key}
        )

    if set(profiles_by_key) != bound_profile_keys:
        raise CompilationInvariantError("unbound_sufficiency_profile")
    resolved_bundle = bundle.model_copy(
        update={
            "candidate_records": rewritten_candidates,
            "external_case_evidence_refs": rewritten_externals,
        }
    )
    resolved_objects = dict(loaded.objects_by_input_id)
    resolved_objects.update(profiles_by_key)
    return ResolvedSufficiencyInputs(
        bundle=resolved_bundle,
        profiles_by_input_id=dict(profiles_by_key),
        objects_by_input_id=resolved_objects,
    )


def _object_ref_key(value: Any) -> tuple[str, str] | None:
    if isinstance(value, Mapping):
        object_id = value.get("object_id")
        object_version = value.get("object_version")
    else:
        object_id = getattr(value, "object_id", None)
        object_version = getattr(value, "object_version", None)
    if not isinstance(object_id, str) or not isinstance(object_version, str):
        return None
    return object_id, object_version


def _select_embedded_profile(
    choices: list[tuple[str, EvidenceSufficiencyProfileV2]],
    *,
    product_case_ref: Any,
    domain_id: Any = None,
    measurement_spec_ref: tuple[str, str] | None = None,
    profile_ref: tuple[str, str] | None = None,
    allow_single_profile_fallback: bool = False,
) -> tuple[str, EvidenceSufficiencyProfileV2]:
    case_ref = _object_ref_key(product_case_ref)
    case_choices = [
        item
        for item in choices
        if _object_ref_key(item[1].product_case_ref) == case_ref
    ]
    matches = case_choices
    if profile_ref is not None:
        matches = [
            item
            for item in matches
            if (item[1].profile_id, item[1].profile_version) == profile_ref
        ]
    if measurement_spec_ref is not None:
        matches = [
            item
            for item in matches
            if _object_ref_key(item[1].measurement_spec_ref)
            == measurement_spec_ref
        ]
    if domain_id is not None:
        domain_value = getattr(domain_id, "value", domain_id)
        matches = [
            item
            for item in matches
            if item[1].domain_id is not None
            and item[1].domain_id.value == domain_value
        ]
    if len(matches) == 1:
        return matches[0]
    if (
        allow_single_profile_fallback
        and profile_ref is None
        and measurement_spec_ref is None
        and len(case_choices) == 1
    ):
        return case_choices[0]
    raise CompilationInvariantError("sufficiency_run_profile_binding_invalid")


def _verify_graph_inputs(
    request: ToolRequestV2,
    loaded: LoadedInputs,
    bundle: EvidenceCompilationBundle,
) -> VerifiedGraphInputs:
    refs_by_role: dict[str, list[StructuredInputRef]] = {}
    for ref in request.object_inputs:
        refs_by_role.setdefault(ref.role, []).append(ref)

    base_manifests = refs_by_role.get("base_graph_manifest", [])
    base_record_sets = refs_by_role.get("base_evidence_record_set", [])
    base_requirement_sets = refs_by_role.get("base_evidence_requirement_set", [])
    if bundle.base_graph_ref is None:
        if base_manifests or base_record_sets or base_requirement_sets:
            raise CompilationInvariantError("prior_history_invalid", "unexpected base inputs")
        base_manifest = None
    else:
        if not (
            len(base_manifests) == len(base_record_sets) == len(base_requirement_sets) == 1
        ):
            raise CompilationInvariantError("prior_history_invalid", "base inputs required")
        manifest_ref = base_manifests[0]
        manifest = loaded.objects_by_input_id.get(manifest_ref.input_id)
        record_ref = base_record_sets[0]
        record_set = loaded.objects_by_input_id.get(record_ref.input_id)
        requirement_ref = base_requirement_sets[0]
        requirement_set = loaded.objects_by_input_id.get(requirement_ref.input_id)
        if not isinstance(manifest, (CaseEvidenceGraphManifest, ComparisonEvidenceGraphManifest)):
            raise CompilationInvariantError("prior_history_invalid", "base manifest invalid")
        if not isinstance(record_set, EvidenceRecordSet) or not isinstance(
            requirement_set, EvidenceRequirementSet
        ):
            raise CompilationInvariantError("prior_history_invalid", "base fact sets invalid")
        base = bundle.base_graph_ref
        if (
            manifest_ref.input_id != base.manifest_input_id
            or record_ref.input_id != base.record_set_input_id
            or requirement_ref.input_id != base.requirement_set_input_id
        ):
            raise CompilationInvariantError("prior_history_invalid", "base input binding mismatch")
        manifest_sha = hashlib.sha256(loaded.bytes_by_input_id[manifest_ref.input_id]).hexdigest()
        expected_kind = GraphKind.CASE if isinstance(manifest, CaseEvidenceGraphManifest) else GraphKind.COMPARISON
        root_matches = (
            isinstance(manifest, CaseEvidenceGraphManifest)
            and bundle.product_case_ref == manifest.product_case_ref
        ) or (
            isinstance(manifest, ComparisonEvidenceGraphManifest)
            and bundle.comparison_ref == manifest.comparison_ref
        )
        if (
            expected_kind is not bundle.graph_kind
            or not root_matches
            or base.graph_id != manifest.graph_id
            or base.graph_version != manifest.graph_version
            or base.manifest_sha256 != manifest_sha
            or record_ref.sha256 != manifest.evidence_records.sha256
            or requirement_ref.sha256 != manifest.evidence_requirements.sha256
            or record_set.graph_id != manifest.graph_id
            or record_set.graph_version != manifest.graph_version
            or requirement_set.graph_id != manifest.graph_id
            or requirement_set.graph_version != manifest.graph_version
            or record_set.records != bundle.prior_evidence_records
            or requirement_set.requirements != bundle.prior_requirements
        ):
            raise CompilationInvariantError("prior_history_invalid", "base graph mismatch")
        _preflight_graph_manifest(manifest_ref.path)
        base_manifest = manifest

    source_manifests: dict[str, CaseEvidenceGraphManifest] = {}
    source_record_sets: dict[str, EvidenceRecordSet] = {}
    source_effective_lifecycle: dict[
        str, dict[str, EvidenceLifecycleState]
    ] = {}
    source_manifest_refs = refs_by_role.get("source_case_graph_manifest", [])
    source_record_refs = refs_by_role.get("source_case_evidence_record_set", [])
    if bundle.graph_kind is GraphKind.CASE:
        if source_manifest_refs or source_record_refs:
            raise CompilationInvariantError("prior_history_invalid", "unexpected source graph inputs")
    else:
        declared_manifest_ids = [item.manifest_input_id for item in bundle.case_graph_refs]
        declared_record_ids = [item.record_set_input_id for item in bundle.case_graph_refs]
        actual_manifest_ids = [item.input_id for item in source_manifest_refs]
        actual_record_ids = [item.input_id for item in source_record_refs]
        if (
            len(set(declared_manifest_ids)) != len(declared_manifest_ids)
            or len(set(declared_record_ids)) != len(declared_record_ids)
            or set(actual_manifest_ids) != set(declared_manifest_ids)
            or set(actual_record_ids) != set(declared_record_ids)
        ):
            raise CompilationInvariantError("prior_history_invalid", "source graph inputs required")
        manifest_refs_by_id = {item.input_id: item for item in source_manifest_refs}
        record_refs_by_id = {item.input_id: item for item in source_record_refs}
        for declared_ref in bundle.case_graph_refs:
            ref = manifest_refs_by_id[declared_ref.manifest_input_id]
            record_ref = record_refs_by_id[declared_ref.record_set_input_id]
            manifest = loaded.objects_by_input_id.get(declared_ref.manifest_input_id)
            if not isinstance(manifest, CaseEvidenceGraphManifest):
                raise CompilationInvariantError("prior_history_invalid", "source manifest invalid")
            record_set = loaded.objects_by_input_id.get(declared_ref.record_set_input_id)
            if (
                not isinstance(record_set, EvidenceRecordSet)
                or declared_ref.graph_id != graph_identity_for_product_case(
                    declared_ref.product_case_ref
                )
                or declared_ref.graph_id != manifest.graph_id
                or declared_ref.graph_version != manifest.graph_version
                or declared_ref.product_case_ref != manifest.product_case_ref
                or declared_ref.manifest_sha256
                != hashlib.sha256(loaded.bytes_by_input_id[ref.input_id]).hexdigest()
                or record_ref.sha256 != manifest.evidence_records.sha256
                or record_set.graph_id != manifest.graph_id
                or record_set.graph_version != manifest.graph_version
            ):
                raise CompilationInvariantError("prior_history_invalid", "source graph mismatch")
            _preflight_graph_manifest(ref.path)
            effective = _validate_source_record_set(record_set, manifest)
            source_manifests[manifest.graph_id] = manifest
            source_record_sets[manifest.graph_id] = record_set
            source_effective_lifecycle[manifest.graph_id] = effective
        if len(source_manifests) != len(bundle.case_graph_refs):
            raise CompilationInvariantError("prior_history_invalid", "source graph set mismatch")
    return VerifiedGraphInputs(
        base_manifest=base_manifest,
        source_manifests=source_manifests,
        source_record_sets=source_record_sets,
        source_effective_lifecycle=source_effective_lifecycle,
    )


def _validate_source_record_set(
    record_set: EvidenceRecordSet, manifest: CaseEvidenceGraphManifest
) -> dict[str, EvidenceLifecycleState]:
    seen: set[str] = set()
    by_id: dict[str, list[Any]] = {}
    for record in record_set.records:
        if (
            record.ref in seen
            or record.product_case_ref != manifest.product_case_ref
            or record.evidence_id
            != f"evidence:{logical_key_hash(record.logical_key)[:24]}"
            or record.content_hash != evidence_record_content_hash(record)
        ):
            raise CompilationInvariantError(
                "prior_history_invalid", "source evidence facts invalid"
            )
        seen.add(record.ref)
        by_id.setdefault(record.evidence_id, []).append(record)
    effective: dict[str, EvidenceLifecycleState] = {}
    for versions in by_id.values():
        versions.sort(key=lambda item: item.evidence_version)
        if [item.evidence_version for item in versions] != list(
            range(1, len(versions) + 1)
        ) or len({item.logical_key for item in versions}) != 1:
            raise CompilationInvariantError(
                "prior_history_invalid", "source evidence history invalid"
            )
        for index, record in enumerate(versions):
            if index == 0:
                if record.revision_action.value != "create" or record.predecessor_ref is not None:
                    raise CompilationInvariantError(
                        "prior_history_invalid", "source evidence history invalid"
                    )
            elif record.predecessor_ref != versions[index - 1].ref:
                raise CompilationInvariantError(
                    "prior_history_invalid", "source evidence history invalid"
                )
            effective[record.ref] = record.lifecycle_state
        for predecessor, successor in zip(versions, versions[1:], strict=False):
            effective[predecessor.ref] = (
                EvidenceLifecycleState.INVALIDATED
                if successor.lifecycle_state is EvidenceLifecycleState.INVALIDATED
                else EvidenceLifecycleState.SUPERSEDED
            )
    return effective


def graph_identity_for_product_case(product_case_ref: Any) -> str:
    identity = f"case|{product_case_ref.ref}"
    return (
        "case-evidence-graph:"
        + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
    )


def _preflight_graph_manifest(path: Path) -> None:
    try:
        from bridge.tool_packages.p0_09_evidence_compiler.queries import (
            EvidenceGraphQueries,
        )

        EvidenceGraphQueries.open(path)
    except (OSError, ValueError) as exc:
        raise CompilationInvariantError(
            "prior_history_invalid", "graph manifest preflight failed"
        ) from exc


def _external_profile_input_id(
    item: ExternalCaseEvidenceRef | dict[str, Any],
) -> str | None:
    if isinstance(item, ExternalCaseEvidenceRef):
        return item.sufficiency_profile_input_id
    value = item.get("sufficiency_profile_input_id")
    return value if isinstance(value, str) else None


def _contains_legacy_contract(value: object) -> bool:
    if isinstance(value, dict):
        if any(is_prohibited_conclusion_key(key) for key in value):
            return True
        return any(_contains_legacy_contract(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_legacy_contract(item) for item in value)
    return False


def _write_bundle(
    *,
    staging: Path,
    request: ToolRequestV2,
    spec: ToolPackageSpecV2,
    bundle: EvidenceCompilationBundle,
    compiled: Any,
    run_id: str,
    objects_by_input_id: Mapping[str, FrozenModel],
    prepared_visualizations: PreparedEvidenceCompilerVisualizations,
) -> EvidenceCompilerRunResult:
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
        roundtrip_nodes, roundtrip_edges = read_parquet_bytes(
            _read_regular_bytes(staging / "graph_nodes.parquet"),
            _read_regular_bytes(staging / "graph_edges.parquet"),
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
        base_graph_ref=(
            BaseGraphRef(
                graph_id=bundle.base_graph_ref.graph_id,
                graph_version=bundle.base_graph_ref.graph_version,
                manifest_sha256=bundle.base_graph_ref.manifest_sha256,
            )
            if bundle.base_graph_ref is not None
            else None
        ),
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
            case_graph_refs=[
                CaseGraphRef(
                    graph_id=item.graph_id,
                    graph_version=item.graph_version,
                    manifest_sha256=item.manifest_sha256,
                    product_case_ref=item.product_case_ref,
                )
                for item in bundle.case_graph_refs
            ],
            external_evidence_bindings=[
                ExternalCaseEvidenceBinding(
                    source_case_graph_ref=item.source_case_graph_ref,
                    evidence_ref=item.evidence_ref,
                    evidence_content_hash=item.evidence_content_hash,
                    product_case_ref=item.product_case_ref,
                    source_claim_ref=item.source_claim_ref,
                    comparison_claim_ref=item.comparison_claim_ref,
                    evidence_family_ref=item.evidence_family_ref,
                    sufficiency_profile_ref=VersionedObjectRef(
                        object_id=profile.profile_id,
                        object_version=profile.profile_version,
                    ),
                    relation=item.relation,
                    evidence_state=item.evidence_state,
                    evidence_tier=item.evidence_tier,
                    lifecycle_state=item.lifecycle_state,
                    applicability=item.applicability,
                    tool_run_execution_state=item.tool_run_execution_state,
                )
                for item in compiled.external_case_evidence_refs
                if (
                    (profile := objects_by_input_id.get(item.sufficiency_profile_input_id))
                    is not None
                    and any(
                        node.node_type is GraphNodeType.EVIDENCE_RECORD
                        and node.record_mode is GraphRecordMode.EXTERNAL_REF
                        and f"{node.object_id}@{node.object_version}" == item.evidence_ref
                        and node.source_graph_id == item.source_case_graph_ref.graph_id
                        and node.content_hash == item.evidence_content_hash
                        for node in compiled.nodes
                    )
                )
            ],
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
    for filename, payload in sorted(prepared_visualizations.payloads.items()):
        path = staging / filename
        if not _safe_artifact_filename(filename) or path.exists():
            raise ValueError("artifact_checksum_verification_failed")
        path.write_bytes(payload)

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
            *sorted(prepared_visualizations.payloads),
            "evidence_compiler_run_result.json",
        ]
    )
    artifact_specs = [
        {
            "filename": filename,
            "media_type": _artifact_media_type(filename),
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
        "structured_inputs": semantic_input_projection(
            request, objects_by_input_id
        )[0],
        "artifacts": artifact_specs,
    }
    _write_json(staging / "artifact_manifest.json", artifact_manifest)
    _verify_artifacts(staging, artifact_specs)
    return result


def _artifact_media_type(filename: str) -> str:
    return {
        ".json": "application/json",
        ".parquet": "application/vnd.apache.parquet",
        ".tsv": "text/tab-separated-values",
        ".svg": "image/svg+xml",
        ".png": "image/png",
        ".pdf": "application/pdf",
    }.get(Path(filename).suffix, "application/octet-stream")


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


def _runtime_artifacts(
    final: Path,
    run_id: str,
    evidence_ids: list[str],
    visualization_artifacts: tuple[ArtifactManifest, ...],
) -> list[ArtifactManifest]:
    evidence_ids = sorted(set(evidence_ids))
    visualizations_by_name = {
        Path(item.path).name: item for item in visualization_artifacts
    }
    items = []
    for path in sorted(final.iterdir(), key=lambda item: item.name):
        if not path.is_file():
            continue
        if path.name in visualizations_by_name:
            items.append(visualizations_by_name[path.name])
            continue
        suffix = path.stem
        items.append(
            ArtifactManifest(
                artifact_id=f"artifact:{run_id}:{suffix}",
                kind=suffix,
                path=path.resolve(),
                media_type=_artifact_media_type(path.name),
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                evidence_ids=evidence_ids,
            )
        )
    return sorted(items, key=lambda item: item.artifact_id)


def _failed_run(
    request: ToolRequestV2,
    spec: ToolPackageSpecV2,
    reason_codes: list[str],
    *,
    input_hash: str | None = None,
) -> ToolRunV2:
    return failed_v2_run(
        request,
        spec,
        reason_codes,
        result_schema_ref=RESULT_SCHEMA_REF,
        fingerprint_input_key="object_inputs",
        input_hash=input_hash,
    )


def _failed_v1_request(
    request: ToolRequest, spec: ToolPackageSpecV2
) -> ToolRunV2:
    request_v2 = ToolRequestV2(
        request_id=request.request_id,
        tool_id=request.tool_id,
        output_dir=request.output_dir,
        tool_version=request.tool_version,
        assets=request.assets,
        measurement_spec_ref=request.measurement_spec_ref,
        parameters=request.parameters,
        random_seed=request.random_seed,
        object_inputs=[],
    )
    return _failed_run(request_v2, spec, ["tool_request_v2_required"])
