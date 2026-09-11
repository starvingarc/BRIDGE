"""Versioned development decisions; never a scientific release or user signature."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from importlib.resources import files
from typing import Literal

from pydantic import Field, model_validator
import yaml

from bridge.toolkit.contracts import FrozenModel

_RESOURCE_PACKAGE = "bridge.tool_packages.p0_02_cell_state.resources"


class ScientificReviewSource(FrozenModel):
    source_id: str
    citation: str
    locator: str
    evidence_scope: str
    limitation: str


class DevelopmentProductScope(FrozenModel):
    target_lineage: Literal["ventral_midbrain_dopaminergic"]
    intended_stages: list[Literal["progenitor", "early_neuroblast"]]
    stage_evaluation: Literal["separate_from_identity"]
    culture_to_fetal_age: Literal["not_inferred"]
    role_basis: Literal["lineage_evidence_not_source_label"]
    biological_unit_policy: Literal["unknown_is_not_an_independent_replicate"]


class StateDevelopmentDecision(FrozenModel):
    state_id: str
    display_name: str
    definition: str
    decision: Literal["evaluate", "parent_only", "unavailable"]
    parent_state_id: str | None = None
    definition_support: Literal["broad_family_supported", "source_boundary_unresolved", "reference_unavailable"]
    positive_markers: list[str]
    counter_markers: list[str]
    source_ids: list[str] = Field(min_length=1)
    default_product_role: Literal["known_off_target", "role_unresolved"]
    rationale: str
    limitations: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def decision_is_not_an_unearned_identity(self):
        if self.decision == "parent_only" and not self.parent_state_id:
            raise ValueError("parent_only_requires_parent")
        if self.decision == "evaluate" and not self.positive_markers:
            raise ValueError("evaluated_state_requires_positive_program")
        if self.definition_support != "broad_family_supported" and self.decision != "unavailable":
            raise ValueError("unresolved_definition_cannot_assign_identity")
        return self


class CellStateDevelopmentReview(FrozenModel):
    object_version: Literal["1.0.0"] = "1.0.0"
    review_id: str
    policy_ref: Literal["CELLSTATE-DEVELOPMENT-DECISIONS-v1"]
    status: Literal["complete"]
    vocabulary_ref: str
    legacy_review_ref: str
    legacy_review_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    scientific_qualification: Literal["not_established"]
    marker_semantics: Literal["support_and_competing_programs_not_gene_absence"]
    sources: list[ScientificReviewSource] = Field(min_length=1)
    product_scope: DevelopmentProductScope
    state_reviews: list[StateDevelopmentDecision] = Field(min_length=1)

    @model_validator(mode="after")
    def preserve_source_scope(self):
        raw = files(_RESOURCE_PACKAGE).joinpath("biological_review_draft.yaml").read_bytes()
        legacy = yaml.safe_load(raw)
        if (
            self.legacy_review_sha256 != hashlib.sha256(raw).hexdigest()
            or self.legacy_review_ref != legacy["review_record_id"]
            or self.vocabulary_ref != legacy["vocabulary_ref"]
        ):
            raise ValueError("legacy_review_binding_mismatch")
        old_cards = {row["state_id"]: row for row in legacy["state_reviews"]}
        rows = {row.state_id: row for row in self.state_reviews}
        if len(rows) != len(self.state_reviews) or set(rows) != set(old_cards):
            raise ValueError("complete_state_coverage_required")
        sources = {row.source_id for row in self.sources}
        if len(sources) != len(self.sources):
            raise ValueError("duplicate_review_source")
        for row in self.state_reviews:
            if not set(row.source_ids).issubset(sources):
                raise ValueError("review_source_not_registered")
            old = old_cards[row.state_id]
            if old["n_observations"] == 0 and row.decision != "unavailable":
                raise ValueError("zero_observation_state_must_remain_unavailable")
            if row.parent_state_id is not None:
                if row.parent_state_id not in old.get("parent_state_ids", []):
                    raise ValueError("review_parent_not_source_bound")
                parent = rows.get(row.parent_state_id)
                if parent is None or parent.decision != "evaluate":
                    raise ValueError("review_parent_not_evaluable")
        return self


class DevelopmentProductScopeV11(DevelopmentProductScope):
    source_label_target_mapping: Literal["unavailable_not_zero"]
    source_label_window_mapping: Literal["unavailable_not_zero"]
    off_target_policy: Literal["conditional_on_supported_identity_not_source_label"]
    stress_program_state: Literal["not_assessed_no_registered_program"]


class CellStateDevelopmentReviewV11(CellStateDevelopmentReview):
    object_version: Literal["1.1.0"] = "1.1.0"
    policy_ref: Literal["CELLSTATE-DEVELOPMENT-DECISIONS-v1.1"]
    product_scope: DevelopmentProductScopeV11


def _review_resource(version: str):
    versions = {
        "1.0.0": ("development_review_v1.json", CellStateDevelopmentReview),
        "1.1.0": ("development_review_v1_1.json", CellStateDevelopmentReviewV11),
    }
    if version not in versions:
        raise ValueError("development_review_version_unsupported")
    return versions[version]


@dataclass(frozen=True)
class ReviewedAssignment:
    state_id: str | None
    assignment_state: Literal["candidate", "parent_candidate", "unknown"]
    product_role: Literal["known_off_target", "role_unresolved"]
    reason_code: str


def load_development_review(version: str = "1.1.0") -> CellStateDevelopmentReview | CellStateDevelopmentReviewV11:
    resource, model = _review_resource(version)
    raw = files(_RESOURCE_PACKAGE).joinpath(resource).read_bytes()
    return model.model_validate_json(raw)


def resolve_development_state(
    review: CellStateDevelopmentReview, state_id: str, *, ood_rejected: bool = False,
) -> ReviewedAssignment:
    if ood_rejected:
        return ReviewedAssignment(None, "unknown", "role_unresolved", "ood_rejected")
    rows = {row.state_id: row for row in review.state_reviews}
    row = rows.get(state_id)
    if row is None:
        return ReviewedAssignment(None, "unknown", "role_unresolved", "state_not_reviewed")
    if row.decision == "unavailable":
        return ReviewedAssignment(None, "unknown", "role_unresolved", "state_identity_unavailable")
    if row.decision == "parent_only":
        parent = rows[row.parent_state_id]
        return ReviewedAssignment(
            parent.state_id, "parent_candidate", "role_unresolved",
            "regional_source_label_not_validated",
        )
    return ReviewedAssignment(row.state_id, "candidate", "role_unresolved", "development_candidate_only")


def development_review_sha256(version: str = "1.1.0") -> str:
    resource, _ = _review_resource(version)
    return hashlib.sha256(files(_RESOURCE_PACKAGE).joinpath(resource).read_bytes()).hexdigest()
