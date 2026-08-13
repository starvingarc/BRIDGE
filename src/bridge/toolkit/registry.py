from __future__ import annotations

from importlib import import_module
from importlib.resources import files
from importlib.util import find_spec
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4

import yaml

from bridge.toolkit.contracts import (
    ExecutionState,
    EligibilityResult,
    InputAsset,
    ImplementationState,
    ToolPackageSpec,
    ToolPackageAdapter,
    ToolPackageSpecV2,
    ToolRequest,
    ToolRequestV2,
    ToolRun,
    ToolRunV2,
)


ToolSpec = ToolPackageSpec | ToolPackageSpecV2
ToolRequestModel = ToolRequest | ToolRequestV2
ToolRunModel = ToolRun | ToolRunV2


class ToolRegistry:
    def __init__(self, specs: Iterable[ToolSpec]) -> None:
        by_id = {spec.tool_id: spec for spec in specs}
        if len(by_id) != 12:
            raise ValueError(f"Expected 12 unique Tool Packages, found {len(by_id)}")
        self._specs = by_id
        self._adapters: dict[str, ToolPackageAdapter] = {}

    @classmethod
    def load_default(cls) -> "ToolRegistry":
        resource_root = files("bridge.tool_packages.specs")
        specs: list[ToolSpec] = []
        for resource in sorted(resource_root.iterdir(), key=lambda item: item.name):
            if resource.name.endswith(".yaml"):
                payload = yaml.safe_load(resource.read_text(encoding="utf-8"))
                specs.append(cls._parse_spec(payload))
        return cls(specs)

    @staticmethod
    def _parse_spec(payload: dict[str, Any]) -> ToolSpec:
        is_v2 = (
            payload.get("input_schema_ref") == "bridge://schemas/tool-request/v0.2"
            or payload.get("output_schema_ref") == "bridge://schemas/tool-run/v0.2"
            or "adapter_ref" in payload
            or "result_schema_ref" in payload
        )
        model = ToolPackageSpecV2 if is_v2 else ToolPackageSpec
        return model.model_validate(payload)

    def ids(self) -> list[str]:
        return sorted(self._specs)

    def list(self) -> list[ToolSpec]:
        return [self._specs[tool_id] for tool_id in self.ids()]

    def describe(self, tool_id: str) -> ToolSpec:
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

    def request_model(self, tool_id: str) -> type[ToolRequest] | type[ToolRequestV2]:
        spec = self.describe(tool_id)
        return ToolRequestV2 if isinstance(spec, ToolPackageSpecV2) else ToolRequest

    def parse_request(self, payload: dict[str, Any]) -> ToolRequestModel:
        tool_id = payload.get("tool_id")
        if not isinstance(tool_id, str):
            raise ValueError("request must declare tool_id before contract selection")
        return self.request_model(tool_id).model_validate(payload)

    def check_eligibility(self, request: ToolRequestModel) -> EligibilityResult:
        spec = self.describe(request.tool_id)
        self._require_matching_request_model(request, spec)
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
        if isinstance(spec, ToolPackageSpecV2):
            adapter = self._resolve_adapter(spec)
            eligibility = adapter.check_eligibility(request, spec)
            if not isinstance(eligibility, EligibilityResult):
                raise TypeError("Tool Package adapter returned an invalid eligibility result")
            if eligibility.tool_id != request.tool_id:
                raise ValueError("Tool Package adapter eligibility tool binding mismatch")
            return eligibility
        if request.tool_id == "P0-01":
            return self._check_input_qc_eligibility(request)
        if request.tool_id == "P0-02":
            return self._check_cell_state_eligibility(request)
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

    @staticmethod
    def _check_cell_state_eligibility(request: ToolRequest) -> EligibilityResult:
        if len(request.assets) != 1:
            return EligibilityResult(
                tool_id=request.tool_id,
                eligible=False,
                reason_codes=["exactly_one_post_qc_expression_asset_required"],
            )
        asset = request.assets[0]
        reasons: list[str] = []
        if asset.format != "h5ad":
            reasons.append("cell_state_requires_h5ad")
        if not asset.path.exists():
            reasons.append("input_asset_not_found")
        if asset.assay not in {"scRNA-seq", "snRNA-seq"}:
            reasons.append("assay_must_be_declared")
        if asset.input_level.value not in {"analysis_ready", "count_ready"}:
            reasons.append("post_cell_calling_expression_required")
        if not asset.metadata.get("source_family_id"):
            reasons.append("source_family_id_required")
        try:
            from bridge.tool_packages.p0_02_cell_state.qc import validate_upstream_qc

            validate_upstream_qc(asset)
        except ValueError as exc:
            reasons.append(getattr(exc, "reason_code", "qc_profile_invalid"))
        from bridge.tool_packages.p0_02_cell_state.measurement_specs import load_measurement_spec

        measurement_spec = load_measurement_spec(request.measurement_spec_ref)
        if measurement_spec is None:
            reasons.append("measurement_spec_not_found")
        else:
            if measurement_spec.assay != asset.assay:
                reasons.append("measurement_spec_assay_mismatch")
            if asset.input_level.value not in measurement_spec.input_contract.get("supported_levels", []):
                reasons.append("measurement_spec_input_level_mismatch")
            try:
                from bridge.tool_packages.p0_02_cell_state.reference import (
                    resolve_reference_snapshot,
                    validate_runtime_reference,
                    validate_reference_snapshot,
                )

                root = resolve_reference_snapshot(measurement_spec.reference_refs[0])
                manifest = validate_reference_snapshot(root)
                validate_runtime_reference(manifest)
                if measurement_spec.measurement_spec_id not in manifest.measurement_spec_ids:
                    reasons.append("measurement_spec_not_supported_by_reference")
            except ValueError as exc:
                reasons.append(getattr(exc, "reason_code", "reference_snapshot_invalid"))
            if measurement_spec.release_manifest_ref:
                try:
                    from bridge.tool_packages.p0_02_cell_state.freeze import resolve_release_bundle

                    release = resolve_release_bundle(measurement_spec.release_manifest_ref)
                    if release.measurement_spec_ref != measurement_spec.measurement_spec_id:
                        reasons.append("cell_state_release_measurement_spec_mismatch")
                    if release.reference_snapshot_ref != measurement_spec.reference_refs[0]:
                        reasons.append("cell_state_release_reference_mismatch")
                except ValueError as exc:
                    reasons.append(getattr(exc, "reason_code", "cell_state_release_invalid"))
        if asset.path.is_dir() and request.output_dir.resolve().is_relative_to(asset.path.resolve()):
            reasons.append("output_dir_overlaps_input_asset")
        return EligibilityResult(tool_id=request.tool_id, eligible=not reasons, reason_codes=sorted(set(reasons)))

    def run(self, request: ToolRequestModel) -> ToolRunModel:
        spec = self.describe(request.tool_id)
        self._require_matching_request_model(request, spec)
        if request.tool_version is not None and request.tool_version != spec.version:
            return self._empty_run(
                request,
                spec,
                ExecutionState.FAILED,
                ["tool_version_mismatch"],
            )
        if spec.implementation_state is ImplementationState.SCAFFOLD:
            return self._empty_run(
                request,
                spec,
                ExecutionState.NOT_IMPLEMENTED,
                ["tool_package_not_implemented"],
            )
        eligibility = self.check_eligibility(request)
        if not eligibility.eligible:
            return self._empty_run(
                request,
                spec,
                ExecutionState.FAILED,
                eligibility.reason_codes,
                warnings=eligibility.warnings,
            )
        if isinstance(spec, ToolPackageSpecV2):
            result = self._resolve_adapter(spec).run(request, spec)
            return self._validate_adapter_result(result, request, spec)
        if request.tool_id == "P0-01":
            from bridge.tool_packages.p0_01_input_qc.executor import run_input_audit_qc

            return run_input_audit_qc(request, spec)
        if request.tool_id == "P0-02":
            from bridge.tool_packages.p0_02_cell_state.executor import run_cell_state_evidence

            return run_cell_state_evidence(request, spec)
        raise RuntimeError(f"No executor registered for implemented tool {request.tool_id}")

    @staticmethod
    def _require_matching_request_model(request: ToolRequestModel, spec: ToolSpec) -> None:
        if isinstance(spec, ToolPackageSpecV2) != isinstance(request, ToolRequestV2):
            raise TypeError("request model does not match the Tool Package contract version")

    @staticmethod
    def _empty_run(
        request: ToolRequestModel,
        spec: ToolSpec,
        execution_state: ExecutionState,
        reason_codes: list[str],
        *,
        warnings: list[str] | None = None,
    ) -> ToolRunModel:
        model = ToolRunV2 if isinstance(spec, ToolPackageSpecV2) else ToolRun
        return model(
            run_id=f"run-{uuid4().hex}",
            request=request,
            implementation_state=spec.implementation_state,
            execution_state=execution_state,
            tool_version=spec.version,
            environment_spec_id=spec.environment_spec_id,
            reason_codes=reason_codes,
            warnings=warnings or [],
        )

    def _resolve_adapter(self, spec: ToolPackageSpecV2) -> ToolPackageAdapter:
        if spec.adapter_ref is None:
            raise ValueError(f"Implemented Tool Package {spec.tool_id} has no adapter_ref")
        cached = self._adapters.get(spec.adapter_ref)
        if cached is not None:
            return cached

        module_name, attribute = spec.adapter_ref.split(":", 1)
        package_spec = find_spec("bridge.tool_packages")
        module_spec = find_spec(module_name)
        package_roots = tuple(package_spec.submodule_search_locations or ()) if package_spec else ()
        if module_spec is None or module_spec.origin is None or not package_roots:
            raise ValueError(f"Adapter module is not packaged: {module_name}")
        module_path = Path(module_spec.origin).resolve()
        if not any(module_path.is_relative_to(Path(root).resolve()) for root in package_roots):
            raise ValueError(f"Adapter module is outside bridge.tool_packages: {module_name}")

        module = import_module(module_name)
        try:
            adapter = getattr(module, attribute)
        except AttributeError as exc:
            raise ValueError(f"Adapter attribute is missing: {spec.adapter_ref}") from exc
        if not isinstance(adapter, ToolPackageAdapter):
            raise TypeError(f"Adapter does not satisfy ToolPackageAdapter: {spec.adapter_ref}")
        self._adapters[spec.adapter_ref] = adapter
        return adapter

    @staticmethod
    def _validate_adapter_result(
        result: object,
        request: ToolRequestV2,
        spec: ToolPackageSpecV2,
    ) -> ToolRunV2:
        if not isinstance(result, ToolRunV2):
            raise TypeError("Tool Package adapter returned an invalid ToolRunV2")
        if result.request != request or result.request.tool_id != spec.tool_id:
            raise ValueError("Tool Package adapter returned a mismatched tool or request")
        if result.tool_version != spec.version:
            raise ValueError("Tool Package adapter returned a mismatched tool version")
        if result.implementation_state is not spec.implementation_state:
            raise ValueError("Tool Package adapter returned a mismatched implementation state")
        if (
            result.result_schema_ref is not None
            and result.result_schema_ref != spec.result_schema_ref
        ):
            raise ValueError("Tool Package adapter returned a mismatched result schema")
        if (
            result.execution_state in {ExecutionState.SUCCEEDED, ExecutionState.PARTIAL}
            and result.result_schema_ref != spec.result_schema_ref
        ):
            raise ValueError("Tool Package adapter returned a mismatched result schema")
        return result
