# bridge-step2

Use this skill for BRIDGE Step2 mDA progenitor identity assessment.

## Purpose

Step2 consumes the Step1 RG candidate subset and runs target-specific identity assessment to identify mDA progenitor candidates.

## Expected User Prompt

Claude Code:

```text
/bridge-step2 identify mDA progenitor candidates from ./bridge-demo/runs/demo_dataset/step1 using ./bridge-demo/bridge.run.yaml
```

Codex:

```text
@bridge-step2 identify mDA progenitor candidates from ./bridge-demo/runs/demo_dataset/step1 using ./bridge-demo/bridge.run.yaml
```

## Required Inputs

- Step1 RG candidate subset
- target-specific reference AnnData and scANVI model path
- writable Step2 output directory

## Agent Responsibilities

1. Locate the Step1 RG candidate h5ad.
2. Validate the target-specific model and config.
3. In the Step2 notebook, call `from bridge.identity import identify`.
4. Run `identify(bdata_rg, adata_ref, ref_model_dir=..., target_class=..., output_dir=..., prefix=...)`.
5. Preserve the current Step2 artifact contract.
6. Call `from bridge.identity.report import write_report as write_identity_report`.
7. Run `write_identity_report(result=result, output_dir=..., prefix=..., target_class=...)` at the notebook tail.
8. Summarize candidate count, candidate fraction, and threshold metadata without overclaiming final biological interpretation.

## Notebook API

```python
from bridge.identity import identify
from bridge.identity.report import write_report as write_identity_report

result = identify(
    bdata_rg,
    adata_ref,
    ref_model_dir="./models/target_ref_model",
    target_class="RG_Mesencephalon_FP",
    output_dir="./outputs/identity",
    prefix="demo_prefix",
)

report = write_identity_report(
    result=result,
    output_dir="./outputs/identity/report",
    prefix="demo_prefix",
    target_class="RG_Mesencephalon_FP",
)
```

## Expected Outputs

- `<prefix>.thresholds.json`
- `<prefix>.bdata_step2.h5ad`
- `<prefix>.adata_ref_step2.h5ad`
- `<prefix>.probs_ref_cal.csv`
- `<prefix>.probs_query_cal.csv`
- `<prefix>.mean_org.csv`
- `<prefix>.std_org.csv`
- `<prefix>.Hnorm.csv`
- Step2 report Markdown
- Step2 report manifest JSON
- report tables and available figures

## Report Coverage

The Step2 report API covers target probability, uncertainty, entropy, candidate summaries, optional UMAP views, and mean-probability identity composition with an `Uncertain` label below cutoff. Interpret high `p_mean` with low `p_std`/`Hnorm` as stable target convergence; interpret high uncertainty as boundary, transition, or competing-fate structure.
