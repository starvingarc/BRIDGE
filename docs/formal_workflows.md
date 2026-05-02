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
- `src/bridge/io` and `src/bridge/workflows` support packaging and workflow organization

The public repository is intended to present BRIDGE as software:
- installable from GitHub
- usable through a CLI
- configured through public templates
- documented as a workflow package for external readers and coding agents

## Executable Entrypoints

BRIDGE v1 exposes workflow-level commands rather than component-level CLI commands:
- `bridge identity run --config <yaml>`
- `bridge cls run --config <yaml>`
- `bridge report summarize --config <yaml>`
- `bridge report summarize-batch --config-list <yaml>`

The current execution model centers on:
- Step 1 as notebook-callable whole-brain prescreening API
- Step 2 as a formal workflow
- Step 3 as a formal workflow and reporting layer

## Configuration Contract

BRIDGE v1 uses a single YAML file per run. The top-level sections are:
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
- `identity` defines the Step 2 candidate-selection logic
- `cls` defines enabled Step 3 components and component-specific settings
- `report` defines summary output filenames and optional CLS weights

For multi-run analyses, BRIDGE also supports config-list driven report generation through `bridge report summarize-batch`.

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
- CLS component A-F
- shared result packaging
- serialization scaffolding
- reporting and visualization scaffolding

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
