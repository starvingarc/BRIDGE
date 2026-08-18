from __future__ import annotations

from pathlib import Path
import hashlib
import json

from bridge.domain import ProductCase, SampleRecord
from bridge.planner import PlanBuilder
from bridge.toolkit.contracts import EligibilityResult, InputAsset, StructuredInputRef
from bridge.toolkit.registry import ToolRegistry


def _case(
    tmp_path: Path, *, status: str = "confirmed", asset_count: int = 1
) -> ProductCase:
    assets = []
    for index in range(asset_count):
        asset_path = tmp_path / f"product-{index + 1}.h5ad"
        asset_path.touch()
        assets.append(
            InputAsset(
                asset_id=f"asset-{index + 1}",
                path=asset_path.resolve(),
                format="h5ad",
                input_level="analysis_ready",
                matrix_semantics="normalized_expression",
                assay="scRNA-seq",
            )
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
        assets=assets,
        samples=[
            SampleRecord(
                sample_id="sample-1",
                preparation_id="prep-1",
                asset_ids=[asset.asset_id for asset in assets],
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
    assert first.steps[2].reason_codes == ("upstream_step_not_executable",)
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


def test_plan_builder_expands_input_qc_per_asset_without_collapsing_steps(
    tmp_path: Path,
) -> None:
    plan = PlanBuilder().build(
        _case(tmp_path, asset_count=2),
        output_root=tmp_path / "runs",
        knowledge_snapshot_ref="knowledge://p0/2026-08-12",
    )

    qc_steps = [step for step in plan.steps if step.tool_id == "P0-01"]
    assert [step.step_id for step in qc_steps] == [
        "step-p0-01-asset-001",
        "step-p0-01-asset-002",
    ]
    requests = [json.loads(step.approved_request_json or "{}") for step in qc_steps]
    assert [[asset["asset_id"] for asset in item["assets"]] for item in requests] == [
        ["asset-1"],
        ["asset-2"],
    ]


class _StructuredPlanningRegistry:
    def __init__(self) -> None:
        self._delegate = ToolRegistry.load_default()

    def list(self):
        return self._delegate.list()

    def check_eligibility(self, request):
        if request.tool_id == "P0-08":
            return EligibilityResult(tool_id=request.tool_id, eligible=True)
        return self._delegate.check_eligibility(request)


def test_structured_tool_requires_explicit_inputs_and_is_not_blocked_by_scaffolds(
    tmp_path: Path,
) -> None:
    structured_path = (tmp_path / "gate.json").resolve()
    structured_path.write_text("{}", encoding="utf-8")
    structured = StructuredInputRef(
        input_id="gate-1",
        role="gate_rule_spec",
        schema_ref="bridge://schemas/evidence-gate-rule-spec/v0.1",
        object_version="0.1",
        path=structured_path,
        sha256=hashlib.sha256(b"{}").hexdigest(),
    )
    builder = PlanBuilder(_StructuredPlanningRegistry())

    missing = builder.build(
        _case(tmp_path),
        output_root=tmp_path / "runs-missing",
        knowledge_snapshot_ref="knowledge://p0/2026-08-12",
    )
    supplied = builder.build(
        _case(tmp_path),
        output_root=tmp_path / "runs-supplied",
        knowledge_snapshot_ref="knowledge://p0/2026-08-12",
        structured_input_bindings={"P0-08": [structured]},
    )

    missing_step = next(step for step in missing.steps if step.tool_id == "P0-08")
    supplied_step = next(step for step in supplied.steps if step.tool_id == "P0-08")
    assert missing_step.reason_codes == ("structured_inputs_not_selected",)
    assert supplied_step.disposition == "execute"
    assert supplied_step.depends_on == ()
    assert json.loads(supplied_step.approved_request_json or "{}")["object_inputs"][0][
        "input_id"
    ] == "gate-1"
