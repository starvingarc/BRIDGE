# P0-07 Product Comparison & Stability v0.2 validation

- Branch: `p0-07-product-comparison-stability-v1`
- Implementation base: `720639a223d0905315bb6550dce3c4200382725a`
- Final integration base: `07b8fd0b664c8061769ea13d943653d3f673d141`
- Runtime: Ubuntu server, Python 3.12, `ENV-P0-CORE-v0.1`
- Scientific state: `candidate`; registered methods remain formally ineligible
- Score boundary: all product/domain/overall scores and ranks remain null

## Implemented scope

The first executable package consumes one checksummed comparison spec, one
checksummed case manifest and 2–20 checksummed ProductEvidenceBundle objects. It
validates cross-object bindings, applies external comparability/confounding
policies, and emits descriptive group means, ranges, deltas and stability states.
It does not rerun scientific domains or infer biological desirability.

## Server verification

The exact staged source was validated in an isolated private server worktree:

- focused P0-07 suite: **15 passed**;
- complete repository suite: **1,077 passed**, with eight pre-existing
  dependency warnings;
- registry, packaged Schema, active-method and example-version checks:
  **9 passed**;
- tool discovery: exactly **12** packages, with P0-07 marked implemented;
- generated public Schemas: **4** P0-07 contracts registered and packaged;
- repository policy and staged `git diff --check`: passed;
- tracked repository files after final staging: **327**, within the dynamic policy
  budget.

The focused suite exercises deterministic path/order-independent runs,
checksum refusal, V1 refusal, missing-not-zero semantics, contract/binding
mismatches, contextual and OOD comparisons, complete confounding, missing
confounder metadata, and replicated descriptive stability.

After synchronizing the implementation with the final integration base, the
P0-07 focused, registry and knowledge suites passed together (**36 passed**).
The version-aware Schema exporter resolved both v0.1 and v0.2 names, the four
P0-07 Schema bytes matched two independent in-memory generations, and Tool Card
generation was byte-idempotent across two rounds. Repository policy and both
working/staged diff checks passed. The complete suite above was not repeated for
this merge-only synchronization.

## Retained boundaries

Missing is not zero. Inferential statistics, winner/equivalence/Pareto claims,
safety, efficacy and release conclusions are unavailable. P0-08 insufficiency
keeps raw evidence shadow and prevents a complete profile.
