from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Literal

from bridge.tool_packages._configurable_contracts import (
    BiologicalUnitManifest,
    CompositionView,
    ProductCase,
    ProductDefinitionCard,
    ProductRole,
    RoleFraction,
    StateRoleMap,
    VersionedObjectRef,
)
from bridge.tool_packages._structured_runtime import canonical_json_bytes
from bridge.tool_packages.p0_03_target_regional.method_models import (
    TargetRegionalMethodArtifactBinding,
)
from bridge.tool_packages.p0_03_target_regional.models import (
    ChannelAssessmentState,
    MetricArtifactBinding,
    NormalizedMetricName,
    TargetRegionalAssessmentSpec,
    TargetRegionalChannelResult,
    TargetRegionalEvidenceResult,
)
from bridge.toolkit.contracts import (
    AnnotationVocabulary,
    CellStateCompositionRecord,
    CellStateCompositionRecordState,
    CellStateCompositionView,
    CellStateEvidenceProfileV3,
    EvidenceState,
    MeasurementResultV2,
    MeasurementSpecV2,
    QCReadinessProfileV2,
    ReferenceManifest,
    ScoreState,
)

ChannelKey = tuple[CompositionView, str | None, Literal["L1", "L2", "L3"]]


@dataclass(frozen=True)
class EvaluationBundle:
    result: TargetRegionalEvidenceResult
    measurements: list[MeasurementResultV2]
    measurement_payloads: dict[str, bytes]


@dataclass(frozen=True)
class _ChannelDraft:
    key: ChannelKey
    state: ChannelAssessmentState
    target_identity: RoleFraction | None
    regional_fidelity: RoleFraction | None
    whole_product_target_region: RoleFraction | None
    evidence_state: EvidenceState
    reasons: tuple[str, ...]


def evaluate_target_regional(
    *,
    run_id: str,
    tool_version: str,
    product_case: ProductCase,
    product_definition: ProductDefinitionCard,
    state_role_map: StateRoleMap,
    assessment_spec: TargetRegionalAssessmentSpec,
    measurement_spec: MeasurementSpecV2,
    cell_state_profile: CellStateEvidenceProfileV3,
    cell_state_profile_version: str,
    qc_profile: QCReadinessProfileV2,
    qc_profile_version: str,
    biological_unit_manifest: BiologicalUnitManifest,
    annotation_vocabulary: AnnotationVocabulary,
    reference_manifest: ReferenceManifest,
    input_sha256_by_role: dict[str, str],
    method_artifact: TargetRegionalMethodArtifactBinding | None = None,
    method_reason_codes: list[str] | None = None,
) -> EvaluationBundle:
    assignments = {item.state_id: item for item in state_role_map.assignments}
    records = cell_state_profile.composition.records
    blocking_reason, blocking_state = _composition_block(records)
    if cell_state_profile.composition.state != "shadow":
        blocking_reason = (
            f"cell_state_composition_{cell_state_profile.composition.state}"
        )
        blocking_state = (
            EvidenceState.UNKNOWN
            if cell_state_profile.composition.state == "unknown"
            else EvidenceState.UNAVAILABLE
        )

    drafts: list[_ChannelDraft] = []
    for key in _expected_channels(assessment_spec):
        if blocking_reason is not None:
            drafts.append(_not_assessed_draft(key, blocking_reason, blocking_state))
            continue
        selected = _selected_records(records, key)
        if not selected:
            drafts.append(
                _not_assessed_draft(
                    key,
                    "requested_composition_channel_unavailable",
                    EvidenceState.UNAVAILABLE,
                )
            )
            continue
        denominator = cell_state_profile.input_data_view.n_observations
        if sum(item.count for item in selected) != denominator:
            drafts.append(
                _not_assessed_draft(
                    key,
                    "composition_channel_not_denominator_complete",
                    EvidenceState.UNAVAILABLE,
                )
            )
            continue
        channel_assignments = [assignments.get(item.label) for item in selected]
        if any(item is None for item in channel_assignments):
            drafts.append(
                _not_assessed_draft(
                    key,
                    "state_role_mapping_incomplete",
                    EvidenceState.UNAVAILABLE,
                )
            )
            continue
        resolved = [item for item in channel_assignments if item is not None]
        if any(item.product_role is ProductRole.ROLE_UNRESOLVED for item in resolved):
            drafts.append(
                _not_assessed_draft(
                    key,
                    "state_role_mapping_unresolved",
                    EvidenceState.UNKNOWN,
                )
            )
            continue
        drafts.append(
            _numeric_draft(
                key,
                selected,
                resolved,
                assessment_spec,
                denominator,
            )
        )

    result_state = _result_state(drafts)
    source_execution_state: Literal["succeeded", "partial"] = (
        "succeeded" if result_state == "complete" else "partial"
    )
    evidence_refs = sorted(
        set(cell_state_profile.evidence_ids) | set(qc_profile.evidence_ids)
    )
    channels: list[TargetRegionalChannelResult] = []
    measurements: list[MeasurementResultV2] = []
    payloads: dict[str, bytes] = {}
    artifact_bindings: list[MetricArtifactBinding] = []
    for draft in drafts:
        measurement_ids: dict[NormalizedMetricName, str] = {}
        values = {
            NormalizedMetricName.TARGET_IDENTITY_FRACTION: draft.target_identity,
            NormalizedMetricName.REGIONAL_FIDELITY_FRACTION: draft.regional_fidelity,
            NormalizedMetricName.WHOLE_PRODUCT_TARGET_REGION_FRACTION: (
                draft.whole_product_target_region
            ),
        }
        channel_token = _channel_token(draft.key)
        for metric_name in NormalizedMetricName:
            measurement = _measurement(
                run_id=run_id,
                tool_version=tool_version,
                measurement_spec=measurement_spec,
                metric_name=metric_name,
                channel_token=channel_token,
                ratio=values[metric_name],
                evidence_state=draft.evidence_state,
                source_execution_state=source_execution_state,
                evidence_refs=evidence_refs,
            )
            payload = canonical_json_bytes(
                measurement.model_dump(mode="json"), indent=2
            )
            filename = f"{channel_token}.{metric_name.value}.measurement_result.json"
            artifact_id = f"artifact:{run_id}:{channel_token}:{metric_name.value}"
            measurements.append(measurement)
            payloads[filename] = payload
            measurement_ids[metric_name] = measurement.measurement_id
            artifact_bindings.append(
                MetricArtifactBinding(
                    measurement_id=measurement.measurement_id,
                    metric_name=metric_name,
                    composition_view=draft.key[0],
                    source_id=draft.key[1],
                    label_level=draft.key[2],
                    artifact_id=artifact_id,
                    file_name=filename,
                    sha256=hashlib.sha256(payload).hexdigest(),
                )
            )
        channels.append(
            TargetRegionalChannelResult(
                composition_view=draft.key[0],
                source_id=draft.key[1],
                label_level=draft.key[2],
                denominator_scope="selected_data_view",
                assessment_state=draft.state,
                target_identity_fraction=draft.target_identity,
                regional_fidelity_fraction=draft.regional_fidelity,
                whole_product_target_region_fraction=(
                    draft.whole_product_target_region
                ),
                measurement_ids=measurement_ids,
                reason_codes=list(draft.reasons),
            )
        )

    reasons = sorted(
        {
            "spatial_projection_not_supplied",
            *(reason for draft in drafts for reason in draft.reasons),
            *(method_reason_codes or []),
        }
    )
    result = TargetRegionalEvidenceResult(
        object_version="0.2.0",
        result_id=f"target-regional-result:{run_id.removeprefix('run-')}",
        tool_id="P0-03",
        tool_version=tool_version,
        product_case_ref=product_case.ref,
        product_definition_ref=product_definition.ref,
        state_role_map_ref=state_role_map.ref,
        assessment_spec_ref=assessment_spec.ref,
        measurement_spec_ref=VersionedObjectRef(
            object_id=measurement_spec.measurement_spec_id,
            object_version=measurement_spec.version,
        ),
        cell_state_profile_ref=VersionedObjectRef(
            object_id=cell_state_profile.profile_id,
            object_version=cell_state_profile_version,
        ),
        qc_profile_ref=VersionedObjectRef(
            object_id=qc_profile.profile_id,
            object_version=qc_profile_version,
        ),
        biological_unit_manifest_ref=biological_unit_manifest.ref,
        annotation_vocabulary_ref=VersionedObjectRef(
            object_id=annotation_vocabulary.vocabulary_id,
            object_version=annotation_vocabulary.version,
        ),
        reference_manifest_ref=VersionedObjectRef(
            object_id=reference_manifest.snapshot_id,
            object_version=reference_manifest.version,
        ),
        input_sha256_by_role=input_sha256_by_role,
        upstream_composition_state=cell_state_profile.composition.state,
        result_state=result_state,
        channels=channels,
        metric_artifacts=sorted(artifact_bindings, key=lambda item: item.file_name),
        method_artifact=method_artifact,
        spatial_projection_state="not_assessed",
        evidence_refs=evidence_refs,
        reason_codes=reasons,
        domain_score=None,
        score_state=(
            ScoreState.UNAVAILABLE
            if result_state == "not_assessed"
            else ScoreState.SHADOW
        ),
    )
    return EvaluationBundle(
        result=result,
        measurements=measurements,
        measurement_payloads=payloads,
    )


def _expected_channels(spec: TargetRegionalAssessmentSpec) -> list[ChannelKey]:
    keys: list[ChannelKey] = []
    for view in spec.composition_views:
        sources: list[str | None] = (
            list(spec.source_ids) if view is CompositionView.SOURCE_SPECIFIC else [None]
        )
        for source_id in sources:
            for level in spec.included_label_levels:
                keys.append((view, source_id, level))
    return sorted(keys, key=lambda item: (item[0].value, item[1] or "", item[2]))


def _selected_records(
    records: list[CellStateCompositionRecord], key: ChannelKey
) -> list[CellStateCompositionRecord]:
    view, source_id, level = key
    return sorted(
        [
            item
            for item in records
            if item.view.value == view.value
            and item.source_id == source_id
            and item.label_level == level
        ],
        key=lambda item: item.label,
    )


def _composition_block(
    records: list[CellStateCompositionRecord],
) -> tuple[str | None, EvidenceState]:
    states = {
        item.state_evidence_state
        for item in records
        if item.view is CellStateCompositionView.RECONCILIATION_STATE
        and item.count > 0
        and item.state_evidence_state is not CellStateCompositionRecordState.CANDIDATE
    }
    if states & {
        CellStateCompositionRecordState.UNKNOWN,
        CellStateCompositionRecordState.OOD,
    }:
        return "upstream_unknown_or_ood_not_assessed", EvidenceState.UNKNOWN
    if CellStateCompositionRecordState.UNRESOLVED in states:
        return "upstream_composition_unresolved", EvidenceState.UNKNOWN
    if CellStateCompositionRecordState.UNAVAILABLE in states:
        return "upstream_composition_unavailable", EvidenceState.UNAVAILABLE
    return None, EvidenceState.INFERRED


def _not_assessed_draft(
    key: ChannelKey, reason: str, evidence_state: EvidenceState
) -> _ChannelDraft:
    return _ChannelDraft(
        key=key,
        state=ChannelAssessmentState.NOT_ASSESSED,
        target_identity=None,
        regional_fidelity=None,
        whole_product_target_region=None,
        evidence_state=evidence_state,
        reasons=(reason,),
    )


def _numeric_draft(
    key: ChannelKey,
    records: list[CellStateCompositionRecord],
    assignments: list,
    spec: TargetRegionalAssessmentSpec,
    denominator: int,
) -> _ChannelDraft:
    target_count = sum(
        record.count
        for record, assignment in zip(records, assignments, strict=True)
        if assignment.product_role in spec.target_identity_numerator_product_roles
    )
    target_related_count = sum(
        record.count
        for record in records
        if record.label in spec.regional_denominator_state_ids
    )
    regional_target_count = sum(
        record.count
        for record in records
        if record.label in spec.regional_target_numerator_state_ids
    )
    whole_region_count = sum(
        record.count
        for record in records
        if record.label in spec.whole_product_target_region_state_ids
    )
    target_fraction = _fraction("configured_target_identity", target_count, denominator)
    whole_fraction = _fraction(
        "configured_whole_product_target_region",
        whole_region_count,
        denominator,
    )
    if target_related_count == 0:
        return _ChannelDraft(
            key=key,
            state=ChannelAssessmentState.PARTIAL,
            target_identity=target_fraction,
            regional_fidelity=None,
            whole_product_target_region=whole_fraction,
            evidence_state=EvidenceState.INFERRED,
            reasons=("target_related_denominator_zero",),
        )
    return _ChannelDraft(
        key=key,
        state=ChannelAssessmentState.COMPLETE,
        target_identity=target_fraction,
        regional_fidelity=_fraction(
            "configured_regional_fidelity",
            regional_target_count,
            target_related_count,
        ),
        whole_product_target_region=whole_fraction,
        evidence_state=EvidenceState.INFERRED,
        reasons=(),
    )


def _fraction(role: str, numerator: int, denominator: int) -> RoleFraction:
    return RoleFraction(
        role=role,
        numerator=numerator,
        denominator=denominator,
        fraction=numerator / denominator,
    )


def _result_state(
    drafts: list[_ChannelDraft],
) -> Literal["complete", "partial", "not_assessed"]:
    if all(item.state is ChannelAssessmentState.COMPLETE for item in drafts):
        return "complete"
    if all(item.state is ChannelAssessmentState.NOT_ASSESSED for item in drafts):
        return "not_assessed"
    return "partial"


def _channel_token(key: ChannelKey) -> str:
    raw = canonical_json_bytes([key[0].value, key[1], key[2]])
    return hashlib.sha256(raw).hexdigest()[:12]


def _measurement(
    *,
    run_id: str,
    tool_version: str,
    measurement_spec: MeasurementSpecV2,
    metric_name: NormalizedMetricName,
    channel_token: str,
    ratio: RoleFraction | None,
    evidence_state: EvidenceState,
    source_execution_state: Literal["succeeded", "partial"],
    evidence_refs: list[str],
) -> MeasurementResultV2:
    resolved_state = evidence_state
    if ratio is None and evidence_state is EvidenceState.INFERRED:
        resolved_state = EvidenceState.UNAVAILABLE
    return MeasurementResultV2(
        measurement_id=(
            f"measurement:{run_id.removeprefix('run-')}:{channel_token}:"
            f"{metric_name.value}"
        ),
        measurement_spec_id=measurement_spec.measurement_spec_id,
        measurement_spec_version=measurement_spec.version,
        metric_name=metric_name.value,
        raw_value=None if ratio is None else ratio.fraction,
        unit="fraction",
        numerator=None if ratio is None else ratio.numerator,
        denominator=None if ratio is None else ratio.denominator,
        interval=None,
        interval_confidence_level=None,
        interval_method_ref=None,
        source_run_ref=f"tool-run:{run_id}@{tool_version}",
        source_execution_state=source_execution_state,
        unknown_scope=(
            "measurement" if resolved_state is EvidenceState.UNKNOWN else None
        ),
        domain_score=None,
        score_state=(
            ScoreState.SHADOW if ratio is not None else ScoreState.UNAVAILABLE
        ),
        evidence_state=resolved_state,
        provenance_refs=evidence_refs,
    )
