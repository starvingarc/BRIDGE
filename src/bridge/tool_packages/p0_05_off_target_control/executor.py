from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Literal

from bridge.tool_packages._configurable_contracts import VersionedObjectRef
from bridge.tool_packages._structured_runtime import canonical_json_bytes
from bridge.tool_packages.p0_05_off_target_control.models import (
    CoverageState,
    OffTargetControlProfile,
    OffTargetControlProfileV2,
    OffTargetMeasurementArtifactBinding,
    RareDetectionState,
    rare_projection_evidence_state,
    role_projection_evidence_state,
    unknown_projection_evidence_state,
)
from bridge.toolkit.contracts import (
    EvidenceState,
    MeasurementResultV2,
    MeasurementSpecV2,
    ScoreState,
)

ROLE_METRIC_NAME = "off_target_role_composition"
UNKNOWN_METRIC_NAME = "off_target_identity_unknown"
RARE_METRIC_NAME = "off_target_rare_state_detection"
MEASUREMENT_PROJECTION_METRIC_NAMES = frozenset(
    {ROLE_METRIC_NAME, UNKNOWN_METRIC_NAME, RARE_METRIC_NAME}
)


@dataclass(frozen=True)
class MeasurementProjectionBundle:
    profile: OffTargetControlProfileV2
    measurements: list[MeasurementResultV2]
    payloads: dict[str, bytes]


@dataclass(frozen=True)
class _ProjectionDraft:
    metric_name: Literal[
        "off_target_role_composition",
        "off_target_identity_unknown",
        "off_target_rare_state_detection",
    ]
    record_scope: Literal["role", "identity_unknown", "rare_state"]
    record_id: str
    raw_record: dict
    evidence_state: EvidenceState
    unknown_scope: Literal["identity", "measurement"] | None = None


def profile_v2_without_projection(
    profile: OffTargetControlProfile,
) -> OffTargetControlProfileV2:
    return OffTargetControlProfileV2.model_validate(
        {
            **profile.model_dump(mode="python"),
            "object_version": "0.2.0",
            "profile_version": "0.2.0",
            "measurement_projection_state": "not_requested",
            "measurement_spec_ref": None,
            "measurement_spec_sha256": None,
            "measurement_artifacts": [],
        }
    )


def project_off_target_measurements(
    *,
    run_id: str,
    tool_version: str,
    profile: OffTargetControlProfile,
    measurement_spec: MeasurementSpecV2,
    measurement_spec_sha256: str,
    evidence_refs: list[str],
) -> MeasurementProjectionBundle:
    drafts = _projection_drafts(profile)
    measurements: list[MeasurementResultV2] = []
    payloads: dict[str, bytes] = {}
    bindings: list[OffTargetMeasurementArtifactBinding] = []
    for draft in drafts:
        token = _record_token(draft.record_scope, draft.record_id)
        measurement = _measurement(
            run_id=run_id,
            tool_version=tool_version,
            measurement_spec=measurement_spec,
            draft=draft,
            token=token,
            evidence_refs=evidence_refs,
        )
        payload = canonical_json_bytes(measurement.model_dump(mode="json"), indent=2)
        filename = f"{token}.{draft.metric_name}.measurement_result.json"
        artifact_id = f"artifact:{run_id}:{token}:{draft.metric_name}"
        sha256 = hashlib.sha256(payload).hexdigest()
        measurements.append(measurement)
        payloads[filename] = payload
        bindings.append(
            OffTargetMeasurementArtifactBinding(
                measurement_id=measurement.measurement_id,
                metric_name=draft.metric_name,
                record_scope=draft.record_scope,
                record_id=draft.record_id,
                evidence_state=draft.evidence_state,
                artifact_id=artifact_id,
                file_name=filename,
                sha256=sha256,
            )
        )

    profile_v2 = OffTargetControlProfileV2.model_validate(
        {
            **profile.model_dump(mode="python"),
            "object_version": "0.2.0",
            "profile_version": "0.2.0",
            "measurement_projection_state": "available",
            "measurement_spec_ref": VersionedObjectRef(
                object_id=measurement_spec.measurement_spec_id,
                object_version=measurement_spec.version,
            ),
            "measurement_spec_sha256": measurement_spec_sha256,
            "measurement_artifacts": sorted(
                bindings, key=lambda item: item.file_name
            ),
        }
    )
    return MeasurementProjectionBundle(
        profile=profile_v2,
        measurements=measurements,
        payloads=payloads,
    )


def _projection_drafts(profile: OffTargetControlProfile) -> list[_ProjectionDraft]:
    drafts = [
        _ProjectionDraft(
            metric_name=ROLE_METRIC_NAME,
            record_scope="role",
            record_id=record.product_role.value,
            raw_record=record.model_dump(mode="json"),
            evidence_state=role_projection_evidence_state(record.assessment_state),
        )
        for record in profile.role_composition
    ]
    drafts.append(
        _ProjectionDraft(
            metric_name=UNKNOWN_METRIC_NAME,
            record_scope="identity_unknown",
            record_id="identity-unknown",
            raw_record=profile.unknown_profile.model_dump(mode="json"),
            evidence_state=unknown_projection_evidence_state(
                profile.unknown_profile.coverage_state
            ),
            unknown_scope=(
                "identity"
                if profile.unknown_profile.coverage_state
                is not CoverageState.NOT_ASSESSED
                else None
            ),
        )
    )
    drafts.extend(
        _ProjectionDraft(
            metric_name=RARE_METRIC_NAME,
            record_scope="rare_state",
            record_id=record.state_id,
            raw_record=record.model_dump(mode="json"),
            evidence_state=rare_projection_evidence_state(record.detection_state),
            unknown_scope=(
                "measurement"
                if record.detection_state is RareDetectionState.CANNOT_EXCLUDE
                else None
            ),
        )
        for record in profile.rare_state_profile
    )
    return sorted(
        drafts,
        key=lambda item: (item.record_scope, item.record_id, item.metric_name),
    )


def _measurement(
    *,
    run_id: str,
    tool_version: str,
    measurement_spec: MeasurementSpecV2,
    draft: _ProjectionDraft,
    token: str,
    evidence_refs: list[str],
) -> MeasurementResultV2:
    raw_value = (
        None
        if draft.evidence_state is EvidenceState.UNAVAILABLE
        or (
            draft.evidence_state is EvidenceState.UNKNOWN
            and draft.unknown_scope == "measurement"
        )
        else draft.raw_record
    )
    run_token = run_id.removeprefix("run-")
    return MeasurementResultV2(
        measurement_id=f"measurement:{run_token}:{token}:{draft.metric_name}",
        measurement_spec_id=measurement_spec.measurement_spec_id,
        measurement_spec_version=measurement_spec.version,
        metric_name=draft.metric_name,
        raw_value=raw_value,
        unit=None,
        numerator=None,
        denominator=None,
        interval=None,
        interval_confidence_level=None,
        interval_method_ref=None,
        source_run_ref=f"tool-run:{run_id}@{tool_version}",
        source_execution_state="succeeded",
        unknown_scope=draft.unknown_scope,
        domain_score=None,
        score_state=ScoreState.UNAVAILABLE,
        evidence_state=draft.evidence_state,
        provenance_refs=evidence_refs,
    )


def _record_token(record_scope: str, record_id: str) -> str:
    digest = hashlib.sha256(
        canonical_json_bytes([record_scope, record_id])
    ).hexdigest()[:12]
    scope_token = record_scope.replace("_", "-")
    return f"p005-{scope_token}-{digest}"
