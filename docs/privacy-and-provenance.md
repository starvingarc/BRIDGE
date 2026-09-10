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

Web clients must render `PublicSafeReport.claim.text` as escaped plain text.
They must not inject it directly as HTML or Markdown. A candidate with no
registered blocking finding is not proof that a separate renderer is XSS-safe.

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
recorded in the [Web validation history](validation/web_preview_20260905.md).

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
not made provider-safe by matching a string pattern. Hard-count accounting keeps
selected-view counts/fractions and unavailable soft mass; local denominator and
producer labels are replaced by per-turn aliases for the model.

Authenticated browser evidence retains verified program IDs/roles, exact
receipt/artifact bindings, dependency versions and local display-artifact IDs.
Graph-query drilldown resolves the original source manifest and graph version
through canonical identity/hash bindings, not a latest-tool lookup. Display
links grant no public export authority. Valid model hypothesis citations resolve
back from ephemeral aliases to exact local evidence before display; unbound
citations or checks outside the scope fail closed.

Fact corrections do not rewrite immutable receipts. The public session
projection reports current, review-pending or historical binding state, and
historical scopes cannot resume against changed facts/resources. Partial
recomputation requires new consent for the selected checks.

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
