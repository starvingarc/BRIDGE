from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, StrictInt, field_validator, model_validator

from bridge.toolkit.contracts import FrozenModel

TOOL_INPUT_CONTRACT_SCHEMA_REF = "bridge://schemas/tool-input-contract/v0.1"


class AssetInputContract(FrozenModel):
    min_count: StrictInt = Field(ge=0)
    max_count: StrictInt | None = Field(default=None, ge=0)
    formats: list[str] = Field(default_factory=list)
    assays: list[str] = Field(default_factory=list)
    input_levels: list[str] = Field(default_factory=list)
    matrix_semantics: list[str] = Field(default_factory=list)
    required_metadata_keys: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def cardinality_is_valid(self) -> Self:
        if self.max_count is not None and self.max_count < self.min_count:
            raise ValueError("asset max_count cannot be smaller than min_count")
        return self

    @field_validator(
        "formats",
        "assays",
        "input_levels",
        "matrix_semantics",
        "required_metadata_keys",
    )
    @classmethod
    def values_are_unique(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("asset contract values must be unique")
        return value


class ObjectInputRoleContract(FrozenModel):
    role: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    schema_refs: list[str] = Field(min_length=1)
    object_version_policy: Literal["fixed", "payload"]
    object_versions: list[str] = Field(default_factory=list)
    min_count: StrictInt = Field(ge=0)
    max_count: StrictInt | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def role_contract_is_valid(self) -> Self:
        if self.max_count is not None and self.max_count < self.min_count:
            raise ValueError("object-input max_count cannot be smaller than min_count")
        if self.object_version_policy == "fixed" and not self.object_versions:
            raise ValueError("fixed object-version policy requires object_versions")
        if self.object_version_policy == "payload" and self.object_versions:
            raise ValueError("payload object-version policy cannot list fixed versions")
        if len(self.schema_refs) != len(set(self.schema_refs)):
            raise ValueError("schema_refs must be unique")
        if len(self.object_versions) != len(set(self.object_versions)):
            raise ValueError("object_versions must be unique")
        return self


class ObjectInputModeContract(FrozenModel):
    mode_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    roles: list[ObjectInputRoleContract] = Field(default_factory=list)

    asset_input: AssetInputContract | None = None

    @field_validator("roles")
    @classmethod
    def roles_are_unique(
        cls, value: list[ObjectInputRoleContract]
    ) -> list[ObjectInputRoleContract]:
        roles = [item.role for item in value]
        if len(roles) != len(set(roles)):
            raise ValueError("object-input roles must be unique within a mode")
        return value


class ToolInputContract(FrozenModel):
    object_version: Literal["0.1.0"] = "0.1.0"
    schema_ref: Literal["bridge://schemas/tool-input-contract/v0.1"] = (
        TOOL_INPUT_CONTRACT_SCHEMA_REF
    )
    tool_id: str = Field(pattern=r"^P0-(0[1-9]|1[0-2])$")
    request_schema_ref: Literal[
        "bridge://schemas/tool-request/v0.1",
        "bridge://schemas/tool-request/v0.2",
    ]
    asset_input: AssetInputContract | None = None
    measurement_spec_ref_policy: Literal["forbidden", "optional", "required"]
    parameters_allowed: bool
    random_seed_policy: Literal["any_integer", "fixed_zero"]
    object_input_modes: list[ObjectInputModeContract] = Field(default_factory=list)
    semantic_validation: Literal["adapter"] = "adapter"

    @model_validator(mode="after")
    def envelope_is_coherent(self) -> Self:
        mode_ids = [item.mode_id for item in self.object_input_modes]
        if len(mode_ids) != len(set(mode_ids)):
            raise ValueError("object-input mode IDs must be unique")
        if self.request_schema_ref.endswith("/v0.1"):
            if self.object_input_modes:
                raise ValueError("ToolRequest v0.1 cannot declare object-input modes")
        elif not self.object_input_modes:
            raise ValueError("ToolRequest v0.2 requires object-input modes")
        return self


def _role(
    role: str,
    schema_refs: str | tuple[str, ...],
    versions: str | tuple[str, ...] | None,
    minimum: int,
    maximum: int | None,
) -> ObjectInputRoleContract:
    schemas = (schema_refs,) if isinstance(schema_refs, str) else schema_refs
    fixed_versions: tuple[str, ...]
    if versions is None:
        policy = "payload"
        fixed_versions = ()
    else:
        policy = "fixed"
        fixed_versions = (versions,) if isinstance(versions, str) else versions
    return ObjectInputRoleContract(
        role=role,
        schema_refs=list(schemas),
        object_version_policy=policy,
        object_versions=list(fixed_versions),
        min_count=minimum,
        max_count=maximum,
    )


def _mode(
    mode_id: str,
    *roles: ObjectInputRoleContract,
    asset_input: AssetInputContract | None = None,
) -> ObjectInputModeContract:
    return ObjectInputModeContract(
        mode_id=mode_id, roles=list(roles), asset_input=asset_input
    )


V01 = "0.1.0"
V02 = "0.2.0"
V03 = "0.3.0"


def _p006_base_roles(
    cell_state_schema: str,
    cell_state_version: str,
    *,
    include_program_evidence: bool,
    measurement_min_count: int,
) -> tuple[ObjectInputRoleContract, ...]:
    common = (
        _role("product_case", "bridge://schemas/product-case/v0.1", V01, 1, 1),
        _role(
            "product_definition_card",
            "bridge://schemas/product-definition-card/v0.1",
            V01,
            1,
            1,
        ),
        _role(
            "development_window_spec",
            "bridge://schemas/development-window-spec/v0.1",
            V01,
            1,
            1,
        ),
        _role(
            "program_spec",
            "bridge://schemas/program-spec/v0.1",
            V01,
            1,
            1,
        ),
        _role(
            "cell_state_evidence_profile",
            cell_state_schema,
            cell_state_version,
            1,
            1,
        ),
        _role(
            "protocol_ir",
            "bridge://schemas/protocol-ir/v0.1",
            V01,
            1,
            1,
        ),
    )
    evidence = (
        _role(
            "program_evidence_bundle",
            "bridge://schemas/program-evidence-bundle/v0.1",
            V01,
            1,
            1,
        ),
    )
    return (
        *common,
        *(evidence if include_program_evidence else ()),
        _role(
            "measurement_spec",
            "bridge://schemas/measurement-spec/v0.2",
            None,
            measurement_min_count,
            1,
        ),
    )


def _p009_mode(
    mode_id: str,
    *,
    comparison: bool,
    append: bool,
    canonical_run: bool,
) -> ObjectInputModeContract:
    if canonical_run:
        sufficiency = _role(
            "evidence_sufficiency_run_result",
            "bridge://schemas/evidence-sufficiency-run-result/v0.2",
            V02,
            2 if comparison else 1,
            5 if comparison else 1,
        )
    else:
        sufficiency = _role(
            "evidence_sufficiency_profile",
            (
                "bridge://schemas/evidence-sufficiency-profile/v0.1",
                "bridge://schemas/evidence-sufficiency-profile/v0.2",
            ),
            (V01, V02),
            2 if comparison else 1,
            25 if comparison else 5,
        )
    roles = [
        _role(
            "compilation_bundle",
            "bridge://schemas/evidence-compilation-bundle/v0.1",
            V01,
            1,
            1,
        ),
        sufficiency,
        _role(
            "evidence_family_registry",
            "bridge://schemas/evidence-family-registry/v0.1",
            V01,
            1,
            1,
        ),
        _role(
            "claim_registry",
            "bridge://schemas/claim-registry/v0.1",
            V01,
            1,
            1,
        ),
        _role(
            "reconciliation_spec_registry",
            "bridge://schemas/reconciliation-spec-registry/v0.1",
            V01,
            1,
            1,
        ),
    ]
    if append:
        roles.extend(
            [
                _role(
                    "base_graph_manifest",
                    (
                        "bridge://schemas/comparison-evidence-graph-manifest/v0.1"
                        if comparison
                        else "bridge://schemas/case-evidence-graph-manifest/v0.1"
                    ),
                    None,
                    1,
                    1,
                ),
                _role(
                    "base_evidence_record_set",
                    "bridge://schemas/evidence-record-set/v0.1",
                    V01,
                    1,
                    1,
                ),
                _role(
                    "base_evidence_requirement_set",
                    "bridge://schemas/evidence-requirement-set/v0.1",
                    V01,
                    1,
                    1,
                ),
            ]
        )
    if comparison:
        roles.extend(
            [
                _role(
                    "source_case_graph_manifest",
                    "bridge://schemas/case-evidence-graph-manifest/v0.1",
                    None,
                    2,
                    5,
                ),
                _role(
                    "source_case_evidence_record_set",
                    "bridge://schemas/evidence-record-set/v0.1",
                    V01,
                    2,
                    5,
                ),
            ]
        )
    return _mode(mode_id, *roles)


INPUT_CONTRACTS: dict[str, ToolInputContract] = {
    "P0-01": ToolInputContract(
        tool_id="P0-01",
        request_schema_ref="bridge://schemas/tool-request/v0.1",
        asset_input=AssetInputContract(
            min_count=1,
            max_count=1,
            formats=["h5ad", "10x_h5", "10x_mtx"],
            assays=["scRNA-seq", "snRNA-seq"],
            input_levels=["analysis_ready", "count_ready", "droplet_ready"],
            matrix_semantics=["normalized_expression", "raw_counts"],
        ),
        measurement_spec_ref_policy="optional",
        parameters_allowed=True,
        random_seed_policy="any_integer",
    ),
    "P0-02": ToolInputContract(
        tool_id="P0-02",
        request_schema_ref="bridge://schemas/tool-request/v0.1",
        asset_input=AssetInputContract(
            min_count=1,
            max_count=1,
            formats=["h5ad"],
            assays=["scRNA-seq", "snRNA-seq"],
            input_levels=["analysis_ready", "count_ready"],
            matrix_semantics=["normalized_expression", "raw_counts"],
            required_metadata_keys=["source_family_id", "qc_profile_ref"],
        ),
        measurement_spec_ref_policy="required",
        parameters_allowed=True,
        random_seed_policy="any_integer",
    ),
    "P0-03": ToolInputContract(
        tool_id="P0-03",
        request_schema_ref="bridge://schemas/tool-request/v0.2",
        asset_input=AssetInputContract(
            min_count=0,
            max_count=1,
            formats=["h5ad"],
            assays=["scRNA-seq", "snRNA-seq"],
            input_levels=["analysis_ready"],
            matrix_semantics=["normalized_expression"],
            required_metadata_keys=["data_view_id", "parent_asset_sha256"],
        ),
        measurement_spec_ref_policy="forbidden",
        parameters_allowed=False,
        random_seed_policy="any_integer",
        object_input_modes=[
            _mode(
                "default",
                _role("product_case", "bridge://schemas/product-case/v0.1", V01, 1, 1),
                _role(
                    "product_definition_card",
                    "bridge://schemas/product-definition-card/v0.1",
                    V01,
                    1,
                    1,
                ),
                _role(
                    "state_role_map", "bridge://schemas/state-role-map/v0.1", V01, 1, 1
                ),
                _role(
                    "target_regional_assessment_spec",
                    "bridge://schemas/target-regional-assessment-spec/v0.1",
                    V01,
                    1,
                    1,
                ),
                _role(
                    "measurement_spec",
                    "bridge://schemas/measurement-spec/v0.2",
                    None,
                    1,
                    1,
                ),
                _role(
                    "cell_state_evidence_profile",
                    "bridge://schemas/cell-state-evidence-profile/v0.3",
                    V03,
                    1,
                    1,
                ),
                _role(
                    "qc_readiness_profile",
                    "bridge://schemas/qc-readiness-profile/v0.2",
                    V02,
                    1,
                    1,
                ),
                _role(
                    "biological_unit_manifest",
                    "bridge://schemas/biological-unit-manifest/v0.1",
                    V01,
                    1,
                    1,
                ),
                _role(
                    "biological_unit_assignment",
                    "bridge://schemas/biological-unit-assignment/v0.1",
                    V01,
                    1,
                    1,
                ),
                _role(
                    "annotation_vocabulary",
                    "bridge://schemas/annotation-vocabulary/v0.1",
                    None,
                    1,
                    1,
                ),
                _role(
                    "reference_manifest",
                    "bridge://schemas/reference-manifest/v0.1",
                    None,
                    1,
                    1,
                ),
                _role(
                    "target_regional_method_spec",
                    "bridge://schemas/target-regional-method-spec/v0.1",
                    V01,
                    0,
                    1,
                ),
            )
        ],
    ),
    "P0-04": ToolInputContract(
        tool_id="P0-04",
        request_schema_ref="bridge://schemas/tool-request/v0.2",
        asset_input=AssetInputContract(
            min_count=0,
            max_count=1,
            formats=["h5ad"],
            assays=["scRNA-seq", "snRNA-seq"],
            input_levels=["analysis_ready"],
            matrix_semantics=["normalized_expression"],
            required_metadata_keys=["data_view_id", "parent_asset_sha256"],
        ),
        measurement_spec_ref_policy="forbidden",
        parameters_allowed=False,
        random_seed_policy="any_integer",
        object_input_modes=[
            _mode(
                "default",
                _role("product_case", "bridge://schemas/product-case/v0.1", V01, 1, 1),
                _role(
                    "product_definition_card",
                    "bridge://schemas/product-definition-card/v0.1",
                    V01,
                    1,
                    1,
                ),
                _role(
                    "development_window_spec",
                    "bridge://schemas/development-window-spec/v0.1",
                    V01,
                    1,
                    1,
                ),
                _role(
                    "development_state_map",
                    "bridge://schemas/development-state-map/v0.1",
                    V01,
                    1,
                    1,
                ),
                _role(
                    "measurement_spec",
                    "bridge://schemas/measurement-spec/v0.2",
                    None,
                    1,
                    1,
                ),
                _role(
                    "cell_state_evidence_profile",
                    "bridge://schemas/cell-state-evidence-profile/v0.3",
                    V03,
                    1,
                    1,
                ),
                _role(
                    "qc_readiness_profile",
                    "bridge://schemas/qc-readiness-profile/v0.2",
                    V02,
                    1,
                    1,
                ),
                _role(
                    "biological_unit_manifest",
                    "bridge://schemas/biological-unit-manifest/v0.1",
                    V01,
                    1,
                    1,
                ),
                _role(
                    "biological_unit_assignment",
                    "bridge://schemas/biological-unit-assignment/v0.1",
                    V01,
                    1,
                    1,
                ),
                _role(
                    "annotation_vocabulary",
                    "bridge://schemas/annotation-vocabulary/v0.1",
                    None,
                    1,
                    1,
                ),
                _role(
                    "reference_manifest",
                    "bridge://schemas/reference-manifest/v0.1",
                    None,
                    1,
                    1,
                ),
                _role(
                    "development_timepoint_series",
                    "bridge://schemas/development-timepoint-series/v0.1",
                    V01,
                    0,
                    1,
                ),
                _role(
                    "development_method_spec",
                    "bridge://schemas/development-method-spec/v0.1",
                    V01,
                    0,
                    1,
                ),
            )
        ],
    ),
    "P0-05": ToolInputContract(
        tool_id="P0-05",
        request_schema_ref="bridge://schemas/tool-request/v0.2",
        measurement_spec_ref_policy="forbidden",
        parameters_allowed=False,
        random_seed_policy="any_integer",
        object_input_modes=[
            _mode(
                "legacy_aggregation",
                _role("product_case", "bridge://schemas/product-case/v0.1", V01, 1, 1),
                _role(
                    "product_definition_card",
                    "bridge://schemas/product-definition-card/v0.1",
                    V01,
                    1,
                    1,
                ),
                _role(
                    "state_role_map", "bridge://schemas/state-role-map/v0.1", V01, 1, 1
                ),
                _role(
                    "off_target_assessment_spec",
                    "bridge://schemas/off-target-assessment-spec/v0.1",
                    V01,
                    1,
                    1,
                ),
                _role(
                    "cell_state_evidence_profile",
                    "bridge://schemas/cell-state-evidence-profile/v0.2",
                    V02,
                    1,
                    1,
                ),
                _role(
                    "off_target_evidence_bundle",
                    "bridge://schemas/off-target-evidence-bundle/v0.1",
                    V01,
                    1,
                    1,
                ),
                _role(
                    "biological_unit_manifest",
                    "bridge://schemas/biological-unit-manifest/v0.1",
                    V01,
                    0,
                    1,
                ),
                _role(
                    "measurement_spec",
                    "bridge://schemas/measurement-spec/v0.2",
                    None,
                    0,
                    1,
                ),
            ),
            _mode(
                "method_runtime",
                _role("product_case", "bridge://schemas/product-case/v0.1", V01, 1, 1),
                _role(
                    "product_definition_card",
                    "bridge://schemas/product-definition-card/v0.1",
                    V01,
                    1,
                    1,
                ),
                _role(
                    "state_role_map", "bridge://schemas/state-role-map/v0.1", V01, 1, 1
                ),
                _role(
                    "off_target_assessment_spec",
                    "bridge://schemas/off-target-assessment-spec/v0.1",
                    V01,
                    1,
                    1,
                ),
                _role(
                    "cell_state_evidence_profile",
                    "bridge://schemas/cell-state-evidence-profile/v0.3",
                    V03,
                    1,
                    1,
                ),
                _role(
                    "off_target_evidence_bundle",
                    "bridge://schemas/off-target-evidence-bundle/v0.1",
                    V01,
                    1,
                    1,
                ),
                _role(
                    "measurement_spec",
                    "bridge://schemas/measurement-spec/v0.2",
                    None,
                    0,
                    1,
                ),
                _role(
                    "biological_unit_manifest",
                    "bridge://schemas/biological-unit-manifest/v0.1",
                    V01,
                    1,
                    1,
                ),
                _role(
                    "biological_unit_attestation_receipt",
                    "bridge://schemas/biological-unit-attestation-receipt/v0.1",
                    V01,
                    1,
                    1,
                ),
                _role(
                    "off_target_method_spec",
                    "bridge://schemas/off-target-method-spec/v0.1",
                    V01,
                    1,
                    1,
                ),
                _role(
                    "off_target_method_input",
                    "bridge://schemas/off-target-method-input/v0.1",
                    V01,
                    1,
                    1,
                ),
            ),
        ],
    ),
    "P0-06": ToolInputContract(
        tool_id="P0-06",
        request_schema_ref="bridge://schemas/tool-request/v0.2",
        measurement_spec_ref_policy="forbidden",
        parameters_allowed=False,
        random_seed_policy="any_integer",
        object_input_modes=[
            _mode(
                "legacy_aggregation",
                *_p006_base_roles(
                    "bridge://schemas/cell-state-evidence-profile/v0.2",
                    V02,
                    include_program_evidence=True,
                    measurement_min_count=0,
                ),
            ),
            _mode(
                "method_runtime",
                *_p006_base_roles(
                    "bridge://schemas/cell-state-evidence-profile/v0.3",
                    V03,
                    include_program_evidence=False,
                    measurement_min_count=1,
                ),
                _role(
                    "biological_unit_manifest",
                    "bridge://schemas/biological-unit-manifest/v0.1",
                    V01,
                    1,
                    1,
                ),
                _role(
                    "biological_unit_assignment",
                    "bridge://schemas/biological-unit-assignment/v0.1",
                    V01,
                    1,
                    1,
                ),
                _role(
                    "biological_unit_attestation_receipt",
                    "bridge://schemas/biological-unit-attestation-receipt/v0.1",
                    V01,
                    1,
                    1,
                ),
                _role(
                    "process_method_spec",
                    "bridge://schemas/process-method-spec/v0.1",
                    V01,
                    1,
                    1,
                ),
                _role(
                    "process_method_input",
                    "bridge://schemas/process-method-input/v0.1",
                    V01,
                    1,
                    1,
                ),
                asset_input=AssetInputContract(
                    min_count=1,
                    max_count=1,
                    formats=["h5ad"],
                    assays=["scRNA-seq", "snRNA-seq"],
                    input_levels=["analysis_ready", "count_ready"],
                    matrix_semantics=["normalized_expression", "raw_counts"],
                ),
            ),
        ],
    ),
    "P0-07": ToolInputContract(
        tool_id="P0-07",
        request_schema_ref="bridge://schemas/tool-request/v0.2",
        measurement_spec_ref_policy="forbidden",
        parameters_allowed=False,
        random_seed_policy="fixed_zero",
        object_input_modes=[
            _mode(
                "legacy_comparison",
                _role(
                    "comparison_stability_spec",
                    "bridge://schemas/comparison-stability-spec/v0.1",
                    V01,
                    1,
                    1,
                ),
                _role(
                    "comparison_case_manifest",
                    "bridge://schemas/comparison-case-manifest/v0.1",
                    V01,
                    1,
                    1,
                ),
                _role(
                    "product_evidence_bundle",
                    "bridge://schemas/product-evidence-bundle/v0.1",
                    V01,
                    2,
                    20,
                ),
            ),
            _mode(
                "method_runtime",
                _role(
                    "comparison_stability_spec",
                    "bridge://schemas/comparison-stability-spec/v0.1",
                    V01,
                    1,
                    1,
                ),
                _role(
                    "comparison_case_manifest",
                    "bridge://schemas/comparison-case-manifest/v0.1",
                    V01,
                    1,
                    1,
                ),
                _role(
                    "product_evidence_bundle",
                    "bridge://schemas/product-evidence-bundle/v0.1",
                    V01,
                    2,
                    20,
                ),
                _role(
                    "comparison_method_spec",
                    "bridge://schemas/comparison-method-spec/v0.1",
                    V01,
                    1,
                    1,
                ),
                _role(
                    "comparison_method_input",
                    "bridge://schemas/comparison-method-input/v0.1",
                    V01,
                    1,
                    1,
                ),
            )
        ],
    ),
    "P0-08": ToolInputContract(
        tool_id="P0-08",
        request_schema_ref="bridge://schemas/tool-request/v0.2",
        measurement_spec_ref_policy="forbidden",
        parameters_allowed=False,
        random_seed_policy="any_integer",
        object_input_modes=[
            _mode(
                "default",
                _role(
                    "gate_rule_spec",
                    "bridge://schemas/evidence-sufficiency-gate-rule-spec/v0.2",
                    V02,
                    1,
                    1,
                ),
                _role(
                    "domain_gate_input",
                    "bridge://schemas/domain-gate-input/v0.1",
                    V01,
                    1,
                    5,
                ),
                _role(
                    "product_case",
                    "bridge://schemas/product-case/v0.1",
                    V01,
                    0,
                    1,
                ),
                _role(
                    "measurement_spec",
                    "bridge://schemas/measurement-spec/v0.2",
                    None,
                    0,
                    5,
                ),
                _role(
                    "qc_readiness_profile",
                    "bridge://schemas/qc-readiness-profile/v0.2",
                    V02,
                    0,
                    5,
                ),
                _role(
                    "measurement_result",
                    "bridge://schemas/measurement-result/v0.2",
                    V02,
                    0,
                    None,
                ),
                _role(
                    "validation_record",
                    "bridge://schemas/evidence-validation-record/v0.1",
                    None,
                    0,
                    None,
                ),
                _role(
                    "prior_applicability_record",
                    "bridge://schemas/prior-applicability-record/v0.1",
                    None,
                    0,
                    None,
                ),
                _role(
                    "sensitivity_record",
                    "bridge://schemas/evidence-sensitivity-record/v0.1",
                    None,
                    0,
                    None,
                ),
            )
        ],
    ),
    "P0-09": ToolInputContract(
        tool_id="P0-09",
        request_schema_ref="bridge://schemas/tool-request/v0.2",
        measurement_spec_ref_policy="forbidden",
        parameters_allowed=False,
        random_seed_policy="any_integer",
        object_input_modes=[
            _p009_mode(
                "case_initial",
                comparison=False,
                append=False,
                canonical_run=False,
            ),
            _p009_mode(
                "case_append",
                comparison=False,
                append=True,
                canonical_run=False,
            ),
            _p009_mode(
                "comparison_initial",
                comparison=True,
                append=False,
                canonical_run=False,
            ),
            _p009_mode(
                "comparison_append",
                comparison=True,
                append=True,
                canonical_run=False,
            ),
            _p009_mode(
                "case_initial_v2",
                comparison=False,
                append=False,
                canonical_run=True,
            ),
            _p009_mode(
                "case_append_v2",
                comparison=False,
                append=True,
                canonical_run=True,
            ),
            _p009_mode(
                "comparison_initial_v2",
                comparison=True,
                append=False,
                canonical_run=True,
            ),
            _p009_mode(
                "comparison_append_v2",
                comparison=True,
                append=True,
                canonical_run=True,
            ),
        ],
    ),
    "P0-10": ToolInputContract(
        tool_id="P0-10",
        request_schema_ref="bridge://schemas/tool-request/v0.2",
        measurement_spec_ref_policy="forbidden",
        parameters_allowed=False,
        random_seed_policy="any_integer",
        object_input_modes=[
            _mode(
                "default",
                _role("report_draft", "bridge://schemas/report-draft/v0.1", V01, 1, 1),
                _role(
                    "evidence_graph_manifest",
                    "bridge://schemas/case-evidence-graph-manifest/v0.1",
                    None,
                    1,
                    1,
                ),
                _role(
                    "claim_policy_spec",
                    "bridge://schemas/claim-policy-spec/v0.1",
                    V01,
                    1,
                    1,
                ),
                _role(
                    "statement_registry",
                    "bridge://schemas/statement-registry/v0.1",
                    V01,
                    1,
                    1,
                ),
            )
        ],
    ),
    "P0-11": ToolInputContract(
        tool_id="P0-11",
        request_schema_ref="bridge://schemas/tool-request/v0.2",
        measurement_spec_ref_policy="forbidden",
        parameters_allowed=False,
        random_seed_policy="any_integer",
        object_input_modes=[
            _mode(
                "report_export",
                _role("report_draft", "bridge://schemas/report-draft/v0.1", V01, 1, 1),
                _role(
                    "claim_verification_result",
                    "bridge://schemas/claim-verification-result/v0.1",
                    V01,
                    1,
                    1,
                ),
                _role(
                    "public_export_policy",
                    "bridge://schemas/public-export-policy-spec/v0.1",
                    V01,
                    1,
                    1,
                ),
                _role(
                    "public_export_request",
                    "bridge://schemas/public-export-request/v0.1",
                    V01,
                    1,
                    1,
                ),
            ),
            _mode(
                "artifact_audit",
                _role(
                    "public_artifact_audit_policy",
                    "bridge://schemas/public-artifact-audit-policy/v0.1",
                    V01,
                    1,
                    1,
                ),
                _role(
                    "public_artifact_manifest",
                    "bridge://schemas/public-artifact-manifest/v0.1",
                    V01,
                    1,
                    1,
                ),
            ),
        ],
    ),
    "P0-12": ToolInputContract(
        tool_id="P0-12",
        request_schema_ref="bridge://schemas/tool-request/v0.2",
        measurement_spec_ref_policy="forbidden",
        parameters_allowed=False,
        random_seed_policy="any_integer",
        object_input_modes=[
            _mode("not_provided"),
            _mode(
                "graft_assessment",
                _role("graft_case", "bridge://schemas/graft-case/v0.1", V01, 1, 1),
                _role(
                    "assessment_spec",
                    "bridge://schemas/graft-assessment-spec/v0.1",
                    V01,
                    1,
                    1,
                ),
                _role(
                    "evidence_bundle",
                    "bridge://schemas/graft-evidence-bundle/v0.1",
                    V01,
                    1,
                    1,
                ),
            ),
            _mode(
                "expression_analysis",
                _role("graft_case", "bridge://schemas/graft-case/v0.1", V01, 1, 1),
                _role(
                    "graft_expression_asset",
                    "bridge://schemas/graft-expression-asset/v0.1",
                    V01,
                    1,
                    1,
                ),
                _role(
                    "graft_expression_analysis_spec",
                    "bridge://schemas/graft-expression-analysis-spec/v0.1",
                    V01,
                    1,
                    1,
                ),
                _role(
                    "graft_reference_panel",
                    "bridge://schemas/graft-reference-panel/v0.1",
                    V01,
                    1,
                    1,
                ),
                _role(
                    "graft_marker_program_collection",
                    "bridge://schemas/graft-marker-program-collection/v0.1",
                    V01,
                    1,
                    1,
                ),
            ),
        ],
    ),
}


def get_input_contract(tool_id: str) -> ToolInputContract:
    try:
        return INPUT_CONTRACTS[tool_id]
    except KeyError as exc:
        raise KeyError(f"Unknown Tool Package: {tool_id}") from exc
