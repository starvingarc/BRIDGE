# bridge-step3

Use this skill for BRIDGE Step3 CLS scoring and report generation.

## Purpose

Step3 consumes Step2 identity artifacts, runs CLS scoring components, and produces final structured report outputs.

## Expected User Prompt

Claude Code:

```text
/bridge-step3 score CLS for ./bridge-demo/runs/demo_dataset/step2 using ./bridge-demo/bridge.run.yaml
```

Codex:

```text
@bridge-step3 score CLS for ./bridge-demo/runs/demo_dataset/step2 using ./bridge-demo/bridge.run.yaml
```

## Required Inputs

- Step2 `bdata` and `adata_ref` objects or loaded Step2 artifact h5ad files
- `probs_ref_cal` when running components A or C
- component-specific assets required by selected components

## Agent Responsibilities

1. Validate that required Step2 artifacts exist.
2. Build `CLSContext` in the Step3 notebook.
3. Run any selected `component_A(ctx)` through `component_F(ctx)` independently, or call `score(ctx)` for the default full A-F pass.
4. Save component-level JSON/detail tables plus `summary.csv` and `manifest.json`.
5. Call `from bridge.cls.report import write_report as write_cls_report, compare_reports`.
6. Run `write_cls_report(result=cls_result, ctx=ctx, output_dir=..., prefix=...)` at the notebook tail.
7. For the demo comparison, use `compare_reports(...)` to place the current dataset beside the three thesis protocols: SphereDiff (CSC 2025), MacroDiff (unpublished), and MSK-DA01 (CSC 2021). Do not hard-code private server paths in committed notebooks or docs; read the paper baseline CLS root from the user prompt or local config.
8. Interpret CLS as multidimensional concordance; use component decomposition to explain structural differences rather than simple ranking.

## Notebook API

```python
from bridge.cls import CLSContext, component_A, component_B, component_C, component_D, component_E, component_F, score
from bridge.cls.report import write_report as write_cls_report, compare_reports

ctx = CLSContext(
    bdata=bdata_step2,
    adata_ref=adata_ref_step2,
    target_class="RG_Mesencephalon_FP",
    output_dir="./outputs/cls",
    dataset_id="demo_prefix",
    probs_ref_cal=probs_ref_cal,
)

# Each component can be run independently when debugging or customizing.
# a = component_A(ctx)
# b = component_B(ctx)
# c = component_C(ctx)
# d = component_D(ctx)
# e = component_E(ctx)
# f = component_F(ctx)

# Default full A-F run for report generation. Component params can be supplied
# from config when a dataset needs explicit layers, embeddings, or short demo
# adapter training for component D.
component_params = {}
result = score(ctx, component_params=component_params)

report = write_cls_report(
    result=result,
    ctx=ctx,
    output_dir="./outputs/cls/report",
    prefix="demo_prefix",
)
```

Thesis-style four-protocol comparison:

```python
comparison = compare_reports(
    protocols=[
        {"name": "SphereDiff (CSC 2025)", "dataset_id": "zxy_XPBD28B", "step3_dir": "./paper_cls_results"},
        {"name": "MacroDiff (unpublished)", "dataset_id": "oyqk_organoid_OYQK_OMYD28", "step3_dir": "./paper_cls_results"},
        {"name": "MSK-DA01 (CSC 2021)", "dataset_id": "StuderD16", "step3_dir": "./paper_cls_results"},
        {"name": "Current dataset", "dataset_id": ctx.dataset_id, "step3_dir": ctx.output_dir},
    ],
    output_dir="./runs/comparison/cls_report",
    prefix="four_protocol_cls_comparison",
)
```

## Expected Outputs

- component global JSON files
- component detail tables when available
- report summary CSV
- report manifest JSON
- Step3 report Markdown
- Step3 report manifest JSON
- report tables and available figures
- optional multi-protocol comparison report
- optional four-protocol thesis-style comparison report for SphereDiff, MacroDiff, MSK-DA01, and the current dataset

## Report Coverage

The Step3 report API uses the thesis-style CLS visual language from the project visualization notebooks. It covers component score overview, radar profile, weighted CLS, weighted contribution stack, component heatmap, and available A-F diagnostic panels when required columns or files exist. For protocol comparison, include the thesis-style A/C/D/E diagnostics when the component batch or gene artifacts are present. Missing optional component diagnostics should be recorded as manifest warnings, not treated as fatal errors.

## Notebook-Visible Report Sections

After the core workflow runs, the notebook must include notebook-visible report sections rather than only writing files under `report/`. For each report table, add a short Markdown context cell, a code cell that builds and displays the table, and a concise interpretation Markdown cell. For each report figure, add a short Markdown context cell, a code cell that calls the public `plot_*` function and displays the figure, and a concise interpretation Markdown cell. The final cell should still call `write_report(...)`, print artifact paths, and save the standard Markdown, manifest, CSV, and image files. Agents should display each table and display each figure as code-cell output.

## Narrative Notebook Structure

Generated notebooks must be notebook-native analysis records, not a report dump at the end. Use this exact structure:

1. Opening Markdown: explain what this step does, why it matters in BRIDGE, what biological question it addresses, and what artifacts it will produce.
2. Core workflow cells: load input, validate config/model paths, run the step, and print only concise run metadata.
3. Notebook-visible report sections: create one logical section per table or figure. Each section must contain:
   - purpose/context Markdown before the code, explaining what this table or figure is meant to evaluate;
   - exactly one code cell that builds one table or one figure;
   - for table cells, call `display(table_df)`;
   - for figure cells, call `fig = plot_...(...)` followed by `_ = display_matplotlib_figure(fig)` from `bridge.reporting.notebook`;
   - biological interpretation Markdown after the output, grounded in the observed values and developmental meaning.
4. Final Markdown summary: summarize what this step concluded and how it feeds the next BRIDGE step.
5. Final artifact cell: call `write_report(...)`, print saved paths, and do not re-display every report artifact. The saved `report/` folder remains the artifact contract.

Do not use a final cell that loops through report tables/figures and displays them all together. Do not rely on a bare `fig` expression, because some notebook renderers show only `<Figure size ...>` instead of the image.

Step3 biological interpretation should explain component-level concordance and divergence across identity, expression, transferability, neighborhood, pseudotime, and regulon axes rather than presenting a simple ranking. For the four-protocol comparison, display the comparison score table, grouped component overview, radar plot, weighted CLS bar plot, weighted contribution stack, component heatmap, and available A/C/D/E diagnostic panels as separate notebook sections, each with context before the code and biological interpretation after the output. Prefer the public plotting helpers in `bridge.cls.report` so the notebook visibly executes the same code used by the saved report artifacts.
