# P0-11 Internal Review Projection — scientific and engineering task card

## 1. Biological question

Can a human reviewer receive a small, traceable view of claims that P0-10 has
checked against its declared evidence package without exposing the full
internal report graph or silently converting contract correspondence into
biological truth or publication permission?

P0-11 does not answer whether a cell product is effective, safe, mature,
stable or releasable. It only checks and reconstructs an internal review view.

## 2. Scope decision

The callable v0.3 surface is intentionally named **Internal Review
Projection**. “Public-safe Export” is not an accurate description because the
repository has no authenticated producer identity, configured release
authority, complete disclosure policy, PII/secret assurance, confirmation
receipt or publication transport. A successful run must therefore stop at:

- `producer_authentication_state=not_available`;
- `release_authority_state=not_configured`;
- `distribution_state=internal_review_only`;
- `projection_state=review_required`.

This is a fail-closed product boundary, not a placeholder wording change.

## 3. Inputs and ownership

| Role | Cardinality | Owner | Contract |
|---|---:|---|---|
| `report_draft` | exactly 1 | report assembler | `ReportDraft` v0.1; audience must be `public_candidate` |
| `claim_verification_result` | exactly 1 | P0-10 | `ClaimVerificationResult` v0.1, verified or verified with warnings |
| `claim_verifier_run` | exactly 1 | P0-10 runtime | Exact `ToolRunV2` whose one verification artifact matches the result checksum |
| `review_projection_spec` | exactly 1 | human review workflow | `ReviewProjectionSpec` v0.1 with selections, allowlists, labels, accessions, prohibited literals and mandatory review policy |

All objects are immutable, checksummed local JSON. Inline payloads, expression
assets and arbitrary request parameters are out of scope. The review workflow
owns selections and labels; P0-11 does not infer disclosure policy from claim
text or IDs.

## 4. Required cross-bindings

Before projection, the adapter must prove:

1. ReportDraft, ClaimVerificationResult and ReviewProjectionSpec refer to the
   same report and exact report content hash.
2. Verification audience and ReportDraft audience are identical.
3. The result is `verified` or `verified_with_warnings`, while package release
   authority remains `not_configured` and public-export eligibility remains
   `ineligible`.
4. `claim_verifier_run.request.tool_id` is P0-10; its structured result equals
   the supplied verification result; it has exactly one verification artifact;
   and that artifact checksum equals the structured-input checksum.
5. Every selected source claim exists and satisfies the configured claim-type
   and evidence-state allowlists.

These checks bind bytes and package ownership. The current ToolRun has no
cryptographic actor authentication, so the output must disclose that producer
provenance remains unverified.

## 5. Deterministic projection

P0-11 builds a new allowlisted object rather than deleting fields from the
source report. For each selected claim it keeps only a review ID/label, exact
verified claim text, language, claim type, evidence state, comparison mode and
canonical numeric bindings with units. It may carry explicitly supplied public
accessions.

It must not project source Report, Claim, ProductCase, Evidence, preparation or
value-binding identifiers. It must not rewrite verified prose, synthesize a
claim, repair evidence, rerun P0-10 or decide whether a warning is acceptable.
Configured prohibited literals and a recursive bounded machine-reference guard
run over the reconstructed object before publication. The guard detects known
internal namespaces, local/server paths and credential-like assignments; it is
not advertised as comprehensive privacy or secret detection.

## 6. Output interface

Result Schema:
`bridge://schemas/contract-validated-review-projection/v0.1`.

Artifact: `contract_validated_review_projection.json`.

The output contains source hashes and checksums, ReviewProjectionSpec reference,
language, accessions, projected claims, deterministic check receipts, explicit
unavailable authority/authentication states and a semantic projection hash.
Every valid output remains `review_required`; its ToolRun is `partial` to make
the unresolved release boundary machine-visible.

The required baseline reason codes are:

- `producer_provenance_unverified`;
- `public_release_authority_not_configured`.

`p0_10_verified_with_warnings` is added when applicable.

## 7. Failure and missing semantics

- Bad envelope, role, Schema, version, checksum or cross-binding: failed
  ToolRun, no result artifact.
- P0-10 blocked/unverified result: failed ToolRun, no review projection.
- Missing or disallowed selected claim: failed ToolRun, no silent omission.
- Prohibited literal or machine reference in the rebuilt object: failed
  ToolRun, no partial leak.
- Valid projection without authority: contract-valid `review_required`, never
  `ready`, `released`, `published` or `exported`.

“Not configured” is not equivalent to a failed privacy scan, and “verified” in
P0-10 is not equivalent to biological validation.

## 8. Validation matrix

Tests must cover:

- source and installed-wheel CLI/SDK describe, validate and run;
- exact report/result/ToolRun/artifact checksum binding;
- verified and verified-with-warnings paths;
- blocked, wrong-audience, wrong-tool, stale-run, duplicate-artifact and
  replaced-file refusals;
- disallowed claim type/evidence state and missing selection;
- numeric identifier and large finite number preservation without coercion;
- recursive prohibited-literal, local path, server path and credential-like
  marker rejection;
- deterministic identity, immutable publication and repeated-run reuse;
- V1 typed refusal and no publication/upload side effect.

## 9. Acceptance boundary

Engineering acceptance means the callable package, public Schema, packaged
Schema, Tool Card, example and tests agree and reproduce from a clean wheel.
Scientific/release acceptance is explicitly absent. P0-11 remains a
`candidate`, produces no score and grants no public-release permission.

Evidence record:
`docs/validation/p0_11_internal_review_projection_20260824.md`.
