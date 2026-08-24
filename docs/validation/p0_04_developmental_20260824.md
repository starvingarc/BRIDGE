# P0-04 configurable developmental candidate validation — 2026-08-24

## Question

Can P0-04 produce a deterministic static developmental-window profile while
keeping the window and state assignments in a versioned, checksummed object?

This is an engineering validation. Synthetic assignments do not validate a
real developmental window, fetal reference, time course or product.

## Candidate interface

The candidate accepts ProductCase, ProductDefinitionCard,
DevelopmentWindowSpec, CellStateEvidenceProfile and QCReadinessProfile through
`ToolRequestV2`. It publishes one DevelopmentalCompatibilityResult and no
MeasurementResult or visualization. `domain_score` is always null.

## Controls

- exact role, Schema, version, checksum, assay and cross-object binding;
- ProductDefinition and annotation-vocabulary binding;
- P0-02 reconciliation-state compatibility without denominator contamination;
- whole-product and target-related denominators with their source view;
- configurable state roles, missing sources and unresolved residuals;
- strict numeric, deterministic reuse, input mutation and output-path tests;
- V1 typed refusal and public Schema/Pydantic state parity;
- source and installed-wheel execution.

## Evidence status

No local project code was run. The bounded closure implementation at
`3b7928e130cf1853d4e28a68efb2e1f5c820f7bf` was transferred as a Git archive
to `/data1` and exercised there from both the exact source tree and a clean
wheel installation. The installed package resolved from the temporary
environment's `site-packages`, outside the source checkout. The wheel SHA-256
was `54b0877d5ef22509b2b91ee27f98e9c259aa22088d7e3032da0e35bbe372f03f`.

| Gate | Current result |
|---|---|
| Source focused suite | 65 P0-03/P0-04 tests passed |
| Source complete pytest | 1,024 passed; 3 existing dependency warnings |
| Installed-wheel complete pytest | 1,024 passed; 2 dependency warnings |
| 12-tool discovery | passed; exactly 12 |
| Knowledge validation | passed; no dangling method/source refs; 0 formal-eligible methods |
| Repository policy | passed |
| Schema/Card projection parity and diff check | passed |

The closure also removes P0-04's dependency on P0-03-private contract
implementations and rejects machine-local or credential-like
`denominator_view` text before any result or artifact is published. These are
interface and publication-safety changes only; developmental assignments and
fractions are unchanged.

The PR remains Draft. These results demonstrate packaging and deterministic
mechanics, not approval of any biological assignment or scientific release.

## Scientific boundary

P0-04 remains `candidate`. Static output remains shadow and cannot approve the
input window, convert D to GW/PCW, infer a trajectory, or support efficacy,
safety, potency, release or ranking claims.

## Peer-review closeout addendum

The combined closeout adds the exact ProductCase-bound
`BiologicalUnitManifest` and its checksum/scope/unit/group binding. This change
closes cross-module lineage ambiguity but does not alter any developmental
window or promote declared units to biological replicates. Final exact-head
evidence is recorded in the stack closeout validation.
