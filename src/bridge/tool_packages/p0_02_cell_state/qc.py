from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path

from pydantic import ValidationError

from bridge.tool_packages._configurable_contracts import (
    BiologicalUnitAssignmentArtifact,
    BiologicalUnitManifest,
    biological_unit_assignment_reasons,
    observation_ids_sha256,
)
from bridge.tool_packages.p0_01_input_qc.io import (
    P001StructuredOutputIndex,
    sha256_path,
)
from bridge.toolkit.contracts import (
    DataViewBinding,
    InputAsset,
    QCReadinessProfile,
    QCReadinessProfileV2,
)


@dataclass(frozen=True)
class ValidatedTypedLineage:
    index_path: Path
    index_sha256: str
    assignment: BiologicalUnitAssignmentArtifact
    assignment_path: Path
    assignment_sha256: str
    manifest: BiologicalUnitManifest
    manifest_path: Path
    manifest_sha256: str


@dataclass(frozen=True)
class ValidatedUpstreamQC:
    profile: QCReadinessProfile
    profile_path: Path
    profile_sha256: str
    profile_v2: QCReadinessProfileV2 | None
    profile_v2_path: Path | None
    profile_v2_sha256: str | None
    typed_lineage: ValidatedTypedLineage | None
    v3_unavailable_reason: str | None


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

    profile_path, profile_bytes, profile_sha256 = _read_catalog_artifact(
        record,
        path_key="path",
        checksum_key="sha256",
        reason_code="qc_profile_artifact_invalid",
        detail=str(profile_ref),
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
        typed_lineage,
        v3_unavailable_reason,
    ) = _resolve_p0_01_structured_outputs(record, str(profile_ref))

    actual_hash = input_hash or sha256_path(asset.path)
    selected_view = profile_v2.selected_data_view if profile_v2 is not None else None
    checks = {
        "profile_id": profile.profile_id == profile_ref,
        "input_hash": profile.matrix_provenance.get("input_hash") == actual_hash,
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
        typed_lineage=typed_lineage,
        v3_unavailable_reason=v3_unavailable_reason,
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
    if validated.profile_v2_path is not None and validated.profile_v2_sha256 is not None:
        artifacts.append(
            (
                validated.profile_v2_path,
                validated.profile_v2_sha256,
                "qc_profile_v2_modified_during_run",
            )
        )
    if validated.typed_lineage is not None:
        lineage = validated.typed_lineage
        artifacts.extend(
            [
                (
                    lineage.index_path,
                    lineage.index_sha256,
                    "p0_01_structured_output_index_modified_during_run",
                ),
                (
                    lineage.assignment_path,
                    lineage.assignment_sha256,
                    "biological_unit_assignment_modified_during_run",
                ),
                (
                    lineage.manifest_path,
                    lineage.manifest_sha256,
                    "biological_unit_manifest_modified_during_run",
                ),
            ]
        )
    for path, expected_sha256, reason_code in artifacts:
        try:
            actual_sha256 = sha256_path(path)
        except OSError as exc:
            raise UpstreamQCError(reason_code, str(path)) from exc
        if actual_sha256 != expected_sha256:
            raise UpstreamQCError(reason_code, str(path))


def _resolve_p0_01_structured_outputs(
    record: dict[str, object],
    profile_ref: str,
) -> tuple[
    QCReadinessProfileV2 | None,
    Path | None,
    str | None,
    ValidatedTypedLineage | None,
    str | None,
]:
    path_key = "structured_output_index_path"
    checksum_key = "structured_output_index_sha256"
    has_path = bool(record.get(path_key))
    has_sha256 = bool(record.get(checksum_key))
    if not has_path and not has_sha256:
        return None, None, None, None, "p0_01_structured_output_index_not_resolved"
    if has_path != has_sha256:
        raise UpstreamQCError(
            "p0_01_structured_output_index_catalog_incomplete", profile_ref
        )

    index_path, index_bytes, index_sha256 = _read_catalog_artifact(
        record,
        path_key=path_key,
        checksum_key=checksum_key,
        reason_code="p0_01_structured_output_index_invalid",
        detail=profile_ref,
    )
    try:
        index = P001StructuredOutputIndex.model_validate_json(index_bytes)
    except (ValidationError, ValueError) as exc:
        raise UpstreamQCError(
            "p0_01_structured_output_index_invalid", profile_ref
        ) from exc
    if profile_ref != f"qc-profile:{index.run_id}":
        raise UpstreamQCError(
            "p0_01_structured_output_index_binding_mismatch", profile_ref
        )

    outputs = {item.role: item for item in index.outputs}
    profile_v2_path, profile_v2_bytes, profile_v2_sha256 = _read_indexed_artifact(
        index_path,
        outputs["qc_readiness_profile_v2"],
        reason_code="qc_profile_v2_artifact_invalid",
        detail=profile_ref,
    )
    try:
        profile_v2 = QCReadinessProfileV2.model_validate_json(profile_v2_bytes)
    except (ValidationError, ValueError) as exc:
        raise UpstreamQCError(
            "qc_profile_v2_artifact_invalid", profile_ref
        ) from exc

    lineage_roles = {
        "biological_unit_assignment",
        "biological_unit_manifest",
    }
    if not lineage_roles <= outputs.keys():
        return (
            profile_v2,
            profile_v2_path,
            profile_v2_sha256,
            None,
            "p0_01_typed_lineage_not_resolved",
        )

    assignment_path, assignment_bytes, assignment_sha256 = _read_indexed_artifact(
        index_path,
        outputs["biological_unit_assignment"],
        reason_code="biological_unit_assignment_artifact_invalid",
        detail=profile_ref,
    )
    manifest_path, manifest_bytes, manifest_sha256 = _read_indexed_artifact(
        index_path,
        outputs["biological_unit_manifest"],
        reason_code="biological_unit_manifest_artifact_invalid",
        detail=profile_ref,
    )
    try:
        assignment = BiologicalUnitAssignmentArtifact.model_validate_json(
            assignment_bytes
        )
        manifest = BiologicalUnitManifest.model_validate_json(manifest_bytes)
    except (ValidationError, ValueError) as exc:
        raise UpstreamQCError("p0_01_typed_lineage_invalid", profile_ref) from exc

    selected_view = profile_v2.selected_data_view
    lineage_reasons = biological_unit_assignment_reasons(
        manifest=manifest,
        artifact=assignment,
        artifact_sha256=assignment_sha256,
    )
    lineage_checks = {
        "profile_id": profile_v2.profile_id == profile_ref,
        "manifest_id": manifest.manifest_id
        == f"biological-unit-manifest:{index.run_id}",
        "generator": manifest.generator_tool_id == "P0-01",
        "declared_only": manifest.lineage_state.value == "declared",
        "selected_view": selected_view is not None,
        "view_manifest_ref": selected_view is not None
        and selected_view.biological_unit_manifest_ref == manifest.ref.ref,
        "view_manifest_sha256": selected_view is not None
        and selected_view.biological_unit_manifest_sha256 == manifest_sha256,
        "view_id": selected_view is not None
        and selected_view.view_id == manifest.data_view_ref,
        "input_hash": selected_view is not None
        and selected_view.sha256 == manifest.selected_artifact_sha256,
        "observation_digest": selected_view is not None
        and selected_view.observation_ids_sha256 == manifest.observation_ids_sha256,
        "observation_count": selected_view is not None
        and selected_view.n_observations == manifest.n_observations,
    }
    failed = [name for name, passed in lineage_checks.items() if not passed]
    if lineage_reasons or failed:
        detail = ",".join(sorted([*lineage_reasons, *failed]))
        raise UpstreamQCError(
            "p0_01_typed_lineage_binding_mismatch",
            f"{profile_ref}:{detail}",
        )

    return (
        profile_v2,
        profile_v2_path,
        profile_v2_sha256,
        ValidatedTypedLineage(
            index_path=index_path,
            index_sha256=index_sha256,
            assignment=assignment,
            assignment_path=assignment_path,
            assignment_sha256=assignment_sha256,
            manifest=manifest,
            manifest_path=manifest_path,
            manifest_sha256=manifest_sha256,
        ),
        None,
    )


def _read_catalog_artifact(
    record: dict[str, object],
    *,
    path_key: str,
    checksum_key: str,
    reason_code: str,
    detail: str,
) -> tuple[Path, bytes, str]:
    try:
        path = Path(str(record[path_key])).expanduser().resolve()
        expected_sha256 = record[checksum_key]
    except (KeyError, TypeError) as exc:
        raise UpstreamQCError(reason_code, detail) from exc
    return _read_path(path, expected_sha256, reason_code, detail)


def _read_indexed_artifact(
    index_path: Path,
    output,
    *,
    reason_code: str,
    detail: str,
) -> tuple[Path, bytes, str]:
    path = (index_path.parent / output.relative_filename).resolve()
    if path.parent != index_path.parent:
        raise UpstreamQCError(reason_code, detail)
    return _read_path(path, output.sha256, reason_code, detail)


def _read_path(
    path: Path,
    expected_sha256: object,
    reason_code: str,
    detail: str,
) -> tuple[Path, bytes, str]:
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise UpstreamQCError(reason_code, detail) from exc
    actual_sha256 = hashlib.sha256(payload).hexdigest()
    if not isinstance(expected_sha256, str) or actual_sha256 != expected_sha256:
        raise UpstreamQCError(reason_code, detail)
    return path, payload, actual_sha256
