from __future__ import annotations

import re
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, RootModel, field_validator, model_validator

from bridge.tool_packages.p0_10_claim_verifier.models import ReportDraft
from bridge.tool_packages.p0_11_public_safe_export.artifact_models import (
    ArtifactAuditState,
    ArtifactCheckState,
    PublicArtifactAuditResult,
    PublicArtifactFormat,
)
from bridge.tool_packages.p0_11_public_safe_export.models import (
    PublicClaimField,
    PublicExportPolicySpec,
    PublicExportResult,
    PublicExportState,
    PublicSafeReport,
)
from bridge.toolkit.contracts import EvidenceState, FrozenModel
from bridge.toolkit.visualization import VisualizationArtifactV2


PUBLIC_SAFE_EXPORT_VISUALIZATION_DATA_SCHEMA_REF = (
    "bridge://schemas/public-safe-export-visualization-data/v0.1"
)
P011_VISUALIZATION_ARTIFACT_SET_SCHEMA_REF = (
    "bridge://schemas/p0-11-visualization-artifact-set/v0.1"
)
REPORT_FIELD_PROJECTION_COMPONENT_REF = (
    "bridge.public-safe-export.report-field-projection@0.1.0"
)
LOCAL_EXPORT_STATE_COMPONENT_REF = (
    "bridge.public-safe-export.local-export-state@0.1.0"
)
ARTIFACT_STATUS_COMPONENT_REF = (
    "bridge.public-safe-export.artifact-status@0.1.0"
)
REGISTERED_CHECKS_COMPONENT_REF = (
    "bridge.public-safe-export.registered-checks@0.1.0"
)

REPORT_COMPONENT_BINDINGS = (
    (REPORT_FIELD_PROJECTION_COMPONENT_REF, "report-field-projection", "field_records"),
    (LOCAL_EXPORT_STATE_COMPONENT_REF, "local-export-state", "state_records"),
)
AUDIT_COMPONENT_BINDINGS = (
    (ARTIFACT_STATUS_COMPONENT_REF, "artifact-status", "artifact_records"),
    (REGISTERED_CHECKS_COMPONENT_REF, "registered-checks", "check_records"),
)

_SHA256 = r"^[0-9a-f]{64}$"
_RECORD_ID = r"^[a-z][a-z0-9.-]+$"
_REASON_CODE = re.compile(r"^[a-z][a-z0-9_]*$")


def _p011_artifact_id(digest: str, suffix: str) -> str:
    return f"artifact:run-{digest}:{suffix}"


def _p011_visualization_id(digest: str, slug: str) -> str:
    return f"visualization:run-{digest}:{slug}"


def _sorted_unique(values: list[str], field_name: str) -> list[str]:
    if values != sorted(set(values)):
        raise ValueError(f"{field_name} must be sorted and unique")
    return values


class PublicSafeExportMode(StrEnum):
    REPORT_EXPORT = "report_export"
    ARTIFACT_AUDIT = "artifact_audit"


class FieldProjectionState(StrEnum):
    INCLUDED = "included"
    OMITTED_BY_POLICY = "omitted_by_policy"
    NOT_APPLICABLE_IN_SOURCE = "not_applicable_in_source"


class LocalExportStep(StrEnum):
    ALLOWLIST_PROJECTION = "allowlist_projection"
    REGISTERED_LEAK_RULES = "registered_leak_rules"
    CANDIDATE_HASH_MATCH = "candidate_hash_match"
    LOCAL_CANDIDATE_FILES = "local_candidate_files"
    NETWORK_UPLOAD = "network_upload"


class LocalExportStepState(StrEnum):
    COMPLETED = "completed"
    NO_REGISTERED_RULE_BLOCKED = "no_registered_rule_blocked"
    AWAITING_MATCHING_CANDIDATE_HASH = "awaiting_matching_candidate_hash"
    MATCHING_CANDIDATE_HASH_SUPPLIED = "matching_candidate_hash_supplied"
    WRITTEN_LOCALLY = "written_locally"
    NOT_PERFORMED_BY_TOOL = "not_performed_by_tool"


class CandidateHashDisplayState(StrEnum):
    AWAITING_MATCHING_CANDIDATE_HASH = "awaiting_matching_candidate_hash"
    MATCHING_CANDIDATE_HASH_SUPPLIED = "matching_candidate_hash_supplied"


class ArtifactDisplayState(StrEnum):
    NO_REGISTERED_RULE_BLOCKED = "no_registered_rule_blocked"
    BLOCKED_BY_REGISTERED_RULE = "blocked_by_registered_rule"


class RegisteredCheckDisplayState(StrEnum):
    NO_REGISTERED_RULE_BLOCKED = "no_registered_rule_blocked"
    BLOCKED_BY_REGISTERED_RULE = "blocked_by_registered_rule"
    NOT_APPLICABLE = "not_applicable"


CHECK_DISPLAY_NAMES = {
    "METHOD-CSV-DETERMINISTIC-RULE": "CSV structure and formula rules",
    "METHOD-CUSTOM-DETERMINISTIC-RULES": "Reference format and registered sensitive-text rules",
    "METHOD-CUSTOM-SVG-INSPECTOR": "SVG element and attribute rules",
    "METHOD-FORMAT-GATE": "Declared and detected file type",
    "METHOD-JSONSCHEMA-HASHLIB": "JSON Schema and checksum",
    "METHOD-MARKDOWN-PARSER-REGEX": "Markdown structure and text rules",
    "METHOD-OS-CLI": "Detected media type",
    "METHOD-URL-PARSER-ALLOWLIST": "External URL allowlist",
}


REASON_DISPLAY_NAMES = {
    "public_artifact_checksum_mismatch": "Checksum does not match",
    "public_artifact_control_character": "Control character is not allowed",
    "public_artifact_csv_columns_not_allowed": "CSV columns are not allowlisted",
    "public_artifact_csv_formula_injection": "CSV formula-like value is blocked",
    "public_artifact_csv_invalid": "CSV structure is invalid",
    "public_artifact_csv_row_width_invalid": "CSV rows have inconsistent widths",
    "public_artifact_declared_media_type_mismatch": "Declared media type does not match format",
    "public_artifact_empty": "File is empty",
    "public_artifact_file_command_failed": "Media-type detection could not complete",
    "public_artifact_json_schema_invalid": "JSON does not match its registered schema",
    "public_artifact_leak_pattern_detected": "A registered disclosure pattern was detected",
    "public_artifact_markdown_html_forbidden": "Embedded HTML is not allowed",
    "public_artifact_markdown_invalid": "Markdown could not be parsed",
    "public_artifact_media_type_mismatch": "Detected media type does not match format",
    "public_artifact_source_ref_syntax_invalid": "Source reference syntax is invalid",
    "public_artifact_svg_attribute_forbidden": "SVG contains a disallowed attribute",
    "public_artifact_svg_duplicate_id": "SVG contains duplicate element IDs",
    "public_artifact_svg_element_forbidden": "SVG contains a disallowed element",
    "public_artifact_svg_external_resource_forbidden": "SVG external resources are not allowed",
    "public_artifact_svg_hidden_content": "SVG contains hidden content",
    "public_artifact_svg_invalid": "SVG could not be parsed",
    "public_artifact_svg_local_reference_missing": "SVG local reference is missing",
    "public_artifact_svg_root_invalid": "SVG root element is invalid",
    "public_artifact_svg_url_invalid": "SVG URL reference is invalid",
    "public_artifact_too_large": "File exceeds the registered size limit",
    "public_artifact_url_not_allowed": "External URL is not allowlisted",
    "public_artifact_utf8_invalid": "Text is not valid UTF-8",
}


class _VisualizationRecord(FrozenModel):

    record_id: str = Field(pattern=_RECORD_ID)
    evidence_ids: list[str] = Field(min_length=1, max_length=1)
    evidence_state: EvidenceState
    scientific_status: Literal["candidate"] = "candidate"
    missingness: Literal["available"] = "available"
    applicability: Literal["applicable", "not_applicable"]
    display_state: str = Field(min_length=1)
    reason_codes: list[str]

    @field_validator("evidence_ids", "reason_codes")
    @classmethod
    def set_like_fields_are_sorted(cls, values: list[str], info):
        return _sorted_unique(values, info.field_name)

    @field_validator("reason_codes")
    @classmethod
    def reason_codes_are_controlled(cls, values: list[str]) -> list[str]:
        if any(
            not _REASON_CODE.fullmatch(value) or value not in REASON_DISPLAY_NAMES
            for value in values
        ):
            raise ValueError("reason codes must use the fixed public vocabulary")
        return values


class ReportFieldProjectionRecord(_VisualizationRecord):
    record_kind: Literal["report_field_projection"] = "report_field_projection"
    claim_display_id: str = Field(pattern=r"^Claim [0-9]{2,6}$")
    field: PublicClaimField
    projection_state: FieldProjectionState

    @model_validator(mode="after")
    def state_axes_are_coherent(self) -> Self:
        expected_applicability = (
            "not_applicable"
            if self.projection_state is FieldProjectionState.NOT_APPLICABLE_IN_SOURCE
            else "applicable"
        )
        if (
            self.display_state != self.projection_state.value
            or self.evidence_state is not EvidenceState.INFERRED
            or self.applicability != expected_applicability
            or self.reason_codes
        ):
            raise ValueError("field projection state axes disagree")
        return self


class LocalExportStateRecord(_VisualizationRecord):
    record_kind: Literal["local_export_state"] = "local_export_state"
    step: LocalExportStep
    state: LocalExportStepState

    @model_validator(mode="after")
    def state_axes_are_coherent(self) -> Self:
        if (
            self.display_state != self.state.value
            or self.evidence_state is not EvidenceState.INFERRED
            or self.applicability != "applicable"
            or self.reason_codes
        ):
            raise ValueError("local export state axes disagree")
        return self


class ArtifactStatusRecord(_VisualizationRecord):
    record_kind: Literal["artifact_status"] = "artifact_status"
    artifact_display_id: str = Field(pattern=r"^Artifact [0-9]{2}$")
    declared_format: PublicArtifactFormat
    byte_count: int = Field(ge=1)
    check_count: int = Field(ge=1)
    blocked_check_count: int = Field(ge=0)
    audit_state: ArtifactDisplayState

    @model_validator(mode="after")
    def state_axes_are_coherent(self) -> Self:
        blocked = self.audit_state is ArtifactDisplayState.BLOCKED_BY_REGISTERED_RULE
        expected_evidence = EvidenceState.ALERT if blocked else EvidenceState.INFERRED
        if (
            self.blocked_check_count > self.check_count
            or blocked != bool(self.blocked_check_count)
            or self.display_state != self.audit_state.value
            or self.evidence_state is not expected_evidence
            or self.applicability != "applicable"
            or blocked != bool(self.reason_codes)
        ):
            raise ValueError("artifact audit state axes disagree")
        return self


class RegisteredCheckRecord(_VisualizationRecord):
    record_kind: Literal["registered_check"] = "registered_check"
    artifact_display_id: str = Field(pattern=r"^Artifact [0-9]{2}$")
    method_id: str = Field(pattern=r"^METHOD-[A-Z0-9-]+$")
    check_name: str = Field(min_length=1)
    check_state: RegisteredCheckDisplayState

    @model_validator(mode="after")
    def state_axes_are_coherent(self) -> Self:
        if (
            self.method_id not in CHECK_DISPLAY_NAMES
            or self.check_name != CHECK_DISPLAY_NAMES[self.method_id]
        ):
            raise ValueError("registered check lacks its fixed public display name")
        blocked = (
            self.check_state is RegisteredCheckDisplayState.BLOCKED_BY_REGISTERED_RULE
        )
        expected_evidence = EvidenceState.ALERT if blocked else EvidenceState.INFERRED
        expected_applicability = (
            "not_applicable"
            if self.check_state is RegisteredCheckDisplayState.NOT_APPLICABLE
            else "applicable"
        )
        if (
            self.display_state != self.check_state.value
            or self.evidence_state is not expected_evidence
            or self.applicability != expected_applicability
            or blocked != bool(self.reason_codes)
        ):
            raise ValueError("registered check state axes disagree")
        return self


class _ProfileBase(FrozenModel):
    object_version: Literal["0.1.0"] = "0.1.0"
    schema_ref: Literal[PUBLIC_SAFE_EXPORT_VISUALIZATION_DATA_SCHEMA_REF] = (
        PUBLIC_SAFE_EXPORT_VISUALIZATION_DATA_SCHEMA_REF
    )
    visualization_profile_id: str = Field(
        pattern=r"^public-safe-export-visualization:[a-f0-9]{16}$"
    )
    producer_tool_id: Literal["P0-11"] = "P0-11"
    producer_tool_version: str = Field(min_length=1)
    producer_run_ref: str = Field(pattern=r"^run:run-[a-f0-9]{16}$")
    source_result_sha256: str = Field(pattern=_SHA256)
    evidence_ids: list[str] = Field(min_length=1, max_length=1)
    limitations: list[str] = Field(min_length=1)
    audit_counts_are_not_risk_scores: Literal[True] = True
    visualization_artifacts_are_not_publication_approval: Literal[True] = True
    no_network_upload_performed: Literal[True] = True
    domain_score: None = None

    @field_validator("evidence_ids", "limitations")
    @classmethod
    def set_like_fields_are_sorted(cls, values: list[str], info):
        return _sorted_unique(values, info.field_name)

    def _validate_common(self, records: list[_VisualizationRecord]) -> None:
        digest = self.visualization_profile_id.rsplit(":", 1)[1]
        if self.producer_run_ref != f"run:run-{digest}":
            raise ValueError("visualization profile and producer run digests must agree")
        if any(record.evidence_ids != self.evidence_ids for record in records):
            raise ValueError("every record must bind only the source result")


class ReportExportVisualizationDataV1(_ProfileBase):
    mode: Literal[PublicSafeExportMode.REPORT_EXPORT] = (
        PublicSafeExportMode.REPORT_EXPORT
    )
    source_result_ref: str = Field(pattern=r"^public-export:[a-f0-9]{16}$")
    candidate_hash_state: CandidateHashDisplayState
    target_channel: Literal["public_json"] = "public_json"
    candidate_hash: str = Field(pattern=_SHA256)
    claim_count: int = Field(ge=1, le=999999)
    field_records: list[ReportFieldProjectionRecord] = Field(min_length=6)
    state_records: list[LocalExportStateRecord] = Field(min_length=5, max_length=5)

    @model_validator(mode="after")
    def records_are_complete_and_conserved(self) -> Self:
        records: list[_VisualizationRecord] = [*self.field_records, *self.state_records]
        self._validate_common(records)
        if self.evidence_ids != [self.source_result_ref]:
            raise ValueError("report visualization must bind the export result")
        if len(self.field_records) != self.claim_count * len(PublicClaimField):
            raise ValueError("field grid must contain every field for every claim")
        expected_field_ids = [
            f"field.{index:03d}" for index in range(1, len(self.field_records) + 1)
        ]
        if [record.record_id for record in self.field_records] != expected_field_ids:
            raise ValueError("field record IDs must be stable and ordered")
        for claim_index in range(1, self.claim_count + 1):
            display_id = f"Claim {claim_index:02d}"
            rows = [
                record
                for record in self.field_records
                if record.claim_display_id == display_id
            ]
            if [record.field for record in rows] != list(PublicClaimField):
                raise ValueError("each claim requires all six public fields in order")
        if [record.step for record in self.state_records] != list(LocalExportStep):
            raise ValueError("local export state requires five fixed steps")
        if [record.record_id for record in self.state_records] != [
            f"state.{index:03d}" for index in range(1, 6)
        ]:
            raise ValueError("state record IDs must be stable and ordered")
        expected_confirmation = (
            LocalExportStepState.MATCHING_CANDIDATE_HASH_SUPPLIED
            if self.candidate_hash_state
            is CandidateHashDisplayState.MATCHING_CANDIDATE_HASH_SUPPLIED
            else LocalExportStepState.AWAITING_MATCHING_CANDIDATE_HASH
        )
        expected_states = [
            LocalExportStepState.COMPLETED,
            LocalExportStepState.NO_REGISTERED_RULE_BLOCKED,
            expected_confirmation,
            LocalExportStepState.WRITTEN_LOCALLY,
            LocalExportStepState.NOT_PERFORMED_BY_TOOL,
        ]
        if [record.state for record in self.state_records] != expected_states:
            raise ValueError("local export steps disagree with export state")
        return self


class ArtifactAuditVisualizationDataV1(_ProfileBase):
    mode: Literal[PublicSafeExportMode.ARTIFACT_AUDIT] = (
        PublicSafeExportMode.ARTIFACT_AUDIT
    )
    source_result_ref: str = Field(
        pattern=r"^public-artifact-audit:[a-f0-9]{16}$"
    )
    overall_display_state: ArtifactDisplayState
    artifact_count: int = Field(ge=1, le=20)
    registered_method_count: int = Field(ge=1)
    artifact_records: list[ArtifactStatusRecord] = Field(min_length=1, max_length=20)
    check_records: list[RegisteredCheckRecord] = Field(min_length=1)

    @model_validator(mode="after")
    def records_are_complete_and_conserved(self) -> Self:
        records: list[_VisualizationRecord] = [*self.artifact_records, *self.check_records]
        self._validate_common(records)
        if self.evidence_ids != [self.source_result_ref]:
            raise ValueError("audit visualization must bind the audit result")
        if self.artifact_count != len(self.artifact_records):
            raise ValueError("artifact count must equal artifact rows")
        if [record.record_id for record in self.artifact_records] != [
            f"artifact.{index:03d}" for index in range(1, self.artifact_count + 1)
        ]:
            raise ValueError("artifact record IDs must be stable and ordered")
        expected_displays = [
            f"Artifact {index:02d}" for index in range(1, self.artifact_count + 1)
        ]
        if [
            record.artifact_display_id for record in self.artifact_records
        ] != expected_displays:
            raise ValueError("artifact display IDs must be stable and ordered")
        if [record.record_id for record in self.check_records] != [
            f"check.{index:03d}" for index in range(1, len(self.check_records) + 1)
        ]:
            raise ValueError("check record IDs must be stable and ordered")
        methods = sorted({record.method_id for record in self.check_records})
        if self.registered_method_count != len(methods):
            raise ValueError("registered method count must equal the check union")
        by_display = {
            record.artifact_display_id: record for record in self.artifact_records
        }
        for display_id, artifact in by_display.items():
            checks = [
                record
                for record in self.check_records
                if record.artifact_display_id == display_id
            ]
            if [record.method_id for record in checks] != sorted(
                record.method_id for record in checks
            ) or len({record.method_id for record in checks}) != len(checks):
                raise ValueError("artifact checks must be unique and method-sorted")
            if {record.method_id for record in checks} != set(methods):
                raise ValueError("each artifact requires the complete method union")
            applicable = [
                record
                for record in checks
                if record.check_state is not RegisteredCheckDisplayState.NOT_APPLICABLE
            ]
            blocked = [
                record
                for record in applicable
                if record.check_state
                is RegisteredCheckDisplayState.BLOCKED_BY_REGISTERED_RULE
            ]
            reasons = sorted(
                {reason for record in blocked for reason in record.reason_codes}
            )
            if (
                artifact.check_count != len(applicable)
                or artifact.blocked_check_count != len(blocked)
                or artifact.reason_codes != reasons
            ):
                raise ValueError("artifact summary must equal its applicable checks")
        overall_blocked = any(
            record.audit_state is ArtifactDisplayState.BLOCKED_BY_REGISTERED_RULE
            for record in self.artifact_records
        )
        if overall_blocked != (
            self.overall_display_state is ArtifactDisplayState.BLOCKED_BY_REGISTERED_RULE
        ):
            raise ValueError("overall audit state must equal artifact summaries")
        return self


VisualizationProfile = Annotated[
    ReportExportVisualizationDataV1 | ArtifactAuditVisualizationDataV1,
    Field(discriminator="mode"),
]


class PublicSafeExportVisualizationDataV1(RootModel[VisualizationProfile]):
    pass


class P011VisualizationArtifactSet(FrozenModel):
    object_version: Literal["0.1.0"] = "0.1.0"
    schema_ref: Literal[P011_VISUALIZATION_ARTIFACT_SET_SCHEMA_REF] = (
        P011_VISUALIZATION_ARTIFACT_SET_SCHEMA_REF
    )
    mode: PublicSafeExportMode
    artifact_set_id: str = Field(pattern=r"^p0-11-visualizations:[a-f0-9]{16}$")
    data_profile_artifact_id: str = Field(min_length=1)
    data_profile_sha256: str = Field(pattern=_SHA256)
    visualizations: list[VisualizationArtifactV2] = Field(min_length=2, max_length=2)

    @model_validator(mode="after")
    def artifact_set_is_exactly_bound(self) -> Self:
        bindings = (
            REPORT_COMPONENT_BINDINGS
            if self.mode is PublicSafeExportMode.REPORT_EXPORT
            else AUDIT_COMPONENT_BINDINGS
        )
        if [item.component_ref for item in self.visualizations] != [
            item[0] for item in bindings
        ]:
            raise ValueError("artifact set contains the wrong P0-11 components")
        if any(
            item.data_binding.artifact_id != self.data_profile_artifact_id
            or item.data_binding.sha256 != self.data_profile_sha256
            for item in self.visualizations
        ):
            raise ValueError("visualizations must bind the exact data profile")
        expected_media = ["image/svg+xml", "image/png", "application/pdf"]
        if any(
            [render.media_type for render in item.renders] != expected_media
            for item in self.visualizations
        ):
            raise ValueError("each visualization requires ordered SVG, PNG and PDF")
        digest = self.artifact_set_id.rsplit(":", 1)[1]
        if self.data_profile_artifact_id != _p011_artifact_id(
            digest, "public-safe-export-visualization-data"
        ):
            raise ValueError("data profile artifact ID must bind the artifact-set run")
        if len({item.visualization_id for item in self.visualizations}) != 2:
            raise ValueError("visualization IDs must be unique")
        table_ids = [
            item.accessibility.table_artifact_id for item in self.visualizations
        ]
        if len(set(table_ids)) != 2:
            raise ValueError("visualization table artifact IDs must be unique")
        for item, (_ref, slug, records_path) in zip(
            self.visualizations, bindings, strict=True
        ):
            if (
                item.visualization_id != _p011_visualization_id(digest, slug)
                or item.data_binding.records_path != records_path
                or item.accessibility.table_artifact_id
                != _p011_artifact_id(
                    digest, f"public-safe-export-{slug}-table"
                )
            ):
                raise ValueError("visualization identity does not match its component")
            expected_render_ids = [
                _p011_artifact_id(
                    digest, f"public-safe-export-{slug}-{extension}"
                )
                for extension in ("svg", "png", "pdf")
            ]
            if [render.artifact_id for render in item.renders] != expected_render_ids:
                raise ValueError("render artifact IDs must match format and component")
        producer_contracts = {
            (item.producer_tool_id, item.producer_tool_version, item.producer_run_ref)
            for item in self.visualizations
        }
        if producer_contracts != {
            ("P0-11", self.visualizations[0].producer_tool_version, f"run:run-{digest}")
        }:
            raise ValueError("visualizations must share the artifact-set producer run")
        all_ids = {
            self.data_profile_artifact_id,
            *table_ids,
            *(
                render.artifact_id
                for item in self.visualizations
                for render in item.renders
            ),
        }
        if len(all_ids) != 9:
            raise ValueError("data, table and render artifact IDs must be disjoint")
        return self


def build_report_export_visualization_data(
    *,
    run_id: str,
    tool_version: str,
    report: ReportDraft,
    policy: PublicExportPolicySpec,
    public_report: PublicSafeReport,
    result: PublicExportResult,
    source_result_sha256: str,
) -> ReportExportVisualizationDataV1:
    if len(report.claim_blocks) != len(public_report.claims):
        raise ValueError("projected claim count does not match the source report")
    evidence_ids = [result.export_id]
    allowed = set(policy.allowlisted_claim_fields)
    field_records: list[ReportFieldProjectionRecord] = []
    for claim_index, claim in enumerate(public_report.claims, start=1):
        for field in PublicClaimField:
            value = getattr(claim, field.value)
            state = (
                FieldProjectionState.OMITTED_BY_POLICY
                if field not in allowed
                else FieldProjectionState.NOT_APPLICABLE_IN_SOURCE
                if value is None
                else FieldProjectionState.INCLUDED
            )
            field_records.append(
                ReportFieldProjectionRecord(
                    record_id=f"field.{len(field_records) + 1:03d}",
                    claim_display_id=f"Claim {claim_index:02d}",
                    field=field,
                    projection_state=state,
                    evidence_ids=evidence_ids,
                    evidence_state=EvidenceState.INFERRED,
                    applicability=(
                        "not_applicable"
                        if state is FieldProjectionState.NOT_APPLICABLE_IN_SOURCE
                        else "applicable"
                    ),
                    display_state=state.value,
                    reason_codes=[],
                )
            )
    candidate_hash_state = (
        CandidateHashDisplayState.MATCHING_CANDIDATE_HASH_SUPPLIED
        if result.export_state is PublicExportState.EXPORTED
        else CandidateHashDisplayState.AWAITING_MATCHING_CANDIDATE_HASH
    )
    confirmation_state = (
        LocalExportStepState.MATCHING_CANDIDATE_HASH_SUPPLIED
        if result.export_state is PublicExportState.EXPORTED
        else LocalExportStepState.AWAITING_MATCHING_CANDIDATE_HASH
    )
    states = [
        LocalExportStepState.COMPLETED,
        LocalExportStepState.NO_REGISTERED_RULE_BLOCKED,
        confirmation_state,
        LocalExportStepState.WRITTEN_LOCALLY,
        LocalExportStepState.NOT_PERFORMED_BY_TOOL,
    ]
    state_records = [
        LocalExportStateRecord(
            record_id=f"state.{index:03d}",
            step=step,
            state=state,
            evidence_ids=evidence_ids,
            evidence_state=EvidenceState.INFERRED,
            applicability="applicable",
            display_state=state.value,
            reason_codes=[],
        )
        for index, (step, state) in enumerate(
            zip(LocalExportStep, states, strict=True), start=1
        )
    ]
    return ReportExportVisualizationDataV1(
        visualization_profile_id=(
            f"public-safe-export-visualization:{run_id.removeprefix('run-')}"
        ),
        producer_tool_version=tool_version,
        producer_run_ref=f"run:{run_id}",
        source_result_ref=result.export_id,
        source_result_sha256=source_result_sha256,
        evidence_ids=evidence_ids,
        limitations=sorted(
            [
                "Field inclusion reflects the current allowlist; it does not approve the report for publication.",
                "The tool writes local candidate files and performs no network upload.",
                "The visual profile excludes claim text, paths, input identifiers and original internal references.",
                "A matching candidate digest does not authenticate its supplier or constitute approval.",
            ]
        ),
        candidate_hash_state=candidate_hash_state,
        candidate_hash=result.candidate_hash,
        claim_count=len(public_report.claims),
        field_records=field_records,
        state_records=state_records,
    )


def build_artifact_audit_visualization_data(
    *,
    run_id: str,
    tool_version: str,
    result: PublicArtifactAuditResult,
    source_result_sha256: str,
) -> ArtifactAuditVisualizationDataV1:
    evidence_ids = [result.audit_id]
    artifact_records: list[ArtifactStatusRecord] = []
    check_records: list[RegisteredCheckRecord] = []
    for artifact_index, source in enumerate(result.records, start=1):
        display_id = f"Artifact {artifact_index:02d}"
        blocked_checks = [
            check for check in source.checks if check.state is ArtifactCheckState.BLOCKED
        ]
        reasons = sorted(
            {reason for check in blocked_checks for reason in check.reason_codes}
        )
        state = (
            ArtifactDisplayState.BLOCKED_BY_REGISTERED_RULE
            if blocked_checks
            else ArtifactDisplayState.NO_REGISTERED_RULE_BLOCKED
        )
        artifact_records.append(
            ArtifactStatusRecord(
                record_id=f"artifact.{artifact_index:03d}",
                artifact_display_id=display_id,
                declared_format=source.declared_format,
                byte_count=source.byte_count,
                check_count=len(source.checks),
                blocked_check_count=len(blocked_checks),
                audit_state=state,
                evidence_ids=evidence_ids,
                evidence_state=(
                    EvidenceState.ALERT
                    if blocked_checks
                    else EvidenceState.INFERRED
                ),
                applicability="applicable",
                display_state=state.value,
                reason_codes=reasons,
            )
        )
        checks_by_method = {check.method_id: check for check in source.checks}
        for method_id in result.selected_method_ids:
            if method_id not in CHECK_DISPLAY_NAMES:
                raise ValueError("unmapped artifact audit method")
            check = checks_by_method.get(method_id)
            source_state = (
                check.state if check is not None else ArtifactCheckState.NOT_APPLICABLE
            )
            check_state = {
                ArtifactCheckState.PASSED: (
                    RegisteredCheckDisplayState.NO_REGISTERED_RULE_BLOCKED
                ),
                ArtifactCheckState.BLOCKED: (
                    RegisteredCheckDisplayState.BLOCKED_BY_REGISTERED_RULE
                ),
                ArtifactCheckState.NOT_APPLICABLE: (
                    RegisteredCheckDisplayState.NOT_APPLICABLE
                ),
            }[source_state]
            check_records.append(
                RegisteredCheckRecord(
                    record_id="check.pending",
                    artifact_display_id=display_id,
                    method_id=method_id,
                    check_name=CHECK_DISPLAY_NAMES[method_id],
                    check_state=check_state,
                    evidence_ids=evidence_ids,
                    evidence_state=(
                        EvidenceState.ALERT
                        if source_state is ArtifactCheckState.BLOCKED
                        else EvidenceState.INFERRED
                    ),
                    applicability=(
                        "not_applicable"
                        if source_state is ArtifactCheckState.NOT_APPLICABLE
                        else "applicable"
                    ),
                    display_state=check_state.value,
                    reason_codes=[] if check is None else check.reason_codes,
                )
            )
    check_records.sort(key=lambda item: (item.artifact_display_id, item.method_id))
    check_records = [
        item.model_copy(update={"record_id": f"check.{index:03d}"})
        for index, item in enumerate(check_records, start=1)
    ]
    return ArtifactAuditVisualizationDataV1(
        visualization_profile_id=(
            f"public-safe-export-visualization:{run_id.removeprefix('run-')}"
        ),
        producer_tool_version=tool_version,
        producer_run_ref=f"run:{run_id}",
        source_result_ref=result.audit_id,
        source_result_sha256=source_result_sha256,
        evidence_ids=evidence_ids,
        limitations=sorted(
            [
                "No registered rule blocked is limited to the executed checks and is not a general safety or publication decision.",
                "Audit and check counts are descriptive counts, not risk scores or evidence weights.",
                "The visual profile excludes paths, content, original artifact identifiers, source references and runtime environment details.",
            ]
        ),
        overall_display_state=(
            ArtifactDisplayState.BLOCKED_BY_REGISTERED_RULE
            if result.audit_state is ArtifactAuditState.BLOCKED
            else ArtifactDisplayState.NO_REGISTERED_RULE_BLOCKED
        ),
        artifact_count=len(artifact_records),
        registered_method_count=len(result.selected_method_ids),
        artifact_records=artifact_records,
        check_records=check_records,
    )


PUBLIC_VISUALIZATION_SCHEMA_MODELS = {
    PUBLIC_SAFE_EXPORT_VISUALIZATION_DATA_SCHEMA_REF: PublicSafeExportVisualizationDataV1,
    P011_VISUALIZATION_ARTIFACT_SET_SCHEMA_REF: P011VisualizationArtifactSet,
}
