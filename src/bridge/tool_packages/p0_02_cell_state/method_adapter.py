from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.util
import json
import os
import sys
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd
import h5py
from scipy import sparse
from pydantic import ValidationError

from bridge.toolkit.contracts import BenchmarkSplitManifest

ADAPTER_IMPLEMENTATION_VERSION = "0.2.2"


class MethodAdapterError(RuntimeError):
    def __init__(self, reason_code: str, detail: str | None = None) -> None:
        self.reason_code = reason_code
        super().__init__(f"{reason_code}: {detail}" if detail else reason_code)


@dataclass(frozen=True)
class AdapterBundle:
    asset_id: str
    matrix: sparse.csr_matrix
    features: list[str]
    observations: pd.DataFrame
    metadata: dict[str, Any]
    raw_counts: sparse.csr_matrix | None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bridge-cellstate-adapter")
    methods = parser.add_subparsers(dest="method", required=True)
    for method in ("celltypist", "scanvi"):
        command = methods.add_parser(method)
        command.add_argument("--exchange-root", required=True)
        command.add_argument("--asset-id", required=True)
        command.add_argument("--split-manifest", required=True)
        command.add_argument("--output", required=True)
        command.add_argument("--seed", type=int, default=0)
        command.add_argument("--query-asset", action="append", default=[])
    celltypist = methods.choices["celltypist"]
    celltypist.add_argument("--max-iter", type=int, default=200)
    celltypist.add_argument("--n-jobs", type=int, default=1)
    scanvi = methods.choices["scanvi"]
    scanvi.add_argument("--preset", choices=("small", "full"), default="small")
    scanvi.add_argument("--scvi-epochs", type=int)
    scanvi.add_argument("--scanvi-epochs", type=int)
    scanvi.add_argument("--accelerator", choices=("auto", "cpu", "gpu"), default="auto")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    common = {
        "exchange_root": Path(args.exchange_root),
        "asset_id": args.asset_id,
        "split_manifest_path": Path(args.split_manifest),
        "output_path": Path(args.output),
        "seed": args.seed,
        "query_asset_ids": args.query_asset,
    }
    if args.method == "celltypist":
        run_celltypist(**common, max_iter=args.max_iter, n_jobs=args.n_jobs)
    else:
        run_scanvi(
            **common,
            preset=args.preset,
            scvi_epochs=args.scvi_epochs,
            scanvi_epochs=args.scanvi_epochs,
            accelerator=args.accelerator,
        )
    return 0


def run_celltypist(
    *,
    exchange_root: Path,
    asset_id: str,
    split_manifest_path: Path,
    output_path: Path,
    seed: int = 0,
    max_iter: int = 200,
    n_jobs: int = 1,
    query_asset_ids: Sequence[str] = (),
) -> dict[str, Any]:
    bundle, folds = load_adapter_context(exchange_root, asset_id, split_manifest_path)
    split = _load_split(split_manifest_path, asset_id)
    query_bundles = _load_query_bundles(
        exchange_root,
        query_asset_ids,
        expected_level=str(bundle.metadata["label_level"]),
        split=split,
    )
    if bundle.metadata.get("matrix_semantics") not in {
        "raw_counts",
        "normalized_expression",
    }:
        raise MethodAdapterError("celltypist_expression_semantics_unsupported")
    celltypist = _require_module("celltypist")
    anndata = _require_module("anndata")
    sklearn = _require_module("sklearn")
    if _package_version("celltypist") == "1.7.1" and _version_prefix(sklearn.__version__) >= (1, 8):
        raise MethodAdapterError(
            "celltypist_dependency_incompatible", f"scikit-learn={sklearn.__version__}"
        )
    label_universe = _label_universe(bundle)
    missing_by_fold: dict[str, list[str]] = {}
    frames = []
    for fold_id, partitions in folds.items():
        train = partitions.eq("train").to_numpy()
        query = partitions.isin(["calibration", "test"]).to_numpy()
        _validate_training_labels(bundle.observations, train, fold_id)
        model = celltypist.train(
            X=bundle.matrix[train],
            labels=bundle.observations.loc[train, "true_label"].astype(str).to_numpy(),
            genes=bundle.features,
            check_expression=False,
            max_iter=max_iter,
            n_jobs=n_jobs,
            random_state=seed,
        )
        query_obs = bundle.observations.loc[query].copy()
        adata = anndata.AnnData(
            X=bundle.matrix[query].copy(),
            obs=query_obs.set_index("observation_id", drop=False),
            var=pd.DataFrame(index=bundle.features),
        )
        result = celltypist.annotate(
            adata,
            model=model,
            mode="best match",
            majority_voting=False,
        )
        probabilities = _celltypist_probabilities(result, query_obs, model)
        probabilities, missing_by_fold[fold_id] = _align_probability_columns(
            probabilities, label_universe
        )
        frames.append(
            _prediction_rows(
                fold_id,
                query_obs,
                partitions.loc[query],
                probabilities,
                simplex=False,
                asset_id=bundle.asset_id,
                source_family_id=str(bundle.metadata["source_family_id"]),
                label_level=str(bundle.metadata["label_level"]),
            )
        )
        for query_bundle in query_bundles:
            query_obs = query_bundle.observations.copy()
            query_data = anndata.AnnData(
                X=query_bundle.matrix.copy(),
                obs=query_obs.set_index("observation_id", drop=False),
                var=pd.DataFrame(index=query_bundle.features),
            )
            result = celltypist.annotate(
                query_data, model=model, mode="best match", majority_voting=False
            )
            probabilities = _celltypist_probabilities(result, query_obs, model)
            probabilities, _ = _align_probability_columns(probabilities, label_universe)
            partition = str(query_bundle.metadata["data_role"])
            frames.append(
                _prediction_rows(
                    fold_id,
                    query_obs,
                    pd.Series(partition, index=query_obs.index),
                    probabilities,
                    simplex=False,
                    asset_id=query_bundle.asset_id,
                    source_family_id=str(query_bundle.metadata["source_family_id"]),
                    label_level=str(query_bundle.metadata["label_level"]),
                    assignment_state="forced_mapping_uncalibrated",
                )
            )
    metadata = adapter_metadata("celltypist", seed=seed)
    metadata.update(
        {
            "max_iter": max_iter,
            "n_jobs": n_jobs,
            "query_asset_ids": sorted(query_asset_ids),
            "fold_missing_training_labels": missing_by_fold,
            **_input_provenance(
                exchange_root,
                [asset_id, *query_asset_ids],
                split_manifest_path,
            ),
        }
    )
    return _write_predictions(output_path, frames, metadata)


def run_scanvi(
    *,
    exchange_root: Path,
    asset_id: str,
    split_manifest_path: Path,
    output_path: Path,
    seed: int = 0,
    preset: str = "small",
    scvi_epochs: int | None = None,
    scanvi_epochs: int | None = None,
    accelerator: str = "auto",
    query_asset_ids: Sequence[str] = (),
) -> dict[str, Any]:
    if query_asset_ids:
        raise MethodAdapterError("scanvi_external_query_adapter_not_implemented")
    bundle, folds = load_adapter_context(
        exchange_root,
        asset_id,
        split_manifest_path,
        require_raw_counts=True,
    )
    if bundle.raw_counts is None:
        raise MethodAdapterError("scanvi_raw_counts_required")
    os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"
    anndata = _require_module("anndata")
    scvi = _require_module("scvi")
    torch = _require_module("torch")
    epochs = {"small": (20, 10), "full": (200, 100)}[preset]
    scvi_epochs = scvi_epochs or epochs[0]
    scanvi_epochs = scanvi_epochs or epochs[1]
    if scvi_epochs < 1 or scanvi_epochs < 1:
        raise MethodAdapterError("training_epochs_must_be_positive")

    np.random.seed(seed)
    torch.manual_seed(seed)
    scvi.settings.seed = seed
    label_universe = _label_universe(bundle)
    missing_by_fold: dict[str, list[str]] = {}
    frames = []
    for fold_id, partitions in folds.items():
        included = partitions.isin(["train", "calibration", "test"]).to_numpy()
        train = partitions.eq("train").to_numpy()
        _validate_training_labels(bundle.observations, train, fold_id)
        obs = bundle.observations.loc[included].copy()
        fold_partitions = partitions.loc[included].reset_index(drop=True)
        obs["_bridge_label"] = np.where(
            fold_partitions.eq("train"), obs["true_label"].astype(str), "__unlabeled__"
        )
        adata = anndata.AnnData(
            X=bundle.raw_counts[included].copy(),
            obs=obs.set_index("observation_id", drop=False),
            var=pd.DataFrame(index=bundle.features),
        )
        scvi.model.SCVI.setup_anndata(
            adata,
            labels_key="_bridge_label",
            batch_key="sample_id",
        )
        vae = scvi.model.SCVI(adata)
        vae.train(max_epochs=scvi_epochs, **_scanvi_trainer_kwargs(accelerator))
        model = scvi.model.SCANVI.from_scvi_model(
            vae,
            labels_key="_bridge_label",
            unlabeled_category="__unlabeled__",
        )
        model.train(max_epochs=scanvi_epochs, **_scanvi_trainer_kwargs(accelerator))
        query = fold_partitions.isin(["calibration", "test"]).to_numpy()
        probabilities = _scanvi_probabilities(model, adata[query].copy())
        probabilities, missing_by_fold[fold_id] = _align_probability_columns(
            probabilities, label_universe
        )
        query_obs = obs.iloc[query].copy()
        frames.append(
            _prediction_rows(
                fold_id,
                query_obs,
                fold_partitions.loc[query],
                probabilities,
                simplex=True,
                asset_id=bundle.asset_id,
                source_family_id=str(bundle.metadata["source_family_id"]),
                label_level=str(bundle.metadata["label_level"]),
            )
        )
    metadata = adapter_metadata("scanvi", seed=seed)
    metadata.update(
        {
            "preset": preset,
            "scvi_epochs": scvi_epochs,
            "scanvi_epochs": scanvi_epochs,
            "accelerator": accelerator,
            "deterministic_training": True,
            "trainer_benchmark": False,
            "cublas_workspace_config": os.environ["CUBLAS_WORKSPACE_CONFIG"],
            "fold_missing_training_labels": missing_by_fold,
            **_input_provenance(exchange_root, [asset_id], split_manifest_path),
        }
    )
    return _write_predictions(output_path, frames, metadata)


def _scanvi_trainer_kwargs(accelerator: str) -> dict[str, Any]:
    return {
        "accelerator": accelerator,
        "deterministic": True,
        "benchmark": False,
        "enable_checkpointing": False,
        "logger": False,
    }


def load_adapter_context(
    exchange_root: Path,
    asset_id: str,
    split_manifest_path: Path,
    *,
    require_raw_counts: bool = False,
) -> tuple[AdapterBundle, dict[str, pd.Series]]:
    split = _load_split(split_manifest_path, asset_id)
    bundle = _load_bundle(exchange_root, asset_id, require_raw_counts=require_raw_counts)
    rows = [record for record in split.records if record.asset_id == asset_id]
    folds: dict[str, pd.Series] = {}
    for fold_id in sorted({record.fold_id for record in rows if record.fold_id}):
        mapping = {
            record.sample_id: record.partition for record in rows if record.fold_id == fold_id
        }
        partitions = bundle.observations["sample_id"].astype(str).map(mapping)
        if partitions.isna().any():
            raise MethodAdapterError("split_missing_bundle_sample", fold_id)
        observed = set(partitions)
        if not {"train", "calibration", "test"}.issubset(observed):
            raise MethodAdapterError("train_calibration_test_required", fold_id)
        folds[str(fold_id)] = partitions
    if not folds:
        raise MethodAdapterError("benchmark_folds_not_found", asset_id)
    return bundle, folds


def _load_query_bundles(
    exchange_root: Path,
    asset_ids: Sequence[str],
    *,
    expected_level: str,
    split: BenchmarkSplitManifest,
) -> list[AdapterBundle]:
    bundles = []
    for asset_id in sorted(set(asset_ids)):
        records = [record for record in split.records if record.asset_id == asset_id]
        if not records:
            raise MethodAdapterError("query_asset_not_in_split_manifest", asset_id)
        partitions = {record.partition for record in records}
        if not partitions.issubset({"development_ood", "behavior_only"}):
            raise MethodAdapterError("query_asset_partition_invalid", asset_id)
        bundle = _load_bundle(exchange_root, asset_id, require_raw_counts=False)
        if bundle.metadata.get("label_level") != expected_level:
            raise MethodAdapterError("query_label_level_mismatch", asset_id)
        if bundle.metadata.get("data_role") not in {"development_ood", "behavior_only"}:
            raise MethodAdapterError("query_asset_role_invalid", asset_id)
        if {str(bundle.metadata["data_role"])} != partitions:
            raise MethodAdapterError("query_asset_role_split_mismatch", asset_id)
        if any(record.source_family_id != bundle.metadata["source_family_id"] for record in records):
            raise MethodAdapterError("query_asset_source_family_mismatch", asset_id)
        bundles.append(bundle)
    return bundles


def adapter_metadata(method: str, *, seed: int = 0) -> dict[str, Any]:
    if method == "celltypist":
        return {
            "adapter": "celltypist_custom",
            "adapter_implementation_version": ADAPTER_IMPLEMENTATION_VERSION,
            "package_version": _package_version("celltypist"),
            "probability_semantics": "one_vs_rest_sigmoid",
            "row_sum_constraint": "none",
            "conformal_eligible": False,
            "not_conformal_ready_reason": "independent_sigmoid_scores_are_not_categorical_simplex",
            "evidence_family": "supervised_classifier",
            "seed": seed,
        }
    if method == "scanvi":
        return {
            "adapter": "scanvi",
            "adapter_implementation_version": ADAPTER_IMPLEMENTATION_VERSION,
            "package_version": _package_version("scvi-tools"),
            "probability_semantics": "categorical_simplex",
            "row_sum_constraint": "sum_to_one",
            "conformal_eligible": True,
            "calibration_partition_required": True,
            "query_expression_used_as_unlabeled_during_training": True,
            "evidence_family": "latent_reference_mapping",
            "seed": seed,
        }
    raise MethodAdapterError("adapter_not_supported", method)


def _load_split(path: Path, asset_id: str) -> BenchmarkSplitManifest:
    try:
        split = BenchmarkSplitManifest.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError, ValueError) as exc:
        raise MethodAdapterError("split_manifest_invalid", str(exc)) from exc
    if split.phase != "pilot" or split.locked_assets_opened or split.sealed_assets_opened:
        raise MethodAdapterError("locked_or_sealed_split_forbidden")
    rows = [record for record in split.records if record.asset_id == asset_id]
    if not rows:
        raise MethodAdapterError("asset_not_in_split_manifest", asset_id)
    identities = [(record.fold_id, record.source_family_id, record.sample_id) for record in rows]
    if len(identities) != len(set(identities)):
        raise MethodAdapterError("split_sample_record_not_unique", asset_id)
    if any(
        record.partition == "locked_test"
        or "sealed" in record.data_role.casefold()
        or "competitor" in record.data_role.casefold()
        for record in rows
    ):
        raise MethodAdapterError("locked_or_sealed_split_forbidden", asset_id)
    return split


def _load_bundle(root: Path, asset_id: str, *, require_raw_counts: bool) -> AdapterBundle:
    bundle_root = root / asset_id
    metadata_path = bundle_root / "bundle.json"
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MethodAdapterError("bundle_manifest_invalid", asset_id) from exc
    if metadata.get("asset_id") != asset_id:
        raise MethodAdapterError("bundle_asset_id_mismatch", asset_id)
    if not metadata.get("source_family_id") or not metadata.get("label_level"):
        raise MethodAdapterError("bundle_context_incomplete", asset_id)
    if not isinstance(metadata.get("label_universe"), list):
        raise MethodAdapterError("bundle_label_universe_invalid", asset_id)
    artifacts = metadata.get("artifacts")
    if not isinstance(artifacts, dict):
        raise MethodAdapterError("bundle_artifacts_missing", asset_id)
    required = ("matrix.h5", "features.tsv", "observations.tsv", "observations.parquet")
    for name in required:
        _validate_artifact(bundle_root, name, artifacts.get(name))

    matrix = _read_matrix(bundle_root / "matrix.h5")
    features = (
        pd.read_csv(bundle_root / "features.tsv", sep="\t", header=None)[0]
        .astype(str)
        .tolist()
    )
    observations = pd.read_csv(bundle_root / "observations.tsv", sep="\t", dtype=str)
    try:
        parquet_observations = pd.read_parquet(bundle_root / "observations.parquet")
    except ImportError as exc:
        raise MethodAdapterError("python_package_missing", "pyarrow") from exc
    except Exception as exc:
        raise MethodAdapterError("bundle_observations_parquet_invalid") from exc
    _validate_observation_views(observations, parquet_observations)
    _validate_bundle_shape(matrix, features, observations, metadata)

    raw_counts = matrix if metadata.get("matrix_semantics") == "raw_counts" else None
    if raw_counts is not None:
        values = raw_counts.data
        if np.any(values < 0) or not np.allclose(values, np.rint(values)):
            raise MethodAdapterError("raw_counts_must_be_nonnegative_integers")
        matrix = _log1p_cp10k(raw_counts)
    if require_raw_counts and raw_counts is None:
        raise MethodAdapterError("scanvi_raw_counts_required")
    return AdapterBundle(asset_id, matrix, features, observations, metadata, raw_counts)


def _validate_artifact(root: Path, name: str, expected_sha256: Any) -> None:
    safe_name = _safe_relative_name(name)
    path = root / safe_name
    if not path.is_file():
        raise MethodAdapterError("bundle_artifact_missing", safe_name)
    if not isinstance(expected_sha256, str) or _sha256(path) != expected_sha256:
        raise MethodAdapterError("bundle_artifact_checksum_mismatch", safe_name)


def _safe_relative_name(value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise MethodAdapterError("bundle_artifact_path_invalid")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or len(path.parts) != 1:
        raise MethodAdapterError("bundle_artifact_path_invalid", value)
    return value


def _read_matrix(path: Path) -> sparse.csr_matrix:
    try:
        with h5py.File(path, "r") as handle:
            group = handle["matrix"]
            if group.attrs.get("format") != "csr":
                raise MethodAdapterError("bundle_matrix_format_invalid")
            shape = tuple(int(value) for value in group["shape"][:])
            matrix = sparse.csr_matrix(
                (group["data"][:], group["indices"][:], group["indptr"][:]),
                shape=shape,
            )
    except MethodAdapterError:
        raise
    except Exception as exc:
        raise MethodAdapterError("bundle_matrix_invalid") from exc
    return matrix.astype(np.float32)


def _log1p_cp10k(counts: sparse.csr_matrix) -> sparse.csr_matrix:
    totals = np.asarray(counts.sum(axis=1)).ravel()
    scale = np.divide(10_000.0, totals, out=np.zeros_like(totals), where=totals > 0)
    matrix = (sparse.diags(scale) @ counts).astype(np.float32).tocsr()
    matrix.data = np.log1p(matrix.data)
    return matrix


def _validate_bundle_shape(
    matrix: sparse.csr_matrix,
    features: list[str],
    observations: pd.DataFrame,
    metadata: dict[str, Any],
) -> None:
    required = {"observation_id", "sample_id", "true_label"}
    if not required.issubset(observations.columns):
        raise MethodAdapterError("bundle_observations_incomplete")
    if observations["observation_id"].duplicated().any():
        raise MethodAdapterError("bundle_observation_ids_not_unique")
    if observations[["observation_id", "sample_id"]].isna().any().any():
        raise MethodAdapterError("bundle_observation_identity_missing")
    if len(features) != len(set(features)):
        raise MethodAdapterError("bundle_features_not_unique")
    expected = tuple(metadata.get("matrix_shape", ()))
    if matrix.shape != (len(observations), len(features)) or expected != matrix.shape:
        raise MethodAdapterError("bundle_matrix_shape_mismatch")


def _validate_observation_views(tsv: pd.DataFrame, parquet: pd.DataFrame) -> None:
    required = ["observation_id", "sample_id", "true_label"]
    if not set(required).issubset(parquet.columns) or len(tsv) != len(parquet):
        raise MethodAdapterError("bundle_observation_views_mismatch")
    left = tsv[required].fillna("").astype(str).reset_index(drop=True)
    right = parquet[required].fillna("").astype(str).reset_index(drop=True)
    if not left.equals(right):
        raise MethodAdapterError("bundle_observation_views_mismatch")


def _validate_training_labels(observations: pd.DataFrame, train: np.ndarray, fold_id: str) -> None:
    labels = observations.loc[train, "true_label"]
    if labels.isna().any() or (labels.astype(str).str.strip() == "").any():
        raise MethodAdapterError("training_labels_missing", fold_id)
    if labels.nunique() < 2:
        raise MethodAdapterError("at_least_two_training_labels_required", fold_id)


def _label_universe(bundle: AdapterBundle) -> list[str]:
    labels = bundle.metadata.get("label_universe")
    if not isinstance(labels, list) or len(labels) < 2:
        raise MethodAdapterError("bundle_label_universe_invalid", bundle.asset_id)
    normalized = sorted({str(label) for label in labels if str(label)})
    level = str(bundle.metadata["label_level"])
    if len(normalized) != len(labels) or any(
        not label.startswith(f"{level}:") for label in normalized
    ):
        raise MethodAdapterError("bundle_label_universe_invalid", bundle.asset_id)
    return normalized


def _align_probability_columns(
    probabilities: pd.DataFrame, label_universe: Sequence[str]
) -> tuple[pd.DataFrame, list[str]]:
    unexpected = sorted(set(probabilities.columns.astype(str)) - set(label_universe))
    if unexpected:
        raise MethodAdapterError("prediction_labels_outside_reference", ",".join(unexpected))
    missing = sorted(set(label_universe) - set(probabilities.columns.astype(str)))
    aligned = probabilities.copy()
    aligned.columns = aligned.columns.astype(str)
    return aligned.reindex(columns=label_universe, fill_value=0.0), missing


def _celltypist_probabilities(result: Any, query_obs: pd.DataFrame, model: Any) -> pd.DataFrame:
    values = result.probability_matrix
    if isinstance(values, pd.DataFrame):
        probabilities = values.copy()
    else:
        classes = [str(item) for item in getattr(model, "cell_types", [])]
        probabilities = pd.DataFrame(values, columns=classes or None)
    if probabilities.shape[0] != len(query_obs) or probabilities.shape[1] < 2:
        raise MethodAdapterError("celltypist_probability_shape_invalid")
    probabilities.index = query_obs["observation_id"].astype(str)
    probabilities.columns = probabilities.columns.astype(str)
    return probabilities


def _scanvi_probabilities(model: Any, query: Any) -> pd.DataFrame:
    values = model.predict(query, soft=True)
    if isinstance(values, pd.DataFrame):
        probabilities = values.copy()
    else:
        try:
            registry = model.adata_manager.get_state_registry("labels")
            classes = [str(value) for value in registry.categorical_mapping]
            classes = [value for value in classes if value != "__unlabeled__"]
        except Exception as exc:  # pragma: no cover - depends on scvi internals
            raise MethodAdapterError("scanvi_probability_labels_unavailable") from exc
        probabilities = pd.DataFrame(values, columns=classes)
    probabilities.index = query.obs_names.astype(str)
    if probabilities.shape[1] < 2 or not np.allclose(
        probabilities.sum(axis=1).to_numpy(), 1.0, atol=1e-5
    ):
        raise MethodAdapterError("scanvi_probabilities_not_categorical_simplex")
    return probabilities


def _prediction_rows(
    fold_id: str,
    observations: pd.DataFrame,
    partitions: pd.Series,
    probabilities: pd.DataFrame,
    *,
    simplex: bool,
    asset_id: str,
    source_family_id: str,
    label_level: str,
    assignment_state: str = "assigned_uncalibrated",
) -> pd.DataFrame:
    values = probabilities.to_numpy(dtype=float)
    if np.isnan(values).any() or np.any((values < 0) | (values > 1)):
        raise MethodAdapterError("probability_values_invalid", fold_id)
    order = np.argsort(values, axis=1)
    top = order[:, -1]
    second = order[:, -2]
    labels = probabilities.columns.to_numpy(dtype=str)[top]
    frame = pd.DataFrame(
        {
            "fold_id": fold_id,
            "observation_id": observations["observation_id"].astype(str).to_numpy(),
            "sample_id": observations["sample_id"].astype(str).to_numpy(),
            "asset_id": asset_id,
            "source_family_id": source_family_id,
            "label_level": label_level,
            "partition": partitions.astype(str).to_numpy(),
            "true_label": observations["true_label"].to_numpy(),
            "predicted_label": labels,
            "score": values[np.arange(len(values)), top],
            "margin": values[np.arange(len(values)), top] - values[np.arange(len(values)), second],
            "assignment_state": assignment_state,
            "prediction_set": [json.dumps([label], separators=(",", ":")) for label in labels],
        }
    )
    reserved = {"observation_id", "sample_id", "true_label"}
    for column in observations.columns:
        if column not in reserved and column not in frame and not column.startswith("_"):
            frame[column] = observations[column].to_numpy()
    for index, state_id in enumerate(probabilities.columns.astype(str)):
        frame[f"prob__{state_id}"] = values[:, index]
    if simplex and not np.allclose(values.sum(axis=1), 1.0, atol=1e-5):
        raise MethodAdapterError("probability_rows_must_sum_to_one", fold_id)
    return frame


def _write_predictions(
    output_path: Path, frames: list[pd.DataFrame], metadata: dict[str, Any]
) -> dict[str, Any]:
    if not frames:
        raise MethodAdapterError("adapter_produced_no_predictions")
    frame = pd.concat(frames, ignore_index=True).sort_values(
        ["fold_id", "partition", "observation_id"]
    )
    if frame[["fold_id", "observation_id"]].duplicated().any():
        raise MethodAdapterError("prediction_identity_not_unique")
    probability_columns = [column for column in frame if column.startswith("prob__")]
    if probability_columns:
        values = frame[probability_columns].to_numpy(dtype=float)
        if not np.isfinite(values).all() or np.any((values < 0) | (values > 1)):
            raise MethodAdapterError("probability_values_invalid")
        if metadata.get("probability_semantics") == "categorical_simplex" and not np.allclose(
            values.sum(axis=1), 1.0, atol=1e-5
        ):
            raise MethodAdapterError("probability_rows_must_sum_to_one")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.suffix == ".parquet":
        frame.to_parquet(output_path, index=False)
    elif output_path.suffix in {".tsv", ".txt"}:
        frame.to_csv(output_path, sep="\t", index=False)
    else:
        raise MethodAdapterError("prediction_output_format_unsupported", output_path.suffix)
    metadata = {
        **metadata,
        "output_sha256": _sha256(output_path),
        "n_predictions": int(len(frame)),
        "partitions": sorted(frame["partition"].unique()),
    }
    metadata_path = Path(f"{output_path}.metadata.json")
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return {"output": output_path, "metadata": metadata_path, **metadata}


def _input_provenance(
    exchange_root: Path, asset_ids: Sequence[str], split_manifest_path: Path
) -> dict[str, Any]:
    split = BenchmarkSplitManifest.model_validate_json(
        split_manifest_path.read_text(encoding="utf-8")
    )
    return {
        "split_manifest_sha256": _sha256(split_manifest_path),
        "split_manifest_id": split.split_manifest_id,
        "benchmark_spec_ref": split.benchmark_spec_ref,
        "input_bundle_sha256": {
            asset_id: _sha256(exchange_root / asset_id / "bundle.json")
            for asset_id in sorted(set(asset_ids))
        },
    }


def _require_module(name: str) -> Any:
    if importlib.util.find_spec(name) is None:
        raise MethodAdapterError("python_package_missing", name)
    return importlib.import_module(name)


def _package_version(name: str) -> str | None:
    try:
        return version(name)
    except PackageNotFoundError:
        return None


def _version_prefix(value: str) -> tuple[int, int]:
    numbers = []
    for part in value.split(".")[:2]:
        digits = "".join(character for character in part if character.isdigit())
        numbers.append(int(digits or 0))
    return tuple((numbers + [0, 0])[:2])


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except MethodAdapterError as error:
        print(
            json.dumps(
                {"status": "failed", "reason_code": error.reason_code, "detail": str(error)}
            ),
            file=sys.stderr,
        )
        raise SystemExit(2) from None
