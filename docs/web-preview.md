# Web preview

BRIDGE has a private, single-operator conversational preview. Upload an H5AD,
declare its assay and counts layer, then review and confirm each analysis stage.
Actual tool figures, tables and downloads remain available beside the conversation.

| Web stage | Required context | Current scope |
|---|---|---|
| P0-01 input QC | Uploaded H5AD and explicit assay/raw-count declarations | Input quality and readiness evidence |
| P0-02 cell-state evidence | Completed canonical QC, a privately supplied source-family reference and configured candidate reference resources | Existing raw-count-compatible candidate analysis; not guaranteed to produce a V3 result |
| P0-12 graft assessment | Explicit declaration that no graft data are provided, within an existing product analysis | Zero-input `not_provided` record only; no expression-graft analysis |
| P0-03–P0-11 | Additional scientific objects and Web input constructors | Not connected in the Web preview |

The 12 P0 packages remain callable through their CLI and SDK. This preview does
not yet construct a complete product-evaluation chain. Missing sample design,
product definitions, reference contracts and composition weights are not invented.

The preview supports explicit `scRNA-seq` or `snRNA-seq` declarations and raw
counts in `X` or `layers/counts`. Uploads are limited to 128 MiB per file and
eight files per conversation. The HDF5 structure is checked before planning;
separate CSV/JSON metadata uploads are not supported in this first preview.
No metadata table is automatically joined or treated as verified sample design.

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
| `BRIDGE_WEB_STATIC_DIR` | Absolute path to the built `web/dist` directory |
| `BRIDGE_WEB_ORIGIN` | Exact browser origin; defaults to `http://127.0.0.1:8765` |
| `BRIDGE_WEB_PORT` | Loopback port; defaults to `8765` |
| `BRIDGE_WEB_TRUSTED_ANCESTORS` | Optional startup-only JSON mapping from explicitly approved ancestor paths to `[uid, device, inode]` pins |
| `BRIDGE_WEB_CELL_STATE_MEASUREMENT_SPEC_REF` | Optional registered MeasurementSpec for P0-02; no biological default is selected |

The configured chat-completions provider must support JSON mode through
`response_format: {"type": "json_object"}`. BRIDGE requests one typed JSON
action and does not send native tool definitions; malformed prose, XML/DSML or
incomplete actions fail closed. See the [DeepSeek JSON Output guide](https://api-docs.deepseek.com/guides/json_mode/).

P0-02 also requires the toolkit's existing reference configuration and permitted
candidate resources. A nonblank MeasurementSpec ID is insufficient: capability
checks inspect the registered spec, reference artifacts and canonical QC receipt.
The service maintains its private QC catalog; operators do not copy presentation
JSON into that catalog. Missing configuration is shown as `needs_input`.

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
3. Tell BRIDGE the assay and which matrix contains raw counts. The Agent asks
   for clarification when those declarations are missing.
4. Review the proposed input-QC plan. Confirmation is bound to its exact
   digest; sending a chat message alone never approves execution.
5. Inspect actual figures, tables, evidence and downloads. Refreshing the page
   restores the session.
6. To continue with cell-state analysis, expand **Data and tool chain** and enter
   the uploaded dataset's actual **Data source / experiment reference**. This
   value is saved privately, outside the model conversation. Ask for P0-02 and
   confirm its new plan once the prerequisites are met.
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

Counts declarations do not establish sample, capture, preparation or batch
relationships. Unknown biological design remains unknown. A successful tool
run can still have limited readiness or unavailable measurements.

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
| `POST /api/sessions/{id}/inputs` | Bind `{upload_id, source_family_id}` to an existing upload; source ID starts with an ASCII letter/digit, permits letters/digits/`.`/`_`/`:`/`-`, and is at most 160 characters |
| `POST /api/sessions/{id}/messages` | Submit one conversation turn |
| `POST /api/sessions/{id}/approve` | Approve the exact proposed plan ID and digest |
| `GET /api/sessions/{id}/artifacts/{artifact_id}` | Retrieve a registered artifact under authentication |
| `GET /api/sessions/{id}/transcript` | Download the conversation |

The Web layer uses `PlanBuilder`, immutable approved requests,
`ToolExecutionPipeline` and `LocalWorkflowExecutor` with SQLite events.
It does not execute model-generated commands or invoke scientific libraries
outside the registered package.

## Privacy and interpretation

- Provider requests contain conversation text and a small status context, not
  uploaded matrices, private file paths or tool-owned biological measurements.
  Avoid entering confidential identifiers or secrets into chat text.
- The model can reply or propose QC, candidate cell-state analysis or explicit
  no-graft recording. It cannot approve a plan, change scientific values or
  select arbitrary filesystem paths. Privately entered source-family values
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
