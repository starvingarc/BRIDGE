# Structured Tool Runtime Contracts

## Biological question

How can future high-level P0 packages consume immutable upstream scientific objects without losing schema identity, version, role or checksum provenance? This branch establishes that shared runtime interface. It does not evaluate a biological sample and does not implement P0-08 or P0-09.

## Data, references and controls

Only synthetic request/spec/adapter fixtures are used. No private, locked, sealed, competitor or biological data are opened. Compatibility is controlled against the existing v0.1 Python models, generated schemas and P0-01/P0-02 tests.

## Finding and product meaning

The runtime can preserve a structured object's identity and checksum across a request and can bind an implemented package's successful or partial result to its declared schema. This supports traceable future package composition but supplies no scientific evidence, score, eligibility decision or product interpretation by itself.

## Scope

- Add frozen v0.2 package, request and run models plus `StructuredInputRef` and the two-method adapter protocol.
- Load v0.1 and v0.2 package specs together and keep v0.1 execution behavior unchanged.
- Select the CLI request contract after reading `tool_id`; expose corresponding unions through the Python SDK.
- Export and package four new public schemas while retaining all v0.1 schema bytes.
- Add repository policy, documentation and synthetic regression coverage.

## Non-goals

- Do not migrate P0-01 or P0-02 to v0.2.
- Do not implement, promote or scientifically validate P0-08 or P0-09.
- Do not add HTTP/MCP/job orchestration or accept inline structured payloads.
- Do not change domain-score or scientific-release policy.

## Decisions

- `tool_id` chooses the package spec before a request model is validated.
- Implemented v0.2 packages resolve only their declared packaged adapter; the central registry gains no new tool-ID dispatch branch for v0.2.
- Structured JSON inputs are schema-validated and checksum-snapshotted before adapter calls, then checked again after adapter eligibility and execution.
- Successful or partial v0.2 runs must preserve request, tool version, implementation state, environment and result-schema bindings and carry a schema-valid non-null result.
- `jsonschema` is a runtime dependency because validation occurs inside the registry rather than only in tests.
- Existing v0.1 models and schema files remain unchanged.

## Acceptance evidence

- [x] Baseline: `192 passed, 3 warnings` before edits.
- [x] Focused contract/CLI/policy suite after review hardening: `73 passed`.
- [x] Full source suite after final eligibility mutation regression: `234 passed, 3 warnings`.
- [x] CLI registry gate: 12 Tool Packages listed as JSON.
- [x] Knowledge validation: `valid=true`, no dangling method or source references.
- [x] Repository policy, runtime-binding and public/packaged schema parity gates after review hardening: passed.
- [x] Diff whitespace and explicit v0.1 schema compatibility checks after review hardening: passed.

## Remaining uncertainty and next scientific action

The adapter seam has only synthetic contract evidence. A separately scoped, biologically reviewed P0 package must define its real structured input roles, eligibility/refusal codes and result schema before scientific execution. P0-08 and P0-09 remain `scaffold`.
