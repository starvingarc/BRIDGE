# BRIDGE Roadmap

This roadmap tracks the public agent-first BRIDGE demo path. It complements the formal package roadmap: Step1 prescreening now has a notebook-callable package API, Step2 and Step3 have package/CLI workflows, and Step0 remains agent-guided setup.

## Phase 1: Agent-First Documentation and Step Skills

Goal: make the GitHub repository directly usable in a demo where a first-time user copies commands into Claude Code or Codex.

Planned deliverables:
- README quick start centered on agent commands
- `docs/agent_demo.md` with the full video script
- repository-local skills for `bridge-step0`, `bridge-step1`, `bridge-step2`, and `bridge-step3`
- supporting docs for models, notebooks, and skill behavior

Status: agent docs and skills are present; Step1 is being connected as notebook-callable package code.

## Phase 2: Model Assets and Step0 Validation

Goal: make Step0 capable of validating the model assets required for a complete demo run.

Planned deliverables:
- model metadata under `models/`
- documented model directory layout
- validation checks for required model files and labels
- environment initialization using the default `bridge` conda environment

Model note:
- if large model files are stored in the repository tree, they should use Git LFS rather than normal Git blobs.

## Phase 3: Step1-Step3 Notebook Skeletons

Goal: ensure each biological step can leave a readable executed notebook or notebook-like run record.

Planned deliverables:
- Step1 prescreening notebook skeleton
- Step2 mDA progenitor identity notebook skeleton
- Step3 CLS/report notebook skeleton
- consistent links between notebooks and machine-readable artifacts

Current boundary:
- notebook skeletons may include simple summaries and artifact tables
- polished plotting and rich biological interpretation are not required in this phase

## Phase 4: Plotting Functions and Interpretation Templates

Goal: integrate the per-step plotting functions and result interpretation text after those functions are supplied.

Planned deliverables:
- Step1 prediction distribution, RG candidate, and UMAP-style summaries
- Step2 probability, uncertainty, entropy, and candidate summaries
- Step3 component A-F, weighted CLS, and final interpretation summaries
- result-oriented interpretation templates for each step

Status: pending user-supplied plotting functions.

## Phase 5: Polished Demo and Batch Extensions

Goal: turn the single-dataset demo into a polished public workflow and extend it to multi-dataset use.

Planned deliverables:
- complete end-to-end video demo script
- fully executed example run with public-safe paths and assets
- batch report guidance for comparing multiple in vitro differentiation datasets
- final documentation pass for external users and reviewers
