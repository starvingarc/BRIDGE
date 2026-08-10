# Privacy And Provenance

## Repository Rules

Do not commit private expression data, internal sample metadata, server paths, usernames, credentials, restricted SOP text or copyrighted full text without an explicit redistribution license.

Public accessions, DOI metadata and approved aliases are allowed. Internal assets are represented by logical IDs and access-policy records.

## Runtime Records

Internal runtime manifests may contain controlled artifact locations, but every object must also include a stable asset ID, version and checksum. Public-safe output is generated from an allowlist and never by editing the internal report in place.

## Knowledge Sources

- Official documentation, source repositories and primary papers are recorded separately.
- Open-license full text may be indexed with its license and snapshot hash.
- Restricted full text remains outside Git and is represented by an asset ID and access policy.
- Live Web findings are candidate curation material and cannot change a formal run.

## Fixtures

Committed fixtures must be synthetic, public, licensed or irreversibly de-identified. Each fixture records source class, intended tests and checksum. A fixture validates only the behavior it explicitly covers.
