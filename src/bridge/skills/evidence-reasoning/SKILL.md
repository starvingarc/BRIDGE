---
name: evidence-reasoning
description: Use when interpreting supporting, opposing, missing or conflicting research evidence, forming competing explanations, choosing a discriminating next check, or deciding whether an approved assessment can continue. 证据冲突、竞争假设和下一步验证；不用于把缺失测量解释为阴性结果。
---

# Evidence reasoning

## Scope and inputs

Explain the current observations before proposing a mechanism. Read the current
evidence/citation choices, approved options, interpretation gaps and resource limits.
A hypothesis, its predicted observation and evidence already measured are distinct.
The server's schema and citation-role rules own the actual output structure.

## Decisions

1. Fix the question and analysis unit. Check whether apparently conflicting results
   use the same input/view, denominator, definition, timepoint and applicable reference.
   Different estimands need not be contradictions; a successful method is not proof
   of the inferred mechanism or a qualified annotation.
2. Separate supported observations from assumptions and gaps. Preserve unavailable
   versus negative, and same-family dependence versus independent corroboration.
3. When observations justify explanation, keep a small set of plausible rivals:
   biological state, measurement/preprocessing artifact, reference mismatch or
   confounding, as relevant. Do not force extra hypotheses to fill a quota.
4. For each supported candidate, identify the observation, competing explanation and
   a next measurement whose outcomes could distinguish them. State the expected
   pattern, refutation condition and indeterminate outcome when the current evidence
   supports doing so; these are predictions, not new observed results.
5. Within `assessment` scope, choose only supplied `check`/`query` IDs, or produce
   structured `explain` hypotheses with current citation aliases in their proper
   support/opposition/missing arrays. A discriminating check must be a supplied
   eligible biological check; graph/report operations are not biological experiments.
   Evidence-gap items keep support empty and describe only what this run cannot assess.
6. Outside assessment scope, provide a concise `reply` using supplied observation
   choices when available. Explain the next useful check without executing it or
   inventing an authorized option. Tool results supply all numbers and states.

## Handoff, stopping and output

Return the strongest bounded explanation, material uncertainty and at most three
useful next actions. If no grounded explanation is possible, ask the consequential
question or stop with the known/unknown/gap and its effect on the conclusion.
Stop according to evidence requirements, eligibility or resource limits, never model
confidence. A cited explanation can finish a phase with unresolved rivals; it is not
a verified report. Report continuation uses the existing current-version handoff.

Contracts: [sufficiency](../../tool_packages/cards/P0-08.md),
[evidence graph](../../tool_packages/cards/P0-09.md).
Adapted workflow and license attribution: [sources](../SOURCES.md).
