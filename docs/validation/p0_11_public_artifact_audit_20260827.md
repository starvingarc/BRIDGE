# P0-11 public artifact audit validation — 2026-08-27

## Scope

This record covers P0-11 v0.3.0 with two callable modes:

- the existing four-object allowlisted JSON report export;
- the new two-object audit for checksummed JSON, Markdown, CSV and SVG
  candidates.

It validates engineering behavior only. It does not establish complete
anonymization, scientific validity or release permission.

## Interface evidence

- `bridge-tool describe P0-11` reports v0.3.0 and the narrowed method set.
- `bridge-tool input-contract P0-11` reports `report_export` and
  `artifact_audit`.
- Artifact-audit inputs are a frozen policy and a manifest of regular local
  files; output is one path-free `PublicArtifactAuditResult`.
- Unsafe content is a completed audit with `audit_state=blocked`; malformed
  contracts or changed files are typed execution failures.

## Reproducible verification

The focused P0-11, registry and shared-contract tests are run from the server
environment. Repository policy, knowledge validation, generated Schema parity
and `git diff --check` are run on the same source tree. This record intentionally
does not freeze repository-wide test totals or wheel hashes, which change as
independent modules are integrated.

The artifact matrix executes strict JSON Schema validation, Markdown parsing,
an HTTPS host allowlist, Pandas/CSV rules, defused SVG parsing, manifest-ref
syntax checks, checksum, MIME and leak rules. External URLs reject userinfo,
query, fragment and non-default ports. SVG `url()` values must point to an
existing local fragment. Adversarial fixtures cover raw Markdown HTML, CSV
formula injection, SVG active content, missing/external SVG resource references,
ambiguous URLs and file replacement.

Manifest refs are syntax-checked only. The audit does not contact or validate a

## Boundary

A passed audit means the supplied files satisfied the frozen first-version
rules. It is not a privacy proof. P0-11 remains `candidate`,
`domain_score=null` and `score_state=unavailable`; it performs no upload.
