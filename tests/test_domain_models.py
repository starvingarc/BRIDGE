from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from bridge.domain import AnalysisPlan, PlanStep, ProductCase, SampleRecord
from bridge.toolkit.contracts import InputAsset


def _asset(tmp_path: Path) -> InputAsset:
    return InputAsset(
        asset_id="asset-1",
        path=(tmp_path / "product.h5ad").resolve(),
        format="h5ad",
        input_level="analysis_ready",
        matrix_semantics="normalized_expression",
        assay="scRNA-seq",
    )


def test_product_case_requires_declared_sample_assets(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="unknown assets"):
        ProductCase(
            case_id="case-1",
            version="0.1",
            status="confirmed",
            product_type="mDA progenitor preparation",
            target_cell_type="midbrain dopaminergic progenitor",
            differentiation_stage="D16",
            intended_use="research evaluation",
            assay="scRNA-seq",
            product_definition_card_ref="card://pd-mda/v0.1",
            reference_policy_ref="reference-policy://pd-mda/v0.1",
            prior_snapshot_ref="prior://pd-mda/v0.1",
            assets=[_asset(tmp_path)],
            samples=[
                SampleRecord(
                    sample_id="sample-1",
                    preparation_id="prep-1",
                    asset_ids=["undeclared-asset"],
                    data_role="evaluation",
                    sampling_context="pre-transplant",
                )
            ],
        )


def test_analysis_plan_requires_ordered_dependencies() -> None:
    with pytest.raises(ValidationError, match="must precede"):
        AnalysisPlan(
            plan_id="plan-1",
            version="0.1",
            case_ref="case-1@0.1",
            status="draft",
            knowledge_snapshot_ref="knowledge://p0/2026-08-12",
            steps=[
                PlanStep(
                    step_id="step-p0-02",
                    tool_id="P0-02",
                    tool_version="0.1.0",
                    disposition="execute",
                    depends_on=["step-p0-01"],
                ),
                PlanStep(
                    step_id="step-p0-01",
                    tool_id="P0-01",
                    tool_version="0.1.0",
                    disposition="execute",
                ),
            ],
        )


def test_skipped_plan_step_requires_reason_code() -> None:
    with pytest.raises(ValidationError, match="requires a reason code"):
        PlanStep(
            step_id="step-p0-03",
            tool_id="P0-03",
            tool_version="0.1.0",
            disposition="skip",
        )


def test_plan_rejects_execute_step_after_skipped_dependency() -> None:
    with pytest.raises(ValidationError, match="depends on skipped steps"):
        AnalysisPlan(
            plan_id="plan-1",
            version="0.1",
            case_ref="case-1@0.1",
            status="draft",
            knowledge_snapshot_ref="knowledge://p0/2026-08-12",
            steps=[
                PlanStep(
                    step_id="step-p0-01",
                    tool_id="P0-01",
                    tool_version="0.1.0",
                    disposition="skip",
                    reason_codes=["input_missing"],
                ),
                PlanStep(
                    step_id="step-p0-02",
                    tool_id="P0-02",
                    tool_version="0.1.0",
                    disposition="execute",
                    depends_on=["step-p0-01"],
                ),
            ],
        )


def test_domain_identifiers_and_references_cannot_be_empty() -> None:
    with pytest.raises(ValidationError, match="at least 1 character"):
        SampleRecord(
            sample_id="",
            preparation_id="prep-1",
            asset_ids=["asset-1"],
            data_role="evaluation",
            sampling_context="pre-transplant",
        )
    with pytest.raises(ValidationError, match="must be nonempty"):
        PlanStep(
            step_id="step-p0-01",
            tool_id="P0-01",
            tool_version="0.1.0",
            disposition="skip",
            reason_codes=[""],
        )
    with pytest.raises(ValidationError, match="nonblank"):
        SampleRecord(
            sample_id="   ",
            preparation_id="prep-1",
            asset_ids=["asset-1"],
            data_role="evaluation",
            sampling_context="pre-transplant",
        )


def test_plan_collections_are_immutable_snapshots() -> None:
    dependencies = ["step-p0-01"]
    step = PlanStep(
        step_id="step-p0-02",
        tool_id="P0-02",
        tool_version="0.1.0",
        disposition="skip",
        depends_on=dependencies,
        reference_refs=["reference://v1"],
        reason_codes=["measurement_spec_not_selected"],
    )
    dependencies.append("step-p0-99")

    assert step.depends_on == ("step-p0-01",)
    assert isinstance(step.reference_refs, tuple)
