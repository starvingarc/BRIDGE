from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path

from pydantic import ValidationError

from bridge.tool_packages._configurable_contracts import observation_ids_sha256
from bridge.tool_packages.p0_01_input_qc.io import sha256_path
from bridge.toolkit.contracts import (
    DataViewBinding,
    InputAsset,
    QCReadinessProfile,
    QCReadinessProfileV2,
)


@dataclass(frozen=True)
class ValidatedUpstreamQC:
    profile: QCReadinessProfile
    profile_path: Path
    profile_sha256: str
    profile_v2: QCReadinessProfileV2 | None
    profile_v2_path: Path | None
    profile_v2_sha256: str | None
    v2_unavailable_reason: str | None


class UpstreamQCError(ValueError):
    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(detail)
        self.reason_code = reason_code


def validate_upstream_qc(
    asset: InputAsset, input_hash: str | None = None
) -> QCReadinessProfile:
    return validate_upstream_qc_bundle(asset, input_hash).profile


def validate_upstream_qc_bundle(
    asset: InputAsset, input_hash: str | None = None
) -> ValidatedUpstreamQC:
    profile_ref = asset.metadata.get("qc_profile_ref")
    if not profile_ref:
        raise UpstreamQCError("qc_profile_ref_required", "qc_profile_ref")
    catalog_value = os.environ.get("BRIDGE_QC_PROFILE_CATALOG")
    if not catalog_value:
        raise UpstreamQCError("qc_profile_catalog_not_configured", str(profile_ref))
    catalog_path = Path(catalog_value).expanduser().resolve()
    try:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        record = catalog["profiles"][profile_ref]
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise UpstreamQCError("qc_profile_not_resolved", str(profile_ref)) from exc
    if not isinstance(record, dict):
        raise UpstreamQCError("qc_profile_not_resolved", str(profile_ref))
    profile_path, profile_bytes, profile_sha256 = _read_checksummed_artifact(
        record,
        path_key="path",
        checksum_key="sha256",
        reason_code="qc_profile_artifact_invalid",
        profile_ref=str(profile_ref),
    )
    try:
        profile = QCReadinessProfile.model_validate_json(profile_bytes)
    except (ValidationError, ValueError) as exc:
        raise UpstreamQCError(
            "qc_profile_artifact_invalid", str(profile_ref)
        ) from exc

    (
        profile_v2,
        profile_v2_path,
        profile_v2_sha256,
        v2_unavailable_reason,
    ) = _resolve_v2_profile(record, str(profile_ref))
    actual_hash = input_hash or sha256_path(asset.path)
    selected_view = profile_v2.selected_data_view if profile_v2 is not None else None
    legacy_input_hash = profile.matrix_provenance.get("input_hash")
    checks = {
        "profile_id": profile.profile_id == profile_ref,
        "input_hash": legacy_input_hash == actual_hash,
        "assay": profile.assay == asset.assay,
        "matrix_location": profile.matrix_provenance.get("matrix_location")
        == (asset.matrix_location or "X"),
        "matrix_semantics": profile.matrix_provenance.get("matrix_semantics")
        == asset.matrix_semantics,
        "data_view": profile.data_views.get("all_cells_view", {}).get("state")
        == "available",
        "readiness": profile.readiness_state.value in {"ready", "limited"},
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise UpstreamQCError(
            "qc_profile_binding_mismatch", f"{profile_ref}:{','.join(failed)}"
        )

    if profile_v2 is not None:
        if selected_view is None:
            raise UpstreamQCError(
                "qc_profile_v2_binding_mismatch",
                f"{profile_ref}:selected_data_view",
            )
        v2_checks = {
            "profile_id": profile_v2.profile_id == profile_ref,
            "assay": profile_v2.assay == asset.assay,
            "readiness": profile_v2.readiness_state.value in {"ready", "limited"},
            "view_kind": selected_view.view_kind == "all_observations",
            "artifact_id": selected_view.artifact_id
            == f"input-asset:{asset.asset_id}",
            "parent_asset_id": selected_view.parent_asset_id == asset.asset_id,
            "input_hash": selected_view.sha256 == actual_hash,
            "parent_input_hash": selected_view.parent_asset_sha256
            == actual_hash,
            "matrix_location": selected_view.matrix_location
            == (asset.matrix_location or "X"),
            "matrix_semantics": selected_view.matrix_semantics
            == asset.matrix_semantics,
        }
        failed_v2 = [name for name, passed in v2_checks.items() if not passed]
        if failed_v2:
            raise UpstreamQCError(
                "qc_profile_v2_binding_mismatch",
                f"{profile_ref}:{','.join(failed_v2)}",
            )

    return ValidatedUpstreamQC(
        profile=profile,
        profile_path=profile_path,
        profile_sha256=profile_sha256,
        profile_v2=profile_v2,
        profile_v2_path=profile_v2_path,
        profile_v2_sha256=profile_v2_sha256,
        v2_unavailable_reason=v2_unavailable_reason,
    )


def validate_selected_data_view(
    profile: QCReadinessProfileV2,
    observation_ids: list[str],
) -> DataViewBinding:
    view = profile.selected_data_view
    if view is None:
        raise UpstreamQCError(
            "qc_profile_v2_binding_mismatch",
            f"{profile.profile_id}:selected_data_view",
        )
    checks = {
        "n_observations": view.n_observations == len(observation_ids),
        "observation_ids_sha256": view.observation_ids_sha256
        == observation_ids_sha256(observation_ids),
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise UpstreamQCError(
            "qc_profile_v2_data_view_mismatch",
            f"{profile.profile_id}:{','.join(failed)}",
        )
    return view


def validate_upstream_qc_unchanged(validated: ValidatedUpstreamQC) -> None:
    artifacts = [
        (
            validated.profile_path,
            validated.profile_sha256,
            "qc_profile_modified_during_run",
        )
    ]
    if (
        validated.profile_v2_path is not None
        and validated.profile_v2_sha256 is not None
    ):
        artifacts.append(
            (
                validated.profile_v2_path,
                validated.profile_v2_sha256,
                "qc_profile_v2_modified_during_run",
            )
        )
    for path, expected_sha256, reason_code in artifacts:
        try:
            actual_sha256 = sha256_path(path)
        except OSError as exc:
            raise UpstreamQCError(reason_code, str(path)) from exc
        if actual_sha256 != expected_sha256:
            raise UpstreamQCError(reason_code, str(path))


def _resolve_v2_profile(
    record: dict[str, object],
    profile_ref: str,
) -> tuple[
    QCReadinessProfileV2 | None,
    Path | None,
    str | None,
    str | None,
]:
    has_path = bool(record.get("v2_path"))
    has_sha256 = bool(record.get("v2_sha256"))
    if not has_path and not has_sha256:
        return None, None, None, "qc_profile_v2_not_resolved"
    if has_path != has_sha256:
        raise UpstreamQCError(
            "qc_profile_v2_catalog_incomplete", profile_ref
        )
    profile_path, profile_bytes, profile_sha256 = _read_checksummed_artifact(
        record,
        path_key="v2_path",
        checksum_key="v2_sha256",
        reason_code="qc_profile_v2_artifact_invalid",
        profile_ref=profile_ref,
    )
    try:
        profile = QCReadinessProfileV2.model_validate_json(profile_bytes)
    except (ValidationError, ValueError) as exc:
        raise UpstreamQCError(
            "qc_profile_v2_artifact_invalid", profile_ref
        ) from exc
    return profile, profile_path, profile_sha256, None


def _read_checksummed_artifact(
    record: dict[str, object],
    *,
    path_key: str,
    checksum_key: str,
    reason_code: str,
    profile_ref: str,
) -> tuple[Path, bytes, str]:
    try:
        path = Path(str(record[path_key])).expanduser().resolve()
        expected_sha256 = record[checksum_key]
        payload = path.read_bytes()
    except (OSError, KeyError, TypeError) as exc:
        raise UpstreamQCError(reason_code, profile_ref) from exc
    actual_sha256 = hashlib.sha256(payload).hexdigest()
    if not isinstance(expected_sha256, str) or actual_sha256 != expected_sha256:
        raise UpstreamQCError(reason_code, profile_ref)
    return path, payload, actual_sha256
