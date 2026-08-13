# P0-08 Evidence Sufficiency

## Biological question

For one versioned ProductCase and up to five P0 domains, determine whether already-produced evidence records are assessable and sufficiently supported for their declared raw-evidence use. P0-08 does not decide whether a product is biologically good or bad.

No real product case is evaluated by the packaged fixture. The executable implementation is an engineering candidate only; it does not freeze a MeasurementSpec, ScoreContract, state definition, threshold, method, environment, or scientific release.

## Contract

| Field | Value |
|---|---|
| Tool ID | `P0-08` |
| Package version | `0.2.0` |
| Runtime state | `implemented` |
| Scientific state | `candidate` |
| EnvironmentSpec | `ENV-EVIDENCE-v0.1` (`proposed`) |
| Input envelope | `bridge://schemas/tool-request/v0.2` |
| Output envelope | `bridge://schemas/tool-run/v0.2` |
| Result schema | `bridge://schemas/evidence-sufficiency-run-result/v0.1` |
| Adapter | `bridge.tool_packages.p0_08_evidence_sufficiency.adapter:adapter` |

The package is available through the existing entry points:

```bash
bridge-tool describe P0-08 --json
bridge-tool validate --request /absolute/path/request.json
bridge-tool run --request /absolute/path/request.json
```

```python
from bridge.toolkit import api
from bridge.toolkit.contracts import ToolRequestV2

request = ToolRequestV2.model_validate(payload)
eligibility = api.validate_request(request)
run = api.run_tool(request)
```

CLI and SDK use the same models, adapter, eligibility rules and result envelope.

## Request envelope

| Field | Type | Required behavior |
|---|---|---|
| `request_id` | string | Operational identifier; excluded from the deterministic scientific run identity. |
| `tool_id` | literal `P0-08` | Selects this package. |
| `tool_version` | string or null | When declared, must equal `0.2.0`. |
| `output_dir` | absolute path | Receives one immutable `<run_id>/` bundle and must not contain an input. |
| `assets` | list | Must be empty; P0-08 never reads expression assets. |
| `measurement_spec_ref` | null | Must be null; MeasurementSpecs arrive only as structured objects. |
| `parameters` | object | Must be empty; callers cannot change scientific rules. |
| `random_seed` | integer | Accepted for envelope parity, recorded in identity, and never used by the gate. |
| `object_inputs` | list of `StructuredInputRef` | One gate rule plus one to five domain bindings and their immutable upstream records. |

Every `StructuredInputRef` requires `input_id`, exact `role`, exact `schema_ref`, `object_version`, an absolute `path`, a lowercase 64-character `sha256`, and `media_type=application/json`. Inline payloads, symlinks, non-files, checksum drift, invalid JSON and alternate caller-authored gate rules are rejected. After checksum verification, every string in every structured JSON payload is recursively screened before model validation. Absolute POSIX, Windows drive-letter and UNC references; home-relative references using tilde, HOME, USERPROFILE or HOMEPATH variables; any embedded `file://` URI; credential-bearing URLs; password, API-key, secret, token, access-token, auth, authorization or credential assignments; bearer credentials; and common GitHub/OpenAI/AWS token forms fail eligibility as `unsafe_scientific_reference`. Ordinary `bridge://` identifiers, credential-free `http://`/`https://` URLs and scientific slash text remain legal.

| `StructuredInputRef` field | Type | Meaning |
|---|---|---|
| `input_id` | non-empty string | Request-local identifier used by domain bindings; unique across the request. |
| `role` | exact role string | Selects the expected object model and cardinality. |
| `schema_ref` | exact URI | Public schema governing the referenced JSON object. |
| `object_version` | non-empty string | Must agree with the payload's declared object/legacy version. The versionless QCReadinessProfile and MeasurementResult schemas accept only the adapter-owned `0.1.0` contract version. |
| `path` | absolute local path | Read-only JSON file; no inline or network payload. |
| `sha256` | lowercase 64-hex string | Hash of the exact immutable source bytes, checked before and after execution. |
| `media_type` | `application/json` | Other media types fail eligibility. |

| Role | Cardinality | Schema | Binding |
|---|---:|---|---|
| `gate_rule_spec` | exactly 1 | `bridge://schemas/evidence-sufficiency-gate-rule-spec/v0.1` | Bytes and checksum must equal the packaged candidate rule. |
| `domain_gate_input` | 1..5 | `bridge://schemas/domain-gate-input/v0.1` | One profile per object; non-null domains are unique. |
| `measurement_spec` | 0..5 | `bridge://schemas/measurement-spec/v0.1` | Selected by `measurement_spec_input_id`. |
| `qc_readiness_profile` | 0..5 | `bridge://schemas/qc-readiness-profile/v0.1` | Selected by `qc_profile_input_id`. |
| `measurement_result` | 0..N | `bridge://schemas/measurement-result/v0.1` | IDs occur in `measurement_result_input_ids`. |
| `validation_record` | 0..N | `bridge://schemas/evidence-validation-record/v0.1` | IDs occur in `validation_record_input_ids`. |
| `prior_applicability_record` | 0..N | `bridge://schemas/prior-applicability-record/v0.1` | IDs occur in `prior_record_input_ids`. |
| `sensitivity_record` | 0..N | `bridge://schemas/evidence-sensitivity-record/v0.1` | IDs occur in `sensitivity_record_input_ids`. |

`DomainGateInput` binds a versioned ProductCase, ProductDefinition, P0 domain, MeasurementSpec, QC profile, upstream MeasurementResults, validation/prior/sensitivity records, method and prior requirements, required sensitivity kinds, task validation state, evidence/provenance references, and the optional provenance-only `score_contract_ref`. Null scientific bindings are legal and produce `not_assessed`; dangling or wrong-role IDs are malformed. Every non-null ProductCase pointer across the request must be identical in object ID, version and provenance-reference set; the same full-pointer rule applies independently to ProductDefinition. Each `domain_gate_input_id` is unique. MeasurementSpec, QC profile and MeasurementResult logical IDs are unique across distinct request objects; callers reuse one input reference when multiple domains share an object. Validation, prior and sensitivity logical IDs may repeat only inside one Evidence Family, where exact content duplicates collapse and non-identical required content becomes a scientific conflict. Reusing one such logical ID across Evidence Families is an eligibility failure.

### Gate rule fields

| Field | Type | Required | Source and behavior |
|---|---|---:|---|
| `gate_rule_spec_id` | literal | yes | Packaged value `GATE-EVIDENCE-SUFFICIENCY-v0.1`. |
| `object_version` | literal `0.1.0` | yes | Must match `StructuredInputRef.object_version`. |
| `status` | `candidate` or `frozen` | yes | Packaged release is `candidate`; alternate bytes are rejected even if fields validate. |
| `created_at` | UTC datetime | yes | Version timestamp, never the runtime wall clock. |
| four `*_method_id` fields | literals | yes | Bind the deterministic engine/matcher, reason registry and legacy checker records. |
| `reason_code_catalog_ref` | literal URI | yes | Binds the 45-code packaged catalog. |
| `applicable_domains` | five-domain array | yes | Exact enum order, without duplicates. |
| `precedence` | four-state tuple | yes | Exact order `not_assessed`, `insufficient`, `limited`, `sufficient`. |
| `score_policy` | literal | yes | Forces null/unavailable score behavior. |

### Domain binding fields

| Field | Type | Required | Source and behavior |
|---|---|---:|---|
| `domain_gate_input_id` | namespaced string | yes | Stable upstream binding ID. |
| `object_version` | literal `0.1.0` | yes | Binding object version. |
| `created_at` | UTC datetime | yes | Copied to the resulting profile; no wall-clock substitution. |
| `product_case` | `VersionedObjectPointer` or null | yes | Upstream ProductCase ID/version/provenance; null is valid `not_assessed`. |
| `product_definition` | `VersionedObjectPointer` or null | yes | Reviewed product definition; when non-null its ID must occur in the bound MeasurementSpec's applicable product cards. Null is valid `not_assessed`. |
| `domain_id` | P0 domain enum or null | yes | One of the five P0 domains; null is valid `not_assessed`. |
| `measurement_spec_input_id` | string or null | yes | Selects one role-correct MeasurementSpec object. |
| `qc_profile_input_id` | string or null | yes | Selects one role-correct QCReadinessProfile whose assay and MeasurementSpec status agree with the bound MeasurementSpec. |
| four `*_input_ids` lists | unique string arrays | yes | Select MeasurementResult, validation, prior and sensitivity records by request-local ID. |
| `method_requirement` | required/not_required/not_assessed | yes | Copied from the reviewed MeasurementSpec-side requirement. |
| `prior_requirement` | required/not_required/not_assessed | yes | Copied from the reviewed MeasurementSpec-side requirement. |
| `required_sensitivity_kinds` | unique enum array | yes | Upstream reviewed requirements; P0-08 never invents the list. |
| `task_validation_state` | frozen/candidate/not_assessed | yes | Upstream domain-task validation conclusion. |
| `score_contract_ref` | string or null | yes | Provenance only; ignored for scoring in this release. |
| `evidence_refs` | unique string array | yes | Upstream Evidence IDs copied to traceable outputs. |
| `provenance_refs` | non-empty unique string array | yes | Internal lineage; it does not alter a gate. |

`VersionedObjectPointer` contains non-empty `object_id`, `object_version` and `provenance_refs`. All identifier/reference strings are stripped and all declared lists reject duplicates. Pointer provenance order is set-like for identity, but changing its membership creates a different pointer and fails cross-domain eligibility.

### Validation record fields

| Field group | Type | Source and behavior |
|---|---|---|
| `validation_record_id`, `object_version`, `created_at` | ID/version/UTC datetime | Immutable upstream record identity. |
| `measurement_spec_ref` | string | Must equal the bound MeasurementSpec ID. |
| `method_id`, `method_version`, `tool_ref`, `environment_spec_ref` | strings | Exact executed method/tool/environment lineage; `tool_ref` must occur in the non-empty bound MeasurementSpec tool list. |
| `evidence_family_id`, `required_for_interpretation` | string, boolean | Family de-duplication and gate participation. |
| `method_kind` | learned/deterministic | Only a frozen deterministic record can establish `method_requirement=not_required`. |
| `validation_state`, `environment_state` | frozen/candidate/not_assessed | Upstream review conclusions, not recomputed. |
| `context_of_use_ref`, `context_of_use_state` | string, enum | Required applicability conclusion. |
| `source_family_ref`, `source_holdout_state` | string, coverage enum | Source-family holdout conclusion. |
| `modality`, `modality_holdout_state` | string, coverage enum | Modality must equal the bound MeasurementSpec assay; the enum records its holdout conclusion. |
| `calibration_state`, `ood_state` | passed/failed/not_required/not_assessed | Upstream validation checks; P0-08 has no numeric calibration field. |
| `validation_refs`, `evidence_refs`, `provenance_refs` | non-empty unique arrays | Reviewed records, biological Evidence IDs and lineage. |

### Prior-applicability record fields

| Field group | Type | Source and behavior |
|---|---|---|
| `prior_record_id`, `object_version`, `created_at` | ID/version/UTC datetime | Immutable upstream record identity. |
| `measurement_spec_ref`, `product_definition_ref` | strings | Must match the domain binding. |
| `prior_ref`, `snapshot_ref`, `prior_kind` | strings/enum | Exact versioned prior or knowledge snapshot. |
| `evidence_family_id`, `required_for_interpretation` | string, boolean | Family de-duplication and gate participation. |
| nine `*_match` fields | match/partial_match/mismatch/not_required/not_assessed | Species, assay, specimen, anatomy, developmental stage, product definition, gene coverage, version and license applicability. |
| `crosswalk_ref` | string or null | Optional reviewed crosswalk lineage; never inferred. |
| `evidence_refs`, `provenance_refs` | non-empty unique arrays | Biological evidence and internal provenance. |

There is no database-count, support-score, rank or majority field. A required license mismatch is inapplicable even if biological dimensions match.

### Sensitivity record fields

| Field | Type | Source and behavior |
|---|---|---|
| `sensitivity_record_id`, `object_version`, `created_at` | ID/version/UTC datetime | Immutable upstream record identity. |
| `measurement_spec_ref` | string | Must equal the bound MeasurementSpec ID. |
| `sensitivity_kind` | reference/preprocessing/annotation/assay/method/downsampling | Upstream sensitivity dimension. |
| `evidence_family_id`, `required_for_interpretation` | string, boolean | Family and gate participation. |
| `state` | stable/limited/unstable/not_assessed | Upstream conclusion; no recomputation. |
| `baseline_ref`, `perturbation_ref`, `conclusion_ref` | strings | Trace the compared records and their conclusion. |
| `evidence_refs`, `provenance_refs` | non-empty unique arrays | Biological evidence and internal provenance. |

Sensitivity records deliberately carry no threshold, effect size, direction or metric. Those facts remain owned by the referenced upstream record.

## Deterministic scientific behavior

P0-08 reads upstream conclusions but does not recompute QC, calibration, OOD, holdout, sensitivity, prior support or any biological measurement. It applies this fixed precedence independently per domain:

1. Data Readiness: `adequate`, `limited`, `insufficient`, or `not_assessed` from the bound QC record and required contract presence.
2. Model Robustness: `validated_applicable`, `candidate_applicable`, `unstable`, `not_applicable`, `not_required`, or `not_assessed` from required validation and sensitivity records.
3. Prior Applicability: `applicable`, `partially_applicable`, `inapplicable`, `not_required`, or `not_assessed` from required context matches.
4. Final precedence: `not_assessed` → `insufficient` → `limited` → `sufficient`.

Canonical-content-identical records in one Evidence Family collapse to one deterministic representative while every duplicate input reference remains in the trace. A family conflicts only when it contains more than one distinct canonical record marked `required_for_interpretation=true`. All distinct required representatives remain in output provenance while the axis is `not_assessed`. Supporting records (`required_for_interpretation=false`) remain provenance only: they can neither improve nor worsen an axis, and one required record plus any number of different supporting records is not a conflict. Record or tool count never acts as a vote.

The deterministic scientific input hash sorts `object_inputs` and normalizes only contract-declared set-like lists: DomainGateInput bindings, required sensitivity kinds and references; record validation/evidence/provenance references; MeasurementSpec applicability/tool/reference/prior references; MeasurementResult provenance; and QC missing/blocking/warning/evidence lists. Caller ordering of these sets therefore cannot change run identity, result bytes or the reusable bundle. Semantically ordered gate-rule fields, including `applicable_domains` and `precedence`, retain their declared order. Exact source-byte checksums remain unchanged in the invocation's `ToolRunV2.request.object_inputs`; the reusable bundle records a canonical semantic checksum for each object.

## Result and artifacts

`ToolRunV2.result` is an `EvidenceSufficiencyRunResult` containing:

| Field | Meaning |
|---|---|
| `profiles[]` | One ordered `EvidenceSufficiencyProfile` per domain binding, including all three axes, reason codes, missing/limiting/blocking lists and provenance references. |
| `case_summary` | Counts of `sufficient`, `limited`, `insufficient`, `not_assessed`, plus unavailable-score count and blocking reasons. |
| `gate_trace[]` | Rule precedence, selected state/reasons and ignored exact-duplicate input refs for each profile. |

### Profile fields and denominators

| Field group | Type | Meaning |
|---|---|---|
| `profile_id`, `profile_version`, `deterministic_run_ref`, `created_at` | IDs/version/UTC datetime | Deterministic identity and source-binding timestamp. |
| gate, case, product, domain and MeasurementSpec refs | strings or null | Exact assessed context; null stays null. |
| `data_readiness`, `data_reason_codes`, `qc_profile_ref` | enum/list/ref | Data axis and its upstream QC lineage. |
| `model_robustness`, `robustness_reason_codes`, `validation_refs` | enum/list/list | Method axis and validation records. |
| `prior_applicability`, `prior_reason_codes`, `snapshot_refs` | enum/list/list | Prior axis and snapshot lineage. |
| `evidence_sufficiency_state` | four-state enum | First matching state under the fixed precedence. |
| `blocking_reasons`, `limiting_reasons`, `missing_requirements` | catalog-ordered unique arrays | Severity-separated trace: only catalog `blocking`, `limiting` and `missing` codes respectively. A missing code is never duplicated into `blocking_reasons`. |
| `domain_score`, `score_state`, `score_reason_codes` | null/unavailable/list | Forced no-score release contract. |
| measurement, evidence, sensitivity and family refs | unique arrays | Upstream record identifiers and de-duplicated Evidence Families. |

P0-08 emits categorical states, identifiers and counts only: there is no biological numeric unit, numerator, interval or raw-value denominator. The summary denominator is `profile_count` (one per accepted `DomainGateInput`, range 1..5), and all four sufficiency counts must sum to it. `score_state_counts.unavailable` must also equal `profile_count`.

Every profile has `domain_score=null`, `score_state=unavailable`, and `p0_score_contract_unavailable`. A supplied `score_contract_ref` adds `score_contract_ignored_current_release` but cannot enable a score.

Successful runs emit no `MeasurementResult` and no visualization. They publish exactly five checksummed JSON artifacts:

- `evidence_sufficiency_profiles.json`
- `case_evidence_readiness_summary.json`
- `gate_trace.json`
- `evidence_sufficiency_run_result.json`
- `artifact_manifest.json`

Scientific JSON contains no local path. The internal manifest binds tool/environment versions, the full input hash, per-object canonical semantic checksums and the first four artifact checksums; it has no circular self-hash. Raw source-byte checksums are invocation provenance in `ToolRunV2.request.object_inputs`, are checked before and after execution, and deliberately do not alter reusable bundle bytes. Reordering a declared set and running into the same output directory therefore reuses the byte-identical bundle, while any semantic object change produces a different full input hash and run directory. Mutated inputs or a drifted existing bundle fail without overwrite. Every returned `ArtifactManifest.sha256`, including the bundle manifest itself, verifies the bytes at its returned path.

## Eligibility, refusal and degradation

Technical eligibility failures return `execution_state=failed`, no result and no artifacts. Stable reason codes are:

- envelope and roles: `tool_version_mismatch`, `tool_request_v2_required`, `p0_08_expression_assets_forbidden`, `p0_08_top_level_measurement_spec_forbidden`, `p0_08_parameters_forbidden`, `exactly_one_gate_rule_spec_required`, `one_to_five_domain_gate_inputs_required`, `unsupported_object_input_role`, `object_input_schema_mismatch`, `duplicate_object_input_id`;
- immutable files: `structured_input_not_found`, `structured_input_not_regular_file`, `structured_input_checksum_mismatch`, `structured_input_media_type_unsupported`, `structured_input_json_invalid`, `structured_input_schema_invalid`, `structured_input_modified_during_run`;
- binding and policy: `unsupported_gate_rule_spec`, `domain_gate_input_binding_invalid`, `domain_input_measurement_spec_mismatch`, `domain_input_product_definition_mismatch`, `duplicate_logical_object_id`, `duplicate_domain_id`, `multiple_product_cases_in_request`, `unbound_structured_input`, `output_dir_overlaps_structured_input`, `legacy_evidence_contract_rejected`, `unsafe_scientific_reference`;
- publication: `existing_run_bundle_hash_mismatch`.

Eligibility reason codes are de-duplicated and lexicographically sorted. Scientific profile reason codes instead follow the fixed 45-code catalog order; they include missing-contract, data, model, prior, final-gate, score and Evidence-Family provenance reasons. Descriptions and remediations live in the packaged `reason_code_catalog_v0.1.json` and never describe a product failure.

The public SDK/registry rejects a v0.1 request for P0-08 with `tool_request_v2_required`; the module adapter returns the same stable code when called directly.

A contract-complete request with absent or unassessed scientific evidence is different: it is eligible, executes successfully and emits a `not_assessed` profile. Its catalog `missing` codes appear only in `missing_requirements`; case-summary blocking reasons are derived only from profile `blocking_reasons`. Missing, unknown, unavailable, negative and alert upstream states remain distinct and are never converted to zero, product failure or a safety statement.

## Minimum request example

See `examples/requests/p0_08_evidence_sufficiency.json`. Its absolute paths and checksums are deliberate placeholders. Executable validation must generate real local objects and SHA-256 values; callers must not paste inline objects or edit the packaged rule.

A successful minimal result has this shape; omitted profile fields remain required by the public Schema:

```json
{
  "result_id": "evidence-sufficiency-result:0123456789abcdef",
  "result_version": "0.1.0",
  "gate_rule_spec_ref": "GATE-EVIDENCE-SUFFICIENCY-v0.1",
  "profiles": [
    {
      "domain_id": "target_identity",
      "data_readiness": "adequate",
      "model_robustness": "validated_applicable",
      "prior_applicability": "applicable",
      "evidence_sufficiency_state": "sufficient",
      "domain_score": null,
      "score_state": "unavailable",
      "score_reason_codes": ["p0_score_contract_unavailable"]
    }
  ],
  "case_summary": {
    "profile_count": 1,
    "evidence_sufficiency_counts": {
      "sufficient": 1,
      "limited": 0,
      "insufficient": 0,
      "not_assessed": 0
    },
    "score_state_counts": {"unavailable": 1}
  },
  "gate_trace": [
    {
      "selected_state": "sufficient",
      "selected_reason_codes": [
        "data_readiness_adequate",
        "method_validated_applicable",
        "prior_applicable",
        "raw_evidence_gate_sufficient",
        "p0_score_contract_unavailable"
      ]
    }
  ]
}
```

The shortened example is explanatory, not a standalone Schema-valid fixture. Exact IDs and full required fields are deterministic outputs of `run`.

## Methods, environment and license

The package selects only the existing internal records `METHOD-BRIDGE-ALGORITHM-A0908D`, `METHOD-BRIDGE-REGISTRY`, and `METHOD-BRIDGE-VALIDATOR`. All remain `formal_eligible=false`. Pydantic performs contract parsing but is not represented as an executed scientific method. `ENV-EVIDENCE-v0.1` remains proposed pending a separate reproducibility and health-check record. Repository code is distributed under the repository MIT license; selected method/source records retain their own catalogued version, source and license fields.

## Prohibited interpretation and remaining work

Engineering tests with synthetic records show deterministic contract behavior only. They do not establish that a real domain is sufficient, validate upstream evidence, freeze thresholds, prove potency/safety/efficacy, authorize GMP release, rank products, or support a clinical claim. Real use requires separately reviewed upstream records, a reviewed gate-resource version, reproducible environment evidence and scientific review.

Detailed scientific requirement: `docs/bridge_spec_v0.1/evidence_sufficiency_task_card.md`.
