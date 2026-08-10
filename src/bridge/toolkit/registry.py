from __future__ import annotations

from importlib.resources import files
from typing import Iterable
from uuid import uuid4

import yaml

from bridge.toolkit.contracts import (
    ExecutionState,
    EligibilityResult,
    InputAsset,
    ImplementationState,
    ToolPackageSpec,
    ToolRequest,
    ToolRun,
)


class ToolRegistry:
    def __init__(self, specs: Iterable[ToolPackageSpec]) -> None:
        by_id = {spec.tool_id: spec for spec in specs}
        if len(by_id) != 12:
            raise ValueError(f"Expected 12 unique Tool Packages, found {len(by_id)}")
        self._specs = by_id

    @classmethod
    def load_default(cls) -> "ToolRegistry":
        resource_root = files("bridge.tool_packages.specs")
        specs: list[ToolPackageSpec] = []
        for resource in sorted(resource_root.iterdir(), key=lambda item: item.name):
            if resource.name.endswith(".yaml"):
                payload = yaml.safe_load(resource.read_text(encoding="utf-8"))
                specs.append(ToolPackageSpec.model_validate(payload))
        return cls(specs)

    def ids(self) -> list[str]:
        return sorted(self._specs)

    def list(self) -> list[ToolPackageSpec]:
        return [self._specs[tool_id] for tool_id in self.ids()]

    def describe(self, tool_id: str) -> ToolPackageSpec:
        try:
            return self._specs[tool_id]
        except KeyError as exc:
            raise KeyError(f"Unknown Tool Package: {tool_id}") from exc

    def read_card(self, tool_id: str) -> str:
        spec = self.describe(tool_id)
        expected_ref = f"bridge://tool-cards/{tool_id}"
        if spec.card_ref != expected_ref:
            raise ValueError(f"Unexpected Tool Card reference for {tool_id}: {spec.card_ref}")
        resource = files("bridge.tool_packages.cards").joinpath(f"{tool_id}.md")
        if not resource.is_file():
            raise FileNotFoundError(f"Missing packaged Tool Card for {tool_id}")
        return resource.read_text(encoding="utf-8")

    def resolve_schema(self, schema_ref: str) -> dict:
        from bridge.toolkit.schemas import load_schema

        return load_schema(schema_ref)

    def check_eligibility(self, request: ToolRequest) -> EligibilityResult:
        spec = self.describe(request.tool_id)
        if request.tool_version is not None and request.tool_version != spec.version:
            return EligibilityResult(
                tool_id=request.tool_id,
                eligible=False,
                reason_codes=["tool_version_mismatch"],
            )
        if spec.implementation_state is not ImplementationState.IMPLEMENTED:
            return EligibilityResult(
                tool_id=request.tool_id,
                eligible=False,
                reason_codes=["tool_package_not_implemented"],
            )
        if request.tool_id == "P0-01":
            return self._check_input_qc_eligibility(request)
        return EligibilityResult(
            tool_id=request.tool_id,
            eligible=False,
            reason_codes=["executor_not_registered"],
        )

    @staticmethod
    def _check_input_qc_eligibility(request: ToolRequest) -> EligibilityResult:
        if len(request.assets) != 1:
            return EligibilityResult(
                tool_id=request.tool_id,
                eligible=False,
                reason_codes=["exactly_one_expression_asset_required"],
            )
        asset: InputAsset = request.assets[0]
        reasons: list[str] = []
        if asset.format not in {"h5ad", "10x_h5", "10x_mtx"}:
            reasons.append("unsupported_expression_format")
        if not asset.path.exists():
            reasons.append("input_asset_not_found")
        if asset.assay not in {"scRNA-seq", "snRNA-seq"}:
            reasons.append("assay_must_be_declared")
        if asset.matrix_semantics not in {"raw_counts", "normalized_expression"}:
            reasons.append("matrix_semantics_must_be_declared")
        if asset.format in {"10x_h5", "10x_mtx"} and asset.matrix_semantics != "raw_counts":
            reasons.append("10x_input_requires_raw_counts_semantics")
        if asset.input_level.value == "droplet_ready" and not (
            asset.metadata.get("capture_id") or asset.metadata.get("capture_id_column")
        ):
            reasons.append("droplet_ready_requires_capture_id")
        if request.measurement_spec_ref is not None:
            from bridge.tool_packages.p0_01_input_qc.measurement_specs import load_measurement_spec

            measurement_spec = load_measurement_spec(request.measurement_spec_ref)
            if measurement_spec is None:
                reasons.append("measurement_spec_not_found")
            else:
                if measurement_spec.assay != asset.assay:
                    reasons.append("measurement_spec_assay_mismatch")
                supported_levels = measurement_spec.input_contract.get("supported_levels", [])
                if asset.input_level.value not in supported_levels:
                    reasons.append("measurement_spec_input_level_mismatch")
        if asset.path.is_dir() and request.output_dir.resolve().is_relative_to(asset.path.resolve()):
            reasons.append("output_dir_overlaps_input_asset")
        return EligibilityResult(tool_id=request.tool_id, eligible=not reasons, reason_codes=reasons)

    def run(self, request: ToolRequest) -> ToolRun:
        spec = self.describe(request.tool_id)
        if request.tool_version is not None and request.tool_version != spec.version:
            return ToolRun(
                run_id=f"run-{uuid4().hex}",
                request=request,
                implementation_state=spec.implementation_state,
                execution_state=ExecutionState.FAILED,
                tool_version=spec.version,
                environment_spec_id=spec.environment_spec_id,
                reason_codes=["tool_version_mismatch"],
            )
        if spec.implementation_state is ImplementationState.SCAFFOLD:
            return ToolRun(
                run_id=f"run-{uuid4().hex}",
                request=request,
                implementation_state=spec.implementation_state,
                execution_state=ExecutionState.NOT_IMPLEMENTED,
                tool_version=spec.version,
                environment_spec_id=spec.environment_spec_id,
                reason_codes=["tool_package_not_implemented"],
            )
        eligibility = self.check_eligibility(request)
        if not eligibility.eligible:
            return ToolRun(
                run_id=f"run-{uuid4().hex}",
                request=request,
                implementation_state=spec.implementation_state,
                execution_state=ExecutionState.FAILED,
                tool_version=spec.version,
                environment_spec_id=spec.environment_spec_id,
                reason_codes=eligibility.reason_codes,
                warnings=eligibility.warnings,
            )
        if request.tool_id == "P0-01":
            from bridge.tool_packages.p0_01_input_qc.executor import run_input_audit_qc

            return run_input_audit_qc(request, spec)
        raise RuntimeError(f"No executor registered for implemented tool {request.tool_id}")
