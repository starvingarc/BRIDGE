from __future__ import annotations

from pathlib import Path

from bridge.domain import ProductCase, SampleRecord
from bridge.planner import PlanBuilder
from bridge.toolkit.contracts import InputAsset


def _case(tmp_path: Path, *, status: str = "confirmed") -> ProductCase:
    asset_path = tmp_path / "product.h5ad"
    asset_path.touch()
    asset = InputAsset(
        asset_id="asset-1",
        path=asset_path.resolve(),
        format="h5ad",
        input_level="analysis_ready",
        matrix_semantics="normalized_expression",
        assay="scRNA-seq",
    )
    return ProductCase(
        case_id="case-1",
        version="0.1",
        status=status,
        product_type="mDA progenitor preparation",
        target_cell_type="midbrain dopaminergic progenitor",
        differentiation_stage="D16",
        intended_use="research evaluation",
        assay="scRNA-seq",
        product_definition_card_ref="card://pd-mda/v0.1",
        reference_policy_ref="reference-policy://pd-mda/v0.1",
        prior_snapshot_ref="prior://pd-mda/v0.1",
        assets=[asset],
        samples=[
            SampleRecord(
                sample_id="sample-1",
                preparation_id="prep-1",
                asset_ids=[asset.asset_id],
                data_role="evaluation",
                sampling_context="pre-transplant",
            )
        ],
    )


def test_plan_builder_is_deterministic_and_keeps_scaffolds_skipped(tmp_path: Path) -> None:
    builder = PlanBuilder()
    case = _case(tmp_path)

    first = builder.build(
        case,
        output_root=tmp_path / "runs",
        knowledge_snapshot_ref="knowledge://p0/2026-08-12",
    )
    second = builder.build(
        case,
        output_root=tmp_path / "runs",
        knowledge_snapshot_ref="knowledge://p0/2026-08-12",
    )

    assert first == second
    assert first.steps[0].tool_id == "P0-01"
    assert first.steps[0].disposition == "execute"
    assert first.steps[2].disposition == "skip"
    assert first.steps[2].reason_codes == ["upstream_step_not_executable"]
    assert first.steps[-1].tool_id == "P0-12"


def test_plan_builder_rejects_unconfirmed_case(tmp_path: Path) -> None:
    try:
        PlanBuilder().build(
            _case(tmp_path, status="draft"),
            output_root=tmp_path / "runs",
            knowledge_snapshot_ref="knowledge://p0/2026-08-12",
        )
    except ValueError as exc:
        assert str(exc) == "case_not_confirmed"
    else:
        raise AssertionError("draft case unexpectedly produced a plan")
