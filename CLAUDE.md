# CLAUDE.md

## Project Positioning

BRIDGE is a formal repository for the parts of the workflow that are stable enough to be versioned, documented, and tested.

The intended end-to-end BRIDGE pipeline has three steps:
- **Step 1**: reference construction and whole-brain pre-screening
- **Step 2**: identity assessment and candidate selection
- **Step 3**: CLS-based concordance scoring, reporting, and visualization

Current repository scope for **v1**:
- formal package code for Step 2
- formal package code for Step 3
- documentation that explains how Step 1 fits into the full architecture without presenting it as already released production logic

## Code Organization Principles

- `src/bridge/identity` maps to formal Step 2 logic.
- `src/bridge/cls` maps to formal Step 3 logic.
- `src/bridge/io` and `src/bridge/workflows` host output handling and orchestration.
- notebooks must not carry core business logic.

Interpretation rule:
- Step 1 may be documented in `docs/`, but it must not be advertised as implemented production code unless formalized.
- Step 2 and Step 3 may continue to evolve as public package modules because they already have stable code structure.

## What May Enter the Formal Codebase

Allowed content includes:
- standardized APIs
- configuration-driven parameters
- documented output contracts
- testable modules
- stable wrappers around query loading, scoring, serialization, and reporting

## What Must Stay Out for Now

Do not place the following directly into the formal package until standardized:
- `drafts`-style exploratory notebooks
- thesis-only plotting scripts
- provisional analysis fragments without stable I/O contracts
- unpublished ad hoc code that has not been documented or tested

## Contribution Rules

When adding new work:
1. First classify it as either formal workflow code or exploratory extension.
2. If it belongs to the formal workflow, place it in `src/bridge`.
3. If it is exploratory, document it outside the formal package first.
4. Do not move notebook logic into core modules without defining stable interfaces.

## Output and Naming Rules

- Keep output contracts explicit and documented.
- Prefer stable directory and file naming over notebook-local conventions.
- Model binaries should not be committed unless they are intentionally part of a release-artifact strategy.
- Public repository terminology should remain consistent with the three-step BRIDGE workflow.

## Thesis-to-Code Alignment

The repository should remain legible to a reader who comes from the thesis:
- Step 1 in the thesis corresponds to reference construction and whole-brain pre-screening and is currently documented as future formalization work.
- Step 2 in the thesis corresponds to the `identity` package.
- Step 3 in the thesis corresponds to the `cls` package plus shared output and workflow layers.

If a new implementation choice makes the thesis-to-code mapping less clear, document the mapping explicitly instead of relying on internal context.

## Migration Rules

- Step 1 can be promoted into the formal repository only after method, interfaces, and outputs are stabilized.
- Experimental materials can be migrated only after standardization, documentation, and testability are established.
- Public repository structure takes precedence over preserving the layout of earlier research drafts.
