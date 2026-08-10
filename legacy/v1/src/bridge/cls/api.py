from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from bridge.common.results import CLSComponentResult
from bridge.common.stats import normalize_weights

DEFAULT_ENABLED_COMPONENTS = ("A", "B", "C", "D", "E", "F")
DEFAULT_CLS_WEIGHTS = {
    "A": 0.2222,
    "B": 0.1667,
    "C": 0.1667,
    "D": 0.1111,
    "E": 0.1667,
    "F": 0.1667,
}


@dataclass(frozen=True)
class CLSContext:
    bdata: Any
    adata_ref: Any
    target_class: str
    output_dir: str | Path
    dataset_id: str
    probs_ref_cal: pd.DataFrame | None = None
    ref_model_dir: str | Path | None = None
    ref_sceniclike: Any | None = None
    regulons_json_path: str | Path | None = None
    batch_key: str = "Sample"
    candidate_flag_prefix: str = "is_candidate_"
    ref_label_key: str = "cell_subtype"

    def __post_init__(self) -> None:
        if not str(self.target_class).strip():
            raise ValueError("target_class must be a non-empty string.")
        if not str(self.dataset_id).strip():
            raise ValueError("dataset_id must be a non-empty string.")
        object.__setattr__(self, "output_dir", Path(self.output_dir))
        if self.ref_model_dir is not None:
            object.__setattr__(self, "ref_model_dir", Path(self.ref_model_dir))
        if self.regulons_json_path is not None:
            object.__setattr__(self, "regulons_json_path", Path(self.regulons_json_path))


@dataclass(frozen=True)
class CLSResult:
    component_results: dict[str, CLSComponentResult]
    component_payloads: dict[str, dict[str, Any]]
    summary: pd.DataFrame
    manifest: dict[str, Any]
    weighted_total_cls: float | None
    output_paths: dict[str, str]


def _component_json_path(ctx: CLSContext, component: str) -> Path:
    return ctx.output_dir / ctx.dataset_id / component / f"component_{component}_global.json"


def _component_dir(ctx: CLSContext, component: str) -> Path:
    return ctx.output_dir / ctx.dataset_id / component


def _report_paths(ctx: CLSContext) -> dict[str, Path]:
    base = ctx.output_dir / ctx.dataset_id
    return {
        "base_dir": base,
        "summary_csv": base / "summary.csv",
        "manifest_json": base / "manifest.json",
    }


def _saved_tuple_to_result(component: str, saved) -> CLSComponentResult:
    score_df, global_score, payload = saved[:3]
    meta = payload.get("meta", {}) if isinstance(payload, dict) else {}
    return CLSComponentResult(component=component, score_df=score_df, global_score=float(global_score), meta=meta)


def _require_probs_ref_cal(ctx: CLSContext, component: str) -> pd.DataFrame:
    if ctx.probs_ref_cal is None:
        raise ValueError(f"component_{component} requires CLSContext.probs_ref_cal.")
    return ctx.probs_ref_cal


def _common_kwargs(ctx: CLSContext) -> dict[str, Any]:
    return {
        "target_class": ctx.target_class,
        "outdir": str(ctx.output_dir),
        "dataset_id": ctx.dataset_id,
        "batch_key": ctx.batch_key,
        "candidate_flag_prefix": ctx.candidate_flag_prefix,
        "ref_label_key": ctx.ref_label_key,
    }


def component_A(ctx: CLSContext, **params) -> CLSComponentResult:
    from bridge.cls.component_a import compute_A_and_save

    kwargs = {**_common_kwargs(ctx), **params}
    saved = compute_A_and_save(
        bdata=ctx.bdata,
        adata_ref=ctx.adata_ref,
        probs_ref_cal=_require_probs_ref_cal(ctx, "A"),
        **kwargs,
    )
    return _saved_tuple_to_result("A", saved)


def component_B(ctx: CLSContext, **params) -> CLSComponentResult:
    from bridge.cls.component_b import compute_B_and_save

    kwargs = {**_common_kwargs(ctx), **params}
    saved = compute_B_and_save(
        bdata=ctx.bdata,
        adata_ref=ctx.adata_ref,
        **kwargs,
    )
    return _saved_tuple_to_result("B", saved)


def component_C(ctx: CLSContext, **params) -> CLSComponentResult:
    from bridge.cls.component_c import compute_C_and_save

    kwargs = {**_common_kwargs(ctx), **params}
    saved = compute_C_and_save(
        bdata=ctx.bdata,
        adata_ref=ctx.adata_ref,
        probs_ref_cal=_require_probs_ref_cal(ctx, "C"),
        **kwargs,
    )
    return _saved_tuple_to_result("C", saved)


def component_D(ctx: CLSContext, **params) -> CLSComponentResult:
    from bridge.cls.component_d import compute_D_and_save

    kwargs = {**_common_kwargs(ctx), **params}
    kwargs.setdefault("ref_model_dir", str(ctx.ref_model_dir) if ctx.ref_model_dir is not None else None)
    emb_key = str(kwargs.get("emb_key", "X_scanvi"))
    b_obsm = getattr(ctx.bdata, "obsm", {})
    r_obsm = getattr(ctx.adata_ref, "obsm", {})
    needs_embedding = emb_key not in b_obsm or emb_key not in r_obsm
    if needs_embedding and kwargs.get("ref_model_dir") is not None and "train_query" not in kwargs:
        kwargs["train_query"] = True

    saved = compute_D_and_save(
        bdata=ctx.bdata,
        adata_ref=ctx.adata_ref,
        **kwargs,
    )
    return _saved_tuple_to_result("D", saved)


def component_E(ctx: CLSContext, **params) -> CLSComponentResult:
    from bridge.cls.component_e import compute_E_and_save

    params = dict(params)
    ref_obsm = getattr(ctx.adata_ref, "obsm", {})
    org_obsm = getattr(ctx.bdata, "obsm", {})
    if "rep_key_ref" not in params and "X_scanvi" not in ref_obsm and "X_scVI" in ref_obsm:
        params["rep_key_ref"] = "X_scVI"
    if "rep_key_org" not in params and "X_scanvi" not in org_obsm and "X_pca" in org_obsm:
        params["rep_key_org"] = "X_pca"

    flag_col = f"{ctx.candidate_flag_prefix}{ctx.target_class}"
    if ctx.ref_label_key not in ctx.adata_ref.obs:
        raise KeyError(f"component_E requires ref_label_key '{ctx.ref_label_key}' in adata_ref.obs.")
    if flag_col not in ctx.bdata.obs:
        raise KeyError(f"component_E requires candidate flag column '{flag_col}' in bdata.obs.")

    ref_target = ctx.adata_ref[ctx.adata_ref.obs[ctx.ref_label_key].astype(str) == ctx.target_class].copy()
    org_target = ctx.bdata[ctx.bdata.obs[flag_col].astype(bool)].copy()
    saved = compute_E_and_save(
        adata_ref=ref_target,
        adata_org=org_target,
        outdir=str(ctx.output_dir),
        dataset_id=ctx.dataset_id,
        **params,
    )
    return _saved_tuple_to_result("E", saved)


def component_F(ctx: CLSContext, **params) -> CLSComponentResult:
    from bridge.cls.component_f import compute_F_and_save

    if ctx.ref_sceniclike is None:
        raise ValueError("component_F requires CLSContext.ref_sceniclike.")
    if ctx.regulons_json_path is None:
        raise ValueError("component_F requires CLSContext.regulons_json_path.")

    kwargs = dict(params)
    kwargs.setdefault("save_qry_auc", True)
    saved = compute_F_and_save(
        adata_ref_sceniclike=ctx.ref_sceniclike,
        regulons_json_path=str(ctx.regulons_json_path),
        adata_query=ctx.bdata,
        outdir=str(ctx.output_dir),
        dataset_id=ctx.dataset_id,
        batch_key=ctx.batch_key,
        **kwargs,
    )
    return _saved_tuple_to_result("F", saved)


def _normalize_components(enabled_components) -> list[str]:
    components = [str(component).upper() for component in enabled_components]
    unknown = sorted(set(components).difference(DEFAULT_ENABLED_COMPONENTS))
    if unknown:
        raise ValueError(f"Unknown CLS components: {', '.join(unknown)}")
    if not components:
        raise ValueError("enabled_components must include at least one CLS component.")
    return components


def _normalize_component_params(component_params: dict[str, dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    if component_params is None:
        return {}
    normalized: dict[str, dict[str, Any]] = {}
    for component, params in component_params.items():
        normalized[str(component).upper()] = dict(params)
    return normalized


def _component_functions() -> dict[str, Callable[..., CLSComponentResult]]:
    return {
        "A": component_A,
        "B": component_B,
        "C": component_C,
        "D": component_D,
        "E": component_E,
        "F": component_F,
    }


def _weighted_total(component_results: dict[str, CLSComponentResult], cls_weights: dict[str, float] | None) -> float | None:
    if not component_results:
        return None
    components = list(component_results.keys())
    weights_source = DEFAULT_CLS_WEIGHTS if cls_weights is None else {str(k).upper(): float(v) for k, v in cls_weights.items()}
    missing = [component for component in components if component not in weights_source]
    if missing:
        raise ValueError(f"cls_weights is missing enabled components: {', '.join(missing)}")
    weights = normalize_weights([weights_source[component] for component in components])
    scores = [component_results[component].global_score for component in components]
    total = sum(float(score) * float(weight) for score, weight in zip(scores, weights))
    return float(round(total, 12))


def _component_detail(ctx: CLSContext, result: CLSComponentResult) -> dict[str, Any]:
    component = result.component
    component_dir = _component_dir(ctx, component)
    return {
        "component": component,
        "global_score": float(result.global_score),
        "result_json": str(_component_json_path(ctx, component)),
        "has_batch_csv": (component_dir / f"component_{component}_batch.csv").exists(),
        "has_branch_csv": (component_dir / f"component_{component}_branch.csv").exists(),
        "has_genes_csv": (component_dir / f"component_{component}_genes.csv").exists(),
        "has_query_aucell_csv": (component_dir / "query_aucell.csv").exists(),
    }


def _candidate_summary(ctx: CLSContext) -> dict[str, Any]:
    query_count = int(getattr(ctx.bdata, "n_obs", len(ctx.bdata.obs)))
    flag_col = f"{ctx.candidate_flag_prefix}{ctx.target_class}"
    summary: dict[str, Any] = {"n_query": query_count, "candidate_count": None, "candidate_fraction": None}
    if flag_col in ctx.bdata.obs:
        candidate_count = int(ctx.bdata.obs[flag_col].astype(bool).sum())
        summary["candidate_count"] = candidate_count
        summary["candidate_fraction"] = float(candidate_count / query_count) if query_count else 0.0
    return summary


def _write_cls_report(
    ctx: CLSContext,
    component_results: dict[str, CLSComponentResult],
    component_payloads: dict[str, dict[str, Any]],
    weighted_total_cls: float | None,
) -> tuple[pd.DataFrame, dict[str, Any], dict[str, str]]:
    paths = _report_paths(ctx)
    paths["base_dir"].mkdir(parents=True, exist_ok=True)

    row: dict[str, Any] = {
        "dataset_id": ctx.dataset_id,
        "target_class": ctx.target_class,
        **_candidate_summary(ctx),
    }
    for component, result in component_results.items():
        row[f"cls_{component}"] = float(result.global_score)
        detail = _component_detail(ctx, result)
        row[f"has_{component}_detail_table"] = bool(
            detail["has_batch_csv"] or detail["has_branch_csv"] or detail["has_genes_csv"] or detail["has_query_aucell_csv"]
        )
    row["weighted_total_cls"] = weighted_total_cls
    summary_df = pd.DataFrame([row])
    summary_df.to_csv(paths["summary_csv"], index=False)

    manifest = {
        "dataset_id": ctx.dataset_id,
        "target_class": ctx.target_class,
        "enabled_components": list(component_results.keys()),
        "summary_csv": str(paths["summary_csv"]),
        "weighted_total_cls": weighted_total_cls,
        "component_payloads": {
            component: str(_component_json_path(ctx, component)) for component in component_results
        },
        "component_details": [_component_detail(ctx, result) for result in component_results.values()],
        "component_results": component_payloads,
    }
    paths["manifest_json"].write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    output_paths = {
        "summary_csv": str(paths["summary_csv"]),
        "manifest_json": str(paths["manifest_json"]),
    }
    for component in component_results:
        output_paths[f"component_{component}_json"] = str(_component_json_path(ctx, component))
    return summary_df, manifest, output_paths


def score(
    ctx: CLSContext,
    *,
    enabled_components=DEFAULT_ENABLED_COMPONENTS,
    component_params: dict[str, dict[str, Any]] | None = None,
    cls_weights: dict[str, float] | None = None,
) -> CLSResult:
    components = _normalize_components(enabled_components)
    params_by_component = _normalize_component_params(component_params)
    functions = _component_functions()

    component_results: dict[str, CLSComponentResult] = {}
    component_payloads: dict[str, dict[str, Any]] = {}
    for component in components:
        result = functions[component](ctx, **params_by_component.get(component, {}))
        component_results[component] = result
        component_payloads[component] = result.to_payload(dataset_id=ctx.dataset_id)

    weighted_total_cls = _weighted_total(component_results, cls_weights)
    summary, manifest, output_paths = _write_cls_report(ctx, component_results, component_payloads, weighted_total_cls)
    return CLSResult(
        component_results=component_results,
        component_payloads=component_payloads,
        summary=summary,
        manifest=manifest,
        weighted_total_cls=weighted_total_cls,
        output_paths=output_paths,
    )
