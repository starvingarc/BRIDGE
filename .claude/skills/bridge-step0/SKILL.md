# bridge-step0

Use this skill to initialize BRIDGE before a public demo run.

## Purpose

Step0 prepares the runtime context for BRIDGE:
- create or validate the `bridge` conda environment
- install BRIDGE
- validate or download model assets declared by `models/assets.json`
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

1. Inspect the repository root, `configs/`, `models/`, `docs/`, and `.claude/skills/`.
2. Create or validate the requested conda environment, defaulting to `bridge`.
3. Install BRIDGE in editable mode when operating from a source checkout.
4. Inspect `models/assets.json` and validate the expected model asset destinations.
5. If assets are missing, run `python scripts/download_model_assets.py --dry-run`, then ask before running the full download unless the user already requested automatic setup.
6. Validate that required model files exist under `models/` after download or manual placement.
7. Create the run root and an editable run config.
8. Print the next Step1 command with the user data path left explicit.

## Expected Outputs

- initialized run directory
- editable YAML config
- environment validation summary
- model asset validation summary

## Current Boundary

Do not claim downstream analysis is ready until required model assets exist locally. Report APIs are available package code, but public demo notebooks still need to be created from a verified run. If public object-storage assets are unavailable or downloads fail, report the missing asset URL and stop before running downstream steps. Never use private server paths, internal IPs, or user-specific paths as public asset URLs.
