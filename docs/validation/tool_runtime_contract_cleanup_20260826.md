# Tool Runtime Contract Cleanup Validation

**Date:** 2026-08-26
**Scope:** Agent-facing input discovery, exact runtime-helper consolidation and
shared configurable-contract ownership.
**Base:** `main` at `1476962b810fee8254858fabe95156fe4e4c71ee`

## Result

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

## Deterministic artifacts

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

## Scientific boundary

This validation establishes packaging and interface behavior only. It does not
freeze biological labels, roles, markers, thresholds or estimands; it does not
make a method formally eligible; and it does not make a domain score available.
