from __future__ import annotations

from collections import defaultdict
from statistics import fmean

from bridge.tool_packages.p0_12_graft_assessment.models import (
    ConfiguredIntervalRelation,
    GraftAnalysisMode,
    GraftAssessment,
    GraftAssessmentSpec,
    GraftAnimalChannelSummary,
    GraftAvailability,
    GraftChannelRule,
    GraftChannelSummary,
    GraftEvidenceBundle,
    GraftLineageManifest,
    GraftLineageState,
    GraftLinkageState,
    GraftObservation,
    GraftStratumRule,
    PreparationGraftLinkage,
    UnmatchedGraftObservation,
    WithinAnimalAggregation,
)
from bridge.toolkit.contracts import MeasurementSpec, ScoreState


def evaluate_graft_assessment(
    *,
    run_id: str,
    tool_version: str,
    assessment_spec: GraftAssessmentSpec,
    evidence_bundle: GraftEvidenceBundle,
    graft_measurement_spec: MeasurementSpec,
    lineage_manifest: GraftLineageManifest | None,
    input_sha256_by_role: dict[str, str],
) -> GraftAssessment:
    if evidence_bundle.graft_availability is GraftAvailability.NOT_PROVIDED:
        return GraftAssessment(
            object_version="0.1.0",
            assessment_id=f"graft-assessment:{run_id.removeprefix('run-')}",
            tool_id="P0-12",
            tool_version=tool_version,
            assessment_spec_ref=assessment_spec.ref,
            evidence_bundle_ref=evidence_bundle.ref,
            product_case_ref=evidence_bundle.product_case_ref,
            graft_case_ref=None,
            product_measurement_spec_ref=assessment_spec.product_measurement_spec_ref,
            graft_measurement_spec_ref=None,
            graft_lineage_manifest_ref=None,
            graft_lineage_state=None,
            input_sha256_by_role=input_sha256_by_role,
            result_state="not_provided",
            graft_availability=GraftAvailability.NOT_PROVIDED,
            linkage_state=GraftLinkageState.NOT_APPLICABLE,
            analysis_mode=GraftAnalysisMode.UNAVAILABLE,
            observation_unit_count=0,
            independent_animal_count=0,
            design_constraint_refs=[],
            channel_summaries=[],
            preparation_linkages=[],
            unmatched_observations=[],
            evidence_refs=[],
            reason_codes=[
                "graft_not_provided",
                "graft_score_unavailable",
                "product_backfill_not_performed",
            ],
            product_backfill="not_performed",
            graft_score=None,
            domain_score=None,
            score_state=ScoreState.UNAVAILABLE,
        )

    if lineage_manifest is None:
        raise ValueError("graft lineage manifest required")
    if (
        assessment_spec.graft_measurement_spec_ref.object_id
        != graft_measurement_spec.measurement_spec_id
        or assessment_spec.graft_measurement_spec_ref.object_version
        != graft_measurement_spec.version
    ):
        raise ValueError("graft measurement specification mismatch")

    rules = {item.channel_id: item for item in assessment_spec.rules}
    lineage_reviewed = lineage_manifest.lineage_state in {
        GraftLineageState.REVIEWED,
        GraftLineageState.FROZEN,
    }
    summaries = sorted(
        [
            _summarize_channel_stratum(
                rule,
                stratum,
                evidence_bundle,
                lineage_reviewed=lineage_reviewed,
            )
            for rule in assessment_spec.rules
            for stratum in rule.strata
        ],
        key=lambda item: (item.channel_id, item.stratum_id),
    )
    unmatched = sorted(
        [
            UnmatchedGraftObservation(
                unit_ref=unit.unit_ref,
                observation_id=observation.observation_id,
                channel_id=observation.channel_id,
                reason_code="graft_channel_not_configured",
            )
            for unit in evidence_bundle.units
            for observation in unit.observations
            if observation.channel_id not in rules
        ],
        key=lambda item: (item.unit_ref.ref, item.observation_id),
    )
    linkages = sorted(
        [
            PreparationGraftLinkage(
                unit_ref=unit.unit_ref,
                animal_ref=unit.animal_ref,
                originating_preparation_ref=unit.originating_preparation_ref,
                evidence_refs=sorted(unit.linkage_evidence_refs),
            )
            for unit in evidence_bundle.units
            if unit.originating_preparation_ref is not None
        ],
        key=lambda item: item.unit_ref.ref,
    )
    all_units_linked = bool(evidence_bundle.units) and len(linkages) == len(
        evidence_bundle.units
    )
    if all_units_linked:
        linkage_state = GraftLinkageState.DECLARED_WITH_EVIDENCE
    elif linkages:
        linkage_state = GraftLinkageState.PARTIALLY_DECLARED
    else:
        linkage_state = GraftLinkageState.NOT_DECLARED

    available = [item for item in summaries if item.result_state == "available"]
    required_ready = all(
        (not item.required)
        or (
            item.result_state == "available"
            and item.eligible_animal_count >= item.minimum_independent_animals
        )
        for item in summaries
    )
    if not lineage_reviewed:
        result_state = "partial"
    elif not available:
        result_state = "not_assessed"
    elif required_ready and not unmatched:
        result_state = "complete"
    else:
        result_state = "partial"

    reasons = {
        "analysis_limited_to_descriptive_summary",
        "cross_stratum_aggregation_forbidden",
        "graft_score_unavailable",
        "product_backfill_not_performed",
        *(reason for item in summaries for reason in item.reason_codes),
    }
    if not lineage_reviewed:
        reasons.add("graft_lineage_not_reviewed")
    if evidence_bundle.design_constraint_refs:
        reasons.add("configured_design_constraints_present")
    if unmatched:
        reasons.add("unmatched_graft_observations")
    if linkages:
        reasons.add("preparation_linkage_declared_not_verified")
    if linkages and not all_units_linked:
        reasons.add("partial_preparation_linkage_declaration")
    if not linkages:
        reasons.add("preparation_linkage_not_declared")
    evidence_refs = sorted(
        {
            *(evidence for item in summaries for evidence in item.evidence_refs),
            *(evidence for item in linkages for evidence in item.evidence_refs),
        }
    )
    return GraftAssessment(
        object_version="0.1.0",
        assessment_id=f"graft-assessment:{run_id.removeprefix('run-')}",
        tool_id="P0-12",
        tool_version=tool_version,
        assessment_spec_ref=assessment_spec.ref,
        evidence_bundle_ref=evidence_bundle.ref,
        product_case_ref=evidence_bundle.product_case_ref,
        graft_case_ref=evidence_bundle.graft_case_ref,
        product_measurement_spec_ref=assessment_spec.product_measurement_spec_ref,
        graft_measurement_spec_ref=assessment_spec.graft_measurement_spec_ref,
        graft_lineage_manifest_ref=lineage_manifest.ref,
        graft_lineage_state=lineage_manifest.lineage_state,
        input_sha256_by_role=input_sha256_by_role,
        result_state=result_state,
        graft_availability=GraftAvailability.PROVIDED,
        linkage_state=linkage_state,
        analysis_mode=GraftAnalysisMode.DESCRIPTIVE_ONLY,
        observation_unit_count=len(evidence_bundle.units),
        independent_animal_count=len(
            {unit.animal_ref.ref for unit in evidence_bundle.units}
        ),
        design_constraint_refs=sorted(
            evidence_bundle.design_constraint_refs, key=lambda item: item.ref
        ),
        channel_summaries=summaries,
        preparation_linkages=linkages,
        unmatched_observations=unmatched,
        evidence_refs=evidence_refs,
        reason_codes=sorted(reasons),
        product_backfill="not_performed",
        graft_score=None,
        domain_score=None,
        score_state=(ScoreState.SHADOW if available else ScoreState.UNAVAILABLE),
    )


def _summarize_channel_stratum(
    rule: GraftChannelRule,
    stratum: GraftStratumRule,
    evidence_bundle: GraftEvidenceBundle,
    *,
    lineage_reviewed: bool,
) -> GraftChannelSummary:
    common = dict(
        channel_id=rule.channel_id,
        stratum_id=stratum.stratum_id,
        stratum_members=stratum.members,
        unit=rule.unit,
        required=rule.required,
        animal_estimand=rule.animal_estimand,
        within_animal_aggregation=rule.within_animal_aggregation,
        denominator_semantics=rule.denominator_semantics,
        cross_stratum_aggregation=rule.cross_stratum_aggregation,
        minimum_independent_animals=stratum.minimum_independent_animals,
        configured_lower_bound=stratum.configured_lower_bound,
        configured_upper_bound=stratum.configured_upper_bound,
    )
    if not lineage_reviewed:
        return GraftChannelSummary(
            **common,
            eligible_animal_count=0,
            animal_summaries=[],
            mean=None,
            minimum=None,
            maximum=None,
            configured_interval_relation=ConfiguredIntervalRelation.UNAVAILABLE,
            result_state="not_assessed",
            evidence_refs=[],
            reason_codes=["graft_lineage_not_reviewed"],
        )

    member_keys = {
        (item.graft_ref.ref, item.timepoint_ref.ref) for item in stratum.members
    }
    observations_by_animal: dict[str, list[GraftObservation]] = defaultdict(list)
    animal_refs = {}
    reasons: set[str] = set()
    for unit in evidence_bundle.units:
        if (unit.graft_ref.ref, unit.timepoint_ref.ref) not in member_keys:
            continue
        observation = next(
            (item for item in unit.observations if item.channel_id == rule.channel_id),
            None,
        )
        if observation is None:
            reasons.add("graft_channel_missing_for_stratum_unit")
            continue
        if not _observation_is_eligible(rule, observation, reasons):
            continue
        animal_key = unit.animal_ref.ref
        animal_refs[animal_key] = unit.animal_ref
        observations_by_animal[animal_key].append(observation)

    animal_summaries: list[GraftAnimalChannelSummary] = []
    for animal_key, observations in sorted(observations_by_animal.items()):
        summary = _aggregate_animal(rule, animal_refs[animal_key], observations, reasons)
        if summary is not None:
            animal_summaries.append(summary)

    if not animal_summaries:
        reasons.add("graft_channel_unavailable")
        return GraftChannelSummary(
            **common,
            eligible_animal_count=0,
            animal_summaries=[],
            mean=None,
            minimum=None,
            maximum=None,
            configured_interval_relation=ConfiguredIntervalRelation.UNAVAILABLE,
            result_state="unavailable",
            evidence_refs=[],
            reason_codes=sorted(reasons),
        )

    animal_values = [float(item.mean) for item in animal_summaries]
    mean = fmean(animal_values)
    if len(animal_values) < stratum.minimum_independent_animals:
        reasons.add("independent_animals_below_configured_minimum")
        relation = ConfiguredIntervalRelation.UNAVAILABLE
    else:
        relation = _interval_relation(stratum, mean)
        if relation in {
            ConfiguredIntervalRelation.BELOW_CONFIGURED_INTERVAL,
            ConfiguredIntervalRelation.ABOVE_CONFIGURED_INTERVAL,
        }:
            reasons.add("outside_configured_interval")
    return GraftChannelSummary(
        **common,
        eligible_animal_count=len(animal_values),
        animal_summaries=animal_summaries,
        mean=mean,
        minimum=min(animal_values),
        maximum=max(animal_values),
        configured_interval_relation=relation,
        result_state="available",
        evidence_refs=sorted(
            {
                evidence
                for animal in animal_summaries
                for evidence in animal.evidence_refs
            }
        ),
        reason_codes=sorted(reasons),
    )


def _observation_is_eligible(
    rule: GraftChannelRule,
    observation: GraftObservation,
    reasons: set[str],
) -> bool:
    if observation.unit != rule.unit:
        reasons.add("graft_channel_unit_mismatch")
        return False
    if observation.evidence_state not in rule.eligible_evidence_states:
        reasons.add("graft_evidence_state_not_eligible")
        return False
    if observation.value is None:
        reasons.add("graft_observation_value_unavailable")
        return False
    if rule.denominator_semantics == "not_applicable" and (
        observation.numerator is not None or observation.denominator is not None
    ):
        reasons.add("graft_denominator_semantics_mismatch")
        return False
    if rule.denominator_semantics != "not_applicable" and (
        observation.numerator is None or observation.denominator is None
    ):
        reasons.add("graft_denominator_required")
        return False
    return True


def _aggregate_animal(
    rule: GraftChannelRule,
    animal_ref,
    observations: list[GraftObservation],
    reasons: set[str],
) -> GraftAnimalChannelSummary | None:
    if (
        rule.within_animal_aggregation is WithinAnimalAggregation.SINGLE_OBSERVATION
        and len(observations) != 1
    ):
        reasons.add("single_observation_estimand_violated")
        return None
    pooled_numerator = None
    pooled_denominator = None
    if (
        rule.within_animal_aggregation
        is WithinAnimalAggregation.POOLED_NUMERATOR_DENOMINATOR
    ):
        pooled_numerator = sum(float(item.numerator) for item in observations)
        pooled_denominator = sum(int(item.denominator) for item in observations)
        animal_value = pooled_numerator / pooled_denominator
    else:
        animal_value = fmean(float(item.value) for item in observations)
        if len(observations) > 1:
            reasons.add("repeated_observations_aggregated_within_animal")
    return GraftAnimalChannelSummary(
        animal_ref=animal_ref,
        eligible_observation_count=len(observations),
        mean=animal_value,
        pooled_numerator=pooled_numerator,
        pooled_denominator=pooled_denominator,
        evidence_refs=sorted(
            {evidence for item in observations for evidence in item.evidence_refs}
        ),
    )


def _interval_relation(
    stratum: GraftStratumRule,
    mean: float,
) -> ConfiguredIntervalRelation:
    if stratum.interpretation_policy == "descriptive_only":
        return ConfiguredIntervalRelation.NO_INTERVAL_CONFIGURED
    assert stratum.configured_lower_bound is not None
    assert stratum.configured_upper_bound is not None
    if mean < float(stratum.configured_lower_bound):
        return ConfiguredIntervalRelation.BELOW_CONFIGURED_INTERVAL
    if mean > float(stratum.configured_upper_bound):
        return ConfiguredIntervalRelation.ABOVE_CONFIGURED_INTERVAL
    return ConfiguredIntervalRelation.WITHIN_CONFIGURED_INTERVAL
