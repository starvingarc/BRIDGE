# Skill Interface

BRIDGE exposes a repository-local skill interface through `.claude/skills`.

The skill interface is a structured guidance layer for coding agents and workflow-aware assistants that operate inside this repository. Runtime execution still flows through the Python package and CLI.

## Location

Skills live under:

```text
.claude/skills/
```

## Current Skills

- `bridge`
  - top-level coordination across the released BRIDGE workflow surface
- `bridge-identity`
  - guidance for Step 2 execution and validation
- `bridge-cls`
  - guidance for Step 3 execution, prerequisites, and reporting

## What Skills Are For

Skills help an agent or advanced collaborator understand:
- which workflow surface is formal
- how package layers map onto BRIDGE workflow steps
- what inputs, outputs, and prerequisites matter
- how to reason about execution and reporting behavior

## How Skills Fit With the Package

Skills complement the package and docs:
- use the CLI for execution
- use YAML configs for reproducible workflow parameters
- use skills for repository-local guidance, review checklists, and workflow interpretation
