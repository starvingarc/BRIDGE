# Configs

This directory stores public configuration templates and environment notes for formal BRIDGE workflows.

Current templates:
- `bridge.minimal.yaml`: smallest editable run template for a BRIDGE workflow
- `bridge.example.yaml`: fuller schema example for formal Step 2 and Step 3 runs

Environment export:
- `environments/pytorch-linux.yml`: sanitized Linux conda environment export for BRIDGE runtime setup

The exported environment file keeps the package set while leaving machine-local paths and editable package entries out of the public template.
