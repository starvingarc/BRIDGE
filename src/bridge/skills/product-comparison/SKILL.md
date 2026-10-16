---
name: product-comparison
description: Use when comparing cell products, preparations, protocol versions or their stability, selecting product comparators, or interpreting comparability and confounding. 产品批次或方案比较；同一细胞群内的基因差异表达属于 expression-exploration。
---

# Product comparison

## Scope and inputs

Compare product-level evidence under an explicit comparability contract. Read the
declared query/comparator preparations, analysis versions, upstream metric bundles,
measurement definitions, units, denominators, timepoints and independence bindings.
Within-population gene expression contrasts use the registered expression workflow;
P0-07 structured comparison consumes product evidence, not arbitrary H5AD files.

## Decisions

1. Define the contrast and analysis unit before discussing a statistic. Distinguish
   independent preparations, repeated/paired measurements and technical captures.
   Multiple files or cells never establish independent biological replication. One
   sequencing capture can contain multiple declared independent preparations; do not
   infer a single biological replicate or absent estimability from sequencing count.
   If preparation identity is absent, ask for it and keep independence unknown.
   Do not later rephrase one capture as one observation or one biological sample.
   Separate wells/aliquots also do not prove independent preparation or allocation.
   Only a supplied design can establish insufficient or adequate replication; if
   absent, stop the replication judgment here. Give only a short reply (at most
   120 words) with the known technical facts, the unresolved preparation/allocation
   relationships, and what must be confirmed for comparison. Do not continue to
   infer a biological observation count, inability to estimate variance or a
   minimum repeat count. The tool remains descriptive regardless of that gap.
2. Classify supplied objects as usable comparators, contextual/background references
   or excluded objects, with their actual eligibility reasons. Publication alone is
   not registration, comparability or permission. Comparator scope needs confirmation.
3. Check that input/view, metric, MeasurementSpec, unit, denominator, timepoint and
   preprocessing/reference context match the intended contrast. Surface confounding
   between protocol, batch, donor and time. Changing alignment requires a separately
   approved recomputation; preserve existing versions.
4. For an eligible requested comparison, use the registered P0-07 plan, or the exact
   supplied check ID in an approved assessment. The server owns inputs and eligibility.
   Missing required bundles/contracts produce a gap explanation, not reconstructed
   objects or an ad-hoc statistical script.
5. Interpret each returned effect, distance, correlation or dispersion on its own
   scale and with its stated unit. An observed range is not a confidence interval.
   Current structured comparison is descriptive; do not add p-values, equivalence,
   superiority or causal protocol effects that the tool did not compute or establish.

## Stopping and output

Give the comparison's applicability, supported differences, confounding/uncertainty
and next useful check. A reference may provide context without supporting a numeric
contrast. One preparation remains descriptive. If independence or a denominator is
unknown, preserve the tool's not-assessed/not-estimable state and identify what would
change it. Effect direction and similarity have no intrinsic better/worse meaning;
keep `overall_rank`, `overall_score` and unqualified domain scores unavailable.

Contract: [comparison and stability](../../tool_packages/cards/P0-07.md).
Adapted workflow and license attribution: [sources](../SOURCES.md).
