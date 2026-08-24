from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from bridge.tool_packages._configurable_contracts import (
    BiologicalUnitAssignmentArtifact,
    BiologicalUnitBinding,
    BiologicalUnitManifest,
    ProductCase,
    ProductDefinitionCard,
    VersionedObjectRef,
    biological_unit_assignment_reasons,
    observation_ids_sha256,
    profile_lineage_reasons,
)
from bridge.toolkit.contracts import (
    CellStateEvidenceProfileV2,
    DataViewBinding,
    EvidenceState,
    ExecutionState,
    ImplementationState,
    MeasurementResult,
    MeasurementResultV2,
    QCReadinessProfileV2,
    ScoreState,
    ToolRequestV2,
    ToolRunV2,
)
from bridge.toolkit.schemas import load_schema


def _ref(object_id: str) -> VersionedObjectRef:
    return VersionedObjectRef(object_id=object_id, object_version="1.0.0")


def _binding() -> BiologicalUnitBinding:
    preparation = _ref("preparation:demo")
    sample = _ref("sample:demo")
    return BiologicalUnitBinding(
        analysis_unit_ref=preparation,
        analysis_unit_kind="preparation",
        independence_group_ref=sample,
        independence_group_kind="sample",
        preparation_ref=preparation,
        sample_ref=sample,
    )


def _manifest(**overrides: object) -> BiologicalUnitManifest:
    payload: dict[str, object] = {
        "object_version": "0.1.0",
        "manifest_id": "biological-unit-manifest:demo",
        "manifest_version": "1.0.0",
        "schema_ref": "bridge://schemas/biological-unit-manifest/v0.1",
        "generator_tool_id": "P0-01",
        "generator_tool_version": "1.0.0",
        "data_view_ref": "data-view:demo@1.0.0",
        "selected_artifact_sha256": "a" * 64,
        "observation_ids_sha256": observation_ids_sha256(
            [f"demo-observation-{index:04d}" for index in range(8)]
        ),
        "n_observations": 8,
        "assignment_schema_ref": "bridge://schemas/biological-unit-assignment/v0.1",
        "assignment_artifact_sha256": "c" * 64,
        "assignment_row_count": 8,
        "unit_identity_namespace_ref": _ref("biological-unit-namespace:demo"),
        "analysis_unit_kind": "preparation",
        "independence_group_kind": "sample",
        "independence_scope_ref": _ref("independence-scope:demo"),
        "lineage_state": "declared",
        "unit_bindings": [_binding()],
    }
    payload.update(overrides)
    return BiologicalUnitManifest.model_validate(payload)


def _assignment_artifact(
    *,
    group_ref: str = "sample:demo@1.0.0",
) -> BiologicalUnitAssignmentArtifact:
    observation_ids = [
        f"demo-observation-{index:04d}" for index in range(8)
    ]
    return BiologicalUnitAssignmentArtifact.model_validate(
        {
            "object_version": "0.1.0",
            "schema_ref": "bridge://schemas/biological-unit-assignment/v0.1",
            "data_view_ref": "data-view:demo@1.0.0",
            "observation_ids_sha256": observation_ids_sha256(observation_ids),
            "assignments": [
                {
                    "observation_id": observation_id,
                    "preparation_ref": "preparation:demo@1.0.0",
                    "sample_ref": "sample:demo@1.0.0",
                    "analysis_unit_ref": "preparation:demo@1.0.0",
                    "independence_group_ref": group_ref,
                }
                for observation_id in observation_ids
            ],
        }
    )


def _measurement_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "measurement_id": "measurement:demo",
        "measurement_spec_id": "measurement-spec:demo",
        "metric_name": "demo_fraction",
        "raw_value": 0.5,
        "domain_score": None,
        "score_state": "unavailable",
        "evidence_state": "measured",
    }
    payload.update(overrides)
    return payload


def test_v2_run_accepts_v1_shaped_measurement_without_enabling_score(
    tmp_path: Path,
) -> None:
    measurement = MeasurementResult(
        measurement_id="measurement:demo",
        measurement_spec_id="measurement-spec:demo",
        metric_name="demo_fraction",
        raw_value=0.5,
        domain_score=None,
        score_state=ScoreState.UNAVAILABLE,
        evidence_state=EvidenceState.MEASURED,
    )
    run = ToolRunV2(
        run_id="tool-run:demo@1.0.0",
        request=ToolRequestV2(
            request_id="request:demo",
            tool_id="P0-08",
            output_dir=tmp_path.resolve(),
        ),
        implementation_state=ImplementationState.IMPLEMENTED,
        execution_state=ExecutionState.SUCCEEDED,
        tool_version="1.0.0",
        environment_spec_id="ENV-P0-CORE-v0.1",
        measurements=[measurement],
        result_schema_ref="bridge://schemas/evidence-sufficiency-run-result/v0.1",
        result={},
    )

    assert run.measurements == [measurement]
    assert run.measurements[0].domain_score is None


def test_measurement_v2_requires_paired_source_and_interval_metadata() -> None:
    with pytest.raises(ValidationError, match="source_run_ref"):
        MeasurementResultV2(
            **_measurement_payload(),
            source_execution_state="succeeded",
        )
    with pytest.raises(ValidationError, match="interval metadata"):
        MeasurementResultV2(
            **_measurement_payload(),
            interval_confidence_level=0.95,
        )



@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"numerator": 1}, "numerator and denominator"),
        ({"numerator": 0, "denominator": 0}, "greater than 0"),
        ({"interval": (1.0, 0.0)}, "lower bound"),
        ({"interval": (0.0, float("inf"))}, "finite"),
        ({"evidence_state": "missing", "raw_value": 0}, "cannot carry a value"),
        (
            {"evidence_state": "unavailable", "raw_value": 0},
            "cannot carry a value",
        ),
        ({"evidence_state": "unknown"}, "unknown_scope"),
    ],
)
def test_measurement_v2_rejects_ambiguous_numeric_states(
    overrides: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(ValidationError, match=message):
        MeasurementResultV2(**_measurement_payload(**overrides))


def test_measurement_v2_scopes_unknown_without_a_numeric_value() -> None:
    result = MeasurementResultV2(
        **_measurement_payload(
            evidence_state="unknown",
            raw_value=None,
            unknown_scope="identity",
        )
    )
    assert result.unknown_scope == "identity"

def test_p0_01_cannot_claim_reviewed_biological_lineage() -> None:
    with pytest.raises(ValidationError, match="P0-01 can only generate declared"):
        _manifest(
            lineage_state="reviewed",
            review_gate_ref=_ref("biological-unit-review:demo"),
            review_gate_sha256="d" * 64,
        )


@pytest.mark.parametrize("independence_kind", ["capture", "graft_unit"])
def test_technical_units_cannot_be_independence_groups(
    independence_kind: str,
) -> None:
    with pytest.raises(ValidationError, match="Input should be"):
        _manifest(independence_group_kind=independence_kind)




def test_binding_rejects_independence_group_that_contradicts_hierarchy() -> None:
    preparation = _ref("preparation:demo")
    sample = _ref("sample:demo")
    with pytest.raises(ValidationError, match="typed hierarchy ref"):
        BiologicalUnitBinding(
            analysis_unit_ref=preparation,
            analysis_unit_kind="preparation",
            independence_group_ref=_ref("sample:fabricated"),
            independence_group_kind="sample",
            preparation_ref=preparation,
            sample_ref=sample,
        )


def test_assignment_artifact_is_checked_row_by_row_against_manifest() -> None:
    assert biological_unit_assignment_reasons(
        manifest=_manifest(),
        artifact=_assignment_artifact(),
        artifact_sha256="c" * 64,
    ) == []

    reasons = biological_unit_assignment_reasons(
        manifest=_manifest(),
        artifact=_assignment_artifact(group_ref="sample:fabricated@1.0.0"),
        artifact_sha256="c" * 64,
    )
    assert "biological_unit_assignment_group_mismatch" in reasons


def test_assignment_artifact_cannot_leave_declared_groups_unused() -> None:
    second_preparation = _ref("preparation:second")
    second_sample = _ref("sample:second")
    second_binding = BiologicalUnitBinding(
        analysis_unit_ref=second_preparation,
        analysis_unit_kind="preparation",
        independence_group_ref=second_sample,
        independence_group_kind="sample",
        preparation_ref=second_preparation,
        sample_ref=second_sample,
    )
    reasons = biological_unit_assignment_reasons(
        manifest=_manifest(unit_bindings=[_binding(), second_binding]),
        artifact=_assignment_artifact(),
        artifact_sha256="c" * 64,
    )
    assert "biological_unit_assignment_unused_analysis_unit" in reasons
    assert "biological_unit_assignment_unused_independence_group" in reasons


def test_product_definition_card_cannot_self_assert_review_authority() -> None:
    with pytest.raises(ValidationError, match="Input should be 'draft'"):
        ProductDefinitionCard(
            object_version="0.1.0",
            product_definition_id="product-definition:demo",
            definition_version="1.0.0",
            state_role_map_ref=_ref("state-role-map:demo"),
            supported_assays=["scRNA-seq"],
            review_state="reviewed",
            provenance_refs=[_ref("provenance:demo")],
        )


def test_product_case_requires_complete_manifest_binding() -> None:
    common = {
        "object_version": "0.1.0",
        "product_case_id": "product-case:demo",
        "case_version": "1.0.0",
        "product_definition_ref": _ref("product-definition:demo"),
        "source_unit_kind": "preparation",
        "sample_or_preparation_ref": _ref("preparation:demo"),
        "measurement_spec_ref": _ref("measurement-spec:demo"),
        "assay": "scRNA-seq",
        "provenance_refs": [_ref("provenance:demo")],
        "created_at": datetime(2026, 8, 25, tzinfo=timezone.utc),
    }
    with pytest.raises(ValidationError, match="must be supplied together"):
        ProductCase(
            **common,
            biological_unit_manifest_ref=_ref("biological-unit-manifest:demo"),
        )



    with pytest.raises(
        ValidationError,
        match="independence group references require",
    ):
        ProductCase(
            **common,
            independence_group_refs=[_ref("sample:demo")],
        )
def test_data_view_requires_paired_manifest_reference_and_checksum() -> None:
    with pytest.raises(ValidationError, match="must be paired"):
        DataViewBinding(
            view_id="data-view:demo@1.0.0",
            view_kind="qc_selected_observations",
            artifact_id="artifact:demo",
            sha256="a" * 64,
            parent_asset_id="asset:demo",
            parent_asset_sha256="b" * 64,
            matrix_location="X",
            matrix_semantics="raw_counts",
            n_observations=8,
            observation_ids_sha256="c" * 64,
            biological_unit_manifest_ref="biological-unit-manifest:demo@1.0.0",
        )


@pytest.mark.parametrize(
    "schema_ref",
    [
        "bridge://schemas/biological-unit-assignment/v0.1",
        "bridge://schemas/biological-unit-manifest/v0.1",
        "bridge://schemas/measurement-result/v0.2",
        "bridge://schemas/measurement-spec/v0.2",
        "bridge://schemas/qc-readiness-profile/v0.2",
        "bridge://schemas/cell-state-evidence-profile/v0.2",
        "bridge://schemas/product-case/v0.1",
        "bridge://schemas/product-definition-card/v0.1",
    ],
)
def test_shared_contract_schemas_are_packaged(schema_ref: str) -> None:
    assert load_schema(schema_ref)["$id"] == schema_ref


def test_public_manifest_schema_enforces_structural_invariants() -> None:
    schema = load_schema("bridge://schemas/biological-unit-manifest/v0.1")
    validator = Draft202012Validator(schema)
    valid = _manifest().model_dump(mode="json")
    assert not list(validator.iter_errors(valid))

    invalid_review = deepcopy(valid)
    invalid_review.update(
        {
            "lineage_state": "reviewed",
            "review_gate_ref": _ref("biological-unit-review:demo").model_dump(
                mode="json"
            ),
            "review_gate_sha256": "d" * 64,
        }
    )
    empty_bindings = deepcopy(valid)
    empty_bindings["unit_bindings"] = []
    technical_group = deepcopy(valid)
    technical_group["independence_group_kind"] = "capture"
    for payload in (invalid_review, empty_bindings, technical_group):
        assert list(validator.iter_errors(payload))


def test_public_product_schemas_cannot_claim_unbound_or_reviewed_state() -> None:
    product_case = ProductCase(
        object_version="0.1.0",
        product_case_id="product-case:demo",
        case_version="1.0.0",
        product_definition_ref=_ref("product-definition:demo"),
        source_unit_kind="preparation",
        sample_or_preparation_ref=_ref("preparation:demo"),
        measurement_spec_ref=_ref("measurement-spec:demo"),
        assay="scRNA-seq",
        provenance_refs=[_ref("provenance:demo")],
        created_at=datetime(2026, 8, 25, tzinfo=timezone.utc),
    ).model_dump(mode="json")
    case_validator = Draft202012Validator(
        load_schema("bridge://schemas/product-case/v0.1")
    )
    assert not list(case_validator.iter_errors(product_case))

    partial_binding = deepcopy(product_case)
    partial_binding["biological_unit_manifest_ref"] = _ref(
        "biological-unit-manifest:demo"
    ).model_dump(mode="json")
    unbound_groups = deepcopy(product_case)
    unbound_groups["independence_group_refs"] = [
        _ref("sample:demo").model_dump(mode="json")
    ]
    assert list(case_validator.iter_errors(partial_binding))
    assert list(case_validator.iter_errors(unbound_groups))

    card = ProductDefinitionCard(
        object_version="0.1.0",
        product_definition_id="product-definition:demo",
        definition_version="1.0.0",
        state_role_map_ref=_ref("state-role-map:demo"),
        supported_assays=["scRNA-seq"],
        review_state="draft",
        provenance_refs=[_ref("provenance:demo")],
    ).model_dump(mode="json")
    card_validator = Draft202012Validator(
        load_schema("bridge://schemas/product-definition-card/v0.1")
    )
    assert not list(card_validator.iter_errors(card))
    card["review_state"] = "reviewed"
    assert list(card_validator.iter_errors(card))


def test_public_measurement_schema_rejects_false_numeric_evidence() -> None:
    validator = Draft202012Validator(
        load_schema("bridge://schemas/measurement-result/v0.2")
    )
    valid = MeasurementResultV2(
        **_measurement_payload()
    ).model_dump(mode="json")
    assert not list(validator.iter_errors(valid))

    zero_denominator = deepcopy(valid)
    zero_denominator.update({"numerator": 0, "denominator": 0})
    missing_zero = deepcopy(valid)
    missing_zero.update({"evidence_state": "missing", "raw_value": 0})
    unpaired_source = deepcopy(valid)
    unpaired_source["source_execution_state"] = "succeeded"
    for payload in (zero_denominator, missing_zero, unpaired_source):
        assert list(validator.iter_errors(payload))


def _data_view_with_manifest() -> DataViewBinding:
    return DataViewBinding(
        view_id="data-view:demo@1.0.0",
        view_kind="qc_selected_observations",
        artifact_id="artifact:demo",
        sha256="a" * 64,
        parent_asset_id="asset:demo",
        parent_asset_sha256="b" * 64,
        matrix_location="X",
        matrix_semantics="raw_counts",
        n_observations=8,
        observation_ids_sha256=observation_ids_sha256(
            [f"demo-observation-{index:04d}" for index in range(8)]
        ),
        sample_or_preparation_ref="preparation:demo@1.0.0",
        biological_unit_manifest_ref=(
            "biological-unit-manifest:demo@1.0.0"
        ),
        biological_unit_manifest_sha256="d" * 64,
    )


def test_public_profile_schemas_require_paired_lineage_references() -> None:
    view = _data_view_with_manifest()
    qc = QCReadinessProfileV2(
        profile_id="qc-profile:demo",
        input_level="analysis_ready",
        assay="scRNA-seq",
        readiness_state="ready",
        schema_integrity={},
        metadata_completeness={},
        matrix_provenance={},
        upstream_library_qc={},
        cell_qc={},
        doublet_assessment={},
        cell_calling_assessment={},
        ambient_assessment={},
        data_views={},
        module_eligibility={},
        selected_data_view=view,
    ).model_dump(mode="json")
    qc_validator = Draft202012Validator(
        load_schema("bridge://schemas/qc-readiness-profile/v0.2")
    )
    assert not list(qc_validator.iter_errors(qc))
    qc["selected_data_view"]["biological_unit_manifest_sha256"] = None
    assert list(qc_validator.iter_errors(qc))

    profile = CellStateEvidenceProfileV2(
        profile_id="cell-state-profile:demo",
        assay="scRNA-seq",
        measurement_spec_id="measurement-spec:demo",
        measurement_spec_status="candidate",
        annotation_vocabulary_ref="annotation-vocabulary:demo@1.0.0",
        reference_snapshot_ref="reference-manifest:demo@1.0.0",
        n_observations=8,
        n_genes=100,
        denominator="qc_selected_observations",
        label_levels={},
        source_support={},
        marker_program_evidence={},
        prediction_sets={},
        composition={"records": []},
        gene_coverage={},
        modality_sensitivity={},
        upstream_qc_profile_ref="qc-profile:demo",
        upstream_qc_profile_sha256="e" * 64,
        input_data_view=view,
    ).model_dump(mode="json")
    profile_validator = Draft202012Validator(
        load_schema("bridge://schemas/cell-state-evidence-profile/v0.2")
    )
    assert not list(profile_validator.iter_errors(profile))
    profile["upstream_qc_profile_sha256"] = None
    assert list(profile_validator.iter_errors(profile))


def test_profile_lineage_rejects_unrelated_product_case_source_unit() -> None:
    manifest = _manifest()
    view = _data_view_with_manifest()
    qc = QCReadinessProfileV2(
        profile_id="qc-profile:demo",
        input_level="analysis_ready",
        assay="scRNA-seq",
        readiness_state="ready",
        schema_integrity={},
        metadata_completeness={},
        matrix_provenance={},
        upstream_library_qc={},
        cell_qc={},
        doublet_assessment={},
        cell_calling_assessment={},
        ambient_assessment={},
        data_views={},
        module_eligibility={},
        selected_data_view=view,
    )
    cell_state = CellStateEvidenceProfileV2(
        profile_id="cell-state-profile:demo",
        assay="scRNA-seq",
        measurement_spec_id="measurement-spec:demo",
        measurement_spec_version="1.0.0",
        measurement_spec_status="candidate",
        annotation_vocabulary_ref="annotation-vocabulary:demo@1.0.0",
        reference_snapshot_ref="reference-manifest:demo@1.0.0",
        n_observations=8,
        n_genes=100,
        denominator="qc_selected_observations",
        label_levels={},
        source_support={},
        marker_program_evidence={},
        prediction_sets={},
        composition={"records": []},
        gene_coverage={},
        modality_sensitivity={},
        upstream_qc_profile_ref=qc.profile_id,
        upstream_qc_profile_sha256="e" * 64,
        input_data_view=view,
    )
    product_case = ProductCase(
        object_version="0.1.0",
        product_case_id="product-case:demo",
        case_version="1.0.0",
        product_definition_ref=_ref("product-definition:demo"),
        source_unit_kind="preparation",
        sample_or_preparation_ref=_ref("preparation:unrelated"),
        independence_group_refs=[_ref("sample:demo")],
        biological_unit_manifest_ref=manifest.ref,
        biological_unit_manifest_sha256="d" * 64,
        independence_scope_ref=manifest.independence_scope_ref,
        measurement_spec_ref=_ref("measurement-spec:demo"),
        assay="scRNA-seq",
        provenance_refs=[_ref("provenance:demo")],
        created_at=datetime(2026, 8, 25, tzinfo=timezone.utc),
    )

    reasons = profile_lineage_reasons(
        product_case=product_case,
        cell_state_profile=cell_state,
        qc_profile=qc,
        biological_unit_manifest=manifest,
        biological_unit_assignment_artifact=_assignment_artifact(),
        input_sha256_by_role={
            "biological_unit_assignment": "c" * 64,
            "biological_unit_manifest": "d" * 64,
            "qc_readiness_profile": "e" * 64,
        },
    )
    assert "product_case_source_unit_binding_mismatch" in reasons
