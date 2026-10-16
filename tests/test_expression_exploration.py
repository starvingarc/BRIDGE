"""Synthetic expression patterns; no biological identities or real samples."""
import numpy as np
import pandas as pd
import pytest
from anndata import AnnData
from scipy import sparse

from bridge.tool_packages._expression_contracts import ExplorationOptions, Contrast
from bridge.tool_packages.p0_02_cell_state.expression import explore
from bridge.tool_packages.p0_07_product_comparison_stability.expression import compare_expression


def matrix():
    rng = np.random.default_rng(24)
    x = rng.poisson(2, (120, 80))
    x[:60, :5] += 18
    x[60:, 5:10] += 18
    return AnnData(sparse.csr_matrix(x), obs=pd.DataFrame({
        'type': ['A'] * 60 + ['B'] * 60,
        'batch': ['one', 'two'] * 60,
    }, index=[f'cell-{i}' for i in range(120)]),
        var=pd.DataFrame(index=[f'gene-{i}' for i in range(80)]))


def test_umap_markers_preserve_input_and_full_denominator():
    data = matrix()
    original = data.X.copy()
    result = explore(data, ExplorationOptions(group_key='type', color_keys=['batch'],
        genes=['gene-0'], max_points=40, n_pcs=10, n_neighbors=8), semantics='raw_counts', seed=17)
    assert (data.X != original).nnz == 0 and 'X_umap' not in data.obsm
    assert result.n_observations == 120 and len(result.coordinates) == 40
    assert sum(row['count'] for row in result.composition) == 120
    assert len(result.umap) == 120
    assert set(result.markers.query("group == 'A'").head(5).gene) == {f'gene-{i}' for i in range(5)}
    assert result.summary()['marker_inference'] == 'cell_level_exploratory_not_condition_inference'


def test_declared_embedding_is_used_without_normalizing_twice():
    import scanpy as sc
    data = matrix()
    sc.pp.normalize_total(data, target_sum=10000)
    sc.pp.log1p(data)
    data.obsm['X_umap'] = np.arange(240).reshape(120, 2).astype(float)
    result = explore(data, ExplorationOptions(group_key='type', embedding_key='X_umap',
        normalized_scale='log1p', max_points=120), semantics='normalized_expression', seed=17)
    assert result.coordinates == data.obsm['X_umap'].tolist()
    assert result.embedding_source == 'user_declared'
    assert result.preparation['normalization'] == 'reused_declared_log1p'
    with pytest.raises(ValueError, match='normalized_scale_required'):
        explore(data, ExplorationOptions(group_key='type'), semantics='normalized_expression', seed=17)


def test_expression_comparison_does_not_treat_cells_as_replicates():
    data = matrix()
    data.obs['condition'] = ['control'] * 30 + ['treated'] * 30 + ['control'] * 30 + ['treated'] * 30
    data.obs['sample'] = data.obs.condition
    result = compare_expression(data, Contrast(group_key='type', group='A',
        condition_key='condition', reference='control', comparison='treated', sample_key='sample'), threads=1)
    assert result.state == 'descriptive_only'
    assert result.summary()['analysis_unit'] == 'declared_independent_sample'
    assert result.summary()['n_genes_tested'] == 0
    assert result.n_samples == {'control': 1, 'treated': 1}
    assert result.table.pvalue.isna().all() and result.table.padj.isna().all()
    assert result.pseudobulk.shape[0] == 2
    assert sum(result.sample_cells.values()) == 60


def test_invalid_sample_mapping_and_non_integer_counts_rejected():
    data = matrix()
    data.obs['condition'] = ['control', 'treated'] * 60
    data.obs['sample'] = 'same'
    options = Contrast(group_key='type', group='A', condition_key='condition',
        reference='control', comparison='treated', sample_key='sample')
    with pytest.raises(ValueError, match='sample_condition_ambiguous'):
        compare_expression(data, options, threads=1)
    data.X = data.X.astype(float) / 2
    with pytest.raises(ValueError, match='raw_integer_counts_required'):
        compare_expression(data, options, threads=1)


def test_raw_sample_inference_and_confounded_batch():
    pytest.importorskip('pydeseq2')
    data = matrix()
    data.obs['type'] = 'A'
    data.obs['sample'] = np.repeat([f's{i}' for i in range(6)], 20)
    data.obs['condition'] = np.repeat(['control', 'treated'], 60)
    options = Contrast(group_key='type', group='A', condition_key='condition',
        reference='control', comparison='treated', sample_key='sample', independent_samples_confirmed=True)
    result = compare_expression(data, options, threads=1)
    assert result.state == 'conditional_sample_inference'
    assert result.n_samples == {'control': 3, 'treated': 3}
    assert len(result.pseudobulk) == 6 and len(result.table) == data.n_vars
    assert result.table.query("gene == 'gene-5'").iloc[0].log2_fold_change > 2
    assert result.table.padj.notna().sum() > 50
    data.obs['batch'] = data.obs.condition
    result = compare_expression(data, options.model_copy(update={'batch_key': 'batch'}), threads=1)
    assert result.state == 'descriptive_only' and result.table.padj.isna().all()


@pytest.mark.parametrize("single_group", [False, True])
def test_expression_figures_use_existing_contract_and_static_exports(single_group):
    import json
    from jsonschema import Draft202012Validator
    from bridge.toolkit.schemas import load_schema
    from bridge.tool_packages.p0_02_cell_state.expression_figures import prepare_figures
    data = matrix()
    if single_group:
        data.obs['type'] = 'A'
    data.obsm['X_umap'] = np.random.default_rng(1).normal(size=(120, 2))
    result = explore(data, ExplorationOptions(group_key='type', embedding_key='X_umap'),
                             semantics='raw_counts', seed=1)
    bundle = prepare_figures(result, run_id='test-expression', version='0.7.0',
                                 input_sha256='a' * 64, data_view_ref='view:synthetic')
    for kind in ('umap', 'markers'):
        assert bundle.payloads['expression_' + kind + '.png'].startswith(b'\x89PNG')
        assert bundle.payloads['expression_' + kind + '.pdf'].startswith(b'%PDF')
        raw = json.loads(bundle.payloads['expression_' + kind + '.json'])
        Draft202012Validator(load_schema(raw['schema_ref'])).validate(raw)
    figure_set = json.loads(bundle.payloads['expression_visualization_artifact_set.json'])
    assert len(figure_set['visualizations']) == 2
    if single_group:
        marker = figure_set['visualizations'][1]
        assert marker['evidence_states'] == ['unavailable']
        assert marker['missing_reason_codes'] == ['insufficient_groups_or_cells']
