# BRIDGE Agent Demo Script

This document describes the intended public demo flow for BRIDGE. The demo is agent-first: a first-time user copies commands from GitHub into Claude Code or Codex and lets the agent run the workflow.

The current public deliverable is documentation, workflow guidance, and artifact contracts. Final plotting functions, rich report interpretation, and polished executed notebooks are roadmap items that will be added after the per-step plotting functions are supplied.

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
- the agent can run `bridge --help` once the environment is active
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
- model assets under `models/` or a model manifest pointing to them
- permission to create or validate a conda environment named `bridge`

Agent responsibility:
- create or validate the `bridge` conda environment
- install BRIDGE in editable or package mode
- validate that required model directories and metadata exist under `models/`
- create a run directory such as `./bridge-demo/runs/demo_dataset/`
- create an initial run config such as `./bridge-demo/bridge.run.yaml`
- print the next Step1 command with the user data path left explicit

Expected current artifacts:
- initialized run directory
- editable YAML config
- environment verification output
- model validation summary

Future notebook/report goals:
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
- read and validate the `.h5ad` input
- align query variables to the whole-brain reference model
- run whole-brain prescreening
- annotate cells as `RG_candidate` or `non_RG`
- save the full prescreened object and the RG candidate subset
- produce a simple executed notebook or run log when notebook scaffolding is available

Expected current artifacts:
- `step1_prescreened.h5ad`
- `step1_rg_candidates.h5ad`
- probability or prediction table
- simple artifact summary

Important interpretation rule:
- Step1 is in vitro prescreening, not a held-out labeled test set. Do not report accuracy, recall, confusion matrices, or other supervised test-set metrics for this step.

Future notebook/report goals:
- prediction distribution plots
- RG candidate summaries
- UMAP-style visual summaries
- short result-oriented interpretation text

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
- target-specific reference/model metadata from the config
- writable Step2 output directory

Agent responsibility:
- consume the Step1 RG candidate subset
- run target-specific identity assessment for mDA progenitor candidates
- preserve the current Step2 artifact contract
- summarize candidate count and threshold metadata without overclaiming biological interpretation

Expected current artifacts:
- `<prefix>.thresholds.json`
- `<prefix>.bdata_step2.h5ad`
- `<prefix>.adata_ref_step2.h5ad`
- `<prefix>.probs_ref_cal.csv`
- `<prefix>.probs_query_cal.csv`
- `<prefix>.mean_org.csv`
- `<prefix>.std_org.csv`
- `<prefix>.Hnorm.csv`

Future notebook/report goals:
- probability distribution plots
- uncertainty and entropy summaries
- mDA progenitor candidate visual summaries
- concise result-oriented interpretation text

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
- Step2 artifact set
- CLS configuration
- any component-specific assets required by enabled components

Agent responsibility:
- run enabled CLS components
- save component-level outputs
- run report summarization
- preserve machine-readable output contracts
- produce a simple final summary while plotting/report polish is still pending

Expected current artifacts:
- component global JSON files
- component detail tables when available
- report summary CSV
- report manifest JSON

Future notebook/report goals:
- component A-F visual summary
- weighted total CLS figure
- final biological interpretation section
- multi-dataset comparison extensions
