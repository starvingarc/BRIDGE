# Decision Log

## 2026-08-10: Rebuild The Active Package

The historical Step1-Step3 implementation remains available through Git history. BRIDGE uses new high-level Tool Package contracts and has no compatibility requirement with historical score or report APIs.

## 2026-08-10: Separate Scientific Tools From Agent Infrastructure

BRIDGE owns deterministic scientific modules, contracts, environments, artifacts, visualizations and knowledge semantics. The collaborating Agent team owns orchestration, Web, job management and model-provider integration. The first boundary is Python plus JSON CLI; HTTP and MCP adapters are future integration work.

## 2026-08-10: No Current P0 Domain Scores

The PRD's 0-100 language is a future design target. No current `ScoreContract` is frozen, so active tools must emit `domain_score=null`. Raw evidence can still be sufficient for interpretation.

## 2026-08-10: Versioned Local Knowledge

Curated registry rows, overrides and source-verification records are the rebuild inputs. Runtime retrieval uses one deterministic packaged snapshot; only the active P0 method shortlist is expanded as Markdown. Formal runs cannot depend on live Web results.

## 2026-08-10: First Executable Package

P0-01 supports declared h5ad and 10x inputs at `analysis_ready`, `count_ready` and contract-only `droplet_ready`. Droplet-specific cell calling and ambient correction remain conditional and are not executed in the first vertical slice.

## 2026-08-11: Cell-State Promotion Is Per State

P0-02 biological review and release occur per state. Review cards, a signed pre-locked `FreezeGateSpec`, locked-test evidence and a signed `CellStateReleaseManifest` are all required before runtime promotion. L2 cannot exceed `provisional_frozen`; snRNA remains shadow in the first release. Locked and sealed competitor assets have zero data flow during pilot development.

## 2026-08-11: Cell-State Freeze Is Content-Bound And Fail-Closed

Benchmark, split, MeasurementSpec, reference, environment, adapter source and asset-catalog identities are checksum-bound. Source-family and transitive derivative overlap is rejected across development, OOD, locked and sealed roles. scConform remains a calibration layer whose base probabilities and prediction sets are independently recomputed. Pilot evidence can only propose unsigned gates; locked execution remains disabled until the biological review and gate are signed.

## 2026-08-11: Full-Cell SingleR Is Not A Pilot Runtime

The full-cell SingleR configuration produced no complete L1 output within the 3,600-second development budget. Its partial L2 output is excluded. Any future aggregated-reference configuration must be registered and benchmarked as a new method version.

## 2026-08-11: The Rebuilt BRIDGE Replaces The Legacy Mainline

The rebuilt BRIDGE is the canonical product rather than a separately branded parallel line. It replaces the historical implementation through a topic-branch Pull Request targeting `main`; after integration, all new work branches from `main`. Opening or updating a PR never authorizes an automatic merge.

## 2026-08-12: Use Proliferation & Stress Response As The P0-06 Working Name

P0-06 uses `Proliferation & Stress Response` as its working display name instead of `Process Integrity`. The new name identifies a stage-conditioned transcriptional-program assessment built on upstream cell-state and composition evidence, and avoids implying manufacturing-process, GMP or release integrity. P0-06 does not reassign cell identity or recompute off-target composition.

This naming change does not alter the scientific scope or release state: `TranscriptomicReviewFlag` remains `shadow`, `domain_score` remains `null`, and no clinical safety, tumorigenicity, potency or product-release conclusion is introduced. Stable identifiers `P0-06` and `TASK-PROCESS-v0.1` remain unchanged. Historical `source_ref` paths retain their original filenames so provenance links are not rewritten.
