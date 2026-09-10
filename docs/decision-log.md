# Decision Log

## 2026-09-07: Separate P0-05 Counts From Assignment Mass

The approved P0-05 hard_count_accounting input mode consumes the existing
producer V3 count partition without requiring a caller-authored mass bundle.
Consensus-supported role counts and non-consensus reconciliation buckets remain
separate. A zero supported count cannot establish biological absence. Soft mass,
open-set assessment and rare-state detection remain unavailable/not assessed.

A distinct versioned profile and package result union preserve existing profile
contracts. The count-only mode does not run soft-composition figures, bootstrap
inference or detection calibration. Required manifest/receipt bindings establish
execution ownership correspondence, not independently verified biological units.
The branch plan tracks implementation and validation; this decision does not
claim a completed genuine-data chain or scientific release.


## 2026-09-07: Bind P0-06 Observations To Producer Artifacts

The approved ProcessMethodInput v0.2 replaces caller-repeated state rows with a
checksummed descriptor of the existing P0-02 evidence table and same-run artifact
manifest. Source conflict remains unresolved; no winning identity, probability
or biological unknown state is invented. Whole-product summaries retain every
selected observation. Conditioned summaries use only uniquely supported states
that match externally declared ProgramSpec rules.

The existing v0.1 input remains unchanged. Exact artifact correspondence is not
authentication of an arbitrary fabricated bundle; deployment registration owns
that trust boundary. No new source catalog or signature framework is introduced.
This follows [AnnData observation identity](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.obs_names.html)
and explicit entity/derivation binding in [W3C PROV-DM](https://www.w3.org/TR/prov-dm/)
without adopting a separate platform stack. Implementation and validation remain
tracked in the branch plan, independently of scientific readiness.


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

## 2026-08-28: Separate Visualization Evidence From Rendering

BRIDGE uses a standalone `VisualizationArtifact` v0.2 contract to bind typed,
checksummed figure data, evidence semantics, provenance, public interactions,
accessible fallbacks and deterministic renders. Scientific tools remain the
owners of values and evidence states; future Web renderers may select and
present those records but cannot recompute or promote them.

Current P0-01/P0-02 runs retain byte-compatible v0.1 artifacts. Their seven
registered components remain `legacy_untyped` until component-specific PRs
provide typed data, table/text fallbacks and renderer validation.

## 2026-09-04: Keep The Local Runtime Explicit And Content-Bound

The local single-worker core records workflow transitions as append-only
`RunEvent` facts and derives current state through a deterministic projection.
Each executable step is bound to an exact request, checksum, Tool Package
contract, output-directory identity and typed approval receipt. Attempt-specific
claims fence stale workers, and completion is accepted only with a validated
`ToolRun` receipt.

The planner creates upload-QC requests and accepts explicitly materialized
downstream requests. It does not encode a universal P0 dependency graph or
construct missing scientific inputs. The upload envelope remains distinct from
the scientific `ProductCase` contract. Workflow success describes execution
only and does not change evidence state, scientific readiness or release status.
Model-provider integration, distributed execution and authentication remain
outside this core.

## 2026-09-05: Keep The First Web Preview Bounded

The private Web preview adds conversation, uploaded-file intake and explicit
approval around the existing input-QC planner and local workflow. It does not
construct the scientific contracts required for every downstream P0 package.
Browser results are registered tool-owned artifacts, not model-generated
measurements. Numerical results and raw matrices are excluded from provider
context by default.

Deployment trust for an administrator-owned shared ancestor is explicit,
startup-only and pinned to its path, owner and filesystem identity. Default
private-path ownership checks remain strict; trust does not propagate to
descendants or relax symlink, permission or replacement checks. This is a
single-operator deployment boundary, not a multi-tenant authorization model.

## 2026-09-07: Permit Explicitly Opted-in Aggregate Interpretation

The owner approved sending field-allowlisted aggregate analysis summaries to the
configured model for research interpretation. Raw expression matrices,
observation-level records, sample/source identities, private paths, credentials
and private provenance hashes remain local. The default deployment remains
status-only; the opt-in is startup-owned, not a model or HTTP permission.

Summary values must come from verified canonical tool artifacts and preserve
counts, denominators, evidence states and uncertainty. A private per-turn binding
retains their exact provenance. An interpretation is not a verified report,
scientific validation or public-export approval. Aggregate results remain
controlled biological data even after identifiers are removed. Public-safe
acceptance evidence is retained in the
[Web validation history](validation/web_preview_20260905.md); private provenance
receipts remain outside the repository.

## 2026-09-08: Bound Product-intent Sharing To Scientific-input Drafts

The owner approved the configured model receiving three explicitly confirmed
product-intent fields for scientific-input candidate drafting: `product_family`,
`target_cell_type` and `target_stage`. This is a purpose-specific authorization,
not permission to send the whole intake form or to expand ordinary conversation
context. Product names, sampling and independence information, sample/source
identities, metadata columns, raw expression, paths and private provenance remain
outside this new authorization. Existing aggregate-summary consent is separate.

Draft, stale, retracted or unconfirmed values must not be promoted to confirmed
intent. Any candidate remains reviewable and source-backed; confirmation is not
scientific freezing, biological validation or public-export approval. The current
runtime still sends intake readiness only. Implementation and public-safe
acceptance evidence for the draft-specific
projection remain in the [Web validation history](validation/web_preview_20260905.md)
and Git history.


## 2026-09-09: Metadata-First Experimental Intake

The owner approved reading uploaded obs/var/uns metadata before asking research
users repetitive questions, and using uploaded differentiation protocols to
produce editable, source-cited experimental drafts. A dedicated configured-model
purpose may receive bounded semantic metadata and protocol passages. It does not
inherit general access to matrices, observation rows, sample/capture identities,
private paths, credentials or provenance hashes.

Direct metadata and source-backed model interpretation remain distinguishable.
Known sample-scoped culture days are preserved without claiming independent
replicates. Starting cells and sequencing methods use experimental language;
internal product categories and routine matrix-processing questions are not the
initial interview. Remaining questions appear one at a time with Other last,
no unknown choice, and persistent private answers. Missing facts remain missing.

User confirmation and tool approval remain separate gates. Prescribed protocol
steps are not attested execution, annotations are not intended target identity,
and file structure/integer values are not raw-count provenance. This increment
changes intake, not the scientific measurement contracts or release criteria.

## 2026-09-09: Separate Descriptive Expression Measurement From Product Assessment

The owner approved a bounded exploratory P0-06 route before product-state,
role and biological-independence review is complete. Its versioned input binds
the selected expression view and exact candidate S/G2M resource. It measures
relative program expression and predicted phases only; it cannot manufacture
reviewed product objects, an independence attestation or gate-facing evidence.

The new result union retains the old product-profile schema and adds a distinct
exploratory profile with pending state review, unknown independence, null
independent n and unavailable domain scoring. Original product modes retain
their scientific and attestation requirements. A common matrix and gene
programs define shared evidence, not independent validation by multiple methods.
No division-rate, quiescence, stress, purity, acceptance or release conclusion
follows from these descriptive measurements. No new data-sharing permission or
public-export approval is implied. Exact public-safe evidence is retained in the
[P0-06 validation record](validation/p0_06_proliferation_stress_response.md);
private execution receipts remain outside the repository.


## 2026-09-09: Derive Protocol Code And Source Spans From One Fragment Sequence

The owner approved replacing the model's separate full-program and source-map
outputs after real generation/repair failures. Ordered source-backed body
fragments are now the sole proposed code source. BRIDGE assembles a fixed
protocol wrapper, physical line spans and any compatibility occurrence fields.
A syntax repair replaces named existing fragments and atomically regenerates the
program; the initial readable statements, sources, questions and order remain
unchanged. Option-only repair cannot edit successfully compiled code.

Historical versions, user edits and source passages remain unchanged. This
eliminates independently authored code/map copies, not semantic uncertainty:
literal checks and passage accounting are not entailment, experimental execution
or biological validation. Bounded raw responses remain private. Public-safe
installed model/browser
evidence is retained in the [Web validation history](validation/web_preview_20260905.md)
and construction chronology remains in Git.

## 2026-09-09: Permit Add-only Repair Of Missing Protocol Citations

The owner approved appending missing existing source IDs to an unchanged step.
Original source passages are authoritative; an initial model citation omission
must not become an immutable error. Prior citations and their order remain,
as do step IDs/order, readable operations, parameters, questions and exclusions.
A source-only repair cannot change BPL, including after successful compilation.
Unknown/duplicate additions and the existing per-step reference limit are checked,
then all source accounting and literal-support checks run again. The server
reports the unsupported numeric value and owning step, but does not guess its
supporting passage. This repairs provenance indexing, not experimental semantics
or human review. Installed actual-model acceptance remains a separate gate.

## 2026-09-09: Review Unparsed Wait Information Separately From Compilation

The owner authorized fixing a real-model omission before merging: the model
preserved an unspecified wait as a string but returned no question. Source
accounting and an empty question list cannot establish sufficient information.
For unparsed wait durations with no outstanding question, require a separate
source review within the existing three-request budget. Its closed response
may append a source-backed question or identify a verbatim cited duration/end
condition. Existing source text, operations, parameters, questions and compiled
code remain unchanged. Each resolution binds its owning step and exact
server-supplied diagnostic line and column, not every wait in a multi-operation
fragment or on one physical line. Compiler warnings retain those distinct calls.
Unknown/duplicate targets and unsupported excerpts are rejected; missing review
is not a completed representation.

Compiler inability to parse `8 days` does not mean that the original source omits
the duration. Explicit unsure remains unresolved without another automatic
question. This bounded model review and its private audit are not human approval,
complete semantic verification, experimental execution or a scientific claim.

## 2026-09-10: Keep One Workflow Contract And Separate Approved Targets From Current Evidence

The owner approved PRD section 6 as the single maintained product-workflow
contract. The first six intake-to-QC steps, including source-bound protocol
review, retain their already accepted scope. The downstream graph-driven
feedback loop, internally selected and user-confirmed comparison cohort, and
qualified report/export are approved target behavior, not claims about current
end-to-end capability.

The target coordinator queries evidence, maintains a small set of competing
hypotheses and chooses discriminating registered high-level tools. Tools remain
authoritative for values, denominators, thresholds, states, versions and
Evidence IDs. The default target reference is one reviewed, internally aligned
multi-source system with applicability and source/version traceability; current
candidate references are not thereby scientifically frozen.

Public documentation records stable contracts and public-safe validation
evidence. Private runtime records and operational deployment state remain
outside GitHub. Completed construction diaries may leave the active tree only
after unique facts, unresolved scientific work and exact validation records are
preserved; retirement does not upgrade scientific status.
