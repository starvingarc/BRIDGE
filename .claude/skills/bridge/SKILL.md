# bridge

Use this as the top-level coordination skill for work inside the BRIDGE repository.

## Purpose

This skill helps an agent:
- understand the BRIDGE Step 1 / Step 2 / Step 3 architecture
- route work to the right package area
- distinguish formal workflow code from supporting docs and configuration
- coordinate Step 2 identity work, Step 3 CLS work, and report generation

## Scope

- Step 1 is documented architecture only in the current public package.
- Step 2 maps to the `identity` package.
- Step 3 maps to the `cls`, `io`, and `workflows` packages.

## Repository landmarks

- `src/bridge/identity`: Step 2
- `src/bridge/cls`: Step 3 component logic
- `src/bridge/workflows`: executable workflow entrypoints
- `configs/`: public config templates
- `docs/`: concept and usage docs

## Coordination rule

If the task is:
- about candidate selection or Step 2 outputs, use `bridge-identity`
- about CLS execution or component prerequisites, use `bridge-cls`
- about public package structure, CLI, config, or docs, keep work at this top-level skill
