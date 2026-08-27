from __future__ import annotations

from dataclasses import dataclass
import hashlib
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import re
import stat
from typing import Any

import anndata as ad
import numpy as np
import pandas as pd
import scanpy as sc
from scipy import sparse
from scipy.stats import spearmanr

from bridge.tool_packages.p0_01_input_qc.io import (
    InputAuditError,
    validate_expression_object,
)
from bridge.tool_packages._structured_runtime import (
    LoadedInputs,
    PublicationError,
    StructuredInputError,
    canonical_json_bytes,
    directory_state,
    failed_v2_run,
    inputs_unchanged,
    load_structured_inputs,
    publish_json_bundle,
    read_regular_bytes,
    request_v2_from_v1,
    single_object,
)
from bridge.tool_packages.p0_12_graft_assessment.analysis_models import (
    AnalysisAvailability,
    GraftCompositionEstimate,
    GraftExpressionAnalysisResult,
    GraftExpressionAnalysisSpec,
    GraftExpressionAsset,
    GraftMarkerProgramCollection,
    GraftMatrixSemantics,
    GraftProgramEvidence,
    GraftReferencePanel,
    GraftReferenceSupport,
)
from bridge.tool_packages.p0_12_graft_assessment.models import (
    GraftCase,
    GraftSourceBinding,
    SAFE_ID_PATTERN,
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


RESULT_SCHEMA_REF = "bridge://schemas/graft-assessment-run-result/v0.1"
ANALYSIS_METHOD_IDS = [
    "METHOD-ANNDATA",
    "METHOD-BRIDGE-GRAFTCASE-VALIDATOR",
    "METHOD-BRIDGE-PSEUDOBULK-REFERENCE-CORRELATION-2C3A8F",
    "METHOD-BRIDGE-SOFT-COMPOSITION-404672",
    "METHOD-SCANPY",
]
ROLE_MODELS: dict[str, tuple[str, type[FrozenModel]]] = {
    "graft_case": ("bridge://schemas/graft-case/v0.1", GraftCase),
    "graft_expression_asset": (
        "bridge://schemas/graft-expression-asset/v0.1",
        GraftExpressionAsset,
    ),
    "graft_expression_analysis_spec": (
        "bridge://schemas/graft-expression-analysis-spec/v0.1",
        GraftExpressionAnalysisSpec,
    ),
    "graft_reference_panel": (
        "bridge://schemas/graft-reference-panel/v0.1",
        GraftReferencePanel,
    ),
    "graft_marker_program_collection": (
        "bridge://schemas/graft-marker-program-collection/v0.1",
        GraftMarkerProgramCollection,
    ),
}
ANALYSIS_ONLY_ROLES = frozenset(ROLE_MODELS).difference({"graft_case"})


class GraftAnalysisError(ValueError):
    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


def is_expression_analysis_request(request: ToolRequestV2) -> bool:
    return any(
        ref.role in ANALYSIS_ONLY_ROLES for ref in request.object_inputs
    )


def check_eligibility(
    request: ToolRequestV2,
    spec: ToolPackageSpecV2,
) -> EligibilityResult:
    if not isinstance(request, ToolRequestV2):
        tool_id = request.tool_id if isinstance(request, ToolRequest) else "P0-12"
        return EligibilityResult(
            tool_id=tool_id,
            eligible=False,
            reason_codes=["tool_request_v2_required"],
        )
    reasons = _envelope_reasons(request, spec)
    loaded, loading_reasons = _load_inputs(request.object_inputs)
    reasons.extend(loading_reasons)
    if loaded is not None and not reasons:
        reasons.extend(_binding_reasons(request, loaded, spec))
    reason_codes = sorted(set(reasons))
    return EligibilityResult(
        tool_id=request.tool_id,
        eligible=not reason_codes,
        reason_codes=reason_codes,
    )


def run(request: ToolRequestV2, spec: ToolPackageSpecV2) -> ToolRunV2:
    if not isinstance(request, ToolRequestV2):
        return _failed_v1_request(request, spec)
    eligibility = check_eligibility(request, spec)
    input_hash = _input_hash(request, spec)
    if not eligibility.eligible:
        return _failed_run(
            request, spec, eligibility.reason_codes, input_hash=input_hash
        )
    loaded, reasons = _load_inputs(request.object_inputs)
    if loaded is None or reasons:
        return _failed_run(request, spec, reasons, input_hash=input_hash)
    case, asset, analysis_spec, reference_panel, programs = _objects(
        request, loaded
    )
    try:
        result = _analyze(
            request=request,
            case=case,
            asset=asset,
            analysis_spec=analysis_spec,
            reference_panel=reference_panel,
            programs=programs,
            tool_version=spec.version,
            input_hash=input_hash,
        )
    except GraftAnalysisError as exc:
        return _failed_run(
            request, spec, [exc.reason_code], input_hash=input_hash
        )
    run_id = f"run-{input_hash[:16]}"
    result_bytes = canonical_json_bytes(result.model_dump(mode="json"), indent=2)
    manifest_bytes = canonical_json_bytes(
        _manifest_payload(request, spec, run_id, input_hash, result_bytes),
        indent=2,
    )
    try:
        published = publish_json_bundle(
            request=request,
            run_id=run_id,
            payloads={
                "graft_expression_analysis_result.json": result_bytes,
                "artifact_manifest.json": manifest_bytes,
            },
            inputs_are_unchanged=lambda refs: (
                inputs_unchanged(refs) and _asset_unchanged(asset)
            ),
        )
    except PublicationError as exc:
        return _failed_run(
            request, spec, [exc.reason_code], input_hash=input_hash
        )
    artifacts = [
        ArtifactManifest(
            artifact_id=f"artifact:{run_id}:{path.stem}",
            kind=path.stem,
            path=path,
            media_type="application/json",
            sha256=hashlib.sha256(read_regular_bytes(path)).hexdigest(),
            evidence_ids=[],
        )
        for path in sorted(published.values(), key=lambda value: value.name)
    ]
    return ToolRunV2(
        run_id=run_id,
        request=request,
        implementation_state=ImplementationState.IMPLEMENTED,
        execution_state=ExecutionState.SUCCEEDED,
        tool_version=spec.version,
        environment_spec_id=spec.environment_spec_id,
        input_hash=input_hash,
        created_at=asset.created_at,
        measurements=[],
        artifacts=artifacts,
        visualizations=[],
        result_schema_ref=RESULT_SCHEMA_REF,
        result=result.model_dump(mode="json"),
        reason_codes=[],
        warnings=[],
    )


def _envelope_reasons(
    request: ToolRequestV2,
    spec: ToolPackageSpecV2,
) -> list[str]:
    reasons: list[str] = []
    if request.tool_version is not None and request.tool_version != spec.version:
        reasons.append("tool_version_mismatch")
    if request.assets:
        reasons.append("p0_12_expression_assets_require_manifest")
    if request.measurement_spec_ref is not None:
        reasons.append("p0_12_measurement_spec_forbidden")
    if request.parameters:
        reasons.append("p0_12_parameters_forbidden")
    roles = [ref.role for ref in request.object_inputs]
    for role in ROLE_MODELS:
        if roles.count(role) != 1:
            reasons.append(f"exactly_one_{role}_required")
    if any(role not in ROLE_MODELS for role in roles):
        reasons.append("unsupported_object_input_role")
    for ref in request.object_inputs:
        contract = ROLE_MODELS.get(ref.role)
        if contract is not None and ref.schema_ref != contract[0]:
            reasons.append("object_input_schema_mismatch")
        if ref.object_version != "0.1.0":
            reasons.append("object_input_version_mismatch")
    if directory_state(request.output_dir) == "other":
        reasons.append("output_dir_not_regular_directory")
    return reasons


def _load_inputs(
    refs: list[StructuredInputRef],
) -> tuple[LoadedInputs | None, list[str]]:
    return load_structured_inputs(
        refs,
        model_for=lambda ref: ROLE_MODELS.get(ref.role, ("", None))[1],
        validate_model=_validate_object_version,
    )


def _validate_object_version(
    ref: StructuredInputRef,
    value: FrozenModel,
) -> None:
    if getattr(value, "object_version", None) != ref.object_version:
        raise StructuredInputError("object_input_version_mismatch")


def _objects(
    request: ToolRequestV2,
    loaded: LoadedInputs,
) -> tuple[
    GraftCase,
    GraftExpressionAsset,
    GraftExpressionAnalysisSpec,
    GraftReferencePanel,
    GraftMarkerProgramCollection,
]:
    return (
        single_object(request, loaded, "graft_case", GraftCase),
        single_object(
            request, loaded, "graft_expression_asset", GraftExpressionAsset
        ),
        single_object(
            request,
            loaded,
            "graft_expression_analysis_spec",
            GraftExpressionAnalysisSpec,
        ),
        single_object(
            request, loaded, "graft_reference_panel", GraftReferencePanel
        ),
        single_object(
            request,
            loaded,
            "graft_marker_program_collection",
            GraftMarkerProgramCollection,
        ),
    )


def _binding_reasons(
    request: ToolRequestV2,
    loaded: LoadedInputs,
    spec: ToolPackageSpecV2,
) -> list[str]:
    case, asset, analysis_spec, reference_panel, programs = _objects(
        request, loaded
    )
    reasons: set[str] = set()
    if asset.graft_case_ref != case.graft_case_id:
        reasons.add("graft_case_binding_mismatch")
    if asset.assay_id != case.assay_id:
        reasons.add("graft_assay_binding_mismatch")
    if analysis_spec.reference_panel_ref != reference_panel.reference_panel_id:
        reasons.add("graft_reference_panel_binding_mismatch")
    if (
        analysis_spec.marker_program_collection_ref
        != programs.collection_id
    ):
        reasons.add("graft_marker_program_binding_mismatch")
    if asset.organism != reference_panel.organism:
        reasons.add("graft_reference_organism_mismatch")
    if asset.organism != programs.organism:
        reasons.add("graft_marker_program_organism_mismatch")
    if asset.gene_id_namespace != reference_panel.gene_id_namespace:
        reasons.add("graft_reference_gene_namespace_mismatch")
    if asset.gene_id_namespace != programs.gene_id_namespace:
        reasons.add("graft_marker_program_gene_namespace_mismatch")
    if asset.assay != reference_panel.assay:
        reasons.add("graft_reference_assay_mismatch")
    if asset.analysis_value_semantics != reference_panel.value_semantics:
        reasons.add("graft_reference_value_semantics_mismatch")
    if asset.analysis_value_semantics != programs.value_semantics:
        reasons.add("graft_marker_program_value_semantics_mismatch")
    if analysis_spec.method_ids != ANALYSIS_METHOD_IDS:
        reasons.add("graft_analysis_method_binding_mismatch")
    if not set(ANALYSIS_METHOD_IDS).issubset(spec.method_ids):
        reasons.add("graft_analysis_method_not_registered")
    output_root = request.output_dir.resolve(strict=False)
    resolved = asset.path.resolve(strict=False)
    if resolved == output_root or resolved.is_relative_to(output_root):
        reasons.add("graft_expression_output_overlap")
    reasons.update(_asset_file_reasons(asset, analysis_spec))
    return sorted(reasons)


def _asset_file_reasons(
    asset: GraftExpressionAsset,
    analysis_spec: GraftExpressionAnalysisSpec,
) -> set[str]:
    reasons: set[str] = set()
    try:
        metadata = asset.path.lstat()
        if not stat.S_ISREG(metadata.st_mode) or asset.path.is_symlink():
            return {"graft_expression_not_regular_file"}
        if metadata.st_size == 0:
            reasons.add("graft_expression_empty")
        if metadata.st_size > analysis_spec.max_file_bytes:
            return {"graft_expression_too_large"}
        if _file_digest(asset.path) != asset.sha256:
            return {"graft_expression_checksum_mismatch"}
    except FileNotFoundError:
        return {"graft_expression_not_found"}
    except OSError:
        return {"graft_expression_not_regular_file"}
    data: ad.AnnData | None = None
    try:
        data = sc.read_h5ad(asset.path, backed="r")
        if not isinstance(data, ad.AnnData):
            reasons.add("graft_expression_not_anndata")
            return reasons
        if data.n_obs * data.n_vars > analysis_spec.max_matrix_elements:
            return {"graft_expression_memory_budget_exceeded"}
        if data.n_obs < analysis_spec.minimum_cells:
            reasons.add("graft_expression_cell_count_below_minimum")
        if data.n_vars < analysis_spec.minimum_genes:
            reasons.add("graft_expression_gene_count_below_minimum")
        if asset.expression_layer != "X" and (
            asset.expression_layer not in data.layers
        ):
            reasons.add("graft_expression_layer_missing")
        required = {
            asset.sample_id_key,
            *asset.state_probability_columns.values(),
            *analysis_spec.required_obs_fields,
        }
        if asset.graft_id_key is not None:
            required.add(asset.graft_id_key)
        if not required.issubset(data.obs.columns):
            reasons.add("graft_expression_obs_fields_missing")
        gene_values = (
            data.var_names.astype(str).tolist()
            if asset.gene_symbol_key is None
            else (
                data.var[asset.gene_symbol_key].astype(str).tolist()
                if asset.gene_symbol_key in data.var
                else []
            )
        )
        if not gene_values:
            reasons.add("graft_expression_gene_symbols_missing")
        elif len(gene_values) != len(set(gene_values)):
            reasons.add("graft_expression_gene_symbols_not_unique")
    except (OSError, ValueError, KeyError):
        reasons.add("graft_expression_h5ad_invalid")
    finally:
        if data is not None and data.isbacked:
            data.file.close()
    try:
        if _file_digest(asset.path) != asset.sha256:
            reasons.add("graft_expression_modified_during_validation")
    except OSError:
        reasons.add("graft_expression_modified_during_validation")
    return reasons


def _file_digest(path: Path) -> str:
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or path.is_symlink():
        raise OSError("not a regular file")
    with path.open("rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
    after = path.lstat()
    if (
        before.st_dev != after.st_dev
        or before.st_ino != after.st_ino
        or before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
    ):
        raise OSError("file changed while hashing")
    return digest


def _asset_unchanged(asset: GraftExpressionAsset) -> bool:
    try:
        return _file_digest(asset.path) == asset.sha256
    except OSError:
        return False


def _analyze(
    *,
    request: ToolRequestV2,
    case: GraftCase,
    asset: GraftExpressionAsset,
    analysis_spec: GraftExpressionAnalysisSpec,
    reference_panel: GraftReferencePanel,
    programs: GraftMarkerProgramCollection,
    tool_version: str,
    input_hash: str,
) -> GraftExpressionAnalysisResult:
    try:
        data = sc.read_h5ad(asset.path)
    except (OSError, ValueError) as exc:
        raise GraftAnalysisError("graft_expression_h5ad_invalid") from exc
    if not isinstance(data, ad.AnnData):
        raise GraftAnalysisError("graft_expression_not_anndata")
    analysis = _analysis_view(data, asset)
    probabilities = _probabilities(analysis, asset, analysis_spec)
    samples = _labels(analysis.obs[asset.sample_id_key], "sample")
    grafts = (
        _labels(analysis.obs[asset.graft_id_key], "graft")
        if asset.graft_id_key is not None
        else None
    )
    gene_symbols = _gene_symbols(analysis, asset)
    analysis.var_names = gene_symbols
    composition = _composition(probabilities)
    reference_support, program_evidence = _expression_evidence(
        analysis=analysis,
        samples=samples,
        matrix_semantics=asset.matrix_semantics,
        reference_panel=reference_panel,
        programs=programs,
        analysis_spec=analysis_spec,
    )
    methods = {
        "METHOD-ANNDATA",
        "METHOD-BRIDGE-GRAFTCASE-VALIDATOR",
        "METHOD-BRIDGE-PSEUDOBULK-REFERENCE-CORRELATION-2C3A8F",
        "METHOD-BRIDGE-SOFT-COMPOSITION-404672",
        "METHOD-SCANPY",
    }
    reasons: set[str] = set()
    if grafts is None:
        reasons.add("graft_id_not_provided")
    if any(
        value is None
        for value in (
            case.animal_id,
            case.post_transplant_timepoint,
            case.biological_replicate_id,
        )
    ):
        reasons.add("graft_metadata_incomplete")
    if any(
        item.availability is AnalysisAvailability.UNAVAILABLE
        for item in reference_support
    ):
        reasons.add("graft_reference_support_partial")
    if any(
        item.availability is AnalysisAvailability.UNAVAILABLE
        for item in program_evidence
    ):
        reasons.add("graft_program_evidence_partial")
    row_sums = probabilities.sum(axis=1).to_numpy(dtype=float)
    return GraftExpressionAnalysisResult(
        object_version="0.1.0",
        result_id=f"graft-expression-analysis:{input_hash[:24]}",
        tool_id="P0-12",
        tool_version=tool_version,
        state="candidate",
        evidence_state="shadow",
        analysis_mode="expression_analysis",
        graft_case_ref=case.graft_case_id,
        asset_ref=asset.asset_id,
        analysis_spec_ref=analysis_spec.analysis_spec_id,
        reference_panel_ref=reference_panel.reference_panel_id,
        marker_program_collection_ref=programs.collection_id,
        assay=asset.assay,
        matrix_semantics=asset.matrix_semantics,
        analysis_value_semantics=asset.analysis_value_semantics,
        reference_source_family_id=reference_panel.source_family_id,
        marker_source_family_id=programs.source_family_id,
        qc_state="not_reassessed",
        composition_denominator="all_uploaded_rows",
        cell_count=analysis.n_obs,
        gene_count=analysis.n_vars,
        sample_count=len(set(samples.tolist())),
        graft_count=0 if grafts is None else len(set(grafts.tolist())),
        unassigned_fraction=float(
            np.clip(np.mean(1.0 - row_sums), 0.0, 1.0)
        ),
        composition_estimates=composition,
        reference_support=reference_support,
        program_evidence=program_evidence,
        source_bindings=_source_bindings(request),
        selected_method_ids=sorted(methods),
        runtime_versions=_runtime_versions(),
        reason_codes=sorted(reasons),
        created_at=asset.created_at,
    )


def _analysis_view(
    data: ad.AnnData,
    asset: GraftExpressionAsset,
) -> ad.AnnData:
    source = (
        data.X
        if asset.expression_layer == "X"
        else data.layers[asset.expression_layer]
    )
    result = ad.AnnData(
        X=source,
        obs=data.obs.copy(),
        var=data.var.copy(),
    )
    try:
        validate_expression_object(
            result,
            require_counts=(
                asset.matrix_semantics is GraftMatrixSemantics.RAW_COUNTS
            ),
        )
    except InputAuditError as exc:
        if exc.reason_code == "non_finite_expression_values":
            reason = "graft_expression_non_finite"
        elif (
            asset.matrix_semantics is GraftMatrixSemantics.RAW_COUNTS
            and exc.reason_code
            in {
                "negative_expression_values",
                "raw_counts_must_be_nonnegative_integers",
            }
        ):
            reason = "graft_expression_counts_invalid"
        elif exc.reason_code == "duplicate_cell_ids":
            reason = "graft_expression_cell_ids_invalid"
        elif exc.reason_code == "duplicate_gene_ids":
            reason = "graft_expression_gene_ids_invalid"
        else:
            reason = "graft_expression_matrix_invalid"
        raise GraftAnalysisError(reason) from exc
    return result


def _probabilities(
    data: ad.AnnData,
    asset: GraftExpressionAsset,
    analysis_spec: GraftExpressionAnalysisSpec,
) -> pd.DataFrame:
    ordered = sorted(asset.state_probability_columns.items())
    try:
        values = pd.DataFrame(
            {
                state_id: pd.to_numeric(
                    data.obs[column], errors="raise"
                ).to_numpy(dtype=float)
                for state_id, column in ordered
            },
            index=data.obs_names,
        )
    except (TypeError, ValueError) as exc:
        raise GraftAnalysisError(
            "graft_state_probabilities_invalid"
        ) from exc
    array = values.to_numpy(dtype=float)
    if (
        not np.isfinite(array).all()
        or np.any(array < -analysis_spec.probability_tolerance)
        or np.any(array > 1 + analysis_spec.probability_tolerance)
        or np.any(
            array.sum(axis=1) > 1 + analysis_spec.probability_tolerance
        )
    ):
        raise GraftAnalysisError("graft_state_probabilities_invalid")
    return values.clip(lower=0.0, upper=1.0)


def _labels(values: pd.Series, kind: str) -> np.ndarray:
    if values.isna().any():
        raise GraftAnalysisError(f"graft_{kind}_labels_invalid")
    labels = values.astype(str).to_numpy()
    if any(
        re.fullmatch(SAFE_ID_PATTERN, value) is None
        for value in labels
    ):
        raise GraftAnalysisError(f"graft_{kind}_labels_invalid")
    return labels


def _gene_symbols(
    data: ad.AnnData,
    asset: GraftExpressionAsset,
) -> list[str]:
    values = (
        data.var_names.astype(str).tolist()
        if asset.gene_symbol_key is None
        else data.var[asset.gene_symbol_key].astype(str).tolist()
    )
    if any(not value for value in values) or len(values) != len(set(values)):
        raise GraftAnalysisError("graft_expression_gene_symbols_invalid")
    return values


def _composition(
    probabilities: pd.DataFrame,
) -> list[GraftCompositionEstimate]:
    cell_count = len(probabilities)
    result: list[GraftCompositionEstimate] = []
    for state_id in sorted(probabilities.columns):
        cell_equivalent = float(probabilities[state_id].sum())
        result.append(
            GraftCompositionEstimate(
                state_id=state_id,
                mean_fraction=cell_equivalent / cell_count,
                cell_equivalent=cell_equivalent,
                denominator_cells=cell_count,
            )
        )
    return result


def _expression_evidence(
    *,
    analysis: ad.AnnData,
    samples: np.ndarray,
    matrix_semantics: GraftMatrixSemantics,
    reference_panel: GraftReferencePanel,
    programs: GraftMarkerProgramCollection,
    analysis_spec: GraftExpressionAnalysisSpec,
) -> tuple[list[GraftReferenceSupport], list[GraftProgramEvidence]]:
    requested_genes = sorted(
        {
            gene
            for profile in reference_panel.profiles
            for gene in profile.gene_values
        }
        | {
            gene
            for program in programs.programs
            for gene in program.genes
        }
    )
    present = [gene for gene in requested_genes if gene in analysis.var_names]
    gene_index = {
        gene: int(analysis.var_names.get_loc(gene)) for gene in present
    }
    pseudobulk = _sample_profiles(
        analysis.X, samples, matrix_semantics
    )
    reference_result: list[GraftReferenceSupport] = []
    for sample_id, values in pseudobulk.items():
        for profile in reference_panel.profiles:
            shared = sorted(set(profile.gene_values).intersection(gene_index))
            correlation: float | None = None
            reasons: list[str] = []
            if len(shared) < analysis_spec.minimum_reference_genes:
                reasons.append("graft_reference_gene_coverage_insufficient")
            else:
                observed = np.array(
                    [values[gene_index[gene]] for gene in shared],
                    dtype=float,
                )
                reference = np.array(
                    [profile.gene_values[gene] for gene in shared],
                    dtype=float,
                )
                if np.ptp(observed) == 0 or np.ptp(reference) == 0:
                    reasons.append("graft_reference_correlation_undefined")
                else:
                    value = float(spearmanr(observed, reference).statistic)
                    if np.isfinite(value):
                        correlation = value
                    else:
                        reasons.append(
                            "graft_reference_correlation_undefined"
                        )
            reference_result.append(
                GraftReferenceSupport(
                    sample_id=sample_id,
                    profile_id=profile.profile_id,
                    availability=(
                        AnalysisAvailability.AVAILABLE
                        if correlation is not None
                        else AnalysisAvailability.UNAVAILABLE
                    ),
                    spearman_correlation=correlation,
                    shared_gene_count=len(shared),
                    reason_codes=sorted(reasons),
                )
            )
    program_result: list[GraftProgramEvidence] = []
    for sample_id, values in pseudobulk.items():
        for program in programs.programs:
            shared = sorted(set(program.genes).intersection(gene_index))
            score: float | None = None
            reasons: list[str] = []
            if len(shared) < analysis_spec.minimum_program_genes:
                reasons.append("graft_program_gene_coverage_insufficient")
            else:
                score = float(
                    np.mean([values[gene_index[gene]] for gene in shared])
                )
            program_result.append(
                GraftProgramEvidence(
                    sample_id=sample_id,
                    program_id=program.program_id,
                    availability=(
                        AnalysisAvailability.AVAILABLE
                        if score is not None
                        else AnalysisAvailability.UNAVAILABLE
                    ),
                    mean_expression=score,
                    gene_count=len(shared),
                    gene_coverage=len(shared) / len(program.genes),
                    reason_codes=sorted(reasons),
                )
            )
    return reference_result, program_result


def _sample_profiles(
    matrix: Any,
    samples: np.ndarray,
    matrix_semantics: GraftMatrixSemantics,
) -> dict[str, np.ndarray]:
    sample_ids = sorted(set(samples.tolist()))
    rows: list[np.ndarray] = []
    for sample_id in sample_ids:
        selected = matrix[samples == sample_id]
        if sparse.issparse(selected):
            aggregate = (
                selected.sum(axis=0)
                if matrix_semantics is GraftMatrixSemantics.RAW_COUNTS
                else selected.mean(axis=0)
            )
            row = np.asarray(aggregate).ravel()
        else:
            values = np.asarray(selected, dtype=float)
            row = (
                values.sum(axis=0)
                if matrix_semantics is GraftMatrixSemantics.RAW_COUNTS
                else values.mean(axis=0)
            )
        rows.append(np.asarray(row, dtype=float))
    values = np.vstack(rows)
    if matrix_semantics is GraftMatrixSemantics.RAW_COUNTS:
        pseudobulk = ad.AnnData(X=values)
        sc.pp.normalize_total(pseudobulk, target_sum=10_000)
        sc.pp.log1p(pseudobulk)
        values = np.asarray(pseudobulk.X, dtype=float)
    return {
        sample_id: values[index]
        for index, sample_id in enumerate(sample_ids)
    }


def _source_bindings(request: ToolRequestV2) -> list[GraftSourceBinding]:
    return [
        GraftSourceBinding(
            input_id=ref.input_id,
            role=ref.role,
            schema_ref=ref.schema_ref,
            object_version="0.1.0",
            source_sha256=ref.sha256,
        )
        for ref in sorted(request.object_inputs, key=lambda value: value.role)
    ]


def _runtime_versions() -> dict[str, str]:
    result: dict[str, str] = {}
    for package in ("anndata", "numpy", "pandas", "scanpy", "scipy"):
        try:
            result[package] = version(package)
        except PackageNotFoundError:
            result[package] = "unavailable"
    return dict(sorted(result.items()))


def _input_hash(
    request: ToolRequestV2,
    spec: ToolPackageSpecV2,
) -> str:
    asset_ref = next(
        (
            ref
            for ref in request.object_inputs
            if ref.role == "graft_expression_asset"
        ),
        None,
    )
    payload = {
        "tool_id": spec.tool_id,
        "tool_version": spec.version,
        "environment_spec_id": spec.environment_spec_id,
        "mode": "expression_analysis",
        "asset_manifest_sha256": (
            None if asset_ref is None else asset_ref.sha256
        ),
        "object_inputs": [
            {
                "role": ref.role,
                "schema_ref": ref.schema_ref,
                "object_version": ref.object_version,
                "sha256": ref.sha256,
                "media_type": ref.media_type,
            }
            for ref in sorted(request.object_inputs, key=lambda value: value.role)
        ],
    }
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def _manifest_payload(
    request: ToolRequestV2,
    spec: ToolPackageSpecV2,
    run_id: str,
    input_hash: str,
    result_bytes: bytes,
) -> dict[str, object]:
    return {
        "manifest_version": "0.1.0",
        "tool_id": spec.tool_id,
        "tool_version": spec.version,
        "run_id": run_id,
        "input_hash": input_hash,
        "inputs": [
            {
                "input_id": ref.input_id,
                "role": ref.role,
                "schema_ref": ref.schema_ref,
                "object_version": ref.object_version,
                "sha256": ref.sha256,
                "media_type": ref.media_type,
            }
            for ref in sorted(request.object_inputs, key=lambda value: value.role)
        ],
        "artifacts": [
            {
                "filename": "graft_expression_analysis_result.json",
                "media_type": "application/json",
                "sha256": hashlib.sha256(result_bytes).hexdigest(),
            }
        ],
    }


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
        fingerprint_input_key="graft_expression_inputs",
        input_hash=input_hash,
    )


def _failed_v1_request(
    request: ToolRequest,
    spec: ToolPackageSpecV2,
) -> ToolRunV2:
    return _failed_run(
        request_v2_from_v1(request),
        spec,
        ["tool_request_v2_required"],
    )
