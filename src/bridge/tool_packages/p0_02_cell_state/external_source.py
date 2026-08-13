from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class ExternalSourceAuditError(ValueError):
    pass


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _LineageAsset(_StrictModel):
    asset_id: str
    root_source_family_id: str
    parent_asset_ids: list[str] = Field(default_factory=list)
    candidate_decision: Literal[
        "development_reference",
        "development_ood",
        "behavior_only",
        "external_holdout",
        "excluded_from_candidate",
        "sealed_excluded",
    ]
    rationale: str


class _LineageMap(_StrictModel):
    audit_id: str
    version: str
    external_holdout_roots: list[str] = Field(min_length=1)
    assets: list[_LineageAsset] = Field(min_length=1)


def audit_external_source_lineage(
    lineage_map_path: Path,
    output_path: Path,
) -> dict[str, object]:
    """Fail if an external holdout root is present in candidate fitting roles."""
    lineage_map = _load_lineage_map(lineage_map_path)
    assets = {asset.asset_id: asset for asset in lineage_map.assets}
    if len(assets) != len(lineage_map.assets):
        raise ExternalSourceAuditError("lineage_asset_ids_not_unique")
    for asset in lineage_map.assets:
        missing = sorted(set(asset.parent_asset_ids) - set(assets))
        if missing:
            raise ExternalSourceAuditError(
                f"lineage_parent_missing:{asset.asset_id}:{','.join(missing)}"
            )

    root_cache: dict[str, set[str]] = {}

    def roots(asset_id: str, visiting: set[str]) -> set[str]:
        if asset_id in root_cache:
            return root_cache[asset_id]
        if asset_id in visiting:
            raise ExternalSourceAuditError(f"lineage_cycle:{asset_id}")
        asset = assets[asset_id]
        values = {asset.root_source_family_id}
        next_visiting = {*visiting, asset_id}
        for parent in asset.parent_asset_ids:
            values.update(roots(parent, next_visiting))
        root_cache[asset_id] = values
        return values

    fitting_roles = {"development_reference", "development_ood", "behavior_only"}
    external_roots = set(lineage_map.external_holdout_roots)
    resolved_roots = {
        asset.asset_id: sorted(roots(asset.asset_id, set())) for asset in lineage_map.assets
    }
    represented_external_roots = {
        root
        for asset in lineage_map.assets
        if asset.candidate_decision == "external_holdout"
        for root in resolved_roots[asset.asset_id]
    }
    missing_external_roots = sorted(external_roots - represented_external_roots)
    if missing_external_roots:
        raise ExternalSourceAuditError(
            "external_holdout_root_not_represented:"
            f"{','.join(missing_external_roots)}"
        )
    prohibited: list[dict[str, str]] = []
    for asset in lineage_map.assets:
        overlap = sorted(set(resolved_roots[asset.asset_id]) & external_roots)
        if asset.candidate_decision in fitting_roles and overlap:
            prohibited.extend(
                {
                    "asset_id": asset.asset_id,
                    "candidate_decision": asset.candidate_decision,
                    "external_holdout_root": root,
                }
                for root in overlap
            )
    if prohibited:
        first = prohibited[0]
        raise ExternalSourceAuditError(
            "external_source_lineage_overlap:"
            f"{first['asset_id']}:{first['external_holdout_root']}"
        )

    report: dict[str, object] = {
        "asset_count": len(lineage_map.assets),
        "audit_id": lineage_map.audit_id,
        "candidate_decisions": {
            asset.asset_id: asset.candidate_decision for asset in lineage_map.assets
        },
        "external_holdout_roots": sorted(external_roots),
        "lineage_map_sha256": _sha256(lineage_map_path),
        "prohibited_overlap_count": 0,
        "resolved_roots": resolved_roots,
        "status": "passed",
        "version": lineage_map.version,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def _load_lineage_map(path: Path) -> _LineageMap:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        return _LineageMap.model_validate(payload)
    except (OSError, ValidationError, ValueError, yaml.YAMLError) as exc:
        raise ExternalSourceAuditError(f"invalid_lineage_map:{type(exc).__name__}") from exc


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
