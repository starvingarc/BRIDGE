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
The shared v0.2 visualization data binding, v0.1 figure registry and
package-owned deterministic static renderers are available; they do not
constitute an integrated Composer or Web result page.

## Current Tool-layer Outputs

![The current P0 tool layer connects developmental references and a pre-transplant cell product to five evidence domains and traceable outputs.](assets/bridge-biological-workflow.svg)

- Input readiness and explicit evidence gaps.
- Cell-state, identity, developmental, composition, proliferation and stress-response measurements as their modules become validated.
- Conditional comparison under matched product definitions and analysis contracts.
- Traceable visualizations, claims and versioned evidence records.

## Visualization And User Reading Order

The approved [visualization system](BRIDGE_PRD.md#66-visualization-composer-与-web-交互) organizes the result
experience around researcher questions: data readiness, product composition,
identity support, target/regional and developmental fit, off-target/unknown and
process signals, comparison, and evidence gaps.
The figure registry contains 38 components: 31 typed candidates and 7 legacy
components. P0-11 contributes four typed local-review components for
claim-content projection, candidate-digest state, candidate artifact status and
registered checks. Discovery records current capability and does not promote
scientific or publication status.

The product overview uses domain rows with explicit status, denominator,
limitations and evidence links. It does not use a total score, radar chart,
overall rank or pass/fail traffic light. Interactive and static figures must use
the same checksummed data and preserve missingness, uncertainty, provenance and
candidate/shadow status. P0-11 local-review figures are not publication approval;
its internal ToolRun and provenance manifest are not public downloads. This is
an approved design contract; the integrated Web runtime is not yet implemented.

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
