# Tool Runtime Contract Cleanup

## Motivation

The 12 P0 packages are callable, but an Agent cannot retrieve one typed summary
of each module's accepted request shape. Several adapters also repeat identical
publication and legacy-request conversion code, and two product-context types
are owned by downstream scientific modules despite being consumed elsewhere.

## Scope

- Expose one versioned, machine-readable input contract for every P0 tool.
- Keep existing `describe`, `validate` and `run` behavior compatible; add a
  focused SDK and CLI discovery entry point.
- Consolidate repeated legacy-request conversion and publication helpers only
  where behavior, artifact layout and reason-code contracts are equivalent.
- Move shared StateRoleMap and DevelopmentWindowSpec contracts to the existing
  configurable product-context module while preserving their old imports.
- Remove operational hardware details from the product requirements document
  and keep the active-plan index aligned with current work.

## Non-goals

- No biological label, marker, threshold, role assignment or developmental
  interpretation is added to code.
- No request, result, Tool ID or existing public Schema is changed in place.
- No P0-02 scientific release work, P0-09 graph/compiler rewrite, orchestration
  framework, renderer or scoring contract is introduced.
- No module is promoted beyond its current candidate or shadow state.

## Frozen interfaces

- Existing ToolRequest, ToolRun, ToolPackageSpec and module-result references
  retain their current versions and behavior.
- Input-contract discovery is additive and returns a new
  `bridge://schemas/tool-input-contract/v0.1` object.
- Module-specific semantic binding remains the responsibility of each adapter;
  the discoverable contract describes the request envelope, role cardinality,
  accepted Schema references and object-version policy.
- Existing module import paths for StateRoleMap and DevelopmentWindowSpec remain
  valid aliases.

## Tasks

1. Add the input-contract model, public Schema, SDK function and CLI command.
2. Declare and test contracts for P0-01 through P0-12.
3. Extract exact publication and V1 conversion helpers without changing hashes,
   paths, reason codes or failure behavior.
4. Relocate the two shared product-context contracts with compatibility exports.
5. Update stable documentation and remove the completed contract-spine plan.

## Validation

- Contract discovery and public-Schema tests for all 12 tools.
- Focused adapter compatibility and publication tests.
- Full test suite, 12-tool discovery, schema-generation parity, knowledge
  validation, repository policy and diff checks.
- Wheel build and isolated installed-package smoke for list, describe,
  input-contract, validate and run entry points.

## Decisions and risks

- P0-02 remains untouched apart from current documentation because its pending
  work is biological review.
- P0-09 receives only a declarative input description; compiler, graph,
  reconciliation and query code remain unchanged.
- Cardinality discovery cannot replace cross-object semantic validation. Tool
  Cards and adapter reason codes remain authoritative for those bindings.
