"""Isolated registered-tool pipeline for one immutable research mapping attempt."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import sys
import subprocess

from bridge.toolkit.contracts import InputAsset, StructuredInputRef, ToolRequest, ToolRequestV2
from bridge.toolkit.registry import ToolRegistry
from bridge.web.sessions import now, write_file


def cell_cycle_request(asset, attempt_id, root):
    """Bind the existing exploratory tool to the immutable, unfiltered input."""
    import anndata
    from bridge.tool_packages._configurable_contracts import observation_ids_sha256
    import bridge.tool_packages.p0_06_proliferation_stress_response as cycle_package
    from bridge.tool_packages.p0_06_proliferation_stress_response.exploratory_models import ExploratoryProcessInput

    resource = Path(cycle_package.__file__).parent / "resources" / "seurat-cell-cycle-v5.5.1-candidate.json"
    resource_raw = resource.read_bytes()
    bundle = json.loads(resource_raw)
    data = anndata.read_h5ad(asset.path, backed="r")
    try:
        observations = data.obs_names.astype(str).tolist()
    finally:
        data.file.close()
    payload = ExploratoryProcessInput.model_validate({
        "object_version": "0.1.0", "input_id": "exploratory:" + attempt_id,
        "source_family_id": asset.metadata["source_family_id"],
        "data_view": {
            "view_id": "view:" + attempt_id + "-all", "view_kind": "all_observations",
            "artifact_id": asset.asset_id, "sha256": asset.checksum,
            "parent_asset_id": asset.asset_id, "parent_asset_sha256": asset.checksum,
            "matrix_location": asset.matrix_location, "matrix_semantics": asset.matrix_semantics,
            "n_observations": len(observations), "observation_ids_sha256": observation_ids_sha256(observations),
        },
        "gene_symbol_column": asset.metadata.get("gene_symbol_column"),
        "resource_ref": bundle["resource_candidate_id"], "resource_version": bundle["candidate_version"],
        "resource_sha256": hashlib.sha256(resource_raw).hexdigest(),
        "s_genes": bundle["lists"]["s.genes"]["genes"],
        "s_genes_sha256": bundle["lists"]["s.genes"]["sha256"],
        "g2m_genes": bundle["lists"]["g2m.genes"]["genes"],
        "g2m_genes_sha256": bundle["lists"]["g2m.genes"]["sha256"], "created_at": now(),
    })
    raw = payload.model_dump_json().encode()
    path = root / "cell-cycle-input.json"
    write_file(path, raw)
    ref = StructuredInputRef(input_id=payload.input_id, role="exploratory_process_input",
        schema_ref="bridge://schemas/exploratory-process-input/v0.1", object_version="0.1.0",
        path=path, sha256=hashlib.sha256(raw).hexdigest(), media_type="application/json")
    return ToolRequestV2(request_id=attempt_id + "-cell-cycle", tool_id="P0-06", assets=[asset],
                         object_inputs=[ref], output_dir=root / "cell-cycle", random_seed=0)


def run_cell_cycle(registry, asset, attempt_id, root):
    # A failed descriptive result must not invalidate completed QC or prevent mapping.
    try:
        request = cell_cycle_request(asset, attempt_id, root)
        result = registry.run(request)
        registry.validate_result(result, request)
        write_file(root / "cell-cycle-run.json", result.model_dump_json().encode())
    except Exception:
        import traceback
        traceback.print_exc()
        write_file(root / "cell-cycle-error.json", b'{"reason_code":"cell_cycle_execution_failed"}')


def run_optional_analysis(path, kind):
    """Isolate native crashes/timeouts so other completed analyses survive."""
    command = [sys.executable, "-m", "bridge.web.atlas_worker", "--" + kind, str(path)]
    try:
        subprocess.run(command, check=True, timeout=600, stdin=subprocess.DEVNULL)
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, OSError) as exc:
        reason = kind.replace("-", "_") + ("_execution_timeout" if isinstance(exc, subprocess.TimeoutExpired)
                                               else "_execution_failed")
        write_file(Path(path).parent / (kind + "-error.json"), json.dumps({"reason_code": reason}).encode())


def run_optional_cell_cycle(path):
    run_optional_analysis(path, "cell-cycle")


def run_cell_atlas(registry, asset, attempt_id, root):
    """Use registered expression exploration; never reuse reference coordinates."""
    from bridge.tool_packages._expression_contracts import ExpressionAnalysis, EXPLORATION_SPEC
    try:
        qc_raw = (root / "qc-run.json").read_bytes()
        qc = json.loads(qc_raw)
        profile_ref = "qc-profile:" + qc["run_id"]
        declared = asset.model_copy(update={"metadata": {**asset.metadata,
            "qc_profile_ref": profile_ref, "qc_receipt_sha256": hashlib.sha256(qc_raw).hexdigest()}})
        request = ToolRequest(request_id=attempt_id + "-cell-atlas", tool_id="P0-02", assets=[declared],
            output_dir=root / "cell-atlas", measurement_spec_ref=EXPLORATION_SPEC,
            parameters=ExpressionAnalysis().model_dump(mode="json"), random_seed=0)
        result = registry.run(request)
        registry.validate_result(result, request)
        write_file(root / "cell-atlas-run.json", result.model_dump_json().encode())
    except Exception:
        import traceback
        traceback.print_exc()
        write_file(root / "cell-atlas-error.json", b'{"reason_code":"cell_atlas_execution_failed"}')


def run_job(path, *, cell_cycle_only=False, cell_atlas_only=False):
    # Inherit the same operator-pinned directory policy as the web launcher.
    from bridge.storage.private_paths import configure_trusted_ancestors
    pins = json.loads(os.environ.get("BRIDGE_WEB_TRUSTED_ANCESTORS", "{}"))
    if not isinstance(pins, dict):
        raise ValueError("invalid_server_configuration")
    if pins:
        configure_trusted_ancestors({Path(p): tuple(identity) for p, identity in pins.items()})
    job = json.loads(Path(path).read_bytes())
    root = Path(path).parent
    asset = InputAsset.model_validate(job["asset"])
    registry = ToolRegistry.load_default()
    if cell_cycle_only:
        run_cell_cycle(registry, asset, job["id"], root)
        return
    if cell_atlas_only:
        run_cell_atlas(registry, asset, job["id"], root)
        return
    qc_request = ToolRequest(request_id=job["id"] + "-qc", tool_id="P0-01", assets=[asset],
                             output_dir=root / "qc", parameters={"run_scrublet": True})
    qc = registry.run(qc_request)
    registry.validate_result(qc, qc_request)
    write_file(root / "qc-run.json", qc.model_dump_json().encode())
    if qc.execution_state != "succeeded":
        raise ValueError("mapping_input_qc_failed")
    run_optional_cell_cycle(path)
    artifacts = {a.path.name: a for a in qc.artifacts}
    profile = json.loads(artifacts["qc_readiness_profile.json"].path.read_bytes())
    catalog = {"profiles": {profile["profile_id"]: {
        "path": str(artifacts["qc_readiness_profile.json"].path),
        "sha256": artifacts["qc_readiness_profile.json"].sha256,
        "structured_output_index_path": str(artifacts["structured_output_index.json"].path),
        "structured_output_index_sha256": artifacts["structured_output_index.json"].sha256,
    }}}
    catalog_path = root / "qc-catalog.json"
    write_file(catalog_path, json.dumps(catalog).encode())
    os.environ["BRIDGE_QC_PROFILE_CATALOG"] = str(catalog_path)
    run_optional_analysis(path, "cell-atlas")
    if not job["parameters"]:
        return  # Basic analyses do not require a configured mapping reference.
    declared = asset.model_copy(update={"metadata": {**asset.metadata, "qc_profile_ref": profile["profile_id"]}})
    request = ToolRequest(request_id=job["id"], tool_id="P0-02", assets=[declared],
                          output_dir=root / "mapping", measurement_spec_ref="ATLAS-ingest-quick-v0.1",
                          parameters=job["parameters"])
    result = registry.run(request)
    registry.validate_result(result, request)
    write_file(root / "mapping-run.json", result.model_dump_json().encode())


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--cell-cycle":
        run_job(sys.argv[2], cell_cycle_only=True)
    elif len(sys.argv) == 3 and sys.argv[1] == "--cell-atlas":
        run_job(sys.argv[2], cell_atlas_only=True)
    else:
        run_job(sys.argv[1])
