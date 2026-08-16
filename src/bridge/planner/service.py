from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Mapping

from bridge.domain import AnalysisPlan, PlanStep, ProductCase, StepDisposition
from bridge.toolkit.contracts import ToolRequest
from bridge.toolkit.registry import ToolRegistry


_DEPENDENCIES = {
    "P0-01": [],
    "P0-02": ["P0-01"],
    "P0-03": ["P0-02"],
    "P0-04": ["P0-03"],
    "P0-05": ["P0-04"],
    "P0-06": ["P0-05"],
    "P0-07": ["P0-06"],
    "P0-08": ["P0-07"],
    "P0-09": ["P0-08"],
    "P0-10": ["P0-09"],
    "P0-11": ["P0-10"],
    "P0-12": ["P0-01"],
}


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
    ) -> AnalysisPlan:
        if case.status.value != "confirmed":
            raise ValueError("case_not_confirmed")
        output_root = output_root.resolve()
        measurement_spec_refs = measurement_spec_refs or {}
        steps: list[PlanStep] = []
        dispositions: dict[str, StepDisposition] = {}

        for spec in self._registry.list():
            dependency_tools = _DEPENDENCIES[spec.tool_id]
            dependencies = [f"step-{tool_id.lower()}" for tool_id in dependency_tools]
            blocked = any(
                dispositions[tool_id] is StepDisposition.SKIP for tool_id in dependency_tools
            )
            measurement_spec_ref = measurement_spec_refs.get(spec.tool_id)
            if blocked:
                disposition = StepDisposition.SKIP
                reasons = ["upstream_step_not_executable"]
            elif spec.tool_id != "P0-01" and measurement_spec_ref is None:
                disposition = StepDisposition.SKIP
                reasons = ["measurement_spec_not_selected"]
            else:
                request = ToolRequest(
                    request_id=f"plan-{case.case_id}-{spec.tool_id.lower()}",
                    tool_id=spec.tool_id,
                    tool_version=spec.version,
                    output_dir=output_root / case.case_id / spec.tool_id.lower(),
                    assets=case.assets,
                    measurement_spec_ref=measurement_spec_ref,
                )
                eligibility = self._registry.check_eligibility(request)
                disposition = (
                    StepDisposition.EXECUTE if eligibility.eligible else StepDisposition.SKIP
                )
                reasons = eligibility.reason_codes
            dispositions[spec.tool_id] = disposition
            steps.append(
                PlanStep(
                    step_id=f"step-{spec.tool_id.lower()}",
                    tool_id=spec.tool_id,
                    tool_version=spec.version,
                    disposition=disposition,
                    depends_on=dependencies,
                    measurement_spec_ref=measurement_spec_ref,
                    reference_refs=[case.reference_policy_ref],
                    prior_refs=[case.prior_snapshot_ref],
                    reason_codes=reasons,
                )
            )

        identity_payload = {
            "case": case.model_dump(mode="json"),
            "knowledge_snapshot_ref": knowledge_snapshot_ref,
            "steps": [step.model_dump(mode="json") for step in steps],
        }
        digest = hashlib.sha256(
            json.dumps(identity_payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()[:16]
        return AnalysisPlan(
            plan_id=f"plan-{digest}",
            version="0.1",
            case_ref=f"{case.case_id}@{case.version}",
            status="draft",
            knowledge_snapshot_ref=knowledge_snapshot_ref,
            steps=steps,
        )
