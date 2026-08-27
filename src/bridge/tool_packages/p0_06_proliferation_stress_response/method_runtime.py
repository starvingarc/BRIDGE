from __future__ import annotations

import importlib
import math
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from typing import Any

import numpy as np
import pandas as pd
from scipy import sparse
from scipy.stats import spearmanr

from bridge.tool_packages._configurable_contracts import (
    BiologicalUnitAssignmentArtifact,
)
from bridge.tool_packages.p0_06_proliferation_stress_response.method_models import (
    CellCycleSummary,
    MethodAgreementRecord,
    MethodExecutionRecord,
    MethodExecutionState,
    ObservationState,
    ProcessMethodBundle,
    ProcessMethodId,
    ProcessMethodInput,
    ProcessMethodSpec,
    ProgramScoreSummary,
)
from bridge.tool_packages.p0_06_proliferation_stress_response.models import (
    AnalysisScope,
    ProgramRule,
    ProgramSpec,
)
from bridge.toolkit.contracts import InputAsset


METHOD_REFS = {
    ProcessMethodId.SCANPY_SCORE_GENES: (
        "METHOD-SCANPY-SCORE-GENES",
        "scanpy.tl.score_genes",
    ),
    ProcessMethodId.DECOUPLER_ULM: (
        "METHOD-DECOUPLER",
        "decoupler.mt.ulm",
    ),
    ProcessMethodId.SCANPY_CELL_CYCLE: (
        "METHOD-SCANPY-SCORE-GENES-CELL-CYCLE",
        "scanpy.tl.score_genes_cell_cycle",
    ),
    ProcessMethodId.CELL_CYCLE_AGGREGATION: (
        "METHOD-BRIDGE-SAMPLE-STATE-AGGREGATION",
        "BRIDGE sample/state phase aggregation",
    ),
}


class ProcessMethodError(RuntimeError):
    def __init__(self, reason_code: str, detail: str | None = None) -> None:
        self.reason_code = reason_code
        super().__init__(f"{reason_code}: {detail}" if detail else reason_code)


@dataclass(frozen=True)
class _ExpressionData:
    adata: Any
    observation_ids: np.ndarray
    genes: np.ndarray
    analysis_units: np.ndarray
    independence_groups: np.ndarray
    state_ids: np.ndarray


@dataclass(frozen=True)
class _SummaryGroup:
    scope: AnalysisScope
    analysis_unit_ref: str
    independence_group_ref: str
    state_id: str | None
    mask: np.ndarray


def _require_module(name: str) -> Any:
    try:
        return importlib.import_module(name)
    except ImportError as exc:
        raise ProcessMethodError(f"{name}_runtime_unavailable") from exc


def _package_versions() -> dict[str, str]:
    result: dict[str, str] = {}
    for package in ("anndata", "scanpy", "decoupler", "numpy", "scipy"):
        try:
            result[package] = version(package)
        except PackageNotFoundError:
            result[package] = "unavailable"
    return result


def _load_expression(
    *,
    asset: InputAsset,
    method_spec: ProcessMethodSpec,
    method_input: ProcessMethodInput,
    assignment: BiologicalUnitAssignmentArtifact,
) -> _ExpressionData:
    anndata = _require_module("anndata")
    try:
        adata = anndata.read_h5ad(asset.path)
    except (OSError, ValueError) as exc:
        raise ProcessMethodError("expression_asset_unreadable", str(exc)) from exc
    observation_ids = np.asarray(adata.obs_names.astype(str), dtype=object)
    if len(observation_ids) == 0:
        raise ProcessMethodError("expression_view_empty")
    if len(set(observation_ids.tolist())) != len(observation_ids):
        raise ProcessMethodError("expression_observation_ids_not_unique")

    if method_spec.gene_symbol_column is None:
        genes = np.asarray(adata.var_names.astype(str), dtype=object)
    else:
        if method_spec.gene_symbol_column not in adata.var:
            raise ProcessMethodError("gene_symbol_column_missing")
        genes = np.asarray(
            adata.var[method_spec.gene_symbol_column].astype(str), dtype=object
        )
    if any(not gene or any(char.isspace() for char in gene) for gene in genes):
        raise ProcessMethodError("gene_symbols_invalid")
    if len(set(genes.tolist())) != len(genes):
        raise ProcessMethodError("gene_symbols_not_unique")
    adata.var_names = pd.Index(genes)

    if method_spec.expression_layer is None:
        matrix = adata.X
    else:
        if method_spec.expression_layer not in adata.layers:
            raise ProcessMethodError("expression_layer_missing")
        matrix = adata.layers[method_spec.expression_layer]
    values = matrix.data if sparse.issparse(matrix) else np.asarray(matrix)
    if not np.isfinite(values).all():
        raise ProcessMethodError("expression_matrix_nonfinite")

    assignment_by_id = {
        item.observation_id: item for item in assignment.assignments
    }
    state_by_id = {
        item.observation_id: item for item in method_input.observation_states
    }
    observed = set(observation_ids.tolist())
    if observed != set(assignment_by_id):
        raise ProcessMethodError("expression_biological_unit_set_mismatch")
    if observed != set(state_by_id):
        raise ProcessMethodError("expression_state_assignment_set_mismatch")
    analysis_units = np.asarray(
        [assignment_by_id[item].analysis_unit_ref for item in observation_ids],
        dtype=object,
    )
    independence_groups = np.asarray(
        [assignment_by_id[item].independence_group_ref for item in observation_ids],
        dtype=object,
    )
    state_ids = np.asarray(
        [
            state_by_id[item].state_id
            if state_by_id[item].state is ObservationState.CANDIDATE
            else None
            for item in observation_ids
        ],
        dtype=object,
    )
    return _ExpressionData(
        adata=adata,
        observation_ids=observation_ids,
        genes=genes,
        analysis_units=analysis_units,
        independence_groups=independence_groups,
        state_ids=state_ids,
    )


def _groups(
    data: _ExpressionData,
    scopes: set[AnalysisScope],
    allowed_state_ids: set[str],
) -> list[_SummaryGroup]:
    result: list[_SummaryGroup] = []
    for unit in sorted(set(data.analysis_units.tolist())):
        unit_mask = data.analysis_units == unit
        groups = sorted(set(data.independence_groups[unit_mask].tolist()))
        if len(groups) != 1:
            raise ProcessMethodError("analysis_unit_independence_group_ambiguous")
        independence_group = str(groups[0])
        if AnalysisScope.WHOLE_PRODUCT in scopes:
            result.append(
                _SummaryGroup(
                    scope=AnalysisScope.WHOLE_PRODUCT,
                    analysis_unit_ref=str(unit),
                    independence_group_ref=independence_group,
                    state_id=None,
                    mask=unit_mask,
                )
            )
        if AnalysisScope.STATE_SPECIFIC in scopes:
            observed_states = {
                str(value)
                for value in data.state_ids[unit_mask].tolist()
                if value is not None and str(value) in allowed_state_ids
            }
            for state_id in sorted(observed_states):
                result.append(
                    _SummaryGroup(
                        scope=AnalysisScope.STATE_SPECIFIC,
                        analysis_unit_ref=str(unit),
                        independence_group_ref=independence_group,
                        state_id=state_id,
                        mask=unit_mask & (data.state_ids == state_id),
                    )
                )
    return result


def _program_summaries(
    *,
    method_id: ProcessMethodId,
    program_id: str,
    scores: np.ndarray | None,
    groups: list[_SummaryGroup],
    observed_gene_count: int,
    declared_gene_count: int,
    score_unit: str,
    spec: ProcessMethodSpec,
    unavailable_reason: str | None,
) -> list[ProgramScoreSummary]:
    coverage = observed_gene_count / declared_gene_count
    result: list[ProgramScoreSummary] = []
    for group in groups:
        n_observations = int(group.mask.sum())
        reason = unavailable_reason
        if reason is None and n_observations < spec.minimum_cells_per_summary:
            reason = "summary_cell_count_insufficient"
        if reason is not None or scores is None:
            result.append(
                ProgramScoreSummary(
                    method_id=method_id,
                    program_id=program_id,
                    analysis_scope=group.scope,
                    analysis_unit_ref=group.analysis_unit_ref,
                    independence_group_ref=group.independence_group_ref,
                    cell_state_id=group.state_id,
                    n_observations=n_observations,
                    observed_gene_count=observed_gene_count,
                    declared_gene_count=declared_gene_count,
                    gene_coverage=float(coverage),
                    score_unit=score_unit,
                    assessment_state="not_assessed",
                    reason_codes=[reason or "method_output_unavailable"],
                )
            )
            continue
        values = np.asarray(scores[group.mask], dtype=float)
        if not np.isfinite(values).all():
            raise ProcessMethodError("program_score_nonfinite")
        result.append(
            ProgramScoreSummary(
                method_id=method_id,
                program_id=program_id,
                analysis_scope=group.scope,
                analysis_unit_ref=group.analysis_unit_ref,
                independence_group_ref=group.independence_group_ref,
                cell_state_id=group.state_id,
                n_observations=n_observations,
                observed_gene_count=observed_gene_count,
                declared_gene_count=declared_gene_count,
                gene_coverage=float(coverage),
                score_unit=score_unit,
                mean=float(values.mean()),
                median=float(np.median(values)),
                lower_quantile=float(np.quantile(values, spec.lower_quantile)),
                upper_quantile=float(np.quantile(values, spec.upper_quantile)),
                assessment_state="available",
                reason_codes=[],
            )
        )
    return result


def _scanpy_program_scores(
    data: _ExpressionData,
    method_spec: ProcessMethodSpec,
    rules: dict[str, ProgramRule],
    random_seed: int,
) -> tuple[list[ProgramScoreSummary], list[str]]:
    scanpy = _require_module("scanpy")
    results: list[ProgramScoreSummary] = []
    limitations: set[str] = set()
    genes = set(data.genes.tolist())
    for index, program in enumerate(method_spec.programs):
        rule = rules[program.program_id]
        positive = [item.gene for item in rule.targets if item.weight > 0]
        observed = [gene for gene in positive if gene in genes]
        coverage = len(observed) / len(positive) if positive else 0.0
        reason = None
        scores = None
        if len(observed) < 2 or coverage < rule.minimum_gene_coverage:
            reason = "program_gene_coverage_insufficient"
        else:
            score_name = f"_bridge_program_{index}"
            try:
                scanpy.tl.score_genes(
                    data.adata,
                    observed,
                    ctrl_as_ref=method_spec.scanpy_ctrl_as_ref,
                    ctrl_size=method_spec.scanpy_ctrl_size,
                    n_bins=method_spec.scanpy_n_bins,
                    score_name=score_name,
                    random_state=random_seed,
                    copy=False,
                    use_raw=False,
                    layer=method_spec.expression_layer,
                )
            except Exception as exc:
                raise ProcessMethodError(
                    "scanpy_score_genes_failed", str(exc)
                ) from exc
            scores = np.asarray(data.adata.obs[score_name], dtype=float)
        if any(item.weight != 1.0 for item in rule.targets):
            limitations.add("scanpy_target_weights_not_applied")
        if any(item.weight < 0 for item in rule.targets):
            limitations.add("scanpy_negative_targets_not_scored")
        scopes = set(method_spec.selected_analysis_scopes).intersection(
            rule.allowed_analysis_scopes
        )
        results.extend(
            _program_summaries(
                method_id=ProcessMethodId.SCANPY_SCORE_GENES,
                program_id=program.program_id,
                scores=scores,
                groups=_groups(data, scopes, set(rule.allowed_state_ids)),
                observed_gene_count=len(observed),
                declared_gene_count=max(1, len(positive)),
                score_unit="scanpy_control_adjusted_expression",
                spec=method_spec,
                unavailable_reason=reason,
            )
        )
    return results, sorted(limitations)


def _decoupler_program_scores(
    data: _ExpressionData,
    method_spec: ProcessMethodSpec,
    rules: dict[str, ProgramRule],
) -> list[ProgramScoreSummary]:
    decoupler = _require_module("decoupler")
    genes = set(data.genes.tolist())
    network_rows: list[dict[str, str | float]] = []
    observed_by_program: dict[str, list[str]] = {}
    for program in method_spec.programs:
        targets = rules[program.program_id].targets
        observed = [item for item in targets if item.gene in genes]
        observed_by_program[program.program_id] = [item.gene for item in observed]
        network_rows.extend(
            {
                "source": program.program_id,
                "target": item.gene,
                "weight": item.weight,
            }
            for item in observed
        )
    activities = pd.DataFrame(index=data.adata.obs_names)
    if network_rows:
        try:
            output = decoupler.mt.ulm(
                data=data.adata,
                net=pd.DataFrame(network_rows),
                tmin=method_spec.decoupler_tmin,
                layer=method_spec.expression_layer,
                raw=False,
                verbose=False,
            )
        except Exception as exc:
            raise ProcessMethodError("decoupler_ulm_failed", str(exc)) from exc
        if isinstance(output, tuple):
            activities = output[0]
        elif "score_ulm" in data.adata.obsm:
            activities = data.adata.obsm["score_ulm"]
        if not isinstance(activities, pd.DataFrame):
            activities = pd.DataFrame(
                np.asarray(activities),
                index=data.adata.obs_names,
            )

    results: list[ProgramScoreSummary] = []
    for program in method_spec.programs:
        rule = rules[program.program_id]
        observed = observed_by_program[program.program_id]
        coverage = len(observed) / len(rule.targets)
        available = (
            len(observed) >= method_spec.decoupler_tmin
            and coverage >= rule.minimum_gene_coverage
            and program.program_id in activities.columns
        )
        scores = (
            np.asarray(activities[program.program_id], dtype=float)
            if available
            else None
        )
        scopes = set(method_spec.selected_analysis_scopes).intersection(
            rule.allowed_analysis_scopes
        )
        results.extend(
            _program_summaries(
                method_id=ProcessMethodId.DECOUPLER_ULM,
                program_id=program.program_id,
                scores=scores,
                groups=_groups(data, scopes, set(rule.allowed_state_ids)),
                observed_gene_count=len(observed),
                declared_gene_count=len(rule.targets),
                score_unit="decoupler_ulm_t_value",
                spec=method_spec,
                unavailable_reason=(
                    None if available else "program_gene_coverage_insufficient"
                ),
            )
        )
    return results


def _cell_cycle_summaries(
    data: _ExpressionData,
    method_spec: ProcessMethodSpec,
    rule: ProgramRule,
    random_seed: int,
) -> list[CellCycleSummary]:
    if method_spec.cell_cycle is None:
        return []
    genes = set(data.genes.tolist())
    s_genes = [gene for gene in rule.s_genes if gene in genes]
    g2m_genes = [gene for gene in rule.g2m_genes if gene in genes]
    s_coverage = len(s_genes) / len(rule.s_genes)
    g2m_coverage = len(g2m_genes) / len(rule.g2m_genes)
    reason = None
    if (
        len(s_genes) < 2
        or len(g2m_genes) < 2
        or s_coverage < rule.minimum_gene_coverage
        or g2m_coverage < rule.minimum_gene_coverage
    ):
        reason = "cell_cycle_gene_coverage_insufficient"
    if reason is None:
        scanpy = _require_module("scanpy")
        try:
            scanpy.tl.score_genes_cell_cycle(
                data.adata,
                s_genes=s_genes,
                g2m_genes=g2m_genes,
                copy=False,
                ctrl_as_ref=method_spec.scanpy_ctrl_as_ref,
                n_bins=method_spec.scanpy_n_bins,
                random_state=random_seed,
                use_raw=False,
                layer=method_spec.expression_layer,
            )
        except Exception as exc:
            raise ProcessMethodError(
                "scanpy_cell_cycle_failed", str(exc)
            ) from exc
    scopes = set(method_spec.selected_analysis_scopes).intersection(
        rule.allowed_analysis_scopes
    )
    result: list[CellCycleSummary] = []
    for group in _groups(data, scopes, set(rule.allowed_state_ids)):
        n_observations = int(group.mask.sum())
        group_reason = reason
        if group_reason is None and n_observations < method_spec.minimum_cells_per_summary:
            group_reason = "summary_cell_count_insufficient"
        if group_reason is not None:
            result.append(
                CellCycleSummary(
                    analysis_scope=group.scope,
                    analysis_unit_ref=group.analysis_unit_ref,
                    independence_group_ref=group.independence_group_ref,
                    cell_state_id=group.state_id,
                    n_observations=n_observations,
                    s_gene_coverage=float(s_coverage),
                    g2m_gene_coverage=float(g2m_coverage),
                    phase_counts={"G1": 0, "S": 0, "G2M": 0},
                    assessment_state="not_assessed",
                    reason_codes=[group_reason],
                )
            )
            continue
        s_scores = np.asarray(data.adata.obs["S_score"], dtype=float)[group.mask]
        g2m_scores = np.asarray(data.adata.obs["G2M_score"], dtype=float)[group.mask]
        phases = np.asarray(data.adata.obs["phase"], dtype=object)[group.mask]
        counts = {phase: int(np.sum(phases == phase)) for phase in ("G1", "S", "G2M")}
        result.append(
            CellCycleSummary(
                analysis_scope=group.scope,
                analysis_unit_ref=group.analysis_unit_ref,
                independence_group_ref=group.independence_group_ref,
                cell_state_id=group.state_id,
                n_observations=n_observations,
                s_gene_coverage=float(s_coverage),
                g2m_gene_coverage=float(g2m_coverage),
                mean_s_score=float(s_scores.mean()),
                mean_g2m_score=float(g2m_scores.mean()),
                phase_counts=counts,
                cycling_fraction=float((counts["S"] + counts["G2M"]) / n_observations),
                assessment_state="available",
                reason_codes=[],
            )
        )
    return result


def _execution(
    method_id: ProcessMethodId,
    available: int,
    unavailable_reasons: list[str],
    package_versions: dict[str, str],
) -> MethodExecutionRecord:
    reasons = sorted(set(unavailable_reasons))
    if available == 0:
        state = MethodExecutionState.NOT_ASSESSED
        reasons = reasons or ["method_output_unavailable"]
    elif reasons:
        state = MethodExecutionState.PARTIAL
    else:
        state = MethodExecutionState.SUCCEEDED
    method_ref, implementation = METHOD_REFS[method_id]
    return MethodExecutionRecord(
        method_id=method_id,
        method_ref=method_ref,
        implementation=implementation,
        execution_state=state,
        package_versions=package_versions,
        reason_codes=reasons,
    )


def _agreement(scores: list[ProgramScoreSummary]) -> list[MethodAgreementRecord]:
    available = [item for item in scores if item.assessment_state == "available"]
    keys = sorted(
        {
            (item.program_id, item.analysis_scope, item.cell_state_id)
            for item in available
        },
        key=lambda item: (item[0], item[1].value, item[2] or ""),
    )
    result: list[MethodAgreementRecord] = []
    for program_id, scope, state_id in keys:
        by_method: dict[ProcessMethodId, dict[str, float]] = {}
        for item in available:
            if (
                item.program_id,
                item.analysis_scope,
                item.cell_state_id,
            ) != (program_id, scope, state_id):
                continue
            by_method.setdefault(item.method_id, {})[item.analysis_unit_ref] = item.mean
        left = by_method.get(ProcessMethodId.SCANPY_SCORE_GENES, {})
        right = by_method.get(ProcessMethodId.DECOUPLER_ULM, {})
        units = sorted(set(left).intersection(right))
        reason = None
        rho = None
        if len(units) < 2:
            reason = "multiple_analysis_units_required"
        else:
            left_values = np.asarray([left[unit] for unit in units], dtype=float)
            right_values = np.asarray([right[unit] for unit in units], dtype=float)
            if np.ptp(left_values) == 0.0 or np.ptp(right_values) == 0.0:
                reason = "method_agreement_constant_input"
            else:
                value = float(spearmanr(left_values, right_values).statistic)
                if math.isfinite(value):
                    rho = value
                else:
                    reason = "method_agreement_nonfinite"
        result.append(
            MethodAgreementRecord(
                program_id=program_id,
                analysis_scope=scope,
                cell_state_id=state_id,
                n_analysis_units=len(units),
                spearman_rho=rho,
                assessment_state="available" if rho is not None else "not_assessed",
                reason_codes=[] if rho is not None else [reason or "not_assessed"],
            )
        )
    return result


def _summary_reasons(
    summaries: list[ProgramScoreSummary] | list[CellCycleSummary],
) -> list[str]:
    return sorted(
        {
            reason
            for summary in summaries
            if summary.assessment_state == "not_assessed"
            for reason in summary.reason_codes
        }
    )


def run_process_methods(
    *,
    run_id: str,
    tool_version: str,
    asset: InputAsset,
    asset_sha256: str,
    method_spec: ProcessMethodSpec,
    method_spec_sha256: str,
    program_spec_sha256: str,
    method_input: ProcessMethodInput,
    method_input_sha256: str,
    assignment: BiologicalUnitAssignmentArtifact,
    assignment_sha256: str,
    biological_unit_manifest_sha256: str,
    program_spec: ProgramSpec,
    random_seed: int,
) -> ProcessMethodBundle:
    """Execute only the methods selected by the checksummed method contract."""

    data = _load_expression(
        asset=asset,
        method_spec=method_spec,
        method_input=method_input,
        assignment=assignment,
    )
    rules = {item.program_id: item for item in program_spec.program_rules}
    package_versions = _package_versions()
    selected = set(method_spec.selected_method_ids)
    program_scores: list[ProgramScoreSummary] = []
    cell_cycle_summaries: list[CellCycleSummary] = []
    executions: list[MethodExecutionRecord] = []

    if ProcessMethodId.SCANPY_SCORE_GENES in selected:
        summaries, limitations = _scanpy_program_scores(
            data,
            method_spec,
            rules,
            random_seed,
        )
        program_scores.extend(summaries)
        reasons = sorted(set(_summary_reasons(summaries) + limitations))
        executions.append(
            _execution(
                ProcessMethodId.SCANPY_SCORE_GENES,
                sum(item.assessment_state == "available" for item in summaries),
                reasons,
                package_versions,
            )
        )

    if ProcessMethodId.DECOUPLER_ULM in selected:
        summaries = _decoupler_program_scores(data, method_spec, rules)
        program_scores.extend(summaries)
        executions.append(
            _execution(
                ProcessMethodId.DECOUPLER_ULM,
                sum(item.assessment_state == "available" for item in summaries),
                _summary_reasons(summaries),
                package_versions,
            )
        )

    if ProcessMethodId.SCANPY_CELL_CYCLE in selected:
        assert method_spec.cell_cycle is not None
        summaries = _cell_cycle_summaries(
            data,
            method_spec,
            rules[method_spec.cell_cycle.program_id],
            random_seed,
        )
        cell_cycle_summaries.extend(summaries)
        available = sum(
            item.assessment_state == "available" for item in summaries
        )
        reasons = _summary_reasons(summaries)
        executions.append(
            _execution(
                ProcessMethodId.SCANPY_CELL_CYCLE,
                available,
                reasons,
                package_versions,
            )
        )
        if ProcessMethodId.CELL_CYCLE_AGGREGATION in selected:
            executions.append(
                _execution(
                    ProcessMethodId.CELL_CYCLE_AGGREGATION,
                    available,
                    reasons,
                    package_versions,
                )
            )

    program_scores.sort(
        key=lambda item: (
            item.method_id.value,
            item.program_id,
            item.analysis_scope.value,
            item.cell_state_id or "",
            item.analysis_unit_ref,
        )
    )
    cell_cycle_summaries.sort(
        key=lambda item: (
            item.analysis_scope.value,
            item.cell_state_id or "",
            item.analysis_unit_ref,
        )
    )
    executions.sort(key=lambda item: item.method_id.value)
    return ProcessMethodBundle(
        object_version="0.1.0",
        bundle_id=f"process-method-bundle:{run_id.removeprefix('run-')}",
        tool_id="P0-06",
        tool_version=tool_version,
        method_spec_sha256=method_spec_sha256,
        program_spec_sha256=program_spec_sha256,
        method_input_sha256=method_input_sha256,
        expression_asset_id=asset.asset_id,
        expression_asset_sha256=asset_sha256,
        biological_unit_manifest_sha256=biological_unit_manifest_sha256,
        biological_unit_assignment_sha256=assignment_sha256,
        analysis_unit_refs=sorted(set(data.analysis_units.tolist())),
        independence_group_refs=sorted(set(data.independence_groups.tolist())),
        selected_method_ids=method_spec.selected_method_ids,
        lower_quantile=method_spec.lower_quantile,
        upper_quantile=method_spec.upper_quantile,
        executions=executions,
        program_scores=program_scores,
        cell_cycle_summaries=cell_cycle_summaries,
        method_agreement=_agreement(program_scores),
        evidence_state="shadow",
        score_state="unavailable",
        domain_score=None,
        created_at=method_input.created_at,
    )
