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

## Knowledge Sources

- Official documentation, source repositories and primary papers are recorded separately.
- Open-license full text may be indexed with its license and snapshot hash.
- Restricted full text is represented only by an asset ID and access policy.
- Live Web findings are candidate curation material and cannot change a formal run.

## Fixtures

Repository fixtures are synthetic, public, licensed or irreversibly de-identified.
Each fixture records source class, intended tests and checksum. A fixture validates
only the behavior it explicitly covers.
