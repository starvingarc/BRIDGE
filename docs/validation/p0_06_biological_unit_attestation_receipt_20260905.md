# P0-06 biological-unit attestation receipt validation

Date: 2026-09-05

## Scope

P0-06 v0.6.1 keeps `legacy_aggregation` unchanged and requires one
`BiologicalUnitAttestationReceipt v0.1` for `method_runtime`. The shared receipt
records a caller/data-owner assertion for `analysis_execution` and binds the
immutable P0-01 `declared` manifest to its assignment, the P0-02 selected
DataView, observation digest, biological-unit contract and external attestation
trace.

Runtime validates receipt structure and these content bindings. It does not
authenticate the attestor or establish biological truth, independent review,
publication permission or product-release authority. Deployment is responsible
for mapping an authenticated conversation or workflow record to the receipt's
attestation reference and checksum.

## Engineering checks

| Check | Result |
|---|---|
| P0-06 focused suites and registry | 72 passed |
| Receipt refusal | Missing, not-confirmed and assignment-mismatched receipts rejected before execution |
| Immutable lineage | Valid method execution retained the exact declared manifest bytes |
| Provenance | Receipt role and checksum recorded in the artifact manifest and profile source bindings |
| Schema generation | Public profile v0.3 Schema generated twice without drift; source-binding limit widened only from 10 to 11 |
| Repository policy and diff hygiene | Passed |
| Clean-wheel smoke | Installed package reported P0-06 v0.6.1 and a 12-role method-runtime contract with exactly one receipt |
| Scientific output boundary | Method algorithms, result fields, measurements, `domain_score=null` and `score_state=unavailable` unchanged |

The checks use synthetic contract fixtures only. The fixture attestation hash is
not an authenticated record. No private data or deployment resource is included.
