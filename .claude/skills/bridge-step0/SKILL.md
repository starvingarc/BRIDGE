# bridge-step0

Use this skill to initialize BRIDGE before a public demo run.

## Purpose

Step0 prepares the runtime context for BRIDGE:
- create or validate the `bridge` conda environment
- install BRIDGE
- validate model assets under `models/`
- create an initial run config and run directory

## Expected User Prompt

Claude Code:

```text
/bridge-step0 initialize BRIDGE in ./bridge-demo using env bridge
```

Codex:

```text
@bridge-step0 initialize BRIDGE in ./bridge-demo using env bridge
```

## Agent Responsibilities

1. Inspect the repository root, `configs/`, `models/`, and `docs/`.
2. Create or validate the requested conda environment, defaulting to `bridge`.
3. Install BRIDGE in editable mode when operating from a source checkout.
4. Validate model metadata and expected model directories under `models/`.
5. Create the run root and an editable run config.
6. Print the next Step1 command with the user data path left explicit.

## Expected Outputs

- initialized run directory
- editable YAML config
- environment validation summary
- model validation summary

## Current Boundary

Do not claim that final model assets, plotting functions, or polished notebooks are complete unless the files exist in the repository. If required model files are missing, report the expected `models/` location and stop before running downstream steps.
