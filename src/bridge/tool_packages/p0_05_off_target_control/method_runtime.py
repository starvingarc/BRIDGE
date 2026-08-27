from __future__ import annotations

import math
from collections import Counter, defaultdict
from importlib.metadata import PackageNotFoundError, version

import numpy as np
from scipy.stats import beta

from bridge.tool_packages._configurable_contracts import ProductRole
from bridge.tool_packages.p0_05_off_target_control.method_models import (
    AnalysisUnitComposition,
    HardSoftSensitivityRecord,
    MethodExecutionRecord,
    MethodExecutionState,
    OODDecisionState,
    OODDisagreementRecord,
    OODEnsembleRecord,
    OffTargetMethodBundle,
    OffTargetMethodId,
    OffTargetMethodInput,
    OffTargetMethodSpec,
    ProportionInterval,
    RarePlanningRecord,
    SpikeInCalibrationRecord,
    SpikeInCurvePoint,
)
from bridge.tool_packages.p0_05_off_target_control.models import (
    OffTargetAssessmentSpec,
    OffTargetEvidenceBundle,
    StateRoleMap,
)

METHOD_REFS = {
    OffTargetMethodId.COMPOSITION_EXACT: (
        "METHOD-EXACT-BINOMIAL-CLOPPER-PEARSON",
        "scipy.stats.beta Clopper-Pearson interval",
    ),
    OffTargetMethodId.HARD_LABEL_SENSITIVITY: (
        "METHOD-HARD-LABEL-COMPOSITION",
        "BRIDGE hard-versus-soft role composition",
    ),
    OffTargetMethodId.HIERARCHICAL_BOOTSTRAP: (
        "METHOD-SAMPLE-PRESERVING-HIERARCHICAL-BOOTSTRAP-9669E1",
        "NumPy independence-group bootstrap",
    ),
    OffTargetMethodId.RARE_EXACT: (
        "METHOD-EXACT-BINOMIAL-CLOPPER-PEARSON",
        "scipy.stats.beta rare-state interval",
    ),
    OffTargetMethodId.RARE_SPIKE_IN: (
        "METHOD-BRIDGE-SAMPLE-PRESERVING-SPIKE-IN",
        "BRIDGE empirical spike-in recovery curve",
    ),
    OffTargetMethodId.RARE_BINOMIAL_PLANNER: (
        "METHOD-SINGLE-STATE-AT-LEAST-ONE-BINOMIAL-PLANNER",
        "single-state at-least-one binomial sample-size planner",
    ),
    OffTargetMethodId.OOD_DISAGREEMENT: (
        "METHOD-BRIDGE-MODEL-AND-REFERENCE-DISAGREEMENT",
        "BRIDGE source-family disagreement audit",
    ),
    OffTargetMethodId.OOD_ENSEMBLE: (
        "METHOD-BRIDGE-OOD-ENSEMBLE",
        "BRIDGE ordered external-rule coordinator",
    ),
}


def _package_versions() -> dict[str, str]:
    values: dict[str, str] = {}
    for package in ("numpy", "scipy"):
        try:
            values[package] = version(package)
        except PackageNotFoundError:
            values[package] = "unavailable"
    return values


def _clopper_pearson(
    count: int,
    denominator: int,
    confidence_level: float,
) -> tuple[float, float]:
    alpha = 1.0 - confidence_level
    lower = (
        0.0
        if count == 0
        else float(beta.ppf(alpha / 2.0, count, denominator - count + 1))
    )
    upper = (
        1.0
        if count == denominator
        else float(beta.ppf(1.0 - alpha / 2.0, count + 1, denominator - count))
    )
    return lower, upper


def _role_state_ids(role_map: StateRoleMap) -> dict[ProductRole, set[str]]:
    result = {role: set() for role in ProductRole}
    for assignment in role_map.assignments:
        result[assignment.product_role].add(assignment.state_id)
    return result


def _whole_role_totals(
    role_map: StateRoleMap,
    evidence: OffTargetEvidenceBundle,
) -> dict[ProductRole, tuple[float, int]]:
    states = _role_state_ids(role_map)
    observations = {item.state_id: item for item in evidence.state_observations}
    return {
        role: (
            float(
                math.fsum(
                    observations[state].soft_mass
                    for state in ids
                    if state in observations
                )
            ),
            sum(
                observations[state].observed_count
                for state in ids
                if state in observations
            ),
        )
        for role, ids in states.items()
    }


def _unit_role_soft_mass(
    unit: AnalysisUnitComposition,
    role_states: set[str],
) -> float:
    return float(
        math.fsum(
            item.soft_mass
            for item in unit.state_observations
            if item.state_id in role_states
        )
    )


def _exact_composition_intervals(
    role_map: StateRoleMap,
    evidence: OffTargetEvidenceBundle,
    confidence_level: float,
    n_groups: int,
) -> list[ProportionInterval]:
    totals = _whole_role_totals(role_map, evidence)
    denominator = evidence.denominator.n_observations
    records: list[ProportionInterval] = []
    for role in ProductRole:
        count = totals[role][1]
        lower, upper = _clopper_pearson(count, denominator, confidence_level)
        records.append(
            ProportionInterval(
                scope_id=f"product-role:{role.value}",
                method_id=OffTargetMethodId.COMPOSITION_EXACT,
                numerator_kind="hard_count",
                estimate=float(count / denominator),
                lower=lower,
                upper=upper,
                confidence_level=confidence_level,
                n_observations=denominator,
                n_independence_groups=n_groups,
                assessment_state="available",
                reason_codes=["count_interval_excludes_annotation_uncertainty"],
            )
        )
    return records


def _hard_soft_sensitivity(
    role_map: StateRoleMap,
    evidence: OffTargetEvidenceBundle,
) -> list[HardSoftSensitivityRecord]:
    totals = _whole_role_totals(role_map, evidence)
    return [
        HardSoftSensitivityRecord(
            product_role=role,
            soft_fraction=float(totals[role][0] / evidence.denominator.total_soft_mass),
            hard_fraction=float(totals[role][1] / evidence.denominator.n_observations),
            hard_minus_soft=float(
                totals[role][1] / evidence.denominator.n_observations
                - totals[role][0] / evidence.denominator.total_soft_mass
            ),
        )
        for role in ProductRole
    ]


def _bootstrap_intervals(
    role_map: StateRoleMap,
    method_input: OffTargetMethodInput,
    confidence_level: float,
    replicates: int,
    seed: int,
) -> tuple[list[ProportionInterval], list[str]]:
    groups: dict[str, list[AnalysisUnitComposition]] = defaultdict(list)
    for unit in method_input.analysis_units:
        groups[unit.independence_group_ref].append(unit)
    group_ids = sorted(groups)
    if len(group_ids) < 2:
        return (
            [
                ProportionInterval(
                    scope_id=f"product-role:{role.value}",
                    method_id=OffTargetMethodId.HIERARCHICAL_BOOTSTRAP,
                    numerator_kind="soft_mass",
                    estimate=None,
                    lower=None,
                    upper=None,
                    confidence_level=confidence_level,
                    n_observations=sum(
                        item.denominator_count for item in method_input.analysis_units
                    ),
                    n_independence_groups=len(group_ids),
                    assessment_state="not_assessed",
                    reason_codes=["multiple_independence_groups_required"],
                )
                for role in ProductRole
            ],
            ["multiple_independence_groups_required"],
        )

    rng = np.random.default_rng(seed)
    role_states = _role_state_ids(role_map)
    estimates: dict[ProductRole, list[float]] = {role: [] for role in ProductRole}
    for _ in range(replicates):
        sampled_groups = rng.choice(group_ids, size=len(group_ids), replace=True)
        denominator = 0
        numerators = {role: 0.0 for role in ProductRole}
        for group_id in sampled_groups:
            for unit in groups[str(group_id)]:
                denominator += unit.denominator_count
                for role, state_ids in role_states.items():
                    numerators[role] += _unit_role_soft_mass(unit, state_ids)
        for role in ProductRole:
            estimates[role].append(numerators[role] / denominator)

    alpha = 1.0 - confidence_level
    observed_denominator = sum(
        item.denominator_count for item in method_input.analysis_units
    )
    records = []
    for role in ProductRole:
        values = np.asarray(estimates[role], dtype=float)
        observed = (
            sum(
                _unit_role_soft_mass(unit, role_states[role])
                for unit in method_input.analysis_units
            )
            / observed_denominator
        )
        records.append(
            ProportionInterval(
                scope_id=f"product-role:{role.value}",
                method_id=OffTargetMethodId.HIERARCHICAL_BOOTSTRAP,
                numerator_kind="soft_mass",
                estimate=float(observed),
                lower=float(np.quantile(values, alpha / 2.0)),
                upper=float(np.quantile(values, 1.0 - alpha / 2.0)),
                confidence_level=confidence_level,
                n_observations=observed_denominator,
                n_independence_groups=len(group_ids),
                assessment_state="available",
                reason_codes=[],
            )
        )
    return records, []


def _rare_exact_intervals(
    assessment_spec: OffTargetAssessmentSpec,
    evidence: OffTargetEvidenceBundle,
    confidence_level: float,
    n_groups: int,
) -> tuple[list[ProportionInterval], list[str]]:
    observations = {item.state_id: item for item in evidence.state_observations}
    denominator = evidence.denominator.n_observations
    records: list[ProportionInterval] = []
    available = 0
    for rule in sorted(
        assessment_spec.rare_state_rules, key=lambda item: item.state_id
    ):
        observation = observations.get(rule.state_id)
        if observation is None:
            records.append(
                ProportionInterval(
                    scope_id=rule.state_id,
                    method_id=OffTargetMethodId.RARE_EXACT,
                    numerator_kind="hard_count",
                    estimate=None,
                    lower=None,
                    upper=None,
                    confidence_level=confidence_level,
                    n_observations=denominator,
                    n_independence_groups=n_groups,
                    assessment_state="not_assessed",
                    reason_codes=["rare_state_observation_missing"],
                )
            )
            continue
        available += 1
        lower, upper = _clopper_pearson(
            observation.observed_count,
            denominator,
            confidence_level,
        )
        records.append(
            ProportionInterval(
                scope_id=rule.state_id,
                method_id=OffTargetMethodId.RARE_EXACT,
                numerator_kind="hard_count",
                estimate=float(observation.observed_count / denominator),
                lower=lower,
                upper=upper,
                confidence_level=confidence_level,
                n_observations=denominator,
                n_independence_groups=n_groups,
                assessment_state="available",
                reason_codes=["count_interval_excludes_annotation_uncertainty"],
            )
        )
    return records, ([] if available else ["rare_state_observations_missing"])


def _spike_in_calibrations(
    assessment_spec: OffTargetAssessmentSpec,
    method_spec: OffTargetMethodSpec,
    method_input: OffTargetMethodInput,
) -> tuple[list[SpikeInCalibrationRecord], list[str]]:
    by_state: dict[str, list] = defaultdict(list)
    for trial in method_input.spike_in_trials:
        by_state[trial.state_id].append(trial)
    records: list[SpikeInCalibrationRecord] = []
    available = 0
    for rule in sorted(
        assessment_spec.rare_state_rules, key=lambda item: item.state_id
    ):
        trials = by_state.get(rule.state_id, [])
        by_fraction: dict[float, list] = defaultdict(list)
        for trial in trials:
            by_fraction[trial.spike_fraction].append(trial)
        curve: list[SpikeInCurvePoint] = []
        for fraction, fraction_trials in sorted(by_fraction.items()):
            if fraction <= 0.0:
                continue
            independence_groups = {
                item.independence_group_ref for item in fraction_trials
            }
            detected = sum(item.recovered_spike_count > 0 for item in fraction_trials)
            lower, upper = _clopper_pearson(
                detected,
                len(independence_groups),
                method_spec.confidence_level,
            )
            curve.append(
                SpikeInCurvePoint(
                    spike_fraction=float(fraction),
                    trial_count=len(fraction_trials),
                    detected_trial_count=detected,
                    independence_group_count=len(independence_groups),
                    detection_rate=float(detected / len(independence_groups)),
                    detection_lower=lower,
                    detection_upper=upper,
                )
            )
        background = sum(
            item.n_observations - item.expected_spike_count for item in trials
        )
        false_positives = sum(item.false_positive_count for item in trials)
        false_positive_fraction = (
            float(false_positives / background) if background else None
        )
        eligible_points = [
            point
            for point in curve
            if point.detection_lower
            >= method_spec.minimum_spike_in_detection_probability
            and point.spike_fraction <= rule.max_validated_detection_limit_fraction
            and false_positive_fraction is not None
            and false_positive_fraction <= rule.max_false_positive_fraction
        ]
        if eligible_points:
            available += 1
            records.append(
                SpikeInCalibrationRecord(
                    state_id=rule.state_id,
                    candidate_detection_limit_fraction=min(
                        item.spike_fraction for item in eligible_points
                    ),
                    false_positive_fraction=false_positive_fraction,
                    assessment_state="available",
                    curve=curve,
                    reason_codes=[],
                )
            )
        else:
            reasons = []
            if not trials:
                reasons.append("spike_in_trials_missing")
            if trials and false_positive_fraction is None:
                reasons.append("spike_in_background_missing")
            if curve and not reasons:
                reasons.append("spike_in_acceptance_rule_not_met")
            records.append(
                SpikeInCalibrationRecord(
                    state_id=rule.state_id,
                    candidate_detection_limit_fraction=None,
                    false_positive_fraction=false_positive_fraction,
                    assessment_state="not_assessed",
                    curve=curve,
                    reason_codes=reasons,
                )
            )
    return records, (
        [] if available else ["no_rare_state_spike_in_calibration_available"]
    )


def _single_state_planning_records(
    method_spec: OffTargetMethodSpec,
) -> list[RarePlanningRecord]:
    records = []
    for target in sorted(method_spec.planning_targets, key=lambda item: item.state_id):
        required = math.ceil(
            math.log1p(-target.desired_detection_probability)
            / math.log1p(-target.expected_frequency_fraction)
        )
        records.append(
            RarePlanningRecord(
                state_id=target.state_id,
                expected_frequency_fraction=target.expected_frequency_fraction,
                desired_detection_probability=target.desired_detection_probability,
                assumption_codes=[
                    "independent_random_sampling_assumed",
                    "single_state_at_least_one_cell_target",
                    "perfect_detection_assumed",
                ],
                required_observations=max(1, required),
            )
        )
    return records


def _family_states(
    method_spec: OffTargetMethodSpec,
    method_input: OffTargetMethodInput,
) -> dict[str, str]:
    bindings = {
        item.channel_id: item for item in method_spec.ood_channel_bindings
    }
    by_family: dict[str, set[str]] = defaultdict(set)
    for channel in method_input.ood_channels:
        if channel.state.value != "unavailable":
            by_family[bindings[channel.channel_id].source_family_id].add(
                channel.state.value
            )
    return {
        family: next(iter(states)) if len(states) == 1 else "conflict"
        for family, states in sorted(by_family.items())
        if states
    }


def _ood_disagreement(
    method_spec: OffTargetMethodSpec,
    method_input: OffTargetMethodInput,
) -> OODDisagreementRecord:
    family_states = _family_states(method_spec, method_input)
    assessed_channels = sum(
        item.state.value != "unavailable" for item in method_input.ood_channels
    )
    if len(family_states) < 2:
        return OODDisagreementRecord(
            assessed_channel_count=assessed_channels,
            distinct_source_family_count=len(family_states),
            family_states=family_states,
            disagreement=None,
            assessment_state="not_assessed",
            reason_codes=["multiple_source_families_required"],
        )
    disagreement = (
        "conflict" in family_states.values() or len(set(family_states.values())) > 1
    )
    return OODDisagreementRecord(
        assessed_channel_count=assessed_channels,
        distinct_source_family_count=len(family_states),
        family_states=family_states,
        disagreement=disagreement,
        assessment_state="available",
        reason_codes=[],
    )


def _ood_ensemble(
    method_spec: OffTargetMethodSpec,
    method_input: OffTargetMethodInput,
) -> OODEnsembleRecord:
    family_states = _family_states(method_spec, method_input)
    if "conflict" in family_states.values():
        return OODEnsembleRecord(
            decision_state=OODDecisionState.NOT_ASSESSED,
            distinct_source_family_count=len(family_states),
            family_vote_counts={},
            matched_reason_id=None,
            assessment_state="not_assessed",
            reason_codes=["within_source_family_ood_conflict"],
        )
    votes = Counter(state for state in family_states.values() if state != "conflict")
    for rule in method_spec.ood_decision_rules:
        if votes[rule.channel_state] >= rule.minimum_distinct_source_families:
            return OODEnsembleRecord(
                decision_state=OODDecisionState(rule.output_state),
                distinct_source_family_count=sum(votes.values()),
                family_vote_counts=dict(sorted(votes.items())),
                matched_reason_id=rule.reason_id,
                assessment_state="available",
                reason_codes=[],
            )
    return OODEnsembleRecord(
        decision_state=OODDecisionState.NOT_ASSESSED,
        distinct_source_family_count=sum(votes.values()),
        family_vote_counts=dict(sorted(votes.items())),
        matched_reason_id=None,
        assessment_state="not_assessed",
        reason_codes=["no_ood_coordination_rule_matched"],
    )


def execute_methods(
    *,
    tool_version: str,
    input_hash: str,
    random_seed: int,
    role_map: StateRoleMap,
    assessment_spec: OffTargetAssessmentSpec,
    evidence: OffTargetEvidenceBundle,
    method_spec: OffTargetMethodSpec,
    method_input: OffTargetMethodInput,
    method_spec_sha256: str,
    method_input_sha256: str,
    biological_unit_manifest_sha256: str,
) -> OffTargetMethodBundle:
    n_groups = len(
        {item.independence_group_ref for item in method_input.analysis_units}
    )
    composition_intervals: list[ProportionInterval] = []
    sensitivity: list[HardSoftSensitivityRecord] = []
    rare_intervals: list[ProportionInterval] = []
    spike_in: list[SpikeInCalibrationRecord] = []
    planning: list[RarePlanningRecord] = []
    disagreement: OODDisagreementRecord | None = None
    ensemble: OODEnsembleRecord | None = None
    execution_reasons: dict[OffTargetMethodId, list[str]] = {}

    for method_id in method_spec.selected_method_ids:
        reasons: list[str] = []
        if method_id is OffTargetMethodId.COMPOSITION_EXACT:
            composition_intervals.extend(
                _exact_composition_intervals(
                    role_map,
                    evidence,
                    method_spec.confidence_level,
                    n_groups,
                )
            )
        elif method_id is OffTargetMethodId.HARD_LABEL_SENSITIVITY:
            sensitivity.extend(_hard_soft_sensitivity(role_map, evidence))
        elif method_id is OffTargetMethodId.HIERARCHICAL_BOOTSTRAP:
            records, reasons = _bootstrap_intervals(
                role_map,
                method_input,
                method_spec.confidence_level,
                method_spec.bootstrap_replicates,
                random_seed,
            )
            composition_intervals.extend(records)
        elif method_id is OffTargetMethodId.RARE_EXACT:
            records, reasons = _rare_exact_intervals(
                assessment_spec,
                evidence,
                method_spec.confidence_level,
                n_groups,
            )
            rare_intervals.extend(records)
        elif method_id is OffTargetMethodId.RARE_SPIKE_IN:
            records, reasons = _spike_in_calibrations(
                assessment_spec,
                method_spec,
                method_input,
            )
            spike_in.extend(records)
        elif method_id is OffTargetMethodId.RARE_BINOMIAL_PLANNER:
            planning.extend(_single_state_planning_records(method_spec))
        elif method_id is OffTargetMethodId.OOD_DISAGREEMENT:
            disagreement = _ood_disagreement(method_spec, method_input)
            if disagreement.assessment_state == "not_assessed":
                reasons = disagreement.reason_codes
        elif method_id is OffTargetMethodId.OOD_ENSEMBLE:
            ensemble = _ood_ensemble(method_spec, method_input)
            if ensemble.assessment_state == "not_assessed":
                reasons = ensemble.reason_codes
        execution_reasons[method_id] = reasons

    packages = _package_versions()
    executions = [
        MethodExecutionRecord(
            method_id=method_id,
            method_ref=METHOD_REFS[method_id][0],
            implementation=METHOD_REFS[method_id][1],
            execution_state=(
                MethodExecutionState.NOT_ASSESSED
                if execution_reasons[method_id]
                else MethodExecutionState.SUCCEEDED
            ),
            package_versions=packages,
            reason_codes=execution_reasons[method_id],
        )
        for method_id in method_spec.selected_method_ids
    ]
    return OffTargetMethodBundle(
        object_version="0.1.0",
        bundle_id=f"off-target-method-bundle:{input_hash[:24]}",
        bundle_version="0.1.0",
        tool_id="P0-05",
        tool_version=tool_version,
        method_spec_sha256=method_spec_sha256,
        method_input_sha256=method_input_sha256,
        biological_unit_manifest_sha256=biological_unit_manifest_sha256,
        analysis_unit_refs=sorted(
            item.analysis_unit_ref for item in method_input.analysis_units
        ),
        independence_group_refs=sorted(
            {item.independence_group_ref for item in method_input.analysis_units}
        ),
        executions=executions,
        composition_intervals=composition_intervals,
        hard_soft_sensitivity=sensitivity,
        rare_intervals=rare_intervals,
        spike_in_calibrations=spike_in,
        planning_records=planning,
        ood_disagreement=disagreement,
        ood_ensemble=ensemble,
        evidence_state="shadow",
        score_state="unavailable",
        domain_score=None,
        created_at=method_input.created_at,
    )
