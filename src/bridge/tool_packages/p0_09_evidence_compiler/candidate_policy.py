"""Unreviewed missingness-only policy for the source-gated research Web flow."""
from __future__ import annotations

from datetime import datetime
import hashlib

from bridge.tool_packages._configurable_contracts import ProductCase, ProductDefinitionCard
from bridge.tool_packages._structured_runtime import canonical_json_bytes
from bridge.tool_packages.p0_08_evidence_sufficiency.models import EvidenceSufficiencyRunResultV2, P0DomainId
from bridge.toolkit.contracts import FrozenModel
from .models import (
    ClaimRegistry, EvidenceCompilationBundle, EvidenceFamilyRegistry,
    MissingEvidenceObservation, ReconciliationSpecRegistry,
)

POLICY_VERSION = "0.1.0"
POLICY_REF = "candidate-policy:web-missingness@" + POLICY_VERSION


def build_missingness_policy(
    case: ProductCase, definition: ProductDefinitionCard,
    result: EvidenceSufficiencyRunResultV2, *, created_at: datetime,
) -> dict[str, FrozenModel]:
    """Bind five absent domain measurements, without asserting biological findings.

    The Web caller validates the hPSC-mDA intent and exact canonical run receipt.
    This factory validates the modeled case/definition and only accepts unmeasured
    P0-08 results. Its candidate policy does not change any frozen release rule.
    """
    case_ref = case.ref.model_dump(mode="json")
    definition_ref = definition.ref.model_dump(mode="json")
    if (case.product_definition_ref != definition.ref
            or case.assay not in definition.supported_assays
            or result.case_summary.product_case_ref is None
            or result.case_summary.product_case_ref.model_dump(mode="json") != case_ref
            or {row.domain_id for row in result.profiles} != set(P0DomainId)
            or len(result.profiles) != 5):
        raise ValueError("candidate_policy_case_binding_mismatch")
    for profile in result.profiles:
        if (profile.product_definition_ref is None
                or profile.product_definition_ref.model_dump(mode="json") != definition_ref
                or profile.evidence_sufficiency_state.value != "not_assessed"
                or profile.measurement_result_refs or profile.domain_score is not None
                or profile.score_state.value != "unavailable"):
            raise ValueError("candidate_policy_requires_unmeasured_domains")
    identity = hashlib.sha256(canonical_json_bytes(case_ref)).hexdigest()[:24]
    provenance = [POLICY_REF, result.result_id + "@" + result.result_version]
    spec_ref = {"object_id": "reconciliation-spec:web-descriptive-domain", "object_version": POLICY_VERSION}
    claims, missing = [], []
    for domain in P0DomainId:
        claim_ref = {"object_id": "claim:web-" + identity + ":" + domain.value, "object_version": POLICY_VERSION}
        claims.append({
            "claim_id": claim_ref["object_id"], "version": POLICY_VERSION,
            "claim_type": "descriptive_domain_observation", "domain_id": domain.value,
            "claim_target_ref": case.product_case_id + "@" + case.case_version,
            "biological_context_ref": definition_ref, "allowed_relations": ["supports", "contradicts"],
            "reconciliation_spec_ref": spec_ref, "status": "candidate",
            "requirement_specs": [{"requirement_key": "canonical_measurement",
                "channel_role": "canonical_measurement", "required_modality": case.assay,
                "blocking_scope": "claim", "required": True}],
        })
        missing.append(MissingEvidenceObservation(
            observation_id="missing-evidence:web-" + identity + ":" + domain.value,
            product_case_ref=case_ref, claim_ref=claim_ref, requirement_key="canonical_measurement",
            reason_code="measurement_not_provided", source_contract_ref=claim_ref,
            provenance_refs=provenance, observed_at=created_at).model_dump(mode="json"))
    common = {"registry_version": POLICY_VERSION, "created_at": created_at, "status": "candidate"}
    catalog = [
        {**case_ref, "node_type": "ProductCase", "schema_ref": "bridge://schemas/product-case/v0.1",
         "content_hash": hashlib.sha256(canonical_json_bytes(case.model_dump(mode="json"))).hexdigest()},
        {**definition_ref, "node_type": "ProductDefinitionCard",
         "schema_ref": "bridge://schemas/product-definition-card/v0.1",
         "content_hash": hashlib.sha256(canonical_json_bytes(definition.model_dump(mode="json"))).hexdigest()},
    ]
    return {
        "compilation_bundle": EvidenceCompilationBundle(
            bundle_id="evidence-compilation-bundle:web-" + identity, bundle_version=POLICY_VERSION,
            graph_kind="case", product_case_ref=case_ref, object_catalog=catalog,
            missing_observations=missing, created_at=created_at, provenance_refs=provenance),
        "evidence_family_registry": EvidenceFamilyRegistry.model_validate({
            **common, "registry_id": "BRIDGE-EVIDENCE-FAMILY-REGISTRY-v0.1",
            "families": [{"evidence_family_id": "evidence-family:web-" + identity,
                "version": POLICY_VERSION, "family_type": "shared_data", "channel_role": "canonical_measurement",
                "shared_source_refs": [case.sample_or_preparation_ref.ref], "independence_scope": "not_attested",
                "known_dependencies": [], "rationale": "One uploaded source; no independent family is established.",
                "status": "unreviewed"}]}),
        "claim_registry": ClaimRegistry.model_validate({
            **common, "registry_id": "BRIDGE-CLAIM-REGISTRY-v0.1", "claims": claims}),
        "reconciliation_spec_registry": ReconciliationSpecRegistry.model_validate({
            **common, "registry_id": "BRIDGE-RECONCILIATION-SPEC-REGISTRY-v0.1", "specs": [{
                "reconciliation_spec_id": spec_ref["object_id"], "version": POLICY_VERSION,
                "claim_type": "descriptive_domain_observation",
                "required_channel_roles": ["canonical_measurement"],
                "primary_channel_roles": ["canonical_measurement"],
                "minimum_independent_families_by_role": {"canonical_measurement": 1},
                "allowed_evidence_states": ["measured", "inferred"],
                "conflict_rule": "family_dedup_then_channel_resolution",
                "consensus_rule": "unanimous_independent_confirmation",
                "integration_sensitivity_rule": "integration_role_disagrees_with_resolved_direction",
                "missing_behavior": "insufficient_evidence", "status": "candidate"}]}),
    }
