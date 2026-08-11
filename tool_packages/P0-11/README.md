# P0-11 Public-safe Export

## Purpose

Generate allowlisted public artifacts from an eligible verified report.

## Contract

| Field | Value |
|---|---|
| Package version | `0.1.0` |
| Runtime state | `scaffold` |
| Scientific state | `candidate` |
| Optional | `no` |
| EnvironmentSpec | `ENV-EVIDENCE-v0.1` |
| Input schema | `bridge://schemas/tool-request/v0.1` |
| Output schema | `bridge://schemas/tool-run/v0.1` |

**Input:** VerifiedReport with eligible export state, field allowlist, public aliases, registered visualizations, and export policy version.

**Output:** New PublicSafeReport candidate, regenerated public figures, file manifest, checksums, scan results, and confirmation-bound package hash.

**Runtime behavior:** Discoverable contract only; `run` returns `not_implemented` without scientific results.

## Refusal Conditions

Any non-allowlisted field, private path or identifier, unsafe embedded content, unregistered file, hash drift, or missing user confirmation.

Missing, unknown, unavailable, negative, and alert states remain distinct. No package may infer a clinical, safety, potency, GMP-release, or absolute product-ranking claim.

## Visualization Contract

Public-data payload only; figures are regenerated and checked for metadata, scripts, links, hidden text, and tooltip leakage.

Every formal chart must retain its data version, denominator, units, evidence references, and missing-state semantics.

## Validation Before Freeze

Leakage canaries, public accession preservation, CSV injection, MIME mismatch, archive traversal, media metadata, and deterministic packaging.

Method documentation and accessible sources do not constitute benchmark completion. The registered method IDs are returned by `bridge-tool describe P0-11`.

## Detailed Scientific Requirement

Repository document: `docs/bridge_spec_v0.1/public_safe_export_task_card.md`.
