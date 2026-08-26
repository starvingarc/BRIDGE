# P0-03 expression-method validation — 2026-08-26

## Scope

This record verifies that P0-03 invokes its declared expression methods rather
than only registering their names. The fixture is fully synthetic and tests
engineering behavior only.

## Fixture and lineage

The request binds the standard eleven P0-03 JSON objects, one checksummed
analysis-ready H5AD and one checksummed `TargetRegionalMethodSpec`. The H5AD
observation IDs exactly match the P0-01 biological-unit assignment. Target and
regional evidence use separately declared reference-profile sets. Reference
matrices, metadata and marker-program files are resolved from the supplied
`ReferenceManifest` and verified by SHA-256.

The fixture contains one ProductCase, one analysis unit, one independence group,
two synthetic reference profiles with different assay labels, three synthetic
states and one signed marker program. It contains no real genes, samples,
laboratory identifiers or unpublished data.

## Methods exercised

| Method | Observed runtime behavior |
|---|---|
| `TRG-PBCORR` | sample-pseudobulk Spearman/cosine and label margin against target references |
| `REG-PBCORR` | the same calculation against the separate regional references |
| `TRG-NNLS` | SciPy NNLS state weights with simplex normalization and residual |
| `TRG-DECOUPLER` | decoupler ULM target-program activity and marker coverage |
| `REG-DECOUPLER` | decoupler ULM regional-program activity and marker coverage |
| `TRG-BOOTSTRAP` | explicit `descriptive_only` result for one independent unit |
| `REG-CROSSREF` | cross-reference label agreement and support range |
| `REG-MODALITY` | scRNA/snRNA reference-sensitivity record |

Pseudobulk grouping comes from `analysis_unit_ref`; the executor does not trust
an independent H5AD sample column. Bootstrap grouping comes from
`independence_group_ref`. The one-unit fixture therefore yields a typed partial
ToolRun instead of a fabricated confidence interval.

## Outputs and reproducibility

The run publishes the existing ratio artifacts plus one
`TargetRegionalMethodBundle`. The bundle records the selected methods, package
versions, input asset checksum, reference manifest, biological units, method
states and all method outputs. The parent result binds the bundle checksum.

Focused server verification passed 30 P0-03 tests, including the complete
aggregation path, the eight-method expression path, paired-input refusal and
asset-replacement protection. The complete repository suite passed 1,232 tests.
A clean wheel installation passed all 12 `describe` calls, all 12
`input-contract` calls, 12-tool discovery and the four expression-method
tests. Public schemas were regenerated from Pydantic models and validated as
JSON Schema Draft 2020-12. Knowledge and repository-policy gates also passed.

## Catalog disposition

P0-03 v0.3.0 directly executes only the methods listed above. CellTypist,
scANVI, SingleR, scmap, Symphony and scConform remain upstream P0-02 benchmark
adapters. UCell, AUCell, popV, scArches, ontology crosswalks and spatial methods
remain catalog candidates without a P0-03 runtime artifact.

## Scientific boundary

P0-03 remains `candidate`. Numeric evidence remains `shadow` and
`domain_score=null`. Successful execution does not validate reference
suitability, marker programs, target identity, regional fidelity, spatial
localization, potency, safety, efficacy or release eligibility.
