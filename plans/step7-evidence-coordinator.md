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
- [ ] Extend the existing synthetic graph test helper to construct a registered query request against a real compiler-produced graph. Derive expected graph identity and node/edge assertions from the fixture, not the query implementation.
- [ ] RED: assert public input discovery exposes both exact query modes and that `registry.run(query_request).result["graph_id"]` equals the compiler-produced graph ID. Confirm rejection on current code for the missing mode/contract.
- [ ] Implement the typed request, additive input modes, versioned result union and dispatch to existing queries; do not duplicate traversal, integrity validation or reconciliation.
- [ ] Verify all seven query kinds through registered calls, including an actual comparison graph for comparison paths. Test wrong graph kind, unknown query/arguments, strict numeric limits, malformed selector combinations, tier/lifecycle handling and truncation.
- [ ] Verify altered manifest bytes, sidecar tampering, symlinks, input/output overlap and mixed roles fail closed without source changes or private payload leakage. Hash source artifacts before/after successful and refused queries.
- [ ] Verify equivalent identical calls return equivalent bounded facts; query/compilation receipts and output directories do not collide; existing compilation tests keep passing.
- [ ] Run `python -m pytest -q tests/test_p0_09_evidence_compiler.py tests/test_registry.py` plus the actual input-contract/Schema test files, then knowledge validation, Schema/Card regeneration checks, repository policy and whitespace checks. Report existing warnings explicitly.
- [ ] Commit only this task's reviewed files and provide RED/GREEN commands and outputs in the private report.

## Task 2: Scope-bound coordinator and real input materialization

**Deliverable:** A confirmed study scope can select and execute currently eligible checks, inspect their canonical evidence, and continue without requesting redundant approvals; facts, scope or resource changes still stop execution.

**Files:** `src/bridge/web/assessment.py` (new focused coordinator), `app.py`, `provider.py`, `inputs.py`, `evidence.py`, `scientific_inputs.py`, `report_inputs.py`; narrow `control.py` additions only to invalidate/stop the assessment through the existing shared fence; narrow additions to `src/bridge/domain/models.py` and `src/bridge/runners/pipeline.py` only where exact scope-derived approval must be represented. Tests in `tests/test_web_assessment.py` and the existing Web/planner/pipeline suites.

**Interfaces and requirements:**
- A private typed `AssessmentScope` binds the confirmed question, selected upload/DataView, input revision, exact reference/knowledge/measurement/role resources, allowed tool modes and finite maximum tool runs/model turns. These are approval-visible limits, not a promise of a hard wall-clock limit.
- `AssessmentCoordinator` owns propose/approve/advance/stop/resume state. It consumes verified registered inputs and receipts, not model-authored scientific objects. Persist authorization and counters before dispatch; retain the original approver/scope identity without forging a fresh human approval for each derived request.
- Preserve exact AnalysisPlan hashes and ToolExecutionPipeline checks. A concrete request is admitted only by deterministic binding rules inside the current approved scope, then checked by the package. New input versions, changed roles/references, comparison/graft, or larger budgets require new approval.
- Reuse existing input builders and the single-product integration profile. Build missing objects only from confirmed facts, versioned resources and verified producer outputs; absence remains a named blocker. Scientific review false/pending is not changed by scope approval.
- Add a purpose-limited provider action for bounded evidence query, eligible next check, explanation/necessary question, or explicit stop. Hypotheses cite validated evidence aliases; free text cannot change deterministic facts or eligibility.
- After a successful verified tool result, append measured evidence through existing P0-08/P0-09 compilation contracts when eligible and otherwise retain the exact blocker. Reuse current graph versions and receipts. Do not feed unreviewed standalone observations into a formal compilation path.
- Prevent duplicate unchanged executions, unbounded query/reply loops, stale scope reuse and post-stop continuation. Preserve existing epoch fencing, single-worker execution and interruption behavior.
- Project actual P0-03–P0-06 result summaries with exact units, denominators, state and provenance. Separate directly observed exploratory results from gate-facing measurements. Read no raw cell rows into model context.
- Preserve the prior isolated intake/QC/protocol path; ordinary explanation-only conversations do not start assessment.

**Tests and implementation:**
- [ ] RED: a scope-approved real registered-tool round records one admitted request, processes its verified result and chooses the next allowed action without an extra human approval.
- [ ] Implement the smallest private coordinator and scope-admission seam needed by that flow; write no generic workflow framework.
- [ ] Test exhausted run/model budgets, repeated unchanged requests, malformed model replies, unavailable inputs, scientific-review blockers, disabled result sharing, input/reference drift, stop/resume and restart interruption.
- [ ] Test at least two different real tool result shapes through the same coordinator, with literal expected state/value/denominator assertions and an external-model-only fake.
- [ ] Test graph write-after-query semantics and version reuse; candidate, missing, negative and unavailable results remain distinguishable and do not become formal claims.
- [ ] Run focused Web/planner/pipeline integration suites, then commit the smallest reviewed task.

## Task 3: Version-bound Step 7 portrait and real-case acceptance

**Deliverable:** The researcher can inspect every core assessment axis, the exact evidence behind it, and meaningful continuing/stopping state in the real Web path.

**Files:** `web/src/components/ResultsPane.tsx`, `PlanCard.tsx`, `ScientificInputs.tsx`, `web/src/types.ts`, `api.ts`, necessary `App.tsx` integration; use existing test locations and add one focused assessment component only if responsibility warrants it. Update `docs/agent-integration.md`, `docs/web-preview.md`, relevant validation record, and this plan with observed evidence.

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
- Further evidence is appended only after the stated run completes. Completed transient task reports stay private; stable reusable facts are promoted once.
