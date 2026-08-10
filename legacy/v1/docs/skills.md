# Skill Interface

BRIDGE ships repository-local skills through `.claude/skills`. These are the public agent workflow for the demo; there is no separate agent-demo skill layer.

Use the same skill names across agents. Add the prefix your agent expects, such as `/bridge-step1` or `@bridge-step1`.

| Step | Skill | Purpose |
| --- | --- | --- |
| Step0 | `bridge-step0` | Prepare environment, model assets, config, and run directory. |
| Step1 | `bridge-step1` | Run whole-brain prescreening and a notebook-visible report. |
| Step2 | `bridge-step2` | Run mDA progenitor identity assessment and an identity report. |
| Step3 | `bridge-step3` | Run CLS scoring, single-dataset reporting, and optional protocol comparison. |

## What Skills Specify

Each skill tells the agent:
- required inputs and config fields
- notebook imports and package API calls
- expected artifacts
- report sections to display in the notebook
- validation checks for executed notebook outputs

## Notebook Report Standard

Step notebooks should contain one table or one figure per section:

1. Markdown context that states the purpose of the output.
2. One executable code cell that builds and displays the table or figure.
3. Markdown interpretation grounded in the observed values and biological meaning.

Plot cells should use `display_matplotlib_figure(fig)` from `bridge.reporting.notebook`. The final artifact cell should call the appropriate `write_report(...)` function and print saved paths.

## Recommended Imports

```python
from bridge.prescreen.report import write_report as write_prescreen_report
from bridge.identity.report import write_report as write_identity_report
from bridge.cls.report import write_report as write_cls_report, compare_reports
```

Step2 uses `paths.reference_h5ad` as the target-specific reference AnnData. `paths.ref_sceniclike_h5ad` belongs to Step3 component F.
