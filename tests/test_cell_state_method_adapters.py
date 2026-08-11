from __future__ import annotations

import hashlib
import json
from importlib.resources import files
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import h5py
from scipy import sparse

from bridge.tool_packages.p0_02_cell_state import method_adapter
from bridge.tool_packages.p0_02_cell_state.method_adapter import (
    MethodAdapterError,
    adapter_metadata,
    build_parser,
    load_adapter_context,
    run_celltypist,
    run_scanvi,
)
from bridge.toolkit.contracts import BenchmarkSplitManifest, BenchmarkSplitRecord


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_matrix(path: Path, matrix: sparse.csr_matrix) -> None:
    matrix = sparse.csr_matrix(matrix)
    with h5py.File(path, "w") as handle:
        group = handle.create_group("matrix")
        group.attrs["format"] = "csr"
        group.create_dataset("shape", data=np.asarray(matrix.shape, dtype=np.int64))
        group.create_dataset("data", data=matrix.data)
        group.create_dataset("indices", data=matrix.indices)
        group.create_dataset("indptr", data=matrix.indptr)


def _exchange_bundle(
    tmp_path: Path,
    *,
    raw_counts: bool = False,
    asset_id: str = "CHEN-vMB-scRNA",
    data_role: str = "labeled_reference",
) -> tuple[Path, str]:
    root = tmp_path / "exchange" / asset_id
    root.mkdir(parents=True)
    counts = sparse.csr_matrix(
        np.asarray(
            [
                [10, 1, 0],
                [9, 1, 0],
                [0, 1, 10],
                [0, 1, 9],
            ]
            * 3,
            dtype=np.int64,
        )
    )
    totals = np.asarray(counts.sum(axis=1)).ravel()
    normalized = sparse.diags(10_000 / totals) @ counts
    normalized = normalized.astype(np.float32).tocsr()
    normalized.data = np.log1p(normalized.data)
    matrix = counts if raw_counts else normalized
    _write_matrix(root / "matrix.h5", matrix)
    (root / "features.tsv").write_text("TH\nFOXA2\nAQP4\n", encoding="utf-8")
    observations = pd.DataFrame(
        {
            "observation_id": [f"cell-{index:02d}" for index in range(12)],
            "sample_id": np.repeat(["donor-1", "donor-2", "donor-3"], 4),
            "true_label": ["L1:Neuron_DA", "L1:Neuron_DA", "L1:Astrocyte", "L1:Astrocyte"]
            * 3,
        }
    )
    observations.to_csv(root / "observations.tsv", sep="\t", index=False)
    observations.to_parquet(root / "observations.parquet", index=False)
    artifacts = {
        name: _sha256(root / name)
        for name in ("matrix.h5", "features.tsv", "observations.tsv", "observations.parquet")
    }
    manifest: dict[str, object] = {
        "bundle_version": "0.2.0",
        "asset_id": asset_id,
        "source_family_id": "CHEN-VMB",
        "assay": "scRNA-seq",
        "data_role": data_role,
        "label_level": "L1",
        "label_universe": ["L1:Astrocyte", "L1:Neuron_DA"],
        "matrix_shape": [12, 3],
        "matrix_semantics": "raw_counts" if raw_counts else "normalized_expression",
        "artifacts": artifacts,
    }
    (root / "bundle.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return tmp_path / "exchange", asset_id


def _split_manifest(tmp_path: Path, asset_id: str) -> Path:
    records = []
    samples = ["donor-1", "donor-2", "donor-3"]
    for index, test_sample in enumerate(samples):
        calibration_sample = samples[(index + 1) % len(samples)]
        for sample in samples:
            partition = (
                "test"
                if sample == test_sample
                else "calibration"
                if sample == calibration_sample
                else "train"
            )
            records.append(
                BenchmarkSplitRecord(
                    asset_id=asset_id,
                    source_family_id="CHEN-VMB",
                    sample_id=sample,
                    partition=partition,
                    data_role="labeled_reference",
                    fold_id=f"fold-{index + 1:02d}",
                    n_observations=4,
                )
            )
    manifest = BenchmarkSplitManifest(
        split_manifest_id="CELLSTATE-SPLIT-pilot-fixture",
        benchmark_spec_ref="CELLSTATE-BENCHMARK-scRNA-pilot-v0.1",
        phase="pilot",
        random_seed=7,
        input_catalog_sha256="a" * 64,
        records=records,
    )
    path = tmp_path / "split.json"
    path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    return path


def test_cli_parses_celltypist_and_scanvi_presets(tmp_path: Path) -> None:
    parser = build_parser()
    common = [
        "--exchange-root",
        str(tmp_path),
        "--asset-id",
        "asset",
        "--split-manifest",
        str(tmp_path / "split.json"),
        "--output",
        str(tmp_path / "predictions.tsv"),
    ]

    celltypist = parser.parse_args(
        ["celltypist", *common, "--max-iter", "10", "--query-asset", "OOD-1"]
    )
    assert celltypist.max_iter == 10
    assert celltypist.query_asset == ["OOD-1"]
    scanvi = parser.parse_args(["scanvi", *common, "--preset", "full"])
    assert scanvi.preset == "full"
    assert scanvi.accelerator == "auto"


def test_adapter_context_uses_sample_level_folds(tmp_path: Path) -> None:
    root, asset_id = _exchange_bundle(tmp_path)
    bundle, folds = load_adapter_context(root, asset_id, _split_manifest(tmp_path, asset_id))

    assert bundle.matrix.shape == (12, 3)
    assert set(folds) == {"fold-01", "fold-02", "fold-03"}
    assert all(set(partitions) == {"train", "calibration", "test"} for partitions in folds.values())
    for partitions in folds.values():
        assert all(
            partitions[bundle.observations["sample_id"].eq(sample)].nunique() == 1
            for sample in bundle.observations["sample_id"].unique()
        )


def test_malformed_split_leakage_fails_before_optional_packages(tmp_path: Path) -> None:
    root, asset_id = _exchange_bundle(tmp_path)
    path = _split_manifest(tmp_path, asset_id)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["records"].append(
        {
            **payload["records"][0],
            "partition": "train" if payload["records"][0]["partition"] != "train" else "test",
        }
    )
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(MethodAdapterError, match="split_manifest_invalid"):
        load_adapter_context(root, asset_id, path)


def test_celltypist_missing_package_fails_loudly(tmp_path: Path, monkeypatch) -> None:
    root, asset_id = _exchange_bundle(tmp_path)
    split = _split_manifest(tmp_path, asset_id)
    monkeypatch.setattr(method_adapter.importlib.util, "find_spec", lambda name: None)

    with pytest.raises(MethodAdapterError, match="python_package_missing: celltypist"):
        run_celltypist(
            exchange_root=root,
            asset_id=asset_id,
            split_manifest_path=split,
            output_path=tmp_path / "predictions.tsv",
        )


def test_scanvi_refuses_a_normalized_only_bundle_before_import(tmp_path: Path, monkeypatch) -> None:
    root, asset_id = _exchange_bundle(tmp_path)
    split = _split_manifest(tmp_path, asset_id)
    monkeypatch.setattr(
        method_adapter,
        "_require_module",
        lambda name: pytest.fail(f"optional package import attempted: {name}"),
    )

    with pytest.raises(MethodAdapterError, match="scanvi_raw_counts_required"):
        run_scanvi(
            exchange_root=root,
            asset_id=asset_id,
            split_manifest_path=split,
            output_path=tmp_path / "predictions.tsv",
        )


def test_query_bundle_requires_registered_ood_or_behavior_role(tmp_path: Path) -> None:
    root, asset_id = _exchange_bundle(tmp_path)
    _exchange_bundle(
        tmp_path,
        asset_id="GSE190729",
        data_role="development_ood",
    )
    split = BenchmarkSplitManifest.model_validate_json(
        _split_manifest(tmp_path, asset_id).read_text(encoding="utf-8")
    ).model_copy(
        update={
            "records": [
                *BenchmarkSplitManifest.model_validate_json(
                    _split_manifest(tmp_path, asset_id).read_text(encoding="utf-8")
                ).records,
                BenchmarkSplitRecord(
                    asset_id="GSE190729",
                    source_family_id="CHEN-VMB",
                    sample_id="donor-1",
                    partition="development_ood",
                    data_role="development_ood",
                    n_observations=12,
                ),
            ]
        }
    )

    queries = method_adapter._load_query_bundles(
        root, ["GSE190729"], expected_level="L1", split=split
    )

    assert [bundle.asset_id for bundle in queries] == ["GSE190729"]


def test_query_bundle_must_be_registered_in_split(tmp_path: Path) -> None:
    root, asset_id = _exchange_bundle(tmp_path)
    _exchange_bundle(tmp_path, asset_id="GSE190729", data_role="development_ood")
    split = BenchmarkSplitManifest.model_validate_json(
        _split_manifest(tmp_path, asset_id).read_text(encoding="utf-8")
    )

    with pytest.raises(MethodAdapterError, match="query_asset_not_in_split_manifest"):
        method_adapter._load_query_bundles(
            root, ["GSE190729"], expected_level="L1", split=split
        )


def test_scanvi_external_query_is_explicitly_unavailable(tmp_path: Path) -> None:
    with pytest.raises(MethodAdapterError, match="scanvi_external_query_adapter_not_implemented"):
        run_scanvi(
            exchange_root=tmp_path,
            asset_id="CHEN-vMB-scRNA",
            split_manifest_path=tmp_path / "split.json",
            output_path=tmp_path / "predictions.tsv",
            query_asset_ids=["GSE190729"],
        )


def test_scanvi_trainer_disables_cudnn_benchmark() -> None:
    options = method_adapter._scanvi_trainer_kwargs("gpu")

    assert options["deterministic"] is True
    assert options["benchmark"] is False
    assert options["accelerator"] == "gpu"


def test_prediction_rows_preserve_registered_context_columns() -> None:
    observations = pd.DataFrame(
        {
            "observation_id": ["cell-1", "cell-2"],
            "sample_id": ["sample-1", "sample-1"],
            "true_label": [None, None],
            "timepoint_or_stage": ["D16", "D16"],
        }
    )
    probabilities = pd.DataFrame(
        {"L1:A": [0.8, 0.2], "L1:B": [0.2, 0.8]},
        index=observations["observation_id"],
    )

    frame = method_adapter._prediction_rows(
        "fold-01",
        observations,
        pd.Series(["behavior_only", "behavior_only"]),
        probabilities,
        simplex=True,
        asset_id="PRODUCT",
        source_family_id="PRODUCT",
        label_level="L1",
    )

    assert frame["timepoint_or_stage"].tolist() == ["D16", "D16"]


def test_probability_alignment_preserves_a_fixed_reference_label_universe() -> None:
    probabilities = pd.DataFrame({"L1:A": [0.8], "L1:B": [0.2]})

    aligned, missing = method_adapter._align_probability_columns(
        probabilities, ["L1:A", "L1:B", "L1:C"]
    )

    assert aligned.columns.tolist() == ["L1:A", "L1:B", "L1:C"]
    assert aligned.iloc[0].tolist() == [0.8, 0.2, 0.0]
    assert missing == ["L1:C"]
    assert not aligned.isna().any().any()


def test_prediction_writer_rejects_fold_specific_probability_columns(tmp_path: Path) -> None:
    base = pd.DataFrame(
        {
            "fold_id": ["fold-01"],
            "partition": ["test"],
            "observation_id": ["cell-1"],
            "prob__L1:A": [1.0],
        }
    )
    second = base.assign(fold_id="fold-02", observation_id="cell-2").rename(
        columns={"prob__L1:A": "prob__L1:B"}
    )

    with pytest.raises(MethodAdapterError, match="probability_values_invalid"):
        method_adapter._write_predictions(
            tmp_path / "predictions.tsv",
            [base, second],
            {"probability_semantics": "categorical_simplex"},
        )


def test_raw_count_bundle_is_checksum_and_integer_validated(tmp_path: Path) -> None:
    root, asset_id = _exchange_bundle(tmp_path, raw_counts=True)
    bundle, _ = load_adapter_context(
        root,
        asset_id,
        _split_manifest(tmp_path, asset_id),
        require_raw_counts=True,
    )

    assert bundle.raw_counts is not None
    assert bundle.raw_counts.shape == bundle.matrix.shape
    assert np.allclose(bundle.raw_counts.data, np.rint(bundle.raw_counts.data))
    assert not np.allclose(bundle.matrix.data, bundle.raw_counts.data)


def test_adapter_input_provenance_binds_split_and_bundles(tmp_path: Path) -> None:
    root, asset_id = _exchange_bundle(tmp_path)
    split = _split_manifest(tmp_path, asset_id)

    provenance = method_adapter._input_provenance(root, [asset_id], split)

    assert provenance["split_manifest_sha256"] == _sha256(split)
    assert provenance["input_bundle_sha256"] == {
        asset_id: _sha256(root / asset_id / "bundle.json")
    }


def test_celltypist_probability_semantics_are_not_conformal_ready() -> None:
    metadata = adapter_metadata("celltypist", seed=11)

    assert metadata["probability_semantics"] == "one_vs_rest_sigmoid"
    assert metadata["row_sum_constraint"] == "none"
    assert metadata["conformal_eligible"] is False
    assert metadata["seed"] == 11


def test_prediction_contract_keeps_sample_source_and_label_context() -> None:
    observations = pd.DataFrame(
        {
            "observation_id": ["cell-1", "cell-2"],
            "sample_id": ["donor-1", "donor-2"],
            "true_label": ["L1:Neuron_DA", "L1:Astrocyte"],
        }
    )
    probabilities = pd.DataFrame(
        {
            "L1:Astrocyte": [0.1, 0.9],
            "L1:Neuron_DA": [0.9, 0.1],
        }
    )

    frame = method_adapter._prediction_rows(
        "fold-01",
        observations,
        pd.Series(["test", "test"]),
        probabilities,
        simplex=True,
        asset_id="CHEN-vMB-scRNA",
        source_family_id="CHEN-VMB",
        label_level="L1",
    )

    assert frame[["sample_id", "asset_id", "source_family_id", "label_level"]].to_dict(
        orient="list"
    ) == {
        "sample_id": ["donor-1", "donor-2"],
        "asset_id": ["CHEN-vMB-scRNA", "CHEN-vMB-scRNA"],
        "source_family_id": ["CHEN-VMB", "CHEN-VMB"],
        "label_level": ["L1", "L1"],
    }


def test_celltypist_171_rejects_sklearn_18(tmp_path: Path, monkeypatch) -> None:
    root, asset_id = _exchange_bundle(tmp_path)
    split = _split_manifest(tmp_path, asset_id)
    modules = {
        "celltypist": object(),
        "anndata": object(),
        "sklearn": type("Sklearn", (), {"__version__": "1.8.0"})(),
    }
    monkeypatch.setattr(method_adapter, "_require_module", modules.__getitem__)
    monkeypatch.setattr(
        method_adapter,
        "_package_version",
        lambda name: "1.7.1" if name == "celltypist" else None,
    )

    with pytest.raises(MethodAdapterError, match="celltypist_dependency_incompatible"):
        run_celltypist(
            exchange_root=root,
            asset_id=asset_id,
            split_manifest_path=split,
            output_path=tmp_path / "predictions.tsv",
        )


def test_r_adapter_is_packaged_and_keeps_scconform_as_a_calibration_layer() -> None:
    script = files("bridge.tool_packages.p0_02_cell_state").joinpath("r_adapter.R")
    text = script.read_text(encoding="utf-8")

    assert "scConform::getPredictionSets" in text
    assert 'independent_evidence_vote = FALSE' in text
    assert 'probability_semantics_not_conformal_ready' in text
    assert 'locked_or_sealed_split_forbidden' in text
    assert 'rhdf5::h5read' in text
    assert 'fold_missing_training_labels' in text
    assert 'bundle$manifest$label_universe' in text
    assert 'list(sha256(file.path(exchange_root, asset_id, "bundle.json")))' in text
    assert 'sort(unique(bundle$observations$true_label))' not in text
    assert 'query_expression_used_as_unlabeled_during_training' in text
