from __future__ import annotations

import copy
import hashlib
from pathlib import Path
from typing import Any

import pytest
from matplotlib import pyplot as plt
from jsonschema import Draft202012Validator

from bridge.tool_packages._structured_runtime import canonical_json_bytes
from bridge.tool_packages.p0_12_graft_assessment.analysis_models import (
    GraftExpressionAnalysisResult,
)
from bridge.tool_packages.p0_12_graft_assessment.models import (
    GraftAssessmentResult,
)
from bridge.tool_packages.p0_12_graft_assessment.visualization import (
    _render_composition,
    _render_molecular,
    _render_scope,
    _static_render_reason,
    prepare_graft_assessment_visualizations,
)
from bridge.tool_packages.p0_12_graft_assessment.visualization_data import (
    CompositionRowKind,
    GraftAssessmentVisualizationDataV1,
    GraftVisualizationMode,
    MolecularPanel,
    P012VisualizationArtifactSet,
    PUBLIC_VISUALIZATION_SCHEMA_MODELS,
    REFERENCE_AND_PROGRAM_COMPONENT_REF,
    build_graft_assessment_visualization_data,
    UPLOADED_PROFILE_COMPOSITION_COMPONENT_REF,
)
from bridge.toolkit.schemas import load_schema


RUN_ID = "run-0123456789abcdef"
TOOL_VERSION = "0.4.0"
CREATED_AT = "2026-08-27T00:00:00Z"


def _expression_result(
    *,
    state_id: str = "state-a",
    first_fraction: float = 0.55,
    second_fraction: float = 0.35,
    unassigned_fraction: float = 0.10,
    reference_reason_codes: list[str] | None = None,
    program_reason_codes: list[str] | None = None,
    animal_id: str = "animal:demo",
) -> GraftExpressionAnalysisResult:
    reference_reason_codes = reference_reason_codes or []
    program_reason_codes = program_reason_codes or []
    reference_available = not reference_reason_codes
    program_available = not program_reason_codes
    return GraftExpressionAnalysisResult.model_validate(
        {
            "object_version": "0.1.0",
            "result_id": "graft-expression-result:demo",
            "tool_id": "P0-12",
            "tool_version": TOOL_VERSION,
            "state": "candidate",
            "evidence_state": "shadow",
            "analysis_mode": "expression_analysis",
            "graft_case_ref": "graft-case:demo",
            "asset_ref": "asset:demo",
            "analysis_spec_ref": "analysis-spec:demo",
            "reference_panel_ref": "reference-panel:demo",
            "marker_program_collection_ref": "programs:demo",
            "graft_id": "graft:demo",
            "animal_id": animal_id,
            "post_transplant_timepoint": "day-42",
            "reference_source_family_id": "source-family:reference",
            "marker_source_family_id": "source-family:programs",
            "assay": "scRNA-seq",
            "matrix_semantics": "raw_counts",
            "analysis_value_semantics": "log1p_cp10k",
            "profile_aggregation": "sample_pseudobulk",
            "qc_state": "not_reassessed",
            "sample_unit": "technical_sample",
            "composition_denominator": "all_uploaded_rows",
            "cell_count": 10,
            "gene_count": 100,
            "sample_count": 2,
            "graft_count": 1,
            "unassigned_fraction": unassigned_fraction,
            "composition_estimates": [
                {
                    "state_id": state_id,
                    "mean_fraction": first_fraction,
                    "cell_equivalent": first_fraction * 10,
                    "denominator_cells": 10,
                },
                {
                    "state_id": "state-b",
                    "mean_fraction": second_fraction,
                    "cell_equivalent": second_fraction * 10,
                    "denominator_cells": 10,
                },
            ],
            "reference_support": [
                {
                    "sample_id": "sample-a",
                    "profile_id": "profile-a",
                    "availability": (
                        "available" if reference_available else "unavailable"
                    ),
                    "spearman_correlation": (0.65 if reference_available else None),
                    "shared_gene_count": 80,
                    "reason_codes": reference_reason_codes,
                },
                {
                    "sample_id": "sample-b",
                    "profile_id": "profile-a",
                    "availability": "available",
                    "spearman_correlation": 0.25,
                    "shared_gene_count": 75,
                    "reason_codes": [],
                },
            ],
            "program_evidence": [
                {
                    "sample_id": "sample-a",
                    "program_id": "program-a",
                    "availability": (
                        "available" if program_available else "unavailable"
                    ),
                    "mean_expression": (1.5 if program_available else None),
                    "gene_count": 8,
                    "gene_coverage": 0.8,
                    "reason_codes": program_reason_codes,
                },
                {
                    "sample_id": "sample-b",
                    "program_id": "program-a",
                    "availability": (
                        "available" if program_available else "unavailable"
                    ),
                    "mean_expression": (0.7 if program_available else None),
                    "gene_count": 6,
                    "gene_coverage": 0.6,
                    "reason_codes": program_reason_codes,
                },
            ],
            "source_bindings": [],
            "selected_method_ids": ["METHOD-ANNDATA"],
            "runtime_versions": {"python": "3.12"},
            "reason_codes": [],
            "created_at": CREATED_AT,
        }
    )


def _precomputed_result() -> GraftAssessmentResult:
    return GraftAssessmentResult.model_validate(
        {
            "result_id": "graft-assessment:demo",
            "result_version": "0.1.0",
            "state": "candidate",
            "graft_availability": "provided",
            "graft_case_ref": "graft-case:demo",
            "assessment_spec_ref": "graft-spec:demo",
            "evidence_bundle_ref": "graft-evidence:demo",
            "linkage_state": "provided_unlinked",
            "analysis_mode": "descriptive_only",
            "evidence_state": "shadow",
            "source_bindings": [
                {
                    "input_id": "case",
                    "role": "graft_case",
                    "schema_ref": "bridge://schemas/graft-case/v0.1",
                    "object_version": "0.1.0",
                    "source_sha256": "a" * 64,
                },
                {
                    "input_id": "spec",
                    "role": "assessment_spec",
                    "schema_ref": "bridge://schemas/graft-assessment-spec/v0.1",
                    "object_version": "0.1.0",
                    "source_sha256": "b" * 64,
                },
                {
                    "input_id": "bundle",
                    "role": "evidence_bundle",
                    "schema_ref": "bridge://schemas/graft-evidence-bundle/v0.1",
                    "object_version": "0.1.0",
                    "source_sha256": "c" * 64,
                },
            ],
            "role_summaries": [
                {
                    "role_id": "composition",
                    "record_count": 2,
                    "metric_ids": ["soft-composition"],
                    "evidence_states": ["observed"],
                    "state_class_counts": {"usable": 2},
                    "evidence_ids": [
                        "evidence:composition-a",
                        "evidence:composition-b",
                    ],
                }
            ],
            "missing_metadata": [],
            "confounder_refs": [],
            "required_roles_missing": [],
            "preparation_linkage": None,
            "reason_codes": [
                "graft_evidence_descriptive_candidate",
                "graft_preparation_linkage_not_provided",
            ],
            "created_at": CREATED_AT,
        }
    )


def _not_provided_result() -> GraftAssessmentResult:
    return GraftAssessmentResult.model_validate(
        {
            "result_id": "graft-assessment:not-provided",
            "result_version": "0.1.0",
            "state": "not_provided",
            "graft_availability": "not_provided",
            "linkage_state": "not_applicable",
            "analysis_mode": "unavailable",
            "evidence_state": "unavailable",
            "source_bindings": [],
            "role_summaries": [],
            "missing_metadata": [],
            "confounder_refs": [],
            "required_roles_missing": [],
            "reason_codes": ["graft_not_provided"],
            "created_at": CREATED_AT,
        }
    )


def _profile(result) -> GraftAssessmentVisualizationDataV1:
    payload = canonical_json_bytes(result.model_dump(mode="json"), indent=2)
    return build_graft_assessment_visualization_data(
        result=result,
        result_sha=hashlib.sha256(payload).hexdigest(),
        run_id=RUN_ID,
        tool_version=TOOL_VERSION,
    )


def test_expression_profile_preserves_probability_mass_and_denominator() -> None:
    profile = _profile(_expression_result())

    assert profile.mode is GraftVisualizationMode.EXPRESSION_ANALYSIS
    assert profile.uploaded_profile_count == 10
    assert profile.reference_source_family_id == "source-family:reference"
    assert profile.marker_source_family_id == "source-family:programs"
    assert profile.formal_evidence_ids == []
    assert profile.candidate_evidence_anchor.formal_evidence is False
    assert profile.composition_is_pooled_probability_mass
    assert profile.unassigned_is_not_an_unknown_state
    assert [record.state_id for record in profile.composition_records] == [
        "state-a",
        "state-b",
        None,
    ]
    assert [record.row_kind for record in profile.composition_records][
        -1
    ] is CompositionRowKind.UNASSIGNED_PROBABILITY_MASS
    assert {record.denominator_rows for record in profile.composition_records} == {10}
    assert sum(
        record.mean_fraction for record in profile.composition_records
    ) == pytest.approx(1.0)


def test_precomputed_profile_retains_formal_evidence_separately() -> None:
    profile = _profile(_precomputed_result())

    assert profile.mode is GraftVisualizationMode.PRECOMPUTED
    assert profile.formal_evidence_ids == [
        "evidence:composition-a",
        "evidence:composition-b",
    ]
    assert profile.formal_evidence_count == 2
    assert profile.candidate_evidence_anchor.anchor_id not in (
        profile.formal_evidence_ids
    )
    anchor_ids = [profile.candidate_evidence_anchor.anchor_id]
    assert all(
        record.evidence_ids == anchor_ids
        for record in (
            *profile.composition_records,
            *profile.molecular_records,
        )
    )
    role_count_records = [
        record
        for record in profile.scope_records
        if record.field_id in {"evidence_roles", "evidence_records"}
    ]
    assert all(
        record.evidence_ids == profile.evidence_ids for record in role_count_records
    )
    assert (
        next(
            record
            for record in profile.scope_records
            if record.field_id == "pretransplant_effect"
        ).evidence_ids
        == anchor_ids
    )


def test_not_provided_is_typed_empty_state_with_boundary() -> None:
    profile = _profile(_not_provided_result())

    assert profile.mode is GraftVisualizationMode.NOT_PROVIDED
    assert all(record.mean_fraction is None for record in profile.composition_records)
    assert all(record.display_value is None for record in profile.molecular_records)
    boundary = next(
        record
        for record in profile.scope_records
        if record.field_id == "pretransplant_effect"
    )
    assert boundary.display_value == "none"
    assert boundary.missingness == "available"


def test_render_bundle_is_complete_deterministic_and_registry_valid(
    tmp_path: Path,
) -> None:
    profile = _profile(_expression_result())

    first = prepare_graft_assessment_visualizations(
        profile, tmp_path, RUN_ID, TOOL_VERSION
    )
    second = prepare_graft_assessment_visualizations(
        profile, tmp_path, RUN_ID, TOOL_VERSION
    )

    assert first.payloads == second.payloads
    assert len(first.payloads) == 14
    assert len(first.artifacts) == 14
    assert (
        sum(artifact.kind == "visualization_render" for artifact in first.artifacts)
        == 9
    )
    artifact_set = P012VisualizationArtifactSet.model_validate_json(
        first.payloads["p0_12_visualization_artifact_set.json"]
    )
    assert len(artifact_set.visualizations) == 3
    assert all(
        visualization.producer_tool_id == "P0-12"
        for visualization in artifact_set.visualizations
    )
    assert all(
        b"file://" not in payload and str(tmp_path).encode() not in payload
        for name, payload in first.payloads.items()
        if name.endswith(".svg")
    )
    molecular_svg = first.payloads[
        "graft_assessment_reference-and-program-expression.svg"
    ].decode("utf-8")
    assert "source-family:reference" in molecular_svg
    assert "source-family:programs" in molecular_svg


def test_composition_numeric_column_stays_inside_canvas() -> None:
    figure = _render_composition(_profile(_expression_result()))
    try:
        figure.canvas.draw()
        renderer = figure.canvas.get_renderer()
        labels = [
            text
            for axis in figure.axes
            for text in axis.texts
            if text.get_text().startswith("mass-equivalent")
        ]
        assert labels
        assert all(
            text.get_window_extent(renderer).x1 <= figure.bbox.x1 for text in labels
        )
    finally:
        plt.close(figure)


def test_dense_reference_matrix_uses_complete_table_fallback(
    tmp_path: Path,
) -> None:
    result_payload = _expression_result().model_dump(mode="json")
    result_payload["reference_support"] = [
        {
            "sample_id": sample_id,
            "profile_id": f"profile-{profile_index:02d}",
            "availability": "available",
            "spearman_correlation": 0.25,
            "shared_gene_count": 75,
            "reason_codes": [],
        }
        for sample_id in ("sample-a", "sample-b")
        for profile_index in range(9)
    ]
    profile = _profile(GraftExpressionAnalysisResult.model_validate(result_payload))

    prepared = prepare_graft_assessment_visualizations(
        profile, tmp_path, RUN_ID, TOOL_VERSION
    )
    svg = prepared.payloads[
        "graft_assessment_reference-and-program-expression.svg"
    ].decode("utf-8")
    table = prepared.payloads[
        "graft_assessment_reference_and_program_expression.tsv"
    ].decode("utf-8")

    assert "Complete-table view required" in svg
    assert "profile-08" in table


def test_molecular_static_render_boundary_is_conservative() -> None:
    result_payload = _expression_result().model_dump(mode="json")
    sample_ids = ("W" * 11 + "0", "W" * 11 + "1")
    result_payload["reference_support"] = [
        {
            "sample_id": sample_id,
            "profile_id": "W" * 7 + str(profile_index),
            "availability": "available",
            "spearman_correlation": 0.25,
            "shared_gene_count": 75,
            "reason_codes": [],
        }
        for sample_id in sample_ids
        for profile_index in range(8)
    ]
    result_payload["program_evidence"] = [
        {
            "sample_id": sample_id,
            "program_id": "W" * 7 + str(program_index),
            "availability": "available",
            "mean_expression": 0.7,
            "gene_count": 6,
            "gene_coverage": 0.6,
            "reason_codes": [],
        }
        for sample_id in sample_ids
        for program_index in range(8)
    ]
    profile = _profile(GraftExpressionAnalysisResult.model_validate(result_payload))

    assert _static_render_reason(profile, REFERENCE_AND_PROGRAM_COMPONENT_REF) is None

    figure = _render_molecular(profile)
    try:
        figure.canvas.draw()
        renderer = figure.canvas.get_renderer()
        matrix_x_boxes = []
        for axis in figure.axes:
            if not axis.axison:
                continue
            x_boxes = [
                label.get_window_extent(renderer)
                for label in axis.get_xticklabels()
                if label.get_visible() and label.get_text()
            ]
            matrix_x_boxes.extend(x_boxes)
            assert all(
                not left.overlaps(right)
                for left, right in zip(x_boxes, x_boxes[1:], strict=False)
            )
            assert all(
                figure.bbox.x0 <= box.x0 and box.x1 <= figure.bbox.x1 for box in x_boxes
            )
            assert all(
                label.get_window_extent(renderer).x0 >= figure.bbox.x0
                for label in axis.get_yticklabels()
                if label.get_visible() and label.get_text()
            )
        source_boxes = [
            text.get_window_extent(renderer)
            for text in figure.texts
            if text.get_text().startswith("Reference source")
        ]
        assert len(source_boxes) == 1
        assert all(not source_boxes[0].overlaps(label) for label in matrix_x_boxes)
    finally:
        plt.close(figure)

    crowded_payload = copy.deepcopy(result_payload)
    for record in crowded_payload["reference_support"]:
        record["profile_id"] += "W"
    for record in crowded_payload["program_evidence"]:
        record["program_id"] += "W"
    crowded = _profile(GraftExpressionAnalysisResult.model_validate(crowded_payload))
    assert (
        _static_render_reason(crowded, REFERENCE_AND_PROGRAM_COMPONENT_REF)
        == "static_render_requires_complete_table_fallback"
    )


def test_single_molecular_label_width_is_bounded() -> None:
    result_payload = _expression_result().model_dump(mode="json")
    for record in result_payload["reference_support"]:
        record["profile_id"] = "W" * 32
    for record in result_payload["program_evidence"]:
        record["program_id"] = "W" * 32
    profile = _profile(GraftExpressionAnalysisResult.model_validate(result_payload))

    assert _static_render_reason(profile, REFERENCE_AND_PROGRAM_COMPONENT_REF) is None
    figure = _render_molecular(profile)
    try:
        figure.canvas.draw()
        renderer = figure.canvas.get_renderer()
        for axis in (item for item in figure.axes if item.axison):
            boxes = [
                label.get_window_extent(renderer)
                for label in axis.get_xticklabels()
                if label.get_text()
            ]
            assert all(
                figure.bbox.x0 <= box.x0 and box.x1 <= figure.bbox.x1 for box in boxes
            )
    finally:
        plt.close(figure)

    crowded_payload = copy.deepcopy(result_payload)
    for record in crowded_payload["reference_support"]:
        record["profile_id"] = "W" * 33
    for record in crowded_payload["program_evidence"]:
        record["program_id"] = "W" * 33
    crowded = _profile(GraftExpressionAnalysisResult.model_validate(crowded_payload))
    assert (
        _static_render_reason(crowded, REFERENCE_AND_PROGRAM_COMPONENT_REF)
        == "static_render_requires_complete_table_fallback"
    )


def test_composition_label_budget_prevents_clipping() -> None:
    allowed = _profile(_expression_result(state_id="W" * 20))
    assert (
        _static_render_reason(allowed, UPLOADED_PROFILE_COMPOSITION_COMPONENT_REF)
        is None
    )
    figure = _render_composition(allowed)
    try:
        figure.canvas.draw()
        renderer = figure.canvas.get_renderer()
        assert all(
            label.get_window_extent(renderer).x0 >= figure.bbox.x0
            for label in figure.axes[0].get_yticklabels()
        )
    finally:
        plt.close(figure)

    crowded = _profile(_expression_result(state_id="W" * 21))
    assert (
        _static_render_reason(crowded, UPLOADED_PROFILE_COMPOSITION_COMPONENT_REF)
        == "static_render_requires_complete_table_fallback"
    )


def test_artifact_set_rejects_cross_run_and_duplicate_bindings(
    tmp_path: Path,
) -> None:
    profile = _profile(_expression_result())
    prepared = prepare_graft_assessment_visualizations(
        profile, tmp_path, RUN_ID, TOOL_VERSION
    )
    artifact_set = P012VisualizationArtifactSet.model_validate_json(
        prepared.payloads["p0_12_visualization_artifact_set.json"]
    )
    source = artifact_set.model_dump(mode="json")

    wrong_data = copy.deepcopy(source)
    wrong_data["artifact_set_id"] = "p0-12-visualizations:fedcba9876543210"
    with pytest.raises(ValueError, match="artifact-set run"):
        P012VisualizationArtifactSet.model_validate(wrong_data)

    wrong_order = copy.deepcopy(source)
    wrong_order["visualizations"][0]["renders"][:2] = reversed(
        wrong_order["visualizations"][0]["renders"][:2]
    )
    with pytest.raises(ValueError, match="ordered SVG"):
        P012VisualizationArtifactSet.model_validate(wrong_order)

    duplicate_table = copy.deepcopy(source)
    duplicate_table["visualizations"][1]["accessibility"]["table_artifact_id"] = (
        duplicate_table["visualizations"][0]["accessibility"]["table_artifact_id"]
    )
    with pytest.raises(ValueError, match="table artifact IDs must be unique"):
        P012VisualizationArtifactSet.model_validate(duplicate_table)

    wrong_run = copy.deepcopy(source)
    wrong_run["visualizations"][2]["producer_run_ref"] = "run:run-fedcba9876543210"
    with pytest.raises(ValueError, match="producer run"):
        P012VisualizationArtifactSet.model_validate(wrong_run)

    duplicate_render = copy.deepcopy(source)
    duplicate_render["visualizations"][2]["renders"][2]["artifact_id"] = (
        duplicate_render["visualizations"][0]["renders"][0]["artifact_id"]
    )
    with pytest.raises(ValueError, match="render artifact IDs|must be disjoint"):
        P012VisualizationArtifactSet.model_validate(duplicate_render)


def test_unavailable_rows_keep_every_upstream_reason() -> None:
    profile = _profile(
        _expression_result(
            reference_reason_codes=[
                "insufficient_shared_genes",
                "reference_profile_unavailable",
            ]
        )
    )

    record = next(
        item
        for item in profile.molecular_records
        if item.sample_id == "sample-a"
        and item.panel is MolecularPanel.REFERENCE_SIMILARITY
    )
    assert record.display_value is None
    assert record.reason_codes == [
        "insufficient_shared_genes",
        "reference_profile_unavailable",
    ]
    assert record.shared_gene_count == 80


def test_all_unavailable_program_rows_render_without_zero_fill(
    tmp_path: Path,
) -> None:
    profile = _profile(
        _expression_result(program_reason_codes=["registered_program_genes_missing"])
    )

    prepared = prepare_graft_assessment_visualizations(
        profile, tmp_path, RUN_ID, TOOL_VERSION
    )
    svg = prepared.payloads[
        "graft_assessment_reference-and-program-expression.svg"
    ].decode("utf-8")

    assert "No numeric value" in svg
    assert all(
        record.display_value is None
        for record in profile.molecular_records
        if record.panel is MolecularPanel.REGISTERED_GENE_PROGRAM_EXPRESSION
    )


def test_long_scope_identifier_keeps_both_ends_without_clipping(
    tmp_path: Path,
) -> None:
    animal_id = "W" * 80
    profile = _profile(_expression_result(animal_id=animal_id))

    prepared = prepare_graft_assessment_visualizations(
        profile, tmp_path, RUN_ID, TOOL_VERSION
    )
    svg = prepared.payloads["graft_assessment_specimen-scope.svg"].decode("utf-8")
    table = prepared.payloads["graft_assessment_specimen_scope.tsv"].decode("utf-8")

    assert animal_id[:5] in svg
    assert animal_id[-5:] in svg
    assert animal_id in table
    assert "Complete-table view required" not in svg


def test_long_identifier_uses_complete_table_fallback(
    tmp_path: Path,
) -> None:
    state_id = "state-" + "a" * 120
    profile = _profile(_expression_result(state_id=state_id))

    prepared = prepare_graft_assessment_visualizations(
        profile, tmp_path, RUN_ID, TOOL_VERSION
    )
    table = prepared.payloads[
        "graft_assessment_uploaded_profile_composition.tsv"
    ].decode("utf-8")
    svg = prepared.payloads["graft_assessment_uploaded-profile-composition.svg"].decode(
        "utf-8"
    )

    assert state_id in table
    assert "Complete-table view required" in svg
    assert "No top-N selection" in svg


def test_partial_molecular_grid_is_rejected_without_zero_fill() -> None:
    profile = _profile(_expression_result())
    payload = profile.model_dump(mode="json")
    payload["molecular_records"] = [
        record
        for record in payload["molecular_records"]
        if not (
            record["panel"] == "reference_similarity"
            and record["sample_id"] == "sample-b"
        )
    ]

    with pytest.raises(
        ValueError,
        match="complete Cartesian grid|cover every technical sample",
    ):
        GraftAssessmentVisualizationDataV1.model_validate(payload)


def test_scope_fields_and_empty_panels_are_mode_complete() -> None:
    expression = _profile(_expression_result()).model_dump(mode="json")
    expression["scope_records"] = [
        record
        for record in expression["scope_records"]
        if record["field_id"] != "animal"
    ]
    with pytest.raises(ValueError, match="scope fields must be complete"):
        GraftAssessmentVisualizationDataV1.model_validate(expression)

    precomputed = _profile(_precomputed_result()).model_dump(mode="json")
    precomputed["molecular_records"][1]["panel"] = "reference_similarity"
    with pytest.raises(ValueError, match="one empty row per molecular panel"):
        GraftAssessmentVisualizationDataV1.model_validate(precomputed)

    not_provided = _profile(_not_provided_result()).model_dump(mode="json")
    formal_id = "evidence:unexpected"
    not_provided["formal_evidence_ids"] = [formal_id]
    not_provided["formal_evidence_count"] = 1
    not_provided["evidence_ids"] = sorted([*not_provided["evidence_ids"], formal_id])
    with pytest.raises(ValueError, match="cannot carry formal evidence"):
        GraftAssessmentVisualizationDataV1.model_validate(not_provided)


def test_record_evidence_bindings_are_exact() -> None:
    expression = _profile(_expression_result()).model_dump(mode="json")
    formal_id = "evidence:unexpected"
    expression["formal_evidence_ids"] = [formal_id]
    expression["formal_evidence_count"] = 1
    expression["evidence_ids"] = sorted([*expression["evidence_ids"], formal_id])
    with pytest.raises(ValueError, match="cannot carry formal evidence"):
        GraftAssessmentVisualizationDataV1.model_validate(expression)

    precomputed = _profile(_precomputed_result()).model_dump(mode="json")
    overbound = next(
        record
        for record in precomputed["scope_records"]
        if record["field_id"] == "pretransplant_effect"
    )
    overbound["evidence_ids"] = list(precomputed["evidence_ids"])
    with pytest.raises(ValueError, match="exact evidence"):
        GraftAssessmentVisualizationDataV1.model_validate(precomputed)


@pytest.mark.parametrize(
    "schema_ref,model",
    PUBLIC_VISUALIZATION_SCHEMA_MODELS.items(),
)
def test_p0_12_visualization_schema_files_are_exact_exports(
    schema_ref: str,
    model: type[Any],
) -> None:
    expected = model.model_json_schema()
    expected["$id"] = schema_ref
    actual = load_schema(schema_ref)

    Draft202012Validator.check_schema(actual)
    assert actual == expected


def test_probability_mass_outside_tolerance_is_rejected() -> None:
    result = _expression_result(
        first_fraction=0.50,
        second_fraction=0.30,
        unassigned_fraction=0.10,
    )

    with pytest.raises(
        ValueError,
        match="assigned and unassigned probability mass",
    ):
        _profile(result)


def test_tolerance_is_accepted_without_renormalization() -> None:
    result = _expression_result(
        first_fraction=0.55,
        second_fraction=0.35,
        unassigned_fraction=0.1000005,
    )
    profile = _profile(result)

    assert profile.composition_records[-1].mean_fraction == 0.1000005
    assert sum(
        record.mean_fraction for record in profile.composition_records
    ) == pytest.approx(1.0000005)


def test_existing_result_schema_bytes_remain_unchanged() -> None:
    expected = {
        "graft_assessment_result.schema.json": "48f54b07ec2ce8356f29dad82a8cc8eab62364f5ec058365618153a738f9f91a",
        "graft_expression_analysis_result.schema.json": "0320c875a7ed5c84b65c39bb53cd277c14382f0f5ce824c8dba95d1900c98e98",
        "graft_assessment_run_result.schema.json": "c55297f3fcd564139ef3d7a610540de186a575d64724df4d62d67e31d769b8a3",
    }
    schema_root = Path("src/bridge/resources/schemas")

    assert {
        name: hashlib.sha256((schema_root / name).read_bytes()).hexdigest()
        for name in expected
    } == expected
