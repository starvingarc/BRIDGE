# BRIDGE Agent Demo Script

This document describes the intended public demo flow for BRIDGE. The demo is agent-first: a first-time user copies commands from GitHub into Claude Code or Codex and lets the agent run the workflow.

The current public deliverable includes workflow guidance, notebook-callable package APIs, artifact contracts, and per-step report APIs for figures, Markdown reports, JSON manifests, and concise English interpretation. Formal polished example notebooks are still a roadmap item. Notebook display rule: report tables and figures should appear as executed code-cell outputs with short context and interpretation around them, while the saved `report/` folder remains the artifact contract.

## Part 1: Install BRIDGE

User prompt:

```text
Help me install https://github.com/starvingarc/BRIDGE
```

Agent responsibility:
- clone or install BRIDGE from GitHub
- inspect `README.md`, `docs/`, `configs/`, `models/`, and `.claude/skills/`
- identify the recommended agent workflow commands
- avoid putting runtime data into the repository checkout

Expected current outcome:
- BRIDGE source or package is available
- the agent can run package and runtime import smoke checks once the environment is active
- the user is ready to run Step0

Future demo polish:
- include a short install verification cell or terminal transcript in the demo notes

## Part 2: Step0 Environment, Models, and Config

Claude Code command:

```text
/bridge-step0 initialize BRIDGE in ./bridge-demo using env bridge
```

Codex command:

```text
@bridge-step0 initialize BRIDGE in ./bridge-demo using env bridge
```

Required input:
- a BRIDGE checkout or installed package
- model assets under `models/` or public object-storage URLs declared in `models/assets.json`
- permission to create or validate a conda environment named `bridge`

Agent responsibility:
- create or validate the `bridge` conda environment
- install BRIDGE with workflow runtime dependencies, for example `python -m pip install -e ".[workflow]"` from a source checkout
- validate `models/assets.json` and download or verify required model assets under `models/`
- create a run directory such as `./bridge-demo/runs/demo_dataset/`
- create an initial run config such as `./bridge-demo/bridge.run.yaml`
- print the next Step1 command with the user data path left explicit

Expected current artifacts:
- initialized run directory
- editable YAML config
- environment verification output
- model validation summary

Future demo polish:
- a setup notebook or setup report is optional; it should remain lightweight and focus on reproducibility

## Part 3: Step1 Whole-Brain Prescreening

Claude Code command:

```text
/bridge-step1 prescreen the h5ad file ./my-data/organoid.h5ad using ./bridge-demo/bridge.run.yaml and write outputs to ./bridge-demo/runs/demo_dataset/step1
```

Codex command:

```text
@bridge-step1 prescreen the h5ad file ./my-data/organoid.h5ad using ./bridge-demo/bridge.run.yaml and write outputs to ./bridge-demo/runs/demo_dataset/step1
```

Required input:
- one in vitro `.h5ad` dataset
- a whole-brain reference model configured by Step0
- a writable Step1 output directory

Agent responsibility:
- generate or update a Step1 notebook that imports `from bridge.prescreen import prescreen`
- read and validate the `.h5ad` input
- call `prescreen(adata, ref_model_dir=..., output_dir=..., prefix=...)`
- annotate cells as `RG_candidate` or `non_RG`
- save the full prescreened object, RG candidate subset, probability table, and summary JSON through the API
- call `from bridge.prescreen.report import write_report as write_prescreen_report`
- build and display Step1 report tables, figures, and interpretation in notebook cells, then run `write_prescreen_report(result=step1, output_dir=..., prefix=...)` to save figures, tables, Markdown, manifest, and English interpretation

Expected current artifacts:
- `<prefix>.step1_prescreened.h5ad`
- `<prefix>.step1_rg_candidates.h5ad`
- `<prefix>.step1_scanvi_probs.csv`
- `<prefix>.step1_summary.json`
- report directory with Markdown report, manifest JSON, tables, and available figures

Important interpretation rule:
- Step1 is in vitro prescreening, not a held-out labeled test set. Do not report accuracy, recall, confusion matrices, or other supervised test-set metrics for this step.

Report API coverage:
- prediction label counts
- RG candidate versus non-RG summary
- prediction confidence distribution
- optional UMAP views when `X_umap` is present
- concise interpretation of global identity composition and RG candidate fraction

## Part 4: Step2 mDA Progenitor Identity Assessment

Claude Code command:

```text
/bridge-step2 identify mDA progenitor candidates from ./bridge-demo/runs/demo_dataset/step1 using ./bridge-demo/bridge.run.yaml
```

Codex command:

```text
@bridge-step2 identify mDA progenitor candidates from ./bridge-demo/runs/demo_dataset/step1 using ./bridge-demo/bridge.run.yaml
```

Required input:
- Step1 RG candidate subset
- target-specific reference AnnData from `paths.reference_h5ad`
- target-specific scANVI model from `paths.ref_model_dir`
- writable Step2 output directory

Agent responsibility:
- consume the Step1 RG candidate subset
- run `from bridge.identity import identify` in the Step2 notebook
- load only the configured target reference AnnData, never `paths.ref_sceniclike_h5ad`, then call `identify(..., reference_h5ad_path=...)` and preserve the Step2 artifact contract without duplicating the full reference file
- call `from bridge.identity.report import write_report as write_identity_report`
- build and display Step2 report tables, figures, and interpretation in notebook cells, then run `write_identity_report(result=step2, output_dir=..., prefix=..., target_class=...)`
- summarize candidate count and threshold metadata without overclaiming biological interpretation

Expected current artifacts:
- `<prefix>.thresholds.json`
- `<prefix>.bdata_step2.h5ad`
- `<prefix>.adata_ref_step2.h5ad` (preferably a symlink to the configured target reference)
- `<prefix>.probs_ref_cal.csv`
- `<prefix>.probs_query_cal.csv`
- `<prefix>.mean_org.csv`
- `<prefix>.std_org.csv`
- `<prefix>.Hnorm.csv`
- report directory with Markdown report, manifest JSON, tables, and available figures

Report API coverage:
- target probability, uncertainty, and entropy distributions
- candidate fraction summary
- mean-probability identity composition with an `Uncertain` label below cutoff
- optional UMAP views when `X_umap` is present
- interpretation of stable target convergence versus boundary, transition, or competing-fate cells

## Part 5: Step3 CLS Scoring and Report Generation

Claude Code command:

```text
/bridge-step3 score CLS for ./bridge-demo/runs/demo_dataset/step2 using ./bridge-demo/bridge.run.yaml
```

Codex command:

```text
@bridge-step3 score CLS for ./bridge-demo/runs/demo_dataset/step2 using ./bridge-demo/bridge.run.yaml
```

Required input:
- Step2 `bdata` and `adata_ref` objects or loaded Step2 artifact h5ad files
- `probs_ref_cal` when running components A or C
- component-specific assets required by selected components, such as embeddings or regulon assets

Agent responsibility:
- build `CLSContext` in the Step3 notebook
- run selected `component_A(ctx)` through `component_F(ctx)`, or call `score(ctx)` for the default full pass
- preserve machine-readable output contracts
- call `from bridge.cls.report import write_report as write_cls_report, compare_reports`
- build and display Step3 report tables, figures, and interpretation in notebook cells, then run `write_cls_report(result=cls_result, ctx=ctx, output_dir=..., prefix=...)`
- for the demo, use `compare_reports(...)` to show a different-protocol comparison: SphereDiff (CSC 2025), MacroDiff (unpublished), MSK-DA01 (CSC 2021), and the current BRIDGE demo dataset. The root directory for the three paper baseline CLS artifacts should come from local config or the user prompt, not from a committed private path.

Expected current artifacts:
- component global JSON files
- component detail tables when available
- `summary.csv`
- `manifest.json`
- report directory with Markdown report, manifest JSON, tables, and available single-dataset figures
- optional multi-protocol comparison report with radar, weighted CLS bar, and component heatmap
- different-protocol comparison report with radar, weighted CLS bar, component heatmap, component B diagnostics, F1/F2 regulon diagnostics, and a component score table when paper baseline artifacts are available

Report API coverage:
- component score bar and heatmap
- weighted CLS summary
- available A-F diagnostic panels when the required component columns or files exist
- multi-protocol comparison figures inspired by the thesis Fig 3-9 / Fig 3-10 style
- interpretation that emphasizes component decomposition and structural differences rather than simple protocol ranking
