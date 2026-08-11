from __future__ import annotations

import base64
import hashlib
import json
import time
from pathlib import Path

import anndata as ad
import numpy as np
import pandas as pd
import pytest
import yaml
from pydantic import ValidationError
from scipy import sparse
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from bridge.tool_packages.p0_02_cell_state import freeze as cell_state_freeze
from bridge.tool_packages.p0_02_cell_state.freeze import (
    BenchmarkError,
    load_biological_review_draft,
    load_pilot_benchmark_spec,
    load_release_manifest_draft,
    object_signing_hash,
    prepare_benchmark_split,
    run_pilot_benchmark,
    resolve_release_bundle,
    summarize_benchmark,
    validate_release_bundle,
    validate_probability_output,
)
from bridge.tool_packages.p0_02_cell_state.benchmark_cli import main as benchmark_main
from bridge.toolkit.contracts import (
    BiologicalReviewRecord,
    CellStateBenchmarkSpec,
    CellStateReleaseManifest,
    FreezeGateSpec,
    ReviewerSignature,
)


def _signature(role: str, reviewer: str) -> ReviewerSignature:
    return ReviewerSignature.model_validate(_signed(role, reviewer, "a" * 64))


def _signed(role: str, reviewer: str, object_hash: str) -> dict:
    key = _reviewer_key(reviewer)
    return {
        "reviewer_id": reviewer,
        "reviewer_role": role,
        "key_id": f"{reviewer}-key-v1",
        "algorithm": "ed25519",
        "signed_at": "2026-08-11T00:00:00Z",
        "object_sha256": object_hash,
        "signature_base64": base64.b64encode(
            key.sign(cell_state_freeze.SIGNATURE_DOMAIN + object_hash.encode())
        ).decode(),
    }


def _reviewer_key(reviewer: str) -> Ed25519PrivateKey:
    seed = hashlib.sha256(f"BRIDGE test key:{reviewer}".encode()).digest()
    return Ed25519PrivateKey.from_private_bytes(seed)


def _write_reviewer_registry(tmp_path: Path) -> Path:
    reviewers = [
        ("bridge-reviewer", "bridge_scientific_lead"),
        ("chen-reviewer", "chen_team_reviewer"),
    ]
    payload = {
        "reviewers": [
            {
                "reviewer_id": reviewer,
                "reviewer_role": role,
                "key_id": f"{reviewer}-key-v1",
                "public_key_base64": base64.b64encode(
                    _reviewer_key(reviewer)
                    .public_key()
                    .public_bytes(Encoding.Raw, PublicFormat.Raw)
                ).decode(),
            }
            for reviewer, role in reviewers
        ]
    }
    path = tmp_path / "trusted-reviewers.json"
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    return path


def _lineage(
    source_family_id: str,
    *,
    derived_from: list[str] | None = None,
    access_policy: str = "test_fixture",
) -> dict:
    return {
        "source_accession": source_family_id,
        "root_source_family_id": source_family_id,
        "derived_from": derived_from or [],
        "leakage_group": source_family_id,
        "access_policy": access_policy,
    }


def _gate_bindings(spec: CellStateBenchmarkSpec, catalog_sha256: str) -> dict:
    return {
        "benchmark_spec_sha256": cell_state_freeze._model_sha256(spec),
        "asset_catalog_sha256": catalog_sha256,
        "reference_snapshot_ref": spec.reference_snapshot_ref,
        "reference_snapshot_sha256": "c" * 64,
        "environment_spec_refs": spec.environment_spec_refs,
        "environment_spec_sha256": {
            environment: "d" * 64 for environment in spec.environment_spec_refs
        },
        "environment_health_record_sha256": "e" * 64,
        "adapter_contract_sha256": cell_state_freeze._adapter_contract_sha256(spec),
        "pilot_evidence_sha256": "f" * 64,
    }


def _scconform_fixture(frame: pd.DataFrame, alpha: float = 0.1) -> pd.DataFrame:
    probability_columns = sorted(column for column in frame if column.startswith("prob__"))
    labels = [column.removeprefix("prob__") for column in probability_columns]
    output = []
    for fold_id in sorted(frame["fold_id"].unique()):
        current = frame["fold_id"].eq(fold_id)
        calibration = frame.loc[current & frame["partition"].eq("calibration")]
        test = frame.loc[current & frame["partition"].eq("test")].copy()
        label_index = {label: index for index, label in enumerate(labels)}
        indices = [label_index[label] for label in calibration["true_label"]]
        probabilities = calibration[probability_columns].to_numpy(dtype=float)
        conformity = 1.0 - probabilities[np.arange(len(calibration)), indices]
        quantile = np.ceil((len(calibration) + 1) * (1 - alpha)) / len(calibration)
        threshold = 1.0 - np.quantile(conformity, quantile, method="linear")
        sets = [
            [
                label
                for label, probability in zip(labels, row, strict=True)
                if probability >= threshold
            ]
            for row in test[probability_columns].to_numpy(dtype=float)
        ]
        test["prediction_set"] = [json.dumps(values) for values in sets]
        test["assignment_state"] = [
            "conformal_empty"
            if not values
            else "conformal_singleton"
            if len(values) == 1
            else "conformal_set"
            for values in sets
        ]
        output.append(test)
    return pd.concat(output, ignore_index=True)


def _asset_catalog(tmp_path: Path) -> Path:
    payload = {
        "assets": [
            {
                "asset_id": "CHEN-vMB-scRNA",
                "source_family_id": "CHEN-VMB",
                **_lineage("CHEN-VMB"),
                "assay": "scRNA-seq",
                "data_role": "labeled_reference",
                "path": str(tmp_path / "chen.tsv"),
                "sample_column": "sample_id",
                "label_column": "cell_type",
            },
            {
                "asset_id": "GSE190729",
                "source_family_id": "GSE190729",
                **_lineage("GSE190729"),
                "assay": "scRNA-seq",
                "data_role": "development_ood",
                "path": str(tmp_path / "ood.tsv"),
                "sample_column": "sample_id",
            },
            {
                "asset_id": "LAMANNO-2016",
                "source_family_id": "LAMANNO-2016",
                **_lineage("LAMANNO-2016"),
                "assay": "scRNA-seq",
                "data_role": "locked_source_holdout",
                "path": str(tmp_path / "must-not-be-opened.tsv"),
                "sample_column": "sample_id",
                "label_column": "cell_type",
            },
        ]
    }
    (tmp_path / "chen.tsv").write_text(
        "observation_id\tsample_id\tcell_type\n"
        "c1\tdonor-1\tNeuron_DA\n"
        "c2\tdonor-2\tNeuron_DA\n"
        "c3\tdonor-3\tAstrocyte\n"
        "c4\tdonor-4\tAstrocyte\n",
        encoding="utf-8",
    )
    (tmp_path / "ood.tsv").write_text(
        "observation_id\tsample_id\nq1\tood-1\n",
        encoding="utf-8",
    )
    for asset in payload["assets"]:
        source = Path(asset["path"])
        if source.is_file():
            asset["checksum"] = _sha256(source)
    path = tmp_path / "catalog.yaml"
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return path


def _write_expression_fixture(tmp_path: Path) -> tuple[Path, Path]:
    genes = ["TH", "DDC", "SLC6A3", "AQP4", "ALDH1L1", "GFAP", "G001", "G002"]
    rows: list[list[int]] = []
    samples: list[str] = []
    labels: list[str] = []
    for donor in ["donor-1", "donor-2", "donor-3", "donor-4"]:
        rows.extend(
            [
                [30, 25, 20, 1, 1, 1, 4, 3],
                [28, 24, 18, 1, 1, 1, 3, 4],
                [1, 1, 1, 30, 25, 20, 4, 3],
                [1, 1, 1, 28, 24, 18, 3, 4],
            ]
        )
        samples.extend([donor] * 4)
        labels.extend(["Neuron_DA", "Neuron_DA", "Astrocyte", "Astrocyte"])
    path = tmp_path / "chen.h5ad"
    ad.AnnData(
        sparse.csr_matrix(np.asarray(rows)),
        obs=pd.DataFrame(
            {"sample_id": samples, "cell_type": labels},
            index=[f"cell-{index:02d}" for index in range(len(rows))],
        ),
        var=pd.DataFrame(index=genes),
    ).write_h5ad(path)
    catalog = {
        "assets": [
            {
                "asset_id": "CHEN-vMB-scRNA",
                "source_family_id": "CHEN-VMB",
                **_lineage("CHEN-VMB"),
                "assay": "scRNA-seq",
                "data_role": "labeled_reference",
                "path": str(path),
                "sample_column": "sample_id",
                "label_column": "cell_type",
                "label_level": "L1",
                "matrix_location": "X",
                "matrix_semantics": "raw_counts",
                "checksum": _sha256(path),
            }
        ]
    }
    catalog_path = tmp_path / "expression-catalog.yaml"
    catalog_path.write_text(yaml.safe_dump(catalog, sort_keys=False), encoding="utf-8")
    return path, catalog_path


def _adapter_provenance(run_dir: Path, asset_ids: list[str]) -> dict:
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    split = manifest["split_manifest"]
    return {
        "split_manifest_sha256": manifest["split_manifest_sha256"],
        "split_manifest_id": split["split_manifest_id"],
        "benchmark_spec_ref": split["benchmark_spec_ref"],
        "input_bundle_sha256": {
            asset_id: manifest["native_artifact_hashes"][
                f"exchange/{asset_id}/bundle.json"
            ]
            for asset_id in asset_ids
        },
    }


def _scanvi_parameters() -> dict:
    return {
        "seed": 20260811,
        "preset": "small",
        "scvi_epochs": 20,
        "scanvi_epochs": 10,
    }


def test_biological_review_draft_covers_all_l1_and_priority_l2() -> None:
    review = load_biological_review_draft()

    levels = [card.level for card in review.state_reviews]
    priority_l2 = {
        "L2:RG_mFP",
        "L2:RG_mBMP",
        "L2:RG_mBIP",
        "L2:Nb_mFP",
        "L2:Nb_mBMP",
        "L2:Nb_mBIP",
        "L2:Nb_mAP",
    }
    assert levels.count("L1") == 18
    assert {card.state_id for card in review.state_reviews if card.level == "L2"} == priority_l2
    assert review.status == "pending"
    assert review.product_definition_review_status == "pending"
    assert review.state_role_map_review_status == "pending"
    assert review.conflict_exclusions == {
        "historical_rg_to_pericyte": 25,
        "historical_broad_refined_disagreement_excluding_rg_to_pericyte": 303,
    }
    assert sum(review.conflict_exclusions.values()) == 328
    assert review.alias_decisions == {"Neuron_Chat": "Neuron_ChAT"}
    assert all(card.allowed_interpretations for card in review.state_reviews)
    assert all(card.forbidden_interpretations for card in review.state_reviews)
    assert {card.count_source_id for card in review.state_reviews} == {"REF-CHEN-VMB-SC-v1"}


def test_biological_review_cannot_be_approved_without_both_review_roles() -> None:
    draft = load_biological_review_draft()
    payload = draft.model_dump(mode="json")
    payload.update(
                {
            "status": "approved",
            "product_definition_review_status": "approved",
            "state_role_map_review_status": "approved",
            "signatures": [_signature("bridge_scientific_lead", "reviewer-a").model_dump(mode="json")],
        }
    )
    payload["state_reviews"] = [
        {
            **card,
            "positive_markers": card["positive_markers"] or ["FIXTURE_POS"],
            "negative_markers": card["negative_markers"] or ["FIXTURE_NEG"],
            "review_blockers": [],
            "review_status": "approved",
        }
        for card in payload["state_reviews"]
    ]

    with pytest.raises(ValidationError, match="chen_team_reviewer"):
        BiologicalReviewRecord.model_validate(payload)


def test_biological_review_rejects_duplicate_reviewer_signatures() -> None:
    draft = load_biological_review_draft()
    payload = draft.model_dump(mode="json")
    payload.update(
        {
            "status": "approved",
            "product_definition_review_status": "approved",
            "state_role_map_review_status": "approved",
            "signatures": [
                _signature("bridge_scientific_lead", "reviewer-a").model_dump(mode="json"),
                _signature("chen_team_reviewer", "reviewer-b").model_dump(mode="json"),
                _signature("chen_team_reviewer", "reviewer-c").model_dump(mode="json"),
            ],
        }
    )
    payload["state_reviews"] = [
        {
            **card,
            "positive_markers": card["positive_markers"] or ["FIXTURE_POS"],
            "negative_markers": card["negative_markers"] or ["FIXTURE_NEG"],
            "review_blockers": [],
            "review_status": "approved",
        }
        for card in payload["state_reviews"]
    ]

    with pytest.raises(ValidationError, match="exactly two signatures"):
        BiologicalReviewRecord.model_validate(payload)


def test_biological_review_rejects_one_person_in_both_roles() -> None:
    draft = load_biological_review_draft()
    payload = draft.model_dump(mode="json")
    payload.update(
        {
            "status": "approved",
            "product_definition_review_status": "approved",
            "state_role_map_review_status": "approved",
            "signatures": [
                _signature("bridge_scientific_lead", "same-reviewer").model_dump(mode="json"),
                _signature("chen_team_reviewer", "same-reviewer").model_dump(mode="json"),
            ],
        }
    )
    payload["state_reviews"] = [
        {
            **card,
            "positive_markers": card["positive_markers"] or ["FIXTURE_POS"],
            "negative_markers": card["negative_markers"] or ["FIXTURE_NEG"],
            "review_blockers": [],
            "review_status": "approved",
        }
        for card in payload["state_reviews"]
    ]

    with pytest.raises(ValidationError, match="distinct reviewers"):
        BiologicalReviewRecord.model_validate(payload)


def test_pilot_prepare_is_donor_aware_and_does_not_open_locked_assets(tmp_path: Path) -> None:
    spec = load_pilot_benchmark_spec().model_copy(
        update={
            "development_asset_ids": ["CHEN-vMB-scRNA"],
            "development_ood_asset_ids": ["GSE190729"],
            "behavior_only_asset_ids": [],
        }
    )
    manifest = prepare_benchmark_split(spec, _asset_catalog(tmp_path))

    assert manifest.phase == "pilot"
    assert manifest.locked_assets_opened is False
    assert manifest.sealed_assets_opened is False
    assert "LAMANNO-2016" not in {record.asset_id for record in manifest.records}
    assert {record.partition for record in manifest.records} >= {
        "train",
        "calibration",
        "test",
        "development_ood",
    }
    for fold_id in {record.fold_id for record in manifest.records if record.fold_id}:
        rows = [record for record in manifest.records if record.fold_id == fold_id]
        by_group: dict[tuple[str, str], set[str]] = {}
        for row in rows:
            by_group.setdefault((row.source_family_id, row.sample_id), set()).add(row.partition)
        assert all(len(partitions) == 1 for partitions in by_group.values())


def test_benchmark_spec_rejects_asset_role_overlap() -> None:
    payload = load_pilot_benchmark_spec().model_dump(mode="json")
    payload["sealed_asset_ids"].append(payload["development_ood_asset_ids"][0])

    with pytest.raises(ValidationError, match="asset role overlap"):
        CellStateBenchmarkSpec.model_validate(payload)


def test_benchmark_spec_rejects_invalid_locked_method_exclusion() -> None:
    payload = load_pilot_benchmark_spec().model_dump(mode="json")
    payload["locked_method_exclusions"] = {
        "NOT-A-LOCKED-ASSET": ["source_specific_correlation"]
    }

    with pytest.raises(ValidationError, match="non-locked assets"):
        CellStateBenchmarkSpec.model_validate(payload)


def test_split_rejects_lineage_shared_across_benchmark_roles(tmp_path: Path) -> None:
    path, catalog_path = _write_expression_fixture(tmp_path)
    catalog = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
    catalog["assets"].append(
        {
            "asset_id": "GSE190729",
            "source_family_id": "GSE190729",
            "source_accession": "GSE190729",
            "root_source_family_id": "CHEN-VMB",
            "derived_from": ["CHEN-vMB-scRNA"],
            "leakage_group": "CHEN-VMB",
            "access_policy": "public",
            "assay": "scRNA-seq",
            "data_role": "development_ood",
            "path": str(path),
            "sample_column": "sample_id",
            "label_level": "L1",
            "matrix_location": "X",
            "matrix_semantics": "raw_counts",
            "checksum": _sha256(path),
        }
    )
    catalog_path.write_text(yaml.safe_dump(catalog, sort_keys=False), encoding="utf-8")
    spec = load_pilot_benchmark_spec().model_copy(
        update={
            "development_asset_ids": ["CHEN-vMB-scRNA"],
            "development_ood_asset_ids": ["GSE190729"],
            "behavior_only_asset_ids": [],
        }
    )

    with pytest.raises(BenchmarkError) as error:
        prepare_benchmark_split(spec, catalog_path)
    assert error.value.reason_code == "benchmark_role_lineage_overlap"


def test_split_rejects_shared_source_family_across_roles(tmp_path: Path) -> None:
    path, catalog_path = _write_expression_fixture(tmp_path)
    catalog = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
    catalog["assets"].append(
        {
            "asset_id": "OOD-SHARED-FAMILY",
            "source_family_id": "CHEN-VMB",
            **_lineage("OOD-INDEPENDENT"),
            "access_policy": "public",
            "assay": "scRNA-seq",
            "data_role": "development_ood",
            "path": str(path),
            "sample_column": "sample_id",
            "label_level": "L1",
            "matrix_location": "X",
            "matrix_semantics": "raw_counts",
            "checksum": _sha256(path),
        }
    )
    catalog_path.write_text(yaml.safe_dump(catalog, sort_keys=False), encoding="utf-8")
    spec = load_pilot_benchmark_spec().model_copy(
        update={
            "development_asset_ids": ["CHEN-vMB-scRNA"],
            "development_ood_asset_ids": ["OOD-SHARED-FAMILY"],
            "behavior_only_asset_ids": [],
        }
    )

    with pytest.raises(BenchmarkError) as error:
        prepare_benchmark_split(spec, catalog_path)
    assert error.value.reason_code == "benchmark_role_lineage_overlap"


def test_split_rejects_transitive_lineage_overlap_across_roles(tmp_path: Path) -> None:
    path, catalog_path = _write_expression_fixture(tmp_path)
    catalog = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
    base = {
        "access_policy": "public",
        "assay": "scRNA-seq",
        "path": str(path),
        "sample_column": "sample_id",
        "label_level": "L1",
        "matrix_location": "X",
        "matrix_semantics": "raw_counts",
        "checksum": _sha256(path),
    }
    catalog["assets"].extend(
        [
            {
                **base,
                "asset_id": "INTERMEDIATE-DERIVATIVE",
                "source_family_id": "INTERMEDIATE-FAMILY",
                **_lineage(
                    "INTERMEDIATE-FAMILY", derived_from=["CHEN-vMB-scRNA"]
                ),
                "data_role": "derived_reference",
            },
            {
                **base,
                "asset_id": "TRANSITIVE-OOD",
                "source_family_id": "TRANSITIVE-OOD",
                **_lineage(
                    "TRANSITIVE-OOD", derived_from=["INTERMEDIATE-DERIVATIVE"]
                ),
                "data_role": "development_ood",
            },
        ]
    )
    catalog_path.write_text(yaml.safe_dump(catalog, sort_keys=False), encoding="utf-8")
    spec = load_pilot_benchmark_spec().model_copy(
        update={
            "development_asset_ids": ["CHEN-vMB-scRNA"],
            "development_ood_asset_ids": ["TRANSITIVE-OOD"],
            "behavior_only_asset_ids": [],
        }
    )

    with pytest.raises(BenchmarkError) as error:
        prepare_benchmark_split(spec, catalog_path)
    assert error.value.reason_code == "benchmark_role_lineage_overlap"


def test_competitor_alias_is_rejected_by_source_family(tmp_path: Path) -> None:
    _, catalog_path = _write_expression_fixture(tmp_path)
    catalog = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
    catalog["assets"][0].update(
        {"asset_id": "COMPETITOR-ALIAS", "source_family_id": "E-MTAB-14729"}
    )
    catalog_path.write_text(yaml.safe_dump(catalog, sort_keys=False), encoding="utf-8")
    spec = load_pilot_benchmark_spec().model_copy(
        update={
            "development_asset_ids": ["COMPETITOR-ALIAS"],
            "development_ood_asset_ids": [],
            "behavior_only_asset_ids": [],
        }
    )

    with pytest.raises(BenchmarkError) as error:
        prepare_benchmark_split(spec, catalog_path)
    assert error.value.reason_code == "sealed_or_denied_asset_selected"


def test_derived_competitor_source_name_is_rejected(tmp_path: Path) -> None:
    _, catalog_path = _write_expression_fixture(tmp_path)
    catalog = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
    catalog["assets"][0].update(
        {"asset_id": "PUBLIC-ALIAS", "source_family_id": "STUDER-2026-derived"}
    )
    catalog_path.write_text(yaml.safe_dump(catalog, sort_keys=False), encoding="utf-8")
    spec = load_pilot_benchmark_spec().model_copy(
        update={
            "development_asset_ids": ["PUBLIC-ALIAS"],
            "development_ood_asset_ids": [],
            "behavior_only_asset_ids": [],
        }
    )

    with pytest.raises(BenchmarkError) as error:
        prepare_benchmark_split(spec, catalog_path)
    assert error.value.reason_code == "sealed_or_denied_asset_selected"


def test_competitor_derivative_is_rejected_from_lineage_fields(tmp_path: Path) -> None:
    _, catalog_path = _write_expression_fixture(tmp_path)
    catalog = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
    catalog["assets"][0].update(
        {
            "asset_id": "PUBLIC-ALIAS",
            "source_family_id": "PUBLIC-FAMILY",
            "source_accession": "E-MTAB-14729",
            "root_source_family_id": "PUBLIC-FAMILY",
            "leakage_group": "PUBLIC-FAMILY",
        }
    )
    catalog_path.write_text(yaml.safe_dump(catalog, sort_keys=False), encoding="utf-8")
    spec = load_pilot_benchmark_spec().model_copy(
        update={
            "development_asset_ids": ["PUBLIC-ALIAS"],
            "development_ood_asset_ids": [],
            "behavior_only_asset_ids": [],
        }
    )

    with pytest.raises(BenchmarkError) as error:
        prepare_benchmark_split(spec, catalog_path)
    assert error.value.reason_code == "sealed_or_denied_asset_selected"


def test_split_requires_every_declared_development_asset(tmp_path: Path) -> None:
    _, catalog_path = _write_expression_fixture(tmp_path)
    spec = load_pilot_benchmark_spec().model_copy(
        update={
            "development_asset_ids": ["CHEN-vMB-scRNA", "MISSING-SOURCE"],
            "development_ood_asset_ids": [],
            "behavior_only_asset_ids": [],
        }
    )

    with pytest.raises(BenchmarkError) as error:
        prepare_benchmark_split(spec, catalog_path)

    assert error.value.reason_code == "benchmark_assets_missing_from_catalog"


def test_split_requires_a_matching_asset_checksum(tmp_path: Path) -> None:
    path, catalog_path = _write_expression_fixture(tmp_path)
    path.write_bytes(path.read_bytes() + b"changed")
    spec = load_pilot_benchmark_spec().model_copy(
        update={
            "development_asset_ids": ["CHEN-vMB-scRNA"],
            "development_ood_asset_ids": [],
            "behavior_only_asset_ids": [],
        }
    )

    with pytest.raises(BenchmarkError) as error:
        prepare_benchmark_split(spec, catalog_path)

    assert error.value.reason_code == "benchmark_asset_checksum_mismatch"


def test_pilot_run_rejects_catalog_changed_after_split(tmp_path: Path) -> None:
    _, catalog_path = _write_expression_fixture(tmp_path)
    spec = load_pilot_benchmark_spec().model_copy(
        update={
            "methods": ["source_specific_correlation"],
            "development_asset_ids": ["CHEN-vMB-scRNA"],
            "development_ood_asset_ids": [],
            "behavior_only_asset_ids": [],
        }
    )
    split = prepare_benchmark_split(spec, catalog_path)
    catalog_path.write_text(
        catalog_path.read_text(encoding="utf-8") + "\n# changed\n", encoding="utf-8"
    )

    with pytest.raises(BenchmarkError) as error:
        run_pilot_benchmark(spec, catalog_path, split, tmp_path / "run")
    assert error.value.reason_code == "benchmark_split_not_canonical"


def test_pilot_run_rejects_a_handwritten_split(tmp_path: Path) -> None:
    _, catalog_path = _write_expression_fixture(tmp_path)
    spec = load_pilot_benchmark_spec().model_copy(
        update={
            "methods": ["source_specific_correlation"],
            "development_asset_ids": ["CHEN-vMB-scRNA"],
            "development_ood_asset_ids": [],
            "behavior_only_asset_ids": [],
        }
    )
    split = prepare_benchmark_split(spec, catalog_path)
    forged = split.model_copy(update={"records": split.records[:-1]})

    with pytest.raises(BenchmarkError) as error:
        run_pilot_benchmark(spec, catalog_path, forged, tmp_path / "run")
    assert error.value.reason_code == "benchmark_split_not_canonical"


def test_benchmark_identity_binds_adapter_source_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, catalog_path = _write_expression_fixture(tmp_path)
    spec = load_pilot_benchmark_spec().model_copy(
        update={
            "methods": ["source_specific_correlation"],
            "development_asset_ids": ["CHEN-vMB-scRNA"],
            "development_ood_asset_ids": [],
            "behavior_only_asset_ids": [],
        }
    )
    split = prepare_benchmark_split(spec, catalog_path)
    result = run_pilot_benchmark(spec, catalog_path, split, tmp_path / "run")
    run_dir = Path(result["run_dir"])
    hashes = cell_state_freeze._adapter_implementation_hashes()
    assert {
        "freeze.py",
        "method_adapter.py",
        "r_adapter.R",
        "bridge/toolkit/contracts.py",
    }.issubset(hashes)
    monkeypatch.setattr(
        cell_state_freeze,
        "_adapter_implementation_hashes",
        lambda: {**hashes, "bridge/toolkit/contracts.py": "0" * 64},
    )

    with pytest.raises(BenchmarkError) as error:
        summarize_benchmark(run_dir)
    assert error.value.reason_code == "adapter_contract_artifact_mismatch"


def test_locked_prepare_is_blocked_until_runner_exists(tmp_path: Path) -> None:
    spec = load_pilot_benchmark_spec().model_copy(update={"phase": "locked"})
    gate = FreezeGateSpec(
        gate_spec_id="FREEZE-GATE-CELLSTATE-scRNA-v1-draft",
        version="0.1.0",
        status="proposed",
        benchmark_spec_ref=spec.benchmark_spec_id,
        criteria=[],
    )

    with pytest.raises(BenchmarkError, match="locked_runner_not_implemented"):
        prepare_benchmark_split(spec, _asset_catalog(tmp_path), freeze_gate=gate)


def test_locked_prepare_rejects_placeholder_signature_hashes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cell_state_freeze, "LOCKED_RUNNER_IMPLEMENTATION_VERSION", "test")
    spec = load_pilot_benchmark_spec().model_copy(update={"phase": "locked"})
    catalog = _asset_catalog(tmp_path)
    criteria = [
        {
            "metric": metric,
            "scope": "locked fixture",
            "operator": "<=" if metric in {
                "composition_mae",
                "false_reassurance",
                "downsampling_drift",
                "preprocessing_sensitivity",
            } else ">=",
            "threshold": 0.5,
            "rationale": "Fixture only.",
        }
        for metric in {
            "exact_accuracy",
            "macro_f1",
            "composition_mae",
            "prediction_set_coverage",
            "false_reassurance",
            "ood_assessment_coverage",
            "downsampling_drift",
            "preprocessing_sensitivity",
        }
    ]
    gate = FreezeGateSpec.model_validate(
        {
            "gate_spec_id": "FREEZE-GATE-CELLSTATE-scRNA-v1",
            "version": "1.0.0",
            "status": "approved",
            "benchmark_spec_ref": spec.benchmark_spec_id,
            **_gate_bindings(spec, _sha256(catalog)),
            "criteria": criteria,
            "signatures": [
                _signed("bridge_scientific_lead", "bridge-reviewer", "0" * 64),
                _signed("chen_team_reviewer", "chen-reviewer", "0" * 64),
            ],
        }
    )

    with pytest.raises(BenchmarkError) as error:
        prepare_benchmark_split(
            spec,
            catalog,
            freeze_gate=gate,
            reviewer_registry_path=_write_reviewer_registry(tmp_path),
        )
    assert error.value.reason_code == "reviewer_signature_identity_mismatch"


def test_locked_prepare_rejects_invalid_cryptographic_signature(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cell_state_freeze, "LOCKED_RUNNER_IMPLEMENTATION_VERSION", "test")
    spec = load_pilot_benchmark_spec().model_copy(update={"phase": "locked"})
    catalog = _asset_catalog(tmp_path)
    metrics = {
        "exact_accuracy",
        "macro_f1",
        "composition_mae",
        "prediction_set_coverage",
        "false_reassurance",
        "ood_assessment_coverage",
        "downsampling_drift",
        "preprocessing_sensitivity",
    }
    payload = {
        "gate_spec_id": "FREEZE-GATE-CELLSTATE-scRNA-v1",
        "version": "1.0.0",
        "status": "approved",
        "benchmark_spec_ref": spec.benchmark_spec_id,
        **_gate_bindings(spec, _sha256(catalog)),
        "criteria": [
            {
                "metric": metric,
                "scope": "locked fixture",
                "operator": "<=" if metric in {
                    "composition_mae",
                    "false_reassurance",
                    "downsampling_drift",
                    "preprocessing_sensitivity",
                } else ">=",
                "threshold": 0.5,
                "rationale": "Fixture only.",
            }
            for metric in metrics
        ],
        "signatures": [],
    }
    object_hash = object_signing_hash(payload)
    payload["signatures"] = [
        _signed("bridge_scientific_lead", "bridge-reviewer", object_hash),
        _signed("chen_team_reviewer", "chen-reviewer", object_hash),
    ]
    normalized_hash = object_signing_hash(FreezeGateSpec.model_validate(payload))
    payload["signatures"] = [
        _signed("bridge_scientific_lead", "bridge-reviewer", normalized_hash),
        _signed("chen_team_reviewer", "chen-reviewer", normalized_hash),
    ]
    payload["signatures"][1]["signature_base64"] = "A" * 88
    gate = FreezeGateSpec.model_validate(payload)

    with pytest.raises(BenchmarkError) as error:
        prepare_benchmark_split(
            spec,
            catalog,
            freeze_gate=gate,
            reviewer_registry_path=_write_reviewer_registry(tmp_path),
        )
    assert error.value.reason_code == "reviewer_signature_invalid"


def test_locked_gate_is_bound_to_the_full_spec_and_catalog(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cell_state_freeze, "LOCKED_RUNNER_IMPLEMENTATION_VERSION", "test")
    spec = load_pilot_benchmark_spec().model_copy(update={"phase": "locked"})
    catalog = _asset_catalog(tmp_path)
    metrics = {
        "exact_accuracy",
        "macro_f1",
        "composition_mae",
        "prediction_set_coverage",
        "false_reassurance",
        "ood_assessment_coverage",
        "downsampling_drift",
        "preprocessing_sensitivity",
    }
    gate = FreezeGateSpec.model_validate(
        {
            "gate_spec_id": "FREEZE-GATE-CELLSTATE-scRNA-v1",
            "version": "1.0.0",
            "status": "approved",
            "benchmark_spec_ref": spec.benchmark_spec_id,
            **_gate_bindings(spec, _sha256(catalog)),
            "benchmark_spec_sha256": "f" * 64,
            "criteria": [
                {
                    "metric": metric,
                    "scope": "locked fixture",
                    "operator": "<=" if metric in {
                        "composition_mae",
                        "false_reassurance",
                        "downsampling_drift",
                        "preprocessing_sensitivity",
                    } else ">=",
                    "threshold": 0.5,
                    "rationale": "Fixture only.",
                }
                for metric in metrics
            ],
            "signatures": [
                _signed("bridge_scientific_lead", "bridge-reviewer", "0" * 64),
                _signed("chen_team_reviewer", "chen-reviewer", "0" * 64),
            ],
        }
    )

    with pytest.raises(BenchmarkError) as error:
        prepare_benchmark_split(spec, catalog, freeze_gate=gate)
    assert error.value.reason_code == "freeze_gate_binding_mismatch"


def test_two_reviewers_cannot_share_one_public_key(tmp_path: Path) -> None:
    gate_payload = {
        "gate_spec_id": "FREEZE-GATE-CELLSTATE-draft",
        "version": "0.1.0",
        "status": "proposed",
        "benchmark_spec_ref": "CELLSTATE-BENCHMARK-scRNA-pilot-v0.2",
        "criteria": [],
        "signatures": [],
    }
    object_hash = object_signing_hash(gate_payload)
    key = _reviewer_key("shared")
    signatures = []
    reviewers = [
        ("bridge-reviewer", "bridge_scientific_lead"),
        ("chen-reviewer", "chen_team_reviewer"),
    ]
    for reviewer_id, role in reviewers:
        signatures.append(
            {
                "reviewer_id": reviewer_id,
                "reviewer_role": role,
                "key_id": f"{reviewer_id}-key-v1",
                "algorithm": "ed25519",
                "signed_at": "2026-08-11T00:00:00Z",
                "object_sha256": object_hash,
                "signature_base64": base64.b64encode(
                    key.sign(cell_state_freeze.SIGNATURE_DOMAIN + object_hash.encode())
                ).decode(),
            }
        )
    gate_payload["signatures"] = signatures
    gate = FreezeGateSpec.model_validate(gate_payload)
    public_key = base64.b64encode(
        key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    ).decode()
    registry = tmp_path / "trusted-reviewers.json"
    registry.write_text(
        json.dumps(
            {
                "reviewers": [
                    {
                        "reviewer_id": reviewer_id,
                        "reviewer_role": role,
                        "key_id": f"{reviewer_id}-key-v1",
                        "public_key_base64": public_key,
                    }
                    for reviewer_id, role in reviewers
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(BenchmarkError) as error:
        cell_state_freeze.verify_reviewer_signatures(gate, registry)
    assert error.value.reason_code == "trusted_reviewer_registry_invalid"


def test_scconform_requires_probabilities_and_an_independent_calibration_split(tmp_path: Path) -> None:
    prediction_path = tmp_path / "predictions.tsv"
    prediction_path.write_text(
        "observation_id\tpartition\ttrue_label\tprob__A\tprob__B\n"
        "a\tcalibration\tA\t0.8\t0.2\n"
        "b\ttest\tB\t0.1\t0.9\n",
        encoding="utf-8",
    )
    assert validate_probability_output(prediction_path) == {"A", "B"}

    bad = tmp_path / "bad.tsv"
    bad.write_text(
        "observation_id\tpartition\ttrue_label\tpredicted_label\n"
        "a\tcalibration\tA\tA\n",
        encoding="utf-8",
    )
    with pytest.raises(BenchmarkError, match="probability_columns_required"):
        validate_probability_output(bad)


def _probability_fixture() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "fold_id": ["fold-01", "fold-01"],
            "observation_id": ["cal", "test"],
            "partition": ["calibration", "test"],
            "true_label": ["A", "B"],
            "predicted_label": ["A", "B"],
            "prob__A": [0.8, 0.1],
            "prob__B": [0.2, 0.9],
        }
    )


def test_scconform_rejects_nonfinite_calibration_probabilities() -> None:
    frame = _probability_fixture()
    frame.loc[0, "prob__A"] = np.nan

    with pytest.raises(BenchmarkError) as error:
        cell_state_freeze._validate_probability_frame(
            frame, require_predicted_label=True
        )
    assert error.value.reason_code == "probability_values_invalid"


def test_scconform_rejects_calibration_rows_outside_simplex() -> None:
    frame = _probability_fixture()
    frame.loc[0, "prob__A"] = 0.7

    with pytest.raises(BenchmarkError) as error:
        cell_state_freeze._validate_probability_frame(
            frame, require_predicted_label=True
        )
    assert error.value.reason_code == "probability_rows_must_sum_to_one"


def test_scconform_rejects_base_label_that_is_not_probability_argmax() -> None:
    frame = _probability_fixture()
    frame.loc[0, "predicted_label"] = "B"

    with pytest.raises(BenchmarkError) as error:
        cell_state_freeze._validate_probability_frame(
            frame, require_predicted_label=True
        )
    assert error.value.reason_code == "predicted_label_probability_mismatch"


def test_l2_release_cannot_claim_external_freeze() -> None:
    with pytest.raises(ValidationError, match="L2 states cannot exceed provisional_frozen"):
        CellStateReleaseManifest(
            release_manifest_id="CELLSTATE-RELEASE-scRNA-v1.0",
            version="1.0.0",
            status="draft",
            assay="scRNA-seq",
            annotation_vocabulary_ref="BRIDGE-PD-vMB-ANNOTATION-v1.0",
            reference_snapshot_ref="REF-PD-vMB-CELLSTATE-v1.0",
            measurement_spec_ref="CELLSTATE-scRNA-v1.0",
            benchmark_spec_ref="CELLSTATE-BENCHMARK-scRNA-v1.0",
            biological_review_ref="BIOREVIEW-PD-vMB-v1.0",
            freeze_gate_ref="FREEZE-GATE-CELLSTATE-scRNA-v1.0",
            locked_test_state="not_run",
            per_state_release={"L2:RG_mFP": "frozen"},
        )


def test_release_cannot_be_frozen_without_human_signatures() -> None:
    with pytest.raises(ValidationError, match="release signatures"):
        CellStateReleaseManifest(
            release_manifest_id="CELLSTATE-RELEASE-scRNA-v1.0",
            version="1.0.0",
            status="frozen",
            assay="scRNA-seq",
            annotation_vocabulary_ref="BRIDGE-PD-vMB-ANNOTATION-v1.0",
            reference_snapshot_ref="REF-PD-vMB-CELLSTATE-v1.0",
            measurement_spec_ref="CELLSTATE-scRNA-v1.0",
            benchmark_spec_ref="CELLSTATE-BENCHMARK-scRNA-v1.0",
            biological_review_ref="BIOREVIEW-PD-vMB-v1.0",
            freeze_gate_ref="FREEZE-GATE-CELLSTATE-scRNA-v1.0",
            locked_test_state="passed",
            per_state_release={"L1:Neuron_DA": "frozen"},
            selected_methods={"L1:Neuron_DA": ["source_specific_correlation"]},
        )


def test_release_rejects_duplicate_reviewer_signatures() -> None:
    signatures = [
        _signature("bridge_scientific_lead", "reviewer-a"),
        _signature("chen_team_reviewer", "reviewer-b"),
        _signature("chen_team_reviewer", "reviewer-c"),
    ]

    with pytest.raises(ValidationError, match="release signatures"):
        CellStateReleaseManifest(
            release_manifest_id="CELLSTATE-RELEASE-scRNA-v1.0",
            version="1.0.0",
            status="frozen",
            assay="scRNA-seq",
            annotation_vocabulary_ref="BRIDGE-PD-vMB-ANNOTATION-v1.0",
            reference_snapshot_ref="REF-PD-vMB-CELLSTATE-v1.0",
            measurement_spec_ref="CELLSTATE-scRNA-v1.0",
            benchmark_spec_ref="CELLSTATE-BENCHMARK-scRNA-v1.0",
            biological_review_ref="BIOREVIEW-PD-vMB-v1.0",
            freeze_gate_ref="FREEZE-GATE-CELLSTATE-scRNA-v1.0",
            locked_test_state="passed",
            per_state_release={"L1:Neuron_DA": "frozen"},
            selected_methods={"L1:Neuron_DA": ["source_specific_correlation"]},
            biological_review_sha256="a" * 64,
            freeze_gate_sha256="b" * 64,
            locked_summary_sha256="c" * 64,
            signatures=signatures,
        )


def test_release_draft_keeps_all_states_shadow_or_unavailable() -> None:
    release = load_release_manifest_draft()

    assert release.status == "draft"
    assert release.locked_test_state == "not_run"
    assert release.signatures == []
    assert set(release.per_state_release.values()) <= {"shadow", "unavailable"}
    assert release.selected_methods == {}


def test_pilot_run_emits_native_predictions_metrics_and_unsigned_gate(tmp_path: Path) -> None:
    _, catalog_path = _write_expression_fixture(tmp_path)
    spec = load_pilot_benchmark_spec().model_copy(
        update={
            "methods": ["source_specific_correlation", "marker_program_evidence"],
            "development_asset_ids": ["CHEN-vMB-scRNA"],
            "development_ood_asset_ids": [],
            "behavior_only_asset_ids": [],
        }
    )
    split = prepare_benchmark_split(spec, catalog_path)

    result = run_pilot_benchmark(spec, catalog_path, split, tmp_path / "run")
    summary = summarize_benchmark(Path(result["run_dir"]))

    assert result["run_id"] == summary["run_id"]
    assert "predictions/source_specific_correlation.parquet" in result["artifact_hashes"]
    assert result["locked_assets_opened"] is False
    assert result["sealed_assets_opened"] is False
    assert set(summary["method_metrics"]) == {
        "source_specific_correlation",
        "marker_program_evidence",
    }
    assert summary["method_metrics"]["source_specific_correlation"]["exact_accuracy"] == 1.0
    assert summary["method_metrics"]["marker_program_evidence"]["exact_accuracy"] == 1.0
    assert summary["method_metrics"]["source_specific_correlation"]["metric_scope"] == "L1"
    assert summary["method_metrics"]["source_specific_correlation"]["by_label_level"][
        "L1"
    ]["exact_accuracy"] == 1.0
    assert summary["method_metrics"]["source_specific_correlation"]["per_state"] == {
        "L1:Astrocyte": {
            "n": 8,
            "precision": 1.0,
            "recall": 1.0,
            "f1": 1.0,
        },
        "L1:Neuron_DA": {
            "n": 8,
            "precision": 1.0,
            "recall": 1.0,
            "f1": 1.0,
        },
    }
    assert summary["pareto_candidates"] == []
    assert set(summary["preliminary_pareto_candidates"]) == {
        "source_specific_correlation",
        "marker_program_evidence",
    }
    assert summary["selection_state"] == "blocked_until_gate_and_locked_test"
    assert summary["freeze_gate_proposal"]["status"] == "proposed"
    assert summary["freeze_gate_proposal"]["signatures"] == []
    assert all(
        criterion["threshold"] is None
        for criterion in summary["freeze_gate_proposal"]["criteria"]
    )
    assert {item["metric"] for item in summary["freeze_gate_proposal"]["criteria"]} >= {
        "exact_accuracy",
        "macro_f1",
        "composition_mae",
        "prediction_set_coverage",
        "false_reassurance",
        "ood_assessment_coverage",
        "downsampling_drift",
        "preprocessing_sensitivity",
    }
    assert summary["method_metrics"]["source_specific_correlation"][
        "hierarchical_error"
    ]["cross_parent_error_rate"] == 0.0
    assert (Path(result["run_dir"]) / "exchange" / "CHEN-vMB-scRNA" / "matrix.h5").is_file()
    assert (Path(result["run_dir"]) / "exchange" / "CHEN-vMB-scRNA" / "observations.parquet").is_file()
    assert (Path(result["run_dir"]) / "exchange" / "CHEN-vMB-scRNA" / "bundle.json").is_file()
    bundle = json.loads(
        (Path(result["run_dir"]) / "exchange" / "CHEN-vMB-scRNA" / "bundle.json").read_text(
            encoding="utf-8"
        )
    )
    assert bundle["source_family_id"] == "CHEN-VMB"
    assert bundle["source_sha256"] == _sha256(tmp_path / "chen.h5ad")
    assert bundle["matrix_semantics"] == "raw_counts"
    assert "raw_count_artifact" not in bundle
    run_manifest = json.loads(
        (Path(result["run_dir"]) / "run_manifest.json").read_text(encoding="utf-8")
    )
    assert "predictions/source_specific_correlation.parquet" in run_manifest[
        "native_artifact_hashes"
    ]


def test_pilot_run_is_content_deterministic(tmp_path: Path) -> None:
    _, catalog_path = _write_expression_fixture(tmp_path)
    spec = load_pilot_benchmark_spec().model_copy(
        update={
            "methods": ["source_specific_correlation"],
            "development_asset_ids": ["CHEN-vMB-scRNA"],
            "development_ood_asset_ids": [],
            "behavior_only_asset_ids": [],
        }
    )
    split = prepare_benchmark_split(spec, catalog_path)

    first = run_pilot_benchmark(spec, catalog_path, split, tmp_path / "first")
    second = run_pilot_benchmark(spec, catalog_path, split, tmp_path / "second")

    assert first["run_id"] == second["run_id"]
    assert first["artifact_hashes"]
    assert first["artifact_hashes"] == second["artifact_hashes"]


def test_sparse_exchange_h5_is_deterministic_across_clock_ticks(tmp_path: Path) -> None:
    matrix = sparse.csr_matrix(np.asarray([[0.0, 1.0], [2.0, 0.0]], dtype=np.float32))
    first = tmp_path / "first.h5"
    second = tmp_path / "second.h5"

    cell_state_freeze._write_sparse_h5(first, matrix)
    time.sleep(1.1)
    cell_state_freeze._write_sparse_h5(second, matrix)

    assert _sha256(first) == _sha256(second)


def test_pilot_reuses_a_valid_exchange_bundle(tmp_path: Path, monkeypatch) -> None:
    _, catalog_path = _write_expression_fixture(tmp_path)
    spec = load_pilot_benchmark_spec().model_copy(
        update={
            "methods": ["source_specific_correlation"],
            "development_asset_ids": ["CHEN-vMB-scRNA"],
            "development_ood_asset_ids": [],
            "behavior_only_asset_ids": [],
        }
    )
    split = prepare_benchmark_split(spec, catalog_path)
    output = tmp_path / "run"
    first = run_pilot_benchmark(spec, catalog_path, split, output)
    run_dir = Path(first["run_dir"])
    (run_dir / "predictions" / "partial-external.tsv").write_text(
        "incomplete\n", encoding="utf-8"
    )
    monkeypatch.setattr(
        cell_state_freeze,
        "_write_sparse_h5",
        lambda *args, **kwargs: pytest.fail("valid exchange bundle was rewritten"),
    )

    second = run_pilot_benchmark(spec, catalog_path, split, output)

    assert second["artifact_hashes"] == first["artifact_hashes"]
    summary = json.loads((run_dir / "benchmark_summary.json").read_text(encoding="utf-8"))
    assert set(summary["method_metrics"]) == {"source_specific_correlation"}


def test_pilot_applies_native_methods_to_development_ood_and_behavior_only(tmp_path: Path) -> None:
    _, catalog_path = _write_expression_fixture(tmp_path)
    catalog = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
    for asset_id, role, samples in [
        ("GSE190729", "development_ood", ["ood-1", "ood-1"]),
        ("GSE204796", "behavior_only", ["D8", "D14"]),
    ]:
        path = tmp_path / f"{asset_id}.h5ad"
        ad.AnnData(
            sparse.csr_matrix(np.asarray([[4, 3, 2, 4, 3, 2, 20, 20]] * 2)),
            obs=pd.DataFrame(
                {"sample_id": samples, "timepoint": samples},
                index=[f"{asset_id}-{index}" for index in range(2)],
            ),
            var=pd.DataFrame(
                index=["TH", "DDC", "SLC6A3", "AQP4", "ALDH1L1", "GFAP", "G001", "G002"]
            ),
        ).write_h5ad(path)
        catalog["assets"].append(
                {
                    "asset_id": asset_id,
                    "source_family_id": asset_id,
                    **_lineage(asset_id),
                "assay": "scRNA-seq",
                "data_role": role,
                "path": str(path),
                "sample_column": "sample_id",
                "label_level": "L1",
                "matrix_location": "X",
                "matrix_semantics": "raw_counts",
                "metadata_columns": ["timepoint"],
                "checksum": _sha256(path),
            }
        )
    catalog_path.write_text(yaml.safe_dump(catalog, sort_keys=False), encoding="utf-8")
    spec = load_pilot_benchmark_spec().model_copy(
        update={
            "methods": ["source_specific_correlation"],
            "development_asset_ids": ["CHEN-vMB-scRNA"],
            "development_ood_asset_ids": ["GSE190729"],
            "behavior_only_asset_ids": ["GSE204796"],
        }
    )
    split = prepare_benchmark_split(spec, catalog_path)

    result = run_pilot_benchmark(spec, catalog_path, split, tmp_path / "run")
    summary = summarize_benchmark(Path(result["run_dir"]))

    metrics = summary["method_metrics"]["source_specific_correlation"]
    assert metrics["false_reassurance"] == 1.0
    assert metrics["ood_assessment_coverage"] == 1.0
    assert metrics["n_development_ood_assessed_evaluations"] == 8
    assert metrics["n_development_ood_observations"] == 2
    assert metrics["n_development_ood_evaluations"] == 8
    assert summary["behavior_only"]["source_specific_correlation"]["n_observations"] == 2
    assert summary["behavior_only"]["source_specific_correlation"]["n_evaluations"] == 8
    assert summary["behavior_only"]["source_specific_correlation"]["context_columns"] == [
        "timepoint"
    ]


def test_ood_with_insufficient_marker_coverage_is_not_assessed(tmp_path: Path) -> None:
    _, catalog_path = _write_expression_fixture(tmp_path)
    catalog = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
    path = tmp_path / "ood.h5ad"
    ad.AnnData(
        sparse.csr_matrix(np.asarray([[1, 2], [2, 1]])),
        obs=pd.DataFrame(
            {"sample_id": ["ood-1", "ood-1"]},
            index=["ood-cell-1", "ood-cell-2"],
        ),
        var=pd.DataFrame(index=["UNRELATED_A", "UNRELATED_B"]),
    ).write_h5ad(path)
    catalog["assets"].append(
            {
                "asset_id": "GSE190729",
                "source_family_id": "GSE190729",
                **_lineage("GSE190729"),
            "assay": "scRNA-seq",
            "data_role": "development_ood",
            "path": str(path),
            "sample_column": "sample_id",
            "label_level": "L1",
            "matrix_location": "X",
            "matrix_semantics": "raw_counts",
            "checksum": _sha256(path),
        }
    )
    catalog_path.write_text(yaml.safe_dump(catalog, sort_keys=False), encoding="utf-8")
    spec = load_pilot_benchmark_spec().model_copy(
        update={
            "methods": ["marker_program_evidence"],
            "development_asset_ids": ["CHEN-vMB-scRNA"],
            "development_ood_asset_ids": ["GSE190729"],
            "behavior_only_asset_ids": [],
        }
    )
    split = prepare_benchmark_split(spec, catalog_path)

    result = run_pilot_benchmark(spec, catalog_path, split, tmp_path / "run")
    predictions = pd.read_parquet(
        Path(result["run_dir"]) / "predictions" / "marker_program_evidence.parquet"
    )
    ood = predictions.loc[predictions["partition"].eq("development_ood")]

    assert set(ood["assignment_state"]) == {"not_assessed"}
    assert set(ood["unavailable_reason"].dropna()) == {
        "marker_program_gene_coverage_insufficient"
    }
    summary = summarize_benchmark(Path(result["run_dir"]))
    metrics = summary["method_metrics"]["marker_program_evidence"]
    assert metrics["ood_assessment_coverage"] == 0.0
    assert metrics["false_reassurance"] is None


def test_static_sample_id_supports_metadata_sparse_ood_assets(tmp_path: Path) -> None:
    _, catalog_path = _write_expression_fixture(tmp_path)
    catalog = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
    path = tmp_path / "GSE224152.h5ad"
    ad.AnnData(
        sparse.csr_matrix(np.asarray([[1, 1, 1, 2, 2, 2, 3, 3]] * 2)),
        obs=pd.DataFrame(index=["msc-1", "msc-2"]),
        var=pd.DataFrame(
            index=["TH", "DDC", "SLC6A3", "AQP4", "ALDH1L1", "GFAP", "G001", "G002"]
        ),
    ).write_h5ad(path)
    catalog["assets"].append(
            {
                "asset_id": "GSE224152",
                "source_family_id": "GSE224152",
                **_lineage("GSE224152"),
            "assay": "scRNA-seq",
            "data_role": "development_ood",
            "path": str(path),
            "sample_id_value": "dataset-only",
            "label_level": "L1",
            "matrix_location": "X",
            "matrix_semantics": "raw_counts",
            "checksum": _sha256(path),
        }
    )
    catalog_path.write_text(yaml.safe_dump(catalog, sort_keys=False), encoding="utf-8")
    spec = load_pilot_benchmark_spec().model_copy(
        update={
            "methods": ["source_specific_correlation"],
            "development_asset_ids": ["CHEN-vMB-scRNA"],
            "development_ood_asset_ids": ["GSE224152"],
            "behavior_only_asset_ids": [],
        }
    )

    split = prepare_benchmark_split(spec, catalog_path)
    assert [
        record.sample_id for record in split.records if record.asset_id == "GSE224152"
    ] == ["dataset-only"]


def test_split_applies_modality_filter_and_parent_label_consistency(tmp_path: Path) -> None:
    path = tmp_path / "rgnb.h5ad"
    ad.AnnData(
        sparse.csr_matrix(np.ones((5, 3))),
        obs=pd.DataFrame(
            {
                "Sample": ["donor-1", "donor-2", "donor-3", "sn-only", "conflict"],
                "system": ["sc_RNA_seq", "sc_RNA_seq", "sc_RNA_seq", "sn_RNA_seq", "sc_RNA_seq"],
                "cell_type": [
                    "Radial_Glia",
                    "Radial_Glia",
                    "Neuroblast",
                    "Radial_Glia",
                    "Pericyte",
                ],
                "subtype": ["RG_mFP", "RG_mBMP", "Nb_mFP", "RG_mFP", "RG_mFP"],
            },
            index=[f"cell-{index}" for index in range(5)],
        ),
        var=pd.DataFrame(index=["A", "B", "C"]),
    ).write_h5ad(path)
    catalog = {
        "assets": [
                {
                    "asset_id": "CHEN-RGNB-scRNA",
                    "source_family_id": "CHEN-VMB",
                    **_lineage("CHEN-VMB", derived_from=["CHEN-vMB-scRNA"]),
                "assay": "scRNA-seq",
                "data_role": "labeled_reference",
                "path": str(path),
                "sample_column": "Sample",
                "label_column": "subtype",
                "parent_label_column": "cell_type",
                "label_level": "L2",
                "filters": {"system": ["sc_RNA_seq"]},
                "checksum": _sha256(path),
            }
        ]
    }
    catalog_path = tmp_path / "catalog.yaml"
    catalog_path.write_text(yaml.safe_dump(catalog, sort_keys=False), encoding="utf-8")
    spec = load_pilot_benchmark_spec().model_copy(
        update={
            "development_asset_ids": ["CHEN-RGNB-scRNA"],
            "development_ood_asset_ids": [],
            "behavior_only_asset_ids": [],
            "locked_asset_ids": [],
            "locked_method_exclusions": {},
        }
    )

    split = prepare_benchmark_split(spec, catalog_path)

    assert {record.sample_id for record in split.records} == {
        "donor-1",
        "donor-2",
        "donor-3",
    }


def test_summary_registers_external_adapter_metadata_without_extra_evidence_vote(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(
        cell_state_freeze.METHOD_ADAPTER_CONTRACTS["scconform_calibration"],
        "alpha",
        0.25,
    )
    _, catalog_path = _write_expression_fixture(tmp_path)
    spec = load_pilot_benchmark_spec().model_copy(
        update={
            "methods": ["source_specific_correlation", "scanvi", "scconform_calibration"],
            "development_asset_ids": ["CHEN-vMB-scRNA"],
            "development_ood_asset_ids": [],
            "behavior_only_asset_ids": [],
        }
    )
    split = prepare_benchmark_split(spec, catalog_path)
    result = run_pilot_benchmark(spec, catalog_path, split, tmp_path / "run")
    run_dir = Path(result["run_dir"])
    baseline = pd.read_parquet(run_dir / "predictions" / "source_specific_correlation.parquet")
    scanvi = baseline.copy()
    scanvi["prob__L1:Astrocyte"] = np.where(
        scanvi["predicted_label"].eq("L1:Astrocyte"), 0.9, 0.1
    )
    scanvi["prob__L1:Neuron_DA"] = 1.0 - scanvi["prob__L1:Astrocyte"]
    scanvi_path = run_dir / "predictions" / "scanvi--CHEN-vMB-scRNA.parquet"
    scanvi.to_parquet(scanvi_path, index=False)
    scanvi_metadata_path = Path(f"{scanvi_path}.metadata.json")
    scanvi_metadata_path.write_text(
        json.dumps(
            {
                "adapter": "scanvi",
                **_scanvi_parameters(),
                "adapter_implementation_version": "0.2.3",
                "package_version": "1.4.0.post1",
                "evidence_family": "latent_reference_mapping",
                "probability_semantics": "categorical_simplex",
                "query_expression_used_as_unlabeled_during_training": True,
                "conformal_eligible": True,
                    "independent_evidence_vote": True,
                    "output_sha256": _sha256(scanvi_path),
                    **_adapter_provenance(run_dir, ["CHEN-vMB-scRNA"]),
            }
        ),
        encoding="utf-8",
    )
    second = scanvi.copy()
    second["label_level"] = "L2"
    second_path = run_dir / "predictions" / "scanvi--CHEN-RGNB-scRNA.parquet"
    second.to_parquet(second_path, index=False)
    (run_dir / "predictions" / "scanvi--CHEN-RGNB-scRNA.parquet.metadata.json").write_text(
        json.dumps(
                {
                "adapter": "scanvi",
                **_scanvi_parameters(),
                "adapter_implementation_version": "0.2.3",
                "package_version": "1.4.0.post1",
                "evidence_family": "latent_reference_mapping",
                "probability_semantics": "categorical_simplex",
                "query_expression_used_as_unlabeled_during_training": True,
                "conformal_eligible": True,
                    "independent_evidence_vote": True,
                    "output_sha256": _sha256(second_path),
                    **_adapter_provenance(run_dir, ["CHEN-vMB-scRNA"]),
            }
        ),
        encoding="utf-8",
    )
    calibrated = _scconform_fixture(scanvi, alpha=0.25)
    calibrated.to_parquet(
        run_dir / "predictions" / "scconform_calibration.parquet", index=False
    )
    (run_dir / "predictions" / "scconform_calibration.parquet.metadata.json").write_text(
        json.dumps(
                {
                "adapter": "scconform_calibration",
                "adapter_implementation_version": "0.1.2",
                "package_version": "1.0.0",
                "evidence_family": "latent_reference_mapping",
                "probability_semantics": "prediction_set",
                "independent_evidence_vote": False,
                "base_adapter": "scanvi",
                "alpha": 0.25,
                "base_prediction_sha256": _sha256(scanvi_path),
                "probability_metadata_sha256": _sha256(scanvi_metadata_path),
                    "query_expression_used_as_unlabeled_during_training": True,
                    **_adapter_provenance(run_dir, ["CHEN-vMB-scRNA"]),
                    "output_sha256": _sha256(
                    run_dir / "predictions" / "scconform_calibration.parquet"
                ),
            }
        ),
        encoding="utf-8",
    )

    summary = summarize_benchmark(run_dir)

    assert summary["method_status"]["scanvi"] == "completed_external_adapter"
    assert summary["method_metrics"]["scanvi"]["n_test_observations"] == 32
    assert summary["method_metrics"]["scanvi"]["metric_scope"] == "pooled_diagnostic"
    assert set(summary["method_metrics"]["scanvi"]["by_label_level"]) == {"L1", "L2"}
    assert set(
        summary["method_metrics"]["scanvi"][
            "fold_missing_training_labels_by_label_level"
        ]
    ) == {"L1", "L2"}
    assert summary["method_metrics"]["scanvi"]["evidence_family"] == (
        "latent_reference_mapping"
    )
    assert summary["method_metrics"]["scanvi"]["evaluation_protocol"] == (
        "transductive_unlabeled_query"
    )
    assert summary["transductive_diagnostics"] == ["scanvi", "scconform_calibration"]
    assert "scanvi" not in summary["preliminary_pareto_candidates"]
    assert summary["method_metrics"]["scconform_calibration"][
        "independent_evidence_vote"
    ] is False
    assert summary["method_metrics"]["scconform_calibration"][
        "evaluation_protocol"
    ] == "calibration_layer_on_transductive_base"
    assert "scconform_calibration" not in summary["preliminary_pareto_candidates"]

    conform_metadata_path = (
        run_dir / "predictions" / "scconform_calibration.parquet.metadata.json"
    )
    original_scanvi_bytes = scanvi_path.read_bytes()
    original_scanvi_metadata = scanvi_metadata_path.read_text(encoding="utf-8")
    original_conform_metadata = conform_metadata_path.read_text(encoding="utf-8")
    invalid_scanvi = pd.read_parquet(scanvi_path)
    calibration_row = invalid_scanvi.index[invalid_scanvi["partition"].eq("calibration")][0]
    invalid_scanvi.loc[calibration_row, "prob__L1:Astrocyte"] = np.nan
    invalid_scanvi.to_parquet(scanvi_path, index=False)
    scanvi_metadata = json.loads(original_scanvi_metadata)
    scanvi_metadata["output_sha256"] = _sha256(scanvi_path)
    scanvi_metadata_path.write_text(json.dumps(scanvi_metadata), encoding="utf-8")
    conform_metadata = json.loads(original_conform_metadata)
    conform_metadata["base_prediction_sha256"] = _sha256(scanvi_path)
    conform_metadata["probability_metadata_sha256"] = _sha256(scanvi_metadata_path)
    conform_metadata_path.write_text(json.dumps(conform_metadata), encoding="utf-8")
    with pytest.raises(BenchmarkError) as error:
        summarize_benchmark(run_dir)
    assert error.value.reason_code == "probability_values_invalid"
    scanvi_path.write_bytes(original_scanvi_bytes)
    scanvi_metadata_path.write_text(original_scanvi_metadata, encoding="utf-8")
    conform_metadata_path.write_text(original_conform_metadata, encoding="utf-8")

    scanvi_metadata_text = scanvi_metadata_path.read_text(encoding="utf-8")
    scanvi_metadata = json.loads(scanvi_metadata_text)
    scanvi_metadata["preset"] = "full"
    scanvi_metadata_path.write_text(json.dumps(scanvi_metadata), encoding="utf-8")
    with pytest.raises(BenchmarkError) as error:
        summarize_benchmark(run_dir)
    assert error.value.reason_code == "adapter_contract_mismatch"
    scanvi_metadata_path.write_text(scanvi_metadata_text, encoding="utf-8")

    conform_metadata = json.loads(conform_metadata_path.read_text(encoding="utf-8"))
    conform_metadata["base_prediction_sha256"] = "0" * 64
    conform_metadata_path.write_text(json.dumps(conform_metadata), encoding="utf-8")
    with pytest.raises(BenchmarkError) as error:
        summarize_benchmark(run_dir)
    assert error.value.reason_code == "scconform_conversion_manifest_invalid"

    conform_metadata["base_prediction_sha256"] = _sha256(scanvi_path)
    calibrated["prediction_set"] = "[]"
    calibrated["assignment_state"] = "conformal_empty"
    conform_path = run_dir / "predictions" / "scconform_calibration.parquet"
    calibrated.to_parquet(conform_path, index=False)
    conform_metadata["output_sha256"] = _sha256(conform_path)
    conform_metadata_path.write_text(json.dumps(conform_metadata), encoding="utf-8")
    with pytest.raises(BenchmarkError) as error:
        summarize_benchmark(run_dir)
    assert error.value.reason_code == "scconform_prediction_set_mismatch"


def test_summary_reads_external_tsv_without_arrow_dependency(tmp_path: Path) -> None:
    _, catalog_path = _write_expression_fixture(tmp_path)
    spec = load_pilot_benchmark_spec().model_copy(
        update={
            "methods": ["source_specific_correlation", "scanvi"],
            "development_asset_ids": ["CHEN-vMB-scRNA"],
            "development_ood_asset_ids": [],
            "behavior_only_asset_ids": [],
        }
    )
    split = prepare_benchmark_split(spec, catalog_path)
    result = run_pilot_benchmark(spec, catalog_path, split, tmp_path / "run")
    run_dir = Path(result["run_dir"])
    prediction = pd.read_parquet(
        run_dir / "predictions" / "source_specific_correlation.parquet"
    )
    output = run_dir / "predictions" / "scanvi--CHEN-vMB-scRNA.tsv"
    prediction.to_csv(output, sep="\t", index=False)
    Path(f"{output}.metadata.json").write_text(
        json.dumps(
                {
                "adapter": "scanvi",
                **_scanvi_parameters(),
                "adapter_implementation_version": "0.2.3",
                "package_version": "1.4.0.post1",
                "evidence_family": "latent_reference_mapping",
                "probability_semantics": "categorical_simplex",
                "query_expression_used_as_unlabeled_during_training": True,
                    "independent_evidence_vote": True,
                    "output_sha256": _sha256(output),
                    **_adapter_provenance(run_dir, ["CHEN-vMB-scRNA"]),
            }
        ),
        encoding="utf-8",
    )

    summary = summarize_benchmark(run_dir)

    assert summary["method_status"]["scanvi"] == "completed_external_adapter"
    assert summary["method_metrics"]["scanvi"]["n_test_observations"] == 16
    first_evidence_run = summary["evidence_run_id"]
    versioned_summary = run_dir / f"benchmark_summary--{first_evidence_run}.json"
    original_snapshot = versioned_summary.read_text(encoding="utf-8")
    versioned_summary.write_text("{}\n", encoding="utf-8")
    with pytest.raises(BenchmarkError) as error:
        summarize_benchmark(run_dir)
    assert error.value.reason_code == "versioned_evidence_collision"
    versioned_summary.write_text(original_snapshot, encoding="utf-8")

    metadata_path = Path(f"{output}.metadata.json")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["execution_note"] = "resource-only metadata changed"
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    revised = summarize_benchmark(run_dir)
    assert revised["evidence_run_id"] != first_evidence_run
    assert versioned_summary.read_text(encoding="utf-8") == original_snapshot


def test_prediction_content_accepts_lossless_float_text_roundtrip(tmp_path: Path) -> None:
    original = pd.DataFrame(
        {
            "fold_id": ["fold-01", "fold-01"],
            "observation_id": ["cell-1", "cell-2"],
            "score": [0.12345678901234568, 0.8765432109876543],
            "margin": [0.012345678901234568, 0.09876543210987654],
            "prob__L1:A": [0.12345678901234568, 0.8765432109876543],
            "prob__L1:ZERO": [0.0, 0.0],
        }
    )
    path = tmp_path / "predictions.tsv"
    original.to_csv(path, sep="\t", index=False)
    roundtripped = pd.read_csv(path, sep="\t")

    cell_state_freeze._assert_prediction_content_equal(
        original, roundtripped, "float-roundtrip"
    )

    roundtripped.loc[0, "score"] += 1e-6
    with pytest.raises(BenchmarkError) as error:
        cell_state_freeze._assert_prediction_content_equal(
            original, roundtripped, "float-roundtrip"
        )
    assert error.value.reason_code == "prediction_content_mismatch"


def test_summary_rejects_an_adapter_that_omits_test_observations(tmp_path: Path) -> None:
    _, catalog_path = _write_expression_fixture(tmp_path)
    spec = load_pilot_benchmark_spec().model_copy(
        update={
            "methods": ["source_specific_correlation", "scanvi"],
            "development_asset_ids": ["CHEN-vMB-scRNA"],
            "development_ood_asset_ids": [],
            "behavior_only_asset_ids": [],
        }
    )
    split = prepare_benchmark_split(spec, catalog_path)
    result = run_pilot_benchmark(spec, catalog_path, split, tmp_path / "run")
    run_dir = Path(result["run_dir"])
    prediction = pd.read_parquet(
        run_dir / "predictions" / "source_specific_correlation.parquet"
    ).iloc[:-1]
    output = run_dir / "predictions" / "scanvi--CHEN-vMB-scRNA.parquet"
    prediction.to_parquet(output, index=False)
    Path(f"{output}.metadata.json").write_text(
        json.dumps(
            {
                "adapter": "scanvi",
                **_scanvi_parameters(),
                "adapter_implementation_version": "0.2.3",
                "package_version": "1.4.0.post1",
                "evidence_family": "latent_reference_mapping",
                "probability_semantics": "categorical_simplex",
                "query_expression_used_as_unlabeled_during_training": True,
                "independent_evidence_vote": True,
                "output_sha256": _sha256(output),
                **_adapter_provenance(run_dir, ["CHEN-vMB-scRNA"]),
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(BenchmarkError) as error:
        summarize_benchmark(run_dir)
    assert error.value.reason_code == "prediction_observation_coverage_mismatch"


def test_summary_rejects_an_adapter_that_omits_a_declared_asset(tmp_path: Path) -> None:
    path, catalog_path = _write_expression_fixture(tmp_path)
    catalog = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
    catalog["assets"].append(
        {
            **catalog["assets"][0],
            "asset_id": "CHEN-vMB-scRNA-B",
            "source_family_id": "CHEN-VMB-B",
            **_lineage("CHEN-VMB-B", derived_from=["CHEN-vMB-scRNA"]),
            "path": str(path),
        }
    )
    catalog_path.write_text(yaml.safe_dump(catalog, sort_keys=False), encoding="utf-8")
    spec = load_pilot_benchmark_spec().model_copy(
        update={
            "methods": ["source_specific_correlation", "scanvi"],
            "development_asset_ids": ["CHEN-vMB-scRNA", "CHEN-vMB-scRNA-B"],
            "development_ood_asset_ids": [],
            "behavior_only_asset_ids": [],
        }
    )
    split = prepare_benchmark_split(spec, catalog_path)
    result = run_pilot_benchmark(spec, catalog_path, split, tmp_path / "run")
    run_dir = Path(result["run_dir"])
    prediction = pd.read_parquet(
        run_dir / "predictions" / "source_specific_correlation.parquet"
    )
    prediction = prediction.loc[prediction["asset_id"].eq("CHEN-vMB-scRNA")]
    output = run_dir / "predictions" / "scanvi--CHEN-vMB-scRNA.parquet"
    prediction.to_parquet(output, index=False)
    Path(f"{output}.metadata.json").write_text(
        json.dumps(
            {
                "adapter": "scanvi",
                **_scanvi_parameters(),
                "adapter_implementation_version": "0.2.3",
                "package_version": "1.4.0.post1",
                "evidence_family": "latent_reference_mapping",
                "probability_semantics": "categorical_simplex",
                "query_expression_used_as_unlabeled_during_training": True,
                "independent_evidence_vote": True,
                "output_sha256": _sha256(output),
                **_adapter_provenance(run_dir, ["CHEN-vMB-scRNA"]),
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(BenchmarkError) as error:
        summarize_benchmark(run_dir)

    assert error.value.reason_code == "adapter_asset_coverage_mismatch"


def test_summary_rejects_adapter_declared_evidence_family(tmp_path: Path) -> None:
    _, catalog_path = _write_expression_fixture(tmp_path)
    spec = load_pilot_benchmark_spec().model_copy(
        update={
            "methods": ["source_specific_correlation", "scmap"],
            "development_asset_ids": ["CHEN-vMB-scRNA"],
            "development_ood_asset_ids": [],
            "behavior_only_asset_ids": [],
        }
    )
    split = prepare_benchmark_split(spec, catalog_path)
    result = run_pilot_benchmark(spec, catalog_path, split, tmp_path / "run")
    run_dir = Path(result["run_dir"])
    prediction = pd.read_parquet(
        run_dir / "predictions" / "source_specific_correlation.parquet"
    )
    output = run_dir / "predictions" / "scmap--CHEN-vMB-scRNA.parquet"
    prediction.to_parquet(output, index=False)
    Path(f"{output}.metadata.json").write_text(
        json.dumps(
            {
                "adapter": "scmap",
                "adapter_implementation_version": "0.1.2",
                "package_version": "1.34.0",
                "evidence_family": "fabricated_independent_family",
                "probability_semantics": "multi_similarity_consensus",
                "query_expression_used_as_unlabeled_during_training": False,
                "independent_evidence_vote": True,
                "output_sha256": _sha256(output),
                **_adapter_provenance(run_dir, ["CHEN-vMB-scRNA"]),
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(BenchmarkError) as error:
        summarize_benchmark(run_dir)

    assert error.value.reason_code == "adapter_contract_mismatch"


def test_pareto_keeps_only_one_representative_per_evidence_family() -> None:
    metrics = {
        "singler": {
            "evidence_family": "reference_similarity",
            "independent_evidence_vote": True,
            "evaluation_protocol": "inductive",
            "exact_accuracy": 0.8,
            "composition_mae": 0.1,
        },
        "scmap": {
            "evidence_family": "reference_similarity",
            "independent_evidence_vote": True,
            "evaluation_protocol": "inductive",
            "exact_accuracy": 0.7,
            "composition_mae": 0.05,
        },
        "celltypist": {
            "evidence_family": "supervised_classifier",
            "independent_evidence_vote": True,
            "evaluation_protocol": "inductive",
            "exact_accuracy": 0.75,
            "composition_mae": 0.08,
        },
    }

    candidates = cell_state_freeze._pareto_candidates(metrics)

    assert "singler" in candidates
    assert "scmap" not in candidates


def test_science_team_cli_prepare_run_and_summarize(tmp_path: Path, capsys) -> None:
    _, catalog_path = _write_expression_fixture(tmp_path)
    spec = load_pilot_benchmark_spec().model_copy(
        update={
            "methods": ["source_specific_correlation"],
            "development_asset_ids": ["CHEN-vMB-scRNA"],
            "development_ood_asset_ids": [],
            "behavior_only_asset_ids": [],
        }
    )
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(spec.model_dump_json(indent=2), encoding="utf-8")
    split_path = tmp_path / "split.json"

    assert benchmark_main(
        [
            "cell-state",
            "prepare",
            "--spec",
            str(spec_path),
            "--asset-catalog",
            str(catalog_path),
            "--output",
            str(split_path),
        ]
    ) == 0
    capsys.readouterr()
    assert split_path.is_file()

    output_root = tmp_path / "cli-run"
    assert benchmark_main(
        [
            "cell-state",
            "run",
            "--spec",
            str(spec_path),
            "--asset-catalog",
            str(catalog_path),
            "--split-manifest",
            str(split_path),
            "--output-dir",
            str(output_root),
        ]
    ) == 0
    run_payload = json.loads(capsys.readouterr().out)

    summary_path = tmp_path / "summary.json"
    assert benchmark_main(
        [
            "cell-state",
            "summarize",
            "--run-dir",
            run_payload["run_dir"],
            "--output",
            str(summary_path),
        ]
    ) == 0
    capsys.readouterr()
    assert json.loads(summary_path.read_text(encoding="utf-8"))["locked_test_state"] == "not_authorized"


def _write_valid_release_bundle(
    tmp_path: Path,
    selected_method: str = "source_specific_correlation",
    release_status: str = "frozen",
):
    reviewer_registry = _write_reviewer_registry(tmp_path)
    review_payload = load_biological_review_draft().model_dump(mode="json")
    review_payload["review_record_id"] = "BIOREVIEW-PD-vMB-v1.0"
    review_payload["vocabulary_ref"] = "BRIDGE-PD-vMB-ANNOTATION-v1.0"
    review_payload["status"] = "partially_approved"
    review_payload["product_definition_review_status"] = "approved"
    review_payload["state_role_map_review_status"] = "approved"
    approved_states = {"L1:Neuron_DA", "L2:RG_mFP"}
    selected_methods = (
        ["source_specific_correlation", selected_method]
        if selected_method == "marker_program_evidence"
        else [selected_method]
    )
    review_payload["state_reviews"] = [
        {
            **card,
            "positive_markers": (
                card["positive_markers"] or ["FIXTURE_POS"]
                if card["state_id"] in approved_states
                else card["positive_markers"]
            ),
            "negative_markers": (
                card["negative_markers"] or ["FIXTURE_NEG"]
                if card["state_id"] in approved_states
                else card["negative_markers"]
            ),
            "review_blockers": [] if card["state_id"] in approved_states else card["review_blockers"],
            "review_status": "approved" if card["state_id"] in approved_states else "pending",
        }
        for card in review_payload["state_reviews"]
    ]
    review_hash = object_signing_hash(review_payload)
    review_payload["signatures"] = [
        _signed("bridge_scientific_lead", "bridge-reviewer", review_hash),
        _signed("chen_team_reviewer", "chen-reviewer", review_hash),
    ]
    review = BiologicalReviewRecord.model_validate(review_payload)

    gate_metrics = [
        ("exact_accuracy", "L1 source holdout", ">=", 0.80, 0.90),
        ("macro_f1", "L1 source holdout", ">=", 0.75, 0.85),
        ("composition_mae", "product composition", "<=", 0.10, 0.05),
        ("prediction_set_coverage", "calibration", ">=", 0.90, 0.94),
        ("false_reassurance", "locked OOD", "<=", 0.05, 0.02),
        ("ood_assessment_coverage", "locked OOD", ">=", 0.95, 1.0),
        ("downsampling_drift", "sensitivity", "<=", 0.10, 0.04),
        ("preprocessing_sensitivity", "sensitivity", "<=", 0.10, 0.03),
    ]
    locked_spec = load_pilot_benchmark_spec().model_copy(
        update={
            "benchmark_spec_id": "CELLSTATE-BENCHMARK-scRNA-v1.0",
            "version": "1.0.0",
            "phase": "locked",
            "annotation_vocabulary_ref": "BRIDGE-PD-vMB-ANNOTATION-v1.0",
            "reference_snapshot_ref": "REF-PD-vMB-CELLSTATE-v1.0",
            "measurement_spec_ref": "CELLSTATE-scRNA-v1.0",
        }
    )
    state_gate_metrics = []
    for state_id in approved_states:
        for method_id in selected_methods:
            state_gate_metrics.extend(
                [
                    {
                        "metric": "f1",
                        "scope": f"{state_id} locked source holdout",
                        "state_id": state_id,
                        "method_id": method_id,
                        "operator": ">=",
                        "threshold": 0.70,
                        "pilot_observation": 0.80,
                        "rationale": "Fixture per-state threshold.",
                    },
                    {
                        "metric": "n",
                        "scope": f"{state_id} locked source holdout support",
                        "state_id": state_id,
                        "method_id": method_id,
                        "operator": ">=",
                        "threshold": 1.0,
                        "pilot_observation": 100.0,
                        "rationale": "Fixture support threshold.",
                    },
                ]
            )
    gate_payload = {
        "gate_spec_id": "FREEZE-GATE-CELLSTATE-scRNA-v1.0",
        "version": "1.0.0",
        "status": "approved",
        "benchmark_spec_ref": "CELLSTATE-BENCHMARK-scRNA-v1.0",
        "benchmark_spec_sha256": cell_state_freeze._model_sha256(locked_spec),
        "asset_catalog_sha256": "e" * 64,
        "reference_snapshot_ref": "REF-PD-vMB-CELLSTATE-v1.0",
        "reference_snapshot_sha256": "c" * 64,
        "environment_spec_refs": [
            "ENV-CELLSTATE-PY-v0.1",
            "ENV-CELLSTATE-BIOC-R46-v0.1",
        ],
        "environment_spec_sha256": {
            "ENV-CELLSTATE-PY-v0.1": "d" * 64,
            "ENV-CELLSTATE-BIOC-R46-v0.1": "d" * 64,
        },
        "environment_health_record_sha256": "e" * 64,
        "adapter_contract_sha256": cell_state_freeze._adapter_contract_sha256(locked_spec),
        "pilot_evidence_sha256": "1" * 64,
        "criteria": [
            {
                "metric": metric,
                "scope": scope,
                "operator": operator,
                "threshold": threshold,
                "pilot_observation": observation,
                "rationale": "Fixture threshold for contract validation only.",
            }
            for metric, scope, operator, threshold, observation in gate_metrics
        ]
        + state_gate_metrics,
        "signatures": [],
    }
    for criterion in gate_payload["criteria"]:
        criterion.setdefault("state_id", None)
        criterion.setdefault("method_id", None)
    gate_hash = object_signing_hash(gate_payload)
    gate_payload["signatures"] = [
        _signed("bridge_scientific_lead", "bridge-reviewer", gate_hash),
        _signed("chen_team_reviewer", "chen-reviewer", gate_hash),
    ]
    gate = FreezeGateSpec.model_validate(gate_payload)
    (tmp_path / "freeze_gate.json").write_text(
        json.dumps(gate.model_dump(mode="json"), sort_keys=True), encoding="utf-8"
    )
    freeze_gate_sha256 = _sha256(tmp_path / "freeze_gate.json")
    reference_manifest_sha256 = gate.reference_snapshot_sha256

    split_payload = {
        "split_manifest_id": "CELLSTATE-LOCKED-SPLIT-fixture",
        "benchmark_spec_ref": gate.benchmark_spec_ref,
        "benchmark_spec_sha256": gate.benchmark_spec_sha256,
        "phase": "locked",
        "random_seed": 20260811,
        "input_catalog_sha256": "e" * 64,
        "records": [
            {
                "asset_id": "LAMANNO-2016",
                "source_family_id": "LAMANNO-2016",
                "sample_id": "locked-source",
                "partition": "locked_test",
                "data_role": "locked_source_holdout",
                "fold_id": None,
                "n_observations": 10,
            },
            {
                "asset_id": "GSE120046",
                "source_family_id": "GSE120046",
                "sample_id": "locked-ood",
                "partition": "locked_test",
                "data_role": "locked_ood",
                "fold_id": None,
                "n_observations": 10,
            },
        ],
        "locked_assets_opened": True,
        "sealed_assets_opened": False,
    }
    split_path = tmp_path / "locked_split_manifest.json"
    split_path.write_text(json.dumps(split_payload, sort_keys=True), encoding="utf-8")

    artifact_path = tmp_path / "locked_artifacts" / "result.json"
    artifact_path.parent.mkdir()
    artifact_path.write_text('{"fixture":true}', encoding="utf-8")
    method_versions = {
        method_id: cell_state_freeze.BENCHMARK_IMPLEMENTATION_VERSION
        for method_id in selected_methods
    }
    run_payload = {
        "run_id": "locked-run-1",
        "phase": "locked",
        "implementation_version": cell_state_freeze.BENCHMARK_IMPLEMENTATION_VERSION,
        "benchmark_spec": locked_spec.model_dump(mode="json"),
        "benchmark_spec_ref": gate.benchmark_spec_ref,
        "benchmark_spec_sha256": gate.benchmark_spec_sha256,
        "gate_spec_ref": gate.gate_spec_id,
        "freeze_gate_sha256": freeze_gate_sha256,
        "asset_catalog_sha256": gate.asset_catalog_sha256,
        "split_manifest_sha256": _sha256(split_path),
        "reference_snapshot_ref": gate.reference_snapshot_ref,
        "reference_manifest_sha256": reference_manifest_sha256,
        "environment_spec_refs": gate.environment_spec_refs,
        "environment_spec_sha256": gate.environment_spec_sha256,
        "environment_health_record_sha256": gate.environment_health_record_sha256,
        "adapter_contract_sha256": gate.adapter_contract_sha256,
        "pilot_evidence_sha256": gate.pilot_evidence_sha256,
        "locked_assets_opened": True,
        "sealed_assets_opened": False,
        "tuning_after_lock": False,
        "artifact_hashes": {"locked_artifacts/result.json": _sha256(artifact_path)},
        "method_implementation_versions": method_versions,
    }
    run_path = tmp_path / "locked_run_manifest.json"
    run_path.write_text(json.dumps(run_payload, sort_keys=True), encoding="utf-8")

    summary = {
        "run_id": "locked-run-1",
        "benchmark_spec_ref": gate.benchmark_spec_ref,
        "locked_test_state": "passed",
        "gate_spec_ref": gate.gate_spec_id,
        "tuning_after_lock": False,
        "run_manifest_sha256": _sha256(run_path),
        "split_manifest_sha256": _sha256(split_path),
        "reference_manifest_sha256": reference_manifest_sha256,
        "gate_results": [
            {
                "metric": criterion.metric,
                "scope": criterion.scope,
                "value": criterion.pilot_observation,
                "state": "passed",
                "method_asset_pairs": [
                    {
                        "method_id": "source_specific_correlation",
                        "asset_id": "LAMANNO-2016",
                    }
                ],
            }
            for criterion in gate.criteria
            if criterion.state_id is None
        ],
        "state_method_results": {
            state_id: {
                method_id: {
                    "implementation_version": method_versions[method_id],
                    "tested_asset_ids": ["LAMANNO-2016"],
                    "metrics": {"f1": 0.80, "n": 100},
                }
                for method_id in selected_methods
            }
            for state_id in approved_states
        },
    }

    for name, payload in [
        ("biological_review.json", review.model_dump(mode="json")),
        ("locked_benchmark_summary.json", summary),
    ]:
        (tmp_path / name).write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")

    release_payload = {
        "release_manifest_id": "CELLSTATE-RELEASE-scRNA-v1.0",
        "version": "1.0.0",
        "status": release_status,
        "assay": "scRNA-seq",
        "annotation_vocabulary_ref": "BRIDGE-PD-vMB-ANNOTATION-v1.0",
        "reference_snapshot_ref": "REF-PD-vMB-CELLSTATE-v1.0",
        "measurement_spec_ref": "CELLSTATE-scRNA-v1.0",
        "benchmark_spec_ref": gate.benchmark_spec_ref,
        "biological_review_ref": review.review_record_id,
        "freeze_gate_ref": gate.gate_spec_id,
        "locked_test_state": "passed",
        "per_state_release": {
            "L1:Neuron_DA": "frozen",
            "L2:RG_mFP": "provisional_frozen",
        },
        "selected_methods": {
            "L1:Neuron_DA": selected_methods,
            "L2:RG_mFP": selected_methods,
        },
        "biological_review_sha256": _sha256(tmp_path / "biological_review.json"),
        "freeze_gate_sha256": _sha256(tmp_path / "freeze_gate.json"),
        "locked_summary_sha256": _sha256(tmp_path / "locked_benchmark_summary.json"),
        "locked_run_manifest_sha256": _sha256(run_path),
        "locked_split_manifest_sha256": _sha256(split_path),
        "reference_manifest_sha256": reference_manifest_sha256,
        "runtime_tool_version": cell_state_freeze.RUNTIME_TOOL_VERSION,
        "environment_spec_ref": cell_state_freeze.RUNTIME_ENVIRONMENT_SPEC,
        "method_implementation_versions": method_versions,
        "signatures": [],
    }
    release_hash = object_signing_hash(release_payload)
    release_payload["signatures"] = [
        _signed("bridge_scientific_lead", "bridge-reviewer", release_hash),
        _signed("chen_team_reviewer", "chen-reviewer", release_hash),
    ]
    (tmp_path / "release_manifest.json").write_text(
        json.dumps(release_payload, sort_keys=True), encoding="utf-8"
    )

    return cell_state_freeze._validate_release_bundle_structure(
        tmp_path, reviewer_registry_path=reviewer_registry
    )


def test_public_release_validation_stays_blocked_without_a_locked_runner(tmp_path: Path) -> None:
    with pytest.raises(BenchmarkError) as error:
        validate_release_bundle(tmp_path)
    assert error.value.reason_code == "locked_runner_not_implemented"


def test_release_bundle_requires_matching_signed_review_gate_and_locked_summary(
    tmp_path: Path,
) -> None:
    release = _write_valid_release_bundle(tmp_path)

    assert release.status == "frozen"
    assert release.per_state_release["L2:RG_mFP"] == "provisional_frozen"


def test_release_bundle_rejects_method_not_executable_by_runtime(tmp_path: Path) -> None:
    with pytest.raises(BenchmarkError) as error:
        _write_valid_release_bundle(tmp_path, selected_method="scanvi")
    assert error.value.reason_code == "released_method_not_available_in_runtime"


def test_release_bundle_rejects_method_excluded_from_locked_source(tmp_path: Path) -> None:
    with pytest.raises(BenchmarkError) as error:
        _write_valid_release_bundle(tmp_path, selected_method="marker_program_evidence")
    assert error.value.reason_code == "released_state_gate_missing"


def test_release_bundle_rejects_a_signed_draft(tmp_path: Path) -> None:
    with pytest.raises(BenchmarkError) as error:
        _write_valid_release_bundle(tmp_path, release_status="draft")
    assert error.value.reason_code == "cell_state_release_not_frozen"


def test_release_bundle_requires_machine_verifiable_locked_run(tmp_path: Path) -> None:
    _write_valid_release_bundle(tmp_path)
    (tmp_path / "locked_run_manifest.json").unlink()

    with pytest.raises(BenchmarkError) as error:
        cell_state_freeze._validate_release_bundle_structure(
            tmp_path, reviewer_registry_path=tmp_path / "trusted-reviewers.json"
        )
    assert error.value.reason_code == "release_bundle_incomplete"


def test_release_id_cannot_escape_release_root(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BRIDGE_CELLSTATE_RELEASE_ROOT", str(tmp_path))

    with pytest.raises(BenchmarkError) as error:
        resolve_release_bundle("../forged-release")
    assert error.value.reason_code == "cell_state_release_id_invalid"


def test_release_bundle_recomputes_signed_gate_result(tmp_path: Path) -> None:
    _write_valid_release_bundle(tmp_path)
    summary_path = tmp_path / "locked_benchmark_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["gate_results"][0]["value"] = 0.1
    summary_path.write_text(json.dumps(summary, sort_keys=True), encoding="utf-8")

    release_path = tmp_path / "release_manifest.json"
    release = json.loads(release_path.read_text(encoding="utf-8"))
    release["locked_summary_sha256"] = _sha256(summary_path)
    release["signatures"] = []
    release_hash = object_signing_hash(release)
    release["signatures"] = [
        _signed("bridge_scientific_lead", "bridge-reviewer", release_hash),
        _signed("chen_team_reviewer", "chen-reviewer", release_hash),
    ]
    release_path.write_text(json.dumps(release, sort_keys=True), encoding="utf-8")

    with pytest.raises(BenchmarkError) as error:
        cell_state_freeze._validate_release_bundle_structure(
            tmp_path, reviewer_registry_path=tmp_path / "trusted-reviewers.json"
        )
    assert error.value.reason_code == "locked_benchmark_not_releasable"


def test_release_bundle_binds_gate_content_to_locked_run(tmp_path: Path) -> None:
    _write_valid_release_bundle(tmp_path)
    run_path = tmp_path / "locked_run_manifest.json"
    run = json.loads(run_path.read_text(encoding="utf-8"))
    run["pilot_evidence_sha256"] = "2" * 64
    run_path.write_text(json.dumps(run, sort_keys=True), encoding="utf-8")

    summary_path = tmp_path / "locked_benchmark_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["run_manifest_sha256"] = _sha256(run_path)
    summary_path.write_text(json.dumps(summary, sort_keys=True), encoding="utf-8")
    _resign_release(tmp_path)

    with pytest.raises(BenchmarkError) as error:
        cell_state_freeze._validate_release_bundle_structure(
            tmp_path, reviewer_registry_path=tmp_path / "trusted-reviewers.json"
        )
    assert error.value.reason_code == "locked_run_manifest_mismatch"


@pytest.mark.parametrize(
    ("field", "forged_value", "reason_code"),
    [
        (
            "annotation_vocabulary_ref",
            "BRIDGE-PD-vMB-ANNOTATION-FORGED",
            "release_annotation_review_mismatch",
        ),
        (
            "reference_snapshot_ref",
            "REF-PD-vMB-CELLSTATE-FORGED",
            "release_scientific_contract_mismatch",
        ),
        (
            "measurement_spec_ref",
            "CELLSTATE-scRNA-FORGED",
            "release_scientific_contract_mismatch",
        ),
    ],
)
def test_release_bundle_rejects_scientific_contract_relabel(
    tmp_path: Path, field: str, forged_value: str, reason_code: str
) -> None:
    _write_valid_release_bundle(tmp_path)
    release_path = tmp_path / "release_manifest.json"
    release = json.loads(release_path.read_text(encoding="utf-8"))
    release[field] = forged_value
    release_path.write_text(json.dumps(release, sort_keys=True), encoding="utf-8")
    _resign_release(tmp_path)

    with pytest.raises(BenchmarkError) as error:
        cell_state_freeze._validate_release_bundle_structure(
            tmp_path, reviewer_registry_path=tmp_path / "trusted-reviewers.json"
        )
    assert error.value.reason_code == reason_code


@pytest.mark.parametrize("binding", ["reference", "environment", "adapter"])
def test_release_bundle_rejects_gate_binding_outside_locked_spec(
    tmp_path: Path, binding: str
) -> None:
    _write_valid_release_bundle(tmp_path)
    gate_path = tmp_path / "freeze_gate.json"
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    run_path = tmp_path / "locked_run_manifest.json"
    run = json.loads(run_path.read_text(encoding="utf-8"))
    if binding == "reference":
        gate["reference_snapshot_ref"] = "REF-PD-vMB-CELLSTATE-FORGED"
        run["reference_snapshot_ref"] = gate["reference_snapshot_ref"]
    elif binding == "environment":
        gate["environment_spec_refs"] = ["ENV-CELLSTATE-FORGED"]
        gate["environment_spec_sha256"] = {"ENV-CELLSTATE-FORGED": "d" * 64}
        run["environment_spec_refs"] = gate["environment_spec_refs"]
        run["environment_spec_sha256"] = gate["environment_spec_sha256"]
    else:
        gate["adapter_contract_sha256"] = "9" * 64
        run["adapter_contract_sha256"] = gate["adapter_contract_sha256"]
    gate["signatures"] = []
    gate_hash = object_signing_hash(gate)
    gate["signatures"] = [
        _signed("bridge_scientific_lead", "bridge-reviewer", gate_hash),
        _signed("chen_team_reviewer", "chen-reviewer", gate_hash),
    ]
    gate_path.write_text(json.dumps(gate, sort_keys=True), encoding="utf-8")

    run["freeze_gate_sha256"] = _sha256(gate_path)
    run_path.write_text(json.dumps(run, sort_keys=True), encoding="utf-8")

    summary_path = tmp_path / "locked_benchmark_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["run_manifest_sha256"] = _sha256(run_path)
    summary_path.write_text(json.dumps(summary, sort_keys=True), encoding="utf-8")

    release_path = tmp_path / "release_manifest.json"
    release = json.loads(release_path.read_text(encoding="utf-8"))
    release["freeze_gate_sha256"] = _sha256(gate_path)
    release_path.write_text(json.dumps(release, sort_keys=True), encoding="utf-8")
    _resign_release(tmp_path)

    with pytest.raises(BenchmarkError) as error:
        cell_state_freeze._validate_release_bundle_structure(
            tmp_path, reviewer_registry_path=tmp_path / "trusted-reviewers.json"
        )
    assert error.value.reason_code == "freeze_gate_binding_mismatch"


def test_release_bundle_requires_global_gate_provenance(tmp_path: Path) -> None:
    _write_valid_release_bundle(tmp_path)
    summary_path = tmp_path / "locked_benchmark_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["gate_results"][0].pop("method_asset_pairs")
    summary_path.write_text(json.dumps(summary, sort_keys=True), encoding="utf-8")
    _resign_release(tmp_path)

    with pytest.raises(BenchmarkError) as error:
        cell_state_freeze._validate_release_bundle_structure(
            tmp_path, reviewer_registry_path=tmp_path / "trusted-reviewers.json"
        )
    assert error.value.reason_code == "locked_gate_provenance_missing"


def test_release_bundle_rejects_global_gate_using_lamanno_marker(
    tmp_path: Path,
) -> None:
    _write_valid_release_bundle(tmp_path)
    summary_path = tmp_path / "locked_benchmark_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["gate_results"][0]["method_asset_pairs"] = [
        {"method_id": "marker_program_evidence", "asset_id": "LAMANNO-2016"}
    ]
    summary_path.write_text(json.dumps(summary, sort_keys=True), encoding="utf-8")
    _resign_release(tmp_path)

    with pytest.raises(BenchmarkError) as error:
        cell_state_freeze._validate_release_bundle_structure(
            tmp_path, reviewer_registry_path=tmp_path / "trusted-reviewers.json"
        )
    assert error.value.reason_code == "locked_gate_uses_excluded_method"


def test_release_bundle_rejects_locked_split_from_another_catalog(tmp_path: Path) -> None:
    _write_valid_release_bundle(tmp_path)
    split_path = tmp_path / "locked_split_manifest.json"
    split = json.loads(split_path.read_text(encoding="utf-8"))
    split["input_catalog_sha256"] = "9" * 64
    split_path.write_text(json.dumps(split, sort_keys=True), encoding="utf-8")

    run_path = tmp_path / "locked_run_manifest.json"
    run = json.loads(run_path.read_text(encoding="utf-8"))
    run["split_manifest_sha256"] = _sha256(split_path)
    run_path.write_text(json.dumps(run, sort_keys=True), encoding="utf-8")

    summary_path = tmp_path / "locked_benchmark_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["split_manifest_sha256"] = _sha256(split_path)
    summary["run_manifest_sha256"] = _sha256(run_path)
    summary_path.write_text(json.dumps(summary, sort_keys=True), encoding="utf-8")
    _resign_release(tmp_path)

    with pytest.raises(BenchmarkError) as error:
        cell_state_freeze._validate_release_bundle_structure(
            tmp_path, reviewer_registry_path=tmp_path / "trusted-reviewers.json"
        )
    assert error.value.reason_code == "locked_split_manifest_invalid"


def test_release_bundle_recomputes_per_state_method_gate(tmp_path: Path) -> None:
    _write_valid_release_bundle(tmp_path)
    summary_path = tmp_path / "locked_benchmark_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["state_method_results"]["L1:Neuron_DA"][
        "source_specific_correlation"
    ]["metrics"]["f1"] = 0.1
    summary_path.write_text(json.dumps(summary, sort_keys=True), encoding="utf-8")
    _resign_release(tmp_path)

    with pytest.raises(BenchmarkError) as error:
        cell_state_freeze._validate_release_bundle_structure(
            tmp_path, reviewer_registry_path=tmp_path / "trusted-reviewers.json"
        )
    assert error.value.reason_code == "released_state_method_not_passed"


@pytest.mark.parametrize("support", [0, None])
def test_release_bundle_rejects_missing_or_zero_state_support(
    tmp_path: Path, support: int | None
) -> None:
    _write_valid_release_bundle(tmp_path)
    summary_path = tmp_path / "locked_benchmark_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    metrics = summary["state_method_results"]["L1:Neuron_DA"][
        "source_specific_correlation"
    ]["metrics"]
    if support is None:
        metrics.pop("n")
    else:
        metrics["n"] = support
    summary_path.write_text(json.dumps(summary, sort_keys=True), encoding="utf-8")
    _resign_release(tmp_path)

    with pytest.raises(BenchmarkError) as error:
        cell_state_freeze._validate_release_bundle_structure(
            tmp_path, reviewer_registry_path=tmp_path / "trusted-reviewers.json"
        )
    assert error.value.reason_code == "released_state_support_insufficient"


def test_approved_gate_requires_per_state_support_threshold(tmp_path: Path) -> None:
    _write_valid_release_bundle(tmp_path)
    payload = json.loads((tmp_path / "freeze_gate.json").read_text(encoding="utf-8"))
    payload["criteria"] = [
        criterion for criterion in payload["criteria"] if criterion["metric"] != "n"
    ]
    payload["signatures"] = []
    gate_hash = object_signing_hash(payload)
    payload["signatures"] = [
        _signed("bridge_scientific_lead", "bridge-reviewer", gate_hash),
        _signed("chen_team_reviewer", "chen-reviewer", gate_hash),
    ]

    with pytest.raises(ValueError, match="positive support threshold"):
        FreezeGateSpec.model_validate(payload)


def test_approved_freeze_gate_requires_all_mandatory_metrics() -> None:
    payload = {
        "gate_spec_id": "FREEZE-GATE-INCOMPLETE",
        "version": "1.0.0",
        "status": "approved",
        "benchmark_spec_ref": "CELLSTATE-BENCHMARK-scRNA-v1.0",
        "benchmark_spec_sha256": "a" * 64,
        "asset_catalog_sha256": "b" * 64,
        "reference_snapshot_ref": "REF-PD-vMB-CELLSTATE-v1.0",
        "reference_snapshot_sha256": "c" * 64,
        "environment_spec_refs": ["ENV-CELLSTATE-PY-v0.1"],
        "environment_spec_sha256": {"ENV-CELLSTATE-PY-v0.1": "d" * 64},
        "environment_health_record_sha256": "e" * 64,
        "adapter_contract_sha256": "f" * 64,
        "pilot_evidence_sha256": "1" * 64,
        "criteria": [
            {
                "metric": "exact_accuracy",
                "scope": "L1 source holdout",
                "operator": ">=",
                "threshold": 0.8,
                "rationale": "Deliberately incomplete fixture.",
            }
        ],
        "signatures": [
            _signed("bridge_scientific_lead", "bridge-reviewer", "0" * 64),
            _signed("chen_team_reviewer", "chen-reviewer", "0" * 64),
        ],
    }

    with pytest.raises(ValueError, match="missing mandatory metrics"):
        FreezeGateSpec.model_validate(payload)


def _sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resign_release(tmp_path: Path) -> None:
    release_path = tmp_path / "release_manifest.json"
    release = json.loads(release_path.read_text(encoding="utf-8"))
    release["locked_run_manifest_sha256"] = _sha256(
        tmp_path / "locked_run_manifest.json"
    )
    release["locked_summary_sha256"] = _sha256(
        tmp_path / "locked_benchmark_summary.json"
    )
    release["locked_split_manifest_sha256"] = _sha256(
        tmp_path / "locked_split_manifest.json"
    )
    release["signatures"] = []
    release_hash = object_signing_hash(release)
    release["signatures"] = [
        _signed("bridge_scientific_lead", "bridge-reviewer", release_hash),
        _signed("chen_team_reviewer", "chen-reviewer", release_hash),
    ]
    release_path.write_text(json.dumps(release, sort_keys=True), encoding="utf-8")
