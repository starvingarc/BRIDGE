from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import hashlib
import json
import re
from typing import Any, Iterable, Mapping

from pydantic import ValidationError

from bridge.tool_packages.p0_08_evidence_sufficiency.models import (
    EvidenceSufficiencyProfile,
    EvidenceSufficiencyState,
)
from bridge.tool_packages.p0_09_evidence_compiler.models import (
    CANONICALIZATION_ID,
    COMPILER_VERSION,
    EVIDENCE_REF_PATTERN,
    ClaimRegistry,
    ClaimSpec,
    CompilationDisposition,
    CompiledEvidenceGraph,
    EvidenceApplicability,
    EvidenceCandidate,
    EvidenceCompilationBundle,
    EvidenceFamilyRegistry,
    EvidenceFamilySpec,
    EvidenceFamilyStatus,
    EvidenceLifecycleState,
    EvidenceRecord,
    EvidenceRecordDisposition,
    EvidenceRecordSet,
    EvidenceRequirement,
    EvidenceRequirementSet,
    EvidenceRequirementState,
    EvidenceTier,
    ExternalCaseEvidenceRef,
    GraphNodeType,
    GraphKind,
    MissingEvidenceObservation,
    ReconciliationRecord,
    ReconciliationSpec,
    ReconciliationSpecRegistry,
    RegistryStatus,
    RejectedEvidenceRecord,
    RejectedEvidenceRecordList,
    RevisionAction,
    VersionedObjectRef,
    publication_ref,
    publication_version,
    is_prohibited_conclusion_key,
    contains_unsafe_reference,
)
from bridge.toolkit.contracts import EvidenceState, FrozenModel, ToolPackageSpecV2, ToolRequestV2


INDIVIDUAL_REASON_CODES = (
    "individual_record_schema_invalid",
    "duplicate_candidate_id",
    "declared_object_ref_not_found",
    "claim_not_registered",
    "claim_version_mismatch",
    "claim_domain_mismatch",
    "relation_not_allowed_by_claim",
    "evidence_family_not_registered",
    "evidence_family_version_mismatch",
    "sufficiency_profile_not_bound",
    "sufficiency_profile_case_mismatch",
    "sufficiency_profile_domain_mismatch",
    "sufficiency_profile_measurement_spec_mismatch",
    "sufficiency_profile_measurement_result_mismatch",
    "sufficiency_profile_family_mismatch",
    "sufficiency_profile_version_binding_unavailable",
    "claim_context_mismatch",
    "failed_tool_run_not_compilable",
    "missing_state_requires_evidence_requirement",
    "nonfinite_numeric_value",
    "invalid_denominator",
    "formal_tier_requires_sufficient_profile",
    "formal_tier_requires_reviewed_family",
    "formal_tier_requires_frozen_claim",
    "formal_tier_requires_frozen_reconciliation_spec",
    "create_conflicts_with_existing_logical_key",
    "changed_logical_record_requires_revision_relation",
    "revision_predecessor_not_found",
    "revision_predecessor_not_latest",
    "revision_logical_key_mismatch",
    "duplicate_logical_key_conflict",
    "comparison_case_evidence_must_be_external_ref",
    "external_evidence_claim_mapping_invalid",
)
INDIVIDUAL_REASON_ORDER = {
    code: index for index, code in enumerate(INDIVIDUAL_REASON_CODES)
}


class CompilationInvariantError(ValueError):
    """A top-level/history invariant that must fail the whole run."""

    def __init__(self, reason_code: str, detail: str = "") -> None:
        super().__init__(detail or reason_code)
        self.reason_code = reason_code
        self.detail = detail


def canonical_json_bytes(payload: object, *, indent: int | None = None) -> bytes:
    separators = (",", ":") if indent is None else None
    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=separators,
            indent=indent,
        )
        + ("\n" if indent is not None else "")
    ).encode("utf-8")


def canonical_hash(payload: object) -> str:
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


SET_LIKE_FIELDS = {
    "artifact_refs",
    "case_graph_refs",
    "candidate_records",
    "claims",
    "deduplicated_evidence_family_ids",
    "evidence_refs",
    "external_case_evidence_refs",
    "families",
    "known_dependencies",
    "measurement_result_refs",
    "missing_observations",
    "object_catalog",
    "prior_evidence_records",
    "prior_refs",
    "prior_requirements",
    "provenance_refs",
    "reference_refs",
    "requirement_specs",
    "sensitivity_refs",
    "shared_algorithm_refs",
    "shared_reference_or_prior_refs",
    "shared_source_refs",
    "snapshot_refs",
    "specs",
    "validation_refs",
}
CONTENT_ADDRESSED_GRAPH_ROLES = {
    "base_graph_manifest",
    "base_evidence_record_set",
    "base_evidence_requirement_set",
    "source_case_graph_manifest",
    "source_case_evidence_record_set",
}


def normalize_identity_payload(value: Any, *, field_name: str | None = None) -> Any:
    """Normalize only fields whose contract declares set semantics.

    Reason catalogs, precedence arrays, timestamps, traces, and interpretive role order
    remain untouched. This is deliberately narrower than recursively sorting every list.
    """

    if isinstance(value, FrozenModel):
        value = value.model_dump(mode="json")
    if isinstance(value, dict):
        return {
            key: normalize_identity_payload(item, field_name=key)
            for key, item in value.items()
        }
    if isinstance(value, list):
        normalized = [normalize_identity_payload(item) for item in value]
        if field_name in SET_LIKE_FIELDS:
            return sorted(normalized, key=canonical_json_bytes)
        return normalized
    if isinstance(value, tuple):
        return [normalize_identity_payload(item) for item in value]
    return value


def canonical_input_hash(
    *,
    request: ToolRequestV2,
    spec: ToolPackageSpecV2,
    objects_by_input_id: Mapping[str, FrozenModel],
) -> str:
    refs, objects = semantic_input_projection(request, objects_by_input_id)
    return canonical_hash(
        {
            "tool_id": spec.tool_id,
            "tool_version": spec.version,
            "environment_spec_id": spec.environment_spec_id,
            "result_schema_ref": spec.result_schema_ref,
            "canonicalization_id": CANONICALIZATION_ID,
            "object_inputs": refs,
            "validated_objects": objects,
            "random_seed": request.random_seed,
        }
    )


REQUEST_BINDING_FIELDS = frozenset(
    {
        "manifest_input_id",
        "record_set_input_id",
        "requirement_set_input_id",
        "sufficiency_profile_input_id",
    }
)


def _replace_binding_ids(value: Any, semantic_tokens: Mapping[str, str]) -> Any:
    if isinstance(value, dict):
        return {
            key: (
                semantic_tokens.get(item, item)
                if key in REQUEST_BINDING_FIELDS and isinstance(item, str)
                else _replace_binding_ids(item, semantic_tokens)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_replace_binding_ids(item, semantic_tokens) for item in value]
    return value


def semantic_input_projection(
    request: ToolRequestV2,
    objects_by_input_id: Mapping[str, FrozenModel],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Project caller labels into content identities before hashing/publication."""

    provisional: dict[str, tuple[dict[str, Any], Any]] = {}
    for ref in request.object_inputs:
        normalized = normalize_identity_payload(objects_by_input_id[ref.input_id])
        identity = {
            "role": ref.role,
            "schema_ref": ref.schema_ref,
            "object_version": ref.object_version,
            "semantic_sha256": hashlib.sha256(canonical_json_bytes(normalized)).hexdigest(),
            "media_type": ref.media_type,
        }
        if ref.role in CONTENT_ADDRESSED_GRAPH_ROLES:
            identity["content_addressed_sha256"] = ref.sha256
        provisional[ref.input_id] = (identity, normalized)
    tokens = {
        input_id: "semantic-input:"
        + hashlib.sha256(canonical_json_bytes(identity)).hexdigest()[:24]
        for input_id, (identity, _) in provisional.items()
        if identity["role"] != "compilation_bundle"
    }
    finalized: list[tuple[dict[str, Any], Any]] = []
    for ref in request.object_inputs:
        identity, normalized = provisional[ref.input_id]
        if ref.role == "compilation_bundle":
            normalized = normalize_identity_payload(
                _replace_binding_ids(
                    objects_by_input_id[ref.input_id].model_dump(mode="json"), tokens
                )
            )
            identity = {
                **identity,
                "semantic_sha256": hashlib.sha256(
                    canonical_json_bytes(normalized)
                ).hexdigest(),
            }
        finalized.append((identity, normalized))
    finalized.sort(key=lambda item: canonical_json_bytes(item[0]))
    occurrence: dict[bytes, int] = defaultdict(int)
    refs: list[dict[str, Any]] = []
    objects: list[dict[str, Any]] = []
    for identity, normalized in finalized:
        key = canonical_json_bytes(identity)
        index = occurrence[key]
        occurrence[key] += 1
        refs.append({**identity, "occurrence": index})
        objects.append(
            {
                "semantic_input_ref": "semantic-input:"
                + hashlib.sha256(key).hexdigest()[:24],
                "occurrence": index,
                "payload": normalized,
            }
        )
    return refs, objects


def graph_identity(bundle: EvidenceCompilationBundle) -> str:
    if bundle.graph_kind is GraphKind.CASE:
        assert bundle.product_case_ref is not None
        return graph_identity_for_ref(GraphKind.CASE, bundle.product_case_ref)
    else:
        assert bundle.comparison_ref is not None
        return graph_identity_for_ref(GraphKind.COMPARISON, bundle.comparison_ref)


def graph_identity_for_ref(kind: GraphKind, root_ref: VersionedObjectRef) -> str:
    identity = f"{kind.value}|{root_ref.ref}"
    prefix = f"{kind.value}-evidence-graph"
    return f"{prefix}:{hashlib.sha256(identity.encode('utf-8')).hexdigest()[:24]}"


def evidence_logical_key(candidate: EvidenceCandidate) -> str:
    return canonical_json_bytes(
        {
            "product_case_ref": candidate.product_case_ref.model_dump(mode="json"),
            "sample_or_preparation_ref": candidate.sample_or_preparation_ref.model_dump(
                mode="json"
            ),
            "domain_id": candidate.domain_id.value,
            "metric_id": candidate.metric_id,
            "claim_ref": candidate.claim_ref.model_dump(mode="json"),
            "biological_context": candidate.biological_context.model_dump(mode="json"),
            "measurement_spec_ref": candidate.measurement_spec_ref.model_dump(mode="json"),
        }
    ).decode("utf-8")


def evidence_record_logical_key(record: EvidenceRecord) -> str:
    """Rebuild the immutable logical key from a compiled record's identity fields."""

    return canonical_json_bytes(
        {
            "product_case_ref": record.product_case_ref.model_dump(mode="json"),
            "sample_or_preparation_ref": record.sample_or_preparation_ref.model_dump(
                mode="json"
            ),
            "domain_id": record.domain_id.value,
            "metric_id": record.metric_id,
            "claim_ref": record.claim_ref.model_dump(mode="json"),
            "biological_context": record.biological_context.model_dump(mode="json"),
            "measurement_spec_ref": record.measurement_spec_ref.model_dump(mode="json"),
        }
    ).decode("utf-8")


def evidence_identity(logical_key: str) -> str:
    return f"evidence:{hashlib.sha256(logical_key.encode('utf-8')).hexdigest()[:24]}"


def evidence_content_payload(
    candidate: EvidenceCandidate,
    *,
    sufficiency_profile_ref: VersionedObjectRef,
    lifecycle_state: EvidenceLifecycleState,
) -> dict[str, Any]:
    return {
        "product_case_ref": candidate.product_case_ref.model_dump(mode="json"),
        "sample_or_preparation_ref": candidate.sample_or_preparation_ref.model_dump(mode="json"),
        "domain_id": candidate.domain_id.value,
        "measurement_result_ref": candidate.measurement_result_ref.model_dump(mode="json"),
        "measurement_spec_ref": candidate.measurement_spec_ref.model_dump(mode="json"),
        "score_contract_ref": (
            candidate.score_contract_ref.model_dump(mode="json")
            if candidate.score_contract_ref
            else None
        ),
        "metric_id": candidate.metric_id,
        "value": candidate.value,
        "unit": candidate.unit,
        "numerator": candidate.numerator,
        "denominator": candidate.denominator,
        "interval": candidate.interval.model_dump(mode="json") if candidate.interval else None,
        "claim_ref": candidate.claim_ref.model_dump(mode="json"),
        "biological_context": candidate.biological_context.model_dump(mode="json"),
        "relation": candidate.relation.value,
        "evidence_state": candidate.evidence_state.value,
        "evidence_tier": candidate.evidence_tier.value,
        "lifecycle_state": lifecycle_state.value,
        "applicability": candidate.applicability.value,
        "evidence_family_ref": candidate.evidence_family_ref.model_dump(mode="json"),
        "sufficiency_profile_ref": sufficiency_profile_ref.model_dump(mode="json"),
        "tool_run_ref": candidate.tool_run_ref.model_dump(mode="json"),
        "tool_run_execution_state": candidate.tool_run_execution_state,
        "reference_refs": [item.model_dump(mode="json") for item in candidate.reference_refs],
        "prior_refs": [item.model_dump(mode="json") for item in candidate.prior_refs],
        "artifact_refs": [item.model_dump(mode="json") for item in candidate.artifact_refs],
        "provenance_refs": candidate.provenance_refs,
    }


def evidence_record_content_hash(record: EvidenceRecord) -> str:
    payload = record.model_dump(mode="json", exclude={
        "evidence_id",
        "evidence_version",
        "logical_key",
        "content_hash",
        "created_at",
        "compiler_version",
        "revision_action",
        "predecessor_ref",
    })
    return canonical_hash(payload)


def requirement_identity(
    graph_id: str, claim_ref: VersionedObjectRef, requirement_key: str
) -> str:
    digest = hashlib.sha256(
        f"{graph_id}|{claim_ref.ref}|{requirement_key}".encode("utf-8")
    ).hexdigest()[:24]
    return f"requirement:{digest}"


def reconciliation_identity(
    graph_id: str,
    claim_ref: VersionedObjectRef,
    reconciliation_spec_ref: VersionedObjectRef,
) -> str:
    digest = hashlib.sha256(
        f"{graph_id}|{claim_ref.ref}|{reconciliation_spec_ref.ref}".encode("utf-8")
    ).hexdigest()[:24]
    return f"reconciliation:{digest}"


def requirement_content_hash(requirement: EvidenceRequirement) -> str:
    return canonical_hash(
        {
            "claim_ref": requirement.claim_ref.ref,
            "product_case_ref": requirement.product_case_ref.ref,
            "requirement_key": requirement.requirement_key,
            "source_contract_ref": requirement.source_contract_ref.ref,
            "channel_role": requirement.channel_role,
            "required_modality": requirement.required_modality,
            "required_experiment": requirement.required_experiment,
            "blocking_scope": requirement.blocking_scope,
            "state": requirement.state.value,
            "reason_codes": requirement.reason_codes,
            "satisfying_evidence_refs": requirement.satisfying_evidence_refs,
        }
    )


def reconciliation_record_content_hash(record: ReconciliationRecord) -> str:
    return canonical_hash(
        {
            "graph_id": record.graph_id,
            "graph_version": record.graph_version,
            "claim_ref": record.claim_ref.ref,
            "reconciliation_spec_ref": record.reconciliation_spec_ref.ref,
            "sufficiency_profile_refs": [
                item.ref for item in record.sufficiency_profile_refs
            ],
            "eligibility": record.eligibility.value,
            "state": record.state.value if record.state else None,
            "direction": record.direction.value if record.direction else None,
            "channel_resolutions": [
                item.model_dump(mode="json") for item in record.channel_resolutions
            ],
            "included_evidence_refs": record.included_evidence_refs,
            "excluded_evidence_refs": record.excluded_evidence_refs,
            "open_requirement_refs": record.open_requirement_refs,
            "reason_codes": record.reason_codes,
        }
    )


def logical_key_hash(logical_key: str) -> str:
    return hashlib.sha256(logical_key.encode("utf-8")).hexdigest()


EXPECTED_CATALOG_SCHEMAS: dict[GraphNodeType, str] = {
    GraphNodeType.PRODUCT_CASE: "bridge://schemas/product-case/v0.1",
    GraphNodeType.PRODUCT_DEFINITION_CARD: "bridge://schemas/product-definition-card/v0.1",
    GraphNodeType.SAMPLE: "bridge://schemas/sample/v0.1",
    GraphNodeType.PREPARATION: "bridge://schemas/preparation/v0.1",
    GraphNodeType.MEASUREMENT_SPEC: "bridge://schemas/measurement-spec/v0.1",
    GraphNodeType.SCORE_CONTRACT: "bridge://schemas/score-contract/v0.1",
    GraphNodeType.TOOL_RUN: "bridge://schemas/tool-run/v0.1",
    GraphNodeType.MEASUREMENT_RESULT: "bridge://schemas/measurement-result/v0.1",
    GraphNodeType.REFERENCE_SNAPSHOT: "bridge://schemas/reference-snapshot/v0.1",
    GraphNodeType.PRIOR_SNAPSHOT: "bridge://schemas/prior-snapshot/v0.1",
    GraphNodeType.ARTIFACT: "bridge://schemas/artifact/v0.1",
    GraphNodeType.COMPARISON_RECORD: "bridge://schemas/comparison-record/v0.1",
}


def _catalog_binding_matches(
    catalog: Mapping[tuple[str, str], Any],
    ref: VersionedObjectRef,
    allowed_types: set[GraphNodeType],
) -> bool:
    item = catalog.get((ref.object_id, ref.object_version))
    return bool(
        item is not None
        and item.node_type in allowed_types
        and item.schema_ref == EXPECTED_CATALOG_SCHEMAS.get(item.node_type)
    )


def _profile_matches_record(
    profile: EvidenceSufficiencyProfile, record: EvidenceRecord
) -> bool:
    return (
        profile.product_case_ref == record.product_case_ref.object_id
        and profile.domain_id is record.domain_id
        and profile.measurement_spec_ref == record.measurement_spec_ref.object_id
        and record.measurement_result_ref.object_id in profile.measurement_result_refs
        and record.evidence_family_ref.object_id
        in profile.deduplicated_evidence_family_ids
    )


def validate_prior_history(
    bundle: EvidenceCompilationBundle,
    *,
    profiles_by_input_id: Mapping[str, EvidenceSufficiencyProfile] | None = None,
    claims: Mapping[tuple[str, str], ClaimSpec] | None = None,
    families: Mapping[tuple[str, str], EvidenceFamilySpec] | None = None,
) -> None:
    graph_id = graph_identity(bundle)
    if bundle.base_graph_ref is not None and bundle.base_graph_ref.graph_id != graph_id:
        raise CompilationInvariantError("prior_history_invalid", "base graph ID mismatch")
    by_id: dict[str, list[EvidenceRecord]] = defaultdict(list)
    refs: set[str] = set()
    for record in bundle.prior_evidence_records:
        if record.ref in refs:
            raise CompilationInvariantError("prior_history_invalid", "duplicate evidence version")
        refs.add(record.ref)
        by_id[record.evidence_id].append(record)
        if bundle.graph_kind is not GraphKind.CASE or record.product_case_ref != bundle.product_case_ref:
            raise CompilationInvariantError(
                "prior_history_invalid", "evidence ProductCase mismatch"
            )
        if claims is not None and (
            record.claim_ref.object_id,
            record.claim_ref.object_version,
        ) not in claims:
            raise CompilationInvariantError(
                "prior_history_invalid", "evidence Claim mismatch"
            )
        if families is not None and (
            record.evidence_family_ref.object_id,
            record.evidence_family_ref.object_version,
        ) not in families:
            raise CompilationInvariantError(
                "prior_history_invalid", "evidence family mismatch"
            )
        if profiles_by_input_id is not None:
            matching_profiles = [
                profile
                for profile in profiles_by_input_id.values()
                if profile.profile_id == record.sufficiency_profile_ref.object_id
                and profile.profile_version == record.sufficiency_profile_ref.object_version
            ]
            if len(matching_profiles) != 1 or not _profile_matches_record(
                matching_profiles[0], record
            ):
                raise CompilationInvariantError(
                    "prior_history_invalid", "evidence profile binding mismatch"
                )
            if record.evidence_tier is EvidenceTier.FORMAL:
                raise CompilationInvariantError(
                    "prior_history_invalid",
                    "P0-08 v0.1 profile cannot prove formal object versions",
                )
        if record.evidence_id != f"evidence:{logical_key_hash(record.logical_key)[:24]}":
            raise CompilationInvariantError("prior_history_invalid", "evidence ID mismatch")
        if record.content_hash != evidence_record_content_hash(record):
            raise CompilationInvariantError("prior_history_invalid", "content hash mismatch")
    for records in by_id.values():
        records.sort(key=lambda item: item.evidence_version)
        if [item.evidence_version for item in records] != list(range(1, len(records) + 1)):
            raise CompilationInvariantError("prior_history_invalid", "evidence version gap")
        if len({item.logical_key for item in records}) != 1:
            raise CompilationInvariantError("prior_history_invalid", "cross-key evidence chain")
        for index, record in enumerate(records):
            if index == 0:
                if record.revision_action is not RevisionAction.CREATE:
                    raise CompilationInvariantError("prior_history_invalid", "first version is not create")
            else:
                expected = records[index - 1].ref
                if record.predecessor_ref != expected:
                    raise CompilationInvariantError("prior_history_invalid", "non-linear evidence chain")

    requirement_groups: dict[str, list[EvidenceRequirement]] = defaultdict(list)
    seen_requirements: set[str] = set()
    for requirement in bundle.prior_requirements:
        if requirement.ref in seen_requirements:
            raise CompilationInvariantError("prior_history_invalid", "duplicate requirement version")
        seen_requirements.add(requirement.ref)
        requirement_groups[requirement.requirement_id].append(requirement)
        if (
            bundle.graph_kind is not GraphKind.CASE
            or requirement.product_case_ref != bundle.product_case_ref
            or (
                claims is not None
                and (
                    requirement.claim_ref.object_id,
                    requirement.claim_ref.object_version,
                )
                not in claims
            )
        ):
            raise CompilationInvariantError(
                "prior_history_invalid", "requirement graph binding mismatch"
            )
        if requirement.requirement_id != requirement_identity(
            graph_id, requirement.claim_ref, requirement.requirement_key
        ):
            raise CompilationInvariantError(
                "prior_history_invalid", "requirement ID mismatch"
            )
        if requirement.content_hash != requirement_content_hash(requirement):
            raise CompilationInvariantError(
                "prior_history_invalid", "requirement content hash mismatch"
            )
    for requirements in requirement_groups.values():
        requirements.sort(key=lambda item: item.requirement_version)
        if [item.requirement_version for item in requirements] != list(
            range(1, len(requirements) + 1)
        ):
            raise CompilationInvariantError("prior_history_invalid", "requirement version gap")
        if requirements[0].supersedes_requirement_ref is not None:
            raise CompilationInvariantError(
                "prior_history_invalid", "first requirement version supersedes history"
            )
        for previous, current in zip(requirements, requirements[1:], strict=False):
            if current.supersedes_requirement_ref != previous.ref:
                raise CompilationInvariantError(
                    "prior_history_invalid", "non-linear requirement chain"
                )


def compile_evidence_graph(
    *,
    request: ToolRequestV2,
    spec: ToolPackageSpecV2,
    bundle: EvidenceCompilationBundle,
    profiles_by_input_id: Mapping[str, EvidenceSufficiencyProfile],
    family_registry: EvidenceFamilyRegistry,
    claim_registry: ClaimRegistry,
    reconciliation_registry: ReconciliationSpecRegistry,
    verified_graph_inputs: Any,
    objects_by_input_id: Mapping[str, FrozenModel],
) -> CompiledEvidenceGraph:
    claims = {(item.claim_id, item.version): item for item in claim_registry.claims}
    families = {
        (item.evidence_family_id, item.version): item for item in family_registry.families
    }
    validate_prior_history(
        bundle,
        profiles_by_input_id=profiles_by_input_id,
        claims=claims,
        families=families,
    )
    input_hash = canonical_input_hash(
        request=request,
        spec=spec,
        objects_by_input_id=objects_by_input_id,
    )
    digest = input_hash[:16]
    graph_id = graph_identity(bundle)
    catalog = {(item.object_id, item.object_version): item for item in bundle.object_catalog}
    specs = {
        (item.reconciliation_spec_id, item.version): item
        for item in reconciliation_registry.specs
    }

    comparison_bundle = bundle
    comparison_rejected: list[RejectedEvidenceRecord] = []
    if bundle.graph_kind is GraphKind.COMPARISON:
        accepted_external, comparison_rejected = _validate_comparison_bindings(
            bundle=bundle,
            profiles_by_input_id=profiles_by_input_id,
            claims=claims,
            families=families,
            source_record_sets=verified_graph_inputs.source_record_sets,
            source_effective_lifecycle=verified_graph_inputs.source_effective_lifecycle,
        )
        comparison_bundle = bundle.model_copy(
            update={"external_case_evidence_refs": accepted_external}
        )

    records, dispositions, rejected_candidates = _compile_candidates(
        bundle=comparison_bundle,
        profiles_by_input_id=profiles_by_input_id,
        family_registry=family_registry,
        claim_registry=claim_registry,
        reconciliation_registry=reconciliation_registry,
        catalog=catalog,
        claims=claims,
        families=families,
        specs=specs,
    )
    observations, rejected_observations = _validate_missing_observations(
        bundle=comparison_bundle,
        catalog=catalog,
        claims=claims,
    )
    requirements, _requirements_changed = _compile_requirements(
        graph_id=graph_id,
        bundle=comparison_bundle,
        records=records,
        observations=observations,
        claims=claims,
        families=families,
    )
    if bundle.base_graph_ref is None:
        graph_version = 1
    else:
        # A base-bound request is a new immutable compilation bundle even when
        # every candidate disposition is unchanged. Reusing the prior graph
        # version with new run-level manifests would create two contents for one
        # graph identity, so v0.1 always appends the next graph version.
        graph_version = bundle.base_graph_ref.graph_version + 1

    record_set = EvidenceRecordSet(
        record_set_id=f"evidence-record-set:{digest}",
        record_set_version="0.1.0",
        graph_id=graph_id,
        graph_version=graph_version,
        records=sorted(records, key=lambda item: (item.evidence_id, item.evidence_version)),
        dispositions=sorted(dispositions, key=lambda item: item.candidate_id),
    )
    requirement_set = EvidenceRequirementSet(
        requirement_set_id=f"evidence-requirement-set:{digest}",
        requirement_set_version="0.1.0",
        graph_id=graph_id,
        graph_version=graph_version,
        requirements=sorted(
            requirements, key=lambda item: (item.requirement_id, item.requirement_version)
        ),
    )
    from bridge.tool_packages.p0_09_evidence_compiler.reconciler import reconcile_graph

    reconciliation_set = reconcile_graph(
        digest=digest,
        graph_id=graph_id,
        graph_version=graph_version,
        bundle=comparison_bundle,
        records=record_set.records,
        requirements=requirement_set.requirements,
        profiles_by_input_id=profiles_by_input_id,
        family_registry=family_registry,
        claim_registry=claim_registry,
        reconciliation_registry=reconciliation_registry,
        created_at=_created_at(
            bundle,
            profiles_by_input_id.values(),
            family_registry,
            claim_registry,
            reconciliation_registry,
        ),
    )
    rejected = sorted(
        [*rejected_candidates, *rejected_observations, *comparison_rejected],
        key=lambda item: (item.source_kind, item.source_index, item.source_id),
    )
    rejected_list = RejectedEvidenceRecordList(
        rejected_list_id=f"rejected-evidence-records:{digest}",
        rejected_list_version="0.1.0",
        records=rejected,
    )

    from bridge.tool_packages.p0_09_evidence_compiler.graph import build_graph_rows

    nodes, edges = build_graph_rows(
        graph_id=graph_id,
        graph_version=graph_version,
        bundle=comparison_bundle,
        records=record_set.records,
        requirements=requirement_set.requirements,
        reconciliation_records=reconciliation_set.records,
        profiles_by_input_id=profiles_by_input_id,
        family_registry=family_registry,
        claim_registry=claim_registry,
        reconciliation_registry=reconciliation_registry,
    )
    return CompiledEvidenceGraph(
        graph_kind=comparison_bundle.graph_kind,
        graph_id=graph_id,
        graph_version=graph_version,
        input_hash=input_hash,
        created_at=_created_at(
            bundle,
            profiles_by_input_id.values(),
            family_registry,
            claim_registry,
            reconciliation_registry,
        ),
        record_set=record_set,
        requirement_set=requirement_set,
        reconciliation_set=reconciliation_set,
        rejected_records=rejected_list,
        external_case_evidence_refs=[
            item
            for item in comparison_bundle.external_case_evidence_refs
            if isinstance(item, ExternalCaseEvidenceRef)
        ],
        nodes=nodes,
        edges=edges,
    )


def _compile_candidates(
    *,
    bundle: EvidenceCompilationBundle,
    profiles_by_input_id: Mapping[str, EvidenceSufficiencyProfile],
    family_registry: EvidenceFamilyRegistry,
    claim_registry: ClaimRegistry,
    reconciliation_registry: ReconciliationSpecRegistry,
    catalog: Mapping[tuple[str, str], Any],
    claims: Mapping[tuple[str, str], ClaimSpec],
    families: Mapping[tuple[str, str], EvidenceFamilySpec],
    specs: Mapping[tuple[str, str], ReconciliationSpec],
) -> tuple[list[EvidenceRecord], list[EvidenceRecordDisposition], list[RejectedEvidenceRecord]]:
    if bundle.graph_kind is GraphKind.COMPARISON:
        return [], [], []
    history = list(bundle.prior_evidence_records)
    latest_by_key: dict[str, EvidenceRecord] = {}
    by_ref = {item.ref: item for item in history}
    for record in sorted(history, key=lambda item: item.evidence_version):
        latest_by_key[record.logical_key] = record
    dispositions: list[EvidenceRecordDisposition] = []
    rejected: list[RejectedEvidenceRecord] = []
    seen_candidate_ids: set[str] = set()
    seen_logical: dict[str, str] = {}

    for index, raw in enumerate(bundle.candidate_records):
        source_id = _source_id(raw, "candidate_id", index, "candidate")
        early_reasons = _raw_candidate_reasons(raw)
        try:
            candidate = EvidenceCandidate.model_validate(raw)
        except ValidationError:
            candidate = None
            if not early_reasons:
                early_reasons.append("individual_record_schema_invalid")
        if candidate is None:
            reasons = _ordered_individual_reasons(early_reasons)
            rejected.append(
                RejectedEvidenceRecord(
                    source_kind="candidate_record",
                    source_id=source_id,
                    source_index=index,
                    reason_codes=reasons,
                    claim_ref=_raw_ref(raw.get("claim_ref")) if isinstance(raw, dict) else None,
                )
            )
            dispositions.append(
                EvidenceRecordDisposition(
                    candidate_id=source_id,
                    disposition=CompilationDisposition.REJECTED,
                    reason_codes=reasons,
                )
            )
            continue

        reasons = list(early_reasons)
        if candidate.candidate_id in seen_candidate_ids:
            reasons.append("duplicate_candidate_id")
        seen_candidate_ids.add(candidate.candidate_id)
        logical_key = evidence_logical_key(candidate)
        logical_digest = logical_key_hash(logical_key)
        previous_candidate_id = seen_logical.get(logical_key)
        if previous_candidate_id is not None:
            reasons.append("duplicate_logical_key_conflict")
        else:
            seen_logical[logical_key] = candidate.candidate_id

        catalog_bindings = [
            (candidate.product_case_ref, {GraphNodeType.PRODUCT_CASE}),
            (
                candidate.sample_or_preparation_ref,
                {GraphNodeType.SAMPLE, GraphNodeType.PREPARATION},
            ),
            (candidate.measurement_result_ref, {GraphNodeType.MEASUREMENT_RESULT}),
            (candidate.measurement_spec_ref, {GraphNodeType.MEASUREMENT_SPEC}),
            (candidate.tool_run_ref, {GraphNodeType.TOOL_RUN}),
            *(
                (item, {GraphNodeType.REFERENCE_SNAPSHOT})
                for item in candidate.reference_refs
            ),
            *((item, {GraphNodeType.PRIOR_SNAPSHOT}) for item in candidate.prior_refs),
            *((item, {GraphNodeType.ARTIFACT}) for item in candidate.artifact_refs),
        ]
        if candidate.score_contract_ref is not None:
            catalog_bindings.append(
                (candidate.score_contract_ref, {GraphNodeType.SCORE_CONTRACT})
            )
        if any(
            not _catalog_binding_matches(catalog, item, allowed_types)
            for item, allowed_types in catalog_bindings
        ):
            reasons.append("declared_object_ref_not_found")
        if candidate.product_case_ref != bundle.product_case_ref:
            reasons.append("declared_object_ref_not_found")

        claim = claims.get((candidate.claim_ref.object_id, candidate.claim_ref.object_version))
        if claim is None:
            if any(item.claim_id == candidate.claim_ref.object_id for item in claims.values()):
                reasons.append("claim_version_mismatch")
            else:
                reasons.append("claim_not_registered")
        else:
            if claim.domain_id is not candidate.domain_id:
                reasons.append("claim_domain_mismatch")
            if candidate.relation not in claim.allowed_relations:
                reasons.append("relation_not_allowed_by_claim")
            candidate_context_ref = VersionedObjectRef(
                object_id=candidate.biological_context.context_id,
                object_version=candidate.biological_context.context_version,
            )
            if claim.biological_context_ref != candidate_context_ref:
                reasons.append("claim_context_mismatch")

        family = families.get(
            (candidate.evidence_family_ref.object_id, candidate.evidence_family_ref.object_version)
        )
        if family is None:
            if any(
                item.evidence_family_id == candidate.evidence_family_ref.object_id
                for item in families.values()
            ):
                reasons.append("evidence_family_version_mismatch")
            else:
                reasons.append("evidence_family_not_registered")

        profile = profiles_by_input_id.get(candidate.sufficiency_profile_input_id)
        if profile is None:
            reasons.append("sufficiency_profile_not_bound")
        else:
            if profile.product_case_ref != candidate.product_case_ref.object_id:
                reasons.append("sufficiency_profile_case_mismatch")
            if profile.domain_id is not candidate.domain_id:
                reasons.append("sufficiency_profile_domain_mismatch")
            if profile.measurement_spec_ref != candidate.measurement_spec_ref.object_id:
                reasons.append("sufficiency_profile_measurement_spec_mismatch")
            if (
                candidate.measurement_result_ref.object_id
                not in profile.measurement_result_refs
            ):
                reasons.append("sufficiency_profile_measurement_result_mismatch")
            if (
                candidate.evidence_family_ref.object_id
                not in profile.deduplicated_evidence_family_ids
            ):
                reasons.append("sufficiency_profile_family_mismatch")
        if candidate.tool_run_execution_state not in {"succeeded", "partial"}:
            reasons.append("failed_tool_run_not_compilable")

        spec_for_claim = (
            specs.get(
                (
                    claim.reconciliation_spec_ref.object_id,
                    claim.reconciliation_spec_ref.object_version,
                )
            )
            if claim is not None
            else None
        )
        if candidate.evidence_tier is EvidenceTier.FORMAL:
            if profile is not None:
                reasons.append("sufficiency_profile_version_binding_unavailable")
            if profile is None or (
                profile.evidence_sufficiency_state is not EvidenceSufficiencyState.SUFFICIENT
            ):
                reasons.append("formal_tier_requires_sufficient_profile")
            if (
                family is None
                or family.status is not EvidenceFamilyStatus.REVIEWED
                or family_registry.status is not RegistryStatus.FROZEN
            ):
                reasons.append("formal_tier_requires_reviewed_family")
            if (
                claim is None
                or claim.status is not RegistryStatus.FROZEN
                or claim_registry.status is not RegistryStatus.FROZEN
            ):
                reasons.append("formal_tier_requires_frozen_claim")
            if (
                spec_for_claim is None
                or spec_for_claim.status is not RegistryStatus.FROZEN
                or reconciliation_registry.status is not RegistryStatus.FROZEN
            ):
                reasons.append("formal_tier_requires_frozen_reconciliation_spec")

        lifecycle = (
            EvidenceLifecycleState.INVALIDATED
            if candidate.revision_action is RevisionAction.INVALIDATE
            else EvidenceLifecycleState.ACTIVE
        )
        profile_ref = (
            VersionedObjectRef(object_id=profile.profile_id, object_version=profile.profile_version)
            if profile is not None
            else VersionedObjectRef(object_id="unbound-profile", object_version="0")
        )
        content_hash = canonical_hash(
            evidence_content_payload(
                candidate,
                sufficiency_profile_ref=profile_ref,
                lifecycle_state=lifecycle,
            )
        )
        prior = latest_by_key.get(logical_key)
        disposition = CompilationDisposition.REJECTED
        version = 1
        if not reasons:
            if prior is None:
                if candidate.revision_action is not RevisionAction.CREATE:
                    reasons.append("revision_predecessor_not_found")
                else:
                    disposition = CompilationDisposition.CREATED
            elif prior.content_hash == content_hash:
                disposition = CompilationDisposition.UNCHANGED
                version = prior.evidence_version
            elif candidate.revision_action is RevisionAction.CREATE:
                reasons.extend(
                    [
                        "create_conflicts_with_existing_logical_key",
                        "changed_logical_record_requires_revision_relation",
                    ]
                )
            elif candidate.predecessor_ref not in by_ref:
                reasons.append("revision_predecessor_not_found")
            else:
                predecessor = by_ref[candidate.predecessor_ref]
                if predecessor.ref != prior.ref:
                    reasons.append("revision_predecessor_not_latest")
                if predecessor.logical_key != logical_key:
                    reasons.append("revision_logical_key_mismatch")
                if not reasons:
                    disposition = CompilationDisposition.APPENDED
                    version = prior.evidence_version + 1

        if reasons:
            ordered = _ordered_individual_reasons(reasons)
            rejected.append(
                RejectedEvidenceRecord(
                    source_kind="candidate_record",
                    source_id=candidate.candidate_id,
                    source_index=index,
                    reason_codes=ordered,
                    claim_ref=candidate.claim_ref.ref,
                    logical_key_digest=logical_digest,
                )
            )
            dispositions.append(
                EvidenceRecordDisposition(
                    candidate_id=candidate.candidate_id,
                    disposition=CompilationDisposition.REJECTED,
                    reason_codes=ordered,
                )
            )
            continue
        if disposition is CompilationDisposition.UNCHANGED:
            assert prior is not None
            dispositions.append(
                EvidenceRecordDisposition(
                    candidate_id=candidate.candidate_id,
                    disposition=disposition,
                    evidence_ref=prior.ref,
                    reason_codes=[],
                )
            )
            continue
        evidence_id = f"evidence:{logical_key_hash(logical_key)[:24]}"
        record = EvidenceRecord(
            evidence_id=evidence_id,
            evidence_version=version,
            logical_key=logical_key,
            content_hash=content_hash,
            product_case_ref=candidate.product_case_ref,
            sample_or_preparation_ref=candidate.sample_or_preparation_ref,
            domain_id=candidate.domain_id,
            measurement_result_ref=candidate.measurement_result_ref,
            measurement_spec_ref=candidate.measurement_spec_ref,
            score_contract_ref=candidate.score_contract_ref,
            metric_id=candidate.metric_id,
            value=candidate.value,
            unit=candidate.unit,
            numerator=candidate.numerator,
            denominator=candidate.denominator,
            interval=candidate.interval,
            claim_ref=candidate.claim_ref,
            biological_context=candidate.biological_context,
            relation=candidate.relation,
            evidence_state=candidate.evidence_state,
            evidence_tier=candidate.evidence_tier,
            lifecycle_state=lifecycle,
            applicability=candidate.applicability,
            evidence_family_ref=candidate.evidence_family_ref,
            sufficiency_profile_ref=profile_ref,
            tool_run_ref=candidate.tool_run_ref,
            tool_run_execution_state=candidate.tool_run_execution_state,
            reference_refs=candidate.reference_refs,
            prior_refs=candidate.prior_refs,
            artifact_refs=candidate.artifact_refs,
            provenance_refs=candidate.provenance_refs,
            revision_action=candidate.revision_action,
            predecessor_ref=candidate.predecessor_ref,
            created_at=candidate.created_at,
            compiler_version=COMPILER_VERSION,
        )
        if record.content_hash != evidence_record_content_hash(record):
            raise CompilationInvariantError("graph_invariant_failed", "record hash mismatch")
        history.append(record)
        latest_by_key[logical_key] = record
        by_ref[record.ref] = record
        dispositions.append(
            EvidenceRecordDisposition(
                candidate_id=candidate.candidate_id,
                disposition=disposition,
                evidence_ref=record.ref,
                reason_codes=[],
            )
        )
    return history, dispositions, rejected


def _raw_candidate_reasons(raw: Any) -> list[str]:
    if not isinstance(raw, dict):
        return ["individual_record_schema_invalid"]
    reasons: list[str] = []
    if contains_unsafe_reference(raw):
        reasons.append("individual_record_schema_invalid")
    if _contains_prohibited_conclusion_key(raw):
        reasons.append("individual_record_schema_invalid")
    if raw.get("evidence_state") == EvidenceState.MISSING.value:
        reasons.append("missing_state_requires_evidence_requirement")
    if _contains_nonfinite(raw.get("value")):
        reasons.append("nonfinite_numeric_value")
    denominator = raw.get("denominator")
    if isinstance(denominator, bool) or (
        isinstance(denominator, (int, float)) and denominator <= 0
    ):
        reasons.append("invalid_denominator")
    return reasons


def _contains_prohibited_conclusion_key(value: Any) -> bool:
    if isinstance(value, dict):
        return any(is_prohibited_conclusion_key(key) for key in value) or any(
            _contains_prohibited_conclusion_key(item) for item in value.values()
        )
    if isinstance(value, list):
        return any(_contains_prohibited_conclusion_key(item) for item in value)
    return False


def _contains_nonfinite(value: Any) -> bool:
    if isinstance(value, float):
        return not (float("-inf") < value < float("inf"))
    if isinstance(value, list):
        return any(_contains_nonfinite(item) for item in value)
    if isinstance(value, dict):
        return any(_contains_nonfinite(item) for item in value.values())
    return False


def _validate_missing_observations(
    *,
    bundle: EvidenceCompilationBundle,
    catalog: Mapping[tuple[str, str], Any],
    claims: Mapping[tuple[str, str], ClaimSpec],
) -> tuple[list[MissingEvidenceObservation], list[RejectedEvidenceRecord]]:
    if bundle.graph_kind is GraphKind.COMPARISON:
        return [], []
    accepted: list[MissingEvidenceObservation] = []
    rejected: list[RejectedEvidenceRecord] = []
    seen: set[str] = set()
    for index, raw in enumerate(bundle.missing_observations):
        source_id = _source_id(raw, "observation_id", index, "missing")
        reasons: list[str] = []
        if contains_unsafe_reference(raw):
            reasons.append("individual_record_schema_invalid")
        try:
            observation = MissingEvidenceObservation.model_validate(raw)
        except ValidationError:
            observation = None
            reasons.append("individual_record_schema_invalid")
        if observation is not None:
            if observation.observation_id in seen:
                reasons.append("duplicate_candidate_id")
            seen.add(observation.observation_id)
            claim = claims.get((observation.claim_ref.object_id, observation.claim_ref.object_version))
            if claim is None:
                reasons.append("claim_not_registered")
            elif observation.requirement_key not in {
                item.requirement_key for item in claim.requirement_specs
            }:
                reasons.append("declared_object_ref_not_found")
            if observation.product_case_ref != bundle.product_case_ref:
                reasons.append("declared_object_ref_not_found")
            if (
                observation.source_contract_ref.object_id,
                observation.source_contract_ref.object_version,
            ) not in catalog and observation.source_contract_ref != observation.claim_ref:
                reasons.append("declared_object_ref_not_found")
        if reasons:
            rejected.append(
                RejectedEvidenceRecord(
                    source_kind="missing_observation",
                    source_id=source_id,
                    source_index=index,
                    reason_codes=_ordered_individual_reasons(reasons),
                    claim_ref=(observation.claim_ref.ref if observation else _raw_ref(raw.get("claim_ref"))),
                )
            )
        else:
            assert observation is not None
            accepted.append(observation)
    return accepted, rejected


def _compile_requirements(
    *,
    graph_id: str,
    bundle: EvidenceCompilationBundle,
    records: list[EvidenceRecord],
    observations: list[MissingEvidenceObservation],
    claims: Mapping[tuple[str, str], ClaimSpec],
    families: Mapping[tuple[str, str], EvidenceFamilySpec],
) -> tuple[list[EvidenceRequirement], bool]:
    if bundle.graph_kind is GraphKind.COMPARISON:
        return [], False
    assert bundle.product_case_ref is not None
    history = list(bundle.prior_requirements)
    latest: dict[str, EvidenceRequirement] = {}
    for item in sorted(history, key=lambda item: item.requirement_version):
        latest[item.requirement_id] = item

    relevant_claim_refs = {
        record.claim_ref.ref for record in records
    } | {observation.claim_ref.ref for observation in observations}
    observation_map = {
        (item.claim_ref.ref, item.requirement_key): item for item in observations
    }
    effective = effective_records(records)
    changed = False
    for claim_ref in sorted(relevant_claim_refs):
        claim_id, version = claim_ref.rsplit("@", 1)
        claim = claims.get((claim_id, version))
        if claim is None:
            continue
        for requirement_spec in claim.requirement_specs:
            explicit = observation_map.get((claim.ref, requirement_spec.requirement_key))
            qualifying = sorted(
                record.ref
                for record in effective
                if record.claim_ref.ref == claim.ref
                and record.lifecycle_state is EvidenceLifecycleState.ACTIVE
                and record.evidence_tier is EvidenceTier.FORMAL
                and record.applicability is EvidenceApplicability.APPLICABLE
                and (
                    family := families.get(
                        (
                            record.evidence_family_ref.object_id,
                            record.evidence_family_ref.object_version,
                        )
                    )
                )
                is not None
                and family.channel_role == requirement_spec.channel_role
                and family.status is EvidenceFamilyStatus.REVIEWED
            )
            if not requirement_spec.required and explicit is None:
                continue
            claim_object_ref = VersionedObjectRef(
                object_id=claim.claim_id, object_version=claim.version
            )
            requirement_id = requirement_identity(
                graph_id, claim_object_ref, requirement_spec.requirement_key
            )
            prior = latest.get(requirement_id)
            desired_state = (
                EvidenceRequirementState.SATISFIED
                if qualifying
                else EvidenceRequirementState.OPEN
            )
            reason_codes = (
                ["qualifying_evidence_available"]
                if qualifying
                else [explicit.reason_code if explicit else "required_evidence_missing"]
            )
            source_contract_ref = (
                explicit.source_contract_ref
                if explicit is not None
                else claim_object_ref
            )
            created_at = explicit.observed_at if explicit is not None else bundle.created_at
            content_payload = {
                "claim_ref": claim.ref,
                "product_case_ref": bundle.product_case_ref.ref,
                "requirement_key": requirement_spec.requirement_key,
                "source_contract_ref": source_contract_ref.ref,
                "channel_role": requirement_spec.channel_role,
                "required_modality": requirement_spec.required_modality,
                "required_experiment": requirement_spec.required_experiment,
                "blocking_scope": requirement_spec.blocking_scope,
                "state": desired_state.value,
                "reason_codes": reason_codes,
                "satisfying_evidence_refs": qualifying,
            }
            desired_content_hash = canonical_hash(content_payload)
            if prior is not None:
                if prior.content_hash == desired_content_hash:
                    continue
                requirement_version = prior.requirement_version + 1
                supersedes = prior.ref
            else:
                requirement_version = 1
                supersedes = None
            requirement = EvidenceRequirement(
                requirement_id=requirement_id,
                requirement_version=requirement_version,
                claim_ref=claim_object_ref,
                product_case_ref=bundle.product_case_ref,
                requirement_key=requirement_spec.requirement_key,
                source_contract_ref=source_contract_ref,
                channel_role=requirement_spec.channel_role,
                required_modality=requirement_spec.required_modality,
                required_experiment=requirement_spec.required_experiment,
                blocking_scope=requirement_spec.blocking_scope,
                state=desired_state,
                reason_codes=reason_codes,
                satisfying_evidence_refs=qualifying,
                supersedes_requirement_ref=supersedes,
                created_at=created_at,
                content_hash=desired_content_hash,
            )
            history.append(requirement)
            if requirement.content_hash != requirement_content_hash(requirement):
                raise CompilationInvariantError(
                    "graph_invariant_failed", "requirement hash mismatch"
                )
            latest[requirement_id] = requirement
            changed = True
    return history, changed


def effective_records(records: Iterable[EvidenceRecord]) -> list[EvidenceRecord]:
    by_id: dict[str, list[EvidenceRecord]] = defaultdict(list)
    for record in records:
        by_id[record.evidence_id].append(record)
    effective: list[EvidenceRecord] = []
    for versions in by_id.values():
        latest = max(versions, key=lambda item: item.evidence_version)
        if latest.lifecycle_state is EvidenceLifecycleState.ACTIVE:
            effective.append(latest)
    return sorted(effective, key=lambda item: (item.evidence_id, item.evidence_version))


def _validate_comparison_bindings(
    *,
    bundle: EvidenceCompilationBundle,
    profiles_by_input_id: Mapping[str, EvidenceSufficiencyProfile],
    claims: Mapping[tuple[str, str], ClaimSpec],
    families: Mapping[tuple[str, str], EvidenceFamilySpec],
    source_record_sets: Mapping[str, EvidenceRecordSet],
    source_effective_lifecycle: Mapping[
        str, Mapping[str, EvidenceLifecycleState]
    ],
) -> tuple[list[ExternalCaseEvidenceRef], list[RejectedEvidenceRecord]]:
    graph_refs = {item.graph_id: item for item in bundle.case_graph_refs}
    bound_inputs: set[str] = set()
    declared_inputs: set[str] = set()
    accepted: list[ExternalCaseEvidenceRef] = []
    rejected: list[RejectedEvidenceRecord] = []
    evidence_declarations: dict[str, set[str]] = defaultdict(set)
    for item in bundle.external_case_evidence_refs:
        raw = item.model_dump(mode="json") if isinstance(item, ExternalCaseEvidenceRef) else item
        try:
            modeled = ExternalCaseEvidenceRef.model_validate(raw)
        except (ValidationError, ValueError):
            continue
        evidence_declarations[modeled.evidence_ref].add(canonical_hash(modeled.model_dump(mode="json")))
    for index, raw_external in enumerate(bundle.external_case_evidence_refs):
        raw = (
            raw_external.model_dump(mode="json")
            if isinstance(raw_external, ExternalCaseEvidenceRef)
            else raw_external
        )
        if isinstance(raw, dict):
            profile_input_id = raw.get("sufficiency_profile_input_id")
            if (
                isinstance(profile_input_id, str)
                and profile_input_id
                and not contains_unsafe_reference(profile_input_id)
            ):
                declared_inputs.add(profile_input_id)
        reasons: list[str] = []
        if contains_unsafe_reference(raw):
            reasons.append("individual_record_schema_invalid")
        try:
            external = ExternalCaseEvidenceRef.model_validate(raw)
        except (ValidationError, ValueError):
            external = None
            reasons.append("individual_record_schema_invalid")
        if external is None:
            ordered = _ordered_individual_reasons(reasons)
            rejected.append(
                RejectedEvidenceRecord(
                    source_kind="external_case_evidence_ref",
                    source_id=_source_id(raw, "evidence_ref", index, "external"),
                    source_index=index,
                    reason_codes=ordered,
                    claim_ref=(
                        _raw_ref(raw.get("comparison_claim_ref"))
                        if isinstance(raw, dict)
                        else None
                    ),
                    logical_key_digest=(
                        canonical_hash(_safe_external_identity(raw))
                        if isinstance(raw, dict)
                        else None
                    ),
                )
            )
            continue
        case_graph = graph_refs.get(external.source_case_graph_ref.graph_id)
        if case_graph is None or (
            case_graph.graph_id != external.source_case_graph_ref.graph_id
            or case_graph.graph_version != external.source_case_graph_ref.graph_version
            or case_graph.manifest_sha256
            != external.source_case_graph_ref.manifest_sha256
            or case_graph.product_case_ref
            != external.source_case_graph_ref.product_case_ref
        ):
            reasons.append("declared_object_ref_not_found")
        elif case_graph.product_case_ref != external.product_case_ref:
            reasons.append("external_evidence_claim_mapping_invalid")
        source_set = source_record_sets.get(external.source_case_graph_ref.graph_id)
        source_record = next(
            (
                record
                for record in (source_set.records if source_set is not None else [])
                if record.ref == external.evidence_ref
            ),
            None,
        )
        effective_state = source_effective_lifecycle.get(
            external.source_case_graph_ref.graph_id, {}
        ).get(external.evidence_ref)
        if (
            source_record is None
            or source_record.content_hash != external.evidence_content_hash
            or source_record.product_case_ref != external.product_case_ref
            or source_record.claim_ref != external.source_claim_ref
            or source_record.evidence_family_ref != external.evidence_family_ref
            or source_record.relation is not external.relation
            or source_record.evidence_state is not external.evidence_state
            or source_record.evidence_tier is not external.evidence_tier
            or effective_state is not external.lifecycle_state
            or source_record.applicability is not external.applicability
            or source_record.tool_run_execution_state
            != external.tool_run_execution_state
        ):
            reasons.append("external_evidence_claim_mapping_invalid")
        if len(evidence_declarations[external.evidence_ref]) > 1:
            reasons.append("duplicate_logical_key_conflict")
        source_claim = claims.get(
            (external.source_claim_ref.object_id, external.source_claim_ref.object_version)
        )
        comparison_claim = claims.get(
            (external.comparison_claim_ref.object_id, external.comparison_claim_ref.object_version)
        )
        family = families.get(
            (external.evidence_family_ref.object_id, external.evidence_family_ref.object_version)
        )
        profile = profiles_by_input_id.get(external.sufficiency_profile_input_id)
        if source_claim is None or comparison_claim is None or family is None:
            reasons.append("declared_object_ref_not_found")
        elif (
            source_claim.domain_id is not comparison_claim.domain_id
            or external.relation not in comparison_claim.allowed_relations
        ):
            reasons.append("external_evidence_claim_mapping_invalid")
        if profile is None:
            reasons.append("sufficiency_profile_not_bound")
        elif (
            comparison_claim is not None
            and (
                profile.product_case_ref != external.product_case_ref.object_id
                or profile.domain_id is not comparison_claim.domain_id
            )
        ):
            reasons.append("external_evidence_claim_mapping_invalid")
        elif source_record is not None and (
            source_record.measurement_result_ref.object_id
            not in profile.measurement_result_refs
            or source_record.evidence_family_ref.object_id
            not in profile.deduplicated_evidence_family_ids
            or profile.measurement_spec_ref
            != source_record.measurement_spec_ref.object_id
        ):
            reasons.append("external_evidence_claim_mapping_invalid")
        if external.evidence_tier is EvidenceTier.FORMAL and profile is not None:
            reasons.append("sufficiency_profile_version_binding_unavailable")
        if reasons:
            rejected.append(
                RejectedEvidenceRecord(
                    source_kind="external_case_evidence_ref",
                    source_id=_source_id(raw, "evidence_ref", index, "external"),
                    source_index=index,
                    reason_codes=_ordered_individual_reasons(reasons),
                    claim_ref=external.comparison_claim_ref.ref,
                    logical_key_digest=canonical_hash(
                        {
                            "source_graph": external.source_case_graph_ref.graph_id,
                            "evidence_ref": external.evidence_ref,
                            "comparison_claim_ref": external.comparison_claim_ref.ref,
                        }
                    ),
                )
            )
            continue
        accepted.append(external)
        bound_inputs.add(external.sufficiency_profile_input_id)
    if set(profiles_by_input_id) != bound_inputs:
        # Completely unbound profiles remain a top-level ambiguity. A profile bound
        # only by a rejected external item is retained as rejection provenance.
        if not set(profiles_by_input_id).issubset(declared_inputs):
            raise CompilationInvariantError("unbound_sufficiency_profile")
    return accepted, rejected


def _safe_external_identity(raw: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    evidence_ref = raw.get("evidence_ref")
    if (
        isinstance(evidence_ref, str)
        and not contains_unsafe_reference(evidence_ref)
        and len(evidence_ref) <= 256
    ):
        result["evidence_ref"] = evidence_ref
    for name in ("source_case_graph_ref", "comparison_claim_ref"):
        ref = _raw_ref(raw.get(name))
        if ref is not None:
            result[name] = ref
    return result


def _created_at(
    bundle: EvidenceCompilationBundle,
    profiles: Iterable[EvidenceSufficiencyProfile],
    family_registry: EvidenceFamilyRegistry,
    claim_registry: ClaimRegistry,
    reconciliation_registry: ReconciliationSpecRegistry,
) -> datetime:
    return max(
        [
            bundle.created_at,
            family_registry.created_at,
            claim_registry.created_at,
            reconciliation_registry.created_at,
            *(profile.created_at for profile in profiles),
        ]
    )


def _ordered_individual_reasons(reasons: Iterable[str]) -> list[str]:
    unique = set(reasons)
    return sorted(
        unique,
        key=lambda item: (
            INDIVIDUAL_REASON_ORDER.get(item, len(INDIVIDUAL_REASON_ORDER)),
            item,
        ),
    )


def _source_id(raw: Any, field: str, index: int, prefix: str) -> str:
    if (
        isinstance(raw, dict)
        and isinstance(raw.get(field), str)
        and raw[field]
        and not contains_unsafe_reference(raw[field])
        and len(raw[field]) <= 256
    ):
        if re.fullmatch(EVIDENCE_REF_PATTERN, raw[field]):
            return raw[field]
        try:
            return publication_ref(raw[field])
        except ValueError:
            pass
    return f"{prefix}-index-{index}"


def _raw_ref(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    object_id = value.get("object_id")
    version = value.get("object_version")
    if (
        isinstance(object_id, str)
        and isinstance(version, str)
        and not contains_unsafe_reference(object_id)
        and not contains_unsafe_reference(version)
        and len(object_id) <= 256
        and len(version) <= 128
    ):
        try:
            return f"{publication_ref(object_id)}@{publication_version(version)}"
        except ValueError:
            return None
    return None
