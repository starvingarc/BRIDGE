# P0-01 Optional Mitochondrial QC

## Goal

Keep mitochondrial measurements unavailable when no mitochondrial symbols are
recognized, while still evaluating independent count-depth and detected-gene
candidate rules.

## Scope

- Skip only `max_mitochondrial_fraction` when mitochondrial coverage is zero.
- Emit explicit gene-set-unavailable and candidate-rule-skipped warnings.
- Preserve `null` mitochondrial measurements; never impute zero.
- Add focused regression coverage and synchronize the P0-01 task card.

## Non-goals

- No threshold, score, schema, data, or visualization-contract changes.
- No claim that candidate eligibility is a validated product-quality decision.

## Validation

- Focused P0-01 regression tests.
- Full repository engineering gates before review readiness.
- Secret and generated-artifact scan over the proposed diff.

## Validation results

- Focused P0-01 regression: 2 passed.
- Full test suite: 1,458 passed with 20 existing dependency warnings.
- Tool registry listing, knowledge validation, repository policy, and
  `git diff --check`: passed.
- Proposed files contain no raw data, generated run artifacts, local absolute
  paths, credentials, tokens, or private-key material.

## Decision

Missing mitochondrial coverage invalidates only the mitochondrial candidate
rule. Independent candidate rules remain computable and retain their existing
candidate-only interpretation.
