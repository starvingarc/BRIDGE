# Web preview

BRIDGE has a private, single-operator conversational preview. Upload an H5AD,
declare its assay and counts layer, review an input-QC plan, then confirm it.
The existing P0-01 package produces the figures and artifacts shown alongside
the conversation.

This first Web release covers input QC. The 12 P0 packages remain available
through their existing CLI and SDK; the Web interface does not yet construct
the scientific inputs needed to execute the full tool chain. Missing sample
design, product definitions and reference contracts are not invented.

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
6. Ask follow-up questions. The conversation retains context; the tool outputs
   remain the source of numerical evidence.

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
| `GET /api/sessions/{id}` | Read messages, uploads, plan status and artifact index |
| `POST /api/sessions/{id}/uploads` | Accept a bounded multipart upload |
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
- The model can request a bounded QC plan or reply. It cannot approve a plan,
  change scientific values or select arbitrary filesystem paths. Model replies
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
