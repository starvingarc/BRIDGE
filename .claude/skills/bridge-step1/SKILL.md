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

1. Validate that the input `.h5ad` exists and can be read in the active environment.
2. Validate the model path from the config.
3. Align query variables to the reference model as required by the model loader.
4. Run whole-brain prescreening.
5. Annotate cells with Step1 prediction columns and `RG_candidate` or `non_RG` status.
6. Save the full prescreened object and the RG candidate subset.
7. Create a simple run summary or notebook skeleton when notebook scaffolding is available.

## Expected Outputs

- `step1_prescreened.h5ad`
- `step1_rg_candidates.h5ad`
- prediction or probability table
- simple artifact summary

## Interpretation Rule

Step1 is in vitro prescreening, not supervised test-set evaluation. Do not report accuracy, recall, confusion matrices, or crosstabs as performance metrics for this step.

## Roadmap Boundary

Future plotting may include prediction distributions, RG candidate summaries, and UMAP-style summaries. Do not invent polished plotting functions before they are added to the repository.
