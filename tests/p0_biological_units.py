from __future__ import annotations

import hashlib
import json


def canonical_sha256(payload: dict) -> str:
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(raw).hexdigest()


def bind_reviewed_biological_units(
    payloads: dict[str, dict],
    view: dict,
    *,
    slug: str = "demo",
    preparation_ref: str = "preparation:demo@1.0.0",
    independence_group_ref: str = "sample:demo@1.0.0",
    units: list[tuple[str, str]] | None = None,
    unit_identity_namespace_ref: str | None = None,
    independence_scope_ref: str | None = None,
    lineage_state: str = "reviewed",
    observation_ids: list[str] | None = None,
) -> None:
    resolved_units = units or [(preparation_ref, independence_group_ref)]
    resolved_observation_ids = observation_ids or [
        f"demo-observation-{index:04d}"
        for index in range(view["n_observations"])
    ]
    if len(resolved_observation_ids) != view["n_observations"]:
        raise ValueError("observation_ids must match the selected view")
    if len(resolved_observation_ids) < len(resolved_units):
        raise ValueError("every declared analysis unit requires an observation")

    observation_ids_sha256 = hashlib.sha256(
        json.dumps(
            sorted(resolved_observation_ids),
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    view["observation_ids_sha256"] = observation_ids_sha256
    assignments = [
        {
            "observation_id": observation_id,
            "capture_ref": None,
            "preparation_ref": unit_ref,
            "sample_ref": group_ref,
            "donor_ref": None,
            "animal_ref": None,
            "graft_unit_ref": None,
            "analysis_unit_ref": unit_ref,
            "independence_group_ref": group_ref,
        }
        for index, observation_id in enumerate(resolved_observation_ids)
        for unit_ref, group_ref in [resolved_units[index % len(resolved_units)]]
    ]
    assignment_artifact = {
        "object_version": "0.1.0",
        "schema_ref": "bridge://schemas/biological-unit-assignment/v0.1",
        "data_view_ref": view["view_id"],
        "observation_ids_sha256": observation_ids_sha256,
        "assignments": assignments,
    }
    assignment_artifact_sha256 = canonical_sha256(assignment_artifact)
    manifest_id = f"biological-unit-manifest:{slug}"
    manifest = {
        "object_version": "0.1.0",
        "manifest_id": manifest_id,
        "manifest_version": "1.0.0",
        "schema_ref": "bridge://schemas/biological-unit-manifest/v0.1",
        "generator_tool_id": (
            "P0-01"
            if lineage_state == "declared"
            else "BRIDGE-BIOLOGICAL-UNIT-REVIEW"
        ),
        "generator_tool_version": "1.0.0",
        "data_view_ref": view["view_id"],
        "selected_artifact_sha256": view["sha256"],
        "observation_ids_sha256": observation_ids_sha256,
        "n_observations": view["n_observations"],
        "assignment_schema_ref": (
            "bridge://schemas/biological-unit-assignment/v0.1"
        ),
        "assignment_artifact_sha256": assignment_artifact_sha256,
        "assignment_row_count": view["n_observations"],
        "unit_identity_namespace_ref": {
            "object_id": (
                unit_identity_namespace_ref
                or f"biological-unit-namespace:{slug}"
            ),
            "object_version": "1.0.0",
        },
        "analysis_unit_kind": "preparation",
        "independence_group_kind": "sample",
        "independence_scope_ref": {
            "object_id": independence_scope_ref or f"independence-scope:{slug}",
            "object_version": "1.0.0",
        },
        "lineage_state": lineage_state,
        "review_gate_ref": (
            None
            if lineage_state == "declared"
            else {
                "object_id": f"biological-unit-review:{slug}",
                "object_version": "1.0.0",
            }
        ),
        "review_gate_sha256": None if lineage_state == "declared" else "e" * 64,
        "unit_bindings": [
            {
                "analysis_unit_ref": _ref(unit_ref),
                "analysis_unit_kind": "preparation",
                "independence_group_ref": _ref(group_ref),
                "independence_group_kind": "sample",
                "capture_ref": None,
                "preparation_ref": _ref(unit_ref),
                "sample_ref": _ref(group_ref),
            }
            for unit_ref, group_ref in resolved_units
        ],
    }
    manifest_sha256 = canonical_sha256(manifest)
    view.update(
        {
            "biological_unit_manifest_ref": f"{manifest_id}@1.0.0",
            "biological_unit_manifest_sha256": manifest_sha256,
        }
    )
    product_case = payloads["product_case"]
    product_case.update(
        {
            "source_unit_kind": "preparation",
            "independence_group_refs": [
                _ref(group_ref)
                for group_ref in sorted(
                    {group_ref for _, group_ref in resolved_units}
                )
            ],
            "biological_unit_manifest_ref": {
                "object_id": manifest_id,
                "object_version": "1.0.0",
            },
            "biological_unit_manifest_sha256": manifest_sha256,
            "independence_scope_ref": manifest["independence_scope_ref"],
        }
    )
    payloads["biological_unit_assignment"] = assignment_artifact
    payloads["biological_unit_manifest"] = manifest


def _ref(value: str) -> dict[str, str]:
    object_id, separator, object_version = value.rpartition("@")
    if not separator:
        raise ValueError("versioned reference required")
    return {"object_id": object_id, "object_version": object_version}
