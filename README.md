# BRIDGE

**Brain-Referenced In vivo-to-in vitro Developmental Guidance and Evaluation**

BRIDGE is an open-source research software package for evaluating in vitro cell products against in vivo developmental references.

## What BRIDGE Does

BRIDGE currently formalizes the released parts of a three-step workflow:
- **Step 1**: reference construction and whole-brain pre-screening
- **Step 2**: target-specific identity assessment and candidate selection
- **Step 3**: CLS-based concordance scoring and report generation

Current public package scope:
- Step 2 is released as formal package code
- Step 3 is released as formal package code
- Step 1 remains documented architecture and is not yet released as executable package code

## Installation

### Install with a coding agent

Send your coding agent (Claude Code, Codex, or a similar tool) this repository and ask it to install BRIDGE.

### Manual installation

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
pip install -e .[test]
pip install -e .[runtime]
pip install -e .[trajectory]
pip install -e .[regulon]
pip install -e .[notebook]
```

## Quick Start

Start from the minimal editable workflow template:

```bash
cp configs/bridge.minimal.yaml my-run.yaml
```

Edit `my-run.yaml` for your own paths and workflow parameters, then inspect the CLI:

```bash
bridge --help
```

Validate a Step 2 workflow config without running the full workflow:

```bash
bridge identity run --config my-run.yaml --dry-run
```

Validate a Step 3 workflow config without running the full workflow:

```bash
bridge cls run --config my-run.yaml --dry-run
```

Run report generation from existing BRIDGE artifacts:

```bash
bridge report summarize --config my-run.yaml
bridge report summarize-batch --config-list <config-list.yaml>
```

## CLI Overview

Current workflow-level commands:
- `bridge identity run`
- `bridge cls run`
- `bridge report summarize`
- `bridge report summarize-batch`

These commands expose the released Step 2 and Step 3 package surface without introducing a Step 1 execution command before that part of the workflow is formalized.

## Workflow Model

### Step 1

Reference construction and whole-brain pre-screening define the in vivo coordinate system that anchors BRIDGE. This is part of the conceptual architecture and is documented in the repository, but it is not yet released as executable package code.

### Step 2

Identity Assessment refines target candidates under a more specific reference. The current package includes:
- query model loading
- probability handling and calibration
- uncertainty estimation
- entropy-based and threshold-based candidate selection

### Step 3

Step 3 evaluates developmental concordance after candidate selection. The current package includes:
- CLS component A-F
- structured report generation
- per-dataset and batch-level summary packaging

## Skill Interface

BRIDGE includes a repository-local skill interface for coding agents and workflow-aware assistants.

See:
- [docs/skills.md](docs/skills.md)
- [.claude/skills](.claude/skills)

Current public skills:
- `bridge`
- `bridge-identity`
- `bridge-cls`

## Scope and Roadmap

Current public scope:
- formal Step 2 package code
- formal Step 3 package code
- config templates
- workflow and concept documentation
- skill-interface documentation

Not currently part of the released package surface:
- exploratory notebooks from earlier research drafts
- unpublished analysis fragments
- Step 1 executable implementation

Roadmap:
- continue formalizing BRIDGE as workflow-oriented open-source software
- bring Step 1 into the same execution model once its interfaces stabilize
- keep tightening performance, output contracts, and software presentation

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
|- tests/
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
- `tests/`: minimal public smoke and config tests
- `configs/`: public config templates and environment files
- `models/`: model metadata and model-related notes
- `notebooks/`: placeholder area for formal notebooks and examples
- `docs/`: workflow, concept, and roadmap documentation
- `.github/`: community files and CI
- `.claude/skills/`: repository-local skill interface
