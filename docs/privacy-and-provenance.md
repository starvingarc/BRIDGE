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
