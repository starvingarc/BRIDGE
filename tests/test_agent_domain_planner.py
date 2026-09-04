from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from bridge.domain import (
    AnalysisPlan,
    CaseInputBundle,
    PlanStep,
    approve_plan,
)
from bridge.planner import PlanBuilder
from bridge.toolkit.contracts import (
    EligibilityResult,
    ImplementationState,
    InputAsset,
    ToolPackageSpec,
    ToolPackageSpecV2,
    ToolRequest,
    ToolRequestV2,
)


def _asset(tmp_path: Path, *, asset_id: str = "asset-1") -> InputAsset:
    path = tmp_path / f"{asset_id}.h5ad"
    path.write_bytes(b"synthetic-upload")
    return InputAsset(
        asset_id=asset_id,
        path=path.resolve(),
        format="h5ad",
        input_level="analysis_ready",
        checksum=hashlib.sha256(path.read_bytes()).hexdigest(),
        matrix_semantics="normalized_expression",
        assay="scRNA-seq",
    )


def _bundle(tmp_path: Path) -> CaseInputBundle:
    return CaseInputBundle(
        bundle_id="upload-bundle-1",
        version="0.1",
        assets=[_asset(tmp_path)],
    )


def _v1_spec() -> ToolPackageSpec:
    return ToolPackageSpec(
        tool_id="P0-01",
        name="Input QC",
        version="0.1.3",
        summary="test",
        implementation_state=ImplementationState.IMPLEMENTED,
        scientific_status="candidate",
        environment_spec_id="env:test",
        input_schema_ref="bridge://schemas/tool-request/v0.1",
        output_schema_ref="bridge://schemas/tool-run/v0.1",
        method_ids=["method:test"],
        card_ref="card:test",
    )


def _v2_spec(tool_id: str) -> ToolPackageSpecV2:
    return ToolPackageSpecV2(
        tool_id=tool_id,
        name=tool_id,
        version="0.1.0",
        summary="test",
        implementation_state=ImplementationState.IMPLEMENTED,
        scientific_status="candidate/shadow",
        environment_spec_id="env:test",
        input_schema_ref="bridge://schemas/tool-request/v0.2",
        output_schema_ref="bridge://schemas/tool-run/v0.2",
        method_ids=["method:test"],
        card_ref="card:test",
        adapter_ref="bridge.tool_packages.test:adapter",
        result_schema_ref="bridge://schemas/test-result/v0.1",
    )


class FakeRegistry:
    def __init__(self, *, refused_request: str | None = None) -> None:
        self._specs = {
            "P0-01": _v1_spec(),
            "P0-03": _v2_spec("P0-03"),
            "P0-04": _v2_spec("P0-04"),
        }
        self.refused_request = refused_request

    def describe(self, tool_id: str):
        return self._specs[tool_id]

    def check_eligibility(self, request):
        refused = request.request_id == self.refused_request
        return EligibilityResult(
            tool_id=request.tool_id,
            eligible=not refused,
            reason_codes=["test_ineligible"] if refused else [],
        )


def _approve(plan: AnalysisPlan) -> AnalysisPlan:
    return approve_plan(
        plan,
        approver_id="reviewer-1",
        authority_ref="local-review-record",
        approved_at=datetime(2026, 9, 4, tzinfo=timezone.utc),
    )


def test_input_bundle_requires_content_bound_assets(tmp_path: Path) -> None:
    asset = _asset(tmp_path).model_copy(update={"checksum": None})
    with pytest.raises(ValidationError, match="checksum"):
        CaseInputBundle(bundle_id="bundle", version="0.1", assets=[asset])


def test_input_bundle_defensively_freezes_asset_metadata(tmp_path: Path) -> None:
    asset = _asset(tmp_path)
    source = {"nested": {"labels": ["declared"]}}
    bundle = CaseInputBundle(
        bundle_id="bundle",
        version="0.1",
        assets=[asset.model_copy(update={"metadata": source})],
    )
    source["nested"]["labels"].append("changed")
    assert bundle.model_dump(mode="json")["assets"][0]["metadata"] == {
        "nested": {"labels": ["declared"]}
    }


def test_upload_bundle_builds_only_selected_qc_step(tmp_path: Path) -> None:
    output_root = tmp_path / "private-output"
    plan = PlanBuilder(FakeRegistry()).build(
        _bundle(tmp_path),
        output_root=output_root,
        knowledge_snapshot_ref="knowledge:test",
    )

    assert plan.status == "draft"
    assert [step.tool_id for step in plan.steps] == ["P0-01"]
    assert plan.steps[0].disposition == "execute"
    assert plan.steps[0].depends_on == ()
    assert plan.steps[0].approved_request_sha256
    assert os.stat(output_root).st_mode & 0o077 == 0


def test_explicit_downstream_requests_are_independent_by_default(tmp_path: Path) -> None:
    placeholder = (tmp_path / "placeholder").resolve()
    requests = [
        ToolRequestV2(
            request_id="development",
            tool_id="P0-03",
            output_dir=placeholder,
        ),
        ToolRequestV2(
            request_id="compatibility",
            tool_id="P0-04",
            output_dir=placeholder,
        ),
    ]
    plan = PlanBuilder(FakeRegistry()).build(
        _bundle(tmp_path),
        output_root=tmp_path / "private-output",
        knowledge_snapshot_ref="knowledge:test",
        requests=requests,
        include_input_qc=False,
    )

    assert [step.tool_id for step in plan.steps] == ["P0-03", "P0-04"]
    assert all(step.depends_on == () for step in plan.steps)
    assert all(step.disposition == "execute" for step in plan.steps)


def test_only_explicit_dependencies_propagate_a_skip(tmp_path: Path) -> None:
    requests = [
        ToolRequestV2(
            request_id="first",
            tool_id="P0-03",
            output_dir=(tmp_path / "placeholder").resolve(),
        ),
        ToolRequestV2(
            request_id="second",
            tool_id="P0-04",
            output_dir=(tmp_path / "placeholder").resolve(),
        ),
    ]
    plan = PlanBuilder(FakeRegistry(refused_request="first")).build(
        _bundle(tmp_path),
        output_root=tmp_path / "private-output",
        knowledge_snapshot_ref="knowledge:test",
        requests=requests,
        dependencies={"second": ["first"]},
        include_input_qc=False,
    )

    assert plan.steps[0].reason_codes == ("test_ineligible",)
    assert plan.steps[1].reason_codes == ("explicit_dependency_not_executable",)


def test_request_asset_must_belong_to_bundle(tmp_path: Path) -> None:
    other = _asset(tmp_path, asset_id="other")
    request = ToolRequest(
        request_id="other-qc",
        tool_id="P0-01",
        output_dir=(tmp_path / "placeholder").resolve(),
        assets=[other],
    )
    with pytest.raises(ValueError, match="asset_not_in_input_bundle"):
        PlanBuilder(FakeRegistry()).build(
            _bundle(tmp_path),
            output_root=tmp_path / "private-output",
            knowledge_snapshot_ref="knowledge:test",
            requests=[request],
            include_input_qc=False,
        )


def test_approval_receipt_binds_complete_plan(tmp_path: Path) -> None:
    draft = PlanBuilder(FakeRegistry()).build(
        _bundle(tmp_path),
        output_root=tmp_path / "private-output",
        knowledge_snapshot_ref="knowledge:test",
    )
    approved = _approve(draft)

    assert approved.approval_receipt is not None
    assert approved.approval_receipt.plan_sha256 == approved.approval_sha256()

    payload = approved.model_dump(mode="json")
    payload["knowledge_snapshot_ref"] = "knowledge:changed"
    with pytest.raises(ValidationError, match="approval receipt digest mismatch"):
        AnalysisPlan.model_validate(payload)


def test_approved_plan_cannot_be_constructed_without_receipt(tmp_path: Path) -> None:
    draft = PlanBuilder(FakeRegistry()).build(
        _bundle(tmp_path),
        output_root=tmp_path / "private-output",
        knowledge_snapshot_ref="knowledge:test",
    )
    payload = draft.model_dump(mode="json")
    payload["status"] = "approved"
    with pytest.raises(ValidationError, match="requires an approval receipt"):
        AnalysisPlan.model_validate(payload)


def test_plan_step_rejects_a_forged_request_digest() -> None:
    with pytest.raises(ValidationError, match="approved request digest mismatch"):
        PlanStep(
            step_id="step-1",
            tool_id="P0-01",
            tool_version="0.1.3",
            disposition="execute",
            approved_request_json=json.dumps({"tool_id": "P0-01"}),
            approved_request_sha256="0" * 64,
            output_directory={"path": "/private/output", "device": 1, "inode": 1},
            environment_spec_id="env:test",
            input_schema_ref="input:test",
            output_schema_ref="output:test",
            implementation_state="implemented",
            scientific_status="candidate",
        )


def test_planner_rejects_non_private_existing_output_root(tmp_path: Path) -> None:
    root = tmp_path / "shared"
    root.mkdir(mode=0o755)
    root.chmod(0o755)
    with pytest.raises(ValueError, match="private_directory_permissions_invalid"):
        PlanBuilder(FakeRegistry()).build(
            _bundle(tmp_path),
            output_root=root,
            knowledge_snapshot_ref="knowledge:test",
        )


def test_planner_rejects_symlinked_output_component(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir(mode=0o700)
    link = tmp_path / "link"
    link.symlink_to(target, target_is_directory=True)
    with pytest.raises(ValueError, match="private_path_not_directory"):
        PlanBuilder(FakeRegistry()).build(
            _bundle(tmp_path),
            output_root=link,
            knowledge_snapshot_ref="knowledge:test",
        )
