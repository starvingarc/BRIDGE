"""P0-02 registered quick mapping; ToolRun and immutable artifacts own provenance."""
from __future__ import annotations

import hashlib
from importlib.metadata import version
from io import BytesIO
from pathlib import Path

from bridge.toolkit.contracts import ArtifactManifest, ToolRun
from bridge.tool_packages._structured_runtime import publish_json_bundle, request_v2_from_v1
from bridge.tool_packages.p0_01_input_qc.io import sha256_path
from .quick_atlas_reference import MappingParameters, canonical, load_reference, read_manifest


def parameter_reasons(request):
    reasons = []
    try:
        options = MappingParameters.model_validate(request.parameters)
        manifest = read_manifest(options.reference_manifest, options.reference_manifest_sha256)
        context_modality = {"pre_graft": ("scRNA", "scRNA-seq"), "post_graft": ("snRNA", "snRNA-seq")}
        modality, assay = context_modality[options.sample_context]
        if manifest["modality"] != modality or request.assets[0].assay != assay:
            reasons.append("quick_mapping_reference_modality_mismatch")
        if request.random_seed != manifest["recipe"]["random_seed"]:
            reasons.append("quick_mapping_seed_mismatch")
        if request.assets[0].matrix_semantics != "raw_counts":
            reasons.append("quick_mapping_raw_counts_required")
    except (KeyError, ValueError, OSError):
        reasons.append("quick_mapping_reference_integrity")
    return reasons


def run_quick_atlas_mapping(request, spec):
    run_id = "atlas-" + hashlib.sha256(request.request_id.encode()).hexdigest()[:24]
    base = dict(run_id=run_id, request=request, implementation_state=spec.implementation_state,
                tool_version=spec.version, environment_spec_id=spec.environment_spec_id)
    try:
        from bridge.tool_packages.p0_01_input_qc.io import read_expression_asset
        from .qc import validate_upstream_qc_bundle, validate_selected_data_view, validate_upstream_qc_unchanged
        from .quick_atlas import map_counts

        asset = request.assets[0]
        input_sha = sha256_path(asset.path)
        base["input_hash"] = input_sha
        if input_sha != asset.checksum:
            raise ValueError("input_checksum_mismatch")
        reasons = parameter_reasons(request)
        if reasons:
            raise ValueError(reasons[0])
        options = MappingParameters.model_validate(request.parameters)
        upstream = validate_upstream_qc_bundle(asset, input_sha)
        if upstream.profile_v2 is None:
            raise ValueError("typed_selected_data_view_required")
        query = read_expression_asset(asset)
        view = validate_selected_data_view(upstream.profile_v2, query.obs_names.tolist())
        modality = "scRNA" if options.sample_context == "pre_graft" else "snRNA"
        resource = load_reference(options.reference_manifest, expected_modality=modality,
                                  expected_sha256=options.reference_manifest_sha256)
        summary, cells = map_counts(query, resource.reference, resource.tree, resource.tree_cell_ids,
                                    resource.manifest["recipe"])
        panel = summary.pop("marker_expression_payload")
        panel_bytes = canonical(panel)
        summary["marker_expression"] = {
            "status": "available", "version": panel["object_version"], "genes": panel["genes"],
            "sha256": hashlib.sha256(panel_bytes).hexdigest(),
            "n_sample_points": len(panel["sample"]["values"]),
            "n_reference_points": len(panel["reference"]["values"]),
        }
        evidence = ["evidence:" + run_id + ":quick-mapping"]
        summary.update(
            input_sha256=input_sha, input_data_view=view.model_dump(mode="json"),
            versions={"reference": resource.manifest["reference_id"],
                      "atlas": resource.manifest["reference_version"],
                      "naming": resource.manifest["annotation_version"],
                      "method": resource.manifest["method_version"], "metrics": "not_computed",
                      "tree": resource.manifest["tree"]["sha256"],
                      "features": summary["feature_set_sha256"],
                      "projection": summary["projection_sha256"]},
            sample_context=options.sample_context, evidence_ids=evidence,
            reference_manifest_sha256=options.reference_manifest_sha256,
            recipe=resource.manifest["recipe"],
            dependencies={name: version(name) for name in ("scanpy", "anndata", "numpy", "scipy", "scikit-learn")},
            score_state="unavailable", domain_score=None,
        )
        buffer = BytesIO()
        cells.to_parquet(buffer, index=True)
        payloads = {"quick_atlas_mapping.json": canonical(summary), "quick_atlas_cells.parquet": buffer.getvalue(),
                    "quick_atlas_marker_expression.json": panel_bytes}

        def unchanged(_):
            validate_upstream_qc_unchanged(upstream)
            from .quick_atlas_reference import checked_resource
            read_manifest(options.reference_manifest, options.reference_manifest_sha256)
            for name in ("data", "tree", "tree_cell_ids"):
                checked_resource(options.reference_manifest.parent, resource.manifest[name])
            return sha256_path(asset.path) == input_sha

        paths = publish_json_bundle(request=request_v2_from_v1(request), run_id=run_id,
                                    payloads=payloads, inputs_are_unchanged=unchanged)
        kinds = {"quick_atlas_marker_expression.json": ("quick_atlas_marker_expression", "application/json"),"quick_atlas_mapping.json": ("quick_atlas_mapping", "application/json"),
                 "quick_atlas_cells.parquet": ("quick_atlas_cells", "application/vnd.apache.parquet")}
        artifacts = [
            ArtifactManifest(artifact_id="artifact:" + run_id + ":" + name.replace(".", "-"),
                             kind=kinds[name][0], path=path, media_type=kinds[name][1],
                             sha256=hashlib.sha256(payloads[name]).hexdigest(), evidence_ids=evidence)
            for name, path in paths.items()
        ]
        return ToolRun(**base, execution_state="succeeded", artifacts=artifacts, result=summary)
    except (ValueError, OSError, RuntimeError, ImportError, KeyError) as exc:
        reason = getattr(exc, "reason_code", None)
        if not reason:
            detail = str(exc)
            reason = detail if detail.replace("_", "").isalnum() and len(detail) < 100 else "quick_mapping_failed"
        return ToolRun(**base, execution_state="failed", reason_codes=[reason],
                       warnings=["error_type:" + type(exc).__name__])
