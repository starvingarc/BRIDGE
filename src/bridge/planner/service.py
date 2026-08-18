from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Mapping, Sequence

from bridge.domain.models import AnalysisPlan, PlanStep, ProductCase, StepDisposition
from bridge.toolkit.contracts import (
    StructuredInputRef,
    ToolPackageSpecV2,
    ToolRequest,
    ToolRequestV2,
)
from bridge.toolkit.registry import ToolRegistry


# These are execution prerequisites, not a claim that every scientific package
# produces the next package's structured contract. P0-08/P0-09 therefore only
# become executable when their required immutable object inputs are supplied.
_DEPENDENCIES = {
    "P0-01": [],
    "P0-02": ["P0-01"],
    "P0-03": ["P0-02"],
    "P0-04": ["P0-03"],
    "P0-05": ["P0-04"],
    "P0-06": ["P0-05"],
    "P0-07": ["P0-06"],
    "P0-08": [],
    "P0-09": [],
    "P0-10": ["P0-09"],
    "P0-11": ["P0-10"],
    "P0-12": ["P0-01"],
}


def _canonical_json(value: object) -> str:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


class PlanBuilder:
    def __init__(self, registry: ToolRegistry | None = None) -> None:
        self._registry = registry or ToolRegistry.load_default()

    def build(
        self,
        case: ProductCase,
        *,
        output_root: Path,
        knowledge_snapshot_ref: str,
        measurement_spec_refs: Mapping[str, str] | None = None,
        structured_input_bindings: Mapping[
            str, Sequence[StructuredInputRef]
        ] | None = None,
    ) -> AnalysisPlan:
        if case.status.value != "confirmed":
            raise ValueError("case_not_confirmed")
        output_root = output_root.resolve()
        measurement_spec_refs = measurement_spec_refs or {}
        structured_input_bindings = structured_input_bindings or {}
        case_identity_json = _canonical_json(
            {"case_id": case.case_id, "case_version": case.version}
        )
        case_key = "case-" + hashlib.sha256(case_identity_json.encode()).hexdigest()
        case_output_root = (output_root / case_key).resolve()
        if not case_output_root.is_relative_to(output_root):
            raise ValueError("case_output_root_not_confined")
        steps: list[PlanStep] = []
        steps_by_tool: dict[str, list[PlanStep]] = {}

        for spec in self._registry.list():
            dependency_steps = [
                step
                for dependency_tool in _DEPENDENCIES[spec.tool_id]
                for step in steps_by_tool[dependency_tool]
            ]
            units = list(case.assets) if spec.tool_id == "P0-01" else [None]
            tool_steps: list[PlanStep] = []
            for unit_index, asset in enumerate(units, start=1):
                # Asset identifiers are provenance values, not path segments.
                suffix = (
                    f"-asset-{unit_index:03d}"
                    if asset is not None and len(units) > 1
                    else ""
                )
                step_id = f"step-{spec.tool_id.lower()}{suffix}"
                dependencies = tuple(step.step_id for step in dependency_steps)
                blocked = any(
                    step.disposition is StepDisposition.SKIP
                    for step in dependency_steps
                )
                measurement_spec_ref = measurement_spec_refs.get(spec.tool_id)
                object_inputs = tuple(structured_input_bindings.get(spec.tool_id, ()))

                request: ToolRequest | ToolRequestV2 | None = None
                if blocked:
                    disposition = StepDisposition.SKIP
                    reasons = ("upstream_step_not_executable",)
                elif isinstance(spec, ToolPackageSpecV2) and not object_inputs:
                    disposition = StepDisposition.SKIP
                    reasons = ("structured_inputs_not_selected",)
                elif (
                    not isinstance(spec, ToolPackageSpecV2)
                    and spec.tool_id != "P0-01"
                    and measurement_spec_ref is None
                ):
                    disposition = StepDisposition.SKIP
                    reasons = ("measurement_spec_not_selected",)
                else:
                    request_id = f"plan-{case_key}-{spec.tool_id.lower()}{suffix}"
                    output_dir = (
                        case_output_root / f"{spec.tool_id.lower()}{suffix}"
                    ).resolve()
                    if not output_dir.is_relative_to(output_root):
                        raise ValueError("tool_output_dir_not_confined")
                    if isinstance(spec, ToolPackageSpecV2):
                        request = ToolRequestV2(
                            request_id=request_id,
                            tool_id=spec.tool_id,
                            tool_version=spec.version,
                            output_dir=output_dir,
                            object_inputs=object_inputs,
                            measurement_spec_ref=measurement_spec_ref,
                        )
                    else:
                        request = ToolRequest(
                            request_id=request_id,
                            tool_id=spec.tool_id,
                            tool_version=spec.version,
                            output_dir=output_dir,
                            assets=(
                                [asset.to_toolkit_asset()]
                                if asset is not None
                                else [item.to_toolkit_asset() for item in case.assets]
                            ),
                            measurement_spec_ref=measurement_spec_ref,
                        )
                    eligibility = self._registry.check_case_eligibility(
                        request,
                        case_id=case.case_id,
                        case_version=case.version,
                    )
                    disposition = (
                        StepDisposition.EXECUTE
                        if eligibility.eligible
                        else StepDisposition.SKIP
                    )
                    reasons = tuple(eligibility.reason_codes)

                step = PlanStep(
                    step_id=step_id,
                    tool_id=spec.tool_id,
                    tool_version=spec.version,
                    disposition=disposition,
                    depends_on=dependencies,
                    measurement_spec_ref=measurement_spec_ref,
                    reference_refs=(case.reference_policy_ref,),
                    prior_refs=(case.prior_snapshot_ref,),
                    reason_codes=reasons,
                    approved_request_json=(
                        _canonical_json(request)
                        if disposition is StepDisposition.EXECUTE and request is not None
                        else None
                    ),
                    environment_spec_id=spec.environment_spec_id,
                    input_schema_ref=spec.input_schema_ref,
                    output_schema_ref=spec.output_schema_ref,
                    implementation_state=spec.implementation_state.value,
                    result_schema_ref=(
                        spec.result_schema_ref
                        if isinstance(spec, ToolPackageSpecV2)
                        else None
                    ),
                )
                steps.append(step)
                tool_steps.append(step)
            steps_by_tool[spec.tool_id] = tool_steps

        case_json = _canonical_json(case)
        case_digest = hashlib.sha256(case_json.encode()).hexdigest()
        identity_payload = {
            "case_contract_sha256": case_digest,
            "knowledge_snapshot_ref": knowledge_snapshot_ref,
            "steps": [step.model_dump(mode="json") for step in steps],
        }
        digest = hashlib.sha256(_canonical_json(identity_payload).encode()).hexdigest()[:16]
        return AnalysisPlan(
            plan_id=f"plan-{digest}",
            version="0.2",
            case_ref=f"{case.case_id}@{case.version}",
            case_id=case.case_id,
            case_version=case.version,
            case_contract_sha256=case_digest,
            status="draft",
            knowledge_snapshot_ref=knowledge_snapshot_ref,
            steps=steps,
        )
