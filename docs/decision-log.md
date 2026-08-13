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
## 2026-08-12: Birtele Is A Source-Level Holdout With Provisional Groups

The project scientific lead conditionally approved processed `GSE192405` for source-level external holdout, stage-level description and provisional-group sensitivity. Publication totals reconstruct the primary 6-week, 8-week and 11-week analysis groups; Table S1 constrains cultured samples, but `GSM5746439` and conflicting `GSM5746445` remain ambiguous between the 7.3-week single-3D and 8-week four-condition groups. These groups do not establish verified donor identities: formal `biological_unit_id` values remain null, biological-replicate estimation remains prohibited, and this decision does not promote any method, state, threshold or product role.

## 2026-08-13: Version Structured Tool Inputs Without Replacing V0.1

Current P0-01 and P0-02 execution remains on the byte-compatible v0.1 request, run and package schemas. Structured cross-tool inputs use separate v0.2 request, run and package contracts plus `StructuredInputRef` v0.1. Structured objects are referenced by absolute local path, object version, schema and SHA-256; inline payloads are forbidden.

The adapter seam is declared by each implemented v0.2 Tool Package and is restricted to packaged `bridge.tool_packages.*` modules. The registry validates strict structured JSON inputs and their hashes before adapter calls and verifies hashes after every adapter outcome, including exceptions and invalid return types. Versioned schemas bind top-level `object_version` or `version`; legacy registered schemas without either property retain external `object_version` metadata compatibility so current `QCReadinessProfile` and `MeasurementResult` objects remain usable by later modules. Successful and partial runs require a non-null result validated against the package's registered result schema, with request, version, implementation and environment bindings preserved. This avoids adding central tool-ID dispatch branches as future packages become executable. At this interface decision point P0-08 and P0-09 remained scaffolds; no biological finding or product-evaluation claim followed from the runtime contract itself.

## 2026-08-13: P0-08 Gates Raw-Evidence Sufficiency Without Scoring

P0-08 is an executable deterministic candidate that consumes only immutable, versioned upstream evidence objects. It evaluates Data Readiness, Model Robustness and Prior Applicability independently for each P0 domain, then applies the registered `not_assessed` → `insufficient` → `limited` → `sufficient` precedence. Exact same-family records may be collapsed for influence while retaining provenance; conflicting required records in one family force review rather than a vote.

This engineering implementation does not validate any real ProductCase or upstream scientific conclusion. A contract-valid evidence gap yields `not_assessed`, and every output keeps `domain_score=null` and `score_state=unavailable`. P0-08 emits neither a `MeasurementResult` nor a product pass/fail, safety, potency, efficacy, GMP-release or clinical claim. The candidate gate resource, proposed environment and selected formal-ineligible method records require separate review before any scientific promotion.

## 2026-08-13: P0-09 Uses Append-Only JSON And Parquet Evidence Graphs

P0-09 treats normalized JSON fact sets and fixed-column Parquet node/edge tables as the authoritative Evidence Graph representation. NetworkX reconstructs and validates that representation and serves seven bounded in-process read-only queries; it is not the persistent source of truth. LadybugDB remains a deferred, reconstructable shadow adapter and is not a candidate-release dependency.

An unchanged logical record is idempotent. Changed content appends a new version through an explicit `supersedes` or `invalidates` relation and never overwrites history. Missing evidence creates an `EvidenceRequirement`, not a numeric zero. Shadow and exploratory inputs remain auditable but cannot be promoted to formal evidence. A malformed top-level contract fails without publication; independently invalid sibling records are excluded and recorded by ID/index/digest in a partial bundle without returning raw rejected payloads.

This is an engineering evidence-compilation candidate, not a Claim verifier or scientific release. It emits no domain score, product pass/fail, safety, potency, efficacy, GMP-release, clinical or absolute-ranking conclusion. Evidence Family assignments, Claims, reconciliation rules and any real ProductCase interpretation still require separate scientific review.
