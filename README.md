# BRIDGE

**Brain-Referenced In vivo-to-in vitro Developmental Guidance and Evaluation**

BRIDGE is an open-source research software package and agent-guided workflow for evaluating in vitro cell products against in vivo developmental references.

BRIDGE is designed to be usable in two ways:
- as a Python package for notebook-callable Step1 prescreening and Step2 identity assessment, plus remaining CLI workflows for Step3/report packaging
- as an agent-first demo workflow where a first-time user asks Claude Code or Codex to run each step from repository-local guidance

## Agent-First Quick Start

The recommended public demo path is to let an agent install and operate BRIDGE from this repository. In a demo video, the user can copy the prompts below directly from GitHub.

### 1. Install BRIDGE

Send this to Claude Code, Codex, or a similar coding agent:

```text
Help me install https://github.com/starvingarc/BRIDGE
```

The agent should clone or install BRIDGE, inspect the repository guidance, and prepare to run the step skills below.

### 2. Step0: initialize environment, models, and config

Claude Code:

```text
/bridge-step0 initialize BRIDGE in ./bridge-demo using env bridge
```

Codex:

```text
@bridge-step0 initialize BRIDGE in ./bridge-demo using env bridge
```

Step0 should create or validate the `bridge` conda environment, install BRIDGE, verify model assets under `models/`, and create an initial run config and output directory.

### 3. Step1: whole-brain prescreening

Claude Code:

```text
/bridge-step1 prescreen the h5ad file ./my-data/organoid.h5ad using ./bridge-demo/bridge.run.yaml and write outputs to ./bridge-demo/runs/demo_dataset/step1
```

Codex:

```text
@bridge-step1 prescreen the h5ad file ./my-data/organoid.h5ad using ./bridge-demo/bridge.run.yaml and write outputs to ./bridge-demo/runs/demo_dataset/step1
```

Step1 screens an in vitro `.h5ad` dataset against the whole-brain reference model and marks cells as `RG_candidate` or `non_RG`. In notebooks, agents should call `from bridge.prescreen import prescreen` and then `prescreen(adata, ref_model_dir=...)`. Because this is an in vitro prescreening step rather than a labeled test set, documentation and reports should not present accuracy, recall, or confusion-matrix metrics here.

### 4. Step2: mDA progenitor identity assessment

Claude Code:

```text
/bridge-step2 identify mDA progenitor candidates from ./bridge-demo/runs/demo_dataset/step1 using ./bridge-demo/bridge.run.yaml
```

Codex:

```text
@bridge-step2 identify mDA progenitor candidates from ./bridge-demo/runs/demo_dataset/step1 using ./bridge-demo/bridge.run.yaml
```

Step2 consumes the Step1 RG candidate subset and runs target-specific identity assessment for mDA progenitor candidates. In notebooks, agents should call `from bridge.identity import identity_assessment` and then `identity_assessment(bdata_rg, adata_ref, ref_model_dir=..., target_class=...)`.

### 5. Step3: CLS scoring and report generation

Claude Code:

```text
/bridge-step3 score CLS for ./bridge-demo/runs/demo_dataset/step2 using ./bridge-demo/bridge.run.yaml
```

Codex:

```text
@bridge-step3 score CLS for ./bridge-demo/runs/demo_dataset/step2 using ./bridge-demo/bridge.run.yaml
```

Step3 consumes Step2 artifacts, runs CLS components, and summarizes the final BRIDGE scoring outputs.

Command names are lowercase for agent compatibility. The project brand remains **BRIDGE**.

See [docs/agent_demo.md](docs/agent_demo.md) for the full demo script and [docs/roadmap.md](docs/roadmap.md) for the staged roadmap.

## What BRIDGE Does

BRIDGE organizes a three-step biological workflow plus a setup step:
- **Step0**: environment, model, and configuration initialization
- **Step1**: whole-brain reference prescreening for RG-like candidates
- **Step2**: target-specific identity assessment and mDA progenitor candidate selection
- **Step3**: CLS-based concordance scoring and report generation

Current package surface:
- Step1 whole-brain prescreening is available as a notebook-callable Python API
- Step2 is available as a notebook-callable Python API
- Step3 is available as formal package code and CLI workflow
- Step0 remains agent-guided setup and model/config initialization
- upstream reference construction remains roadmap/model-building context

Polished per-step plotting functions, rich biological interpretation text, and publication-ready executed notebooks are roadmap items. The current documentation describes the intended artifact flow without claiming those visual/report layers are complete.

## Manual Installation

Install directly from GitHub:

```bash
pip install git+https://github.com/starvingarc/BRIDGE.git
```

Or install from a local source checkout:

```bash
git clone https://github.com/starvingarc/BRIDGE.git
cd BRIDGE
pip install -e .
```

Optional dependency groups:

```bash
pip install -e .[runtime]
pip install -e .[trajectory]
pip install -e .[regulon]
pip install -e .[notebook]
```

## Python API and CLI Overview

Notebook-callable APIs:
- `from bridge.prescreen import prescreen`
- `from bridge.identity import identity_assessment`

Remaining workflow-level CLI commands:
- `bridge cls run`
- `bridge report summarize`
- `bridge report summarize-batch`

Step1 and Step2 are notebook-first APIs. The CLI remains for Step3 CLS and report packaging.

Start from the minimal editable workflow template when preparing Step3/report configuration:

```bash
cp configs/bridge.minimal.yaml my-run.yaml
bridge --help
bridge cls run --config my-run.yaml --dry-run
```

## Skill Interface

BRIDGE includes a repository-local skill interface for coding agents and workflow-aware assistants.

See:
- [docs/skills.md](docs/skills.md)
- [.claude/skills](.claude/skills)

Current public skills:
- `bridge`
- `bridge-step0`
- `bridge-step1`
- `bridge-step2`
- `bridge-step3`
- `bridge-identity`
- `bridge-cls`

## Repository Layout

```text
BRIDGE/
|- README.md
|- LICENSE
|- CONTRIBUTING.md
|- CODE_OF_CONDUCT.md
|- SECURITY.md
|- CLAUDE.md
|- pyproject.toml
|- src/bridge/
|- configs/
|- models/
|- notebooks/
|- docs/
|- .github/
`- .claude/
   `- skills/
```

Directory meanings:
- `src/bridge/`: formal Python package
- `configs/`: public config templates and environment files
- `models/`: public model metadata and model-asset entry point
- `notebooks/`: placeholder area for formal notebook entrypoints and examples
- `docs/`: workflow, demo, concept, and roadmap documentation
- `.github/`: community files and CI
- `.claude/skills/`: repository-local agent skill interface
