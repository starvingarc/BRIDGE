# cls-run

Use this skill when running or validating the formal BRIDGE Step 3 workflow.

## Purpose

This skill covers:
- Step 3 prerequisites
- A-F component dependencies
- when Step 3 can run directly from stored Step 2 outputs
- how CLS outputs are organized

## Core dependency

Step 3 depends on Step 2 artifacts. At minimum, the workflow requires:
- `<prefix>.bdata_step2.h5ad`
- `<prefix>.adata_ref_step2.h5ad`
- `<prefix>.probs_ref_cal.csv`

## Component prerequisites

### A, B, C

Require the standard Step 2 outputs listed above.

### D

Requires embeddings in the loaded h5ad objects, or a valid `ref_model_dir` so embeddings can be produced via the existing helper.

### E

Requires:
- valid embeddings for reference and query
- target-class subsetting
- candidate-cell subset in the Step 2 query output

### F

Requires:
- `paths.ref_sceniclike_h5ad`
- `paths.regulons_json`

## Output structure

CLS outputs are written under:
- `paths.cls_output_dir / dataset.id / <component>/`

Expected files include:
- `component_<X>_global.json`
- `component_<X>_batch.csv` when relevant
- `component_E_branch.csv`
- `component_E_genes.csv`
- `query_aucell.csv` for component F when present

## Common failure points

- wrong dataset ID relative to existing CLS result directory
- missing Step 2 artifact set
- embeddings absent for D or E
- missing SCENIC-like inputs for F
