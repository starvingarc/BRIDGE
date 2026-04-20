# Skill Interface

BRIDGE exposes a repository-local skill interface through `.claude/skills`.

The skill interface is not part of the runtime package API. It is a structured guidance layer for coding agents and workflow-aware assistants that need to operate inside this repository.

## Location

Skills live under:

```text
.claude/skills/
```

## Current Skills

- `identity-run`
  - guidance for Step 2 execution and validation
- `cls-run`
  - guidance for Step 3 execution and component prerequisites
- `report-review`
  - guidance for interpreting and comparing Step 2 + Step 3 report outputs

## What Skills Are For

Skills help an agent or advanced collaborator understand:
- which workflow surface is formal
- how package layers map onto BRIDGE workflow steps
- what inputs, outputs, and prerequisites matter
- how to reason about execution and reporting behavior

## What Skills Are Not

Skills are not:
- executable package code
- replacements for the CLI
- substitutes for workflow configs

They are repository-local operational guidance that complements the package and docs.
