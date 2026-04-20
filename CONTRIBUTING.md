# Contributing to BRIDGE

Thanks for your interest in BRIDGE.

## Before contributing

Please read:
- `README.md`
- `CLAUDE.md`
- `docs/formal_workflows.md`
- `docs/thesis_to_code.md`

## Contribution principles

- Preserve the Step 1 / Step 2 / Step 3 boundary.
- Treat Step 2 as the identity workflow layer.
- Treat Step 3 as the CLS + reporting layer.
- Do not move exploratory notebook logic directly into `src/bridge`.
- Prefer small, reviewable changes with explicit motivation.

## Code contributions

When contributing code:
- keep public CLI behavior stable unless there is a strong reason to change it
- preserve stable output contracts where possible
- document public-facing behavior changes in docs
- avoid expanding scientific scope casually

## Issues and pull requests

- open an issue for bugs, usability problems, or feature proposals
- keep pull requests focused
- explain whether a change affects:
  - package surface
  - workflow behavior
  - config contract
  - output schema

## Sensitive material

Do not contribute:
- private infrastructure details
- real dataset-specific runtime configs
- internal logs
- unpublished sensitive data artifacts
