# BRIDGE Agent Notes

BRIDGE is a notebook-first research software package for brain-referenced evaluation of in vitro mDA progenitor products.

## Current Public Surface

- Step0 setup is handled by `.claude/skills/bridge-step0`.
- Step1 prescreening is implemented in `src/bridge/prescreen`.
- Step2 identity assessment is implemented in `src/bridge/identity`.
- Step3 CLS scoring and reporting are implemented in `src/bridge/cls`.
- Shared report utilities live in `src/bridge/reporting`.
- YAML config helpers live in `src/bridge/workflows/config.py`.

The public workflow is API/notebook-first. BRIDGE does not expose a package CLI for Step1-Step3.

## Preferred Notebook Imports

```python
from bridge.prescreen import prescreen
from bridge.identity import identify
from bridge.cls import CLSContext, component_A, component_B, component_C, component_D, component_E, component_F, score
```

Report imports:

```python
from bridge.prescreen.report import write_report as write_prescreen_report
from bridge.identity.report import write_report as write_identity_report
from bridge.cls.report import write_report as write_cls_report, compare_reports
```

## Development Rules

- Keep core workflow logic in `src/bridge`, not embedded only in notebooks.
- Keep runtime data, downloaded assets, and private paths outside Git history.
- Preserve Step1, Step2, and Step3 artifact contracts when refactoring.
- Use lazy imports for runtime-heavy dependencies such as `scanpy`, `scvi`, and `decoupler`.
- Public docs should describe the released notebook/API workflow and model assets without environment-specific server details.

## Thesis Alignment

- Step1: whole-brain prescreening and RG candidate enrichment.
- Step2: target-specific mDA progenitor identity assessment.
- Step3: CLS component scoring, reporting, and protocol comparison.

Reference construction and model training remain model-building context; the public package consumes the resulting model assets through `models/assets.json` and user-provided paths.
