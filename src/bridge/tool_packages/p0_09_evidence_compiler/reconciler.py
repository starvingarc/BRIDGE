from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Mapping

from bridge.tool_packages.p0_08_evidence_sufficiency.models import (
    EvidenceSufficiencyProfile,
    EvidenceSufficiencyState,
)
from bridge.tool_packages.p0_09_evidence_compiler.compiler import (
    canonical_hash,
    effective_records,
    reconciliation_identity,
)
from bridge.tool_packages.p0_09_evidence_compiler.models import (
    ChannelResolution,
    ClaimRegistry,
    ClaimSpec,
    EvidenceApplicability,
    EvidenceCompilationBundle,
    EvidenceFamilyRegistry,
    EvidenceFamilySpec,
    EvidenceFamilyStatus,
    EvidenceLifecycleState,
    EvidenceRecord,
    EvidenceRelation,
    EvidenceRequirement,
    EvidenceRequirementState,
    EvidenceState,
    EvidenceTier,
    GraphKind,
    ReconciliationEligibility,
    ReconciliationRecord,
    ReconciliationRecordSet,
    ReconciliationSpec,
    ReconciliationSpecRegistry,
    ReconciliationState,
    RegistryStatus,
    VersionedObjectRef,
)


RECONCILIATION_REASON_CODES = (
    "claim_contract_not_frozen",
    "reconciliation_spec_not_frozen",
    "reconciliation_contract_mismatch",
    "sufficiency_not_sufficient",
    "lower_tier_excluded",
    "inactive_evidence_excluded",
    "not_applicable_evidence_excluded",
    "tool_run_state_excluded",
    "unreviewed_family_excluded",
    "evidence_state_excluded",
    "same_family_records_deduplicated",
    "same_family_direction_conflict",
    "non_independent_families_deduplicated",
    "dependent_family_direction_conflict",
    "required_independent_channel_missing",
    "no_formal_eligible_evidence",
    "integration_channel_direction_conflict",
    "independent_confirmation_resolved_conflict",
    "unresolved_cross_family_direction_conflict",
    "family_deduplicated_direction_stable",
)
REASON_ORDER = {code: index for index, code in enumerate(RECONCILIATION_REASON_CODES)}


@dataclass(frozen=True)
class ReconciliationEvidence:
    evidence_ref: str
    claim_ref: str
    family_ref: str
    profile_input_id: str | None
    profile_ref: VersionedObjectRef | None
    relation: EvidenceRelation
    evidence_state: EvidenceState
    evidence_tier: EvidenceTier
    lifecycle_state: EvidenceLifecycleState
    applicability: EvidenceApplicability
    tool_run_execution_state: str


def reconcile_graph(
    *,
    digest: str,
    graph_id: str,
    graph_version: int,
    bundle: EvidenceCompilationBundle,
    records: list[EvidenceRecord],
    requirements: list[EvidenceRequirement],
    profiles_by_input_id: Mapping[str, EvidenceSufficiencyProfile],
    family_registry: EvidenceFamilyRegistry,
    claim_registry: ClaimRegistry,
    reconciliation_registry: ReconciliationSpecRegistry,
    created_at: datetime,
) -> ReconciliationRecordSet:
    claims = {(item.claim_id, item.version): item for item in claim_registry.claims}
    specs = {
        (item.reconciliation_spec_id, item.version): item
        for item in reconciliation_registry.specs
    }
    families = {
        (item.evidence_family_id, item.version): item for item in family_registry.families
    }
    evidence = _project_evidence(bundle, records, profiles_by_input_id)
    relevant_claim_refs = sorted(
        {item.claim_ref for item in evidence}
        | {item.claim_ref.ref for item in requirements}
    )
    reconciliations: list[ReconciliationRecord] = []
    for claim_ref in relevant_claim_refs:
        claim_id, claim_version = claim_ref.rsplit("@", 1)
        claim = claims.get((claim_id, claim_version))
        if claim is None:
            continue
        spec = specs.get(
            (
                claim.reconciliation_spec_ref.object_id,
                claim.reconciliation_spec_ref.object_version,
            )
        )
        reconciliations.append(
            _reconcile_claim(
                graph_id=graph_id,
                graph_version=graph_version,
                claim=claim,
                spec=spec,
                claim_registry=claim_registry,
                reconciliation_registry=reconciliation_registry,
                family_registry=family_registry,
                families=families,
                evidence=[item for item in evidence if item.claim_ref == claim.ref],
                requirements=requirements,
                profiles_by_input_id=profiles_by_input_id,
                created_at=created_at,
            )
        )
    return ReconciliationRecordSet(
        reconciliation_set_id=f"reconciliation-record-set:{digest}",
        reconciliation_set_version="0.1.0",
        graph_id=graph_id,
        graph_version=graph_version,
        records=sorted(reconciliations, key=lambda item: item.claim_ref.ref),
    )


def _project_evidence(
    bundle: EvidenceCompilationBundle,
    records: list[EvidenceRecord],
    profiles_by_input_id: Mapping[str, EvidenceSufficiencyProfile],
) -> list[ReconciliationEvidence]:
    if bundle.graph_kind is GraphKind.CASE:
        profile_ids = {
            (profile.profile_id, profile.profile_version): input_id
            for input_id, profile in profiles_by_input_id.items()
        }
        return [
            ReconciliationEvidence(
                evidence_ref=record.ref,
                claim_ref=record.claim_ref.ref,
                family_ref=record.evidence_family_ref.ref,
                profile_input_id=profile_ids.get(
                    (
                        record.sufficiency_profile_ref.object_id,
                        record.sufficiency_profile_ref.object_version,
                    )
                ),
                profile_ref=record.sufficiency_profile_ref,
                relation=record.relation,
                evidence_state=record.evidence_state,
                evidence_tier=record.evidence_tier,
                lifecycle_state=(
                    record.lifecycle_state
                    if record in effective_records(records)
                    else EvidenceLifecycleState.SUPERSEDED
                ),
                applicability=record.applicability,
                tool_run_execution_state=record.tool_run_execution_state,
            )
            for record in records
        ]
    return [
        ReconciliationEvidence(
            evidence_ref=item.evidence_ref,
            claim_ref=item.comparison_claim_ref.ref,
            family_ref=item.evidence_family_ref.ref,
            profile_input_id=item.sufficiency_profile_input_id,
            profile_ref=(
                VersionedObjectRef(
                    object_id=profiles_by_input_id[item.sufficiency_profile_input_id].profile_id,
                    object_version=profiles_by_input_id[item.sufficiency_profile_input_id].profile_version,
                )
                if item.sufficiency_profile_input_id in profiles_by_input_id
                else None
            ),
            relation=item.relation,
            evidence_state=item.evidence_state,
            evidence_tier=item.evidence_tier,
            lifecycle_state=item.lifecycle_state,
            applicability=item.applicability,
            tool_run_execution_state=item.tool_run_execution_state,
        )
        for item in bundle.external_case_evidence_refs
    ]


def _reconcile_claim(
    *,
    graph_id: str,
    graph_version: int,
    claim: ClaimSpec,
    spec: ReconciliationSpec | None,
    claim_registry: ClaimRegistry,
    reconciliation_registry: ReconciliationSpecRegistry,
    family_registry: EvidenceFamilyRegistry,
    families: Mapping[tuple[str, str], EvidenceFamilySpec],
    evidence: list[ReconciliationEvidence],
    requirements: list[EvidenceRequirement],
    profiles_by_input_id: Mapping[str, EvidenceSufficiencyProfile],
    created_at: datetime,
) -> ReconciliationRecord:
    reasons: list[str] = []
    eligibility = ReconciliationEligibility.ELIGIBLE
    if (
        claim_registry.status is not RegistryStatus.FROZEN
        or claim.status is not RegistryStatus.FROZEN
    ):
        reasons.append("claim_contract_not_frozen")
        eligibility = ReconciliationEligibility.NOT_ASSESSED
    if (
        spec is None
        or reconciliation_registry.status is not RegistryStatus.FROZEN
        or spec.status is not RegistryStatus.FROZEN
    ):
        reasons.append("reconciliation_spec_not_frozen")
        eligibility = ReconciliationEligibility.NOT_ASSESSED
    if spec is not None and spec.claim_type != claim.claim_type:
        reasons.append("reconciliation_contract_mismatch")
        eligibility = ReconciliationEligibility.NOT_ASSESSED

    profile_input_ids = sorted(
        {item.profile_input_id for item in evidence if item.profile_input_id is not None}
    )
    profiles = [profiles_by_input_id[item] for item in profile_input_ids]
    profile_refs = sorted(
        {
            item.profile_ref.ref: item.profile_ref
            for item in evidence
            if item.profile_ref is not None
        }.values(),
        key=lambda item: item.ref,
    )
    if eligibility is ReconciliationEligibility.ELIGIBLE and (
        not profiles
        or any(
            profile.evidence_sufficiency_state is not EvidenceSufficiencyState.SUFFICIENT
            for profile in profiles
        )
    ):
        reasons.append("sufficiency_not_sufficient")
        eligibility = ReconciliationEligibility.INSUFFICIENT_EVIDENCE

    included: list[ReconciliationEvidence] = []
    excluded_refs: list[str] = []
    exclusion_reasons: list[str] = []
    allowed_states = set(spec.allowed_evidence_states) if spec is not None else set()
    for item in sorted(evidence, key=lambda value: value.evidence_ref):
        item_reasons: list[str] = []
        if item.evidence_tier is not EvidenceTier.FORMAL:
            item_reasons.append("lower_tier_excluded")
        if item.lifecycle_state is not EvidenceLifecycleState.ACTIVE:
            item_reasons.append("inactive_evidence_excluded")
        if item.applicability is not EvidenceApplicability.APPLICABLE:
            item_reasons.append("not_applicable_evidence_excluded")
        if item.tool_run_execution_state not in {"succeeded", "partial"}:
            item_reasons.append("tool_run_state_excluded")
        family_id, family_version = item.family_ref.rsplit("@", 1)
        family = families.get((family_id, family_version))
        if (
            family is None
            or family.status is not EvidenceFamilyStatus.REVIEWED
            or family_registry.status is not RegistryStatus.FROZEN
        ):
            item_reasons.append("unreviewed_family_excluded")
        if item.evidence_state not in allowed_states:
            item_reasons.append("evidence_state_excluded")
        if item_reasons:
            excluded_refs.append(item.evidence_ref)
            exclusion_reasons.extend(item_reasons)
        else:
            included.append(item)
    reasons.extend(exclusion_reasons)

    channel_resolutions: list[ChannelResolution] = []
    if spec is not None:
        role_order = [*spec.required_channel_roles]
        role_order.extend(
            role
            for role in spec.optional_channel_roles
            if role not in role_order
        )
        for role in role_order:
            resolution, role_reasons = _resolve_channel(
                role=role,
                evidence=included,
                families=families,
                minimum=spec.minimum_independent_families_by_role.get(role, 0),
            )
            channel_resolutions.append(resolution)
            reasons.extend(role_reasons)

    open_requirements = _latest_open_requirements(requirements, claim.ref)
    if spec is not None:
        missing_required = any(
            not resolution.eligible
            for resolution in channel_resolutions
            if resolution.channel_role in spec.required_channel_roles
        )
        if missing_required:
            reasons.append("required_independent_channel_missing")
            if eligibility is ReconciliationEligibility.ELIGIBLE:
                eligibility = ReconciliationEligibility.INSUFFICIENT_EVIDENCE
    if not included:
        reasons.append("no_formal_eligible_evidence")
        if eligibility is ReconciliationEligibility.ELIGIBLE:
            eligibility = ReconciliationEligibility.INSUFFICIENT_EVIDENCE

    state: ReconciliationState | None = None
    direction: EvidenceRelation | None = None
    if eligibility is ReconciliationEligibility.ELIGIBLE and spec is not None:
        state, direction, state_reason = _resolve_state(
            spec=spec,
            resolutions=channel_resolutions,
            evidence=included,
            families=families,
        )
        reasons.append(state_reason)

    reconciliation_id = reconciliation_identity(
        graph_id,
        VersionedObjectRef(object_id=claim.claim_id, object_version=claim.version),
        claim.reconciliation_spec_ref,
    )
    content_payload = {
        "graph_id": graph_id,
        "graph_version": graph_version,
        "claim_ref": claim.ref,
        "reconciliation_spec_ref": claim.reconciliation_spec_ref.ref,
        "sufficiency_profile_refs": [item.ref for item in profile_refs],
        "eligibility": eligibility.value,
        "state": state.value if state else None,
        "direction": direction.value if direction else None,
        "channel_resolutions": [item.model_dump(mode="json") for item in channel_resolutions],
        "included_evidence_refs": sorted(item.evidence_ref for item in included),
        "excluded_evidence_refs": sorted(set(excluded_refs)),
        "open_requirement_refs": open_requirements,
        "reason_codes": _ordered_reasons(reasons),
    }
    return ReconciliationRecord(
        reconciliation_id=reconciliation_id,
        reconciliation_version=graph_version,
        graph_id=graph_id,
        graph_version=graph_version,
        claim_ref=VersionedObjectRef(object_id=claim.claim_id, object_version=claim.version),
        reconciliation_spec_ref=claim.reconciliation_spec_ref,
        sufficiency_profile_refs=profile_refs,
        eligibility=eligibility,
        state=state,
        direction=direction,
        channel_resolutions=channel_resolutions,
        included_evidence_refs=sorted(item.evidence_ref for item in included),
        excluded_evidence_refs=sorted(set(excluded_refs)),
        open_requirement_refs=open_requirements,
        reason_codes=_ordered_reasons(reasons),
        created_at=created_at,
        content_hash=canonical_hash(content_payload),
    )


def _resolve_channel(
    *,
    role: str,
    evidence: list[ReconciliationEvidence],
    families: Mapping[tuple[str, str], EvidenceFamilySpec],
    minimum: int,
) -> tuple[ChannelResolution, list[str]]:
    role_items = []
    for item in evidence:
        family_id, family_version = item.family_ref.rsplit("@", 1)
        family = families.get((family_id, family_version))
        if family is not None and family.channel_role == role:
            role_items.append(item)
    by_family: dict[str, list[ReconciliationEvidence]] = defaultdict(list)
    for item in role_items:
        by_family[item.family_ref].append(item)
    reasons: list[str] = []
    family_directions: dict[str, EvidenceRelation | None] = {}
    for family_ref, items in sorted(by_family.items()):
        directions = {item.relation for item in items}
        if len(items) > 1:
            reasons.append("same_family_records_deduplicated")
        if len(directions) != 1:
            reasons.append("same_family_direction_conflict")
            family_directions[family_ref] = None
        else:
            family_directions[family_ref] = next(iter(directions))
    components = _family_independence_components(set(by_family), families)
    by_component: dict[str, list[str]] = defaultdict(list)
    for family_ref, component in components.items():
        by_component[component].append(family_ref)
    component_directions: list[EvidenceRelation] = []
    for component_families in by_component.values():
        if len(component_families) > 1:
            reasons.append("non_independent_families_deduplicated")
        values = [family_directions[item] for item in component_families]
        directions = {item for item in values if item is not None}
        if any(item is None for item in values) or len(directions) > 1:
            if len(component_families) > 1 and directions:
                reasons.append("dependent_family_direction_conflict")
            continue
        if len(directions) == 1:
            component_directions.append(next(iter(directions)))
    contributing = component_directions
    direction = contributing[0] if contributing and len(set(contributing)) == 1 else None
    eligible = len(contributing) >= minimum
    return (
        ChannelResolution(
            channel_role=role,
            evidence_refs=sorted(item.evidence_ref for item in role_items),
            evidence_family_refs=sorted(by_family),
            direction=direction,
            eligible=eligible,
            reason_codes=_ordered_reasons(reasons),
        ),
        reasons,
    )


def _resolve_state(
    *,
    spec: ReconciliationSpec,
    resolutions: list[ChannelResolution],
    evidence: list[ReconciliationEvidence],
    families: Mapping[tuple[str, str], EvidenceFamilySpec],
) -> tuple[ReconciliationState, EvidenceRelation | None, str]:
    by_role = {item.channel_role: item for item in resolutions}
    principal_roles = [*spec.primary_channel_roles, *spec.confirmation_channel_roles]
    principal_directions = {
        by_role[role].direction
        for role in principal_roles
        if role in by_role and by_role[role].eligible and by_role[role].direction is not None
    }
    integration_directions = {
        by_role[role].direction
        for role in spec.integration_sensitive_channel_roles
        if role in by_role and by_role[role].eligible and by_role[role].direction is not None
    }
    if len(principal_directions) == 1:
        resolved = next(iter(principal_directions))
        if any(item is not resolved for item in integration_directions):
            return (
                ReconciliationState.INTEGRATION_SENSITIVE,
                resolved,
                "integration_channel_direction_conflict",
            )

    unresolved_primary = any(
        role not in by_role
        or not by_role[role].eligible
        or by_role[role].direction is None
        for role in spec.primary_channel_roles
    ) or len(
        {
            by_role[role].direction
            for role in spec.primary_channel_roles
            if role in by_role and by_role[role].direction is not None
        }
    ) > 1
    confirmation = [by_role[role] for role in spec.confirmation_channel_roles if role in by_role]
    confirmation_directions = {
        item.direction for item in confirmation if item.eligible and item.direction is not None
    }
    if (
        unresolved_primary
        and spec.confirmation_channel_roles
        and len(confirmation) == len(spec.confirmation_channel_roles)
        and all(item.eligible for item in confirmation)
        and len(confirmation_directions) == 1
        and _confirmation_is_independent(spec, resolutions, evidence, families)
    ):
        return (
            ReconciliationState.CONSENSUS_SUPPORTED,
            next(iter(confirmation_directions)),
            "independent_confirmation_resolved_conflict",
        )

    required_primary = set(spec.required_channel_roles) | set(spec.primary_channel_roles)
    relevant = [by_role[role] for role in required_primary if role in by_role]
    relevant_directions = {
        item.direction for item in relevant if item.eligible and item.direction is not None
    }
    if (
        len(relevant) != len(required_primary)
        or any(not item.eligible or item.direction is None for item in relevant)
        or len(relevant_directions) != 1
    ):
        return (
            ReconciliationState.UNSTABLE,
            None,
            "unresolved_cross_family_direction_conflict",
        )
    resolved = next(iter(relevant_directions))
    all_eligible_directions = {
        item.direction
        for item in resolutions
        if item.eligible and item.direction is not None
    }
    if any(item is not resolved for item in all_eligible_directions):
        return (
            ReconciliationState.UNSTABLE,
            None,
            "unresolved_cross_family_direction_conflict",
        )
    return (
        ReconciliationState.STABLE,
        resolved,
        "family_deduplicated_direction_stable",
    )


def _confirmation_is_independent(
    spec: ReconciliationSpec,
    resolutions: list[ChannelResolution],
    evidence: list[ReconciliationEvidence],
    families: Mapping[tuple[str, str], EvidenceFamilySpec],
) -> bool:
    by_role = {item.channel_role: item for item in resolutions}
    primary_families = {
        family
        for role in spec.primary_channel_roles
        for family in by_role.get(
            role,
            ChannelResolution(
                channel_role=role,
                evidence_refs=[],
                evidence_family_refs=[],
                direction=None,
                eligible=False,
                reason_codes=[],
            ),
        ).evidence_family_refs
    }
    confirmation_families = {
        family
        for role in spec.confirmation_channel_roles
        for family in by_role.get(
            role,
            ChannelResolution(
                channel_role=role,
                evidence_refs=[],
                evidence_family_refs=[],
                direction=None,
                eligible=False,
                reason_codes=[],
            ),
        ).evidence_family_refs
    }
    all_families = primary_families | confirmation_families
    components = _family_independence_components(all_families, families)
    del evidence
    return not any(
        components.get(primary) == components.get(confirmation)
        for primary in primary_families
        for confirmation in confirmation_families
    )


def _family_independence_components(
    family_refs: set[str],
    families: Mapping[tuple[str, str], EvidenceFamilySpec],
) -> dict[str, str]:
    parent = {item: item for item in family_refs}

    def find(item: str) -> str:
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    def union(left: str, right: str) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[max(left_root, right_root)] = min(left_root, right_root)

    resolved = {
        ref: families.get(tuple(ref.rsplit("@", 1))) for ref in family_refs
    }
    tokens: dict[str, set[str]] = {}
    for ref, family in resolved.items():
        if family is None:
            tokens[ref] = set()
            continue
        tokens[ref] = set(family.known_dependencies)
    ordered = sorted(family_refs)
    for index, left in enumerate(ordered):
        left_family = resolved[left]
        for right in ordered[index + 1 :]:
            right_family = resolved[right]
            if left_family is None or right_family is None:
                continue
            right_ids = {right, right_family.evidence_family_id}
            left_ids = {left, left_family.evidence_family_id}
            if (
                left_family.independence_scope == right_family.independence_scope
                or bool(tokens[left] & tokens[right])
                or bool(tokens[left] & right_ids)
                or bool(tokens[right] & left_ids)
            ):
                union(left, right)
    return {item: find(item) for item in family_refs}


def _latest_open_requirements(
    requirements: Iterable[EvidenceRequirement], claim_ref: str
) -> list[str]:
    latest: dict[str, EvidenceRequirement] = {}
    for item in requirements:
        if item.claim_ref.ref == claim_ref and (
            item.requirement_id not in latest
            or item.requirement_version > latest[item.requirement_id].requirement_version
        ):
            latest[item.requirement_id] = item
    return sorted(
        item.ref
        for item in latest.values()
        if item.state is EvidenceRequirementState.OPEN
    )


def _ordered_reasons(reasons: Iterable[str]) -> list[str]:
    return sorted(
        set(reasons),
        key=lambda item: (REASON_ORDER.get(item, len(REASON_ORDER)), item),
    )
