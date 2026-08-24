from __future__ import annotations

from enum import StrEnum
import hashlib
import re
from typing import Annotated, Any, Literal, Self

from pydantic import Field, StrictBool, StrictInt, field_validator, model_validator

from bridge.tool_packages._structured_runtime import canonical_json_bytes
from bridge.tool_packages._configurable_contracts import (
    SHA256_PATTERN,
    VERSION_PATTERN,
    VersionedObjectRef,
)
from bridge.tool_packages._publication_safety import contains_unsafe_reference
from bridge.tool_packages.p0_10_claim_verifier.models import (
    ClaimType,
    ComparisonMode,
    DECIMAL_STRING_PATTERN,
    FREE_MARKUP,
    PLAIN_UNIT_PATTERN,
    ReportLanguage,
)
from bridge.toolkit.contracts import EvidenceState, FrozenModel


ReasonCode = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*$")]
PublicClaimId = Annotated[
    str, Field(pattern=r"^public-claim:[A-Za-z0-9._:-]+$")
]
PlainPublicText = Annotated[str, Field(min_length=1, max_length=4000)]
LOCAL_USER_ROOT = "/" + "Users/"
MACHINE_REFERENCE = re.compile(
    r"(?i)(?:" + re.escape(LOCAL_USER_ROOT) + r"|/data[12]/|\\Users\\|file\s*:|"
    r"(?<![A-Za-z0-9-])(?:report|claim|claim-block|evidence|product-case|sample|preparation):|"
    r"(?:password|passphrase|passwd|pwd|secret|token|credential)\s*[:=])"
)


def _plain_public_text(value: str) -> str:
    if (
        not value.strip()
        or any(marker in value for marker in ("\n", "\r", "\x00"))
        or FREE_MARKUP.search(value)
    ):
        raise ValueError("public text must be one plain paragraph")
    return value


def _unique(values: list[Any], field: str) -> list[Any]:
    if len(values) != len(set(values)):
        raise ValueError(f"{field} must contain unique values")
    return values


class ExportState(StrEnum):
    REVIEW_REQUIRED = "review_required"


class PublicClaimSelection(FrozenModel):
    source_claim_id: str = Field(pattern=r"^claim-block:[A-Za-z0-9._:-]+$")
    public_claim_id: PublicClaimId
    public_case_label: PlainPublicText

    _public_case_label_is_plain = field_validator("public_case_label")(
        _plain_public_text
    )


class PublicExportSpec(FrozenModel):
    object_version: Literal["0.1.0"]
    export_spec_id: str = Field(pattern=r"^public-export-spec:[A-Za-z0-9._:-]+$")
    export_spec_version: str = Field(pattern=VERSION_PATTERN)
    source_report_ref: str = Field(
        pattern=r"^report:[A-Za-z0-9._:-]+@[A-Za-z0-9._:-]+$"
    )
    source_report_hash: str = Field(pattern=SHA256_PATTERN)
    claim_verification_id: str = Field(
        pattern=r"^claim-verification:[a-f0-9]{16}$"
    )
    target_language: ReportLanguage
    allowed_claim_types: list[ClaimType] = Field(
        min_length=1, json_schema_extra={"uniqueItems": True}
    )
    allowed_evidence_states: list[EvidenceState] = Field(
        min_length=1, json_schema_extra={"uniqueItems": True}
    )
    allow_claims_without_evidence_state: StrictBool
    selections: list[PublicClaimSelection] = Field(min_length=1)
    public_source_accessions: list[str] = Field(
        default_factory=list, json_schema_extra={"uniqueItems": True}
    )
    prohibited_literals: list[str] = Field(
        min_length=1, json_schema_extra={"uniqueItems": True}
    )
    candidate_policy: Literal["human_confirmation_required"]

    @field_validator("allowed_claim_types", "allowed_evidence_states")
    @classmethod
    def enum_lists_are_unique(cls, value: list[Any]) -> list[Any]:
        return _unique(value, "allowlist")

    @field_validator("selections")
    @classmethod
    def selections_are_unique(
        cls, value: list[PublicClaimSelection]
    ) -> list[PublicClaimSelection]:
        _unique([item.source_claim_id for item in value], "source claim IDs")
        _unique([item.public_claim_id for item in value], "public claim IDs")
        return value

    @field_validator("public_source_accessions")
    @classmethod
    def accessions_are_public_identifiers(cls, value: list[str]) -> list[str]:
        _unique(value, "public source accessions")
        if any(
            not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{1,159}", item)
            for item in value
        ):
            raise ValueError("public source accessions must be explicit identifiers")
        return value

    @field_validator("prohibited_literals")
    @classmethod
    def prohibited_literals_are_usable(cls, value: list[str]) -> list[str]:
        _unique(value, "prohibited literals")
        if any(not item or len(item) > 500 for item in value):
            raise ValueError("prohibited literals must be non-empty and bounded")
        return value

    @property
    def ref(self) -> VersionedObjectRef:
        return VersionedObjectRef(
            object_id=self.export_spec_id,
            object_version=self.export_spec_version,
        )


class PublicValueBinding(FrozenModel):
    binding_index: StrictInt = Field(ge=0)
    source_field: Literal[
        "value", "numerator", "denominator", "interval_lower", "interval_upper"
    ]
    canonical_numeric_string: str = Field(pattern=DECIMAL_STRING_PATTERN)
    raw_unit: str | None = Field(default=None, pattern=PLAIN_UNIT_PATTERN)


class PublicSafeClaim(FrozenModel):
    public_claim_id: PublicClaimId
    public_case_label: PlainPublicText
    claim_type: ClaimType
    text: PlainPublicText
    language: ReportLanguage
    evidence_state: EvidenceState | None
    comparison_mode: ComparisonMode
    value_bindings: list[PublicValueBinding]

    _public_case_label_is_plain = field_validator("public_case_label")(
        _plain_public_text
    )
    _text_is_plain = field_validator("text")(_plain_public_text)


class PublicExportInputChecksums(FrozenModel):
    report_draft: str = Field(pattern=SHA256_PATTERN)
    claim_verification_result: str = Field(pattern=SHA256_PATTERN)
    public_export_spec: str = Field(pattern=SHA256_PATTERN)


class PublicSafeReport(FrozenModel):
    object_version: Literal["0.1.0"]
    public_report_id: str = Field(pattern=r"^public-report:[a-f0-9]{16}$")
    public_report_version: Literal["0.1.0"]
    tool_id: Literal["P0-11"]
    tool_version: str = Field(pattern=VERSION_PATTERN)
    source_report_hash: str = Field(pattern=SHA256_PATTERN)
    claim_verification_sha256: str = Field(pattern=SHA256_PATTERN)
    export_spec_ref: VersionedObjectRef
    input_sha256_by_role: PublicExportInputChecksums
    language: ReportLanguage
    public_source_accessions: list[str] = Field(
        json_schema_extra={"uniqueItems": True}
    )
    claims: list[PublicSafeClaim] = Field(min_length=1)
    export_state: ExportState
    checks: list[
        Literal[
            "allowlist_projection_passed",
            "configured_literals_absent",
            "bounded_machine_reference_guard_passed",
        ]
    ] = Field(min_length=3, max_length=3, json_schema_extra={"uniqueItems": True})
    reason_codes: list[ReasonCode] = Field(json_schema_extra={"uniqueItems": True})
    candidate_hash: str = Field(pattern=SHA256_PATTERN)

    @field_validator("public_source_accessions", "reason_codes")
    @classmethod
    def string_lists_are_unique_sorted(cls, value: list[str]) -> list[str]:
        if value != sorted(set(value)):
            raise ValueError("public report lists must be unique and sorted")
        return value

    @field_validator("claims")
    @classmethod
    def claims_are_unique_sorted(
        cls, value: list[PublicSafeClaim]
    ) -> list[PublicSafeClaim]:
        ids = [item.public_claim_id for item in value]
        if ids != sorted(set(ids)):
            raise ValueError("public claims must be unique and sorted")
        return value

    @field_validator("checks")
    @classmethod
    def all_checks_are_present(cls, value: list[str]) -> list[str]:
        expected = {
            "allowlist_projection_passed",
            "configured_literals_absent",
            "bounded_machine_reference_guard_passed",
        }
        if set(value) != expected:
            raise ValueError("public report requires all deterministic checks")
        return value

    @model_validator(mode="after")
    def state_and_hash_are_coherent(self) -> Self:
        if self.export_state is not ExportState.REVIEW_REQUIRED:
            raise ValueError("public export requires review while authority is absent")
        if "public_release_authority_not_configured" not in self.reason_codes:
            raise ValueError("public export must disclose missing release authority")
        if contains_machine_reference(self.model_dump(mode="json")):
            raise ValueError("bounded machine reference remains")
        if self.candidate_hash != public_safe_report_hash(
            self.model_dump(mode="json")
        ):
            raise ValueError("candidate_hash does not match public report")
        return self


def public_safe_report_hash(payload: dict[str, Any]) -> str:
    content = dict(payload)
    content.pop("candidate_hash", None)
    return hashlib.sha256(canonical_json_bytes(content)).hexdigest()


def contains_machine_reference(value: Any) -> bool:
    if contains_unsafe_reference(value):
        return True
    if isinstance(value, str):
        return bool(MACHINE_REFERENCE.search(value))
    if isinstance(value, dict):
        return any(contains_machine_reference(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(contains_machine_reference(item) for item in value)
    return False


PUBLIC_SCHEMA_MODELS = {
    "bridge://schemas/public-export-spec/v0.1": PublicExportSpec,
    "bridge://schemas/public-safe-report/v0.1": PublicSafeReport,
}
