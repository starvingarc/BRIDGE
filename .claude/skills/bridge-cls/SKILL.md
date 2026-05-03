# bridge-cls

Use this skill for BRIDGE Step 3 work.

## Purpose

This skill covers:
- CLS component execution
- Step 3 prerequisites
- summary and manifest generation from Step 2 + Step 3 artifacts

## Core package areas

- `src/bridge/cls`

## Step 3 prerequisites

At minimum, Step 3 depends on Step 2 objects or loaded Step2 artifacts:
- candidate-bearing `bdata`
- target-specific `adata_ref`
- `probs_ref_cal` for components A and C

Additional component-specific inputs may be required for:
- embeddings
- trajectory analysis
- regulon-based scoring

## Output structure

Step 3 writes:
- component-level global JSON files
- optional detail tables
- `summary.csv` and `manifest.json`
