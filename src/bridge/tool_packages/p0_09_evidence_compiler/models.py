from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
import json
import math
import re
from typing import Any, Literal, Self
from urllib.parse import parse_qsl, urlsplit

from pydantic import Field, SkipValidation, field_serializer, field_validator, model_validator

from bridge.tool_packages.p0_08_evidence_sufficiency.models import (
    EvidenceSufficiencyProfile,
    P0DomainId,
)
from bridge.toolkit.contracts import EvidenceState, FrozenModel


CANONICALIZATION_ID = "bridge-canonical-json/v0.1"
COMPILER_VERSION = "0.2.0"
SHA256_PATTERN = r"^[0-9a-f]{64}$"
EVIDENCE_REF_PATTERN = r"^evidence:[a-f0-9]{24}@[1-9][0-9]*$"
REQUIREMENT_REF_PATTERN = r"^requirement:[a-f0-9]{24}@[1-9][0-9]*$"


class GraphKind(StrEnum):
    CASE = "case"
    COMPARISON = "comparison"


class RegistryStatus(StrEnum):
    CANDIDATE = "candidate"
    FROZEN = "frozen"
    RETIRED = "retired"


class EvidenceTier(StrEnum):
    FORMAL = "formal"
    SHADOW = "shadow"
    EXPLORATORY = "exploratory"


class EvidenceLifecycleState(StrEnum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    INVALIDATED = "invalidated"


class EvidenceApplicability(StrEnum):
    APPLICABLE = "applicable"
    NOT_APPLICABLE = "not_applicable"
    NOT_ASSESSED = "not_assessed"


class EvidenceRelation(StrEnum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"


class RevisionAction(StrEnum):
    CREATE = "create"
    SUPERSEDE = "supersede"
    INVALIDATE = "invalidate"


class EvidenceFamilyStatus(StrEnum):
    REVIEWED = "reviewed"
    UNREVIEWED = "unreviewed"
    RETIRED = "retired"


class EvidenceFamilyType(StrEnum):
    SHARED_DATA = "shared_data"
    SHARED_ALGORITHM = "shared_algorithm"
    SHARED_REFERENCE = "shared_reference"
    SHARED_PRIOR = "shared_prior"
    SHARED_KNOWLEDGE = "shared_knowledge"
    SHARED_AGGREGATION = "shared_aggregation"


class EvidenceRequirementState(StrEnum):
    OPEN = "open"
    SATISFIED = "satisfied"
    NOT_APPLICABLE = "not_applicable"


class ReconciliationEligibility(StrEnum):
    ELIGIBLE = "eligible"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    NOT_ASSESSED = "not_assessed"


class ReconciliationState(StrEnum):
    STABLE = "stable"
    CONSENSUS_SUPPORTED = "consensus_supported"
    INTEGRATION_SENSITIVE = "integration_sensitive"
    UNSTABLE = "unstable"


class CompilationDisposition(StrEnum):
    CREATED = "created"
    APPENDED = "appended"
    UNCHANGED = "unchanged"
    REJECTED = "rejected"


class GraphNodeType(StrEnum):
    PRODUCT_CASE = "ProductCase"
    PRODUCT_DEFINITION_CARD = "ProductDefinitionCard"
    SAMPLE = "Sample"
    PREPARATION = "Preparation"
    MEASUREMENT_SPEC = "MeasurementSpec"
    SCORE_CONTRACT = "ScoreContract"
    TOOL_RUN = "ToolRun"
    MEASUREMENT_RESULT = "MeasurementResult"
    EVIDENCE_RECORD = "EvidenceRecord"
    CLAIM = "Claim"
    EVIDENCE_FAMILY = "EvidenceFamily"
    EVIDENCE_REQUIREMENT = "EvidenceRequirement"
    EVIDENCE_SUFFICIENCY_PROFILE = "EvidenceSufficiencyProfile"
    REFERENCE_SNAPSHOT = "ReferenceSnapshot"
    PRIOR_SNAPSHOT = "PriorSnapshot"
    ARTIFACT = "Artifact"
    COMPARISON_RECORD = "ComparisonRecord"
    RECONCILIATION_SPEC = "ReconciliationSpec"
    RECONCILIATION_RECORD = "ReconciliationRecord"


class GraphEdgeType(StrEnum):
    DERIVED_FROM = "derived_from"
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    DEPENDS_ON = "depends_on"
    APPLICABLE_TO = "applicable_to"
    MISSING_FOR = "missing_for"
    BELONGS_TO_EVIDENCE_FAMILY = "belongs_to_evidence_family"
    SUPERSEDES = "supersedes"
    INVALIDATES = "invalidates"


class GraphRecordMode(StrEnum):
    OWNED = "owned"
    EXTERNAL_REF = "external_ref"


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(timezone.utc)


def _strip(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("string values must not be blank")
    if _unsafe_publication_string(value):
        raise ValueError("unsafe path or credential-like string is forbidden")
    return value


def publication_ref(value: str) -> str:
    """Validate a string that can be copied into a public P0-09 artifact.

    This is an identifier/URI-shape allowlist at the P0-09 publication boundary,
    not a general-purpose secret scanner.
    """

    value = _strip(value)
    if not PUBLICATION_REF_PATTERN.fullmatch(value):
        raise ValueError("published references must be scheme- or identifier-shaped")
    return value


def _unique(values: list[Any], field_name: str) -> list[Any]:
    keys = [str(value) for value in values]
    if len(keys) != len(set(keys)):
        raise ValueError(f"{field_name} must not contain duplicates")
    return values


def _sort_json_list(values: list[Any]) -> list[Any]:
    return sorted(
        values,
        key=lambda value: json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ),
    )


PROHIBITED_VALUE_KEYS = {
    "_".join(("integrated", "score")),
    "_".join(("evidence", "confidence", "score")),
    "_".join(("potency", "proxy")),
    "_".join(("overall", "score")),
    "_".join(("overall", "rank")),
    "_".join(("product", "pass")),
    "_".join(("negative", "pass")),
}
PRIVATE_PATH_KEYS = {
    "path",
    "file_path",
    "source_path",
    "input_path",
    "output_path",
    "server_path",
}
PUBLICATION_REF_PATTERN = re.compile(
    r"^(?:[A-Za-z][A-Za-z0-9+.-]*://[^\s]+|"
    r"[A-Za-z][A-Za-z0-9._-]*(?::[A-Za-z0-9._:/-]+)?)$"
)
PUBLICATION_VERSION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]*$")
WINDOWS_ABSOLUTE_PATH = re.compile(
    r"(?:^|[\s=:'\"(])(?:[A-Za-z]:[\\/]|\\\\[^\\\s]+\\[^\\\s]+)"
)
EMBEDDED_POSIX_PATH = re.compile(
    r"(?:^|[\s=:'\"(])/(?!/)(?:[A-Za-z0-9._~-]+/)+[^\s<>\"']*"
)
URI_URL = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://[^\s<>\"']+")
FILE_URI = re.compile(r"(?i)(?<![A-Za-z0-9+.-])file:")
HOME_RELATIVE_PATH = re.compile(
    r"(?:^|[\s=:'\"(])(?:~[A-Za-z0-9._-]*|\$HOME|\$\{HOME\}|"
    r"\$USERPROFILE|\$\{USERPROFILE\}|\$HOMEPATH|\$\{HOMEPATH\}|"
    r"%HOME%|%USERPROFILE%|%HOMEPATH%)[\\/]",
    re.IGNORECASE,
)
HOME_VARIABLE_NAMES = frozenset({"home", "userprofile", "homepath"})
CREDENTIAL_EXACT_NAMES = frozenset({"auth", "authorization"})
CREDENTIAL_SUFFIXES = (
    "password",
    "passphrase",
    "passwd",
    "pwd",
    "secret",
    "token",
    "credential",
    "credentials",
    "passcode",
    "pincode",
)
CREDENTIAL_KEY_QUALIFIERS = frozenset(
    {
        "api",
        "access",
        "account",
        "client",
        "consumer",
        "database",
        "db",
        "master",
        "private",
        "service",
        "signing",
        "ssh",
        "webhook",
        "encryption",
        "decryption",
        "secret",
    }
)
PIN_CONTEXT_QUALIFIERS = frozenset(
    {
        "access",
        "account",
        "auth",
        "authorization",
        "credential",
        "device",
        "login",
        "security",
        "user",
        "verification",
    }
)
BEARER_CREDENTIAL = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{8,}")
COMMON_CREDENTIAL_TOKEN = re.compile(
    r"(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"sk-[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16})"
)
ASSIGNMENT = re.compile(
    r"(?:^|[\s?&,;])([A-Za-z][A-Za-z0-9_.-]{1,64})\s*[:=]\s*([^\s,;}\]]+)"
)


def _normalized_name(value: object) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "", str(value)).casefold()


def _is_credential_name(value: object) -> bool:
    compact = _normalized_name(value)
    if compact in CREDENTIAL_EXACT_NAMES or compact.endswith(CREDENTIAL_SUFFIXES):
        return True
    if compact.endswith("pin"):
        stem = compact[:-3]
        return any(
            stem.startswith(qualifier) or stem.endswith(qualifier)
            for qualifier in PIN_CONTEXT_QUALIFIERS
        )
    if not compact.endswith("key"):
        return False
    stem = compact[:-3]
    return any(
        stem.startswith(qualifier) or stem.endswith(qualifier)
        for qualifier in CREDENTIAL_KEY_QUALIFIERS
    )


def _nonempty(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (dict, list, tuple)):
        return bool(value)
    return True


def _unsafe_publication_string(value: str) -> bool:
    stripped = value.strip()
    if not stripped:
        return False
    if (
        stripped.startswith(("/", "\\\\"))
        or WINDOWS_ABSOLUTE_PATH.search(stripped)
        or EMBEDDED_POSIX_PATH.search(stripped)
        or HOME_RELATIVE_PATH.search(stripped)
        or FILE_URI.search(stripped)
    ):
        return True
    if BEARER_CREDENTIAL.search(stripped) or COMMON_CREDENTIAL_TOKEN.search(stripped):
        return True
    for name, assigned in ASSIGNMENT.findall(stripped):
        if assigned and (
            _is_credential_name(name) or _normalized_name(name) in HOME_VARIABLE_NAMES
        ):
            return True
    for url in URI_URL.findall(stripped):
        parsed = urlsplit(url.rstrip(".,);]"))
        if parsed.scheme.casefold() == "file" or parsed.username or parsed.password:
            return True
        if any(
            _is_credential_name(key) and bool(item)
            for key, item in parse_qsl(parsed.query, keep_blank_values=True)
        ):
            return True
    return False


def contains_unsafe_reference(value: Any) -> bool:
    if isinstance(value, str):
        return _unsafe_publication_string(value)
    if isinstance(value, dict):
        return any(
            _unsafe_publication_string(str(key))
            or str(key).lower() in PRIVATE_PATH_KEYS
            or (_normalized_name(key) in HOME_VARIABLE_NAMES and _nonempty(item))
            or (_is_credential_name(key) and _nonempty(item))
            or contains_unsafe_reference(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(contains_unsafe_reference(item) for item in value)
    return False


def publication_version(value: str) -> str:
    value = _strip(value)
    if not PUBLICATION_VERSION_PATTERN.fullmatch(value):
        raise ValueError("published object versions must be identifier-shaped")
    return value


def validate_safe_json(value: Any, *, location: str = "value") -> Any:
    if isinstance(value, str):
        _strip(value)
        return value
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float)):
        if not math.isfinite(float(value)):
            raise ValueError(f"{location} contains a non-finite number")
        return value
    if isinstance(value, list):
        for index, item in enumerate(value):
            validate_safe_json(item, location=f"{location}[{index}]")
        return value
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key)
            if key_text in PROHIBITED_VALUE_KEYS:
                raise ValueError(f"{location} contains prohibited legacy score field")
            if key_text.lower() in PRIVATE_PATH_KEYS:
                raise ValueError(f"{location} contains a private path field")
            validate_safe_json(item, location=f"{location}.{key_text}")
        return value
    raise ValueError(f"{location} must contain JSON-compatible values")


class VersionedObjectRef(FrozenModel):
    object_id: str = Field(min_length=1)
    object_version: str = Field(min_length=1)

    _publishable_id = field_validator("object_id")(publication_ref)
    _publishable_version = field_validator("object_version")(publication_version)

    @property
    def ref(self) -> str:
        return f"{self.object_id}@{self.object_version}"


class CompilationObjectRef(VersionedObjectRef):
    node_type: GraphNodeType
    schema_ref: str = Field(min_length=1)
    content_hash: str = Field(pattern=SHA256_PATTERN)

    _publishable_schema = field_validator("schema_ref")(publication_ref)


class BiologicalContext(FrozenModel):
    context_id: str = Field(min_length=1)
    context_version: str = Field(min_length=1)
    species: str | None = None
    assay: str | None = None
    specimen: str | None = None
    anatomy: str | None = None
    developmental_stage: str | None = None
    product_stage: str | None = None
    sampling_context: str | None = None

    _publishable_context_id = field_validator("context_id")(publication_ref)
    _publishable_context_version = field_validator("context_version")(publication_version)

    @field_validator("context_id", "context_version")
    @classmethod
    def strip_required(cls, value: str) -> str:
        return _strip(value)

    @field_validator(
        "species",
        "assay",
        "specimen",
        "anatomy",
        "developmental_stage",
        "product_stage",
        "sampling_context",
    )
    @classmethod
    def strip_optional(cls, value: str | None) -> str | None:
        return None if value is None else _strip(value)


class EvidenceInterval(FrozenModel):
    lower: float
    upper: float
    confidence_level: float | None = Field(default=None, gt=0, lt=1)
    method_ref: str | None = None

    @field_validator("method_ref")
    @classmethod
    def publishable_method_ref(cls, value: str | None) -> str | None:
        return None if value is None else publication_ref(value)

    @model_validator(mode="after")
    def finite_ordered_interval(self) -> Self:
        if not math.isfinite(self.lower) or not math.isfinite(self.upper):
            raise ValueError("interval bounds must be finite")
        if self.lower > self.upper:
            raise ValueError("interval lower bound cannot exceed upper bound")
        if self.confidence_level is not None and not math.isfinite(self.confidence_level):
            raise ValueError("confidence level must be finite")
        return self


class BaseGraphRef(FrozenModel):
    graph_id: str = Field(min_length=1)
    graph_version: int = Field(ge=1)
    manifest_sha256: str = Field(pattern=SHA256_PATTERN)

    _publishable_graph_id = field_validator("graph_id")(publication_ref)


class CaseGraphRef(BaseGraphRef):
    product_case_ref: VersionedObjectRef


class ExternalCaseEvidenceRef(FrozenModel):
    source_case_graph_ref: CaseGraphRef
    evidence_ref: str = Field(pattern=EVIDENCE_REF_PATTERN)
    evidence_content_hash: str = Field(pattern=SHA256_PATTERN)
    product_case_ref: VersionedObjectRef
    source_claim_ref: VersionedObjectRef
    comparison_claim_ref: VersionedObjectRef
    evidence_family_ref: VersionedObjectRef
    sufficiency_profile_input_id: str = Field(min_length=1)
    relation: EvidenceRelation
    evidence_state: EvidenceState
    evidence_tier: EvidenceTier
    lifecycle_state: EvidenceLifecycleState
    applicability: EvidenceApplicability
    tool_run_execution_state: Literal[
        "succeeded", "partial", "failed", "skipped", "not_implemented"
    ]


class EvidenceRecord(FrozenModel):
    evidence_id: str = Field(pattern=r"^evidence:[a-f0-9]{24}$")
    evidence_version: int = Field(ge=1)
    logical_key: str = Field(min_length=1)
    content_hash: str = Field(pattern=SHA256_PATTERN)
    product_case_ref: VersionedObjectRef
    sample_or_preparation_ref: VersionedObjectRef
    domain_id: P0DomainId
    measurement_result_ref: VersionedObjectRef
    measurement_spec_ref: VersionedObjectRef
    score_contract_ref: VersionedObjectRef | None = None
    metric_id: str = Field(min_length=1)
    value: Any
    unit: str | None = None
    numerator: float | int | None = None
    denominator: float | int | None = None
    interval: EvidenceInterval | None = None
    claim_ref: VersionedObjectRef
    biological_context: BiologicalContext
    relation: EvidenceRelation
    evidence_state: EvidenceState
    evidence_tier: EvidenceTier
    lifecycle_state: EvidenceLifecycleState
    applicability: EvidenceApplicability
    evidence_family_ref: VersionedObjectRef
    sufficiency_profile_ref: VersionedObjectRef
    tool_run_ref: VersionedObjectRef
    tool_run_execution_state: Literal["succeeded", "partial"]
    reference_refs: list[VersionedObjectRef]
    prior_refs: list[VersionedObjectRef]
    artifact_refs: list[VersionedObjectRef]
    provenance_refs: list[str] = Field(min_length=1)
    revision_action: RevisionAction
    predecessor_ref: str | None = Field(default=None, pattern=EVIDENCE_REF_PATTERN)
    created_at: datetime
    compiler_version: Literal["0.2.0"]

    _created_at_utc = field_validator("created_at")(_aware_utc)

    @field_validator("value")
    @classmethod
    def safe_value(cls, value: Any) -> Any:
        if isinstance(value, bool):
            raise ValueError("boolean is not a numeric evidence value")
        return validate_safe_json(value)

    @field_validator("numerator", "denominator")
    @classmethod
    def finite_numbers(cls, value: float | int | None) -> float | int | None:
        if value is not None and (isinstance(value, bool) or not math.isfinite(float(value))):
            raise ValueError("numerator and denominator must be finite numeric values")
        return value

    @field_validator("reference_refs", "prior_refs", "artifact_refs")
    @classmethod
    def unique_refs(cls, value: list[VersionedObjectRef]) -> list[VersionedObjectRef]:
        return sorted(_unique(value, "reference list"), key=lambda item: item.ref)

    @field_validator("provenance_refs")
    @classmethod
    def unique_provenance(cls, value: list[str]) -> list[str]:
        return sorted(_unique([publication_ref(item) for item in value], "provenance_refs"))

    @model_validator(mode="after")
    def scientific_states_are_coherent(self) -> Self:
        if self.denominator is not None and self.denominator <= 0:
            raise ValueError("denominator must be positive")
        if self.evidence_state is EvidenceState.MISSING:
            raise ValueError("missing evidence must be an EvidenceRequirement")
        if self.value is None and self.evidence_state not in {
            EvidenceState.UNKNOWN,
            EvidenceState.UNAVAILABLE,
            EvidenceState.ALERT,
        }:
            raise ValueError("null evidence value is only valid for unknown/unavailable/alert")
        if self.revision_action is RevisionAction.CREATE and self.predecessor_ref is not None:
            raise ValueError("create cannot declare predecessor_ref")
        if self.revision_action is not RevisionAction.CREATE and self.predecessor_ref is None:
            raise ValueError("revision records require predecessor_ref")
        if self.revision_action is RevisionAction.INVALIDATE:
            if self.lifecycle_state is not EvidenceLifecycleState.INVALIDATED:
                raise ValueError("invalidate must create an invalidated lifecycle record")
        elif self.lifecycle_state is not EvidenceLifecycleState.ACTIVE:
            raise ValueError("create/supersede records must be active in immutable JSON")
        return self

    @property
    def ref(self) -> str:
        return f"{self.evidence_id}@{self.evidence_version}"


class EvidenceRequirement(FrozenModel):
    requirement_id: str = Field(pattern=r"^requirement:[a-f0-9]{24}$")
    requirement_version: int = Field(ge=1)
    claim_ref: VersionedObjectRef
    product_case_ref: VersionedObjectRef
    requirement_key: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    source_contract_ref: VersionedObjectRef
    channel_role: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    required_modality: str | None = None
    required_experiment: str | None = None
    blocking_scope: str = Field(min_length=1)
    state: EvidenceRequirementState
    reason_codes: list[str] = Field(min_length=1)
    satisfying_evidence_refs: list[str] = Field(default_factory=list)
    supersedes_requirement_ref: str | None = Field(
        default=None, pattern=REQUIREMENT_REF_PATTERN
    )
    created_at: datetime
    content_hash: str = Field(pattern=SHA256_PATTERN)

    _created_at_utc = field_validator("created_at")(_aware_utc)

    @field_validator("reason_codes")
    @classmethod
    def unique_reason_codes(cls, value: list[str]) -> list[str]:
        return _unique([_strip(item) for item in value], "requirement reason codes")

    @field_validator("satisfying_evidence_refs")
    @classmethod
    def unique_evidence_refs(cls, value: list[str]) -> list[str]:
        cleaned = [_strip(item) for item in value]
        if any(not re.fullmatch(EVIDENCE_REF_PATTERN, item) for item in cleaned):
            raise ValueError("satisfying evidence refs must be versioned evidence IDs")
        return sorted(_unique(cleaned, "satisfying_evidence_refs"))

    @model_validator(mode="after")
    def state_matches_satisfaction(self) -> Self:
        if self.state is EvidenceRequirementState.SATISFIED and not self.satisfying_evidence_refs:
            raise ValueError("satisfied requirement needs evidence")
        if self.state is EvidenceRequirementState.OPEN and self.satisfying_evidence_refs:
            raise ValueError("open requirement cannot list satisfying evidence")
        return self

    @property
    def ref(self) -> str:
        return f"{self.requirement_id}@{self.requirement_version}"


class EvidenceCompilationBundle(FrozenModel):
    bundle_id: str = Field(pattern=r"^evidence-compilation-bundle:[A-Za-z0-9._:-]+$")
    bundle_version: Literal["0.1.0"]
    graph_kind: GraphKind
    product_case_ref: VersionedObjectRef | None = None
    comparison_ref: VersionedObjectRef | None = None
    case_graph_refs: list[CaseGraphRef] = Field(default_factory=list)
    external_case_evidence_refs: list[SkipValidation[ExternalCaseEvidenceRef]] = Field(
        default_factory=list
    )
    base_graph_ref: BaseGraphRef | None = None
    object_catalog: list[CompilationObjectRef] = Field(min_length=1)
    candidate_records: list[dict[str, Any]] = Field(default_factory=list)
    missing_observations: list[dict[str, Any]] = Field(default_factory=list)
    prior_evidence_records: list[EvidenceRecord] = Field(default_factory=list)
    prior_requirements: list[EvidenceRequirement] = Field(default_factory=list)
    created_at: datetime
    provenance_refs: list[str] = Field(min_length=1)

    _created_at_utc = field_validator("created_at")(_aware_utc)

    @field_validator("case_graph_refs")
    @classmethod
    def sort_case_graphs(cls, value: list[CaseGraphRef]) -> list[CaseGraphRef]:
        return sorted(value, key=lambda item: (item.graph_id, item.graph_version))

    @field_validator("external_case_evidence_refs")
    @classmethod
    def sort_external_evidence(
        cls, value: list[ExternalCaseEvidenceRef | dict[str, Any]]
    ) -> list[ExternalCaseEvidenceRef | dict[str, Any]]:
        return sorted(
            value,
            key=lambda item: json.dumps(
                item.model_dump(mode="json") if isinstance(item, FrozenModel) else item,
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
        )

    @field_serializer("external_case_evidence_refs")
    def serialize_external_evidence(
        self, value: list[ExternalCaseEvidenceRef | dict[str, Any]]
    ) -> list[dict[str, Any]]:
        return [
            item.model_dump(mode="json")
            if isinstance(item, ExternalCaseEvidenceRef)
            else item
            for item in value
        ]

    @field_validator("object_catalog")
    @classmethod
    def sort_catalog(cls, value: list[CompilationObjectRef]) -> list[CompilationObjectRef]:
        return sorted(value, key=lambda item: (item.object_id, item.object_version))

    @field_validator("candidate_records", "missing_observations")
    @classmethod
    def sort_raw_records(cls, value: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return _sort_json_list(value)

    @field_validator("prior_evidence_records")
    @classmethod
    def sort_prior_evidence(cls, value: list[EvidenceRecord]) -> list[EvidenceRecord]:
        return sorted(value, key=lambda item: (item.evidence_id, item.evidence_version))

    @field_validator("prior_requirements")
    @classmethod
    def sort_prior_requirements(
        cls, value: list[EvidenceRequirement]
    ) -> list[EvidenceRequirement]:
        return sorted(value, key=lambda item: (item.requirement_id, item.requirement_version))

    @field_validator("provenance_refs")
    @classmethod
    def unique_provenance(cls, value: list[str]) -> list[str]:
        return sorted(_unique([publication_ref(item) for item in value], "provenance_refs"))

    @model_validator(mode="after")
    def graph_scope_is_explicit(self) -> Self:
        catalog_keys = [(item.object_id, item.object_version) for item in self.object_catalog]
        _unique(catalog_keys, "object_catalog")
        if self.graph_kind is GraphKind.CASE:
            if self.product_case_ref is None or self.comparison_ref is not None:
                raise ValueError("case bundle requires exactly one product_case_ref")
            if self.case_graph_refs or self.external_case_evidence_refs:
                raise ValueError("case bundle cannot contain comparison references")
        else:
            if self.comparison_ref is None or self.product_case_ref is not None:
                raise ValueError("comparison bundle requires exactly one comparison_ref")
            if not 2 <= len(self.case_graph_refs) <= 5:
                raise ValueError("comparison bundle requires two to five case graphs")
            _unique([item.graph_id for item in self.case_graph_refs], "case_graph_refs")
            if not self.external_case_evidence_refs:
                raise ValueError("comparison bundle requires external case evidence")
            if (
                self.candidate_records
                or self.missing_observations
                or self.prior_evidence_records
                or self.prior_requirements
            ):
                raise ValueError("comparison bundle cannot own case evidence history")
        return self


class EvidenceCandidate(FrozenModel):
    candidate_id: str = Field(pattern=r"^evidence-candidate:[A-Za-z0-9._:-]+$")
    product_case_ref: VersionedObjectRef
    sample_or_preparation_ref: VersionedObjectRef
    domain_id: P0DomainId
    measurement_result_ref: VersionedObjectRef
    measurement_spec_ref: VersionedObjectRef
    score_contract_ref: VersionedObjectRef | None = None
    metric_id: str = Field(min_length=1)
    value: Any
    unit: str | None = None
    numerator: float | int | None = None
    denominator: float | int | None = None
    interval: EvidenceInterval | None = None
    claim_ref: VersionedObjectRef
    biological_context: BiologicalContext
    relation: EvidenceRelation
    evidence_state: EvidenceState
    evidence_tier: EvidenceTier
    applicability: EvidenceApplicability
    evidence_family_ref: VersionedObjectRef
    sufficiency_profile_input_id: str = Field(min_length=1)
    tool_run_ref: VersionedObjectRef
    tool_run_execution_state: Literal[
        "succeeded", "partial", "failed", "skipped", "not_implemented"
    ]
    reference_refs: list[VersionedObjectRef] = Field(default_factory=list)
    prior_refs: list[VersionedObjectRef] = Field(default_factory=list)
    artifact_refs: list[VersionedObjectRef] = Field(default_factory=list)
    provenance_refs: list[str] = Field(min_length=1)
    revision_action: RevisionAction
    predecessor_ref: str | None = Field(default=None, pattern=EVIDENCE_REF_PATTERN)
    created_at: datetime

    _created_at_utc = field_validator("created_at")(_aware_utc)

    @field_validator("value")
    @classmethod
    def safe_value(cls, value: Any) -> Any:
        if isinstance(value, bool):
            raise ValueError("boolean is not a numeric evidence value")
        return validate_safe_json(value)

    @field_validator("numerator", "denominator")
    @classmethod
    def finite_numbers(cls, value: float | int | None) -> float | int | None:
        if value is not None and (isinstance(value, bool) or not math.isfinite(float(value))):
            raise ValueError("numerator and denominator must be finite numeric values")
        return value

    @field_validator("reference_refs", "prior_refs", "artifact_refs")
    @classmethod
    def unique_refs(cls, value: list[VersionedObjectRef]) -> list[VersionedObjectRef]:
        return sorted(_unique(value, "reference list"), key=lambda item: item.ref)

    @field_validator("provenance_refs")
    @classmethod
    def unique_provenance(cls, value: list[str]) -> list[str]:
        return sorted(_unique([publication_ref(item) for item in value], "provenance_refs"))

    @model_validator(mode="after")
    def candidate_semantics(self) -> Self:
        if self.denominator is not None and self.denominator <= 0:
            raise ValueError("denominator must be positive")
        if self.evidence_state is EvidenceState.MISSING:
            raise ValueError("missing state must use MissingEvidenceObservation")
        if self.value is None and self.evidence_state not in {
            EvidenceState.UNKNOWN,
            EvidenceState.UNAVAILABLE,
            EvidenceState.ALERT,
        }:
            raise ValueError("null evidence value is only valid for unknown/unavailable/alert")
        if self.revision_action is RevisionAction.CREATE and self.predecessor_ref is not None:
            raise ValueError("create cannot declare predecessor_ref")
        if self.revision_action is not RevisionAction.CREATE and self.predecessor_ref is None:
            raise ValueError("revision requires predecessor_ref")
        return self


class MissingEvidenceObservation(FrozenModel):
    observation_id: str = Field(pattern=r"^missing-evidence:[A-Za-z0-9._:-]+$")
    product_case_ref: VersionedObjectRef
    claim_ref: VersionedObjectRef
    requirement_key: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    reason_code: Literal[
        "measurement_not_provided",
        "measurement_unavailable",
        "required_channel_not_provided",
        "required_experiment_not_performed",
    ]
    source_contract_ref: VersionedObjectRef
    provenance_refs: list[str] = Field(min_length=1)
    observed_at: datetime

    _observed_at_utc = field_validator("observed_at")(_aware_utc)

    @field_validator("provenance_refs")
    @classmethod
    def unique_provenance(cls, value: list[str]) -> list[str]:
        return sorted(_unique([publication_ref(item) for item in value], "provenance_refs"))


class EvidenceFamilySpec(FrozenModel):
    evidence_family_id: str = Field(pattern=r"^evidence-family:[A-Za-z0-9._:-]+$")
    version: str = Field(min_length=1)
    family_type: EvidenceFamilyType
    channel_role: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    shared_source_refs: list[str] = Field(default_factory=list)
    shared_algorithm_refs: list[str] = Field(default_factory=list)
    shared_reference_or_prior_refs: list[str] = Field(default_factory=list)
    independence_scope: str = Field(min_length=1)
    known_dependencies: list[str] = Field(default_factory=list)
    rationale: str = Field(min_length=1)
    reviewer_ref: str | None = None
    status: EvidenceFamilyStatus

    _publishable_version = field_validator("version")(publication_version)

    @field_validator(
        "shared_source_refs",
        "shared_algorithm_refs",
        "shared_reference_or_prior_refs",
        "known_dependencies",
    )
    @classmethod
    def unique_lists(cls, value: list[str]) -> list[str]:
        return sorted(_unique([publication_ref(item) for item in value], "family reference list"))

    @field_validator("reviewer_ref")
    @classmethod
    def publishable_reviewer_ref(cls, value: str | None) -> str | None:
        return None if value is None else publication_ref(value)

    @model_validator(mode="after")
    def reviewed_requires_reviewer(self) -> Self:
        if self.status is EvidenceFamilyStatus.REVIEWED and not self.reviewer_ref:
            raise ValueError("reviewed family requires reviewer_ref")
        return self

    @property
    def ref(self) -> str:
        return f"{self.evidence_family_id}@{self.version}"


class EvidenceFamilyRegistry(FrozenModel):
    registry_id: Literal["BRIDGE-EVIDENCE-FAMILY-REGISTRY-v0.1"]
    registry_version: Literal["0.1.0"]
    status: RegistryStatus
    created_at: datetime
    families: list[EvidenceFamilySpec] = Field(min_length=1)

    _created_at_utc = field_validator("created_at")(_aware_utc)

    @field_validator("families")
    @classmethod
    def unique_families(cls, value: list[EvidenceFamilySpec]) -> list[EvidenceFamilySpec]:
        _unique([(item.evidence_family_id, item.version) for item in value], "families")
        return sorted(value, key=lambda item: (item.evidence_family_id, item.version))


class ClaimRequirementSpec(FrozenModel):
    requirement_key: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    channel_role: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    required_modality: str | None = None
    required_experiment: str | None = None
    blocking_scope: str = Field(min_length=1)
    required: bool = True


class ClaimSpec(FrozenModel):
    claim_id: str = Field(pattern=r"^claim:[A-Za-z0-9._:-]+$")
    version: str = Field(min_length=1)
    claim_type: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    domain_id: P0DomainId
    claim_target_ref: str = Field(min_length=1)
    biological_context_ref: str = Field(min_length=1)
    allowed_relations: list[EvidenceRelation] = Field(min_length=1)
    reconciliation_spec_ref: VersionedObjectRef
    requirement_specs: list[ClaimRequirementSpec] = Field(default_factory=list)
    status: RegistryStatus
    reviewer_ref: str | None = None

    _publishable_version = field_validator("version")(publication_version)
    _publishable_claim_refs = field_validator(
        "claim_target_ref", "biological_context_ref"
    )(publication_ref)

    @field_validator("reviewer_ref")
    @classmethod
    def publishable_reviewer_ref(cls, value: str | None) -> str | None:
        return None if value is None else publication_ref(value)

    @field_validator("allowed_relations")
    @classmethod
    def unique_relations(cls, value: list[EvidenceRelation]) -> list[EvidenceRelation]:
        return sorted(_unique(value, "allowed_relations"), key=lambda item: item.value)

    @field_validator("requirement_specs")
    @classmethod
    def unique_requirements(
        cls, value: list[ClaimRequirementSpec]
    ) -> list[ClaimRequirementSpec]:
        _unique([item.requirement_key for item in value], "requirement_specs")
        return sorted(value, key=lambda item: item.requirement_key)

    @model_validator(mode="after")
    def frozen_requires_reviewer(self) -> Self:
        if self.status is RegistryStatus.FROZEN and not self.reviewer_ref:
            raise ValueError("frozen claim requires reviewer_ref")
        return self

    @property
    def ref(self) -> str:
        return f"{self.claim_id}@{self.version}"


class ClaimRegistry(FrozenModel):
    registry_id: Literal["BRIDGE-CLAIM-REGISTRY-v0.1"]
    registry_version: Literal["0.1.0"]
    status: RegistryStatus
    created_at: datetime
    claims: list[ClaimSpec] = Field(min_length=1)

    _created_at_utc = field_validator("created_at")(_aware_utc)

    @field_validator("claims")
    @classmethod
    def unique_claims(cls, value: list[ClaimSpec]) -> list[ClaimSpec]:
        _unique([(item.claim_id, item.version) for item in value], "claims")
        return sorted(value, key=lambda item: (item.claim_id, item.version))


class ReconciliationSpec(FrozenModel):
    reconciliation_spec_id: str = Field(pattern=r"^reconciliation-spec:[A-Za-z0-9._:-]+$")
    version: str = Field(min_length=1)
    claim_type: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    required_channel_roles: list[str]
    optional_channel_roles: list[str] = Field(default_factory=list)
    primary_channel_roles: list[str] = Field(min_length=1)
    confirmation_channel_roles: list[str] = Field(default_factory=list)
    integration_sensitive_channel_roles: list[str] = Field(default_factory=list)
    minimum_independent_families_by_role: dict[str, int]
    allowed_evidence_states: list[EvidenceState] = Field(min_length=1)
    required_sufficiency_states: tuple[Literal["sufficient"]] = ("sufficient",)
    conflict_rule: Literal["family_dedup_then_channel_resolution"]
    consensus_rule: Literal["unanimous_independent_confirmation"]
    integration_sensitivity_rule: Literal[
        "integration_role_disagrees_with_resolved_direction"
    ]
    missing_behavior: Literal["insufficient_evidence"]
    validation_ref: str | None = None
    reviewer_ref: str | None = None
    status: RegistryStatus

    _publishable_version = field_validator("version")(publication_version)

    @field_validator("validation_ref", "reviewer_ref")
    @classmethod
    def publishable_review_refs(cls, value: str | None) -> str | None:
        return None if value is None else publication_ref(value)

    @field_validator(
        "required_channel_roles",
        "optional_channel_roles",
        "primary_channel_roles",
        "confirmation_channel_roles",
        "integration_sensitive_channel_roles",
    )
    @classmethod
    def unique_roles(cls, value: list[str]) -> list[str]:
        return sorted(_unique([_strip(item) for item in value], "channel roles"))

    @field_validator("allowed_evidence_states")
    @classmethod
    def unique_states(cls, value: list[EvidenceState]) -> list[EvidenceState]:
        return sorted(_unique(value, "allowed_evidence_states"), key=lambda item: item.value)

    @model_validator(mode="after")
    def validate_role_contract(self) -> Self:
        role_union = set(self.required_channel_roles) | set(self.optional_channel_roles)
        for roles in (
            self.primary_channel_roles,
            self.confirmation_channel_roles,
            self.integration_sensitive_channel_roles,
        ):
            if not set(roles).issubset(role_union):
                raise ValueError("resolution roles must be declared required or optional")
        if set(self.minimum_independent_families_by_role) != set(
            self.required_channel_roles
        ):
            raise ValueError("minimum family map must exactly match required roles")
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value <= 0
            for value in self.minimum_independent_families_by_role.values()
        ):
            raise ValueError("minimum family counts must be positive integers")
        if self.status is RegistryStatus.FROZEN and (
            not self.reviewer_ref or not self.validation_ref
        ):
            raise ValueError("frozen reconciliation spec requires review and validation")
        return self

    @property
    def ref(self) -> str:
        return f"{self.reconciliation_spec_id}@{self.version}"


class ReconciliationSpecRegistry(FrozenModel):
    registry_id: Literal["BRIDGE-RECONCILIATION-SPEC-REGISTRY-v0.1"]
    registry_version: Literal["0.1.0"]
    status: RegistryStatus
    created_at: datetime
    specs: list[ReconciliationSpec] = Field(min_length=1)

    _created_at_utc = field_validator("created_at")(_aware_utc)

    @field_validator("specs")
    @classmethod
    def unique_specs(cls, value: list[ReconciliationSpec]) -> list[ReconciliationSpec]:
        _unique(
            [(item.reconciliation_spec_id, item.version) for item in value],
            "reconciliation specs",
        )
        return sorted(
            value, key=lambda item: (item.reconciliation_spec_id, item.version)
        )


class EvidenceRecordDisposition(FrozenModel):
    candidate_id: str
    disposition: CompilationDisposition
    evidence_ref: str | None = None
    reason_codes: list[str]


class EvidenceRecordSet(FrozenModel):
    record_set_id: str = Field(pattern=r"^evidence-record-set:[a-f0-9]{16}$")
    record_set_version: Literal["0.1.0"]
    graph_id: str
    graph_version: int = Field(ge=1)
    records: list[EvidenceRecord]
    dispositions: list[EvidenceRecordDisposition]


class EvidenceRequirementSet(FrozenModel):
    requirement_set_id: str = Field(pattern=r"^evidence-requirement-set:[a-f0-9]{16}$")
    requirement_set_version: Literal["0.1.0"]
    graph_id: str
    graph_version: int = Field(ge=1)
    requirements: list[EvidenceRequirement]


class ChannelResolution(FrozenModel):
    channel_role: str
    evidence_refs: list[str]
    evidence_family_refs: list[str]
    direction: EvidenceRelation | None
    eligible: bool
    reason_codes: list[str]


class ReconciliationRecord(FrozenModel):
    reconciliation_id: str = Field(pattern=r"^reconciliation:[a-f0-9]{24}$")
    reconciliation_version: int = Field(ge=1)
    graph_id: str
    graph_version: int = Field(ge=1)
    claim_ref: VersionedObjectRef
    reconciliation_spec_ref: VersionedObjectRef
    sufficiency_profile_refs: list[VersionedObjectRef]
    eligibility: ReconciliationEligibility
    state: ReconciliationState | None = None
    direction: EvidenceRelation | None = None
    channel_resolutions: list[ChannelResolution]
    included_evidence_refs: list[str]
    excluded_evidence_refs: list[str]
    open_requirement_refs: list[str]
    reason_codes: list[str]
    created_at: datetime
    content_hash: str = Field(pattern=SHA256_PATTERN)

    _created_at_utc = field_validator("created_at")(_aware_utc)

    @model_validator(mode="after")
    def eligible_state_contract(self) -> Self:
        if self.eligibility is ReconciliationEligibility.ELIGIBLE:
            if self.state is None:
                raise ValueError("eligible reconciliation requires state")
            if self.state is ReconciliationState.UNSTABLE:
                if self.direction is not None:
                    raise ValueError("unstable reconciliation has no direction")
            elif self.direction is None:
                raise ValueError("resolved reconciliation requires direction")
        elif self.state is not None or self.direction is not None:
            raise ValueError("ineligible reconciliation cannot emit state or direction")
        return self

    @property
    def ref(self) -> str:
        return f"{self.reconciliation_id}@{self.reconciliation_version}"


class ReconciliationRecordSet(FrozenModel):
    reconciliation_set_id: str = Field(pattern=r"^reconciliation-record-set:[a-f0-9]{16}$")
    reconciliation_set_version: Literal["0.1.0"]
    graph_id: str
    graph_version: int = Field(ge=1)
    records: list[ReconciliationRecord]


class RejectedEvidenceRecord(FrozenModel):
    source_kind: Literal[
        "candidate_record", "missing_observation", "external_case_evidence_ref"
    ]
    source_id: str
    source_index: int = Field(ge=0)
    reason_codes: list[str] = Field(min_length=1)
    claim_ref: str | None = None
    logical_key_digest: str | None = Field(default=None, pattern=SHA256_PATTERN)


class RejectedEvidenceRecordList(FrozenModel):
    rejected_list_id: str = Field(pattern=r"^rejected-evidence-records:[a-f0-9]{16}$")
    rejected_list_version: Literal["0.1.0"]
    records: list[RejectedEvidenceRecord]


class EvidenceCompilerRunResult(FrozenModel):
    result_id: str = Field(pattern=r"^evidence-compiler-result:[a-f0-9]{16}$")
    result_version: Literal["0.1.0"]
    graph_kind: GraphKind
    graph_id: str
    graph_version: int = Field(ge=1)
    record_set_ref: str
    requirement_set_ref: str
    reconciliation_refs: list[str]
    graph_manifest_schema_ref: Literal[
        "bridge://schemas/case-evidence-graph-manifest/v0.1",
        "bridge://schemas/comparison-evidence-graph-manifest/v0.1",
    ]
    graph_manifest_ref: str
    cytoscape_export_ref: str
    rejected_record_count: int = Field(ge=0)
    accepted_record_count: int = Field(ge=0)
    unchanged_record_count: int = Field(ge=0)
    reason_codes: list[str]


class GraphArtifactRef(FrozenModel):
    filename: str = Field(pattern=r"^[a-z0-9_]+(?:\.[a-z0-9]+)+$")
    media_type: str
    sha256: str = Field(pattern=SHA256_PATTERN)
    row_count: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def artifact_contract_matches_extension(self) -> Self:
        if self.filename.endswith(".parquet"):
            if (
                self.media_type != "application/vnd.apache.parquet"
                or self.row_count is None
            ):
                raise ValueError("Parquet artifacts require media type and row_count")
        elif self.filename.endswith(".json"):
            if self.media_type != "application/json" or self.row_count is not None:
                raise ValueError("JSON artifacts require JSON media type and no row_count")
        else:
            raise ValueError("unsupported graph artifact extension")
        return self


class EvidenceGraphManifestBase(FrozenModel):
    graph_id: str
    graph_version: int = Field(ge=1)
    canonicalization_id: Literal["bridge-canonical-json/v0.1"]
    node_count: int = Field(ge=0)
    edge_count: int = Field(ge=0)
    object_counts: dict[GraphNodeType, int]
    source_input_hash: str = Field(pattern=SHA256_PATTERN)
    base_graph_ref: BaseGraphRef | None = None
    evidence_records: GraphArtifactRef
    evidence_requirements: GraphArtifactRef
    reconciliation_records: GraphArtifactRef
    graph_nodes: GraphArtifactRef
    graph_edges: GraphArtifactRef
    created_at: datetime

    _created_at_utc = field_validator("created_at")(_aware_utc)

    @model_validator(mode="after")
    def authoritative_artifact_contract(self) -> Self:
        expected = {
            "evidence_records": "evidence_records.json",
            "evidence_requirements": "evidence_requirements.json",
            "reconciliation_records": "reconciliation_records.json",
            "graph_nodes": "graph_nodes.parquet",
            "graph_edges": "graph_edges.parquet",
        }
        for field_name, filename in expected.items():
            if getattr(self, field_name).filename != filename:
                raise ValueError("graph manifest artifact filename is not allowlisted")
        if (
            self.graph_nodes.row_count != self.node_count
            or self.graph_edges.row_count != self.edge_count
            or sum(self.object_counts.values()) != self.node_count
        ):
            raise ValueError("graph manifest counts do not agree")
        return self


class CaseEvidenceGraphManifest(EvidenceGraphManifestBase):
    graph_kind: Literal[GraphKind.CASE] = GraphKind.CASE
    product_case_ref: VersionedObjectRef


class ComparisonEvidenceGraphManifest(EvidenceGraphManifestBase):
    graph_kind: Literal[GraphKind.COMPARISON] = GraphKind.COMPARISON
    comparison_ref: VersionedObjectRef
    case_graph_refs: list[CaseGraphRef] = Field(min_length=2, max_length=5)

    @field_validator("case_graph_refs")
    @classmethod
    def unique_sorted_case_graph_refs(cls, value: list[CaseGraphRef]) -> list[CaseGraphRef]:
        _unique(
            [(item.graph_id, item.graph_version) for item in value],
            "case_graph_refs",
        )
        return sorted(value, key=lambda item: (item.graph_id, item.graph_version))


class CytoscapeElements(FrozenModel):
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]


class CytoscapeEvidenceElements(FrozenModel):
    graph_id: str
    graph_version: int = Field(ge=1)
    elements: CytoscapeElements
    filters: dict[str, Any]
    truncated: bool
    returned_node_count: int = Field(ge=0)
    returned_edge_count: int = Field(ge=0)
    omitted_node_count: int = Field(default=0, ge=0)
    omitted_edge_count: int = Field(default=0, ge=0)


class EvidenceGraphQueryResult(FrozenModel):
    query_name: Literal[
        "get_claim_evidence",
        "trace_evidence_provenance",
        "get_conflicting_evidence",
        "get_missing_requirements",
        "get_evidence_family_members",
        "get_case_evidence_subgraph",
        "compare_evidence_paths",
    ]
    graph_id: str
    graph_version: int
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    returned_node_count: int = Field(ge=0)
    returned_edge_count: int = Field(ge=0)
    truncated: bool
    omitted_node_count: int = Field(ge=0)
    omitted_edge_count: int = Field(ge=0)
    reason_codes: list[str]


class GraphNodeRow(FrozenModel):
    graph_id: str
    graph_version: int
    node_id: str
    node_type: GraphNodeType
    record_mode: GraphRecordMode
    object_id: str
    object_version: str
    source_graph_id: str | None = None
    source_graph_version: int | None = None
    lifecycle_state: str | None = None
    evidence_tier: str | None = None
    properties_json: str | None = None
    content_hash: str = Field(pattern=SHA256_PATTERN)


class GraphEdgeRow(FrozenModel):
    graph_id: str
    graph_version: int
    edge_id: str
    edge_type: GraphEdgeType
    source_node_id: str
    target_node_id: str
    properties_json: str
    content_hash: str = Field(pattern=SHA256_PATTERN)


class CompiledEvidenceGraph(FrozenModel):
    graph_kind: GraphKind
    graph_id: str
    graph_version: int
    input_hash: str = Field(pattern=SHA256_PATTERN)
    created_at: datetime
    record_set: EvidenceRecordSet
    requirement_set: EvidenceRequirementSet
    reconciliation_set: ReconciliationRecordSet
    rejected_records: RejectedEvidenceRecordList
    nodes: list[GraphNodeRow]
    edges: list[GraphEdgeRow]

    _created_at_utc = field_validator("created_at")(_aware_utc)


PUBLIC_SCHEMA_MODELS = {
    "bridge://schemas/evidence-compilation-bundle/v0.1": EvidenceCompilationBundle,
    "bridge://schemas/evidence-family-registry/v0.1": EvidenceFamilyRegistry,
    "bridge://schemas/claim-registry/v0.1": ClaimRegistry,
    "bridge://schemas/reconciliation-spec-registry/v0.1": ReconciliationSpecRegistry,
    "bridge://schemas/evidence-record/v0.1": EvidenceRecord,
    "bridge://schemas/evidence-record-set/v0.1": EvidenceRecordSet,
    "bridge://schemas/evidence-requirement/v0.1": EvidenceRequirement,
    "bridge://schemas/evidence-requirement-set/v0.1": EvidenceRequirementSet,
    "bridge://schemas/reconciliation-record/v0.1": ReconciliationRecord,
    "bridge://schemas/reconciliation-record-set/v0.1": ReconciliationRecordSet,
    "bridge://schemas/evidence-rejected-record-list/v0.1": RejectedEvidenceRecordList,
    "bridge://schemas/case-evidence-graph-manifest/v0.1": CaseEvidenceGraphManifest,
    "bridge://schemas/comparison-evidence-graph-manifest/v0.1": ComparisonEvidenceGraphManifest,
    "bridge://schemas/cytoscape-evidence-elements/v0.1": CytoscapeEvidenceElements,
    "bridge://schemas/evidence-graph-query-result/v0.1": EvidenceGraphQueryResult,
    "bridge://schemas/evidence-compiler-run-result/v0.1": EvidenceCompilerRunResult,
}
