# Product And Scientific Principles

## Purpose

BRIDGE is an evidence-grounded scientific Agent for cell-therapy product
evaluation. It is intended to work with researchers to define a case, plan and
orchestrate analyses, retrieve governed knowledge, reconcile evidence, explain
uncertainty and prepare reviewable reports and next-step hypotheses.

PD hPSC-mDA is the first biological use case. The same product architecture may
later support other products after their definitions, references, priors and
measurement specifications are replaced and validated.

## Implementation Stage

The current `main` branch implements the deterministic P0 tool and contract
layer that the Agent will call. The conversational Coordinator, AnalysisPlan and
task-graph runtime, Web application, product-evidence database, Visualization
Composer and interactive interpretation/recommendation workflow remain target
product capabilities rather than integrated runtime behavior.

## Current Tool-layer Outputs

![The current P0 tool layer connects developmental references and a pre-transplant cell product to five evidence domains and traceable outputs.](assets/bridge-biological-workflow.svg)

- Input readiness and explicit evidence gaps.
- Cell-state, identity, developmental, composition, proliferation and stress-response measurements as their modules become validated.
- Conditional comparison under matched product definitions and analysis contracts.
- Traceable visualizations, claims and versioned evidence records.

## Current Non-claims

BRIDGE does not currently establish clinical efficacy, clinical safety, validated potency, GMP release, an absolute product ranking or a globally optimal harvest stage. Transcriptomic alerts are review signals, not safety conclusions.

## Evidence Semantics

- Preserve raw metrics, numerator, denominator, interval and provenance.
- Keep `negative`, `missing`, `unknown`, `unavailable` and `alert` distinct.
- Missing or technically ineligible evidence cannot be interpreted as product failure or a negative-control pass.
- Unknown/OOD and critical review signals act as gates; they are not silently folded into a score.
- Same-family evidence is deduplicated before reconciliation.

## Score Boundary

No P0 `ScoreContract` is frozen in the current release. All domain outputs therefore retain `domain_score=null`; exploratory transformations may be stored only as non-score `shadow` artifacts after explicit review.

## Agent Boundary

The Agent may collect requirements, construct an analysis plan, choose and
orchestrate registered high-level tools, retrieve frozen knowledge, reconcile
returned evidence and explain it to researchers. Deterministic tools—not the
language model—own numerical values, denominators, thresholds, evidence states,
versions and Evidence IDs.

The Agent cannot invent missing metadata, choose a favorable method after seeing
results, modify tool output, promote a candidate method or approve public
release. Human confirmation remains required at consequential scientific and
release boundaries.
