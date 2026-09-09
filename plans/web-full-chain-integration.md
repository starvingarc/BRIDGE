# Web Full-Chain Integration Implementation Plan

> Current scope and owner instructions below take precedence over historical task
> procedures. Do not automatically delegate, reopen completed work or start reviews.

**Goal:** Connect real, approved Web analysis stages to the existing P0 toolkit and report actual chain coverage without invented scientific inputs.
**Architecture:** Retain PlanBuilder, exact AnalysisPlan approval, ToolExecutionPipeline and LocalWorkflowExecutor. Materialize each stage only after its real inputs exist; retain prior plans and canonical ToolRuns.
**Tech Stack:** Existing Python/FastAPI runtime, React/assistant-ui client and server-side Playwright.
**Spec:** [Agent integration](../docs/agent-integration.md), [local runtime](../docs/local-agent-runtime.md), [Web preview](../docs/web-preview.md), and the user-approved design below.
**Status:** downstream_measured_inputs_pending. Tasks 1–20 record the earlier PR scope. Tasks 21–25 have installed, browser-exercised choice cards, canonical V2 interpretation, source-backed candidate review/revision and missingness-only P0-08. Task 23's continuation now adds candidate P0-09 missingness compilation and a P0-10 internal draft with actual blocked verification. Runtime snapshot `ea655bc6` was packaged from clean committed source and checked against the built client before isolated acceptance and preview replacement. The existing genuine case reused its prior P0-08 and separately approved only P0-09 and P0-10; original inputs and historical receipts were preserved. Documentation is reconciled afterward. Task 27 subsequently completed the owner-approved descriptive P0-06 joint measurement through a fresh installed SDK. Task 28 adds separately approved genuine L2 marker-context evidence through installed P0-02 0.5.4 while preserving original labels, reference profiles and QC. Neither increment mutated the preview/session. Product-domain measurement construction, new-mode Web acceptance and a qualified/exportable report remain unfinished.

## Current progress (2026-09-08)

The goal remains differentiation-product evaluation using genuine data and
reference resources. Existing QC and cell-state evidence do not establish
product identity, potency, safety or a validated score. The explicit no-graft
path records absence, not post-transplant validation.

| Area | Implemented / observed | Still open |
|---|---|---|
| Tool access | All 12 packages have contract-driven Web input, plan, approval and execution routes | Tool availability does not supply scientific inputs |
| Real user execution | Prior genuine P0-01/P0-02 and separate P0-12 no-graft remain recorded; the author-data case has separately approved missingness-only P0-08, candidate P0-09 compilation and P0-10 blocked internal-report verification. Tasks 27–28 add genuine descriptive P0-06 expression/cycle and P0-02 L2 marker-context measurements through isolated installed SDKs | No product-assessment P0-03–P0-06 result, new-mode Web acceptance, qualified/exportable report, comparison or graft-expression chain |
| Controls and interpretation | Stop, exact input-change confirmation, stage history, JSON/native actions and opt-in aggregate projection exist | Model interpretation quality is separate from transport tests |
| Task 16: table preview | Installed; fresh genuine QC Parquet preview shows bounded rows; original download checksum verified | Preview is intentionally bounded, not the complete artifact |
| Task 17: selected P0-02 | Installed; exact selected-upload reuse retains its recorded focused tests | No new P0-02 execution in the intake journey; product family was intentionally left unknown |
| Task 18: QC explanation | Installed; actual configured model explained genuine canonical E0 measurements and unavailable assessments without rerunning QC | E1 interpretation was not repeated in this journey; independent review cancelled, not passed; one reply's unconfirmed/unsupported wording remains imprecise |
| Task 20 (absorbs 19): product intake | Installed; actual model draft, private exact confirmation, separately approved genuine QC, desktop/mobile, refresh and download observed | This is entry-flow acceptance; later candidate authoring is recorded under Tasks 21–25, not full product evaluation |
| Downstream inputs | Installed and browser-exercised choice cards, canonical V2 interpretation, source-backed candidate review/revision, stage blockers, missingness checks/compilation and a readable internal report with actual release_blocked/ineligible findings | Reviewed state/role definitions, lineage/attestation and curated measured-stage inputs remain open; current release policy does not approve availability claims or this renderer |

### Current PR closeout and next development

PR #95 consolidates the existing Web integration, explicit controls, native/JSON
actions, opt-in evidence summaries, bounded table previews and confirmed product
intake. The integrated tree includes the already-published P0-05/P0-06 dependency
snapshots from PR #96 and PR #97; those scientific-input repairs retain their
separate module scope and validation records. This closeout does not merge any PR,
change a scientific contract, restart a service or repeat completed QC work.

The public PR description and this current-progress section are the current
handoff. Earlier task procedures and validation sections are history, not competing
work queues. The latest public-head CI is reported independently; old green checks
never certify a newly published revision. The PR remains Draft while integration
checks and genuine downstream acceptance are incomplete.

The first closeout CI on public head `4855c0a` ([run 34194301229](https://github.com/starvingarc/BRIDGE/actions/runs/34194301229))
reported **2 failed, 2,137 passed, 66 warnings**. Both failures were service-test
setups/expectations that still assumed the removed initial chat declaration or
upload message. They now explicitly confirm the count declaration, check the
bounded intake-readiness context without private values, and inspect count-layer
availability in the intake structure without inferring raw-count semantics.
The two exact failed node IDs in `tests/test_web_service.py` passed in the focused
follow-up (**2 passed, 2 warnings**). Runtime files and the installed preview were
unchanged; this focused result does not replace CI on the corrected public head.

The corrected-head run `34196606403` was subsequently cancelled by the job's
30-minute execution limit (GitHub annotation: maximum execution time exceeded),
not recorded as a completed test result. The job budget is now 45 minutes; the
suite, checks and failure conditions are unchanged. A new-head result is still
required before closing the engineering gate.

The owner has approved a draft-purpose-only projection of confirmed
`product_family`, `target_cell_type` and `target_stage` to the configured model.
All other private intake fields remain excluded. This authorization is recorded
in the decision log. Task 22 implements it for scientific-draft requests only;
the current installed preview includes this purpose boundary.

The reviewable scientific-input candidate flow is now installed: it uses the
confirmed product intent plus versioned knowledge to propose product-definition
and state-role inputs, explains sources and missing facts, and materializes
validated, explicitly confirmed candidates through the existing registration and
planner path. The next milestone returns to PRD steps 4 and 7: resolve the actual
state/role review and experiment-design facts needed for measured product domains.
Do not infer product targets from the observed result, create biological replicates from a count, promote provisional states, or require
the researcher to author internal scientific JSON. Detailed implementation starts
from the current contract inventory, not another QC or provider-protocol rewrite.
Later milestones are question-led product evidence, evidence-grounded report
assembly, and separate comparison/graft journeys when their genuine inputs exist.

### Scientific-input construction design (2026-09-08)

The owner has now explicitly approved filling the Agent construction gap. The
[written design](web-scientific-input-design.md) extends this existing workstream,
not a second plan. It records the observed missing provider action, purpose-scoped
intent projection and deterministic object construction, plus the V2 cell-state
interpretation gap. The design preserves separate scientific-choice review,
biological-unit attestation, analysis approval and export approval. The owner's
subsequent request adds inline single/multiple-choice clarification with free
text and unknown answers, persisted responses and purpose-scoped privacy;
answering a question is not execution or attestation approval.

The owner has approved the written design, including inline choice questions,
and requested implementation. Tasks 21–25 below govern the increment; Task 25
records its installed/browser acceptance and remaining limits. Existing genuine
runs remain immutable; missing sample independence is not filled to unlock a stage.

### Downstream candidate-rule design (2026-09-08; formulation completed)

After the owner requested further downstream completion, the explicit packaged
source-review gate and missing product-specific graph/report rules were confirmed.
The owner then authorized source-backed formulation of new candidate rules.
The [v0.1 candidate appendix](web-scientific-input-design.md#downstream-candidate-rules-v01)
now proposes separate identity/anatomy/development accounting, unresolved-state
preservation, descriptive cell-cycle scope, dependency-aware claims and an
evidence-bound partial report. Its source ledger distinguishes original studies,
current state-review limitations and BRIDGE's proposed governance rules.

At that formulation checkpoint this was research and written design only; Task 23
continuation below records the subsequent owner-approved implementation. No
candidate policy was scientifically approved at that earlier checkpoint and
no source gate, score, schema, service or historical run was changed. The owner
subsequently approved bounded implementation; the continuation below records the
code and installed acceptance, while scientific source and release review remain
separate. The earlier documentation-only proposal passed repository policy and
whitespace checks; it did not include biological tests or broad regressions.

### Remaining product and scientific gaps

- Product-assessment P0-03–P0-06 modes need genuine product definitions, state
  roles, developmental/process specifications and mode-specific measurement/
  attestation inputs. Existing QC, cell-state and biological-unit outputs do not
  supply those decisions. Task 27's separately approved descriptive P0-06 mode
  has run, but supplies no gate-facing domain MeasurementResult.
- P0-07 needs real comparison arms, bundles and a comparison design.
- P0-08–P0-11 still need measured upstream domain evidence and a qualified
  report/export path. The current genuine missingness-only graph and blocked
  internal report do not supply that evidence or release approval.
- P0-12 supplied-evidence/expression modes need genuine graft inputs; a no-graft
  result does not satisfy either mode.
- The advanced input panel still offers registration/reuse; the separate Agent
  candidate card now covers product/role and optional regional/development drafts,
  not every measured-stage prerequisite. No hidden input identity was guessed.
- Culture/source declarations do not establish donor, pooling or cross-timepoint
  independence. No new scientific state, score or release claim is authorized.

### Execution state and next work

The documentation-only alignment was completed first. The owner's subsequent
"现在请你补齐" approved Task 20's product-entry flow. It now replaces initial
free-text declaration scanning and pending-QC state, reuses existing controls and
tool execution, and presents a private product draft plus readable evidence route.
Tasks 16–18 retain their recorded validation; no independent review wave or
broad unchanged-suite replay is authorized.

The narrowed product-entry increment is implemented and installed. A fresh
genuine-data browser journey completed upload, actual-model draft, two explicit
fact confirmations, an unapproved next-stage plan and a separately approved QC
run. Follow-up explanation reused that run. Missing formal scientific-input
builders remain a separate downstream gap; the private product draft does not
fabricate those objects. No further QC review or broad-suite cycle is implied.

The sections below retain implementation history. Earlier `not_connected`
states, broad-suite instructions and review loops are not current work orders.

## Owner-directed execution override (2026-09-08)

The owner stopped repeated review, old-code comparison and stability-proof loops.
This instruction supersedes the automatic review/re-review and broad repeat-test
steps below; completed historical records remain records, not tasks to rerun.

- Freeze completed QC work and advance the actual user journey with genuine data
  and reference resources. Do not add another QC framework.
- Make only the changes needed for an observed current-path blocker. Read the
  active implementation, remove confirmed superseded code in the same focused
  change, and avoid parallel legacy/new mechanisms or repeated rework.
- Verify the changed behavior once, then exercise it through the actual UI.
  Do not rerun already-passing suites or repeat old-version comparisons merely
  to demonstrate general stability.
- No automatic independent review waves. Task 18's in-progress review was
  cancelled by the owner; its implementation and recorded tests are not thereby
  labelled independently reviewed.
- Clean only specifically identified obsolete code. Preserve unrelated worktrees,
  original inputs, genuine reference resources and historical run evidence.
- Task 19 is absorbed by owner-approved Task 20. Its initial parser has been
  replaced in the same focused change; it is not authority to resume completed
  review or full-suite cycles.

## Approved design and current finding

Tasks 1–3 below record the completed staged increment. Tasks 4–6 extend that
baseline to contract-driven access for every P0 tool; their requirements replace
the earlier `not_connected` capability restriction, without changing the genuine
data acceptance conditions.

The user approved reusing the existing tools/executor, connecting Web inputs, staged approval and per-tool results; single-product, comparison and independent graft paths remain the complete target. This plan does not replace those targets with an offline replay.

At the initial baseline, the genuine upload lacked declared sample/capture/independence relationships, and P0-05/P0-06 had the producer-contract gaps recorded in Tasks 7/8. Subsequent owner-confirmed culture relationships and exact source-backed column declarations permit genuine QC and V3 cell-state continuation. They do not establish donor, pooling or cross-timepoint independence. The integrated count-only/source-bound routes do not authorize fabricated weights, unknown labels, attestations or scientific definitions.

The first increment connected raw-count-compatible P0-02 and independent P0-12 no-graft. Tasks 4–6 subsequently connected P0-03–P0-11 through contract-driven supplied inputs; they are no longer categorically not_connected. Missing scientific inputs still block genuine execution. A normalized single-product profile requires its own declared matrix semantics and true lineage; a raw-count QC DataView must not be relabeled.

## Global Constraints

- All project code, tests, builds and data remain on the designated server workspace.
- Prefer the configured current provider. The owner explicitly authorized the existing older API as a fallback after a primary outage; use it only in the isolated validation instance. Provider context is status-only by default. The owner-approved opt-in summary projection below may include bounded aggregate measurements, never raw matrices, observation rows, source-family values, sample identities, private paths or credentials.
- No P0 Tool ID, scientific Schema, score, threshold, state definition or release authority change in this Web increment.
- Preserve candidate/shadow and domain_score=null; preserve partial, unavailable, not_assessed and explicit input-construction blockers.
- No fabricated metadata, weights, replicas, attestations, references, measurements, successful exports or tool execution.
- No old-request replay as proof of a freshly constructed Web chain.
- Keep the current deployed preview running during development. Test a separate instance before any rollout.
- Shared policy, docs and integration are root-owned; implementation workers write only their assigned server worktree paths.
- No private host/path/environment/key/resource identity, hash, biological result or scale in public Git content.
- One integration PR; any necessary P0 contract change is a separate module decision, not hidden in this branch.


## Tasks 21–25: Owner-approved scientific construction (2026-09-08)

The owner approved the written construction design and conversational choice
questions, and explicitly requested connection to existing product code.
Execute inline under executing-plans and test-driven-development. The current
isolated worktree is retained; no new review wave, baseline rerun or automatic
delegation is part of this increment.

**Spec:** [Scientific-input design](web-scientific-input-design.md).
**Goal:** Connect source-backed input candidates, exact user review, registered
scientific execution and evidence-bound report delivery in the existing Web.
**Architecture:** Extend the current Action, private session, Controls, Inputs,
PlanBuilder and executor. A choice answer is a draft fact, not tool approval.
Use package-owned scientific contracts and policies without changing them.
**Tech stack:** Existing Python/FastAPI/Pydantic and React/assistant-ui; configured
provider transports; installed server test and browser runtimes.

### Task 21: Conversation questions that produce private, reviewable answers

**Implemented and installed; real choice-card acceptance is recorded in Task 25.** The new action first failed in both
transports and all 14 initial service cases because the feature was absent.
Those 14 then passed. A separate native JSON Schema check caught nested local
references resolving from the wrong root; inlining the local definitions fixed
it. The extended focused run passed 36 cases with one expected action-inventory
assertion requiring the new action; that exact corrected case passed afterward.
All 17 new cases passed in that extended run. Two existing dependency deprecation
warnings remain. This is engineering evidence, not an actual-model or browser
acceptance result. No scientific tools were invoked by these question tests.

**Files:** Create src/bridge/web/clarification.py and
tests/test_web_clarification.py; modify provider.py and app.py.
**Interfaces:** QuestionSet has upload_id and one to three Question records.
Question has field, title, reason, multiple and two to four Option records
(id, label, description). Allowed fields are IntakeFacts fields plus
assessment_focus. Application-owned unknown and free-text answers remain
available. Clarifications(service).stage(state, QuestionSet) returns an inline
private card. AnswerBody carries card_id, card_digest and answers
(field, selected option IDs, text, unknown). Clarifications.answer stages intake
changes via Controls; it never confirms them or executes tools.
Clarifications.context returns status/field names only.

- [ ] Add transport/service tests using real session storage and the existing
  synthetic upload helper, replacing only provider HTTP. The missing action must
  first fail an assertion that parse_action accepts this proposal:
  ```python
  payload = {"action": "ask_user_input", "questions": {
      "upload_id": "a" * 32, "questions": [{
          "field": "assay", "title": "Which assay?", "reason": "Choose compatible input checks.",
          "multiple": False, "options": [
              {"id": "scRNA-seq", "label": "Single-cell", "description": ""},
              {"id": "snRNA-seq", "label": "Single-nucleus", "description": ""}]}]}}
  try:
      action = parse_action({"content": json.dumps(payload)})
  except ValueError:
      action = None
  assert action is not None
  assert action.action == "ask_user_input"
  ```
- [ ] Run pytest tests/test_web_clarification.py. Confirm rejection of the new
  action is the RED failure, not missing runtime setup.
- [ ] Add the constrained model and both transport schemas; stage bounded,
  session/revision-bound cards; add POST clarification/answer and
  clarification/cancel. Validate option membership, duplicates, multi-selection,
  unknown exclusivity, free text and allowed field types. Compare exact digest
  before mutation. Persist answered cards, idempotent identical retries and
  pending facts; exclude their transcript records from provider history.
- [ ] Verify submitted assay remains unconfirmed until Controls.resolve; no
  ToolRun appears. Verify private supplementary text never reaches converse;
  stale/cross-session/unknown-option requests reject without state changes.
- [ ] Run this focused test file plus affected provider protocol tests once,
  inspect the diff and commit the tested feature.

### Task 22: Source-backed scientific candidates and canonical interpretation

**Candidate backend installed in part; not a completed measured scientific stage.**
Eleven initial tests failed for the absent service/action. They then passed.
The focused construction/intake/question run passed 49 tests, including actual
HTTP-boundary coverage of JSON and native draft requests, matching state/source
IDs, exact confirmation, stale/cross-session refusal, no invented independence,
and candidate regional/development objects without review promotion.
A new source-review gating test first exposed the generic missing-object reason;
the exact source gate is now retained before preparation. Dependency deprecation
warnings remain. Eighteen additional action/protocol cases passed; their sole
outdated native-action inventory assertion was updated for the two new actions,
and that exact case then passed. These are engineering fixtures, not genuine
scientific execution.
The source catalog is the packaged biological review, not method-search titles.
Its pending review and product-context execution prohibition remain explicit.
Core ProductCase/definition/role-map and supported optional regional/development
objects are built after confirmation. Remaining prerequisite binding, typed
lineage/attestation and P0-05/P0-06 inputs remain unfinished. The review UI and
exact revision endpoint are now implemented under Task 24.

**V2 interpretation installed; remaining measured-stage construction still pending.** Five
new canonical legacy tests first failed because V2 was not projected. All five
then passed with 40 affected existing evidence tests (45 passed). Six additional
negative cases passed in an 11-case legacy run. The implementation validates the
original upload, producer, artifact, per-level denominator, labels, partitions
and assessment states. It identifies V2 and does not create typed lineage or
fallback from an invalid V3. No scientific tool was rerun. Existing dependency
deprecation warnings remain; this code is now installed, with actual E1 interpretation recorded in Task 25.

**Files:** Create src/bridge/web/scientific_inputs.py and
tests/test_web_scientific_inputs.py; modify intake.py, control.py, inputs.py,
provider.py, app.py, evidence.py and tests/test_web_evidence.py.
**Interfaces:** ScientificInputs(service).context(state, upload_id) returns
draft-purpose product intent and configured versioned scientific choices.
ScientificInputs.propose(state, upload_id, candidate) stores a private draft;
candidate contains semantic choice IDs and supporting source IDs, not arbitrary
scientific JSON. ScientificInputs.confirm(state, draft_id, digest) validates,
materializes and registers ProductCase, ProductDefinitionCard and supported
stage-specific objects, returning their existing input IDs. The draft response
contains sources, unknowns and per-stage blocking reasons.

- [ ] Add a real-service test confirming only product_family, target_cell_type
  and target_stage enter a draft request; ordinary chat still excludes all
  privately entered facts. Assert a stale intake cannot produce draft context.
- [ ] Add canonical synthetic V2 result tests: expose its bounded tool-owned
  counts with its original denominator, explicitly identify V2 and reject a
  modified receipt/hash. Never label this result V3 or downstream-ready.
- [ ] Run the new tests and observe missing construction/V2 support failures.
- [ ] Build context from existing configured reference/vocabulary and local
  knowledge resources. Validate candidate source/choice IDs against that exact
  snapshot. Construct required models through the existing package classes;
  unknown independence remains absent. Register objects only after exact
  confirmation and use existing Selection/Inputs validation for eligible stages.
  Missing V3 lineage or attestation is an explicit blocker, not a fallback
  fabricated evidence bundle.
- [ ] Verify a confirmed source-backed draft produces schema-valid input objects,
  unknown choices do not acquire positive roles, tampered dependencies invalidate
  only mutable proposals, and no tool runs before plan approval.
- [ ] Run focused construction/evidence tests, inspect and commit the change.

### Task 23: Evidence sufficiency, graph, report verification and export inputs

**Historical checkpoint after the owner's “先完成” continuation; the candidate-report continuation below supersedes this earlier construction limit.** Eight focused
report tests pass, including the actual P0-08 tool on a synthetic Web case, five
not-assessed profiles with null scores, no execution during preparation, cached
input reuse, stale draft refusal and source change between proposal and approval.
The owned selection is rechecked before preparing and approving a plan. Together
with the candidate/revision tests, the focused run passed 29 tests (two existing
deprecation warnings). This does not establish genuine-data browser acceptance.
The missingness-only route intentionally does not bind unmatched historical QC
or V2 cell-state evidence. No report policy or scientific threshold was added.
P0-09–P0-11 construction remains unavailable for the following reason. Read-only
inspection found that P0-08 supplies its gate rule and P0-10 supplies its
hash-approved claim policy/statement registry, but P0-09 supplies models and
adapters only, not packaged EvidenceFamilyRegistry, ClaimRegistry or
ReconciliationSpecRegistry instances. They require product-specific channel,
independence-family and reconciliation decisions. No configured Web catalog
supplies these instances. Test/example registries are not scientific authority.
The approved design says to reuse package-owned rules and forbids new scientific
thresholds or release authority. Do not invent those registries to obtain a
successful graph/report. The owner then directed completion of the existing
scope first. Expose the missing policy in the page and finish available review
and missingness routes; do not repeatedly ask the same question or silently
invent policy. Preview installation and genuine missingness-only execution are
now recorded in Task 25; complete report acceptance has not happened. This is an
unconfigured scientific-policy prerequisite, not evidence
that a tool or completed upstream run failed.

**Files:** Create src/bridge/web/report_inputs.py and
tests/test_web_report_inputs.py; modify scientific_inputs.py, intake.py and app.py.
**Interfaces:** ReportInputs(service).prepare(state, tool_id, upload_id) constructs
inputs for P0-08–P0-11 from the current confirmed product context and canonical
ToolRun artifacts. It registers and selects through Inputs, then calls the
existing preparation path. Only explicit plan approval executes a tool.

- [ ] Add tests with real schema-valid canonical outputs for stage input
  construction. Assert an unrun target stage is a missing observation, not a
  MeasurementResult; a draft cannot bind a numeric claim absent from evidence.
- [ ] Run the new tests to observe missing report-construction behavior.
- [ ] Assemble DomainGateInput using load_gate_rule; assemble compilation inputs
  using package registries, real outputs and unresolved requirements. Construct
  ReportDraft with exact evidence bindings and package-approved statement
  policy; feed P0-10 rather than self-certifying it. P0-11 remains a distinct
  approved plan using its export policy and verified draft binding.
- [ ] Test canonical receipt changes, stale product context, unavailable source
  stages, verifier findings and separate export approval. Reject unsupported
  report claims instead of replacing missing values with zero.
- [ ] Run the focused report-input tests and commit the verified integration.


### Task 23 continuation: PRD-led candidate evidence and internal report

**Status:** implementation authorized by the owner on 2026-09-08, including the
v0.1 candidate proposal. The owner requires regular PRD review, explicit personas,
step-by-step user/developer reasoning and concrete examples. The earlier
no-new-policy limitation above is history for that earlier authorization; source
review, attestation, execution and export gates still apply. Execute inline in
this existing worktree; no automatic independent review waves or new plan.

**Goal:** A researcher who has a confirmed product draft and genuine P0-08
missingness result can inspect its candidate evidence graph and an honest internal
report, without writing scientific JSON or rerunning QC. A verified report or
export is not promised when the current P0-10 contract rejects availability text.

**PRD:** sections 1.2, 3.3–3.6 and 6.1.1 steps 4–12.
**Spec:** downstream candidate appendix R1–R6 in the existing scientific-input
design. Correct its schema term `observed` to the actual `measured` enum; this is
a naming alignment, not additional measurement or scientific approval.

**Exact changes and responsibilities:**

- Modify `docs/BRIDGE_PRD.md`: refresh confirmed capability boundaries, describe
  wet-lab/researcher and developer responsibilities, the detailed journey and two
  worked examples. Do not maintain a second per-commit runtime ledger there.
- Create `src/bridge/tool_packages/p0_09_evidence_compiler/candidate_policy.py`:
  a narrowly scoped, versioned candidate factory owns descriptive claim semantics,
  the one-family minimum and candidate/unreviewed statuses. It does not run a
  method or freeze science. Account for this one source file in
  `scripts/check_repository.py`; no generic policy engine or new public Schema.
- Modify `src/bridge/web/report_inputs.py`: keep P0-08 preparation, extend the
  same endpoint to exact next-stage P0-09/P0-10 preparation, bind verified
  same-draft producer receipts, and expose a bounded private report projection.
  Cache immutable inputs per draft/stage; reject stale/mixed selections.
- Modify `src/bridge/web/app.py`, `scientific_inputs.py`, existing
  `provider.py` guidance and `web/src/{api.ts,types.ts}`: connect the existing
  prepare/approval path and private projection. Do not broaden model sharing.
- Modify `web/src/components/ScientificInputs.tsx` and `Conversation.tsx`:
  explicit next-stage controls and internal-report reading; fix P0-07's observed
  “graft evidence” mislabel to product comparison, with its own missing-input
  reason. No graft input is required for a pre-transplant comparison.
- Extend `tests/test_web_report_inputs.py` and
  `web/tests/scientific-inputs.test.tsx`; run only newly changed behavior and
  directly affected tests. Keep genuine data and browser artifacts private.

**Interfaces to implement:**

`build_missingness_policy(case: ProductCase, definition: ProductDefinitionCard,
result: EvidenceSufficiencyRunResultV2, *, created_at: datetime)
-> dict[str, FrozenModel]` returns the four P0-09 input roles:
compilation_bundle, evidence_family_registry, claim_registry and
reconciliation_spec_registry. The Web boundary rejects non-hPSC-mDA scope using
confirmed intake facts (ProductCase has no product-family field). The factory
rejects wrong case/definition, duplicate/incomplete domains, or measured results rather than turning them into
missingness. Compilation references actual object hashes and canonical P0-08
provenance; each missing observation refers to the real candidate claim contract.

`ReportPreparation(DraftIdentity)` adds
`tool_id: Literal["P0-08", "P0-09", "P0-10"] = "P0-08"`.
`ReportInputs.prepare(state, body)` constructs only that requested eligible stage.
`ReportInputs.public_report(state, draft)` returns no paths, hashes, raw rows or
credentials; report/claim-check status and wording are derived from exact verified
objects. Source changes or any successful P0-03–P0-06 result invalidate this
missingness-only construction; measured report binding is a separate path.

- [x] Write/observe a failing endpoint test for P0-09 preparation after a genuine
  P0-08 ToolRun on a synthetic case; construction must not execute:
  ```python
  response = client.post(f"/api/sessions/{sid}/report-inputs/prepare",
      json={**body, "tool_id": "P0-09"})
  assert response.status_code == 200
  assert response.json()["plan"]["steps"][0]["tool_id"] == "P0-09"
  assert service.load(sid)["_tool_runs"] == before["_tool_runs"]
  ```
- [x] Implement the package candidate factory and P0-09 assembly. Approve the
  synthetic plan through the real API. Assert five open domain requirements,
  zero EvidenceRecords, candidate/unreviewed contracts and not_assessed
  reconciliation; do not assert science from test success.
- [x] Check missing/corrupt/wrong-draft producer,
  modified selection, altered policy and repeated preparation. Assert rejection
  before a new ToolRun and preservation of historical receipts.
- [x] Write/observe a failing P0-10 construction test. Generate actual
  ReportDraft claims from the P0-09 requirements, include the existing approved
  boundary statement verbatim, and bind the real graph and unchanged package
  policy/registry. Use a genuine authoring/renderer identity; unsupported claim
  types must keep the actual verifier's blocked result.
  ```python
  response = client.post(f"/api/sessions/{sid}/report-inputs/prepare",
      json={**body, "tool_id": "P0-10"})
  assert response.status_code == 200
  assert response.json()["plan"]["steps"][0]["tool_id"] == "P0-10"
  assert not response.json().get("public_export_approved", False)
  ```
- [x] Implement report projection and rendered next-step controls. Write the
  frontend tests first for the correct comparison label, explicit report step,
  readable missingness and blocked-export explanation. Verify requests carry
  the exact draft identity and selected tool, and do not approve themselves.
- [x] Revisit PRD steps 9–11, run the focused tests and client typecheck/build,
  inspect the changed diff and record limitations. Commit the coherent increment.
- [x] Build/install in the isolated acceptance runtime first, then update the
  existing preview after acceptance; preserve all original inputs/history and
  walk the genuine case through the ordinary browser.
  Reuse the existing approved P0-08 receipt if all exact bindings remain valid.
  Approve each new tool stage separately, inspect desktop/mobile and refreshed
  report state, and record actual P0-09/P0-10 receipts and export eligibility.
- [ ] Return to PRD steps 4 and 7 after report acceptance: implement only the
  source-backed measured-stage construction permitted by actual reviewed
  definitions, fully curated program resources and genuine experiment facts.
  Preserve every unsupported state and required confirmation; do not invent
  these inputs or mark the full downstream chain completed.


### Task 23 candidate-report engineering evidence (2026-09-08)

The candidate graph test first failed on the absent selected-stage interface; the
internal report test first failed on the missing P0-10 preparation path. Real
approved synthetic P0-08/P0-09/P0-10 calls now retain five open requirements,
zero EvidenceRecords, five not_assessed reconciliation records and the actual
release_blocked/ineligible verification. The packaged safety-boundary statement
is copied exactly; no release rule, scientific source or renderer approval changed.

A targeted corruption test exposed that P0-10 approval did not yet recheck the
P0-08 result. After adding upstream input verification, all four corruption
variants passed; stale reports are withheld. Repeat preparation preserves
immutable inputs, a modified selection cannot be approved, and a new scientific
draft cannot borrow an earlier draft result. The factory rejects wrong or
incomplete case/domain bindings and measured inputs. Sixteen related backend
cases were covered across focused runs, not a new whole-repository suite.

Three new browser-component cases first failed on the missing comparison label,
next-stage controls and report. Those three plus the directly affected P0-08
request case passed. The report shows candidate status, exact blocked reasons,
unchanged safety boundary, next facts and no export control after refresh.
These are engineering tests with synthetic fixtures, not genuine-data or
scientific validation. Packaging, installed browser acceptance and actual
case receipts remain separate work below.

The isolated browser then completed all three stages using a clearly labeled
synthetic input and the configured model. It showed the actual blocked result,
with source-review and independence gates unchanged and no QC run. Visual
acceptance found alphabetical domain ordering and an incorrect "above" approval
hint. A failing first-heading assertion reproduced the order issue; the client
now follows the PRD domain order and uses a position-independent approval hint.
No ReportDraft, evidence receipt or verifier result was changed by this display fix.

### Task 23 installed browser acceptance and PRD return (2026-09-09)

**Biological question and observation.** Can the existing pre-transplant product
case show what remains unanswered without turning reference correspondence into
product purity? Its genuine, previously registered author-count input and
canonical QC/cell-state/missingness receipts were retained. The original case
then separately approved exactly two new stages through the ordinary browser:
P0-09 compilation and P0-10 verification. The graph contains five open domain
requirements, zero domain EvidenceRecords and five not_assessed reconciliation
records. This zero refers to the missingness-only domain graph, not absence of
the earlier QC or cell-state observations.

The internal report displays each unmeasured domain, the exact existing safety
boundary and actual release_blocked/ineligible findings. The reasons are
claim_type_policy_missing and unapproved_renderer_requires_review. A successful
ToolRun is therefore not a passed claim check or a product failure. No score,
biological independence, source approval or export permission was created.
The interface offers no export control.

**Installation and acceptance evidence.** Clean source snapshot `ea655bc6`
was built into a wheel and installed in private acceptance directories. Installed
Python and client bytes were compared with their source/build inputs; all
12 tool packages and eight model actions imported. The isolated synthetic case
used the configured model and ordinary UI, then approved P0-08/P0-09/P0-10.
After the domain-order and approval-hint fixes, its desktop/mobile and refreshed
report were inspected before switching the existing preview. Provider settings,
reference resources and trust configuration were unchanged.

The controlled preview replacement preserved all six original sessions and
166 existing case files at startup. The genuine-case audit subsequently checked
every new receipt/artifact hash, exact report-to-verification content binding,
the unchanged first three ToolRun registrations and every original non-session
case file. It passed. Exact paths, case IDs, hashes, process identities and
backups remain private; no original data or tool artifact was overwritten.
No prior QC, cell-state or missingness stage was rerun.

Regular server-side Playwright was used because the Browser plugin was not
available; no browser dependencies were installed. The intended page rendered
without a framework overlay. Separate preparation/approval, target-first report
order, five missing domains, blocked reasons and absence of export controls were
observed at 1280 x 900 and 390 x 844, then after refresh. Screenshots were
visually inspected. There were no page errors, failed requests or browser
operation errors; the genuine run retained one pre-authentication 401 and a
favicon 404 console message, not a zero-warning claim. This is an Agent-operated
walkthrough, not external wet-lab user acceptance. The non-fatal client chunk-size
warning remains. No push, merge or formal deployment is claimed.

**Return to PRD steps 4 and 7.** The package's current product-context review
still says `review_status: pending` and `execution_allowed: false`; the
biological-review source has pending product/state-role review and no signatures.
The current case has no approved regional numerator/denominator or developmental
window and still lacks confirmed sample/preparation/independence relationships.
At that installed checkpoint the descriptive cell-cycle candidate also lacked
fully curated resource contents; Task 26 now supplies the candidate resource, but
genuine ProgramSpec/ProtocolIR review/design fields remain missing. These are separate
scientific-definition, resource-curation and experiment-fact gaps, not a request
for the researcher to write JSON. R1-R4 measured construction and a qualified
report/export remain open. The next scientific work is to review source state
definitions and their product-role/anatomy/development mappings, curate the exact
program resources, and confirm only experiment facts that can be established.
Implementation approval does not provide the missing scientific signatures.
No protected source or release gate was changed to make this case run further.

### Task 26: Source-state review and curated program inputs (2026-09-09)

**Owner direction:** continue the PRD-led downstream work, ask about material
scientific choices, and synchronize actual progress to the existing GitHub PR
after this increment. The owner located original plots mainly in notebooks under
private server research directories and requested the latest relevant versions,
literature context and joint checks using packaged tools. This does not approve
state definitions, attest independence, open locked data or authorize a merge.

**PRD link:** sections 1.2, 3.3-3.6 and 6.1.1 steps 4 and 7; retain the two
worked product examples. A researcher needs to understand what a state means
and what decision it supports, not reconstruct internal JSON.

- [x] Inventory relevant original annotation and RG/Nb notebooks read-only,
  compare content/version lineage as well as timestamps, and retain exact private
  artifact identities. Do not execute or rewrite notebooks during retrieval.
  Stop at unreadable directories; never bypass permissions. Exclude sealed and
  competitor-isolated evidence from source construction.
- [x] Inspect saved marker/annotation figures and their producing cells; reconcile
  original source metadata against the seven packaged RG/Nb states. Preserve
  shared lineage, unavailable features and mixed execution-order caveats.
- [ ] Complete exact source-state discriminants and product role/window review.
  Historical plots and clinical product descriptions are candidate context,
  not independent validation, executable mappings or human approval.
- [x] Curate the complete proposed S/G2M resource from an exact official release,
  preserving the original bytes, extracted list order, license, provenance and
  content hashes. Check name changes against stable gene identities; ambiguous
  replacements require explicit review, not automatic alias rewriting.
- [x] Establish which source-backed cross-checks the registered packages can
  actually run. Use separate method channels and true source-family dependence;
  no majority vote, fabricated measurement, unreviewed production default or
  locked runner. Record blocked inputs as explicitly as executed checks.
- [x] Ask the owner about material product/resource choices and record the
  updated-list selection. Respond to the tentative target-lineage preference
  with primary clinical literature and a candidate identity-versus-stage
  recommendation. Final product mapping and source review remain separate.
- [x] Verify the changed curation evidence and exact failed Web fixtures; prepare
  the public-safe increment for the existing Draft PR. Preserve public history,
  private runtime/data and the recorded acceptance from earlier increments.
  No private intermediate history, notebook, path, credential or unpublished
  measurement is part of publication.
- [ ] Complete current-public-head CI before closing the engineering gate.
  The PR conversation records the publication receipt and current-head status.
  No automatic independent review, full-suite replay, force push or merge.


#### Task 26 evidence checkpoint

- Read-only source inspection and exact-ID/parent reconciliation reproduce all
  seven packaged RG/Nb scRNA counts, totaling 11,366. Original notebook cells and
  saved figures were inspected; mixed execution order, silently omitted features
  and shared annotation lineage remain explicit caveats. No source file changed.
- The owner selected the official updated cell-cycle list as primary. Seurat
  v5.5.1's exact resource has 43 S and 54 G2M genes; release commit, raw/list
  hashes, exact symbols and MIT attribution are recorded in the linked candidate
  resource. No runtime default, program score or acceptance threshold changed.
- Live P0-02–P0-06 registry/input inspection separates actual candidate channels
  from method-catalog entries. New measured runs remain blocked by genuine
  V3/attestation, reviewed state/role/window inputs and complete ProgramSpec/
  ProtocolIR. Metadata reconciliation is not a new biological ToolRun.
- Full evidence limits and joint-check disposition are in the
  [source/program checkpoint](web-scientific-input-design.md#source-state-and-program-curation-checkpoint--2026-09-09).
  Private notebook excerpts, image hashes and the reproducible metadata audit
  remain private. No old notebook, locked runner, unchanged QC or cell-state
  analysis was rerun; the original preview and case receipts were preserved.
- At the owner's request, three primary clinical publications were checked for
  actual product-state definitions (Kyoto 2025, bemdaneprocel 2025, STEM-PD 2026).
  The design recommends reviewing a specified mDA-lineage developmental interval,
  potentially including early differentiating neurons. Clinical composition,
  assay classes and culture days are not imported as our thresholds or mappings.
  This remains a recommendation; no source signatures or frozen decisions exist.
- Publication validation also inspected the previous public-head CI
  [run 34217860693](https://github.com/starvingarc/BRIDGE/actions/runs/34217860693):
  Python completed with 2,139 passed and 66 warnings; Web had 2 failed, 62 passed
  and two unhandled errors, so later gates were skipped. The two old polling
  fixtures returned a Session for the new intake GET. Both exact failures were
  reproduced, then passed after adding typed synthetic intake responses and
  explicit rendered-structure checks. Existing stop/stale-response and exact
  confirmation assertions remain unchanged. Type-check passed. No runtime code,
  dependency, timeout or test assertion was weakened; no broad suite was replayed.
- Resource/hash integrity, repository-policy and whitespace checks passed for
  this curation increment. Exact notebook evidence remains private and original
  analysis receipts/runtime are unchanged. Latest-head CI is a separate gate,
  not established by the two focused tests or the previous head's Python result.

### Task 27: Approved exploratory expression and cell-cycle measurement

**Status:** implemented and genuinely executed through isolated installed P0-06 0.8.1; publication checkpoint below. New-mode Web acceptance and product-assessment gates remain open.

**Goal:** Describe expression of the owner-selected Seurat S/G2M programs and
predicted cell-cycle phases in the current selected DataView without pretending
that state/role review or biological independence is resolved.

**Approved intent:** On 2026-09-09 the owner approved adding this independent
exploratory path and executing the joint measurement, with literature checked
before further questions. This does not approve a scientific release.

**Design:** Add one opt-in `exploratory_process` mode to existing P0-06.
A checksummed `ExploratoryProcessInput` v0.1 binds the exact DataView, source
family, gene-symbol column, versioned S/G2M resource and exact gene lists.
The package computes Scanpy control-adjusted expression, decoupler ULM scores,
Scanpy S/G2M/G1 predictions and descriptive phase counts for all selected
observations. Require complete feature coverage in this first mode; retain
explicit missing-gene reasons instead of silently substituting symbols.
Use total-count normalization to 10,000 followed by log1p only for declared
raw counts, fixed seed and explicit method parameters. No cell-cycle regression.

A new versioned P0-06 result union preserves existing v0.3 product-profile
payloads and adds a distinctly typed exploratory profile. Old input modes,
review/attestation checks and public schemas remain intact. Exploratory outputs
are checksummed aggregate JSON and per-observation Parquet, not gate-facing
MeasurementResult records. Independence stays unknown, independent n null,
state review pending, product purity/acceptance unavailable and domain score null.
S/G2M methods share one expression evidence family; do not average their units,
count methods as votes or treat cells as biological replicates.

**Literature basis:** Tirosh et al. 2016 (doi:10.1126/science.aad0501);
Badia-i-Mompel et al. 2022 (doi:10.1093/bioadv/vbac016);
official [Scanpy scoring](https://scanpy.readthedocs.io/en/stable/generated/scanpy.tl.score_genes.html),
[cycle](https://scanpy.readthedocs.io/en/stable/generated/scanpy.tl.score_genes_cell_cycle.html),
[ULM](https://decoupler.readthedocs.io/en/latest/api/generated/decoupler.mt.ulm.html)
and [Seurat](https://satijalab.org/seurat/articles/cell_cycle_vignette.html)
method descriptions were checked live. Full-paper browser access was restricted;
do not claim new paper-specific validation. Program scores are relative expression
summaries; predicted phases are neither a measured division rate nor proof of
G0/quiescence, malignancy, stress or product fitness.

**Files:** new package-local `exploratory_models.py` and `exploratory.py`;
integrate via `adapter.py`, reuse numerical loading in `method_runtime.py`;
update `_input_contracts.py`, P0-06 spec/card/README, schema registration/export,
affected stable documentation and `tests/test_p0_06_exploratory.py`.
No new package, Web workflow, dependencies, review wave or unchanged QC run.

**Execution (inline; existing isolated server worktree):**

- [x] Add synthetic registered-tool tests: all observations retained, finite
  method-separated scores, phase counts summing to n, null independent n and
  no gate measurements; expect the new input to be rejected before implementation.
  `PYTHONPATH=src python -m pytest -q tests/test_p0_06_exploratory.py`
- [x] Add the typed mode and minimal runtime; reject changed bytes, mismatched
  observation sets, ambiguous requested symbols, nonfinite/invalid raw counts, extra
  product-review inputs and incomplete lists. Persist not_assessed outputs for
  method/coverage failures without zero-valued fabricated phase counts.
- [x] Verify new behavior and directly affected old P0-06 mode boundaries,
  JSON Schema validity, repository policy and input immutability. Do not replay
  the full suite or independent review pipeline.
- [x] Execute the registered high-level tool on the existing genuine all-observation
  D28 view in a fresh private server output directory; preserve sessions,
  old receipts, raw inputs and live services. Record exact input/resource hashes,
  package versions, actual execution states and descriptive results.
- [x] Sync implemented stable facts and exact evidence to this plan and the existing
  Draft PR using the established public-safe publication boundary; no merge.


#### Task 27 engineering checkpoint

The initial ten fixtures had a missing request ID; after correcting that setup,
the registered new-input tests failed for the expected absent-schema/mode reason
(9 failures, with the unchanged old-mode refusal already passing).
The implemented descriptive route passed 16 scoped tests. A separate receipt test
then exposed the omitted cycle-specific control-size field, which was added;
the final new-mode run passed 17 tests with 116 existing upstream Scanpy
deprecation warnings. Raw-count versus explicitly normalized layer equivalence,
ignored alternate X/raw matrices, deterministic output, invalid count values,
complete observation retention, missing genes and independent method failure
are covered. These are synthetic engineering checks, not scientific validation.

Three contract/discovery checks passed. Four old-mode checks first stopped at
pinned v0.7 requests, then passed with current-version fixture routing. Four
further legacy/source-bound/integration checks passed. Existing v0.3 schema
payloads, old explicit projection specs and attestation rules are retained.
Only fixture/example versions and current result-envelope metadata were aligned.

Repository inventory checking exposed two already-committed curation files not
in the prior named allowance. Their exact candidate/license paths and the six
specific new exploratory implementation/schema/test files are now accounted for;
the baseline and general allowance were not increased. Policy and whitespace
checks passed. Formatting of the three new Python files preserved their syntax
trees. No unchanged broad suite, independent review wave, source notebook, QC or
cell-state computation was rerun. Genuine execution remains the next step.


#### Task 27 genuine-input identifier correction

The first isolated installed attempt stopped before measurement with
`gene_symbols_not_unique`; its failed ToolRun and unchanged-input receipts are
retained privately. The selected matrix has unique original feature IDs, while
some non-program symbols annotate more than one feature. Every selected S/G2M
symbol has one exact feature match. This is an identifier-resolution issue,
not permission to collapse counts or revise the selected DataView.

The [official Scanpy reader](https://scanpy.readthedocs.io/en/stable/generated/scanpy.read_10x_mtx.html)
supports a gene-ID feature index, and ULM accepts matching feature IDs in its
network. The bounded correction retains every original unique feature ID,
resolves only exact requested symbols through the input's own symbol column,
and records that mapping. Missing or ambiguous program symbols are separately
`not_assessed`; no alias substitution, first-match choice, summing, symbol
suffixing, feature removal or independent annotation service is used.
Non-program duplicate symbols stay as distinct input features in the control/
background universe and are reported. Existing product-bound modes retain their
original symbol uniqueness behavior. P0-06 patch version 0.8.1 distinguishes
this corrected execution from the failed 0.8.0 attempt.

The duplicate-background and ambiguous-target regression cases both failed with
the original blanket-symbol rejection, then passed with identity-preserving
resolution. The complete new-mode test file passed 19 cases (136 upstream
deprecation warnings). The final patch-version discovery, profile routing and
two identifier cases passed four focused checks. The corrected run will use a
new installed snapshot/output directory; the failed attempt is not overwritten.

#### Task 27 genuine installed measurement and publication checkpoint

The corrected P0-06 0.8.1 wheel was built from committed source and imported
from a fresh isolated installation. The owner-approved request used the existing
genuine selected DataView and the unchanged pinned Seurat lists, through the
registered high-level SDK. Scanpy program scoring, decoupler ULM, Scanpy cycle
classification and descriptive phase aggregation all returned succeeded.
Every selected observation was retained; both gene lists had complete, unique
feature matches. Aggregate JSON, per-observation Parquet and artifact-manifest
hashes were rechecked against the ToolRun. Row uniqueness, missingness and phase
count reconciliation were checked from the saved table, without rerunning methods.
Private identities, observation scale, measured values and receipts remain in the
private execution record, not this public plan.

The result is descriptive_only: independence unknown, independent n null,
state review pending, domain score null and score unavailable. Original QC
readiness remains limited; QC was not reassessed. Stress was not assessed
because no stress resource was selected. Shared-expression algorithms are not
independent confirmations, and phase labels are not a division-rate, quiescence,
purity, malignancy or product-acceptance result. The existing product-bound
modes and their scientific/attestation gates were not weakened.

The first failed identifier attempt is retained separately. Before/after
checksums confirm that original input bytes, QC profile, canonical QC receipt
and case session are unchanged. No notebook, QC or cell-state analysis was
rerun; neither live preview was restarted. This is genuine installed SDK
measurement, not a new Web conversation, Web result-card acceptance, automatic
P0-08/P0-09 domain integration or report release. The live preview still uses
its earlier snapshot.

At the publication checkpoint, previous public-head CI `07750ffc`
([run 34256051415](https://github.com/starvingarc/BRIDGE/actions/runs/34256051415))
completed with **1 failed, 2,213 passed, 66 warnings**; subsequent Web and
repository gates were skipped. The sole failure was an obsolete exact context-key
expectation that omitted the existing status-only clarification context.
That exact test was reproduced, then its explicit expected field and empty-context
assertion were aligned without changing runtime behavior or weakening the private-
value checks. The focused rerun passed; this is not full-suite or current-head CI
acceptance. Publication remains Draft and unmerged, with new-head CI separate.

### Task 28: Approved L2 descriptive marker evidence

**Owner approval (2026-09-09):** extend only the existing marker-evidence path
to L2 and check literature-derived candidate panels on the already selected
genuine input. Stay on the product-identity mainline; no new UI, independent
review wave, QC replay, label reassignment, purity estimate or freeze approval.

The existing card contract and checksummed reference snapshot already support
L2, but the runtime currently filters out every non-L1 card. Permit L1 and L2
cards explicitly allowed for shadow evidence; keep L3 and other uses excluded.
Retain existing coverage, insufficient-positive-gene and missing-negative-value
semantics. Marker averages remain descriptive, not classifiers or coexpression
tests, and must not change correlation-derived labels or release states.

Prepare a separate versioned candidate resource using the existing checksummed
snapshot contract in an isolated reference root. Copy the existing profile and
vocabulary bytes unchanged, update only the marker resource and candidate
manifest version/hash, and validate the derived snapshot. The fixed measurement
specification retains its logical reference ID; private provenance must bind
both the original and derived manifest hashes. Do not rebuild reference feature
selection from the added panels. Preserve the packaged L1 cards and all prior
reference/input bytes. Use Kee et al. (2017), DOI
10.1016/j.stem.2016.10.003, Figure 4 and La Manno et al. (2016), DOI
10.1016/j.cell.2016.09.027, Figures 4–5 to separate regional/context evidence
from neurogenic stage and mature DA context. Shared floor-plate markers and
NR4A2 are not sufficient identity evidence; mouse findings and human findings
must remain distinguished. Candidate panel names are review questions attached
to existing L2 states, not a claimed cross-atlas label mapping or a reviewed
state definition. Exact selected panels, source limitations and genuine
measurements remain in the private execution record.

Acceptance: first reproduce skipped L2 cards in focused dense/sparse numerical
and registered-tool tests, then verify the smallest implementation change.
Build/install the updated registered tool in isolation and execute a newly
authorized request against the unchanged selected input and existing QC lineage.
Verify card coverage, selected-observation retention, candidate/release states,
saved-artifact hashes and unchanged original input/session receipts. Record
actual measured evidence separately from scientific validation. No frozen
reference, signed gate, product-role declaration or qualified score is created.

#### Task 28 engineering checkpoint

Both dense/sparse numerical cases and the registered-tool case failed first
because L2 summaries/rows were absent. All three then passed after the one-line
L1/L2 allowlist correction; the original source-aware run and candidate-reference
refusal also passed (five focused checks, not a full-suite run). P0-02 patch
version 0.5.4 identifies the behavior change. Numerical assertions cover exact
means, observation order, gene coverage, missing negative values, unavailable
cards, excluded L3/unauthorized uses and unchanged shadow labels. Installation
and genuine candidate measurements are separate acceptance below.

#### Task 28 genuine installed acceptance

A wheel built from committed source was imported from a fresh isolated
installation. The separately owner-approved registered P0-02 0.5.4 request
succeeded on the original selected input and genuine saved QC products. Six
explicitly review-required L2 cards, representing four distinct gene panels,
were added in a private derived candidate snapshot. Shared panels attached to
two state questions are not separate independent evidence. All selected positive and regional-alternative genes were
covered; all selected observations were retained once per assessed card.

The original and derived reference manifests are version/hash-bound in private
provenance under the existing logical reference ID. Every profile matrix,
profile metadata file, vocabulary and packaged L1 card was preserved. The saved
cell-state evidence table and all old L1 marker rows equal the prior results;
the newly authorized marker measurement did not change labels. Artifact hashes
and original input, QC/profile/receipt, reference and session hashes were checked
after execution. No QC, source notebook, locked/OOD runner or Web service was
rerun or restarted. Private identities, counts, values and receipts are retained
only in the private record.

Saved-table summaries examine stage and regional context separately. This is
candidate descriptive evidence, not an independent source-state validation,
cross-atlas mapping or product-role approval. Means do not prove coexpression;
detection of any panel transcript is not a positive-state fraction. Alternative
regional context is not a validated exclusion rule. State review and typed
biological lineage remain missing, score stays shadow and domain score null.
No target purity, new state assignment, freeze signature, product acceptance,
Web result-card acceptance or downstream gate-facing measurement was created.

The three new RED/GREEN cases and two directly affected boundaries passed
together; two registry/version checks, generated-card validation, repository
policy and whitespace checks are recorded separately. Unchanged broad suites
were not replayed. Prior public head `3366b240` completed
[CI run 34263687243](https://github.com/starvingarc/BRIDGE/actions/runs/34263687243)
successfully; that does not certify this new increment. Publication remains
Draft, with new-head CI, deployment and scientific approval separate.

### Task 24: Inline question/draft cards and the real next-stage route

**Question and scientific-draft consumers installed; bounded acceptance recorded in Task 25.**
Six initial scientific-card interaction tests failed for absent rendering/entry,
then passed. Two added stage/next-plan tests failed for absent stage rendering,
then passed with all affected question/intake/API cases (27 passed, four files).
Type-check and production build passed; the existing large-chunk advisory remains.
Scientific cards show actual source definitions, unknowns, editable role/stage
choices, exact confirmation, explicit revision and per-stage blockers. A separate
button prepares (not approves) the missingness check. Six backend revision cases
first failed for the absent endpoint, then passed in the 21-case candidate run.
These checks precede real-model/browser acceptance and preview installation.

Historical question-card verification:
Six new whole-App interaction tests first failed because no choice card was
rendered. The same six then passed, together with the affected intake and API
tests (19 passed across three files). Type-check and production build passed
using existing pinned dependencies in a private build copy. The build retains
its existing large-chunk advisory; no dependency or bundle-budget policy changed.
These are component/build checks, not browser, actual-model or installed acceptance.
The question card preserves the existing page layout and binds to its exact
assistant message. No new UI design, image assets or scientific run is included.


**Files:** Create web/src/components/ClarificationCard.tsx,
ScientificInputs.tsx and web/tests/clarification-card.test.tsx,
scientific-inputs.test.tsx; modify Conversation.tsx, api.ts, types.ts,
ProductIntake.tsx, intakeLabels.ts and styles.css only as needed.
**Interfaces:** ClarificationCard receives its persisted card, busy flag and
onAnswer/onCancel callbacks. ScientificInputs receives the current server draft
and onConfirm callback. api.answerClarification and api.confirmScientificInputs
return the normalized current Session. Cards attach to their recorded message,
not an unrelated floating panel.

- [ ] Add a real-component test using controlled HTTP: choices begin unselected;
  choosing an option does not write; Submit answers sends the exact card digest.
  Unknown is exclusive, free text is preserved, refresh restores the answer.
- [ ] Run the new browser tests to observe the missing card behavior.
- [ ] Implement accessible radio/checkbox groups, fieldsets, explanation and
  optional text entry. Show pending/answered/stale/cancelled states; render
  scientific choices and source references with explicit missingness. Confirming
  a draft does not approve an analysis. Route the next-stage button through
  actual server eligibility; preserve the manual input panel as an advanced
  existing route, not a second materializer.
- [ ] Verify stale/cross-session responses do not replace the active case, keyboard
  submission, mobile layout and single/multiple selection. Run affected tests
  and one production build using the existing installed Node runtime.
- [ ] Commit the verified Web consumer and API/type changes.

### Task 25: Isolated installation and genuine Web acceptance

The first isolated installed browser request reached the actual provider but
failed parsing: it returned the correct two assay choices plus an explicit
reserved "unknown" option, which the application already owns. A diagnostic
confirmed HTTP 200 and invalid_fact_options rather than an unavailable model.
Two transport regressions reproduced this exact duplication, then passed with
all 17 affected question tests (19 passed, two existing warnings). The narrow repair
validates and removes one reserved unknown option before normal question
validation; it does not map arbitrary IDs, remove the two-choice requirement,
select an answer or relax factual enums. Original preview and genuine receipts
remain untouched while this installed-path repair is verified.

The repaired isolated UI produced a real choice card and preserved separate
answer submission and fact confirmation. Another malformed provider attempt
before diagnostic capture remains unexplained, not counted as success. The
scientific-draft request then exposed an actual mixed-L1/L2 candidate with parent
citations and a numerator outside its denominator. Validation rejected it without
materialization. Source-specific constraints are now explicit in draft context;
shape/source failures receive at most one bounded correction, never relaxed
validation. Four initial source-correction tests failed for the absent recovery,
then passed with the 21 candidate cases (25 passed). Four additional mixed-level
shape cases passed; both transports and repeated-invalid termination are covered.
Two existing dependency warnings remain. Actual-model candidate acceptance is
still pending on this repair.

### Task 25 accepted increment and remaining scope

The final installed runtime is committed snapshot `3d8a06af`. Its wheel and
client were built without changing dependencies; installed package files and
client runtime sources matched their source snapshot. Eight final scientific UI
tests passed after a real RED regression caught a superseded card displaying
unsaved local edits. Type-check/build passed; the existing large-chunk advisory
remains. Earlier focused Python and client evidence is recorded above, not
represented as a fresh full-suite/CI run. The repository-policy check initially
failed because the approved increment's twelve concrete source/test/design files
were absent from its Web inventory. Adding exactly those paths (no blanket budget
increase) made the same check pass; diff checks also passed. Subsequent documentation
and inventory edits leave all installed runtime sources unchanged.

In the isolated browser, the configured model produced the assay question card,
then a valid source-backed scientific candidate. Answer submission, fact
confirmation, candidate revision and scientific confirmation were separate.
Source definitions and pending review were visible. Revision preserved both the
original read-only choice and the new pending choice. The final confirmed card
prepared a separate P0-08 approval card; desktop and narrow-layout screenshots
were inspected. No scientific tool was run in this isolated case.

The known idle preview was then replaced using the same configured credentials
and storage. Session backups and before/after hashes preserved existing sessions
and the author-data case; original QC/cell-state receipts and artifacts remained
byte-identical after the subsequent work. The genuine browser reopened the same
case, and the configured model now interpreted its canonical V2 E1 counts and
denominators without rerunning QC or cell-state analysis. Its explanation still
contains imprecise advice to revisit already-bound reference settings; this is
not accepted as a fully polished scientific interpretation.

The genuine draft retained unresolved roles and developmental choices rather
than inventing a source-supported decision. It was explicitly confirmed, then
missingness-only P0-08 was prepared and separately approved in the browser.
The actual canonical ToolRun succeeded and retained unassessed domain profiles,
null scores and unavailable score states. This is a genuine Web check of
missing evidence, not measured downstream science or a product verdict.
The result figures/tables rendered; the downloaded domain SVG and TSV matched
canonical bytes, and the display-redacted result matched its registered hash
while retaining the same states. Refresh retained the confirmed draft and
completed run. Private receipts, transcripts, screenshots and deployment
records stay outside Git.

**Done for this increment:** installed choice/review/revision flow, restored V2
interpretation, exact independent P0-08 approval, missingness-result display and
verified private downloads. **Still open:** genuine measured P0-03–P0-06 inputs,
typed lineage and biological-unit attestation, source review, product-specific
P0-09 compilation registries, and the P0-10/P0-11 verified report/export chain.
No scientific policy was fabricated, no PR was pushed or merged, and no public
report/export was created. The original full-chain goal is not marked complete.

**Files:** Stable behavior updates in docs/web-preview.md and docs/README.md;
execution evidence and current state in this plan. Runtime and Agent ownership
contracts are unchanged; no documentation-only duplication is added there.

- [x] Install the tested build in a separate acceptance runtime while preserving
  the currently running preview and immutable author-data case.
- [x] Use ordinary browser conversation, choice answers, draft confirmation,
  stage-plan approval and result navigation. Reuse valid canonical QC/cell-state
  receipts; approve a new run only for a genuine changed input or failed stage.
- [x] Read actual ToolRuns and rendered artifacts. Distinguish executed science,
  unavailable stages, checked reports and exported outputs. No offline analysis,
  synthetic fixture or manually authored JSON counts as genuine Web acceptance.
- [x] Verify actual missingness downloads; retain explicit unknown independence
  and all candidate/shadow states. Record changed tests, build, installation
  and genuine stage coverage; update stable docs for exercised behavior.
- [ ] Verify final report bindings and public export once real compilation
  policies and the remaining measured-stage prerequisites are supplied.
- [x] Leave PRs unmerged and private data unexported except for the explicitly
  approved allowlisted report delivery. State any unmet scientific prerequisites.

## Task 1: Exact staged Web execution and truthful capabilities

**Files:** Modify src/bridge/web/app.py, src/bridge/web/provider.py, src/bridge/web/__main__.py, tests/test_web_service.py. Optional create src/bridge/web/stages.py for request/materialization helpers; do not grow a generic plugin framework.
**Inputs:** Existing Settings, Service session, registered uploads, current P0-01 canonical ToolRun, installed ToolRegistry, configured existing P0-02 reference catalog.
**Interface produced:**
- Settings adds optional cell_state_measurement_spec_ref: str | None = None, loaded from BRIDGE_WEB_CELL_STATE_MEASUREMENT_SPEC_REF. Existing reference-root/candidate runtime environment and QC catalog remain the toolkit authority; no biological default is selected.
- POST /api/sessions/{sid}/inputs accepts only {upload_id: 32-hex string, source_family_id: bounded nonblank source-family identifier}. This is local, authenticated input, not provider text.
- Public Upload adds optional source_family_id. Public Session adds plan_history: Plan[] and capabilities: ToolCapability[] with defaults for existing saved sessions.
- ToolCapability = {tool_id, label, state: ready|needs_input|not_connected, reason_codes: string[]}. Names/versions/capabilities must match actual registry/runtime. Not-connected materializers must not masquerade as ready when input files are absent.
- Provider Action additionally permits prepare_analysis with tool_id in P0-02/P0-12 and no arbitrary paths, code or parameters. Existing reply/prepare_qc stay compatible.
- Public PlanStep additionally permits partial, cancelled and blocked; Plan may be partial/cancelled. Preserve actual execution state and artifacts.

**Behavior:**
- P0-02 requires a real registered completed QC outcome for the selected upload, a supplied source_family_id and configured MeasurementSpec/reference capability. Create a fresh wrapper around the same exact file/checksum, preserving original assay/count semantics and adding real qc_profile_ref/DataView/parent SHA from canonical QC artifacts. Register canonical QC refs in a private per-instance toolkit QC catalog. Check missing artifacts explicitly. Do not force a V3 result or claim normalized/full-profile readiness.
- Use a fresh immutable CaseInputBundle/version for the enriched stage asset; call PlanBuilder with explicit requests and include_input_qc=False. Build the final plan before showing its digest. New stage requires new exact approval.
- P0-12 no-graft requires an explicit user declaration/request of no graft data. Its ToolRequestV2 has zero assets and zero object_inputs. The current product session's existing upload bundle supplies planner context only; never insert it into the P0-12 request. No graft expression upload is required. An empty conversation lacking a product upload may ask to establish the product analysis context, never for a graft matrix.
- Retain canonical ToolRuns under the session private root with hashes; never use display-redacted artifacts as downstream scientific inputs.
- Retain prior completed/failed/partial plans and receipts when proposing the next stage. Keep old approval invalid for new/modified inputs. Fact edits invalidate only mutable proposals, not historical evidence.
- Distinguish provider failure, input-construction blocker and tool failure. Keep all usable actual partial artifacts.
- Status-only provider descriptions must explicitly distinguish P0-12 no-graft from expression graft and must not invent method-level results.
- Preserve existing upload/auth/path/hash/retraction/restart protections and eight-upload/100-message/bounded-worker limits.

- [x] Add focused failing tests around the real Service seam using synthetic unit fixtures only.
```python
def test_prepare_analysis_accepts_only_connected_tool_actions():
    for tool_id in ("P0-02", "P0-12"):
        action = parse_action({"content": json.dumps({
            "action": "prepare_analysis", "tool_id": tool_id})})
        assert action.tool_id == tool_id
    with pytest.raises(ValueError):
        parse_action({"content": json.dumps({
            "action": "prepare_analysis", "tool_id": "P0-05"})})

def test_private_source_input_is_bound_to_registered_upload(client, tmp_path):
    sid = new_session(client)["id"]
    response = client.post(f"/api/sessions/{sid}/uploads",
        files={"file": ("synthetic.h5ad", h5ad(tmp_path, layer=True))})
    upload_id = response.json()["uploads"][0]["id"]
    saved = client.post(f"/api/sessions/{sid}/inputs",
        json={"upload_id": upload_id, "source_family_id": "source-family:unit-test"})
    assert saved.status_code == 200
    assert saved.json()["uploads"][0]["source_family_id"] == "source-family:unit-test"
    rejected = client.post(f"/api/sessions/{sid}/inputs",
        json={"upload_id": "0"*32, "source_family_id": "source-family:unit-test"})
    assert rejected.status_code == 404
```
Add the stage approval and zero-input no-graft assertions using the existing real-QC Service test fixture, so the tests exercise normal request construction and approval rather than a second executor.
- [x] Run focused tests, capture expected failing assertions.
- [x] Implement minimal typed stage handling, private receipts, truthful capabilities and provider actions.
- [x] Test missing QC artifacts/config/source, altered input bytes, unsupported tool selection, no-graft declaration, old saved sessions, partial outcomes, old-approval replay, metadata privacy and canonical-vs-redacted artifact use.
- [x] Run python -m pytest tests/test_web_service.py -q; record exact output; git diff --check; commit only assigned files.

## Task 2: Stage history, private source declaration and real tool status in Web

**Files:** Modify web/src/types.ts, web/src/api.ts, web/src/App.tsx, web/src/components/Conversation.tsx, web/src/components/PlanCard.tsx, web/src/components/StatusMark.tsx and existing frontend tests/style files only as needed. No dependency or lockfile changes.
**Consumes:** Task 1 public Session additions, POST inputs route, existing messages/approve/artifact routes. New fields are optional at the client boundary for compatibility; normalize them once.
**Produces:** User can supply a source-family identifier privately next to a registered upload, inspect completed stage history/current proposal, and see actual tool availability and partial/blocked states.

- [x] Add tests proving a completed QC plan remains visible after the next proposal, source input posts only the exact registered upload/identifier to inputs, and partial/blocked states never render Succeeded.
- [x] Preserve current understated layout: compact collapsible tool-chain status and stage history; do not list 12 redundant large panels or add a second workflow engine.
- [x] Source declaration is a bounded local form labeled Data source / experiment reference. Explain it is not sent to the model. No arbitrary server paths or JSON request editor.
- [x] Capability rows distinguish implemented tool packages from Web-connected stages. P0-03–P0-11 not_connected is visible, not just missing metadata.
- [x] Existing fresh-session upload, polling, refresh recovery, figure grouping, all-download inventory, bounded previews and mobile layout remain functional.
- [x] Run npm test and npm run build in web; record exact outputs; commit only assigned paths.

## Task 3: Integration, private real-data replay and documentation

**Files:** Root owns docs/web-preview.md, docs/validation/web_preview_20260905.md or one new bounded validation record, plans/README.md, this plan, scripts/check_repository.py and deployment-only private artifacts.
- [x] Integrate approved Task 1/2 commits, validate combined interface and update bounded repository file budget only for actual added files.
- [x] Document the new input route, stage approvals/history, P0-02 candidate boundary, no-graft zero-input behavior, still-unimplemented constructors and required private deployment configuration.
- [x] Build a wheel, install to a new private target, verify imports come from that installation rather than source, run focused suite and 12-tool describe/input-contract smoke.
- [x] Start a separate authenticated loopback preview using the current configured provider. Do not alter the live instance.
- [x] Server browser flow: new conversation -> real H5AD -> explicit assay/counts -> QC approval -> privately entered source metadata supported by actual source records -> P0-02 approval -> real artifacts -> explicit no-graft -> P0-12 approval -> verify no graft expression entered request -> follow-up -> refresh -> desktop/mobile screenshots -> registered download hashes and SQLite/ToolRun receipts.
- [x] Record each actual execution, actual partial/scientific state, missing V3 or lineage, and P0-03–P0-11 not executed. No 12/12 Web claim for this increment.
- [x] Collect full-chain blockers without silently changing P0-05 projection or scientific input ownership.
- [x] Run repository policy, knowledge validation, schema parity where touched, git diff --check and public-content privacy scan.
- [x] Independent exact-head review, focused correction, required GitHub gates before any requested merge/deployment; preserve live state and all private versioned evidence.


## Task 4: Contract-driven Web access for all registered tools

**User continuation:** Implement Web access first for every P0 tool. Missing real source facts constrain real-data acceptance, not implementation of the input/approval/execution seam.

**Files:** src/bridge/web/app.py, src/bridge/web/provider.py, tests/test_web_service.py; add src/bridge/web/inputs.py and tests/test_web_inputs.py for the focused input-binding responsibility. The observed successful-tool/reason-code seam also permits a narrow fix in src/bridge/workflow/executor.py and tests/test_workflow_runtime.py: successful execution events carry no execution-failure reasons; the unchanged canonical ToolRun retains scientific reason codes and its content-bound receipt. Do not change event Schemas/guards or partial/failed behavior. No toolkit, module, Schema, dependency, renderer-authority or scientific-policy changes.

**Frozen HTTP interface (also consumed verbatim by Task 5):**
- GET /api/sessions/{sid}/analysis-inputs returns {tools: [{tool_id, label, input_contract}], objects: [{id, label, schema_ref, object_version, source, producer_tool_id}], assets: [{id, label, declaration}], selections: {tool_id: selection}, measurement_specs: [{id, label}]}. producer_tool_id and declaration may be null. source is user_upload, package_resource, system_resource or tool_output. This authenticated browser response contains no paths, hashes or scientific payloads.
- A selection is {tool_id, mode_id: string|null, asset_ids: string[], object_inputs: [{role, input_id}], measurement_spec_ref: string|null}. POST /api/sessions/{sid}/analysis-inputs saves this exact object and returns the normal Session. Saving an incomplete selection is allowed (shows needs_input); unknown role/mode/ID/schema/version and excess cardinality are rejected. No parameters, tool versions, request IDs or output paths accepted from the client.
- POST /api/sessions/{sid}/analysis-inputs/objects is multipart file plus query parameters tool_id, mode_id, role, schema_ref, object_version. Only a current contract role's scientific JSON object is accepted, not a ToolRequest/ToolRun. Return the normal Session; GET analysis-inputs supplies the registered opaque object ID. Limit each object to 2 MiB, total registrations to 128; reject duplicate JSON keys, non-finite numbers, non-object roots and depth over 32.
- POST /api/sessions/{sid}/analysis-inputs/assets accepts {upload_id, assay, matrix_location, matrix_semantics, input_level, metadata: object}. It explicitly declares one already uploaded H5AD; paths/checksums/asset IDs remain server-owned. Validate via CaseInputAsset and registered matrix locations. Metadata is bounded JSON (32 KiB) restricted to current asset-contract keys and the published biological-unit-lineage/source declarations. Never infer sample/capture/independence, normalization or weights. Return Session.
- POST /api/sessions/{sid}/prepare-analysis accepts {tool_id} and constructs a proposal only. It never approves/runs implicitly. Ordinary chat prepare_analysis supports every registered P0 tool and uses the same saved selection. Retain existing conversational QC, candidate P0-02 and explicit zero-input no-graft shortcuts when no explicit selection exists.
- Existing saved sessions tolerate missing additions; do not put private objects/selection values into model context. Provider receives only bounded tool/mode readiness and terminal execution states.

**Input binding and integrity:**
- Derive modes, roles, versions, cardinalities, asset constraints, random seed and envelope from ToolRegistry.describe_input. Keep all current modes discoverable. A missing source produces a named needs_input reason, not stage_materializer_not_connected.
- Strict-parse and validate against packaged Schema with no remote Schema fetch; preserve scientific object content/version. Server chooses immutable local object path, hash and StructuredInputRef. Do not silently author scientific objects.
- Add package-owned options for the existing P0-08 gate rule and the P0-10 release-contract claim policy/statement registry using exact existing loaders/canonical bytes. Reuse the already configured P0-02 reference resolver to expose its exact manifest/vocabulary as system_resource when compatible, preserving and verifying the existing bundle. No new catalog framework, client paths or scientific defaults.
- Register reusable JSON outputs directly from checksummed canonical same-session ToolRuns, never display-redacted copies. Preserve the original artifact location and its sibling bundle. Validate receipt hash, confinement beneath that session runs directory, regular owner-controlled files, no symlink at any component, artifact hash and Schema/version. Recheck immediately before planning and execution; reject cross-session IDs.
- Caller JSON must not select arbitrary filesystem/network resources. For uploaded nested file descriptors, only explicit opaque references upload:<id> or artifact:<id> are allowed in path fields; resolve from the same authenticated session and derive/check the paired checksum. Relative/absolute file paths, URLs used as file locators, traversal and unknown IDs fail closed. Reject uploaded case/comparison graph manifests; only verified canonical producer graph bundles may fill these roles. Scientific literature/logical reference strings are not file locators and remain unchanged.
- Graft expression descriptors may use path=upload:<id> with remaining genuine biological/matrix declarations; artifact-audit manifest entries may use path=artifact:<id>. The server supplies real file/checksum bindings, never data values. Keep nested source provenance and exact immutable dependency records; verify all referenced files before execution. If a current role cannot be safely bound, report the exact role/reason rather than executing a path-bearing object unchecked.
- Explicit selected assets are included in a fresh CaseInputBundle; object-only requests use the existing declared product-upload bundle as planner context only. Never insert context assets into an object-only/no-graft request.
- Build a fresh ToolRequest/V2 then current PlanBuilder, eligibility, exact approval, ToolExecutionPipeline and LocalWorkflowExecutor. All approved requests remain immutable. Edits invalidate mutable proposals only; history/artifacts survive.
- P0-07 comparison and all P0-12 modes are independent branches, not pre-transplant evidence backfill. No-graft needs an explicit user declaration or explicit mode selection confirmed in the proposal; zero assets/objects remains enforced.
- No automatic P0-05 soft-mass projection or report-draft authoring/authority claim. Supplied scientific objects remain supplied objects and normal tool authority checks remain binding.
- Keep code small: a focused input helper plus reused planning/execution; no nine duplicate stage handlers or second workflow engine.

**Acceptance:**
- [x] All twelve tools have a real construct/plan/approve/execute route; missing inputs are reported by contract role.
- [x] Focused tests cover mode/role/version/cardinality, strict JSON, same-session upstream receipt binding, nested locator confinement, mutation before execute, independent graft/comparison and old approval rejection.
- [x] Construct real requests and use real eligibility/runner in integration tests wherever fixture inputs exist; any isolated mocked seam is clearly separated from execution evidence.
- [x] Existing Web suite plus new input suite passes, diff check passes, commit assigned files only.

## Task 5: Compact analysis-input panel

**Files:** web/src/components/AnalysisInputs.tsx (new), web/src/types.ts, web/src/api.ts, web/src/App.tsx, web/src/components/Conversation.tsx, web/src/styles.css, web/tests/analysis-inputs.test.tsx (new), existing API/plan tests only as necessary. No dependency/lockfile change.

**Consumes:** Task 4 frozen HTTP interface above exactly. GET analysis-inputs is lazy-loaded when opening the panel and refreshed after successful mutations; stale responses from an old session must not overwrite current-session state.

- [x] Add one collapsed Analysis inputs panel, not twelve full-page forms. Tool/mode choices and required/optional named roles derive from server contracts.
- [x] For each role show compatible supplied/package/prior-tool object options and a bounded scientific JSON file upload; allow cardinality multiple selections where supported. No JSON request editor, paths, hashes, scientific-value text guessing or arbitrary tool parameters.
- [x] Offer registered H5AD selection and explicit assay/matrix/input-level declarations. Advanced metadata may be supplied as a JSON file parsed as an object, not a raw editor; no guessed sample or biological-unit facts. Keep normal H5AD chat upload and existing source form working.
- [x] Save selection and Prepare plan are distinct actions. A new/changed selection must be saved before Prepare plan; block double submission and busy-session edits. Existing explicit exact approval remains the only run action.
- [x] Show missing input reasons, source ownership and exact selected mode. Never imply available object choices mean scientific validity or full-chain success.
- [x] Keep compact responsive styles, accessible labels, real errors, history/results intact and no derived-state synchronization effects.
- [x] Frontend tests cover registry-driven modes/roles, compatible options, bounded uploads, API shape, session switching/stale response, save-before-prepare, busy state and error recovery; production build passes.

## Task 6: Integrated Web verification and handoff

**Owner:** Root. Reuse the existing isolated deployment and one PR; do not disturb the original preview.
- [x] Integrate independently reviewed backend/frontend, update repository file allowlist only for actual new files, and synchronize Web docs/input ownership/limitations.
- [x] Build and install a fresh wheel, verify installed imports and source/build byte correspondence, run focused cross-component and twelve-tool input-contract checks.
- [x] Server browser: fresh conversation, real upload, analysis-input selection/declaration/upload/reuse, plan approval, actual eligible tool runs, result figures/downloads, reload, follow-up and desktop/mobile interaction.
- [x] Prove all twelve routes against explicitly synthetic engineering fixtures where real source inputs are unavailable, separately from genuine real-data coverage. Do not use old ToolRequest replay or synthetic metadata as real-user data evidence.
- [x] Run the complete suite once on integrated head plus policy/knowledge/diff/privacy gates. Aggregate one final review with scoped corrections. The server result is 1,883 passed / 64 synthetic trust-fixture failures; retain that limitation and require the unmodified standard-runner CI before any merge.
- [ ] Update the same Draft PR with code/docs only. Keep actual data, resource identities/hashes/results and screenshots private; no merged/full-chain claim until corresponding gates actually pass.

## Task 7: Genuine-conversation declaration and readiness semantics

A fresh actual-provider Web conversation exposed two input-layer defects: unrelated missing-metadata statements retract the earlier QC declaration, and an unselected mode is described as though choosing a mode alone establishes data readiness.

**Scope:** src/bridge/web/app.py, src/bridge/web/provider.py and tests/test_web_service.py only. Root updates plan and validation docs. No scientific modules, Schemas, thresholds, lineage/soft-mass definitions, provider permissions, release authority or dependencies.

- [x] Add failing reproductions using the actual conversation's generic missing sample/batch/product-context statements. Clearly unrelated absence must not revoke existing assay/count declarations or prevent canonical QC reuse. Keep explicit cancellations, assay/count retractions and mixed unrelated-plus-retraction messages fenced. Never infer a new declaration from a negative or ambiguous message.
- [x] Provide bounded package-derived mode IDs and required-role names in safe provider context so the model cannot treat input_mode_required as proof that other inputs exist. No scientific payloads, selected values, source identifiers, paths or hashes. State needs_input means not executable yet; no invented modes or unsupported comparison fallback.
- [x] Run focused tests, all Web/input/workflow tests, and diff checks remotely; preserve all prior retraction/approval tests and immutable history.
- [x] Independently review the scoped diff, install the exact updated wheel in the isolated candidate, and rerun the same fresh genuine-data/current-provider conversation. Report achieved tools and remaining genuine full-chain blockers separately.

## Task 8: Source-bound module inputs through the existing Web seam

**Scope:** Integrate the separately reviewed P0-05 hard-count and P0-06 source-bound module branches in this isolated Web branch for combined validation. Root owns merge conflict resolutions and docs. The implementation worker modifies src/bridge/web/inputs.py and tests/test_web_inputs.py, plus only the existing test_web_service.py mode-discovery expectation made stale by the integrated P0-05 mode. No scientific module, Schema, dependency, frontend, provider or trust-policy changes.

**Named locator contract:** For tool_id=P0-06, mode_id=method_runtime_source_bound, role=process_method_input, schema_ref=bridge://schemas/process-method-input/v0.2 and object_version=0.2.0 only, bind exactly the direct source_observations.artifact_manifest_path/artifact_manifest_sha256 and source_observations.evidence_path/evidence_sha256 pairs. Each path must be artifact:<same-session opaque ID> and resolve through an existing canonical ToolRun receipt, never a display projection or upload. Both artifacts must belong to the same P0-02 producer receipt; retain supplied producer metadata unchanged and let normal module eligibility verify its correspondence.

- [x] Write failing tests before changing input binding: valid same-session canonical source pair reaches packaged JSON validation; wrong role/Schema/mode, raw path/URL, upload locator, wrong/missing checksum, cross-session ID and mixed producer receipts fail closed. A checksum may be blank/null only as the existing binding convention; its key must exist and the server derives the actual digest. Object field order must not affect binding.
- [x] Reuse current receipt/file checks and dependency records. Preserve all non-locator scientific values. Recheck both canonical dependencies before planning/execution, including replacement of either file or its receipt.
- [x] Keep the existing plain path + sha256/checksum behavior for graft uploads and export audit unchanged. Other named file locators remain unsupported. No generic arbitrary *_path resolver or alternative request API.
- [x] Add a bounded synthetic integration check for the P0-05 hard_count_accounting route and P0-06 new source descriptor. Clearly distinguish fixture execution from genuine-data acceptance.
- [x] Run focused changed tests then existing Web/input/workflow tests once using the already configured server startup trust policy. Record pre-existing warnings separately; do not weaken/reset trust guards. Root owns broader installed-wheel and browser acceptance.
- [x] Independently review the narrow change, then root installs and checks the combined wheel on an isolated private instance. Keep genuine metadata unknown where not confirmed and report actual tool calls, including blocking/refusal outcomes; no simulated attestations.

## Task 9: Superseded declaration-parser repair

**Status:** superseded by Tasks 10–12, not an outstanding task. Earlier
phrase/negation patches did not provide a reliable correction contract. The
approved replacement is explicit staged input changes and confirmation, with
immutable historical evidence. The initial-intake remainder is Task 19; do not
resume the abandoned pattern-patching or review loop.

## Approved conversation control contract

The owner approved this interaction on 2026-09-07: stopping takes effect immediately;
input corrections pause subsequent execution, show the exact change and apply only
after confirmation; ordinary conversation does not mutate committed metadata.
Task 9's regex approach is superseded, not accepted. No fourth parser patch.

Frozen Web-only HTTP seam for Tasks 10/11:
- Session adds input_review_required: boolean (default false), pending_input_change: null or
  {id: string, digest: string, kind: "asset"|"source", upload_id: string,
   changes: [{field: string, before: JSON value, after: JSON value}]}.
  This is authenticated browser data only; values never enter provider context.
- Session status additionally permits stopping. It means the stop was acknowledged,
  further work is fenced, and an already-running non-interruptible step is settling.
- POST /api/sessions/{sid}/stop with {} works while thinking/running/awaiting_approval.
  It returns Session immediately, does not wait for model/tool completion, and never
  revokes declarations or deletes historical receipts/artifacts.
- POST /api/sessions/{sid}/inputs and POST /api/sessions/{sid}/analysis-inputs/assets
  keep existing payloads but stage an exact pending change instead of applying it.
  They set input_review_required and fence future approvals/proposals. The current
  declared values remain unchanged. An identical declaration may be a no-op.
- POST /api/sessions/{sid}/input-change/confirm with {change_id, change_digest}
  checks the current pending change and pre-change input revision, then commits it.
  Stale/cross-session/replaced changes fail 409. This does not approve or run a plan.
- POST /api/sessions/{sid}/input-change/discard with {change_id, change_digest}
  discards that exact proposal, preserves committed input and restores planning
  availability only when no unresolved chat correction remains.
- POST /api/sessions/{sid}/input-review/keep with {} is explicit confirmation
  to retain current declarations after a chat-triggered review with no pending
  exact edit. It does not execute or revive old plan approvals.
- A normal provider reply never changes committed input. New bounded provider
  action {action:"review_inputs",text:"..."} pauses future work and directs the
  operator to the existing input panel. The model cannot propose arbitrary metadata
  values. Actual field changes come from the private forms and are then confirmed.
- Ordinary chat cannot clear input_review_required. While reviewing, chat remains
  possible but prepare-analysis/approve are blocked with input_review_required.
- An explicit stop button bypasses busy controls. A small exact whole-message stop
  command set may route directly to the same stop operation without a model call;
  ordinary words such as "not all biological replicates" must not be control commands.
- Initial explicit QC chat can still propose an exact counts/assay plan, but must
  go through the provider action and current positive declarations; no pre-provider
  counts shortcut on a message that asks to wait. Execution retains exact approval.
- Keep current authentication/CSRF/bounds, source ownership, immutable tool receipts,
  uploaded scientific content and provider privacy boundary. No scientific API,
  Schema, workflow-engine redesign, dependency or release-state changes.

## Task 10: Explicit Web control and pending declaration backend

**Files:** src/bridge/web/app.py, src/bridge/web/provider.py, src/bridge/web/inputs.py
only as required, tests/test_web_service.py and tests/test_web_inputs.py.
One focused src/bridge/web/control.py helper is allowed only if it removes/control
isolates the state responsibility; no generic policy or parser framework.
Root owns docs and shared policy. Follow the frozen contract above verbatim.

- [x] Add failing behavioral tests for ordinary negative follow-ups, paused correction,
  unchanged committed declarations before confirmation, exact/stale/cross-session
  confirmations, keep/discard, and explicit initial QC plus separate plan approval.
- [x] Remove negation-driven declaration_start mutation and history retraction scans;
  committed/confirmed metadata, not ordinary chat, determines invalidation.
- [x] Implement immediate stop and stale-worker fencing for thinking and execution.
  Existing executor.cancel holds a lock during an in-process tool call: do not call
  it synchronously from HTTP while work runs. Stop future claims immediately; retain
  actual in-flight outcome/receipt honestly, settle then cancel queued workflow work.
  A late model response/error cannot restore a proposal or overwrite the stop state.
  Do not hold service.lock across provider/tool calls or create a second executor.
- [x] Keep restart state fail-closed, enforce review gate at direct APIs as well as
  provider actions, and preserve historical outputs across stop/correction.
- [x] Run focused RED/GREEN tests then the existing Web/input/workflow suite once
  with the already approved trust pins. Commit assigned paths, self-review and report.

## Task 11: Compact stop and declaration confirmation UI

**Files:** web/src/types.ts, web/src/api.ts, web/src/App.tsx,
web/src/runtime/BridgeRuntimeProvider.tsx, web/src/components/Conversation.tsx,
web/src/components/AnalysisInputs.tsx, web/src/components/StatusMark.tsx,
web/src/styles.css and covering web/tests only. One focused InputChangeCard.tsx
component allowed. No dependencies/lockfiles, backend or scientific changes.
Consumes Approved conversation control contract verbatim. Root owns docs/policy.

- [x] TDD for visible stop while busy, stopping feedback, exact before/after changes,
  confirm/discard/keep-current requests, stale-session response protection and
  blocked plan approval/prepare while input review is unresolved.
- [x] Use one compact accessible confirmation card, existing input forms for edits,
  and a stop control reachable during thinking/running/awaiting_approval.
  Show that already-running work may still finish, while later work is stopped.
- [x] Source/asset save stages a pending change, not a completed save. Allow input
  editing and chat while reviewing, but no prepare/approve until it is resolved.
  Existing selections and result/history/download UI remain intact.
- [x] Handle input_review_required-only state with edit guidance and explicit
  keep-current confirmation. No scientific-value construction, auto-confirm or
  browser-local second workflow state machine.
- [x] Run focused RED/GREEN then npm test and production build once remotely.
  Report existing warnings separately, commit assigned files, self-review.

## Task 12: Integrated control verification and genuine continuation

**Owner:** Root. Tasks 10/11 run in separate server worktrees from one base;
the user's explicit parallel implementation preference overrides serial-only
implementation guidance. Shared HTTP is frozen above; root integrates once.

- [x] Review each task once, fix concrete Important/Critical findings, integrate
  disjoint changes and update Web documentation/repository file budget if necessary.
- [x] Build/install exact combined wheel and client; verify tool discovery,
  changed suites, policy/diff and no private content in tracked changes.
- [ ] Fresh server browser/current configured model/genuine upload: explicit
  declaration review -> exact confirmation -> QC -> ordinary follow-up -> P0-02
  request; stop/correction/refresh/desktop/mobile checked separately as needed.
- [x] Preserve every actual ToolRun, conversation, figure and failure privately.
  Owner-confirmed independent cultures are recorded separately from still-unknown
  pooling, cross-timepoint and scientific definition facts; never fabricate receipts.
- [x] Report actual coverage and remaining input blockers. Existing live services
  stay untouched until the isolated candidate passes. No automatic main merge.

### Reply-envelope alignment found during genuine acceptance

A configured provider returned HTTP 200 with whitespace-only content for an ordinary
follow-up. Replaying the same safe context with the reply-envelope instruction
first produced a valid typed action. Keep JSON mode, the existing action validator
and all privacy/approval boundaries; clarify the existing prompt rather than add a
provider framework, permissive text parser or retry loop. Installed revision
`c9f8df55` still failed ordinary browser follow-up despite successful direct
replays; this is not a proven reliability fix. A history-envelope experiment also
failed and was not deployed. Keep the conversational acceptance box open.

### Input-column alignment found during genuine acceptance

The Web declaration allowlist omitted existing optional `sample_id_column`,
`capture_id_column` and `gene_symbol_column` fields consumed by P0-01/P0-02.
Accept only these existing selectors through the current exact-confirmation route;
keep arbitrary metadata rejected. Reuse request construction and its test helpers.
No new framework, scientific policy, dependency or tool API is introduced.
Verify the unchanged column names reach the approved request, then repeat the
real-input conversation from its paused correction. Retain the failed run.

### Task 12 verification outcome

Installed revision `a812b661` passed 137 Web/input/workflow tests. Revision
`c9f8df55` passed all 86 Web-service tests; unchanged input/workflow sources retain
the preceding baseline. All 350 packaged source files matched. Discovery, 24 CLI
interface checks, knowledge, figures, policy and diff checks passed. The complete
client tree and built bytes match `428ba2e6`, whose 50 tests, typecheck and build
passed; no duplicate client build was needed.

Genuine resumed and fresh browser inputs reached successful P0-01 and P0-02
canonical outcomes after exact declarations and separate approvals. Ordinary
negative follow-up preserved QC; input review and explicit keep-current worked.
Subsequent explanatory replies still failed at the real provider boundary. A
separate stop/refresh/layout/download inspection passed without replacing those
failed conversations. This is partial genuine acceptance, not 12/12 or provider
reliability. Exact inputs, receipts, screenshots and failures remain private.
No GitHub update, merge, scientific promotion or original-service replacement
was performed.

## Full-chain continuation conditions

- Genuine source metadata and explicit owner assertions establish biological-unit relationships and product/process context.
- Reuse the integrated P0-05 hard-count and P0-06 source-bound modes where eligible. Source-backed candidate role/window configurations require review; do not turn unavailable soft mass into probabilities or relabel source conflicts.
- Remaining materializers read only declared dependencies, and all real required artifacts exist.
- Two genuine product cases/design support comparison; expression-graft requires actual specimen/animal/timepoint/linkage data.
- Only then can fresh browser tests count the corresponding branches toward 12/12 actual tool coverage.



## Approved result-interpretation design, 2026-09-07

The owner approved sending bounded aggregate analysis summaries to the configured
external model, excluding raw matrices, observation-level records, sample
identities and private paths. This changes only the explicitly opted-in isolated
deployment. Default deployments remain status-only. Aggregate biological results
remain controlled data; this permission is neither publication nor anonymous-data
certification.

Reuse the existing canonical-input verification, packaged vocabulary, strict
Action parser, exact plan approval and local executor. Build provider context
from field allowlists, not redaction of arbitrary result JSON. The first
independently testable increment projects the latest canonical P0-02 V3
composition and reconciliation evidence. Other modules remain explicitly outside
this first projection; unsupported evidence is never guessed. Later increments
will connect profile-driven candidate inputs, packaged knowledge retrieval and
claim-verified reporting, without replacing the scientific tools.

The agent must derive source-backed candidate assessment configurations for
review, not require the owner to predetermine cell-role conclusions or author
scientific JSON. The owner supplies irrecoverable experimental facts and product
intent. Shared intended target/stage does not imply identical observed outcomes;
additional cell types are not automatically unacceptable.

## Task 13: Opt-in canonical aggregate evidence in conversation

**Files:** Create src/bridge/web/evidence.py and tests/test_web_evidence.py.
Modify src/bridge/web/app.py (Settings and think only),
src/bridge/web/__main__.py (startup option only), and
src/bridge/web/provider.py (context interpretation instructions only).
Root owns docs/decision-log.md, docs/privacy-and-provenance.md,
docs/web-preview.md, plans/README.md, this plan and scripts/check_repository.py.
No frontend, toolkit, scientific package, Schema, dependency or provider wire
protocol change in this task.

**Global Constraints (binding for this task):**
- All project code, tests, builds and data remain on the designated server workspace.
- No raw matrix, observation-level row, sample/source identity, private path,
  credential, private hash, arbitrary result string or source-family value enters
  the model evidence context. Never serialize the whole result or a recursive
  sanitizer output.
- Aggregate sharing is disabled by default and enabled only by a strict
  deployment startup boolean after owner authorization. HTTP/model messages
  cannot enable it.
- Preserve candidate/shadow and domain_score=null; preserve denominators,
  unavailable, not_assessed, unknown, conflicts and actual execution states.
- Reuse Inputs.verify, packaged typed models/vocabulary, strict Action parsing,
  exact approvals and the existing executor. No new dependency or general framework.
- Retain old sessions, inputs, artifacts and receipts. Do not restart any service,
  call a real provider, publish, push or merge in this implementation task.
- Root alone owns shared policy and documentation. Worker edits only listed
  source/test files and its private report.

**Interfaces:**
- Settings.share_result_summaries: bool = False; reject non-bool values in
  __post_init__. __main__ reads BRIDGE_WEB_SHARE_RESULT_SUMMARIES, accepting
  exactly unset/0/1 (unset and 0 disable; 1 enables), otherwise startup fails
  with invalid_server_configuration. No URL inference or default opt-in.
- evidence.build_result_context(inputs, state) -> tuple[dict, dict] returns
  (model_summary, private_binding). It does not call the model, mutate state,
  open raw matrices or execute a tool.
- Service.think calls this only when enabled and input_review_required is false.
  It adds result_summary and results_sent_to_model to the existing context.
  The flag is true only when a valid supported summary is actually supplied.
  Save the exact summary and private binding in a per-user-turn private session
  field _result_contexts keyed by the current user message id; retain at most 24
  entries. No new public Session/API field is required.
- The private binding maps a stable-for-this-turn E1 evidence alias to canonical
  input object id, receipt file/hash and artifact id/hash. None of these private
  values enters result_summary. Repeated calls on unchanged state are deterministic.
- Track the resulting assistant message ID in the same private turn audit.
  When no valid summary is shared (including disabled sharing or input review),
  omit prior result-bearing assistant messages from provider-bound history only;
  retain the visible saved conversation. Test enabled-to-disabled and
  enabled-to-input-review transitions against the actual outgoing HTTP payload.

**Projection contract:**
1. Select the latest canonical P0-02 receipt recorded as succeeded or partial
   first, then its registered tool_output object with schema_ref
   bridge://schemas/cell-state-evidence-profile/v0.3. Do not choose by browser
   selection, filename guessing or supplied labels. Deduplicate identical
   artifact hashes. A missing, unsupported or invalid latest profile must not
   fall back to an older producer. No supported object returns state
   not_available without data; invalid canonical evidence returns state
   unavailable with the fixed code result_evidence_invalid, never exception text.
   This is historical evidence for that completed run's exact selected DataView,
   not evidence about a later upload or changed declaration.
2. Verify it with Inputs.verify and parse CellStateEvidenceProfileV3. Check its
   producer_run_ref and producer_tool_version against the exact verified receipt.
   Use existing strict_json/checked_bytes for that receipt; never weaken path,
   ancestor, checksum or structured-input guards.
3. Return only fixed keys: state, evidence_ref E1, tool_id P0-02, execution_state,
   n_observations, denominator_scope selected_data_view, composition_state,
   open_set_state, calibration_state, score_state, domain_score null,
   composition and reconciliation. All states come from typed enums/Literals.
   Counts must be finite, nonnegative integers; n_observations > 0. No free-text
   warnings, assay names, reference labels, IDs, hashes, gene lists or program
   dictionaries are projected in this first increment.
4. composition includes consensus_supported_only records only, with label_level,
   label, count, fraction, denominator and state_evidence_state. Labels must
   exactly match the corresponding level/state in the packaged public annotation
   vocabulary. Load the existing YAML with its established loader/resource API;
   do not duplicate the vocabulary or adopt custom labels. Unknown labels make
   the whole summary unavailable; do not omit counts or rename identities.
5. reconciliation includes all reconciliation_state records, never source_specific
   rows. Its label allowlist is the producer's existing reconciliation state enum
   or constant; reuse the authoritative definition. If no exported definition
   exists, use only the exact currently implemented fixed state names verified
   in producer code and test unexpected labels fail closed. Preserve all rows;
   do not pool or sum across source-specific records.
6. At most 128 composition+reconciliation rows and 32 KiB encoded summary. If
   either bound would be exceeded, return unavailable with result_summary_limit;
   never truncate denominators/partition rows. No prefix-only apparently complete
   summary. Non-shadow composition retains its declared unavailable state and
   empty records, not numeric zeros.
7. The model may interpret only supplied evidence and cite E1, state uncertainty
   and selected-view scope, and distinguish reference support from released
   cell identity, purity, efficacy, maturity or a product ranking. When no
   summary exists it cannot assert findings. This is explanatory conversation,
   not P0-10 verified report generation. Existing control/action restrictions
   and no metadata mutation remain unchanged.

**Test and implementation steps:**
- [x] Write failing focused tests using real Inputs/Service and existing canonical
  fixture helpers, mocking only the external HTTP model transport. Include an
  independently hand-checked V3 partition, e.g. 8/10 consensus and 2/10 source
  conflict; include source-specific rows but verify they never enter the summary.
  Example consumer assertions:
```python
summary, binding = build_result_context(service.inputs, state)
assert summary["n_observations"] == 10
assert summary["composition"][0]["count"] == 8
assert summary["composition"][0]["fraction"] == 0.8
assert sum(row["count"] for row in summary["reconciliation"]) == 10
assert summary["domain_score"] is None
assert summary["evidence_ref"] == "E1"
assert binding["E1"]["artifact_id"] == canonical_artifact_id
```
  Verify private sentinel strings in source IDs, names, paths, hashes, free-text
  warnings and nested raw result data are absent from the actual outbound HTTP
  request, while numeric evidence reaches it when enabled. Defaults and input
  review send no summary. Tampered receipt/artifact, false producer identity,
  unknown public label and row/byte overflow fail closed without provider leaks.
  Check the private turn binding survives reload without entering public Session.
  Test strict startup configuration through the existing main entrypoint.
- [x] Run the focused tests before implementation and record the expected RED
  assertions, not import/fixture/environment errors.
- [x] Implement the minimal projection and guarded Service context integration.
  Intended call shape (adapt only local names, not semantics):
```python
if self.settings.share_result_summaries and not state["input_review_required"]:
    summary, binding = build_result_context(self.inputs, state)
    context["result_summary"] = summary
    context["results_sent_to_model"] = summary["state"] == "available"
```
  Save the audit record under the same control epoch before the provider call;
  an intervening stop still fences all late model actions.
- [x] Run tests/test_web_evidence.py, tests/test_web_service.py and
  tests/test_web_inputs.py with the existing approved startup trust configuration.
  Report the exact output and warnings. Preserve the known full-suite trust-fixture
  baseline; do not change pins, permissions, ownership, skip tests or claim the
  full repository suite passed. Run git diff --check.
- [x] Self-review, commit only the assigned source/tests, and write the private
  task report with RED/GREEN commands, outcomes and limitations. Independent
  review by the controller is required before deployment.

Task 13 source acceptance: the scoped Web suite passed before the row-limit
fix; the final focused projection suite passed after it. Independent review and
scoped re-review closed the row-limit defect and missing reconciliation test.
Installed-package and actual-model browser acceptance remain separate gates.


## Task 14: Explicit native action protocol for the authorized fallback

**Files:** Modify src/bridge/web/provider.py, src/bridge/web/app.py (Settings
validation only), src/bridge/web/__main__.py (startup setting only) and
tests/test_web_service.py. Root owns documentation/plan/policy. No scientific
package, Schema, frontend, evidence projection, dependency or executor change.

**Goal and evidence:** The configured primary JSON-compatible service and the
authorized fallback have different observed structured-output behavior.
Status-only private probes of one combined Action function failed both analysis
proposals because the model added forbidden text. Four action-specific function
schemas derived from the existing Action fields passed six bounded cases:
original failed reply, analysis proposal twice, review, wait and QC proposal.
This qualifies a small adapter for testing, not a reliability or browser pass.

**Global Constraints (binding):**
- All project code, tests, builds and data remain on the designated server workspace.
- Keep the existing default JSON provider behavior and Task 13 opt-in evidence
  boundary. No endpoint guessing, automatic parser switching or fallback retry.
- Native calls represent reply, review or unapproved plan proposals only; they
  cannot execute scientific tools, authorize metadata or bypass exact approval.
- Reuse the current Action validator, field definitions and one httpx request.
  No regex/XML/DSML parser, token-budget increase, retry loop or new dependency.
- Never retain model reasoning content or expose credentials, raw provider
  payloads or private data in diagnostics/public Git.
- No service restart, real model call, push or merge by the implementation worker.

**Interfaces and behavior:**
1. Settings.model_action_protocol: Literal["json", "deepseek_tools"] = "json".
   __main__ reads BRIDGE_WEB_MODEL_ACTION_PROTOCOL defaulting to json.
   Invalid startup values fail with invalid_server_configuration.
2. parse_action(message: dict, protocol: str = "json") -> Action. Existing callers
   remain JSON callers. JSON continues rejecting tool_calls and requiring content
   JSON validated by Action. No cross-protocol fallback.
3. In deepseek_tools mode, send four function definitions named reply,
   review_inputs, prepare_qc and prepare_analysis. Allowed/required parameter
   names respectively are (text), (text), (upload_id, matrix_location), (tool_id).
   Derive each field schema from Action.model_json_schema()["properties"]; keep
   their patterns and length bounds. Set additionalProperties false. Do not
   include the action discriminator in function parameters.
4. Native requests set tool_choice required, thinking {"type":"disabled"},
   max_tokens 1800 and omit response_format. JSON requests retain their current
   response_format and do not gain DeepSeek-specific parameters. No beta endpoint
   or strict-mode service dependency.
5. Share the substantive system guidance between both modes. JSON framing stays
   JSON-only; native framing requires exactly one named function and arguments
   without an action key. Retain Task 13 evidence interpretation instructions,
   input-review behavior, stop semantics, no metadata mutation and all scientific
   claim restrictions. Preserve the public SYSTEM constant for default JSON
   callers/private existing diagnostics.
6. Native response requires exactly one well-formed function call with a known
   name, string JSON arguments containing exactly its required fields, and no
   non-whitespace content outside the call. Reject missing, multiple, unknown or
   malformed calls, extra/discriminator fields and invalid Action values.
   Construct {"action": name, **arguments} only after rejecting an action key and
   validating the exact allowed-field set, then reuse Action.model_validate.
   Do not execute a function from model text.
7. Return only bounded stable error codes for protocol/shape failures. The
   existing Service provider_unavailable envelope and control epoch fence remain
   authoritative. A stopped turn cannot restore a proposal.

**TDD steps:**
- [x] Extend existing parser/wire boundary tests with independently literal
  fixtures for all four native actions and invalid forms. Positive example:
```python
message = {"content": "", "tool_calls": [{
    "type": "function",
    "function": {"name": "prepare_analysis",
                 "arguments": "{\"tool_id\":\"P0-02\"}"}
}]}
action = parse_action(message, protocol="deepseek_tools")
assert action.action == "prepare_analysis"
assert action.tool_id == "P0-02"
assert action.text is None
```
  Reject two calls, plain prose, unknown function, non-string/non-object
  arguments, action key, prepare-analysis text even when null, wrong tool ID,
  missing text and malformed JSON. Preserve every default JSON regression.
- [x] Capture real RED assertion failures before implementation, with the external
  HTTP transport mocked at the existing wire seam only.
- [x] Implement the small protocol branch. Intended request shape:
```python
if settings.model_action_protocol == "deepseek_tools":
    payload.pop("response_format")
    payload.update(tools=action_tools(), tool_choice="required",
                   thinking={"type": "disabled"})
```
  action_tools() returns definitions using the one field-name mapping also used
  by native argument validation; no duplicated field patterns or second Action
  model hierarchy.
- [x] Verify actual outgoing JSON-mode and native-mode request shapes via
  httpx.MockTransport, including unchanged max_tokens and absence of accidental
  response_format/native parameters in the other mode. Exercise a native
  prepare_analysis through the real Service path and prove the result is
  awaiting_approval with no tool execution.
- [x] Run tests/test_web_service.py, tests/test_web_evidence.py and
  tests/test_web_inputs.py with the existing approved startup trust configuration,
  then git diff --check. Record exact results and existing warnings. Do not
  change environment trust pins or claim a full-repository green suite.
- [x] Self-review, commit only assigned source/tests, report RED/GREEN evidence
  and concerns in the private task report; independent review is required.


## Task 15: Consistent evidence and explanation-only guidance

**Files:** Modify src/bridge/web/provider.py and tests/test_web_service.py only.
Root owns docs/web-preview.md, this plan and private operational acceptance.
No other production, test, dependency or Schema file changes.

**Evidence and scope:** The first installed native browser acceptance returned a
valid reply but omitted requested canonical counts/fractions and mentioned an
unprovided standard error. A preceding explanation request produced an unapproved
QC proposal. The actual provider context contained the correct result_summary.
One fixed-context baseline replay and one conditional-guidance replay both later
returned the counts. Thus the first quality failure is not stably reproduced and
neither replay proves causality or reliability. The static unconditional
status-only prompt contradicts the approved conditional aggregate interpretation.
This task removes that contradiction and clarifies intent, not model reliability.

**Global Constraints (binding):**
- All project code, tests, builds and data remain on the designated server workspace.
- Keep the existing default JSON and explicit native protocols, strict Action
  parsing, privacy opt-in, canonical summary projection and exact approval gates.
- No response rewriting, deterministic fake explanation, prompt retries, new
  keyword intent parser, model switch, token increase or dependency.
- No actual model call, scientific run, service restart, push or merge by the worker.
- Never include real counts, private records, credentials, paths or identities
  in source/tests/public Git. Reuse only existing synthetic test context.

**Exact guidance changes in the shared _SUBSTANTIVE_GUIDANCE:**
Replace the three unconditional sentences beginning "You receive conversation
and minimal execution status only" through "execution-state level" with:
```text
You cannot inspect raw uploaded biological data. Execution success alone is not biological evidence.
When results_sent_to_model is false, describe only the reported tool ID/execution state and ask the user to inspect tool-owned results.
When results_sent_to_model is true, use the supplied result_summary to answer the requested result question; do not replace its numerical evidence with execution-status language.
```
Keep the existing detailed E1, selected-view, denominator and claim restrictions.
Immediately after "This explanatory conversation is not P0-10 verified report
generation." add:
```text
Use the supplied counts and fractions when requested. Do not invent standard errors, confidence intervals or scores absent from result_summary.
```
Replace "Do not prepare a plan when the user asks to wait or stop." with:
```text
For explanation-only requests about results, missing inputs or next steps, use reply, not prepare_qc or prepare_analysis.
Earlier positive input declarations establish prerequisites, not a request for a new plan.
Do not prepare a plan when the user asks to wait, stop, or not prepare a new plan.
```

**Tests and completion:**
- [x] Extend the existing outgoing-payload tests at httpx.MockTransport for both
  json and deepseek_tools. Independently literal assertions must prove that the
  actual system message contains the conditional status/summary guidance,
  supplied-number/no-invented-interval rule and explanation-only intent rule,
  and no longer contains the old unconditional status-only claim.
  Also retain the existing protocol-specific payload assertions. This verifies
  emitted instructions only; it does not assert real-model behavior.
- [x] Run the focused test selection before production changes and capture
  behavioral RED assertion failures (not import/fixture errors).
- [x] Apply only the exact shared-guidance changes; focused GREEN.
- [x] Run tests/test_web_service.py once using existing approved trust setup
  from task-14-report.md. Record exact commands/results, warnings and git diff
  --check. Unchanged evidence/inputs/workflow suites are covered by the root's
  final installed acceptance, not claimed as rerun by this task.
- [x] Self-review, commit only the two assigned files, and write full report
  to the private task-15-report.md. State explicitly that prompt transport
  tests do not establish model quality or full-chain scientific completion.

## User-experience E2E repair scope, 2026-09-08

The owner clarified that E2E means simulating a user's complete experience of
existing functionality and explicitly authorized fixes. Retain genuine evaluation
data and genuine reference resources. Acceptance actions occur through the actual
browser and configured model: no direct API/script invocation may substitute for
a user completing a tool path. Cover every currently exposed P0 module, including
the comparison and graft branches, and report each actual execution, correct
input-blocked outcome and product defect separately. Visiting a panel, fixture
execution, a no-graft declaration or replaying an old request is not proof of
that module's genuine scientific analysis. Do not invent missing experimental
facts, promote test-only scientific configurations or expand a scientific
contract to make a user journey pass.

Confirmed current-path defects justify focused repairs, subject to the owner
execution override above. Preserve the running deployment while preparing the
isolated candidate. Use the existing branch/workspace; do not restart completed
tasks, launch automatic reviews or replace the biological question. Record any
new material scope here before source changes.

## Task 16: Readable, bounded Parquet table previews

**Files:** src/bridge/web/app.py, web/src/components/ResultsPane.tsx,
tests/test_web_service.py and web/tests/results-pane.test.tsx only. Root owns
this plan and stable Web documentation. No dependencies, lockfiles, toolkit,
scientific package or scientific Schema changes.

**Problem and desired behavior:** Tool-produced Parquet downloads are valid, but
the Tables view currently decodes their binary bytes as delimited text. Render
a bounded real table preview for supported Parquet artifacts while preserving
the exact original download. Unsupported or over-limit previews show a plain
download fallback, never binary text and never a claimed complete table.

**Global Constraints (binding):**
- All project code, tests, builds and data remain on the designated server workspace.
- Use the existing registered same-session artifact route, authentication and
  private-file/checksum guards; never trust an artifact URL, raw path or filename
  from a browser request.
- Previewing is read-only. It never runs a tool, changes input declarations,
  rewrites an artifact, sends evidence to a model or grants export authority.
- Reuse the already installed optional PyArrow dependency and existing React
  table presentation. No client Parquet dependency, alternate file service,
  arbitrary query/column API or scientific data transformation.
- Keep exact approvals, stop/review state, original downloads and prior sessions.
  No service restart, real model call, scientific run, push or merge by the worker.

**HTTP/UI seam:**
- Add GET /api/sessions/{sid}/artifacts/{aid}/preview for registered Parquet table
  artifacts only. Return JSON with columns: string[], rows: scalar[][],
  total_rows: integer, total_columns: integer and truncated: boolean.
- Share the existing registered artifact read/checksum behavior with the original
  download handler. Unknown/cross-session IDs remain 404, altered bytes remain
  409. Unsupported formats or invalid Parquet return a fixed bounded error;
  never expose parser exceptions or private paths.
- Bound stored bytes to 8 MiB before parsing, preview to the first 100 rows and
  first 24 top-level columns, and the total declared uncompressed size of the
  row groups actually read to 32 MiB before batch decoding. Bound the encoded
  response to 200,000 bytes; reject over-limit content instead of sending it.
  Reject or clearly represent unsupported nested/binary cell types; do not
  stringify an unbounded object. Limit text cell length to 1,000 characters
  with a visible truncation indication and set truncated=true. Preserve
  ordinary numeric, boolean, string and null values; represent non-finite values
  explicitly as display strings, not invented finite numbers or zero.
- Use ParquetFile batch iteration on a bounded immutable byte snapshot rather
  than loading the complete table. Read enough rows to display the first 100;
  count/shape metadata is informational, not a new scientific result.
- The client recognizes Parquet by registered media type or .parquet suffix
  (old sessions use application/octet-stream), calls only the new same-origin
  route with session credentials and renders cells as inert React text.
  Downloads keep using the unchanged original route/name.
- Preserve CSV/TSV/JSON text previews. Other unsupported binary artifacts show a
  download hint without feeding bytes to TextDecoder. Abort or ignore obsolete
  preview results after session/artifact changes. Show row/column truncation
  honestly, including an empty valid table.

**Test-first steps:**
- [x] Add a real registered tiny Parquet artifact using the existing Service test
  setup. The API response must contain independently literal values:
```python
assert response.status_code == 200
assert response.json()["columns"] == ["metric", "value"]
assert response.json()["rows"] == [["observed", 7], ["missing", None]]
assert response.json()["total_rows"] == 2
assert response.json()["truncated"] is False
```
  Exercise the route, not a mocked decoder. Add hash drift, cross-session,
  invalid/unsupported format, row/column truncation, oversized bytes and
  excessive decoded-row-group/response bounds. Assert original downloaded
  bytes and checksum remain unchanged.
- [x] Add a ResultsPane test for a registered .parquet with octet-stream media:
  opening Tables fetches /preview and renders the expected header and cell,
  not PAR1. Test inert malicious-looking cell text, explicit failure/download
  fallback, truncation and existing TSV/download behavior.
- [x] Run these focused tests on the unchanged production implementation and
  retain the expected behavioral RED failures; environment/import failures
  do not count.
- [x] Implement the smallest guarded route and client rendering change.
- [x] Run the covering tests to GREEN, then the complete Web-service suite and
  complete frontend suite/typecheck/build once. Preserve and report existing
  warnings. Root owns full installed cross-component/browser acceptance.
- [x] Self-review, commit only assigned files, and write the private Task 16
  report with RED/GREEN commands, outcomes and remaining risks. Independent
  task review is required before installation.

**Engineering validation:** Task 16 and two independently reviewed corrections
are complete at `e711d41c`. The final focused checks passed 9 backend Parquet
cases, 14 ResultsPane cases and TypeScript checking. The initial task also ran
the complete service suite (116 passed), complete frontend suite (56 passed)
and build; those broad runs preceded the two numeric/lock corrections and are
not claimed as exact-final-head installed checks. Two pre-existing Python
deprecations and the existing bundle-size warning remain recorded. Installation
and genuine bounded-preview/download acceptance subsequently completed under
Task 20. A media-type-only recognition coverage suggestion remains a deferred
minor; the completed task is not reopened by this closeout.


## Task 17: Reuse verified QC on the selected cell-state path

**Files:** src/bridge/web/app.py, src/bridge/web/inputs.py,
tests/test_web_inputs.py and tests/test_web_service.py only. Root owns plan and
stable documentation. No frontend, scientific package, Schema, dependency or
provider changes. Start only after Task 16 is committed and independently
reviewed; both tasks touch app.py but have separate responsibilities.

**Problem and desired behavior:** Saving the ordinary P0-02 input selection
currently bypasses the existing canonical-QC enrichment path. An unchanged raw
count asset therefore appears to lack the QC reference the same session just
produced. Readiness and construction must use the same effective selected asset,
derived from the exact immutable upload and verified same-session QC artifacts.
The user still confirms genuine source facts through the existing private source
form; the user must not author internal QC identifiers or derived hashes.

**Global Constraints (binding):**
- All project code, tests, builds and data remain on the designated server workspace.
- No P0 Tool ID, scientific Schema, score, threshold, state definition or release
  authority change in this Web increment.
- No fabricated metadata, weights, replicas, attestations, references,
  measurements, successful exports or tool execution.
- Preserve exact input review, declaration epochs, plan approval digests,
  canonical receipt and artifact checksums, private paths, prior sessions and
  the legacy stage path. No source fact or scientific declaration is inferred
  from chat, a filename or the QC result.
- Workers do not restart services, call a model, run private biological data,
  push or merge. Root owns installed and actual-browser acceptance.

**Behavior and ownership seam:**
- On P0-02 only, derive the selected asset using its explicitly selected upload
  ID, never the last upload or an unrelated latest QC run. Require the current
  committed source_family_id from that upload's separate source field; missing
  source reports source_family_id_required. Do not use stale declaration metadata
  to satisfy a missing committed source field.
- Reuse the existing qc_asset verification: completed successful QC, exact
  selected asset/checksum, current declaration epoch and unchanged scientific
  declaration, canonical receipt and required QC artifact hashes. Preserve its
  rejection of stale, tampered, missing and caller-conflicting metadata.
- Provide a read-only enrichment path which returns a fresh CaseInputAsset with
  source_family_id, qc_profile_ref, data_view_id and parent_asset_sha256 derived
  only from the confirmed source field and those verified QC outputs. Preserve
  original path/checksum/assay/matrix/input-level and other metadata. Support a
  valid initial chat-QC declaration as well as a panel declaration; do not require
  redeclaring an unchanged asset merely to copy it into _asset_declarations.
  Do not mutate
  _asset_declarations, _qc_declarations, _uploads, saved receipts or artifacts.
  Preserve the existing verification-only qc_asset(register=False) caller contract
  and legacy migration behavior; do not silently rewrite its caller metadata.
- Readiness uses that effective asset without QC-catalog writes. Construction
  uses the same effective-asset rule and registers canonical QC references only
  under the existing non-blocking catalog-ownership boundary. No new lock order,
  background worker, cached success or alternate request builder.
- Validate the normal selected asset contract and the exact selected
  MeasurementSpec. Do not silently use the configured default when the user did
  not select one. Missing/invalid QC or source produce bounded truthful input
  reasons; do not convert unrelated exceptions into successful readiness.
- Every proposal remains a fresh immutable bundle and exact approval. A committed
  source-only edit invalidates the old proposal and binds the new source without
  rerunning QC; changed scientific declaration still requires fresh QC. Non-P0-02
  asset/object paths and legacy direct P0-02 behavior remain unchanged.

**Test-first steps:**
- [x] Through the normal Service HTTP seam, upload a synthetic unit-test matrix,
  confirm its declaration, approve and execute real QC, confirm the private source,
  save a P0-02 selection with its asset and explicit MeasurementSpec, and prepare
  analysis. On the baseline assert the behavioral failure before implementation.
  Do not inject QC references into metadata or bypass selection construction.
- [x] Assert capabilities are ready and the proposed request binds the exact
  selected file/checksum, raw-count semantics, confirmed source, canonical QC
  profile/DataView/parent checksum and selected MeasurementSpec. Assert a separate
  approval is required and the old QC run/history remains unchanged. Validate the
  constructed upstream QC bundle with the existing tool validation helper.
- [x] Cover no source, missing QC, wrong-upload QC, multiple uploads with explicit
  earlier selection, stale declaration, altered receipt/artifact, source-only
  edit, old approval replay and non-P0-02 regression. Read-only readiness must not
  create or change the QC catalog or mutate registered declarations/receipts.
- [x] Implement the smallest shared effective-asset rule; avoid duplicated QC
  verification and do not add a general enrichment framework.
- [x] Run focused RED/GREEN, then full test_web_service.py and test_web_inputs.py
  once at the final task head. Keep exact commands/results and existing warnings.
- [x] Self-review, commit assigned files and write the private Task 17 report.
  Independent task review precedes installation and browser continuation.

Engineering validation: the normal synthetic Service/input suite passed 158 tests
before the independent review fix; fresh receipt-isolation and legacy coverage
then passed eight tests. Independent re-review has no open Critical/Important
finding. One defensive legacy-plan JSON parsing test remains a deferred minor.
The code was subsequently installed under Task 20. That fresh intake case stopped
after QC because its product family remained unknown; selected P0-02 execution was
not repeated. These results are not a complete scientific chain.

## Task 18: Give the conversation canonical aggregate QC evidence

**Status:** implemented at `066b752a`. The recorded final evidence/service run
passed 160 tests with two existing warnings. This is engineering evidence only.
The independent review was cancelled at the owner's direction. Installation and
actual-model E0 browser explanation subsequently completed under Task 20; E1 was
not repeated there. Do not reopen the completed suite or cancelled review as a
prerequisite to advancing.

**Files:** src/bridge/web/evidence.py, src/bridge/web/provider.py,
tests/test_web_evidence.py and tests/test_web_service.py only. Root owns stable
documentation and this plan. No scientific tool, Schema, raw-data processing,
provider transport or startup-option changes. Start after Task 17 review.

**Problem and desired behavior:** A successful QC-only session currently sends
no result evidence even when aggregate sharing is explicitly enabled. The model
therefore cannot explain the QC results the user sees. Extend the existing
canonical bounded projection, not the model's access to raw input or table rows.

**Global Constraints (binding):**
- All project code, tests, builds and data remain on the designated server workspace.
- Provider context is status-only by default. The owner-approved opt-in summary
  projection may include bounded aggregate measurements, never raw matrices,
  observation rows, source-family values, sample identities, private paths or
  credentials.
- No P0 Tool ID, scientific Schema, score, threshold, state definition or release
  authority change in this Web increment.
- Preserve candidate/shadow and domain_score=null; preserve partial, unavailable,
  not_assessed and explicit input-construction blockers.
- No service restart, real model call, private scientific run, push or merge by
  the worker. Root owns installed and browser acceptance.

**Canonical evidence and exact projection:**
- Preserve existing E1 cell-state selection, projection and private bindings.
  Independently select the latest succeeded/partial P0-01 receipt. Never fall
  back to an older QC receipt if the latest is missing or invalid.
- Verify the receipt's same-session path and SHA, exact tool/execution identity,
  registered canonical artifact identity/path/SHA and the QC profile v0.2 artifact
  bytes. Parse the existing ToolRun and QCReadinessProfileV2 models. Verify the
  profile producer binding to that receipt/run. Reuse checked_bytes and existing
  receipt verification primitives where applicable; do not read matrices,
  Parquet tables, per-observation outputs, display-redacted copies or chat replies
  to construct the summary.
- QC evidence uses local alias E0. A QC-only available summary contains state,
  evidence_ref, tool_id, execution_state, assay, input_level, readiness_state,
  schema_integrity, count_metrics_state, metrics, assessment_states,
  selected_data_view, score_state and domain_score.
- schema_integrity contains only n_observations, observation_kind, n_genes,
  unique_cell_ids and unique_gene_ids. Validate exact bounded scalar types;
  observation_kind is cells, nuclei or barcodes. No observation identities.
- metrics contains only the existing tool-owned aggregate MeasurementResults for
  total_counts_median, detected_genes_median, mitochondrial_fraction_median,
  ribosomal_fraction_median and top_20_gene_fraction_median. Each row contains
  metric_name, raw_value, denominator, evidence_state, score_state and
  domain_score. Copy finite numeric/null values and denominator exactly; never
  calculate a new statistic, impute a missing value or invent units/intervals.
  Duplicate allowlisted metric names, nonnumeric/nonfinite values or inconsistent
  missing/unavailable values fail closed. Ignore unlisted metric names without
  exposing them.
- assessment_states contains only the state for upstream_library_qc,
  doublet_assessment, cell_calling_assessment and ambient_assessment; accepted
  values are not_assessed, candidate, unavailable and not_implemented. Do not copy
  arbitrary reason text, warnings, method parameters or per-group content.
- selected_data_view is null or only {view_kind, n_observations}. Keep its exact
  historical view and count; never imply it is the current upload or a filtered
  view when it is all_observations. Assay/input_level/count-metrics states use
  fixed producer-supported values, not unconstrained strings from a dict.
- E0's private binding records its exact receipt and canonical QC artifact IDs
  and hashes; these values never enter the provider context.
- If E1 is available, preserve its existing top-level fields and add qc_summary
  when a QC receipt exists (available or explicit unavailable/not_available).
  If E1 is not available but E0 is available, return the QC summary at top level;
  when a P0-02 receipt exists, add cell_state_summary containing only its actual
  unavailable/not_available state and bounded reason. Do not label missing E1
  evidence as available. If neither is available, preserve truthful bounded
  unavailable/not_available behavior.
- Apply the existing MAX_SUMMARY_BYTES bound to the combined result and preserve
  the existing fail-closed reason codes and review/opt-in/history-suppression
  behavior. E0 and E1 may refer to different historical runs; never imply they
  share an upload or denominator unless evidence actually binds that relation.

**Provider guidance and tests:**
- Replace the unconditional claim that the context cannot certify QC metrics
  with conditional guidance: interpret E0 aggregate fields when present, use E1
  for its cell-state view, cite the corresponding alias and scope, and describe
  unavailable assessments as not performed/not assessed rather than successful.
  Do not claim filtering, doublet removal, biological QC pass, purity or scientific
  validation from execution success or counts alone.
- Preserve explanation-only reply guidance, exact approval, no raw-data access,
  both JSON/native wire schemas and the existing status-only fallback.
- [x] Add focused failing tests with independently literal QC counts/medians,
  missing metrics and explicit not_assessed states. Use a real registered QC run
  from the existing synthetic Service fixture for an integration regression.
- [x] Test QC-only opt-in sends E0, opt-out/review sends no result values, combined
  E0/E1 keeps separate bindings, latest-invalid QC does not reuse older QC,
  canonical receipt/artifact tampering fails closed, and private sentinel strings
  in every omitted/free-text field never enter the outgoing provider payload.
- [x] Cover nonfinite/nonnumeric/duplicate metrics, size limits, historical upload
  changes and existing E1 regressions. Assert both outgoing protocol prompts
  contain conditional QC guidance and omit the old unconditional denial.
- [x] Record behavioral RED, implement narrowly, run focused GREEN then complete
  test_web_evidence.py and test_web_service.py once, preserving existing warnings.
- [x] Self-review, commit assigned files and report exact commands/results.
  Independent review was cancelled; do not label it passed or restart it.

## Task 20: First product intake, exact confirmation and readable next-stage plan

**Owner-approved scope (2026-09-08):** upload -> readable product-intake draft ->
explicit fact confirmation -> readable executable stage plan. Preserve the existing
conversation/results layout. The owner's no-repeat-review/no-old-suite-loop rule
remains binding. Task 19's initial confirmation and chat QC reuse are absorbed here.

**Design:** one private Web intake record per selected registered upload, not a
new scientific Schema or a fabricated ProductCase/ProductDefinitionCard. Keep
target, expected stage, preparation sampling role and independent-culture count
as researcher declarations; unknown values stay unknown. File structure supplies
only observed shape, matrix locations and column names. An independent-culture
count never becomes a biological-unit mapping or attestation.

**Files and boundaries:**
- Add src/bridge/web/intake.py: typed intake facts; bounded observed upload
  structure; current/confirmed draft projection; exact-confirmation materialization
  through existing AssetDeclaration; truthful next-stage selection.
- Modify src/bridge/web/control.py: add intake as an existing pending-change kind;
  confirm/discard by the existing session/revision/digest contract. Preserve
  immutable history and invalidate only changed scientific asset declarations.
- Modify src/bridge/web/app.py and provider.py: wire intake routes/context and a
  typed propose_intake action; replace initial free-text declaration scans with
  confirmed values; guard completed-QC chat reuse. No change to provider credentials,
  protocol selection, scientific tools, reference resources or execution engine.
- Add web/src/components/ProductIntake.tsx; modify App.tsx, Conversation.tsx,
  InputChangeCard.tsx, ResultsPane.tsx, intakeLabels.ts, api.ts, types.ts and styles.css: visible product draft,
  friendly exact-change labels and next-stage action, with advanced tool inputs
  retained separately. Refresh/session switches must not resurrect stale edits.
- Add tests/test_web_intake.py and web/tests/product-intake.test.tsx; migrate
  directly affected legacy intake setup/tests to explicit declarations, without
  reopening unrelated validation work. Add only actual new files to repository policy.
- Update Web/Agent docs and this plan; current source and installed coverage stay separate.

**Interfaces:**
- GET /api/sessions/{sid}/intake?upload_id={id}: authenticated current upload,
  observed file structure, editable facts, confirmation state, remaining questions
  and a next-stage proposal opportunity. No scientific result inference.
- POST /api/sessions/{sid}/intake: {upload_id, facts}; stages, never commits/runs.
- Existing input-change/confirm or discard resolves that exact proposal.
- POST /api/sessions/{sid}/intake/prepare: {upload_id}; requires current confirmed
  facts and no review/busy state. Uses existing QC or P0-02 planner path with exact
  asset binding; unavailable downstream scientific objects stay visible blockers.
- Model propose_intake(upload_id, facts) may propose only stated initial facts.
  Committed intake changes use the private form. Safe model context carries
  confirmation/missing-field status only, never private form values or file rows.

**Acceptance:**
- [x] Real Service tests: an upload exposes observed structure, not cell identities;
  a draft leaves current declarations/plan/runs unchanged until exact confirmation.
  Cross-session/stale/discard and invalid-column/unknown-location cases fail closed.
- [x] Partial/unknown targets remain explicit. Unsupported product scope may get
  generic input QC only, not a guessed product-reference interpretation.
- [x] Initial chat facts use a typed proposal and exact card. Remove superseded
  initial history/negation scans and pending-QC state; confirmed declarations are
  the only QC authority. Preserve deliberate advanced-panel reruns.
- [x] A confirmed draft can prepare an unapproved real P0-01 request; approval
  runs the existing toolkit. A later explanation-oriented QC action reuses
  unchanged verified QC without a new proposal, while corrupt evidence blocks.
- [x] Five focused frontend cases cover draft submission, confirmation gating,
  older-upload pending-card visibility, separate plan approval and unsaved-edit
  blocking. Existing session-switch guards remain; Service tests cover stale/error
  boundaries. These are focused runs, not a new full frontend-suite claim.
- [x] Typecheck and production build passed. A fresh genuine upload and current
  configured model were exercised through the isolated browser; desktop/mobile,
  refresh, Parquet preview and original download were inspected. Requests/artifacts
  remain private. No old-request replay or test-only scientific configuration was used.
- [x] Actual execution and remaining blockers are documented. No automatic independent
  review, repeated passed suites, primary-instance restart, push or merge.

### Task 20 genuine product-entry observation (2026-09-08)

A fresh registered genuine-data subset was used. Source-backed raw-count
semantics and observed metadata-column selectors were explicitly confirmed.
The private source identity, observation/gene counts and measured values remain
in the private acceptance record, not this public plan. Product family, final-preparation sampling role and
independent-culture count stayed unknown; no biological-unit mapping, formal
product definition or attestation was invented.

The configured model produced an initial typed draft. Confirming facts created
no plan or run. The next-stage button produced an unapproved P0-01 plan, and the
separate analysis approval produced exactly one successful ToolRun: six figures,
three tables, seven evidence artifacts and 22 Web downloads. Canonical bindings
were checksum-verified; the browser-downloaded Parquet matched its source.

The actual model's follow-up used canonical E0 measurements. Displayed values
were checked against the private canonical aggregate record; no biological
measurements are published here. Unassessed upstream items and limited readiness
were preserved, and no score or qualification claim was made. The prompt caused no additional plan or QC execution. One phrase
combined unconfirmed and unsupported product scope; the confirmed UI still shows
unknown. This single response is not general interpretation-quality validation.

Desktop and 390-pixel mobile intake/roadmap views, refresh retention, bounded
Parquet preview and original download were observed. The browser audit recorded
no page errors or failed requests. Expected pre-authentication/restart 401s, a
missing favicon and one attempted click on an off-screen closed sidebar were
retained, not reported as a zero-warning run. The browser was closed after checks.

No new P0-02 or downstream tool ran in this case: the unknown product family
correctly prevents assuming hPSC-mDA reference scope. These observations establish
the entry/confirmation/first-stage experience, not biological identity, independent
replication, full product assessment, scientific validity or release readiness.

### Task 20 engineering evidence (2026-09-08, installed snapshot)

Initial new Service tests showed 11 behavioral failures. With the backend
implemented, 10 passed and the two still-missing provider-action checks failed;
the typed action then passed all 12. Additional privacy, stale source,
integrity and QC-retraction checks plus directly affected migrated setups
produced 67 passes and one obsolete legacy fixture assumption. That fixture
now explicitly represents a saved pre-panel session; its single rerun passed.
These checks used synthetic fixtures and are not genuine scientific validation.

The initial two frontend assertions failed on the absent product panel, then
passed after implementation. The older-upload confirmation case exposed a hidden
pending card and passed with the review file held selected. The separate-approval
case passed after correcting its test's existing button label. An unsaved-edit
case failed first and then passed with plan generation disabled until confirmation
or cancellation. All five new cases passed in focused runs, not one full-suite run.
Final typecheck/build passed. Two observed display/plan-label checks and three
product-scope/private-context checks each failed first and then passed after their
narrow changes. The build retains a non-fatal large-chunk warning.

The final wheel was built, installed and imported with five model actions and all
12 tool packages present. Installed Python files and reused, unchanged client
assets match the source snapshot; this is not the committed baseline alone.
The isolated preview upgrade preserved all four session files byte-for-byte at
startup. Provider model/protocol, reference resources and trust configuration were
unchanged. Source/wheel hashes and private logs bind the installation and browser
receipts. Only changed/new behavior was selected; unchanged broad suites were not
rerun. No scientific-contract change or merge was made. The intake acceptance preceded
this PR closeout; source/publication commits and exact-head CI are recorded as
separate engineering events, not additional scientific runs.

## Task 19: Initial fact confirmation and completed-QC chat reuse

**Execution update:** absorbed by Task 20; do not implement a parallel intake path.

**Status:** implemented within Task 20; retained below as scope history, not an
independent work queue. Current installation and browser acceptance are recorded
under Task 20.

**Scope:** existing Web Action/Service boundary and focused tests only. Reuse
Controls and the exact InputChangeCard; no new workflow, general parser,
scientific contract, model switch or automatic execution.

- Let the model propose only explicitly supplied assay and raw-count location
  for an undeclared registered upload. Validate them and stage the existing
  exact confirmation card; a proposal does not commit facts.
- Exact fact confirmation still requires a separately approved plan before
  execution. Preserve stale-action/stop fences and the correction workflow.
- Replace the superseded initial parsing path after checking its current callers.
  Do not keep competing declaration authorities or more negation exceptions
  merely for compatibility.
- At the chat QC-preparation boundary, reuse verified unchanged canonical QC
  without a duplicate proposal. Preserve deliberate input-panel reruns and fail
  closed on invalid evidence.
- Ground guidance in the actual source field and confirmation controls; QC
  references are server-derived. Ordinary unverified notes may explain supplied
  evidence but are not formal claim-verified reports or exports.

Verify the changed behavior with a focused confirmation-to-approved-QC and
explanation/reuse check, including affected invalid/stale-input boundaries,
then exercise it through the actual UI/current configured model. Use recorded
passing evidence for unchanged behavior. No full-suite replay, old-version
comparison or automatic independent review wave. Installation and genuine
downstream acceptance remain explicit subsequent work, not implied by a test.

## Historical validation record

This records the earlier staged increment, not acceptance of the current source
head. Use the current-progress table above for installed acceptance scope and
remaining genuine user-flow work. Historical suite counts are not instructions
to repeat them.

Baseline main is b458ab846102310b9138f6f5b0a524027569f1b8. The preceding fresh Web test executed P0-01 only; server private evidence is retained separately. Tasks 1 and 2 are implemented and independently reviewed. The fresh installed-package Web conversation executed P0-01, P0-02 and explicit zero-input P0-12; figure cards, registered download integrity, staged history, refresh and narrow layout were checked. The installed service suite passed 44 tests and the client suite passed 24 tests plus its production build. Provider JSON Action compatibility was verified with the configured provider and the real browser. Private evidence binds the source revision, installed wheel, complete conversation and canonical receipts. Required CI passed for the preceding staged public revision. The contract-driven
extension has its own final-head checks before the same Draft PR is updated;
full-chain genuine-data conditions above remain open.
