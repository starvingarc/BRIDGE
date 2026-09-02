# P0-04 Measurement Projection

## Biological goal

Expose the already-computed developmental role fractions as traceable
measurements without adding a developmental-age interpretation, preferred
window, threshold, score or release decision.

## Scope

- Preserve `DevelopmentalCompatibilityResult` object version `0.2.0`.
- Add a module-owned `0.3.0` result model that binds independent,
  checksummed `MeasurementResultV2` JSON artifacts.
- Project only the existing whole-product, target-related and declared
  timepoint `RoleFraction` values.
- Keep `domain_score=null` and `score_state=unavailable` in both the result and
  every projected measurement.
- Preserve missing, unknown and unavailable states as null measurement values;
  a zero denominator is unavailable, not a numeric zero.

## Non-goals

- No new threshold, developmental judgement, age conversion, score,
  calibration, reference method or time-course inference.
- No change to input contracts, shared toolkit contracts, package specs,
  schema registries, generated schemas, central documentation or repository
  policy in this worktree.

## Frozen projection contract

- One static measurement per denominator kind and developmental role.
- One optional timepoint measurement per declared timepoint, denominator kind
  and developmental role already present in the result.
- Numeric measurements copy fraction, numerator and positive denominator
  exactly and carry no interval.
- Missing or unavailable measurements carry null raw value, numerator,
  denominator and interval, plus a module-owned typed reason binding.
- Artifact IDs, file names, bytes and SHA-256 values are deterministic for the
  immutable input set.

## Validation

- Focused P0-04 tests.
- Draft 2020-12 model-schema checks for both result versions.
- Deterministic reuse and changed-artifact refusal tests.
- Artifact checksum verification and `git diff --check`.

## Validation record

- Module-local focused suite: `23 passed`.
- Expression-mode pseudobulk smoke: v0.3 result and ten measurement artifacts
  published with unavailable scores.
- `git diff --check`: passed.
- The default registry still declares the shared v0.2 result schema and
  therefore rejects a v0.3 adapter result until integration. This is the
  expected and only known contract-registration gap in this branch.

## Integration boundary

The shared P0-04 package spec, schema registry/export and generated JSON Schema
must be updated by the single integration owner after this module branch is
reviewed. They are intentionally not modified here.
