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
- documentation that explains how Step 1 fits into the full architecture

## Code Organization Principles

- `src/bridge/identity` maps to formal Step 2 logic.
- `src/bridge/cls` maps to formal Step 3 logic.
- `src/bridge/io` and `src/bridge/workflows` host output handling and orchestration.
- notebooks must not carry core business logic.
- `.claude/skills` provides repository-local coding-agent guidance.

Interpretation rule:
- Step 1 lives in `docs/` as upstream architecture and interface roadmap.
- Step 2 and Step 3 evolve as public package modules because they already have stable code structure.

## What May Enter the Formal Codebase

Allowed content includes:
- standardized APIs
- configuration-driven parameters
- documented output contracts
- testable modules
- stable wrappers around query loading, scoring, serialization, and reporting

## Companion Materials

Keep the following outside the formal package until they have stable contracts:
- `drafts`-style exploratory notebooks
- thesis-only plotting scripts
- provisional analysis fragments
- unpublished ad hoc code awaiting documentation and verification

## Contribution Rules

When adding new work:
1. First classify it as either formal workflow code or exploratory extension.
2. If it belongs to the formal workflow, place it in `src/bridge`.
3. If it is exploratory, document it outside the formal package first.
4. Move notebook logic into core modules after defining stable interfaces.

## Output and Naming Rules

- Keep output contracts explicit and documented.
- Prefer stable directory and file naming over notebook-local conventions.
- Commit model binaries when they are intentionally part of a release-artifact strategy.
- Public repository terminology should remain consistent with the three-step BRIDGE workflow.

## Thesis-to-Code Alignment

The repository should remain legible to a reader who comes from the thesis:
- Step 1 in the thesis corresponds to reference construction and whole-brain pre-screening and is documented as interface roadmap work.
- Step 2 in the thesis corresponds to the `identity` package.
- Step 3 in the thesis corresponds to the `cls` package plus shared output and workflow layers.

If a new implementation choice changes the thesis-to-code mapping, document the mapping explicitly.

## Migration Rules

- Step 1 can be promoted into the formal repository only after method, interfaces, and outputs are stabilized.
- Experimental materials can be migrated only after standardization, documentation, and testability are established.
- Public repository structure takes precedence over preserving the layout of earlier research drafts.
