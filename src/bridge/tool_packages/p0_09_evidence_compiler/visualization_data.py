from __future__ import annotations

from collections import defaultdict
import hashlib
from typing import Annotated, Literal, Self

from pydantic import Field, StrictInt, field_validator, model_validator

from bridge.tool_packages.p0_09_evidence_compiler.models import (
    ClaimRegistry,
    CompiledEvidenceGraph,
    EvidenceApplicability,
    EvidenceFamilyRegistry,
    EvidenceRelation,
    EvidenceRequirementState,
    EvidenceState,
    ReconciliationEligibility,
    ReconciliationState,
)
from bridge.tool_packages.p0_09_evidence_compiler.reconciler import (
    _family_independence_components,
)
from bridge.toolkit.contracts import FrozenModel
from bridge.toolkit.visualization import VisualizationArtifactV2


EVIDENCE_COMPILER_VISUALIZATION_DATA_SCHEMA_REF = (
    "bridge://schemas/evidence-compiler-visualization-data/v0.1"
)
P009_VISUALIZATION_ARTIFACT_SET_SCHEMA_REF = (
    "bridge://schemas/p0-09-visualization-artifact-set/v0.1"
)
CLAIM_INTERPRETATION_COMPONENT_REF = (
    "bridge.evidence-compiler.claim-interpretation@0.1.0"
)
FAMILY_RELATIONS_COMPONENT_REF = (
    "bridge.evidence-compiler.family-relations@0.1.0"
)
REQUIREMENTS_EXCLUSIONS_COMPONENT_REF = (
    "bridge.evidence-compiler.requirements-exclusions@0.1.0"
)
_COMPONENT_REFS = (
    CLAIM_INTERPRETATION_COMPONENT_REF,
    FAMILY_RELATIONS_COMPONENT_REF,
    REQUIREMENTS_EXCLUSIONS_COMPONENT_REF,
)
_SHA256 = r"^[0-9a-f]{64}$"

_MISSINGNESS_BY_EVIDENCE_STATE = {
    EvidenceState.MISSING: "missing",
    EvidenceState.ALERT: "conflict",
    EvidenceState.UNKNOWN: "not_assessed",
    EvidenceState.UNAVAILABLE: "not_assessed",
    EvidenceState.INFERRED: "none",
}


class _VisualizationRecord(FrozenModel):
    record_id: str = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)
    evidence_state: EvidenceState
    scientific_status: Literal["candidate"] = "candidate"
    missingness: Literal["none", "missing", "conflict", "not_assessed"]
    applicability: Literal[
        "applicable",
        "partially_applicable",
        "not_applicable",
        "not_assessed",
    ]
    reason_codes: list[str] = Field(default_factory=list)

    @field_validator("evidence_ids", "reason_codes")
    @classmethod
    def unique_sorted(cls, value: list[str]) -> list[str]:
        if value != sorted(set(value)):
            raise ValueError("visualization record lists must be sorted and unique")
        return value

    @model_validator(mode="after")
    def evidence_state_matches_missingness(self) -> Self:
        expected = _MISSINGNESS_BY_EVIDENCE_STATE.get(self.evidence_state)
        if expected is None or self.missingness != expected:
            raise ValueError("evidence state and missingness projection disagree")
        return self


class ClaimInterpretationRecord(_VisualizationRecord):
    claim_ref: str
    claim_type: str
    domain_id: str
    eligibility: ReconciliationEligibility
    reconciliation_state: ReconciliationState | None
    direction: EvidenceRelation | None
    included_record_count: StrictInt = Field(ge=0)
    excluded_record_count: StrictInt = Field(ge=0)
    open_requirement_count: StrictInt = Field(ge=0)
    eligible_channel_count: StrictInt = Field(ge=0)
    total_channel_count: StrictInt = Field(ge=0)
    independent_evidence_count: Literal[False] = False

    @model_validator(mode="after")
    def channel_counts_are_coherent(self) -> Self:
        if self.eligible_channel_count > self.total_channel_count:
            raise ValueError("eligible channel count exceeds total channel count")
        if self.eligibility is ReconciliationEligibility.ELIGIBLE:
            if self.reconciliation_state is None:
                raise ValueError("eligible reconciliation requires state")
            if self.reconciliation_state is ReconciliationState.UNSTABLE:
                if self.direction is not None:
                    raise ValueError("unstable reconciliation has no direction")
            elif self.direction is None:
                raise ValueError("resolved reconciliation requires direction")
        elif self.reconciliation_state is not None or self.direction is not None:
            raise ValueError("ineligible reconciliation cannot emit state or direction")
        expected_axes = (
            (EvidenceState.MISSING, "partially_applicable")
            if self.eligibility is ReconciliationEligibility.INSUFFICIENT_EVIDENCE
            else (EvidenceState.UNAVAILABLE, "not_assessed")
            if self.eligibility is ReconciliationEligibility.NOT_ASSESSED
            else (EvidenceState.ALERT, "partially_applicable")
            if self.reconciliation_state is ReconciliationState.UNSTABLE
            else (EvidenceState.INFERRED, "applicable")
        )
        if (self.evidence_state, self.applicability) != expected_axes:
            raise ValueError("claim interpretation axes disagree")
        return self


class EvidenceFamilyRelationRecord(_VisualizationRecord):
    claim_ref: str
    domain_id: str
    channel_role: str
    component_id: str
    family_refs: list[str] = Field(min_length=1)
    evidence_refs: list[str] = Field(min_length=1)
    raw_record_count: StrictInt = Field(ge=1)
    relation: Literal["supports", "contradicts", "conflict"]
    participation: Literal["included", "excluded", "mixed"]
    independent_influence_candidate: Literal[True] = True
    record_and_family_counts_are_not_independent_evidence: Literal[True] = True

    @field_validator("family_refs", "evidence_refs")
    @classmethod
    def relation_lists_are_unique_sorted(cls, value: list[str]) -> list[str]:
        if value != sorted(set(value)):
            raise ValueError("family relation lists must be sorted and unique")
        return value

    @model_validator(mode="after")
    def raw_count_matches_records(self) -> Self:
        if self.raw_record_count != len(self.evidence_refs):
            raise ValueError("raw record count must match evidence refs")
        if (
            self.relation == "conflict" and self.evidence_state is not EvidenceState.ALERT
        ):
            raise ValueError("conflicting family relations require alert evidence state")
        return self


class EvidenceRequirementRecord(_VisualizationRecord):
    requirement_ref: str
    requirement_key: str
    required_modality: str | None
    required_experiment: str | None
    record_kind: Literal["requirement"] = "requirement"
    claim_ref: str
    domain_id: str
    channel_role: str
    requirement_state: EvidenceRequirementState
    satisfying_record_count: StrictInt = Field(ge=0)
    version_history_count: StrictInt = Field(ge=1)
    missing_is_not_zero: Literal[True] = True

    @model_validator(mode="after")
    def state_matches_satisfaction(self) -> Self:
        if (
            self.requirement_state is EvidenceRequirementState.OPEN
            and self.satisfying_record_count != 0
        ):
            raise ValueError("open requirement cannot count satisfying evidence")
        if (
            self.requirement_state is EvidenceRequirementState.SATISFIED
            and self.satisfying_record_count < 1
        ):
            raise ValueError("satisfied requirement needs evidence")
        expected_axes = {
            EvidenceRequirementState.OPEN: (
                EvidenceState.MISSING,
                "partially_applicable",
            ),
            EvidenceRequirementState.SATISFIED: (
                EvidenceState.INFERRED,
                "applicable",
            ),
            EvidenceRequirementState.NOT_APPLICABLE: (
                EvidenceState.UNAVAILABLE,
                "not_applicable",
            ),
        }[self.requirement_state]
        if (self.evidence_state, self.applicability) != expected_axes:
            raise ValueError("requirement state axes disagree")
        return self


class CompilationExclusionRecord(_VisualizationRecord):
    exclusion_kind: Literal["reconciliation_exclusion", "input_rejection"]
    record_kind: Literal["exclusion"] = "exclusion"
    claim_ref: str | None
    excluded_record_count: StrictInt = Field(ge=1)
    excluded_evidence_refs: list[str]
    source_kind: str | None = None
    source_id: str | None = None
    reason_attribution_scope: Literal[
        "claim_level_not_per_evidence", "exact_rejected_input"
    ]

    @field_validator("excluded_evidence_refs")
    @classmethod
    def excluded_refs_are_unique_sorted(cls, value: list[str]) -> list[str]:
        if value != sorted(set(value)):
            raise ValueError("excluded evidence refs must be sorted and unique")
        return value

    @model_validator(mode="after")
    def attribution_is_not_invented(self) -> Self:
        if self.exclusion_kind == "reconciliation_exclusion":
            if (
                self.reason_attribution_scope != "claim_level_not_per_evidence"
                or self.source_kind is not None
                or self.source_id is not None
                or self.excluded_record_count != len(self.excluded_evidence_refs)
            ):
                raise ValueError("claim-level reasons cannot be assigned to evidence items")
        elif (
            self.reason_attribution_scope != "exact_rejected_input"
            or self.source_kind is None
            or self.source_id is None
            or self.excluded_evidence_refs
            or self.excluded_record_count != 1
        ):
            raise ValueError("input rejection requires its exact sanitized source")
        expected_axes = (
            (EvidenceState.UNKNOWN, "partially_applicable")
            if self.exclusion_kind == "reconciliation_exclusion"
            else (EvidenceState.ALERT, "not_assessed")
        )
        if (self.evidence_state, self.applicability) != expected_axes:
            raise ValueError("compilation exclusion axes disagree")
        return self


RequirementsExclusionsRecord = Annotated[
    EvidenceRequirementRecord | CompilationExclusionRecord,
    Field(discriminator="record_kind"),
]


class EvidenceCompilerVisualizationDataV1(FrozenModel):
    object_version: Literal["0.1.0"] = "0.1.0"
    schema_ref: Literal[
        "bridge://schemas/evidence-compiler-visualization-data/v0.1"
    ] = EVIDENCE_COMPILER_VISUALIZATION_DATA_SCHEMA_REF
    visualization_data_id: str = Field(min_length=1)
    producer_tool_id: Literal["P0-09"] = "P0-09"
    producer_tool_version: str
    producer_run_ref: str
    graph_id: str
    graph_version: StrictInt = Field(ge=1)
    source_input_sha256: str = Field(pattern=_SHA256)
    claim_records: list[ClaimInterpretationRecord]
    family_relation_records: list[EvidenceFamilyRelationRecord]
    requirement_records: list[EvidenceRequirementRecord]
    exclusion_records: list[CompilationExclusionRecord]
    requirements_exclusions_records: list[RequirementsExclusionsRecord]
    evidence_ids: list[str]
    limitations: list[str] = Field(min_length=1)
    record_and_family_counts_are_not_independent_evidence: Literal[True] = True
    missing_requirements_are_not_zero_measurements: Literal[True] = True
    claim_level_reasons_are_not_item_attribution: Literal[True] = True
    domain_score: None = None

    @field_validator("evidence_ids", "limitations")
    @classmethod
    def top_level_lists_are_unique_sorted(cls, value: list[str]) -> list[str]:
        if value != sorted(set(value)):
            raise ValueError("visualization data lists must be sorted and unique")
        return value

    @model_validator(mode="after")
    def records_are_stable_and_unique(self) -> Self:
        collections = (
            self.claim_records,
            self.family_relation_records,
            self.requirement_records,
            self.exclusion_records,
            self.requirements_exclusions_records,
        )
        for records in collections:
            ids = [item.record_id for item in records]
            if ids != sorted(ids) or len(ids) != len(set(ids)):
                raise ValueError("visualization records must have stable unique ordering")
        combined = sorted(
            [*self.requirement_records, *self.exclusion_records],
            key=lambda item: item.record_id,
        )
        if [
            item.model_dump(mode="json")
            for item in self.requirements_exclusions_records
        ] != [item.model_dump(mode="json") for item in combined]:
            raise ValueError("requirements/exclusions projection is not conserved")
        expected_evidence_ids = _record_evidence_ids(
            self.claim_records,
            self.family_relation_records,
            self.requirement_records,
            self.exclusion_records,
        )
        if self.evidence_ids != expected_evidence_ids:
            raise ValueError("top-level evidence IDs do not conserve output records")
        return self


class P009VisualizationArtifactSet(FrozenModel):
    object_version: Literal["0.1.0"] = "0.1.0"
    schema_ref: Literal[
        "bridge://schemas/p0-09-visualization-artifact-set/v0.1"
    ] = P009_VISUALIZATION_ARTIFACT_SET_SCHEMA_REF
    artifact_set_id: str
    data_profile_artifact_id: str
    data_profile_sha256: str = Field(pattern=_SHA256)
    visualizations: list[VisualizationArtifactV2]

    @model_validator(mode="after")
    def exact_component_set_is_present(self) -> Self:
        refs = [item.component_ref for item in self.visualizations]
        if refs != list(_COMPONENT_REFS):
            raise ValueError("P0-09 visualization component set is incomplete or reordered")
        hashes = {item.data_binding.sha256 for item in self.visualizations}
        if hashes != {self.data_profile_sha256}:
            raise ValueError("P0-09 visualizations must bind the exact typed data object")
        if any(
            item.data_binding.artifact_id != self.data_profile_artifact_id
            for item in self.visualizations
        ):
            raise ValueError("P0-09 data artifact binding mismatch")
        return self


def _record_evidence_ids(*record_groups) -> list[str]:
    return sorted(
        {
            evidence_id
            for records in record_groups
            for record in records
            for evidence_id in record.evidence_ids
        }
    )


def build_evidence_compiler_visualization_data(
    *,
    compiled: CompiledEvidenceGraph,
    claim_registry: ClaimRegistry,
    family_registry: EvidenceFamilyRegistry,
    run_id: str,
    tool_version: str,
) -> EvidenceCompilerVisualizationDataV1:
    claims = {item.ref: item for item in claim_registry.claims}
    families = {(item.evidence_family_id, item.version): item for item in family_registry.families}
    reconciliations = sorted(
        compiled.reconciliation_set.records, key=lambda item: item.claim_ref.ref
    )
    claim_records = sorted(
        [
            _claim_record(item, claims.get(item.claim_ref.ref))
            for item in reconciliations
        ],
        key=lambda item: item.record_id,
    )
    family_records = _family_records(compiled, reconciliations, claims, families)
    requirement_records = _requirement_records(compiled, claims)
    exclusion_records = _exclusion_records(compiled, reconciliations)
    evidence_ids = _record_evidence_ids(
        claim_records,
        family_records,
        requirement_records,
        exclusion_records,
    )
    return EvidenceCompilerVisualizationDataV1(
        visualization_data_id=f"evidence-compiler-visualization:{compiled.input_hash[:16]}",
        producer_tool_version=tool_version,
        producer_run_ref=f"run:{run_id}",
        graph_id=compiled.graph_id,
        graph_version=compiled.graph_version,
        source_input_sha256=compiled.input_hash,
        claim_records=claim_records,
        family_relation_records=family_records,
        requirement_records=requirement_records,
        exclusion_records=exclusion_records,
        requirements_exclusions_records=sorted(
            [*requirement_records, *exclusion_records],
            key=lambda item: item.record_id,
        ),
        evidence_ids=evidence_ids,
        limitations=sorted(
            {
                "claim_interpretations_are_scoped_to_registered_claims_and_current_reconciliation_rules",
                "registry_claims_without_evidence_or_explicit_requirements_do_not_produce_rows_and_are_not_zero_or_missing",
                "evidence_family_components_are_dependency_aware_candidates_not_votes",
                "missing_requirements_are_not_zero_measurements",
                "record_and_family_counts_are_audit_counts_not_independent_evidence",
                "reconciliation_reason_codes_are_claim_level_not_per_evidence_attribution",
                "no_cross_claim_score_rank_release_or_product_decision_is_produced",
            }
        ),
        domain_score=None,
    )


def _claim_record(reconciliation, claim) -> ClaimInterpretationRecord:
    eligibility = reconciliation.eligibility
    state = reconciliation.state
    if eligibility is ReconciliationEligibility.INSUFFICIENT_EVIDENCE:
        evidence_state = EvidenceState.MISSING
        missingness = "missing"
        applicability = "partially_applicable"
    elif eligibility is ReconciliationEligibility.NOT_ASSESSED:
        evidence_state = EvidenceState.UNAVAILABLE
        missingness = "not_assessed"
        applicability = "not_assessed"
    elif state is ReconciliationState.UNSTABLE:
        evidence_state = EvidenceState.ALERT
        missingness = "conflict"
        applicability = "partially_applicable"
    else:
        evidence_state = EvidenceState.INFERRED
        missingness = "none"
        applicability = "applicable"
    evidence_ids = sorted(
        {
            reconciliation.reconciliation_id,
            *(_unversioned(item) for item in reconciliation.included_evidence_refs),
            *(_unversioned(item) for item in reconciliation.excluded_evidence_refs),
            *(_unversioned(item) for item in reconciliation.open_requirement_refs),
        }
    )
    return ClaimInterpretationRecord(
        record_id=f"claim-interpretation:{hashlib.sha256(reconciliation.claim_ref.ref.encode()).hexdigest()[:16]}",
        evidence_ids=evidence_ids,
        evidence_state=evidence_state,
        missingness=missingness,
        applicability=applicability,
        reason_codes=sorted(set(reconciliation.reason_codes)),
        claim_ref=reconciliation.claim_ref.ref,
        claim_type=claim.claim_type if claim is not None else "unregistered_claim",
        domain_id=claim.domain_id.value if claim is not None else "unregistered",
        eligibility=eligibility.value,
        reconciliation_state=state.value if state is not None else None,
        direction=(
            reconciliation.direction.value
            if reconciliation.direction is not None
            else None
        ),
        included_record_count=len(reconciliation.included_evidence_refs),
        excluded_record_count=len(reconciliation.excluded_evidence_refs),
        open_requirement_count=len(reconciliation.open_requirement_refs),
        eligible_channel_count=sum(
            item.eligible for item in reconciliation.channel_resolutions
        ),
        total_channel_count=len(reconciliation.channel_resolutions),
    )


def _family_records(compiled, reconciliations, claims, families):
    included_by_claim = {
        item.claim_ref.ref: set(item.included_evidence_refs) for item in reconciliations
    }
    excluded_by_claim = {
        item.claim_ref.ref: set(item.excluded_evidence_refs) for item in reconciliations
    }
    entries = []
    for record in compiled.record_set.records:
        claim_ref = record.claim_ref.ref
        if record.ref not in included_by_claim.get(claim_ref, set()) | excluded_by_claim.get(
            claim_ref, set()
        ):
            continue
        entries.append(
            (
                claim_ref,
                record.evidence_family_ref.ref,
                record.ref,
                record.relation,
                record.evidence_state,
                record.applicability,
            )
        )
    for record in compiled.external_case_evidence_refs:
        claim_ref = record.comparison_claim_ref.ref
        if record.evidence_ref not in included_by_claim.get(
            claim_ref, set()
        ) | excluded_by_claim.get(claim_ref, set()):
            continue
        entries.append(
            (
                claim_ref,
                record.evidence_family_ref.ref,
                record.evidence_ref,
                record.relation,
                record.evidence_state,
                record.applicability,
            )
        )
    by_claim = defaultdict(list)
    for entry in entries:
        by_claim[entry[0]].append(entry)
    output = []
    for claim_ref in sorted(by_claim):
        claim_entries = by_claim[claim_ref]
        family_refs = {entry[1] for entry in claim_entries}
        components = _family_independence_components(family_refs, families)
        grouped = defaultdict(list)
        for entry in claim_entries:
            family = families.get(tuple(entry[1].rsplit("@", 1)))
            channel = family.channel_role if family is not None else "unregistered"
            grouped[(channel, components[entry[1]])].append(entry)
        for (channel, component), group in sorted(grouped.items()):
            relations = {entry[3] for entry in group}
            relation = (
                "conflict"
                if len(relations) > 1
                else next(iter(relations)).value
            )
            refs = {entry[2] for entry in group}
            included = refs & included_by_claim.get(claim_ref, set())
            excluded = refs & excluded_by_claim.get(claim_ref, set())
            participation = (
                "mixed" if included and excluded else "included" if included else "excluded"
            )
            states = {entry[4] for entry in group}
            applicability_values = {entry[5] for entry in group}
            if relation == "conflict" or EvidenceState.ALERT in states:
                evidence_state = EvidenceState.ALERT
                missingness = "conflict"
            elif EvidenceState.UNKNOWN in states:
                evidence_state = EvidenceState.UNKNOWN
                missingness = "not_assessed"
            elif EvidenceState.UNAVAILABLE in states:
                evidence_state = EvidenceState.UNAVAILABLE
                missingness = "not_assessed"
            else:
                evidence_state = EvidenceState.INFERRED
                missingness = "none"
            applicability = (
                "not_assessed"
                if applicability_values == {EvidenceApplicability.NOT_ASSESSED}
                else "not_applicable"
                if applicability_values == {EvidenceApplicability.NOT_APPLICABLE}
                else "applicable"
                if applicability_values == {EvidenceApplicability.APPLICABLE}
                else "partially_applicable"
            )
            family_list = sorted({entry[1] for entry in group})
            evidence_list = sorted(refs)
            output.append(
                EvidenceFamilyRelationRecord(
                    record_id=f"family-relation:{hashlib.sha256((claim_ref + '|' + channel + '|' + component).encode()).hexdigest()[:16]}",
                    evidence_ids=sorted({_unversioned(item) for item in evidence_list}),
                    evidence_state=evidence_state,
                    missingness=missingness,
                    applicability=applicability,
                    reason_codes=(
                        ["opposing_relations_within_dependency_component"]
                        if relation == "conflict"
                        else []
                    ),
                    claim_ref=claim_ref,
                    domain_id=(
                        claims[claim_ref].domain_id.value
                        if claim_ref in claims
                        else "unregistered"
                    ),
                    channel_role=channel,
                    component_id=component,
                    family_refs=family_list,
                    evidence_refs=evidence_list,
                    raw_record_count=len(evidence_list),
                    relation=relation,
                    participation=participation,
                )
            )
    return sorted(output, key=lambda item: item.record_id)


def _requirement_records(compiled, claims):
    grouped = defaultdict(list)
    for item in compiled.requirement_set.requirements:
        grouped[item.requirement_id].append(item)
    output = []
    for requirement_id in sorted(grouped):
        history = sorted(
            grouped[requirement_id], key=lambda item: item.requirement_version
        )
        item = history[-1]
        if item.state is EvidenceRequirementState.OPEN:
            evidence_state = EvidenceState.MISSING
            missingness = "missing"
            applicability = "partially_applicable"
        elif item.state is EvidenceRequirementState.NOT_APPLICABLE:
            evidence_state = EvidenceState.UNAVAILABLE
            missingness = "not_assessed"
            applicability = "not_applicable"
        else:
            evidence_state = EvidenceState.INFERRED
            missingness = "none"
            applicability = "applicable"
        output.append(
            EvidenceRequirementRecord(
                record_id=f"requirement-state:{hashlib.sha256(item.ref.encode()).hexdigest()[:16]}",
                evidence_ids=sorted(
                    {
                        item.requirement_id,
                        *(_unversioned(ref) for ref in item.satisfying_evidence_refs),
                    }
                ),
                evidence_state=evidence_state,
                missingness=missingness,
                applicability=applicability,
                reason_codes=sorted(set(item.reason_codes)),
                requirement_ref=item.ref,
                requirement_key=item.requirement_key,
                required_modality=item.required_modality,
                required_experiment=item.required_experiment,
                claim_ref=item.claim_ref.ref,
                domain_id=(
                    claims[item.claim_ref.ref].domain_id.value
                    if item.claim_ref.ref in claims
                    else "unregistered"
                ),
                channel_role=item.channel_role,
                requirement_state=item.state.value,
                satisfying_record_count=len(item.satisfying_evidence_refs),
                version_history_count=len(history),
            )
        )
    return sorted(output, key=lambda item: item.record_id)


def _exclusion_records(compiled, reconciliations):
    output = []
    for item in reconciliations:
        if not item.excluded_evidence_refs:
            continue
        output.append(
            CompilationExclusionRecord(
                record_id=f"reconciliation-exclusion:{hashlib.sha256(item.claim_ref.ref.encode()).hexdigest()[:16]}",
                evidence_ids=sorted(
                    {
                        item.reconciliation_id,
                        *(_unversioned(ref) for ref in item.excluded_evidence_refs),
                    }
                ),
                evidence_state=EvidenceState.UNKNOWN,
                missingness="not_assessed",
                applicability="partially_applicable",
                reason_codes=sorted(set(item.reason_codes)),
                exclusion_kind="reconciliation_exclusion",
                claim_ref=item.claim_ref.ref,
                excluded_record_count=len(item.excluded_evidence_refs),
                excluded_evidence_refs=sorted(item.excluded_evidence_refs),
                reason_attribution_scope="claim_level_not_per_evidence",
            )
        )
    for item in compiled.rejected_records.records:
        source_evidence_id = _unversioned(item.source_id)
        output.append(
            CompilationExclusionRecord(
                record_id=f"input-rejection:{item.source_kind}:{item.source_index:06d}",
                evidence_ids=sorted({compiled.graph_id, source_evidence_id}),
                evidence_state=EvidenceState.ALERT,
                missingness="conflict",
                applicability="not_assessed",
                reason_codes=sorted(set(item.reason_codes)),
                exclusion_kind="input_rejection",
                claim_ref=item.claim_ref,
                excluded_record_count=1,
                excluded_evidence_refs=[],
                source_kind=item.source_kind,
                source_id=item.source_id,
                reason_attribution_scope="exact_rejected_input",
            )
        )
    return sorted(output, key=lambda item: item.record_id)


def _unversioned(ref: str) -> str:
    return ref.rsplit("@", 1)[0]


PUBLIC_VISUALIZATION_SCHEMA_MODELS = {
    EVIDENCE_COMPILER_VISUALIZATION_DATA_SCHEMA_REF: (
        EvidenceCompilerVisualizationDataV1
    ),
    P009_VISUALIZATION_ARTIFACT_SET_SCHEMA_REF: P009VisualizationArtifactSet,
}
