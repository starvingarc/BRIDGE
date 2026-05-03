# BRIDGE Roadmap

This roadmap tracks the public agent-first BRIDGE demo path. It complements the formal package roadmap: Step1 prescreening, Step2 identity assessment, Step3 CLS scoring, and per-step reports now have notebook-callable package APIs; Step0 remains agent-guided setup.

## Phase 1: Agent-First Documentation and Step Skills

Goal: make the GitHub repository directly usable in a demo where a first-time user copies commands into Claude Code or Codex.

Planned deliverables:
- README quick start centered on agent commands
- `docs/agent_demo.md` with the full video script
- repository-local skills for `bridge-step0`, `bridge-step1`, `bridge-step2`, and `bridge-step3`
- supporting docs for models, notebooks, and skill behavior

Status: agent docs and skills are present; Step1, Step2, Step3, and report APIs are connected as notebook-callable package code.

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
- Step1 prescreening notebook skeleton that calls `prescreen(...)` and `bridge.prescreen.report.write_report(...)`
- Step2 mDA progenitor identity notebook skeleton that calls `identify(...)` and `bridge.identity.report.write_report(...)`
- Step3 CLS notebook skeleton that calls component APIs, `score(...)`, `bridge.cls.report.write_report(...)`, and optional `compare_reports(...)`
- consistent links between notebooks and machine-readable artifacts

Current boundary:
- package report APIs are available
- formal public-safe executed notebooks still need to be curated and verified

## Phase 4: Report Polish and Interpretation Refinement

Goal: refine the package report APIs and interpretation text as demo data, model assets, and public notebooks stabilize.

Available now:
- Step1 prediction distribution, RG candidate, and optional UMAP-style summaries
- Step2 probability, uncertainty, entropy, candidate, and optional UMAP summaries
- Step3 component A-F diagnostics when supporting files exist
- weighted CLS and multi-protocol comparison figures
- concise English interpretation templates for each step

Future polish:
- tune figure styling on the final public demo dataset
- add any additional panels you want after reviewing executed outputs
- expand interpretation templates only where the data supports it

## Phase 5: Polished Demo and Batch Extensions

Goal: turn the single-dataset demo into a polished public workflow and extend it to broader multi-dataset use.

Planned deliverables:
- complete end-to-end video demo script
- fully executed example run with public-safe paths and assets
- multi-protocol comparison guidance using `compare_reports(...)`
- broader batch/multi-dataset extensions beyond the initial demo
- final documentation pass for external users and reviewers
