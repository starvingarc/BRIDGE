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
    GraftLinkageState,
    GraftObservation,
    PreparationGraftLinkage,
    UnmatchedGraftObservation,
)
from bridge.toolkit.contracts import ScoreState


def evaluate_graft_assessment(
    *,
    run_id: str,
    tool_version: str,
    assessment_spec: GraftAssessmentSpec,
    evidence_bundle: GraftEvidenceBundle,
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
            measurement_spec_ref=None,
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

    rules = {item.channel_id: item for item in assessment_spec.rules}
    summaries = [
        _summarize_channel(rule, evidence_bundle)
        for rule in sorted(assessment_spec.rules, key=lambda item: item.channel_id)
    ]
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
    if not available:
        result_state = "not_assessed"
    elif required_ready and not unmatched:
        result_state = "complete"
    else:
        result_state = "partial"

    reasons = {
        "analysis_limited_to_descriptive_summary",
        "graft_score_unavailable",
        "product_backfill_not_performed",
        *(reason for item in summaries for reason in item.reason_codes),
    }
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
        measurement_spec_ref=evidence_bundle.measurement_spec_ref,
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


def _summarize_channel(
    rule: GraftChannelRule,
    evidence_bundle: GraftEvidenceBundle,
) -> GraftChannelSummary:
    values_by_animal: dict[str, list[float]] = defaultdict(list)
    animal_refs = {}
    evidence_by_animal: dict[str, set[str]] = defaultdict(set)
    reasons: set[str] = set()
    for unit in evidence_bundle.units:
        observation = next(
            (
                item
                for item in unit.observations
                if item.channel_id == rule.channel_id
            ),
            None,
        )
        if observation is None:
            reasons.add("graft_channel_missing_for_unit")
            continue
        value = _eligible_observation(rule, observation, reasons)
        if value is None:
            continue
        animal_key = unit.animal_ref.ref
        animal_refs[animal_key] = unit.animal_ref
        values_by_animal[animal_key].append(value)
        evidence_by_animal[animal_key].update(observation.evidence_refs)

    if not values_by_animal:
        reasons.add("graft_channel_unavailable")
        return GraftChannelSummary(
            channel_id=rule.channel_id,
            unit=rule.unit,
            required=rule.required,
            minimum_independent_animals=rule.minimum_independent_animals,
            eligible_animal_count=0,
            animal_summaries=[],
            mean=None,
            minimum=None,
            maximum=None,
            configured_lower_bound=rule.configured_lower_bound,
            configured_upper_bound=rule.configured_upper_bound,
            configured_interval_relation=ConfiguredIntervalRelation.UNAVAILABLE,
            result_state="unavailable",
            evidence_refs=[],
            reason_codes=sorted(reasons),
        )

    animal_summaries = [
        GraftAnimalChannelSummary(
            animal_ref=animal_refs[animal_key],
            eligible_observation_count=len(values),
            mean=fmean(values),
            evidence_refs=sorted(evidence_by_animal[animal_key]),
        )
        for animal_key, values in sorted(values_by_animal.items())
    ]
    if any(item.eligible_observation_count > 1 for item in animal_summaries):
        reasons.add("repeated_observations_aggregated_within_animal")
    animal_values = [float(item.mean) for item in animal_summaries]
    mean = fmean(animal_values)
    if len(animal_values) < rule.minimum_independent_animals:
        reasons.add("independent_animals_below_configured_minimum")
    relation = _interval_relation(rule, mean)
    if relation in {
        ConfiguredIntervalRelation.BELOW_CONFIGURED_INTERVAL,
        ConfiguredIntervalRelation.ABOVE_CONFIGURED_INTERVAL,
    }:
        reasons.add("outside_configured_interval")
    return GraftChannelSummary(
        channel_id=rule.channel_id,
        unit=rule.unit,
        required=rule.required,
        minimum_independent_animals=rule.minimum_independent_animals,
        eligible_animal_count=len(animal_values),
        animal_summaries=animal_summaries,
        mean=mean,
        minimum=min(animal_values),
        maximum=max(animal_values),
        configured_lower_bound=rule.configured_lower_bound,
        configured_upper_bound=rule.configured_upper_bound,
        configured_interval_relation=relation,
        result_state="available",
        evidence_refs=sorted(
            {
                evidence
                for animal_evidence in evidence_by_animal.values()
                for evidence in animal_evidence
            }
        ),
        reason_codes=sorted(reasons),
    )


def _eligible_observation(
    rule: GraftChannelRule,
    observation: GraftObservation,
    reasons: set[str],
) -> float | None:
    if observation.unit != rule.unit:
        reasons.add("graft_channel_unit_mismatch")
        return None
    if observation.evidence_state not in rule.eligible_evidence_states:
        reasons.add("graft_evidence_state_not_eligible")
        return None
    if observation.value is None:
        reasons.add("graft_observation_value_unavailable")
        return None
    return float(observation.value)


def _interval_relation(
    rule: GraftChannelRule, mean: float
) -> ConfiguredIntervalRelation:
    if rule.interpretation_policy == "descriptive_only":
        return ConfiguredIntervalRelation.NO_INTERVAL_CONFIGURED
    assert rule.configured_lower_bound is not None
    assert rule.configured_upper_bound is not None
    if mean < float(rule.configured_lower_bound):
        return ConfiguredIntervalRelation.BELOW_CONFIGURED_INTERVAL
    if mean > float(rule.configured_upper_bound):
        return ConfiguredIntervalRelation.ABOVE_CONFIGURED_INTERVAL
    return ConfiguredIntervalRelation.WITHIN_CONFIGURED_INTERVAL
