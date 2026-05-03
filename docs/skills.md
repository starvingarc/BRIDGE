# Skill Interface

BRIDGE exposes a repository-local skill interface through `.claude/skills`.

The skill interface is a structured guidance layer for coding agents and workflow-aware assistants that operate inside this repository. Runtime execution flows through the Python package, notebooks, and documented artifacts.

## Location

Skills live under:

```text
.claude/skills/
```

## Agent Demo Skills

The public demo path uses lowercase command names for compatibility:

- `bridge-step0`
  - initialize environment, model assets, config, and run directory
- `bridge-step1`
  - run whole-brain prescreening on one in vitro `.h5ad`
- `bridge-step2`
  - run mDA progenitor identity assessment from Step1 RG candidates
- `bridge-step3`
  - run component-first CLS scoring and summary generation from Step2 artifacts

For Claude Code, these are intended to be invoked as `/bridge-step0` through `/bridge-step3` when the repository skills are available. For Codex-oriented demos, docs show the analogous `@bridge-step0` through `@bridge-step3` prompts.

## Package-Oriented Skills

Current package-oriented skills:

- `bridge`
  - top-level coordination across the BRIDGE workflow surface
- `bridge-identity`
  - guidance for Step2 execution and validation
- `bridge-cls`
  - guidance for Step3 execution, prerequisites, and reporting

## What Skills Are For

Skills help an agent or advanced collaborator understand:
- which workflow surface is formal
- how package layers map onto BRIDGE workflow steps
- what inputs, outputs, and prerequisites matter
- how to reason about execution and reporting behavior
- which outputs are current artifact contracts versus future plotting/report polish

## Current Visualization Boundary

The Step0-Step3 skills may ask agents to create simple artifact summaries or notebook skeletons. They should not claim that polished plotting functions or rich biological interpretation templates already exist. Those are tracked in `docs/roadmap.md` and should be integrated after per-step plotting functions are supplied.
