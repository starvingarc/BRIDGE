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
3. Run selected `component_A(ctx)` through `component_F(ctx)`, or call `score(ctx)` for the default full pass.
4. Save component-level JSON/detail tables plus `summary.csv` and `manifest.json`.
5. Produce a simple final summary while polished plots and interpretation templates remain pending.

## Expected Outputs

- component global JSON files
- component detail tables when available
- report summary CSV
- report manifest JSON

## Roadmap Boundary

Future plotting may include component A-F summaries, weighted CLS figures, and final biological interpretation. Do not claim those outputs are complete until the plotting and interpretation templates are implemented.
