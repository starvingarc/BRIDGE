# Research Workspace Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task. The approved design is the scope; no additional design approval is needed for routine implementation decisions.

**Goal:** Deliver the approved soft laboratory interface with persistent research workspaces, shared original materials and independent conversations.

**Architecture:** ResearchStore owns account-scoped research metadata and immutable originals; SessionStore continues to own conversations and scientific state. A narrow HTTP integration imports selected material through existing input contracts. The React shell composes the research home, materials drawer and stage-aware conversation/results using existing scientific components.

**Tech Stack:** Existing Python/FastAPI, React/TypeScript, CSS and Lucide; no new dependencies.

**Spec:** [Research workspace design](../docs/research-workspace.md)

## Global Constraints

- Research directly contains conversations and shared materials; no mandatory intermediate experiment/batch layer.
- Server-side implementation and verification; preserve existing services and user data.
- Account ownership, origin protection, finite storage/upload limits and immutable source provenance apply to every new route.
- No changes to scientific calculations, confirmation/approval semantics or report integrity.
- Publish, PR, merge and production deployment remain separate authorization boundaries.

## Review Focus

- Cross-account IDs and file URLs return no private existence, name, bytes or state.
- Shared originals remain usable after the originating conversation is deleted and after restart.
- Adding or selecting material cannot copy another conversation's messages, confirmations or results, or silently change an active plan.
- Navigation, polling and delayed requests cannot overwrite a different research/session or reset a user's chosen view.
- Old sessions, archives and empty research workspaces remain reachable without invented data or automatic biological grouping.

---

### Task 1: Durable research and material ownership

**Files:** Create `src/bridge/web/researches.py`, `src/bridge/web/research_http.py`, `tests/test_web_researches.py`; modify `sessions.py`, `service.py`, `http.py`, `access.py`, `quotas.py` in `src/bridge/web/`.

**Interfaces:**
- `GET/POST /api/researches`; create `{name, description?}`. Summary has `id, name, description, created_at, updated_at, session_count, material_count`.
- `GET/PATCH /api/researches/{rid}`; detail adds `materials` with `id, name, kind, size, created_at`.
- `POST /api/sessions` accepts optional `research_id`; session and summary expose nullable `research_id`.
- `POST /api/sessions/{sid}/research` assigns an ungrouped session to an owned research; `PATCH /api/sessions/{sid}/title` changes only its display title.
- `POST /api/researches/{rid}/uploads` stores a validated H5AD, protocol or supporting text/table source; `GET /api/researches/{rid}/materials/{mid}` downloads only the verified original.
- `POST /api/sessions/{sid}/share-material` accepts `{upload_id}` to explicitly retain legacy H5AD originals in the research library. Assignment itself does not share old files.
- `POST /api/sessions/{sid}/research-materials` accepts `{material_id, upload_id?}`. H5AD creates an independent session-local input; protocol requires a current H5AD `upload_id` and uses existing intake attachment. Repeated selection is idempotent. Table storage does not automatically join a scientific input.
- `ResearchStore` receives SessionStore, never Service. HTTP coordinates existing domain calls; byte validation and persistence remain with their owners.

- [x] Write behavior tests for ownership/origin denial, research/session persistence, independent histories, immutable selected H5AD, explicit protocol selection, quota enforcement, corrupt sources, legacy assignment, busy sessions and origin-session deletion.
- [x] Run `python -m pytest -q tests/test_web_researches.py`; expected failures for absent research routes.
- [x] Implement the above interfaces and quota accounting, preserving legacy no-research sessions and existing input contracts.
- [x] Run `python -m pytest -q tests/test_web_researches.py tests/test_web_ownership.py tests/test_web_session_management.py tests/test_web_large_upload.py`; expected all pass.
- [x] Commit the validated backend change.

### Task 2: Research home and live materials/session navigation

**Files:** Create `frontend/src/components/ResearchHome.tsx`, `ResearchMaterials.tsx` and `ResearchCover.tsx`; modify `frontend/src/App.tsx`, `api.ts`, `types.ts`, `components/Sidebar.tsx`, `Conversation.tsx`, `ProductIntake.tsx`, `styles.css`; add `frontend/tests/research-workspace.test.tsx` and adapt affected app fixtures.

**Interfaces:** Consume Task 1 endpoints with typed `ResearchSummary`, `Research` and `ResearchMaterial`. App owns selected research/session and request generation. Home receives research list and explicit create/open callbacks. Materials drawer receives research and optional current session; successful selections report the returned session through the existing generation fence. Sidebar retains SettingsDialog and session management.

- [x] Write tests for login home, create/open research, independent conversations, shared material availability and explicit selection, preserved old/archived sessions, error retry and late-response navigation fencing.
- [x] Run focused frontend tests; expected the new behavior to fail before implementation.
- [x] Build the real research home, shared drawer and sidebar using the approved cell covers, glass chrome and opaque reading surfaces. Keep empty states honest and upload busy/size errors actionable.
- [x] Add stage-aware conversation/results controls by adding a view selection prop to the existing ResultsPane, without changing scientific tool output. Preserve an explicit view choice while polling.
- [x] Run affected frontend tests and `npm --prefix frontend run build`; expected pass.
- [x] Commit the validated frontend change.

### Task 3: Integration and browser acceptance

**Files:** Update `docs/research-workspace.md`, `docs/web-preview.md`, `frontend/README.md`, `docs/BRIDGE_PRD.md` organization wording and `plans/README.md`.

**Interfaces:** Reuse all existing account/model and scientific APIs. An isolated acceptance instance uses synthetic data and its own storage; production remains untouched.

- [x] Reconcile maintained documentation with delivered organization, material-selection behavior and limits.
- [x] Run focused cross-module tests, frontend suite/build, repository static checks and `git diff --check`; expected pass, with any pre-existing failure reported separately.
- [x] Inspect actual desktop and narrow browser pages: account login, research home/create, independent sessions, shared H5AD/protocol, loading/error/empty states, result navigation and settings.
- [x] Restart the acceptance instance and verify research/material/session persistence and shared originals after deleting a disposable conversation.
- [x] Review the complete branch in a fresh review context, fix consequential findings, and present the verified preview plus remaining publication boundary.

## Validation record

- Targeted backend suite: 51 passed, one private-H5AD test skipped; the subsequent smaller document-ceiling check passed with all 15 research tests. These checks cover ownership, restart, original integrity, independent selection, legacy assignment/sharing and concurrent file IO.
- Full frontend suite: 280 passed. After final error wording and result-header changes, the affected research/navigation/result/API tests passed (46 tests), and the production build passed. The existing large-bundle warning remains.
- Static repository checks and diff formatting passed. No scientific schema or computation changed.
- Isolated browser acceptance used synthetic files: desktop 1440 x 960 and narrow 390 x 844; research creation, materials upload/selection, protocol attachment, background review and account entry remained accessible. A real P0-01 QC run on four synthetic observations completed and registered 22 artifacts; it is an engineering example, not biological qualification.
- A real process restart retained the research, selected inputs, completed QC and original downloads. Deleting a disposable conversation preserved the shared original; a new conversation had no inherited inputs or artifacts.
- Fresh code review found protocol target loss and cleanup ordering under a file deletion error; both were corrected. A concurrency probe demonstrated global lock blocking during material copy/share, then passed after moving file IO outside the existing per-session guard.
- Integration and deployment follow the separate release procedure; a merged change does not confer scientific qualification.
