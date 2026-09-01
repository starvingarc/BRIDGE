from __future__ import annotations

import math
from collections import defaultdict

from bridge.tool_packages._configurable_contracts import (
    BiologicalUnitManifest,
    ProductCase,
)
from bridge.tool_packages.p0_05_off_target_control.method_models import (
    OffTargetMethodInput,
    OffTargetMethodSpec,
)
from bridge.tool_packages.p0_05_off_target_control.models import (
    OffTargetAssessmentSpec,
    OffTargetEvidenceBundle,
    StateRoleMap,
)
from bridge.toolkit.contracts import (
    CellStateEvidenceProfileV3,
    StructuredInputRef,
)


def method_binding_reasons(
    *,
    input_refs: dict[str, StructuredInputRef],
    product_case: ProductCase,
    cell_state_profile: CellStateEvidenceProfileV3,
    evidence_bundle: OffTargetEvidenceBundle,
    biological_units: BiologicalUnitManifest,
    method_spec: OffTargetMethodSpec,
    method_input: OffTargetMethodInput,
    role_map: StateRoleMap,
    assessment_spec: OffTargetAssessmentSpec,
) -> list[str]:
    reasons: list[str] = []
    manifest_ref = biological_units.ref.ref
    manifest_sha = input_refs["biological_unit_manifest"].sha256
    cell_state_sha = input_refs["cell_state_evidence_profile"].sha256
    evidence_sha = input_refs["off_target_evidence_bundle"].sha256

    if not method_spec.active:
        reasons.append("off_target_method_spec_inactive")
    if not biological_units.review_claim_is_present:
        reasons.append("biological_unit_lineage_not_reviewed")
    if (
        product_case.biological_unit_manifest_ref is None
        or product_case.biological_unit_manifest_ref.ref != manifest_ref
        or product_case.biological_unit_manifest_sha256 != manifest_sha
    ):
        reasons.append("product_case_biological_unit_manifest_mismatch")
    view = cell_state_profile.input_data_view
    if (
        view.biological_unit_manifest_ref != manifest_ref
        or view.biological_unit_manifest_sha256 != manifest_sha
    ):
        reasons.append("cell_state_biological_unit_manifest_mismatch")
    if biological_units.data_view_ref != view.view_id:
        reasons.append("biological_unit_data_view_mismatch")
    if biological_units.n_observations != cell_state_profile.n_observations:
        reasons.append("biological_unit_observation_count_mismatch")

    expected_bindings = {
        item.analysis_unit_ref.ref: item.independence_group_ref.ref
        for item in biological_units.unit_bindings
    }
    observed_bindings = {
        item.analysis_unit_ref: item.independence_group_ref
        for item in method_input.analysis_units
    }
    if set(observed_bindings) != set(expected_bindings):
        reasons.append("method_input_analysis_unit_set_mismatch")
    elif any(
        observed_bindings[unit_ref] != group_ref
        for unit_ref, group_ref in expected_bindings.items()
    ):
        reasons.append("method_input_independence_group_mismatch")

    if method_input.product_case_ref != product_case.ref.ref:
        reasons.append("method_input_product_case_ref_mismatch")
    if method_input.product_case_sha256 != input_refs["product_case"].sha256:
        reasons.append("method_input_product_case_checksum_mismatch")
    if method_input.cell_state_profile_id != cell_state_profile.profile_id:
        reasons.append("method_input_cell_state_profile_ref_mismatch")
    if method_input.cell_state_profile_sha256 != cell_state_sha:
        reasons.append("method_input_cell_state_profile_checksum_mismatch")
    if method_input.evidence_bundle_ref != evidence_bundle.ref.ref:
        reasons.append("method_input_evidence_bundle_ref_mismatch")
    if method_input.evidence_bundle_sha256 != evidence_sha:
        reasons.append("method_input_evidence_bundle_checksum_mismatch")
    if method_input.biological_unit_manifest_ref != manifest_ref:
        reasons.append("method_input_biological_unit_manifest_ref_mismatch")
    if method_input.biological_unit_manifest_sha256 != manifest_sha:
        reasons.append("method_input_biological_unit_manifest_checksum_mismatch")

    if sum(item.denominator_count for item in method_input.analysis_units) != (
        evidence_bundle.denominator.n_observations
    ):
        reasons.append("method_input_denominator_mismatch")
    state_soft: dict[str, list[float]] = defaultdict(list)
    state_hard: dict[str, int] = defaultdict(int)
    unknown_soft: dict[str, list[float]] = defaultdict(list)
    unknown_hard: dict[str, int] = defaultdict(int)
    for unit in method_input.analysis_units:
        for item in unit.state_observations:
            state_soft[item.state_id].append(item.soft_mass)
            state_hard[item.state_id] += item.hard_count
        for item in unit.unknown_observations:
            unknown_soft[item.reason_id].append(item.soft_mass)
            unknown_hard[item.reason_id] += item.hard_count
    bundle_states = {item.state_id: item for item in evidence_bundle.state_observations}
    bundle_unknown = {
        item.reason_id: item for item in evidence_bundle.unknown_observations
    }
    if set(state_soft) != set(bundle_states):
        reasons.append("method_input_state_set_mismatch")
    else:
        for state_id, observation in bundle_states.items():
            if state_hard[state_id] != observation.observed_count or not math.isclose(
                math.fsum(state_soft[state_id]),
                observation.soft_mass,
                rel_tol=0.0,
                abs_tol=max(1e-9, observation.soft_mass * 1e-9),
            ):
                reasons.append("method_input_state_aggregate_mismatch")
                break
    if set(unknown_soft) != set(bundle_unknown):
        reasons.append("method_input_unknown_set_mismatch")
    else:
        for reason_id, observation in bundle_unknown.items():
            if unknown_hard[
                reason_id
            ] != observation.observed_count or not math.isclose(
                math.fsum(unknown_soft[reason_id]),
                observation.soft_mass,
                rel_tol=0.0,
                abs_tol=max(1e-9, observation.soft_mass * 1e-9),
            ):
                reasons.append("method_input_unknown_aggregate_mismatch")
                break

    consensus_counts = {
        item.label: item.count
        for item in cell_state_profile.composition.records
        if item.view.value == "consensus_supported_only"
    }
    if consensus_counts != {
        state_id: item.observed_count for state_id, item in bundle_states.items()
    }:
        reasons.append("cell_state_consensus_composition_mismatch")
    unresolved_count = sum(
        item.count
        for item in cell_state_profile.composition.records
        if item.view.value == "reconciliation_state"
        and item.state_evidence_state.value != "candidate"
    )
    if unresolved_count != sum(
        item.observed_count for item in evidence_bundle.unknown_observations
    ):
        reasons.append("cell_state_unknown_composition_mismatch")

    role_state_ids = {item.state_id for item in role_map.assignments}
    rare_state_ids = {item.state_id for item in assessment_spec.rare_state_rules}
    allowed_unknown = set(assessment_spec.allowed_unknown_reason_ids)
    if not set(state_soft).issubset(role_state_ids):
        reasons.append("method_input_contains_unmapped_state")
    if any(
        item.state_id not in rare_state_ids for item in method_input.spike_in_trials
    ):
        reasons.append("spike_in_trial_state_not_declared")
    manifest_groups = set(expected_bindings.values())
    if any(
        item.independence_group_ref not in manifest_groups
        for item in method_input.spike_in_trials
    ):
        reasons.append("spike_in_independence_group_not_declared")
    spike_in_group_keys = [
        (item.state_id, item.spike_fraction, item.independence_group_ref)
        for item in method_input.spike_in_trials
    ]
    if len(spike_in_group_keys) != len(set(spike_in_group_keys)):
        reasons.append("spike_in_independence_group_reused_within_fraction")

    expected_ood_channels = {
        item.channel_id: item for item in method_spec.ood_channel_bindings
    }
    if set(expected_ood_channels) != {
        item.channel_id for item in method_input.ood_channels
    }:
        reasons.append("ood_channel_set_mismatch")
    families_by_upstream_hash: dict[str, set[str]] = defaultdict(set)
    for binding in method_spec.ood_channel_bindings:
        families_by_upstream_hash[binding.upstream_result_sha256].add(
            binding.source_family_id
        )
    if any(len(families) > 1 for families in families_by_upstream_hash.values()):
        reasons.append("ood_upstream_result_reused_across_source_families")
    if any(
        item.reason_id is not None and item.reason_id not in allowed_unknown
        for item in method_input.ood_channels
    ):
        reasons.append("ood_channel_reason_not_allowed")
    if any(
        item.state_id not in rare_state_ids for item in method_spec.planning_targets
    ):
        reasons.append("planning_target_state_not_declared")
    if any(
        item.reason_id not in allowed_unknown for item in method_spec.ood_decision_rules
    ):
        reasons.append("ood_decision_reason_not_allowed")
    return reasons
