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
construction, not passed through a generic redaction filter. The approved initial
implementation scope and acceptance gates are tracked in the
[Web integration plan](../plans/web-full-chain-integration.md).

## Intake Extraction Purpose

The owner approved a separate `intake_extraction` purpose for uploaded
experimental metadata and differentiation protocols. Deterministic readers
select bounded semantic metadata; raw expression matrices, observation rows,
gene/barcode values, sample/capture identities, filesystem paths, credentials
and private hashes are not part of its request contract. Identifiers used for
sample grouping stay in the authenticated local projection. Protocol passages
are treated as untrusted data, never executable instructions. Known credential,
email and private-path forms are redacted; this is not general anonymization
or permission to upload arbitrary personal information.

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

The file hash, protocol bytes, source labels and user revisions remain bound
locally. A late model response cannot replace a newer manual answer. Newly
attached protocols reopen the intake draft; an earlier confirmation does not
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

The source module accepts model-proposed BPL plus step/source IDs, questions and
explicitly excluded passages. The server locates exact BPL fragments, resolves
quotes from checked sources and records source accounting and unchecked compiler
semantics. Literal membership and source accounting are deliberately bounded
checks, not semantic entailment or proof of complete preservation. Source day
intervals must not acquire derived durations. At most three model requests are
made per generation; repairs cannot reset the original source-step baseline.

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
