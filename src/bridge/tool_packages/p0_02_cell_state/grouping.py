from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Literal

import anndata as ad
import numpy as np
import pandas as pd
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score

from bridge.toolkit.contracts import InputAsset, ToolRequest


_SEEDS = (17, 29, 43, 71, 101)
_PRIMARY_RESOLUTION = 0.5
_SENSITIVITY_RESOLUTIONS = (0.3, 0.8)
_MIN_OBSERVATIONS = 200
_MAX_OBSERVATIONS = 200_000
_MIN_GENES = 500
_MAX_GROUPS = 30
_MIN_MEDOID_MEAN_ARI = 0.8
_MAX_CAPTURE_NMI = 0.5


@dataclass(frozen=True)
class GroupingOutcome:
    state: Literal["user_provided", "generated", "not_generated"]
    source: Literal["user_label", "exploratory_leiden", "whole_product"]
    labels: pd.Series | None
    grouping_key: str | None
    grouping_hash: str | None
    reason_codes: tuple[str, ...]
    method: dict[str, Any]
    warnings: tuple[str, ...] = ()

    @property
    def available(self) -> bool:
        return self.labels is not None


def resolve_product_grouping(
    adata: ad.AnnData,
    asset: InputAsset,
    request: ToolRequest,
    *,
    threads: int,
) -> GroupingOutcome:
    """Preserve declared user labels or derive neutral exploratory groups."""

    grouping_key = _declared_key(request, asset, "grouping_key")
    if grouping_key is not None:
        return _user_grouping(adata, grouping_key)
    if asset.matrix_semantics != "raw_counts":
        return _not_generated("raw_counts_required_for_exploratory_grouping")
    if adata.n_obs < _MIN_OBSERVATIONS:
        return _not_generated("too_few_observations_for_exploratory_grouping")
    if adata.n_obs > _MAX_OBSERVATIONS:
        return _not_generated("exploratory_grouping_resource_limit_exceeded")
    if adata.n_vars < _MIN_GENES:
        return _not_generated("too_few_genes_for_exploratory_grouping")

    preparation_key = _declared_key(request, asset, "preparation_key")
    capture_key = _declared_key(request, asset, "capture_key")
    missing = [
        key
        for key in (preparation_key, capture_key)
        if key is not None and key not in adata.obs
    ]
    if missing:
        return _not_generated(
            "declared_grouping_metadata_not_found",
            warnings=tuple(f"missing_obs_column:{key}" for key in missing),
        )
    preparations = (
        adata.obs[preparation_key].astype("string")
        if preparation_key is not None
        else pd.Series("product", index=adata.obs_names, dtype="string")
    )
    if preparations.isna().any() or (preparations.str.strip() == "").any():
        return _not_generated("preparation_metadata_incomplete")

    labels = pd.Series(index=adata.obs_names, dtype="string")
    records: list[dict[str, Any]] = []
    next_group = 1
    try:
        for preparation in sorted(preparations.unique()):
            mask = preparations.eq(preparation).to_numpy()
            subset = adata[mask].copy()
            if subset.n_obs < _MIN_OBSERVATIONS:
                return _not_generated(
                    "preparation_too_small_for_exploratory_grouping",
                    warnings=(f"preparation:{preparation}",),
                )
            captures = (
                adata.obs.loc[subset.obs_names, capture_key].astype("string")
                if capture_key is not None
                else None
            )
            if captures is not None and (
                captures.isna().any() or (captures.str.strip() == "").any()
            ):
                return _not_generated("capture_metadata_incomplete")
            partition = _cluster_preparation(
                subset,
                captures=captures,
                threads=threads,
            )
            if partition["reason_code"] is not None:
                return _not_generated(
                    str(partition["reason_code"]),
                    warnings=(f"preparation:{preparation}",),
                )
            selected = partition.pop("selected")
            local_to_public = {
                local: f"Cluster {index:02d}"
                for index, local in enumerate(
                    sorted(pd.unique(selected), key=_natural_cluster_key),
                    start=next_group,
                )
            }
            if next_group - 1 + len(local_to_public) > _MAX_GROUPS:
                return _not_generated("exploratory_grouping_too_many_groups")
            next_group += len(local_to_public)
            labels.loc[subset.obs_names] = [
                local_to_public[str(value)] for value in selected
            ]
            records.append(
                {
                    "preparation_id": str(preparation),
                    "public_group_ids": list(local_to_public.values()),
                    **partition,
                }
            )
    except (ImportError, ModuleNotFoundError):
        return _not_generated("exploratory_grouping_dependency_unavailable")
    except Exception as exc:  # grouping is optional; identity analysis still proceeds
        return _not_generated(
            "exploratory_grouping_failed",
            warnings=(f"error_type:{type(exc).__name__}",),
        )

    if labels.isna().any():
        return _not_generated("exploratory_grouping_incomplete")
    method = {
        "method_id": "BRIDGE-EXPLORATORY-LEIDEN",
        "method_version": "0.1.0",
        "n_groups": int(labels.nunique()),
        "parameters": {
            "normalization_target_sum": 10_000,
            "n_highly_variable_genes": 2_000,
            "n_principal_components": 30,
            "n_neighbors": 30,
            "graph": "undirected_weighted",
            "resolution": _PRIMARY_RESOLUTION,
            "seeds": list(_SEEDS),
            "medoid_selection": "highest_mean_pairwise_adjusted_rand_index",
            "sensitivity_resolutions": list(_SENSITIVITY_RESOLUTIONS),
            "minimum_medoid_mean_ari": _MIN_MEDOID_MEAN_ARI,
            "maximum_capture_nmi": _MAX_CAPTURE_NMI,
        },
        "preparations": records,
        "runtime": {
            "threads": threads,
        },
        "interpretation": (
            "Exploratory expression-similarity groups; groups do not assign "
            "cell identity or product roles."
        ),
    }
    return GroupingOutcome(
        state="generated",
        source="exploratory_leiden",
        labels=labels,
        grouping_key=None,
        grouping_hash=_series_hash(labels),
        reason_codes=(),
        method=method,
    )


def _user_grouping(adata: ad.AnnData, grouping_key: str) -> GroupingOutcome:
    if grouping_key not in adata.obs:
        return _not_generated(
            "declared_grouping_key_not_found",
            warnings=(f"missing_obs_column:{grouping_key}",),
        )
    labels = adata.obs[grouping_key].astype("string")
    if labels.isna().any() or (labels.str.strip() == "").any():
        return _not_generated("declared_grouping_labels_incomplete")
    labels = labels.astype(str)
    return GroupingOutcome(
        state="user_provided",
        source="user_label",
        labels=labels,
        grouping_key=grouping_key,
        grouping_hash=_series_hash(labels),
        reason_codes=(),
        method={
            "method_id": "USER-PROVIDED-GROUPING",
            "method_version": "1",
            "interpretation": (
                "User-provided labels are preserved verbatim and are not "
                "treated as reference-derived identities."
            ),
        },
    )


def _cluster_preparation(
    adata: ad.AnnData,
    *,
    captures: pd.Series | None,
    threads: int,
) -> dict[str, Any]:
    import scanpy as sc
    from threadpoolctl import threadpool_limits

    batch_key = None
    if captures is not None and captures.nunique() > 1:
        batch_key = "_bridge_capture"
        adata.obs[batch_key] = captures.loc[adata.obs_names].astype(str).to_numpy()

    with threadpool_limits(limits=threads):
        sc.pp.normalize_total(adata, target_sum=10_000)
        sc.pp.log1p(adata)
        sc.pp.highly_variable_genes(
            adata,
            n_top_genes=min(2_000, adata.n_vars),
            flavor="seurat",
            batch_key=batch_key,
            subset=True,
        )
        if adata.n_vars <= 30:
            return {"reason_code": "insufficient_highly_variable_genes"}
        sc.pp.pca(adata, n_comps=30, zero_center=True, random_state=_SEEDS[0])
        sc.pp.neighbors(
            adata,
            n_neighbors=30,
            n_pcs=30,
            random_state=_SEEDS[0],
        )
        partitions = [
            _leiden(adata, resolution=_PRIMARY_RESOLUTION, seed=seed)
            for seed in _SEEDS
        ]
        ari = np.asarray(
            [
                [
                    adjusted_rand_score(left, right)
                    for right in partitions
                ]
                for left in partitions
            ],
            dtype=float,
        )
        means = (ari.sum(axis=1) - 1.0) / (len(_SEEDS) - 1)
        medoid_index = int(np.argmax(means))
        selected = partitions[medoid_index]
        medoid_mean = float(means[medoid_index])
        if medoid_mean < _MIN_MEDOID_MEAN_ARI:
            return {"reason_code": "exploratory_grouping_unstable"}
        n_groups = len(pd.unique(selected))
        if n_groups == 1:
            return {"reason_code": "exploratory_grouping_single_group"}
        if n_groups > _MAX_GROUPS:
            return {"reason_code": "exploratory_grouping_too_many_groups"}
        capture_nmi = None
        if captures is not None and captures.nunique() > 1:
            capture_nmi = float(
                normalized_mutual_info_score(
                    captures.loc[adata.obs_names].astype(str),
                    selected,
                )
            )
            if capture_nmi > _MAX_CAPTURE_NMI:
                return {"reason_code": "exploratory_grouping_capture_dominated"}
        sensitivity = {}
        for resolution in _SENSITIVITY_RESOLUTIONS:
            alternative = _leiden(
                adata,
                resolution=resolution,
                seed=_SEEDS[medoid_index],
            )
            sensitivity[str(resolution)] = {
                "n_groups": int(len(pd.unique(alternative))),
                "adjusted_rand_index_to_primary": float(
                    adjusted_rand_score(selected, alternative)
                ),
            }
    return {
        "reason_code": None,
        "selected": selected,
        "n_observations": int(adata.n_obs),
        "n_groups": int(n_groups),
        "selected_seed": int(_SEEDS[medoid_index]),
        "medoid_mean_ari": medoid_mean,
        "minimum_pairwise_ari": float(ari[np.triu_indices(len(_SEEDS), 1)].min()),
        "capture_nmi": capture_nmi,
        "sensitivity": sensitivity,
    }


def _leiden(adata: ad.AnnData, *, resolution: float, seed: int) -> np.ndarray:
    import scanpy as sc

    key = f"_bridge_leiden_{resolution}_{seed}"
    sc.tl.leiden(
        adata,
        resolution=resolution,
        random_state=seed,
        directed=False,
        use_weights=True,
        flavor="igraph",
        n_iterations=-1,
        key_added=key,
    )
    return adata.obs[key].astype(str).to_numpy()


def _declared_key(
    request: ToolRequest,
    asset: InputAsset,
    name: str,
) -> str | None:
    value = request.parameters.get(name, asset.metadata.get(name))
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


def _not_generated(
    reason_code: str,
    *,
    warnings: tuple[str, ...] = (),
) -> GroupingOutcome:
    return GroupingOutcome(
        state="not_generated",
        source="whole_product",
        labels=None,
        grouping_key=None,
        grouping_hash=None,
        reason_codes=(reason_code,),
        method={
            "method_id": "BRIDGE-EXPLORATORY-LEIDEN",
            "method_version": "0.1.0",
            "interpretation": "Whole-product view retained; no grouping was inferred.",
        },
        warnings=warnings,
    )


def _series_hash(values: pd.Series) -> str:
    payload = [
        [str(index), str(value)]
        for index, value in values.items()
    ]
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _natural_cluster_key(value: object) -> tuple[int, str]:
    text = str(value)
    return (int(text), text) if text.isdigit() else (2**31 - 1, text)
