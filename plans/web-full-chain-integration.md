# Web Full-Chain Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement the ready tasks. Steps use checkboxes.

**Goal:** Connect real, approved Web analysis stages to the existing P0 toolkit and report actual chain coverage without invented scientific inputs.
**Architecture:** Retain PlanBuilder, exact AnalysisPlan approval, ToolExecutionPipeline and LocalWorkflowExecutor. Materialize each stage only after its real inputs exist; retain prior plans and canonical ToolRuns.
**Tech Stack:** Existing Python/FastAPI runtime, React/assistant-ui client and server-side Playwright.
**Spec:** [Agent integration](../docs/agent-integration.md), [local runtime](../docs/local-agent-runtime.md), [Web preview](../docs/web-preview.md), and the user-approved design below.
**Status:** in_progress; full-chain real-data acceptance blocked on source lineage and explicit P0-05 mass / P0-06 unresolved-state contract gaps.

## Approved design and current finding

Tasks 1–3 below record the completed staged increment. Tasks 4–6 extend that
baseline to contract-driven access for every P0 tool; their requirements replace
the earlier `not_connected` capability restriction, without changing the genuine
data acceptance conditions.

The user approved reusing the existing tools/executor, connecting Web inputs, staged approval and per-tool results; single-product, comparison and independent graft paths remain the complete target. This plan does not replace those targets with an offline replay.

The current genuine upload lacks declared sample/capture/independence relationships. Historical reconstructed-design objects must not be registered as genuine user facts. Current P0-02 observation outputs do not define P0-05 soft mass or close its single-source accounting. No conversion that invents weights, unknown labels or scientific definitions is authorized. The follow-up contract audit also found that P0-06's current observation input cannot preserve P0-02 source-conflict evidence losslessly; mapping it to unknown, unavailable or a winning state is not authorized.

The first executable increment adds the existing raw-count-compatible P0-02 candidate path and independent P0-12 no-graft path to the existing QC conversation. P0-03–P0-11 remain explicitly not connected until their constructors and real prerequisite facts can be defined faithfully. This increment is not 12/12 Web completion. A normalized single-product profile requires its own explicitly declared matrix semantics and true lineage; a raw-count QC DataView must not be relabeled.

## Global Constraints

- All project code, tests, builds and data remain on the designated server workspace.
- Use the configured current model provider only. Provider context contains conversation and bounded execution status, never biological measurements, source-family values, private paths or credentials.
- No P0 Tool ID, scientific Schema, score, threshold, state definition or release authority change in this Web increment.
- Preserve candidate/shadow and domain_score=null; preserve partial, unavailable, not_assessed and explicit input-construction blockers.
- No fabricated metadata, weights, replicas, attestations, references, measurements, successful exports or tool execution.
- No old-request replay as proof of a freshly constructed Web chain.
- Keep the current deployed preview running during development. Test a separate instance before any rollout.
- Shared policy, docs and integration are root-owned; implementation workers write only their assigned server worktree paths.
- No private host/path/environment/key/resource identity, hash, biological result or scale in public Git content.
- One integration PR; any necessary P0 contract change is a separate module decision, not hidden in this branch.

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

## Full-chain continuation conditions

- Genuine source metadata and explicit owner assertions establish biological-unit relationships and product/process context.
- A scientist-reviewed, explicit P0-02-to-P0-05 composition contract resolves missing soft mass and single-source accounting without relabeling evidence.
- Remaining materializers read only declared dependencies, and all real required artifacts exist.
- Two genuine product cases/design support comparison; expression-graft requires actual specimen/animal/timepoint/linkage data.
- Only then can fresh browser tests count the corresponding branches toward 12/12 actual tool coverage.

## Validation record

Baseline main is b458ab846102310b9138f6f5b0a524027569f1b8. The preceding fresh Web test executed P0-01 only; server private evidence is retained separately. Tasks 1 and 2 are implemented and independently reviewed. The fresh installed-package Web conversation executed P0-01, P0-02 and explicit zero-input P0-12; figure cards, registered download integrity, staged history, refresh and narrow layout were checked. The installed service suite passed 44 tests and the client suite passed 24 tests plus its production build. Provider JSON Action compatibility was verified with the configured provider and the real browser. Private evidence binds the source revision, installed wheel, complete conversation and canonical receipts. Required CI passed for the preceding staged public revision. The contract-driven
extension has its own final-head checks before the same Draft PR is updated;
full-chain genuine-data conditions above remain open.
