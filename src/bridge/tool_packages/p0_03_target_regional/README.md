# P0-03 Target Identity & Regional Fidelity

This module converts a checksummed P0-02 V3 composition into three
product-relative candidate ratios. It only binds metadata and aggregates
precomputed counts; it never reads an expression matrix, reruns scRNA analysis,
performs spatial projection or assigns a biological role itself.

## Call surface

Use a `ToolRequestV2` with `tool_id=P0-03`, then call
`ToolRegistry.check_eligibility` followed by `ToolRegistry.run`. The equivalent
CLI commands are:

```bash
bridge-tool validate --request /absolute/path/to/request.json
bridge-tool run --request /absolute/path/to/request.json
```

The request requires exactly eleven checksummed JSON roles:

1. `product_case`
2. `product_definition_card`
3. `state_role_map`
4. `target_regional_assessment_spec`
5. `measurement_spec`
6. `cell_state_evidence_profile` (`v0.3`)
7. `qc_readiness_profile`
8. `biological_unit_manifest`
9. `biological_unit_assignment`
10. `annotation_vocabulary`
11. `reference_manifest`

Every role, Schema URI, object version, path and SHA-256 must match. The adapter
then closes ProductCase, ProductDefinition, MeasurementSpec, vocabulary,
reference, QC, selected DataView, observation set, analysis unit and
independence-group lineage before execution.

## External biology

P0-03 consumes the same `StateRoleMap` contract as P0-05; it does not define a
second model for that Schema URI. The shared map provides externally reviewed
product roles. `TargetRegionalAssessmentSpec` binds the exact map checksum and
provides every requested channel, the target-identity product-role set and the
explicit state-ID sets used for regional numerator/denominator membership.
Replacing a biological decision means supplying a new versioned object, not
changing Python.

The only normalized metric names are:

- `target_identity_fraction`;
- `regional_fidelity_fraction`;
- `whole_product_target_region_fraction`.

Each metric is published as an independent checksummed `MeasurementResultV2`
JSON. An `unknown`/`ood` upstream state produces `not_assessed` and null values.
A zero target-related denominator produces an `unavailable`, null regional
metric. No missing state is represented as zero.

The same atomic run directory also contains one
`TargetRegionalEvidenceResult`, which binds all eleven input checksums and all
metric artifact checksums. Identical reruns reuse bytes; drift fails closed.

All outputs remain `candidate/shadow`, `domain_score=null`. They are not
biological validation, safety, efficacy, potency, release or ranking claims.
See the detailed Tool Card at `src/bridge/tool_packages/cards/P0-03.md` and the
documentation-only request under `examples/requests/`.
