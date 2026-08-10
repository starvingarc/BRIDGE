# Formal Workflows

BRIDGE v1 exposes the thesis workflow as Python interfaces designed for notebook-based analysis. Step0 is agent-guided setup; Step1-Step3 are package calls that can be executed and documented inside notebooks.

## Pipeline

| Stage | Package surface | Biological role |
| --- | --- | --- |
| Step0 | `.claude/skills/bridge-step0` plus config/model manifests | Prepare environment, model assets, and run directory. |
| Step1 | `bridge.prescreen` | Whole-brain prescreening of one in vitro `.h5ad` to enrich radial glia candidates. |
| Step2 | `bridge.identity` | Target-specific mDA progenitor identity assessment using calibrated probability and uncertainty. |
| Step3 | `bridge.cls` | Component-level developmental concordance scoring and reporting. |

## Python Interfaces

Recommended imports:

```python
from bridge.prescreen import prescreen
from bridge.identity import identify
from bridge.cls import CLSContext, component_A, component_B, component_C, component_D, component_E, component_F, score

from bridge.prescreen.report import write_report as write_prescreen_report
from bridge.identity.report import write_report as write_identity_report
from bridge.cls.report import write_report as write_cls_report, compare_reports
```

Each step should be run from an executed notebook. Report modules provide table builders, plotting helpers, interpretation text, Markdown reports, JSON manifests, and saved figures. Notebook cells should display the same tables and figures that are saved into the `report/` artifact folder.

## Configuration Contract

YAML templates under `configs/` are editable parameter references for agent and notebook workflows. The main sections are:

| Section | Role |
| --- | --- |
| `dataset` | Run identifier and filename prefix. |
| `paths` | Query data, model assets, output directories, and optional comparison assets. |
| `prescreen` | Step1 whole-brain prescreening defaults. |
| `identity` | Step2 target class, reference labels, training, calibration, and selection settings. |
| `cls` | Step3 enabled components and component-specific parameters. |
| `comparison` | Optional protocol comparison metadata. |
| `report` | Output filenames and CLS weights. |

Paths are interpreted relative to the YAML file when they are not absolute.

## Step1: Prescreen

Step1 maps an in vitro query dataset against a whole-brain reference model and annotates cells as `RG_candidate` or `non_RG`.

Core outputs:
- full prescreened h5ad
- RG candidate h5ad subset
- scANVI probability table
- summary JSON
- notebook-visible report and saved report artifacts

Step1 interpretation describes global identity composition, RG enrichment, and exclusion of off-target or neuroblast-like populations. It is framed as in vitro prescreening rather than supervised benchmark evaluation.

## Step2: Identify

Step2 consumes the Step1 RG candidate subset and evaluates target-specific mDA progenitor identity.

Core outputs:
- candidate-bearing Step2 h5ad
- target reference artifact or symlink
- calibrated reference/query probabilities
- mean probability, standard deviation, entropy tables
- threshold JSON
- notebook-visible report and saved report artifacts

Step2 interpretation focuses on stable target convergence versus uncertain, transitional, or competing-fate cells.

## Step3: Score

Step3 consumes Step2 artifacts and scores developmental concordance through CLS components A-F.

Core outputs:
- component global JSON files
- component detail tables when available
- summary CSV
- manifest JSON
- notebook-visible report and saved report artifacts
- optional multi-protocol comparison report

The component-first API allows individual component calls for debugging or customization. `score(ctx)` remains the default full-run entry point.

## Validation Surface

Public validation is package-oriented and lightweight:

```bash
PYTHONPATH=src pytest -q
```

Full scientific validation depends on model assets, runtime data, and environment-specific notebooks managed outside Git history.
