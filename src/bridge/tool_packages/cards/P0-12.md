# P0-12 Optional Graft Assessment

## Purpose

Produce a deterministic, independent summary of optional post-transplant
evidence without embedding biological channels, species choices, time windows,
thresholds or product decisions in executable code.

## Package contract

| Field | Value |
|---|---|
| Package version | `0.2.0` |
| Runtime state | `implemented` |
| Scientific state | `candidate` |
| EnvironmentSpec | `ENV-P0-CORE-v0.1` (`health_check_passed`) |
| Input envelope | `bridge://schemas/tool-request/v0.2` |
| Output envelope | `bridge://schemas/tool-run/v0.2` |
| Result schema | `bridge://schemas/graft-assessment/v0.1` |
| Adapter | `bridge.tool_packages.p0_12_graft_assessment.adapter:adapter` |

The CLI entry points are:

```bash
bridge-tool describe P0-12
bridge-tool validate --request request.json
bridge-tool run --request request.json
```

The Python SDK accepts the same `ToolRequestV2` through
`ToolRegistry.load_default().check_eligibility(request)` and `.run(request)`.

## Structured inputs

Inputs are immutable local JSON files with an absolute path, exact role,
registered Schema URI, object version, media type and SHA-256 checksum. Five
roles are always required; the graft-lineage role is conditional. Module object
version is `0.1.0`; the graft MeasurementSpec declares its own version.

| Role | Schema | Required content |
|---|---|---|
| `product_case` | `bridge://schemas/product-case/v0.1` | Exact case, product MeasurementSpec and independence-group references. |
| `biological_unit_manifest` | `bridge://schemas/biological-unit-manifest/v0.1` | Exact ProductCase-bound product analysis-unit/preparation assignments, manifest checksum and independence scope. |
| `graft_measurement_spec` | `bridge://schemas/measurement-spec/v0.1` | Independent graft assay, analysis-unit kind, applicable context and version. |
| `graft_lineage_manifest` | `bridge://schemas/graft-lineage-manifest/v0.1` | At most one; required for `provided`, forbidden for `not_provided`; exact unit/animal/graft/timepoint/preparation assignments and external review state. |
| `graft_assessment_spec` | `bridge://schemas/graft-assessment-spec/v0.1` | ProductCase, product/graft MeasurementSpecs, assay, sampling, reference and algorithm bindings; channel IDs, units, animal estimand, within-animal aggregation, denominator semantics, disjoint strata, minimum animals and optional intervals. |
| `graft_evidence_bundle` | `bridge://schemas/graft-evidence-bundle/v0.1` | Explicit `provided` or `not_provided` state; matching context when provided; observation units, design constraints and exact lineage-manifest reference. |

A `not_provided` bundle must contain no graft context, units, constraints or
observations, and the request must omit the lineage manifest. A provided bundle
requires one exact lineage manifest but may contain no usable observations;
that is a valid `not_assessed` scientific result rather than a technical failure.

Every observation declares its own ID, configured channel, unit, finite numeric
value or explicit unavailable state, optional denominator and Evidence
references. Missing, unknown and unavailable observations require null value and
denominator. A preparation link exists only when both a versioned preparation
reference and non-empty linkage Evidence are supplied, and that preparation
must occur in the product BiologicalUnitManifest's `unit_bindings`. Bundle and graft-lineage manifest
assignments must be identical. A `declared` manifest is traceable but cannot
support assessment. A checksummed caller-supplied `reviewed`/`frozen` gate is
also trace-only in this version because no trusted receipt verifier is
configured; P0-12 cannot assert or authenticate that state for itself.

Expression assets, the request-envelope MeasurementSpec field, arbitrary
parameters and nonzero random seeds are refused. P0-12 v0.2 does not accept
inline scientific payloads.

## Deterministic evaluation

For every channel and configured stratum, the executor:

1. matches observations only by the caller-supplied channel ID;
2. accepts observations only from exact graft/timepoint stratum members, with
   the exact unit and an allowlisted evidence state;
3. applies `single_observation`, `mean` or `pooled_numerator_denominator`
   within each animal and stratum only after trusted lineage review, then
   counts animals as independent units;
4. reports each animal aggregate and the equal-animal mean, minimum and maximum,
   with cross-stratum aggregation forbidden;
5. compares the mean with input bounds only when the rule selects
   `configured_interval`;
6. reports unmatched channels, missing observations and insufficient independent animals
   with stable reason codes.

`descriptive_only` rules have no bounds or directional interpretation.
When eligible animals are below the configured minimum, descriptive values
remain visible but the configured interval relation is `unavailable`.
Changing a channel, unit, evidence-state allowlist, minimum or interval requires
a new checksummed spec, not a code change.

The standard adapter currently has no trusted graft-review verifier and no
typed GraftCase assay/specimen binding. It therefore keeps eligible animal
counts at zero, channel summaries `not_assessed`, and reports
`graft_review_authority_not_configured` for caller-reviewed/frozen lineage (or
`graft_lineage_not_reviewed` for declared lineage), plus
`graft_assay_applicability_not_assessed`. Scientific-mechanics tests inject a
test-only verifier result; ordinary input JSON cannot enable it.

## Output

One `GraftAssessment` is written as `graft_assessment.json` in an immutable,
content-addressed run directory. It contains:

- spec, evidence-bundle, ProductCase and available graft-context references;
- checksums for all five always-required inputs and the graft-lineage manifest when supplied;
- `complete`, `partial`, `not_assessed` or `not_provided`;
- graft availability, explicit-only linkage state and descriptive analysis mode;
- observation-unit and independent-animal counts plus declared design constraints;
- configured per-channel-and-stratum members and denominator semantics,
  animal count, per-animal aggregates, equal-animal mean/range, interval
  relation, Evidence and reason codes;
- explicit preparation-linkage records and unmatched observations;
- `product_backfill=not_performed`, `graft_score=null`,
  `domain_score=null` and `score_state=shadow|unavailable`.

The run emits no `MeasurementResult`, visualization, expression-derived
artifact, ranking or second association artifact.

## Eligibility, refusal and degradation

Top-level failures publish nothing:

- missing, duplicate or unsupported role;
- Schema, object-version, checksum or media-type mismatch;
- ProductCase, product BiologicalUnitManifest, product/graft MeasurementSpec,
  graft-lineage manifest, preparation or provided-context mismatch;
- incomplete provided context or evidence in a `not_provided` bundle;
- duplicate units, duplicate channels within a unit or implicit preparation
  linkage;
- non-finite/coerced numeric values or missing states carrying numeric values;
- expression assets, free parameters, envelope MeasurementSpec or nonzero seed;
- unusable output, input mutation or immutable-run collision;
- a V1 request, returned as typed `tool_request_v2_required`.

Contract-valid limitations stay visible in the result. Unverified lineage,
including a caller-asserted reviewed/frozen label, produces
`partial/not_assessed` instead of pretending the assignments were reviewed. No eligible channel
returns `not_assessed`; incomplete required coverage or an unmatched channel
returns `partial`; linkage state is explicitly `not_declared`,
`partially_declared` or `declared_with_evidence`, and every declared linkage is
marked `preparation_linkage_declared_not_verified`. A supplied design constraint
is reported and the current implementation remains descriptive. Reason codes
never turn missing evidence into zero or a product failure.

## Minimal example

See `examples/requests/p0_12_graft_assessment.json`. Replace placeholder paths
and checksums with six exact immutable JSON objects for a provided graft.

## Reproducibility and scientific boundary

Input paths and caller-local input IDs do not affect run identity. Tool and
environment version, role, Schema, object version, media type and raw input
checksums do. Identical content reuses identical result bytes.

The registered methods cover GraftCase contract validation and configured
summary of already prepared observations. They do not claim that upstream
matrix QC, species assignment, reference mapping, cell-state analysis,
composition estimation, maturation analysis or inference ran inside P0-12.

Synthetic tests establish callable contract and packaging behavior only. Real
channel definitions, references, thresholds and graft evidence require
independent biological review. P0-12 remains `candidate`; graft evidence is
independent post-treatment evidence and cannot establish efficacy, safety,
potency, release, a score or a pre-transplant product conclusion.

## Detailed requirement

See `docs/bridge_spec_v0.1/graft_assessment_task_card.md` and
`docs/validation/p0_12_graft_assessment_20260824.md`.
