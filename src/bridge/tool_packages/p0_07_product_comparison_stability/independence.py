from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Literal

from bridge.tool_packages.p0_07_product_comparison_stability.models import (
    ComparisonGroup,
    ProductEvidenceBundle,
)

IndependenceState = Literal["declared", "not_recorded", "inconsistent"]


@dataclass(frozen=True)
class AnalysisUnitIndependence:
    bundle_ref: str
    analysis_unit_ref: str
    state: IndependenceState
    biological_unit_manifest_ref: str | None
    biological_unit_manifest_sha256: str | None
    independence_scope_ref: str | None
    independence_group_refs: tuple[str, ...]
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class GroupIndependence:
    group_id: str
    state: IndependenceState
    analysis_unit_count: int
    independence_scope_ref: str | None
    independence_group_refs: tuple[str, ...]
    declared_independence_group_count: int | None
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class ComparisonIndependence:
    by_bundle_ref: dict[str, AnalysisUnitIndependence]
    by_group_id: dict[str, GroupIndependence]


def summarize_independence(
    groups: list[ComparisonGroup],
    grouped: dict[str, list[ProductEvidenceBundle]],
) -> ComparisonIndependence:
    by_bundle_ref: dict[str, AnalysisUnitIndependence] = {}
    group_candidates: dict[str, GroupIndependence] = {}
    ref_owners: dict[str, set[str]] = defaultdict(set)

    for group in groups:
        units: list[AnalysisUnitIndependence] = []
        for bundle in grouped[group.group_id]:
            case = bundle.product_case
            bound_values = (
                case.biological_unit_manifest_ref,
                case.biological_unit_manifest_sha256,
                case.independence_scope_ref,
            )
            refs = tuple(sorted(ref.ref for ref in case.independence_group_refs))
            any_binding = any(value is not None for value in bound_values) or bool(refs)
            complete = all(value is not None for value in bound_values) and len(refs) == 1
            for ref in refs:
                ref_owners[ref].add(group.group_id)
            if not any_binding:
                state: IndependenceState = "not_recorded"
                reasons = ("independence_not_recorded",)
            elif complete:
                state = "declared"
                reasons = ()
            else:
                state = "inconsistent"
                reason = (
                    "independence_requires_one_group_per_analysis_unit"
                    if all(value is not None for value in bound_values) and len(refs) != 1
                    else "independence_binding_incomplete"
                )
                reasons = (reason,)
            unit = AnalysisUnitIndependence(
                bundle_ref=bundle.ref.ref,
                analysis_unit_ref=case.sample_or_preparation_ref.ref,
                state=state,
                biological_unit_manifest_ref=(
                    case.biological_unit_manifest_ref.ref
                    if case.biological_unit_manifest_ref is not None
                    else None
                ),
                biological_unit_manifest_sha256=case.biological_unit_manifest_sha256,
                independence_scope_ref=(
                    case.independence_scope_ref.ref
                    if case.independence_scope_ref is not None
                    else None
                ),
                independence_group_refs=refs,
                reason_codes=reasons,
            )
            units.append(unit)
            by_bundle_ref[unit.bundle_ref] = unit

        scopes = {
            unit.independence_scope_ref
            for unit in units
            if unit.independence_scope_ref is not None
        }
        refs = tuple(
            sorted(
                {
                    ref
                    for unit in units
                    for ref in unit.independence_group_refs
                }
            )
        )
        analysis_units = {unit.analysis_unit_ref for unit in units}
        reasons = {reason for unit in units for reason in unit.reason_codes}
        if len(analysis_units) != len(units):
            reasons.add("duplicate_analysis_unit_ref")
        if units and all(unit.state == "not_recorded" for unit in units):
            state = "not_recorded"
        elif (
            any(unit.state != "declared" for unit in units)
            or len(scopes) != 1
            or len(refs) != len(units)
            or len(analysis_units) != len(units)
        ):
            state = "inconsistent"
            if len(scopes) != 1:
                reasons.add("independence_scope_inconsistent_within_group")
            if len(refs) != len(units):
                reasons.add("independence_groups_not_one_to_one_with_analysis_units")
        else:
            state = "declared"
        group_candidates[group.group_id] = GroupIndependence(
            group_id=group.group_id,
            state=state,
            analysis_unit_count=len(analysis_units),
            independence_scope_ref=next(iter(scopes)) if state == "declared" else None,
            independence_group_refs=refs,
            declared_independence_group_count=(
                len(refs) if state == "declared" else None
            ),
            reason_codes=tuple(sorted(reasons)),
        )

    overlapping_groups = {
        group_id
        for owners in ref_owners.values()
        if len(owners) > 1
        for group_id in owners
    }
    by_group_id: dict[str, GroupIndependence] = {}
    for group_id, summary in group_candidates.items():
        if group_id not in overlapping_groups:
            by_group_id[group_id] = summary
            continue
        by_group_id[group_id] = GroupIndependence(
            group_id=summary.group_id,
            state="inconsistent",
            analysis_unit_count=summary.analysis_unit_count,
            independence_scope_ref=None,
            independence_group_refs=summary.independence_group_refs,
            declared_independence_group_count=None,
            reason_codes=tuple(
                sorted(
                    {
                        *summary.reason_codes,
                        "independence_group_overlap_across_comparison_groups",
                    }
                )
            ),
        )
    return ComparisonIndependence(
        by_bundle_ref=by_bundle_ref,
        by_group_id=by_group_id,
    )
