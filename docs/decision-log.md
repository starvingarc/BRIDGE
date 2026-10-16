# Decision Log

## 2026-09-11: Separate Developer Scientific Decisions From Legacy Signatures

The approved Step 7–10 design treats scientific definition review as development
work backed by explicit source evidence and method validation. A new versioned
policy replaces fixed two-role signatures as a development prerequisite; it
does not fabricate reviewer identities, mark historical pending records approved,
or remove checksum, source-isolation, independent-validation or per-state release
requirements. Legacy signed contracts remain readable with their original rules.
The implementation and validation of the replacement are tracked in the
[mainline plan](../plans/step7-evidence-coordinator.md).

The first VM/mDA product scope includes lineage-supported progenitors and early
neuroblasts. Identity, product role and developmental compatibility are separate
axes: a historical neuroblast label alone establishes none of them, and culture
day does not establish fetal age. Scientific qualification, clinical suitability
and domain scores are not granted by this scope decision.

Reports are layered: a claim-verified, explicitly bounded research report may
precede full scientific qualification. The initial download is private offline
Chinese HTML with data attachments, not public HTML export or PDF. Results,
statements and corrections bind immutable analysis versions and original tool
receipts. Existing runtime approvals remain explicit; no merge, publication or
deployment follows from this development decision.

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

Field-allowlisted aggregate analysis summaries may be sent to the
configured model for opted-in research interpretation. Raw expression matrices,
observation-level records, sample/source identities, private paths, credentials
and private provenance hashes remain local. The default deployment remains
status-only; the opt-in is startup-owned, not a model or HTTP permission.

Summary values must come from verified canonical tool artifacts and preserve
counts, denominators, evidence states and uncertainty. A private per-turn binding
retains their exact provenance. An interpretation is not a verified report,
scientific validation or public-export approval. Aggregate results remain
controlled biological data even after identifiers are removed. Public-safe
acceptance evidence is retained in the
[Web validation history](https://github.com/starvingarc/BRIDGE/blob/d3d69363c50541fb34320f703db2995edb27105e/docs/validation/web_preview_20260905.md); private provenance
receipts remain outside the repository.

## 2026-09-08: Bound Product-intent Sharing To Scientific-input Drafts

Scientific-input candidate drafting may send the configured model three explicitly
confirmed product-intent fields: `product_family`,
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
projection remain in the [Web validation history](https://github.com/starvingarc/BRIDGE/blob/d3d69363c50541fb34320f703db2995edb27105e/docs/validation/web_preview_20260905.md)
and Git history.


## 2026-09-09: Metadata-First Experimental Intake

Experimental intake reads uploaded obs/var/uns metadata first and uses uploaded
differentiation protocols to produce editable, source-cited experimental drafts. A dedicated configured-model
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

A bounded exploratory process-assessment route is available before product-state,
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

Separate full-program and source-map outputs were replaced after observed
generation and repair failures. Ordered source-backed body
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
evidence is retained in the [Web validation history](https://github.com/starvingarc/BRIDGE/blob/d3d69363c50541fb34320f703db2995edb27105e/docs/validation/web_preview_20260905.md)
and construction chronology remains in Git.

## 2026-09-09: Permit Add-only Repair Of Missing Protocol Citations

Missing existing source IDs may be appended to an otherwise unchanged step.
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

An observed model output preserved an unspecified wait as a string but returned
no question. Source
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

PRD section 6 is the single maintained product-workflow contract. The first six intake-to-QC steps, including source-bound protocol
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

## 2026-09-11: Separate Assessment Display, Provider Projection And Scope Authority

The scope coordinator admits only reconstructed registered requests inside the
exact approved question, upload, fact/resource bindings and finite limits.
Candidate preparation exposes actual blocking prerequisites and separate
interpretation gaps before approval without running tools/models or changing
scientific facts. This is execution authority, not source-state, product-role,
window, program, biological-unit, score or release approval.

The researcher-facing portrait preserves independent assessment axes, exact
values/denominators, canonical missingness and local source/version drilldown.
All seven process families stay explicit. The exploratory S/G2M route covers
cell cycle only; no family is inferred from an arbitrary program name.
Pending fact review differs from a confirmed historical binding; existing
receipts and stop reasons remain intact and recomputation needs a fresh scope.

The provider context is independently rebuilt from allowed aggregate fields
with opaque per-turn aliases. Private fingerprints, receipt/artifact hashes,
plan identities, dependency bindings and local links stay local; validated
citations resolve back to canonical evidence. Existing request reconstruction
and deduplication remain unchanged.

The browser tree is named `frontend/`; the Python package stays
`src/bridge/web/`. Contributor/document lifecycle requirements are consolidated
in AGENTS, preserving scientific contracts and dated validation records.
[Step 7 validation](validation/step7_evidence_coordinator_20260911.md) separates
observed engineering checks from unverified real-input and scientific gates.

## 2026-09-11 — External method observations and evidence admission v0.2

Method selection, graph admission and scientific qualification are separate.
Verified outputs from authorized query runs, including external methods, are
admissible as attributed research observations with native semantics and shared
source dependencies. Public method metadata is retrievable for planning and
explanation. This supersedes the blanket graph exclusion in the original
CapybaraBrain task card; sealed inputs remain isolated. Neither catalog presence
nor graph admission establishes execution, independent validation, training or
calibration permission, or product qualification. Frozen historical runs retain
their original policies and are not relabeled.

## 2026-09-23 — Technical-view evidence without invented biological independence

A selected RNA view may support descriptive measurements even when independent
biological units are unknown. MeasurementSpec v0.3 therefore binds an exact
DataViewBinding, a whole-view technical aggregate, unknown independence and null
independent replicate count; its status cannot become frozen. Existing v0.1/v0.2
models and schemas remain unchanged. MeasurementResultV2 is reused.

Saved P003 coefficients enter the normal evidence chain only through an explicit
source-checked projection with original producer, artifact and input/reference
hashes. It does not rerun matrices or alter the original native result. New P006
exploratory output uses the honest unit; old receipts and five native values are
preserved without silent rebinding. P008 adds a versioned receipt accepting the
new spec; its gate/profile/summary semantics and P009 scientific admission
policy do not change. Shared RNA remains one dependent family. No product-role,
developmental-window, threshold, formal score or clinical claim is authorized.

## 2026-09-23 — Explicit source-defined program coverage

P006 adds a versioned source-bound exploratory input and result union while
preserving prior cycle contracts and native values. Exact resource bytes and
selected membership are bound before native Scanpy/ULM execution. The input must
choose complete-only or observed-subset coverage; the latter is authorized only
for clearly labeled candidate descriptions with full missing/actual gene lists.
Ambiguous identifiers and insufficient executable membership remain unavailable.
No activation, product-quality or safety threshold is introduced. This decision
does not freeze a ProgramSpec, developmental window or ScoreContract. The current
product context is midbrain dopaminergic progenitor/precursor research, not a
requirement for mature dopaminergic expression or absence of cycling cells.


## 2026-10-08 — Bind proposed interpretations and input coverage to their evidence

The evidence-bound extension in PR #55 keeps model-authored support, limitation,
contradiction and missing-evidence relations as unverified propositions. Every
relation names a supplied citation, rationale and applicability. Interpretation
v1.2 and report context/snapshot v0.5 preserve the graph identity, explanation
version and input revision; later evidence cannot silently qualify an earlier
explanation. User-visible interpretation graphs and report disclosures consume
those bindings. Missing graph binding and real-model/report acceptance remain
open review gates; this decision does not assert that the extension is released.

Input coverage is exact membership on the confirmed feature axis, not expression,
cell identity or biological absence. Only allowlisted membership facts and their
semantics reach the model; private upload hashes, input revisions and matrix/column
paths remain local. Nonempty stored queries require a coverage snapshot, while
incomplete checks retain explicit unknown states. Raw measurements and historical
artifacts are not rewritten by review or repair.

Review reasons may use up to 1,200 characters; a longer explanation still has to
satisfy the same citation and semantic checks. Narrow consistency reviews use low
reasoning effort only for the supported DeepSeek model family at the official
endpoint. Generation, repair and other gateways retain their existing effort.
Unavailable or invalid review results block admission; lower effort is not weaker
acceptance. Continuation of an unresolved draft requires new explicit approval
and matching source/draft/non-budget bindings, without resetting prior usage.

P0-06 0.11.1 separates a scientific input fingerprint from execution-attempt
identity and binds native candidate definitions to their observed coverage. This
prevents a repeated request from overwriting the identity of an earlier outcome;
it does not change the measurement formulas or establish scientific qualification.
The [version-bound record](validation/interpretation_evidence_20261008.md) defines
what was checked and the remaining literature, reader and scientific gates.


## 2026-10-08 — Block publication of unbound interpretation drafts

A reviewed explanation with evidence relations or feature queries must bind a
unique verified current evidence graph before a new v1.2 version is published.
If that binding is unavailable or ambiguous, retain the private draft and expose
`interpretation_graph_binding_unavailable`; do not save an explanation that the
report would subsequently hide. Historical explanation objects keep their
existing schemas. Native report sources continue matching the graph's exact
producer receipt; same-name historical executions remain skippable, while missing
current sources block the report with an explicit diagnostic.


## 2026-10-08 — Share the research-report read limit

The evidence view reads verified P0-10 research reports with the existing 8 MB
report-reader limit. Ordinary graph records retain their 2 MB limit. A real
2.33 MB report exposed the mismatch; stream-limit regressions and actual browser
inspection verify the bounded change. The saved-case extension passed scoped
model/report/download/browser/restart acceptance; broader literature, human-reader
and scientific qualification gates remain independent.


## 2026-10-12 — Adopt the BRIDGE product direction

The product owner approved the direction recorded in the
[BRIDGE product design](../plans/bridge-product-design.md). BRIDGE is the
application section of the ventral-midbrain atlas paper and is first an internal
laboratory tool. Research workspaces stay user-defined containers whose typed
objects (protocols, samples, datasets, assessments, comparisons, plans) drive a
culture-wall home, a 3D developmental tree built from the atlas and a protocol
score that links reagent windows to the differentiation chain.

Analysis gains an exploratory tier: with user consent the Agent may install or
write tools in an isolated sandbox. Exploratory results remain labelled and do
not enter formal assessment conclusions; registered tools remain the formal tier.
Shared memory requires user confirmation. Neither tier nor memory may change
references, thresholds or measurement definitions.

Quantitative assessment is introduced as a versioned, atlas-anchored chain of
conditional fractions (pluripotency exit, neural induction, midbrain positioning,
floor-plate specification, DA fate; graft-only DA subtype), displayed as radar
and funnel views. Their product, the target-cell fraction, is the only summary
number; weighted totals and traffic-light grades remain prohibited. Boost/Boost+
and RC17 become comparison objects only, still excluded from training,
calibration and references.

This entry records an approved direction. The existing AGENTS, PRD and product
principles remain in force until the implementing changes update them; nothing
here is implemented, validated or deployed.


## 2026-10-12 — Treat the differentiation chain as raw measurement and split ownership

The [research objects](../plans/research-objects.md) contract defines protocols, runs,
samples, atlas assessments, leads and confirmation actions for milestone M1. The
differentiation chain is five conditional fractions with numerators and denominators
and their product; it is versioned raw measurement, not a `domain_score`, so the
existing score rules stay unchanged. PRD 6.6 now allows ring, radar and funnel views
of these fractions while still prohibiting weighted totals, ranking and traffic-light
grades. Boost/Boost+ and RC17 enter the comparison queue as comparison objects only.
Frontend and backend write scopes are recorded in that contract.

## 2026-10-13 — Map fast first and fix the chain-v1 demo rules

The query encoder behind the current developmental tree cannot be recovered, so
standard mapping starts with a fast v0 (Scanpy ingest, nearest reference neighbours,
tree position taken from those neighbours) labelled with its method and reference
versions, while a projectable reference model is retrained to replace it. Pre-graft
samples use the scRNA reference only; post-graft samples use the snRNA reference.

The chain-v1 demo rules are operational and versioned: level 1 counts the CNS neural
lineage including glia and excludes neural crest and perivascular-like cells; level 3
counts the candidate floor-plate lineage from current labels, shown as candidate and
paired with marker colouring on the tree; level 0 waits for a calibration that needs
pluripotent positive controls; level 4 shows DA programme evidence until fate
probabilities are recomputed with a DA terminal state. The single headline number
switches by stage: candidate floor-plate lineage fraction for progenitor-stage
products, DA fraction for Stage IV and post-graft samples. Details are in
[BRIDGE product design](../plans/bridge-product-design.md) §§3.4, 6.1–6.2 and 7.
Nothing here is implemented, calibrated or scientifically validated yet.

## 2026-10-13 — Build along the user journey and accept on preset public protocols

Workbench functions are now ordered by the path a wet-lab user takes, from protocol
entry to post-graft outcome, and each is finished before the next starts. A function
counts as done only when it runs on real data for three preset public protocols
(GSE204796, Boost/Boost+ from E-MTAB-14729, STEM-PD D16 from GSE200610), seeded into
an ordinary research of a demonstration account through the public interfaces. The
workbench becomes the single path: QC, evidence graphs and reports move in from the
conversation workspace. The old five-domain score is no longer shown and there is no
weighted total; the differentiation chain with ring, radar and funnel views is the
quantitative assessment. A run on the developmental tree is drawn as a flow along the
tree's own branches instead of a path through the weighted centre of its labels.
The order and acceptance are in [User journey and roadmap](../plans/user-journey.md).

## 2026-10-14 — Open experiments on their protocol flow, with sampling points and a sample panel

The product owner chose a wet-lab path through the workbench: an incubator card
opens straight onto its protocol flow; samples sit as points under the flow's
day axis and open a side panel with the sample's analyses (mapping, QC and
records). The developmental tree is the visualisation of the mapping analysis,
shown small in the panel and full size on demand, not the frame of a run's
results; the all-runs tree moves under comparison. QC charts are redrawn in the
browser from the per-cell table, keeping the tool's figures as originals. The
UI no longer says "round": cards are titled by protocol, version and, for a
repeated run, cell line and start date; confirming a protocol will record the
experiment in a follow-up change. Registration order of analyses is shown as
order, never as adoption. Details: [user journey](../plans/user-journey.md) ②.

## 2026-10-14 — Track workbench functions by journey stage on GitHub

The workbench roadmap is organised by the order a wet-lab researcher works:
A prepare protocols, B record experiments, C read one sample, D compare,
E explain and draft the next version, F reports and outputs, G after
grafting, and X platform and acceptance. `plans/user-journey.md` is the
single source for each function's status, issue and order; GitHub has one
milestone per stage and a `roadmap` label on each function issue, with a
pinned overview issue whose task lists update as issues close. The overall
project stages remain in `docs/ROADMAP.md`. The product owner also chose
the left rail (research switcher; incubator, comparison and materials; an
experiment list) and to generate and read reports where they arise, on the
experiment and comparison pages, rather than in the rail. Superseded issues
#126, #127 and #136 were closed with their replacements named, and the
delivered #134 and #135 were closed.

## 2026-10-15 — Doublets inside QC, cell cycle as its own sample tab

Scrublet doublet candidates are shown inside the QC tab, only when the
assessment produced candidates: count and share (a small non-zero share
reads "<0.1%", never 0) and the score distribution with candidates coloured.
A threshold belongs to one capture, so it is drawn only when the sample is a
single capture, together with Scrublet's simulated doublet score outline;
several captures are listed with their own thresholds. Cell-cycle scoring is
a separate tab that appears once a scoring is registered: the S or G2/M
share, phase counts, the sample's own UMAP (from the cell atlas analysis,
joined by observation id) coloured by phase or either score with hover
readouts, and the per-cell S × G2/M scatter, whose axes cover the middle
99% of cells with the rest drawn on the edge as hollow points. At the
product owner's request the sample tabs carry little explanatory text: no
reading guide, no per-cell table preview or not-assessed list, and the
library-complexity scatter is removed; downloads sit in the footer. The
data declaration gains an optional capture question; an unknown capture
sends nothing and doublets are simply not assessed. Details:
[user journey](../plans/user-journey.md) ③a.

## 2026-10-15 — Demo protocols open as confirmed protocol flows

The public demo research shows four papers as five dishes: Xu/Chen, Boost,
Boost+ (a labelled second version of Boost), STEM-PD and SphereDiff. Each
protocol is curated from its paper's Methods into the factors that drive
differentiation, with doses and day windows; base media, coatings and
dissociation enzymes stay off the flow. The versions are confirmed, so a
card opens straight on its flow. Dose steps of one factor share a lane.
Gaps in the sources stay blank: STEM-PD days 16–18 and the SphereDiff
recipe. Details: [user journey](../plans/user-journey.md) §2.

## 2026-10-15 — Signing in opens the incubator

After signing in, the workbench opens the incubator of the research used
last in this browser, or else the most recently updated one, so the
protocol dishes are the first thing seen. The research list is no longer
a landing page that draws researches as dishes; it is reached from the
rail's 所有研究 until a navigation page is designed. A user without any
research still sees the list's empty state. The synthetic deployment
test research is to be removed from the demo account.

## 2026-10-15 — The original text opens on demand

Opening a protocol shows only its flow. The original document opens beside
it from a reagent's details (在原文中查看, scrolled to that reagent) or from
the review checklist of a draft (打开原文), is read the first time it is
opened, and closes again with 收起. The source-review item of a draft can
still be ticked only after the text has been shown.

## 2026-10-15 — Doublets and the cell cycle belong to QC

The sample panel keeps three tabs (mapping, QC, records). QC always has a
doublet section: the Scrublet result when there is one, otherwise the
reason; a sample declared without a capture batch can add it there, which
runs its standard analysis again through the sample workflow and keeps the
earlier results in the records. The cell cycle, with the sample's UMAP and
the S × G2/M scatter, is a section of QC rather than a tab of its own.

## 2026-10-15 — Several batches on one day

Samples of the same day are that day's batches and share one marker on
the day axis (D18 ×2). It opens on all batches side by side: one QC table,
count, gene and mitochondrial distributions drawn per batch as shares of
its own cells, and cell-cycle phases and mapping per batch; a switcher
opens one batch's usual panel. Batches are analysed separately and are not
merged here; a merged UMAP needs batch integration and belongs with the
multi-time-point view (#186). Each public demo file is declared as one
capture, named by its accession, so doublets are detected per capture.
