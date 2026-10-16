"""Reference-free expression exploration on one immutable, selected data view."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal
import numpy as np
import pandas as pd
from scipy import sparse
from threadpoolctl import threadpool_limits

from bridge.tool_packages._expression_contracts import ExplorationOptions
from bridge.tool_packages._expression_data import labels, validate_matrix

if TYPE_CHECKING:
    from anndata import AnnData

@dataclass(frozen=True)
class ExplorationResult:
    """Exploration values for one selected view; tables retain all observations.

    Coordinates, indices and colors describe the same bounded display sample.
    Composition, counts and derived expression always use the full view.
    Original input data is never mutated. Summary serialization excludes
    display vectors, full tables and the derived expression matrix.
    """

    n_observations: int
    n_genes: int
    coordinates: list[list[float]]
    observation_indices: list[int]
    colors: dict[str, list[str | float | None]]
    composition: list[dict[str, str | int | float]]
    embedding_source: Literal['user_declared', 'scanpy_umap']
    grouping_source: Literal['user_declared', 'exploratory_leiden']
    preparation: dict[str, str | int]
    missing_genes: list[str]
    marker_state: str
    umap: pd.DataFrame
    markers: pd.DataFrame
    expression: sparse.csc_matrix
    gene_ids: list[str]

    def summary(self) -> dict:
        """Return the persisted scientific summary, without sampled display data."""
        return dict(object_version='0.1.0', analysis_kind='expression_exploration',
            n_observations=self.n_observations, n_genes=self.n_genes,
            composition=self.composition, embedding_source=self.embedding_source,
            grouping_source=self.grouping_source, preparation=self.preparation,
            missing_genes=self.missing_genes, marker_state=self.marker_state,
            marker_inference='cell_level_exploratory_not_condition_inference',
            domain_score=None)


def explore(data: AnnData, options: ExplorationOptions, *, semantics: str, seed: int) -> ExplorationResult:
    """Return exploration on raw counts or explicitly declared natural-log1p data.

    The seed controls graph construction and display sampling. Invalid matrices,
    labels or declared coordinates raise ValueError with a stable reason code.
    """
    import scanpy as sc
    validate_matrix(data, raw=semantics == 'raw_counts')
    from anndata import AnnData
    work = AnnData(data.X.copy(), obs=data.obs.copy(), var=data.var.copy())
    if "log1p" in data.uns:
        work.uns["log1p"] = dict(data.uns["log1p"])
    preparation = {'normalization': 'reused_declared_log1p'}
    with threadpool_limits(limits=options.threads):
        if semantics == 'raw_counts':
            # Foreign preprocessing metadata does not describe the selected counts layer.
            work.uns.pop('log1p', None)
            sc.pp.normalize_total(work, target_sum=10000)
            sc.pp.log1p(work)
            preparation['normalization'] = 'total_10000_log1p'
        elif semantics != 'normalized_expression' or options.normalized_scale != 'log1p':
            raise ValueError('normalized_scale_required')
        elif work.uns.get('log1p', {}).get('base') is not None:
            raise ValueError('natural_log1p_required')
        if options.embedding_key:
            if options.embedding_key not in data.obsm:
                raise ValueError('declared_embedding_not_found')
            coordinates = np.asarray(data.obsm[options.embedding_key])
            if coordinates.shape != (data.n_obs, 2) or not np.isfinite(coordinates).all():
                raise ValueError('declared_embedding_invalid')
        else:
            coordinates = None
        # Graph construction is needed only for a new embedding or new clustering.
        if coordinates is None or options.group_key is None:
            graph = work.copy()
            sc.pp.highly_variable_genes(graph, n_top_genes=min(options.n_hvg, graph.n_vars),
                                       flavor='seurat', subset=True)
            n_pcs = min(options.n_pcs, graph.n_obs - 1, graph.n_vars - 1)
            if n_pcs < 2:
                raise ValueError('insufficient_variable_genes')
            sc.pp.pca(graph, n_comps=n_pcs, random_state=seed)
            sc.pp.neighbors(graph, n_neighbors=min(options.n_neighbors, graph.n_obs - 1),
                            n_pcs=n_pcs, random_state=seed)
            preparation.update(n_hvg=graph.n_vars, n_pcs=n_pcs,
                               n_neighbors=min(options.n_neighbors, graph.n_obs - 1))
            if coordinates is None:
                sc.tl.umap(graph, min_dist=options.min_dist, random_state=seed)
                coordinates = graph.obsm['X_umap']
            if options.group_key is None:
                sc.tl.leiden(graph, resolution=options.resolution, random_state=seed,
                             flavor='igraph', directed=False, n_iterations=2)
                groups = graph.obs['leiden'].astype(str).map(lambda x: 'Cluster ' + x)
        if options.group_key:
            groups = labels(work, options.group_key)
        work.obs['_bridge_group'] = pd.Categorical(groups)
        counts = groups.value_counts().sort_index()
        marker_state = 'available'
        if len(counts) < 2 or counts.min() < 2:
            marker_state = 'insufficient_groups_or_cells'
            markers = pd.DataFrame(columns=['group', 'gene', 'score', 'log2_fold_change',
                                           'pvalue', 'padj', 'fraction_in', 'fraction_rest'])
        else:
            sc.tl.rank_genes_groups(work, '_bridge_group', method='wilcoxon', use_raw=False,
                                   n_genes=min(options.marker_genes, work.n_vars), pts=True,
                                   tie_correct=True, corr_method='benjamini-hochberg')
            markers = sc.get.rank_genes_groups_df(work, group=None).rename(columns={
                'names': 'gene', 'scores': 'score', 'logfoldchanges': 'log2_fold_change',
                'pvals': 'pvalue', 'pvals_adj': 'padj', 'pct_nz_group': 'fraction_in',
                'pct_nz_reference': 'fraction_rest'})
    sample = np.sort(np.random.default_rng(seed).choice(data.n_obs, min(data.n_obs, options.max_points), replace=False))
    colors = {'分群': groups.iloc[sample].tolist()}
    for key in dict.fromkeys(options.color_keys):
        if key not in data.obs:
            raise ValueError('observation_column_not_found')
        column = data.obs[key]
        if pd.api.types.is_numeric_dtype(column):
            colors['注释 · ' + key] = [float(v) if pd.notna(v) and np.isfinite(v) else None for v in column.iloc[sample]]
        else:
            colors['注释 · ' + key] = labels(data, key).iloc[sample].tolist()
    totals = np.asarray(data.X.sum(axis=1)).ravel()
    detected = np.asarray((data.X > 0).sum(axis=1)).ravel()
    colors['检测基因数'] = detected[sample].astype(int).tolist()
    if semantics == 'raw_counts':
        colors['总计数'] = totals[sample].astype(float).tolist()
    missing = []
    for gene in dict.fromkeys(options.genes):
        if gene not in work.var_names:
            missing.append(gene)
            continue
        values = work[sample, gene].X
        colors['基因 · ' + gene] = np.asarray(values.toarray() if sparse.issparse(values) else values).ravel().tolist()
    table = pd.DataFrame({'observation_id': data.obs_names, 'umap_1': coordinates[:, 0],
                          'umap_2': coordinates[:, 1], 'group': groups.to_numpy()})
    return ExplorationResult(
        n_observations=data.n_obs, n_genes=data.n_vars, coordinates=coordinates[sample].tolist(),
        observation_indices=sample.tolist(), colors=colors,
        composition=[{'group': str(key), 'count': int(n), 'fraction': float(n / data.n_obs)} for key, n in counts.items()],
        embedding_source='user_declared' if options.embedding_key else 'scanpy_umap',
        grouping_source='user_declared' if options.group_key else 'exploratory_leiden',
        preparation=preparation, missing_genes=missing, marker_state=marker_state,
        umap=table, markers=markers, expression=sparse.csc_matrix(work.X),
        gene_ids=work.var_names.tolist())
