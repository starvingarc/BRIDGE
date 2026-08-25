from __future__ import annotations

from datetime import datetime
from enum import StrEnum
import re
from typing import Annotated, Literal, Self

from pydantic import Field, StrictBool, StrictInt, field_validator, model_validator

from bridge.tool_packages.p0_10_claim_verifier.models import (
    ClaimType,
    ComparisonMode,
    ReportLanguage,
    SHA256_PATTERN,
    STATEMENT_REF_PATTERN,
)
from bridge.toolkit.contracts import EvidenceState, FrozenModel


PRODUCT_CASE_REF = re.compile(
    r"^product-case:[A-Za-z0-9._:-]+@[A-Za-z0-9._:-]+$"
)
PUBLIC_ALIAS = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._-]{0,63}$")
StatementRef = Annotated[str, Field(pattern=STATEMENT_REF_PATTERN)]


class PublicExportChannel(StrEnum):
    PUBLIC_JSON = "public_json"


class PublicClaimField(StrEnum):
    CLAIM_TYPE = "claim_type"
    TEXT = "text"
    LANGUAGE = "language"
    STATEMENT_REFS = "statement_refs"
    REPORTED_EVIDENCE_STATE = "reported_evidence_state"
    COMPARISON_MODE = "comparison_mode"


class PublicExportState(StrEnum):
    READY_FOR_CONFIRMATION = "ready_for_confirmation"
    EXPORTED = "exported"


class PublicExportPolicySpec(FrozenModel):
    object_version: Literal["0.1.0"]
    policy_id: str = Field(pattern=r"^public-export-policy:[A-Za-z0-9._:-]+$")
    policy_version: str = Field(pattern=r"^[A-Za-z0-9._:-]+$")
    active: StrictBool
    report_audience: Literal["public_candidate"]
    target_channels: list[PublicExportChannel] = Field(min_length=1)
    allowlisted_claim_fields: list[PublicClaimField] = Field(min_length=3)
    public_case_aliases: dict[str, str] = Field(min_length=1)
    allowed_statement_refs: list[StatementRef]

    @field_validator(
        "target_channels", "allowlisted_claim_fields", "allowed_statement_refs"
    )
    @classmethod
    def ordered_values_are_unique(cls, value: list[object]) -> list[object]:
        if list(value) != sorted(set(value), key=str):
            raise ValueError("policy lists must be unique and sorted")
        return value

    @field_validator("allowlisted_claim_fields")
    @classmethod
    def core_claim_fields_are_present(
        cls, value: list[PublicClaimField]
    ) -> list[PublicClaimField]:
        required = {
            PublicClaimField.CLAIM_TYPE,
            PublicClaimField.LANGUAGE,
            PublicClaimField.TEXT,
        }
        if not required.issubset(value):
            raise ValueError("claim_type, language and text must be allowlisted")
        return value

    @field_validator("public_case_aliases")
    @classmethod
    def aliases_are_public_and_unique(cls, value: dict[str, str]) -> dict[str, str]:
        if any(not PRODUCT_CASE_REF.fullmatch(key) for key in value):
            raise ValueError("public case aliases require versioned ProductCase refs")
        if any(not PUBLIC_ALIAS.fullmatch(alias) for alias in value.values()):
            raise ValueError("public aliases must use a restricted public label")
        if len(value.values()) != len(set(value.values())):
            raise ValueError("public aliases must be unique")
        return value

    @property
    def ref(self) -> str:
        return f"{self.policy_id}@{self.policy_version}"


class PublicExportRequest(FrozenModel):
    object_version: Literal["0.1.0"]
    export_request_id: str = Field(
        pattern=r"^public-export-request:[A-Za-z0-9._:-]+$"
    )
    report_draft_ref: str = Field(
        pattern=r"^report:[A-Za-z0-9._:-]+@[A-Za-z0-9._:-]+$"
    )
    policy_ref: str = Field(
        pattern=r"^public-export-policy:[A-Za-z0-9._:-]+@[A-Za-z0-9._:-]+$"
    )
    target_channel: PublicExportChannel
    confirmation_hash: str | None = Field(default=None, pattern=SHA256_PATTERN)
    created_at: datetime


class PublicSafeClaim(FrozenModel):
    public_claim_id: str = Field(pattern=r"^public-claim:[a-f0-9]{16}$")
    public_case_alias: str = Field(pattern=PUBLIC_ALIAS.pattern)
    claim_type: ClaimType
    text: str = Field(min_length=1)
    language: ReportLanguage
    statement_refs: list[StatementRef] | None = None
    reported_evidence_state: EvidenceState | None = None
    comparison_mode: ComparisonMode | None = None

    @field_validator("statement_refs")
    @classmethod
    def statement_refs_are_sorted(
        cls, value: list[str] | None
    ) -> list[str] | None:
        if value is not None and value != sorted(set(value)):
            raise ValueError("public statement refs must be unique and sorted")
        return value


class PublicSafeReport(FrozenModel):
    object_version: Literal["0.1.0"]
    public_report_id: str = Field(pattern=r"^public-report:[a-f0-9]{16}$")
    public_report_version: Literal["0.1.0"]
    source_report_sha256: str = Field(pattern=SHA256_PATTERN)
    claim_verification_receipt_sha256: str = Field(pattern=SHA256_PATTERN)
    export_policy_ref: str = Field(
        pattern=r"^public-export-policy:[A-Za-z0-9._:-]+@[A-Za-z0-9._:-]+$"
    )
    target_channel: PublicExportChannel
    claims: list[PublicSafeClaim] = Field(min_length=1)
    created_at: datetime

    @field_validator("claims")
    @classmethod
    def claims_are_unique_and_sorted(
        cls, value: list[PublicSafeClaim]
    ) -> list[PublicSafeClaim]:
        ids = [claim.public_claim_id for claim in value]
        if ids != sorted(set(ids)):
            raise ValueError("public claims must have unique sorted IDs")
        return value


class PublicExportManifestEntry(FrozenModel):
    filename: Literal["public_safe_report.json"]
    media_type: Literal["application/json"]
    sha256: str = Field(pattern=SHA256_PATTERN)
    byte_count: StrictInt = Field(ge=1)


class PublicExportManifest(FrozenModel):
    object_version: Literal["0.1.0"]
    manifest_id: str = Field(pattern=r"^public-export-manifest:[a-f0-9]{16}$")
    tool_id: Literal["P0-11"]
    tool_version: str
    canonicalization_id: Literal["bridge-canonical-json/v0.1"]
    candidate_hash: str = Field(pattern=SHA256_PATTERN)
    export_state: PublicExportState
    confirmation_hash: str | None = Field(default=None, pattern=SHA256_PATTERN)
    entries: list[PublicExportManifestEntry] = Field(min_length=1, max_length=1)

    @model_validator(mode="after")
    def confirmation_matches_state(self) -> Self:
        if self.export_state is PublicExportState.EXPORTED:
            if self.confirmation_hash != self.candidate_hash:
                raise ValueError("exported manifest requires matching confirmation")
        elif self.confirmation_hash is not None:
            raise ValueError("unconfirmed manifest cannot carry confirmation_hash")
        return self


class PublicExportResult(FrozenModel):
    object_version: Literal["0.1.0"]
    export_id: str = Field(pattern=r"^public-export:[a-f0-9]{16}$")
    tool_id: Literal["P0-11"]
    tool_version: str
    export_state: PublicExportState
    candidate_hash: str = Field(pattern=SHA256_PATTERN)
    confirmation_hash: str | None = Field(default=None, pattern=SHA256_PATTERN)
    public_report_sha256: str = Field(pattern=SHA256_PATTERN)
    manifest_sha256: str = Field(pattern=SHA256_PATTERN)
    leak_scan_state: Literal["passed"]
    artifact_count: Literal[3]
    domain_score: None = None
    score_state: Literal["unavailable"]

    @model_validator(mode="after")
    def confirmation_matches_state(self) -> Self:
        if self.export_state is PublicExportState.EXPORTED:
            if self.confirmation_hash != self.candidate_hash:
                raise ValueError("exported result requires matching confirmation")
        elif self.confirmation_hash is not None:
            raise ValueError("unconfirmed result cannot carry confirmation_hash")
        return self


PUBLIC_SCHEMA_MODELS = {
    "bridge://schemas/public-export-policy-spec/v0.1": PublicExportPolicySpec,
    "bridge://schemas/public-export-request/v0.1": PublicExportRequest,
    "bridge://schemas/public-safe-report/v0.1": PublicSafeReport,
    "bridge://schemas/public-export-manifest/v0.1": PublicExportManifest,
    "bridge://schemas/public-export-result/v0.1": PublicExportResult,
}
