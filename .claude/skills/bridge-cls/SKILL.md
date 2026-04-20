# bridge-cls

Use this skill for BRIDGE Step 3 work.

## Purpose

This skill covers:
- CLS component execution
- Step 3 prerequisites
- report generation from Step 2 + Step 3 artifacts

## Core package areas

- `src/bridge/cls`
- `src/bridge/workflows/cls.py`
- `src/bridge/workflows/report.py`

## Step 3 prerequisites

At minimum, Step 3 depends on Step 2 outputs:
- `<prefix>.bdata_step2.h5ad`
- `<prefix>.adata_ref_step2.h5ad`
- `<prefix>.probs_ref_cal.csv`

Additional component-specific inputs may be required for:
- embeddings
- trajectory analysis
- regulon-based scoring

## Output structure

Step 3 writes:
- component-level global JSON files
- optional detail tables
- report summaries and manifests
