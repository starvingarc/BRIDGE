from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from bridge.tool_packages._configurable_contracts import (
    BiologicalUnitAssignmentArtifact,
    BiologicalUnitManifest,
    ProductCase,
    ProductDefinitionCard,
    VersionedObjectRef,
    profile_lineage_reasons,
)
from bridge.tool_packages._structured_runtime import (
    LoadedInputs,
    PublicationError,
    StructuredInputError,
    canonical_json_bytes,
    directory_state,
    failed_v2_run,
    inputs_unchanged,
    load_structured_inputs,
    objects_for_role,
    publish_json_bundle,
    request_v2_from_v1,
    single_object,
)
from bridge.tool_packages.p0_01_input_qc.io import InputAuditError, sha256_path
from bridge.tool_packages.p0_04_developmental_compatibility.executor import (
    evaluate_developmental_compatibility,
)
from bridge.tool_packages.p0_04_developmental_compatibility.method_models import (
    DevelopmentMethodArtifactBinding,
    DevelopmentMethodId,
    DevelopmentMethodSpec,
    MethodExecutionState,
)
from bridge.tool_packages.p0_04_developmental_compatibility.method_runtime import (
    DevelopmentMethodError,
    run_development_methods,
)
from bridge.tool_packages.p0_04_developmental_compatibility.models import (
    DevelopmentStateMap,
    DevelopmentTimepointSeries,
    DevelopmentWindowSpec,
)
from bridge.tool_packages.p0_04_developmental_compatibility.visualization import (
    prepare_developmental_compatibility_visualizations,
)
from bridge.tool_packages.p0_04_developmental_compatibility.visualization_data import (
    build_developmental_compatibility_visualization_data,
)
from bridge.toolkit.contracts import (
    AnnotationVocabulary,
    ArtifactManifest,
    CellStateEvidenceProfileV3,
    EligibilityResult,
    ExecutionState,
    FrozenModel,
    InputAsset,
    InputLevel,
    ImplementationState,
    MeasurementSpecV2,
    QCReadinessProfileV2,
    ReadinessState,
    ReferenceManifest,
    StructuredInputRef,
    ToolPackageSpecV2,
    ToolRequest,
    ToolRequestV2,
    ToolRunV2,
)

RESULT_SCHEMA_REF = "bridge://schemas/developmental-compatibility-result/v0.3"
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
        "bridge://schemas/cell-state-evidence-profile/v0.3",
        CellStateEvidenceProfileV3,
    ),
    "qc_readiness_profile": (
        "bridge://schemas/qc-readiness-profile/v0.2",
        QCReadinessProfileV2,
    ),
    "biological_unit_manifest": (
        "bridge://schemas/biological-unit-manifest/v0.1",
        BiologicalUnitManifest,
    ),
    "biological_unit_assignment": (
        "bridge://schemas/biological-unit-assignment/v0.1",
        BiologicalUnitAssignmentArtifact,
    ),
    "annotation_vocabulary": (
        "bridge://schemas/annotation-vocabulary/v0.1",
        AnnotationVocabulary,
    ),
    "reference_manifest": (
        "bridge://schemas/reference-manifest/v0.1",
        ReferenceManifest,
    ),
    "development_timepoint_series": (
        "bridge://schemas/development-timepoint-series/v0.1",
        DevelopmentTimepointSeries,
    ),
    "development_method_spec": (
        "bridge://schemas/development-method-spec/v0.1",
        DevelopmentMethodSpec,
    ),
}
OPTIONAL_ROLES = {"development_timepoint_series", "development_method_spec"}
REQUIRED_ROLES = frozenset(ROLE_MODELS) - OPTIONAL_ROLES
FIXED_OBJECT_VERSIONS = {
    "product_case": "0.1.0",
    "product_definition_card": "0.1.0",
    "development_window_spec": "0.1.0",
    "development_state_map": "0.1.0",
    "cell_state_evidence_profile": "0.3.0",
    "qc_readiness_profile": "0.2.0",
    "biological_unit_manifest": "0.1.0",
    "biological_unit_assignment": "0.1.0",
    "development_timepoint_series": "0.1.0",
    "development_method_spec": "0.1.0",
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
            CellStateEvidenceProfileV3,
        )
        reference_manifest = single_object(
            request, loaded, "reference_manifest", ReferenceManifest
        )
        biological_unit_assignment = single_object(
            request,
            loaded,
            "biological_unit_assignment",
            BiologicalUnitAssignmentArtifact,
        )
        series_values = objects_for_role(
            request,
            loaded,
            "development_timepoint_series",
            DevelopmentTimepointSeries,
        )
        series = series_values[0] if series_values else None
        input_hash = _input_hash(request, spec)
        run_id = f"run-{input_hash[:16]}"

        method_values = objects_for_role(
            request, loaded, "development_method_spec", DevelopmentMethodSpec
        )
        method_spec = method_values[0] if method_values else None
        method_bundle = None
        method_payload = None
        method_binding = None
        method_reasons: list[str] = []
        reference_stage_support_available = False
        if method_spec is not None:
            asset = request.assets[0]
            try:
                asset_sha256 = sha256_path(asset.path)
            except (OSError, InputAuditError):
                return _failed_run(
                    request,
                    spec,
                    ["expression_asset_unreadable"],
                    input_hash=input_hash,
                )
            if asset_sha256 != asset.checksum:
                return _failed_run(
                    request,
                    spec,
                    ["expression_asset_checksum_mismatch"],
                    input_hash=input_hash,
                )
            try:
                method_bundle = run_development_methods(
                    run_id=run_id,
                    tool_version=spec.version,
                    asset=asset,
                    asset_sha256=asset_sha256,
                    method_spec=method_spec,
                    reference_manifest=reference_manifest,
                    biological_unit_assignment=biological_unit_assignment,
                    reference_manifest_path=_input_path(request, "reference_manifest"),
                    random_seed=request.random_seed,
                    expected_n_observations=cell_state_profile.n_observations,
                    expected_observation_ids_sha256=(
                        cell_state_profile.input_data_view.observation_ids_sha256
                    ),
                )
            except DevelopmentMethodError as exc:
                return _failed_run(
                    request, spec, [exc.reason_code], input_hash=input_hash
                )
            method_payload = canonical_json_bytes(
                method_bundle.model_dump(mode="json"), indent=2
            )
            method_binding = DevelopmentMethodArtifactBinding(
                bundle_ref=VersionedObjectRef(
                    object_id=method_bundle.bundle_id,
                    object_version=method_bundle.object_version,
                ),
                file_name="development_method_bundle.json",
                sha256=hashlib.sha256(method_payload).hexdigest(),
                selected_method_ids=sorted(
                    method_spec.selected_method_ids, key=str
                ),
            )
            method_reasons = sorted(
                {
                    reason
                    for item in method_bundle.method_evidence
                    for reason in item.reason_codes
                }
            )
            reference_stage_support_available = any(
                item.method_id is DevelopmentMethodId.PSEUDOBULK_CORRELATION
                and item.execution_state
                in {
                    MethodExecutionState.SUCCEEDED,
                    MethodExecutionState.PARTIAL,
                }
                for item in method_bundle.method_evidence
            )

        evaluation = evaluate_developmental_compatibility(
            run_id=run_id,
            tool_version=spec.version,
            product_case=product_case,
            product_definition=product_definition,
            window_spec=window_spec,
            state_map=state_map,
            measurement_spec=measurement_spec,
            cell_state_profile=cell_state_profile,
            cell_state_profile_version=_input_version(
                request, "cell_state_evidence_profile"
            ),
            timepoint_series=series,
            input_sha256_by_role={
                ref.role: ref.sha256 for ref in request.object_inputs
            },
            method_bundle_ref=(
                None if method_binding is None else method_binding.bundle_ref
            ),
            method_bundle_sha256=(
                None if method_binding is None else method_binding.sha256
            ),
            selected_method_ids=(
                []
                if method_binding is None
                else [str(item) for item in method_binding.selected_method_ids]
            ),
            method_reason_codes=method_reasons,
            reference_stage_support_available=reference_stage_support_available,
        )
        result = evaluation.result
        try:
            visualization_profile = (
                build_developmental_compatibility_visualization_data(
                    run_id=run_id,
                    tool_version=spec.version,
                    result=result,
                    window_spec=window_spec,
                    timepoint_series=series,
                    method_spec=method_spec,
                    method_bundle=method_bundle,
                    method_bundle_sha256=(
                        None
                        if method_binding is None
                        else method_binding.sha256
                    ),
                    reference_manifest=reference_manifest,
                    cell_state_profile=cell_state_profile,
                )
            )
        except (KeyError, ValueError):
            return _failed_run(
                request,
                spec,
                ["visualization_data_invalid"],
                input_hash=input_hash,
            )
        try:
            prepared_visualizations = (
                prepare_developmental_compatibility_visualizations(
                    profile=visualization_profile,
                    output_dir=request.output_dir,
                    run_id=run_id,
                    tool_version=spec.version,
                )
            )
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            return _failed_run(
                request,
                spec,
                ["visualization_render_failed"],
                input_hash=input_hash,
            )
        result_payload = canonical_json_bytes(
            result.model_dump(mode="json"), indent=2
        )
        payloads = {
            "developmental_compatibility_result.json": result_payload,
            **evaluation.measurement_payloads,
            **prepared_visualizations.payloads,
        }
        if method_payload is not None:
            payloads["development_method_bundle.json"] = method_payload
        try:
            output_files = publish_json_bundle(
                request=request,
                run_id=run_id,
                payloads=payloads,
                inputs_are_unchanged=lambda refs: inputs_unchanged(refs)
                and _assets_unchanged(request.assets),
            )
        except PublicationError as exc:
            return _failed_run(
                request, spec, [exc.reason_code], input_hash=input_hash
            )

        artifacts = [
            ArtifactManifest(
                artifact_id=f"artifact:{run_id}:developmental-compatibility-result",
                kind="developmental_compatibility_result",
                path=output_files["developmental_compatibility_result.json"],
                media_type="application/json",
                sha256=hashlib.sha256(result_payload).hexdigest(),
                evidence_ids=result.evidence_refs,
            )
        ]
        artifacts.extend(prepared_visualizations.artifacts)
        if method_binding is not None:
            artifacts.append(
                ArtifactManifest(
                    artifact_id=f"artifact:{run_id}:development-method-bundle",
                    kind="development_method_bundle",
                    path=output_files[method_binding.file_name],
                    media_type="application/json",
                    sha256=method_binding.sha256,
                    evidence_ids=result.evidence_refs,
                )
            )
        binding_by_file = {
            item.file_name: item for item in result.measurement_artifacts
        }
        for filename in sorted(evaluation.measurement_payloads):
            binding = binding_by_file[filename]
            artifacts.append(
                ArtifactManifest(
                    artifact_id=binding.artifact_id,
                    kind="measurement_result_v2",
                    path=output_files[filename],
                    media_type="application/json",
                    sha256=binding.sha256,
                    evidence_ids=result.evidence_refs,
                )
            )
        methods_complete = method_bundle is None or all(
            item.execution_state is MethodExecutionState.SUCCEEDED
            for item in method_bundle.method_evidence
        )
        execution_state = (
            ExecutionState.SUCCEEDED
            if result.result_state == "complete" and methods_complete
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
            created_at=product_case.created_at,
            measurements=evaluation.measurements,
            artifacts=artifacts,
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
    roles = [ref.role for ref in request.object_inputs]
    method_count = roles.count("development_method_spec")
    asset_count = len(request.assets)
    if method_count > 1:
        reasons.append("at_most_one_development_method_spec_allowed")
    if bool(method_count) != bool(asset_count):
        reasons.append("expression_method_inputs_incomplete")
    if asset_count > 1:
        reasons.append("at_most_one_expression_asset_allowed")
    if asset_count == 1:
        asset = request.assets[0]
        if asset.input_level is not InputLevel.ANALYSIS_READY:
            reasons.append("analysis_ready_expression_asset_required")
        if not re.fullmatch(r"[0-9a-f]{64}", asset.checksum or ""):
            reasons.append("expression_asset_checksum_required")
        if asset.assay is None:
            reasons.append("expression_asset_assay_required")
        if {"data_view_id", "parent_asset_sha256"} - set(asset.metadata):
            reasons.append("expression_asset_view_metadata_incomplete")
    elif request.random_seed != 0:
        reasons.append("p0_04_random_seed_forbidden_without_methods")
    if request.measurement_spec_ref is not None:
        reasons.append("p0_04_measurement_spec_parameter_forbidden")
    if request.parameters:
        reasons.append("p0_04_parameters_forbidden")
    for role in REQUIRED_ROLES:
        if roles.count(role) != 1:
            reasons.append(f"exactly_one_{role}_required")
    for role in OPTIONAL_ROLES:
        if roles.count(role) > 1:
            reasons.append(f"at_most_one_{role}_allowed")
    if any(role not in ROLE_MODELS for role in roles):
        reasons.append("unsupported_object_input_role")
    for ref in request.object_inputs:
        contract = ROLE_MODELS.get(ref.role)
        if contract is not None and ref.schema_ref != contract[0]:
            reasons.append("object_input_schema_mismatch")
        fixed_version = FIXED_OBJECT_VERSIONS.get(ref.role)
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
    if isinstance(value, (MeasurementSpecV2, AnnotationVocabulary, ReferenceManifest)):
        object_version = value.version
    else:
        object_version = getattr(value, "object_version", None)
        if object_version is None:
            object_version = FIXED_OBJECT_VERSIONS.get(ref.role)
    if object_version != ref.object_version:
        raise StructuredInputError("object_input_version_mismatch")


def _binding_reasons(
    request: ToolRequestV2, loaded: LoadedInputs
) -> list[str]:
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
    profile = single_object(
        request, loaded, "cell_state_evidence_profile", CellStateEvidenceProfileV3
    )
    qc_profile = single_object(
        request, loaded, "qc_readiness_profile", QCReadinessProfileV2
    )
    biological_unit_manifest = single_object(
        request, loaded, "biological_unit_manifest", BiologicalUnitManifest
    )
    biological_unit_assignment = single_object(
        request,
        loaded,
        "biological_unit_assignment",
        BiologicalUnitAssignmentArtifact,
    )
    annotation_vocabulary = single_object(
        request, loaded, "annotation_vocabulary", AnnotationVocabulary
    )
    reference_manifest = single_object(
        request, loaded, "reference_manifest", ReferenceManifest
    )
    series_values = objects_for_role(
        request,
        loaded,
        "development_timepoint_series",
        DevelopmentTimepointSeries,
    )
    method_values = objects_for_role(
        request, loaded, "development_method_spec", DevelopmentMethodSpec
    )
    input_sha256_by_role = {
        ref.role: ref.sha256 for ref in request.object_inputs
    }
    reasons = profile_lineage_reasons(
        product_case=product_case,
        cell_state_profile=profile,
        measurement_spec=measurement_spec,
        qc_profile=qc_profile,
        biological_unit_manifest=biological_unit_manifest,
        biological_unit_assignment_artifact=biological_unit_assignment,
        input_sha256_by_role=input_sha256_by_role,
    )

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
    if measurement_spec.assay != product_case.assay:
        reasons.append("measurement_spec_assay_mismatch")
    if (
        measurement_spec.applicable_product_cards
        and product_definition.product_definition_id
        not in measurement_spec.applicable_product_cards
        and product_definition.ref.ref not in measurement_spec.applicable_product_cards
    ):
        reasons.append("measurement_spec_product_definition_not_applicable")
    if profile.assay != product_case.assay:
        reasons.append("cell_state_assay_binding_mismatch")
    if qc_profile.assay != product_case.assay:
        reasons.append("qc_profile_assay_mismatch")
    if (
        qc_profile.readiness_state
        in {
            ReadinessState.BLOCKED,
            ReadinessState.NOT_ASSESSED,
            ReadinessState.NOT_APPLICABLE,
        }
        or qc_profile.module_eligibility.get("P0-04") != "eligible"
    ):
        reasons.append("qc_not_ready_for_developmental_compatibility")
    if profile.composition.state not in COMPOSITION_STATES:
        reasons.append("cell_state_composition_state_invalid")
    if (
        profile.annotation_vocabulary_ref != annotation_vocabulary.vocabulary_id
        or profile.annotation_vocabulary_version != annotation_vocabulary.version
    ):
        reasons.append("annotation_vocabulary_binding_mismatch")
    if (
        profile.annotation_vocabulary_sha256
        != input_sha256_by_role["annotation_vocabulary"]
        or reference_manifest.vocabulary_sha256
        != input_sha256_by_role["annotation_vocabulary"]
    ):
        reasons.append("annotation_vocabulary_checksum_mismatch")
    if (
        profile.reference_snapshot_ref != reference_manifest.snapshot_id
        or profile.reference_manifest_version != reference_manifest.version
    ):
        reasons.append("reference_manifest_binding_mismatch")
    if (
        profile.reference_manifest_sha256
        != input_sha256_by_role["reference_manifest"]
    ):
        reasons.append("reference_manifest_checksum_mismatch")
    if measurement_spec.measurement_spec_id not in reference_manifest.measurement_spec_ids:
        reasons.append("reference_manifest_measurement_spec_mismatch")
    if measurement_spec.reference_refs and not {
        reference_manifest.snapshot_id,
        f"{reference_manifest.snapshot_id}@{reference_manifest.version}",
    }.intersection(measurement_spec.reference_refs):
        reasons.append("measurement_spec_reference_not_applicable")

    if series_values:
        series = series_values[0]
        if series.product_case_ref != product_case.ref:
            reasons.append("timepoint_series_product_case_binding_mismatch")
        if series.state_map_ref != state_map.ref:
            reasons.append("timepoint_series_state_map_binding_mismatch")
    if method_values:
        method_spec = method_values[0]
        asset = request.assets[0]
        view = profile.input_data_view
        if method_spec.expression_asset_id != asset.asset_id:
            reasons.append("expression_asset_binding_mismatch")
        if asset.assay != product_case.assay:
            reasons.append("expression_asset_assay_mismatch")
        if asset.metadata.get("data_view_id") != view.view_id:
            reasons.append("expression_asset_data_view_mismatch")
        if asset.metadata.get("parent_asset_sha256") != view.parent_asset_sha256:
            reasons.append("expression_asset_parent_checksum_mismatch")
        method_units = {
            item.analysis_unit_ref for item in method_spec.analysis_unit_timepoints
        }
        assignment_units = {
            item.analysis_unit_ref for item in biological_unit_assignment.assignments
        }
        if not method_units.issubset(assignment_units):
            reasons.append("method_timepoint_analysis_unit_mismatch")
    return sorted(set(reasons))


def _input_version(request: ToolRequestV2, role: str) -> str:
    return next(
        ref.object_version for ref in request.object_inputs if ref.role == role
    )


def _input_path(request: ToolRequestV2, role: str) -> Path:
    return Path(next(ref.path for ref in request.object_inputs if ref.role == role))


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
        "assets": [
            {
                "asset_id": asset.asset_id,
                "checksum": asset.checksum,
                "format": asset.format,
                "input_level": asset.input_level,
                "matrix_location": asset.matrix_location,
                "matrix_semantics": asset.matrix_semantics,
                "assay": asset.assay,
                "data_view_id": asset.metadata.get("data_view_id"),
                "parent_asset_sha256": asset.metadata.get("parent_asset_sha256"),
            }
            for asset in sorted(request.assets, key=lambda item: item.asset_id)
        ],
        "random_seed": request.random_seed,
    }
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def _assets_unchanged(assets: list[InputAsset]) -> bool:
    for asset in assets:
        try:
            if sha256_path(asset.path) != asset.checksum:
                return False
        except (OSError, InputAuditError):
            return False
    return True


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
