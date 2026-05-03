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
3. Validate that the input `.h5ad` exists and can be read in the active environment.
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
