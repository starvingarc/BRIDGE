# Configs

This directory stores configuration templates and output naming conventions for formal BRIDGE workflows.

Planned v1 content:
- workflow config templates for Step 2 and Step 3
- output directory conventions
- model-loading references

Current templates:
- `bridge.minimal.yaml`: smallest editable run template for a BRIDGE workflow
- `bridge.example.yaml`: fuller schema example for formal Step 2 and Step 3 runs

Environment export:
- `environments/pytorch-linux.yml`: sanitized export of the Linux `pytorch` conda environment used for BRIDGE server-side execution

The exported environment file keeps the package set but omits the machine-local `prefix` field and excludes local editable BRIDGE package entries.
