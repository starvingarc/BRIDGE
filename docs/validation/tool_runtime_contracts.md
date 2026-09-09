# Shared Tool Runtime Contracts: Validation History

This subject-level record preserves the complete dated receipts below.
Each receipt's inputs, source versions, test counts and scientific limits
apply to that historical run, not to the current main branch or a newly
qualified method/product. Consolidation changes organization and links only;
it does not combine evidence families or create a new validation result.

- [Structured Tool Runtime Contract Validation — 2026-08-13](#record-tool-runtime-structured-contracts-20260813)
- [Tool Runtime Contract Cleanup Validation](#record-tool-runtime-contract-cleanup-20260826)

<a id="record-tool-runtime-structured-contracts-20260813"></a>

## Structured Tool Runtime Contract Validation — 2026-08-13

### Biological question

This validation asks whether future Tool Packages can receive immutable, schema-bound upstream objects without weakening existing P0-01/P0-02 contracts. It does not test a biological hypothesis or produce a product-evaluation finding.

### Data, references and controls

Tests use synthetic paths, checksums, package specs, requests, adapter responses and JSON payloads only. No biological, private, locked, sealed or competitor data are used. Existing v0.1 schemas and the P0-01/P0-02 regression suite are the compatibility controls.

### Observed finding and interpretation

The source suite passed with v0.1 behavior and schema bytes stable while the v0.2 path rejected inline objects, relative paths, duplicate IDs/path aliases, nonexistent paths, directories, invalid checksums/media types, non-standard or duplicate-key JSON, version mismatches, unknown or violated input schemas, non-packaged adapters and mismatched result bindings. Registered legacy objects without a schema-defined version field remained eligible with external `object_version` metadata. Mixed v0.1/v0.2 registries selected the request model from `tool_id`; manually constructed SDK requests using the opposite envelope generation returned structured `tool_request_v1_required` or `tool_request_v2_required` refusals without resolving an adapter or executor. Synthetic successful v0.2 runs retained request, tool version, environment and registered result-schema bindings, carried a non-null schema-valid result, and were discarded if an input changed during execution—even when the adapter raised or returned an invalid type. Deprecated packages did not execute.

This evidence cannot establish scientific validity, package eligibility on real data, or any product claim. At the shared-runtime commit validated here, P0-08 and P0-09 were still unimplemented scaffolds; P0-08's later candidate implementation has its own validation record and does not retroactively change this infrastructure-only evidence.

### Engineering evidence

- Pre-change baseline: `PYTHONPATH=src .../.venv/bin/python -m pytest -q` — `192 passed, 3 warnings`.
- Focused contract/CLI/policy tests: `PYTHONPATH=src .../.venv/bin/python -m pytest -q tests/test_structured_runtime.py tests/test_cli.py tests/test_registry.py tests/test_contracts.py` — `104 passed`.
- Final source tests: `PYTHONPATH=src .../.venv/bin/python -m pytest -q` — `265 passed, 3 warnings`.
- CLI registry: `PYTHONPATH=src .../.venv/bin/python -m bridge.toolkit.cli list --json` — 12 Tool Packages listed.
- Knowledge gate: `PYTHONPATH=src .../.venv/bin/python -m bridge.toolkit.cli knowledge validate` — `valid=true`, no dangling method/source references.
- Repository gate: `PYTHONPATH=src .../.venv/bin/python tools/check_repository.py` — passed; implemented v0.2 adapters and result schemas resolve without adapter execution.
- v0.1 compatibility: fixed SHA-256 regression checks passed for the existing tool request, run and package schema files; schema export produced no diff in any existing v0.1 schema.
- Diff whitespace, compile and explicit v0.1 schema compatibility checks after second review hardening: passed.
- Packaging: the standard isolated wheel build passed and contained all four structured-runtime schemas. A diagnostic `--no-isolation` attempt could not load `setuptools.build_meta` from the shared venv; no shared-environment package was installed or changed.

### Remaining uncertainty and next scientific action

A future package-specific change must define and biologically review its object roles, result fields, units, sources, eligibility/refusal reasons and real-data validation. This shared runtime validation is not evidence that any scaffold package is ready to execute.


---

<a id="record-tool-runtime-contract-cleanup-20260826"></a>

## Tool Runtime Contract Cleanup Validation

**Date:** 2026-08-26
**Scope:** Agent-facing input discovery, exact runtime-helper consolidation and
shared configurable-contract ownership.
**Base:** `main` at `1476962b810fee8254858fabe95156fe4e4c71ee`

### Result

The additive `ToolInputContract` interface resolves for all 12 registered P0
packages. Existing request, run, result and scientific-state contracts remain
unchanged. P0-02 implementation code and P0-09 compiler, graph,
reconciliation and query code were not modified.

| Check | Result |
|---|---|
| Python 3.12 source suite | 1,225 passed; 8 existing dependency warnings |
| Tool discovery | 12 tools |
| Input-contract discovery | 12 contracts |
| Focused affected-module suite | 217 passed |
| Knowledge validation | valid; no dangling method or source references; 0 formal-eligible methods |
| Repository policy | passed |
| Static import/error checks | passed |
| Diff whitespace check | passed |
| Isolated wheel import | passed; imported from installed `site-packages` |
| Installed CLI/SDK smoke | list, describe, input-contract and structured validate/run refusal passed |

### Deterministic artifacts

| Artifact | SHA-256 |
|---|---|
| Built wheel | `e2c14e436ab3914f607b3a6cc2782ac2c64eebe2b188f731f94868dd1c9cb12d` |
| `tool_input_contract.schema.json` | `fd5c2a5223c70f5f47dcddf6be9956e1df4bf19b1e36c47ca2ee059ab9ea96d2` |
| `development_window_spec.schema.json` | `a33d9e6b245c0a5cd00c913b9469af41707303b9b56ba0a4afa8edf856696df1` |
| `state_role_map.schema.json` | `661a9e1d409e1f046f54d1d62432d334812ea090742735eee5f6b0ec1dbad8e6` |

Two clean wheel builds with a fixed build epoch matched byte for byte.
Two independent renders of each listed Schema matched the committed bytes.
The isolated validate/run smoke used a deliberately absent input asset and
returned the documented structured refusal `input_asset_not_found`.

### Scientific boundary

This validation establishes packaging and interface behavior only. It does not
freeze biological labels, roles, markers, thresholds or estimands; it does not
make a method formally eligible; and it does not make a domain score available.
