# P0-06 configurable program-evidence candidate validation — 2026-08-24

## Question

Can P0-06 deterministically assemble stage-bound program observations and
configured shadow review signals without encoding biological programs or
decision thresholds in the implementation?

This is engineering validation. Synthetic programs, intervals and observations
do not validate a real ProgramSpec, scorer, reference, threshold or product
conclusion.

## Candidate interface

The candidate accepts ProductCase, ProductDefinitionCard,
ProgramAssessmentSpec, ProgramEvidenceBundle, DevelopmentalCompatibilityResult
and QCReadinessProfile through `ToolRequestV2`. It publishes one
ProliferationStressResponseProfile and no MeasurementResult or visualization.
`domain_score` is always null.

## Controls

- exact role, Schema, version, checksum, assay and cross-object binding;
- ProductDefinition, P0-04 developmental-window and Cell-State-profile binding;
- caller-supplied reference interval, coverage, evidence-state and direction;
- Evidence Family and independence-group de-duplication;
- missing/unavailable, low-coverage and unmatched-observation semantics;
- strict numeric, deterministic reuse, input mutation and output-path tests;
- V1 typed refusal and public Schema/Pydantic parity;
- source and installed-wheel execution.

## Evidence status

No local project code was run. The bounded closure implementation at
`2785a9c8f71c9b7e9a7ee5fa104a627bb426331b` was transferred as a Git archive
to `/data1` and exercised there from both the exact source tree and a clean
wheel installation. The installed package resolved from the temporary
environment's `site-packages`, outside the source checkout. The wheel SHA-256
was `2f6a269c445dfe1eae0ad125752987e91ba42dae077d6c24c326466f222e8ec7`.

| Gate | Current result |
|---|---|
| Source focused chain | 126 P0-03/P0-04/P0-05/P0-06 tests passed |
| Source complete pytest | 1,085 passed; 3 existing dependency warnings |
| Installed-wheel complete pytest | 1,085 passed; 2 dependency warnings |
| 12-tool discovery | passed; exactly 12 |
| Knowledge validation | passed; no dangling method/source refs; 0 formal-eligible methods |
| Repository policy | passed |
| Public/packaged Schema and Tool Card parity | passed |
| Committed diff check | passed |

The closure also moves generic object references to the shared configurable
contract and rejects machine-local or credential-like unit text in both the
input rule and result model. Program evaluation, intervals and review-flag
semantics are unchanged.

The PR remains Draft. These results demonstrate packaging, strict contracts and
deterministic mechanics, not approval of a biological program, reference range
or release rule.

## Scientific boundary

P0-06 remains `candidate`. All assessed review flags remain `shadow`.
Protocol attribution, residual-pluripotency LOD and transcriptomic CNV remain
`not_assessed`. The module establishes neither biological truth nor safety,
potency, release or ranking.

## Peer-review closeout addendum

The combined closeout now aggregates analysis units within exact manifest
independence groups. Only externally reviewed/frozen lineage with a checksummed
review gate can contribute independent group counts; declared lineage produces
`cannot_resolve` and zero independent groups. P0-06 cannot self-review lineage.
Final exact-head evidence is recorded in the stack closeout validation.
