# Runtime Notes

This document describes the intended runtime model for BRIDGE without embedding deployment-specific infrastructure details.

## Runtime Model

BRIDGE supports two execution modes:
- direct workflow execution for released Step 2 and Step 3 modules
- artifact-driven reporting from previously generated Step 2 and Step 3 outputs

## Artifact Ownership

The report layer should consume structured BRIDGE artifacts rather than rely on notebook-local conventions.

Typical artifact groups include:
- Step 2 threshold and summary outputs
- Step 2 query/reference h5ad outputs
- Step 3 component-level JSON and detail tables
- report-level summary CSV and manifest JSON outputs

## Reproducibility Notes

- Runtime configuration should be explicit and file-based.
- Reporting should be able to consume precomputed artifacts without forcing recomputation.
- Environment-specific paths and operational deployment details should be maintained outside the public repository.
