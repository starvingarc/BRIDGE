# P0-11 public artifact audit validation — 2026-08-27

## Scope

This record covers P0-11 v0.3.0 with two callable modes:

- the existing four-object allowlisted JSON report export;
- the new two-object audit for checksummed JSON, Markdown, CSV, SVG and ZIP
  candidates.

It validates engineering behavior only. It does not establish complete
anonymization, scientific validity or release permission.

## Interface evidence

- `bridge-tool describe P0-11` reports v0.3.0 and 14 registered methods.
- `bridge-tool input-contract P0-11` reports `report_export` and
  `artifact_audit`.
- Artifact-audit inputs are a frozen policy and a manifest of regular local
  files; output is one path-free `PublicArtifactAuditResult`.
- Unsafe content is a completed audit with `audit_state=blocked`; malformed
  contracts or changed files are typed execution failures.

## Verification

| Check | Result |
|---|---|
| P0-11, registry and shared-contract matrix | `103 passed` |
| Full pytest | `1232 passed, 8 warnings` |
| Clean-wheel P0-11 matrix | `24 passed`; imports resolved from the wheel install |
| Tool discovery | Exactly 12 packages |
| Knowledge validation | Valid; no dangling method or source refs |
| Repository policy | Passed |
| Diff hygiene | Passed |

The artifact matrix executes strict JSON Schema validation, Markdown and URL
checks, Pandas/CSV rules, defused SVG parsing, ZIP structure checks, provenance,
checksum, MIME and leak rules. Adversarial fixtures cover raw Markdown HTML,
CSV formula injection, SVG active content, ZIP path traversal and file
replacement.

## Boundary

A passed audit means the supplied files satisfied the frozen first-version
rules. It is not a privacy proof. P0-11 remains `candidate`,
`domain_score=null` and `score_state=unavailable`; it performs no upload.
