# Skill Interface

BRIDGE exposes repository-local skills through `.claude/skills`. These skills are the public Step0-Step3 workflow used in the demo; there is no separate agent-demo skill layer.

## Location

Skills live under:

```text
.claude/skills/
```

## Available Skills

| Skill | Claude Code | Codex | Purpose |
| --- | --- | --- | --- |
| `bridge-step0` | `/bridge-step0` | `@bridge-step0` | Initialize environment, model assets, config, and run directory. |
| `bridge-step1` | `/bridge-step1` | `@bridge-step1` | Run whole-brain prescreening and call the Step1 report API. |
| `bridge-step2` | `/bridge-step2` | `@bridge-step2` | Run mDA progenitor identity assessment and call the Step2 report API. |
| `bridge-step3` | `/bridge-step3` | `@bridge-step3` | Run component-first CLS scoring, single-dataset reports, and optional protocol comparison. |

## What Skills Are For

Skills help an agent or advanced collaborator understand:
- what inputs each workflow step requires
- which notebook API to call for that step
- what artifacts each step should produce
- how to write the figures, Markdown report, JSON manifest, and English interpretation after each core workflow

## Report APIs

Recommended notebook imports:

```python
from bridge.prescreen.report import write_report as write_prescreen_report
from bridge.identity.report import write_report as write_identity_report
from bridge.cls.report import write_report as write_cls_report, compare_reports
```

The report APIs are available package code. They produce standard figure files, tables, Markdown reports, JSON manifests, and concise interpretation text. Formal public example notebooks remain a roadmap item.

## Environment Expectations

Step0 should install demo extras from a source checkout with `python -m pip install -e ".[demo]"` and verify imports for `torch`, `anndata`, `scanpy`, and `scvi` before downstream notebook steps.
