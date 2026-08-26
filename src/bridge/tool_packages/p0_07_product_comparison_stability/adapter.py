from __future__ import annotations

import hashlib
from dataclasses import dataclass

from bridge.tool_packages._structured_runtime import (
    LoadedInputs,
    StructuredInputError,
    canonical_json_bytes,
    directory_state,
    failed_v2_run,
    load_structured_inputs,
    objects_for_role,
    request_v2_from_v1,
    single_object,
)
from bridge.tool_packages._structured_runtime import (
    publish_single_json as _publish_single_json,
)
from bridge.tool_packages.p0_07_product_comparison_stability.executor import (
    evaluate_product_comparison,
)
from bridge.tool_packages.p0_07_product_comparison_stability.models import (
    ComparisonCaseManifest,
    ComparisonStabilitySpec,
    InputChecksumBinding,
    ProductEvidenceBundle,
)
from bridge.toolkit.contracts import (
    ArtifactManifest,
    EligibilityResult,
    ExecutionState,
    FrozenModel,
    ImplementationState,
    StructuredInputRef,
    ToolPackageSpecV2,
    ToolRequest,
    ToolRequestV2,
    ToolRunV2,
)

RESULT_SCHEMA_REF = "bridge://schemas/product-comparison-stability-profile/v0.1"
ROLE_MODELS: dict[str, tuple[str, type[FrozenModel]]] = {
    "comparison_stability_spec": (
        "bridge://schemas/comparison-stability-spec/v0.1",
        ComparisonStabilitySpec,
    ),
    "comparison_case_manifest": (
        "bridge://schemas/comparison-case-manifest/v0.1",
        ComparisonCaseManifest,
    ),
    "product_evidence_bundle": (
        "bridge://schemas/product-evidence-bundle/v0.1",
        ProductEvidenceBundle,
    ),
}


@dataclass(frozen=True)
class ProductComparisonStabilityAdapter:
    def check_eligibility(
        self, request: ToolRequestV2, spec: ToolPackageSpecV2
    ) -> EligibilityResult:
        if not isinstance(request, ToolRequestV2):
            tool_id = request.tool_id if isinstance(request, ToolRequest) else "P0-07"
            return EligibilityResult(
                tool_id=tool_id,
                eligible=False,
                reason_codes=["tool_request_v2_required"],
            )
        reasons = _envelope_reasons(request, spec)
        loaded, loading_reasons = _load_inputs(request.object_inputs)
        reasons.extend(loading_reasons)
        if loaded is not None and not reasons:
            reasons.extend(_binding_reasons(request, loaded))
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
        input_hash = _input_hash(request, spec)
        if not eligibility.eligible:
            return _failed_run(
                request, spec, eligibility.reason_codes, input_hash=input_hash
            )
        loaded, reasons = _load_inputs(request.object_inputs)
        if loaded is None or reasons:
            return _failed_run(request, spec, reasons, input_hash=input_hash)
        comparison_spec = single_object(
            request, loaded, "comparison_stability_spec", ComparisonStabilitySpec
        )
        manifest = single_object(
            request, loaded, "comparison_case_manifest", ComparisonCaseManifest
        )
        bundles = objects_for_role(
            request, loaded, "product_evidence_bundle", ProductEvidenceBundle
        )
        run_id = f"run-{input_hash[:16]}"
        result = evaluate_product_comparison(
            run_id=run_id,
            tool_version=spec.version,
            spec=comparison_spec,
            manifest=manifest,
            bundles=bundles,
            input_bindings=[
                InputChecksumBinding(
                    role=ref.role,
                    sha256=ref.sha256,
                )
                for ref in sorted(
                    request.object_inputs,
                    key=lambda item: (
                        item.role,
                        item.sha256,
                        item.schema_ref,
                        item.object_version,
                    ),
                )
            ],
        )
        payload = canonical_json_bytes(result.model_dump(mode="json"), indent=2)
        try:
            output_file = _publish_single_json(
                request=request,
                run_id=run_id,
                filename="product_comparison_stability_profile.json",
                payload=payload,
            )
        except StructuredInputError as exc:
            return _failed_run(
                request, spec, [exc.reason_code], input_hash=input_hash
            )
        artifact = ArtifactManifest(
            artifact_id=f"artifact:{run_id}:product-comparison-stability-profile",
            kind="product_comparison_stability_profile",
            path=output_file,
            media_type="application/json",
            sha256=hashlib.sha256(payload).hexdigest(),
            evidence_ids=result.evidence_refs,
        )
        execution_state = (
            ExecutionState.SUCCEEDED
            if result.profile_state == "complete"
            else ExecutionState.PARTIAL
        )
        return ToolRunV2(
            run_id=run_id,
            request=request,
            implementation_state=ImplementationState.IMPLEMENTED,
            execution_state=execution_state,
            tool_version=spec.version,
            environment_spec_id=spec.environment_spec_id,
            input_hash=input_hash,
            created_at=manifest.created_at,
            measurements=[],
            artifacts=[artifact],
            visualizations=[],
            result_schema_ref=RESULT_SCHEMA_REF,
            result=result.model_dump(mode="json"),
            reason_codes=result.reason_codes,
            warnings=[],
        )


adapter = ProductComparisonStabilityAdapter()


def _envelope_reasons(
    request: ToolRequestV2, spec: ToolPackageSpecV2
) -> list[str]:
    reasons: list[str] = []
    if request.tool_version is not None and request.tool_version != spec.version:
        reasons.append("tool_version_mismatch")
    if request.assets:
        reasons.append("p0_07_expression_assets_forbidden")
    if request.measurement_spec_ref is not None:
        reasons.append("p0_07_measurement_spec_parameter_forbidden")
    if request.parameters:
        reasons.append("p0_07_parameters_forbidden")
    if request.random_seed != 0:
        reasons.append("p0_07_random_seed_forbidden")
    roles = [ref.role for ref in request.object_inputs]
    for role in ("comparison_stability_spec", "comparison_case_manifest"):
        if roles.count(role) != 1:
            reasons.append(f"exactly_one_{role}_required")
    if not 2 <= roles.count("product_evidence_bundle") <= 20:
        reasons.append("two_to_twenty_product_evidence_bundles_required")
    if any(role not in ROLE_MODELS for role in roles):
        reasons.append("unsupported_object_input_role")
    for ref in request.object_inputs:
        contract = ROLE_MODELS.get(ref.role)
        if contract is not None and ref.schema_ref != contract[0]:
            reasons.append("object_input_schema_mismatch")
        if ref.object_version != "0.1.0":
            reasons.append("object_input_version_mismatch")
    if directory_state(request.output_dir) == "other":
        reasons.append("output_dir_not_regular_directory")
    return reasons


def _load_inputs(
    refs: list[StructuredInputRef],
) -> tuple[LoadedInputs | None, list[str]]:
    return load_structured_inputs(
        refs,
        model_for=lambda ref: ROLE_MODELS.get(ref.role, ("", None))[1],
        validate_model=_validate_object_version,
    )


def _validate_object_version(ref: StructuredInputRef, value: FrozenModel) -> None:
    if getattr(value, "object_version", None) != ref.object_version:
        raise StructuredInputError("object_input_version_mismatch")


def _binding_reasons(
    request: ToolRequestV2, loaded: LoadedInputs
) -> list[str]:
    spec = single_object(
        request, loaded, "comparison_stability_spec", ComparisonStabilitySpec
    )
    manifest = single_object(
        request, loaded, "comparison_case_manifest", ComparisonCaseManifest
    )
    bundles = objects_for_role(
        request, loaded, "product_evidence_bundle", ProductEvidenceBundle
    )
    reasons: list[str] = []
    if spec.comparison_ref != manifest.ref:
        reasons.append("comparison_spec_manifest_binding_mismatch")
    if manifest.spec_ref != spec.ref:
        reasons.append("comparison_manifest_spec_binding_mismatch")
    expected_refs = {
        ref.ref for group in manifest.groups for ref in group.bundle_refs
    }
    actual_refs = {bundle.ref.ref for bundle in bundles}
    if len(actual_refs) != len(bundles):
        reasons.append("duplicate_product_evidence_bundle_ref")
    if expected_refs != actual_refs:
        reasons.append("comparison_manifest_bundle_set_mismatch")
    groups = {group.group_id: group for group in manifest.groups}
    case_refs: set[str] = set()
    analysis_units: set[str] = set()
    contracts = {item.metric_id: item for item in spec.metric_contracts}
    for bundle in bundles:
        if bundle.comparison_ref != manifest.ref:
            reasons.append("bundle_comparison_binding_mismatch")
        group = groups.get(bundle.group_id)
        if group is None or bundle.ref not in group.bundle_refs:
            reasons.append("bundle_group_binding_mismatch")
            continue
        if bundle.product_definition.ref != group.product_definition_ref:
            reasons.append("bundle_product_definition_binding_mismatch")
        if bundle.target_stage_ref != group.target_stage_ref:
            reasons.append("bundle_target_stage_binding_mismatch")
        case_ref = bundle.product_case.ref.ref
        if case_ref in case_refs:
            reasons.append("duplicate_product_case_ref")
        case_refs.add(case_ref)
        analysis_ref = bundle.product_case.sample_or_preparation_ref.ref
        if analysis_ref in analysis_units:
            reasons.append("duplicate_analysis_unit_ref")
        analysis_units.add(analysis_ref)
        if set(item.metric_id for item in bundle.metrics) != set(contracts):
            reasons.append("bundle_metric_contract_set_mismatch")
        for metric in bundle.metrics:
            contract = contracts.get(metric.metric_id)
            if contract is None:
                continue
            if (
                metric.measurement_spec_ref != contract.measurement_spec_ref
                or metric.unit != contract.unit
                or metric.denominator_kind != contract.denominator_kind
            ):
                reasons.append("bundle_metric_contract_mismatch")
        if bundle.sufficiency_summary_ref is not None and not (
            bundle.sufficiency_summary_ref.startswith(
                "case-evidence-readiness-summary:"
            )
            or bundle.sufficiency_summary_ref.startswith(
                "evidence-sufficiency-profile:"
            )
        ):
            reasons.append("evidence_sufficiency_ref_invalid")
    return reasons


def _input_hash(request: ToolRequestV2, spec: ToolPackageSpecV2) -> str:
    payload = {
        "tool_id": spec.tool_id,
        "tool_version": spec.version,
        "environment_spec_id": spec.environment_spec_id,
        "result_schema_ref": spec.result_schema_ref,
        "object_inputs": [
            {
                "role": ref.role,
                "schema_ref": ref.schema_ref,
                "object_version": ref.object_version,
                "sha256": ref.sha256,
                "media_type": ref.media_type,
            }
            for ref in sorted(
                request.object_inputs,
                key=lambda item: (
                    item.role,
                    item.schema_ref,
                    item.object_version,
                    item.sha256,
                    item.media_type,
                ),
            )
        ],
    }
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()




def _failed_run(
    request: ToolRequestV2,
    spec: ToolPackageSpecV2,
    reasons: list[str],
    *,
    input_hash: str | None = None,
) -> ToolRunV2:
    return failed_v2_run(
        request,
        spec,
        reasons,
        result_schema_ref=RESULT_SCHEMA_REF,
        fingerprint_input_key="p0_07_object_inputs",
        input_hash=input_hash,
    )


def _failed_v1_request(
    request: ToolRequest, spec: ToolPackageSpecV2
) -> ToolRunV2:
    return _failed_run(
        request_v2_from_v1(request), spec, ["tool_request_v2_required"]
    )
