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
- target-specific model and reference configuration
- writable Step2 output directory

## Agent Responsibilities

1. Locate the Step1 RG candidate h5ad.
2. Validate the target-specific model and config.
3. Run the BRIDGE identity workflow or equivalent package API.
4. Preserve the current Step2 artifact contract.
5. Summarize candidate count and threshold metadata without overclaiming final biological interpretation.

## Expected Outputs

- `<prefix>.thresholds.json`
- `<prefix>.bdata_step2.h5ad`
- `<prefix>.adata_ref_step2.h5ad`
- `<prefix>.probs_ref_cal.csv`
- `<prefix>.probs_query_cal.csv`
- `<prefix>.mean_org.csv`
- `<prefix>.std_org.csv`
- `<prefix>.Hnorm.csv`

## Roadmap Boundary

Future plotting may include probability distributions, uncertainty and entropy views, and candidate summaries. Until those functions are added, keep notebooks or summaries simple and artifact-focused.
