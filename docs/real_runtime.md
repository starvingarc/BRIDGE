# Runtime Notes

This document describes the intended runtime model for BRIDGE in infrastructure-neutral terms.

## Runtime Model

BRIDGE supports two execution modes:
- notebook execution for released Step 1, Step 2, and Step 3 APIs
- artifact-driven reporting from previously generated Step 2 and Step 3 outputs

## Artifact Ownership

The report layer should consume structured BRIDGE artifacts rather than rely on notebook-local conventions.

Typical artifact groups include:
- Step 2 threshold and summary outputs
- Step 2 query/reference h5ad outputs
- Step 3 component-level JSON and detail tables
- report-level summary CSV and manifest JSON outputs

## Reproducibility Notes

- Runtime configuration should be explicit in notebooks or file-backed parameter templates.
- Reporting can consume precomputed artifacts and reuse existing Step3 outputs.
- Environment-specific paths and operational deployment details should be maintained outside the public repository.
