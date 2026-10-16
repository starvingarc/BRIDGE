"""Expression figures reuse BRIDGE's typed bindings, registry and static exporter."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from pydantic import Field, model_validator

from bridge.tool_packages._figure_export import render_figure_payloads
from bridge.tool_packages._structured_runtime import canonical_json_bytes
from bridge.toolkit.contracts import FrozenModel
from bridge.toolkit.visualization import (
    FigureRegistry, VisualizationArtifactV2, VisualizationAccessibility, VisualizationDataBinding,
    VisualizationRenderBinding, VisualizationInteractionContract,
)

if TYPE_CHECKING:
    import pandas as pd
    from .expression import ExplorationResult
    from bridge.tool_packages.p0_07_product_comparison_stability.expression import ContrastResult

DATA_SCHEMA = 'bridge://schemas/expression-plot-data/v0.1'
SET_SCHEMA = 'bridge://schemas/p0-02-visualization-artifact-set/v0.2'


class ExpressionPoint(FrozenModel):
    record_id: str
    x: float | None
    y: float | None
    label: str
    group: str | None = None
    evidence_ids: list[str]
    evidence_state: Literal['measured', 'unavailable'] = 'measured'
    scientific_status: Literal['exploratory'] = 'exploratory'
    missing_reason_codes: list[str] = Field(default_factory=list)
    applicability: Literal['applicable'] = 'applicable'


class ExpressionPlotData(FrozenModel):
    schema_ref: Literal[DATA_SCHEMA] = DATA_SCHEMA
    object_version: Literal['0.1.0'] = '0.1.0'
    kind: Literal['umap', 'markers', 'differential_expression']
    input_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    data_view_ref: str
    n_observations: int = Field(gt=0)
    records: list[ExpressionPoint]
    colors: dict[str, list[str | float | None]] = Field(default_factory=dict)
    composition: list[dict[str, str | int | float]] = Field(default_factory=list)
    x_label: str
    y_label: str
    inference: str
    missing_genes: list[str] = Field(default_factory=list)

    @model_validator(mode='after')
    def coloring_matches_points(self):
        import numpy as np

        if len({p.record_id for p in self.records}) != len(self.records):
            raise ValueError('unique_plot_record_ids_required')
        if any(len(values) != len(self.records) for values in self.colors.values()):
            raise ValueError('color_vector_length_mismatch')
        if any(isinstance(v, float) and not np.isfinite(v) for values in self.colors.values() for v in values):
            raise ValueError('finite_color_values_required')
        if any(v is not None and not np.isfinite(v) for p in self.records for v in (p.x, p.y)):
            raise ValueError('finite_plot_values_required')
        return self


class ExpressionFigureSet(FrozenModel):
    schema_ref: Literal[SET_SCHEMA] = SET_SCHEMA
    object_version: Literal['0.2.0'] = '0.2.0'
    visualizations: list[VisualizationArtifactV2] = Field(min_length=2, max_length=3)

    @model_validator(mode='after')
    def coherent_producer(self):
        if len({v.component_id for v in self.visualizations}) != len(self.visualizations):
            raise ValueError('duplicate_expression_figure')
        if any(v.producer_tool_id != 'P0-02' for v in self.visualizations):
            raise ValueError('expression_producer_required')
        if len({(v.producer_run_ref, v.producer_tool_version) for v in self.visualizations}) != 1:
            raise ValueError('shared_expression_producer_required')
        return self


PUBLIC_SCHEMA_MODELS = {DATA_SCHEMA: ExpressionPlotData, SET_SCHEMA: ExpressionFigureSet}


def _records(frame: pd.DataFrame) -> list[dict]:
    """Encode non-estimable numbers as JSON null without dropping result rows."""
    import numpy as np

    import pandas as pd

    finite = frame.replace([np.inf, -np.inf], np.nan)
    return finite.astype(object).where(pd.notna(finite), None).to_dict('records')


@dataclass(frozen=True)
class ExpressionArtifacts:
    """Unpublished artifact bytes and their manifest kinds, keyed by filename."""

    payloads: dict[str, bytes]
    kinds: dict[str, str]


def prepare_figures(result: ExplorationResult, contrast: ContrastResult | None = None, *,
                    run_id: str, version: str, input_sha256: str,
                    data_view_ref: str) -> ExpressionArtifacts:
    """Build source-bound plots, complete tables and exports without writing files.

    The selected-view hash and reference bind every figure to the same input.
    Contrast figures are omitted when no sample comparison was requested.
    """
    import numpy as np

    import matplotlib
    matplotlib.use('Agg')
    from matplotlib import pyplot as plt

    payloads, kinds, views = {}, {}, []
    evidence = 'evidence:' + run_id + ':expression'
    def identity(filename):
        return 'artifact:' + run_id + ':' + filename.replace('.', '-')
    chart_frames = [('umap', result.umap), ('markers', result.markers)]
    if contrast is not None:
        chart_frames.append(('differential_expression', contrast.table))
    for kind, frame in chart_frames:
        points, colors = [], {}
        if kind == 'umap':
            colors = result.colors
            points = [ExpressionPoint(record_id=str(i), x=x, y=y, label=str(i), group=g, evidence_ids=[evidence])
                      for i, (x, y), g in zip(result.observation_indices, result.coordinates, colors['分群'], strict=True)]
            x_label, y_label, title = 'UMAP 1', 'UMAP 2', 'Expression neighborhoods'
            inference = 'Expression similarity only; visual distance does not establish lineage or identity.'
        elif kind == 'markers':
            top = frame.groupby('group', observed=True, sort=False).head(5).head(40) if len(frame) else frame
            points = [ExpressionPoint(record_id=str(i), x=row['log2_fold_change'], y=float(i),
                label=str(row['gene']), group=str(row['group']), evidence_ids=[evidence]) for i, row in enumerate(_records(top))]
            x_label, y_label, title = 'Approximate log2 fold change', 'Group marker', 'Exploratory group markers'
            inference = 'Within-dataset cell-level marker ranking; not biological-replicate condition inference.'
        else:
            assert contrast is not None
            inferential = contrast.state == 'conditional_sample_inference'
            finite = frame.dropna(subset=['log2_fold_change'])
            # The table contains every gene. The plot keeps a bounded deterministic view.
            top = finite.head(20000)
            points = [ExpressionPoint(record_id=str(i), x=row['log2_fold_change'],
                y=(float(-np.log10(max(row['padj'], 1e-300))) if row['padj'] is not None else None) if inferential
                  else float(np.log10(1 + (row['mean_cpm_reference'] + row['mean_cpm_comparison']) / 2)),
                label=str(row['gene']), evidence_ids=[evidence]) for i, row in enumerate(_records(top))]
            x_label = 'log2 fold change (comparison / reference)'
            y_label = '-log10 adjusted p' if inferential else 'log10 (1 + mean CPM)'
            title = 'Within-population sample contrast'
            inference = contrast.state + '; ' + contrast.effect_definition
        points = [p.model_copy(update={'evidence_state': 'unavailable',
                  'missing_reason_codes': ['plot_value_not_estimable']}) if p.x is None or p.y is None else p for p in points]
        data = ExpressionPlotData(kind=kind, input_sha256=input_sha256, data_view_ref=data_view_ref,
            n_observations=result.n_observations, records=points, colors=colors,
            composition=result.composition if kind == 'umap' else [],
            x_label=x_label, y_label=y_label, inference=inference,
            missing_genes=result.missing_genes if kind == 'umap' else [])
        filename = 'expression_' + kind + '.json'
        raw = canonical_json_bytes(data.model_dump(mode='json'))
        payloads[filename], kinds[filename] = raw, 'expression_plot_data'
        digest = hashlib.sha256(raw).hexdigest()
        table_name = 'expression_' + kind + '.tsv'
        payloads[table_name] = frame.to_csv(sep='\t', index=False, na_rep='').encode()
        kinds[table_name] = 'expression_table'
        with plt.rc_context({'svg.hashsalt': 'BRIDGE-EXPRESSION', 'svg.fonttype': 'none', 'pdf.fonttype': 42}):
            fig, ax = plt.subplots(figsize=(8, 5), layout='constrained')
            present = [p for p in points if p.x is not None and p.y is not None]
            groups = sorted({p.group or 'all' for p in present})
            for group in groups:
                subset = [p for p in present if (p.group or 'all') == group]
                ax.scatter([p.x for p in subset], [p.y for p in subset], s=9, alpha=0.65, label=group, rasterized=len(subset) > 5000)
            if kind == 'umap' and len(groups) <= 20:
                ax.legend(fontsize=7, markerscale=2, frameon=False, loc='best')
            if kind == 'markers':
                ax.set_yticks([p.y for p in present], [f'{p.group}: {p.label}' for p in present], fontsize=7)
            if not present:
                ax.text(.5, .5, 'Not estimable: see data table and limitations', ha='center', transform=ax.transAxes)
            ax.set(xlabel=x_label, ylabel=y_label, title=title)
            ax.spines[['top', 'right']].set_visible(False)
            exports = render_figure_payloads(fig)
        renders = []
        for extension, (media, raw_render) in exports.items():
            name = 'expression_' + kind + '.' + extension
            payloads[name], kinds[name] = raw_render, 'expression_figure'
            renders.append(VisualizationRenderBinding(artifact_id=identity(name), media_type=media,
                renderer_id='bridge.matplotlib.expression', renderer_version='0.1.0',
                export_profile_id='bridge-static-scientific-figure-v0.1', data_sha256=digest,
                config_sha256=hashlib.sha256(canonical_json_bytes({'x': x_label, 'y': y_label})).hexdigest()))
        missing_reasons = sorted({reason for point in points for reason in point.missing_reason_codes})
        if not points:
            missing_reasons = [result.marker_state if kind == 'markers' else 'no_estimable_plot_values']
        view = VisualizationArtifactV2(visualization_id='visualization:' + run_id + ':' + kind,
            component_id='bridge.expression.' + kind.replace('_', '-'), component_version='0.1.0',
            data_binding=VisualizationDataBinding(artifact_id=identity(filename), schema_ref=DATA_SCHEMA,
                object_version='0.1.0', sha256=digest, records_path='records', record_lookup_key='record_id',
                evidence_ids_field='evidence_ids', value_field='x', evidence_state_field='evidence_state',
                scientific_status_field='scientific_status', missingness_field='missing_reason_codes', applicability_field='applicability'),
            producer_tool_id='P0-02', producer_tool_version=version, producer_run_ref='run:' + run_id,
            evidence_ids=[evidence], evidence_states=sorted({p.evidence_state for p in points}) or ['unavailable'], scientific_status='exploratory',
            missing_reason_codes=missing_reasons,
            applicability='applicable', unit='expression similarity' if kind == 'umap' else 'log2 fold change',
            insight_title=title, takeaway=(
                '表达相似性分布；图上距离不能证明细胞身份或谱系。' if kind == 'umap'
                else '群标记是本数据内的探索性线索，不代表样本条件效应。' if kind == 'markers'
                else '按声明的独立样本比较两组条件；统计解释依赖样本独立性及可估计的设计。' if inferential
                else '样本重复或设计条件不足，仅展示按样本汇总的描述性差异，不输出显著性判断。'),
            limitations=[inference, 'Display sampling never changes analysis counts. Marker plot: at most 40 ranked rows; DE plot: at most 20,000 genes. See complete tables.'],
            interactions=VisualizationInteractionContract(filter_ids=['color', 'group']) if kind == 'umap' else VisualizationInteractionContract(),
            accessibility=VisualizationAccessibility(alt_text=title + '; source-bound exploratory observations.',
                long_description=inference + ' Full values and source bindings are available in the associated table.',
                table_artifact_id=identity(table_name), data_sha256=digest), renders=renders)
        FigureRegistry.load_default().validate_artifact(view)
        views.append(view)
    name = 'expression_visualization_artifact_set.json'
    payloads[name] = canonical_json_bytes(ExpressionFigureSet(visualizations=views).model_dump(mode='json'))
    kinds[name] = 'visualization_artifact_set'
    return ExpressionArtifacts(payloads=payloads, kinds=kinds)
