# Step 7 Evidence Coordinator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Execute one implementation task at a time, in a dedicated server worktree, with independent task review.

**Status:** in_progress.
**Goal:** Connect the approved Step 7 evidence-driven assessment loop to real registered tools and a researcher-readable, version-bound product portrait.
**Architecture:** Reuse ToolRegistry, exact AnalysisPlan execution, canonical ToolRun receipts and the existing P0-09 graph. One coordinator selects bounded actions; scientific packages retain all measurements, denominators, eligibility and evidence states. Hypotheses remain planning statements, never measurement facts.
**Tech Stack:** Existing Python/Pydantic/FastAPI workflow runtime, JSON/Parquet/NetworkX graph artifacts and React Web preview. No new runtime framework or graph store.
**Spec:** [BRIDGE PRD section 6](../docs/BRIDGE_PRD.md#6-agent-功能需求), [Agent Integration](../docs/agent-integration.md), and the owner-approved implementation design of 2026-09-10.
**Baseline:** main `fa6017b3924e7b99055f051898d7a5a87f572e7b`.

## Global Constraints

- The first six intake-to-QC steps are accepted only within their stated scope; do not redesign or repeat them.
- Agent calls remain registered high-level P0-01 through P0-12 packages; no direct Scanpy/R/model commands.
- Existing inputs and results are immutable, versioned and checksummed. Original uploads and historical receipts remain available.
- All active domains keep `domain_score=null` and `score_state=shadow` or `unavailable`.
- `negative`, `missing`, `unknown`, `unavailable` and `alert` remain distinct; missing evidence never becomes zero.
- Same-family and dependent methods are not independent votes. A cell is not a biological replicate.
- Product roles, regional definitions, developmental windows, programs, reference applicability and biological-unit facts require their actual source/review records. Never create approval or attestation by inference.
- Sealed/competitor-isolated inputs remain unopened and excluded. Graft never backfills pre-transplant evidence; comparison/graft execution requires separate applicable authorization.
- Model access respects the existing result-sharing control. No raw cells, private paths, unapproved facts, or credentials are added to provider context.
- All code, tests, previews and private evidence stay on the server. Do not modify running services, push/merge main, or deploy.
- Public Schema semantics are versioned; keep old compilation behavior compatible. One manually maintained source per fact; generated projections are rebuilt deterministically.
- Tests exercise registered calls, real canonical artifacts and user-observable state transitions; mocks are limited to the external model/network.

## Mathematical and execution invariants

1. A composition is conditional on its declared selected DataView and denominator. Exclusive partitions close including unresolved mass; overlapping biological programs are separate axes, not a categorical simplex.
2. Reference support, classifier scores, product roles and scientific qualification are different objects. Do not manufacture a normalized posterior, confidence score, or numerical information gain from method agreement.
3. At each turn an action must be in the intersection of approved scope, current deterministic eligibility and remaining resource budget. Store the exact materialized request and its scope authorization before execution.
4. A hypothesis names existing evidence, a competing explanation, and a discriminating approved check. It cannot assign a MeasurementResult value, evidence tier or review status.
5. Only verified ToolRun outputs advance the evidence graph; changes create a new graph version. Repeated queries or unchanged requests cannot create new evidence or consume an unbounded loop.
6. Evidence completion, exhausted budget, unavailable prerequisites, changed facts and interruption are distinct stopping reasons. An all-missing portrait is not completed product assessment.

## Task 1: Registered, bounded P0-09 graph queries

**Deliverable:** The existing seven validated graph queries become available through the registered P0-09 package without modifying source graphs or performing new biological computations.

**Files:**
- Modify: `src/bridge/tool_packages/p0_09_evidence_compiler/adapter.py`, `models.py`, `src/bridge/tool_packages/_input_contracts.py`, `specs/p0_09.yaml`, `cards/P0-09.md`.
- Create: `src/bridge/tool_packages/p0_09_evidence_compiler/query_runtime.py` only if this keeps the compilation adapter focused; do not split the existing query implementation.
- Modify: `src/bridge/toolkit/schemas.py` only to register the two new planned query-input and compiler-result Schema URIs against their deterministically generated filenames.
- Modify: `tests/test_p0_09_evidence_compiler.py`, `tests/test_web_inputs.py` and `tests/test_registry.py` where they consume input discovery and Schema validation.
- Deterministically regenerate affected `src/bridge/resources/schemas/` files and Tool Card projections using existing scripts. Align only P0-09 version pins in `examples/agent-integration/profiles/` and their existing tests when necessary; do not edit shared scientific contracts or unrelated package versions.

**Interfaces:**
- Consume `ToolRegistry.run(ToolRequestV2)`, verified `StructuredInputRef` graph manifests, and `EvidenceGraphQueries.open(manifest_path)`.
- Add two input modes `case_query` and `comparison_query`, each with exactly one `evidence_graph_manifest` of its matching existing Schema and one `evidence_graph_query` using `bridge://schemas/evidence-graph-query/v0.1`, object version `0.1.0`.
- `EvidenceGraphQuery` exposes `object_version`, `query_name`, and strictly typed named arguments matching the existing seven query methods. Reject unknown or inapplicable arguments; no arbitrary expressions, paths, queries or SQL.
- Reuse `EvidenceGraphQueryResult` unchanged for the result payload. Publish a versioned P0-09 result union `bridge://schemas/evidence-compiler-result/v0.2` accepting existing compilation results and query results. Keep old result Schema registered; package becomes `0.5.0`.
- Query requests require `assets=[]`, `parameters={}`, `measurement_spec_ref=null`; query and compilation roles cannot mix. Compilation results and query results remain distinguishable by their existing shapes.
- Query execution returns a canonical ToolRun with exact graph identity, bounded result, empty measurements and no new scientific state. It may write its own content-bound query receipt/artifact to the request output directory, but must not modify any graph source. Never synthesize a query graph or change existing graph lineage.
- The coordinator will use case subgraph/missingness/conflict/provenance/family queries with explicit evidence tiers; formal defaults must not hide candidate records and imply they never existed.

**Tests and implementation:**
- [x] Extend the existing synthetic graph test helper to construct a registered query request against a real compiler-produced graph. Derive expected graph identity and node/edge assertions from the fixture, not the query implementation.
- [x] RED: assert public input discovery exposes both exact query modes and that `registry.run(query_request).result["graph_id"]` equals the compiler-produced graph ID. Confirm rejection on current code for the missing mode/contract.
- [x] Implement the typed request, additive input modes, versioned result union and dispatch to existing queries; do not duplicate traversal, integrity validation or reconciliation.
- [x] Verify all seven query kinds through registered calls, including an actual comparison graph for comparison paths. Test wrong graph kind, unknown query/arguments, strict numeric limits, malformed selector combinations, tier/lifecycle handling and truncation.
- [x] Verify altered manifest bytes, sidecar tampering, symlinks, input/output overlap and mixed roles fail closed without source changes or private payload leakage. Hash source artifacts before/after successful and refused queries.
- [x] Verify equivalent identical calls return equivalent bounded facts; query/compilation receipts and output directories do not collide; existing compilation tests keep passing.
- [x] Run `python -m pytest -q tests/test_p0_09_evidence_compiler.py tests/test_registry.py` plus the actual input-contract/Schema test files, then knowledge validation, Schema/Card regeneration checks, repository policy and whitespace checks. Report existing warnings explicitly.
- [x] Commit only this task's reviewed files and provide RED/GREEN commands and outputs in the private report.

## Task 2: Scope-bound coordinator and registered-input execution

**Deliverable:** A confirmed study scope can select and execute currently eligible registered-input checks, inspect their canonical evidence, and continue without requesting redundant approvals; facts, scope or resource changes still stop execution. Deterministic assembly of missing producer-bound scientific inputs is implemented separately in Task 3, not silently replaced by blockers.

**Files:** `src/bridge/web/assessment.py` (new focused coordinator), `app.py`, `provider.py`, `inputs.py`, `evidence.py`; narrow `control.py` additions only to invalidate/stop the assessment through the existing shared fence; narrow additions to `src/bridge/domain/models.py` and `src/bridge/runners/pipeline.py` only where exact scope-derived approval must be represented. Tests in `tests/test_web_assessment.py` and the existing Web/planner/pipeline suites.

**Interfaces and requirements:**
- A private typed `AssessmentScope` binds the confirmed question, selected upload/DataView, input revision, exact reference/knowledge/measurement/role resources, allowed tool modes and finite maximum tool runs/model turns. These are approval-visible limits, not a promise of a hard wall-clock limit.
- `AssessmentCoordinator` owns propose/approve/advance/stop/resume state. It consumes verified registered inputs and receipts, not model-authored scientific objects. Persist authorization and counters before dispatch; retain the original approver/scope identity without forging a fresh human approval for each derived request.
- Preserve exact AnalysisPlan hashes and ToolExecutionPipeline checks. A concrete request is admitted only by deterministic binding rules inside the current approved scope, then checked by the package. New input versions, changed roles/references, comparison/graft, or larger budgets require new approval.
- Reuse existing input construction for already registered selections. Keep one directly used `Inputs.assessment_candidates(state, scope)` entry for concrete requests/bundles, mode, normalized scientific-request fingerprints and blockers; Task 3 adds real producer-aware assembly there. The single-product profile describes dependencies but does not itself materialize inputs. Do not introduce unused hooks or a generic workflow layer. Scientific review false/pending is not changed by scope approval.
- Add a purpose-limited provider action for bounded evidence query, eligible next check, explanation/necessary question, or explicit stop. Hypotheses cite validated evidence aliases; free text cannot change deterministic facts or eligibility.
- After a successful verified tool result, admit eligible already-materialized P0-08/P0-09 checks and consume their canonical new graph versions/receipts; retain exact blockers when such inputs are absent. Task 3 owns measured-domain compilation-input assembly. Do not feed unreviewed standalone observations into a formal compilation path.
- Prevent duplicate unchanged executions, unbounded query/reply loops, stale scope reuse and post-stop continuation. Preserve existing epoch fencing, single-worker execution and interruption behavior.
- Project actual P0-03–P0-06 result summaries with exact units, denominators, state and provenance. Separate directly observed exploratory results from gate-facing measurements. Read no raw cell rows into model context.
- Preserve the prior isolated intake/QC/protocol path; ordinary explanation-only conversations do not start assessment.
- The current scope authorizes checks and resource limits, not an applicable whole-question completion contract. Model requests for `evidence_requirements_reached` remain private audit proposals and produce `blocked / completion_contract_unavailable`; graph-local satisfied requirements or empty evidence cannot establish research completion.

**Tests and implementation:**
- [x] RED: a scope-approved real registered-tool round records one admitted request, processes its verified result and chooses the next allowed action without an extra human approval.
- [x] Implement the smallest private coordinator and scope-admission seam needed by that flow; write no generic workflow framework.
- [x] Test exhausted run/model budgets, repeated unchanged requests, malformed model replies, unavailable inputs, scientific-review blockers, disabled result sharing, input/reference drift, stop/resume and restart interruption.
- [x] Test at least two different real tool result shapes through the same coordinator, with literal expected state/value/denominator assertions and an external-model-only fake.
- [x] Test canonical graph/query version binding and reuse across registered selections; candidate, missing, negative and unavailable results remain distinguishable and do not become formal claims. Task 3 additionally verifies newly materialized measured write-after-query.
- [x] Run focused Web/planner/pipeline integration suites, then commit the smallest reviewed task.

## Task 3: Deterministic scientific input and measured-evidence assembly

**Deliverable:** The coordinator constructs actually derivable inputs from confirmed facts, reviewed applicable resources and verified producer outputs, then continues through the existing scientific packages. A real absent scientific prerequisite remains a blocker; missing assembly code is not presented as an absent fact.

**Files:** `src/bridge/web/inputs.py`, `scientific_inputs.py`, `report_inputs.py`; only the narrow `assessment.py` integration call required by the established Task 2 entry. Tests in the existing Web input/scientific/report suites and `tests/test_web_assessment.py`. A separate focused materialization module requires a controller ruling if the existing files cannot keep responsibilities clear. No changes to package scientific contracts, review signatures, scientific resource content or release policies; the byte-identical resource relocation/package-data/link edits explicitly listed below are the sole resource-file exception.

**Narrow implementation rulings:**
- `Inputs.assessment_resource_ids` may compute the explicit dependency-source resource closure; `AssessmentCoordinator.propose` and `_binding` may pin that closure and its original selections. This does not authorize execution of a dependency tool outside allowed modes.
- `_binding` must select the actual P0-01 `qc_profile_v2` artifact from a verified producer receipt, not the first Schema-compatible JSON. Keep historical records and public Schemas unchanged; test scope proposal after QC already exists.
- For measured P0-08 assembly, consume an explicitly selected, source-supported `DomainGateInput` applicable to the same case/definition as the requirements template. Preserve method/prior/sensitivity/task-validation requirements and bind only verified measurement/spec/QC inputs. Without applicable requirements, report that gap; missingness-only defaults are not measured policy.
- Relocate the existing `plans/resources/seurat-cell-cycle-v5.5.1-candidate.json` and adjacent `seurat-cell-cycle-LICENSE.txt` byte-for-byte to `src/bridge/tool_packages/p0_06_proliferation_stress_response/resources/`. Add only the exact package-data inclusion in `pyproject.toml`; no new Python resource package or dependency is required. Update only the broken links/status sentence in `plans/product-evidence-validation.md`. There remains one maintained resource and license copy.
- Bind the raw candidate JSON hash in the existing scope binding science collection, not `_input_objects`; it is a data resource and has no registered Schema. In the existing public resources list expose `schema_ref=null`, `resource_ref=bridge://resources/seurat-cell-cycle-candidate/v5.5.1`, candidate `object_version`, alias, `sha256` and `source=package_resource`. Adding this one typed `resource_ref` field in the used assessment public-resource projection is allowed; do not add another top-level scope/public field or generic resource framework. Only a real derived ExploratoryProcessInput is registered under its actual Schema. Verify current bytes before construction/admission, and test that raw resource drift invalidates prior scope approval.
- The relocated resource is exposed only for explicitly scope-authorized `P0-06/exploratory_process` assembly, with its exact bytes/hash visible in approval binding. Preserve original gene membership/order, provenance/version, license, `scientific_release_approved=false`, candidate status and no automatic alias/update policy. It is not a ProgramSpec, seven-family assessment, default formal input or a gate-facing MeasurementResult. Verify packaged bytes and runtime access outside the source checkout without installing new dependencies.

**Interfaces and requirements:**
- Consume Task 2's `Inputs.assessment_candidates(state, scope)` entry, exact approved producer/resource closure, typed private scope and canonical registered input/result objects. Do not create a second coordinator or another approval path.
- Add producer-aware P0-03–P0-06 input assembly where required objects can genuinely be derived. The single-product integration profile is the dependency source, not a claim that all prerequisite data exists. Reviewed definitions/methods/programs/windows and genuine biological-unit facts are required inputs, never generated attestations.
- Bind P0-03/P0-04/P0-06 and downstream composition to the exact selected QC DataView when their modes consume that view; preserve parent upload, cell IDs/counts, gene metadata, lineage and denominator. No fallback to the original whole upload when selected-view binding is required.
- Keep candidate/exploratory routes distinct from gate-facing measurements. Reuse one eligible role definition for P0-03/P0-05 and retain unresolved mass; P0-06 exploratory S/G2M does not supply the other program families or a formal measurement.
- Construct measured P0-08 DomainGateInput and P0-09 EvidenceCompilationBundle only from verified eligible canonical producer outputs and applicable versioned policy/resources. Candidate missingness-only ReportInputs remains compatible; no model-authored MeasurementResult, evidence-family reassignment, review promotion or formal report release.
- Register constructed objects deterministically with hashes and producer provenance. Repeated preparation reuses identical objects; changed inputs/resources create explicit new versions and respect the existing scope/fact fences.
- After an eligible tool result, materialize the next authorized check, compile a new canonical graph version when permitted and expose it to the coordinator. Queries are read-only and cannot themselves be counted as new biological evidence.

**Tests and implementation:**
- [ ] RED: real registered producer output plus confirmed/resource inputs yields the expected downstream request without hand-authored backend request injection. Missing construction must fail before implementation.
- [ ] Cover each implemented P0-03–P0-06 route with exact selected-view/parent/count/resource assertions and genuine missing-review/unit/program blockers. Include stale source, changed view and same-role-definition checks.
- [ ] Verify real measured P0-08/P0-09 assembly against package contracts, with literal expected values, denominators, evidence families and candidate/formal boundaries; retain existing missingness-only behavior.
- [ ] Prove a registered result → graph query → eligible discriminating next check → verified append/new graph version through the coordinator using synthetic engineering data and only an external-model fake. A scientific prerequisite may not be bypassed to make this test pass.
- [ ] Verify deterministic reuse, admission/resource counters, provenance drift and no post-stop continuation. Run focused Web/coordinator integration suites, self-review and commit this task only.

## Task 4: Version-bound Step 7 portrait and real-case acceptance

**Deliverable:** The researcher can inspect every core assessment axis, the exact evidence behind it, and meaningful continuing/stopping state in the real Web path.

**Files:** `web/src/components/ResultsPane.tsx`, `PlanCard.tsx`, `ScientificInputs.tsx`, `web/src/types.ts`, `api.ts`, necessary `App.tsx` integration; use existing test locations and add one focused assessment component only if responsibility warrants it. Update `docs/agent-integration.md`, `docs/web-preview.md`, `docs/decision-log.md` for the approved scope-derived execution contract, relevant validation record, and this plan with observed evidence.

**Interfaces and requirements:**
- Consume the server-owned assessment projection, scope identity and exact evidence/graph versions. UI never recalculates scientific values, thresholds or scores.
- Always display cell state, target identity, regional identity, development, whole-product/non-target composition, and proliferation/stress. The seven process families each show measured, missing input or unavailable plus their specific reason; S/G2M does not stand for all seven.
- Separate findings, conflicts, prerequisites and next actions. Provide local evidence-chain drilldown and complete denominator/table fallback; no total score, radar grade, ranking or color-only status.
- Scope approval shows finite resource limits and known unresolved scientific inputs; stop and explicit resume remain accessible. Fact correction shows affected evidence and requires confirmed partial recomputation.
- Real acceptance starts from one actual uploaded case and accepted facts/QC, not a backend-injected scenario. Verify a genuine tool result, graph query, discriminating next action, canonical update and same-version portrait. Existing isolated runtime credentials/config remain within their configured workflow; production deployment is separate.
- Source-state/product-role/window/program and biological-unit approvals remain scientific gates. Record exact missing reviews and real-data blockers without claiming full Step 7 completion.

**Tests and implementation:**
- [ ] RED: show all core axes from a mixed measured/missing/unavailable projection without invented zeros or hidden blockers.
- [ ] Implement portrait, scope controls and evidence drilldown using the existing typed artifact/result components.
- [ ] Test exact values/denominators, source dependencies, keyboard access, stale-version correction, stopping and disabled actions.
- [ ] Run browser tests/build and one isolated real-model/real-input acceptance; capture canonical receipts and page evidence on the server.
- [ ] Re-run the full backend suite, explicitly cover opt-in compiler tests, verify 12 registered tools, knowledge and figure registries, repository policy, whitespace and source/publication boundaries.
- [ ] Independently review the whole branch; leave unresolved scientific prerequisites explicit. No automatic merge or deployment.

## Scientific review and full-completion gate

The biological review of 25 source-state cards precedes product-role/window approval and any signed FreezeGate. Existing locked runner restrictions remain unchanged. The controller will reconcile source evidence and prepare concrete review decisions alongside implementation; it will not impersonate the scientific reviewer.

Full Step 7 completion requires source-reviewed applicable resources, genuine sample/unit facts, measured eligible domains and the real Web evidence-feedback chain. Engineering connectivity alone, exploratory observations, a blocked report, all-missing states, or a green suite do not meet this gate.

## Verification evidence

- Baseline at `fa6017b3`: `python -m pytest -q tests/test_agent_domain_planner.py tests/test_p0_09_evidence_compiler.py tests/test_web_evidence.py` — **279 passed, 2 existing dependency deprecation warnings**, 212.76 s. This is engineering baseline evidence, not scientific validation.
- Task 1 registered graph queries at `ff7aa7ec` (integrated as `b17c6c04`): **411 passed, 9 existing dependency deprecation warnings**, 371.83 s, covering compiler/registry/Web inputs/shared contracts/SDK/integration. Schema/Card regeneration was byte-identical; knowledge, repository policy and whitespace checks passed. Independent review found no blocking issue; public Schema/runtime selector-validation parity and existing dependency warnings remain nonblocking follow-up items.
- Controller integration checks at `b17c6c04`: registered graph query selection **45 passed**, 227 deselected, 60.93 s; registry **10 passed**, 5.04 s; no warnings in either focused run. This establishes registered retrieval behavior only, not coordinator, real-case or scientific completion.
- Task 2 scope coordinator at `fb341ad2`, fix `5733f65a` (integrated as `3adc8b5c` / `17890ad0`): the original broad command produced **499 passed, 43 skipped, 17 warnings** in 574.58 s, including 27 duplicated executions; unique coverage was **472 passed and 43 skipped**. Root resolved all skipped protocol cases with the existing pinned BPL 2.4.0 runtime: **119 passed, 2 warnings, no skips**, 104.89 s. The completion-claim review finding passed two RED/GREEN regressions, then **29 passed, 6 warnings**, 111.11 s; scoped independent re-review found it addressed with no new breakage.
- Root integration at `17890ad0`: `python -m pytest -q tests/test_web_assessment.py tests/test_agent_domain_planner.py tests/test_tool_execution_pipeline.py` with the existing runtime and pinned compiler setting — **52 passed, 6 existing warnings, no skips**, 109.81 s. These are synthetic engineering/provenance checks, not real D28 or scientific qualification. Task 3 measured assembly and Task 4 UI/real-case acceptance remain open.
- Further evidence is appended only after the stated run completes. Completed transient task reports stay private; stable reusable facts are promoted once.
