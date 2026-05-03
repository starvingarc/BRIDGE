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
7. Use `compare_reports(...)` when comparing multiple protocols or datasets.
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

# Default full A-F run for report generation.
result = score(ctx)

report = write_cls_report(
    result=result,
    ctx=ctx,
    output_dir="./outputs/cls/report",
    prefix="demo_prefix",
)
```

Multi-protocol comparison:

```python
comparison = compare_reports(
    protocols=[
        {"name": "SphereDiff", "dataset_id": "sphere", "step3_dir": "./runs/sphere/step3"},
        {"name": "MacroDiff", "dataset_id": "macro", "step3_dir": "./runs/macro/step3"},
    ],
    output_dir="./runs/comparison/cls_report",
    prefix="cls_comparison",
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

## Report Coverage

The Step3 report API covers component score bar and heatmap, weighted CLS summary, available A-F diagnostic panels when required columns or files exist, and multi-protocol comparison figures. Missing optional component diagnostics should be recorded as manifest warnings, not treated as fatal errors.

## Notebook-Visible Report Sections

After the core workflow runs, the notebook must include notebook-visible report sections rather than only writing files under `report/`. For each report table, add a short Markdown context cell, a code cell that builds and displays the table, and a concise interpretation Markdown cell. For each report figure, add a short Markdown context cell, a code cell that calls the public `plot_*` function and displays the figure, and a concise interpretation Markdown cell. The final cell should still call `write_report(...)`, print artifact paths, and save the standard Markdown, manifest, CSV, and image files. Agents should display each table and display each figure as code-cell output.
