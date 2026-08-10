# Notebooks

Generated Step1-Step3 notebooks are run artifacts. In a demo or study workspace they should be written under that workspace, executed there, and kept together with the corresponding `runs/` outputs.

This repository directory is reserved for curated public examples and lightweight templates. Add notebooks here only when their data inputs, model assets, outputs, and interpretation are public-safe and reproducible.

Notebook standard:
- opening Markdown explains the step and biological question
- core workflow cells call `prescreen(...)`, `identify(...)`, or CLS component APIs
- each table or figure appears in its own section with context and interpretation
- final artifact cell calls the relevant `write_report(...)` function

Report APIs:
- `bridge.prescreen.report.write_report(...)`
- `bridge.identity.report.write_report(...)`
- `bridge.cls.report.write_report(...)`
- `bridge.cls.report.compare_reports(...)`
