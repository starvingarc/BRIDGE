from __future__ import annotations

import hashlib
from dataclasses import dataclass

from bridge.tool_packages._configurable_contracts import (
    BiologicalUnitAssignmentArtifact,
    BiologicalUnitManifest,
    DevelopmentWindowSpec,
    ProductCase,
    ProductDefinitionCard,
)
from bridge.tool_packages._structured_runtime import (
    LoadedInputs,
    PublicationError,
    canonical_json_bytes,
    directory_state,
    failed_v2_run,
    inputs_unchanged,
    load_structured_inputs,
    objects_for_role,
    request_v2_from_v1,
    single_object,
)
from bridge.tool_packages._structured_runtime import (
    publish_json_bundle as _publish_bundle,
)
from bridge.tool_packages.p0_06_proliferation_stress_response.method_binding import (
    ExpressionAssetError,
    expression_asset_sha256,
    method_binding_reasons,
)
from bridge.tool_packages.p0_06_proliferation_stress_response.method_models import (
    ProcessMethodBundle,
    ProcessMethodInput,
    ProcessMethodSpec,
)
from bridge.tool_packages.p0_06_proliferation_stress_response.method_runtime import (
    ProcessMethodError,
    run_process_methods,
)
from bridge.tool_packages.p0_06_proliferation_stress_response.models import (
    AnalysisScope,
    BatchConfoundingState,
    ProcessAttributionState,
    ProgramApplicabilityState,
    ProgramAvailabilityState,
    ProgramEvidenceBundle,
    ProgramEvidenceSummary,
    ProgramMeasurementArtifactBinding,
    ProgramSourceBinding,
    ProgramSpec,
    ProliferationStressResponseProfile,
    ProliferationStressResponseProfileV2,
    ProtocolIR,
    ProtocolMetadataState,
    ReviewFlagState,
    TranscriptomicReviewFlag,
    projected_program_evidence_state,
)
from bridge.tool_packages.p0_06_proliferation_stress_response.visualization import (
    prepare_proliferation_stress_visualizations,
)
from bridge.tool_packages.p0_06_proliferation_stress_response.visualization_data import (
    build_proliferation_stress_visualization_data,
)
from bridge.toolkit.contracts import (
    ArtifactManifest,
    CellStateEvidenceProfileV2,
    CellStateEvidenceProfileV3,
    EligibilityResult,
    EvidenceState,
    ExecutionState,
    FrozenModel,
    ImplementationState,
    InputAsset,
    InputLevel,
    MeasurementResultV2,
    MeasurementSpecV2,
    ScoreState,
    StructuredInputRef,
    ToolPackageSpecV2,
    ToolRequest,
    ToolRequestV2,
    ToolRunV2,
)

PROFILE_V2_SCHEMA_REF = "bridge://schemas/proliferation-stress-response-profile/v0.2"
CORE_AGGREGATION_METHOD_IDS = {
    "METHOD-BRIDGE-SAMPLE-STATE-AGGREGATION",
    "METHOD-DESIGN-AUDIT-AND-SENSITIVITY-STRATIFICATION",
}
BASE_ROLE_MODELS: dict[str, tuple[str, str, type[FrozenModel]]] = {
    "product_case": (
        "bridge://schemas/product-case/v0.1",
        "0.1.0",
        ProductCase,
    ),
    "product_definition_card": (
        "bridge://schemas/product-definition-card/v0.1",
        "0.1.0",
        ProductDefinitionCard,
    ),
    "development_window_spec": (
        "bridge://schemas/development-window-spec/v0.1",
        "0.1.0",
        DevelopmentWindowSpec,
    ),
    "program_spec": (
        "bridge://schemas/program-spec/v0.1",
        "0.1.0",
        ProgramSpec,
    ),
    "cell_state_evidence_profile": (
        "bridge://schemas/cell-state-evidence-profile/v0.2",
        "0.2.0",
        CellStateEvidenceProfileV2,
    ),
    "protocol_ir": (
        "bridge://schemas/protocol-ir/v0.1",
        "0.1.0",
        ProtocolIR,
    ),
    "program_evidence_bundle": (
        "bridge://schemas/program-evidence-bundle/v0.1",
        "0.1.0",
        ProgramEvidenceBundle,
    ),
}

METHOD_ROLE_MODELS: dict[str, tuple[str, str, type[FrozenModel]]] = {
    **BASE_ROLE_MODELS,
    "cell_state_evidence_profile": (
        "bridge://schemas/cell-state-evidence-profile/v0.3",
        "0.3.0",
        CellStateEvidenceProfileV3,
    ),
    "biological_unit_manifest": (
        "bridge://schemas/biological-unit-manifest/v0.1",
        "0.1.0",
        BiologicalUnitManifest,
    ),
    "biological_unit_assignment": (
        "bridge://schemas/biological-unit-assignment/v0.1",
        "0.1.0",
        BiologicalUnitAssignmentArtifact,
    ),
    "process_method_spec": (
        "bridge://schemas/process-method-spec/v0.1",
        "0.1.0",
        ProcessMethodSpec,
    ),
    "process_method_input": (
        "bridge://schemas/process-method-input/v0.1",
        "0.1.0",
        ProcessMethodInput,
    ),
}
OPTIONAL_ROLE_MODELS: dict[str, tuple[str, str | None, type[FrozenModel]]] = {
    "measurement_spec": (
        "bridge://schemas/measurement-spec/v0.2",
        None,
        MeasurementSpecV2,
    ),
}
ROLE_MODELS = {**METHOD_ROLE_MODELS, **OPTIONAL_ROLE_MODELS}


@dataclass(frozen=True)
class ProliferationStressResponseAdapter:
    def check_eligibility(
        self, request: ToolRequestV2, spec: ToolPackageSpecV2
    ) -> EligibilityResult:
        if not isinstance(request, ToolRequestV2):
            tool_id = request.tool_id if isinstance(request, ToolRequest) else "P0-06"
            return EligibilityResult(
                tool_id=tool_id,
                eligible=False,
                reason_codes=["tool_request_v2_required"],
            )
        mode = _request_mode(request)
        reasons = _envelope_reasons(request, spec, mode)
        loaded, loading_reasons = _load_inputs(request.object_inputs, mode)
        reasons.extend(loading_reasons)
        if loaded is not None and not reasons:
            reasons.extend(_binding_reasons(request, loaded, spec, mode))
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
        mode = _request_mode(request)
        loaded, reasons = _load_inputs(request.object_inputs, mode)
        if loaded is None or reasons:
            return _failed_run(request, spec, reasons)

        input_hash = _input_hash(request, spec)
        run_id = f"run-{input_hash[:16]}"
        result = _build_result(request, loaded, input_hash)
        method_bundle: ProcessMethodBundle | None = None
        method_bytes: bytes | None = None
        method_sha: str | None = None
        asset_sha: str | None = None
        method_spec: ProcessMethodSpec | None = None
        method_input: ProcessMethodInput | None = None
        if mode == "method_runtime":
            asset = request.assets[0]
            try:
                asset_sha = expression_asset_sha256(asset.path)
                method_spec = single_object(
                    request,
                    loaded,
                    "process_method_spec",
                    ProcessMethodSpec,
                )
                method_input = single_object(
                    request,
                    loaded,
                    "process_method_input",
                    ProcessMethodInput,
                )
                assignment = single_object(
                    request,
                    loaded,
                    "biological_unit_assignment",
                    BiologicalUnitAssignmentArtifact,
                )
                method_bundle = run_process_methods(
                    run_id=run_id,
                    tool_version=spec.version,
                    asset=asset,
                    asset_sha256=asset_sha,
                    method_spec=method_spec,
                    method_spec_sha256=_input_sha(request, "process_method_spec"),
                    program_spec_sha256=_input_sha(request, "program_spec"),
                    method_input=method_input,
                    method_input_sha256=_input_sha(request, "process_method_input"),
                    assignment=assignment,
                    assignment_sha256=_input_sha(request, "biological_unit_assignment"),
                    biological_unit_manifest_sha256=_input_sha(
                        request, "biological_unit_manifest"
                    ),
                    program_spec=single_object(
                        request, loaded, "program_spec", ProgramSpec
                    ),
                    random_seed=request.random_seed,
                )
            except (ExpressionAssetError, ProcessMethodError) as exc:
                return _failed_run(
                    request, spec, [exc.reason_code], input_hash=input_hash
                )
            method_bytes = canonical_json_bytes(
                method_bundle.model_dump(mode="json"), indent=2
            )
            method_sha = hashlib.sha256(method_bytes).hexdigest()
        method_reasons = (
            sorted(
                {
                    reason
                    for execution in method_bundle.executions
                    for reason in execution.reason_codes
                }
            )
            if method_bundle is not None
            else []
        )
        execution_state = (
            ExecutionState.PARTIAL if method_reasons else ExecutionState.SUCCEEDED
        )
        bundle = single_object(
            request,
            loaded,
            "program_evidence_bundle",
            ProgramEvidenceBundle,
        )
        measurements: list[MeasurementResultV2] = []
        measurement_payloads: dict[str, bytes] = {}
        measurement_specs = objects_for_role(
            request, loaded, "measurement_spec", MeasurementSpecV2
        )
        if measurement_specs:
            result, measurements, measurement_payloads = _project_measurements(
                result=result,
                bundle=bundle,
                measurement_spec=measurement_specs[0],
                run_id=run_id,
                tool_version=spec.version,
                source_execution_state=(
                    "partial"
                    if execution_state is ExecutionState.PARTIAL
                    else "succeeded"
                ),
            )
        elif spec.result_schema_ref == PROFILE_V2_SCHEMA_REF:
            result = _profile_v2_without_projection(result)
        result_bytes = canonical_json_bytes(result.model_dump(mode="json"), indent=2)
        payloads = {
            "proliferation_stress_response_profile.json": result_bytes,
            **measurement_payloads,
        }
        if method_bytes is not None:
            payloads["process_method_bundle.json"] = method_bytes
        try:
            visualization_profile = build_proliferation_stress_visualization_data(
                run_id=run_id,
                tool_version=spec.version,
                result=result,
                method_spec=method_spec,
                method_input=method_input,
                method_bundle=method_bundle,
                method_bundle_sha256=method_sha,
            )
        except (KeyError, TypeError, ValueError):
            return _failed_run(
                request, spec, ["visualization_data_invalid"], input_hash=input_hash
            )
        try:
            prepared_visualizations = prepare_proliferation_stress_visualizations(
                profile=visualization_profile,
                output_dir=request.output_dir,
                run_id=run_id,
                tool_version=spec.version,
            )
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            return _failed_run(
                request, spec, ["visualization_render_failed"], input_hash=input_hash
            )
        payloads.update(prepared_visualizations.payloads)
        payloads["artifact_manifest.json"] = canonical_json_bytes(
            _artifact_manifest_payload(
                request=request,
                spec=spec,
                run_id=run_id,
                input_hash=input_hash,
                artifact_payloads=payloads,
            ),
            indent=2,
        )
        try:
            published = _publish_bundle(
                request=request,
                run_id=run_id,
                payloads=payloads,
                inputs_are_unchanged=lambda refs: (
                    inputs_unchanged(refs)
                    and _expression_asset_unchanged(request.assets, asset_sha)
                ),
            )
        except PublicationError as exc:
            return _failed_run(
                request,
                spec,
                [exc.reason_code],
                input_hash=input_hash,
            )
        evidence_ids = sorted(item.evidence_id for item in bundle.records)
        artifacts = [
            ArtifactManifest(
                artifact_id=f"artifact:{run_id}:proliferation-stress-response",
                kind="proliferation_stress_response_profile",
                path=published["proliferation_stress_response_profile.json"],
                media_type="application/json",
                sha256=hashlib.sha256(result_bytes).hexdigest(),
                evidence_ids=evidence_ids,
            ),
            ArtifactManifest(
                artifact_id=f"artifact:{run_id}:artifact-manifest",
                kind="artifact_manifest",
                path=published["artifact_manifest.json"],
                media_type="application/json",
                sha256=hashlib.sha256(payloads["artifact_manifest.json"]).hexdigest(),
                evidence_ids=evidence_ids,
            ),
        ]
        if method_bytes is not None:
            artifacts.append(
                ArtifactManifest(
                    artifact_id=f"artifact:{run_id}:process-methods",
                    kind="process_method_bundle",
                    path=published["process_method_bundle.json"],
                    media_type="application/json",
                    sha256=hashlib.sha256(method_bytes).hexdigest(),
                    evidence_ids=evidence_ids,
                )
            )
        if isinstance(result, ProliferationStressResponseProfileV2):
            artifacts.extend(
                ArtifactManifest(
                    artifact_id=binding.artifact_id,
                    kind="measurement_result_v2",
                    path=published[binding.file_name],
                    media_type="application/json",
                    sha256=binding.sha256,
                    evidence_ids=[binding.evidence_id],
                )
                for binding in result.measurement_artifacts
            )
        artifacts.extend(prepared_visualizations.artifacts)
        return ToolRunV2(
            run_id=run_id,
            request=request,
            implementation_state=ImplementationState.IMPLEMENTED,
            execution_state=execution_state,
            tool_version=spec.version,
            environment_spec_id=spec.environment_spec_id,
            input_hash=input_hash,
            created_at=bundle.created_at,
            measurements=measurements,
            artifacts=artifacts,
            visualizations=[],
            result_schema_ref=spec.result_schema_ref,
            result=result.model_dump(mode="json"),
            reason_codes=[],
            warnings=method_reasons,
        )


adapter = ProliferationStressResponseAdapter()


def _request_mode(request: ToolRequestV2) -> str:
    method_only_roles = set(METHOD_ROLE_MODELS).difference(BASE_ROLE_MODELS)
    if request.assets or any(
        ref.role in method_only_roles for ref in request.object_inputs
    ):
        return "method_runtime"
    return "legacy_aggregation"


def _envelope_reasons(
    request: ToolRequestV2,
    spec: ToolPackageSpecV2,
    mode: str,
) -> list[str]:
    reasons: list[str] = []
    if request.tool_version is not None and request.tool_version != spec.version:
        reasons.append("tool_version_mismatch")
    if request.measurement_spec_ref is not None:
        reasons.append("p0_06_measurement_spec_forbidden")
    if request.parameters:
        reasons.append("p0_06_parameters_forbidden")
    required_role_models = (
        METHOD_ROLE_MODELS if mode == "method_runtime" else BASE_ROLE_MODELS
    )
    role_models = {**required_role_models, **OPTIONAL_ROLE_MODELS}
    roles = [ref.role for ref in request.object_inputs]
    for role in required_role_models:
        if roles.count(role) != 1:
            reasons.append(f"exactly_one_{role}_required")
    if roles.count("measurement_spec") > 1:
        reasons.append("at_most_one_measurement_spec_allowed")
    if (
        roles.count("measurement_spec") == 1
        and spec.result_schema_ref != PROFILE_V2_SCHEMA_REF
    ):
        reasons.append("measurement_projection_requires_profile_v2")
    if any(role not in role_models for role in roles):
        reasons.append("unsupported_object_input_role")
    for ref in request.object_inputs:
        contract = role_models.get(ref.role)
        if contract is not None and ref.schema_ref != contract[0]:
            reasons.append("object_input_schema_mismatch")
        if (
            contract is not None
            and contract[1] is not None
            and ref.object_version != contract[1]
        ):
            reasons.append("object_input_version_mismatch")
    if mode == "legacy_aggregation":
        if request.assets:
            reasons.append("p0_06_expression_assets_forbidden")
    elif len(request.assets) != 1:
        reasons.append("exactly_one_expression_asset_required")
    else:
        asset = request.assets[0]
        if (
            asset.input_level is not InputLevel.ANALYSIS_READY
            or asset.format != "h5ad"
            or asset.matrix_semantics != "normalized_expression"
            or asset.checksum is None
        ):
            reasons.append("analysis_ready_normalized_h5ad_required")
        else:
            try:
                if expression_asset_sha256(asset.path) != asset.checksum:
                    reasons.append("expression_asset_checksum_mismatch")
            except ExpressionAssetError as exc:
                reasons.append(exc.reason_code)
    if directory_state(request.output_dir) == "other":
        reasons.append("output_dir_not_regular_directory")
    return reasons


def _load_inputs(
    refs: list[StructuredInputRef],
    mode: str,
) -> tuple[LoadedInputs | None, list[str]]:
    required_role_models = (
        METHOD_ROLE_MODELS if mode == "method_runtime" else BASE_ROLE_MODELS
    )
    role_models = {**required_role_models, **OPTIONAL_ROLE_MODELS}
    return load_structured_inputs(
        refs,
        model_for=lambda ref: role_models.get(ref.role, ("", None, None))[2],
        validate_model=lambda ref, value: _validate_object_version(
            ref, value, role_models
        ),
    )


def _validate_object_version(
    ref: StructuredInputRef,
    value: FrozenModel,
    role_models: dict[str, tuple[str, str | None, type[FrozenModel]]],
) -> None:
    expected = (
        value.version
        if isinstance(value, MeasurementSpecV2)
        else role_models[ref.role][1]
    )
    if expected != ref.object_version:
        from bridge.tool_packages._structured_runtime import StructuredInputError

        raise StructuredInputError("object_input_version_mismatch")


def _binding_reasons(
    request: ToolRequestV2,
    loaded: LoadedInputs,
    spec: ToolPackageSpecV2,
    mode: str,
) -> list[str]:
    product_case = single_object(request, loaded, "product_case", ProductCase)
    product_definition = single_object(
        request,
        loaded,
        "product_definition_card",
        ProductDefinitionCard,
    )
    window = single_object(
        request,
        loaded,
        "development_window_spec",
        DevelopmentWindowSpec,
    )
    program_spec = single_object(request, loaded, "program_spec", ProgramSpec)
    cell_state = single_object(
        request,
        loaded,
        "cell_state_evidence_profile",
        CellStateEvidenceProfileV3
        if mode == "method_runtime"
        else CellStateEvidenceProfileV2,
    )
    protocol = single_object(request, loaded, "protocol_ir", ProtocolIR)
    bundle = single_object(
        request,
        loaded,
        "program_evidence_bundle",
        ProgramEvidenceBundle,
    )
    reasons: list[str] = []
    if (
        product_case.product_definition_ref != product_definition.ref
        or product_case.assay not in product_definition.supported_assays
        or window.product_definition_ref != product_definition.ref
        or product_case.assay not in window.applicable_assays
        or program_spec.product_definition_ref != product_definition.ref
    ):
        reasons.append("product_context_binding_mismatch")
    if program_spec.development_window_ref != window.ref:
        reasons.append("development_window_binding_mismatch")
    if set(program_spec.aggregation_method_ids) != CORE_AGGREGATION_METHOD_IDS:
        reasons.append("program_spec_method_binding_mismatch")
    if (
        cell_state.assay != product_case.assay
        or cell_state.measurement_spec_id != product_case.measurement_spec_ref.object_id
        or cell_state.measurement_spec_version
        != product_case.measurement_spec_ref.object_version
    ):
        reasons.append("cell_state_profile_binding_mismatch")
    if (
        cell_state.input_data_view is not None
        and cell_state.input_data_view.sample_or_preparation_ref
        != product_case.sample_or_preparation_ref.ref
    ):
        reasons.append("cell_state_profile_binding_mismatch")
    if protocol.product_case_ref != product_case.ref:
        reasons.append("protocol_product_case_binding_mismatch")
    if (
        bundle.product_case_ref != product_case.ref
        or bundle.product_definition_ref != product_definition.ref
        or bundle.development_window_ref != window.ref
        or bundle.program_spec_ref != program_spec.ref
        or bundle.cell_state_profile_ref != cell_state.profile_id
        or bundle.protocol_context_ref != protocol.protocol_context_id
    ):
        reasons.append("program_evidence_bundle_binding_mismatch")

    refs = {ref.role: ref for ref in request.object_inputs}
    expected_hashes = {
        "product_case": bundle.product_case_sha256,
        "product_definition_card": bundle.product_definition_sha256,
        "development_window_spec": bundle.development_window_sha256,
        "program_spec": bundle.program_spec_sha256,
        "cell_state_evidence_profile": bundle.cell_state_profile_sha256,
        "protocol_ir": bundle.protocol_context_sha256,
    }
    if any(refs[role].sha256 != sha for role, sha in expected_hashes.items()):
        reasons.append("program_evidence_lineage_checksum_mismatch")

    rules = {item.program_id: item for item in program_spec.program_rules}
    declared_steps = set(protocol.declared_process_step_ids)
    for record in bundle.records:
        rule = rules.get(record.program_id)
        if (
            rule is None
            or record.analysis_scope not in rule.allowed_analysis_scopes
            or (
                record.analysis_scope is AnalysisScope.STATE_SPECIFIC
                and record.cell_state_id not in rule.allowed_state_ids
            )
            or record.metric_id not in rule.allowed_metric_ids
            or record.lod_state not in rule.allowed_lod_states
            or record.evidence_state not in rule.review_outcomes
            or not set(record.process_step_ids).issubset(declared_steps)
        ):
            reasons.append("program_evidence_contract_mismatch")
    if mode == "method_runtime":
        asset = request.assets[0]
        manifest = single_object(
            request,
            loaded,
            "biological_unit_manifest",
            BiologicalUnitManifest,
        )
        if protocol.independent_replicate_count > len(manifest.independence_group_refs):
            reasons.append("protocol_independent_replicate_count_exceeds_manifest")
        try:
            asset_sha = expression_asset_sha256(asset.path)
        except ExpressionAssetError as exc:
            reasons.append(exc.reason_code)
        else:
            reasons.extend(
                method_binding_reasons(
                    product_case=product_case,
                    cell_state=cell_state,
                    program_spec=program_spec,
                    method_spec=single_object(
                        request,
                        loaded,
                        "process_method_spec",
                        ProcessMethodSpec,
                    ),
                    method_input=single_object(
                        request,
                        loaded,
                        "process_method_input",
                        ProcessMethodInput,
                    ),
                    manifest=manifest,
                    assignment=single_object(
                        request,
                        loaded,
                        "biological_unit_assignment",
                        BiologicalUnitAssignmentArtifact,
                    ),
                    asset=asset,
                    asset_sha256=asset_sha,
                    input_sha256_by_role={
                        ref.role: ref.sha256 for ref in request.object_inputs
                    },
                    tool_spec=spec,
                )
            )
    measurement_specs = objects_for_role(
        request, loaded, "measurement_spec", MeasurementSpecV2
    )
    if measurement_specs:
        reasons.extend(
            _measurement_spec_reasons(
                measurement_spec=measurement_specs[0],
                product_case=product_case,
                product_definition=product_definition,
                program_spec=program_spec,
            )
        )
    return reasons


def _measurement_spec_reasons(
    *,
    measurement_spec: MeasurementSpecV2,
    product_case: ProductCase,
    product_definition: ProductDefinitionCard,
    program_spec: ProgramSpec,
) -> list[str]:
    reasons: list[str] = []
    if "P0-06" not in measurement_spec.tool_refs:
        reasons.append("measurement_spec_tool_binding_mismatch")
    if measurement_spec.assay != product_case.assay:
        reasons.append("measurement_spec_assay_mismatch")
    if (
        measurement_spec.applicable_product_cards
        and product_definition.product_definition_id
        not in measurement_spec.applicable_product_cards
        and product_definition.ref.ref not in measurement_spec.applicable_product_cards
    ):
        reasons.append("measurement_spec_product_definition_not_applicable")
    expected_metric_ids = {
        metric_id
        for rule in program_spec.program_rules
        for metric_id in rule.allowed_metric_ids
    }
    expected_analysis_scopes = {
        scope.value
        for rule in program_spec.program_rules
        for scope in rule.allowed_analysis_scopes
    }
    raw = measurement_spec.raw_metric_definition
    if _explicit_string_set(raw.get("metric_ids")) != expected_metric_ids:
        reasons.append("measurement_spec_metric_ids_mismatch")
    if _explicit_string_set(raw.get("analysis_scopes")) != expected_analysis_scopes:
        reasons.append("measurement_spec_analysis_scopes_mismatch")
    return reasons


def _explicit_string_set(value: object) -> set[str] | None:
    if (
        not isinstance(value, list)
        or not value
        or any(not isinstance(item, str) or not item for item in value)
        or len(value) != len(set(value))
    ):
        return None
    return set(value)


def _input_hash(request: ToolRequestV2, spec: ToolPackageSpecV2) -> str:
    payload = {
        "tool_id": spec.tool_id,
        "tool_version": spec.version,
        "environment_spec_id": spec.environment_spec_id,
        "random_seed": request.random_seed,
        "assets": [
            {
                "asset_id": asset.asset_id,
                "format": asset.format,
                "input_level": asset.input_level.value,
                "checksum": asset.checksum,
                "matrix_location": asset.matrix_location,
                "matrix_semantics": asset.matrix_semantics,
                "assay": asset.assay,
            }
            for asset in sorted(request.assets, key=lambda item: item.asset_id)
        ],
        "object_inputs": [
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


def _process_attribution(
    protocol: ProtocolIR,
    program_spec: ProgramSpec,
) -> tuple[ProcessAttributionState, list[str]]:
    reasons: list[str] = []
    if protocol.metadata_state is not ProtocolMetadataState.COMPLETE:
        reasons.append("process_metadata_incomplete")
    if protocol.batch_confounding_state is not BatchConfoundingState.NOT_CONFOUNDED:
        reasons.append("process_batch_confounding_unresolved")
    rule = program_spec.attribution_rule
    if (
        protocol.independent_replicate_count < rule.minimum_independent_replicates
        or protocol.comparable_group_count < rule.minimum_comparable_groups
    ):
        reasons.append("process_replication_insufficient")
    return (
        ProcessAttributionState.CANNOT_ATTRIBUTE
        if reasons
        else ProcessAttributionState.CONDITIONAL_ASSOCIATION,
        reasons,
    )


def _build_result(
    request: ToolRequestV2,
    loaded: LoadedInputs,
    input_hash: str,
) -> ProliferationStressResponseProfile:
    product_case = single_object(request, loaded, "product_case", ProductCase)
    product_definition = single_object(
        request,
        loaded,
        "product_definition_card",
        ProductDefinitionCard,
    )
    window = single_object(
        request,
        loaded,
        "development_window_spec",
        DevelopmentWindowSpec,
    )
    program_spec = single_object(request, loaded, "program_spec", ProgramSpec)
    cell_state = single_object(
        request,
        loaded,
        "cell_state_evidence_profile",
        CellStateEvidenceProfileV2,
    )
    protocol = single_object(request, loaded, "protocol_ir", ProtocolIR)
    bundle = single_object(
        request,
        loaded,
        "program_evidence_bundle",
        ProgramEvidenceBundle,
    )
    process_state, process_reasons = _process_attribution(protocol, program_spec)
    rules = {item.program_id: item for item in program_spec.program_rules}
    results: list[ProgramEvidenceSummary] = []
    flags: list[TranscriptomicReviewFlag] = []
    profile_reasons = set(process_reasons)
    ordered_records = sorted(
        bundle.records,
        key=lambda item: (
            item.program_id,
            item.analysis_scope.value,
            item.cell_state_id or "",
            item.evidence_id,
        ),
    )
    for record in ordered_records:
        rule = rules[record.program_id]
        reasons: list[str] = []
        stage_applicable = (
            window.review_state == "confirmed"
            and record.stage_id in rule.allowed_stage_ids
        )
        if window.review_state != "confirmed":
            reasons.append("development_window_unconfirmed")
        elif not stage_applicable:
            reasons.append("program_stage_not_applicable")
        state_applicable = (
            record.analysis_scope is AnalysisScope.WHOLE_PRODUCT
            or record.cell_state_id in rule.allowed_state_ids
        )
        if not state_applicable:
            reasons.append("program_state_not_applicable")
        applicable = stage_applicable and state_applicable
        if not applicable:
            applicability = ProgramApplicabilityState.NOT_APPLICABLE
            availability = ProgramAvailabilityState.UNAVAILABLE
            flag_state = ReviewFlagState.NOT_ASSESSED
        elif record.gene_coverage < rule.minimum_gene_coverage:
            applicability = ProgramApplicabilityState.APPLICABLE
            availability = ProgramAvailabilityState.UNAVAILABLE
            flag_state = ReviewFlagState.CANNOT_RESOLVE
            reasons.append("program_gene_coverage_insufficient")
        elif record.lod_state not in rule.resolvable_lod_states:
            applicability = ProgramApplicabilityState.APPLICABLE
            availability = ProgramAvailabilityState.CANNOT_RESOLVE
            flag_state = ReviewFlagState.CANNOT_RESOLVE
            reasons.append("program_lod_cannot_resolve")
        else:
            applicability = ProgramApplicabilityState.APPLICABLE
            availability = ProgramAvailabilityState.AVAILABLE
            flag_state = rule.review_outcomes[record.evidence_state]

        if flag_state is ReviewFlagState.NOT_DETECTED_ABOVE_LOD:
            reasons.append("untriggered_not_evidence_of_safety")
        record_process_state = (
            ProcessAttributionState.NOT_REQUESTED
            if not record.process_step_ids
            else process_state
        )
        if (
            record_process_state is ProcessAttributionState.CANNOT_ATTRIBUTE
            and process_reasons
        ):
            reasons.extend(process_reasons)
        reason_codes = sorted(set(reasons))
        profile_reasons.update(reason_codes)
        published_steps = (
            sorted(record.process_step_ids)
            if record_process_state is ProcessAttributionState.CONDITIONAL_ASSOCIATION
            else []
        )
        results.append(
            ProgramEvidenceSummary(
                evidence_id=record.evidence_id,
                program_id=record.program_id,
                analysis_scope=record.analysis_scope,
                cell_state_id=record.cell_state_id,
                stage_id=record.stage_id,
                metric_id=record.metric_id,
                value=record.value,
                unit=record.unit,
                numerator=record.numerator,
                denominator=record.denominator,
                gene_coverage=record.gene_coverage,
                minimum_gene_coverage=rule.minimum_gene_coverage,
                lod_state=record.lod_state,
                evidence_state=record.evidence_state,
                applicability=applicability,
                availability=availability,
                process_attribution=record_process_state,
                process_step_ids=published_steps,
                reason_codes=reason_codes,
            )
        )
        flags.append(
            TranscriptomicReviewFlag(
                flag_id=f"review-flag:{hashlib.sha256(record.evidence_id.encode()).hexdigest()[:20]}",
                evidence_id=record.evidence_id,
                program_id=record.program_id,
                analysis_scope=record.analysis_scope,
                cell_state_id=record.cell_state_id,
                stage_id=record.stage_id,
                review_flag_state=flag_state,
                applicability=applicability,
                availability=availability,
                process_attribution=record_process_state,
                orthogonal_follow_up_refs=rule.orthogonal_follow_up_refs,
                reason_codes=reason_codes,
            )
        )

    refs = sorted(
        (ref for ref in request.object_inputs if ref.role in BASE_ROLE_MODELS),
        key=lambda item: item.role,
    )
    bindings = [
        ProgramSourceBinding(
            input_id=ref.input_id,
            role=ref.role,
            schema_ref=ref.schema_ref,
            object_version=ref.object_version,
            source_sha256=ref.sha256,
        )
        for ref in refs
    ]
    return ProliferationStressResponseProfile(
        profile_id=f"proliferation-stress-profile:{input_hash[:24]}",
        profile_version="0.1.0",
        product_case_ref=product_case.ref,
        product_definition_ref=product_definition.ref,
        development_window_ref=window.ref,
        program_spec_ref=program_spec.ref,
        cell_state_profile_ref=cell_state.profile_id,
        protocol_context_ref=protocol.protocol_context_id,
        source_bindings=bindings,
        process_attribution_state=process_state,
        program_results=results,
        review_flags=flags,
        reason_codes=sorted(profile_reasons),
        created_at=bundle.created_at,
    )


def _profile_v2_without_projection(
    result: ProliferationStressResponseProfile,
) -> ProliferationStressResponseProfileV2:
    profile_payload = result.model_dump(mode="python")
    profile_payload.update(
        {
            "profile_version": "0.2.0",
            "measurement_projection_state": "not_requested",
            "measurement_spec_ref": None,
            "measurement_artifacts": [],
        }
    )
    return ProliferationStressResponseProfileV2.model_validate(profile_payload)


def _project_measurements(
    *,
    result: ProliferationStressResponseProfile,
    bundle: ProgramEvidenceBundle,
    measurement_spec: MeasurementSpecV2,
    run_id: str,
    tool_version: str,
    source_execution_state: str,
) -> tuple[
    ProliferationStressResponseProfileV2,
    list[MeasurementResultV2],
    dict[str, bytes],
]:
    records_by_evidence_id = {item.evidence_id: item for item in bundle.records}
    measurements: list[MeasurementResultV2] = []
    payloads: dict[str, bytes] = {}
    bindings: list[ProgramMeasurementArtifactBinding] = []
    for summary, flag in zip(
        result.program_results,
        result.review_flags,
        strict=True,
    ):
        projected_state = projected_program_evidence_state(
            applicability=summary.applicability,
            availability=summary.availability,
            review_flag_state=flag.review_flag_state,
        )
        carries_values = projected_state in {
            EvidenceState.NEGATIVE,
            EvidenceState.ALERT,
        }
        record = records_by_evidence_id[summary.evidence_id]
        token = hashlib.sha256(summary.evidence_id.encode("utf-8")).hexdigest()[:16]
        measurement = MeasurementResultV2(
            measurement_id=(
                f"measurement:{run_id.removeprefix('run-')}:program:{token}"
            ),
            measurement_spec_id=measurement_spec.measurement_spec_id,
            measurement_spec_version=measurement_spec.version,
            metric_name=summary.metric_id,
            raw_value=summary.value if carries_values else None,
            unit=summary.unit if carries_values else None,
            numerator=summary.numerator if carries_values else None,
            denominator=summary.denominator if carries_values else None,
            interval=None,
            interval_confidence_level=None,
            interval_method_ref=None,
            source_run_ref=f"tool-run:{run_id}@{tool_version}",
            source_execution_state=source_execution_state,
            unknown_scope=(
                "measurement" if projected_state is EvidenceState.UNKNOWN else None
            ),
            domain_score=None,
            score_state=ScoreState.UNAVAILABLE,
            evidence_state=projected_state,
            provenance_refs=sorted({record.source_run_ref, *record.provenance_refs}),
        )
        payload = canonical_json_bytes(measurement.model_dump(mode="json"), indent=2)
        file_name = f"program_measurement.{token}.json"
        artifact_id = f"artifact:{run_id}:program-measurement:{token}"
        measurements.append(measurement)
        payloads[file_name] = payload
        bindings.append(
            ProgramMeasurementArtifactBinding(
                measurement_id=measurement.measurement_id,
                evidence_id=summary.evidence_id,
                source_evidence_state=summary.evidence_state,
                projected_evidence_state=projected_state,
                artifact_id=artifact_id,
                file_name=file_name,
                sha256=hashlib.sha256(payload).hexdigest(),
            )
        )
    profile_payload = result.model_dump(mode="python")
    profile_payload.update(
        {
            "profile_version": "0.2.0",
            "measurement_projection_state": "available",
            "measurement_spec_ref": {
                "object_id": measurement_spec.measurement_spec_id,
                "object_version": measurement_spec.version,
            },
            "measurement_artifacts": bindings,
        }
    )
    return (
        ProliferationStressResponseProfileV2.model_validate(profile_payload),
        measurements,
        payloads,
    )


def _artifact_manifest_payload(
    *,
    request: ToolRequestV2,
    spec: ToolPackageSpecV2,
    run_id: str,
    input_hash: str,
    artifact_payloads: dict[str, bytes],
) -> dict[str, object]:
    return {
        "manifest_version": "0.1.0",
        "tool_id": spec.tool_id,
        "tool_version": spec.version,
        "run_id": run_id,
        "input_hash": input_hash,
        "inputs": [
            {
                "input_id": ref.input_id,
                "role": ref.role,
                "schema_ref": ref.schema_ref,
                "object_version": ref.object_version,
                "sha256": ref.sha256,
                "media_type": ref.media_type,
            }
            for ref in sorted(request.object_inputs, key=lambda item: item.role)
        ],
        "assets": [
            {
                "asset_id": asset.asset_id,
                "sha256": asset.checksum,
                "format": asset.format,
                "matrix_semantics": asset.matrix_semantics,
            }
            for asset in sorted(request.assets, key=lambda item: item.asset_id)
        ],
        "artifacts": [
            {
                "filename": filename,
                "media_type": _artifact_media_type(filename),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
            for filename, payload in sorted(artifact_payloads.items())
        ],
    }


def _artifact_media_type(filename: str) -> str:
    suffix = filename.rsplit(".", maxsplit=1)[-1].lower()
    media_types = {
        "json": "application/json",
        "pdf": "application/pdf",
        "png": "image/png",
        "svg": "image/svg+xml",
        "tsv": "text/tab-separated-values",
    }
    try:
        return media_types[suffix]
    except KeyError as exc:
        raise ValueError(f"unsupported artifact media type: {filename}") from exc


def _input_sha(request: ToolRequestV2, role: str) -> str:
    return next(ref.sha256 for ref in request.object_inputs if ref.role == role)


def _expression_asset_unchanged(
    assets: list[InputAsset],
    expected_sha256: str | None,
) -> bool:
    if expected_sha256 is None:
        return not assets
    if len(assets) != 1:
        return False
    try:
        return expression_asset_sha256(assets[0].path) == expected_sha256
    except ExpressionAssetError:
        return False


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
        result_schema_ref=spec.result_schema_ref,
        fingerprint_input_key="object_inputs",
        input_hash=input_hash,
    )


def _failed_v1_request(request: ToolRequest, spec: ToolPackageSpecV2) -> ToolRunV2:
    return _failed_run(request_v2_from_v1(request), spec, ["tool_request_v2_required"])
