from __future__ import annotations

import hashlib
from importlib import import_module
from importlib.resources import files
from importlib.util import find_spec
import json
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
import yaml

from bridge.toolkit.contracts import (
    ExecutionState,
    EligibilityResult,
    InputAsset,
    ImplementationState,
    StructuredInputRef,
    ToolPackageSpec,
    ToolPackageAdapter,
    ToolPackageSpecV2,
    ToolRequest,
    ToolRequestV2,
    ToolRun,
    ToolRunV2,
)
from bridge.toolkit.schemas import SCHEMA_REFS, load_schema


ToolSpec = ToolPackageSpec | ToolPackageSpecV2
ToolRequestModel = ToolRequest | ToolRequestV2
ToolRunModel = ToolRun | ToolRunV2
StructuredInputSnapshot = tuple[tuple[Path, str], ...]
SUPPORTED_STRUCTURED_INPUT_MEDIA_TYPES = frozenset({"application/json"})
STRUCTURED_OBJECT_VERSION_FIELDS = frozenset({"object_version", "version"})


class _StrictJSONError(ValueError):
    pass


def _reject_nonstandard_json_constant(value: str) -> None:
    raise _StrictJSONError(f"non-standard JSON constant: {value}")


def _reject_duplicate_json_keys(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key, value in pairs:
        if key in payload:
            raise _StrictJSONError(f"duplicate JSON object key: {key}")
        payload[key] = value
    return payload


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
            reason_code = (
                "tool_package_not_implemented"
                if spec.implementation_state is ImplementationState.SCAFFOLD
                else "tool_package_deprecated"
            )
            return EligibilityResult(
                tool_id=request.tool_id,
                eligible=False,
                reason_codes=[reason_code],
            )
        if isinstance(spec, ToolPackageSpecV2):
            input_eligibility, snapshots = self._validate_structured_inputs(request)
            if not input_eligibility.eligible:
                return input_eligibility
            self._resolve_result_schema(spec)
            adapter = self._resolve_adapter(spec)
            return self._call_adapter_eligibility(adapter, request, spec, snapshots)
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
        if spec.implementation_state is not ImplementationState.IMPLEMENTED:
            is_scaffold = spec.implementation_state is ImplementationState.SCAFFOLD
            return self._empty_run(
                request,
                spec,
                ExecutionState.NOT_IMPLEMENTED if is_scaffold else ExecutionState.FAILED,
                [
                    "tool_package_not_implemented"
                    if is_scaffold
                    else "tool_package_deprecated"
                ],
            )
        if isinstance(spec, ToolPackageSpecV2):
            return self._run_v2(request, spec)
        eligibility = self.check_eligibility(request)
        if not eligibility.eligible:
            return self._empty_run(
                request,
                spec,
                ExecutionState.FAILED,
                eligibility.reason_codes,
                warnings=eligibility.warnings,
            )
        if request.tool_id == "P0-01":
            from bridge.tool_packages.p0_01_input_qc.executor import run_input_audit_qc

            return run_input_audit_qc(request, spec)
        if request.tool_id == "P0-02":
            from bridge.tool_packages.p0_02_cell_state.executor import run_cell_state_evidence

            return run_cell_state_evidence(request, spec)
        raise RuntimeError(f"No executor registered for implemented tool {request.tool_id}")

    def _run_v2(
        self, request: ToolRequestV2, spec: ToolPackageSpecV2
    ) -> ToolRunV2:
        input_eligibility, snapshots = self._validate_structured_inputs(request)
        if not input_eligibility.eligible:
            return self._empty_run(
                request,
                spec,
                ExecutionState.FAILED,
                input_eligibility.reason_codes,
            )

        result_schema = self._resolve_result_schema(spec)
        adapter = self._resolve_adapter(spec)
        eligibility = self._call_adapter_eligibility(
            adapter, request, spec, snapshots
        )
        if not eligibility.eligible:
            return self._empty_run(
                request,
                spec,
                ExecutionState.FAILED,
                eligibility.reason_codes,
                warnings=eligibility.warnings,
            )

        try:
            result = adapter.run(request, spec)
        except Exception:
            if not self._structured_inputs_unchanged(snapshots):
                return self._empty_run(
                    request,
                    spec,
                    ExecutionState.FAILED,
                    ["input_asset_modified_during_run"],
                )
            raise
        if not self._structured_inputs_unchanged(snapshots):
            return self._empty_run(
                request,
                spec,
                ExecutionState.FAILED,
                ["input_asset_modified_during_run"],
            )
        return self._validate_adapter_result(result, request, spec, result_schema)

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
    def _call_adapter_eligibility(
        adapter: ToolPackageAdapter,
        request: ToolRequestV2,
        spec: ToolPackageSpecV2,
        snapshots: StructuredInputSnapshot,
    ) -> EligibilityResult:
        try:
            eligibility = adapter.check_eligibility(request, spec)
        except Exception:
            if not ToolRegistry._structured_inputs_unchanged(snapshots):
                return EligibilityResult(
                    tool_id=request.tool_id,
                    eligible=False,
                    reason_codes=["input_asset_modified_during_run"],
                )
            raise
        if not ToolRegistry._structured_inputs_unchanged(snapshots):
            return EligibilityResult(
                tool_id=request.tool_id,
                eligible=False,
                reason_codes=["input_asset_modified_during_run"],
            )
        if not isinstance(eligibility, EligibilityResult):
            raise TypeError("Tool Package adapter returned an invalid eligibility result")
        if eligibility.tool_id != request.tool_id:
            raise ValueError("Tool Package adapter eligibility tool binding mismatch")
        return eligibility

    @staticmethod
    def _resolve_result_schema(spec: ToolPackageSpecV2) -> dict[str, Any]:
        schema_ref = spec.result_schema_ref
        if schema_ref is None or schema_ref not in SCHEMA_REFS:
            raise ValueError(
                f"Tool Package result schema is not registered: {schema_ref}"
            )
        schema = load_schema(schema_ref)
        try:
            Draft202012Validator.check_schema(schema)
        except SchemaError as exc:
            raise ValueError(
                f"Tool Package result schema is invalid: {schema_ref}"
            ) from exc
        return schema

    @staticmethod
    def _validate_structured_inputs(
        request: ToolRequestV2,
    ) -> tuple[EligibilityResult, StructuredInputSnapshot]:
        reasons: list[str] = []
        snapshots: list[tuple[Path, str]] = []
        for input_ref in request.object_inputs:
            reason, digest = ToolRegistry._validate_structured_input(input_ref)
            if reason is not None:
                reasons.append(reason)
            elif digest is not None:
                snapshots.append((input_ref.path, digest))
        unique_reasons = sorted(set(reasons))
        return (
            EligibilityResult(
                tool_id=request.tool_id,
                eligible=not unique_reasons,
                reason_codes=unique_reasons,
            ),
            tuple(snapshots),
        )

    @staticmethod
    def _validate_structured_input(
        input_ref: StructuredInputRef,
    ) -> tuple[str | None, str | None]:
        path = input_ref.path
        try:
            if not path.exists():
                return "structured_input_not_found", None
            if not path.is_file():
                return "structured_input_not_regular_file", None
        except OSError:
            return "structured_input_unreadable", None
        if input_ref.media_type not in SUPPORTED_STRUCTURED_INPUT_MEDIA_TYPES:
            return "structured_input_media_type_unsupported", None
        try:
            encoded = path.read_bytes()
        except OSError:
            return "structured_input_unreadable", None
        digest = hashlib.sha256(encoded).hexdigest()
        if digest != input_ref.sha256:
            return "structured_input_checksum_mismatch", None
        try:
            payload = json.loads(
                encoded,
                parse_constant=_reject_nonstandard_json_constant,
                object_pairs_hook=_reject_duplicate_json_keys,
            )
        except (UnicodeDecodeError, json.JSONDecodeError, _StrictJSONError):
            return "structured_input_invalid_json", None
        if input_ref.schema_ref not in SCHEMA_REFS:
            return "structured_input_schema_not_registered", None
        schema = load_schema(input_ref.schema_ref)
        try:
            Draft202012Validator.check_schema(schema)
        except SchemaError:
            return "structured_input_schema_invalid", None
        version_reason = ToolRegistry._validate_structured_object_version(
            input_ref, payload, schema
        )
        if version_reason is not None:
            return version_reason, None
        if not Draft202012Validator(schema).is_valid(payload):
            return "structured_input_schema_validation_failed", None
        return None, digest

    @staticmethod
    def _validate_structured_object_version(
        input_ref: StructuredInputRef,
        payload: Any,
        schema: dict[str, Any],
    ) -> str | None:
        schema_properties = schema.get("properties", {})
        schema_version_fields = {
            field
            for field in STRUCTURED_OBJECT_VERSION_FIELDS
            if field in schema_properties
        }
        payload_version_fields = (
            {
                field
                for field in STRUCTURED_OBJECT_VERSION_FIELDS
                if field in payload
            }
            if isinstance(payload, dict)
            else set()
        )
        if schema_version_fields and not isinstance(payload, dict):
            return "structured_input_object_version_missing"
        if isinstance(payload, dict) and any(
            field not in payload for field in schema_version_fields
        ):
            return "structured_input_object_version_missing"
        for field in schema_version_fields | payload_version_fields:
            if payload[field] != input_ref.object_version:
                return "structured_input_object_version_mismatch"
        return None

    @staticmethod
    def _structured_inputs_unchanged(snapshots: StructuredInputSnapshot) -> bool:
        for path, expected_digest in snapshots:
            try:
                if not path.is_file():
                    return False
                current_digest = hashlib.sha256(path.read_bytes()).hexdigest()
            except OSError:
                return False
            if current_digest != expected_digest:
                return False
        return True

    @staticmethod
    def _validate_adapter_result(
        result: object,
        request: ToolRequestV2,
        spec: ToolPackageSpecV2,
        result_schema: dict[str, Any],
    ) -> ToolRunV2:
        if not isinstance(result, ToolRunV2):
            raise TypeError("Tool Package adapter returned an invalid ToolRunV2")
        if result.request != request or result.request.tool_id != spec.tool_id:
            raise ValueError("Tool Package adapter returned a mismatched tool or request")
        if result.tool_version != spec.version:
            raise ValueError("Tool Package adapter returned a mismatched tool version")
        if result.implementation_state is not spec.implementation_state:
            raise ValueError("Tool Package adapter returned a mismatched implementation state")
        if result.environment_spec_id != spec.environment_spec_id:
            raise ValueError("Tool Package adapter returned a mismatched environment spec")
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
        if (
            result.execution_state in {ExecutionState.SUCCEEDED, ExecutionState.PARTIAL}
            and result.result is None
        ):
            raise ValueError(
                "Tool Package adapter returned a successful or partial run without "
                "a bound result payload"
            )
        if result.result is not None:
            if result.result_schema_ref != spec.result_schema_ref:
                raise ValueError("Tool Package adapter returned an unbound result payload")
            if not Draft202012Validator(result_schema).is_valid(result.result):
                raise ValueError(
                    "Tool Package adapter returned a result that violates its registered schema"
                )
        return result
