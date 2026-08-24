from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from bridge.tool_packages.p0_01_input_qc.io import sha256_path
from bridge.toolkit.contracts import DataViewBinding, InputAsset, QCReadinessProfile


class UpstreamQCError(ValueError):
    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(detail)
        self.reason_code = reason_code


@dataclass(frozen=True)
class UpstreamQCBinding:
    profile: QCReadinessProfile
    profile_sha256: str
    selected_view: DataViewBinding


def validate_upstream_qc(
    asset: InputAsset, input_hash: str | None = None
) -> UpstreamQCBinding:
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
    profile_path = Path(record["path"]).expanduser().resolve()
    if not profile_path.is_file() or sha256_path(profile_path) != record.get("sha256"):
        raise UpstreamQCError("qc_profile_artifact_invalid", str(profile_ref))
    profile_sha256 = str(record.get("sha256", ""))
    profile = QCReadinessProfile.model_validate_json(profile_path.read_text(encoding="utf-8"))
    selected = profile.selected_data_view
    if selected is None or selected.view_kind != "qc_selected_observations":
        raise UpstreamQCError("qc_selected_view_not_available", str(profile_ref))
    if selected.sample_or_preparation_ref is None:
        raise UpstreamQCError(
            "sample_or_preparation_ref_required",
            selected.view_id,
        )
    actual_hash = input_hash or sha256_path(asset.path)
    checks = {
        "profile_id": profile.profile_id == profile_ref,
        "selected_view_hash": selected.sha256 == actual_hash,
        "selected_view_ref": asset.metadata.get("data_view_ref") == selected.view_id,
        "assay": profile.assay == asset.assay,
        "matrix_location": selected.matrix_location == (asset.matrix_location or "X"),
        "matrix_semantics": selected.matrix_semantics == asset.matrix_semantics,
        "sample_or_preparation": (
            selected.sample_or_preparation_ref
            == asset.metadata.get("sample_or_preparation_ref")
        ),
        "readiness": profile.readiness_state.value in {"ready", "limited"},
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise UpstreamQCError("qc_profile_binding_mismatch", f"{profile_ref}:{','.join(failed)}")
    return UpstreamQCBinding(
        profile=profile,
        profile_sha256=profile_sha256,
        selected_view=selected,
    )
