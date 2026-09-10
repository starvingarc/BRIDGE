# Web preview

BRIDGE has a private, single-operator conversational preview. It supports the
first six steps of the canonical [PRD workflow](BRIDGE_PRD.md#61-agent-总体工作流)
within their accepted scope: research question, materials, necessary questions,
source-backed fact confirmation, scoped plan/resource approval and QC. Uploaded
protocols can be represented and reviewed under the approved BPL design.

This current scope does not provide the complete downstream graph-driven
research loop, internal comparator selection or qualified report/export.
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
| P0-03–P0-11 input panel | Contract discovery, explicit registration, plan approval and normal execution | Automatic construction of every prerequisite or a connected feedback loop |
| P0-12 | Explicit no-graft or supplied eligible graft modes | Graft evidence from an absence record or pre-transplant backfill |

The bounded candidate card can materialize source-backed product/role and
optional regional/development candidates after exact confirmation. A separate
missingness-only P0-08 path can compile candidate missing requirements through
P0-09 and build an internal P0-10 draft whose actual release state remains
blocked. It creates no domain MeasurementResult and offers no qualified export.

Uploads are limited to eight H5AD files per conversation and 128 MiB per file.
Scientific JSON objects are limited to 2 MiB each and 128 registrations per
conversation. The server checks HDF5 structure and uses explicit assay, matrix
and metadata declarations; it does not infer sample relationships, join an
unreviewed metadata table or rewrite normalized input.

## Table previews and downloads

Registered Parquet tables have a checksum-verified, read-only preview. It shows
at most 100 rows and 24 columns, accepts at most 8 MiB of stored Parquet bytes
and 32 MiB of declared uncompressed row-group data, and emits at most 200,000
bytes of preview JSON. Text cells are visibly truncated after 1,000 characters.

Unsupported or over-limit content falls back to download. Null and non-finite
values are not replaced with zero; large integers use exact display strings.
The original download keeps its registered bytes and checksum. Previewing does
not run analysis, send rows to the model or grant export authority.

## Start a private instance

Use Python 3.12 and Node.js 22:

~~~bash
python -m pip install ".[qc,web]"
npm --prefix web ci
npm --prefix web run build
~~~

Configure the service outside the checkout. Credentials remain server-side and
must never enter Git, browser bundles or public evidence.

| Setting | Meaning |
|---|---|
| BRIDGE_WEB_STORAGE | Absolute private session, upload and workflow storage |
| BRIDGE_WEB_TOKEN | Operator login secret of at least 24 characters |
| BRIDGE_WEB_MODEL_BASE_URL / BRIDGE_WEB_MODEL | Configured OpenAI-compatible provider |
| BRIDGE_WEB_MODEL_API_KEY | Server-only provider credential |
| BRIDGE_WEB_MODEL_ACTION_PROTOCOL | Explicit json or deepseek_tools protocol; other values fail startup |
| BRIDGE_WEB_STATIC_DIR | Built web/dist directory |
| BRIDGE_WEB_ORIGIN / BRIDGE_WEB_PORT | Exact browser origin and loopback port |
| BRIDGE_WEB_TRUSTED_ANCESTORS | Optional startup-only approved ancestor identity pins |
| BRIDGE_WEB_CELL_STATE_MEASUREMENT_SPEC_REF | Optional registered P0-02 MeasurementSpec; no scientific default |
| BRIDGE_WEB_SHARE_RESULT_SUMMARIES | Exactly 1 enables owner-authorized bounded summaries; unset/0 disables |
| BRIDGE_WEB_PROTOCOL_COMPILER_PYTHON | Optional source-pinned BPL 2.4.0 runtime |

The default json protocol requires one typed JSON action. deepseek_tools uses
the same validated application actions through native function definitions.
Malformed, mixed or unsupported responses fail closed. Model output can prepare
an unapproved plan but cannot approve or execute it. Exact package eligibility
is always checked locally.

The service may be started with the documented bridge.web entry point. Operators
must verify the installed package, built client and configured dependencies for
their own deployment; repository source status is not a deployment receipt.

## A typical conversation

The complete ten-step product behavior is specified only in
[PRD section 6.1](BRIDGE_PRD.md#61-agent-总体工作流). The current accepted preview
covers:

1. The researcher states the question and uploads material.
2. Deterministic extraction records observable structure separately from claims.
3. The Agent asks only necessary questions and can retain unknown.
4. The researcher reviews a concise sourced fact summary, together or fact by
   fact. Absent facts, explicit-but-unparseable facts, conflict and uncertainty
   remain distinct.
5. The researcher confirms question, overall scope, resource ceiling, stop
   conditions and an exact unapproved plan; approval is a separate action.
6. P0-01 returns actual QC observations, denominators, limitations and revised
   eligibility. Work continues autonomously only inside unchanged approval.

Product-only or source-only corrections can preserve compatible QC. Assay,
matrix or QC-relevant metadata changes invalidate the binding. Old versions and
receipts remain traceable; the server never rehabilitates corrupt historical
evidence by silently substituting a newer run.

Protocol review follows the
[approved BPL design](superpowers/specs/2026-09-09-protocol-bpl-design.md).
The model proposes source-backed fragments; the server assembles one
authoritative representation and runs a fixed compiler under limits. Source
coverage, compiler status, human review and biological meaning are separate.
Unknown or ambiguous source facts stay unresolved; a compiler default is never
accepted as the missing experimental value.

## Stop and input corrections

Stop fences subsequent model/planning work. A non-interruptible tool step may
finish; its actual outcome remains recorded. Stopping does not retract inputs.

Ordinary chat does not edit committed declarations. A correction opens an exact
before/after review:

- Confirm change applies only the displayed ID/digest-bound proposal.
- Discard change drops that proposal.
- Keep current inputs explicitly resolves review without an edit.

None approves analysis. Fact corrections first expose affected dimensions,
comparisons and report versions, then propose a partial update. Recompute occurs
only after confirmation; unaffected evidence is reused and previous versions
remain available. This is separate from autonomous checks under unchanged facts,
scope and resources.

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
| artifacts, preview and transcript | Authenticated, integrity-checked retrieval |

Execution uses PlanBuilder, immutable approved requests,
ToolExecutionPipeline and LocalWorkflowExecutor. The service does not execute
model-generated commands or invoke scientific libraries outside registered
packages.

## Privacy and interpretation

- Default provider context contains conversation text and bounded status, not
  tool-owned biological measurements.
- With explicit owner authorization, allowlisted aggregate P0-01 and supported
  P0-02 summaries may be shared. Raw matrices, observation rows, source/sample
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
and the [Web validation record](validation/web_preview_20260905.md).
