# bridge-step1

Use this skill for BRIDGE Step1 whole-brain prescreening.

## Purpose

Step1 screens an in vitro `.h5ad` dataset against a whole-brain reference model and marks cells as `RG_candidate` or `non_RG`.

## Expected User Prompt

Claude Code:

```text
/bridge-step1 prescreen the h5ad file ./my-data/organoid.h5ad using ./bridge-demo/bridge.run.yaml and write outputs to ./bridge-demo/runs/demo_dataset/step1
```

Codex:

```text
@bridge-step1 prescreen the h5ad file ./my-data/organoid.h5ad using ./bridge-demo/bridge.run.yaml and write outputs to ./bridge-demo/runs/demo_dataset/step1
```

## Required Inputs

- one in vitro `.h5ad` dataset
- Step0 config with whole-brain model location
- writable Step1 output directory

## Agent Responsibilities

1. Prefer notebook-callable package code for Step1.
2. Generate or update a Step1 notebook that imports `from bridge.prescreen import prescreen`.
3. Validate that the input `.h5ad` exists and can be read in the active environment. If it reads successfully, use the user-provided path directly in the notebook; do not create or reuse a compatibility copy.
4. Validate the whole-brain reference model path.
5. Call `prescreen(adata, ref_model_dir=..., output_dir=..., prefix=...)` with explicit parameters.
6. Save the full prescreened object, RG candidate subset, probability table, and summary JSON through the API.
7. Call `from bridge.prescreen.report import write_report as write_prescreen_report`.
8. Run `write_prescreen_report(result=result, output_dir=..., prefix=...)` at the notebook tail.
9. Keep Step1 interpretation as in vitro prescreening, not supervised test-set evaluation.

## Notebook API

```python
from bridge.prescreen import prescreen
from bridge.prescreen.report import write_report as write_prescreen_report

result = prescreen(
    adata,
    ref_model_dir="./models/whole_brain_ref_model",
    rg_label="Radial Glia",
    counts_layer="counts",
    train_query=False,
    output_dir="./outputs/prescreen",
    prefix="demo_prefix",
)

report = write_prescreen_report(
    result=result,
    output_dir="./outputs/prescreen/report",
    prefix="demo_prefix",
)

bdata = result.adata
summary = result.summary
```

## Expected Outputs

- `<prefix>.step1_prescreened.h5ad`
- `<prefix>.step1_rg_candidates.h5ad`
- `<prefix>.step1_scanvi_probs.csv`
- `<prefix>.step1_summary.json`
- Step1 report Markdown
- Step1 report manifest JSON
- report tables and available figures

## Interpretation Rule

Step1 is in vitro prescreening, not supervised test-set evaluation. Do not report accuracy, recall, confusion matrices, ROC/AUC, or crosstabs as performance metrics for this step.

## Report Coverage

The Step1 report API covers predicted label counts, RG candidate summaries, confidence distributions, optional UMAP views when `X_umap` exists, and concise English interpretation of identity composition and RG candidate fraction.

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

Step1 biological interpretation should emphasize RG enrichment, exclusion of non-RG/neuroblast-like/off-target populations, confidence of whole-brain mapping, and readiness for Step2 target-specific assessment. It must not use supervised accuracy, recall, ROC/AUC, or confusion-matrix language.
