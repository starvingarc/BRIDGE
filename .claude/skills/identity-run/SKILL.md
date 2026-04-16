# identity-run

Use this skill when running or validating the formal BRIDGE Step 2 workflow.

## Purpose

This skill covers:
- selecting the correct workflow config
- validating that Step 2 inputs exist in the target runtime environment
- understanding what Step 2 writes out
- deciding whether to rerun Step 2 or reuse existing Step 2 outputs

## Expected Step 2 inputs

Each execution config must resolve:
- `paths.reference_h5ad`
- `paths.query_h5ad`
- `paths.ref_model_dir`

## Expected Step 2 outputs

The formal Step 2 output set is anchored by `dataset.prefix` and should include:
- `<prefix>.thresholds.json`
- `<prefix>.bdata_step2.h5ad`
- `<prefix>.adata_ref_step2.h5ad`
- `<prefix>.probs_ref_cal.csv`
- `<prefix>.probs_query_cal.csv`
- `<prefix>.mean_org.csv`
- `<prefix>.std_org.csv`
- `<prefix>.Hnorm.csv`

## When to rerun Step 2

Rerun Step 2 only when:
- the configured Step 2 artifacts are missing
- the target class changes
- the identity thresholds or runtime parameters change intentionally
- the query input dataset changes

Reuse existing Step 2 outputs when:
- the artifact set is complete
- the report only needs to summarize existing results
- Step 3 and report are being validated against already computed artifacts

## Common failure points

- missing `ref_model_dir`
- config points to the wrong Step 2 prefix
- missing `counts` layer in query/reference objects
- query model loads but ensemble runs fail and produce no successful members
