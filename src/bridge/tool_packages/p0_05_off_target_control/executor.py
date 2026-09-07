from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Literal

from bridge.tool_packages._configurable_contracts import (
    BiologicalUnitManifest,
    BiologicalUnitAttestationReceipt,
    ProductCase,
    ProductDefinitionCard,
    VersionedObjectRef,
)
from bridge.tool_packages._structured_runtime import canonical_json_bytes
from bridge.tool_packages.p0_05_off_target_control.models import (
    CoverageState,
    HardCountMetricName,
    OffTargetAssessmentSpec,
    OffTargetControlProfile,
    OffTargetControlProfileV2,
    OffTargetHardCountAccounting,
    OffTargetHardCountMeasurementArtifactBinding,
    OffTargetHardCountProfileV1,
    OffTargetHardCountRoleRecord,
    OffTargetMeasurementArtifactBinding,
    ProductRole,
    StateRoleMap,
    RareDetectionState,
    rare_projection_evidence_state,
    role_projection_evidence_state,
    unknown_projection_evidence_state,
)
from bridge.toolkit.contracts import (
    CellStateEvidenceProfileV3,
    EvidenceState,
    MeasurementResultV2,
    MeasurementSpecV2,
    ScoreState,
)

ROLE_METRIC_NAME = "off_target_role_composition"
UNKNOWN_METRIC_NAME = "off_target_identity_unknown"
RARE_METRIC_NAME = "off_target_rare_state_detection"
MEASUREMENT_PROJECTION_METRIC_NAMES = frozenset(
    {ROLE_METRIC_NAME, UNKNOWN_METRIC_NAME, RARE_METRIC_NAME}
)
HARD_COUNT_METRIC_NAME = "off_target_hard_count_accounting"
SOFT_MASS_UNAVAILABLE_METRIC_NAME = "off_target_soft_mass_composition"
HARD_COUNT_MEASUREMENT_METRIC_NAMES = frozenset(
    {
        HARD_COUNT_METRIC_NAME,
        SOFT_MASS_UNAVAILABLE_METRIC_NAME,
        UNKNOWN_METRIC_NAME,
        RARE_METRIC_NAME,
    }
)


@dataclass(frozen=True)
class MeasurementProjectionBundle:
    profile: OffTargetControlProfileV2
    measurements: list[MeasurementResultV2]
    payloads: dict[str, bytes]


@dataclass(frozen=True)
class HardCountMeasurementProjectionBundle:
    profile: OffTargetHardCountProfileV1
    measurements: list[MeasurementResultV2]
    payloads: dict[str, bytes]


@dataclass(frozen=True)
class _ProjectionDraft:
    metric_name: Literal[
        "off_target_role_composition",
        "off_target_identity_unknown",
        "off_target_rare_state_detection",
    ]
    record_scope: Literal["role", "identity_unknown", "rare_state"]
    record_id: str
    raw_record: dict
    evidence_state: EvidenceState
    unknown_scope: Literal["identity", "measurement"] | None = None


def aggregate_hard_count_profile(
    *,
    tool_version: str,
    input_hash: str,
    product_case: ProductCase,
    product_definition: ProductDefinitionCard,
    role_map: StateRoleMap,
    assessment_spec: OffTargetAssessmentSpec,
    cell_state_profile: CellStateEvidenceProfileV3,
    biological_units: BiologicalUnitManifest,
    attestation_receipt: BiologicalUnitAttestationReceipt,
    input_sha256_by_role: dict[str, str],
) -> OffTargetHardCountProfileV1:
    assignments = {item.state_id: item.product_role for item in role_map.assignments}
    count_by_role = {role: 0 for role in ProductRole}
    for record in cell_state_profile.composition.records:
        if record.view.value == "consensus_supported_only":
            count_by_role[assignments[record.label]] += record.count
    reason_codes = {
        "consensus_support_is_not_biological_independence",
        "hard_count_support_is_not_soft_mass",
        "open_set_assessment_not_assessed",
        "rare_state_detection_not_assessed",
        "whole_view_count_has_no_per_unit_or_bootstrap_estimate",
    }
    if any(count == 0 for count in count_by_role.values()):
        reason_codes.add("zero_role_count_does_not_establish_absence")
    if sum(count_by_role.values()) == 0:
        reason_codes.add("zero_consensus_support_does_not_establish_absence")
    n_observations = cell_state_profile.n_observations
    accounting = OffTargetHardCountAccounting(
        primary_denominator_id=assessment_spec.primary_denominator_id,
        n_observations=n_observations,
        observation_unit=(
            "nucleus" if cell_state_profile.assay == "snRNA-seq" else "cell"
        ),
        producer_composition=cell_state_profile.composition,
        role_counts=[
            OffTargetHardCountRoleRecord(
                product_role=role,
                consensus_supported_count=count_by_role[role],
                fraction_of_selected_view=float(
                    count_by_role[role] / n_observations
                ),
                support_basis="consensus_supported_only",
                exclusion_state="cannot_exclude",
            )
            for role in ProductRole
        ],
        accounting_basis="producer_reference_support_counts",
        accounting_state="complete",
        mass_state="unavailable",
        total_soft_mass=None,
        reason_codes=sorted(reason_codes),
    )
    profile_reasons = set(accounting.reason_codes)
    profile_reasons.add("biological_unit_attestation_is_caller_declared")
    return OffTargetHardCountProfileV1(
        object_version="0.1.0",
        profile_id=f"off-target-hard-count:{input_hash[:24]}",
        profile_version="0.1.0",
        tool_id="P0-05",
        tool_version=tool_version,
        product_case_ref=product_case.ref.ref,
        product_case_sha256=input_sha256_by_role["product_case"],
        product_definition_ref=product_definition.ref.ref,
        product_definition_sha256=input_sha256_by_role[
            "product_definition_card"
        ],
        state_role_map_ref=role_map.ref.ref,
        state_role_map_sha256=input_sha256_by_role["state_role_map"],
        assessment_spec_ref=assessment_spec.ref.ref,
        assessment_spec_sha256=input_sha256_by_role[
            "off_target_assessment_spec"
        ],
        cell_state_profile_id=cell_state_profile.profile_id,
        cell_state_profile_sha256=input_sha256_by_role[
            "cell_state_evidence_profile"
        ],
        biological_unit_manifest_ref=biological_units.ref.ref,
        biological_unit_manifest_sha256=input_sha256_by_role[
            "biological_unit_manifest"
        ],
        biological_unit_attestation_receipt_ref=attestation_receipt.ref.ref,
        biological_unit_attestation_receipt_sha256=input_sha256_by_role[
            "biological_unit_attestation_receipt"
        ],
        input_data_view=cell_state_profile.input_data_view,
        accounting=accounting,
        open_set_assessment_state="not_assessed",
        rare_detection_state="not_assessed",
        measurement_projection_state="not_requested",
        measurement_spec_ref=None,
        measurement_spec_sha256=None,
        measurement_artifacts=[],
        evidence_state="shadow",
        score_state="unavailable",
        domain_score=None,
        reason_codes=sorted(profile_reasons),
        created_at=product_case.created_at,
    )


def project_hard_count_measurements(
    *,
    run_id: str,
    profile: OffTargetHardCountProfileV1,
    measurement_spec: MeasurementSpecV2,
    measurement_spec_sha256: str,
    evidence_refs: list[str],
) -> HardCountMeasurementProjectionBundle:
    evidence_by_metric = {
        HARD_COUNT_METRIC_NAME: EvidenceState.INFERRED,
        SOFT_MASS_UNAVAILABLE_METRIC_NAME: EvidenceState.UNAVAILABLE,
        UNKNOWN_METRIC_NAME: EvidenceState.UNAVAILABLE,
        RARE_METRIC_NAME: EvidenceState.UNAVAILABLE,
    }
    measurements: list[MeasurementResultV2] = []
    payloads: dict[str, bytes] = {}
    bindings: list[OffTargetHardCountMeasurementArtifactBinding] = []
    run_token = run_id.removeprefix("run-")
    for metric_name in sorted(HARD_COUNT_MEASUREMENT_METRIC_NAMES):
        evidence_state = evidence_by_metric[metric_name]
        token = _record_token("hard_count", metric_name)
        measurement = MeasurementResultV2(
            measurement_id=f"measurement:{run_token}:{token}:{metric_name}",
            measurement_spec_id=measurement_spec.measurement_spec_id,
            measurement_spec_version=measurement_spec.version,
            metric_name=metric_name,
            raw_value=(
                profile.accounting.model_dump(mode="json")
                if metric_name == HARD_COUNT_METRIC_NAME
                else None
            ),
            unit=None,
            numerator=None,
            denominator=None,
            interval=None,
            interval_confidence_level=None,
            interval_method_ref=None,
            source_run_ref=f"tool-run:{run_id}@{profile.tool_version}",
            source_execution_state="succeeded",
            unknown_scope=None,
            domain_score=None,
            score_state=ScoreState.UNAVAILABLE,
            evidence_state=evidence_state,
            provenance_refs=evidence_refs,
        )
        payload = canonical_json_bytes(measurement.model_dump(mode="json"), indent=2)
        filename = f"{token}.{metric_name}.measurement_result.json"
        artifact_id = f"artifact:{run_id}:{token}:{metric_name}"
        sha256 = hashlib.sha256(payload).hexdigest()
        measurements.append(measurement)
        payloads[filename] = payload
        bindings.append(
            OffTargetHardCountMeasurementArtifactBinding(
                measurement_id=measurement.measurement_id,
                metric_name=metric_name,
                evidence_state=evidence_state.value,
                artifact_id=artifact_id,
                file_name=filename,
                sha256=sha256,
            )
        )
    projected = OffTargetHardCountProfileV1.model_validate(
        {
            **profile.model_dump(mode="python"),
            "measurement_projection_state": "available",
            "measurement_spec_ref": VersionedObjectRef(
                object_id=measurement_spec.measurement_spec_id,
                object_version=measurement_spec.version,
            ),
            "measurement_spec_sha256": measurement_spec_sha256,
            "measurement_artifacts": bindings,
        }
    )
    return HardCountMeasurementProjectionBundle(
        profile=projected,
        measurements=measurements,
        payloads=payloads,
    )


def profile_v2_without_projection(
    profile: OffTargetControlProfile,
) -> OffTargetControlProfileV2:
    return OffTargetControlProfileV2.model_validate(
        {
            **profile.model_dump(mode="python"),
            "object_version": "0.2.0",
            "profile_version": "0.2.0",
            "measurement_projection_state": "not_requested",
            "measurement_spec_ref": None,
            "measurement_spec_sha256": None,
            "measurement_artifacts": [],
        }
    )


def project_off_target_measurements(
    *,
    run_id: str,
    tool_version: str,
    profile: OffTargetControlProfile,
    measurement_spec: MeasurementSpecV2,
    measurement_spec_sha256: str,
    evidence_refs: list[str],
) -> MeasurementProjectionBundle:
    drafts = _projection_drafts(profile)
    measurements: list[MeasurementResultV2] = []
    payloads: dict[str, bytes] = {}
    bindings: list[OffTargetMeasurementArtifactBinding] = []
    for draft in drafts:
        token = _record_token(draft.record_scope, draft.record_id)
        measurement = _measurement(
            run_id=run_id,
            tool_version=tool_version,
            measurement_spec=measurement_spec,
            draft=draft,
            token=token,
            evidence_refs=evidence_refs,
        )
        payload = canonical_json_bytes(measurement.model_dump(mode="json"), indent=2)
        filename = f"{token}.{draft.metric_name}.measurement_result.json"
        artifact_id = f"artifact:{run_id}:{token}:{draft.metric_name}"
        sha256 = hashlib.sha256(payload).hexdigest()
        measurements.append(measurement)
        payloads[filename] = payload
        bindings.append(
            OffTargetMeasurementArtifactBinding(
                measurement_id=measurement.measurement_id,
                metric_name=draft.metric_name,
                record_scope=draft.record_scope,
                record_id=draft.record_id,
                evidence_state=draft.evidence_state,
                artifact_id=artifact_id,
                file_name=filename,
                sha256=sha256,
            )
        )

    profile_v2 = OffTargetControlProfileV2.model_validate(
        {
            **profile.model_dump(mode="python"),
            "object_version": "0.2.0",
            "profile_version": "0.2.0",
            "measurement_projection_state": "available",
            "measurement_spec_ref": VersionedObjectRef(
                object_id=measurement_spec.measurement_spec_id,
                object_version=measurement_spec.version,
            ),
            "measurement_spec_sha256": measurement_spec_sha256,
            "measurement_artifacts": sorted(
                bindings, key=lambda item: item.file_name
            ),
        }
    )
    return MeasurementProjectionBundle(
        profile=profile_v2,
        measurements=measurements,
        payloads=payloads,
    )


def _projection_drafts(profile: OffTargetControlProfile) -> list[_ProjectionDraft]:
    drafts = [
        _ProjectionDraft(
            metric_name=ROLE_METRIC_NAME,
            record_scope="role",
            record_id=record.product_role.value,
            raw_record=record.model_dump(mode="json"),
            evidence_state=role_projection_evidence_state(record.assessment_state),
        )
        for record in profile.role_composition
    ]
    drafts.append(
        _ProjectionDraft(
            metric_name=UNKNOWN_METRIC_NAME,
            record_scope="identity_unknown",
            record_id="identity-unknown",
            raw_record=profile.unknown_profile.model_dump(mode="json"),
            evidence_state=unknown_projection_evidence_state(
                profile.unknown_profile.coverage_state
            ),
            unknown_scope=(
                "identity"
                if profile.unknown_profile.coverage_state
                is not CoverageState.NOT_ASSESSED
                else None
            ),
        )
    )
    drafts.extend(
        _ProjectionDraft(
            metric_name=RARE_METRIC_NAME,
            record_scope="rare_state",
            record_id=record.state_id,
            raw_record=record.model_dump(mode="json"),
            evidence_state=rare_projection_evidence_state(record.detection_state),
            unknown_scope=(
                "measurement"
                if record.detection_state is RareDetectionState.CANNOT_EXCLUDE
                else None
            ),
        )
        for record in profile.rare_state_profile
    )
    return sorted(
        drafts,
        key=lambda item: (item.record_scope, item.record_id, item.metric_name),
    )


def _measurement(
    *,
    run_id: str,
    tool_version: str,
    measurement_spec: MeasurementSpecV2,
    draft: _ProjectionDraft,
    token: str,
    evidence_refs: list[str],
) -> MeasurementResultV2:
    raw_value = (
        None
        if draft.evidence_state is EvidenceState.UNAVAILABLE
        or (
            draft.evidence_state is EvidenceState.UNKNOWN
            and draft.unknown_scope == "measurement"
        )
        else draft.raw_record
    )
    run_token = run_id.removeprefix("run-")
    return MeasurementResultV2(
        measurement_id=f"measurement:{run_token}:{token}:{draft.metric_name}",
        measurement_spec_id=measurement_spec.measurement_spec_id,
        measurement_spec_version=measurement_spec.version,
        metric_name=draft.metric_name,
        raw_value=raw_value,
        unit=None,
        numerator=None,
        denominator=None,
        interval=None,
        interval_confidence_level=None,
        interval_method_ref=None,
        source_run_ref=f"tool-run:{run_id}@{tool_version}",
        source_execution_state="succeeded",
        unknown_scope=draft.unknown_scope,
        domain_score=None,
        score_state=ScoreState.UNAVAILABLE,
        evidence_state=draft.evidence_state,
        provenance_refs=evidence_refs,
    )


def _record_token(record_scope: str, record_id: str) -> str:
    digest = hashlib.sha256(
        canonical_json_bytes([record_scope, record_id])
    ).hexdigest()[:12]
    scope_token = record_scope.replace("_", "-")
    return f"p005-{scope_token}-{digest}"
