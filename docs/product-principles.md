# Product And Scientific Principles

## Purpose

BRIDGE organizes reproducible transcriptomic evidence for cell-therapy product characterization. PD hPSC-mDA is the first complete application; the same high-level contract may later support other products after their definitions, references, priors and measurement specifications are replaced and validated.

## Current Outputs

- Input readiness and explicit evidence gaps.
- Cell-state, identity, developmental, composition and process-state measurements as their modules become validated.
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

The Agent may collect requirements, choose registered high-level tools, retrieve frozen knowledge and explain returned evidence. It cannot invent missing metadata, choose a favorable method after seeing results, modify numerical output, promote a candidate method or approve public release.
