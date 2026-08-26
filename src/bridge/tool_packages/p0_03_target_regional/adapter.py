from __future__ import annotations

import hashlib
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from bridge.tool_packages._configurable_contracts import (
    BiologicalUnitAssignmentArtifact,
    BiologicalUnitManifest,
    ProductCase,
    ProductDefinitionCard,
    StateRoleMap,
    profile_lineage_reasons,
)
from bridge.tool_packages._structured_runtime import (
    LoadedInputs,
    StructuredInputError,
    canonical_json_bytes,
    directory_state,
    failed_v2_run,
    inputs_unchanged,
    load_structured_inputs,
    read_regular_bytes,
    request_v2_from_v1,
    single_object,
)
from bridge.tool_packages.p0_03_target_regional.executor import (
    evaluate_target_regional,
)
from bridge.tool_packages.p0_03_target_regional.models import (
    TargetRegionalAssessmentSpec,
)
from bridge.toolkit.contracts import (
    AnnotationVocabulary,
    ArtifactManifest,
    CellStateCompositionView,
    CellStateEvidenceProfileV3,
    EligibilityResult,
    ExecutionState,
    FrozenModel,
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

RESULT_SCHEMA_REF = "bridge://schemas/target-regional-evidence-result/v0.1"
ROLE_MODELS: dict[str, tuple[str, type[FrozenModel]]] = {
    "product_case": ("bridge://schemas/product-case/v0.1", ProductCase),
    "product_definition_card": (
        "bridge://schemas/product-definition-card/v0.1",
        ProductDefinitionCard,
    ),
    "state_role_map": ("bridge://schemas/state-role-map/v0.1", StateRoleMap),
    "target_regional_assessment_spec": (
        "bridge://schemas/target-regional-assessment-spec/v0.1",
        TargetRegionalAssessmentSpec,
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
}
FIXED_OBJECT_VERSIONS = {
    "product_case": "0.1.0",
    "product_definition_card": "0.1.0",
    "state_role_map": "0.1.0",
    "target_regional_assessment_spec": "0.1.0",
    "cell_state_evidence_profile": "0.3.0",
    "qc_readiness_profile": "0.2.0",
    "biological_unit_manifest": "0.1.0",
    "biological_unit_assignment": "0.1.0",
}
EVIDENCE_REF = re.compile(r"^evidence:[A-Za-z0-9._:-]+$")
CELL_STATE_PROFILE_REF = re.compile(r"^cell-state-profile:[A-Za-z0-9._:-]+$")
QC_PROFILE_REF = re.compile(r"^qc-profile:[A-Za-z0-9._:-]+$")


@dataclass(frozen=True)
class TargetRegionalAdapter:
    def check_eligibility(
        self, request: ToolRequestV2, spec: ToolPackageSpecV2
    ) -> EligibilityResult:
        if not isinstance(request, ToolRequestV2):
            tool_id = request.tool_id if isinstance(request, ToolRequest) else "P0-03"
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
        state_role_map = single_object(
            request, loaded, "state_role_map", StateRoleMap
        )
        assessment_spec = single_object(
            request,
            loaded,
            "target_regional_assessment_spec",
            TargetRegionalAssessmentSpec,
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
        qc_profile = single_object(
            request, loaded, "qc_readiness_profile", QCReadinessProfileV2
        )
        biological_unit_manifest = single_object(
            request,
            loaded,
            "biological_unit_manifest",
            BiologicalUnitManifest,
        )
        annotation_vocabulary = single_object(
            request,
            loaded,
            "annotation_vocabulary",
            AnnotationVocabulary,
        )
        reference_manifest = single_object(
            request, loaded, "reference_manifest", ReferenceManifest
        )
        input_hash = _input_hash(request, spec)
        run_id = f"run-{input_hash[:16]}"
        evaluation = evaluate_target_regional(
            run_id=run_id,
            tool_version=spec.version,
            product_case=product_case,
            product_definition=product_definition,
            state_role_map=state_role_map,
            assessment_spec=assessment_spec,
            measurement_spec=measurement_spec,
            cell_state_profile=cell_state_profile,
            cell_state_profile_version=_input_version(
                request, "cell_state_evidence_profile"
            ),
            qc_profile=qc_profile,
            qc_profile_version=_input_version(request, "qc_readiness_profile"),
            biological_unit_manifest=biological_unit_manifest,
            annotation_vocabulary=annotation_vocabulary,
            reference_manifest=reference_manifest,
            input_sha256_by_role={
                ref.role: ref.sha256 for ref in request.object_inputs
            },
        )
        result_payload = canonical_json_bytes(
            evaluation.result.model_dump(mode="json"), indent=2
        )
        payloads = {
            "target_regional_evidence_result.json": result_payload,
            **evaluation.measurement_payloads,
        }
        try:
            output_files = _publish_json_bundle(
                request=request,
                run_id=run_id,
                payloads=payloads,
            )
        except StructuredInputError as exc:
            return _failed_run(
                request,
                spec,
                [exc.reason_code],
                input_hash=input_hash,
            )

        artifacts = [
            ArtifactManifest(
                artifact_id=f"artifact:{run_id}:target-regional-result",
                kind="target_regional_evidence_result",
                path=output_files["target_regional_evidence_result.json"],
                media_type="application/json",
                sha256=hashlib.sha256(result_payload).hexdigest(),
                evidence_ids=evaluation.result.evidence_refs,
            )
        ]
        binding_by_file = {
            item.file_name: item for item in evaluation.result.metric_artifacts
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
                    evidence_ids=evaluation.result.evidence_refs,
                )
            )
        execution_state = (
            ExecutionState.SUCCEEDED
            if evaluation.result.result_state == "complete"
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
            result=evaluation.result.model_dump(mode="json"),
            reason_codes=evaluation.result.reason_codes,
            warnings=[],
        )


adapter = TargetRegionalAdapter()


def _envelope_reasons(
    request: ToolRequestV2, spec: ToolPackageSpecV2
) -> list[str]:
    reasons: list[str] = []
    if request.tool_version is not None and request.tool_version != spec.version:
        reasons.append("tool_version_mismatch")
    if request.assets:
        reasons.append("p0_03_expression_assets_forbidden")
    if request.measurement_spec_ref is not None:
        reasons.append("p0_03_measurement_spec_parameter_forbidden")
    if request.parameters:
        reasons.append("p0_03_parameters_forbidden")
    if request.random_seed != 0:
        reasons.append("p0_03_random_seed_forbidden")
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
        version = value.version
    else:
        version = getattr(value, "object_version", None)
        if version is None:
            version = FIXED_OBJECT_VERSIONS.get(ref.role)
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
    state_role_map = single_object(request, loaded, "state_role_map", StateRoleMap)
    assessment_spec = single_object(
        request,
        loaded,
        "target_regional_assessment_spec",
        TargetRegionalAssessmentSpec,
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
    qc_profile = single_object(
        request, loaded, "qc_readiness_profile", QCReadinessProfileV2
    )
    biological_unit_manifest = single_object(
        request,
        loaded,
        "biological_unit_manifest",
        BiologicalUnitManifest,
    )
    biological_unit_assignment = single_object(
        request,
        loaded,
        "biological_unit_assignment",
        BiologicalUnitAssignmentArtifact,
    )
    annotation_vocabulary = single_object(
        request,
        loaded,
        "annotation_vocabulary",
        AnnotationVocabulary,
    )
    reference_manifest = single_object(
        request, loaded, "reference_manifest", ReferenceManifest
    )
    input_sha256_by_role = {
        ref.role: ref.sha256 for ref in request.object_inputs
    }
    reasons = profile_lineage_reasons(
        product_case=product_case,
        cell_state_profile=cell_state_profile,
        measurement_spec=measurement_spec,
        qc_profile=qc_profile,
        biological_unit_manifest=biological_unit_manifest,
        biological_unit_assignment_artifact=biological_unit_assignment,
        input_sha256_by_role=input_sha256_by_role,
    )
    if product_case.product_definition_ref != product_definition.ref:
        reasons.append("product_definition_binding_mismatch")
    if product_definition.state_role_map_ref != state_role_map.ref:
        reasons.append("state_role_map_binding_mismatch")
    if state_role_map.product_definition_ref != product_definition.ref:
        reasons.append("state_role_map_product_definition_mismatch")
    if assessment_spec.product_definition_ref != product_definition.ref:
        reasons.append("assessment_spec_product_definition_mismatch")
    if assessment_spec.state_role_map_ref != state_role_map.ref:
        reasons.append("state_role_map_binding_mismatch")
    if (
        assessment_spec.state_role_map_sha256
        != input_sha256_by_role["state_role_map"]
    ):
        reasons.append("state_role_map_checksum_mismatch")
    if product_case.assay not in product_definition.supported_assays:
        reasons.append("product_case_assay_not_supported")
    if measurement_spec.assay != product_case.assay:
        reasons.append("measurement_spec_assay_mismatch")
    if (
        measurement_spec.applicable_product_cards
        and product_definition.product_definition_id
        not in measurement_spec.applicable_product_cards
        and product_definition.ref.ref
        not in measurement_spec.applicable_product_cards
    ):
        reasons.append("measurement_spec_product_definition_not_applicable")
    if cell_state_profile.assay != product_case.assay:
        reasons.append("cell_state_profile_assay_mismatch")
    if qc_profile.assay != product_case.assay:
        reasons.append("qc_profile_assay_mismatch")
    if qc_profile.readiness_state in {
        ReadinessState.BLOCKED,
        ReadinessState.NOT_ASSESSED,
        ReadinessState.NOT_APPLICABLE,
    } or qc_profile.module_eligibility.get("P0-03") != "eligible":
        reasons.append("qc_not_ready_for_target_regional_evidence")
    if (
        cell_state_profile.measurement_spec_sha256
        != input_sha256_by_role["measurement_spec"]
    ):
        reasons.append("measurement_spec_checksum_mismatch")
    if (
        cell_state_profile.annotation_vocabulary_ref
        != annotation_vocabulary.vocabulary_id
        or cell_state_profile.annotation_vocabulary_version
        != annotation_vocabulary.version
    ):
        reasons.append("annotation_vocabulary_binding_mismatch")
    if (
        cell_state_profile.annotation_vocabulary_sha256
        != input_sha256_by_role["annotation_vocabulary"]
        or reference_manifest.vocabulary_sha256
        != input_sha256_by_role["annotation_vocabulary"]
    ):
        reasons.append("annotation_vocabulary_checksum_mismatch")
    if (
        cell_state_profile.reference_snapshot_ref != reference_manifest.snapshot_id
        or cell_state_profile.reference_manifest_version
        != reference_manifest.version
    ):
        reasons.append("reference_manifest_binding_mismatch")
    if (
        cell_state_profile.reference_manifest_sha256
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
    reference_source_ids = {item.source_id for item in reference_manifest.profiles}
    if set(assessment_spec.source_ids) - reference_source_ids:
        reasons.append("assessment_spec_reference_source_mismatch")
    vocabulary_labels = {
        (item.level, item.state_id) for item in annotation_vocabulary.labels
    }
    vocabulary_state_ids = {item.state_id for item in annotation_vocabulary.labels}
    role_map_state_ids = {item.state_id for item in state_role_map.assignments}
    if role_map_state_ids - vocabulary_state_ids:
        reasons.append("state_role_map_vocabulary_label_mismatch")
    configured_region_state_ids = {
        *assessment_spec.regional_denominator_state_ids,
        *assessment_spec.regional_target_numerator_state_ids,
        *assessment_spec.whole_product_target_region_state_ids,
    }
    if configured_region_state_ids - role_map_state_ids:
        reasons.append("state_role_map_binding_mismatch")
    if any(
        item.view is not CellStateCompositionView.RECONCILIATION_STATE
        and (item.label_level, item.label) not in vocabulary_labels
        for item in cell_state_profile.composition.records
    ):
        reasons.append("cell_state_vocabulary_label_mismatch")
    reasons.extend(
        _product_case_source_reasons(product_case, biological_unit_manifest)
    )
    if (
        qc_profile.measurement_spec_version != measurement_spec.version
        or qc_profile.measurement_spec_status != measurement_spec.status
        or cell_state_profile.measurement_spec_status != measurement_spec.status
    ):
        reasons.append("measurement_spec_profile_binding_mismatch")
    if any(
        not EVIDENCE_REF.fullmatch(evidence_ref)
        for evidence_ref in [*cell_state_profile.evidence_ids, *qc_profile.evidence_ids]
    ):
        reasons.append("unsafe_evidence_reference")
    if (
        not CELL_STATE_PROFILE_REF.fullmatch(cell_state_profile.profile_id)
        or not QC_PROFILE_REF.fullmatch(qc_profile.profile_id)
    ):
        reasons.append("unsafe_profile_reference")
    return sorted(set(reasons))


def _product_case_source_reasons(
    product_case: ProductCase, manifest: BiologicalUnitManifest
) -> list[str]:
    source_field = f"{product_case.source_unit_kind}_ref"
    source_refs = [getattr(item, source_field) for item in manifest.unit_bindings]
    if not source_refs or any(
        item is None or item != product_case.sample_or_preparation_ref
        for item in source_refs
    ):
        return ["product_case_source_unit_binding_mismatch"]
    return []


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


def _publish_json_bundle(
    *, request: ToolRequestV2, run_id: str, payloads: dict[str, bytes]
) -> dict[str, Path]:
    if not payloads or any(
        Path(name).name != name or not name.endswith(".json") for name in payloads
    ):
        raise StructuredInputError("output_filename_invalid")
    if (
        not run_id
        or not run_id.isascii()
        or any(not (character.isalnum() or character in "._-") for character in run_id)
        or run_id in {".", ".."}
    ):
        raise StructuredInputError("output_run_id_invalid")
    output_root = request.output_dir
    if directory_state(output_root) == "other":
        raise StructuredInputError("output_path_invalid")
    try:
        output_root.mkdir(parents=True, exist_ok=True)
    except (OSError, RuntimeError):
        raise StructuredInputError("output_path_invalid") from None
    if directory_state(output_root) != "directory":
        raise StructuredInputError("output_path_invalid")

    staging = output_root / f".{run_id}.staging-{uuid4().hex}"
    try:
        staging.mkdir(mode=0o700)
        for filename, payload in payloads.items():
            (staging / filename).write_bytes(payload)
        if not inputs_unchanged(request.object_inputs):
            raise StructuredInputError("structured_input_modified_during_run")
        final = output_root / run_id
        final_state = directory_state(final)
        if final_state == "directory":
            expected_names = set(payloads)
            try:
                matches = {item.name for item in final.iterdir()} == expected_names
                matches = matches and all(
                    read_regular_bytes(final / name) == payload
                    for name, payload in payloads.items()
                )
            except (OSError, RuntimeError):
                matches = False
            if not matches:
                raise StructuredInputError("existing_run_bundle_hash_mismatch")
            shutil.rmtree(staging)
        elif final_state == "missing":
            os.replace(staging, final)
        else:
            raise StructuredInputError("existing_run_bundle_hash_mismatch")
        published = {name: final / name for name in payloads}
        if any(
            read_regular_bytes(path) != payloads[name]
            for name, path in published.items()
        ):
            raise StructuredInputError("published_result_hash_mismatch")
        return published
    except StructuredInputError:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    except (OSError, RuntimeError):
        shutil.rmtree(staging, ignore_errors=True)
        raise StructuredInputError("output_path_invalid") from None


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


def _failed_v1_request(
    request: ToolRequest, spec: ToolPackageSpecV2
) -> ToolRunV2:
    return _failed_run(
        request_v2_from_v1(request), spec, ["tool_request_v2_required"]
    )
