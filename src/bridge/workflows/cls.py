from __future__ import annotations

from pathlib import Path

import pandas as pd

from bridge.cls.component_a import compute_A_and_save
from bridge.cls.component_b import compute_B_and_save
from bridge.cls.component_c import compute_C_and_save
from bridge.cls.component_d import compute_D_and_save
from bridge.cls.component_e import compute_E_and_save
from bridge.cls.component_f import compute_F_and_save
from bridge.workflows.config import BridgeRunConfig, WorkflowValidationError


def _step2_artifact_paths(config: BridgeRunConfig) -> dict[str, Path]:
    outdir = config.paths.identity_output_dir
    prefix = config.dataset.prefix
    return {
        "bdata_step2_h5ad": outdir / f"{prefix}.bdata_step2.h5ad",
        "adata_ref_step2_h5ad": outdir / f"{prefix}.adata_ref_step2.h5ad",
        "probs_ref_cal_csv": outdir / f"{prefix}.probs_ref_cal.csv",
    }


def _cls_component_json_path(config: BridgeRunConfig, component: str) -> Path:
    return config.paths.cls_output_dir / config.dataset.id / component / f"component_{component}_global.json"


def _validate_common_cls_inputs(config: BridgeRunConfig) -> dict[str, Path]:
    artifacts = _step2_artifact_paths(config)
    missing = [name for name, path in artifacts.items() if not path.exists()]
    if missing:
        raise WorkflowValidationError(f"Missing Step 2 artifacts required by CLS workflow: {', '.join(missing)}")
    return artifacts


def build_cls_run_plan(config: BridgeRunConfig) -> dict:
    artifacts = _validate_common_cls_inputs(config)
    enabled = config.cls.enabled_components
    checks = ["step2 artifact set resolved"]

    if "F" in enabled:
        if config.paths.ref_sceniclike_h5ad is None or not config.paths.ref_sceniclike_h5ad.exists():
            raise WorkflowValidationError("Component F requires 'paths.ref_sceniclike_h5ad' to exist.")
        if config.paths.regulons_json is None or not config.paths.regulons_json.exists():
            raise WorkflowValidationError("Component F requires 'paths.regulons_json' to exist.")
        checks.append("component F inputs resolved")

    if "D" in enabled and config.paths.ref_model_dir is not None and config.paths.ref_model_dir.exists():
        checks.append("component D may fall back to ref_model_dir for embeddings")
    elif "D" in enabled:
        checks.append("component D will require embeddings to already exist in step2 h5ad objects")

    if "E" in enabled:
        checks.append("component E will check required embeddings at runtime")

    outputs = {comp: str(_cls_component_json_path(config, comp)) for comp in enabled}
    return {
        "workflow": "cls",
        "dataset_id": config.dataset.id,
        "dataset_prefix": config.dataset.prefix,
        "target_class": config.identity.target_class,
        "enabled_components": enabled,
        "inputs": {name: str(path) for name, path in artifacts.items()},
        "outputs": outputs,
        "checks": checks,
    }


def run_cls_workflow(config: BridgeRunConfig, dry_run: bool = False) -> dict:
    plan = build_cls_run_plan(config)
    if dry_run:
        return plan

    import scanpy as sc

    artifacts = _step2_artifact_paths(config)
    bdata = sc.read_h5ad(artifacts["bdata_step2_h5ad"])
    adata_ref = sc.read_h5ad(artifacts["adata_ref_step2_h5ad"])
    probs_ref_cal = pd.read_csv(artifacts["probs_ref_cal_csv"], index_col=0)
    target_class = config.identity.target_class
    results: dict[str, dict] = {}

    common_kwargs = {
        "target_class": target_class,
        "outdir": str(config.paths.cls_output_dir),
        "dataset_id": config.dataset.id,
        "batch_key": config.cls.batch_key,
        "candidate_flag_prefix": config.cls.candidate_flag_prefix,
        "ref_label_key": config.cls.ref_label_key,
    }

    if "A" in config.cls.enabled_components:
        _, _, payload = compute_A_and_save(
            bdata=bdata,
            adata_ref=adata_ref,
            probs_ref_cal=probs_ref_cal,
            **common_kwargs,
            **config.cls.a,
        )
        results["A"] = payload

    if "B" in config.cls.enabled_components:
        _, _, payload = compute_B_and_save(
            bdata=bdata,
            adata_ref=adata_ref,
            **common_kwargs,
            **config.cls.b,
        )
        results["B"] = payload

    if "C" in config.cls.enabled_components:
        _, _, payload = compute_C_and_save(
            bdata=bdata,
            adata_ref=adata_ref,
            probs_ref_cal=probs_ref_cal,
            **common_kwargs,
            **config.cls.c,
        )
        results["C"] = payload

    if "D" in config.cls.enabled_components:
        d_kwargs = dict(config.cls.d)
        d_kwargs.setdefault("ref_model_dir", str(config.paths.ref_model_dir) if config.paths.ref_model_dir else None)
        _, _, payload = compute_D_and_save(
            bdata=bdata,
            adata_ref=adata_ref,
            **common_kwargs,
            **d_kwargs,
        )
        results["D"] = payload

    if "E" in config.cls.enabled_components:
        ref_mfp = adata_ref[adata_ref.obs[config.cls.ref_label_key].astype(str) == target_class].copy()
        flag_col = f"{config.cls.candidate_flag_prefix}{target_class}"
        if flag_col not in bdata.obs:
            raise WorkflowValidationError(f"Component E requires candidate flag column '{flag_col}' in Step 2 bdata.")
        org_mfp = bdata[bdata.obs[flag_col].astype(bool)].copy()
        _, _, payload = compute_E_and_save(
            adata_ref=ref_mfp,
            adata_org=org_mfp,
            outdir=str(config.paths.cls_output_dir),
            dataset_id=config.dataset.id,
            **config.cls.e,
        )
        results["E"] = payload

    if "F" in config.cls.enabled_components:
        if config.paths.ref_sceniclike_h5ad is None or config.paths.regulons_json is None:
            raise WorkflowValidationError("Component F requires 'paths.ref_sceniclike_h5ad' and 'paths.regulons_json'.")
        ref_sceniclike = sc.read_h5ad(config.paths.ref_sceniclike_h5ad)
        f_kwargs = dict(config.cls.f)
        f_kwargs.setdefault("save_qry_auc", True)
        _, _, payload = compute_F_and_save(
            adata_ref_sceniclike=ref_sceniclike,
            regulons_json_path=str(config.paths.regulons_json),
            adata_query=bdata,
            outdir=str(config.paths.cls_output_dir),
            dataset_id=config.dataset.id,
            batch_key=config.cls.batch_key,
            **f_kwargs,
        )
        results["F"] = payload

    return {
        "workflow": "cls",
        "status": "completed",
        "dataset_id": config.dataset.id,
        "enabled_components": config.cls.enabled_components,
        "component_outputs": {component: str(_cls_component_json_path(config, component)) for component in results},
    }
