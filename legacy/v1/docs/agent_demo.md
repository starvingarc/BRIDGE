# BRIDGE Agent Demo Script

BRIDGE is designed for an agent-first public demo: a user copies short commands from GitHub into Claude Code or Codex, and the agent runs each notebook/API step in a prepared workspace.

The demo has five parts: installation, Step0 setup, Step1 prescreening, Step2 identity assessment, and Step3 CLS scoring with protocol comparison. Each biological step should leave an executed notebook with visible code, tables, figures, short interpretation, and a saved `report/` artifact folder.

## Notebook Record Standard

For Step1-Step3, notebooks should read like an analysis record rather than a file dump:

1. Opening Markdown explains the step, its biological role, inputs, and outputs.
2. Core workflow cells load data, validate config/model assets, run the package API, and print concise metadata.
3. Each table or figure has its own section: purpose/context Markdown, exactly one executable code cell, rendered output, and biological interpretation Markdown.
4. A final Markdown summary states what the step concluded and how it feeds the next step.
5. The final artifact cell calls `write_report(...)` and prints saved paths.

Use `display_matplotlib_figure(fig)` from `bridge.reporting.notebook` for plot cells so Jupyter and VS Code store real `image/png` outputs.

## Part 1: Install BRIDGE

User prompt:

```text
Help me install https://github.com/starvingarc/BRIDGE
```

Agent responsibilities:
- clone or install BRIDGE from GitHub
- inspect `README.md`, `docs/`, `configs/`, `models/`, and `.claude/skills/`
- install workflow dependencies in the requested environment
- keep runtime data and downloaded model assets outside Git history

Expected outcome:
- BRIDGE source or package is available
- the environment can import the package and workflow runtime dependencies
- the user is ready to run Step0

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
- permission to create or validate the requested conda environment

Agent responsibilities:
- create or validate the conda environment, defaulting to `bridge`
- install BRIDGE with workflow runtime dependencies from a source checkout when needed
- validate `models/assets.json` and fetch or verify model/reference assets under `models/`
- create a run directory and editable run config such as `./bridge-demo/bridge.run.yaml`
- print the next Step1 command with the user data path left explicit

Expected artifacts:
- initialized run directory
- editable YAML config
- environment and model validation summary

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

Agent responsibilities:
- generate or update a Step1 notebook
- import `from bridge.prescreen import prescreen`
- call `prescreen(adata, ref_model_dir=..., output_dir=..., prefix=...)`
- annotate cells as `RG_candidate` or `non_RG`
- save the full prescreened object, RG candidate subset, probability table, and summary JSON
- build notebook-visible tables/figures through `bridge.prescreen.report` helpers
- call `write_prescreen_report(result=step1, output_dir=..., prefix=...)` to save the standard report artifacts

Expected artifacts:
- `<prefix>.step1_prescreened.h5ad`
- `<prefix>.step1_rg_candidates.h5ad`
- `<prefix>.step1_scanvi_probs.csv`
- `<prefix>.step1_summary.json`
- Step1 notebook and report folder with Markdown, manifest JSON, tables, and available figures

Interpretation style:
- describe broad identity composition, RG enrichment, exclusion of non-RG/neuroblast-like/off-target populations, and readiness for target-specific Step2 assessment
- treat Step1 as in vitro prescreening rather than held-out test-set evaluation

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

Agent responsibilities:
- consume the Step1 RG candidate subset
- load the configured target reference AnnData
- run `from bridge.identity import identify`
- call `identify(..., reference_h5ad_path=...)` so large reference artifacts can be represented by a symlink when appropriate
- preserve the Step2 artifact contract
- build notebook-visible report tables/figures through `bridge.identity.report` helpers
- call `write_identity_report(result=step2, output_dir=..., prefix=..., target_class=...)`

Expected artifacts:
- `<prefix>.thresholds.json`
- `<prefix>.bdata_step2.h5ad`
- `<prefix>.adata_ref_step2.h5ad`
- `<prefix>.probs_ref_cal.csv`
- `<prefix>.probs_query_cal.csv`
- `<prefix>.mean_org.csv`
- `<prefix>.std_org.csv`
- `<prefix>.Hnorm.csv`
- Step2 notebook and report folder with Markdown, manifest JSON, tables, and available figures

Interpretation style:
- high calibrated target probability with low variability and low entropy supports stable target convergence
- elevated uncertainty highlights boundary, transitional, or competing-fate structure

## Part 5: Step3 CLS Scoring and Protocol Comparison

Claude Code command:

```text
/bridge-step3 score CLS for ./bridge-demo/runs/demo_dataset/step2 using ./bridge-demo/bridge.run.yaml
```

Codex command:

```text
@bridge-step3 score CLS for ./bridge-demo/runs/demo_dataset/step2 using ./bridge-demo/bridge.run.yaml
```

Required input:
- Step2 `bdata` and `adata_ref` objects or loaded Step2 h5ad artifacts
- `probs_ref_cal` when running components A or C
- component-specific assets for selected CLS components
- optional baseline protocol artifacts for comparison with SphereDiff, MacroDiff, and MSK-DA01

Agent responsibilities:
- build `CLSContext` in the Step3 notebook
- run selected `component_A(ctx)` through `component_F(ctx)` or call `score(ctx)` for the default A-F pass
- write component JSON/detail tables, `summary.csv`, and `manifest.json`
- call `write_cls_report(result=cls_result, ctx=ctx, output_dir=..., prefix=...)`
- call `compare_reports(...)` when comparison protocol artifacts are available
- show single-dataset component overview and different-protocol comparison panels as notebook-visible sections

Expected artifacts:
- component global JSON files and detail tables when available
- `summary.csv`
- `manifest.json`
- Step3 notebook and report folder
- optional comparison report with radar, weighted CLS bar, component heatmap, Component B pseudo-bulk diagnostic, and Component F1/F2 regulon diagnostics

Interpretation style:
- CLS summarizes multidimensional developmental concordance after candidate selection
- component decomposition should explain structural differences across identity, expression, transferability, neighborhood, pseudotime, and regulon axes
