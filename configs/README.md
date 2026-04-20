# Configs

This directory stores configuration templates and output naming conventions for formal BRIDGE workflows.

Current templates:
- `bridge.minimal.yaml`: smallest editable run template for a BRIDGE workflow
- `bridge.example.yaml`: fuller schema example for formal Step 2 and Step 3 runs
- `report-smoke.yaml`: report-only smoke config for public CLI validation

Fixture assets:
- `fixtures/minimal/`: tiny placeholder artifact set used for public dry-run validation
- `fixtures/report/`: tiny placeholder artifact set used for public report smoke validation

Environment export:
- `environments/pytorch-linux.yml`: sanitized export of the Linux `pytorch` conda environment used for BRIDGE server-side execution

The exported environment file keeps the package set but omits the machine-local `prefix` field and excludes local editable BRIDGE package entries.
