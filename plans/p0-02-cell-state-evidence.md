# P0-02 Cell-State Evidence

| Field | Value |
|---|---|
| Branch | `v2-tool-packages` |
| Mode | `auto` |
| Status | `complete` |
| Owner | BRIDGE core |

## Goal

Deliver a source-aware, auditable Cell-State Evidence baseline and a biology-first README.

## Scope

- Build immutable scRNA/snRNA reference snapshots from scientist-owned asset catalogs.
- Run source-specific pseudobulk support and independent marker/program evidence.
- Preserve hierarchical labels, source disagreement, gene coverage and provenance.
- Emit shadow evidence and visual artifacts through the existing Tool Runtime.

## Non-goals

- Formal cell labels, OOD thresholds, domain scores or product rankings.
- Reuse of competitor references, markers, thresholds or models.
- P0-03 implementation or Agent/Web engineering.

## Tasks

- [x] Audit reference assets, labels and runtime contracts.
- [x] Add public contracts, MeasurementSpecs and reference build/validate commands.
- [x] Implement P0-02 execution and visual artifacts.
- [x] Add source-aware, hierarchy and failure-path tests.
- [x] Rewrite README and verify its biological workflow figure.
- [x] Run local and bridge-amax validation.

## Acceptance

- P0-02 supports declared scRNA and snRNA inputs that passed P0-01.
- Reference sources remain separately visible and never receive cell-count weighting.
- Query source family is explicit and matching reference profiles are held out.
- L1 runs on all observations; L2 is conditional; L3 remains shadow-only.
- Every result keeps `domain_score=null` and `score_state=shadow/unavailable`.
- Missing references, low gene coverage and unresolved labels cannot become negative evidence.
