# bridge-step2

Use this skill for BRIDGE Step2 mDA progenitor identity assessment.

## Purpose

Step2 consumes the Step1 RG candidate subset and runs target-specific identity assessment to identify mDA progenitor candidates.

## Expected User Prompt

Claude Code:

```text
/bridge-step2 identify mDA progenitor candidates from ./bridge-demo/runs/demo_dataset/step1 using ./bridge-demo/bridge.run.yaml
```

Codex:

```text
@bridge-step2 identify mDA progenitor candidates from ./bridge-demo/runs/demo_dataset/step1 using ./bridge-demo/bridge.run.yaml
```

## Required Inputs

- Step1 RG candidate subset
- target-specific reference AnnData from `paths.reference_h5ad`
- target-specific scANVI model path from `paths.ref_model_dir`
- writable Step2 output directory

`paths.ref_sceniclike_h5ad` is not a Step2 input. It is reserved for Step3 component F and must never be used as a fallback Step2 reference.

## Agent Responsibilities

1. Locate the Step1 RG candidate h5ad.
2. Validate `paths.reference_h5ad`, `paths.ref_model_dir`, `identity.target_class`, and the Step2 output directory.
3. In the Step2 notebook, call `from bridge.identity import identify`.
4. Run `identify(bdata_rg, adata_ref, ref_model_dir=..., target_class=..., output_dir=..., prefix=..., reference_h5ad_path=...)` so the Step2 reference artifact can be a symlink instead of a full copy.
5. Preserve the current Step2 artifact contract.
6. Call `from bridge.identity.report import write_report as write_identity_report`.
7. Run `write_identity_report(result=result, output_dir=..., prefix=..., target_class=...)` at the notebook tail.
8. Summarize candidate count, candidate fraction, and threshold metadata without overclaiming final biological interpretation.
9. If the configured target reference is missing, unreadable, or has a gene set incompatible with the target model, stop and report the exact problem. Do not search unrelated server paths or substitute another reference file.

## Notebook API

```python
from bridge.identity import identify
from bridge.identity.report import write_report as write_identity_report

adata_ref = sc.read_h5ad(config.paths.reference_h5ad)

result = identify(
    bdata_rg,
    adata_ref,
    ref_model_dir=config.paths.ref_model_dir,
    target_class="RG_Mesencephalon_FP",
    output_dir="./outputs/identity",
    prefix="demo_prefix",
    reference_h5ad_path=config.paths.reference_h5ad,
)

report = write_identity_report(
    result=result,
    output_dir="./outputs/identity/report",
    prefix="demo_prefix",
    target_class="RG_Mesencephalon_FP",
)
```

## Expected Outputs

- `<prefix>.thresholds.json`
- `<prefix>.bdata_step2.h5ad`
- `<prefix>.adata_ref_step2.h5ad` (preferably a symlink to the configured target reference to avoid duplicating large files)
- `<prefix>.probs_ref_cal.csv`
- `<prefix>.probs_query_cal.csv`
- `<prefix>.mean_org.csv`
- `<prefix>.std_org.csv`
- `<prefix>.Hnorm.csv`
- Step2 report Markdown
- Step2 report manifest JSON
- report tables and available figures

## Report Coverage

The Step2 report API covers target probability, uncertainty, entropy, candidate summaries, optional UMAP views, and mean-probability identity composition with an `Uncertain` label below cutoff. Use the public UMAP helpers `plot_mean_identity_umap`, `plot_target_pmean_umap`, `plot_target_pstd_umap`, `plot_entropy_umap`, and `plot_candidate_umap` when adding notebook-visible UMAP sections. Interpret high `p_mean` with low `p_std`/`Hnorm` as stable target convergence; interpret high uncertainty as boundary, transition, or competing-fate structure.

## Notebook-Visible Report Sections

After the core workflow runs, the notebook must include notebook-visible report sections rather than only writing files under `report/`. For each report table, add a short Markdown context cell, a code cell that builds and displays the table, and a concise interpretation Markdown cell. For each report figure, add a short Markdown context cell, a code cell that calls the public `plot_*` function and displays the figure, and a concise interpretation Markdown cell. The final cell should still call `write_report(...)`, print artifact paths, and save the standard Markdown, manifest, CSV, and image files. Agents should display each table and display each figure as code-cell output.

## Narrative Notebook Structure

Generated notebooks must be notebook-native analysis records, not a report dump at the end. Use this exact structure:

1. Opening Markdown: explain what this step does, why it matters in BRIDGE, what biological question it addresses, and what artifacts it will produce.
2. Core workflow cells: load input, validate config/model paths, run the step, and print only concise run metadata.
3. Notebook-visible report sections: create one logical section per table or figure. Each section must contain:
   - purpose/context Markdown before the code, explaining what this table or figure is meant to evaluate;
   - exactly one code cell that builds one table or one figure;
   - for table cells, call `display(table_df)`;
   - for figure cells, call `fig = plot_...(...)` followed by `_ = display_matplotlib_figure(fig)` from `bridge.reporting.notebook`;
   - biological interpretation Markdown after the output, grounded in the observed values and developmental meaning.
4. Final Markdown summary: summarize what this step concluded and how it feeds the next BRIDGE step.
5. Final artifact cell: call `write_report(...)`, print saved paths, and do not re-display every report artifact. The saved `report/` folder remains the artifact contract.

Do not use a final cell that loops through report tables/figures and displays them all together. Do not rely on a bare `fig` expression, because some notebook renderers show only `<Figure size ...>` instead of the image.

## Notebook Output Validation

After executing the notebook, validate the `.ipynb` file itself, not only the saved `report/` folder. Open or parse the notebook JSON and confirm that every notebook-visible table/figure code cell has a real output. Figure cells must contain an `image/png` payload; table cells must contain a displayed table output. Do not accept a notebook that only saved report artifacts while the notebook cells are empty.

If an image cell contains only a `text/plain` fallback, `<Figure size ...>`, or `<IPython.core.display.Image object>`, repair it before finishing by re-running that cell with `display_matplotlib_figure(...)` or by embedding the saved PNG into that exact cell output. Remove stale text-only fallbacks from image outputs so Jupyter and VS Code render the actual figure.

Check file freshness: if report artifacts are newer than the notebook, assume notebook output may not have been flushed and re-save or repair the notebook. Then run `jupyter trust <notebook>` when available, and re-check that the notebook has no error outputs and that each required figure/table appears in its own code cell.

This validation is required for Step2 even when the report folder looks correct.

## Reference Guardrails

Step2 target identity assessment must use the RG target reference AnnData paired with the target scANVI model. The reference should contain the model gene set, the configured `identity.ref_label_key`, and the configured `identity.counts_layer`. `ref_sceniclike_h5ad` has a reduced gene/regulon-oriented feature space for Step3 component F and is biologically and technically invalid for Step2 scANVI query mapping.

Step2 biological interpretation should distinguish stable target convergence from uncertain, transitional, or competing-fate cells using target probability, variability, entropy, candidate fraction, and identity composition.
