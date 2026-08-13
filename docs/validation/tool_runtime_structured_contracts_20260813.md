# Structured Tool Runtime Contract Validation — 2026-08-13

## Biological question

This validation asks whether future Tool Packages can receive immutable, schema-bound upstream objects without weakening existing P0-01/P0-02 contracts. It does not test a biological hypothesis or produce a product-evaluation finding.

## Data, references and controls

Tests use synthetic paths, checksums, package specs, requests, adapter responses and JSON payloads only. No biological, private, locked, sealed or competitor data are used. Existing v0.1 schemas and the P0-01/P0-02 regression suite are the compatibility controls.

## Observed finding and interpretation

The source suite passed with v0.1 behavior and schema bytes stable while the v0.2 path rejected inline objects, relative paths, nonexistent paths, directories, invalid checksums/media types/JSON, unknown or violated input schemas, non-packaged adapters and mismatched result bindings. Mixed v0.1/v0.2 registries selected the request model from `tool_id`. Synthetic successful v0.2 runs retained request, tool version, environment and registered result-schema bindings, carried a non-null schema-valid result, and were discarded if an input changed during execution.

This evidence cannot establish scientific validity, package eligibility on real data, or any product claim. P0-08 and P0-09 remain unimplemented scaffolds.

## Engineering evidence

- Pre-change baseline: `PYTHONPATH=src .../.venv/bin/python -m pytest -q` — `192 passed, 3 warnings`.
- Focused contract/CLI/policy tests: `PYTHONPATH=src .../.venv/bin/python -m pytest -q tests/test_structured_runtime.py tests/test_cli.py tests/test_registry.py tests/test_contracts.py` — `73 passed`.
- Final source tests: `PYTHONPATH=src .../.venv/bin/python -m pytest -q` — `234 passed, 3 warnings`.
- CLI registry: `PYTHONPATH=src .../.venv/bin/python -m bridge.toolkit.cli list --json` — 12 Tool Packages listed.
- Knowledge gate: `PYTHONPATH=src .../.venv/bin/python -m bridge.toolkit.cli knowledge validate` — `valid=true`, no dangling method/source references.
- Repository gate: `PYTHONPATH=src .../.venv/bin/python tools/check_repository.py` — passed; this now loads all package specs and resolves implemented v0.2 adapters and result schemas without executing adapters.
- v0.1 compatibility: fixed SHA-256 regression checks passed for the existing tool request, run and package schema files; schema export produced no diff in any existing v0.1 schema.
- Diff whitespace and explicit v0.1 schema compatibility checks after review hardening: passed.

## Remaining uncertainty and next scientific action

A future package-specific change must define and biologically review its object roles, result fields, units, sources, eligibility/refusal reasons and real-data validation. This shared runtime validation is not evidence that any scaffold package is ready to execute.
