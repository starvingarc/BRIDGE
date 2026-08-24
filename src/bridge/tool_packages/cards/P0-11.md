# P0-11 Public-safe Export

## Purpose

Rebuild a minimal public JSON candidate from an eligible P0-10 report and an
explicit, checksummed allowlist. The source report is never copied wholesale.

## Package contract

| Field | Value |
|---|---|
| Package version | `0.2.0` |
| Runtime state | `implemented` |
| Scientific state | `candidate` |
| EnvironmentSpec | `ENV-EVIDENCE-v0.1` (`health_check_passed`) |
| Input envelope | `bridge://schemas/tool-request/v0.2` |
| Output envelope | `bridge://schemas/tool-run/v0.2` |
| Result schema | `bridge://schemas/public-safe-report/v0.1` |
| Adapter | `bridge.tool_packages.p0_11_public_export.adapter:adapter` |

```bash
bridge-tool describe P0-11
bridge-tool validate --request request.json
bridge-tool run --request request.json
```

The Python SDK accepts the same `ToolRequestV2` through the default
`ToolRegistry` validate and run methods.

## Structured inputs

Each input is a canonical local JSON object with an absolute path, role, Schema
URI, object version, media type and SHA-256 checksum.

| Role | Schema | Required content |
|---|---|---|
| `report_draft` | `bridge://schemas/report-draft/v0.1` | The original structured P0-10 ReportDraft. |
| `claim_verification_result` | `bridge://schemas/claim-verification-result/v0.1` | A receipt bound to the same report/hash/audience with `public_export_eligibility=eligible` and release state `verified` or `verified_with_warnings`. |
| `public_export_spec` | `bridge://schemas/public-export-spec/v0.1` | Source report and receipt binding, target language, allowed claim types/evidence states, selected claims, public IDs and case labels, exact alias replacements, public accessions, prohibited literals and mandatory human-confirmation policy. |

All three object versions are `0.1.0`. File assets, arbitrary parameters,
MeasurementSpec envelope fields and nonzero seeds are refused.

## Projection rules

The implementation creates a new object from selected fields only. For every
selected source claim it emits:

- a caller-approved public claim ID and public case label;
- the P0-10-verified text after exact policy-supplied literal replacements;
- claim type, language, evidence state and comparison mode;
- numeric strings, source-field semantics and units without source Evidence IDs.

It never emits source report, claim, ProductCase, Evidence or value-binding IDs.
Unselected claims and their prose are not copied. Public accessions come only
from the export spec.

## Output

One `PublicSafeReport` is written as `public_safe_report.json` in an immutable,
content-addressed run directory. It binds source-report hash, receipt checksum,
export spec, all three input checksums and candidate hash. A clean P0-10 receipt
produces `ready_for_confirmation`; a receipt with warnings produces
`review_required`. Neither state means `exported`, and the tool never uploads.

The result has no MeasurementResult, visualization, source Evidence ID, score
or biological reinterpretation.

## Eligibility and refusal

Top-level failures publish nothing:

- missing, duplicate or unsupported role; Schema/version/checksum mismatch;
- receipt/report/hash/audience mismatch or ineligible P0-10 receipt;
- export-spec/report/receipt/language mismatch;
- missing selected claim, disallowed claim type or evidence state;
- configured alias source absent from the verified text;
- unusable output, immutable-run collision or input mutation;
- V1 request (`tool_request_v2_required`).

During reconstruction the candidate is also rejected if a caller-supplied
prohibited literal remains, or if the bounded backstop sees a local server/user
path, `file:` reference, internal BRIDGE object namespace or credential-like
assignment. This is a narrow deterministic backstop, not a general secret/PII
detector. The allowlist and disclosure policy remain the primary control.
Every refusal returns a stable, non-sensitive reason code and publishes no
candidate artifact.

## Minimal example

See `examples/requests/p0_11_public_safe_export.json`. Referenced objects must
exist and match their declared checksums before validation.

## Reproducibility and scope

Paths and caller-local input IDs do not affect the candidate identity. The tool
and environment version, Schema/version and raw input checksums do. Identical
content reuses identical result bytes.

This first callable slice deliberately excludes CSV, Markdown, archives,
figures, media metadata, SVG/HTML, scanners external to the package, PII
anonymization, confirmation receipts and publication upload. Those capabilities
must be separately specified and tested rather than hidden in this adapter.

P0-11 remains `candidate`. P0-10 correspondence is not biological truth, and a
public-safe candidate is not approval to publish.

## Detailed requirement

See `docs/bridge_spec_v0.1/public_safe_export_task_card.md` and
`docs/validation/p0_11_public_safe_export_20260824.md`.
