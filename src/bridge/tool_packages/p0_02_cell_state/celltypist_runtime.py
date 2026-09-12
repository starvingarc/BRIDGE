"""Portable CellTypist inference and empirically calibrated rejection.

The raw OvR energy is a development heuristic, not a log density or posterior.
Only fitting imports CellTypist. Inference uses its fitted scaler/linear weights
and is checked against the official predictor; model bundles never use pickle.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
from typing import Any, Literal, Sequence

import numpy as np
import pandas as pd
from pydantic import Field
from scipy import sparse
from scipy.special import expit, logsumexp
from sklearn.decomposition import PCA
from sklearn.neighbors import NearestNeighbors

from bridge.toolkit.contracts import FrozenModel
from .scientific_review import load_development_review, resolve_development_state

IMPLEMENTATION_VERSION = "1.0.0"
_ARRAY_NAMES = (
    "coefficients", "intercepts", "means", "scales",
    "geometry_mean", "geometry_components", "geometry_points",
)


def _encoded(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                      separators=(",", ":")).encode()


@dataclass(frozen=True)
class FittedCellTypist:
    features: tuple[str, ...]
    classes: tuple[str, ...]
    coefficients: np.ndarray
    intercepts: np.ndarray
    means: np.ndarray
    scales: np.ndarray
    with_mean: bool
    geometry_mean: np.ndarray
    geometry_components: np.ndarray
    geometry_points: np.ndarray
    training_provenance: dict[str, Any]

    def __post_init__(self):
        if (
            not self.features or len(self.features) > 50_000
            or len(set(self.features)) != len(self.features)
            or not all(isinstance(x, str) and x for x in self.features)
            or not 2 <= len(self.classes) <= 100
            or len(set(self.classes)) != len(self.classes)
            or not all(isinstance(x, str) and x for x in self.classes)
        ):
            raise ValueError("model_feature_or_class_contract_invalid")
        for name in _ARRAY_NAMES:
            values = np.array(getattr(self, name), dtype=np.float64, copy=True)
            if not np.isfinite(values).all():
                raise ValueError("model_array_nonfinite")
            values.setflags(write=False)
            object.__setattr__(self, name, values)
        width = len(self.features)
        expected_rows = {len(self.classes)} | ({1} if len(self.classes) == 2 else set())
        if (
            self.coefficients.ndim != 2 or self.coefficients.shape[0] not in expected_rows
            or self.coefficients.shape[1] != width
            or self.intercepts.shape != (self.coefficients.shape[0],)
            or self.means.shape != (width,) or self.scales.shape != (width,)
            or np.any(self.scales <= 0)
            or self.geometry_mean.shape != (width,)
            or self.geometry_components.ndim != 2
            or self.geometry_components.shape[1] != width
            or not 1 <= self.geometry_components.shape[0] <= 64
            or self.geometry_points.ndim != 2
            or not 1 <= len(self.geometry_points) <= 25_600
            or self.geometry_points.shape[1] != self.geometry_components.shape[0]
        ):
            raise ValueError("model_array_shape_invalid")
        # Copy metadata too: caller mutation cannot change the model's identity.
        object.__setattr__(self, "training_provenance", json.loads(_encoded(self.training_provenance)))

    @cached_property
    def fingerprint(self) -> str:
        digest = hashlib.sha256(_encoded({
            "implementation_version": IMPLEMENTATION_VERSION,
            "features": self.features, "classes": self.classes,
            "with_mean": self.with_mean,
            "training_provenance": self.training_provenance,
        }))
        for name in _ARRAY_NAMES:
            values = getattr(self, name).astype("<f8", copy=False)
            digest.update(_encoded([name, list(values.shape)]))
            digest.update(values.tobytes(order="C"))
        return digest.hexdigest()

    @cached_property
    def neighbors(self):
        return NearestNeighbors(
            n_neighbors=min(10, len(self.geometry_points)), algorithm="brute", n_jobs=1,
        ).fit(self.geometry_points)


@dataclass(frozen=True)
class ModelPrediction:
    model_sha256: str
    classes: tuple[str, ...]
    decision_scores: np.ndarray
    energy: np.ndarray
    knn_distance: np.ndarray
    feature_coverage: float
    missing_features: tuple[str, ...]

    @property
    def probabilities(self):
        # These are OvR sigmoid values; they do not form a categorical simplex.
        return expit(self.decision_scores)

    @property
    def predicted_labels(self):
        return np.asarray(self.classes)[np.argmax(self.decision_scores, axis=1)]

    @property
    def margins(self):
        top = np.partition(self.decision_scores, -2, axis=1)[:, -2:]
        return top[:, 1] - top[:, 0]


class OODCalibration(FrozenModel):
    object_version: Literal["1.0.0"] = "1.0.0"
    model_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    calibration_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    kind: Literal["empirical_ovr_rejection_not_posterior"] = "empirical_ovr_rejection_not_posterior"
    energy_temperature: Literal[1.0] = 1.0
    alpha: float = Field(gt=0, lt=1)
    energy_threshold: float = Field(allow_inf_nan=False)
    knn_threshold: float = Field(ge=0, allow_inf_nan=False)
    minimum_feature_coverage: float = Field(gt=0, le=1)
    n_calibration: int = Field(ge=1)
    n_unrepresented_labels: int = Field(ge=0)
    min_class_support: int = Field(ge=1)
    class_support: dict[str, int]
    class_margin_thresholds: dict[str, float]
    knn_role: Literal["sensitivity_not_independent_vote"] = "sensitivity_not_independent_vote"
    scientific_qualification: Literal["not_established"] = "not_established"


def _matrix_and_features(expression, genes: Sequence[str]):
    genes = tuple(str(gene) for gene in genes)
    values = sparse.csr_matrix(expression, dtype=np.float64)
    if (
        values.ndim != 2 or values.shape[1] != len(genes)
        or len(set(genes)) != len(genes) or not all(genes)
        or not np.isfinite(values.data).all() or np.any(values.data < 0)
    ):
        raise ValueError("normalized_expression_contract_invalid")
    return values, genes


def _scaled_chunk(model: FittedCellTypist, values, query_indices, model_indices):
    block = values[:, query_indices].toarray()
    if model.with_mean:
        block -= model.means[model_indices]
    block /= model.scales[model_indices]
    # Matches CellTypist 1.7.1: upper clip only, after fitted scaling.
    np.minimum(block, 10.0, out=block)
    return block


def predict_celltypist(
    model: FittedCellTypist, expression, genes: Sequence[str], *, chunk_size: int = 256,
) -> ModelPrediction:
    values, genes = _matrix_and_features(expression, genes)
    if not 1 <= chunk_size <= 4096:
        raise ValueError("prediction_chunk_size_invalid")
    query_lookup = {gene: index for index, gene in enumerate(genes)}
    model_indices = np.array([i for i, gene in enumerate(model.features) if gene in query_lookup], dtype=int)
    if not len(model_indices):
        raise ValueError("model_gene_overlap_unavailable")
    query_indices = np.array([query_lookup[model.features[i]] for i in model_indices], dtype=int)
    missing = tuple(gene for gene in model.features if gene not in query_lookup)
    decisions = np.empty((values.shape[0], len(model.classes)), dtype=np.float64)
    distances = np.empty(values.shape[0], dtype=np.float64)
    for start in range(0, values.shape[0], chunk_size):
        stop = min(start + chunk_size, values.shape[0])
        scaled = _scaled_chunk(model, values[start:stop], query_indices, model_indices)
        raw = scaled @ model.coefficients[:, model_indices].T + model.intercepts
        if raw.shape[1] == 1:
            raw = np.column_stack((-raw[:, 0], raw[:, 0]))
        decisions[start:stop] = raw
        # Unmeasured genes contribute the fitted mean (zero standardized value),
        # not measured-zero expression; the coverage limitation remains explicit.
        projected = (
            scaled @ model.geometry_components[:, model_indices].T
            - model.geometry_mean @ model.geometry_components.T
        )
        distances[start:stop] = model.neighbors.kneighbors(projected, return_distance=True)[0].mean(axis=1)
    return ModelPrediction(
        model.fingerprint, model.classes, decisions, -logsumexp(decisions, axis=1),
        distances, len(model_indices) / len(model.features), missing,
    )


def fit_celltypist(
    expression, genes: Sequence[str], labels: Sequence[str], *, seed: int,
    max_iter: int = 200, n_jobs: int = 1, reference_per_class: int = 256,
    n_components: int = 32, training_provenance: dict[str, Any],
) -> FittedCellTypist:
    import celltypist
    import sklearn

    if version("celltypist") != "1.7.1" or tuple(int(x) for x in sklearn.__version__.split(".")[:2]) >= (1, 8):
        raise ValueError("celltypist_training_environment_not_supported")
    values, genes = _matrix_and_features(expression, genes)
    labels = np.asarray(labels, dtype=str)
    if (
        labels.shape != (values.shape[0],) or len(set(labels)) < 2
        or any(not item.strip() for item in labels) or values.shape[0] < 3
        or not 1 <= n_jobs <= 8 or not 1 <= reference_per_class <= 256
        or not 1 <= n_components <= 64 or not 1 <= max_iter <= 2000
    ):
        raise ValueError("training_inputs_invalid")
    native = celltypist.train(
        X=values, labels=labels, genes=genes, check_expression=False,
        max_iter=max_iter, n_jobs=n_jobs, random_state=seed,
    )
    features = tuple(str(x) for x in native.features)
    lookup = {gene: i for i, gene in enumerate(genes)}
    indices = np.array([lookup[gene] for gene in features], dtype=int)
    rng = np.random.default_rng(seed)
    selected = np.sort(np.concatenate([
        rng.choice(np.flatnonzero(labels == label),
                   min(reference_per_class, np.count_nonzero(labels == label)), replace=False)
        for label in sorted(set(labels))
    ]))
    reference = values[selected][:, indices].toarray()
    if native.scaler.with_mean:
        reference -= native.scaler.mean_
    reference /= native.scaler.scale_
    np.minimum(reference, 10.0, out=reference)
    dimensions = min(n_components, reference.shape[1], reference.shape[0] - 1)
    projection = PCA(n_components=dimensions, svd_solver="randomized", random_state=seed)
    points = projection.fit_transform(reference)
    provenance = {
        **training_provenance, "seed": seed, "celltypist_version": version("celltypist"),
        "sklearn_version": sklearn.__version__, "max_iter": max_iter,
        "n_training_observations": len(labels), "geometry_reference_per_class": reference_per_class,
        "geometry_training_indices_sha256": hashlib.sha256(selected.astype("<i8").tobytes()).hexdigest(),
        "geometry": "training_only_standardized_expression_pca",
    }
    return FittedCellTypist(
        features=features, classes=tuple(str(x) for x in native.cell_types),
        coefficients=native.classifier.coef_, intercepts=native.classifier.intercept_,
        means=native.scaler.mean_, scales=native.scaler.scale_, with_mean=native.scaler.with_mean,
        geometry_mean=projection.mean_, geometry_components=projection.components_,
        geometry_points=points, training_provenance=provenance,
    )


def calibrate_rejection(
    predictions: ModelPrediction, true_labels: Sequence[str], observation_ids: Sequence[str], *,
    alpha: float = 0.05, min_class_support: int = 20, minimum_feature_coverage: float = 0.9,
) -> OODCalibration:
    labels = np.asarray(true_labels, dtype=str)
    identities = [str(x) for x in observation_ids]
    n = len(predictions.energy)
    if not n or len(identities) != n or len(set(identities)) != n or not all(identities):
        raise ValueError("calibration_observation_identity_invalid")
    if labels.shape != (n,) or any(not item.strip() for item in labels):
        raise ValueError("calibration_labels_invalid")
    if not 0 < alpha < 1 or min_class_support < 1 or not 0 < minimum_feature_coverage <= 1:
        raise ValueError("calibration_parameters_invalid")
    represented = np.isin(labels, predictions.classes)
    if not represented.any():
        raise ValueError("calibration_has_no_represented_classes")
    if not np.isfinite(predictions.energy).all() or not np.isfinite(predictions.knn_distance).all():
        raise ValueError("calibration_scores_nonfinite")
    thresholds, support = {}, {}
    for label in predictions.classes:
        correct = (labels == label) & (predictions.predicted_labels == label)
        support[label] = int(correct.sum())
        if support[label] >= min_class_support:
            thresholds[label] = float(np.quantile(predictions.margins[correct], alpha, method="lower"))
    calibration_digest = hashlib.sha256(_encoded({
        "model": predictions.model_sha256, "identities": identities,
        "labels": labels.tolist(), "alpha": alpha,
        "energy": predictions.energy.tolist(), "knn_distance": predictions.knn_distance.tolist(),
        "decisions": predictions.decision_scores.tolist(), "class_support": support,
        "minimum_feature_coverage": minimum_feature_coverage, "min_class_support": min_class_support,
    })).hexdigest()
    return OODCalibration(
        model_sha256=predictions.model_sha256, calibration_sha256=calibration_digest,
        alpha=alpha, energy_threshold=float(np.quantile(predictions.energy[represented], 1-alpha, method="higher")),
        knn_threshold=float(np.quantile(predictions.knn_distance[represented], 1-alpha, method="higher")),
        minimum_feature_coverage=minimum_feature_coverage,
        n_calibration=int(represented.sum()), n_unrepresented_labels=int((~represented).sum()),
        min_class_support=min_class_support, class_support=support, class_margin_thresholds=thresholds,
    )


def classify_with_rejection(
    predictions: ModelPrediction, calibration: OODCalibration, observation_ids: Sequence[str],
) -> pd.DataFrame:
    if predictions.model_sha256 != calibration.model_sha256:
        raise ValueError("calibration_model_mismatch")
    identities = [str(value) for value in observation_ids]
    if len(identities) != len(predictions.energy) or len(set(identities)) != len(identities) or not all(identities):
        raise ValueError("prediction_observation_identity_invalid")
    review = load_development_review()
    labels, margins = predictions.predicted_labels, predictions.margins
    rows = []
    for index, (identity, label) in enumerate(zip(identities, labels, strict=True)):
        assigned, state, reason, role = None, "unknown", "", "role_unresolved"
        if predictions.feature_coverage < calibration.minimum_feature_coverage:
            state, reason = "unavailable", "calibration_feature_coverage_mismatch"
        elif predictions.energy[index] > calibration.energy_threshold:
            reason = "energy_ood_rejected"
        elif label not in calibration.class_margin_thresholds:
            state, reason = "unavailable", "class_calibration_support_insufficient"
        elif margins[index] < calibration.class_margin_thresholds[label]:
            reason = "class_margin_below_calibration"
        else:
            resolved = resolve_development_state(review, label)
            assigned, state, reason, role = (
                resolved.state_id, resolved.assignment_state, resolved.reason_code, resolved.product_role,
            )
            if resolved.reason_code in {"state_not_reviewed", "state_identity_unavailable"}:
                state = "unavailable"
        row = {
            "observation_id": identity, "predicted_source_label": str(label),
            "assigned_state": assigned, "assignment_state": state, "unknown_reason": reason,
            "product_role": role, "energy": float(predictions.energy[index]),
            "decision_margin": float(margins[index]), "knn_distance": float(predictions.knn_distance[index]),
            "knn_sensitivity_rejected": bool(predictions.knn_distance[index] > calibration.knn_threshold),
            "feature_coverage": predictions.feature_coverage,
        }
        rows.append(row)
    return pd.DataFrame(rows)


def save_model_bundle(path: Path, model: FittedCellTypist, calibration: OODCalibration) -> str:
    path = Path(path)
    if model.fingerprint != calibration.model_sha256:
        raise ValueError("calibration_model_mismatch")
    path.mkdir(parents=False, exist_ok=False)
    arrays_path = path / "arrays.npz"
    np.savez_compressed(arrays_path, **{name: getattr(model, name) for name in _ARRAY_NAMES})
    manifest = {
        "object_version": "1.0.0", "implementation_version": IMPLEMENTATION_VERSION,
        "model_sha256": model.fingerprint, "features": model.features, "classes": model.classes,
        "with_mean": model.with_mean, "training_provenance": model.training_provenance,
        "arrays_sha256": hashlib.sha256(arrays_path.read_bytes()).hexdigest(),
        "calibration": calibration.model_dump(mode="json"),
    }
    raw = _encoded(manifest) + b"\n"
    (path / "manifest.json").write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def load_model_bundle(path: Path, *, expected_sha256: str) -> tuple[FittedCellTypist, OODCalibration]:
    path = Path(path)
    manifest_path, arrays_path = path / "manifest.json", path / "arrays.npz"
    if (
        path.is_symlink() or manifest_path.is_symlink() or arrays_path.is_symlink()
        or not manifest_path.is_file() or not arrays_path.is_file()
        or manifest_path.stat().st_size > 8 * 1024 * 1024
        or arrays_path.stat().st_size > 256 * 1024 * 1024
    ):
        raise ValueError("model_bundle_path_invalid")
    raw = manifest_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("model_bundle_checksum_mismatch")
    payload = json.loads(raw)
    if payload.get("object_version") != "1.0.0" or payload.get("implementation_version") != IMPLEMENTATION_VERSION:
        raise ValueError("model_bundle_version_unsupported")
    arrays_raw = arrays_path.read_bytes()
    if hashlib.sha256(arrays_raw).hexdigest() != payload["arrays_sha256"]:
        raise ValueError("model_arrays_checksum_mismatch")
    with np.load(arrays_path, allow_pickle=False) as arrays:
        if set(arrays.files) != set(_ARRAY_NAMES):
            raise ValueError("model_array_keys_invalid")
        model = FittedCellTypist(
            features=tuple(payload["features"]), classes=tuple(payload["classes"]),
            with_mean=payload["with_mean"], training_provenance=payload["training_provenance"],
            **{name: arrays[name] for name in _ARRAY_NAMES},
        )
    if model.fingerprint != payload["model_sha256"]:
        raise ValueError("model_fingerprint_mismatch")
    calibration = OODCalibration.model_validate(payload["calibration"])
    if calibration.model_sha256 != model.fingerprint:
        raise ValueError("calibration_model_mismatch")
    return model, calibration
