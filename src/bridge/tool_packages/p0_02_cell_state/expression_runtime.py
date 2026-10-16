"""Registered expression exploration using the existing QC and artifact boundary."""
from __future__ import annotations

import hashlib
import io
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from bridge.toolkit.contracts import ArtifactManifest, ToolRun
from bridge.tool_packages._structured_runtime import canonical_json_bytes, publish_json_bundle, request_v2_from_v1
from bridge.tool_packages._expression_contracts import ExpressionAnalysis


def run_expression_analysis(request, spec):
    asset = request.assets[0]
    run_id = 'expression-' + hashlib.sha256(request.request_id.encode()).hexdigest()[:24]
    base = dict(run_id=run_id, request=request, implementation_state=spec.implementation_state,
                tool_version=spec.version, environment_spec_id=spec.environment_spec_id)
    try:
        from bridge.tool_packages.p0_01_input_qc.io import read_expression_asset, sha256_path
        from .expression import explore
        from .expression_store import gene_store_bytes, marker_table
        from bridge.tool_packages.p0_07_product_comparison_stability.expression import compare_expression
        from .expression_figures import prepare_figures
        from .qc import validate_upstream_qc_bundle, validate_selected_data_view, validate_upstream_qc_unchanged

        digest = sha256_path(asset.path)
        base['input_hash'] = digest
        if asset.checksum != digest:
            raise ValueError('input_checksum_mismatch')
        upstream = validate_upstream_qc_bundle(asset, digest)
        if upstream.profile_v2 is None:
            raise ValueError('typed_selected_data_view_required')
        options = ExpressionAnalysis.model_validate(request.parameters)
        if options.contrast and asset.matrix_semantics != 'raw_counts':
            raise ValueError('contrast_requires_raw_counts')
        data = read_expression_asset(asset)
        view = validate_selected_data_view(upstream.profile_v2, data.obs_names.tolist())
        exploration = explore(data, options.exploration, semantics=asset.matrix_semantics, seed=request.random_seed)
        contrast = compare_expression(data, options.contrast, threads=options.exploration.threads) if options.contrast else None
        bundle = prepare_figures(exploration, contrast, run_id=run_id, version=spec.version,
                                 input_sha256=digest, data_view_ref=view.view_id)
        # Full-resolution coordinates for sample-owned viewers; figure sampling
        # must never determine the downloadable observation set.
        if exploration.grouping_source == 'exploratory_leiden':
            cells = exploration.umap.rename(columns={'group': 'leiden'}).copy()
            cells['leiden'] = cells['leiden'].str.removeprefix('Cluster ').astype('string')
            buffer = io.BytesIO()
            cells.to_parquet(buffer, index=False)
            bundle.payloads['expression_cells.parquet'] = buffer.getvalue()
            bundle.kinds['expression_cells.parquet'] = 'expression_cell_coordinates'
            buffer = io.BytesIO()
            marker_table(exploration).to_parquet(buffer, index=False)
            bundle.payloads['expression_markers.parquet'] = buffer.getvalue()
            bundle.kinds['expression_markers.parquet'] = 'expression_cluster_markers'
            bundle.payloads['expression_genes.h5'] = gene_store_bytes(exploration, input_sha256=digest)
            bundle.kinds['expression_genes.h5'] = 'expression_gene_store'
        if contrast is not None:
            bundle.payloads['expression_pseudobulk.tsv'] = contrast.pseudobulk.to_csv(sep='\t', index=False).encode()
            bundle.kinds['expression_pseudobulk.tsv'] = 'expression_table'
        summary = exploration.summary()
        if exploration.grouping_source == 'exploratory_leiden':
            summary['gene_expression'] = {
                'object_version': '0.1.0', 'state': 'available', 'n_genes': exploration.n_genes,
                'scale': 'natural_log1p', 'normalization': exploration.preparation['normalization'],
                'mean_definition': 'arithmetic_mean_of_log1p_including_zeros',
                'fraction_definition': 'expression_gt_zero_over_all_group_observations',
                'feature_lookup': 'exact_var_name_no_alias_resolution',
            }
        if contrast is not None:
            summary['differential_expression'] = contrast.summary()
        dependencies = {}
        for package in ('scanpy', 'anndata', 'numpy', 'scipy', 'pydeseq2', 'umap-learn', 'igraph', 'leidenalg'):
            try:
                dependencies[package] = version(package)
            except PackageNotFoundError:
                dependencies[package] = None
        summary.update(input_data_view=view.model_dump(mode='json'), input_sha256=digest,
                       parameters=options.model_dump(mode='json'), random_seed=request.random_seed,
                       dependencies=dependencies, score_state='unavailable')
        bundle.payloads['expression_analysis.json'] = canonical_json_bytes(summary)
        bundle.kinds['expression_analysis.json'] = 'expression_analysis'
        def unchanged(_):
            validate_upstream_qc_unchanged(upstream)
            return sha256_path(asset.path) == digest
        paths = publish_json_bundle(request=request_v2_from_v1(request), run_id=run_id,
                                    payloads=bundle.payloads, inputs_are_unchanged=unchanged)
        media = {'.json': 'application/json', '.tsv': 'text/tab-separated-values',
                 '.svg': 'image/svg+xml', '.png': 'image/png', '.pdf': 'application/pdf', '.parquet': 'application/vnd.apache.parquet', '.h5': 'application/x-hdf5'}
        artifacts = [ArtifactManifest(artifact_id='artifact:' + run_id + ':' + name.replace('.', '-'),
            kind=bundle.kinds[name], path=path, media_type=media[Path(name).suffix],
            sha256=hashlib.sha256(bundle.payloads[name]).hexdigest(), evidence_ids=['evidence:' + run_id + ':expression'])
            for name, path in paths.items()]
        return ToolRun(**base, execution_state='succeeded', artifacts=artifacts, result=summary)
    except (ValueError, OSError, RuntimeError, ImportError) as exc:
        reason = getattr(exc, 'reason_code', None)
        if not reason:
            detail = str(exc)
            reason = detail if detail.replace('_', '').isalnum() and len(detail) < 100 else 'expression_analysis_failed'
        return ToolRun(**base, execution_state='failed', reason_codes=[reason], warnings=['error_type:' + type(exc).__name__])
