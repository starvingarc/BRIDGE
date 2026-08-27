from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import Path
import re
from typing import Literal, Self

from pydantic import Field, StrictBool, StrictInt, field_validator, model_validator

from bridge.tool_packages.p0_10_claim_verifier.models import SHA256_PATTERN
from bridge.toolkit.contracts import FrozenModel


ARTIFACT_ID_PATTERN = r"^public-artifact:[A-Za-z0-9._:-]+$"
VERSION_PATTERN = r"^[A-Za-z0-9._:-]+$"
PUBLIC_REF_PATTERN = r"^public-source:[A-Za-z0-9._:-]+@[A-Za-z0-9._:-]+$"
METHOD_ID_PATTERN = r"^METHOD-[A-Z0-9-]+$"
MEDIA_TYPE_PATTERN = r"^[A-Za-z0-9!#$&^_.+\-]+/[A-Za-z0-9!#$&^_.+\-]+$"
HOST_PATTERN = re.compile(
    r"^(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)"
    r"(?:\.(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?))*$"
)


class PublicArtifactFormat(StrEnum):
    JSON = "json"
    MARKDOWN = "markdown"
    CSV = "csv"
    SVG = "svg"


class ArtifactAuditState(StrEnum):
    PASSED = "passed"
    BLOCKED = "blocked"


class ArtifactCheckState(StrEnum):
    PASSED = "passed"
    BLOCKED = "blocked"
    NOT_APPLICABLE = "not_applicable"


class PublicArtifactFileRef(FrozenModel):
    artifact_id: str = Field(pattern=ARTIFACT_ID_PATTERN)
    source_artifact_ref: str = Field(pattern=PUBLIC_REF_PATTERN)
    path: Path = Field(json_schema_extra={"pattern": r"^/"})
    format: PublicArtifactFormat
    media_type: str = Field(pattern=MEDIA_TYPE_PATTERN)
    sha256: str = Field(pattern=SHA256_PATTERN)

    @field_validator("path")
    @classmethod
    def path_is_absolute(cls, value: Path) -> Path:
        if not value.is_absolute():
            raise ValueError("public artifact path must be absolute")
        return value


class PublicArtifactAuditPolicy(FrozenModel):
    object_version: Literal["0.1.0"]
    policy_id: str = Field(
        pattern=r"^public-artifact-policy:[A-Za-z0-9._:-]+$"
    )
    policy_version: str = Field(pattern=VERSION_PATTERN)
    active: StrictBool
    allowed_formats: list[PublicArtifactFormat] = Field(min_length=1)
    max_file_bytes: StrictInt = Field(ge=1, le=50_000_000)
    allowed_url_schemes: list[Literal["https"]]
    allowed_url_hosts: list[str]
    json_schema_refs: dict[str, str]
    csv_column_allowlists: dict[str, list[str]]

    @field_validator(
        "allowed_formats", "allowed_url_schemes", "allowed_url_hosts"
    )
    @classmethod
    def ordered_lists_are_unique(
        cls, value: list[object]
    ) -> list[object]:
        if value != sorted(set(value), key=str):
            raise ValueError("artifact policy lists must be unique and sorted")
        return value

    @field_validator("allowed_url_hosts")
    @classmethod
    def hosts_are_public_names(cls, value: list[str]) -> list[str]:
        if any(not HOST_PATTERN.fullmatch(host) for host in value):
            raise ValueError("allowed URL hosts must be DNS names")
        return value

    @field_validator("json_schema_refs")
    @classmethod
    def json_schema_bindings_are_typed(
        cls, value: dict[str, str]
    ) -> dict[str, str]:
        if any(
            not re.fullmatch(ARTIFACT_ID_PATTERN, artifact_id)
            or not schema_ref.startswith("bridge://schemas/")
            for artifact_id, schema_ref in value.items()
        ):
            raise ValueError(
                "JSON Schema bindings require artifact IDs and BRIDGE schemas"
            )
        return value

    @field_validator("csv_column_allowlists")
    @classmethod
    def csv_columns_are_unique(
        cls, value: dict[str, list[str]]
    ) -> dict[str, list[str]]:
        for artifact_id, columns in value.items():
            if not re.fullmatch(ARTIFACT_ID_PATTERN, artifact_id):
                raise ValueError("CSV allowlists require artifact IDs")
            if not columns or columns != sorted(set(columns)):
                raise ValueError(
                    "CSV columns must be non-empty, unique and sorted"
                )
            if any(
                not column
                or any(char in column for char in "\r\n\x00")
                for column in columns
            ):
                raise ValueError("CSV columns contain unsafe text")
        return value

    @property
    def ref(self) -> str:
        return f"{self.policy_id}@{self.policy_version}"


class PublicArtifactManifest(FrozenModel):
    object_version: Literal["0.1.0"]
    manifest_id: str = Field(
        pattern=r"^public-artifact-manifest:[A-Za-z0-9._:-]+$"
    )
    manifest_version: str = Field(pattern=VERSION_PATTERN)
    policy_ref: str = Field(
        pattern=(
            r"^public-artifact-policy:[A-Za-z0-9._:-]+"
            r"@[A-Za-z0-9._:-]+$"
        )
    )
    artifacts: list[PublicArtifactFileRef] = Field(
        min_length=1, max_length=20
    )
    created_at: datetime

    @field_validator("artifacts")
    @classmethod
    def artifact_refs_are_unique(
        cls, value: list[PublicArtifactFileRef]
    ) -> list[PublicArtifactFileRef]:
        ids = [item.artifact_id for item in value]
        if ids != sorted(set(ids)):
            raise ValueError("artifact IDs must be unique and sorted")
        paths = [item.path.resolve(strict=False) for item in value]
        if len(paths) != len(set(paths)):
            raise ValueError("artifact paths cannot repeat or alias")
        return value

    @property
    def ref(self) -> str:
        return f"{self.manifest_id}@{self.manifest_version}"


class PublicArtifactCheck(FrozenModel):
    method_id: str = Field(pattern=METHOD_ID_PATTERN)
    implementation: str = Field(min_length=1)
    state: ArtifactCheckState
    reason_codes: list[str]

    @model_validator(mode="after")
    def state_and_reasons_are_coherent(self) -> Self:
        if self.reason_codes != sorted(set(self.reason_codes)):
            raise ValueError(
                "artifact check reason codes must be unique and sorted"
            )
        if (
            self.state is ArtifactCheckState.BLOCKED
        ) != bool(self.reason_codes):
            raise ValueError("only blocked checks carry reason codes")
        return self


class PublicArtifactAuditRecord(FrozenModel):
    artifact_id: str = Field(pattern=ARTIFACT_ID_PATTERN)
    source_artifact_ref: str = Field(pattern=PUBLIC_REF_PATTERN)
    source_sha256: str = Field(pattern=SHA256_PATTERN)
    declared_format: PublicArtifactFormat
    declared_media_type: str = Field(pattern=MEDIA_TYPE_PATTERN)
    detected_media_type: str = Field(pattern=MEDIA_TYPE_PATTERN)
    byte_count: StrictInt = Field(ge=1)
    audit_state: ArtifactAuditState
    checks: list[PublicArtifactCheck] = Field(min_length=1)

    @model_validator(mode="after")
    def record_state_matches_checks(self) -> Self:
        method_ids = [item.method_id for item in self.checks]
        if method_ids != sorted(set(method_ids)):
            raise ValueError(
                "artifact checks must have unique sorted method IDs"
            )
        blocked = any(
            item.state is ArtifactCheckState.BLOCKED
            for item in self.checks
        )
        if blocked != (
            self.audit_state is ArtifactAuditState.BLOCKED
        ):
            raise ValueError("artifact audit state must match checks")
        return self


class PublicArtifactAuditResult(FrozenModel):
    object_version: Literal["0.1.0"]
    audit_id: str = Field(
        pattern=r"^public-artifact-audit:[a-f0-9]{16}$"
    )
    tool_id: Literal["P0-11"]
    tool_version: str = Field(pattern=VERSION_PATTERN)
    policy_ref: str = Field(
        pattern=(
            r"^public-artifact-policy:[A-Za-z0-9._:-]+"
            r"@[A-Za-z0-9._:-]+$"
        )
    )
    policy_sha256: str = Field(pattern=SHA256_PATTERN)
    manifest_ref: str = Field(
        pattern=(
            r"^public-artifact-manifest:[A-Za-z0-9._:-]+"
            r"@[A-Za-z0-9._:-]+$"
        )
    )
    manifest_sha256: str = Field(pattern=SHA256_PATTERN)
    audit_state: ArtifactAuditState
    records: list[PublicArtifactAuditRecord] = Field(min_length=1)
    selected_method_ids: list[str] = Field(min_length=1)
    runtime_versions: dict[str, str]
    created_at: datetime
    domain_score: None = None
    score_state: Literal["unavailable"] = "unavailable"

    @model_validator(mode="after")
    def result_is_coherent(self) -> Self:
        ids = [item.artifact_id for item in self.records]
        if ids != sorted(set(ids)):
            raise ValueError(
                "artifact audit records must be unique and sorted"
            )
        selected = sorted(
            {
                check.method_id
                for record in self.records
                for check in record.checks
            }
        )
        if self.selected_method_ids != selected:
            raise ValueError(
                "selected methods must match executed checks"
            )
        blocked = any(
            item.audit_state is ArtifactAuditState.BLOCKED
            for item in self.records
        )
        if blocked != (
            self.audit_state is ArtifactAuditState.BLOCKED
        ):
            raise ValueError("overall audit state must match records")
        return self


PUBLIC_SCHEMA_MODELS = {
    (
        "bridge://schemas/public-artifact-audit-policy/v0.1"
    ): PublicArtifactAuditPolicy,
    (
        "bridge://schemas/public-artifact-manifest/v0.1"
    ): PublicArtifactManifest,
    (
        "bridge://schemas/public-artifact-audit-result/v0.1"
    ): PublicArtifactAuditResult,
}
