"""Selected-view descriptive measurements; never a product assessment."""

from __future__ import annotations

from io import BytesIO

import numpy as np
import pandas as pd

from bridge.tool_packages._configurable_contracts import observation_ids_sha256
from bridge.tool_packages.p0_06_proliferation_stress_response.exploratory_models import (
    ExploratoryCellCycleSummary,
    ExploratoryMethodParameters,
    ExploratoryProcessInput,
    ExploratoryProcessProfile,
    ExploratoryProgramSummary,
)
from bridge.tool_packages.p0_06_proliferation_stress_response.method_models import (
    ProcessMethodId,
)
from bridge.tool_packages.p0_06_proliferation_stress_response.method_runtime import (
    METHOD_REFS,
    ProcessMethodError,
    _execution,
    _package_versions,
    _require_module,
    load_expression_matrix,
)
from bridge.toolkit.contracts import InputAsset, ToolPackageSpecV2


def exploratory_binding_reasons(
    source: ExploratoryProcessInput,
    asset: InputAsset,
    spec: ToolPackageSpecV2,
) -> list[str]:
    view = source.data_view
    reasons = []
    if (
        asset.asset_id,
        asset.checksum,
        asset.matrix_location,
        asset.matrix_semantics,
    ) != (view.artifact_id, view.sha256, view.matrix_location, view.matrix_semantics):
        reasons.append("expression_data_view_mismatch")
    if asset.assay not in {"scRNA-seq", "snRNA-seq"}:
        reasons.append("single_cell_or_nucleus_expression_required")
    if any(ref not in spec.method_ids for ref, _ in METHOD_REFS.values()):
        reasons.append("process_method_not_registered")
    return reasons


def _summary(program, method, genes, missing, ambiguous, scores, n, reason):
    values = {}
    if scores is not None:
        scores = np.asarray(scores, dtype=float)
        if scores.shape != (n,) or not np.isfinite(scores).all():
            reason = "method_scores_nonfinite_or_misaligned"
        else:
            values = dict(
                mean=float(scores.mean()),
                median=float(np.median(scores)),
                lower_quantile=float(np.quantile(scores, 0.1)),
                upper_quantile=float(np.quantile(scores, 0.9)),
            )
    return ExploratoryProgramSummary(
        program_id=program,
        method_id=method,
        score_unit=(
            "scanpy_control_adjusted_expression"
            if method == ProcessMethodId.SCANPY_SCORE_GENES
            else "decoupler_ulm_t_value"
        ),
        n_observations=n,
        observed_gene_count=len(genes) - len(missing) - len(ambiguous),
        declared_gene_count=len(genes),
        missing_genes=missing,
        ambiguous_genes=ambiguous,
        assessment_state="available" if values else "not_assessed",
        reason_codes=[] if values else [reason or "method_output_unavailable"],
        **values,
    )


def measure_exploratory_process(
    *,
    source: ExploratoryProcessInput,
    asset: InputAsset,
    tool_version: str,
    input_sha256: str,
    run_id: str,
    random_seed: int,
) -> tuple[ExploratoryProcessProfile, bytes]:
    # Original feature IDs are the identity; symbols are only lookup metadata.
    adata = load_expression_matrix(asset=asset, gene_symbol_column=None)
    obs = adata.obs_names.astype(str).tolist()
    if (
        len(obs) != source.data_view.n_observations
        or observation_ids_sha256(obs) != source.data_view.observation_ids_sha256
    ):
        raise ProcessMethodError("expression_observation_set_mismatch")
    if adata.n_vars == 0:
        raise ProcessMethodError("expression_features_empty")
    n = adata.n_obs
    genes = {"S": source.s_genes, "G2M": source.g2m_genes}
    if source.gene_symbol_column is None:
        symbols = adata.var_names.astype(str).tolist()
    else:
        if source.gene_symbol_column not in adata.var:
            raise ProcessMethodError("gene_symbol_column_missing")
        column = adata.var[source.gene_symbol_column]
        if column.isna().any():
            raise ProcessMethodError("gene_symbols_invalid")
        symbols = column.astype(str).tolist()
    if any(not symbol or any(c.isspace() for c in symbol) for symbol in symbols):
        raise ProcessMethodError("gene_symbols_invalid")
    features_by_symbol: dict[str, list[str]] = {}
    for feature, symbol in zip(adata.var_names, symbols, strict=True):
        features_by_symbol.setdefault(symbol, []).append(str(feature))
    requested = set(source.s_genes + source.g2m_genes)
    target_feature_ids = {
        symbol: features[0]
        for symbol, features in features_by_symbol.items()
        if symbol in requested and len(features) == 1
    }
    missing = {
        key: sorted(set(value) - features_by_symbol.keys())
        for key, value in genes.items()
    }
    ambiguous = {
        key: sorted(gene for gene in value if len(features_by_symbol.get(gene, [])) > 1)
        for key, value in genes.items()
    }
    resolution_reasons = {
        key: (
            "program_gene_identifier_ambiguous"
            if ambiguous[key]
            else "program_gene_coverage_insufficient" if missing[key] else None
        )
        for key in genes
    }
    targets_by_program = {
        key: [target_feature_ids[gene] for gene in value if gene in target_feature_ids]
        for key, value in genes.items()
    }
    rows = pd.DataFrame({"observation_id": obs}, index=adata.obs_names)
    params = ExploratoryMethodParameters(
        random_seed=random_seed,
        cell_cycle_ctrl_size=min(len(source.s_genes), len(source.g2m_genes)),
    )
    summaries = []
    versions = _package_versions()
    executions = []

    for program, targets in genes.items():
        scores, reason = None, None
        if resolution_reasons[program]:
            reason = resolution_reasons[program]
        else:
            try:
                scanpy = _require_module("scanpy")
                column = f"scanpy_{program}"
                scanpy.tl.score_genes(
                    adata,
                    targets_by_program[program],
                    ctrl_size=params.scanpy_ctrl_size,
                    n_bins=params.scanpy_n_bins,
                    ctrl_as_ref=params.scanpy_ctrl_as_ref,
                    random_state=random_seed,
                    use_raw=False,
                    layer=None,
                    score_name=column,
                    copy=False,
                )
                scores = np.asarray(adata.obs[column], dtype=float)
            except ProcessMethodError as exc:
                reason = exc.reason_code
            except Exception:
                reason = "scanpy_score_genes_failed"
        summary = _summary(
            program,
            ProcessMethodId.SCANPY_SCORE_GENES,
            targets,
            missing[program],
            ambiguous[program],
            scores,
            n,
            reason,
        )
        summaries.append(summary)
        rows[f"scanpy_{program}"] = (
            scores if summary.assessment_state == "available" else np.nan
        )

    activities = pd.DataFrame(index=adata.obs_names)
    ulm_reason = None
    net = [
        {"source": program, "target": gene, "weight": 1.0}
        for program, targets in targets_by_program.items()
        if not resolution_reasons[program]
        for gene in targets
    ]
    if net:
        try:
            decoupler = _require_module("decoupler")
            output = decoupler.mt.ulm(
                data=adata,
                net=pd.DataFrame(net),
                tmin=params.decoupler_tmin,
                layer=None,
                raw=False,
                empty=False,
                verbose=False,
            )
            activities = (
                output[0] if isinstance(output, tuple) else adata.obsm["score_ulm"]
            )
            if (
                not isinstance(activities, pd.DataFrame)
                or not activities.index.is_unique
            ):
                raise ValueError("ULM output must identify observations")
            if set(activities.index) != set(adata.obs_names):
                raise ValueError("ULM observation set changed")
            activities = activities.reindex(adata.obs_names)
        except ProcessMethodError as exc:
            ulm_reason = exc.reason_code
        except Exception:
            ulm_reason = "decoupler_ulm_failed"
    for program, targets in genes.items():
        reason = resolution_reasons[program] or ulm_reason
        scores = (
            None
            if reason or program not in activities
            else activities[program].to_numpy()
        )
        summary = _summary(
            program,
            ProcessMethodId.DECOUPLER_ULM,
            targets,
            missing[program],
            ambiguous[program],
            scores,
            n,
            reason,
        )
        summaries.append(summary)
        rows[f"ulm_{program}"] = (
            scores if summary.assessment_state == "available" else np.nan
        )

    for method in (ProcessMethodId.SCANPY_SCORE_GENES, ProcessMethodId.DECOUPLER_ULM):
        selected = [s for s in summaries if s.method_id == method]
        executions.append(
            _execution(
                method,
                sum(s.assessment_state == "available" for s in selected),
                [r for s in selected for r in s.reason_codes],
                versions,
            )
        )

    cycle_values = {}
    cycle_reason = None
    if ambiguous["S"] or ambiguous["G2M"]:
        cycle_reason = "cell_cycle_gene_identifier_ambiguous"
    elif missing["S"] or missing["G2M"]:
        cycle_reason = "cell_cycle_gene_coverage_insufficient"
    else:
        try:
            scanpy = _require_module("scanpy")
            scanpy.tl.score_genes_cell_cycle(
                adata,
                s_genes=targets_by_program["S"],
                g2m_genes=targets_by_program["G2M"],
                ctrl_as_ref=params.scanpy_ctrl_as_ref,
                n_bins=params.scanpy_n_bins,
                random_state=random_seed,
                use_raw=False,
                layer=None,
                copy=False,
            )
            s_scores = np.asarray(adata.obs["S_score"], dtype=float)
            g2m_scores = np.asarray(adata.obs["G2M_score"], dtype=float)
            phases = np.asarray(adata.obs["phase"], dtype=object)
            if (
                not np.isfinite(s_scores).all()
                or not np.isfinite(g2m_scores).all()
                or not set(phases).issubset({"G1", "S", "G2M"})
            ):
                raise ValueError("nonfinite scores or unrecognized phase")
            counts = {
                label: int(np.sum(phases == label)) for label in ("G1", "S", "G2M")
            }
            cycle_values = dict(
                phase_counts=counts,
                s_g2m_fraction=(counts["S"] + counts["G2M"]) / n,
                mean_s_score=float(s_scores.mean()),
                mean_g2m_score=float(g2m_scores.mean()),
            )
            rows["cycle_S_score"], rows["cycle_G2M_score"], rows["phase"] = (
                s_scores,
                g2m_scores,
                phases,
            )
        except ProcessMethodError as exc:
            cycle_reason = exc.reason_code
        except Exception:
            cycle_reason = "scanpy_cell_cycle_failed"
    if not cycle_values:
        rows["cycle_S_score"], rows["cycle_G2M_score"], rows["phase"] = (
            np.nan,
            np.nan,
            None,
        )
    cycle = ExploratoryCellCycleSummary(
        n_observations=n,
        s_missing_genes=missing["S"],
        g2m_missing_genes=missing["G2M"],
        s_ambiguous_genes=ambiguous["S"],
        g2m_ambiguous_genes=ambiguous["G2M"],
        assessment_state="available" if cycle_values else "not_assessed",
        reason_codes=[] if cycle_values else [cycle_reason or "cell_cycle_unavailable"],
        **cycle_values,
    )
    for method in (
        ProcessMethodId.SCANPY_CELL_CYCLE,
        ProcessMethodId.CELL_CYCLE_AGGREGATION,
    ):
        executions.append(
            _execution(method, int(bool(cycle_values)), cycle.reason_codes, versions)
        )
    profile = ExploratoryProcessProfile(
        profile_id=f"exploratory-process:{run_id.removeprefix('run-')}",
        tool_version=tool_version,
        input_sha256=input_sha256,
        expression_asset_sha256=asset.checksum,
        input_contract=source,
        method_parameters=params,
        normalization_recipe=(
            "normalize_total_10000_log1p"
            if asset.matrix_semantics == "raw_counts"
            else "declared_normalized_expression"
        ),
        evidence_family_id=f"family:{source.source_family_id}:expression:{asset.checksum[:16]}",
        n_observations=n,
        n_features=adata.n_vars,
        target_feature_ids=target_feature_ids,
        duplicated_background_symbol_count=sum(
            len(features) > 1
            for symbol, features in features_by_symbol.items()
            if symbol not in requested
        ),
        executions=executions,
        program_summaries=summaries,
        cell_cycle=cycle,
        created_at=source.created_at,
        limitations=[
            "same_expression_family_not_independent_evidence",
            "different_score_units_not_combined",
            "observations_are_not_biological_replicates",
            "quantiles_describe_cells_not_confidence_intervals",
            "predicted_phase_not_division_rate_or_quiescence_proof",
            "state_roles_unreviewed_no_target_purity",
            "stress_not_assessed_no_stress_resource",
            "no_product_acceptance_or_release_assessment",
            "qc_not_reassessed",
        ],
    )
    table = BytesIO()
    rows.reset_index(drop=True).to_parquet(table, index=False)
    return profile, table.getvalue()
