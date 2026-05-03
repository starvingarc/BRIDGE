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
| `bridge-step1` | `/bridge-step1` | `@bridge-step1` | Run whole-brain prescreening on one in vitro `.h5ad`. |
| `bridge-step2` | `/bridge-step2` | `@bridge-step2` | Run mDA progenitor identity assessment from Step1 RG candidates. |
| `bridge-step3` | `/bridge-step3` | `@bridge-step3` | Run component-first CLS scoring and summary generation from Step2 artifacts. |

## What Skills Are For

Skills help an agent or advanced collaborator understand:
- what inputs each workflow step requires
- which notebook API to call for that step
- what artifacts each step should produce
- which outputs are current artifact contracts versus future plotting/report polish

## Current Visualization Boundary

The Step0-Step3 skills may ask agents to create simple artifact summaries or notebook skeletons. They should not claim that polished plotting functions or rich biological interpretation templates already exist. Those are tracked in `docs/roadmap.md` and should be integrated after per-step plotting functions are supplied.
