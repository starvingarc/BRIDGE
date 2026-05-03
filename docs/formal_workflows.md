# Formal Workflows

## Conceptual BRIDGE Pipeline

BRIDGE follows a three-step conceptual pipeline:
- **Step 1**: whole-brain pre-screening, with upstream reference construction as model-building context
- **Step 2**: identity assessment and candidate selection
- **Step 3**: CLS-based concordance scoring, reporting, and visualization

This file explains the current public package surface and how it maps onto the full BRIDGE architecture.

## What Is Formalized in BRIDGE v1

The current public repository formalizes:
- **Step 1**: notebook-callable whole-brain prescreening
- **Step 2**: Identity Assessment
- **Step 3**: CLS A-F, result packaging, and reporting scaffolding

More concretely:
- `src/bridge/prescreen` provides the Step 1 notebook-callable prescreening layer
- `src/bridge/identity` provides the Step 2 package layer
- `src/bridge/cls` provides the Step 3 scoring layer
- `src/bridge/io` supports artifact packaging and `src/bridge/workflows` retains config helpers

The public repository is intended to present BRIDGE as software:
- installable from GitHub
- usable through notebook-first Python APIs
- supported by public templates that can guide notebook parameters
- documented as a workflow package for external readers and coding agents

## Executable Entrypoints

BRIDGE v1 exposes Step1-Step3 as notebook-callable APIs:
- `from bridge.prescreen import prescreen`
- `from bridge.identity import identity_assessment`
- `from bridge.cls import Step3Context, component_A, component_B, component_C, component_D, component_E, component_F, step3`

The current execution model centers on:
- Step 1 as notebook-callable whole-brain prescreening API
- Step 2 as notebook-callable target identity assessment API
- Step 3 as component-first notebook-callable CLS and report API

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
- `dataset.id` is the canonical run-level identifier for Step 3 outputs
- `dataset.prefix` is the canonical naming prefix for Step 2 artifacts
- `paths` are resolved relative to the YAML file location
- `identity` records the target class and Step2 artifact conventions used by downstream Step3/report code
- `cls` defines enabled Step 3 components and component-specific settings
- `report` defines summary output filenames and optional CLS weights

Multi-run report generation is a roadmap item after the single-dataset notebook path is polished.

## Step 1 Status

Step 1 is the upstream reference-building layer in the BRIDGE architecture.

In thesis terms, Step 1 corresponds to:
- reference atlas construction
- integration of embryonic brain data into a biologically grounded reference space
- whole-brain pre-screening before target-specific evaluation

In repository terms, Step 1 prescreening is represented by `src/bridge/prescreen`; upstream reference construction remains model-building context.

## Step 2 Status

Step 2 is the formal **Identity Assessment** layer. Its role is to identify high-confidence target candidates under a more specific reference.

The current formal Step 2 package includes:
- query model loading
- prediction and probability handling
- calibration
- uncertainty estimation
- entropy-based and threshold-based candidate selection

## Step 3 Status

Step 3 is the formal **concordance scoring and reporting** layer. Its role is to evaluate how well the selected in vitro candidates reconstruct the intended in vivo developmental program.

The current formal Step 3 package includes:
- component-first CLS A-F notebook APIs
- shared result packaging
- summary CSV and manifest JSON generation
- visualization placeholders tracked in the roadmap

In the current phase, the report layer consumes both:
- Step 2 artifacts such as thresholds JSON and candidate-bearing Step 2 h5ad outputs
- Step 3 component JSON outputs

This means reporting now spans thesis Step 2 outputs plus Step 3 outputs rather than only listing CLS component scores.

The public validation surface is smoke-oriented and package-oriented. Full scientific validation can be maintained in deployment or development environments.

## Why the Distinction Matters

The repository intentionally distinguishes:
- the **full conceptual BRIDGE pipeline**
- the **subset of that pipeline already formalized in public package code**

This keeps the repository aligned with the thesis logic while making the released software surface easy to identify.
