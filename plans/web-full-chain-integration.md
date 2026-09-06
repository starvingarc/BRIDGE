# Web Full-Chain Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement the ready tasks. Steps use checkboxes.

**Goal:** Connect real, approved Web analysis stages to the existing P0 toolkit and report actual chain coverage without invented scientific inputs.
**Architecture:** Retain PlanBuilder, exact AnalysisPlan approval, ToolExecutionPipeline and LocalWorkflowExecutor. Materialize each stage only after its real inputs exist; retain prior plans and canonical ToolRuns.
**Tech Stack:** Existing Python/FastAPI runtime, React/assistant-ui client and server-side Playwright.
**Spec:** [Agent integration](../docs/agent-integration.md), [local runtime](../docs/local-agent-runtime.md), [Web preview](../docs/web-preview.md), and the user-approved design below.
**Status:** in_progress; full-chain real-data acceptance blocked on source facts and the explicit P0-05 projection gap.

## Approved design and current finding

The user approved reusing the existing tools/executor, connecting Web inputs, staged approval and per-tool results; single-product, comparison and independent graft paths remain the complete target. This plan does not replace those targets with an offline replay.

The current genuine upload lacks declared sample/capture/independence relationships. Historical reconstructed-design objects must not be registered as genuine user facts. Current P0-02 observation outputs do not define P0-05 soft mass or close its single-source accounting. No conversion that invents weights, unknown labels or scientific definitions is authorized.

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
- [ ] Integrate approved Task 1/2 commits, validate combined interface and update bounded repository file budget only for actual added files.
- [ ] Document the new input route, stage approvals/history, P0-02 candidate boundary, no-graft zero-input behavior, still-unimplemented constructors and required private deployment configuration.
- [ ] Build a wheel, install to a new private target, verify imports come from that installation rather than source, run focused suite and 12-tool describe/input-contract smoke.
- [ ] Start a separate authenticated loopback preview using the current configured provider. Do not alter the live instance.
- [ ] Server browser flow: new conversation -> real H5AD -> explicit assay/counts -> QC approval -> privately entered source metadata supported by actual source records -> P0-02 approval -> real artifacts -> explicit no-graft -> P0-12 approval -> verify no graft expression entered request -> follow-up -> refresh -> desktop/mobile screenshots -> registered download hashes and SQLite/ToolRun receipts.
- [ ] Record each actual execution, actual partial/scientific state, missing V3 or lineage, and P0-03–P0-11 not executed. No 12/12 Web claim for this increment.
- [ ] Collect full-chain blockers without silently changing P0-05 projection or scientific input ownership.
- [ ] Run repository policy, knowledge validation, schema parity where touched, git diff --check and public-content privacy scan.
- [ ] Independent exact-head review, focused correction, required GitHub gates before any requested merge/deployment; preserve live state and all private versioned evidence.

## Full-chain continuation conditions

- Genuine source metadata and explicit owner assertions establish biological-unit relationships and product/process context.
- A scientist-reviewed, explicit P0-02-to-P0-05 composition contract resolves missing soft mass and single-source accounting without relabeling evidence.
- Remaining materializers read only declared dependencies, and all real required artifacts exist.
- Two genuine product cases/design support comparison; expression-graft requires actual specimen/animal/timepoint/linkage data.
- Only then can fresh browser tests count the corresponding branches toward 12/12 actual tool coverage.

## Validation record

Baseline main is b458ab846102310b9138f6f5b0a524027569f1b8. The preceding fresh Web test executed P0-01 only; server private evidence is retained separately. Tasks 1 and 2 are implemented and independently reviewed. The fresh installed-package Web conversation executed P0-01, P0-02 and explicit zero-input P0-12; figure cards, registered download integrity, staged history, refresh and narrow layout were checked. The installed service suite passed 44 tests and the client suite passed 24 tests plus its production build. Provider JSON Action compatibility was verified with the configured provider and the real browser. Private evidence binds the source revision, installed wheel, complete conversation and canonical receipts. Public required CI and PR closeout remain pending; full-chain continuation conditions above remain open.
