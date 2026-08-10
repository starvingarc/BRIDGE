# P0-02 Cell-State Evidence

## Purpose

Describe which fetal ventral-midbrain cell states are supported in a post-QC product expression view, while preserving source disagreement and unresolved labels.

## Contract

| Field | Value |
|---|---|
| Package version | `0.3.0` |
| Runtime state | `implemented` |
| Scientific state | `candidate / shadow` |
| EnvironmentSpec | `ENV-P0-CORE-v0.1` |
| Input schema | `bridge://schemas/tool-request/v0.1` |
| Output schema | `bridge://schemas/tool-run/v0.1` |

**Input:** one P0-01-qualified h5ad; declared scRNA/snRNA assay and source family; the matching Cell-State `MeasurementSpec`; a deployment-resolved reference snapshot.

**Baseline evidence:**

1. Spearman support to source-specific `sample/donor x label` pseudobulk profiles, with cosine similarity as a sensitivity metric.
2. Positive- and negative-marker expression from versioned shadow marker cards; no conflict threshold is inferred.

Each source retains its full support vector, top label and margin. Source top labels form a candidate prediction set. Agreement is `consensus_supported`; disagreement is `source_conflict`. Neither is a calibrated assignment.

Reference profiles from the query's declared source family are held out before support is computed.

L1 runs on all observations. L2 runs only when the L1 prediction set contains `Radial_Glia` or `Neuroblast`. L3 remains `shadow_not_executed`.

## Reference Policy

- scRNA: Chen fetal vMB scRNA and La Manno fetal VM are independent primary sources.
- snRNA: Chen fetal vMB snRNA is the primary source.
- Chen sc/sn combined is sensitivity-only and never counted as a third source.
- Braun and Zeng provide regional/OOD context outside the L1 identity vote.
- Birtele is added only through a new reviewed snapshot.
- `E-MTAB-14729` and competitor markers, labels, references and thresholds have zero data flow.

The scientific-team command `bridge-reference build` turns a private deployment catalog into an immutable snapshot. Its manifest contains logical IDs, relative artifact names and checksums, never source paths. Agent runtimes only resolve the snapshot named by the `MeasurementSpec`.

## Outputs

- `cell_state_evidence.parquet`
- `source_specific_support.parquet`
- `marker_program_evidence.parquet`
- L1/L2 shadow composition
- reference, marker, composition and conflict figures
- `CellStateEvidenceProfile` and artifact manifest

All measurements remain `domain_score=null` and `score_state=shadow/unavailable`.

## Refusal Conditions

The package refuses when the input lacks a P0-01 profile reference, assay and MeasurementSpec disagree, no applicable reference is installed, checksums fail, or shared gene coverage is below the candidate contract. Missing support is never rewritten as negative evidence.

## Validation Before Freeze

Use source/lab/modality holdouts, leave-one-state-out, rare-state mixtures and true OOD datasets. scANVI, Symphony, scArches, scHPL and popV remain benchmark candidates and cannot alter this baseline until independently validated.

Detailed scientific requirement: `docs/bridge_v2_spec_v0.1/cell_state_annotation_task_card.md`.
