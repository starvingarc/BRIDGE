# Privacy And Provenance

## Repository Scope

Repository content is limited to code, schemas, documentation, public accession
and DOI metadata, approved aliases, and licensed or explicitly authorized
fixtures. Controlled assets are represented by logical IDs and access-policy
records.

## Runtime Records

Runtime manifests bind each controlled artifact to a stable asset ID, version
and checksum. Public-safe output is generated independently from an allowlist.

P0-09 graph facts contain logical object IDs, versions, content hashes and approved evidence/provenance references, not local input paths or raw rejected payloads. Runtime `ToolRunV2` artifact paths remain deployment-local retrieval metadata; Case/Comparison JSON and Parquet facts use checksummed filenames and graph manifests. A rejected sibling record is represented only by source kind, source ID or index, digest and reason codes. P0-09 output is still internal evidence infrastructure and is not a public-safe export; P0-11 must regenerate any future public package from its own allowlist.

P0-11 keeps the same boundary. `ToolRunV2` and its generic
`artifact_manifest.json` (`scope=internal_run_provenance`) contain local
retrieval paths, environment identity and input hashes; they are internal
receipts, not public downloads. User-facing delivery must select the three-file
report candidate or the explicit visualization artifact set rather than expose
all `run.artifacts`.

The public report deliberately retains public object IDs, aliases, policy
references, target channel, timestamps and source/receipt hashes. P0-11 visual
profiles and artifact sets also retain generated run/result IDs and
source/data/config/render hashes for exact lineage binding. These are linkable
fingerprints and do not make content anonymous. The registered-pattern
scanner is a bounded gate for known path, host, email, credential and internal-ID
forms; it does not detect arbitrary names, phone numbers or context-sensitive
fields. Public aliases, claim text and statement/policy references remain the
responsibility of controlled policy and P0-10 receipt creation.

## Runtime Environment And Developer Diagnostics

The Web runtime has three server-owned identities: `development`, `acceptance`
and `production`. Production is the fail-closed default. Diagnostics default to
off and cannot be enabled for acceptance or production. Invalid combinations
fail startup. Each storage root contains a private, owner-only environment
binding; a different environment is refused. A nonempty unbound legacy root
requires a one-time explicit operator binding and its existing session files are
not rewritten. Cookie names include the runtime environment and opaque login credentials are
scoped to each private account database, so authentication from one same-host
instance cannot be replayed into another. Binding an environment does not assign
legacy records to accounts; Web startup requires initialized account storage.

The normal authenticated session response is the researcher view in all three
environments. A development instance may explicitly expose the authenticated
diagnostics route. That projection is allowlisted to runtime/package identity,
session state and internal error code, plan/step states, assessment state and
budgets, bounded provider-error categories and tool-run tool/state/plan IDs.
The categories `result_sharing_disabled` and `review_context_limit` distinguish
a blocked sharing permission from an oversized review/repair context; they do
not grant permission, retry automatically or expose the rejected context. It
contains no prompts, message or response bodies, browser/request material,
paths, credentials, uploaded data, receipt names/hashes or scientific values.
The disabled route is 404; a query, header, browser-storage value or claimed
role cannot opt into it.

Web clients must render `PublicSafeReport.claim.text` as escaped plain text.
They must not inject it directly as HTML or Markdown. A candidate with no
registered blocking finding is not proof that a separate renderer is XSS-safe.

## Session Lifecycle

Archive/restore changes only the session's organization flag and retains its
private evidence and provenance. Explicit deletion removes that session's
private directory and its uploaded copies and generated files, after uploads
and queued/running work have settled. The application does not follow nested
symlinks to delete external originals or shared references. A partial filesystem
cleanup is hidden from list/recovery and remains retryable by session ID.

Shared workflow event journals and operator backups have separate retention;
this action is not a claim of secure erasure from those stores. Deleting a
session neither changes another session's evidence nor confers scientific
qualification. Historical content is never deleted merely by loading/migrating
it or by archiving it.

## Approved Model Interpretation Boundary

The owner may explicitly authorize a private deployment to send bounded,
field-allowlisted aggregate results to its configured model for research
interpretation. Status-only remains the default. Raw matrices, observation-level
records, sample/source identities, private paths, credentials and private
provenance hashes remain local. Aggregation is not anonymous-data certification
or public-export permission.

A summary must preserve verified tool values, denominators, uncertainty and
missingness. Its local per-turn provenance binding must remain available without
being transmitted. Unknown fields or unsupported result shapes are excluded by
construction, not passed through a generic redaction filter. The approved behavior is bounded by the
[canonical PRD workflow](BRIDGE_PRD.md#6-agent-功能需求); actual tested scope is
recorded in the [Web validation history](https://github.com/starvingarc/BRIDGE/blob/d3d69363c50541fb34320f703db2995edb27105e/docs/validation/web_preview_20260905.md).

Ordinary follow-up questions use the same opt-in to receive saved report metadata:
input revision, graph version and current/historical access state, limited to the
last 24 distinct readable HTML report versions. Report prose, filenames, URLs,
identities and hashes are excluded. The exact metadata sent is retained with the
turn's local result-context record. Report existence and version are workflow
facts; report generation does not establish scientific validation. With sharing
disabled or input corrections pending, this report context is withheld.

Feature-coverage facts follow the same sharing boundary in assessment generation,
interpretation review and text repair. The outbound allowlist is object_version,
complete, feature_count, semantics, and results containing only identifier
and state. Upload hashes, input revisions, matrix locations, identifier-column
paths and future unlisted fields stay in the private local snapshot for provenance.
Coverage checks exact identifier membership: present does not establish
expression, and not_found in a complete index does not establish biological
absence. An unmatched identifier in an incomplete index remains unknown.

## Conversation Model Selection

Conversation records store provider ID, model and optional effort, not API keys.
The owning account's private model profile stores the recent choice and bounded
capability metadata. Endpoint, credential, protocol and catalogue changes invalidate
that metadata. A capability refresh sends only an authenticated model-list request;
connection probes continue to send fixed synthetic text. Neither sends research data.
Model selection does not broaden existing research-context or result-sharing gates.
The task captures credentials privately at enqueue time; its public configuration
contains only the existing connection identity plus model, provider ID and effort.
DeepSeek reasoning needed to continue a native skill call is kept only in that
in-memory request sequence, not appended to user conversation history or evidence.
Existing private raw protocol-response receipts retain their established policy.

## Bound Workbench Conversation Purpose

Opening a research or run conversation binds it to that owned workbench scope.
Ordinary Agent turns receive the registered research/protocol names and notes,
protocol stages/reagents/operations (including recorded relative timing), source-review
status and execution-readiness reasons, run dates/state/purpose, sample collection metadata,
open leads and pending-action status. A run uses its pinned protocol edition and
its direct parent; a research conversation covers that research's records.
These are user-entered workflow records, not verified scientific measurements.
The configured provider receives this bounded record context even when aggregate
result sharing is disabled. This purpose is separate from assessment generation,
interpretation review and scientific-input drafting; it grants none of their
sharing or scientific-admission permissions.

An explicit nested allowlist excludes cell-line identity, material/session
bindings, source locators, field-level recipe provenance, source-review notes,
hashes, raw files, measurement
values and future unregistered fields. Logical workbench IDs retain scope and
version relationships. Known private paths in allowed prose are redacted; names
and arbitrary notes can still identify a study and are not certified anonymous.
A context over 48 KiB returns explicit unavailability and object counts instead
of silently omitting records. Private per-turn snapshots and digests retain the
context used; a changed context rejects the late reply/action before admission.
Verified measurements still require the existing session result-summary gates.

## Executable Model-Context Contracts

The regression allowlists are maintained in
[tests/model_wire_contract.py](../tests/model_wire_contract.py), independently
from production projection code. `ASSESSMENT_GENERATION_ALLOWLIST`,
`INTERPRETATION_REVIEW_ALLOWLIST`, `DIRECTED_REPAIR_ALLOWLIST` and
`WORKBENCH_CONTEXT_ALLOWLIST` define the
per-purpose key contracts. They check captured HTTP context JSON in both provider
protocols, including nested objects and every compressed-table column, even a
column marked absent in all rows. Evidence aggregates use an explicit recursive
field vocabulary; gene-detection and definition-decision maps accept only the
existing opaque per-turn aliases. Unknown keys have no wildcard exception.

| Privacy clause | Executable contract |
|---|---|
| Approved model interpretation and feature coverage | `EVIDENCE`, `AGGREGATE_FIELDS` and `FEATURE_COVERAGE`; private receipt/upload/source bindings remain excluded. |
| Bound workbench conversation | `WORKBENCH_CONTEXT_ALLOWLIST`; registered record metadata and protocol text only in this purpose. Nested private/future fields are excluded; captured requests and injected leaks are checked in `tests/test_workbench_conversations.py`. |
| Biological background | `BIOLOGICAL_CONTEXT` permits the documented confirmed facts and the existing local revision counter; names, cell-line identity and protocol text remain excluded. |
| Public literature | `LITERATURE`, `LITERATURE_METADATA` and `LITERATURE_SOURCE`; DOI/PMID, public URLs and public abstract/content hashes identify retrieved literature, not private uploads. Review and repair receive read abstracts only. |
| Assessment purpose and pending revision | `OPTION`, `PREVIOUS_ERROR`, `HYPOTHESIS` and `REVISION`; bounded choices, safe feedback and the draft's approved citations/relations remain distinct from private provenance. |
| Status-only default | `assert_model_context(..., shared=False)` requires empty evidence and withheld background, with no coverage or revision. Review and repair must refuse before transport. |

Run `PYTHONPATH=src python -m pytest -q tests/test_model_wire_contract.py`
for the wire contract and injected-leak checks. Existing assessment transport,
status-only and graph/native projection tests also apply these independent
contracts to real coordinator/projection outputs.

To register a newly model-visible field, review its purpose and meaning, update
the explicit allowlist, update the corresponding privacy clause and add a
captured-request test plus an unregistered-field negative case. Do not derive test
allowlists from production keys or automatically approve fields from generated
fixtures. Fields allowed in one purpose or sharing mode are not thereby allowed
in another.

These are regression checks, not a new runtime sanitization layer. They preserve
current valid payloads and do not change the developer-diagnostics contract,
sharing consent or public export policy. Key checks cannot establish that
arbitrary question/draft prose is anonymous, and the tested request paths are
limited to assessment generation, consistency review, directed repair and bound
workbench conversation.
Existing value, provenance, citation and scientific checks remain necessary.

## Biological Background And Public Literature

With aggregate-result sharing enabled, the configured model also receives an
explicit projection of confirmed intake: product family, starting/target cell
type, culture day, target stage, sampling context, independent-culture count,
assay and sequencing method. These remain researcher statements. Product name,
cell-line identity, protocol name/body, sample/source identifiers and paths are
excluded. Status-only mode withholds this background as well as result summaries.

External literature retrieval has separate per-scope consent. The user selects
public concept references from the reviewed search vocabulary; the model selects
only those references and a fixed biological focus. The server constructs the
query without product text, private numbers, identifiers or model-written URLs.
Initial limits are at most three searches, five discovery records per search and
six reads. Missing public terms require a reviewed vocabulary addition.

Europe PMC is the sole fixed HTTPS endpoint. Redirects, oversized responses and
invalid identities are refused. Reservations consume the search/read budget before
network I/O outside session locks; cancellation or scope changes discard late
results. Disabled, no-results, partial and unavailable states remain distinct.
Discovery metadata and read abstracts are separate; only a read abstract can be
cited as mechanistic background. DOI/PMID deduplication prevents multiple records
of one paper becoming independent support.

Private explanation v1.1 freezes the approved query history, read attempts,
provider-owned bibliographic fields, read time, exact normalized abstract and
hashes. Context/snapshot v0.4 carries that explanation without changing old v0.3
hashes. External text is untrusted data and is rendered escaped. The paper's
species, lineage, stage and experimental applicability remain an explicit,
unverified model inference. A source link or hash verifies attribution and
integrity, not entailment, paper quality or biological truth. Research report
verification remains limited to the existing numerical evidence contract.

Public literature snapshots retain bounded provider publication types and
correction/retraction relationships. Missing notice metadata remains unknown;
an absent flag is not proof that an article is unretracted. Reports show provider
notices next to the stored abstract. Duplicate references to one paper are
rejected before a new interpretation version is persisted.

## User Response And Message Provenance

User-visible errors are fixed safe issues with a public ID, researcher message
and an actual result-preservation state. Internal reason codes remain in private
session state and, when allowed, the development diagnostic projection. A tool
failure, missing input, unknown scientific value and valid negative result are
not interchangeable. Existing results are neither erased nor declared present
from an error-code pattern alone.

New messages carry one server-owned source: user input, server template,
provider-admitted text or deterministic evidence. Ordinary provider text is
stored only after action-schema parsing and the applicable bounded content
checks. Result statements require the current safe summary and evidence alias;
known alias/state/value conflicts produce the fixed public boundary
`解释尚未通过核对`, not a substitute scientific claim. Raw rejected text is not
stored by this message path. The assessment revision exception below keeps a
bounded draft outside messages and admitted evidence. This is a bounded contradiction gate, not general semantic
verification. Historical assistant messages with no trustworthy classification
remain visible with a warning but do not re-enter provider context or a newly
generated transcript. Historical and current user questions remain visible.

## Assessment Purpose

Assessment requests use a separate explicit field projection of canonical
aggregate results. Question text is intentionally sent to the configured model;
the approval panel discloses this and the deployment's result-sharing setting.
Status-only remains the default.

Each provider turn receives fresh opaque selection, evidence, measurement,
graph/node/family and program/method aliases. They are random, not hash prefixes
or deterministic digests of private identities. Within-turn joins remain
consistent. Private binding maps retain normalized request fingerprints,
canonical evidence aliases and exact receipts; they are never included in the
serialized provider context. Admission reconstructs and rechecks the canonical
request after the model reply, preserving exact deduplication.

Large per-turn evidence/provider binding maps are stored in content-addressed
private sidecar files in the session directory. The session contains only their
SHA-256 references on disk; loading verifies each digest, file type, ownership
and size before reconstructing the original maps. Repeated maps share bytes,
without dropping historical turns or rewriting scientific artifacts. Legacy
inline maps remain readable. Each map is bounded to 1 MiB, referenced map bytes
to 32 MiB per load, and the main session JSON remains bounded to 8 MiB. These
private files are not registered artifacts and are never part of a public export.
A missing, altered or linked sidecar fails closed. Session deletion also removes
its sidecars. Downgrading to software that lacks this format requires restoration
of the corresponding pre-upgrade session backup, not a code-only rollback.

Program summaries additionally carry the built-in portrait's reviewed public
family and the registered Scanpy/ULM method display name. These fixed descriptors
do not expose the aliased source/program identities or gene membership; unknown
custom labels remain opaque. Original values, nulls and missingness reasons are
unchanged, and these descriptors grant no scientific qualification.

A literature-enabled assessment may retain one schema-validated unadmitted draft
and its exact, field-bound review findings in private session state. This is a
pending revision, never a message, interpretation version, graph fact or report
input. Explicit continuation spends the existing scope budget and sends the
draft with its criticism as untrusted data. The revision request includes only
draft-cited measurement records and read abstracts, with original defaults and
tool-level context; omitted measurements are explicitly not absent or negative.
When findings concern only statement, rival or prediction prose, the model returns
bounded field replacements. The server rejects duplicate/out-of-range targets and
reassembles the unchanged citations, literature uses and other fields; no-op repairs
are rejected. Findings involving literature or an unavailable review retain the
full-draft repair path. Both paths consume one generation turn and require the same
separately charged full consistency review; neither can admit a draft on its own.
The complete current context remains authoritative for citation admission and
the following consistency review. Initial analysis keeps its full evidence view.
Canonical citations are rebound to fresh request aliases; a missing current binding discards the revision. Transport
failure retains the latest validated proposal for another explicit continuation.
An invalid review contributes no findings and never restores an older draft. A successful review or
replacement scope removes it. Cancellation and input-revision fences still
prevent late admission. No raw provider response or reasoning trace is retained
by this mechanism; ordinary session access and deletion rules apply.

The allowlist preserves tool-owned values, uncertainty, denominators and bounded
canonical missingness codes. It excludes receipt/artifact/request hashes,
plan IDs, input identities, local URLs, paths, complete provenance and local
dependency dictionaries. The ordinary intake/result purposes are unchanged;
this is not a generic redaction or anonymization service.

Graph-query summaries preserve claim domains, literal missingness, reconciliation
eligibility/state/direction and numerical intervals. Metric names are selected
from the existing producer enums/Literals; missingness reasons use the compiler
contract and reconciliation reasons use its authoritative reason tuple. Only
the built-in candidate policy words have direct claim/requirement/channel labels.
Unrestricted custom labels and unrecognized units/metrics remain opaque or
explicitly semantically unavailable, even when Schema-valid. Private values are
not made provider-safe by matching a string pattern. Value projection distinguishes
numeric values, literal null and withheld text independently of the unchanged
canonical evidence state. Hard-count accounting keeps selected-view counts/fractions
and unavailable soft mass; the existing summary row/byte limits still refuse oversized
projections without truncation. Local denominator and producer labels are replaced
by per-turn aliases for the model.

Authenticated browser evidence retains verified program IDs/roles, exact
receipt/artifact bindings, dependency versions and local display-artifact IDs.
Graph-query drilldown resolves the original source manifest and graph version
through canonical identity/hash bindings, not a latest-tool lookup. Display
links grant no public export authority. Valid model hypothesis citations resolve
back from ephemeral aliases to exact local evidence before display; unbound
citations or checks outside the scope fail closed.

Structured explanations distinguish observation-backed hypotheses from evidence-gap
statements. A gap statement has no supporting or opposing citations, cites at least
one current missing record, and has no predicted observation or discriminating check.
It describes only that run's limitation, not a negative biological finding. The
existing `competing_explanation` field is displayed as a limitation for this case.
Missing citations in a support field are still rejected, never repaired automatically.
Report preparation may retain these limitations alongside supported explanations;
gap-only content cannot satisfy its existing observation-backed explanation requirement.
The internal Web action validator and its provider schemas enforce this distinction;
the persisted report shape and public schema are unchanged.

Fact corrections do not rewrite immutable receipts. The public session
projection reports current, review-pending or historical binding state, and
historical scopes cannot resume against changed facts/resources. Partial
recomputation requires new consent for the selected checks.

## User Artifact Access

Artifact classification uses the registered producer and artifact kind stored
by the server, not a client filename or extension. Verified deterministic P0-10
attachments are `research_report`; other admitted scientific displays and
tables are `user_result`. Run manifests, logs, provider request/response
material, receipts, traces and unverified report drafts are
`developer_diagnostic` and have no user-list, download, preview or
acknowledgement bypass.

A new research report records its validated input revision, graph identity and
version, graph-manifest hash, snapshot hash, renderer ID and snapshot object
version. A report is current only when those bindings match the current input
and latest valid graph of the same identity. Legacy or stale reports are exposed
as `historical_unreviewed` with a warning. Their exact registered bytes remain
unchanged. An authenticated acknowledgement records only the artifact checksum
and time and permits retrieval of those bytes; it does not change currentness,
scientific qualification or provenance. The same policy runs for artifact
listing, direct GET, preview and acknowledgement, so renaming cannot bypass it.

## Intake Extraction Purpose

The owner approved a separate `intake_extraction` purpose for uploaded
experimental metadata and differentiation protocols. Deterministic readers
select bounded semantic metadata; raw expression matrices, observation rows,
gene/barcode values, sample/capture identities, filesystem paths, credentials
and private hashes are not part of its request contract. Identifiers used for
sample grouping stay in the authenticated local projection. Protocol passages
are treated as untrusted data, never executable instructions. Known credential,
email and private-path forms are redacted; this is not general anonymization
or permission to upload arbitrary personal information. Before either extraction
or protocol formalization, the server rebuilds the local identity inventory from
the exact checked H5AD. It includes observation IDs, recognized sample/capture/
batch/replicate/donor aliases, and explicitly selected identity/culture columns;
an older cached inventory is not authoritative. Incomplete or over-budget identity
reads block model-context construction. Identity replacement uses token boundaries
so short IDs do not corrupt unrelated scientific words.

Each model field must cite a supplied source. The server, not the model, supplies
its bounded original-text excerpt. PDF text uses reading order rather than
interleaved columns. Whitespace/typographic normalization does not allow omitted
words, fabricated sources or matrix-derived assay assertions.
Nonuniform or incomplete observation summaries cannot establish a global
culture day. Existing cell annotations do not establish intended target identity.
Counts provenance and independent cultures are not model-inferred. The authenticated
intake UI may show bounded candidate batch-column values and accept a researcher
declaration of that column's meaning. These profiles, the selected column,
relationship and upload hash remain private and are excluded from extraction and
ordinary model context. A derived count requires explicit per-value independent
culture confirmation, complete metadata and no missing identifiers. This is still
a researcher declaration, not verified biological-unit relationships or formal
replicate eligibility. Incomplete columns and free-text mappings retain an unknown
count; older manually entered counts do not acquire an inferred column binding.
A custom column-meaning answer is also retained verbatim in the private draft and
exact confirmation source record, bound to the selected column and upload. It is
not parsed into a role or count and does not enter the extraction model context.
Changing or rechecking that mapping clears the superseded supplement. Proposed
protocol date ranges are retained only when the cited passage explicitly contains
that interval; sampling dates and inferred next-day starts do not establish it.
Unsupported boundaries stay empty for review. This bounded check is not semantic
validation of every stage label or operation. Uploaded protocol stages are
prescribed intent, not observed execution. Failed citation
validation or interrupted extraction retains the locally read facts.

Previously confirmed sample/capture/culture identity columns remain masked for
the same immutable upload after a selector is changed. Both model purposes merge
that upload's historical confirmed selectors into the fresh checked-file inventory;
selectors belonging to another upload do not affect its masking or availability.

The file hash, protocol bytes, source labels and user revisions remain bound
locally. Exact confirmation synchronizes the draft baseline, including corrected
or explicitly cleared values, and retires prior manual overrides. A subsequent
deliberate answer starts a new unconfirmed draft; later model extraction cannot
replace an already confirmed non-missing fact. A late model response cannot
replace a newer manual answer. Newly attached protocols reopen the intake draft; an earlier confirmation does not
automatically confirm a new source. Answers and extraction never approve
analysis, authorize export or supply downstream scientific measurements.
Ordinary conversational requests retain their prior private-intake boundary.

## Protocol Formalization Purpose

The owner separately approved `protocol_formalization`: the configured provider
receives bounded, sanitized passages from one attached protocol and relevant
versioned user supplements. It receives no H5AD expression/observation rows,
sample identities, credentials, upload/protocol hashes or private filesystem
paths. Old attachments are not backfilled by a GET. Each new attachment is
handled independently; extraction hands off within the existing fenced worker
only when the isolated compiler runtime is configured.

The source module accepts ordered BPL body fragments with step/source IDs,
questions and explicitly excluded passages. The server derives the full program
and physical spans from that one sequence, resolves quotes from checked sources
and records source accounting and unchecked compiler semantics. Balanced fragment
boundaries cannot close/replace the fixed protocol wrapper: each fragment must
end with complete strings/comments and balanced parentheses, brackets and braces.
Complete multiline strings retain their original bytes. Formatting newlines
inside call expressions become spaces before assembly; non-whitespace symbols,
strings/comments and source statements remain unchanged. This idempotent layout
normalization is not semantic validation. Repairs may replace
existing fragments only after failed syntax/compiler checks, then regenerate all
spans without altering the original readable source statements or their order.
Repairs may also append missing existing source IDs to a step while retaining its
prior citations in order. Source-only patches leave BPL and readable content
unchanged, including after compilation passes. Unknown or duplicate additions
and reference-limit overflow are rejected; every patched draft is revalidated.
Unsupported numeric literals identify their owning step, value and unit for
bounded repair, without selecting or inventing a supporting source.
An unparsed wait duration without an outstanding question requires a separate
source-focused model review within the same three-request budget. The model must
either append a source-backed question or identify a verbatim cited duration/end
condition. A valid string such as `8 days` is not an absent source value merely
because the compiler cannot interpret it. Review cannot change existing code,
steps or questions. Unaddressed review cannot publish a completed representation;
explicit unsure remains unresolved without another automatic question. Decisions
and supporting excerpts remain in the private attempt audit, bound to the owning
step and exact server-supplied diagnostic line and column, retaining distinct
calls on the same physical line. This is a bounded
model check, not proof that every semantic omission has been discovered.
Source accounting also requires every current non-unsure user supplement to be
cited by a generated step; superseded/unsure answers remain history or missingness,
not required condition sources. A stored answer or question-only reference cannot
make an unreferenced supplement incorporated. Generation must represent the
current answer in both readable content and BPL while retaining original citations.
Literal membership and source accounting are deliberately bounded
checks, not semantic entailment or proof of complete preservation. Source day
intervals must not acquire derived durations. At most three model requests are
made per generation; repairs cannot reset the original source-step baseline.
Choice values must occur verbatim in the cited source, even when their displayed
labels are translated. A rejection identifies the offending question/option for
bounded repair; absent explicit alternatives, the model must retain the question
with no suggested choices for free-text/unsure input. Unsupported alternatives
are not accepted as facts or silently presented. Failed attempts remain preserved.
The provider body is captured before envelope, JSON or patch validation, capped
at 1 MiB of decoded HTTP body bytes. Private receipts store base64 bytes, captured
byte count/SHA-256, HTTP status and an explicit truncation flag; an oversized or
interrupted prefix is never described as a complete response. They contain no
request headers, are not included in model repair context and have no public
export route. A pre-response connection failure has no fabricated body receipt.
Rejected replies do not replace the last draft or its paired compiler diagnostics.

Original attachment bytes remain untouched. Complete representations are
append-only BPL/AST/compiler-plan/diagnostic/version files bound to their source
hashes, prompt/model identity and generation. All attempts remain private.
User supplements retain superseded history and never become original-document
statements. Editing BPL releases the old source map; a new version is unreviewed.
Human review is a separate integrity-checked receipt for the exact current
digest. Neither review nor compilation confirms execution, product facts,
independent cultures, scientific inputs, a ToolRun or analysis approval.
Authenticated downloads check session ownership and artifact integrity.

BPL 2.4.0 is pinned by upstream commit and installed source-tree checksum in a
separate Python 3.13 runtime. Its fixed parse/validate/lower entry points use a
human target, a clean environment without provider credentials or HOME, and
30-second/512-MiB/8-MiB resource bounds. This is not an arbitrary-code sandbox:
uploaded code is never executed, and external imports/modules/paths are rejected
before the compiler. There is no experiment simulation, robot export or network
tool grant. Ordinary conversation and scientific-draft purposes do not acquire
protocol contents or artifacts.

## Scientific Draft Purpose

The private Web backend has a separate scientific-input draft request. It
projects only confirmed product_family, target_cell_type and target_stage,
together with versioned local state definitions and their review limitations.
Ordinary chat remains status-only for privately entered intake fields. Stale
or unconfirmed intake cannot supply draft intent. Draft and clarification cards
and their private answer echoes are excluded from ordinary provider history.

The application binds the exact upload, intake revision, source resources and
upstream receipts locally. Candidate choices cannot contain measurements or
arbitrary scientific JSON. Exact confirmation materializes candidate objects,
not reviewed lineage, independent cultures, tool approval or release authority.
Source review prohibitions remain active. This source capability does not imply
that a running deployment or its scientific-draft UI has been updated.

The private internal-report card is a deterministic projection of the exact
candidate ReportDraft and canonical P0-10 result. It contains bounded plain text,
verification reasons and next steps, not raw rows, private paths, hashes or
credentials. It is not included in ordinary model context. This UI projection is
not a PublicSafeReport and grants no export or publication authority.

## Knowledge Sources

- Official documentation, source repositories and primary papers are recorded separately.
- Open-license full text may be indexed with its license and snapshot hash.
- Restricted full text is represented only by an asset ID and access policy.
- Live Web findings are candidate curation material and cannot change a formal run.

## Fixtures

Repository fixtures are synthetic, public, licensed or irreversibly de-identified.
Each fixture records source class, intended tests and checksum. A fixture validates
only the behavior it explicitly covers.

## Private Runtime Ancestor Trust

Private storage rejects ancestors not owned by the process user or root by
default. A deployment operator may call
`bridge.storage.private_paths.configure_trusted_ancestors(ancestors)` at process
startup, before any private-path I/O. The mapping has exact absolute `Path` keys
and `(uid, device, inode)` integer tuples, obtained and approved out of band.
There is no automatic environment discovery, request-level override or runtime
trust expansion. Configuration is copied, validated and locked; changing it
requires a process restart. Repeating the identical configuration revalidates it.

This narrowly trusts the specified directory administrator, not every ancestor
or descendant. Every traversal uses descriptor-relative no-follow opens and
rechecks each configured identity. Replacements, symlinks, identity changes and
group/world-writable trusted ancestors (including sticky ones) are rejected.
Other ancestors retain the default guard. Final private directories must still
be owned by the process user and inaccessible to group/other; files retain the
owner, regular-file and no-follow checks. The guard never changes ancestor
permissions or ownership. Explicitly trusted administrators and root remain in
the deployment trust boundary; this is not isolation from them or a public
multi-tenant security model. Deployment paths and identity pins remain outside
repository content and HTTP/model inputs.


An explicit continuation after an unavailable interpretation review retries the
validated private draft without another generation. The retry consumes one model
turn, reserves fresh private citation maps, and preserves its original proposal
link and all failed-turn history. Admission revalidates the full current context;
review failure retains the draft and consumes the turn without admitting it.


Provider-only evidence tables may use lossless column/row encoding. Missing-field
indices distinguish omitted fields from explicit null, and original record
defaults remain authoritative. Canonical objects and citation choices retain
their original representation. Review and repair include cited sources and
records with their source metadata, program coverage and defaults; omitted
sources or repeated tables never mean absent or negative observations.

A supported interpretation requires a prospective validation design or an
explicit statement of why the rivals cannot yet be distinguished. A gap-only
hypothesis retains its nullable design. Completeness is checked before a paid
consistency review: incomplete prose remains a private pending draft and routes
to bounded field repair. Historical pending drafts receive the same requirements
on continuation. Original findings and consumed turns remain intact; completing
a design does not replace the existing citation and consistency admission gates.
The public interpretation object version and historical report readability are
unchanged.

Literature corrections patch rationale or applicability prose on an existing
source use. They cannot add/remove uses, change source identity or qualification,
or rewrite citation arrays. The reassembled interpretation passes the same full
validation and review as any other revision.

Reasoning-enabled requests, including ordinary conversation, use a bounded
600-second HTTP timeout for the 32,768-token reasoning/output allowance.
An undeclared DeepSeek default receives the same allowance because it may enable
thinking. DeepSeek interpretation review and directed repair retain their larger
65,536-token cap and the same timeout; other review/repair providers start at
20,000 tokens, raised to the reasoning allowance when applicable. No workflow
silently changes the task's effort. A null effort sends no thinking or effort
override and must not be displayed as a confirmed level. Transport failure still spends the
reserved turn and never refunds budget or admits a partial response.

## Internal Test Accounts

Account authentication stores private Argon2id password hashes and opaque, revocable login
cookies. Every session resource and error projection checks ownership. Browser account
changes discard prior requests and scope the remembered session ID to that account.

Registration records the testing notice version. Administrators inspect conversations,
original uploads and registered results through a separate read-only view. Audit records
actor, target, path, status and time without copying content. Disable revokes login and
future requests; already admitted work can finish its approved scope. Reset revokes logins.

Default and personal model credentials occupy separate private files. The API returns
configuration and key-presence status, never keys. Administrators cannot retrieve another
user's key through the UI/API. Host administrators remain trusted with storage access;
backups contain secrets and require the same private permissions. Session deletion does
not erase prior backups, audit or shared workflow journals. Broader cleanup must name
the affected instance and retention scope.

Accounts grant no public release, cross-user sharing or scientific-approval permission.
Configuration and consistent backup/restore are maintained in the
[Web guide](web-preview.md#internal-multi-user-testing).


### 解释核查的用户反馈

会话展示仅从当前被阻塞轮次的白名单错误类别生成失败说明；内容核查意见显示
解释序号、受影响字段与固定修改建议。拒绝草稿、原始模型理由、响应体与内部路径
不进入该公开投影。恢复执行、证据变化或完成后，不继续显示旧核查意见。
核查不可用时可重试已有草稿；发现内容问题时沿用原范围预算定点修订并重新核查。
修订所需额度不足时，页面提供带原范围和草稿摘要绑定的有限继续提案；不包含草稿正文。
提案仍经原有确认与批准流程，保留历史范围，不能静默增加原授权额度或视为解释已通过。
继续范围仅固定原授权中已经接纳并核验的产物作为输入，不重新发现额外来源；
原运行历史保留，旧产物的读取不计为再次执行，新增执行仍消耗新批准的有限额度。
内容核查区分“记录中未记载”与“样本中实际不存在”，以及未来假设条件与当前样本事实；
不能仅凭否定词判定矛盾。条件语句仍须满足推理关系，补充保留意见不能使无依据的前提成立。


Sample workflow handoffs use the bound run conversation. Their model context contains only
logical sample/upload/analysis IDs, registered tool IDs, fixed reason codes and messages,
required field names, declaration field names, workflow states and a field-name mapping for
question cards. It contains no declaration values, matrix/column names, receipt hashes,
measurements or raw artifacts. Scientific result sharing continues through the existing
verified result-summary boundary. Sample question options for observed fields come from the
private file; source/capture IDs are user-entered, never invented by the model. Answers stay
private, bind the sample/material/revision and only resume the declared basic pipeline.
