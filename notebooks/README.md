# Notebooks

This directory is reserved for formal notebook entrypoints and public-facing examples.

Current draft research notebooks are not migrated into BRIDGE v1. Formal notebooks should be promoted only after their inputs, outputs, and artifact contracts are stable.

## Agent Demo Notebook Roadmap

The intended public demo produces one executed notebook or notebook-like run record per biological step:
- Step1 whole-brain prescreening
- Step2 mDA progenitor identity assessment
- Step3 CLS scoring and report generation

Each step can now call a package report API at the notebook tail to write figures, tables, Markdown, JSON manifest, and interpretation text:
- `bridge.prescreen.report.write_report(...)`
- `bridge.identity.report.write_report(...)`
- `bridge.cls.report.write_report(...)`
- `bridge.cls.report.compare_reports(...)`

Migration rule:
- standardize inputs and outputs
- document artifact contracts
- call the package report APIs after the core workflow
- verify on a public-safe demo dataset
- then promote to formal notebooks
