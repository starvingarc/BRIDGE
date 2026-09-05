# Agent Integration

> [!NOTE]
> BRIDGE currently provides deterministic P0 tools and the contracts needed to
> orchestrate them. The conversational Agent, Web workspace and deployment
> runtime remain separate work.

## Integration profile

`AgentIntegrationProfile` is a logical, machine-readable workflow description.
It declares which resources each tool step needs and how tool outputs feed later
steps. It is validated against the live `ToolRegistry` and
`ToolInputContract`, so a profile cannot silently drift from the packaged tool
version, request envelope, mode, role, Schema or cardinality.

- Python model: `bridge.toolkit.AgentIntegrationProfile`
- Public Schema:
  [`agent_integration_profile.schema.json`](../src/bridge/resources/schemas/agent_integration_profile.schema.json)
- Schema reference: `bridge://schemas/agent-integration-profile/v0.1`

A resource slot records ownership and logical compatibility:

| Source | Owner and use |
|---|---|
| `user_upload` | Data or structured information supplied through the user workflow |
| `system_resource` | Versioned reference, method, rule or policy selected by the deployment |
| `derived_output` | A named artifact from an earlier `producer_binding_id` |
| `agent_constructed` | A published BRIDGE object materialized from declared `depends_on_slots` and user-confirmed facts |

Slots use `resource_type=asset` or `structured_object`. An asset slot's
`asset_contract` only declares compatibility with the current tool input
contract: format, assay, input level, matrix semantics and required metadata
keys. It is not an asset locator. Structured-object slots declare a public
Schema and object version.

Profiles contain no runtime path, filename, checksum value, asset identifier,
catalog identifier, host or credential. At execution time, request-bound slots
are materialized with the existing `InputAsset` and `StructuredInputRef`
models, including absolute paths and checksums. A dependency-only derived asset
is read from its producer `ToolRun` and artifact manifest; it does not create a
second request or asset-resolution API.

The public JSON Schema enforces resource-type and ownership shape, plus direct
list-item uniqueness. Run `validate_agent_integration_profile` for invariants
that span records: unique slot and binding IDs, closed references, an acyclic
dependency graph, relative minimum/maximum cardinality and alignment with the
live tool registry. These cross-record checks are intentionally not duplicated
as a second static contract.

## Published profiles

| Profile | Tool path | Endpoint |
|---|---|---|
| [Single product](../examples/agent-integration/profiles/single-product.json) | P0-01 → P0-02 → P0-03/P0-04/P0-05/P0-06 → P0-08 → P0-09 → P0-10 → P0-11 | Local candidate export |
| [Comparison](../examples/agent-integration/profiles/comparison.json) | Two product-evidence bundles → P0-07 `method_runtime` | Descriptive comparison result |
| [Graft](../examples/agent-integration/profiles/graft.json) | P0-12 `not_provided` or `expression_analysis` | Independent graft result |

P0-03 contributes separate `target_identity` and `regional_fidelity`
DomainGateInputs to P0-08. They share the P0-03 MeasurementSpec and measurement
output set, so the single-product path uses five domain inputs and four
MeasurementSpecs. Because P0-03 and P0-04 receive the selected expression asset,
the profile also binds each tool's deployment-owned method specification; the
asset and method specification are treated as one executable input pair.

For the single-product profile, the user upload declares
`biological_unit_lineage` so P0-01 can emit the biological-unit manifest and
assignment required downstream. P0-01 does not rewrite an
`analysis_ready` matrix. After its QC result is available, the Agent constructs
the `qc-selected-expression` `InputAsset` wrapper around the exact same file and
checksum, adding only the published QC profile and selected DataView metadata.
P0-02 then emits two distinct artifacts used by later steps: the V3 aggregate
cell-state profile and the observation-level `cell_state_evidence` table. The
Agent uses that table when materializing P0-05 and P0-06 method inputs; it does
not infer observation states from the aggregate profile.

P0-09's `evidence_records` artifact is declared separately from the case graph
manifest so `ReportDraft.evidence_record_set_ref` is bound to the compiled
record set that the Agent actually reads.

The comparison profile selects P0-07's executable `method_runtime` and binds
its case-specific method input plus a deployment-owned method specification.
Its result remains descriptive and does not enter the single-product
claim/export chain. The graft path does not backfill pre-transplant evidence.

`GraftCase` is user-supplied specimen, animal, timepoint and linkage metadata;
the Agent does not infer it from the graft expression matrix.

`measurement_spec_slot_id` is a top-level request binding, distinct from
`object_inputs`. The single-product profile opts into it for P0-01 and binds
the required P0-02 measurement specification explicitly. The live tool input
contract remains authoritative for whether this field is optional, required or
forbidden. The profile validates the supported MeasurementSpec Schema and
version. The current request envelope carries only an opaque
`measurement_spec_ref`, so step validation can require its presence but cannot
bind that deployment identifier to a logical slot without a deployment-owned
resolver; tool eligibility remains authoritative for the resolved object.

## Validate and run one step

The reference runner is deliberately not installed as a product CLI. It has two
commands:

```bash
python examples/agent-integration/reference_runner.py \
  validate-profile \
  --profile examples/agent-integration/profiles/single-product.json

python examples/agent-integration/reference_runner.py \
  run-step \
  --profile examples/agent-integration/profiles/single-product.json \
  --binding claim-verifier \
  --request <materialized-request.json>
```

`run-step` accepts an already materialized `ToolRequest` or
`ToolRequestV2`. It checks the selected profile binding, calls the existing
eligibility check, and then calls the existing tool runtime. It does not resolve
catalogs, create scientific objects, call a model, fill missing fields or alter
evidence states. Missing system or Agent-constructed resources fail with
`unresolved_input_slot`.

The profile's `artifact_kind` names the producer's checksummed artifact for
connecting steps. The actual `ToolRun`, result Schema, artifact manifest and
checksum remain the execution record.

## Agent responsibilities

1. Select a published profile and validate it against the installed package.
2. Ask for missing user facts and resolve deployment-owned system resources.
3. Materialize every Agent-constructed object against its published Schema,
   preserving its declared dependencies and provenance.
4. Build the exact request, then call `validate_profile_request`,
   `validate_request` and `run_tool` in that order.
5. Preserve `not_assessed`, `unavailable`, `unknown`, `negative`,
   `alert`, units, denominators and evidence references without reinterpretation.

See the [Tool Package guide](tool-packages.md) for module-specific contracts and
the [local runtime guide](local-agent-runtime.md) for upload, approval and
workflow-event boundaries.

## Scientific boundary

The profiles describe engineering connectivity only. P0 methods retain their
published `candidate` or `shadow` status; `domain_score` remains `null`
until a separate ScoreContract and scientific release process are complete.
