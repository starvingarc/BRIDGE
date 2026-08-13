# P0-08 Evidence Sufficiency

## Motivation

Later evidence compilation must distinguish an absent or weak evidence basis from a negative biological observation. P0-08 provides a deterministic gate over already-produced evidence records so downstream tools can see whether a domain is assessable without rerunning analysis, inventing values or treating engineering success as scientific release.

## Frozen branch interface

- Tool ID: `P0-08`; package version: `0.2.0`.
- Request/run envelopes: `bridge://schemas/tool-request/v0.2` and `bridge://schemas/tool-run/v0.2`.
- Result: `bridge://schemas/evidence-sufficiency-run-result/v0.1`.
- Adapter: `bridge.tool_packages.p0_08_evidence_sufficiency.adapter:adapter`.
- Input order: Data Readiness → Model Robustness → Prior Applicability → sufficiency.
- Final precedence: `not_assessed` → `insufficient` → `limited` → `sufficient`.
- Current score contract: `domain_score=null`, `score_state=unavailable`.

## Implemented scope

- Accept one packaged gate rule, one to five domain bindings and versioned QC, measurement, validation, prior and sensitivity objects through checksummed JSON references.
- Separate malformed/unsafe input failures from valid scientific `not_assessed` results.
- De-duplicate byte-equivalent Evidence Family records without increasing influence; refuse to resolve non-identical required-family records by vote.
- Emit deterministic profiles, case summary, gate trace, run result and artifact manifest as immutable JSON.
- Preserve negative, missing, unknown, unavailable and alert semantics and upstream provenance.
- Publish the full CLI/SDK field contract, examples, reason codes and candidate validation record.

## Non-goals

- No expression-matrix read or single-cell reanalysis.
- No new raw measurement, threshold, ScoreContract or domain score.
- No product ranking, pass/fail, potency, safety, efficacy, GMP-release or clinical interpretation.
- No scientific promotion from `candidate`, no environment promotion from `proposed`, and no method promotion to `formal_eligible`.

## Validation and review state

- Module scenarios cover sufficient, limited, insufficient and not-assessed paths; family duplicate/conflict behavior; missing-state semantics; checksum/mutation/drift failures; deterministic artifacts; and score-null enforcement.
- Public and packaged Schemas, Tool Card projections, resources, knowledge projection, CLI/SDK behavior and wheel contents are integration gates for this branch.
- The Pull Request remains Draft until independent code review and the repository `repository-gates` check pass. Passing engineering gates does not authorize a real ProductCase run or merge.

## Remaining scientific work

Before real-case use, reviewers must establish the applicable ProductDefinition and MeasurementSpec-side requirements, validate each upstream record in its declared context, review the candidate gate resource and reproduce the proposed evidence environment. P0-08 output alone cannot make an unsupported upstream record valid.
