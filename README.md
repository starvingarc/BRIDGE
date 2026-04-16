# BRIDGE

**Brain-Referenced In vivo-to-in vitro Developmental Guidance and Evaluation**

BRIDGE is a three-step brain-referenced framework for guiding and evaluating in vitro cell products against in vivo developmental programs.

## Project Summary

BRIDGE is organized around a thesis-derived three-step workflow:
- **Step 1**: construct the in vivo developmental reference and the whole-brain pre-screening space
- **Step 2**: perform target-specific identity assessment and candidate selection
- **Step 3**: quantify developmental concordance with CLS and generate downstream reports

The public repository currently formalizes **Step 2** and **Step 3** as package code. **Step 1** is part of the intended architecture and is documented as roadmap material, but it is not yet released here as a finalized production workflow.

## What BRIDGE Is Trying to Do

The framework is designed for settings where an in vitro sample, such as an organoid-derived or stem-cell-derived product, needs to be evaluated relative to an in vivo developmental reference rather than by a small set of marker genes alone.

The overall logic is:
1. Build a biologically grounded in vivo reference space.
2. Map a query sample into that reference and identify high-confidence target candidates.
3. Score how well those candidates reconstruct the relevant developmental program across multiple complementary dimensions.

## Pipeline Overview

### Step 1: Reference Construction and Whole-Brain Pre-screening

Step 1 defines the reference coordinate system that anchors the rest of the framework. In the thesis logic, this step is intended to include:
- integration of human embryonic brain single-cell data into a reference atlas
- construction of region-aware and stage-aware reference spaces
- whole-brain pre-screening to estimate broad lineage composition and identify obvious off-target populations before more specific evaluation

In this public repository, Step 1 is acknowledged as part of the full BRIDGE pipeline, but it is not yet formalized as released code.

### Step 2: Identity Assessment

Step 2 refines target candidates under a more specific reference. In the current codebase, this step includes:
- query model loading
- soft prediction
- probability calibration
- ensemble-based uncertainty estimation
- normalized entropy calculation
- candidate selection through thresholded identity-stability rules

The formal Step 2 code lives under `src/bridge/identity`.

### Step 3: CLS and Reporting

Step 3 evaluates how well the selected in vitro candidates reconstruct the in vivo developmental program. In the current codebase, this step includes:
- CLS component A-F
- shared result packaging and serialization
- report and visualization scaffolding
- output conventions for cross-sample comparison

The formal Step 3 code lives primarily under `src/bridge/cls`, with supporting pieces under `src/bridge/io` and `src/bridge/workflows`.

## Key Concepts

### Reference

In BRIDGE, the **reference** is the in vivo developmental coordinate system used to interpret a query sample. It is not just a label table. It is intended to encode developmental context, regional identity, and the embedding space used for mapping and comparison.

### Query

The **query** is the in vitro sample being evaluated, such as a differentiation product, organoid dataset, or related cell product that is projected into the reference framework.

### Identity Assessment

**Identity Assessment** is the Step 2 module that decides which query cells should be treated as high-confidence candidates for downstream evaluation. In the current implementation, this relies on calibrated probabilities, uncertainty estimates, and entropy-based filtering rather than on a top-label assignment alone.

### CLS

**CLS** stands for **Composite Likeness Score**. It is the Step 3 concordance layer that summarizes how well an in vitro sample reconstructs the in vivo developmental program after candidate selection.

In the current codebase, CLS is decomposed into six components:
- **A**: identity consistency
- **B**: pseudo-bulk expression similarity
- **C**: classifier transferability
- **D**: embedding neighborhood consistency
- **E**: pseudotime concordance
- **F**: regulatory network similarity

CLS should be read as a structured multi-component evaluation framework, not as a claim that one scalar alone fully captures developmental quality.

## Thesis-to-Code Mapping

The repository is intentionally aligned to the thesis logic:
- **Step 1** thesis logic: documented in `docs/`, not yet formalized as released package code
- **Step 2** thesis logic: implemented in `src/bridge/identity`
- **Step 3** thesis logic: implemented in `src/bridge/cls`, with shared I/O and workflow scaffolding

Supporting documentation:
- `docs/formal_workflows.md`
- `docs/thesis_to_code.md`
- `docs/roadmap_step1.md`
- `docs/experimental_scope.md`

## What Is In Scope for BRIDGE v1

The following are part of the formal BRIDGE v1 repository:
- `src/bridge/identity`: Step 2 identity assessment logic
- `src/bridge/cls`: Step 3 CLS A-F logic
- `src/bridge/io` and `src/bridge/workflows`: output handling and workflow scaffolding
- `tests/`: formal tests for the released package modules
- `configs/`: configuration placeholders and output conventions
- `docs/`: workflow, roadmap, and scope documentation

## What Is Not In Scope for the Initial Public Repository

The following are intentionally kept out of the first public version:
- exploratory notebooks from the earlier `drafts/` workspace
- thesis-generation materials and manuscript assets
- one-off plotting scripts
- unpublished ad hoc analyses
- large model binaries and unpublished intermediate datasets

These materials may be migrated later, but only after standardization, documentation, and testability are established.

## Repository Layout

```text
BRIDGE/
|- README.md
|- CLAUDE.md
|- pyproject.toml
|- src/bridge/
|- tests/
|- configs/
|- models/
|- notebooks/
|- docs/
`- .claude/
   `- skills/
```

Directory meanings:
- `src/bridge/`: formal Python package
- `tests/`: formal test suite
- `configs/`: configuration templates and output naming conventions
- `models/`: model metadata and loading notes, not large weights
- `notebooks/`: formal notebook entrypoints and placeholders only
- `docs/`: workflow notes, concept definitions, roadmap, and scope boundaries
- `.claude/skills/`: repository-local AI collaboration guidance

## Quick Start

```bash
pip install -e .[test]
pytest -q
```

At the current stage, BRIDGE v1 should be treated as a structured public skeleton for Step 2 and Step 3 rather than as a fully packaged end-user release of the entire three-step pipeline.

## Executable Workflows

BRIDGE v1 currently exposes workflow-level execution commands for the released parts of the pipeline:

```bash
bridge identity run --config configs/bridge.minimal.yaml --dry-run
bridge cls run --config configs/bridge.minimal.yaml --dry-run
bridge report summarize --config tests/data/report_fixture.yaml
bridge report summarize-batch --config-list <config-list.yaml>
```

Command mapping:
- `bridge identity run`: Step 2 workflow
- `bridge cls run`: Step 3 scoring workflow
- `bridge report summarize`: Step 2 + Step 3 per-dataset summary/report packaging
- `bridge report summarize-batch`: Step 2 + Step 3 multi-dataset summary packaging

Configuration is provided through a single YAML file per run. The formal configuration contract is documented in `docs/formal_workflows.md`, and example templates are provided under `configs/`.

In the current phase, the report layer is not just a CLS-only summary. It targets:
- Step 2 identity-assessment outputs
- Step 3 CLS outputs
- per-dataset and cross-dataset structured report summaries

## Roadmap

- **v1**: formalize Step 2 and Step 3 under a stable public package structure
- **future**: formalize Step 1, complete the end-to-end three-step pipeline, and migrate selected standardized extensions

## Current Limitations

- Step 1 reference construction is still documented as planned work rather than released code.
- The public repository currently emphasizes formal package structure over exploratory notebook history.
- Models are documented through interfaces and metadata, not distributed as large binary assets.
- Some package code is still transitioning from a research-code structure to a long-lived public-repository structure.
