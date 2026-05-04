<p align="center">
  <img src="docs/assets/bridge-overview.png" alt="BRIDGE workflow overview" width="100%">
</p>

<p align="center">
  <img alt="Status" src="https://img.shields.io/badge/status-research%20software-8fb8f7?style=flat-square">
  <img alt="Version" src="https://img.shields.io/badge/version-0.1.0-f2b8a8?style=flat-square">
  <img alt="Python" src="https://img.shields.io/badge/python-3.10%2B-2f6f68?style=flat-square">
  <a href="docs/formal_workflows.md"><img alt="Docs" src="https://img.shields.io/badge/docs-workflows-5bbfb1?style=flat-square"></a>
  <a href="docs/agent_demo.md"><img alt="Demo" src="https://img.shields.io/badge/demo-agent%20workflow-7f6bb2?style=flat-square"></a>
</p>

# BRIDGE

**Brain-referenced developmental guidance for in vitro cell products.**

<em>🌉 From candidate discovery to developmental concordance scoring.</em>

BRIDGE is a notebook-first framework for asking a careful question: <em>do these in vitro cells resemble the in vivo developmental state they are meant to approximate?</em> It routes cells through reference-guided prescreening, target identity assessment, and component-level concordance scoring, then leaves behind visible evidence for review.

| What BRIDGE keeps visible | Why it matters |
| --- | --- |
| **Reference context** | Candidate cells are evaluated against in vivo developmental atlases, not in isolation. |
| **Notebook-native evidence** | Figures, tables, interpretations, and manifests stay together in executed notebooks. |
| **Component-level scoring** | CLS separates identity, expression, transferability, neighborhood, trajectory, and regulon axes instead of hiding them in one number. |

## ✨ Workflow

| Step | Role | Output |
| --- | --- | --- |
| **Step0** | Prepare environment, config, model assets, and run directory. | Ready-to-run workspace |
| **Step1** | Map one in vitro `.h5ad` against a whole-brain reference. | RG candidate annotations and Step1 report |
| **Step2** | Assess mDA progenitor identity with calibrated probability and uncertainty. | Candidate-bearing data, thresholds, probability tables, Step2 report |
| **Step3** | Score developmental concordance across CLS components A-F. | Component scores, weighted CLS, single-dataset and protocol-comparison reports |

## 🚀 Agent Use (Recommended)

The public demo flow is designed to be driven by a coding agent. For a first-time install, send this to Claude Code, Codex, or another agent:

```text
Help me install https://github.com/starvingarc/BRIDGE
```

Then copy the step command you need. Use `/...` in Claude Code and `@...` in Codex.

| Skill | Claude Code | Codex | Purpose |
| --- | --- | --- | --- |
| `bridge-step0` | `/bridge-step0` | `@bridge-step0` | Initialize environment, assets, config, and run directory. |
| `bridge-step1` | `/bridge-step1` | `@bridge-step1` | Prescreen an in vitro dataset and write a notebook-native Step1 report. |
| `bridge-step2` | `/bridge-step2` | `@bridge-step2` | Run target identity assessment and write a Step2 report. |
| `bridge-step3` | `/bridge-step3` | `@bridge-step3` | Run CLS scoring and optional protocol comparison. |

Full copy-paste demo prompts are in [docs/agent_demo.md](docs/agent_demo.md). Model assets are declared in [models/assets.json](models/assets.json) and fetched separately from public object storage.

## 🧪 Manual Use

```bash
pip install git+https://github.com/starvingarc/BRIDGE.git
# or, from a cloned source tree:
pip install -e ".[workflow]"
```

Notebook entry points:

```python
from bridge.prescreen import prescreen
from bridge.identity import identify
from bridge.cls import CLSContext, component_A, component_B, component_C, component_D, component_E, component_F, score

from bridge.prescreen.report import write_report as write_prescreen_report
from bridge.identity.report import write_report as write_identity_report
from bridge.cls.report import write_report as write_cls_report, compare_reports
```

Each step is designed to be called from a notebook, with report functions that render figures and tables in the notebook while also saving reproducible artifacts under `report/`.

## 🗺️ Explore

- [Agent demo script](docs/agent_demo.md)
- [Skills](docs/skills.md)
- [Formal workflows](docs/formal_workflows.md)
- [Thesis-to-code mapping](docs/thesis_to_code.md)
- [Roadmap](docs/roadmap.md)

## 🛠️ Development

```bash
PYTHONPATH=src pytest -q
```

```text
src/bridge/        Python package
configs/           public config templates
models/            model metadata and asset entry point
notebooks/         formal notebook examples and placeholders
docs/              workflow documentation and roadmap
.claude/skills/    repository-local Step0-Step3 skills
```

## Citation

BRIDGE is research software under active development. If you use it in a study, please cite the repository and include the commit hash used for analysis.
