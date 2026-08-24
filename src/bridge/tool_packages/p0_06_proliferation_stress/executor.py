from __future__ import annotations

from collections import defaultdict

from bridge.tool_packages._configurable_contracts import (
    BiologicalUnitLineageState,
    BiologicalUnitManifest,
    ProductCase,
    ProductDefinitionCard,
    VersionedObjectRef,
)
from bridge.tool_packages.p0_04_developmental.models import (
    DevelopmentalCompatibilityResult,
)
from bridge.tool_packages.p0_06_proliferation_stress.models import (
    DeferredAssessmentProfile,
    ProgramAssessmentSpec,
    ProgramEvidenceBundle,
    ProgramEvidenceState,
    ProgramObservation,
    ProgramObservationAssessment,
    ProgramReviewRule,
    ProgramRuleResult,
    ProliferationStressResponseProfile,
    ReferenceRelation,
    ReviewDirection,
    ReviewFlagState,
    TranscriptomicReviewFlag,
    UnmatchedProgramObservation,
)
from bridge.toolkit.contracts import QCReadinessProfile, ScoreState


def evaluate_proliferation_stress_response(
    *,
    run_id: str,
    tool_version: str,
    product_case: ProductCase,
    product_definition: ProductDefinitionCard,
    assessment_spec: ProgramAssessmentSpec,
    evidence_bundle: ProgramEvidenceBundle,
    developmental_result: DevelopmentalCompatibilityResult,
    qc_profile: QCReadinessProfile,
    biological_unit_manifest: BiologicalUnitManifest,
    qc_profile_version: str,
    input_sha256_by_role: dict[str, str],
) -> ProliferationStressResponseProfile:
    independence_group_by_analysis_unit = {
        item.analysis_unit_ref.ref: item.independence_group_ref
        for item in biological_unit_manifest.unit_bindings
    }
    rules = {rule.rule_id: rule for rule in assessment_spec.rules}
    matched: dict[str, list[ProgramObservation]] = defaultdict(list)
    unmatched: list[UnmatchedProgramObservation] = []
    for observation in evidence_bundle.observations:
        rule = rules.get(observation.rule_id)
        if rule is None:
            unmatched.append(
                UnmatchedProgramObservation(
                    observation_id=observation.observation_id,
                    rule_id=observation.rule_id,
                    reason_code="program_rule_not_configured",
                )
            )
        elif not _observation_matches_rule(observation, rule):
            unmatched.append(
                UnmatchedProgramObservation(
                    observation_id=observation.observation_id,
                    rule_id=observation.rule_id,
                    reason_code="program_rule_binding_mismatch",
                )
            )
        else:
            matched[rule.rule_id].append(observation)

    context_available = developmental_result.result_state != "not_assessed"
    program_results = [
        _evaluate_rule(
            rule,
            matched.get(rule.rule_id, []),
            assay=product_case.assay,
            context_available=context_available,
            independence_group_by_analysis_unit=(
                independence_group_by_analysis_unit
            ),
            biological_unit_lineage_state=(
                biological_unit_manifest.lineage_state
            ),
        )
        for rule in sorted(assessment_spec.rules, key=lambda item: item.rule_id)
    ]
    review_flags = [
        TranscriptomicReviewFlag(
            review_flag_state=result.review_flag_state,
            flag_status="shadow",
            rule_id=result.rule_id,
            program_ref=result.program_ref,
            evidence_refs=result.evidence_refs,
            orthogonal_follow_up_refs=sorted(
                rules[result.rule_id].orthogonal_follow_up_refs
            ),
            reason_codes=result.reason_codes,
        )
        for result in program_results
    ]

    assessed_count = sum(
        result.review_flag_state is not ReviewFlagState.NOT_ASSESSED
        for result in program_results
    )
    if assessed_count == 0:
        result_state = "not_assessed"
    elif (
        assessed_count != len(program_results)
        or unmatched
        or not biological_unit_manifest.independence_is_reviewed
    ):
        result_state = "partial"
    else:
        result_state = "complete"

    reasons = {
        "protocol_ir_not_supplied",
        "pluripotency_lod_not_supplied",
        "transcriptomic_cnv_not_supplied",
        *(reason for result in program_results for reason in result.reason_codes),
    }
    if unmatched:
        reasons.add("unmatched_program_observations")
    if not biological_unit_manifest.independence_is_reviewed:
        reasons.add("biological_unit_lineage_not_reviewed")
    evidence_refs = sorted(
        {
            *qc_profile.evidence_ids,
            *developmental_result.evidence_refs,
            *(
                evidence
                for result in program_results
                for evidence in result.evidence_refs
            ),
        }
    )
    developmental_ref = VersionedObjectRef(
        object_id=developmental_result.result_id,
        object_version=developmental_result.object_version,
    )
    return ProliferationStressResponseProfile(
        object_version="0.1.0",
        profile_id=f"proliferation-stress-profile:{run_id.removeprefix('run-')}",
        tool_id="P0-06",
        tool_version=tool_version,
        product_case_ref=product_case.ref,
        product_definition_ref=product_definition.ref,
        assessment_spec_ref=assessment_spec.ref,
        evidence_bundle_ref=evidence_bundle.ref,
        developmental_result_ref=developmental_ref,
        qc_profile_ref=VersionedObjectRef(
            object_id=qc_profile.profile_id,
            object_version=qc_profile_version,
        ),
        biological_unit_manifest_ref=biological_unit_manifest.ref,
        biological_unit_lineage_state=biological_unit_manifest.lineage_state,
        input_sha256_by_role=input_sha256_by_role,
        result_state=result_state,
        program_results=program_results,
        review_flags=review_flags,
        unmatched_observations=sorted(
            unmatched,
            key=lambda item: (item.rule_id, item.observation_id),
        ),
        process_attribution=DeferredAssessmentProfile(
            assessment_state="not_assessed",
            reason_code="protocol_ir_not_supplied",
        ),
        residual_pluripotency_lod=DeferredAssessmentProfile(
            assessment_state="not_assessed",
            reason_code="pluripotency_lod_not_supplied",
        ),
        transcriptomic_cnv=DeferredAssessmentProfile(
            assessment_state="not_assessed",
            reason_code="transcriptomic_cnv_not_supplied",
        ),
        evidence_refs=evidence_refs,
        reason_codes=sorted(reasons),
        domain_score=None,
        score_state=(
            ScoreState.UNAVAILABLE
            if result_state == "not_assessed"
            else ScoreState.SHADOW
        ),
    )


def _evaluate_rule(
    rule: ProgramReviewRule,
    observations: list[ProgramObservation],
    *,
    assay: str,
    context_available: bool,
    independence_group_by_analysis_unit: dict[str, VersionedObjectRef],
    biological_unit_lineage_state: BiologicalUnitLineageState,
) -> ProgramRuleResult:
    independence_is_reviewed = biological_unit_lineage_state in {
        BiologicalUnitLineageState.REVIEWED,
        BiologicalUnitLineageState.FROZEN,
    }
    assessments: list[ProgramObservationAssessment] = []
    for observation in sorted(observations, key=lambda item: item.observation_id):
        assessments.append(
            _assess_observation(
                rule,
                observation,
                assay=assay,
                context_available=context_available,
                independence_group_ref=(
                    independence_group_by_analysis_unit[
                        observation.analysis_unit_ref.ref
                    ]
                ),
            )
        )

    included = [item for item in assessments if item.included]
    analysis_units = {item.analysis_unit_ref.ref for item in included}
    groups = {item.independence_group_ref.ref for item in included}
    by_group: dict[str, list[ReferenceRelation]] = defaultdict(list)
    for item in included:
        assert item.reference_relation is not None
        by_group[item.independence_group_ref.ref].append(item.reference_relation)
    triggering_groups = {
        group
        for group, relations in by_group.items()
        if any(_triggers(rule.review_direction, relation) for relation in relations)
        and all(_triggers(rule.review_direction, relation) for relation in relations)
    }

    reasons = {
        item.exclusion_reason
        for item in assessments
        if item.exclusion_reason is not None
    }
    if not context_available:
        state = ReviewFlagState.NOT_ASSESSED
        reasons.add("developmental_context_not_assessed")
    elif assay not in rule.applicable_assays:
        state = ReviewFlagState.NOT_ASSESSED
        reasons.add("rule_not_applicable_to_assay")
    elif not included:
        state = ReviewFlagState.NOT_ASSESSED
        reasons.add("program_evidence_not_eligible")
    elif not independence_is_reviewed:
        state = ReviewFlagState.CANNOT_RESOLVE
        reasons.add("biological_unit_lineage_not_reviewed")
    elif len(groups) < rule.minimum_biological_units:
        state = ReviewFlagState.CANNOT_RESOLVE
        reasons.add("biological_unit_evidence_insufficient")
    elif len(triggering_groups) >= rule.minimum_biological_units:
        state = ReviewFlagState.TRANSCRIPTOMIC_REVIEW_FLAG
        reasons.add("configured_review_condition_met")
    else:
        state = ReviewFlagState.CANNOT_RESOLVE
        reasons.add("validated_lod_not_supplied")
        if any(
            any(_triggers(rule.review_direction, relation) for relation in relations)
            and not all(
                _triggers(rule.review_direction, relation) for relation in relations
            )
            for relations in by_group.values()
        ):
            reasons.add("within_group_evidence_conflict")

    return ProgramRuleResult(
        rule_id=rule.rule_id,
        program_ref=rule.program_ref,
        analysis_scope=rule.analysis_scope,
        state_ref=rule.state_ref,
        stage_context_ref=rule.stage_context_ref,
        metric_name=rule.metric_name,
        unit=rule.unit,
        reference_lower=rule.reference_lower,
        reference_upper=rule.reference_upper,
        observations=assessments,
        descriptive_analysis_unit_count=len(analysis_units),
        included_biological_unit_count=(
            len(groups) if independence_is_reviewed else 0
        ),
        triggering_biological_unit_count=(
            len(triggering_groups) if independence_is_reviewed else 0
        ),
        biological_unit_lineage_state=biological_unit_lineage_state,
        review_flag_state=state,
        evidence_refs=sorted(
            {evidence for item in included for evidence in item.evidence_refs}
        ),
        reason_codes=sorted(reasons),
    )


def _assess_observation(
    rule: ProgramReviewRule,
    observation: ProgramObservation,
    *,
    assay: str,
    context_available: bool,
    independence_group_ref: VersionedObjectRef,
) -> ProgramObservationAssessment:
    exclusion: str | None = None
    relation: ReferenceRelation | None = None
    if not context_available:
        exclusion = "developmental_context_not_assessed"
    elif assay not in rule.applicable_assays:
        exclusion = "rule_not_applicable_to_assay"
    elif observation.evidence_state not in rule.eligible_evidence_states:
        exclusion = "evidence_state_not_eligible"
    elif observation.value is None or observation.gene_coverage is None:
        exclusion = "evidence_value_unavailable"
    elif float(observation.gene_coverage) < float(rule.minimum_gene_coverage):
        exclusion = "gene_coverage_below_configured_minimum"
    else:
        relation = _relation(
            float(observation.value),
            float(rule.reference_lower),
            float(rule.reference_upper),
        )
    return ProgramObservationAssessment(
        observation_id=observation.observation_id,
        evidence_family_id=observation.evidence_family_id,
        analysis_unit_ref=observation.analysis_unit_ref,
        independence_group_ref=independence_group_ref,
        metric_name=observation.metric_name,
        unit=observation.unit,
        analysis_scope=observation.analysis_scope,
        state_ref=observation.state_ref,
        stage_context_ref=observation.stage_context_ref,
        method_ref=observation.method_ref,
        evidence_state=observation.evidence_state,
        value=observation.value,
        gene_coverage=observation.gene_coverage,
        reference_relation=relation,
        included=exclusion is None,
        exclusion_reason=exclusion,
        evidence_refs=sorted(observation.evidence_refs),
    )


def _observation_matches_rule(
    observation: ProgramObservation,
    rule: ProgramReviewRule,
) -> bool:
    return (
        observation.program_ref == rule.program_ref
        and observation.metric_name == rule.metric_name
        and observation.unit == rule.unit
        and observation.analysis_scope is rule.analysis_scope
        and observation.state_ref == rule.state_ref
        and observation.stage_context_ref == rule.stage_context_ref
    )


def _relation(value: float, lower: float, upper: float) -> ReferenceRelation:
    if value < lower:
        return ReferenceRelation.BELOW_REFERENCE
    if value > upper:
        return ReferenceRelation.ABOVE_REFERENCE
    return ReferenceRelation.WITHIN_REFERENCE


def _triggers(direction: ReviewDirection, relation: ReferenceRelation) -> bool:
    if direction is ReviewDirection.ABOVE_REFERENCE:
        return relation is ReferenceRelation.ABOVE_REFERENCE
    if direction is ReviewDirection.BELOW_REFERENCE:
        return relation is ReferenceRelation.BELOW_REFERENCE
    return relation is not ReferenceRelation.WITHIN_REFERENCE
