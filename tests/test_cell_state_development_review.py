from __future__ import annotations

import pytest
from pydantic import ValidationError

from bridge.tool_packages.p0_02_cell_state import freeze


def test_completed_development_review_does_not_promote_legacy_science():
    old = freeze.load_biological_review_draft()
    review = freeze.load_development_review()
    assert review.status == "complete"
    assert review.scientific_qualification == "not_established"
    assert {row.state_id for row in review.state_reviews} == {
        row.state_id for row in old.state_reviews
    }
    assert old.status == "pending"
    assert old.signatures == []
    assert all(row.review_status == "pending" for row in old.state_reviews)
    assert review.product_scope.intended_stages == ["progenitor", "early_neuroblast"]
    assert review.product_scope.stage_evaluation == "separate_from_identity"


@pytest.mark.parametrize(
    ("state_id", "expected"),
    [
        ("L2:RG_mFP", "L1:Radial_Glia"),
        ("L2:RG_mBMP", "L1:Radial_Glia"),
        ("L2:RG_mBIP", "L1:Radial_Glia"),
        ("L2:Nb_mFP", "L1:Neuroblast"),
        ("L2:Nb_mBMP", "L1:Neuroblast"),
        ("L2:Nb_mBIP", "L1:Neuroblast"),
        ("L2:Nb_mAP", "L1:Neuroblast"),
    ],
)
def test_unresolved_regional_label_emits_parent_not_anatomical_identity(state_id, expected):
    review = freeze.load_development_review()
    assignment = freeze.resolve_development_state(review, state_id)
    assert assignment.state_id == expected
    assert assignment.assignment_state == "parent_candidate"
    assert assignment.product_role == "role_unresolved"


@pytest.mark.parametrize("state_id", [
    "L1:Neuron_ChAT", "L1:Neuron_Glut_GABA", "L1:Glioblast", "L2:RG_dHyp",
])
def test_unavailable_or_unreviewed_label_cannot_become_identity(state_id):
    assignment = freeze.resolve_development_state(freeze.load_development_review(), state_id)
    assert assignment.state_id is None
    assert assignment.assignment_state == "unknown"
    assert assignment.product_role == "role_unresolved"


def test_ood_rejection_cannot_be_rescued_as_a_known_parent():
    assignment = freeze.resolve_development_state(
        freeze.load_development_review(), "L2:Nb_mFP", ood_rejected=True,
    )
    assert assignment.state_id is None
    assert assignment.assignment_state == "unknown"
    assert assignment.reason_code == "ood_rejected"


def test_missing_reviewed_state_or_unknown_source_rejects_decision_record():
    review = freeze.load_development_review()
    payload = review.model_dump(mode="json")
    payload["state_reviews"] = payload["state_reviews"][:-1]
    with pytest.raises(ValidationError, match="complete_state_coverage_required"):
        type(review).model_validate(payload)
    payload = review.model_dump(mode="json")
    payload["state_reviews"][0]["source_ids"] = ["invented-source"]
    with pytest.raises(ValidationError, match="review_source_not_registered"):
        type(review).model_validate(payload)


def test_development_review_cannot_self_assert_scientific_qualification():
    review = freeze.load_development_review()
    payload = review.model_dump(mode="json")
    payload["scientific_qualification"] = "qualified"
    with pytest.raises(ValidationError):
        type(review).model_validate(payload)
    payload = review.model_dump(mode="json")
    payload["state_reviews"][0]["default_product_role"] = "target"
    with pytest.raises(ValidationError):
        type(review).model_validate(payload)


def test_registry_figure_does_not_present_unresolved_source_group_as_gliogenic_identity():
    from bridge.tool_packages.p0_02_cell_state.visualization_runtime import build_source_state_evidence_matrix
    from bridge.tool_packages.p0_02_cell_state.visualization import _friendly_state_name
    matrix, _, _ = build_source_state_evidence_matrix("run-development-review")
    row = next(row for row in matrix.states if row.state_id == "L1:Glioblast")
    assert "identity unresolved" in row.display_name
    assert "gliogenic progenitor" not in row.display_name.casefold()
    assert _friendly_state_name(row.display_name) == "Glioblast (unresolved)*"
    assert row.review_state == "pending"


def test_development_review_has_a_separate_public_schema():
    from bridge.toolkit.schemas import load_schema
    schema = load_schema("bridge://schemas/cell-state-development-review/v1.0")
    assert schema["properties"]["scientific_qualification"]["const"] == "not_established"
    assert schema["properties"]["policy_ref"]["const"] == "CELLSTATE-DEVELOPMENT-DECISIONS-v1"


@pytest.mark.parametrize("state_id", ["L1:Neuron_GABA", "L1:Neuron_Glut"])
def test_transmitter_program_does_not_exclude_mda_lineage(state_id):
    review = freeze.load_development_review()
    assignment = freeze.resolve_development_state(review, state_id)
    assert assignment.product_role == "role_unresolved"
    assert review.product_scope.source_label_target_mapping == "unavailable_not_zero"
    assert review.product_scope.source_label_window_mapping == "unavailable_not_zero"


def test_initial_development_decision_remains_readable_after_semantic_revision():
    old = freeze.load_development_review("1.0.0")
    current = freeze.load_development_review()
    assert old.object_version == "1.0.0"
    assert current.object_version == "1.1.0"
    assert old.policy_ref != current.policy_ref
    assert current.legacy_review_sha256 == old.legacy_review_sha256


@pytest.mark.parametrize("state_id", ["L1:Astrocyte", "L1:Endothelial_Cell", "L1:Oligo"])
def test_conditional_off_target_policy_does_not_assign_a_candidate_product_role(state_id):
    review = freeze.load_development_review()
    card = next(row for row in review.state_reviews if row.state_id == state_id)
    assert card.default_product_role == "known_off_target"
    assignment = freeze.resolve_development_state(review, state_id)
    assert assignment.state_id == state_id
    assert assignment.product_role == "role_unresolved"
