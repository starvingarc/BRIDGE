"""Raw-count pseudobulk contrasts within one declared cell population."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

import numpy as np
import pandas as pd

from bridge.tool_packages._expression_contracts import Contrast
from bridge.tool_packages._expression_data import labels, validate_matrix

if TYPE_CHECKING:
    from anndata import AnnData


@dataclass(frozen=True)
class ContrastResult:
    """One sample comparison, including excluded samples and every gene.

    P values remain missing for descriptive results. Pseudobulk rows represent
    retained declared samples; cells never become independent replicates.
    """

    state: Literal['descriptive_only', 'conditional_sample_inference']
    reason_codes: list[str]
    n_samples: dict[str, int]
    contrast: Contrast
    sample_cells: dict[str, int]
    excluded_samples: dict[str, int]
    n_genes_tested: int
    effect_definition: str
    independence: Literal['caller_declared', 'unknown']
    table: pd.DataFrame
    pseudobulk: pd.DataFrame

    def summary(self) -> dict:
        """Return inference eligibility and provenance without full gene tables."""
        return dict(state=self.state, reason_codes=self.reason_codes,
            n_samples=self.n_samples, contrast=self.contrast.model_dump(mode='json'),
            sample_cells=self.sample_cells, excluded_samples=self.excluded_samples,
            analysis_unit='declared_independent_sample', n_genes_tested=self.n_genes_tested,
            effect_definition=self.effect_definition, independence=self.independence)


def compare_expression(data: AnnData, options: Contrast, *, threads: int) -> ContrastResult:
    """Compare raw counts without modifying input; threads bounds model workers.

    Ineligible replication/design yields descriptive values with explicit reasons.
    Invalid counts or sample mappings raise ValueError with a stable reason code.
    """
    validate_matrix(data, raw=True)
    if options.reference == options.comparison:
        raise ValueError('distinct_contrast_conditions_required')
    metadata = pd.DataFrame({'group': labels(data, options.group_key),
        'sample': labels(data, options.sample_key), 'condition': labels(data, options.condition_key)})
    if options.batch_key:
        metadata['batch'] = labels(data, options.batch_key)
    # A biological replicate cannot be silently split into independent rows.
    if metadata.groupby('sample').condition.nunique().max() > 1:
        raise ValueError('sample_condition_ambiguous')
    if 'batch' in metadata and metadata.groupby('sample').batch.nunique().max() > 1:
        raise ValueError('sample_batch_ambiguous')
    mask = metadata.group.eq(options.group) & metadata.condition.isin([options.reference, options.comparison])
    selected = metadata.loc[mask]
    if selected.empty or selected.condition.nunique() < 2:
        raise ValueError('contrast_population_missing')
    sample_cells = selected['sample'].value_counts().sort_index()
    retained = sample_cells[sample_cells >= options.min_cells].index
    if len(retained) < 2:
        raise ValueError('insufficient_cells_per_sample')
    counts = pd.DataFrame([
        np.asarray(data.X[(mask & metadata['sample'].eq(sample)).to_numpy()].sum(axis=0)).ravel()
        for sample in retained], index=retained, columns=data.var_names).astype('int64')
    columns = ['condition'] + (['batch'] if options.batch_key else [])
    design = selected.drop_duplicates('sample').set_index('sample').loc[retained, columns]
    n_samples = design.condition.value_counts().to_dict()
    if any(n_samples.get(c, 0) == 0 for c in (options.reference, options.comparison)):
        raise ValueError('contrast_condition_has_no_retained_samples')
    normalized = counts.div(counts.sum(axis=1), axis=0) * 1e6
    means = {c: normalized.loc[design.condition.eq(c)].mean() for c in (options.reference, options.comparison)}
    table = pd.DataFrame({'gene': data.var_names,
        'mean_cpm_reference': means[options.reference].to_numpy(),
        'mean_cpm_comparison': means[options.comparison].to_numpy(),
        'log2_fold_change': np.log2((means[options.comparison].to_numpy() + 0.5) / (means[options.reference].to_numpy() + 0.5)),
        'pvalue': np.nan, 'padj': np.nan})
    reasons = []
    if not options.independent_samples_confirmed:
        reasons.append('biological_independence_not_confirmed')
    if min(n_samples.values()) < 3:
        reasons.append('fewer_than_three_independent_samples_per_condition')
    matrix = pd.get_dummies(design, drop_first=True, dtype=float)
    matrix.insert(0, 'intercept', 1.)
    if np.linalg.matrix_rank(matrix.to_numpy()) < matrix.shape[1] or len(matrix) <= matrix.shape[1]:
        reasons.append('condition_batch_confounded_or_no_residual_degrees_of_freedom')
    kept = counts.columns[counts.sum() >= options.min_total_counts]
    if len(kept) < 2:
        reasons.append('insufficient_expressed_genes')
    state = 'descriptive_only'
    if not reasons:
        try:
            from pydeseq2.dds import DeseqDataSet
            from pydeseq2.ds import DeseqStats
            from pydeseq2.default_inference import DefaultInference
        except ImportError:
            reasons.append('pydeseq2_dependency_unavailable')
        else:
            inference = DefaultInference(n_cpus=threads)
            batch = options.batch_key and design.batch.nunique() > 1
            dataset = DeseqDataSet(counts=counts[kept], metadata=design,
                design='~ batch + condition' if batch else '~ condition',
                size_factors_fit_type='poscounts', inference=inference, quiet=True)
            dataset.deseq2()
            statistics = DeseqStats(dataset, contrast=['condition', options.comparison, options.reference],
                                   inference=inference, quiet=True)
            statistics.summary()
            fitted = statistics.results_df.rename_axis('gene').reset_index().rename(columns={
                'log2FoldChange': 'log2_fold_change', 'lfcSE': 'lfc_se', 'baseMean': 'base_mean'})
            # Filtered/unestimable genes remain explicit null, not a false negative.
            table = table.drop(columns=['log2_fold_change', 'pvalue', 'padj']).merge(fitted, on='gene', how='left')
            state = 'conditional_sample_inference'
    table = table.sort_values(['padj', 'log2_fold_change'], ascending=[True, False], na_position='last')
    return ContrastResult(state=state, reason_codes=reasons, n_samples=n_samples,
        contrast=options, sample_cells={str(k): int(v) for k, v in sample_cells.items()},
        excluded_samples={str(k): int(v) for k, v in sample_cells.items() if k not in retained},
        n_genes_tested=len(kept) if state == 'conditional_sample_inference' else 0,
        effect_definition='DESeq2 log2 coefficient' if state == 'conditional_sample_inference' else 'log2 ratio of equal-sample mean CPM with 0.5 pseudocount',
        independence='caller_declared' if options.independent_samples_confirmed else 'unknown',
        table=table, pseudobulk=counts.rename_axis('sample').reset_index())
