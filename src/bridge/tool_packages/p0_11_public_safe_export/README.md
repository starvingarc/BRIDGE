# P0-11 Public-safe Export

P0-11 provides two local deterministic operations:

- `report_export` rebuilds a P0-10-eligible report through a claim-field
  allowlist and records whether a supplied value matches the candidate digest.
- `artifact_audit` checks checksummed JSON, Markdown, CSV and SVG candidates
  under registered format and disclosure-pattern rules. The HTTPS host
  allowlist applies to links; remote Markdown images are forbidden.

Version 0.4.0 also emits two typed local-review figures per mode, with complete
TSV fallbacks and SVG/PNG/PDF renders. The report views show claim-content field
projection and candidate-digest/local-file state. The artifact views show
candidate status and an explicit artifact-by-check matrix.

No mode uploads data or grants publication permission. A matching digest does
not authenticate its supplier or show that content was reviewed. “No registered
rule blocked” is limited to the rules that ran and is not comprehensive
de-identification.

`ToolRunV2` and the generic `artifact_manifest.json`
(`scope=internal_run_provenance`) contain internal execution provenance and
must not be presented as public-safe downloads. A user-facing client may expose
only an explicitly selected public candidate or visualization artifact set, not
all `run.artifacts`. Claim text must be escaped and rendered as plain text,
never injected as HTML or Markdown.

Results remain `candidate`, `domain_score=null` and
`score_state=unavailable`.

## Documentation

- [Implementation and exact interfaces](../cards/P0-11.md)
- [Scientific task card](../../../../docs/bridge_spec_v0.1/public_safe_export_task_card.md)
- [Tool-package overview](../../../../docs/tool-packages.md#p0-11)
- [Report-export example](../../../../examples/requests/p0_11_public_safe_export.json)
- [Artifact-audit example](../../../../examples/requests/p0_11_public_artifact_audit.json)

Use `bridge-tool describe P0-11` and `bridge-tool input-contract P0-11` for
the installed contract.
