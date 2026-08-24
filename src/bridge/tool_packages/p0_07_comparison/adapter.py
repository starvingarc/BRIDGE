from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib

from bridge.tool_packages._structured_runtime import (
    LoadedInputs,
    StructuredInputError,
    canonical_json_bytes,
    directory_state,
    failed_v2_run,
    load_structured_inputs,
    publish_single_json,
    objects_for_role,
    single_object,
)
from bridge.tool_packages.p0_08_evidence_sufficiency.models import (
    EvidenceSufficiencyRunResult,
)
from bridge.tool_packages._configurable_contracts import (
    BiologicalUnitManifest,
    ProductCase,
    VersionedObjectRef,
)
from bridge.tool_packages.p0_07_comparison.executor import evaluate_comparison
from bridge.tool_packages.p0_07_comparison.models import (
    ComparisonEvidenceBundle,
    ComparisonSpec,
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


RESULT_SCHEMA_REF = "bridge://schemas/comparison-record/v0.1"
ROLE_MODELS: dict[str, tuple[str, type[FrozenModel]]] = {
    "product_case": (
        "bridge://schemas/product-case/v0.1",
        ProductCase,
    ),
    "comparison_spec": (
        "bridge://schemas/comparison-spec/v0.1",
        ComparisonSpec,
    ),
    "comparison_evidence_bundle": (
        "bridge://schemas/comparison-evidence-bundle/v0.1",
        ComparisonEvidenceBundle,
    ),
    "evidence_sufficiency_run_result": (
        "bridge://schemas/evidence-sufficiency-run-result/v0.1",
        EvidenceSufficiencyRunResult,
    ),
    "biological_unit_manifest": (
        "bridge://schemas/biological-unit-manifest/v0.1",
        BiologicalUnitManifest,
    ),
}


@dataclass(frozen=True)
class ComparisonAdapter:
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
        if not eligibility.eligible:
            return _failed_run(request, spec, eligibility.reason_codes)
        loaded, reasons = _load_inputs(request.object_inputs)
        if loaded is None or reasons:
            return _failed_run(request, spec, reasons)
        comparison_spec = single_object(
            request, loaded, "comparison_spec", ComparisonSpec
        )
        evidence_bundle = single_object(
            request,
            loaded,
            "comparison_evidence_bundle",
            ComparisonEvidenceBundle,
        )
        sufficiency_results = objects_for_role(
            request,
            loaded,
            "evidence_sufficiency_run_result",
            EvidenceSufficiencyRunResult,
        )
        biological_unit_manifests = objects_for_role(
            request,
            loaded,
            "biological_unit_manifest",
            BiologicalUnitManifest,
        )
        product_cases = objects_for_role(
            request,
            loaded,
            "product_case",
            ProductCase,
        )
        input_hash = _input_hash(request, spec)
        run_id = f"run-{input_hash[:16]}"
        try:
            result = evaluate_comparison(
                run_id=run_id,
                tool_version=spec.version,
                comparison_spec=comparison_spec,
                evidence_bundle=evidence_bundle,
                sufficiency_results=sufficiency_results,
                biological_unit_manifests=biological_unit_manifests,
                product_cases=product_cases,
                input_sha256_by_role={
                    "comparison_spec": next(
                        ref.sha256
                        for ref in request.object_inputs
                        if ref.role == "comparison_spec"
                    ),
                    "comparison_evidence_bundle": next(
                        ref.sha256
                        for ref in request.object_inputs
                        if ref.role == "comparison_evidence_bundle"
                    ),
                    "product_cases": sorted(
                        ref.sha256
                        for ref in request.object_inputs
                        if ref.role == "product_case"
                    ),
                    "evidence_sufficiency_run_results": sorted(
                        ref.sha256
                        for ref in request.object_inputs
                        if ref.role == "evidence_sufficiency_run_result"
                    ),
                    "biological_unit_manifests": sorted(
                        ref.sha256
                        for ref in request.object_inputs
                        if ref.role == "biological_unit_manifest"
                    ),
                },
            )
        except ValueError:
            return _failed_run(
                request,
                spec,
                ["comparison_evaluation_failed"],
                input_hash=input_hash,
            )
        payload = canonical_json_bytes(result.model_dump(mode="json"), indent=2)
        try:
            output_file = publish_single_json(
                request=request,
                run_id=run_id,
                filename="comparison_record.json",
                payload=payload,
            )
        except StructuredInputError as exc:
            return _failed_run(
                request,
                spec,
                [exc.reason_code],
                input_hash=input_hash,
            )
        artifact = ArtifactManifest(
            artifact_id=f"artifact:{run_id}:comparison-record",
            kind="comparison_record",
            path=output_file,
            media_type="application/json",
            sha256=hashlib.sha256(payload).hexdigest(),
            evidence_ids=result.evidence_refs,
        )
        return ToolRunV2(
            run_id=run_id,
            request=request,
            implementation_state=ImplementationState.IMPLEMENTED,
            execution_state=(
                ExecutionState.PARTIAL
                if result.result_state == "partial"
                else ExecutionState.SUCCEEDED
            ),
            tool_version=spec.version,
            environment_spec_id=spec.environment_spec_id,
            input_hash=input_hash,
            created_at=datetime(1970, 1, 1, tzinfo=timezone.utc),
            measurements=[],
            artifacts=[artifact],
            visualizations=[],
            result_schema_ref=RESULT_SCHEMA_REF,
            result=result.model_dump(mode="json"),
            reason_codes=result.reason_codes,
            warnings=[],
        )


adapter = ComparisonAdapter()


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
    for role in ROLE_MODELS:
        expected = (
            2
            if role
            in {
                "product_case",
                "evidence_sufficiency_run_result",
                "biological_unit_manifest",
            }
            else 1
        )
        if roles.count(role) != expected:
            cardinality = "two" if expected == 2 else "one"
            reasons.append(f"exactly_{cardinality}_{role}_required")
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
    version = getattr(value, "object_version", None)
    if isinstance(value, EvidenceSufficiencyRunResult):
        version = value.result_version
    if version != ref.object_version:
        raise StructuredInputError("object_input_version_mismatch")


def _binding_reasons(
    request: ToolRequestV2,
    loaded: LoadedInputs,
) -> list[str]:
    comparison_spec = single_object(
        request, loaded, "comparison_spec", ComparisonSpec
    )
    evidence_bundle = single_object(
        request,
        loaded,
        "comparison_evidence_bundle",
        ComparisonEvidenceBundle,
    )
    sufficiency_results = objects_for_role(
        request,
        loaded,
        "evidence_sufficiency_run_result",
        EvidenceSufficiencyRunResult,
    )
    biological_unit_manifests = objects_for_role(
        request,
        loaded,
        "biological_unit_manifest",
        BiologicalUnitManifest,
    )
    product_cases = objects_for_role(
        request,
        loaded,
        "product_case",
        ProductCase,
    )
    reasons: list[str] = []
    spec_refs = {item.product_case_ref.ref for item in comparison_spec.cases}
    evidence_refs = {item.product_case_ref.ref for item in evidence_bundle.cases}
    if spec_refs != evidence_refs:
        reasons.append("comparison_case_binding_mismatch")
    product_cases_by_ref = {item.ref.ref: item for item in product_cases}
    if set(product_cases_by_ref) != evidence_refs:
        reasons.append("comparison_product_case_binding_mismatch")
    results_by_case = {
        item.case_summary.product_case_ref.ref: item
        for item in sufficiency_results
        if item.case_summary.product_case_ref is not None
    }
    if set(results_by_case) != evidence_refs:
        reasons.append("comparison_sufficiency_case_binding_mismatch")
    manifests_by_ref = {item.ref.ref: item for item in biological_unit_manifests}
    manifest_sha_by_ref = {
        manifests_by_ref_value.ref.ref: ref.sha256
        for ref in request.object_inputs
        if ref.role == "biological_unit_manifest"
        for manifests_by_ref_value in [
            loaded.objects_by_input_id.get(ref.input_id)
        ]
        if isinstance(manifests_by_ref_value, BiologicalUnitManifest)
    }
    bound_manifest_refs = {
        product_case.biological_unit_manifest_ref.ref
        for product_case in product_cases
        if product_case.biological_unit_manifest_ref is not None
    }
    if (
        len(bound_manifest_refs) != len(product_cases)
        or bound_manifest_refs != set(manifests_by_ref)
    ):
        reasons.append("comparison_biological_unit_manifest_binding_mismatch")
    if len(biological_unit_manifests) == 2:
        if len(
            {
                item.unit_identity_namespace_ref.ref
                for item in biological_unit_manifests
            }
        ) != 1:
            reasons.append("comparison_biological_unit_namespace_mismatch")
        if len(
            {item.independence_scope_ref.ref for item in biological_unit_manifests}
        ) != 1:
            reasons.append("comparison_biological_unit_scope_mismatch")
    for case in evidence_bundle.cases:
        product_case = product_cases_by_ref.get(case.product_case_ref.ref)
        if product_case is not None:
            manifest_ref = product_case.biological_unit_manifest_ref
            manifest = (
                manifests_by_ref.get(manifest_ref.ref)
                if manifest_ref is not None
                else None
            )
            declared_units = (
                {item.analysis_unit_ref.ref for item in manifest.unit_bindings}
                if manifest is not None
                else set()
            )
            supplied_units = {
                item.preparation_ref.ref for item in case.preparations
            }
            if not supplied_units or not supplied_units <= declared_units:
                reasons.append("comparison_biological_unit_binding_mismatch")
            if manifest is not None and (
                product_case.biological_unit_manifest_sha256
                != manifest_sha_by_ref.get(manifest.ref.ref)
                or product_case.independence_scope_ref
                != manifest.independence_scope_ref
                or {item.ref for item in product_case.biological_unit_refs}
                != {item.ref for item in manifest.independence_group_refs}
            ):
                reasons.append(
                    "comparison_biological_unit_manifest_binding_mismatch"
                )
            if (
                case.contract_snapshot.product_definition_ref
                != product_case.product_definition_ref
                or case.contract_snapshot.measurement_spec_ref
                != product_case.measurement_spec_ref
            ):
                reasons.append("comparison_product_case_contract_mismatch")
        sufficiency_result = results_by_case.get(case.product_case_ref.ref)
        if sufficiency_result is None:
            continue
        summary = sufficiency_result.case_summary
        expected_ref = VersionedObjectRef(
            object_id=summary.summary_id,
            object_version=summary.summary_version,
        )
        if case.sufficiency_summary_ref != expected_ref:
            reasons.append("comparison_sufficiency_summary_ref_mismatch")
    independence_sets: list[set[str]] = []
    for case in evidence_bundle.cases:
        product_case = product_cases_by_ref.get(case.product_case_ref.ref)
        manifest = (
            manifests_by_ref.get(product_case.biological_unit_manifest_ref.ref)
            if product_case is not None
            and product_case.biological_unit_manifest_ref is not None
            else None
        )
        by_analysis = (
            {
                item.analysis_unit_ref.ref: item.independence_group_ref.ref
                for item in manifest.unit_bindings
            }
            if manifest is not None
            else {}
        )
        independence_sets.append(
            {
                by_analysis[item.preparation_ref.ref]
                for item in case.preparations
                if item.preparation_ref.ref in by_analysis
            }
        )
    if len(independence_sets) == 2 and independence_sets[0] & independence_sets[1]:
        reasons.append("comparison_biological_unit_overlap")
    if any(
        case.contract_snapshot.score_contract_ref is not None
        for case in evidence_bundle.cases
    ):
        reasons.append("score_contract_not_supported")
    return reasons


def _input_hash(request: ToolRequestV2, spec: ToolPackageSpecV2) -> str:
    payload = {
        "tool_id": spec.tool_id,
        "tool_version": spec.version,
        "environment_spec_id": spec.environment_spec_id,
        "structured_inputs": [
            {
                "role": ref.role,
                "schema_ref": ref.schema_ref,
                "object_version": ref.object_version,
                "sha256": ref.sha256,
                "media_type": ref.media_type,
            }
            for ref in sorted(
                request.object_inputs,
                key=lambda item: (item.role, item.sha256),
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
        fingerprint_input_key="structured_inputs",
        input_hash=input_hash,
    )


def _failed_v1_request(request: ToolRequest, spec: ToolPackageSpecV2) -> ToolRunV2:
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
