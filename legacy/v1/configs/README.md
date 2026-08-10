# Configs

This directory stores public configuration templates for notebook-driven BRIDGE workflows.

Templates:
- `bridge.minimal.yaml`: compact editable template for a single-dataset run
- `bridge.example.yaml`: fuller schema example covering Step1, Step2, Step3, reporting, and optional comparison

Environment export:
- `environments/pytorch-linux.yml`: sanitized Linux conda environment export for BRIDGE runtime setup

Paths in YAML templates are intended to be edited by the user or agent. Machine-local paths, private storage locations, and downloaded model binaries belong outside Git history.
