# P0-05 Biological-unit attestation receipt validation

Date: 2026-09-05

## Scope

P0-05 method execution consumes the immutable P0-01 `declared`
BiologicalUnitManifest together with a separate
`BiologicalUnitAttestationReceipt v0.1`. The receipt records an explicit
caller/data-owner assertion for `analysis_execution` and binds:

- the exact manifest and assignment checksums;
- the selected DataView, selected artifact and observation-set digest;
- the analysis unit, independence group and independence scope;
- four explicit design confirmations;
- the attestor, timezone-aware attested time and an external attestation
  reference/checksum.

Runtime validates only the receipt structure and these content bindings. It does
not authenticate the attestor or verify the truth or origin of the external
attestation record. Deployment is responsible for mapping an authenticated
conversation or workflow record to `attestation_ref` and
`attestation_sha256`.

A legacy `reviewed` or `frozen` manifest cannot replace the receipt. The
receipt does not establish biological truth, independent review, publication
permission, clinical validity, GMP release, safety, efficacy, potency or
product-release authority.

## Engineering checks

| Check | Result |
|---|---|
| P0-05 aggregation and method suites | 70 passed |
| Registry and shared contract-spine suites | 52 passed |
| Receipt refusal matrix | Absence, incomplete trace, not-confirmed decision, incomplete design confirmations, binding drift, file replacement and legacy-manifest bypass rejected |
| Schema generation | Draft 2020-12 public schema generated twice without drift |
| Repository policy and diff hygiene | Passed |
| Clean-wheel smoke | Installed package reported P0-05 v0.5.2, both input modes and the packaged receipt Schema |
| Scientific output boundary | Existing methods, measurements, `domain_score=null` and `score_state=unavailable` unchanged |

The tests use synthetic contract objects only. The fixed attestation hash is a
fixture value, not an authenticated record. No private data or deployment
resource is included.
