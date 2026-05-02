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

1. Prefer notebook-callable package code over a CLI for Step1.
2. Generate or update a Step1 notebook that imports `from bridge.prescreen import prescreen`.
3. Validate that the input `.h5ad` exists and can be read in the active environment.
4. Validate the whole-brain reference model path.
5. Call `prescreen(adata, ref_model_dir=..., output_dir=..., prefix=...)` with explicit parameters.
6. Save the full prescreened object, RG candidate subset, probability table, and summary JSON through the API.
7. Create a simple run summary or notebook skeleton when notebook scaffolding is available.

## Notebook API

```python
from bridge.prescreen import prescreen

result = prescreen(
    adata,
    ref_model_dir="./models/whole_brain_ref_model",
    rg_label="Radial Glia",
    counts_layer="counts",
    train_query=False,
    output_dir="./outputs/prescreen",
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

## Interpretation Rule

Step1 is in vitro prescreening, not supervised test-set evaluation. Do not report accuracy, recall, confusion matrices, or crosstabs as performance metrics for this step.

## Roadmap Boundary

Future plotting may include prediction distributions, RG candidate summaries, and UMAP-style summaries. Do not invent polished plotting functions before they are added to the repository.
