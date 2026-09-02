from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from bridge.tool_packages._configurable_contracts import (
    ProductCase,
    ProductDefinitionCard,
    RoleFraction,
    UpstreamCompositionRecord,
    VersionedObjectRef,
    parse_composition,
)
from bridge.tool_packages._structured_runtime import canonical_json_bytes
from bridge.tool_packages.p0_04_developmental_compatibility.models import (
    DevelopmentMeasurementArtifactBinding,
    DevelopmentMeasurementMetricName,
    DevelopmentalCompatibilityResult,
    DevelopmentalCompatibilityResultV3,
    DevelopmentFractionProfile,
    DevelopmentStageRole,
    DevelopmentStateMap,
    DevelopmentTimepointProfile,
    DevelopmentTimepointRecord,
    DevelopmentTimepointSeries,
    DevelopmentWindowSpec,
    InputChecksumBindings,
    ReferenceStageSupport,
)
from bridge.toolkit.contracts import (
    CellStateEvidenceProfileV3,
    EvidenceState,
    MeasurementResultV2,
    MeasurementSpecV2,
    ScoreState,
)


ROLE_ORDER = tuple(DevelopmentStageRole)


@dataclass(frozen=True)
class EvaluationBundle:
    result: DevelopmentalCompatibilityResultV3
    measurements: list[MeasurementResultV2]
    measurement_payloads: dict[str, bytes]


def evaluate_developmental_compatibility(
    *,
    run_id: str,
    tool_version: str,
    product_case: ProductCase,
    product_definition: ProductDefinitionCard,
    window_spec: DevelopmentWindowSpec,
    state_map: DevelopmentStateMap,
    measurement_spec: MeasurementSpecV2,
    cell_state_profile: CellStateEvidenceProfileV3,
    cell_state_profile_version: str,
    timepoint_series: DevelopmentTimepointSeries | None,
    input_sha256_by_role: dict[str, str],
    method_bundle_ref: VersionedObjectRef | None = None,
    method_bundle_sha256: str | None = None,
    selected_method_ids: list[str] | None = None,
    method_reason_codes: list[str] | None = None,
    reference_stage_support_available: bool = False,
) -> EvaluationBundle:
    composition_state = cell_state_profile.composition.state
    selected_method_ids = sorted(set(selected_method_ids or []))
    reasons: set[str] = set(method_reason_codes or [])
    if method_bundle_ref is None:
        reasons.add("reference_stage_support_not_supplied")
    whole_profile: DevelopmentFractionProfile | None = None
    target_profile: DevelopmentFractionProfile | None = None

    if composition_state == "shadow":
        selected = _selected_records(parse_composition(cell_state_profile), window_spec)
        if selected:
            whole_profile, target_profile, profile_reasons = _profiles_from_records(
                selected, state_map
            )
            reasons.update(profile_reasons)
        else:
            reasons.add("requested_composition_channel_unavailable")
    else:
        reasons.add(f"cell_state_composition_{composition_state}")

    timecourse_profiles: list[DevelopmentTimepointProfile] = []
    if timepoint_series is not None:
        timecourse_profiles = [
            _timepoint_profile(record, state_map) for record in timepoint_series.records
        ]
        if len(timecourse_profiles) == 1:
            reasons.add("single_timepoint_dynamic_evidence_unavailable")
        if any(item.target_related_profile.denominator == 0 for item in timecourse_profiles):
            reasons.add("timepoint_target_related_denominator_zero")

    analysis_mode = (
        "descriptive_timecourse" if len(timecourse_profiles) >= 2 else "static_profile"
    )
    if timepoint_series is None:
        reasons.add("timepoint_series_not_supplied")
    reasons.add("inferential_timecourse_unavailable")

    if whole_profile is None:
        result_state = "not_assessed"
        compatibility_state = "not_assessed"
        evidence_state = "unavailable"
        timecourse_profiles = []
        analysis_mode = "static_profile"
    else:
        evidence_state = "shadow"
        compatibility_state = (
            "candidate" if window_spec.review_state == "confirmed" else "not_assessed"
        )
        if window_spec.review_state != "confirmed":
            reasons.add("development_window_not_confirmed")
        result_state = (
            "complete"
            if window_spec.review_state == "confirmed"
            and not {
                "state_mapping_incomplete",
                "composition_residual_unresolved",
                "target_related_denominator_zero",
            }.intersection(reasons)
            else "partial"
        )

    legacy_result = DevelopmentalCompatibilityResult(
        object_version="0.2.0",
        result_id=(
            "developmental-compatibility-result:"
            f"{run_id.removeprefix('run-')}"
        ),
        tool_id="P0-04",
        tool_version=tool_version,
        product_case_ref=product_case.ref,
        product_definition_ref=product_definition.ref,
        window_spec_ref=window_spec.ref,
        state_map_ref=state_map.ref,
        measurement_spec_ref=VersionedObjectRef(
            object_id=measurement_spec.measurement_spec_id,
            object_version=measurement_spec.version,
        ),
        cell_state_profile_ref=VersionedObjectRef(
            object_id=cell_state_profile.profile_id,
            object_version=cell_state_profile_version,
        ),
        timepoint_series_ref=(None if timepoint_series is None else timepoint_series.ref),
        input_sha256_by_role=InputChecksumBindings(
            product_case=input_sha256_by_role["product_case"],
            product_definition_card=input_sha256_by_role["product_definition_card"],
            development_window_spec=input_sha256_by_role["development_window_spec"],
            development_state_map=input_sha256_by_role["development_state_map"],
            measurement_spec=input_sha256_by_role["measurement_spec"],
            cell_state_evidence_profile=input_sha256_by_role[
                "cell_state_evidence_profile"
            ],
            development_timepoint_series=input_sha256_by_role.get(
                "development_timepoint_series"
            ),
            qc_readiness_profile=input_sha256_by_role.get("qc_readiness_profile"),
            biological_unit_manifest=input_sha256_by_role.get(
                "biological_unit_manifest"
            ),
            biological_unit_assignment=input_sha256_by_role.get(
                "biological_unit_assignment"
            ),
            annotation_vocabulary=input_sha256_by_role.get("annotation_vocabulary"),
            reference_manifest=input_sha256_by_role.get("reference_manifest"),
            development_method_spec=input_sha256_by_role.get(
                "development_method_spec"
            ),
        ),
        upstream_composition_state=composition_state,
        result_state=result_state,
        window_compatibility_state=compatibility_state,
        analysis_mode=analysis_mode,
        whole_product_profile=whole_profile,
        target_related_profile=target_profile,
        timecourse_profiles=timecourse_profiles,
        reference_stage_support=(
            ReferenceStageSupport(
                assessment_state="shadow",
                method_bundle_ref=method_bundle_ref,
                method_bundle_sha256=method_bundle_sha256,
                selected_method_ids=selected_method_ids,
            )
            if method_bundle_ref is not None and reference_stage_support_available
            else ReferenceStageSupport(
                assessment_state="unavailable",
                reason_code=(
                    "reference_stage_support_not_supplied"
                    if method_bundle_ref is None
                    else "reference_stage_support_unavailable"
                ),
            )
        ),
        evidence_state=evidence_state,
        evidence_refs=sorted(set(cell_state_profile.evidence_ids)),
        reason_codes=sorted(reasons),
        domain_score=None,
        score_state="unavailable",
    )
    measurements, payloads, artifact_bindings = _project_measurements(
        run_id=run_id,
        tool_version=tool_version,
        measurement_spec=measurement_spec,
        result=legacy_result,
    )
    result_payload = legacy_result.model_dump(mode="json")
    result_payload.update(
        {
            "object_version": "0.3.0",
            "measurement_artifacts": [
                item.model_dump(mode="json") for item in artifact_bindings
            ],
        }
    )
    return EvaluationBundle(
        result=DevelopmentalCompatibilityResultV3.model_validate(result_payload),
        measurements=measurements,
        measurement_payloads=payloads,
    )


def _selected_records(
    records: list[UpstreamCompositionRecord],
    window_spec: DevelopmentWindowSpec,
) -> list[UpstreamCompositionRecord]:
    return [
        record
        for record in records
        if record.view.value == window_spec.composition_view
        and record.source_id == window_spec.source_id
        and record.label_level == window_spec.label_level
    ]


def _profiles_from_records(
    records: list[UpstreamCompositionRecord],
    state_map: DevelopmentStateMap,
) -> tuple[DevelopmentFractionProfile, DevelopmentFractionProfile, set[str]]:
    denominators = {(item.denominator, item.denominator_view) for item in records}
    if len(denominators) != 1:
        raise ValueError("cell_state_composition_channel_denominator_mismatch")
    denominator, denominator_view = next(iter(denominators))
    assignments = {
        (item.label_level, item.state_id): item for item in state_map.assignments
    }
    whole_counts = defaultdict(int)
    target_counts = defaultdict(int)
    accounted = 0
    reasons: set[str] = set()
    for record in records:
        accounted += record.count
        assignment = assignments.get((record.label_level, record.label))
        if assignment is None:
            whole_counts[DevelopmentStageRole.UNRESOLVED] += record.count
            reasons.add("state_mapping_incomplete")
            continue
        whole_counts[assignment.stage_role] += record.count
        if assignment.target_related:
            target_counts[assignment.stage_role] += record.count
    if accounted > denominator:
        raise ValueError("cell_state_composition_channel_overfull")
    if accounted < denominator:
        whole_counts[DevelopmentStageRole.UNRESOLVED] += denominator - accounted
        reasons.add("composition_residual_unresolved")
    target_denominator = sum(target_counts.values())
    if target_denominator == 0:
        reasons.add("target_related_denominator_zero")
    return (
        _fraction_profile("whole_product", denominator_view, denominator, whole_counts),
        _fraction_profile(
            "target_related", denominator_view, target_denominator, target_counts
        ),
        reasons,
    )


def _timepoint_profile(
    record: DevelopmentTimepointRecord,
    state_map: DevelopmentStateMap,
) -> DevelopmentTimepointProfile:
    assignments = {
        (item.label_level, item.state_id): item for item in state_map.assignments
    }
    whole_counts = defaultdict(int)
    target_counts = defaultdict(int)
    accounted = 0
    for item in record.state_counts:
        accounted += item.count
        assignment = assignments.get((item.label_level, item.state_id))
        if assignment is None:
            whole_counts[DevelopmentStageRole.UNRESOLVED] += item.count
            continue
        whole_counts[assignment.stage_role] += item.count
        if assignment.target_related:
            target_counts[assignment.stage_role] += item.count
    whole_counts[DevelopmentStageRole.UNRESOLVED] += record.denominator - accounted
    target_denominator = sum(target_counts.values())
    return DevelopmentTimepointProfile(
        timepoint_id=record.timepoint_id,
        timepoint_order=record.timepoint_order,
        timepoint_label=record.timepoint_label,
        independence_group_count=len(record.independence_group_refs),
        whole_product_profile=_fraction_profile(
            "whole_product", "declared_timepoint_all_cells", record.denominator, whole_counts
        ),
        target_related_profile=_fraction_profile(
            "target_related",
            "declared_timepoint_target_related",
            target_denominator,
            target_counts,
        ),
    )


def _fraction_profile(
    kind: str,
    denominator_view: str,
    denominator: int,
    counts: dict[DevelopmentStageRole, int],
) -> DevelopmentFractionProfile:
    return DevelopmentFractionProfile(
        denominator_kind=kind,
        denominator_view=denominator_view,
        denominator=denominator,
        role_fractions=[
            RoleFraction(
                role=role.value,
                numerator=counts[role],
                denominator=denominator,
                fraction=(counts[role] / denominator if denominator else None),
            )
            for role in ROLE_ORDER
        ],
    )


def _project_measurements(
    *,
    run_id: str,
    tool_version: str,
    measurement_spec: MeasurementSpecV2,
    result: DevelopmentalCompatibilityResult,
) -> tuple[
    list[MeasurementResultV2],
    dict[str, bytes],
    list[DevelopmentMeasurementArtifactBinding],
]:
    projected: list[
        tuple[
            DevelopmentMeasurementMetricName,
            str,
            DevelopmentStageRole,
            str | None,
            int | None,
            RoleFraction | None,
            list[str],
        ]
    ] = []
    static_profiles = (
        ("whole_product", result.whole_product_profile),
        ("target_related", result.target_related_profile),
    )
    unavailable_reasons = _profile_unavailable_reasons(result)
    for denominator_kind, profile in static_profiles:
        fractions = (
            {DevelopmentStageRole(item.role): item for item in profile.role_fractions}
            if profile is not None
            else {}
        )
        for role in ROLE_ORDER:
            ratio = fractions.get(role)
            reasons = (
                _zero_denominator_reasons(
                    denominator_kind=denominator_kind,
                    timepoint=False,
                    ratio=ratio,
                )
                or ([] if ratio is not None else unavailable_reasons)
            )
            projected.append(
                (
                    _metric_name(denominator_kind, timepoint=False),
                    denominator_kind,
                    role,
                    None,
                    None,
                    ratio,
                    reasons,
                )
            )

    for profile in result.timecourse_profiles:
        for denominator_kind, fraction_profile in (
            ("whole_product", profile.whole_product_profile),
            ("target_related", profile.target_related_profile),
        ):
            fractions = {
                DevelopmentStageRole(item.role): item
                for item in fraction_profile.role_fractions
            }
            for role in ROLE_ORDER:
                ratio = fractions[role]
                projected.append(
                    (
                        _metric_name(denominator_kind, timepoint=True),
                        denominator_kind,
                        role,
                        profile.timepoint_id,
                        profile.timepoint_order,
                        ratio,
                        _zero_denominator_reasons(
                            denominator_kind=denominator_kind,
                            timepoint=True,
                            ratio=ratio,
                        ),
                    )
                )

    measurements: list[MeasurementResultV2] = []
    payloads: dict[str, bytes] = {}
    bindings: list[DevelopmentMeasurementArtifactBinding] = []
    for (
        metric_name,
        denominator_kind,
        role,
        timepoint_id,
        timepoint_order,
        ratio,
        reasons,
    ) in projected:
        token = _projection_token(
            denominator_kind=denominator_kind,
            role=role,
            timepoint_id=timepoint_id,
            timepoint_order=timepoint_order,
        )
        measurement = _measurement(
            run_id=run_id,
            tool_version=tool_version,
            measurement_spec=measurement_spec,
            metric_name=metric_name,
            token=token,
            ratio=ratio,
            result=result,
        )
        payload = canonical_json_bytes(
            measurement.model_dump(mode="json"), indent=2
        )
        prefix = "static" if timepoint_id is None else f"timepoint-{token[:12]}"
        filename = (
            f"{prefix}.{denominator_kind}.{role.value}."
            "measurement_result.json"
        )
        artifact_id = f"artifact:{run_id}:development-measurement:{token}"
        measurements.append(measurement)
        payloads[filename] = payload
        bindings.append(
            DevelopmentMeasurementArtifactBinding(
                measurement_id=measurement.measurement_id,
                metric_name=metric_name,
                denominator_kind=denominator_kind,
                stage_role=role,
                timepoint_id=timepoint_id,
                timepoint_order=timepoint_order,
                artifact_id=artifact_id,
                file_name=filename,
                sha256=hashlib.sha256(payload).hexdigest(),
                reason_codes=sorted(set(reasons)),
            )
        )

    order = sorted(range(len(bindings)), key=lambda index: bindings[index].file_name)
    return (
        [measurements[index] for index in order],
        {
            bindings[index].file_name: payloads[bindings[index].file_name]
            for index in order
        },
        [bindings[index] for index in order],
    )


def _metric_name(
    denominator_kind: str, *, timepoint: bool
) -> DevelopmentMeasurementMetricName:
    return {
        (False, "whole_product"): (
            DevelopmentMeasurementMetricName.WHOLE_PRODUCT_ROLE_FRACTION
        ),
        (False, "target_related"): (
            DevelopmentMeasurementMetricName.TARGET_RELATED_ROLE_FRACTION
        ),
        (True, "whole_product"): (
            DevelopmentMeasurementMetricName.TIMEPOINT_WHOLE_PRODUCT_ROLE_FRACTION
        ),
        (True, "target_related"): (
            DevelopmentMeasurementMetricName.TIMEPOINT_TARGET_RELATED_ROLE_FRACTION
        ),
    }[(timepoint, denominator_kind)]


def _profile_unavailable_reasons(
    result: DevelopmentalCompatibilityResult,
) -> list[str]:
    reasons = [
        reason
        for reason in result.reason_codes
        if reason == "requested_composition_channel_unavailable"
        or reason.startswith("cell_state_composition_")
    ]
    return sorted(set(reasons or ["developmental_fraction_profile_unavailable"]))


def _zero_denominator_reasons(
    *,
    denominator_kind: str,
    timepoint: bool,
    ratio: RoleFraction | None,
) -> list[str]:
    if ratio is None or ratio.denominator > 0:
        return []
    if denominator_kind != "target_related":
        raise ValueError("only target-related projections may have zero denominator")
    return [
        (
            "timepoint_target_related_denominator_zero"
            if timepoint
            else "target_related_denominator_zero"
        )
    ]


def _projection_token(
    *,
    denominator_kind: str,
    role: DevelopmentStageRole,
    timepoint_id: str | None,
    timepoint_order: int | None,
) -> str:
    raw = canonical_json_bytes(
        [timepoint_id, timepoint_order, denominator_kind, role.value]
    )
    return hashlib.sha256(raw).hexdigest()[:16]


def _measurement(
    *,
    run_id: str,
    tool_version: str,
    measurement_spec: MeasurementSpecV2,
    metric_name: DevelopmentMeasurementMetricName,
    token: str,
    ratio: RoleFraction | None,
    result: DevelopmentalCompatibilityResult,
) -> MeasurementResultV2:
    numeric = ratio is not None and ratio.denominator > 0
    evidence_state = (
        EvidenceState.INFERRED if numeric else _unavailable_evidence_state(result)
    )
    return MeasurementResultV2(
        measurement_id=(
            f"measurement:{run_id.removeprefix('run-')}:{token}:"
            f"{metric_name.value}"
        ),
        measurement_spec_id=measurement_spec.measurement_spec_id,
        measurement_spec_version=measurement_spec.version,
        metric_name=metric_name.value,
        raw_value=ratio.fraction if numeric else None,
        unit="fraction",
        numerator=ratio.numerator if numeric else None,
        denominator=ratio.denominator if numeric else None,
        interval=None,
        interval_confidence_level=None,
        interval_method_ref=None,
        source_run_ref=f"tool-run:{run_id}@{tool_version}",
        source_execution_state=(
            "succeeded" if result.result_state == "complete" else "partial"
        ),
        unknown_scope=(
            "measurement" if evidence_state is EvidenceState.UNKNOWN else None
        ),
        domain_score=None,
        score_state=ScoreState.UNAVAILABLE,
        evidence_state=evidence_state,
        provenance_refs=result.evidence_refs,
    )


def _unavailable_evidence_state(
    result: DevelopmentalCompatibilityResult,
) -> EvidenceState:
    if result.upstream_composition_state == "missing":
        return EvidenceState.MISSING
    if result.upstream_composition_state == "unknown":
        return EvidenceState.UNKNOWN
    return EvidenceState.UNAVAILABLE
