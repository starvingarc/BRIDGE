from __future__ import annotations

import hashlib
from dataclasses import dataclass

from bridge.tool_packages._structured_runtime import (
    LoadedInputs,
    PublicationError,
    StructuredInputError,
    canonical_json_bytes,
    directory_state,
    failed_v2_run,
    load_structured_inputs,
    objects_for_role,
    publish_json_bundle,
    request_v2_from_v1,
    single_object,
)
from bridge.tool_packages.p0_07_product_comparison_stability.independence import (
    summarize_independence,
)
from bridge.tool_packages.p0_07_product_comparison_stability.executor import (
    evaluate_product_comparison,
)
from bridge.tool_packages.p0_07_product_comparison_stability.methods import (
    METHOD_REFS,
    run_comparison_methods,
)
from bridge.tool_packages.p0_07_product_comparison_stability.models import (
    ComparisonCaseManifest,
    ComparisonGroupRole,
    ComparisonMethodBundle,
    ComparisonMethodId,
    ComparisonMethodInput,
    ComparisonMethodSpec,
    ComparisonSeriesSemantics,
    ComparisonStabilitySpec,
    InputChecksumBinding,
    ProductComparisonStabilityProfile,
    ProductEvidenceBundle,
)
from bridge.tool_packages.p0_07_product_comparison_stability.visualization import (
    prepare_product_comparison_visualizations,
)
from bridge.tool_packages.p0_07_product_comparison_stability.visualization_data import (
    build_product_comparison_visualization_data,
)
from bridge.toolkit.contracts import (
    ArtifactManifest,
    EligibilityResult,
    ExecutionState,
    FrozenModel,
    ImplementationState,
    StructuredInputRef,
    ToolPackageSpecV2,
    ToolRequest,
    ToolRequestV2,
    ToolRunV2,
)

RESULT_SCHEMA_REF = "bridge://schemas/product-comparison-stability-profile/v0.2"
BASE_ROLE_MODELS: dict[str, tuple[str, type[FrozenModel]]] = {
    "comparison_stability_spec": (
        "bridge://schemas/comparison-stability-spec/v0.1",
        ComparisonStabilitySpec,
    ),
    "comparison_case_manifest": (
        "bridge://schemas/comparison-case-manifest/v0.1",
        ComparisonCaseManifest,
    ),
    "product_evidence_bundle": (
        "bridge://schemas/product-evidence-bundle/v0.1",
        ProductEvidenceBundle,
    ),
}
METHOD_ROLE_MODELS: dict[str, tuple[str, type[FrozenModel]]] = {
    **BASE_ROLE_MODELS,
    "comparison_method_spec": (
        "bridge://schemas/comparison-method-spec/v0.1",
        ComparisonMethodSpec,
    ),
    "comparison_method_input": (
        "bridge://schemas/comparison-method-input/v0.1",
        ComparisonMethodInput,
    ),
}
# Public union used by repository contract checks and external introspection.
ROLE_MODELS = METHOD_ROLE_MODELS


@dataclass(frozen=True)
class ProductComparisonStabilityAdapter:
    def check_eligibility(
        self, request: ToolRequestV2, spec: ToolPackageSpecV2
    ) -> EligibilityResult:
        if not isinstance(request, ToolRequestV2):
            tool_id = request.tool_id if isinstance(request, ToolRequest) else "P0-07"
            return EligibilityResult(
                tool_id=tool_id,
                eligible=False,
                reason_codes=["tool_request_v2_required"],
            )
        mode = _request_mode(request)
        reasons = _envelope_reasons(request, spec, mode)
        loaded, loading_reasons = _load_inputs(request.object_inputs, mode)
        reasons.extend(loading_reasons)
        if loaded is not None and not reasons:
            reasons.extend(_binding_reasons(request, loaded, spec, mode))
        reason_codes = sorted(set(reasons))
        return EligibilityResult(
            tool_id=request.tool_id,
            eligible=not reason_codes,
            reason_codes=reason_codes,
        )

    def run(self, request: ToolRequestV2, spec: ToolPackageSpecV2) -> ToolRunV2:
        if not isinstance(request, ToolRequestV2):
            return _failed_v1_request(request, spec)
        eligibility = self.check_eligibility(request, spec)
        input_hash = _input_hash(request, spec)
        if not eligibility.eligible:
            return _failed_run(
                request, spec, eligibility.reason_codes, input_hash=input_hash
            )
        mode = _request_mode(request)
        loaded, reasons = _load_inputs(request.object_inputs, mode)
        if loaded is None or reasons:
            return _failed_run(request, spec, reasons, input_hash=input_hash)
        comparison_spec = single_object(
            request, loaded, "comparison_stability_spec", ComparisonStabilitySpec
        )
        manifest = single_object(
            request, loaded, "comparison_case_manifest", ComparisonCaseManifest
        )
        bundles = objects_for_role(
            request, loaded, "product_evidence_bundle", ProductEvidenceBundle
        )
        run_id = f"run-{input_hash[:16]}"
        result = evaluate_product_comparison(
            run_id=run_id,
            tool_version=spec.version,
            spec=comparison_spec,
            manifest=manifest,
            bundles=bundles,
            input_bindings=[
                InputChecksumBinding(role=ref.role, sha256=ref.sha256)
                for ref in sorted(
                    (
                        item
                        for item in request.object_inputs
                        if item.role in BASE_ROLE_MODELS
                    ),
                    key=lambda item: (
                        item.role,
                        item.sha256,
                        item.schema_ref,
                        item.object_version,
                    ),
                )
            ],
        )
        result_bytes = canonical_json_bytes(result.model_dump(mode="json"), indent=2)
        method_spec: ComparisonMethodSpec | None = None
        method_input: ComparisonMethodInput | None = None
        method_bundle: ComparisonMethodBundle | None = None
        method_bytes: bytes | None = None
        method_bundle_sha256: str | None = None
        if mode == "method_runtime":
            method_input = single_object(
                request,
                loaded,
                "comparison_method_input",
                ComparisonMethodInput,
            )
            method_spec = single_object(
                request,
                loaded,
                "comparison_method_spec",
                ComparisonMethodSpec,
            )
            method_bundle = run_comparison_methods(
                run_id=run_id,
                tool_version=spec.version,
                comparison_eligibility=result.comparison_eligibility,
                method_spec=method_spec,
                method_spec_sha256=_input_sha(request, "comparison_method_spec"),
                method_input=method_input,
                method_input_sha256=_input_sha(request, "comparison_method_input"),
                series_gate_reasons=_series_gate_reasons(method_input, result),
                task_gate_reasons=_method_independence_gate_reasons(
                    manifest=manifest,
                    bundles=bundles,
                    method_spec=method_spec,
                    method_input=method_input,
                ),
            )
            method_bytes = canonical_json_bytes(
                method_bundle.model_dump(mode="json"), indent=2
            )
            method_bundle_sha256 = hashlib.sha256(method_bytes).hexdigest()
        payloads = {
            "product_comparison_stability_profile.json": result_bytes,
        }
        if method_bytes is not None:
            payloads["comparison_method_bundle.json"] = method_bytes
        try:
            visualization_profile = build_product_comparison_visualization_data(
                run_id=run_id,
                tool_version=spec.version,
                result=result,
                spec=comparison_spec,
                manifest=manifest,
                bundles=bundles,
                method_spec=method_spec,
                method_input=method_input,
                method_bundle=method_bundle,
                method_bundle_sha256=method_bundle_sha256,
            )
        except (KeyError, TypeError, ValueError):
            return _failed_run(
                request,
                spec,
                ["visualization_data_invalid"],
                input_hash=input_hash,
            )
        try:
            prepared_visualizations = prepare_product_comparison_visualizations(
                profile=visualization_profile,
                output_dir=request.output_dir,
                run_id=run_id,
                tool_version=spec.version,
            )
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            return _failed_run(
                request,
                spec,
                ["visualization_render_failed"],
                input_hash=input_hash,
            )
        payloads.update(prepared_visualizations.payloads)
        payloads["artifact_manifest.json"] = canonical_json_bytes(
            _artifact_manifest_payload(
                request=request,
                spec=spec,
                run_id=run_id,
                input_hash=input_hash,
                artifact_payloads=payloads,
            ),
            indent=2,
        )
        try:
            published = publish_json_bundle(
                request=request,
                run_id=run_id,
                payloads=payloads,
            )
        except PublicationError as exc:
            return _failed_run(request, spec, [exc.reason_code], input_hash=input_hash)
        evidence_ids = sorted(result.evidence_refs)
        artifacts = [
            ArtifactManifest(
                artifact_id=f"artifact:{run_id}:product-comparison-stability-profile",
                kind="product_comparison_stability_profile",
                path=published["product_comparison_stability_profile.json"],
                media_type="application/json",
                sha256=hashlib.sha256(result_bytes).hexdigest(),
                evidence_ids=evidence_ids,
            ),
            ArtifactManifest(
                artifact_id=f"artifact:{run_id}:artifact-manifest",
                kind="artifact_manifest",
                path=published["artifact_manifest.json"],
                media_type="application/json",
                sha256=hashlib.sha256(payloads["artifact_manifest.json"]).hexdigest(),
                evidence_ids=evidence_ids,
            ),
        ]
        if method_bytes is not None and method_bundle is not None:
            artifacts.append(
                ArtifactManifest(
                    artifact_id=f"artifact:{run_id}:comparison-method-bundle",
                    kind="comparison_method_bundle",
                    path=published["comparison_method_bundle.json"],
                    media_type="application/json",
                    sha256=hashlib.sha256(method_bytes).hexdigest(),
                    evidence_ids=method_bundle.evidence_refs,
                )
            )
        artifacts.extend(prepared_visualizations.artifacts)
        method_reasons = (
            sorted(
                {
                    reason
                    for execution in method_bundle.executions
                    for reason in execution.reason_codes
                }
            )
            if method_bundle is not None
            else []
        )
        execution_state = (
            ExecutionState.SUCCEEDED
            if result.profile_state == "complete" and not method_reasons
            else ExecutionState.PARTIAL
        )
        return ToolRunV2(
            run_id=run_id,
            request=request,
            implementation_state=ImplementationState.IMPLEMENTED,
            execution_state=execution_state,
            tool_version=spec.version,
            environment_spec_id=spec.environment_spec_id,
            input_hash=input_hash,
            created_at=manifest.created_at,
            measurements=[],
            artifacts=artifacts,
            visualizations=[],
            result_schema_ref=RESULT_SCHEMA_REF,
            result=result.model_dump(mode="json"),
            reason_codes=result.reason_codes,
            warnings=method_reasons,
        )


adapter = ProductComparisonStabilityAdapter()


def _request_mode(request: ToolRequestV2) -> str:
    method_roles = set(METHOD_ROLE_MODELS).difference(BASE_ROLE_MODELS)
    if any(ref.role in method_roles for ref in request.object_inputs):
        return "method_runtime"
    return "legacy_comparison"


def _envelope_reasons(
    request: ToolRequestV2,
    spec: ToolPackageSpecV2,
    mode: str,
) -> list[str]:
    reasons: list[str] = []
    if request.tool_version is not None and request.tool_version != spec.version:
        reasons.append("tool_version_mismatch")
    if request.assets:
        reasons.append("p0_07_expression_assets_forbidden")
    if request.measurement_spec_ref is not None:
        reasons.append("p0_07_measurement_spec_parameter_forbidden")
    if request.parameters:
        reasons.append("p0_07_parameters_forbidden")
    if request.random_seed != 0:
        reasons.append("p0_07_random_seed_forbidden")
    role_models = METHOD_ROLE_MODELS if mode == "method_runtime" else BASE_ROLE_MODELS
    roles = [ref.role for ref in request.object_inputs]
    for role in role_models:
        count = roles.count(role)
        expected = 2 <= count <= 20 if role == "product_evidence_bundle" else count == 1
        if not expected:
            reasons.append(
                "two_to_twenty_product_evidence_bundles_required"
                if role == "product_evidence_bundle"
                else f"exactly_one_{role}_required"
            )
    if any(role not in role_models for role in roles):
        reasons.append("unsupported_object_input_role")
    for ref in request.object_inputs:
        contract = role_models.get(ref.role)
        if contract is not None and ref.schema_ref != contract[0]:
            reasons.append("object_input_schema_mismatch")
        if ref.object_version != "0.1.0":
            reasons.append("object_input_version_mismatch")
    if directory_state(request.output_dir) == "other":
        reasons.append("output_dir_not_regular_directory")
    return reasons


def _load_inputs(
    refs: list[StructuredInputRef],
    mode: str,
) -> tuple[LoadedInputs | None, list[str]]:
    role_models = METHOD_ROLE_MODELS if mode == "method_runtime" else BASE_ROLE_MODELS
    return load_structured_inputs(
        refs,
        model_for=lambda ref: role_models.get(ref.role, ("", None))[1],
        validate_model=_validate_object_version,
    )


def _validate_object_version(ref: StructuredInputRef, value: FrozenModel) -> None:
    if getattr(value, "object_version", None) != ref.object_version:
        raise StructuredInputError("object_input_version_mismatch")


def _binding_reasons(
    request: ToolRequestV2,
    loaded: LoadedInputs,
    tool_spec: ToolPackageSpecV2,
    mode: str,
) -> list[str]:
    comparison_spec = single_object(
        request, loaded, "comparison_stability_spec", ComparisonStabilitySpec
    )
    manifest = single_object(
        request, loaded, "comparison_case_manifest", ComparisonCaseManifest
    )
    bundles = objects_for_role(
        request, loaded, "product_evidence_bundle", ProductEvidenceBundle
    )
    reasons: list[str] = []
    if comparison_spec.comparison_ref != manifest.ref:
        reasons.append("comparison_spec_manifest_binding_mismatch")
    if manifest.spec_ref != comparison_spec.ref:
        reasons.append("comparison_manifest_spec_binding_mismatch")
    expected_refs = {ref.ref for group in manifest.groups for ref in group.bundle_refs}
    actual_refs = {bundle.ref.ref for bundle in bundles}
    if len(actual_refs) != len(bundles):
        reasons.append("duplicate_product_evidence_bundle_ref")
    if expected_refs != actual_refs:
        reasons.append("comparison_manifest_bundle_set_mismatch")
    groups = {group.group_id: group for group in manifest.groups}
    case_refs: set[str] = set()
    analysis_units: set[str] = set()
    contracts = {item.metric_id: item for item in comparison_spec.metric_contracts}
    for bundle in bundles:
        if bundle.comparison_ref != manifest.ref:
            reasons.append("bundle_comparison_binding_mismatch")
        group = groups.get(bundle.group_id)
        if group is None or bundle.ref not in group.bundle_refs:
            reasons.append("bundle_group_binding_mismatch")
            continue
        if bundle.product_definition.ref != group.product_definition_ref:
            reasons.append("bundle_product_definition_binding_mismatch")
        if bundle.target_stage_ref != group.target_stage_ref:
            reasons.append("bundle_target_stage_binding_mismatch")
        case_ref = bundle.product_case.ref.ref
        if case_ref in case_refs:
            reasons.append("duplicate_product_case_ref")
        case_refs.add(case_ref)
        analysis_ref = bundle.product_case.sample_or_preparation_ref.ref
        if analysis_ref in analysis_units:
            reasons.append("duplicate_analysis_unit_ref")
        analysis_units.add(analysis_ref)
        if {item.metric_id for item in bundle.metrics} != set(contracts):
            reasons.append("bundle_metric_contract_set_mismatch")
        for metric in bundle.metrics:
            contract = contracts.get(metric.metric_id)
            if contract is None:
                continue
            if (
                metric.measurement_spec_ref != contract.measurement_spec_ref
                or metric.unit != contract.unit
                or metric.denominator_kind != contract.denominator_kind
            ):
                reasons.append("bundle_metric_contract_mismatch")
        if bundle.sufficiency_summary_ref is not None and not (
            bundle.sufficiency_summary_ref.startswith(
                "case-evidence-readiness-summary:"
            )
            or bundle.sufficiency_summary_ref.startswith(
                "evidence-sufficiency-profile:"
            )
        ):
            reasons.append("evidence_sufficiency_ref_invalid")
    if mode == "method_runtime":
        reasons.extend(
            _method_binding_reasons(
                request=request,
                loaded=loaded,
                tool_spec=tool_spec,
                comparison_spec=comparison_spec,
                manifest=manifest,
                bundles=bundles,
            )
        )
    return reasons


def _method_binding_reasons(
    *,
    request: ToolRequestV2,
    loaded: LoadedInputs,
    tool_spec: ToolPackageSpecV2,
    comparison_spec: ComparisonStabilitySpec,
    manifest: ComparisonCaseManifest,
    bundles: list[ProductEvidenceBundle],
) -> list[str]:
    method_spec = single_object(
        request, loaded, "comparison_method_spec", ComparisonMethodSpec
    )
    method_input = single_object(
        request, loaded, "comparison_method_input", ComparisonMethodInput
    )
    reasons: set[str] = set()
    if not method_spec.active:
        reasons.add("comparison_method_spec_inactive")
    if (
        method_spec.comparison_ref != manifest.ref
        or method_input.comparison_ref != manifest.ref
    ):
        reasons.add("comparison_method_comparison_ref_mismatch")
    if method_input.comparison_manifest_sha256 != _input_sha(
        request, "comparison_case_manifest"
    ):
        reasons.add("comparison_method_manifest_checksum_mismatch")
    if any(
        METHOD_REFS[task.method_id][0] not in tool_spec.method_ids
        for task in method_spec.tasks
    ):
        reasons.add("comparison_method_not_registered")

    bundle_by_ref = {item.ref.ref: item for item in bundles}
    group_by_id = {item.group_id: item for item in manifest.groups}
    contract_by_metric = {
        item.metric_id: item for item in comparison_spec.metric_contracts
    }
    series_by_id = {item.series_id: item for item in method_input.series}
    for series in method_input.series:
        sources = [bundle_by_ref.get(item.ref) for item in series.source_bundle_refs]
        if any(item is None for item in sources):
            reasons.add("comparison_series_source_bundle_missing")
            continue
        bound_sources = [item for item in sources if item is not None]
        if any(item.group_id != series.group_id for item in bound_sources):
            reasons.add("comparison_series_group_mismatch")
        contract = contract_by_metric.get(series.metric_id)
        if (
            contract is None
            or contract.unit != series.unit
            or contract.denominator_kind != series.denominator_kind
        ):
            reasons.add("comparison_series_metric_contract_mismatch")
        if series.semantics is ComparisonSeriesSemantics.SAMPLE_VALUES:
            group = group_by_id.get(series.group_id)
            if group is None or {item.ref for item in series.source_bundle_refs} != {
                item.ref for item in group.bundle_refs
            }:
                reasons.add("comparison_series_source_bundle_set_mismatch")
            source_by_label = {
                item.product_case.sample_or_preparation_ref.ref: item
                for item in bound_sources
            }
            if set(series.labels) != set(source_by_label):
                reasons.add("comparison_series_analysis_unit_mismatch")
            else:
                for label, value in zip(series.labels, series.values, strict=True):
                    metric = next(
                        (
                            item
                            for item in source_by_label[label].metrics
                            if item.metric_id == series.metric_id
                        ),
                        None,
                    )
                    if (
                        metric is None
                        or metric.raw_value is None
                        or value != metric.raw_value
                    ):
                        reasons.add("comparison_series_source_value_mismatch")
                        break

    expected_semantics = {
        ComparisonMethodId.SAMPLE_EFFECT: ComparisonSeriesSemantics.SAMPLE_VALUES,
        ComparisonMethodId.JENSEN_SHANNON: ComparisonSeriesSemantics.PROBABILITY_MASS,
        ComparisonMethodId.PROFILE_CORRELATION: ComparisonSeriesSemantics.MATCHED_FEATURES,
        ComparisonMethodId.WASSERSTEIN_1D: ComparisonSeriesSemantics.ORDERED_VALUES,
        ComparisonMethodId.ROBUST_DISPERSION: ComparisonSeriesSemantics.SAMPLE_VALUES,
    }
    for task in method_spec.tasks:
        series = [series_by_id.get(item) for item in task.series_ids]
        if any(item is None for item in series):
            reasons.add("comparison_method_task_series_missing")
            continue
        bound_series = [item for item in series if item is not None]
        if any(
            item.semantics is not expected_semantics[task.method_id]
            for item in bound_series
        ):
            reasons.add("comparison_method_series_semantics_mismatch")
        if len(bound_series) == 2:
            left, right = bound_series
            if (
                left.metric_id != right.metric_id
                or left.unit != right.unit
                or left.denominator_kind != right.denominator_kind
            ):
                reasons.add("comparison_method_pair_contract_mismatch")
            left_group = group_by_id.get(left.group_id)
            right_group = group_by_id.get(right.group_id)
            if (
                left_group is None
                or left_group.role is not ComparisonGroupRole.BASELINE
                or right_group is None
                or right_group.role is ComparisonGroupRole.BASELINE
            ):
                reasons.add("comparison_method_pair_role_mismatch")
            if (
                task.method_id
                in {
                    ComparisonMethodId.JENSEN_SHANNON,
                    ComparisonMethodId.PROFILE_CORRELATION,
                }
                and left.labels != right.labels
            ):
                reasons.add("comparison_method_feature_labels_mismatch")
    return sorted(reasons)


def _series_gate_reasons(
    method_input: ComparisonMethodInput,
    result: ProductComparisonStabilityProfile,
) -> dict[str, str]:
    states = {
        (item.group_id, item.metric_id): item.value_state
        for item in result.group_summaries
    }
    return {
        series.series_id: f"comparison_method_source_{state}"
        for series in method_input.series
        if (state := states[(series.group_id, series.metric_id)]) != "shadow"
    }


def _method_independence_gate_reasons(
    *,
    manifest: ComparisonCaseManifest,
    bundles: list[ProductEvidenceBundle],
    method_spec: ComparisonMethodSpec,
    method_input: ComparisonMethodInput,
) -> dict[str, list[str]]:
    bundle_by_ref = {bundle.ref.ref: bundle for bundle in bundles}
    grouped = {
        group.group_id: [bundle_by_ref[ref.ref] for ref in group.bundle_refs]
        for group in manifest.groups
    }
    independence = summarize_independence(manifest.groups, grouped)
    series_by_id = {series.series_id: series for series in method_input.series}
    gated_methods = {
        ComparisonMethodId.SAMPLE_EFFECT: "sample_effect",
        ComparisonMethodId.ROBUST_DISPERSION: "dispersion",
    }
    result: dict[str, list[str]] = {}
    for task in method_spec.tasks:
        prefix = gated_methods.get(task.method_id)
        if prefix is None:
            continue
        group_ids = {
            series_by_id[series_id].group_id for series_id in task.series_ids
        }
        summaries = [
            independence.by_group_id[group_id] for group_id in sorted(group_ids)
        ]
        reasons: set[str] = set()
        if any(summary.state == "not_recorded" for summary in summaries):
            reasons.add(f"{prefix}_independence_not_recorded")
        if any(summary.state == "inconsistent" for summary in summaries):
            reasons.add(f"{prefix}_independence_binding_inconsistent")
        if (
            task.method_id is ComparisonMethodId.SAMPLE_EFFECT
            and all(summary.state == "declared" for summary in summaries)
            and len(
                {
                    summary.independence_scope_ref
                    for summary in summaries
                }
            )
            != 1
        ):
            reasons.add("sample_effect_independence_scope_mismatch")
        if reasons:
            result[task.task_id] = sorted(reasons)
    return result


def _artifact_manifest_payload(
    *,
    request: ToolRequestV2,
    spec: ToolPackageSpecV2,
    run_id: str,
    input_hash: str,
    artifact_payloads: dict[str, bytes],
) -> dict[str, object]:
    return {
        "manifest_version": "0.1.0",
        "tool_id": spec.tool_id,
        "tool_version": spec.version,
        "run_id": run_id,
        "input_hash": input_hash,
        "inputs": [
            {
                "role": ref.role,
                "schema_ref": ref.schema_ref,
                "object_version": ref.object_version,
                "sha256": ref.sha256,
                "media_type": ref.media_type,
            }
            for ref in sorted(
                request.object_inputs,
                key=lambda item: (
                    item.role,
                    item.schema_ref,
                    item.object_version,
                    item.sha256,
                    item.media_type,
                ),
            )
        ],
        "assets": [
            {
                "asset_id": asset.asset_id,
                "sha256": asset.checksum,
                "format": asset.format,
                "matrix_semantics": asset.matrix_semantics,
            }
            for asset in sorted(request.assets, key=lambda item: item.asset_id)
        ],
        "artifacts": [
            {
                "filename": filename,
                "media_type": _artifact_media_type(filename),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
            for filename, payload in sorted(artifact_payloads.items())
        ],
    }


def _artifact_media_type(filename: str) -> str:
    suffix = filename.rsplit(".", maxsplit=1)[-1].lower()
    media_types = {
        "json": "application/json",
        "pdf": "application/pdf",
        "png": "image/png",
        "svg": "image/svg+xml",
        "tsv": "text/tab-separated-values",
    }
    try:
        return media_types[suffix]
    except KeyError as exc:
        raise ValueError(f"unsupported artifact media type: {filename}") from exc


def _input_sha(request: ToolRequestV2, role: str) -> str:
    return next(ref.sha256 for ref in request.object_inputs if ref.role == role)


def _input_hash(request: ToolRequestV2, spec: ToolPackageSpecV2) -> str:
    payload = {
        "tool_id": spec.tool_id,
        "tool_version": spec.version,
        "environment_spec_id": spec.environment_spec_id,
        "result_schema_ref": spec.result_schema_ref,
        "object_inputs": [
            {
                "role": ref.role,
                "schema_ref": ref.schema_ref,
                "object_version": ref.object_version,
                "sha256": ref.sha256,
                "media_type": ref.media_type,
            }
            for ref in sorted(
                request.object_inputs,
                key=lambda item: (
                    item.role,
                    item.schema_ref,
                    item.object_version,
                    item.sha256,
                    item.media_type,
                ),
            )
        ],
    }
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def _failed_run(
    request: ToolRequestV2,
    spec: ToolPackageSpecV2,
    reasons: list[str],
    *,
    input_hash: str | None = None,
) -> ToolRunV2:
    return failed_v2_run(
        request,
        spec,
        reasons,
        result_schema_ref=RESULT_SCHEMA_REF,
        fingerprint_input_key="p0_07_object_inputs",
        input_hash=input_hash,
    )


def _failed_v1_request(request: ToolRequest, spec: ToolPackageSpecV2) -> ToolRunV2:
    return _failed_run(request_v2_from_v1(request), spec, ["tool_request_v2_required"])
