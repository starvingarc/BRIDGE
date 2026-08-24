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
from bridge.tool_packages._configurable_contracts import ProductCase
from bridge.tool_packages.p0_12_graft_assessment.executor import (
    evaluate_graft_assessment,
)
from bridge.tool_packages.p0_12_graft_assessment.models import (
    GraftAssessmentSpec,
    GraftEvidenceBundle,
    GraftLineageManifest,
)
from bridge.toolkit.contracts import (
    ArtifactManifest,
    EligibilityResult,
    ExecutionState,
    FrozenModel,
    ImplementationState,
    MeasurementSpec,
    StructuredInputRef,
    ToolPackageSpecV2,
    ToolRequest,
    ToolRequestV2,
    ToolRunV2,
)


RESULT_SCHEMA_REF = "bridge://schemas/graft-assessment/v0.1"
ROLE_MODELS: dict[str, tuple[str, type[FrozenModel]]] = {
    "product_case": ("bridge://schemas/product-case/v0.1", ProductCase),
    "graft_measurement_spec": (
        "bridge://schemas/measurement-spec/v0.1",
        MeasurementSpec,
    ),
    "graft_lineage_manifest": (
        "bridge://schemas/graft-lineage-manifest/v0.1",
        GraftLineageManifest,
    ),
    "graft_assessment_spec": (
        "bridge://schemas/graft-assessment-spec/v0.1",
        GraftAssessmentSpec,
    ),
    "graft_evidence_bundle": (
        "bridge://schemas/graft-evidence-bundle/v0.1",
        GraftEvidenceBundle,
    ),
}


@dataclass(frozen=True)
class GraftAssessmentAdapter:
    def check_eligibility(
        self, request: ToolRequestV2, spec: ToolPackageSpecV2
    ) -> EligibilityResult:
        if not isinstance(request, ToolRequestV2):
            tool_id = request.tool_id if isinstance(request, ToolRequest) else "P0-12"
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
        assessment_spec = single_object(
            request, loaded, "graft_assessment_spec", GraftAssessmentSpec
        )
        evidence_bundle = single_object(
            request, loaded, "graft_evidence_bundle", GraftEvidenceBundle
        )
        graft_measurement_spec = single_object(
            request, loaded, "graft_measurement_spec", MeasurementSpec
        )
        lineage_manifests = objects_for_role(
            request, loaded, "graft_lineage_manifest", GraftLineageManifest
        )
        lineage_manifest = lineage_manifests[0] if lineage_manifests else None
        input_hash = _input_hash(request, spec)
        run_id = f"run-{input_hash[:16]}"
        try:
            result = evaluate_graft_assessment(
                run_id=run_id,
                tool_version=spec.version,
                assessment_spec=assessment_spec,
                evidence_bundle=evidence_bundle,
                graft_measurement_spec=graft_measurement_spec,
                lineage_manifest=lineage_manifest,
                input_sha256_by_role={
                    ref.role: ref.sha256 for ref in request.object_inputs
                },
            )
        except ValueError:
            return _failed_run(
                request,
                spec,
                ["graft_assessment_failed"],
                input_hash=input_hash,
            )
        payload = canonical_json_bytes(result.model_dump(mode="json"), indent=2)
        try:
            output_file = publish_single_json(
                request=request,
                run_id=run_id,
                filename="graft_assessment.json",
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
            artifact_id=f"artifact:{run_id}:graft-assessment",
            kind="graft_assessment",
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


adapter = GraftAssessmentAdapter()


def _envelope_reasons(
    request: ToolRequestV2, spec: ToolPackageSpecV2
) -> list[str]:
    reasons: list[str] = []
    if request.tool_version is not None and request.tool_version != spec.version:
        reasons.append("tool_version_mismatch")
    if request.assets:
        reasons.append("p0_12_expression_assets_not_supported")
    if request.measurement_spec_ref is not None:
        reasons.append("p0_12_measurement_spec_parameter_forbidden")
    if request.parameters:
        reasons.append("p0_12_parameters_forbidden")
    if request.random_seed != 0:
        reasons.append("p0_12_random_seed_forbidden")
    roles = [ref.role for ref in request.object_inputs]
    for role in ROLE_MODELS:
        if role == "graft_lineage_manifest":
            continue
        if roles.count(role) != 1:
            reasons.append(f"exactly_one_{role}_required")
    if roles.count("graft_lineage_manifest") > 1:
        reasons.append("at_most_one_graft_lineage_manifest_allowed")
    if any(role not in ROLE_MODELS for role in roles):
        reasons.append("unsupported_object_input_role")
    for ref in request.object_inputs:
        contract = ROLE_MODELS.get(ref.role)
        if contract is not None and ref.schema_ref != contract[0]:
            reasons.append("object_input_schema_mismatch")
        if ref.role != "graft_measurement_spec" and ref.object_version != "0.1.0":
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
    if ref.role == "graft_measurement_spec":
        if getattr(value, "version", None) != ref.object_version:
            raise StructuredInputError("object_input_version_mismatch")
        return
    if getattr(value, "object_version", None) != ref.object_version:
        raise StructuredInputError("object_input_version_mismatch")


def _binding_reasons(
    request: ToolRequestV2,
    loaded: LoadedInputs,
) -> list[str]:
    assessment_spec = single_object(
        request, loaded, "graft_assessment_spec", GraftAssessmentSpec
    )
    product_case = single_object(request, loaded, "product_case", ProductCase)
    evidence_bundle = single_object(
        request, loaded, "graft_evidence_bundle", GraftEvidenceBundle
    )
    graft_measurement_spec = single_object(
        request, loaded, "graft_measurement_spec", MeasurementSpec
    )
    lineage_manifests = objects_for_role(
        request, loaded, "graft_lineage_manifest", GraftLineageManifest
    )
    lineage_manifest = lineage_manifests[0] if lineage_manifests else None
    reasons: list[str] = []
    if (
        assessment_spec.product_case_ref != product_case.ref
        or evidence_bundle.product_case_ref != product_case.ref
    ):
        reasons.append("graft_product_case_binding_mismatch")
    if assessment_spec.product_measurement_spec_ref != product_case.measurement_spec_ref:
        reasons.append("product_measurement_spec_binding_mismatch")
    graft_measurement_ref = (
        graft_measurement_spec.measurement_spec_id,
        graft_measurement_spec.version,
    )
    if (
        assessment_spec.graft_measurement_spec_ref.object_id,
        assessment_spec.graft_measurement_spec_ref.object_version,
    ) != graft_measurement_ref:
        reasons.append("graft_measurement_spec_binding_mismatch")
    if (
        graft_measurement_spec.assay not in assessment_spec.allowed_graft_assays
        or graft_measurement_spec.analysis_unit_kind
        not in assessment_spec.allowed_graft_analysis_unit_kinds
        or assessment_spec.required_graft_context
        not in graft_measurement_spec.applicable_contexts
    ):
        reasons.append("graft_measurement_spec_context_not_applicable")
    declared_preparations = set(product_case.biological_unit_refs)
    linked_preparations = {
        unit.originating_preparation_ref
        for unit in evidence_bundle.units
        if unit.originating_preparation_ref is not None
    }
    if linked_preparations and not declared_preparations:
        reasons.append("product_case_biological_units_required")
    elif not linked_preparations.issubset(declared_preparations):
        reasons.append("graft_preparation_product_case_mismatch")
    if evidence_bundle.graft_availability == "provided":
        if lineage_manifest is None:
            reasons.append("graft_lineage_manifest_required")
        bindings = (
            (
                assessment_spec.graft_measurement_spec_ref,
                evidence_bundle.graft_measurement_spec_ref,
            ),
            (assessment_spec.assay_ref, evidence_bundle.assay_ref),
            (assessment_spec.sampling_context_ref, evidence_bundle.sampling_context_ref),
            (assessment_spec.reference_snapshot_ref, evidence_bundle.reference_snapshot_ref),
            (assessment_spec.algorithm_ref, evidence_bundle.algorithm_ref),
        )
        if any(expected != observed for expected, observed in bindings):
            reasons.append("graft_context_binding_mismatch")
        if lineage_manifest is not None:
            if (
                evidence_bundle.graft_lineage_manifest_ref != lineage_manifest.ref
                or lineage_manifest.product_case_ref != product_case.ref
                or lineage_manifest.graft_case_ref != evidence_bundle.graft_case_ref
            ):
                reasons.append("graft_lineage_manifest_binding_mismatch")
            declared_units = {
                (
                    item.unit_ref.ref,
                    item.animal_ref.ref,
                    item.graft_ref.ref,
                    item.timepoint_ref.ref,
                    item.originating_preparation_ref.ref
                    if item.originating_preparation_ref is not None
                    else None,
                    tuple(sorted(item.lineage_evidence_refs)),
                )
                for item in lineage_manifest.unit_bindings
            }
            observed_units = {
                (
                    item.unit_ref.ref,
                    item.animal_ref.ref,
                    item.graft_ref.ref,
                    item.timepoint_ref.ref,
                    item.originating_preparation_ref.ref
                    if item.originating_preparation_ref is not None
                    else None,
                    tuple(sorted(item.linkage_evidence_refs)),
                )
                for item in evidence_bundle.units
            }
            if declared_units != observed_units:
                reasons.append("graft_lineage_unit_assignment_mismatch")
    elif lineage_manifest is not None:
        reasons.append("graft_lineage_manifest_forbidden_when_not_provided")
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
            for ref in sorted(request.object_inputs, key=lambda item: item.role)
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
