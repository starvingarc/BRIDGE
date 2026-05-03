# Formal Workflows

## Conceptual BRIDGE Pipeline

BRIDGE follows a three-step conceptual pipeline:
- **Step 1**: whole-brain pre-screening, with upstream reference construction as model-building context
- **Step 2**: identity assessment and candidate selection
- **Step 3**: CLS-based concordance scoring, reporting, and visualization

This file explains the current public package surface and how it maps onto the full BRIDGE architecture.

## What Is Formalized in BRIDGE v1

The current public repository formalizes:
- **Step 1**: notebook-callable whole-brain prescreening and report generation
- **Step 2**: identity assessment and report generation
- **Step 3**: CLS A-F, result packaging, single-dataset reports, and multi-protocol comparison

More concretely:
- `src/bridge/prescreen` provides the Step1 notebook-callable prescreening layer
- `src/bridge/prescreen/report.py` provides Step1 figures, tables, Markdown, manifest, and interpretation
- `src/bridge/identity` provides the Step2 package layer
- `src/bridge/identity/report.py` provides Step2 figures, tables, Markdown, manifest, and interpretation
- `src/bridge/cls` provides Step3 scoring plus `bridge.cls.report` for single-dataset and comparison reports
- `src/bridge/io` supports artifact packaging and `src/bridge/workflows` retains config helpers

The public repository is intended to present BRIDGE as software:
- installable from GitHub
- usable through notebook-first Python APIs
- supported by public templates that can guide notebook parameters
- documented as a workflow package for external readers and coding agents

## Executable Entrypoints

BRIDGE v1 exposes Step1-Step3 as notebook-callable APIs:
- `from bridge.prescreen import prescreen`
- `from bridge.identity import identify`
- `from bridge.cls import CLSContext, component_A, component_B, component_C, component_D, component_E, component_F, score`
- `from bridge.prescreen.report import write_report as write_prescreen_report`
- `from bridge.identity.report import write_report as write_identity_report`
- `from bridge.cls.report import write_report as write_cls_report, compare_reports`

The current execution model centers on:
- Step1 as notebook-callable whole-brain prescreening API
- Step2 as notebook-callable target identity assessment API
- Step3 as component-first notebook-callable CLS API
- report APIs called at the tail of each notebook

## Configuration Contract

BRIDGE v1 keeps YAML templates as editable parameter references. The top-level sections are:
- `version`
- `dataset`
- `paths`
- `runtime`
- `identity`
- `cls`
- `report`

Important semantics:
- `dataset.id` is the canonical run-level identifier for Step3 outputs
- `dataset.prefix` is the canonical naming prefix for Step2 artifacts
- `paths` are resolved relative to the YAML file location
- `identity` records the target class and Step2 artifact conventions used by downstream Step3/report code
- `cls` defines enabled Step3 components and component-specific settings
- `report` defines summary output filenames and optional CLS weights

## Step 1 Status

Step1 is the upstream reference-building layer in the BRIDGE architecture.

In thesis terms, Step1 corresponds to:
- reference atlas construction
- integration of embryonic brain data into a biologically grounded reference space
- whole-brain pre-screening before target-specific evaluation

In repository terms, Step1 prescreening is represented by `src/bridge/prescreen`; upstream reference construction remains model-building context. The Step1 report API summarizes predicted identity composition and RG candidate fraction without supervised test-set metric language.

## Step 2 Status

Step2 is the formal **Identity Assessment** layer. Its role is to identify high-confidence target candidates under a more specific reference.

The current formal Step2 package includes:
- query model loading
- prediction and probability handling
- calibration
- uncertainty estimation
- entropy-based and threshold-based candidate selection
- report summaries for probability, uncertainty, entropy, and candidate structure

## Step 3 Status

Step3 is the formal **concordance scoring and reporting** layer. Its role is to evaluate how well the selected in vitro candidates reconstruct the intended in vivo developmental program.

The current formal Step3 package includes:
- component-first CLS A-F notebook APIs
- shared result packaging
- summary CSV and manifest JSON generation
- single-dataset report API for component scores, weighted CLS, and available A-F diagnostics
- multi-protocol comparison API for radar, weighted CLS, and component heatmap summaries

In the current phase, the report layer consumes both:
- Step2 artifacts such as thresholds JSON and candidate-bearing Step2 h5ad outputs
- Step3 component JSON outputs

This means reporting now spans thesis Step2 outputs plus Step3 outputs rather than only listing CLS component scores.

The public validation surface is smoke-oriented and package-oriented. Full scientific validation can be maintained in deployment or development environments.

## Why the Distinction Matters

The repository intentionally distinguishes:
- the **full conceptual BRIDGE pipeline**
- the **subset of that pipeline already formalized in public package code**

This keeps the repository aligned with the thesis logic while making the released software surface easy to identify.
