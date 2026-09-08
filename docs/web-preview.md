# Web preview

BRIDGE has a private, single-operator conversational preview. Upload an H5AD,
review a readable product-intake draft, confirm its facts, then prepare and
separately approve the next eligible analysis stage. The right-hand **评估概览**
presents product facts and evidence questions; actual figures, tables and
downloads remain in adjacent tabs.

This page describes the current source implementation, not a guarantee that an
already running instance includes every repair. The [integration plan](../plans/web-full-chain-integration.md#current-progress-2026-09-08)
separates implemented changes, installed acceptance and genuine execution coverage.

| Web stage | Required context | Current scope |
|---|---|---|
| P0-01 input QC | Uploaded H5AD and explicit assay/raw-count declarations | Input quality and readiness evidence |
| P0-02 cell-state evidence | Completed canonical QC, a privately supplied source-family reference and configured candidate reference resources | Existing raw-count-compatible candidate analysis; not guaranteed to produce a V3 result |
| P0-03–P0-11 | A selected current tool mode and its required scientific objects; compatible results from this conversation can be reused | Contract-driven input selection, eligibility, separate approval and normal tool execution |
| P0-12 graft assessment | Explicit no-graft declaration, or the selected mode's supplied graft metadata/resources | Independent no-graft, supplied-evidence or expression path; no backfill into product evidence |

All 12 P0 packages share the Web input, planning and approval route as well as
their CLI/SDK. This is tool access, not automatic authorship of every scientific
input or proof that a complete product-evaluation chain has run. The source
backend now supports reviewable, source-backed product-definition/role candidates
and optional regional/development candidates. Exact confirmation creates draft
objects through the existing registration route. Inline cards expose candidate
sources, unknowns, editable choices and exact confirmation. A revision creates a
new pending draft and cannot approve analysis. Superseded and confirmed cards
always display their recorded server candidate, not local edits from a newer
version. The confirmed card lists later
stages and offers a separately approved P0-08 missingness check. This narrow
check supplies the confirmed ProductCase and five unmeasured domains to the
package-owned gate; it does not reinterpret old QC/cell-state outputs as matched
domain measurements. If measured domain runs exist, it refuses this shortcut.
From that same verified missingness result, the card can separately prepare
candidate evidence compilation and an internal research report for actual claim
verification. The current report retains five unassessed domains and a blocked
release result; see the evidence/report construction boundary below.
Draft requests enforce one label level, one matching source per choice and
consistent regional numerator/denominator sets. Shape/source validation permits
one purpose-scoped correction with an error code; invalid values are not accepted
or repeated as conversation history. Two invalid responses leave no draft, and
network/provider failures are not retried by this correction path.
Full measured prerequisite, protocol, comparison and qualified-report construction remain open;
installed acceptance is recorded separately in the active plan. The advanced
panel still accepts supplied scientific objects and reuses compatible results.
Missing sample design, reference contracts and composition weights are not invented. A connected tool can remain `needs_input` until its named roles are supplied.
Choosing a mode does not mean its remaining inputs exist: model context includes
package-owned mode IDs and required role names, without selected values or
scientific payloads. Actual eligibility is still checked before approval.

Inline questions add application-owned unknown and free-text answers. A single
model-supplied option with reserved ID `unknown` is shape-validated and deduplicated;
there must still be two to four valid substantive choices. Other invalid factual
IDs remain errors, and submitting answers only stages a private fact draft.

H5AD uploads are limited to 128 MiB per file and eight files per conversation.
The HDF5 structure is checked before planning. Initial chat facts use a typed
`propose_intake` action and the same exact confirmation card as the private
product form; chat text is never parsed into committed counts or assay facts.
**Analysis inputs** also accepts an explicit compatible
matrix/input-level declaration and bounded metadata. The advanced metadata JSON
accepts `sample_id_column` and `capture_id_column` for existing `obs` columns,
and `gene_symbol_column` for an existing `var` column. These selectors reach
P0-01/P0-02 unchanged after confirmation; they do not infer sample relationships
or generate gene annotations. Selecting normalized input never normalizes or
rewrites the matrix. Scientific JSON objects are limited to
2 MiB each and 128 registrations per conversation. No metadata table is
automatically joined or treated as verified sample design.

## Table previews and downloads

Registered Parquet tables have a read-only preview in **Tables**, including older
artifacts labeled `application/octet-stream` with a `.parquet` filename. The
server verifies the same session, private file and checksum as the original
download before decoding an immutable snapshot.

A preview shows at most 100 rows and 24 columns. It accepts at most 8 MiB of
stored Parquet bytes, at most 32 MiB of declared uncompressed data in the row
groups read, and at most 200,000 bytes of encoded preview JSON. Text cells are
limited to 1,000 characters with a visible truncation marker. Table shape and
truncation are displayed explicitly; a preview is not the complete dataset.

CSV, TSV and JSON retain bounded text previews. Invalid, unsupported or
over-limit binary content, including unsupported Parquet cell types or an
unavailable optional PyArrow runtime, shows a download fallback rather than
binary text. Null and non-finite values are not replaced with zero. Integers and
integral-valued floats outside JavaScript's safe integer range use exact,
round-trippable display strings so browser parsing cannot silently change them.
Original downloads keep their exact registered bytes and checksum. Previewing does not
run analysis, alter scientific evidence, send rows to the model or grant export
authority.

## Start a private instance

Use Python 3.12 and Node.js 22. Install the optional service dependencies and
build the client:

~~~bash
python -m pip install ".[qc,web]"
npm --prefix web ci
npm --prefix web run build
~~~

Configure the service outside the checkout. Keep credentials in an
operator-owned private environment file, never in Git or the browser bundle.

| Setting | Meaning |
|---|---|
| `BRIDGE_WEB_STORAGE` | Absolute private directory for sessions, uploads, plans and workflow evidence |
| `BRIDGE_WEB_TOKEN` | Random operator login secret, at least 24 characters |
| `BRIDGE_WEB_MODEL_BASE_URL` | OpenAI-compatible provider base URL; use HTTPS for external providers |
| `BRIDGE_WEB_MODEL` | Provider model identifier |
| `BRIDGE_WEB_MODEL_API_KEY` | Server-only provider credential |
| `BRIDGE_WEB_MODEL_ACTION_PROTOCOL` | Explicit action protocol: `json` (default) or `deepseek_tools`; other values fail startup |
| `BRIDGE_WEB_STATIC_DIR` | Absolute path to the built `web/dist` directory |
| `BRIDGE_WEB_ORIGIN` | Exact browser origin; defaults to `http://127.0.0.1:8765` |
| `BRIDGE_WEB_PORT` | Loopback port; defaults to `8765` |
| `BRIDGE_WEB_TRUSTED_ANCESTORS` | Optional startup-only JSON mapping from explicitly approved ancestor paths to `[uid, device, inode]` pins |
| `BRIDGE_WEB_CELL_STATE_MEASUREMENT_SPEC_REF` | Optional registered MeasurementSpec for P0-02; no biological default is selected |
| `BRIDGE_WEB_SHARE_RESULT_SUMMARIES` | Optional owner-authorized aggregate interpretation: exactly `1` enables, unset or `0` disables; all other values fail startup |

The default `json` protocol requires chat-completions JSON mode through
`response_format: {"type": "json_object"}`. It requests one typed JSON action
without native tool definitions; ordinary explanations use `reply.text`.
Malformed prose, XML/DSML, empty content and incomplete actions fail closed. See
the [DeepSeek JSON Output guide](https://api-docs.deepseek.com/guides/json_mode/).

Operators may explicitly select `deepseek_tools` for a compatible configured
provider. This sends eight actions (`reply`, `review_inputs`,
`prepare_qc`, `propose_intake`, `prepare_analysis`, `ask_user_input`,
`draft_scientific_inputs`, `propose_scientific_inputs`) as native function definitions,
requires one function call, disables thinking and omits JSON response mode.
Both protocols retain the same Action validation, guidance and sharing boundary.
Ordinary replies have an 1,800-token limit; the separate bounded scientific
candidate request allows 6,000 tokens. Native responses must have exactly the required
arguments and no non-whitespace text outside the call. The service does not guess
a protocol, retry with another parser or execute functions from model text:
preparation actions still create unapproved plans and require exact user approval.

P0-02 also requires the toolkit's existing reference configuration and permitted
candidate resources. A nonblank MeasurementSpec ID is insufficient: capability
checks inspect the registered spec, reference artifacts and canonical QC receipt.
The service maintains its private QC catalog; operators do not copy presentation
JSON into that catalog. Missing configuration is shown as `needs_input`.

For a saved P0-02 selection, the server reuses verified canonical QC from the
exact selected upload and the upload's separately confirmed source field. It
preserves the original matrix declaration and derives internal QC profile,
DataView and parent-checksum bindings without asking the user to enter them.
Readiness checks do not register or alter QC catalog entries. The selected
MeasurementSpec remains explicit; an omitted selection is not replaced by the
configured default. Missing, stale or altered QC remains an input blocker.

With these variables supplied by the deployment environment:

~~~bash
python -m bridge.web
~~~

The service binds to loopback. Access it through an authenticated encrypted
tunnel or an operator-managed HTTPS reverse proxy. Do not expose it as an
unauthenticated public service. It is not a multi-user authorization system.

The default private-path policy accepts root-owned or operator-owned safe
ancestors and requires operator-owned private leaves. A shared mount owned by
another administrator requires explicit trust approval and exact identity
pins. Configure this before private I/O; changing trust requires a restart.
The setting does not relax symlink, replacement, writable-ancestor or
private-leaf checks. See [privacy and provenance](privacy-and-provenance.md).

## A typical conversation

1. Log in with the operator token and create an analysis.
2. Upload an H5AD. The browser lists the accepted file; the service stores a
   checksummed copy under a generated identity.
3. In **产品资料**, distinguish observed file shape from researcher-declared
   product target, sampling context, assay and matrix semantics. Unknown facts
   stay unknown. An initial chat declaration may stage a draft, never confirm it.
4. Click **核对产品资料**, inspect the exact before/after card and click **确认资料**.
   This commits facts only. Then click **生成下一阶段计划** and separately approve
   that plan's exact digest in the conversation.
5. Inspect the six evidence questions and actual figures, tables, evidence and
   downloads. Refreshing restores the session; valid canonical QC is reused for
   ordinary follow-up conversation without a duplicate proposal.
6. To continue with supported hPSC-mDA cell-state analysis, supply the actual
   source-family reference in the private product form (or advanced input form).
   The intake route displays and uses the configured analysis specification for
   the exact selected upload. Confirm source/product changes before preparing
   and separately approving this new stage. Existing cell-state history prompts
   an input/result review instead of automatically rerunning it.
7. If no graft data are available, explicitly say so and request that this be
   recorded. P0-12 receives no expression assets or structured inputs in this
   mode; the original upload supplies product planning context only.
8. Open **Stage history** to inspect previous plans and per-step outcomes. Ask
   follow-up questions or refresh the page; prior results are retained.

Each proposed stage has its own exact approval. Changing source information or
sending another message invalidates an unapproved proposal. Completed evidence
is retained, not rewritten. `partial`, `blocked` and `cancelled` are displayed
separately from successful execution. Older sessions without canonical QC
receipts must run QC again before proceeding to P0-02.

The product-intake draft is private Web context, not a formal
`ProductDefinitionCard`, reviewed state-role map or `ProductCase`. It materializes
only compatible existing asset declarations after exact confirmation. General
candidate authoring is limited to the separate source-backed scientific-draft flow
described above. It does not supply every downstream prerequisite or report rule.
The six-question roadmap is prospective and marks missing evidence explicitly;
it is not a completed report or a plan to run all 12 tools. Comparison and
post-transplant graft evidence are not prerequisites for beginning pre-transplant QC.

The structure readout uses a checksummed registered upload and returns only
observation/gene counts, matrix locations and bounded column names, never row
identities, gene values or expression. Private form values and these structure
details are not added to ordinary provider context; only per-upload confirmation
status and missing-field names are supplied. The separate scientific-draft
request shares only the three approved confirmed product-intent fields; see
[privacy and provenance](privacy-and-provenance.md#scientific-draft-purpose). Facts independently entered in chat remain
ordinary conversation content. Culture counts do not generate biological-unit
mappings or attestations. Confirmed intake with an unknown or unsupported product
family permits generic QC, but does not authorize the hPSC-mDA-specific P0-02
reference path.

Confirmed product-only or source-only edits preserve otherwise valid QC.
Assay, matrix or QC-relevant metadata changes invalidate its binding; retracting
raw-count semantics removes the executable raw-count declaration. Advanced input
edits make the product record stale, and its next display merges the newer
confirmed asset/source facts for explicit reconfirmation. History is retained.
Corrupt or missing historical QC blocks chat reuse rather than being repaired
or silently replaced. Deliberate advanced-panel reruns remain available.

## Stop and input corrections

Use **Stop** while the Agent is thinking, an analysis is running or a plan awaits
approval. The stop is acknowledged immediately and fences subsequent work. A
non-interruptible tool step already in progress may finish; **Stopping…** remains
visible while it settles. Its actual outcome and artifacts are retained. A late
model reply cannot recreate a stopped plan. Stopping does not retract inputs.

Ordinary chat does not edit committed declarations. A requested correction
pauses subsequent planning and approval and asks the operator to review inputs.
Use the existing private forms to **Stage declaration** or **Stage change**.
The confirmation card shows exact before/after values:

- **Confirm change** applies only the displayed ID/digest-bound change.
- **Discard change** drops that proposal. A separate unresolved chat correction
  still requires review.
- **Keep current inputs** explicitly resolves a review with no proposed edit.

None of these actions approves or starts analysis. Stale confirmations are
rejected, and old plan approvals do not revive. A confirmed matrix/assay or
QC-relevant metadata change requires fresh QC; a source-family-only update
preserves otherwise valid canonical QC. Old sessions use saved exact declarations,
not reinterpretations of later chat. Ambiguous legacy state asks for review;
keeping current declarations cannot rehabilitate an invalid historical QC receipt.

Counts declarations do not establish sample, capture, preparation or batch
relationships. Unknown biological design remains unknown. A successful tool
run can still have limited readiness or unavailable measurements.

## Analysis inputs

Expand **Analysis inputs** when a stage needs additional context:

1. Select a tool and one of its current modes. Required roles, accepted Schemas,
   versions and cardinalities come from its packaged input contract.
2. Select compatible objects already supplied, package-owned resources, configured
   reference objects or canonical results produced in this conversation.
3. Upload missing scientific objects into the named roles. These are versioned
   scientific inputs, not executable requests. Stage any selected H5AD's assay,
   matrix semantics and factual metadata, then confirm the displayed changes.
4. Save the selection, then prepare a plan. Review and approve its exact digest
   before execution. A chat request for that tool uses the same saved selection.

Schema and object version belong to the input wrapper; a scientific payload
need not repeat them. Choose the accepted Schema/version without adding fields
to the object. Some scientific objects also contain request-local input IDs:
register their dependencies first, then use the returned opaque IDs in the
supplied binding fields. The Web layer does not guess these links from filenames.

The server owns request IDs, tool versions, paths, checksums and output directories.
The panel does not accept commands, arbitrary parameters or a raw ToolRequest.
Scientific objects retain their supplied content and state. Existing package
eligibility and release-authority checks still apply.

Ordinary JSON uploads cannot point at server files. Supported file descriptors use
opaque `upload:<id>` or `artifact:<id>` references to this conversation; the server
resolves and checks the actual dependency. Case/comparison graph manifests must
come from a verified canonical tool run, with their backing artifact bundle intact.
Unsupported file-bearing resources remain explicitly blocked.

P0-06 `method_runtime_source_bound` accepts one additional descriptor in
`process_method_input` v0.2 (object version `0.2.0`):

| Direct field under `source_observations` | Paired checksum | Canonical artifact kind |
|---|---|---|
| `artifact_manifest_path` | `artifact_manifest_sha256` | `manifest` |
| `evidence_path` | `evidence_sha256` | `cell_state_evidence` |

Both locators must use `artifact:<id>` from the same conversation and P0-02
receipt. The checksum key is required; a null or empty value asks the server to
bind the actual digest, while an incorrect or non-string value is rejected.
The server rechecks both files and their receipt before use. Other provenance
fields remain caller-supplied and are checked by normal P0-06 eligibility.
These named locators are not accepted in other roles or Schemas; raw paths,
URLs, upload IDs and mixed producer receipts are rejected. The existing plain
`path` convention for graft uploads and export audit remains unchanged.

The P0-08 gate rule and P0-10 policy/statement registry are package-owned options.
Reference objects may be drawn from the already configured P0-02 snapshot;
availability does not establish scientific validation. No new reference catalog
or scientific default is selected by the Web layer.

This panel does not invent P0-05 soft mass, domain-gate requirements, comparison
design or report claims. Supplied ReportDrafts remain subject to P0-10's exact
renderer/authority/content checks. Graft and comparison are independent branches.
A P0-11 local candidate export is not a network upload or publication approval.
The source-backed card can now prepare P0-09 from its own verified missingness-only
P0-08 receipt. A versioned tool-package factory constructs five descriptive
candidate claims, one unreviewed shared-source family and candidate reconciliation
rules from the confirmed case and definition. It creates five open requirements,
not MeasurementResults or independence evidence; it uses no test-fixture policy.
P0-10 preparation builds a case-bound internal draft and binds the genuine graph
manifest plus the existing approved policy/statement registry. The current release
contract does not support availability claims and does not approve this renderer:
the actual verifier therefore returns release_blocked, which the card displays
with next steps. No release policy is relaxed and no export control is offered.
Preparation, approval and display recheck the owned inputs and upstream receipts;
corruption/source changes invalidate use without rewriting completed evidence.
The bounded private report projection contains plain text and actual verification
states, not raw matrices, paths or hashes. It is not added to model context.

## Interface and ownership

The React client uses [assistant-ui's external store runtime](https://www.assistant-ui.com/docs/runtimes/custom/external-store).
The server owns session state, approvals and tool execution; assistant-ui does
not act as a second workflow engine.

| Route | Purpose |
|---|---|
| `POST /api/login`, `POST /api/logout` | Establish or revoke the operator cookie |
| `GET /api/sessions`, `POST /api/sessions` | List or create analyses |
| `GET /api/sessions/{id}` | Read messages, uploads, current plan, stage history, capabilities and artifacts |
| `POST /api/sessions/{id}/uploads` | Accept a bounded multipart upload |
| `POST /api/sessions/{id}/inputs` | Stage `{upload_id, source_family_id}` for confirmation; source ID starts with an ASCII letter/digit, permits letters/digits/`.`/`_`/`:`/`-`, and is at most 160 characters |
| `GET /api/sessions/{id}/analysis-inputs` | Read current contracts, safe object/asset options and saved selections |
| `POST /api/sessions/{id}/analysis-inputs` | Save a tool/mode selection using registered input IDs |
| `POST /api/sessions/{id}/analysis-inputs/objects` | Register a bounded scientific JSON file for a current mode/role/Schema/version |
| `POST /api/sessions/{id}/analysis-inputs/assets` | Stage one registered H5AD's assay, matrix and factual metadata |
| `POST /api/sessions/{id}/input-change/confirm`, `.../discard` | Confirm or discard the exact `{change_id, change_digest}` proposal |
| `POST /api/sessions/{id}/input-review/keep` | Explicitly keep current declarations after a chat-triggered review |
| `POST /api/sessions/{id}/scientific-inputs/draft` | Request constrained candidates from confirmed intent and local state-review sources |
| `POST /api/sessions/{id}/scientific-inputs/confirm` | Confirm the exact draft ID/digest; register candidate objects without running tools |
| `POST /api/sessions/{id}/scientific-inputs/revise` | Validate the current source binding and save choices as a new pending version |
| `POST /api/sessions/{id}/report-inputs/prepare` | Prepare the confirmed draft's selected P0-08, P0-09 or P0-10 stage; tool_id defaults to P0-08, and each plan needs separate approval |
| `POST /api/sessions/{id}/clarification/answer`, `.../cancel`, `.../revise` | Persist exact private choice responses without automatically confirming facts |
| `POST /api/sessions/{id}/stop` | Stop future work without waiting for the current provider/tool call |
| `POST /api/sessions/{id}/prepare-analysis` | Propose the selected tool stage; never approve it |
| `POST /api/sessions/{id}/messages` | Submit one conversation turn |
| `POST /api/sessions/{id}/approve` | Approve the exact proposed plan ID and digest |
| `GET /api/sessions/{id}/artifacts/{artifact_id}` | Retrieve a registered artifact under authentication |
| `GET /api/sessions/{id}/artifacts/{artifact_id}/preview` | Read a bounded, checksum-verified Parquet display projection |
| `GET /api/sessions/{id}/transcript` | Download the conversation |

The Web layer uses `PlanBuilder`, immutable approved requests,
`ToolExecutionPipeline` and `LocalWorkflowExecutor` with SQLite events.
It does not execute model-generated commands or invoke scientific libraries
outside the registered package.

## Privacy and interpretation

- By default, provider requests contain conversation text and a small status
  context, not tool-owned biological measurements. Avoid entering confidential
  identifiers or secrets into chat text.
- With explicit owner authorization and `BRIDGE_WEB_SHARE_RESULT_SUMMARIES=1`,
  the model can receive canonical P0-01 aggregate QC evidence as `E0` and the
  supported P0-02 V3 or separately identified V2 composition/reconciliation summary as `E1`. QC includes only
  allowed schema counts, tool-owned median measurements, their denominators and
  evidence states, four assessment states and the minimal historical DataView.
  Cell-state labels come only from the packaged public vocabulary. Both preserve
  declared states and `domain_score=null`. Raw matrices, observation-level
  records, source-specific rows, sample/source identities, private paths and
  provenance hashes remain local. Summary construction does not decode Parquet
  tables or expression matrices. V2 verifies the original upload bytes and
  preserves its historical per-level denominators without manufacturing V3
  lineage, downstream readiness or QC filtering. This is not anonymous-data certification or
  public-export permission.
- Each alias refers to its own historical producer and selected data view, not
  to a later upload or changed declaration. V2 uses its original historical
  input scope, not a claimed V3 selected view. QC and cell-state evidence may come
  from different runs; their uploads or denominators must not be conflated.
  The latest succeeded/partial producer is checked independently before selecting
  its supported artifact; invalid evidence does not fall back to an older result.
  Invalid or unsupported evidence contributes no result values; valid evidence
  for the other alias may still be shared. Oversized combined summaries supply
  no biological data, and input review suspends result sharing.
- The shared model instructions use status-only language when no summary is
  supplied, and request supplied counts/fractions with the corresponding alias
  when authorized evidence is available. Missing or `not_assessed` QC assessments
  are not successful checks; execution alone does not establish filtering,
  doublet removal or biological QC passage. Instructions prohibit inventing
  absent intervals or scores and direct explanation-only requests to a reply
  rather than a new proposal. These instructions do not guarantee model accuracy;
  actual replies still need comparison with the canonical evidence.
- Each evidence-bearing turn retains independent bounded private `E0`/`E1`
  bindings to the exact verified receipts and artifacts. These mappings are not
  exposed in public session state or sent to the model. When sharing is disabled
  or input review is active, prior evidence-bearing assistant content is withheld
  from the model history while remaining visible in the private conversation.
- The model can reply, request input review or propose a registered tool using
  the saved input selection. It can propose constrained candidates only in the
  scientific-draft request; it cannot approve a plan, author arbitrary scientific objects,
  change scientific values or select arbitrary filesystem paths. Privately entered source-family values
  are excluded from its status context. Model replies
  are not P0-10-verified reports; numerical evidence belongs to the tool artifacts.
- Artifacts are private downloads. Downloading them is not P0-11 public-safe
  export, release approval or an assertion that they contain no private data.
- JSON downloads labeled `.display-redacted.json` are presentation copies
  with private paths removed. They are not byte-identical canonical tool
  inputs; the private receipt retains the original artifact ID and digest.
  Use the original server-owned contracts for downstream execution.
- `candidate/shadow` methods and `domain_score=null` are unchanged.
  No clinical, safety, potency or GMP conclusions are authorized.
- Provider errors and interrupted work are explicit. Restarting the service
  must not silently replay a previously running analysis.

See [tool packages](tool-packages.md) for scientific interfaces,
[Agent integration](agent-integration.md) for full-chain ownership, and the
[validation record](validation/web_preview_20260905.md) for the tested preview scope.
