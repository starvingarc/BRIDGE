from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Mapping, Sequence

from bridge.domain.models import (
    AnalysisPlan,
    CaseInputBundle,
    OutputDirectoryBinding,
    PlanStep,
    StepDisposition,
)
from bridge.storage.private_paths import ensure_private_directory
from bridge.toolkit.contracts import (
    ToolPackageSpecV2,
    ToolRequest,
    ToolRequestV2,
)
from bridge.toolkit.registry import ToolRegistry


ToolRequestModel = ToolRequest | ToolRequestV2


def _canonical_json(value: object) -> str:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


class PlanBuilder:
    """Build an execution batch from already materialized tool requests.

    The builder adds upload QC requests and accepts explicit downstream requests.
    It does not infer scientific dependencies or manufacture missing objects.
    """

    def __init__(self, registry: ToolRegistry | None = None) -> None:
        self._registry = registry or ToolRegistry.load_default()

    def build(
        self,
        case: CaseInputBundle,
        *,
        output_root: Path,
        knowledge_snapshot_ref: str,
        requests: Sequence[ToolRequestModel] = (),
        dependencies: Mapping[str, Sequence[str]] | None = None,
        include_input_qc: bool = True,
    ) -> AnalysisPlan:
        output_root, _, _ = ensure_private_directory(output_root)
        bundle_identity = _canonical_json(
            {"bundle_id": case.bundle_id, "version": case.version}
        )
        bundle_key = "bundle-" + hashlib.sha256(bundle_identity.encode()).hexdigest()
        bundle_root, _, _ = ensure_private_directory(output_root / bundle_key)

        selected: list[ToolRequestModel] = []
        if include_input_qc:
            spec = self._registry.describe("P0-01")
            for index, asset in enumerate(case.assets, start=1):
                selected.append(
                    ToolRequest(
                        request_id=f"plan-{bundle_key}-p0-01-{index:03d}",
                        tool_id="P0-01",
                        tool_version=spec.version,
                        output_dir=bundle_root,
                        assets=[asset.to_toolkit_asset()],
                    )
                )
        selected.extend(requests)
        if not selected:
            raise ValueError("analysis_plan_requires_selected_request")

        request_ids = [request.request_id for request in selected]
        if len(request_ids) != len(set(request_ids)):
            raise ValueError("analysis_plan_request_ids_must_be_unique")
        dependencies = dependencies or {}
        unknown_dependency_sources = sorted(set(dependencies) - set(request_ids))
        if unknown_dependency_sources:
            raise ValueError("analysis_plan_dependency_source_unknown")

        declared_assets = {
            asset.asset_id: _canonical_json(asset.to_toolkit_asset())
            for asset in case.assets
        }
        steps: list[PlanStep] = []
        step_by_request: dict[str, str] = {}
        disposition_by_request: dict[str, StepDisposition] = {}
        for index, original in enumerate(selected, start=1):
            spec = self._registry.describe(original.tool_id)
            if original.tool_version not in {None, spec.version}:
                raise ValueError("analysis_plan_tool_version_mismatch")
            for asset in original.assets:
                if asset.checksum is None:
                    raise ValueError("analysis_plan_asset_checksum_missing")
                if declared_assets.get(asset.asset_id) != _canonical_json(asset):
                    raise ValueError("analysis_plan_asset_not_in_input_bundle")

            dependency_ids = tuple(dependencies.get(original.request_id, ()))
            if len(dependency_ids) != len(set(dependency_ids)):
                raise ValueError("analysis_plan_dependencies_must_be_unique")
            unknown = [item for item in dependency_ids if item not in step_by_request]
            if unknown:
                raise ValueError("analysis_plan_dependencies_must_precede_request")

            step_id = f"step-{index:03d}-{original.tool_id.lower()}"
            step_dir, device, inode = ensure_private_directory(
                bundle_root / f"{index:03d}-{original.tool_id.lower()}"
            )
            payload = original.model_dump(mode="python")
            payload["tool_version"] = spec.version
            payload["output_dir"] = step_dir
            request_type = ToolRequestV2 if isinstance(spec, ToolPackageSpecV2) else ToolRequest
            request = request_type.model_validate(payload)

            blocked = any(
                disposition_by_request[item] is StepDisposition.SKIP
                for item in dependency_ids
            )
            if blocked:
                disposition = StepDisposition.SKIP
                reasons = ("explicit_dependency_not_executable",)
                request_json = None
            else:
                eligibility = self._registry.check_eligibility(request)
                disposition = (
                    StepDisposition.EXECUTE
                    if eligibility.eligible
                    else StepDisposition.SKIP
                )
                reasons = tuple(eligibility.reason_codes)
                request_json = (
                    _canonical_json(request)
                    if disposition is StepDisposition.EXECUTE
                    else None
                )

            steps.append(
                PlanStep(
                    step_id=step_id,
                    tool_id=spec.tool_id,
                    tool_version=spec.version,
                    disposition=disposition,
                    depends_on=tuple(step_by_request[item] for item in dependency_ids),
                    reason_codes=reasons,
                    approved_request_json=request_json,
                    approved_request_sha256=(
                        hashlib.sha256(request_json.encode()).hexdigest()
                        if request_json is not None
                        else None
                    ),
                    output_directory=(
                        OutputDirectoryBinding(
                            path=step_dir,
                            device=device,
                            inode=inode,
                        )
                        if request_json is not None
                        else None
                    ),
                    environment_spec_id=spec.environment_spec_id,
                    input_schema_ref=spec.input_schema_ref,
                    output_schema_ref=spec.output_schema_ref,
                    implementation_state=spec.implementation_state.value,
                    scientific_status=spec.scientific_status,
                    result_schema_ref=(
                        spec.result_schema_ref
                        if isinstance(spec, ToolPackageSpecV2)
                        else None
                    ),
                )
            )
            step_by_request[original.request_id] = step_id
            disposition_by_request[original.request_id] = disposition

        bundle_sha256 = hashlib.sha256(_canonical_json(case).encode()).hexdigest()
        identity = {
            "input_bundle_sha256": bundle_sha256,
            "knowledge_snapshot_ref": knowledge_snapshot_ref,
            "steps": [step.model_dump(mode="json") for step in steps],
        }
        plan_digest = hashlib.sha256(_canonical_json(identity).encode()).hexdigest()[:16]
        return AnalysisPlan(
            plan_id=f"plan-{plan_digest}",
            version="0.3",
            input_bundle_ref=f"{case.bundle_id}@{case.version}",
            input_bundle_sha256=bundle_sha256,
            status="draft",
            knowledge_snapshot_ref=knowledge_snapshot_ref,
            steps=steps,
        )
