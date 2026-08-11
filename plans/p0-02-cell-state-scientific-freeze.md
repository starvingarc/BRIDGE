# P0-02 Cell-State Scientific Freeze

| Field | Value |
|---|---|
| Branch | `codex/bridge-scientific-freeze` |
| Mode | `auto` |
| Status | `in_progress` |
| Owner | BRIDGE core |

## Goal

Promote the scRNA Cell-State Evidence baseline only after biological review,
source-aware benchmarking and calibrated abstention. Keep snRNA and unvalidated
states shadow-only.

## Scope

- Version biological review cards for all L1 states and seven priority L2 states.
- Add deterministic pilot and locked split contracts with source-family isolation.
- Benchmark registered method outputs through one science-team CLI.
- Propose, review and sign freeze gates before locked data can be opened.
- Make runtime release selection depend on an approved immutable release manifest.

## Non-goals

- P0-03 execution, Target Identity or Regional Fidelity conclusions.
- Clinical efficacy, safety, potency, release or product-ranking claims.
- Automatic scientific approval, fabricated reviewer signatures or locked-test tuning.
- Formal snRNA release or L2 external-validation claims.

## Tasks

- [x] Freeze contracts, review-card drafts and release-policy invariants.
- [x] Implement split preparation, method adapters, benchmark metrics and summaries.
- [x] Add Conda environment contracts and cross-language exchange validation.
- [x] Run the local engineering gates.
- [ ] Run a development-only bridge-amax pilot.
- [ ] Produce an unsigned FreezeGateSpec proposal and review the full change.

## Current verification

- Local Python 3.12 suite: `126 passed, 3 warnings`.
- Registry: exactly 12 Tool Packages; P0-01 and P0-02 implemented, P0-03 through P0-12 scaffold-only.
- Knowledge validation: 354 methods, 385 verified public Source Cards and no dangling references.
- Repository policy scan and `git diff --check` pass after ignored runtime/deployment directories are excluded from the public-tree scan.
- A clean wheel install exposes all 12 Tool Packages, keeps `bridge-benchmark --help` usable without optional scientific imports, and loads the packaged pilot spec when installed with the `freeze` extra.
- The R adapter parses successfully in the pinned bridge-amax Bioconductor environment.

These checks validate the current engineering contracts. They do not replace the pending bridge-amax pilot, biological review, freeze-gate approval or locked test.

## Acceptance

- Pilot splits operate at source/donor level and never open locked or sealed assets.
- scConform accepts only independent calibration rows and probability outputs.
- Per-state release is explicit; L2 cannot exceed `provisional_frozen`.
- Runtime refuses frozen execution without signed review, gate and release records.
- Repeated runs with the same spec, environment and inputs are content-stable.
- Locked-test execution remains blocked until human approval is recorded.
