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

Both inputs are immutable local JSON files with an absolute path, exact role,
registered Schema URI, object version, media type and SHA-256 checksum. The
current object version is `0.1.0`.

| Role | Schema | Required content |
|---|---|---|
| `graft_assessment_spec` | `bridge://schemas/graft-assessment-spec/v0.1` | ProductCase, MeasurementSpec, assay, sampling, reference and algorithm bindings; channel IDs and publication-safe units; required flags; eligible evidence states; minimum independent-unit counts; optional configured intervals; explicit missing, confounding, linkage and score policies. |
| `graft_evidence_bundle` | `bridge://schemas/graft-evidence-bundle/v0.1` | Explicit `provided` or `not_provided` state; matching context when provided; independent unit, animal, graft and timepoint references; precomputed observations; declared design constraints; optional preparation references supported by linkage Evidence. |

A `not_provided` bundle must contain no graft context, units, constraints or
observations. A provided bundle may contain no usable observations; that is a
valid `not_assessed` scientific result rather than a technical failure.

Every observation declares its own ID, configured channel, unit, finite numeric
value or explicit unavailable state, optional denominator and Evidence
references. Missing, unknown and unavailable observations require null value and
denominator. A preparation link exists only when both a versioned preparation
reference and non-empty linkage Evidence are supplied.

Expression assets, the request-envelope MeasurementSpec field, arbitrary
parameters and nonzero random seeds are refused. P0-12 v0.2 does not accept
inline scientific payloads.

## Deterministic evaluation

For every rule, the executor:

1. matches observations only by the caller-supplied channel ID;
2. includes only exact-unit observations whose evidence state is allowlisted;
3. counts explicit independent graft units, never cells or profiles;
4. reports mean, minimum and maximum of eligible precomputed values;
5. compares the mean with input bounds only when the rule selects
   `configured_interval`;
6. reports unmatched channels, missing units and insufficient independent units
   with stable reason codes.

`descriptive_only` rules have no bounds or directional interpretation.
Changing a channel, unit, evidence-state allowlist, minimum or interval requires
a new checksummed spec, not a code change.

## Output

One `GraftAssessment` is written as `graft_assessment.json` in an immutable,
content-addressed run directory. It contains:

- spec, evidence-bundle, ProductCase and available graft-context references;
- both input checksums;
- `complete`, `partial`, `not_assessed` or `not_provided`;
- graft availability, explicit-only linkage state and descriptive analysis mode;
- independent-unit count and declared design-constraint references;
- configured per-channel count, mean, range, interval relation, Evidence and
  reason codes;
- explicit preparation-linkage records and unmatched observations;
- `product_backfill=not_performed`, `graft_score=null`,
  `domain_score=null` and `score_state=shadow|unavailable`.

The run emits no `MeasurementResult`, visualization, expression-derived
artifact, ranking or second association artifact.

## Eligibility, refusal and degradation

Top-level failures publish nothing:

- missing, duplicate or unsupported role;
- Schema, object-version, checksum or media-type mismatch;
- ProductCase or provided context mismatch across the two inputs;
- incomplete provided context or evidence in a `not_provided` bundle;
- duplicate units, duplicate channels within a unit or implicit preparation
  linkage;
- non-finite/coerced numeric values or missing states carrying numeric values;
- expression assets, free parameters, envelope MeasurementSpec or nonzero seed;
- unusable output, input mutation or immutable-run collision;
- a V1 request, returned as typed `tool_request_v2_required`.

Contract-valid limitations stay visible in the result. No eligible channel
returns `not_assessed`; incomplete required coverage or an unmatched channel
returns `partial`; absent or partial preparation linkage remains
`provided_unlinked`. A supplied design constraint is reported and the current
implementation remains descriptive. Reason codes never turn missing evidence
into zero or a product failure.

## Minimal example

See `examples/requests/p0_12_graft_assessment.json`. Replace placeholder paths
and checksums with two real immutable JSON objects before validation.

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
