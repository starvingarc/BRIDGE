# P0-11 Public-safe Export

P0-11 provides two local, deterministic operations:

- `report_export`: rebuild a P0-10-eligible report as an allowlisted JSON
  candidate with explicit hash confirmation.
- `artifact_audit`: inspect checksummed JSON, Markdown, CSV and SVG candidates
  before an Agent exposes them.

No mode performs a network upload. Results remain `candidate`,
`domain_score=null` and `score_state=unavailable`.

## Documentation

- [Implementation, software and current evidence](../../../../docs/tool-packages.md#p0-11)
- [Tool Card and exact interfaces](../cards/P0-11.md)
- [Scientific task card](../../../../docs/bridge_spec_v0.1/public_safe_export_task_card.md)
- [Report-export example](../../../../examples/requests/p0_11_public_safe_export.json)
- [Artifact-audit example](../../../../examples/requests/p0_11_public_artifact_audit.json)
- [Validation records](../../../../docs/validation/)

Use `bridge-tool describe P0-11` and `bridge-tool input-contract P0-11` for
the installed package contract.
