# Web Scientific-input Construction Design

Status: owner-approved written design, including conversational choice questions,
on 2026-09-08. Implementation follows Tasks 21–25 in the existing activity plan;
completion and installation require their recorded evidence.
The downstream candidate-rules v0.1 appendix was subsequently approved as an
implementation basis by the owner on 2026-09-08, with PRD-led user/developer
walkthroughs required. This does not approve scientific source review or execution.
This design belongs to the existing `web-full-chain-integration` workstream.
It is not a scientific release or a statement that the downstream chain has run.

## Goal and acceptance

A researcher uploads a differentiation-product dataset, confirms ordinary product
and sample facts, reviews source-backed scientific-input candidates, approves
analysis, and receives tool-owned evidence followed by a checked report in Web.
The operator must not author internal JSON, run biological methods outside BRIDGE,
or preload manufactured measurements to make the journey appear complete.

The immediate acceptance case is the owner-approved author-published GSE204796
D28 count matrix. Its existing Web QC and cell-state runs remain immutable.
The current result is candidate reference correspondence, not product purity,
validated identity, potency, safety, or an independently validated score.

Completion has two separate meanings: the user journey reaches a report with
explicit missingness; a scientific stage is completed only if its actual registered
tool ran with eligible, genuine inputs. A report containing unmet requirements
must never be described as a fully executed or scientifically validated chain.

## Verified cause

1. `src/bridge/web/provider.py` exposes only reply, input review, basic-intake
   drafting, QC preparation and analysis preparation. Its guidance explicitly
   prohibits authoring formal scientific objects.
2. `Service.think` sends only confirmed/unconfirmed status and missing field names
   from private intake. The separately approved three-field product-intent
   projection has not been implemented.
3. `Intake.prepare` handles QC and cell-state only. `Inputs` can register,
   validate and select supplied objects, but cannot construct them.
4. The current D28 run emits a V2 cell-state profile. V3 requires the QC producer's
   typed biological-unit lineage, which was not supplied. The conversation
   projector recognizes V3 only, so real V2 figures exist without an interpretable
   model summary. This is not missing reference configuration.
5. P0-03/P0-04 require V3 profiles and typed lineage. P0-05 hard-count accounting
   and P0-06 source-bound method execution additionally require an explicit
   biological-unit attestation. Basic intake confirmation is not that attestation.

## Chosen approach

Extend the existing private registration, exact-confirmation, planner and executor
flow. Do not create a second analysis engine, generic workflow framework, automatic
paper reader, or alternative scientific contracts.

The alternative of only exposing V2 summaries repairs interpretation but leaves
the downstream journey unimplemented. Arbitrary model-authored JSON would cross
the ownership boundary for measurements, identities and review authority.
Use constrained semantic candidates plus deterministic local construction.

## Input ownership and model boundary

- Model: proposes product roles and an expected developmental-window candidate
  from confirmed intent and the configured versioned local knowledge. Each
  proposed scientific choice identifies supporting local source entries and
  explains limitations. Unsupported choices remain unresolved.
- Local application: owns object IDs, versions, hashes, file bindings, references,
  revision checks, canonical producer selection and schema validation.
- Researcher: confirms product intent, source/sample/capture relationships and
  scientific choices. Unknown independence or pooling remains unknown.
- Tool: owns computed values, denominators, uncertainty, eligibility, evidence
  states, thresholds and scoring. A model response never becomes a measurement.

Only product_family, target_cell_type and target_stage may be projected from
confirmed private intake, and only for a scientific-draft request. Ordinary chat
keeps the current privacy boundary. Product names, sources, sample identities,
metadata columns, independence details, raw expression, paths and private hashes
are not added to model context. Aggregate interpretation retains its separate
existing opt-in. Stale or unconfirmed intent is excluded.

## Candidate and confirmation lifecycle

Add a private ScientificInputDraft bound to the exact upload checksum, intake
signature, input revision, reference versions and source knowledge snapshot.
Its review surface separates stated facts, proposed scientific choices, required
unknowns, affected stages and provenance. It contains no release claims.

A draft is not executable input. Editing the upload declaration, confirmed intent,
selected reference or a depended-on result makes it stale. Confirmation uses the
existing exact-digest/revision controls and records the precise candidate accepted.
Confirmation does not execute tools. Execution still needs an AnalysisPlan approval.

Materialize validated objects only after confirmation, then register and select
them through existing Inputs operations. Construct all objects before publishing
the new selection. Fail closed on stale references, bad schemas, mismatched
checksums or missing required roles. Preserve prior object versions and ToolRuns.
Do not copy scientific values from example fixtures into genuine cases.

Biological-unit attestation is a separate explicit confirmation of its four
existing statements: observation mapping, pooling/multiplexing handling, analysis
unit for the estimand, and independence grouping. Defaults remain not_confirmed.
No actor is impersonated, and an intake count or a generic confirm click cannot
generate a confirmed attestation or reviewed/frozen lineage.

## Conversational choice questions

The owner requested choice-based clarification inside the conversation, similar
in interaction style to coding assistants. This is part of the scientific-input
journey, not a separate wizard or an additional scientific tool.

- Add a constrained ask_user_input action. It proposes one card with one question
  by default, or at most three directly related questions. The application owns
  question IDs, allowed answer bindings and the exact pending revision.
- Each question uses ordinary language, explains why the answer matters, and
  offers two to four concise choices with optional one-sentence consequences.
  Use single selection for mutually exclusive answers and multiple selection
  only when several choices can genuinely apply together.
- Keep a free-text alternative and optional supplementary text. Questions about
  unknown facts include an explicit unknown/not sure answer. Unknown is exclusive
  of substantive choices; absence of an answer is not interpreted as no.
- Recommendations need a stated basis. Do not preselect biological facts,
  independence, pooling, raw-count semantics or attestations. A recommendation,
  focus state or selected option never submits itself; the user submits explicitly.
- Render cards inline with the relevant assistant turn. On submission, retain a
  readable answer summary and a way to revise it. Refresh restores pending and
  answered states. Support keyboard operation and the existing mobile layout.
- Ask only for a missing decision that changes construction or eligibility.
  Reuse valid confirmed answers. An unknown answer records missingness and its
  consequence; it does not trigger the same question again on every turn or
  block unrelated eligible work. Re-ask only when a depended-on fact changes or
  the user asks to revise the answer.

A response updates the pending draft through existing validated controls. It
does not confirm every scientific object, attest biological independence, approve
a plan or authorize export. Show consequential changes in the final draft review.
Free text is a candidate statement, never code, a path binding, a measurement or
a substitute for required provenance.

Persist private question/answer records with session identity, question digest,
input revision and relevant dependency references. Reject stale, cross-session,
unknown-option and duplicate conflicting submissions; identical retries are
idempotent. Revision affects only dependent mutable drafts and approvals, never
historical ToolRuns. Cancelling a question grants no default choice or authority.

The card and its answer summary are private Web records, not an automatic model
history entry. Bind answers to allowlisted semantic fields; server-owned field
templates supply private metadata choices without exposing them to the model.
The model receives only permitted status/missingness and, for the approved draft
purpose, the three confirmed product-intent fields. Do not leak private answers
through a readable transcript echo, option labels, errors or supplementary text.
This feature adds no model-sharing permission.

## Stage construction boundaries

| Stage | Construction and execution contract |
|---|---|
| QC / cell-state | Reuse exact valid receipts. Construct declared lineage only from confirmed true relationships. Changed inputs require an explicit new version and new approval; never retrofit an old receipt or relabel V2 as V3. |
| Target / regional | Draft ProductCase, ProductDefinitionCard, StateRoleMap, TargetRegionalAssessmentSpec and applicable MeasurementSpec; bind exact QC, V3 profile, assignment, manifest, vocabulary and reference. Aggregation does not need a normalized expression asset. |
| Development | Add an explicitly reviewed DevelopmentWindowSpec and DevelopmentStateMap. D28 is a culture-time fact, not a fetal-age equivalence. Do not invent a time series from one time point. |
| Off-target | Use the existing hard_count_accounting route only with its genuine V3, lineage and attestation prerequisites. Do not convert hard counts or unresolved support to projection probabilities. |
| Proliferation / stress | Use method_runtime_source_bound with the original declared counts when supported, exact source-observation artifacts and explicit process/program specifications. Do not normalize outside a registered tool or manufacture a program-evidence bundle. |
| Sufficiency / graph | Construct DomainGateInput and compilation inputs from actual canonical outputs and unresolved requirements, using package-owned policies. Missing input or unrun stages remain explicit missing observations, not synthetic MeasurementResults. |
| Report / export | Build evidence-bound ReportDraft claims and exact value bindings, call P0-10, then require distinct export approval before P0-11. Export only the existing allowlisted report artifacts. |

ToolRegistry.describe_input and each adapter remain authoritative for mode IDs,
required roles, schema versions and actual eligibility. An unsupported or
ineligible stage stays blocked with a plain-language reason and affected outputs.
Unchanged scientific contracts are not weakened to force the D28 case through.
Comparison and graft-expression are independent branches and need genuine inputs.

## Existing V2 result interpretation

Add a separately identified V2 projection after verifying its canonical ToolRun,
artifact checksum, tool identity and immutable upload binding. Use only validated,
bounded aggregate composition and reconciliation records with explicit original
denominators and candidate state. Preserve unassessed calibration and open-set
status. Omit unrecognized labels or invalid shapes by failing closed, not by
silently substituting zeros. It must not imply V3 lineage, readiness for P0-03,
reviewed identity, or that QC filtering occurred.

## Implementation boundaries

- `src/bridge/web/scientific_inputs.py`: constrained private draft, source
  validation, deterministic construction and stage binding; no biological methods.
- `provider.py`: draft-purpose and clarification actions with bounded semantic
  response contracts; preserve both configured action transports.
- `control.py`, `app.py`, `intake.py`, `inputs.py`: integrate exact review,
  API lifecycle, roadmap and existing validated registration; retain one path.
- `evidence.py`: verified V2 aggregate interpretation without V3 promotion.
- `web/src/components/ScientificInputs.tsx` and `ClarificationCard.tsx`, existing
  conversation/intake/result/runtime components, `api.ts` and `types.ts`:
  inline choice questions, answer history, ordinary-language draft review,
  distinct attestations, stale states, blocked stages and result navigation.
- `src/bridge/web/report_inputs.py`: deterministic evidence/claim input assembly
  for the existing P0-08–P0-11 tools; not a replacement report verifier.
- Focused tests in `tests/test_web_scientific_inputs.py` and existing Web tests;
  corresponding browser component tests. Stable documentation changes only when
  runtime behavior has actually been implemented and verified.

## Verification and stop conditions

Test the observed seams once per change: purpose-specific privacy; unsupported
candidate/source rejection; exact confirmation and stale replay rejection;
unknown independence; attestation not_confirmed; canonical producer/hash binding;
V2 interpretation without V3 promotion; real tool-plan approval; report value
binding and distinct export approval. Cover single/multiple/free-text/unknown
answers, no automatic submission, stale and duplicate response handling, refresh,
keyboard/mobile interaction, no repeated answered questions and private-answer
exclusion from model history in both action transports. Engineering fixtures
prove contracts only.

Then exercise the genuine case through ordinary Web upload, conversation,
confirmation, plan approval and tool-result navigation. Do not repeat completed
QC or broad review suites just to restate stability. Run another scientific
analysis only for an explicitly changed genuine input or an actual failed run.

All application code, tests, builds, inputs and run artifacts remain on the
designated server. Preserve live services, original inputs and historical cases.
Install into an isolated acceptance runtime before changing a running preview.
Do not merge PRs, publish data, freeze science, alter access policies, or create
new interpretation thresholds under this implementation authorization.

If no source-backed candidate or required biological fact exists, stop that
affected stage, explain the exact missing decision, and retain the partial
evidence. This feature must not promise that author-published data alone supplies
every scientific assessment or experimental-design prerequisite.

## Downstream candidate rules v0.1

**Status:** owner-approved implementation basis, still a scientific candidate.
Researched on 2026-09-08 against source revision `f7c59301`, written at `34c3276d`,
and subsequently approved with a requirement to work from and update the PRD.
Approval authorizes bounded construction, not scientific freeze or execution
without eligible genuine inputs and separate analysis approval. It extends this
workstream only.

### Decision and scope

Recommend a descriptive candidate report with explicit unresolved requirements.
The alternatives are (a) wait for full scientific qualification before any report,
which postpones useful partial evidence, or (b) treat candidate labels as established
identity, which the current sources cannot support. Adopt neither as the default.
Candidate construction, scientific review, genuine experimental-fact confirmation,
analysis approval and export approval remain distinct actions.

The first scope is one pre-transplant hPSC-derived midbrain dopaminergic progenitor
preparation, scRNA-seq, with the declared D28 culture time. It is not a universal
rule for other protocols, fetal ages, mature-neuron products or graft samples.
No efficacy, safety, malignancy, potency, release, ranking or calibrated score is
defined. Numerical rules below are explicitly proposed accounting/completeness
policies, not literature-validated biological cutoffs.

### Source ledger and evidence limits

- **S1 — Xu et al., JCI 2022:** [original study](https://www.jci.org/articles/view/156768).
  The in-vitro time course distinguishes regional progenitors and mDA differentiation.
  LMX1A/FOXA2/EN1/OTX2 coexpression and stage-dependent CLSTN2/PTPRO are informative
  in that study; single markers are not universal identity tests. CLSTN2 peaks
  earlier, while PTPRO emerges before the later progenitor stage and loses
  specificity at the terminal stage. Use Figures 1, 4 and 5 and their discussion
  for candidate rationale, not imported thresholds or current-product outcomes.
  GSE204796 belongs to this study: using its discovered markers on this case is
  same-study exploration, not independent validation. Graft outcomes stay separate.
- **S2 — Kirkeby et al., Cell Stem Cell 2017:** [study record](https://pubmed.ncbi.nlm.nih.gov/28094017/)
  and [author-institution full text](https://orca.cardiff.ac.uk/id/eprint/99434/1/1-s2.0-S1934590916302983-main%20%281%29.pdf).
  Across more than 30 grafted batches, common progenitor-marker expression did
  not reliably predict dopaminergic yield; caudal-midbrain-associated markers
  correlated with outcome. The protocol and animal-graft endpoint differ from
  the current D28 assay. This is external biological context, not validation of
  this sample or permission to tune pre-transplant scoring against graft results.
- **S3 — Kee et al., Cell Stem Cell 2017:** [original abstract](https://pubmed.ncbi.nlm.nih.gov/28094018/).
  Mouse Lmx1a-positive progenitor profiling resolves closely related dopamine and
  subthalamic lineages with shared markers. This supports demanding discriminating
  state evidence; it does not transfer a mouse classifier to this human product.
- **S4 — van den Brink et al., Nature Methods 2017:**
  [original publication](https://www.nature.com/articles/nmeth.4437).
  Dissociation-induced transcription is a processing-confound rationale, not an
  mDA-specific stress calibration or a toxicity threshold. Only the accessible
  publication record was used; no complete stress signature was extracted.
- **S5 — Seurat cell-cycle resource:** [2019-symbol resource definition](https://satijalab.org/seurat/reference/cc.genes.updated.2019.html)
  and [official scoring description](https://satijalab.org/seurat/articles/cell_cycle_vignette.html).
  These specify separate S and G2M gene sets and a relative scoring procedure,
  not measured division rate or malignancy. At initial design they nominated a
  resource for later curation; the 2026-09-09 checkpoint below now records the
  owner-selected exact updated lists and hashes as a non-executable candidate.
- **C1 — current local state source:** P0-02
  `resources/biological_review_draft.yaml`,
  `resources/product_context_review_draft.yaml` and annotation vocabulary.
  The seven RG/Nb regional states remain under review. Some boundaries derive
  from historical label transfer/manual cluster mapping; several Nb states lack
  saved state-specific marker review. Literature cannot silently repair that lineage.
- **C2 — current deterministic contracts:** shared configurable objects and
  P0-03–P0-06/P0-08–P0-11 package models, adapters and reconciliation/report policy.
  They own numeric definitions, required inputs and states. Live literature is
  candidate curation only; execution must use a reviewed, versioned local snapshot.

The following rules are BRIDGE design inferences from S1–S5 and C1–C2. Source
agreement is not a claim that these exact rules were tested in those publications.

### R1 — keep product identity, anatomy and development separate

Review the complete source-state definition, anatomical scope, distinguishing
positive/negative evidence, confusion states and source provenance before assigning
a product role. A gene missing from sparse scRNA-seq is not a negative marker.
Do not create a new per-cell classifier, majority-marker vote or expression cutoff
in the Web layer. The current state labels and their original support/conflict
records remain immutable.

| Existing source states | Candidate hypothesis to review | Current executable disposition |
|---|---|---|
| L1 Radial_Glia / Neuroblast | Broad developmental classes, not exclusive mDA identity | No whole-class target assignment |
| L2 RG_mFP | Floor-plate-associated progenitor: a target-related hypothesis | `role_unresolved` until source-state and product-role review |
| L2 Nb_mFP | Floor-plate-associated neuroblast: lineage-related transitional hypothesis | `role_unresolved`; not automatically target or acceptable adjacent |
| L2 RG_mBMP / RG_mBIP / Nb_mBMP / Nb_mBIP / Nb_mAP | Anatomical alternatives requiring discriminant review | `role_unresolved`; neither automatic acceptable adjacency nor confirmed off-target |
| Any remaining state | Use its exact reviewed definition, not its display-name resemblance | Unresolved unless an explicit reviewed mapping exists |

A mature dopaminergic-neuron state can be lineage-related while later than a
progenitor product's intended window. Do not count it as a progenitor merely
because it expresses dopamine-associated markers. Likewise a caudal/MHB-associated
marker is not, alone, a universal off-target rule (S1–S3).

Proposed P0-03 accounting, only after the necessary state review:
use L2 source-specific views and the existing consensus-supported view separately.
The narrow floor-plate-associated regional hypothesis uses RG_mFP and Nb_mFP as
its numerator and the seven listed RG/Nb regional states as its conditional
denominator. The whole-product counterpart uses those same two states over the
entire exact selected DataView. This is a proposed floor-plate-associated support
fraction, not total ventral-midbrain fidelity or mDA purity. Numerator/denominator
state lists must be recorded in an exact reviewed specification before execution;
no observed percentages are used to choose them.

Target-identity accounting uses only reviewed `target` roles; do not add
`acceptable_adjacent` to that numerator. Keep role-unresolved, conflicting,
unavailable and excluded observations visible with the original whole-view
denominator. Do not pool L1/L2/L3 counts or source views into extra observations.
A zero conditional denominator yields no fraction, not zero.

### R2 — expected window is a reviewed product choice, not inferred age

Propose reviewing a window spanning specified floor-plate progenitors through
early lineage-related neuroblasts. Whether that transitional endpoint belongs in
the intended product is a product-definition choice, not a fact inferred from D28.
Until it is accepted and each relevant state is reviewed, stage assignments remain
`unresolved`; an RG/Nb label alone does not become `within_window`.

After review, assign each state exactly one existing role: earlier, within_window,
later, branch_shift or unresolved. Use a stage-role map separate from the product
role map. A documented alternative lineage can be branch_shift; unknown identity
cannot. Record the permitted target-related subset explicitly. Preserve both
whole-product and target-related denominators in P0-04.

CLSTN2/PTPRO are candidate temporal context, not binary early/late switches.
D28 stays a culture-time fact: no fetal-week conversion, calibrated developmental
clock, maturation percentage, progression rate or single-point time series.

### R3 — off-target evidence is count accounting, not absence certification

Use P0-05 `hard_count_accounting` only with genuine QC/V3 profile,
source assignment, biological-unit lineage and the separately confirmed existing
four-statement attestation. Unknown relationships stay unknown; labels do not
establish replicate independence.

Count `known_off_target` only for explicitly reviewed product-role assignments.
Keep all other observations in their true unresolved/support categories and the
whole-view accounting. The complementary fraction of candidate target support is
not the off-target fraction. No hard-count-to-probability conversion.

Without validated detectability, a zero count means only no such assignments in
the selected observations. Do not emit absence, LOD-qualified negative, an upper
confidence bound, or product safety. Supplied OOD/calibration channels stay
unassessed when absent; no new rare-state detection cutoff is proposed in v0.1.

### R4 — first program candidate is descriptive cell cycle; stress stays open

Nominate S5's complete, version-pinned S/G2M lists for
`PROC-CYCLE-SCANPY` and `PROC-CYCLE-AGG` in the existing
`method_runtime_source_bound` route. Do not execute Seurat or normalize data
outside BRIDGE. Later curation must bind exact list contents, source/license,
symbol mapping, resource revision and computed content hash before a ProgramSpec
can be materialized. Do not fill those fields with placeholder references.

Propose `minimum_gene_coverage=1.0` for both lists in this first candidate.
This is a conservative full-feature availability check, not a validated assay
threshold: absence of any required matrix feature makes the program unassessed,
whereas measured zero counts for a present feature remain observations. Do not
relax coverage after seeing this case without a new reviewed version.

Start with `whole_product` only. Current source-bound observation inputs are L1,
so they cannot support new L2-conditioned summaries. Retain every declared
observation, including unresolved cell identity; state-specific work requires
separately eligible genuine source states. Preserve method identity, actual S/G2M
scores, phase counts, coverage and normalization provenance. G1 assignment is not
proof of quiescence, and cycling expression is not malignancy.

No new stress gene set, weights, reference envelope or alert threshold is approved
or fabricated. P0-06 stress, residual pluripotency, transformation and process
causality remain explicit open requirements. Processing-associated transcription
is a competing explanation, not a diagnosis (S4).

A complete ProgramSpec/ProtocolIR is not yet available: their required program
review/LOD/stage fields and process-design facts must be genuinely curated or
confirmed. Do not set protocol completeness, group counts, attribution minima or
independence facts solely to pass a schema. This candidate can advance only as
far as the existing contract genuinely supports; it does not unlock P0-06 today.

### R5 — explicit candidate families and claim reconciliation

Propose five domain-specific descriptive claims, one for each P0-08 product
domain: target identity, regional fidelity, developmental compatibility,
off-target control and proliferation/stress. Each claim's exact target is the
canonical domain observation under its declared scope, not product acceptability.
Represent missing measurements as open requirements, never synthetic
MeasurementResults. Candidate claims and family/spec registries must be nonempty.

Proposed channel semantics and minima:

| Candidate claim type | Required channel roles / minimum families | Meaning |
|---|---|---|
| Descriptive domain observation | `canonical_measurement: 1` (primary) | One genuine eligible producer observation is necessary; this does not establish one biological replicate or independent confirmation |
| Biological interpretation (reserved, not activated in v0.1) | `canonical_measurement: 1` (primary), `independent_confirmation: 1` (confirmation) | Requires an independently qualified supporting channel; two algorithms on the same data do not meet it |

These minima are proposed governance rules, not empirically calibrated confidence
levels. The first version instantiates only the descriptive claim type, with
`measured`/`inferred` as candidate allowed evidence states; it must also satisfy
every existing tier, execution, applicability and sufficiency gate. There is no
numeric cutoff for a favorable biological interpretation in this version.

For each actual input family, record shared data, algorithm, reference, prior,
knowledge and aggregation dependencies using existing family fields. Same upload
and source specimen remain a shared-data dependency across tools. Alternative
annotations share the relevant reference lineage; the same atlas and its subset
are not independent atlases. Reprocessed results, bootstrap cells and multiple
plots never create independent specimens. Same-study marker discovery and case
evaluation share a declared dependency. Unknown source overlap grants no
independent vote. Keep sensitivity channels separate from confirmation.

Use the existing `family_dedup_then_channel_resolution`,
`unanimous_independent_confirmation` and integration-sensitivity behavior.
Keep `required_sufficiency_states=(sufficient,)` and missing behavior
`insufficient_evidence`. Do not replace conflicts with a majority of tools.

All first-version registries/claims/specs remain `candidate`, families
`unreviewed`, and reviewer/validation references absent until actually provided.
The current reconciler therefore returns `not_assessed` for unfrozen contracts;
it must not show stable/consensus-supported biological conclusions. P0-08
missingness cannot satisfy an unrun domain.

### R6 — report exact observations and missingness; do not certify biology

The proposed report has four sections: declared scope, actual measured findings,
unresolved scientific requirements, and bounded next analyses. Report text and
values bind the genuine P0-09 graph, canonical producer artifact/hash, field,
unit, denominator and source status. Use the existing P0-10 ClaimPolicySpec;
do not weaken it or accept empty registries to get a successful receipt.

Candidate statement wording for review, not yet approved registry entries:

- “This report describes transcriptomic evidence in the declared observations;
  it does not establish efficacy, safety, potency or release eligibility.”
- “An unassessed domain is missing evidence, not a negative result.”
- “Reference correspondence is candidate support, not validated product purity.”
- “Report verification checks evidence and policy correspondence, not biological truth.”

Register these only under compatible existing policy/boundary claim types after
explicit review. Availability claims must name the actual missing requirement;
measurement claims need genuine values and exact bindings. Do not insert a
biological-interpretation claim solely to fill a report section. If the current
P0-10 policy cannot verify a proposed partial report, preserve its actual blocked
or review-required receipt; no fallback label of “verified”.

P0-11 remains a separate user-approved export of existing allowlisted artifacts.
P0-07 comparison and P0-12 graft analyses stay independent optional branches with
their genuine input requirements. No missingness-only report constitutes a full
measured chain.

### Review outcome and acceptance before implementation

This written candidate has not changed the packaged source gate
`review_status: pending` / `execution_allowed: false`, frozen schemas,
registries, scores, current service or historical ToolRuns.

The owner accepted this proposal as the implementation basis. Exact source-state
review, product-window confirmation and approval of any new registry statements
remain separate. Approval of this design authorizes its bounded construction work,
not invented scientific review or biological-unit attestations. Unsupported
states/inputs stay unresolved while unrelated eligible work can proceed.

Implement through the existing Tasks 22–25; do not create another
policy engine or plan. Curate exact resources and review records, construct only
eligible candidates, and verify once the changed boundaries: source-state review,
denominator conservation, missingness, feature coverage, shared-data deduplication,
candidate reconciliation and evidence-bound report text. Then exercise the
genuine next Web step with distinct approval. No repeated QC, broad stability
suite, automatic independent review, push, merge or deployment is part of this
design delivery.

## Source-state and program curation checkpoint — 2026-09-09

This is candidate review material for PRD sections 1.2 and 6.1.1 steps 4 and 7.
It does not change the installed reference, state cards, product roles,
developmental window, thresholds or scientific-release gates.

### Original annotation evidence

Read-only inspection located the relevant broad annotation and dedicated RG/Nb
subtype notebooks. The latest broad notebook is not a replacement for the
dedicated L2 annotation. Exact source observation-ID reconciliation, scRNA
selection and the existing parent-conflict exclusions reproduce the packaged
seven-state total of 11,366 and every existing per-state count. This establishes
metadata lineage consistency, not independent biological correctness.

Saved cluster, regional-marker and DA-marker figures were inspected together
with their producing cells. They provide candidate anatomical/lineage context
beyond label names. However:

- execution counts are out of order, and some cells retain outputs inconsistent
  with their current commented source; no top-to-bottom rerun was performed;
- the plotting helper silently removes unavailable gene features, so an omitted
  panel is not observed negative expression;
- per-gene color scales differ, and a visual location match is not quantified
  same-cell coexpression or a diagnostic cutoff;
- exploratory LMX1A/PAX6 plots and historical transfers do not define exclusive
  positive/negative rules, and the Nb label still lacks a signed state-specific
  discriminant review;
- original notebook figures, package marker evidence and transferred labels
  share source lineage and cannot be counted as independent evidence families.

Private notebooks, original H5AD files and their saved figures remain unchanged.
The detailed artifact hashes, cell references and metadata reconciliation stay
in the private audit. Unreadable directories were not retried with elevated
access; sealed and competitor-isolated sources were not opened for this review.
All R1/R2 executable dispositions remain unresolved.

### Owner-selected updated cell-cycle resource

The owner selected the updated resource as the primary candidate, after review
of its documented differences. The [current official release](https://github.com/satijalab/seurat/releases/tag/v5.5.1)
is pinned to commit `4c0f2dc16fad4e8f0d7b5c98321d8bcb18caa13a`.
The resource is still named `cc.genes.updated.2019`: its name is not the installed
software version. The exact extracted [candidate resource](resources/seurat-cell-cycle-v5.5.1-candidate.json)
contains 43 S and 54 G2M genes, original order, per-list hashes, upstream-file hash
and [MIT attribution](resources/seurat-cell-cycle-LICENSE.txt). It is not a
ProgramSpec and is not loaded by the runtime.

The [official resource documentation](https://satijalab.org/seurat/reference/cc.genes.updated.2019.html)
and actual release data agree on six replacements. In particular,
[MCM2](https://www.ncbi.nlm.nih.gov/gene/4171) /
[MCM7](https://www.ncbi.nlm.nih.gov/gene/4176),
[RPA2](https://www.ncbi.nlm.nih.gov/gene/6118) /
[POLR1B](https://www.ncbi.nlm.nih.gov/gene/84172), and
[BRIP1](https://www.ncbi.nlm.nih.gov/gene/83990) /
[MRPL36](https://www.ncbi.nlm.nih.gov/gene/64979) are distinct current Gene records.
Preserve the selected upstream membership; do not call these same-gene aliases
or silently replace them. The original list is a version-difference record only,
not an approved alternative primary or an executed sensitivity comparison.

The [current vignette](https://satijalab.org/seurat/articles/cell_cycle_vignette.html)
uses the older `cc.genes` in its example and distinguishes phase scores from
regression. Therefore “latest package” does not imply that every tutorial uses
the updated list. BRIDGE's intended analysis remains the existing packaged
Scanpy scoring/aggregation route, with no Seurat method execution and no
regression of cell-cycle signal out of the product matrix. Full-feature
coverage, whole-product scope and R4's missingness/interpretation limits remain.

### Joint-check execution disposition

The live registry and input contracts were inspected for P0-02 through P0-06;
this was contract inspection, not a new scientific run.

| Intended cross-check | Current evidence or blocker |
|---|---|
| P0-02 source-specific correlation plus marker evidence | Existing candidate executor emits these two shadow channels. The method catalog also lists classifiers; catalog presence is not evidence that they ran in this route. Original D28 receipts are preserved without an unchanged rerun. |
| Source-label metadata reconciliation | Executed read-only; existing seven-state counts reproduced. Not expression inference or independent validation. |
| P0-03 / P0-04 regional, target and developmental accounting | Needs genuine V3 lineage and reviewed state/role/window inputs. Notebook retrieval does not approve them. |
| P0-05 hard-count accounting | Needs its genuine V3 input, reviewed roles and separate biological-unit attestation. Unknown units remain unknown. |
| P0-06 updated-list scoring and aggregation | Resource bytes are now curated; ProgramSpec review/LOD/stage fields, ProtocolIR facts, V3 lineage, attestation and exact approved method inputs are still missing. No program score or phase count has been created. |
| Locked external-source/OOD evaluation | Still forbidden until the existing complete biological review and signed FreezeGate; no runner was implemented or run. |

### Clinical context for the target-lineage question — candidate, not release criteria

The owner tentatively favored allowing the target lineage to coexist and asked
for clinical evidence before deciding what developmental states the product
should contain. This is a request for an evidence-backed recommendation, not a
signed ProductDefinitionCard or permission to reclassify current cells.

| Published clinical product | Directly reported product context | What can inform this candidate |
|---|---|---|
| [Kyoto iPSC product, Sawamoto et al., Nature 2025](https://www.nature.com/articles/s41586-025-08700-0) | The final product contained approximately 60% DA progenitors and 40% DA neurons by single-cell RT-qPCR clustering (Extended Data Fig. 1). | Neuronal differentiation is not automatically contamination. These assay-defined classes are not mappings to our RG/Nb labels, and 60/40 is not a BRIDGE threshold. |
| [Bemdaneprocel, Tabar et al., Nature 2025](https://www.nature.com/articles/s41586-025-08845-y) | A cryopreserved hES-derived DA neuron progenitor product, collected at differentiation day 16. Release testing addressed midbrain DA identity, residual pluripotent cells and unwanted serotonergic/choroid-plexus cells. | The intended stage is protocol-specific; regional identity and unwanted-cell evidence are separate requirements. |
| [STEM-PD, Paul et al., Nature Medicine 2026](https://www.nature.com/articles/s41591-026-04525-0) | The July 2026 report describes an RC17 hES-derived cryopreserved DA progenitor product and separate final-suspension viability/sterility checks. | A transcriptomic lineage fraction does not replace product handling, viability, sterility or other clinical release assays. |

These are small, open-label early-phase trials, not a universal composition
standard or validation of this D28 case. Only public product descriptions inform
the recommendation. No competitor transcriptomic data, reproduction, graft
outcome-derived calibration, release cutoff or new runtime knowledge was added.

**BRIDGE design inference:** review the intended product as a specified midbrain
DA-lineage developmental interval, potentially containing progenitors and early
differentiating DA-lineage neurons. Do not define it as either one progenitor
label or every cell carrying a dopamine-associated marker.

Keep three questions separate:

1. **Identity:** does the complete reviewed evidence support the intended midbrain
   DA lineage rather than a nearby regional/neuronal lineage?
2. **Development:** is that supported lineage state earlier than, within, or later
   than the product-specific intended interval? A later target-lineage state is
   not automatically an off-target lineage or an acceptable transplant state.
3. **Other product concerns:** retain separate residual-pluripotency,
   proliferation, unwanted-lineage and processing evidence, with unknown and
   unassessed states intact. Expression alone cannot certify clinical safety.

For R1/R2, the recommendation is to consider supported early DA-lineage neuronal
states as potential intended target components rather than automatically demoting
them to acceptable adjacency. This is a candidate hypothesis only:
`RG_mFP`/`Nb_mFP` remain `role_unresolved`, and no state becomes
`within_window` until its exact discriminants and product-specific mapping are
reviewed. Culture D28 is not directly equivalent to another protocol's D16/D30 or
a fetal gestational week. Do not copy clinical proportions or infer transplant
suitability from the current annotation.

Next: complete the source-state discriminant review, then return the concrete
target-component and developmental-window proposal to the owner for review;
complete the genuine experimental and process-program prerequisites separately.
