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
