# P0-11 Public-safe Export

This directory contains the deterministic allowlist-based JSON export package.

## Interface at a glance

- **Input:** exactly four checksummed objects: ReportDraft, eligible P0-10 receipt,
  PublicExportPolicySpec and PublicExportRequest.
- **Output:** an allowlisted `PublicSafeReport`, export manifest and result in an
  immutable local directory.
- **Boundary:** `exported` means a confirmation-bound local JSON bundle was
  written. The package does not upload, verify biology or grant release authority.

## Documentation

- [Tool Card — authoritative runtime contract](../cards/P0-11.md)
- [Scientific task card](../../../../docs/bridge_spec_v0.1/public_safe_export_task_card.md)
- [Request example](../../../../examples/requests/p0_11_public_safe_export.json)
- [Validation record](../../../../docs/validation/p0_11_public_safe_export_20260825.md)

Use `bridge-tool describe P0-11` for the installed version, schemas, environment
and registered method IDs.
