# P0-10 Claim Verifier

This directory contains the deterministic structured-claim verification package.

## Interface at a glance

- **Input:** exactly four checksummed objects: ReportDraft, P0-09 Case graph
  manifest, package-authoritative ClaimPolicySpec and StatementRegistry.
- **Output:** one `ClaimVerificationResult` receipt plus three typed review
  figures with complete TSV fallbacks and an artifact manifest.
- **Boundary:** `verified` means evidence/policy correspondence, not biological
  truth, public-release authority, efficacy, safety, potency or GMP release.

## Documentation

- [Implementation, software, calls and current evidence](../../../../docs/tool-packages.md#p0-10)
- [Tool Card — authoritative runtime contract](../cards/P0-10.md)
- [Scientific task card](../../../../docs/bridge_spec_v0.1/claim_verifier_task_card.md)
- [Request example](../../../../examples/requests/p0_10_claim_verifier.json)

Use `bridge-tool describe P0-10` for the installed version, schemas, environment
and registered method IDs.
