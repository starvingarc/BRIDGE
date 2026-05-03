# bridge-identity

Use this skill for BRIDGE Step 2 work.

## Purpose

This skill covers:
- notebook-callable identity assessment
- candidate-selection artifacts
- thresholds, probabilities, uncertainty, and entropy outputs

## Core package areas

- `src/bridge/identity`

## Expected Step 2 artifact set

Artifacts are anchored by `dataset.prefix` and typically include:
- `<prefix>.thresholds.json`
- `<prefix>.bdata_step2.h5ad`
- `<prefix>.adata_ref_step2.h5ad`
- `<prefix>.probs_ref_cal.csv`
- `<prefix>.probs_query_cal.csv`
- `<prefix>.mean_org.csv`
- `<prefix>.std_org.csv`
- `<prefix>.Hnorm.csv`

## Common concerns

- query/reference/model path resolution
- calibration and ensemble behavior
- stable candidate-selection output contracts
