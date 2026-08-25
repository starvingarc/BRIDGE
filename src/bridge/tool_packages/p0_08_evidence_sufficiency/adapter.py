from __future__ import annotations

from dataclasses import dataclass
import hashlib
from importlib.resources import files
import os
from pathlib import Path
import re
import shutil
from typing import Any
from urllib.parse import parse_qsl, urlsplit
from uuid import uuid4

from bridge.tool_packages._structured_runtime import (
    LoadedInputs,
    StructuredInputError,
    failed_v2_run,
    inputs_unchanged as _inputs_unchanged,
    load_structured_inputs,
    objects_for_role as _objects_for_role,
    read_regular_bytes,
    single_object as _single_object,
    strict_json_loads as _loads_json,
    write_json as _write_json,
)
from bridge.tool_packages.p0_08_evidence_sufficiency.executor import (
    REASON_CODES,
    canonical_input_hash,
    canonical_object_sha256,
    evaluate_evidence_sufficiency,
)
from bridge.tool_packages.p0_08_evidence_sufficiency.models import (
    DomainGateInput,
    EvidenceSensitivityRecord,
    EvidenceSufficiencyRunResultV2 as EvidenceSufficiencyRunResult,
    EvidenceValidationRecord,
    GateRuleSpec,
    PriorApplicabilityRecord,
    ReasonCodeCatalog,
    VersionedObjectPointer,
    published_ref,
)
from bridge.toolkit.contracts import (
    ArtifactManifest,
    EligibilityResult,
    ExecutionState,
    FrozenModel,
    MeasurementResultV2 as MeasurementResult,
    MeasurementSpecV2 as MeasurementSpec,
    QCReadinessProfileV2 as QCReadinessProfile,
    StructuredInputRef,
    ToolPackageSpecV2,
    ToolRequest,
    ToolRequestV2,
    ToolRunV2,
)


RESULT_SCHEMA_REF = "bridge://schemas/evidence-sufficiency-run-result/v0.2"
ROLE_SCHEMAS = {
    "gate_rule_spec": "bridge://schemas/evidence-sufficiency-gate-rule-spec/v0.1",
    "domain_gate_input": "bridge://schemas/domain-gate-input/v0.1",
    "measurement_spec": "bridge://schemas/measurement-spec/v0.2",
    "qc_readiness_profile": "bridge://schemas/qc-readiness-profile/v0.2",
    "measurement_result": "bridge://schemas/measurement-result/v0.2",
    "validation_record": "bridge://schemas/evidence-validation-record/v0.1",
    "prior_applicability_record": "bridge://schemas/prior-applicability-record/v0.1",
    "sensitivity_record": "bridge://schemas/evidence-sensitivity-record/v0.1",
}
ROLE_MODELS: dict[str, type[FrozenModel]] = {
    "gate_rule_spec": GateRuleSpec,
    "domain_gate_input": DomainGateInput,
    "measurement_spec": MeasurementSpec,
    "qc_readiness_profile": QCReadinessProfile,
    "measurement_result": MeasurementResult,
    "validation_record": EvidenceValidationRecord,
    "prior_applicability_record": PriorApplicabilityRecord,
    "sensitivity_record": EvidenceSensitivityRecord,
}
LEGACY_KEYS = {
    "_".join(("evidence", "confidence", "score")),
    "_".join(("integrated", "score")),
    "_".join(("potency", "proxy")),
    "_".join(("product", "pass")),
    "_".join(("negative", "pass")),
}
LEGACY_SCORE_MAP_KEYS = {"complete", "partial", "minimal"}
WINDOWS_ABSOLUTE_PATH = re.compile(
    r"(?:^|[\s=:'\"(])(?:[A-Za-z]:[\\/]|\\\\[^\\\s]+\\[^\\\s]+)"
)
EMBEDDED_POSIX_PATH = re.compile(
    r"(?:^|[\s=:'\"(])/(?!/)(?:[A-Za-z0-9._~-]+/)+[^\s<>\"']*"
)
URI_URL = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://[^\s<>\"']+")
FILE_URI = re.compile(r"(?i)(?<![A-Za-z0-9+.-])file:")
ASSIGNMENT_SEPARATOR = re.compile(r"[:=]")
BEARER_CREDENTIAL = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{8,}")
COMMON_TOKEN = re.compile(
    r"(?:ghp_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16})"
)
CREDENTIAL_EXACT_NAMES = frozenset({"auth", "authorization"})
CREDENTIAL_NAME_SUFFIXES = (
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
SENSITIVE_KEY_QUALIFIERS = frozenset(
    {
        "database",
        "db",
        "webhook",
        "master",
        "service",
        "account",
        "signing",
        "encryption",
        "decryption",
        "private",
        "ssh",
        "api",
        "access",
        "client",
        "consumer",
        "secret",
    }
)
PIN_CONTEXT_QUALIFIERS = frozenset(
    {
        "auth",
        "authorization",
        "account",
        "access",
        "security",
        "login",
        "user",
        "credential",
        "verification",
        "device",
    }
)
HOME_RELATIVE_PATH = re.compile(
    r"(?:^|[\s=:'\"(])(?:~[A-Za-z0-9._-]*|\$HOME|\$\{HOME\}|"
    r"%USERPROFILE%|%HOMEPATH%)[\\/]",
    re.IGNORECASE,
)
VERSIONLESS_ROLE_OBJECT_VERSIONS = {
    "qc_readiness_profile": "0.2.0",
    "measurement_result": "0.2.0",
}


@dataclass(frozen=True)
class EvidenceSufficiencyAdapter:
    def check_eligibility(
        self,
        request: ToolRequestV2,
        spec: ToolPackageSpecV2,
    ) -> EligibilityResult:
        if not isinstance(request, ToolRequestV2):
            tool_id = request.tool_id if isinstance(request, ToolRequest) else "P0-08"
            return EligibilityResult(
                tool_id=tool_id,
                eligible=False,
                reason_codes=["tool_request_v2_required"],
            )
        reasons = self._envelope_reasons(request, spec)
        loaded, loading_reasons = _load_structured_inputs(request.object_inputs)
        reasons.extend(loading_reasons)
        if loaded is not None:
            reasons.extend(_binding_reasons(request, loaded))
        reason_codes = sorted(set(reasons))
        return EligibilityResult(
            tool_id=request.tool_id,
            eligible=not reason_codes,
            reason_codes=reason_codes,
        )

    def run(self, request: ToolRequestV2, spec: ToolPackageSpecV2) -> ToolRunV2:
        eligibility = self.check_eligibility(request, spec)
        if not eligibility.eligible:
            return _failed_run(
                request=request,
                spec=spec,
                reason_codes=eligibility.reason_codes,
            )
        loaded, reasons = _load_structured_inputs(request.object_inputs)
        if loaded is None or reasons:
            return _failed_run(request=request, spec=spec, reason_codes=reasons)
        gate_rule = _single_object(
            request, loaded, "gate_rule_spec", GateRuleSpec
        )
        domain_inputs = _objects_for_role(
            request, loaded, "domain_gate_input", DomainGateInput
        )
        input_hash = canonical_input_hash(
            request=request,
            spec=spec,
            objects_by_input_id=loaded.objects_by_input_id,
        )
        run_id = f"run-{input_hash[:16]}"
        result = evaluate_evidence_sufficiency(
            request=request,
            spec=spec,
            gate_rule=gate_rule,
            domain_inputs=domain_inputs,
            objects_by_input_id=loaded.objects_by_input_id,
        )
        output_root = request.output_dir.resolve()
        output_root.mkdir(parents=True, exist_ok=True)
        staging_dir = output_root / f".{run_id}.staging-{uuid4().hex}"
        staging_dir.mkdir(mode=0o700)
        try:
            artifact_specs = _write_scientific_payloads(
                staging_dir=staging_dir,
                result=result,
                gate_rule=gate_rule,
            )
            manifest = _manifest_payload(
                request=request,
                spec=spec,
                run_id=run_id,
                input_hash=input_hash,
                objects_by_input_id=loaded.objects_by_input_id,
                artifact_specs=artifact_specs,
            )
            _write_json(staging_dir / "artifact_manifest.json", manifest)
            if not _inputs_unchanged(request.object_inputs):
                return _cleanup_and_fail(
                    staging_dir,
                    request=request,
                    spec=spec,
                    input_hash=input_hash,
                    reason_code="structured_input_modified_during_run",
                )
            final_dir = output_root / run_id
            if final_dir.exists():
                if not _bundles_match(staging_dir, final_dir):
                    return _cleanup_and_fail(
                        staging_dir,
                        request=request,
                        spec=spec,
                        input_hash=input_hash,
                        reason_code="existing_run_bundle_hash_mismatch",
                    )
                shutil.rmtree(staging_dir)
            else:
                os.replace(staging_dir, final_dir)
        except Exception:
            if staging_dir.exists():
                shutil.rmtree(staging_dir)
            raise
        artifacts = _runtime_artifacts(final_dir, run_id, result)
        created_at = max(domain_input.created_at for domain_input in domain_inputs)
        return ToolRunV2(
            run_id=run_id,
            request=request,
            implementation_state=spec.implementation_state,
            execution_state=ExecutionState.SUCCEEDED,
            tool_version=spec.version,
            environment_spec_id=spec.environment_spec_id,
            input_hash=input_hash,
            created_at=created_at,
            measurements=[],
            artifacts=artifacts,
            visualizations=[],
            result_schema_ref=RESULT_SCHEMA_REF,
            result=result.model_dump(mode="json"),
            reason_codes=[],
            warnings=[],
        )

    @staticmethod
    def _envelope_reasons(
        request: ToolRequestV2, spec: ToolPackageSpecV2
    ) -> list[str]:
        reasons: list[str] = []
        if request.tool_version is not None and request.tool_version != spec.version:
            reasons.append("tool_version_mismatch")
        if request.assets:
            reasons.append("p0_08_expression_assets_forbidden")
        if request.measurement_spec_ref is not None:
            reasons.append("p0_08_top_level_measurement_spec_forbidden")
        if request.parameters:
            reasons.append("p0_08_parameters_forbidden")
        roles = [item.role for item in request.object_inputs]
        if roles.count("gate_rule_spec") != 1:
            reasons.append("exactly_one_gate_rule_spec_required")
        if not 1 <= roles.count("domain_gate_input") <= 5:
            reasons.append("one_to_five_domain_gate_inputs_required")
        if len([role for role in roles if role == "measurement_spec"]) > 5:
            reasons.append("domain_gate_input_binding_invalid")
        if len([role for role in roles if role == "qc_readiness_profile"]) > 5:
            reasons.append("domain_gate_input_binding_invalid")
        if any(role not in ROLE_SCHEMAS for role in roles):
            reasons.append("unsupported_object_input_role")
        for ref in request.object_inputs:
            expected = ROLE_SCHEMAS.get(ref.role)
            if expected is not None and ref.schema_ref != expected:
                reasons.append("object_input_schema_mismatch")
        input_ids = [item.input_id for item in request.object_inputs]
        if len(input_ids) != len(set(input_ids)):
            reasons.append("duplicate_object_input_id")
        return reasons


adapter = EvidenceSufficiencyAdapter()


def load_gate_rule() -> GateRuleSpec:
    payload = _resource_bytes("gate_rule_spec_v0.1.json")
    return GateRuleSpec.model_validate(_loads_json(payload))


def load_reason_catalog() -> ReasonCodeCatalog:
    payload = _resource_bytes("reason_code_catalog_v0.1.json")
    catalog = ReasonCodeCatalog.model_validate(_loads_json(payload))
    if tuple(reason.code for reason in catalog.reasons) != REASON_CODES:
        raise ValueError("packaged P0-08 reason catalog order differs from the executor")
    return catalog


def gate_rule_sha256() -> str:
    return hashlib.sha256(_resource_bytes("gate_rule_spec_v0.1.json")).hexdigest()


def _resource_bytes(filename: str) -> bytes:
    resource = files(
        "bridge.tool_packages.p0_08_evidence_sufficiency.resources"
    ).joinpath(filename)
    return resource.read_bytes()


def _load_structured_inputs(
    refs: list[StructuredInputRef],
) -> tuple[LoadedInputs | None, list[str]]:
    return load_structured_inputs(
        refs,
        model_for=lambda ref: ROLE_MODELS.get(ref.role),
        validate_payload=_validate_input_payload,
        validate_model=_validate_input_model,
        read_verified=_read_verified_input,
    )


def _read_verified_input(ref: StructuredInputRef) -> bytes:
    try:
        if not ref.path.exists():
            raise StructuredInputError("structured_input_not_found")
        raw = read_regular_bytes(ref.path)
    except StructuredInputError:
        raise
    except OSError as exc:
        raise StructuredInputError("structured_input_not_regular_file") from exc
    if hashlib.sha256(raw).hexdigest() != ref.sha256:
        raise StructuredInputError("structured_input_checksum_mismatch")
    return raw


def _validate_input_payload(ref: StructuredInputRef, payload: Any) -> None:
    if _contains_legacy_contract(payload):
        raise StructuredInputError("legacy_evidence_contract_rejected")
    if _contains_unsafe_scientific_reference(payload):
        raise StructuredInputError("unsafe_scientific_reference")


def _validate_input_model(ref: StructuredInputRef, value: FrozenModel) -> None:
    _validate_declared_object_version(ref, value)
    _validate_publishable_source_refs(ref.role, value)


def _validate_declared_object_version(
    ref: StructuredInputRef, value: FrozenModel
) -> None:
    for field in ("object_version", "version"):
        actual = getattr(value, field, None)
        if actual is not None:
            if str(actual) != ref.object_version:
                raise ValueError("declared object_version does not match payload")
            return
    expected = VERSIONLESS_ROLE_OBJECT_VERSIONS.get(ref.role)
    if expected is None or ref.object_version != expected:
        raise ValueError("versionless schema object_version is not supported")


def _validate_publishable_source_refs(role: str, value: FrozenModel) -> None:
    refs: list[str] = []
    if role == "measurement_spec" and isinstance(value, MeasurementSpec):
        refs.append(value.measurement_spec_id)
    elif role == "qc_readiness_profile" and isinstance(value, QCReadinessProfile):
        refs.append(value.profile_id)
    elif role == "measurement_result" and isinstance(value, MeasurementResult):
        refs.append(value.measurement_id)
        refs.extend(
            ref for ref in value.provenance_refs if ref.startswith("evidence:")
        )
    elif role == "validation_record" and isinstance(value, EvidenceValidationRecord):
        refs.extend(
            [value.validation_record_id, value.evidence_family_id, *value.evidence_refs]
        )
    elif role == "prior_applicability_record" and isinstance(
        value, PriorApplicabilityRecord
    ):
        refs.extend(
            [
                value.prior_record_id,
                value.snapshot_ref,
                value.evidence_family_id,
                *value.evidence_refs,
            ]
        )
    elif role == "sensitivity_record" and isinstance(
        value, EvidenceSensitivityRecord
    ):
        refs.extend(
            [
                value.sensitivity_record_id,
                value.evidence_family_id,
                *value.evidence_refs,
            ]
        )
    for ref in refs:
        published_ref(ref)


def _pointer_identity(
    pointer: VersionedObjectPointer,
) -> tuple[str, str, tuple[str, ...]]:
    return (
        pointer.object_id,
        pointer.object_version,
        tuple(sorted(pointer.provenance_refs)),
    )


def _binding_reasons(request: ToolRequestV2, loaded: LoadedInputs) -> list[str]:
    reasons: list[str] = []
    refs_by_id = {ref.input_id: ref for ref in request.object_inputs}
    gate_refs = [ref for ref in request.object_inputs if ref.role == "gate_rule_spec"]
    if len(gate_refs) == 1:
        gate_ref = gate_refs[0]
        if (
            gate_ref.sha256 != gate_rule_sha256()
            or loaded.bytes_by_input_id[gate_ref.input_id]
            != _resource_bytes("gate_rule_spec_v0.1.json")
        ):
            reasons.append("unsupported_gate_rule_spec")
    domains = _objects_for_role(request, loaded, "domain_gate_input", DomainGateInput)
    domain_gate_input_ids = [item.domain_gate_input_id for item in domains]
    if len(domain_gate_input_ids) != len(set(domain_gate_input_ids)):
        reasons.append("duplicate_logical_object_id")
    domain_ids = [item.domain_id for item in domains if item.domain_id is not None]
    if len(domain_ids) != len(set(domain_ids)):
        reasons.append("duplicate_domain_id")
    product_cases = {
        _pointer_identity(item.product_case)
        for item in domains
        if item.product_case is not None
    }
    if len(product_cases) > 1:
        reasons.append("multiple_product_cases_in_request")
    product_definitions = {
        _pointer_identity(item.product_definition)
        for item in domains
        if item.product_definition is not None
    }
    if len(product_definitions) > 1:
        reasons.append("domain_input_product_definition_mismatch")
    reasons.extend(_logical_id_reasons(request, loaded))

    bound_ids: set[str] = set()
    for domain in domains:
        bindings = _domain_bindings(domain)
        for input_id, expected_role in bindings:
            ref = refs_by_id.get(input_id)
            if ref is None or ref.role != expected_role:
                reasons.append("domain_gate_input_binding_invalid")
                continue
            bound_ids.add(input_id)
        measurement_spec = None
        if domain.measurement_spec_input_id in loaded.objects_by_input_id:
            candidate = loaded.objects_by_input_id[domain.measurement_spec_input_id]
            if isinstance(candidate, MeasurementSpec):
                measurement_spec = candidate
        if measurement_spec is not None:
            if (
                domain.product_definition is not None
                and domain.product_definition.object_id
                not in measurement_spec.applicable_product_cards
            ):
                reasons.append("domain_input_product_definition_mismatch")
            if domain.qc_profile_input_id is not None:
                qc_profile = loaded.objects_by_input_id.get(domain.qc_profile_input_id)
                if isinstance(qc_profile, QCReadinessProfile) and (
                    qc_profile.assay != measurement_spec.assay
                    or qc_profile.measurement_spec_status != measurement_spec.status
                ):
                    reasons.append("domain_input_measurement_spec_mismatch")
            for input_id in domain.measurement_result_input_ids:
                value = loaded.objects_by_input_id.get(input_id)
                if (
                    isinstance(value, MeasurementResult)
                    and value.measurement_spec_id != measurement_spec.measurement_spec_id
                ):
                    reasons.append("domain_input_measurement_spec_mismatch")
            for input_id in domain.validation_record_input_ids:
                value = loaded.objects_by_input_id.get(input_id)
                if isinstance(value, EvidenceValidationRecord) and (
                    value.modality != measurement_spec.assay
                    or not measurement_spec.tool_refs
                    or value.tool_ref not in measurement_spec.tool_refs
                ):
                    reasons.append("domain_input_measurement_spec_mismatch")
            for input_id in [
                *domain.validation_record_input_ids,
                *domain.prior_record_input_ids,
                *domain.sensitivity_record_input_ids,
            ]:
                value = loaded.objects_by_input_id.get(input_id)
                if (
                    isinstance(
                        value,
                        (
                            EvidenceValidationRecord,
                            PriorApplicabilityRecord,
                            EvidenceSensitivityRecord,
                        ),
                    )
                    and value.measurement_spec_ref != measurement_spec.measurement_spec_id
                ):
                    reasons.append("domain_input_measurement_spec_mismatch")
        if domain.product_definition is not None:
            for input_id in domain.prior_record_input_ids:
                value = loaded.objects_by_input_id.get(input_id)
                if (
                    isinstance(value, PriorApplicabilityRecord)
                    and value.product_definition_ref != domain.product_definition.object_id
                ):
                    reasons.append("domain_input_product_definition_mismatch")

    for ref in request.object_inputs:
        if (
            ref.role not in {"gate_rule_spec", "domain_gate_input"}
            and ref.input_id not in bound_ids
        ):
            reasons.append("unbound_structured_input")
        resolved_input = ref.path.resolve()
        resolved_output = request.output_dir.resolve()
        if resolved_input == resolved_output or resolved_input.is_relative_to(resolved_output):
            reasons.append("output_dir_overlaps_structured_input")
    return sorted(set(reasons))


def _domain_bindings(domain: DomainGateInput) -> list[tuple[str, str]]:
    bindings: list[tuple[str, str]] = []
    if domain.measurement_spec_input_id is not None:
        bindings.append((domain.measurement_spec_input_id, "measurement_spec"))
    if domain.qc_profile_input_id is not None:
        bindings.append((domain.qc_profile_input_id, "qc_readiness_profile"))
    bindings.extend((value, "measurement_result") for value in domain.measurement_result_input_ids)
    bindings.extend((value, "validation_record") for value in domain.validation_record_input_ids)
    bindings.extend(
        (value, "prior_applicability_record")
        for value in domain.prior_record_input_ids
    )
    bindings.extend((value, "sensitivity_record") for value in domain.sensitivity_record_input_ids)
    return bindings


def _contains_legacy_contract(value: object) -> bool:
    if isinstance(value, dict):
        keys = {str(key) for key in value}
        if keys & LEGACY_KEYS or LEGACY_SCORE_MAP_KEYS.issubset(keys):
            return True
        return any(_contains_legacy_contract(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_legacy_contract(item) for item in value)
    return False


def _contains_unsafe_scientific_reference(value: object) -> bool:
    if isinstance(value, str):
        return _unsafe_string(value)
    if isinstance(value, dict):
        return any(
            _unsafe_string(str(key))
            or (_is_credential_name(key) and _is_nonempty(item))
            or _contains_unsafe_scientific_reference(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_contains_unsafe_scientific_reference(item) for item in value)
    return False


def _normalize_credential_name(value: object) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "", str(value)).casefold()


def _is_credential_name(value: object) -> bool:
    compact = _normalize_credential_name(value)
    if compact in CREDENTIAL_EXACT_NAMES:
        return True
    if compact.endswith(CREDENTIAL_NAME_SUFFIXES):
        return True
    if compact.endswith("pin"):
        stem = compact[: -len("pin")]
        return any(
            stem.startswith(qualifier) or stem.endswith(qualifier)
            for qualifier in PIN_CONTEXT_QUALIFIERS
        )
    if not compact.endswith("key"):
        return False
    stem = compact[: -len("key")]
    return any(
        stem.startswith(qualifier) or stem.endswith(qualifier)
        for qualifier in SENSITIVE_KEY_QUALIFIERS
    )


def _has_credential_assignment(value: str) -> bool:
    for separator in ASSIGNMENT_SEPARATOR.finditer(value):
        remainder = value[separator.end() :].lstrip()
        token = re.match(r"[^\s,;}\]]+", remainder)
        if token is None:
            continue
        trailing = remainder[token.end() :].strip()
        if trailing and trailing[0] not in ",;}]":
            continue
        name_fragments = re.findall(r"[A-Za-z0-9]+", value[: separator.start()])
        for width in range(1, min(3, len(name_fragments)) + 1):
            if _is_credential_name("".join(name_fragments[-width:])):
                return True
    return False


def _is_nonempty(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (dict, list)):
        return bool(value)
    return True


def _unsafe_string(value: str) -> bool:
    stripped = value.strip()
    if not stripped:
        return False
    if (
        stripped.startswith("/")
        or stripped.startswith("\\\\")
        or WINDOWS_ABSOLUTE_PATH.search(stripped)
        or EMBEDDED_POSIX_PATH.search(stripped)
        or HOME_RELATIVE_PATH.search(stripped)
        or FILE_URI.search(stripped)
    ):
        return True
    if (
        _has_credential_assignment(stripped)
        or BEARER_CREDENTIAL.search(stripped)
        or COMMON_TOKEN.search(stripped)
    ):
        return True
    for url in URI_URL.findall(stripped):
        parsed = urlsplit(url.rstrip(".,);]"))
        if parsed.scheme.lower() == "file":
            return True
        if parsed.username is not None or parsed.password is not None:
            return True
        if any(
            _is_credential_name(key) and _is_nonempty(item)
            for key, item in parse_qsl(parsed.query, keep_blank_values=True)
        ):
            return True
    return False


def _logical_id_reasons(
    request: ToolRequestV2, loaded: LoadedInputs
) -> list[str]:
    duplicate = False
    simple_roles = {
        "measurement_spec": "measurement_spec_id",
        "qc_readiness_profile": "profile_id",
        "measurement_result": "measurement_id",
    }
    for role, field in simple_roles.items():
        logical_ids = [
            str(getattr(loaded.objects_by_input_id[ref.input_id], field))
            for ref in request.object_inputs
            if ref.role == role and ref.input_id in loaded.objects_by_input_id
        ]
        if len(logical_ids) != len(set(logical_ids)):
            duplicate = True

    family_roles = {
        "validation_record": "validation_record_id",
        "prior_applicability_record": "prior_record_id",
        "sensitivity_record": "sensitivity_record_id",
    }
    for role, field in family_roles.items():
        families_by_id: dict[str, set[str]] = {}
        for ref in request.object_inputs:
            if ref.role != role or ref.input_id not in loaded.objects_by_input_id:
                continue
            record = loaded.objects_by_input_id[ref.input_id]
            logical_id = str(getattr(record, field))
            families_by_id.setdefault(logical_id, set()).add(
                str(getattr(record, "evidence_family_id"))
            )
        if any(len(families) > 1 for families in families_by_id.values()):
            duplicate = True
    return ["duplicate_logical_object_id"] if duplicate else []


def _write_scientific_payloads(
    *,
    staging_dir: Path,
    result: EvidenceSufficiencyRunResult,
    gate_rule: GateRuleSpec,
) -> list[dict[str, Any]]:
    payloads = {
        "evidence_sufficiency_profiles.json": (
            "evidence_sufficiency_profiles",
            {
                "projection_kind": "noncanonical_convenience_projection",
                "canonical_result_ref": result.result_id,
                "profiles": [profile.model_dump(mode="json") for profile in result.profiles],
            },
        ),
        "case_evidence_readiness_summary.json": (
            "case_evidence_readiness_summary",
            result.case_summary.model_dump(mode="json"),
        ),
        "gate_trace.json": (
            "evidence_sufficiency_gate_trace",
            {
                "gate_trace_id": f"gate-trace:{result.result_id.rsplit(':', 1)[1]}",
                "gate_rule_spec_ref": gate_rule.gate_rule_spec_id,
                "entries": [entry.model_dump(mode="json") for entry in result.gate_trace],
            },
        ),
        "evidence_sufficiency_run_result.json": (
            "evidence_sufficiency_run_result",
            result.model_dump(mode="json"),
        ),
    }
    artifact_specs: list[dict[str, Any]] = []
    evidence_ids = sorted(
        {evidence for profile in result.profiles for evidence in profile.evidence_refs}
    )
    for filename, (kind, payload) in payloads.items():
        path = staging_dir / filename
        _write_json(path, payload)
        artifact_specs.append(
            {
                "filename": filename,
                "kind": kind,
                "media_type": "application/json",
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "evidence_ids": evidence_ids,
            }
        )
    return artifact_specs


def _manifest_payload(
    *,
    request: ToolRequestV2,
    spec: ToolPackageSpecV2,
    run_id: str,
    input_hash: str,
    objects_by_input_id: dict[str, FrozenModel],
    artifact_specs: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "tool_id": spec.tool_id,
        "tool_version": spec.version,
        "environment_spec_id": spec.environment_spec_id,
        "result_schema_ref": spec.result_schema_ref,
        "input_hash": input_hash,
        "structured_input_provenance_policy": {
            "bundle_identity": "canonical_semantic_sha256_with_exact_source_sha256",
            "invocation_source_checksum": "ToolRunV2.request.object_inputs[].sha256",
            "result_source_checksum": "source_object_bindings[].source_sha256",
        },
        "structured_inputs": [
            {
                "input_id": ref.input_id,
                "role": ref.role,
                "schema_ref": ref.schema_ref,
                "object_version": ref.object_version,
                "semantic_sha256": canonical_object_sha256(
                    objects_by_input_id[ref.input_id]
                ),
                "source_sha256": ref.sha256,
                "media_type": ref.media_type,
            }
            for ref in sorted(request.object_inputs, key=lambda item: (item.role, item.input_id))
        ],
        "artifacts": artifact_specs,
    }


def _bundles_match(staging_dir: Path, final_dir: Path) -> bool:
    if not final_dir.is_dir() or final_dir.is_symlink():
        return False
    expected_names = {
        "evidence_sufficiency_profiles.json",
        "case_evidence_readiness_summary.json",
        "gate_trace.json",
        "evidence_sufficiency_run_result.json",
        "artifact_manifest.json",
    }
    if {path.name for path in staging_dir.iterdir()} != expected_names:
        return False
    if {path.name for path in final_dir.iterdir()} != expected_names:
        return False
    if (staging_dir / "artifact_manifest.json").read_bytes() != (
        final_dir / "artifact_manifest.json"
    ).read_bytes():
        return False
    try:
        manifest = _loads_json((final_dir / "artifact_manifest.json").read_bytes())
    except (OSError, UnicodeDecodeError, ValueError):
        return False
    if not isinstance(manifest, dict) or not isinstance(manifest.get("artifacts"), list):
        return False
    artifact_entries = manifest["artifacts"]
    expected_artifacts = expected_names - {"artifact_manifest.json"}
    if {
        artifact.get("filename")
        for artifact in artifact_entries
        if isinstance(artifact, dict)
    } != expected_artifacts or len(artifact_entries) != len(expected_artifacts):
        return False
    for artifact in artifact_entries:
        if not isinstance(artifact, dict):
            return False
        path = final_dir / str(artifact.get("filename", ""))
        if not path.is_file() or path.is_symlink():
            return False
        if hashlib.sha256(path.read_bytes()).hexdigest() != artifact.get("sha256"):
            return False
    return all(
        (staging_dir / filename).read_bytes() == (final_dir / filename).read_bytes()
        for filename in expected_names
    )


def _runtime_artifacts(
    final_dir: Path,
    run_id: str,
    result: EvidenceSufficiencyRunResult,
) -> list[ArtifactManifest]:
    evidence_ids = sorted(
        {evidence for profile in result.profiles for evidence in profile.evidence_refs}
    )
    specs = (
        ("profiles", "evidence_sufficiency_profiles", "evidence_sufficiency_profiles.json"),
        ("summary", "case_evidence_readiness_summary", "case_evidence_readiness_summary.json"),
        ("trace", "evidence_sufficiency_gate_trace", "gate_trace.json"),
        ("result", "evidence_sufficiency_run_result", "evidence_sufficiency_run_result.json"),
        ("manifest", "manifest", "artifact_manifest.json"),
    )
    return [
        ArtifactManifest(
            artifact_id=f"artifact:{run_id}:{suffix}",
            kind=kind,
            path=(final_dir / filename).resolve(),
            media_type="application/json",
            sha256=hashlib.sha256((final_dir / filename).read_bytes()).hexdigest(),
            evidence_ids=evidence_ids,
        )
        for suffix, kind, filename in specs
    ]


def _cleanup_and_fail(
    staging_dir: Path,
    *,
    request: ToolRequestV2,
    spec: ToolPackageSpecV2,
    input_hash: str,
    reason_code: str,
) -> ToolRunV2:
    shutil.rmtree(staging_dir)
    return _failed_run(
        request=request,
        spec=spec,
        input_hash=input_hash,
        reason_codes=[reason_code],
    )


def _failed_run(
    *,
    request: ToolRequestV2,
    spec: ToolPackageSpecV2,
    reason_codes: list[str],
    input_hash: str | None = None,
) -> ToolRunV2:
    return failed_v2_run(
        request,
        spec,
        reason_codes,
        result_schema_ref=RESULT_SCHEMA_REF,
        fingerprint_input_key="structured_inputs",
        input_hash=input_hash,
    )
