# P0-06 Proliferation and Stress Response: Validation History

This subject-level record preserves the complete dated receipts below.
Each receipt's inputs, source versions, test counts and scientific limits
apply to that historical run, not to the current main branch or a newly
qualified method/product. Consolidation changes organization and links only;
it does not combine evidence families or create a new validation result.

- [P0-06 proliferation and stress-response candidate validation — 2026-08-25](#record-p0-06-proliferation-stress-response-20260825)
- [P0-06 Real-method Runtime Validation](#record-p0-06-real-methods-20260827)
- [P0-06 biological-unit attestation receipt validation](#record-p0-06-biological-unit-attestation-receipt-20260905)
- [P0-06 method-measurement closeout validation — 2026-09-05](#record-p0-06-method-measurement-closeout-20260905)
- [P0-06 Source-bound Observation Validation](#record-p0-06-source-bound-observations-20260907)

<a id="record-p0-06-proliferation-stress-response-20260825"></a>

## P0-06 proliferation and stress-response candidate validation — 2026-08-25

### Biological question and scope

This validation asks whether precomputed whole-product and state-specific
program evidence can be bound to one ProductCase and represented with explicit
stage, gene-coverage, LOD and process-attribution limits. It does not test a
biological program scorer or analyze expression data.

### Synthetic inputs and controls

Tests use seven synthetic JSON objects: ProductCase, ProductDefinitionCard,
DevelopmentWindowSpec, ProgramSpec, CellStateEvidenceProfileV2, ProtocolIR and
ProgramEvidenceBundle. No real cell, sample, protocol, gene list or private
metadata is used.

DevelopmentWindowSpec is uniquely owned by P0-04 and consumed unchanged by P0-06.

The ProgramSpec owns synthetic program IDs, gene-set references and checksums,
allowed stages/states/scopes/metrics, coverage threshold, allowed and resolvable
LOD states, review mappings and attribution-count requirements. One control
replaces the complete vocabulary to verify that Python does not contain a
biology-specific list.

Controls cover whole-product and state-specific records, triggered and
untriggered review outcomes, missing process metadata, batch confounding,
insufficient replication, low coverage, unresolved LOD, unconfirmed/out-of-
window stages, partial envelopes, lineage checksum drift, cross-object drift,
cell-state MeasurementSpec drift, undeclared program/metric/state/LOD/process
values, input mutation and existing-output drift.

### Observed behavior

The valid synthetic bundle produces a deterministic descriptive shadow profile
with aligned program summaries and review flags. Low coverage becomes
`unavailable`; an unresolved LOD becomes `cannot_resolve`; stage mismatch
becomes not applicable. Missing metadata, batch confounding or insufficient
replication becomes `cannot_attribute`, and process-step associations are not
published in that state.

The externally mapped `not_detected_above_lod` outcome retains
`not_evidence_of_safety`. Every result remains `domain_score=null` and no
measurement or visualization is produced.

Malformed contracts, checksum or reference drift, and records outside the
external ProgramSpec fail before publication. Repeated identical inputs reuse
byte-identical artifacts.

### Engineering evidence

- Focused P0-06 and registry suite: 34 passed.
- Exactly 12 high-level Tool Packages remain discoverable.
- Five module-local public P0-06 Schemas are generated, packaged and byte-identical across
  two consecutive generator runs.
- Knowledge validation passed with 354 methods, 396 bindings, no dangling
  method or source references and zero formally eligible methods.
- Repository policy checks passed.
- The committed request example is documentation-only; focused tests construct
  real temporary files and calculate exact checksums.

### Boundary

This is engineering validation of a candidate handoff and aggregation contract.
It does not validate proliferation, stress, pluripotency, process causality,
tumorigenicity, safety, potency, efficacy or release. All review flags remain
shadow and require independent biological and orthogonal validation.


---

<a id="record-p0-06-real-methods-20260827"></a>

## P0-06 Real-method Runtime Validation

Date: 2026-08-27

### Scope

This record covers the P0-06 `method_runtime` path. It verifies that the package
can execute externally configured expression methods on a checksummed,
analysis-ready H5AD without changing the legacy aggregation contract.

The executable selectors are:

| Selector | Runtime call | Output |
|---|---|---|
| `PROC-SCORE-SCANPY` | `scanpy.tl.score_genes` | program-score summaries |
| `PROC-SCORE-DECOUPLER` | `decoupler.mt.ulm` | weighted program-score summaries |
| `PROC-CYCLE-SCANPY` | `scanpy.tl.score_genes_cell_cycle` | cell-cycle summaries |
| `PROC-CYCLE-AGG` | BRIDGE biological-unit/state aggregation | grouped summaries and method agreement |

UCell, AUCell, pseudobulk differential expression and CNV inference remain
registered candidates. This runtime does not execute them.

### Contract checks

- The method path requires 11 checksummed JSON objects and exactly one
  normalized-expression H5AD.
- `ProgramSpec` is the single source for program genes/weights and S/G2M
  phase genes. `ProcessMethodSpec` selects program IDs and runtime parameters
  without copying that biological content.
- Each selected program's canonical content digest must equal its
  `gene_set_sha256`; changing a gene, weight or phase gene while retaining the
  old digest is refused before execution.
- The H5AD identity and checksum are bound before execution and checked again
  before output publication.
- In method mode, the ProtocolIR independent-replicate count may not exceed the
  distinct groups in the bound BiologicalUnitManifest. A synthetic four-group
  manifest paired with a declared count of five is refused as
  `protocol_independent_replicate_count_exceeds_manifest`.
- Results bind the exact ProgramSpec and method spec checksums, selected
  methods, biological units, state scopes, expression asset and software
  versions.
- Missing coverage produces typed `not_assessed` records; it is not converted to
  zero.
- Repeated runs over identical inputs produce the same run and artifact content
  identities.

### Engineering evidence

| Check | Result |
|---|---|
| P0-06 focused and registry tests | 44 passed |
| Content-integrity adversaries | gene, weight and phase-gene changes under a stale digest, plus ProtocolIR 5 versus manifest 4 independent groups, all refused with typed reasons |
| Generated artifacts | ProgramSpec, ProcessMethodSpec and ProcessMethodBundle schemas regenerated from their repository models |
| Repository checks | repository policy, `git diff --check` and added-lines privacy scan passed |

The runtime test used a fully synthetic expression matrix with synthetic
biological-unit and cell-state assignments. No internal or unpublished data are
part of this record.

These counts describe the focused closure run for this revision. The required
GitHub repository gate remains the authority for the complete source suite,
wheel build, 12-tool discovery and clean-install checks.

### Scientific boundary

This is engineering validation of callable methods and deterministic packaging.
It is not biological validation of a gene program, threshold, state definition,
cell fitness, safety or potency. P0-06 remains `candidate`; method evidence
remains `shadow`; `domain_score` remains `null`.


---

<a id="record-p0-06-biological-unit-attestation-receipt-20260905"></a>

## P0-06 biological-unit attestation receipt validation

Date: 2026-09-05

### Scope

P0-06 v0.6.1 keeps `legacy_aggregation` unchanged and requires one
`BiologicalUnitAttestationReceipt v0.1` for `method_runtime`. The shared receipt
records a caller/data-owner assertion for `analysis_execution` and binds the
immutable P0-01 `declared` manifest to its assignment, the P0-02 selected
DataView, observation digest, biological-unit contract and external attestation
trace.

Runtime validates receipt structure and these content bindings. It does not
authenticate the attestor or establish biological truth, independent review,
publication permission or product-release authority. Deployment is responsible
for mapping an authenticated conversation or workflow record to the receipt's
attestation reference and checksum.

### Engineering checks

| Check | Result |
|---|---|
| P0-06 focused suites and registry | 72 passed |
| Receipt refusal | Missing, not-confirmed and assignment-mismatched receipts rejected before execution |
| Immutable lineage | Valid method execution retained the exact declared manifest bytes |
| Provenance | Receipt role and checksum recorded in the artifact manifest and profile source bindings |
| Schema generation | Public profile v0.3 Schema generated twice without drift; source-binding limit widened only from 10 to 11 |
| Repository policy and diff hygiene | Passed |
| Clean-wheel smoke | Installed package reported P0-06 v0.6.1 and a 12-role method-runtime contract with exactly one receipt |
| Scientific output boundary | Method algorithms, result fields, measurements, `domain_score=null` and `score_state=unavailable` unchanged |

The checks use synthetic contract fixtures only. The fixture attestation hash is
not an authenticated record. No private data or deployment resource is included.


---

<a id="record-p0-06-method-measurement-closeout-20260905"></a>

## P0-06 method-measurement closeout validation — 2026-09-05

### Scope

This record covers P0-06 tool v0.6.0 and its `method_runtime` handoff. It
verifies that gate-facing measurements are derived from package-executed
expression methods over the exact P0-02-selected DataView, not from a
caller-provided precomputed evidence bundle.

The legacy aggregation path remains compatible and continues to consume its
checksummed `ProgramEvidenceBundle`.

### Runtime contract

Method mode requires:

- six case, product, window, program, cell-state and protocol objects;
- a reviewed BiologicalUnit manifest and observation assignment;
- a selector-only `ProcessMethodSpec` and checksummed `ProcessMethodInput`;
- one independent P0-06 `MeasurementSpecV2`;
- one H5AD whose asset ID, checksum, assay, matrix location and matrix semantics
  exactly match the P0-02 V3 DataView.

A caller-provided `ProgramEvidenceBundle` is refused in method mode. The
MeasurementSpec must bind only P0-06 and exactly match the assay, observation,
analysis and independence units, selected methods, scopes, metric names and
units. It does not contain a threshold, alert rule or score.

### Observed behavior

Analysis-ready `normalized_expression` is consumed as selected. Count-ready
`raw_counts` is accepted only when finite, non-negative and integer-valued
with positive per-observation totals; P0-06 then applies deterministic
library-size 10,000 scaling and `log1p` in memory.

The emitted `ProcessMethodBundle` v0.2 records the selected matrix location,
input and analysis semantics, and package-owned normalization lineage. It binds
the expression asset, ProgramSpec, method spec/input and BiologicalUnit inputs
by checksum.

Raw-count bundles use the package recipe ID
`bridge_normalize_total_log1p_v0.1` with target sum `10000.0`; it is not a
knowledge-catalog Method reference. Both the Pydantic model and public Draft
2020-12 Schema reject missing or contradictory normalization lineage.

Each real `ProgramScoreSummary` and `CellCycleSummary` produces exactly one
checksummed `MeasurementResultV2`. Available program means and cycling
fractions use `evidence_state=inferred`; `not_assessed` summaries remain
numeric-null `unavailable`. Program-score means retain their observation denominator and algebraic score-sum
numerator; cell-cycle counts retain their numerator and denominator. The profile binding records the source summary digest, method,
program, scope and biological unit. No caller evidence state, biological
threshold, alert or numeric score is synthesized.

### Engineering verification

Exact-head server checks:

- focused P0-06 plus registry suite: 68 passed;
- schema generation was byte-identical across consecutive runs;
- repository policy and committed-whitespace checks passed;
- both committed requests and the new public Schemas parsed as valid JSON.

The required GitHub repository gate remains authoritative for the complete
suite, wheel build and clean-install checks.

### Scientific boundary

This is engineering validation of executable methods, lineage and interface
behavior. It does not validate a gene program, biological threshold, product
state, cell fitness, process causality, safety or potency. P0-06 remains
`candidate/shadow`; `score_state=unavailable` and `domain_score=null`.


---

<a id="record-p0-06-source-bound-observations-20260907"></a>

## P0-06 Source-bound Observation Validation

Date: 2026-09-07 · Package: P0-06 0.7.0

### Question and observed behavior

Can proliferation/stress summaries retain cells whose source references disagree
without forcing a cell-state identity? The opt-in
`method_runtime_source_bound` route reads canonical P0-02 evidence rows and
their exact artifact manifest through ProcessMethodInputV2.

Producer-format synthetic Parquet fixtures cover consensus support,
single-source support, source conflict and unavailable assignments.
Whole-product analysis retains every observation in its declared unit.
State-specific analysis uses only unique candidate identities allowed by the
supplied program specification. A conflict remains unresolved; an unavailable
assignment stays unavailable. Neither becomes unknown or zero. All-conflict
input creates no artificial state-specific result.

Expression rows are joined by observation identity. Existing per-field
observation-set digests are preserved, while file checksums bind the actual
Parquet bytes. No biological identity, design unit, threshold or program
definition is created by the reader.

### Interfaces and invocation

Use `bridge-tool input-contract P0-06` to discover the explicit new mode.
Its expression input and 12 structured roles match method runtime except for the
versioned `process_method_input` object. The v0.2 source descriptor binds the
producer run/version, V3 profile, exact manifest and evidence artifact; it
replaces caller-supplied observation labels, not the need for valid design
records. The [Tool Card](../../src/bridge/tool_packages/cards/P0-06.md) and
[module guide](../../src/bridge/tool_packages/p0_06_proliferation_stress_response/README.md)
describe its fields, CLI/SDK use and refusals.

Old v0.1 inputs, result profile v0.3 and method bundle v0.2 remain unchanged.
Source correspondence checks do not authenticate an internally consistent but
fabricated bundle. Deployment still owns origin and user-confirmation records.

### Engineering verification

At implementation checkpoint `8f5eb9e1`, a fresh target installation from a
built wheel was checked to import BRIDGE from that installation, not source.

| Check | Observed result |
|---|---|
| Installed P0-06, registry, integration-profile and contract tests | 186 passed |
| Discovery and SDK input contracts | 12 implemented tools |
| CLI describe and input-contract | Passed for P0-06 0.7.0 |
| Knowledge and figure registries | Passed |
| Repository policy and committed whitespace | Passed |
| Source bindings | Run, version, artifact, profile, observation membership, checksum and changed-input refusals covered |
| Aggregation | All four support states, identity joins, allowlist boundaries and whole-product denominators covered |
| Malformed source rows | Stable typed refusal from both eligibility and run |

The test run emitted 49 existing Scanpy deprecation warnings, not failed
checks. No dependency was added. A missing Parquet engine is an execution-time
`source_evidence_runtime_unavailable` refusal, not a discovery import failure.

Independent review found malformed rows escaping as untyped exceptions.
The narrow fix checks singleton cardinality before indexing, rejects
array-shaped semantic cells safely, and converts invalid identifiers into the
existing typed refusal. Four direct-loader and four high-level regressions
failed before the fix; all eight passed after it and are included above.
Scoped re-review found no new breakage.

Reproduce the focused checks from a wheel-installed environment:

```bash
python -m pytest -q tests/test_p0_06*.py tests/test_registry.py tests/test_agent_integration.py tests/test_contracts.py
bridge-tool describe P0-06
bridge-tool input-contract P0-06
bridge-tool knowledge validate
bridge-tool figures validate
python scripts/check_repository.py
git diff --check
```

The test archive root may be importable for helpers; its `src` directory must
not override the wheel installation. GitHub checks bind the published PR head
separately; their outcome is not predeclared here.

### Limits and next evidence

These checks used synthetic source-format fixtures, not a genuine P0-02 run or
a real-model Web full-chain test. They establish parsing, binding and grouping
behavior, not biological accuracy, independent replication or truth of an
attestation. Supplied experimental design and genuine source lineage still
require review before product interpretation.

Existing methods, score semantics and candidate status are unchanged:
`domain_score=null`, `score_state=unavailable`. Next integration work must bind
actual producer artifacts and documented experimental units without coercing
unresolved cells or bypassing missing inputs.
