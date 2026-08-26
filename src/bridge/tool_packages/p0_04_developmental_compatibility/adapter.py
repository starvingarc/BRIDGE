from __future__ import annotations

import hashlib
from dataclasses import dataclass

from bridge.tool_packages._configurable_contracts import (
    ProductCase,
    ProductDefinitionCard,
)
from bridge.tool_packages._structured_runtime import (
    LoadedInputs,
    StructuredInputError,
    canonical_json_bytes,
    directory_state,
    failed_v2_run,
    load_structured_inputs,
    request_v2_from_v1,
    single_object,
)
from bridge.tool_packages._structured_runtime import (
    publish_single_json as _publish_single_json,
)
from bridge.tool_packages.p0_04_developmental_compatibility.executor import (
    evaluate_developmental_compatibility,
)
from bridge.tool_packages.p0_04_developmental_compatibility.models import (
    DevelopmentStateMap,
    DevelopmentTimepointSeries,
    DevelopmentWindowSpec,
)
from bridge.toolkit.contracts import (
    ArtifactManifest,
    CellStateEvidenceProfileV2,
    EligibilityResult,
    ExecutionState,
    FrozenModel,
    ImplementationState,
    MeasurementSpecV2,
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
    "development_state_map": (
        "bridge://schemas/development-state-map/v0.1",
        DevelopmentStateMap,
    ),
    "measurement_spec": (
        "bridge://schemas/measurement-spec/v0.2",
        MeasurementSpecV2,
    ),
    "cell_state_evidence_profile": (
        "bridge://schemas/cell-state-evidence-profile/v0.2",
        CellStateEvidenceProfileV2,
    ),
    "development_timepoint_series": (
        "bridge://schemas/development-timepoint-series/v0.1",
        DevelopmentTimepointSeries,
    ),
}
REQUIRED_ROLES = tuple(role for role in ROLE_MODELS if role != "development_timepoint_series")
FIXED_VERSIONS = {
    "product_case": "0.1.0",
    "product_definition_card": "0.1.0",
    "development_window_spec": "0.1.0",
    "development_state_map": "0.1.0",
    "cell_state_evidence_profile": "0.2.0",
    "development_timepoint_series": "0.1.0",
}
COMPOSITION_STATES = {"shadow", "not_assessed", "unavailable", "unknown", "missing"}


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
        state_map = single_object(
            request, loaded, "development_state_map", DevelopmentStateMap
        )
        measurement_spec = single_object(
            request, loaded, "measurement_spec", MeasurementSpecV2
        )
        cell_state_profile = single_object(
            request,
            loaded,
            "cell_state_evidence_profile",
            CellStateEvidenceProfileV2,
        )
        series = _optional_single_object(
            request, loaded, "development_timepoint_series", DevelopmentTimepointSeries
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
                state_map=state_map,
                measurement_spec=measurement_spec,
                cell_state_profile=cell_state_profile,
                cell_state_profile_version=_version_for(request, "cell_state_evidence_profile"),
                timepoint_series=series,
                input_sha256_by_role={ref.role: ref.sha256 for ref in request.object_inputs},
            )
        except ValueError as exc:
            reason = str(exc)
            if not reason.startswith("cell_state_composition_"):
                reason = "developmental_compatibility_evaluation_failed"
            return _failed_run(request, spec, [reason], input_hash=input_hash)
        payload = canonical_json_bytes(result.model_dump(mode="json"), indent=2)
        try:
            output_file = _publish_single_json(
                request=request,
                run_id=run_id,
                filename="developmental_compatibility_result.json",
                payload=payload,
            )
        except StructuredInputError as exc:
            return _failed_run(request, spec, [exc.reason_code], input_hash=input_hash)
        artifact = ArtifactManifest(
            artifact_id=f"artifact:{run_id}:developmental-compatibility-result",
            kind="developmental_compatibility_result",
            path=output_file,
            media_type="application/json",
            sha256=hashlib.sha256(payload).hexdigest(),
            evidence_ids=result.evidence_refs,
        )
        execution_state = (
            ExecutionState.PARTIAL
            if result.result_state in {"partial", "not_assessed"}
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


def _envelope_reasons(request: ToolRequestV2, spec: ToolPackageSpecV2) -> list[str]:
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
    for role in REQUIRED_ROLES:
        if roles.count(role) != 1:
            reasons.append(f"exactly_one_{role}_required")
    if roles.count("development_timepoint_series") > 1:
        reasons.append("at_most_one_development_timepoint_series_allowed")
    if any(role not in ROLE_MODELS for role in roles):
        reasons.append("unsupported_object_input_role")
    for ref in request.object_inputs:
        contract = ROLE_MODELS.get(ref.role)
        if contract is not None and ref.schema_ref != contract[0]:
            reasons.append("object_input_schema_mismatch")
        fixed_version = FIXED_VERSIONS.get(ref.role)
        if fixed_version is not None and ref.object_version != fixed_version:
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
    version = value.version if isinstance(value, MeasurementSpecV2) else getattr(
        value, "object_version", None
    )
    if version is None:
        version = FIXED_VERSIONS.get(ref.role)
    if version != ref.object_version:
        raise StructuredInputError("object_input_version_mismatch")


def _binding_reasons(request: ToolRequestV2, loaded: LoadedInputs) -> list[str]:
    product_case = single_object(request, loaded, "product_case", ProductCase)
    product_definition = single_object(
        request, loaded, "product_definition_card", ProductDefinitionCard
    )
    window_spec = single_object(
        request, loaded, "development_window_spec", DevelopmentWindowSpec
    )
    state_map = single_object(request, loaded, "development_state_map", DevelopmentStateMap)
    measurement_spec = single_object(request, loaded, "measurement_spec", MeasurementSpecV2)
    profile = single_object(
        request, loaded, "cell_state_evidence_profile", CellStateEvidenceProfileV2
    )
    series = _optional_single_object(
        request, loaded, "development_timepoint_series", DevelopmentTimepointSeries
    )
    reasons: list[str] = []
    if product_case.product_definition_ref != product_definition.ref:
        reasons.append("product_definition_binding_mismatch")
    if window_spec.product_definition_ref != product_definition.ref:
        reasons.append("window_product_definition_binding_mismatch")
    if state_map.product_definition_ref != product_definition.ref:
        reasons.append("state_map_product_definition_binding_mismatch")
    if window_spec.state_map_ref != state_map.ref:
        reasons.append("window_state_map_binding_mismatch")
    if state_map.annotation_vocabulary_ref != profile.annotation_vocabulary_ref:
        reasons.append("state_map_annotation_vocabulary_mismatch")
    if product_case.assay not in product_definition.supported_assays:
        reasons.append("product_case_assay_not_supported")
    if product_case.assay not in window_spec.applicable_assays:
        reasons.append("window_assay_not_supported")
    if (
        product_case.measurement_spec_ref.object_id != measurement_spec.measurement_spec_id
        or product_case.measurement_spec_ref.object_version != measurement_spec.version
    ):
        reasons.append("measurement_spec_binding_mismatch")
    if profile.measurement_spec_id != measurement_spec.measurement_spec_id:
        reasons.append("cell_state_measurement_spec_binding_mismatch")
    if profile.measurement_spec_version != measurement_spec.version:
        reasons.append("cell_state_measurement_spec_version_mismatch")
    if profile.assay != product_case.assay:
        reasons.append("cell_state_assay_binding_mismatch")
    if profile.input_data_view is not None and (
        profile.input_data_view.sample_or_preparation_ref
        != product_case.sample_or_preparation_ref.ref
    ):
        reasons.append("product_case_data_view_binding_mismatch")
    state = profile.composition.get("state")
    if state not in COMPOSITION_STATES:
        reasons.append("cell_state_composition_state_invalid")
    if series is not None:
        if series.product_case_ref != product_case.ref:
            reasons.append("timepoint_series_product_case_binding_mismatch")
        if series.state_map_ref != state_map.ref:
            reasons.append("timepoint_series_state_map_binding_mismatch")
    return reasons


def _optional_single_object(
    request: ToolRequestV2,
    loaded: LoadedInputs,
    role: str,
    model: type[FrozenModel],
) -> FrozenModel | None:
    refs = [ref for ref in request.object_inputs if ref.role == role]
    if not refs:
        return None
    return single_object(request, loaded, role, model)


def _version_for(request: ToolRequestV2, role: str) -> str:
    return next(ref.object_version for ref in request.object_inputs if ref.role == role)


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
        fingerprint_input_key="p0_04_object_inputs",
        input_hash=input_hash,
    )


def _failed_v1_request(
    request: ToolRequest, spec: ToolPackageSpecV2
) -> ToolRunV2:
    return _failed_run(
        request_v2_from_v1(request), spec, ["tool_request_v2_required"]
    )
