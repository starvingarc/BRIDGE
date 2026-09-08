# P0-05 Off-target Control

This directory contains three exact modes for declared-denominator off-target
accounting: compatibility aggregation, transparent method execution, and genuine
P0-02 V3 hard-count accounting without a caller-supplied mass bundle.

## Interface at a glance

- **Input:** `legacy_aggregation` uses the original six objects;
  `method_runtime` uses ten objects; `hard_count_accounting` uses ProductCase,
  ProductDefinitionCard, StateRoleMap, OffTargetAssessmentSpec, a P0-02 V3
  CellStateEvidenceProfile, BiologicalUnitManifest and confirmed
  BiologicalUnitAttestationReceipt. Any mode may add one authorized
  `MeasurementSpecV2`.
- **Output:** P0-05 v0.6.0 returns the
  `bridge://schemas/off-target-control-result/v0.1` union. Existing modes keep
  the unchanged `OffTargetControlProfileV2` payload; method mode also keeps its
  method bundle and candidate figures. Hard-count mode returns
  `OffTargetHardCountProfileV1`, no method bundle, and `visualizations=[]`.
- **Boundary:** “control” means evidence accounting. It is not physical removal,
  a purity estimate, a safety conclusion, a release decision or a domain score.

Hard-count mode preserves the complete producer composition but counts only the
`consensus_supported_only` rows through the external StateRoleMap. Source-specific
rows are traceability records and are never added across sources. The four role
counts plus every non-consensus reconciliation bucket close to selected-view N.
Single-source support, source conflict, unknown, OOD and unavailable remain
separate. `total_soft_mass` is null and `mass_state=unavailable`; whole-view
counts do not create per-unit or bootstrap estimates. Open-set assessment and rare
detection remain `not_assessed`, and zero counts never establish absence.

The manifest and receipt provide ownership and lineage parity with genuine V3
execution. Runtime checks their exact ProductCase/DataView/manifest/assignment and
observation bindings, but does not authenticate the attestor or establish biological
independence, truth, independent review or release authority.

## Calling the mode

Use `bridge-tool input-contract P0-05` (or
`ToolRegistry.load_default().describe_input("P0-05")` in the Python SDK)
and select the `hard_count_accounting` role set. The mode ID is a discovery label,
not a request field: the runtime selects it from the exact object-role and schema
combination. Validate and run the resulting `ToolRequestV2` with:

```bash
bridge-tool validate --request /absolute/path/to/p0_05_hard_count_request.json
bridge-tool run --request /absolute/path/to/p0_05_hard_count_request.json
```

A minimal logical request contains no assets, parameters, evidence bundle or method
objects:

```json
{
  "tool_id": "P0-05",
  "tool_version": "0.6.0",
  "input_mode": "hard_count_accounting (discovery only)",
  "required_object_roles": [
    "product_case",
    "product_definition_card",
    "state_role_map",
    "off_target_assessment_spec",
    "cell_state_evidence_profile",
    "biological_unit_manifest",
    "biological_unit_attestation_receipt"
  ],
  "optional_object_roles": ["measurement_spec"]
}
```

An authorized hard-count MeasurementSpec declares exactly four metrics. The
accounting metric is `inferred` and carries the complete typed accounting object;
soft mass, identity unknown and rare-state detection remain visible as
`unavailable` MeasurementResultV2 records with null values. Without the spec,
no measurement artifacts are emitted.

## Documentation

- [Tool Card — authoritative runtime contract](../cards/P0-05.md)
- [Scientific task card](../../../../docs/bridge_spec_v0.1/off_target_control_task_card.md)
- [Implementation, software, calls and current evidence](../../../../docs/tool-packages.md#p0-05)
- [Existing request example](../../../../examples/requests/p0_05_off_target_control.json)

Use `bridge-tool describe P0-05` for the installed version, result schema,
environment and registered method IDs.
