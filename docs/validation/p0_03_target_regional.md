# P0-03 Target and Regional Evidence: Validation History

This subject-level record preserves the complete dated receipts below.
Each receipt's inputs, source versions, test counts and scientific limits
apply to that historical run, not to the current main branch or a newly
qualified method/product. Consolidation changes organization and links only;
it does not combine evidence families or create a new validation result.

- [P0-03 target/regional candidate validation — 2026-08-25](#record-p0-03-target-regional-20260825)
- [P0-03 expression-method validation — 2026-08-26](#record-p0-03-expression-methods-20260826)

<a id="record-p0-03-target-regional-20260825"></a>

## P0-03 target/regional candidate validation — 2026-08-25

### Question and boundary

This record tests whether P0-03 can bind one P0-02 V3 composition to its
ProductCase, measurement, vocabulary, reference, QC and biological-unit lineage,
then publish three deterministic candidate ratios. It does not validate any
real state role, reference suitability, target/regional conclusion, efficacy,
safety, potency or release decision.

### Synthetic contract

Tests construct eleven immutable synthetic JSON objects: ProductCase,
ProductDefinitionCard, StateRoleMap, TargetRegionalAssessmentSpec,
MeasurementSpecV2, CellStateEvidenceProfileV3, QCReadinessProfileV2,
BiologicalUnitManifest, BiologicalUnitAssignmentArtifact,
AnnotationVocabulary and ReferenceManifest. Every file has a real SHA-256; no
private data, server path, laboratory identifier, gene list or product state is
used.

P0-03 consumes the single StateRoleMap contract owned with P0-05 rather than
publishing another model under the same Schema URI. That map owns product roles;
the assessment spec binds its exact checksum and owns requested channels,
target-role membership and regional state-ID numerator/denominator sets.
Changing those objects changes the result without changing Python.

### Observed behavior

A complete synthetic channel publishes one TargetRegionalEvidenceResult and
three independent checksummed MeasurementResultV2 files:

- target identity / selected DataView;
- configured regional support / target-related denominator;
- configured regional support / selected DataView.

The fixture produces `0.6`, `0.75` and `0.6`, respectively, with the original
integer numerators and denominators. Repeated inputs reuse the same run ID and
artifact bytes.

MeasurementSpec, vocabulary, reference and QC checksum drift fails eligibility.
StateRoleMap checksum, ProductDefinition, DataView, assignment hierarchy, QC
module eligibility, vocabulary labels and reference-source drift fail closed. Upstream
`unknown` or `ood` produces `not_assessed`; all three metric values, numerators
and denominators are null. A zero target-related denominator produces an
`unavailable` regional metric rather than numeric zero. A changed existing
metric artifact prevents bundle reuse.

### Engineering evidence

- Focused P0-03 and registry suite after final main sync: 29 passed.
- Exactly 12 high-level Tool Packages remain discoverable.
- Two module-owned P0-03 Schemas, the shared P0-05 StateRoleMap Schema and the
  detailed Tool Card were byte-identical across two consecutive generator
  runs.
- Knowledge validation passed with 354 methods, 396 bindings, no dangling
  method/source references and zero formally eligible methods.
- Repository policy and staged diff checks passed.

### Interpretation boundary

P0-03 remains `candidate`. Numeric results remain `shadow` and
`domain_score=null`; `complete` means only that the supplied contracts were
bound and the configured arithmetic was available. This engineering evidence
does not freeze biology or authorize a scientific or public claim.


---

<a id="record-p0-03-expression-methods-20260826"></a>

## P0-03 expression-method validation — 2026-08-26

### Scope

This record verifies that P0-03 invokes its declared expression methods rather
than only registering their names. The fixture is fully synthetic and tests
engineering behavior only.

### Fixture and lineage

The request binds the standard eleven P0-03 JSON objects, one checksummed
analysis-ready H5AD and one checksummed `TargetRegionalMethodSpec`. The H5AD
observation IDs exactly match the P0-01 biological-unit assignment. Target and
regional evidence use separately declared reference-profile sets. Reference
matrices, metadata and marker-program files are resolved from the supplied
`ReferenceManifest` and verified by SHA-256.
The method spec also carries a synthetic versioned expression-semantics
contract, an explicitly feature/context-matched modality group and an external
relative-residual applicability limit. These fixtures test contract propagation,
not scientific suitability.

The fixture contains one ProductCase, one analysis unit, one independence group,
two synthetic reference profiles with different assay labels, three synthetic
states and one signed marker program. It contains no real genes, samples,
laboratory identifiers or unpublished data.

### Methods exercised

| Method | Observed runtime behavior |
|---|---|
| `TRG-PBCORR` | sample-pseudobulk Spearman/cosine and label margin against target references |
| `REG-PBCORR` | the same calculation against the separate regional references |
| `TRG-NNLS` | SciPy NNLS state weights with simplex normalization, relative L2 residual and typed applicability |
| `TRG-DECOUPLER` | decoupler ULM target-program activity and marker coverage |
| `REG-DECOUPLER` | decoupler ULM regional-program activity and marker coverage |
| `TRG-BOOTSTRAP` | explicit `descriptive_only` result for one independent unit |
| `REG-CROSSREF` | cross-reference label agreement and support range |
| `REG-MODALITY` | declared matched-group scRNA/snRNA sensitivity record |

Pseudobulk grouping comes from `analysis_unit_ref`; the executor does not trust
an independent H5AD sample column. Bootstrap grouping comes from
`independence_group_ref`. The one-unit fixture therefore yields a typed partial
ToolRun instead of a fabricated confidence interval.

### Outputs and reproducibility

The run publishes the existing ratio artifacts plus one
`TargetRegionalMethodBundle`. The bundle records the selected methods, package
versions, input asset checksum, reference manifest, biological units, method
states and all method outputs. The parent result binds the bundle checksum.

Server verification uses `tests/test_p0_03_expression_methods.py` for the
eight-method expression path, missing-semantics refusal, missing matched-group
refusal, high-residual propagation, paired-input refusal and asset replacement.
The repository gate reruns the full suite, 12-tool discovery, public-Schema
parity, knowledge validation, policy checks and `git diff --check` at the exact
reviewed head. Test counts and wheel hashes are intentionally not copied into
this durable record; the exact-head CI run is the source of those build facts.

### Catalog disposition

P0-03 v0.3.0 directly executes only the methods listed above. CellTypist,
scANVI, SingleR, scmap, Symphony and scConform remain upstream P0-02 benchmark
adapters. UCell, AUCell, popV, scArches, ontology crosswalks and spatial methods
remain catalog candidates without a P0-03 runtime artifact.

### Scientific boundary

P0-03 remains `candidate`. Numeric evidence remains `shadow` and
`domain_score=null`. Successful execution does not validate reference
suitability, marker programs, target identity, regional fidelity, spatial
localization, potency, safety, efficacy or release eligibility.
