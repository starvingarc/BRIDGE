from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import shutil
from uuid import uuid4

from bridge.tool_packages._configurable_contracts import (
    ProductCase,
    ProductDefinitionCard,
)
from bridge.tool_packages._structured_runtime import (
    LoadedInputs,
    canonical_json_bytes,
    directory_state,
    failed_v2_run,
    inputs_unchanged,
    load_structured_inputs,
    read_regular_bytes,
    single_object,
)
from bridge.tool_packages.p0_06_proliferation_stress_response.models import (
    AnalysisScope,
    BatchConfoundingState,
    DevelopmentWindowSpec,
    DevelopmentWindowState,
    ProcessAttributionState,
    ProgramApplicabilityState,
    ProgramAvailabilityState,
    ProgramEvidenceBundle,
    ProgramEvidenceSummary,
    ProgramSourceBinding,
    ProgramSpec,
    ProliferationStressResponseProfile,
    ProtocolIR,
    ProtocolMetadataState,
    ReviewFlagState,
    TranscriptomicReviewFlag,
)
from bridge.toolkit.contracts import (
    ArtifactManifest,
    CellStateEvidenceProfileV2,
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


RESULT_SCHEMA_REF = (
    "bridge://schemas/proliferation-stress-response-profile/v0.1"
)
ROLE_MODELS: dict[str, tuple[str, str, type[FrozenModel]]] = {
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


class PublicationError(ValueError):
    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


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
        reasons = _envelope_reasons(request, spec)
        loaded, loading_reasons = _load_inputs(request.object_inputs)
        reasons.extend(loading_reasons)
        if loaded is not None and not reasons:
            reasons.extend(_binding_reasons(request, loaded, spec))
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

        input_hash = _input_hash(request, spec)
        run_id = f"run-{input_hash[:16]}"
        result = _build_result(request, loaded, input_hash)
        result_bytes = canonical_json_bytes(result.model_dump(mode="json"), indent=2)
        result_sha = hashlib.sha256(result_bytes).hexdigest()
        manifest_bytes = canonical_json_bytes(
            _artifact_manifest_payload(
                request=request,
                spec=spec,
                run_id=run_id,
                input_hash=input_hash,
                result_sha=result_sha,
            ),
            indent=2,
        )
        try:
            published = _publish_bundle(
                request=request,
                run_id=run_id,
                payloads={
                    "proliferation_stress_response_profile.json": result_bytes,
                    "artifact_manifest.json": manifest_bytes,
                },
            )
        except PublicationError as exc:
            return _failed_run(
                request,
                spec,
                [exc.reason_code],
                input_hash=input_hash,
            )
        bundle = single_object(
            request,
            loaded,
            "program_evidence_bundle",
            ProgramEvidenceBundle,
        )
        evidence_ids = sorted(item.evidence_id for item in bundle.records)
        artifacts = [
            ArtifactManifest(
                artifact_id=f"artifact:{run_id}:{path.stem}",
                kind=path.stem,
                path=path,
                media_type="application/json",
                sha256=hashlib.sha256(read_regular_bytes(path)).hexdigest(),
                evidence_ids=evidence_ids,
            )
            for path in sorted(published.values(), key=lambda item: item.name)
        ]
        return ToolRunV2(
            run_id=run_id,
            request=request,
            implementation_state=ImplementationState.IMPLEMENTED,
            execution_state=ExecutionState.SUCCEEDED,
            tool_version=spec.version,
            environment_spec_id=spec.environment_spec_id,
            input_hash=input_hash,
            created_at=bundle.created_at,
            measurements=[],
            artifacts=artifacts,
            visualizations=[],
            result_schema_ref=RESULT_SCHEMA_REF,
            result=result.model_dump(mode="json"),
            reason_codes=[],
            warnings=[],
        )


adapter = ProliferationStressResponseAdapter()


def _envelope_reasons(
    request: ToolRequestV2, spec: ToolPackageSpecV2
) -> list[str]:
    reasons: list[str] = []
    if request.tool_version is not None and request.tool_version != spec.version:
        reasons.append("tool_version_mismatch")
    if request.assets:
        reasons.append("p0_06_expression_assets_forbidden")
    if request.measurement_spec_ref is not None:
        reasons.append("p0_06_measurement_spec_forbidden")
    if request.parameters:
        reasons.append("p0_06_parameters_forbidden")
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
        if contract is not None and ref.object_version != contract[1]:
            reasons.append("object_input_version_mismatch")
    if directory_state(request.output_dir) == "other":
        reasons.append("output_dir_not_regular_directory")
    return reasons


def _load_inputs(
    refs: list[StructuredInputRef],
) -> tuple[LoadedInputs | None, list[str]]:
    return load_structured_inputs(
        refs,
        model_for=lambda ref: ROLE_MODELS.get(ref.role, ("", "", None))[2],
        validate_model=_validate_object_version,
    )


def _validate_object_version(ref: StructuredInputRef, value: FrozenModel) -> None:
    expected = (
        "0.2.0"
        if isinstance(value, CellStateEvidenceProfileV2)
        else getattr(value, "object_version", None)
    )
    if expected != ref.object_version:
        from bridge.tool_packages._structured_runtime import StructuredInputError

        raise StructuredInputError("object_input_version_mismatch")


def _binding_reasons(
    request: ToolRequestV2,
    loaded: LoadedInputs,
    spec: ToolPackageSpecV2,
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
        CellStateEvidenceProfileV2,
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
        or program_spec.product_definition_ref != product_definition.ref
    ):
        reasons.append("product_context_binding_mismatch")
    if program_spec.development_window_ref != window.ref:
        reasons.append("development_window_binding_mismatch")
    if sorted(program_spec.aggregation_method_ids) != sorted(spec.method_ids):
        reasons.append("program_spec_method_binding_mismatch")
    if (
        cell_state.assay != product_case.assay
        or cell_state.measurement_spec_id
        != product_case.measurement_spec_ref.object_id
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
    return reasons


def _input_hash(request: ToolRequestV2, spec: ToolPackageSpecV2) -> str:
    payload = {
        "tool_id": spec.tool_id,
        "tool_version": spec.version,
        "environment_spec_id": spec.environment_spec_id,
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
        protocol.independent_replicate_count
        < rule.minimum_independent_replicates
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
            window.window_state is DevelopmentWindowState.CONFIRMED
            and record.stage_id in window.applicable_stage_ids
            and record.stage_id in rule.allowed_stage_ids
        )
        if window.window_state is not DevelopmentWindowState.CONFIRMED:
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
            if record_process_state
            is ProcessAttributionState.CONDITIONAL_ASSOCIATION
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

    refs = sorted(request.object_inputs, key=lambda item: item.role)
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


def _artifact_manifest_payload(
    *,
    request: ToolRequestV2,
    spec: ToolPackageSpecV2,
    run_id: str,
    input_hash: str,
    result_sha: str,
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
        "artifacts": [
            {
                "filename": "proliferation_stress_response_profile.json",
                "media_type": "application/json",
                "sha256": result_sha,
            }
        ],
    }


def _publish_bundle(
    *,
    request: ToolRequestV2,
    run_id: str,
    payloads: dict[str, bytes],
) -> dict[str, Path]:
    output_root = request.output_dir
    if directory_state(output_root) == "other":
        raise PublicationError("output_path_invalid")
    try:
        output_root.mkdir(parents=True, exist_ok=True)
    except (OSError, RuntimeError):
        raise PublicationError("output_path_invalid") from None
    if directory_state(output_root) != "directory":
        raise PublicationError("output_path_invalid")
    staging = output_root / f".{run_id}.staging-{uuid4().hex}"
    try:
        staging.mkdir(mode=0o700)
        for filename, payload in payloads.items():
            (staging / filename).write_bytes(payload)
        if not inputs_unchanged(request.object_inputs):
            raise PublicationError("structured_input_modified_during_run")
        final = output_root / run_id
        state = directory_state(final)
        if state == "directory":
            try:
                matches = {path.name for path in final.iterdir()} == set(payloads)
                matches = matches and all(
                    read_regular_bytes(final / filename) == payload
                    for filename, payload in payloads.items()
                )
            except (OSError, RuntimeError):
                matches = False
            if not matches:
                raise PublicationError("existing_run_bundle_hash_mismatch")
            shutil.rmtree(staging)
        elif state == "missing":
            os.replace(staging, final)
        else:
            raise PublicationError("existing_run_bundle_hash_mismatch")
        published = {name: final / name for name in payloads}
        if any(
            read_regular_bytes(path) != payloads[name]
            for name, path in published.items()
        ):
            raise PublicationError("published_result_hash_mismatch")
        return published
    except PublicationError:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    except (OSError, RuntimeError):
        shutil.rmtree(staging, ignore_errors=True)
        raise PublicationError("output_path_invalid") from None


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
