from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re

from bridge.tool_packages._structured_runtime import (
    LoadedInputs,
    StructuredInputError,
    canonical_json_bytes,
    directory_state,
    failed_v2_run,
    load_structured_inputs,
    publish_single_json,
    single_object,
)
from bridge.tool_packages._configurable_contracts import (
    ProductCase,
    ProductDefinitionCard,
    parse_composition,
)
from bridge.tool_packages.p0_04_developmental.executor import (
    evaluate_developmental_compatibility,
)
from bridge.tool_packages.p0_04_developmental.models import DevelopmentWindowSpec
from bridge.toolkit.contracts import (
    ArtifactManifest,
    CellStateEvidenceProfile,
    EligibilityResult,
    ExecutionState,
    FrozenModel,
    ImplementationState,
    QCReadinessProfile,
    ReadinessState,
    StructuredInputRef,
    ToolPackageSpecV2,
    ToolRequest,
    ToolRequestV2,
    ToolRunV2,
)


RESULT_SCHEMA_REF = "bridge://schemas/developmental-compatibility-result/v0.1"
ROLE_MODELS: dict[str, tuple[str, type[FrozenModel]]] = {
    "product_case": ("bridge://schemas/product-case/v0.1", ProductCase),
    "product_definition_card": (
        "bridge://schemas/product-definition-card/v0.1",
        ProductDefinitionCard,
    ),
    "development_window_spec": (
        "bridge://schemas/development-window-spec/v0.1",
        DevelopmentWindowSpec,
    ),
    "cell_state_evidence_profile": (
        "bridge://schemas/cell-state-evidence-profile/v0.1",
        CellStateEvidenceProfile,
    ),
    "qc_readiness_profile": (
        "bridge://schemas/qc-readiness-profile/v0.1",
        QCReadinessProfile,
    ),
}
EVIDENCE_REF = re.compile(r"^evidence:[A-Za-z0-9._:-]+$")
CELL_STATE_PROFILE_REF = re.compile(r"^cell-state-profile:[A-Za-z0-9._:-]+$")
QC_PROFILE_REF = re.compile(r"^qc-profile:[A-Za-z0-9._:-]+$")


@dataclass(frozen=True)
class DevelopmentalCompatibilityAdapter:
    def check_eligibility(
        self, request: ToolRequestV2, spec: ToolPackageSpecV2
    ) -> EligibilityResult:
        if not isinstance(request, ToolRequestV2):
            tool_id = request.tool_id if isinstance(request, ToolRequest) else "P0-04"
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

        product_case = single_object(request, loaded, "product_case", ProductCase)
        product_definition = single_object(
            request, loaded, "product_definition_card", ProductDefinitionCard
        )
        window_spec = single_object(
            request, loaded, "development_window_spec", DevelopmentWindowSpec
        )
        cell_state_profile = single_object(
            request,
            loaded,
            "cell_state_evidence_profile",
            CellStateEvidenceProfile,
        )
        qc_profile = single_object(
            request, loaded, "qc_readiness_profile", QCReadinessProfile
        )
        input_hash = _input_hash(request, spec)
        run_id = f"run-{input_hash[:16]}"
        try:
            result = evaluate_developmental_compatibility(
                run_id=run_id,
                tool_version=spec.version,
                product_case=product_case,
                product_definition=product_definition,
                window_spec=window_spec,
                cell_state_profile=cell_state_profile,
                cell_state_profile_version=_input_version(
                    request, "cell_state_evidence_profile"
                ),
                qc_profile=qc_profile,
                qc_profile_version=_input_version(request, "qc_readiness_profile"),
                input_sha256_by_role={
                    ref.role: ref.sha256 for ref in request.object_inputs
                },
            )
        except ValueError as exc:
            reason = str(exc)
            if not reason.startswith("cell_state_composition_"):
                reason = "developmental_evaluation_failed"
            return _failed_run(request, spec, [reason], input_hash=input_hash)

        payload = canonical_json_bytes(result.model_dump(mode="json"), indent=2)
        try:
            output_file = publish_single_json(
                request=request,
                run_id=run_id,
                filename="developmental_compatibility_result.json",
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
            artifact_id=f"artifact:{run_id}:developmental-result",
            kind="developmental_compatibility_result",
            path=output_file,
            media_type="application/json",
            sha256=hashlib.sha256(payload).hexdigest(),
            evidence_ids=result.evidence_refs,
        )
        execution_state = (
            ExecutionState.PARTIAL
            if result.result_state == "partial"
            else ExecutionState.SUCCEEDED
        )
        return ToolRunV2(
            run_id=run_id,
            request=request,
            implementation_state=ImplementationState.IMPLEMENTED,
            execution_state=execution_state,
            tool_version=spec.version,
            environment_spec_id=spec.environment_spec_id,
            input_hash=input_hash,
            created_at=product_case.created_at,
            measurements=[],
            artifacts=[artifact],
            visualizations=[],
            result_schema_ref=RESULT_SCHEMA_REF,
            result=result.model_dump(mode="json"),
            reason_codes=result.reason_codes,
            warnings=[],
        )


adapter = DevelopmentalCompatibilityAdapter()


def _envelope_reasons(
    request: ToolRequestV2, spec: ToolPackageSpecV2
) -> list[str]:
    reasons: list[str] = []
    if request.tool_version is not None and request.tool_version != spec.version:
        reasons.append("tool_version_mismatch")
    if request.assets:
        reasons.append("p0_04_expression_assets_forbidden")
    if request.measurement_spec_ref is not None:
        reasons.append("p0_04_measurement_spec_parameter_forbidden")
    if request.parameters:
        reasons.append("p0_04_parameters_forbidden")
    if request.random_seed != 0:
        reasons.append("p0_04_random_seed_forbidden")
    roles = [ref.role for ref in request.object_inputs]
    for role in ROLE_MODELS:
        if roles.count(role) != 1:
            reasons.append(f"exactly_one_{role}_required")
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
    if version is None and isinstance(value, (CellStateEvidenceProfile, QCReadinessProfile)):
        version = "0.1.0"
    if version != ref.object_version:
        raise StructuredInputError("object_input_version_mismatch")


def _binding_reasons(
    request: ToolRequestV2,
    loaded: LoadedInputs,
) -> list[str]:
    product_case = single_object(request, loaded, "product_case", ProductCase)
    product_definition = single_object(
        request, loaded, "product_definition_card", ProductDefinitionCard
    )
    window_spec = single_object(
        request, loaded, "development_window_spec", DevelopmentWindowSpec
    )
    cell_state_profile = single_object(
        request,
        loaded,
        "cell_state_evidence_profile",
        CellStateEvidenceProfile,
    )
    qc_profile = single_object(
        request, loaded, "qc_readiness_profile", QCReadinessProfile
    )
    reasons: list[str] = []
    if product_case.product_definition_ref != product_definition.ref:
        reasons.append("product_definition_binding_mismatch")
    if window_spec.product_definition_ref != product_definition.ref:
        reasons.append("development_window_product_definition_mismatch")
    if window_spec.annotation_vocabulary_ref != cell_state_profile.annotation_vocabulary_ref:
        reasons.append("annotation_vocabulary_binding_mismatch")
    if product_case.assay not in product_definition.supported_assays:
        reasons.append("product_case_assay_not_supported")
    if product_case.assay not in window_spec.applicable_assays:
        reasons.append("development_window_assay_not_supported")
    if cell_state_profile.assay != product_case.assay:
        reasons.append("cell_state_profile_assay_mismatch")
    if qc_profile.assay != product_case.assay:
        reasons.append("qc_profile_assay_mismatch")
    if cell_state_profile.measurement_spec_id != product_case.measurement_spec_ref.object_id:
        reasons.append("measurement_spec_binding_mismatch")
    if qc_profile.readiness_state in {
        ReadinessState.BLOCKED,
        ReadinessState.NOT_ASSESSED,
        ReadinessState.NOT_APPLICABLE,
    }:
        reasons.append("qc_not_ready_for_developmental_evidence")
    try:
        parse_composition(cell_state_profile)
    except ValueError as exc:
        reasons.append(str(exc))
    if any(
        not EVIDENCE_REF.fullmatch(value)
        for value in [*cell_state_profile.evidence_ids, *qc_profile.evidence_ids]
    ):
        reasons.append("unsafe_evidence_reference")
    if not CELL_STATE_PROFILE_REF.fullmatch(cell_state_profile.profile_id):
        reasons.append("unsafe_cell_state_profile_reference")
    if not QC_PROFILE_REF.fullmatch(qc_profile.profile_id):
        reasons.append("unsafe_qc_profile_reference")
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


def _input_version(request: ToolRequestV2, role: str) -> str:
    return next(ref.object_version for ref in request.object_inputs if ref.role == role)


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
