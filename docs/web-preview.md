# Web preview

BRIDGE uses individual accounts for private local and
[internal multi-user testing](#internal-multi-user-testing). It supports the
first six steps of the canonical [PRD workflow](BRIDGE_PRD.md#61-agent-总体工作流)
within their accepted scope: research question, materials, necessary questions,
source-backed fact confirmation, scoped plan/resource approval and QC. Uploaded
protocols can be represented and reviewed under the approved BPL design.

The current source also connects a finite, approved evidence-coordination loop
and a researcher-facing assessment portrait. Synthetic connectivity is not
real-input acceptance or full Step 7 scientific completion. Conditional comparison selection and private research report delivery are
connected; qualified product conclusions and public export remain separate gates.
Twelve packages are reachable through contract-driven inputs and separate
approval, but access is not automatic scientific-object construction or
end-to-end product qualification. Public documentation describes source
behavior and public-safe evidence; it does not disclose or certify a particular
private deployment.

| Current path | What it establishes | What it does not establish |
|---|---|---|
| Intake and protocol review | Source-bound draft facts, explicit user confirmation and versioned BPL review | Product identity, experiment execution or complete semantic validation |
| P0-01 QC | Input structure, declared matrix semantics, observed QC evidence and updated eligibility | Product quality, complete filtering or downstream domain evidence |
| P0-02 cell-state path | Candidate source-aware cell-state evidence when configured inputs are eligible | Reviewed product roles, purity or released assignment |
| Contract-driven input panel | Contract discovery, explicit registration, plan approval and normal execution | Automatic construction of every prerequisite or scientific approval |
| Scope-bound assessment | Approved registered checks, graph retrieval/update, local evidence portrait and finite counters | Whole-question completion, reviewed seven-family program mapping or product qualification |
| Conditional comparison and graft | Verified registered inputs, comparability reasons, explicit selection and separate plan approval | New data access permission, inferred comparability or pre-transplant backfill |
| Private research report | Same-version Chinese HTML, JSON snapshot, CSV statements and SVG, with exact claim verification | Qualified biological conclusions or public export authorization |

The bounded candidate card can materialize source-backed product/role and
optional regional/development candidates after exact confirmation. A separate
missingness-only P0-08 path can compile candidate missing requirements through
P0-09 and build an internal P0-10 draft whose actual release state remains
blocked. It creates no domain MeasurementResult and offers no qualified export.

## Research and conversations

After login, the research home lists account-owned workspaces. Create a research,
then start conversations with freely chosen purposes. The header and composer
open **研究资料**: add original files once, then explicitly select **用于本会话**.
Each conversation retains its own messages, input declarations, confirmations,
approvals and results. Other conversations can see the shared originals without
inheriting analysis state. Decorative cell covers contain no measured data.

A conversation remains busy until its worker has finished cleanup and released
its task reservation, including completion callbacks. A prepared plan becomes
actionable only then; clients should follow the returned status and presentation
actions rather than the presence of a plan alone. Early plan approval returns a busy
response without approving or executing the plan. Busy/quota responses explain
the admission limit rather than claiming that scientific execution failed.
Stopping during cleanup remains stopping until the reservation is released.

H5AD selection makes a private session copy; protocol selection associates a
shared source with an explicitly selected H5AD. CSV/TSV files can be stored and
downloaded but are not automatically joined to scientific inputs. Shared
originals remain after a conversation is deleted. Each account can create 256
researches and each research can retain 128 materials; storage quotas include
both originals and copies. Documents and sample tables are limited to 25 MiB
and the configured upload ceiling, whichever is smaller.

The research-object API can import a protocol material without an H5AD:
POST to the research's protocols collection with material_id and expected_version=0.
The selected account model produces a source-linked BPL draft and workbench fields;
the pinned compiler and source checks must pass before the draft is saved.
GET the version's formalization subresource to inspect source excerpts, unresolved
questions and compiler limitations. A successful import remains unreviewed and does
not confirm experimental validity. Clear version-level and reagent-level unconfirmed
fields only after reviewing and correcting the source-linked draft, then explicitly
confirm the version before starting a run. The version-level review fields and
failure codes are specified in [the object contract](../plans/research-objects.md#75-文档导入草稿与来源核对133).
Frontend integration and an actual laboratory protocol review remain separate
acceptance steps.

Declared sample H5AD attachments can run the registered [quick atlas mapping](quick-atlas-mapping.md)
pipeline when a private reference catalog and matching tree are configured. This is
a candidate reference mapping with source-bound display positions; frontend integration,
calibrated age/OOD and differentiation-chain measurements remain separate acceptance gates.

**历史会话** keeps older ungrouped work reachable. **移入研究** changes only its
organization; **保存到研究** explicitly shares an existing H5AD original.
Existing protocol attachments remain readable in their original conversation.
Research and conversation names are editable, and session archive/restore/delete
retain the existing behavior. Scientific batches are not inferred from folders.

The workspace initially emphasizes conversation. **实验背景** opens existing
intake and assessment components; **结果** opens the result reader. Results-ready
state can foreground results until the user chooses a view. Polling preserves
that choice. Desktop retains a conversation beside results; narrow screens use
one selected panel. See [research workspace](research-workspace.md) for boundaries.

Uploads are limited to eight H5AD files per conversation. The default file
ceiling is 4 GiB, with a separate 4 GiB logical-HDF5 ceiling and a 100,000,000
element ceiling for any single dataset. All three are finite server settings;
an operator can lower them or raise the two byte ceilings only as far as 16 GiB
and the element ceiling only as far as 1,000,000,000. Scientific JSON objects
remain limited to 2 MiB each and 512 registrations per conversation.

The request boundary checks declared and received body size. The upload route
copies FastAPI's spooled file into a private temporary file in bounded chunks,
computes SHA-256 incrementally, validates HDF5 structure, and atomically binds
the final file to session state only after success. Failed and interrupted
temporary or unregistered files are removed; another upload cannot register in
the same conversation concurrently. Intake and planning recheck the same open
file descriptor before direct HDF5 metadata access rather than constructing a
second whole-file byte string. External links, virtual datasets, excessive
nesting and object counts remain rejected. These engineering checks do not
infer sample relationships, join an unreviewed metadata table, rewrite
normalized input or establish scientific qualification.

### Research objects and workbench API

The M1 object routes under /api/researches/{rid} persist manual protocols and their
editions, differentiation runs, samples, leads and proposed actions. The wire
contract and revision rules are maintained in [research objects](../plans/research-objects.md).
Workbench responses contain actual research objects; an empty research returns
empty arrays. Every run binds an immutable confirmed protocol edition, including
when a newer draft exists. Consumers resolve that binding against all editions,
not only the latest one.

ResearchObjectStore owns a separately versioned objects.json in each private
research directory. It uses the existing single-process store lock, checks the
expected revision inside the same critical section as the atomic file replacement,
and bounds both object count and serialized bytes. Existing research metadata,
original materials and conversation files are not migrated. Corrupt or unsupported
storage fails explicitly rather than appearing as an empty research. Sample material
links reference this research's H5AD originals without copying matrices or creating
analysis sessions. HTTP applies the existing account and origin checks, including
for administrators using normal research routes.

In this storage-only increment, approval records consent but does not launch a
mapping worker or produce an assessment. Mapping execution and document-to-draft
import remain separate work. The molecule catalog is read from the existing
examples/protocol-visualization/molecules/data/catalog.json in source installations;
if that optional resource is absent, non-null catalog links are refused while
manual reagent text and null links remain usable. No catalog entry is inferred by name.

## Researcher response and diagnostics

Missing interpretation-to-graph bindings prevent publication and display a
specific explanation. A native producer identity mismatch prevents report
construction when no exact matching receipt remains; ordinary historical
collisions alongside a valid producer do not trigger degradation. These issues
reuse the existing presentation envelope and result-state derivation. Counts
from previous failures do not create a permanent active warning.

The graph view explains when its optional explanation overlay cannot be loaded,
even when there are no candidate-composition measurements. The saved graph,
measurements and equivalent list remain usable, and the researcher can retry.
HTTP errors, invalid/oversized responses, mismatched graph bindings and transport
failures show the same bounded message; request cancellation during navigation
does not. A successful retry clears the notice.

The development diagnostics field `degradations` contains only `code` and
positive integer `count`. Its closed codes are
`interpretation_graph_binding_unavailable`,
`report_context_producer_identity_mismatch` and `graph_display_unavailable`.
Counters persist with the session and count failed server attempts: explanation
publication, report-candidate preparation and graph-preview validation,
respectively. Repeated failed attempts increment the count; these are not counts
of distinct scientific problems or missing measurements. Existing sessions start
with no recorded counts. Browser-only transport/response failures are visible
in the browser but cannot be inferred from server counters. No client telemetry
endpoint or additional diagnostic store is introduced.


The authenticated session response now has one server-derived `presentation`
object for the researcher-facing stage and allowed actions. Its stage is one of
`needs_input`, `needs_confirmation`, `needs_approval`, `working`,
`results_ready`, `partially_complete`, `blocked` or `idle`. Plan approval and
assessment-scope approval remain distinct actions. A resume action is shown
only when the existing authorization, binding, budget and duplicate-admission
checks would actually allow it; the projection never grants authority.

User-visible failures use a bounded issue with `error_version`, `error_id`,
`user_message` and `results_state`. `results_state` is derived from currently
registered researcher results and evidence, not inferred from an error name.
Internal exception text, stop codes, model-call counters and receipt details are
not part of the normal response. The normal assessment still includes its
question, approved scope, blockers, evidence, candidates, freshness, portrait,
hypotheses, data view and resources.

New conversation messages carry a server-owned source:
`user_input`, `server_template`, `provider_admitted` or
`deterministic_evidence`. Ordinary method and clarification answers may remain
natural even when no result summary is available. A model statement about the
current result must use the result summary supplied for that turn and cite its
current `E0`/`E1` evidence alias. Bounded state/value conflicts are replaced by
`解释尚未通过核对`; the rejected text is not stored as a public message. This
check is deliberately finite and is not a claim of complete semantic
verification. Existing unclassified assistant messages remain visible with a
provenance warning but are neither sent back to the model nor included in a new
conversation transcript. User questions and admitted method/scientific content
remain in the transcript.

Development diagnostics are a separate, authenticated
`GET /api/sessions/{sid}/diagnostics` projection. It contains only bounded
environment/package, session/error, plan-step, assessment-budget/turn and
tool-run states, plus a closed list of degradation codes and counts. It excludes prompts, message bodies, response bodies, paths,
credentials, uploaded data, receipt names/hashes and scientific values. The
route is 404 unless the server was started as `development` with diagnostics
explicitly enabled. Browser parameters, headers and self-declared roles cannot
enable it; acceptance and production always expose the same researcher view.

## Session management

Each history row has an actions control for archive/restore and deletion. The
normal list hides archived sessions; **已归档** shows them with a restore action.
Archiving is an organizational flag: it preserves messages, uploaded copies,
plans, results and approval state, and does not make the session immutable.
Opening or continuing an archived session keeps it archived until restored.
Historical sessions without this field default to unarchived.

Deletion requires an explicit confirmation naming the session. It removes the
session directory, including messages, uploaded copies and generated results;
other sessions and external reference/source files are not deleted. The current
view and its saved selection are cleared when that session is archived/deleted,
and late responses cannot restore the old view.

Management mutations require the existing authenticated cookie and same-origin
boundary. `GET /api/sessions` includes `archived` and `status` in each summary;
optional `archived=true` or `archived=false` filters the result. `PATCH
/api/sessions/{sid}` accepts only a strict boolean `archived`; `DELETE
/api/sessions/{sid}` uses an empty JSON body, as mutating requests require a
content length. Uploads and queued/running workers must finish before either
operation, including the short interval after their display status settles.

Deletion first moves the exact session directory out of the visible namespace,
then removes it without following nested symlinks. A cleanup failure returns an
explicit retry message and retains only the hidden pending directory; retrying
DELETE for the same ID completes cleanup. Other sessions can still load and the
server can restart. This is application-level deletion, not secure erasure of
filesystem backups or the shared workflow event journal. See the
[privacy boundary](privacy-and-provenance.md#session-lifecycle).

## Table previews and downloads

Registered Parquet tables have a checksum-verified, read-only preview. It shows
at most 100 rows and 24 columns, accepts at most 8 MiB of stored Parquet bytes
and 32 MiB of declared uncompressed row-group data, and emits at most 200,000
bytes of preview JSON. Text cells are visibly truncated after 1,000 characters.

Unsupported or over-limit content falls back to download. Null and non-finite
values are not replaced with zero; large integers use exact display strings.
The original download keeps its registered bytes and checksum. Previewing does
not run analysis, send rows to the model or grant export authority.

### QC figure explanations

The first Web QC step preserves the audit-only default: it does not automatically
select a candidate MeasurementSpec or filter observations. Measured count metrics
and candidate QC flags are separate results. An absent specification
(`measurement_spec_not_selected`) means flags were not evaluated, not zero
flagged observations or a pass for every cell.

The **输入质控** figure section is available before a formal product assessment.
QC figures stay separate from that assessment's scope-bound evidence.
In **图表说明与限制**, the read-only figure preview explains the exact saved QC
receipt: count-metric availability, the selected registered candidate rule (or its
absence), whether flags exist, and whether selection was actually applied.
This explanation also covers historical figure sets; it is a Web presentation
addition to the original long description, not a rewritten scientific artifact.
Original downloads, render/data bindings and checksums remain unchanged.

For candidate flags, a maintainer must review the declared raw counts and assay,
then explicitly select a matching scRNA/snRNA rule through the tool interface and
rerun QC. The current Web interface does not offer QC-rule selection; researchers
do not need to invent a MeasurementSpec. Flag generation alone does not remove
observations. Explicit selected-view behavior remains defined by the
[QC tool](../src/bridge/tool_packages/p0_01_input_qc/README.md).

## Start a private instance

One-time setup on a Linux server needs Python 3.12, Node.js 22.12 or newer,
`flock`, and a built frontend. From the checkout, prepare the environment:

~~~bash
python3.12 -m venv .venv
.venv/bin/python -m pip install ".[qc,web,evidence,process]"
npm --prefix frontend ci
npm --prefix frontend run build
~~~

Create a private configuration for **your own server account**, outside the
checkout. The launcher reads this trusted shell file; do not source a file
supplied by another user, and never commit credentials or put them in a browser
bundle. Its default location is `$HOME/.config/bridge/web.env` (or under
`$XDG_CONFIG_HOME`). Prepare it once:

~~~bash
mkdir -p "$HOME/.config/bridge"
chmod 700 "$HOME/.config/bridge"
vi "$HOME/.config/bridge/web.env"
chmod 600 "$HOME/.config/bridge/web.env"
~~~

Enter your own values in the file, replacing every placeholder:

~~~bash
BRIDGE_START_STORAGE='/absolute/path/account-storage'
BRIDGE_WEB_PORT=8765
BRIDGE_RUNTIME_ENV='production'
BRIDGE_WEB_DIAGNOSTICS=0
~~~

Initialize the selected empty private storage before the first launch. The command
prompts for the administrator password; never put passwords in argv or history:

~~~bash
python -m bridge.web.account_admin --config /absolute/path/web.env initialize --root /absolute/path/account-storage --username operator --environment production
~~~

Account/password login is the only authentication method. Remove the retired
`BRIDGE_WEB_TOKEN` and `BRIDGE_WEB_MULTI_USER` assignments from both the private
configuration and inherited environment; either setting now fails startup with
an explicit cleanup message. Old shared tokens and cookies cannot authenticate.
Existing initialized account storage and account cookies remain valid. Unowned
legacy sessions are not imported or deleted; retain them separately and initialize
a new empty account directory.

The model environment variables `BRIDGE_WEB_MODEL_BASE_URL`, `BRIDGE_WEB_MODEL`
and `BRIDGE_WEB_MODEL_API_KEY` are optional initial defaults. Without them, the
service still starts and accepts login. Click the account ID at the bottom of the
sidebar, then choose **模型** in settings to manage
providers and select a model. The shared provider and saved private providers appear
in the same list. DeepSeek/OpenAI presets prefill the service address and existing
action protocol; **自定义模型 API** accepts an OpenAI Chat Completions endpoint.
Each provider has a unique ID, display name, API address, write-only key and model
catalog. Add model IDs manually or use **获取可用模型**, then select returned entries.
Catalog reads use `GET /models`; they do not send research data or save configuration.
A failed catalog can be replaced by manual model entry. A connection test sends only
fixed text and may incur a small charge; neither operation qualifies scientific use.

The UI uses `/api/models` for directory reads, `/api/models/providers` for saves,
`/api/models/providers/{id}` for deletion, and `/api/models/select`, `/catalog` and
`/test` for selection and probes. Directory projections omit keys. Provider IDs and
model IDs are bounded; each account can save 32 providers with 100 models each,
within a 128 KiB private profile. Catalog responses are limited to 1 MiB and 2,000
entries. Old single-configuration API routes remain compatible with this store.

An administrator can edit the shared provider in the same dialog. Its first model
is the default for new accounts. Other models in its catalog may be selected per
account. A new private provider does not change the current selection until the
user chooses its model. Account-level selection supplies new-conversation defaults.
Existing conversations independently retain their selected provider, model and
effort; removing a selected model or provider makes the next task unavailable
instead of silently changing the conversation's model. Editing connection details
for a retained model affects later tasks. Running and queued tasks retain their
captured connection and effort. Scientific resource checks and result-sharing
controls remain live.

Shared defaults take precedence over environment variables after restart. Keys
are plaintext only in owner-readable private server configuration (`0600`), never
returned to the browser or written to browser storage. A blank key retains the
previous key only for the same account, provider and unchanged API address. Private
providers never inherit a shared key. Addresses cannot contain credentials, query
parameters or fragments. Private endpoints retain the restricted transport described
below. Loading old personal configurations does not rewrite them; editing stores the
provider directory format. Back up private model configuration before upgrading;
older program versions cannot read a newly saved directory, so rollback requires
the matching configuration backup. Keep these files out of Git, logs and shared backups.

### Conversation model controls

The backend supports `GET/PUT /api/sessions/{sid}/model-selection`. PUT accepts
`{provider_id, model, effort}`; each conversation persists its own choice and new
conversations inherit the same account's last successful choice. If no effort can
be inherited, the current model's declared default is saved as the conversation's
actual level. Missing defaults remain null: the UI must say the level is not
declared, rather than label it automatic or imply a verified setting. Existing
null choices are resolved once on load after valid metadata arrives; persisted
levels never change just because the provider changes its default. A PUT with
null explicitly resets to the currently declared default. Legacy sessions
without any choice field initialize from the account on first load. The normal session response includes
`model_selection`. The dedicated endpoint additionally returns `availability`,
`capability` and `task_configuration`; the latter is the last started task's model,
provider ID, connection version and effort, and can differ from the next-task choice.
Changing the next-task choice is allowed during a running/queued task. Archived
conversations must first be restored. This backend contract is ready for the
input-area controls; the current settings selector still uses the legacy account
endpoint until the separate frontend integration is delivered.

`POST /api/models/providers/{provider_id}/capabilities` with `{}` refreshes effort
metadata from a saved service's `/models`. It sends no research data and saves a
bounded, account-private capability cache tied to endpoint, credential, protocol
and model catalogue. Directory entries expose `capabilities` by model ID. Each
entry has `status` (`supported`, `unsupported`, `unknown`), `supported_levels` and
`default_level`. Missing or malformed metadata stays unknown; a model name alone
does not establish support. A failed refresh returns `ok: false` and retains the
previous result's timestamp rather than presenting it as a fresh success. Unsaved
catalogue reads still do not persist data. The metadata contract follows the
[DeepSeek model catalogue](https://api-docs.deepseek.com/api/list-models/).

A declared default and an explicitly chosen supported effort are both captured
with the task and applied to ordinary conversation, skill selection,
interpretation generation/review/repair, intake extraction and protocol
formalization. When metadata declares no default, `effort: null` omits both
reasoning effort and the thinking switch; BRIDGE does not substitute an internal
high/low/disabled policy. The provider controls that unconfirmed default.
Explicit reasoning, or an undeclared DeepSeek default that may enable reasoning,
allows at least 32,768 output tokens and a 600-second request timeout; existing
larger allowances remain. DeepSeek
thinking requests omit incompatible forced tool choice. A native skill continuation
carries the provider's required reasoning field only within the bounded request
sequence; reasoning is not added to the conversation or accepted as evidence.
The generic compatible path sends `reasoning_effort` without assuming DeepSeek's
thinking switch. These settings do not change tool, consent or scientific gates.
The standalone research document-import endpoint has no conversation ID: it
captures the account's most recent model and effort (or declared default) before
extraction. Stale effort capabilities reject the import before sending research
content; changing the choice during extraction does not alter that request.

Invalid or removed model choices return `409 model_selection_unavailable`;
unconfirmed/unsupported explicit effort returns `409 model_effort_unavailable`;
a configuration change during refresh returns `409 model_configuration_changed`.
Responses contain safe `detail` codes and actionable `user_message` text. Rejection
does not schedule a task or silently substitute a model. Model credentials remain
in the private provider store, never in conversation selection records.

Account passwords and provider keys are separate credentials. The optional
`BRIDGE_START_PYTHON` selects an existing Python 3.12 interpreter and takes
precedence over this checkout's `.venv`. An explicit process environment override
takes precedence over the config value. Without it, the launcher tries `.venv`,
the current Python 3.12 interpreter, then Python 3.12 on PATH; it does not install or upgrade the interpreter. The
optional `BRIDGE_START_STORAGE` selects an absolute private directory.
Production keeps the compatible `$HOME/.local/state/bridge/web` default (or
`$XDG_STATE_HOME/bridge/web`); development and acceptance default to separate
`bridge/<environment>/web` directories. Every storage directory has a private
environment marker and must be initialized for that environment before launch.
A nonempty legacy directory cannot become account storage by using
`--bind-existing-storage`; that retired option is rejected and never assigns
ownership. Marker mismatches and incomplete initialization are refused. Browser
cookie names include the environment, and login credentials are revocable within
each account database. Same-host instances cannot replay another store's login. A second
launcher cannot use the same storage concurrently. The launcher also fixes
`BRIDGE_WEB_STATIC_DIR` to this checkout and `BRIDGE_WEB_ORIGIN` to its
loopback port; it ignores an older config's `BRIDGE_WEB_STORAGE`, static
directory and origin.

The installed `bridge-web` command, `python -m bridge.web`, and the thin
checkout `./start.sh` wrapper use the same configuration and preflight. The
wrapper needs a system `python3` (3.8+ suffices to select the configured 3.12);
the actual service requires Python 3.12. Configuration is trusted shell syntax,
sourced exactly once with automatic export after owner, regular-file, non-symlink
and exact `0600` checks. Assignment-only files work without `export`.
Unknown or extra arguments fail, including after `--help`.

~~~bash
bridge-web --help
bridge-web --print-version
bridge-web --config /absolute/path/web.env --env development
bridge-web --config /absolute/path/web.env --test
bridge-web --config /absolute/path/web.env --test status
bridge-web --config /absolute/path/web.env --test stop
~~~

`--config` overrides `BRIDGE_START_CONFIG`, which overrides the XDG default.
`--env` overrides `BRIDGE_RUNTIME_ENV`. Default loopback ports are production
8765, acceptance 8766, development 8767; `BRIDGE_WEB_PORT` overrides these and
`--port` overrides that. `--test` always selects acceptance, ignores configured
production port/storage, and uses acceptance's default port and XDG state
directory. If the preferred port is occupied, the OS selects a free loopback
port; the launcher keeps that socket open through startup and displays the
actual URL. An explicit `--port` fixes the port and fails if it is occupied.
The origin and instance metadata use the selected port; an explicit development
`--origin` remains unchanged. Port fallback does not bypass the storage lock.
`--test` rejects a conflicting `--env`; it never enables reload or diagnostics. Diagnostics still require
development. Existing acceptance data is retained across runs; this is not a
temporary directory or a complete test runner. Initialize the acceptance XDG
storage directory separately with `account_admin initialize --environment acceptance`
before the first `--test` launch; development storage similarly requires its own initialization.

Checkout launches use `frontend/dist`; installed wheels require an explicit
`BRIDGE_WEB_STATIC_DIR` pointing to a separately built client. Frontend assets
are not included in the wheel. Both paths derive storage from
`BRIDGE_START_STORAGE` or the environment's XDG default and ignore legacy
`BRIDGE_WEB_STORAGE` and `BRIDGE_WEB_ORIGIN`. Development may explicitly set
`--origin http://127.0.0.1:5173` for Vite; other environments reject this override.
Migrating a direct-module deployment therefore requires a private config and
`BRIDGE_START_STORAGE`; it cannot bypass checks through environment-only launch.

All entries validate Settings, frontend assets, a held loopback socket, storage
binding and an exclusive lock before serving. No provider URL or credential is
printed. Only the subsequent health response confirms readiness; preflight is
not a scientific or model-call validation.

The locked storage holds a private `.bridge-web.pid.json` with instance identity.
`status` shows PID, environment, port and starting/running state. `stop` uses a
nonce-authenticated loopback control connection and waits up to ten seconds for
the storage lock to release. It never signals a PID from a stale file. A stopped
or unverifiable instance returns nonzero; a timeout means exit is not yet
confirmed. Select the same config/environment/`--test` as the original launch.
Only the lock owner replaces stale metadata; normal shutdown removes its record.

The service listens only on `127.0.0.1`. From your own computer, keep an SSH
tunnel open in another terminal (use the actual port shown at startup or by
`status`, and replace the user and host):

~~~bash
ssh -L 8765:127.0.0.1:8765 your-user@your-server
~~~

Then open `http://127.0.0.1:8765` in your local browser and log in with
your account username and password, or create a new account after acknowledging
the testing notice. For a quick service check on the server,
`curl http://127.0.0.1:8765/api/health` returns `{"status":"ok"}` after
startup. Use Ctrl+C to stop the foreground service; disconnecting SSH usually
ends it too. The launcher remains in the foreground and does not install
packages or expose the port publicly. Use the matching `stop` command from another
terminal for graceful shutdown.

Additional private settings may be included in the same file:

| Setting | Meaning |
|---|---|
| BRIDGE_RUNTIME_ENV | development, acceptance or production; defaults to production |
| BRIDGE_WEB_DIAGNOSTICS | 0 by default; 1 is valid only with development |
| BRIDGE_WEB_MODEL_ACTION_PROTOCOL | Explicit json or deepseek_tools protocol; other values fail startup |
| BRIDGE_WEB_TRUSTED_ANCESTORS | Optional startup-only approved ancestor identity pins |
| BRIDGE_WEB_MAX_UPLOAD_BYTES | H5AD file-byte ceiling; default 4294967296, allowed range 1 through 17179869184 |
| BRIDGE_WEB_MAX_H5AD_LOGICAL_BYTES | Sum of HDF5 dataset logical bytes; default 4294967296, allowed range 1 through 17179869184 |
| BRIDGE_WEB_MAX_H5AD_DATASET_ELEMENTS | Per-dataset element ceiling; default 100000000, allowed range 1 through 1000000000 |
| BRIDGE_WEB_CELL_STATE_MEASUREMENT_SPEC_REF | Optional registered cell-state measurement definition; no scientific default |
| BRIDGE_WEB_CELL_STATE_CANDIDATE_RUNTIME_REF | Optional exact controlled candidate model binding |
| BRIDGE_CELLSTATE_CANDIDATE_CATALOG | Private candidate model and development-receipt catalog |
| BRIDGE_REFERENCE_ROOT | Root containing versioned reference snapshot directories; missing configuration raises `reference_root_not_configured`, and unavailable snapshots raise `reference_snapshot_not_found`; manifest and resource integrity checks still apply |
| BRIDGE_WEB_SHARE_RESULT_SUMMARIES | Exactly 1 enables owner-authorized bounded summaries; unset/0 disables |
| BRIDGE_WEB_PROTOCOL_COMPILER_PYTHON | Optional source-pinned BPL 2.4.0 runtime |

P0-06 resource settings are private, server-owned paths. For
`exploratory_programs`, set both `BRIDGE_P006_PROGRAM_RESOURCE_PATH` and
`BRIDGE_P006_PROGRAM_RESOURCE_SHA256` to the pinned MSigDB Hallmark resource
declared by `ScientificInputs.register_program_input`. Missing configuration
or a digest other than the registered source raises `program_resource_not_configured`.
The file must be absolute, free of symlink path components, at most 2 MiB and
match the configured SHA-256; invalid paths or bytes are rejected.

For `directed_programs`, `BRIDGE_P006_PLURI_RESOURCE_PATH` and
`BRIDGE_P006_DISSOC_RESOURCE_PATH` select separate reviewed sources. Their
expected hashes are pinned in `DIRECTED_PROGRAM_RESOURCES`, not supplied by
the browser or additional environment variables. Missing per-program paths are
skipped; configured paths undergo the same path, size and hash checks. These
settings serve different modes and are not fallback aliases for the generic pair.

The scientific release workflow additionally reads
`BRIDGE_CELLSTATE_RELEASE_ROOT` (root of release-ID directories) and
`BRIDGE_CELLSTATE_REVIEWER_REGISTRY` (trusted reviewer registry path). Missing
values raise `cell_state_release_root_not_configured` and
`trusted_reviewer_registry_not_configured`, respectively. These are controlled
scientific-team inputs, not ordinary Web setup requirements. Configuring them
does not satisfy freeze gates or establish scientific qualification.

The default json protocol requires one typed JSON action. deepseek_tools uses
the same validated application actions through native function definitions.
Thinking and effort follow the task's captured conversation selection in both
protocols; no assessment-specific effort override is applied. Reasoning requests
allow at least 32,768 output tokens for reasoning and the final structured action,
with a 600-second HTTP timeout. The approved
scope still owns the model-turn, tool-run and literature budgets; a longer output
allowance does not authorize extra requests. Model reasoning is not admitted as
an explanation or report evidence. Routine JSON actions retain disabled thinking;
other model families retain their existing behavior. The official
[thinking-mode contract](https://api-docs.deepseek.com/guides/thinking_mode/)
defines the request switch. JSON mode guarantees JSON syntax, not compliance with
the application action schema; both protocols still use the same server validation.
These settings do not establish explanation quality or scientific validity.

Saved whole-product composition summaries from P0-03/P0-05 have a bounded
128 KiB allowance; other result limits and record-count limits still apply.
The model context retains a separate 128 KiB ceiling measured using the compact
UTF-8 JSON serialization sent to the provider. Identical composition arrays
can reference their source row; identical row fields use explicit defaults.
Absent fields inherit defaults and explicit null overrides them. Missing genes,
mismatched counts, citation roles and distinct units are preserved; public
results, canonical artifacts and historical receipts are unchanged.

Malformed, mixed or unsupported responses fail closed. Outside an approved
scope, model output can only prepare an unapproved plan. Within the exact scope,
the server admits a reconstructed eligible request using its original approval;
the model cannot create authority or supply execution parameters. Exact package
eligibility is always checked locally. All public launch commands use the
same preflight and storage lock described above.

Operators must verify the installed package, built client and configured
dependencies for their own deployment; repository source status is not a
deployment receipt.

After authentication, `GET /api/config` returns the three active upload/HDF5
limits so the client can explain and preflight the real server policy. The
backend remains authoritative. A declared request, received body or uploaded
file above the file ceiling returns HTTP 413 with
`detail=request_too_large` and `max_upload_bytes`. A structurally valid H5AD
above a logical or per-dataset ceiling returns HTTP 413 with
`detail=h5ad_resource_limit`, its stable `reason`, and both H5AD ceilings.
Neither response weakens authentication, file-count or structure checks.

## A typical conversation

The product workflow is defined in [PRD section 6.1](BRIDGE_PRD.md#61-agent-总体工作流).
Upload the actual material and review the extracted facts before confirming
them. Absent information, explicit-but-unparseable information, conflicts and
unknowns remain distinct. Approve the applicable quality-check plan separately;
its observations and denominators establish input readiness, not product quality.

Product-only or source-only corrections can preserve compatible QC. Assay,
matrix or QC-relevant metadata changes invalidate the binding. Old versions and
receipts remain traceable; the server never rehabilitates corrupt historical
evidence by silently substituting a newer run.

Protocol review follows the
[approved BPL design](protocol-formalization.md).
The model proposes source-backed fragments; the server assembles one
authoritative representation and runs a fixed compiler under limits. Source
coverage, compiler status, human review and biological meaning are separate.
Unknown or ambiguous source facts stay unresolved; a compiler default is never
accepted as the missing experimental value. The complete known-facts editor stays
accessible even when extraction supplies a question list. Researchers can enter
known matrix semantics, product category, sampling context and source family,
leave uncertain facts unknown, then review the exact changes and explicitly
confirm them before preparing any analysis.

## Stop and input corrections

Stop fences subsequent model/planning work. A non-interruptible tool step may
finish; its actual outcome remains recorded. Stopping does not retract inputs.

Ordinary chat does not edit committed declarations. A correction opens an exact
before/after review:

- Confirm change applies only the displayed ID/digest-bound proposal.
- Discard change drops that proposal.
- Keep current inputs explicitly resolves review without an edit.

None approves analysis. Each proposal includes a checksummed impact preview
computed from saved requests and their transitive artifact dependencies.
A product-name-only edit affects report presentation; other product-context edits
preserve compatible QC and native observations but invalidate dependent product
interpretations. A source-family correction, including a concurrent product-context
edit, preserves compatible raw QC but invalidates source-dependent analysis when
no QC inputs changed. Previously invalidated receipts cannot be reused. Assay, matrix and QC-relevant metadata
changes invalidate the linked chain. Unrelated uploads remain reusable.
Confirmed changes mark affected receipts historical without deleting them or
their downloads. Additional requirements, graph queries and graph append requests
retain their existing sources; replacing source inputs still follows the actual
dependency chain. All new executions require approval.

When continuing native saved observations with both sufficiency checking and
graph append approved, the next sufficiency inputs are frozen at proposal time.
The append is then prepared from verified results admitted within that scope.
A historical manual append selection does not freeze a temporary missing-result
blocker. Out-of-scope results, changed inputs and failed producer runs do not
satisfy the dependency; old selections, receipts and graph versions stay intact.

Domain coverage in an appended graph combines new observations with the latest
active records for that same case. Updating one domain does not reset another
domain to “measurement not provided”. Superseded or invalidated observations
cannot be revived by a saved producer. Unavailable values remain unavailable;
retaining an observation does not satisfy independent-validation requirements.

The assessment projection compares the scope's fact/resource binding with the
current session. Pending review is shown separately; a confirmed revision or
resource change labels its evidence historical without rewriting receipts or
its original stop reason. Select the affected checks in a new finite scope for
partial recomputation. No correction automatically executes tools or grants a
new budget. A revised report receives a new immutable snapshot while previous
report bytes remain downloadable.

## Research evidence and reports

Native candidate cell-state observations and exploratory process measurements
can enter the existing evidence compiler through genuine sufficiency checks.
The graph retains exact source receipts, measurement definitions, denominators,
evidence state and family dependencies. Repeated observations from the same
RNA source are not independent votes. Graph append preserves prior records;
large query summaries omit only topology with explicit omission counts and
retain the underlying graph artifact.

A research report binds one graph version, input revision, data view, product
context, interpretation history and statement registry. The existing claim
verifier checks these exact bindings before exposing private Chinese offline
HTML and JSON/CSV/SVG attachments. Reports distinguish observations, proposed
explanations and unresolved scientific qualification. Unavailable measurements
remain null, and failed model development remains visible rather than being
promoted to a validated product result. Current claims, measurement summaries and
native context use the graph's effective version state, not the historical
`active` flag in an immutable source record. Superseded, invalidated and
inapplicable records remain in the source history but cannot become current
report findings. CSV retains the original `lifecycle_state` and `source_json`,
and separately exposes `effective_lifecycle_state` plus `applicability`; current
applicable evidence requires `active` and `applicable` in those latter columns.

Each newly registered report attachment also records the validated input
revision, graph ID/version/manifest hash, snapshot hash, deterministic renderer
ID and snapshot object version. The server compares those bindings with the
current input revision and latest valid graph of the same identity on every
read. Matching reports have `content_class=research_report` and
`access_state=current`. A stale or legacy report is listed as
`historical_unreviewed` with an explicit warning; its original bytes remain
unchanged, and direct display/download is blocked until the authenticated
operator calls that artifact's `/acknowledge` route. Acknowledgement permits
retrieval of those exact bytes but does not make the report current or
scientifically revalidated.

Other registered researcher results use `content_class=user_result` and
`access_state=available`. Classification comes from the server's registered
artifact provenance, never its filename or extension. Developer manifests,
logs, provider request/response material, receipts and report drafts use
`developer_diagnostic`; they are omitted from the user artifact list and denied
consistently by direct download, preview and acknowledgement routes. Renaming
one of those files cannot change its class.

## Conditional comparison and graft

The comparison directory uses only objects already registered in the current
private session. It shows descriptive-comparison, background-only and excluded
entries with deterministic reasons. A frozen comparison specification and
matching measured product evidence are required. Selection confirmation binds
the exact input revision and source checksums; preparing the plan still requires
ordinary separate approval.

Actual graft entry additionally requires explicit preparation linkage, animal,
post-transplant timepoint and biological-replicate identifiers. The linked
pre-transplant ProductCase is pinned without modifying its receipts. Missing,
ambiguous or changed sources block this entry. An explicit no-graft declaration
is a separate absence record, never an authorized graft assessment.

## Analysis inputs

When a stage needs more context, the operator:

1. selects a registered tool and current mode;
2. selects compatible supplied, system-owned or canonical prior objects;
3. registers missing scientific objects in their named roles;
4. saves the selection, prepares a plan and separately approves its digest.

Schemas, role cardinality and eligibility come from the installed package. The
server owns request IDs, versions, paths, checksums and output directories.
The panel accepts no command, arbitrary parameter or raw ToolRequest, and it
does not invent role rules, soft mass, comparison design or report claims.

Canonical graph manifests must come from verified tool runs. P0-08 and P0-10
policies use package-owned options. Comparison and graft are independent
branches. P0-11 creates or audits a local candidate; it is not a network upload,
publication action or approval.

Input selections can reference up to the session registration budget of 512
objects, so multi-domain sufficiency checks retain every registered measurement.
Verification shares a producer's complete artifact scan only within one
synchronous input operation. It discards that cache at the boundary; each use
still checks the object bytes, dependencies, canonical binding and invalidation
state. Later requests and execution phases recheck the producer artifacts.

## Interface and ownership

The server owns authentication, session state, exact approvals, artifacts and
tool execution. The React client renders that state; it is not a second workflow
engine.

| Route group | Responsibility |
|---|---|
| login, sessions, messages and stop | Authenticated conversation lifecycle and cancellation fence |
| uploads, intake, protocols and input changes | Bounded source extraction, versioned review and exact confirmation |
| scientific-inputs and clarification | Candidate questions and objects without execution or scientific promotion |
| analysis-inputs, prepare-analysis and approve | Contract selection, unapproved plan and exact plan approval |
| report-inputs | Separately prepared P0-08/P0-09/P0-10 stages |
| assessment/propose, assessment/approve, assessment/resume | Finite scope, actual prerequisites, exact consent and explicit continuation |
| artifacts, preview and transcript | Authenticated, integrity-checked retrieval |

Execution uses PlanBuilder, immutable approved requests,
ToolExecutionPipeline and LocalWorkflowExecutor. The service does not execute
model-generated commands or invoke scientific libraries outside registered
packages.

## Privacy and interpretation

- Default provider context contains conversation text and bounded status, not
  tool-owned biological measurements.
- With explicit owner authorization, allowlisted aggregate QC/cell-state
  summaries and the purpose-specific assessment projection may be shared. Raw matrices, observation rows, source/sample
  identity, private paths, credentials and provenance hashes remain local.
- Shared summaries preserve actual values, denominators and missingness and
  remain candidate/shadow with domain_score=null. They are not anonymous-data
  certification or public-export permission.
- Model replies are not P0-10-verified reports. Candidate drafting cannot
  approve plans, change tool values or select arbitrary paths.
- Downloads remain private artifacts. A display-redacted copy is not the
  canonical tool input or proof of publication eligibility.
- Missing, unknown, unavailable, negative and alert remain distinct. No
  clinical, safety, potency, GMP or absolute-ranking claim is authorized.

See [privacy and provenance](privacy-and-provenance.md),
[Agent integration](agent-integration.md), the [Tool Package index](tool-packages.md)
and the [Web validation history](validation/README.md).

## Cell-state and product assessment

Result and explanation citations can open their saved evidence graph. The result
panel owns navigation; the graph view resolves checked local object references.
Query record citations stay bound to the original graph version. Tool observations
match exact producer or measurement versions only in graphs admitted by the
assessment; ambiguous or missing references are reported without substituting
another record. These local navigation identifiers are excluded from model context.
Selecting another saved version clears the cited-node focus.


The overview's assessment panel prepares an explicit question, uploaded sample,
allowed modes and resource ceilings before any execution. Proposal calls the
same deterministic candidate preparation used during execution; it can register
derived objects, but does not run a tool/model, change confirmed facts or
selections, grant authority, or consume counters. Each candidate distinguishes
blocking prerequisites from non-disqualifying interpretation gaps.

Approval binds the exact scope ID/digest, input revision, data view, resources
and limits: at most 32 tool runs and 64 model turns. The researcher chooses
smaller limits in the form. Exact-plan approval remains a separate path.
Scope-derived plans retain the original scope authorization. Stop fences the
worker; resume explicitly rechecks current facts/resources and preserves used
counters. Prior stop phases remain inspectable with their original reasons and
then-used counters, including after correction staging or discard. Exhausted
limits or changed bindings require a new scope. Biological check names and
necessary input actions are shown first; raw tool/mode IDs and reason codes
remain in expandable technical details.

The scope form has a separate, default-off choice to generate a private
research report after a cited explanation. Allowing the report tool alone is
not this request. The choice appears in the approval summary and is bound to
the exact scope digest. After an accepted explanation, the same Continue
control states that continuing will generate the report. The server then
rechecks the current input, graph, explanation, authorization, budget and exact
candidate before running the existing report tool; it does not ask the model
to choose again. A valid graph and compatible measurements from an earlier
scope can be reused without rerunning them. Older scopes and scopes without
this choice retain ordinary continuation. A completed report ends its scope;
an admitted report that fails or is interrupted is not retried in place.
The local report remains research-only and is not automatically published.

The portrait always includes cell state, target identity, regional identity,
development, whole-product/non-target composition and proliferation/stress.
Values, numerator/denominator scopes, missingness and evidence versions are
server-owned. Findings, prerequisites, competing explanations and next actions
are separate; there is no combined score or ranking. Seven process families
remain independently visible. The registered exploratory S/G2M route covers
only cell cycle; without an applicable reviewed mapping, other families remain
unavailable. Verified program IDs remain visible locally without being used to
infer a family.

The result overview presents five expandable cards: cell state, target/regional
identity, development, whole-product composition and proliferation/stress.
Target and regional identity retain separate states inside their shared card.
Opening a card reveals existing figures, original values/denominators and
evidence links. Scope approval, prerequisites and technical fields are grouped
separately; pending approval remains visible as an action, not hidden as a result.

`portrait[].context_evidence_aliases` is an optional display-only link for target
and regional axes to the latest available reference-similarity context admitted
or explicitly reused in this scope. It does not change the axis state, summary,
identity measurements or scientific qualification. An unreadable latest context
does not fall back silently to an older valid one. Card figures consume their
bound evidence artifacts; other historical attachments remain independently
accessible and are not aggregated into the current portrait.

Candidate scientific inputs consume the versioned development review, including
parent-only and unavailable states. These states cannot be promoted into target,
non-target, developmental or regional identities by ordinary confirmation.
A completed source review is distinct from a reviewed product-role definition:
when the latter is missing, the interface names that gap rather than asking the
researcher to confirm the same facts again. Candidate composition and reference
context remain inspectable; they do not establish target purity, developmental
age, transplant suitability or a qualified product assay. Previously proposed
drafts with different source bindings must be regenerated before confirmation.

Complete manual selections for target/regional assessment and whole-product
hard-count accounting use the same scope-pinned product definitions, roles and
canonical QC/source view checks as automatically assembled selections. Supplying
all fields does not bypass these checks. Other modes retain their package input
contracts; this is not a new scientific approval or resource-registration API.

Local evidence links bind displayed artifacts to the exact receipt and original
artifact identity/hash. A graph query follows its actual source manifest and
graph version, not the latest output of that tool. The same artifact viewer
provides bounded figure/table/text previews and complete authenticated downloads.
These browser-only projections are not public-safe exports. The supported
pre-query compiler receipt (0.4.2 with result contract v0.1) remains readable
under the current compiler without rewriting its graph or original artifacts.
Historical reads validate that recorded contract and exact integrity bindings;
new execution still requires the current registered version. Selecting a query
without its canonical graph produces a preapproval blocker, not execution.

Model hypotheses must cite supplied per-turn aliases; validated citations are
resolved back to canonical local evidence. See the purpose-specific
[privacy contract](privacy-and-provenance.md#assessment-purpose).
A stop such as `no_discriminating_check` or
`completion_contract_unavailable` does not establish whole-question completion.
Observed engineering evidence and remaining real/scientific gates are recorded
in [Step 7 validation](validation/step7_evidence_coordinator_20260911.md).

## Researcher presentation and diagnostics

Default views answer the current research question, show the analysis stage and
pending action, and let users expand values, denominators, figures and sources.
Keep meaningful limitations beside the affected observation. Ordinary discussion
does not require a fixed report template or repeated confirmations.

Observations, hypotheses and unknowns remain distinct. An unknown replicate
count is not zero; missing evidence is not opposition; values with different
method units cannot be ranked without a comparability basis. A method failing
qualification does not establish a cause for product differences. Explanations
that fail evidence checks cannot become accepted interpretations or new reports.

Diagnostics are controlled by server configuration and authentication, not only
hidden in the frontend. Historical reports retain their original bytes and
version labels; current views and new exports must refer to the same evidence
snapshot. Dialogue readability, recovery and correction still require the real
user-flow acceptance in the [mainline plan](../plans/step7-evidence-coordinator.md).

## 产品与空间参考联动配置

`BRIDGE_WEB_SPATIAL_REFERENCE_MANIFEST` 可选，指向受控 JSON 清单。未配置时保留独立产品 UMAP，并显示参考不可用。读取仅投影 H5AD 的 `obs` 与 `obsm`，不运行分析、读取 `X` 或更改输入。

`BRIDGE_WEB_WORKBENCH_TREE` 可选，指向工作台发育树的 JSON 展示载荷（受控图谱派生，不进入仓库）。只读、需登录，校验字段形状后原样投影；未配置时工作台使用合成示意树。打开研究即进入工作台的培养箱；方案、实验记录与样本读取研究内对象，接口缺失时才回退为标注的示例；每次实验与研究各有绑定的对话。功能顺序见[用户旅程与功能路线](../plans/user-journey.md)。

清单字段由 `web/spatial_reference.py` 的 `ReferenceManifest` 校验：`version`、`reference_id`、`vocabulary_version`、受控 `data_root`、相对 `file`、文件 `sha256`、`coordinate_key`、`type_column`、可选 `capture_column`、完整 `types`、`stage`、`coordinate_convention`（默认图像 y 向下）、`crosswalk` 和可选 `model`。数据路径必须在配置的根目录内；客户端仅使用清单生成的 capture ID。`model` 包含独立的模型 `stage`、相对 `file`、`sha256`、`attribution` 与 `license`；可选 `plane_hypothesis` 仅接受 `near_sagittal_model_landmark` 和显示单位的 `offset`（−0.7 至 0.7）。该方向假设只适用于现有 CS15 查看器，不能表示组织配准。模型只经鉴权资源路由读取。

`crosswalk` 包含版本、两侧词表版本和条目。每条记录 `product_state_id`、`spatial_type_id`、`relation`（`same_type` 或 `broader_type`）、`review_state`（`reviewed`、`pending`、`rejected`）与具体 `basis`。只有存在审阅依据的 `reviewed` 条目可高亮；候选注释的科学资格不因此改变。清单、真实数据与对应表不入 Git。

同一捕获单元中的多个组织块保持原坐标，不按位置推断切片层序。未提供验证过的配准变换时不显示组织底图。无对应与已对应类型在当前捕获中为零分别显示。文件、字段或词表不匹配时明确拒绝读取；文件内容身份或清单变更会使展示上下文失效。

配置空间参考后，现有评估候选会列出同一 QC 视图缺少的候选注释或表达探索。既有有效产物可直接复用；缺项仍需在原分析选择、授权范围和预算内补齐。展示 GET 不补跑分析，不改变 ToolRun 或科学资格。

### Context report presentation

The research reader opens the registered HTML artifact with an empty iframe
sandbox; the frontend does not rebuild reported measurements. The current
[report package](../src/bridge/tool_packages/cards/P0-10.md#contract) presents percentages with the corresponding and total cell counts, groups
process scores by method/unit, and uses concise sample and result labels. Each
proposed mechanism links to its read literature sources and their species, lineage,
developmental-stage and experimental-context limitations; applicability remains
model-proposed and unverified.
Interpretation details are optional disclosures; absent predictions and repeated
generic warnings are omitted. Specific unavailable/candidate states remain visible.
Full numeric precision, source records and hashes remain in the inert HTML audit
template and registered JSON/CSV/SVG. Saved historical report bytes are not rewritten.
When several report snapshots share an input revision, the newest tool-run edition
is the default reader. Earlier editions remain downloadable in history; reports
from changed inputs retain their separate acknowledgement requirement.

Program means can come from cycle profiles or either supported source-bound
program profile version, with the same producer, data-view, value, unit and count
checks. Candidate explanations remain unverified even when report generation and
byte-integrity checks pass.


## Biological interpretation and public literature

Assessment prompts separate a concise biological-analysis role from the current
workflow, data context and action schema. One phase-specific workflow is loaded
per assessment turn; error recovery is included only after the corresponding
rejection. Tool schemas and deterministic admission own action/citation shapes
and budgets. Confirmed background and public retrieval boundaries are specified
in [privacy and provenance](privacy-and-provenance.md#biological-background-and-public-literature).

The scope form exposes optional Europe PMC retrieval and its public concept
selection. Legacy scopes default to retrieval disabled. The model can search and
read through typed actions; neither action executes a scientific measurement.
The assessment and private report display read-source references and explicit
applicability alongside proposed explanations. Source availability, structural
citation validity and biological interpretation quality are separate checks.

For a literature-enabled scope, a structurally admissible proposed explanation
receives one model consistency review before persistence. The review uses only
the already-shared background/evidence, read abstracts, proposed hypothesis
fields and current executable scientific-check identifiers. It does not search, run tools, rewrite measurements or grant scientific
qualification. A literature-enabled scope cannot bypass review with a free-text explanation; without usable evidence it must question or stop. Legacy scopes with literature disabled keep their prior behavior.

The coordinator reserves this review as a separate model turn within the same
approved budget before network I/O. The review supports both provider protocols
and by default uses a bounded 20,000-token response and 600-second timeout; the
output allowances for DeepSeek and reasoning-enabled requests are documented below. Budget exhaustion,
an unavailable/malformed review, or reported inconsistencies prevent admission;
no interpretation or report is created from that proposal. Epoch/scope checks
discard a late response after cancellation. Review findings must quote a real
proposed field. One schema-validated unadmitted draft and its field-bound findings
remain in private pending revision state for explicit Continue, outside messages,
interpretation versions and reports. Current evidence aliases are regenerated;
missing bindings discard the draft. An unavailable review retains the latest
proposal without adopting invalid findings or restoring an older draft; a passed
review or replacement scope clears it. Raw responses and model reasoning traces
are not stored by this mechanism. See the [privacy contract](privacy-and-provenance.md#assessment-purpose).
Continue spends a fresh generation turn and, if it proposes an explanation,
another review turn. There is no hidden retry or budget reset.

The review targets metadata fidelity, aggregate-versus-cell claims, predicted
phase-versus-division claims, stage distinctions, evidence/source applicability
and useful interpretation. A response with no detected issue remains a fallible
model review, not independent biological reader acceptance. Historical
interpretations and reports are preserved and are not retroactively certified.

Interpretation review receives the draft-cited support, opposition and missing
measurement records with their unchanged defaults, tool context and confirmed
background. Uncited measurements and repeated summary tables are explicitly
marked as omitted, not absent. Program summaries retain per-program signature,
coverage, direction and missingness semantics. Generation retains the full existing evidence
projection. Review cannot validate observations outside its cited-record view.

For recognized switchable DeepSeek models, thinking requests omit forced tool
choice, which the provider does not support in thinking mode. Native replies
still must contain exactly one permitted action and no unrelated content.
See the [DeepSeek Chat Completions contract](https://api-docs.deepseek.com/api/create-chat-completion/).

Session writes use the same 8 MiB limit as reads and reject oversize growth before replacing a readable file. Review turns reference their proposal turn instead of duplicating its immutable evidence and provider bindings.

### Continuing a saved evidence assessment

A repeated exploratory execution keeps its scientific input fingerprint but has
a distinct execution identity. The native graph coordinator links a new producer
to the latest active evidence record only when the complete logical measurement
contract matches, using an explicit supersedes relation. Changed contracts remain
separate observations; invalidated evidence cannot be revived implicitly. Old
receipts and graph versions are preserved. Reports resolve each native producer
against the content hash of its ToolRun node, including legacy receipts that may
share a run ID. A pinned graph also restores the exact native producer records
from its verified catalog when the latest-result roots omit historical profiles;
this does not admit a different same-name receipt or an invalidated source.

The assessment context limit applies to the same lossless table encoding used by
the provider. A text-only revision uses the existing projection of cited support,
opposition and missingness plus the confirmed context and read literature before
this check. The complete evidence remains available for citation admission,
persistence and the next full analysis; review and numerical checks still apply.

DeepSeek thinking-mode interpretation review and directed text repair use a bounded 65,536-token output budget: reasoning and the required structured verdict share this allowance. The prior 20,000-token ceiling repeatedly ended with only reasoning and `finish_reason=length` in official API trials. Responses remain capped at 1 MiB, and truncation, malformed output, and unavailable review still block admission. Each attempt consumes one reserved model turn; no implicit retry or empty-review fallback is added. Other providers retain their existing limits. This follows the official thinking-mode default (https://api-docs.deepseek.com/api/create-chat-completion/), without changing review standards or scientific qualification.

Interpretation review and text repair explicitly distinguish a selective measurement summary from the input feature list. A marker omitted from the summary cannot establish that the assay did not cover it; any absence claim requires explicit coverage evidence. This is an epistemic constraint, not an inferred expression measurement.

Interpretation review, generation and directed repair use the same effort captured
for the task. There is no separate low-effort consistency-check override. The
review prompt, evidence projection, schemas, quote checks, response cap and
fail-closed admission remain unchanged. Higher selected effort may exhaust the
bounded allowance without a verdict; that still blocks admission and requires
an explicit subsequent attempt, not a hidden lower-effort retry.

Native-tool review instructions explicitly require one `review_interpretation` function call even when no issues are found. A JSON object in message content remains a protocol failure, never an accepted empty review. Invalid review/revision envelopes now retain the bounded `action_protocol` diagnostic rather than the generic `unexpected` category.


### Model-authored interpretation relations

Current live structured explanations require `evidence_relations` with `supports`,
`limits`, `contradicts` or `missing_for`, a rationale and applicability for every
cited record, plus an explicit `feature_queries` list (which may be empty).
Historical stored explanations can omit these fields. These are proposed semantic
judgments. The coordinator checks
citations and missing-record roles, rebinds nested references on resume, and
reserves consistency review even when public literature retrieval is disabled.
Review can revise a relation kind or its prose while retaining the exact source;
the revised draft must pass the same schema and a new review before admission.

`feature_queries` request at most 32 exact identifiers per hypothesis. Intake
reads only the selected H5AD feature axis after checking the approved upload hash,
using the confirmed gene-symbol column or the axis index. Membership, incomplete
metadata, and no exact match remain distinct from expression and biological absence.
These compact facts enter review and repair, then freeze with explanation v1.2.
Wire and persisted v1.2 explanations use the same identifier validation: identifiers
are unique within a hypothesis, start with an ASCII letter or digit, contain only
ASCII letters, digits, underscores, dots or hyphens, and are at most 64 characters.
A stored v1.2 explanation with nonempty queries requires a coverage snapshot for
the same input revision. Incomplete coverage with explicit `unknown` results is
valid; a missing snapshot is not. Historical empty-query objects may omit coverage.

A native continuation over an invalidated predecessor remains blocked with
`native_invalidated_evidence_revision_requires_review`, including during scope
preparation. The reader is told that the invalidated evidence needs review; this
diagnostic does not authorize a revision or reactivate the evidence. Unexpected
errors during scope preparation retain the generic unavailable category without
exposing their text.

P0-10 context/snapshot v0.5 carries the deterministic interpretation graph and
its explanation/graph-manifest bindings. The evidence view shows these nodes and
relations in its existing entry; verified browser provenance resolves citations
to exact measurement nodes when available. Unresolved citations stay explicit.
When several explanation reports bind the same graph, the reader selects one;
versions are never pooled. Report HTML retains concise biological statements,
with relation reasons and input coverage available in disclosures. Historical
explanations and report artifacts remain readable and unchanged. Binding and
consistency checks do not establish causal or scientific qualification.


Review issue reasons permit up to 1,200 characters; exact quoted snippets remain
limited to 600. Relation reasons and applicability retain their separate 400- and
300-character limits. Provider schema diagnostics identify issue reason/quote
paths without copying arbitrary model output.

An operator can explicitly propose a continuation of an unresolved draft by
supplying its source scope ID, scope digest and pending-revision digest. The
coordinator requires the same question, input revision, resources and non-budget
scope fields, a prior authorization and no accepted interpretation. It preserves
the prior draft/history, creates a new unapproved scope with new budgets, and
checks the draft digest again before approval. It does not automatically retry,
refund prior calls or carry an accepted result forward. Literature-enabled scope
continuation is not available through this narrow path.

A new explanation with evidence relations or feature queries requires a unique,
verified current graph binding before v1.2 publication. Missing or ambiguous
bindings stop with `interpretation_graph_binding_unavailable` and preserve the
private pending draft; no explanation version, admitted message or report is
created. Existing v1.0/v1.1 explanations keep their original contract. Historical
unbound v1.2 objects remain readable as stored history but are not current report
interpretations.

## Internal multi-user testing

Account-based service deployment is for an approved laboratory/campus network, not public registration.
Users self-register after acknowledging administrator access to test conversations, uploaded
materials and results. Each account owns its sessions. The administrator opens **测试管理** inside the same settings window
for audited read-only inspection, disabling accounts and resetting passwords. Reset revokes
logins and requires a new password before workspace access. Reads grant no scientific approval.

New users automatically use the shared provider in **模型**. Additional private providers
and per-account model selection are managed in that same directory. Only administrators
can edit the shared provider. Blank private keys retain only that account and provider's
key at the same endpoint; they never inherit the shared key. Each task captures its
provider/model/version, with no automatic fallback after failure. Sharing revocation and
scientific resource controls stay live. Connection tests send fixed text only. Keys remain
transiently in the open editing form, clearing on configuration save/close; never browser storage.

Use an independent empty private directory. Legacy sessions are not imported. Delete legacy
sessions only within explicit operator cleanup scope after stopping their owning instance.

    python -m bridge.web.account_admin --config /absolute/path/web-accounts.env initialize --root /absolute/path/account-storage --username operator --environment acceptance

The command prompts for the password; never put it in argv/history. --password-stdin accepts
a private pipe. Retries keep the same administrator and refuse nonempty legacy directories.

| Private configuration | Contract |
|---|---|
| BRIDGE_START_STORAGE | Required independent initialized account directory |
| BRIDGE_WEB_PUBLIC_ORIGIN | Exact HTTPS origin without a path; strict Host/Origin and secure cookies |
| BRIDGE_WEB_TRUSTED_PROXY_IPS | Literal loopback proxy IPs, comma-separated; default 127.0.0.1 |
| BRIDGE_WEB_PERSONAL_MODEL_ALLOWLIST | Optional exact literal-IP base URLs for approved personal endpoints |
| BRIDGE_WEB_USER_TASK_LIMIT | Default one admitted task per account; maximum two |
| BRIDGE_WEB_USER_STORAGE_BYTES | Default 20 GiB uploaded payload quota |
| BRIDGE_WEB_TOTAL_STORAGE_BYTES | Default 100 GiB shared payload quota; at least the per-user limit |

Single-file limits still apply. Upload admission counts H5AD, protocol and scientific-object
payload directories plus concurrent reserved request lengths, conservatively including
multipart overhead. Generated outputs, databases and journals require separate disk monitoring.
The global executor retains one worker and two admitted tasks across all accounts.
Registration/login have global/client rate limits, not proof of one human per account.

Personal endpoints require external HTTPS unless their exact literal-IP base URL is allowed.
DNS answers are checked and pinned to the actual connection, preserving Host/TLS verification.
Mixed private/public answers, unsafe IPv6 transitions, redirects and environment proxies are
rejected. Link-local metadata endpoints cannot be allowlisted.

Start at a fixed backend port behind a separately managed HTTPS proxy:

    ./start.sh --config /absolute/path/web-accounts.env --env acceptance --port 8766

The backend/control listener stays on loopback. A configured public origin requires
explicit initialized storage, rejects --test and uses a fixed backend port. Local
account instances support --test and default-port fallback. All launches reject
uninitialized/partial account storage. status/stop use the same config.

Restrict the proxy to approved networks. Overwrite X-Forwarded-For with one actual client IP
and X-Forwarded-Proto with https; preserve the exact public Host and remove client Forwarded
headers. Malformed forwarding headers or untrusted proxies fail closed. Locally issued
certificates require distributing and verifying the CA through a trusted channel; do not
disable TLS verification for user traffic.

Stop the service before taking a consistent snapshot into a new private directory:

    python -m bridge.web.account_admin --config /absolute/path/web-accounts.env backup --source /absolute/path/account-storage --target /absolute/path/new-snapshot
    python -m bridge.web.account_admin --config /absolute/path/web-accounts.env restore --source /absolute/path/new-snapshot --target /absolute/path/account-storage

Exclusive locks cover accounts, audit, model settings and sessions together. Before restore,
stop the service and move the current storage aside to retain it. Restore requires the
original absolute storage path recorded by the snapshot to be absent. It checks file hashes
and ownership and preserves every receipt and provenance path without rewriting them.
An interrupted restore stays unavailable; move the partial directory aside before retrying
at the original path. Account storage uses environment binding version 2.0.0; older
single-operator releases reject that version before opening sessions.

Acceptance covers synthetic A/B/admin accounts, direct-ID rejection, model isolation,
browser account switching, downloads and restart/restore. Another internal-network client
must verify the actual HTTPS entry. Loopback health is not network acceptance, scientific
qualification or public-service readiness.
