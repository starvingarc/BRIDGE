# P0-05 Off-target Control package

P0-05 is a deterministic, JSON-only candidate package. It does not read or
recompute an expression matrix. It groups a precomputed whole-product state
composition using an external, versioned role map and applies external
rare-state calibration limits.

## Call

```python
from bridge.toolkit import validate_request, run_tool

eligibility = validate_request(request)
run = run_tool(request)
```

```bash
bridge-tool validate --request /absolute/path/to/request.json
bridge-tool run --request /absolute/path/to/request.json
```

The request is `ToolRequestV2` and must contain exactly six immutable
`application/json` inputs:

| Role | Object version | Required binding |
|---|---:|---|
| `product_case` | `0.1.0` | ProductDefinition, assay and MeasurementSpec identity |
| `product_definition_card` | `0.1.0` | external StateRoleMap reference and supported assay |
| `state_role_map` | `0.1.0` | state IDs to generic product roles; evidence class and direction remain caller-owned |
| `off_target_assessment_spec` | `0.1.0` | map checksum, denominator ID, allowed unknown reasons and rare-state calibration limits |
| `cell_state_evidence_profile` | `0.2.0` | P0-02 profile ID, assay, MeasurementSpec and observation count |
| `off_target_evidence_bundle` | `0.1.0` | checksummed upstream objects, denominator, precomputed state/unknown observations and calibration records |

Every input reference declares an absolute regular-file path, Schema URI,
object version, media type and SHA-256. Expression assets, top-level
MeasurementSpecs, arbitrary parameters and V1 requests are refused.

## Output

A successful run writes one checksummed
`off_target_control_profile.json` and returns the same
`OffTargetControlProfile` in `ToolRunV2.result`. It contains:

- exact refs and hashes for every defining input;
- the primary denominator;
- four generic role-composition rows with soft mass, observed count, fraction,
  assessment state and exclusion state;
- caller-declared unknown-reason rows;
- one result per caller-declared rare-state rule;
- `evidence_state=shadow`, `score_state=unavailable` and
  `domain_score=null`.

Fractions are withheld when composition coverage is incomplete. Zero
observations are always paired with `cannot_exclude` or the explicit
`not_detected_above_lod` state; they never establish biological absence.
Missing or insufficient calibration returns `cannot_exclude` or
`not_assessed` according to the external assessment spec.

## Boundary

The implementation contains only generic role and result-state enums. State
identities, product-role assignments, evidence classes, evidence directions,
unknown-reason vocabulary and numerical thresholds are external versioned
inputs. P0-05 does not validate biological truth, fit an OOD model, rerun
single-cell analysis, estimate a clinical risk or make efficacy, safety,
potency, GMP-release or product-ranking claims.

See `examples/requests/p0_05_off_target_control.json`, the packaged Tool Card
and `docs/bridge_spec_v0.1/off_target_control_task_card.md`.
