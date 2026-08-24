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
ReviewClaimId = Annotated[
    str, Field(pattern=r"^review-claim:[A-Za-z0-9._:-]+$")
]
PlainReviewText = Annotated[str, Field(min_length=1, max_length=4000)]
LOCAL_USER_ROOT = "/" + "Users/"
MACHINE_REFERENCE = re.compile(
    r"(?i)(?:" + re.escape(LOCAL_USER_ROOT) + r"|/data[12]/|\\Users\\|file\s*:|"
    r"(?<![A-Za-z0-9-])(?:report|claim|claim-block|evidence|product-case|sample|preparation):|"
    r"(?:password|passphrase|passwd|pwd|secret|token|credential)\s*[:=])"
)


def _plain_review_text(value: str) -> str:
    if (
        not value.strip()
        or any(marker in value for marker in ("\n", "\r", "\x00"))
        or FREE_MARKUP.search(value)
    ):
        raise ValueError("review text must be one plain paragraph")
    return value


def _unique(values: list[Any], field: str) -> list[Any]:
    if len(values) != len(set(values)):
        raise ValueError(f"{field} must contain unique values")
    return values


class ProjectionState(StrEnum):
    REVIEW_REQUIRED = "review_required"


class ReviewClaimSelection(FrozenModel):
    source_claim_id: str = Field(pattern=r"^claim-block:[A-Za-z0-9._:-]+$")
    review_claim_id: ReviewClaimId
    review_case_label: PlainReviewText

    _review_case_label_is_plain = field_validator("review_case_label")(
        _plain_review_text
    )


class ReviewProjectionSpec(FrozenModel):
    object_version: Literal["0.1.0"]
    projection_spec_id: str = Field(
        pattern=r"^review-projection-spec:[A-Za-z0-9._:-]+$"
    )
    projection_spec_version: str = Field(pattern=VERSION_PATTERN)
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
    selections: list[ReviewClaimSelection] = Field(min_length=1)
    source_accessions: list[str] = Field(
        default_factory=list, json_schema_extra={"uniqueItems": True}
    )
    prohibited_literals: list[str] = Field(
        min_length=1, json_schema_extra={"uniqueItems": True}
    )
    review_policy: Literal["human_review_required"]

    @field_validator("allowed_claim_types", "allowed_evidence_states")
    @classmethod
    def enum_lists_are_unique(cls, value: list[Any]) -> list[Any]:
        return _unique(value, "allowlist")

    @field_validator("selections")
    @classmethod
    def selections_are_unique(
        cls, value: list[ReviewClaimSelection]
    ) -> list[ReviewClaimSelection]:
        _unique([item.source_claim_id for item in value], "source claim IDs")
        _unique([item.review_claim_id for item in value], "review claim IDs")
        return value

    @field_validator("source_accessions")
    @classmethod
    def accessions_are_public_identifiers(cls, value: list[str]) -> list[str]:
        _unique(value, "source accessions")
        if any(
            not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{1,159}", item)
            for item in value
        ):
            raise ValueError("source accessions must be explicit identifiers")
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
            object_id=self.projection_spec_id,
            object_version=self.projection_spec_version,
        )


class ReviewValueBinding(FrozenModel):
    binding_index: StrictInt = Field(ge=0)
    source_field: Literal[
        "value", "numerator", "denominator", "interval_lower", "interval_upper"
    ]
    canonical_numeric_string: str = Field(pattern=DECIMAL_STRING_PATTERN)
    raw_unit: str | None = Field(default=None, pattern=PLAIN_UNIT_PATTERN)


class ReviewProjectedClaim(FrozenModel):
    review_claim_id: ReviewClaimId
    review_case_label: PlainReviewText
    claim_type: ClaimType
    text: PlainReviewText
    language: ReportLanguage
    evidence_state: EvidenceState | None
    comparison_mode: ComparisonMode
    value_bindings: list[ReviewValueBinding]

    _review_case_label_is_plain = field_validator("review_case_label")(
        _plain_review_text
    )
    _text_is_plain = field_validator("text")(_plain_review_text)


class ReviewProjectionInputChecksums(FrozenModel):
    report_draft: str = Field(pattern=SHA256_PATTERN)
    claim_verification_result: str = Field(pattern=SHA256_PATTERN)
    claim_verifier_run: str = Field(pattern=SHA256_PATTERN)
    review_projection_spec: str = Field(pattern=SHA256_PATTERN)


class ContractValidatedReviewProjection(FrozenModel):
    object_version: Literal["0.1.0"]
    projection_id: str = Field(pattern=r"^review-projection:[a-f0-9]{16}$")
    projection_version: Literal["0.1.0"]
    tool_id: Literal["P0-11"]
    tool_version: str = Field(pattern=VERSION_PATTERN)
    source_report_hash: str = Field(pattern=SHA256_PATTERN)
    claim_verification_sha256: str = Field(pattern=SHA256_PATTERN)
    projection_spec_ref: VersionedObjectRef
    input_sha256_by_role: ReviewProjectionInputChecksums
    language: ReportLanguage
    source_accessions: list[str] = Field(
        json_schema_extra={"uniqueItems": True}
    )
    claims: list[ReviewProjectedClaim] = Field(min_length=1)
    producer_authentication_state: Literal["not_available"]
    release_authority_state: Literal["not_configured"]
    distribution_state: Literal["internal_review_only"]
    projection_state: ProjectionState
    checks: list[
        Literal[
            "allowlist_projection_passed",
            "configured_literals_absent",
            "bounded_machine_reference_guard_passed",
        ]
    ] = Field(min_length=3, max_length=3, json_schema_extra={"uniqueItems": True})
    reason_codes: list[ReasonCode] = Field(json_schema_extra={"uniqueItems": True})
    projection_hash: str = Field(pattern=SHA256_PATTERN)

    @field_validator("source_accessions", "reason_codes")
    @classmethod
    def string_lists_are_unique_sorted(cls, value: list[str]) -> list[str]:
        if value != sorted(set(value)):
            raise ValueError("review projection lists must be unique and sorted")
        return value

    @field_validator("claims")
    @classmethod
    def claims_are_unique_sorted(
        cls, value: list[ReviewProjectedClaim]
    ) -> list[ReviewProjectedClaim]:
        ids = [item.review_claim_id for item in value]
        if ids != sorted(set(ids)):
            raise ValueError("review claims must be unique and sorted")
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
            raise ValueError("review projection requires all deterministic checks")
        return value

    @model_validator(mode="after")
    def state_and_hash_are_coherent(self) -> Self:
        if self.projection_state is not ProjectionState.REVIEW_REQUIRED:
            raise ValueError("projection requires review")
        required_reasons = {
            "producer_provenance_unverified",
            "public_release_authority_not_configured",
        }
        if not required_reasons.issubset(self.reason_codes):
            raise ValueError("projection must disclose unavailable producer and authority")
        if contains_machine_reference(self.model_dump(mode="json")):
            raise ValueError("bounded machine reference remains")
        if self.projection_hash != review_projection_hash(
            self.model_dump(mode="json")
        ):
            raise ValueError("projection_hash does not match review projection")
        return self


def review_projection_hash(payload: dict[str, Any]) -> str:
    content = dict(payload)
    content.pop("projection_hash", None)
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
    "bridge://schemas/review-projection-spec/v0.1": ReviewProjectionSpec,
    "bridge://schemas/contract-validated-review-projection/v0.1": (
        ContractValidatedReviewProjection
    ),
}
