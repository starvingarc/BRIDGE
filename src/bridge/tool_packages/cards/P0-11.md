# P0-11 Internal Review Projection

## Purpose

Create a minimal, contract-validated JSON projection for **internal human
review** from an exact P0-10 report, verification result and producer run. The
module preserves verified claim text and selected numeric bindings, removes
internal identifiers by reconstruction, and stops at a deliberate release
boundary. It is not a public exporter.

## Package contract

| Field | Value |
|---|---|
| Package version | `0.3.0` |
| Runtime state | `implemented` |
| Scientific state | `candidate` |
| EnvironmentSpec | `ENV-EVIDENCE-v0.1` (`health_check_passed`) |
| Input envelope | `bridge://schemas/tool-request/v0.2` |
| Output envelope | `bridge://schemas/tool-run/v0.2` |
| Result schema | `bridge://schemas/contract-validated-review-projection/v0.1` |
| Adapter | `bridge.tool_packages.p0_11_public_export.adapter:adapter` |

```bash
bridge-tool describe P0-11
bridge-tool validate --request request.json
bridge-tool run --request request.json
```

The Python SDK accepts the same `ToolRequestV2` through
`ToolRegistry.load_default().check_eligibility(request)` and `.run(request)`.
The source package keeps its historical Python import path for compatibility;
the callable contract and artifact are named Internal Review Projection.

## Structured inputs

P0-11 accepts exactly four immutable local JSON objects. Every
`StructuredInputRef` requires a unique request-local ID, exact role and Schema,
declared object version, absolute regular-file path, `application/json` media
type and lowercase SHA-256 checksum.

| Role | Cardinality | Schema | Required content |
|---|---:|---|---|
| `report_draft` | 1 | `bridge://schemas/report-draft/v0.1` | Original P0-10 input report with `audience=public_candidate` |
| `claim_verification_result` | 1 | `bridge://schemas/claim-verification-result/v0.1` | Result bound to the same report/hash/audience and in `verified` or `verified_with_warnings` state |
| `claim_verifier_run` | 1 | `bridge://schemas/tool-run/v0.2` | Exact P0-10 `ToolRunV2` that produced the checksummed verification artifact |
| `review_projection_spec` | 1 | `bridge://schemas/review-projection-spec/v0.1` | Report/verification binding, language, allowlists, selections, review IDs, accessions, prohibited literals and mandatory review policy |

The three module objects use object version `0.1.0`; the verifier run declares
its own ToolRun version. Expression assets, request-level MeasurementSpec,
arbitrary parameters, unsupported roles and nonzero random seeds are refused.

## Exact producer and report binding

Eligibility requires all of the following:

1. the verification result matches the report reference, content hash,
   audience and every selected claim;
2. the supplied ToolRun is a P0-10 v0.2 run whose `result` equals the supplied
   verification result;
3. exactly one ToolRun artifact is a `claim_verification_result` and its SHA-256
   equals the `claim_verification_result` input checksum;
4. report, verification and projection spec agree on report hash,
   verification ID and language;
5. package-owned P0-10 release authority remains `not_configured` and public
   export eligibility remains `ineligible`.

These checks prove internal object correspondence. They do not authenticate
who operated P0-10, establish biological truth, or supply release authority.

## Projection mechanics

For every selected claim, P0-11 reconstructs a new object containing only:

- caller-declared review claim ID and review case label;
- the exact verified plain-paragraph claim text;
- claim type, language, evidence state and comparison mode;
- canonical numeric strings, source-field semantics and plain units;
- explicitly supplied public accession identifiers.

It never rewrites claim text and never copies the report wholesale. Report,
Claim, ProductCase, Evidence and value-binding source IDs are not projected.
Unselected claims are absent. Configured prohibited literals and a bounded
machine-reference guard are evaluated recursively over the reconstructed
payload. This guard is deterministic defense in depth, not a general secret or
PII detector.

## Output

One `ContractValidatedReviewProjection` is written as
`contract_validated_review_projection.json` in an immutable,
content-addressed run directory. It includes:

- source report hash, verification checksum and all four input checksums;
- projection-spec reference, language and sorted accessions;
- sorted projected claims and numeric bindings;
- the three deterministic projection checks;
- `producer_authentication_state=not_available`;
- `release_authority_state=not_configured`;
- `distribution_state=internal_review_only`;
- `projection_state=review_required`;
- a semantic `projection_hash`.

A valid run therefore has `execution_state=partial` and always includes
`producer_provenance_unverified` plus
`public_release_authority_not_configured`. A P0-10 warning remains separately
visible. P0-11 never emits `ready`, `released`, `published` or `exported`, and
never uploads an artifact.

## Refusal and degradation

Top-level contract failures publish no result artifact. Stable failures cover
missing/duplicate roles, Schema/version/checksum mismatch, V1 requests,
P0-10/report/artifact mismatch, non-verified verification state, authority
state inconsistency, spec/report mismatch, unavailable or disallowed selected
claims, mutable input, unsafe output and immutable-run collision. A prohibited
literal or machine-local reference also blocks publication of the projection.
All refusals return stable reason codes without echoing rejected private
content.

There is no automatic degradation from an invalid producer binding to an
unverified projection. The only successful state is a contract-valid object
that explicitly requires internal review.

## Minimal example and reproducibility

See `examples/requests/p0_11_internal_review_projection.json`. Replace all
placeholder absolute paths and checksums with four exact immutable objects.
Paths and request-local input IDs do not define the scientific payload;
tool/environment versions, Schema/object versions and raw input checksums do.
Identical inputs reuse identical result bytes.

This first callable slice deliberately excludes public distribution,
authentication, confirmation receipts, redaction of arbitrary free text,
PII/secret scanning, Markdown/CSV/archive generation, figures, media, upload
and release decisions. Those capabilities require a separately configured and
reviewed authority boundary.

P0-11 remains `candidate`. Contract validation is not biological validation,
and an internal review projection is not permission to publish.

## Detailed requirement

See `docs/bridge_spec_v0.1/internal_review_projection_task_card.md` and
`docs/validation/p0_11_internal_review_projection_20260824.md`.
