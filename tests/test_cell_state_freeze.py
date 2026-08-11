from __future__ import annotations

import base64
import hashlib
import json
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


def _asset_catalog(tmp_path: Path) -> Path:
    payload = {
        "assets": [
            {
                "asset_id": "CHEN-vMB-scRNA",
                "source_family_id": "CHEN-VMB",
                "assay": "scRNA-seq",
                "data_role": "labeled_reference",
                "path": str(tmp_path / "chen.tsv"),
                "sample_column": "sample_id",
                "label_column": "cell_type",
            },
            {
                "asset_id": "GSE190729",
                "source_family_id": "GSE190729",
                "assay": "scRNA-seq",
                "data_role": "development_ood",
                "path": str(tmp_path / "ood.tsv"),
                "sample_column": "sample_id",
            },
            {
                "asset_id": "LAMANNO-2016",
                "source_family_id": "LAMANNO-2016",
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
                "assay": "scRNA-seq",
                "data_role": "labeled_reference",
                "path": str(path),
                "sample_column": "sample_id",
                "label_column": "cell_type",
                "label_level": "L1",
                "matrix_location": "X",
                "matrix_semantics": "raw_counts",
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
    spec = load_pilot_benchmark_spec()
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


def test_pilot_run_rejects_catalog_changed_after_split(tmp_path: Path) -> None:
    _, catalog_path = _write_expression_fixture(tmp_path)
    spec = load_pilot_benchmark_spec().model_copy(
        update={
            "methods": ["source_specific_correlation"],
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
    assert error.value.reason_code == "benchmark_asset_catalog_checksum_mismatch"


def test_locked_prepare_requires_an_approved_gate(tmp_path: Path) -> None:
    spec = load_pilot_benchmark_spec().model_copy(update={"phase": "locked"})
    gate = FreezeGateSpec(
        gate_spec_id="FREEZE-GATE-CELLSTATE-scRNA-v1-draft",
        version="0.1.0",
        status="proposed",
        benchmark_spec_ref=spec.benchmark_spec_id,
        criteria=[],
    )

    with pytest.raises(BenchmarkError, match="locked_test_not_authorized"):
        prepare_benchmark_split(spec, _asset_catalog(tmp_path), freeze_gate=gate)


def test_locked_prepare_rejects_placeholder_signature_hashes(tmp_path: Path) -> None:
    spec = load_pilot_benchmark_spec().model_copy(update={"phase": "locked"})
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
            _asset_catalog(tmp_path),
            freeze_gate=gate,
            reviewer_registry_path=_write_reviewer_registry(tmp_path),
        )
    assert error.value.reason_code == "reviewer_signature_identity_mismatch"


def test_locked_prepare_rejects_invalid_cryptographic_signature(tmp_path: Path) -> None:
    spec = load_pilot_benchmark_spec().model_copy(update={"phase": "locked"})
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
            _asset_catalog(tmp_path),
            freeze_gate=gate,
            reviewer_registry_path=_write_reviewer_registry(tmp_path),
        )
    assert error.value.reason_code == "reviewer_signature_invalid"


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


def test_pilot_reuses_a_valid_exchange_bundle(tmp_path: Path, monkeypatch) -> None:
    _, catalog_path = _write_expression_fixture(tmp_path)
    spec = load_pilot_benchmark_spec().model_copy(
        update={
            "methods": ["source_specific_correlation"],
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
                "assay": "scRNA-seq",
                "data_role": role,
                "path": str(path),
                "sample_column": "sample_id",
                "label_level": "L1",
                "matrix_location": "X",
                "matrix_semantics": "raw_counts",
                "metadata_columns": ["timepoint"],
            }
        )
    catalog_path.write_text(yaml.safe_dump(catalog, sort_keys=False), encoding="utf-8")
    spec = load_pilot_benchmark_spec().model_copy(
        update={
            "methods": ["source_specific_correlation"],
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
            "assay": "scRNA-seq",
            "data_role": "development_ood",
            "path": str(path),
            "sample_column": "sample_id",
            "label_level": "L1",
            "matrix_location": "X",
            "matrix_semantics": "raw_counts",
        }
    )
    catalog_path.write_text(yaml.safe_dump(catalog, sort_keys=False), encoding="utf-8")
    spec = load_pilot_benchmark_spec().model_copy(
        update={
            "methods": ["marker_program_evidence"],
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
            "assay": "scRNA-seq",
            "data_role": "development_ood",
            "path": str(path),
            "sample_id_value": "dataset-only",
            "label_level": "L1",
            "matrix_location": "X",
            "matrix_semantics": "raw_counts",
        }
    )
    catalog_path.write_text(yaml.safe_dump(catalog, sort_keys=False), encoding="utf-8")
    spec = load_pilot_benchmark_spec().model_copy(
        update={
            "methods": ["source_specific_correlation"],
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
                "assay": "scRNA-seq",
                "data_role": "labeled_reference",
                "path": str(path),
                "sample_column": "Sample",
                "label_column": "subtype",
                "parent_label_column": "cell_type",
                "label_level": "L2",
                "filters": {"system": ["sc_RNA_seq"]},
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
        }
    )

    split = prepare_benchmark_split(spec, catalog_path)

    assert {record.sample_id for record in split.records} == {
        "donor-1",
        "donor-2",
        "donor-3",
    }


def test_summary_registers_external_adapter_metadata_without_extra_evidence_vote(
    tmp_path: Path,
) -> None:
    _, catalog_path = _write_expression_fixture(tmp_path)
    spec = load_pilot_benchmark_spec().model_copy(
        update={
            "methods": ["source_specific_correlation", "scanvi", "scconform_calibration"],
            "development_ood_asset_ids": [],
            "behavior_only_asset_ids": [],
        }
    )
    split = prepare_benchmark_split(spec, catalog_path)
    result = run_pilot_benchmark(spec, catalog_path, split, tmp_path / "run")
    run_dir = Path(result["run_dir"])
    baseline = pd.read_parquet(run_dir / "predictions" / "source_specific_correlation.parquet")
    scanvi = baseline.copy()
    scanvi_path = run_dir / "predictions" / "scanvi--CHEN-vMB-scRNA.parquet"
    scanvi.to_parquet(scanvi_path, index=False)
    (run_dir / "predictions" / "scanvi--CHEN-vMB-scRNA.parquet.metadata.json").write_text(
        json.dumps(
            {
                "adapter": "scanvi",
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
    calibrated = scanvi.loc[scanvi["partition"].eq("test")].copy()
    calibrated["assignment_state"] = "conformal_singleton"
    calibrated.to_parquet(
        run_dir / "predictions" / "scconform_calibration.parquet", index=False
    )
    (run_dir / "predictions" / "scconform_calibration.parquet.metadata.json").write_text(
        json.dumps(
                {
                "adapter": "scconform_calibration",
                "evidence_family": "latent_reference_mapping",
                "probability_semantics": "prediction_set",
                "independent_evidence_vote": False,
                "base_adapter": "scanvi",
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


def test_summary_reads_external_tsv_without_arrow_dependency(tmp_path: Path) -> None:
    _, catalog_path = _write_expression_fixture(tmp_path)
    spec = load_pilot_benchmark_spec().model_copy(
        update={
            "methods": ["source_specific_correlation", "scanvi"],
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
                "evidence_family": "latent_reference_mapping",
                "probability_semantics": "categorical_simplex",
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


def test_science_team_cli_prepare_run_and_summarize(tmp_path: Path, capsys) -> None:
    _, catalog_path = _write_expression_fixture(tmp_path)
    spec = load_pilot_benchmark_spec().model_copy(
        update={
            "methods": ["source_specific_correlation"],
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
    gate_payload = {
        "gate_spec_id": "FREEZE-GATE-CELLSTATE-scRNA-v1.0",
        "version": "1.0.0",
        "status": "approved",
        "benchmark_spec_ref": "CELLSTATE-BENCHMARK-scRNA-v1.0",
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
        ],
        "signatures": [],
    }
    gate_hash = object_signing_hash(gate_payload)
    gate_payload["signatures"] = [
        _signed("bridge_scientific_lead", "bridge-reviewer", gate_hash),
        _signed("chen_team_reviewer", "chen-reviewer", gate_hash),
    ]
    gate = FreezeGateSpec.model_validate(gate_payload)
    reference_manifest_sha256 = "d" * 64

    split_payload = {
        "split_manifest_id": "CELLSTATE-LOCKED-SPLIT-fixture",
        "benchmark_spec_ref": gate.benchmark_spec_ref,
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
    method_versions = {selected_method: cell_state_freeze.BENCHMARK_IMPLEMENTATION_VERSION}
    run_payload = {
        "run_id": "locked-run-1",
        "phase": "locked",
        "implementation_version": cell_state_freeze.BENCHMARK_IMPLEMENTATION_VERSION,
        "benchmark_spec_ref": gate.benchmark_spec_ref,
        "gate_spec_ref": gate.gate_spec_id,
        "split_manifest_sha256": _sha256(split_path),
        "reference_manifest_sha256": reference_manifest_sha256,
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
            }
            for criterion in gate.criteria
        ],
        "state_method_results": {
            state_id: {
                selected_method: {
                    "state": "passed",
                    "implementation_version": method_versions[selected_method],
                }
            }
            for state_id in approved_states
        },
    }

    for name, payload in [
        ("biological_review.json", review.model_dump(mode="json")),
        ("freeze_gate.json", gate.model_dump(mode="json")),
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
            "L1:Neuron_DA": [selected_method],
            "L2:RG_mFP": [selected_method],
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

    return validate_release_bundle(tmp_path, reviewer_registry_path=reviewer_registry)


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


def test_release_bundle_rejects_a_signed_draft(tmp_path: Path) -> None:
    with pytest.raises(BenchmarkError) as error:
        _write_valid_release_bundle(tmp_path, release_status="draft")
    assert error.value.reason_code == "cell_state_release_not_frozen"


def test_release_bundle_requires_machine_verifiable_locked_run(tmp_path: Path) -> None:
    _write_valid_release_bundle(tmp_path)
    (tmp_path / "locked_run_manifest.json").unlink()

    with pytest.raises(BenchmarkError) as error:
        validate_release_bundle(
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
        validate_release_bundle(
            tmp_path, reviewer_registry_path=tmp_path / "trusted-reviewers.json"
        )
    assert error.value.reason_code == "locked_benchmark_not_releasable"


def test_approved_freeze_gate_requires_all_mandatory_metrics() -> None:
    payload = {
        "gate_spec_id": "FREEZE-GATE-INCOMPLETE",
        "version": "1.0.0",
        "status": "approved",
        "benchmark_spec_ref": "CELLSTATE-BENCHMARK-scRNA-v1.0",
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
