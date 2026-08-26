# P0-04 Developmental Compatibility

This directory contains the deterministic developmental-window evidence package.

## Interface at a glance

- **Input:** checksummed ProductCase, product definition, DevelopmentWindowSpec,
  DevelopmentStateMap, MeasurementSpec and P0-02 profile, with an optional
  declared timepoint series.
- **Output:** `DevelopmentalCompatibilityResult` with window, earlier, later,
  branch-shift and unresolved composition states.
- **Boundary:** alignment is relative to a user-supplied window; the package does
  not infer biological age, trajectory, maturation or a domain score.

## Documentation

- [Implementation, software, calls and current evidence](../../../../docs/tool-packages.md#p0-04)
- [Tool Card — authoritative runtime contract](../cards/P0-04.md)
- [Scientific task card](../../../../docs/bridge_spec_v0.1/developmental_compatibility_task_card.md)
- [Request example](../../../../examples/requests/p0_04_developmental_compatibility.json)
- [Validation record](../../../../docs/validation/p0_04_developmental_compatibility_v0.2.md)

Use `bridge-tool describe P0-04` for the installed version, schemas, environment
and registered method IDs.
