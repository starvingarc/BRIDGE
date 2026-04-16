# report-review

Use this skill when generating or reviewing BRIDGE report outputs from real Step 2 and Step 3 artifacts.

## Purpose

This skill covers:
- report-only execution from existing artifacts
- interpretation of Step 2 summary fields
- interpretation of Step 3 summary fields
- cross-dataset comparison across multiple in vitro datasets

## Report scope in the current BRIDGE phase

The formal report layer now covers both:
- Step 2 summary
- Step 3 summary

It is not limited to CLS-only aggregation.

## Step 2 summary fields to read carefully

At minimum, the report should expose:
- `dataset_id`
- `target_class`
- `n_query`
- `n_ref`
- thresholds `t`, `u`, `u_raw`, `v`
- `candidate_count`
- `candidate_fraction`
- presence of `p_cal`, `p_mean`, `p_std`, and `Hnorm`
- summary statistics of `p_mean`, `p_std`, and `Hnorm` when available

Interpretation guidance:
- threshold values describe the candidate-selection gate, not a biological score by themselves
- candidate fraction reflects how much of the query passed Step 2, not how well Step 3 performed
- high `p_mean` with low `p_std` and low `Hnorm` is usually consistent with more stable identity assignment

## Step 3 summary fields to read carefully

At minimum, the report should expose:
- component scores A-F
- optional weighted total CLS
- paths to source component JSON files
- whether component-level detail tables exist

Interpretation guidance:
- Step 3 scores should be read after Step 2 candidate selection, not as a replacement for Step 2
- a dataset can have a reasonable candidate fraction but uneven CLS profile across A-F
- cross-dataset comparison should distinguish missing-artifact failures from actual score differences

## Execution commands

Per-dataset report:

```bash
bridge report summarize --config <dataset-config.yaml>
```

Cross-dataset report:

```bash
bridge report summarize-batch --config-list <config-list.yaml>
```

## What counts as an infrastructure failure

Treat the run as an infrastructure/config failure if:
- a Step 2 thresholds JSON is missing
- component global JSON files are missing
- the config points to the wrong artifact directory
- required real paths resolve incorrectly

Treat the run as a biological/result difference only after artifact integrity has been verified.
