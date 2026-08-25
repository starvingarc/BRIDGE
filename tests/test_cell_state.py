from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import anndata as ad
import numpy as np
import pandas as pd
import pytest
import yaml
from pydantic import ValidationError
from scipy import sparse

from bridge.tool_packages._configurable_contracts import observation_ids_sha256
from bridge.tool_packages.p0_02_cell_state import executor as cell_state_executor
from bridge.tool_packages.p0_02_cell_state.measurement_specs import (
    load_measurement_spec,
)
from bridge.tool_packages.p0_02_cell_state.reference import (
    DENIED_SOURCE_FAMILIES,
    ReferenceError,
    build_reference_snapshot,
    canonicalize_source_family_id,
    load_packaged_vocabulary,
    validate_reference_snapshot,
)
from bridge.toolkit.contracts import (
    DataViewBinding,
    ExecutionState,
    InputAsset,
    QCReadinessProfileV2,
    ReferenceManifest,
    ToolRequest,
)
from bridge.toolkit.registry import ToolRegistry


MARKERS = [
    "TH",
    "DDC",
    "SLC6A3",
    "NR4A2",
    "PITX3",
    "TPH2",
    "AQP4",
    "ALDH1L1",
    "SLC1A3",
    "GFAP",
    "SOX10",
]
GENES = MARKERS + [f"G{index:03d}" for index in range(109)]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _expression(label: str, *, replicate: int = 0) -> np.ndarray:
    values = np.ones(len(GENES), dtype=np.int64)
    if label == "Neuron_DA":
        values[11:65] = 20 + replicate
        values[:5] = 30
    elif label == "Astrocyte":
        values[65:] = 20 + replicate
        values[6:10] = 30
    elif label == "Radial_Glia":
        values[25:90] = 16 + replicate
    elif label == "RG_mFP":
        values[25:58] = 24 + replicate
    elif label == "RG_mBMP":
        values[58:90] = 24 + replicate
    elif label == "Nb_mFP":
        values[18:48] = 24 + replicate
    elif label == "Nb_mBMP":
        values[78:108] = 24 + replicate
    return values


def _write_reference(path: Path, *, assay: str, swap_labels: bool = False, alias: bool = False) -> Path:
    labels = ["Neuron_DA", "Astrocyte", "Radial_Glia"] * 4
    matrix = np.vstack([_expression(label, replicate=index % 2) for index, label in enumerate(labels)])
    reported = labels.copy()
    if swap_labels:
        reported = ["Astrocyte" if label == "Neuron_DA" else "Neuron_DA" for label in labels]
    if alias:
        reported[0] = "Neuron_Chat"
    obs = pd.DataFrame(
        {
        "sample": ["donor-a"] * 6 + ["donor-b"] * 6,
            "label": reported,
            "assay": assay,
        },
        index=[f"ref-{path.stem}-{index}" for index in range(12)],
    )
    ad.AnnData(sparse.csr_matrix(matrix), obs=obs, var=pd.DataFrame(index=GENES)).write_h5ad(path)
    return path


def _write_l2_reference(path: Path) -> Path:
    labels = ["RG_mFP", "RG_mBMP", "Nb_mFP", "Nb_mBMP", "Pericyte"] * 2
    matrix = np.vstack(
        [_expression(label if label != "Pericyte" else "Radial_Glia", replicate=index % 2) for index, label in enumerate(labels)]
    )
    obs = pd.DataFrame(
        {"sample": ["donor-a"] * 5 + ["donor-b"] * 5, "subtype": labels},
        index=[f"l2-{index}" for index in range(10)],
    )
    ad.AnnData(sparse.csr_matrix(matrix), obs=obs, var=pd.DataFrame(index=GENES)).write_h5ad(path)
    return path


def _write_query(
    path: Path,
    *,
    assay: str = "scRNA-seq",
    genes: list[str] | None = None,
    labels: list[str] | None = None,
) -> Path:
    selected = genes or GENES
    indices = [GENES.index(gene) for gene in selected]
    labels = labels or ["Neuron_DA", "Neuron_DA", "Astrocyte", "Astrocyte"]
    matrix = np.vstack([_expression(label, replicate=index % 2)[indices] for index, label in enumerate(labels)])
    obs = pd.DataFrame(index=[f"query-{index}" for index in range(len(labels))])
    ad.AnnData(sparse.csr_matrix(matrix), obs=obs, var=pd.DataFrame(index=selected)).write_h5ad(path)
    return path


def _build_snapshot(tmp_path: Path, monkeypatch, *, conflict: bool = False, alias: bool = False) -> Path:
    source_a = _write_reference(tmp_path / "source-a.h5ad", assay="scRNA-seq", alias=alias)
    source_b = _write_reference(tmp_path / "source-b.h5ad", assay="scRNA-seq", swap_labels=conflict)
    source_sn = _write_reference(tmp_path / "source-sn.h5ad", assay="snRNA-seq")
    source_l2 = _write_l2_reference(tmp_path / "source-l2.h5ad")
    catalog = {
        "snapshot_id": "REF-PD-vMB-CELLSTATE-v0.2",
        "version": "0.1.0",
        "status": "candidate",
        "measurement_spec_ids": ["CELLSTATE-scRNA-shadow-v0.1", "CELLSTATE-snRNA-shadow-v0.1"],
        "prohibited_source_families": ["STUDER_CAPYBARABRAIN", "EMTAB14729"],
        "sources": [
            _source("REF-CHEN-SC", "CHEN", source_a, "scRNA-seq"),
            _source("REF-LAMANNO", "LAMANNO", source_b, "scRNA-seq"),
            _source("REF-CHEN-SN", "CHEN", source_sn, "snRNA-seq"),
            {
                **_source("REF-CHEN-L2-SC", "CHEN", source_l2, "scRNA-seq"),
                "label_level": "L2",
                "role": "refinement",
                "label_column": "subtype",
            },
            {
                "source_id": "REF-BRAUN-CONTEXT",
                "source_family_id": "BRAUN",
                "evidence_family_id": "EF-BRAUN",
                "assay": "scRNA-seq",
                "anatomy": "first-trimester whole brain",
                "developmental_time": "PCW5-14",
                "label_level": "L1",
                "role": "context",
                "status": "planned",
            },
        ],
    }
    catalog_path = tmp_path / "catalog.yaml"
    catalog_path.write_text(yaml.safe_dump(catalog, sort_keys=False), encoding="utf-8")
    root = tmp_path / "references"
    snapshot = root / catalog["snapshot_id"]
    build_reference_snapshot(catalog_path, snapshot)
    monkeypatch.setenv("BRIDGE_REFERENCE_ROOT", str(root))
    monkeypatch.setenv("BRIDGE_ALLOW_CANDIDATE_REFERENCES", "1")
    return snapshot


def _source(source_id: str, family: str, path: Path, assay: str) -> dict:
    return {
        "source_id": source_id,
        "source_family_id": family,
        "evidence_family_id": f"EF-{family}",
        "asset_path": str(path),
        "assay": assay,
        "anatomy": "human fetal ventral midbrain",
        "developmental_time": "GW/PCW reference interval",
        "label_level": "L1",
        "role": "primary",
        "status": "candidate",
        "label_column": "label",
        "sample_column": "sample",
        "matrix_location": "X",
        "matrix_semantics": "raw_counts",
    }


def _request(tmp_path: Path, query: Path, *, assay: str = "scRNA-seq") -> ToolRequest:
    spec = "CELLSTATE-scRNA-shadow-v0.1" if assay == "scRNA-seq" else "CELLSTATE-snRNA-shadow-v0.1"
    return ToolRequest(
        request_id=f"cell-state-{assay}",
        tool_id="P0-02",
        output_dir=(tmp_path / "results").resolve(),
        assets=[
            InputAsset(
                asset_id="query-product",
                path=query.resolve(),
                format="h5ad",
                input_level="count_ready",
                matrix_location="X",
                matrix_semantics="raw_counts",
                assay=assay,
                metadata={
                    "qc_profile_ref": os.environ["BRIDGE_TEST_QC_PROFILE_REF"],
                    "source_family_id": "QUERY-INDEPENDENT",
                },
            )
        ],
        measurement_spec_ref=spec,
        parameters={"chunk_size": 2, "workers": 2},
    )


def _configure_qc_catalog(
    tmp_path: Path,
    monkeypatch,
    query: Path,
    *,
    assay: str = "scRNA-seq",
    include_v2: bool = True,
) -> tuple[Path, Path | None]:
    qc_request = ToolRequest(
        request_id=f"qc-{query.stem}",
        tool_id="P0-01",
        output_dir=(tmp_path / f"qc-{query.stem}").resolve(),
        assets=[
            InputAsset(
                asset_id="query-product",
                path=query.resolve(),
                format="h5ad",
                input_level="count_ready",
                matrix_location="X",
                matrix_semantics="raw_counts",
                assay=assay,
                metadata={"sample_id": "sample-test", "capture_id": "capture-test"},
            )
        ],
    )
    run = ToolRegistry.load_default().run(qc_request)
    profile_artifact = next(item for item in run.artifacts if item.kind == "qc_profile")
    profile_ref = run.result["profile_id"]
    record = {
        "path": str(profile_artifact.path),
        "sha256": profile_artifact.sha256,
    }
    profile_v2_path = None
    if include_v2:
        query_adata = ad.read_h5ad(query)
        selected_view = DataViewBinding(
            view_id=f"data-view:{profile_ref}:all-observations",
            view_kind="all_observations",
            artifact_id="input-asset:query-product",
            sha256=_sha256(query),
            parent_asset_id="query-product",
            parent_asset_sha256=_sha256(query),
            matrix_location="X",
            matrix_semantics="raw_counts",
            n_observations=int(query_adata.n_obs),
            observation_ids_sha256=observation_ids_sha256(
                query_adata.obs_names.astype(str).tolist()
            ),
        )
        profile_v2 = QCReadinessProfileV2.model_validate(
            {
                **run.result,
                "measurement_spec_version": None,
                "selected_data_view": selected_view,
            }
        )
        profile_v2_path = tmp_path / f"qc-profile-v2-{query.stem}.json"
        profile_v2_path.write_text(
            json.dumps(
                profile_v2.model_dump(mode="json"),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        record.update(
            {
                "v2_path": str(profile_v2_path),
                "v2_sha256": _sha256(profile_v2_path),
            }
        )
    catalog_path = tmp_path / f"qc-catalog-{query.stem}.json"
    catalog_path.write_text(
        json.dumps({"profiles": {profile_ref: record}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("BRIDGE_QC_PROFILE_CATALOG", str(catalog_path))
    monkeypatch.setenv("BRIDGE_TEST_QC_PROFILE_REF", profile_ref)
    return catalog_path, profile_v2_path


def test_vocabulary_has_fixed_hierarchy_alias_and_unresolved_conflict() -> None:
    vocabulary = load_packaged_vocabulary()
    assert len([label for label in vocabulary.labels if label.level == "L1"]) == 18
    assert len([label for label in vocabulary.labels if label.level == "L2"]) == 14
    assert len([label for label in vocabulary.labels if label.level == "L3"]) == 16
    assert vocabulary.alias_map["Neuron_Chat"] == "Neuron_ChAT"
    pericyte = next(label for label in vocabulary.labels if label.state_id == "L2:Pericyte_conflict")
    assert pericyte.status == "unresolved"


def test_source_aware_run_emits_shadow_support_and_preserves_input(tmp_path: Path, monkeypatch) -> None:
    _build_snapshot(tmp_path, monkeypatch)
    query = _write_query(tmp_path / "query.h5ad")
    _configure_qc_catalog(tmp_path, monkeypatch, query)
    before = _sha256(query)

    run = ToolRegistry.load_default().run(_request(tmp_path, query))

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert _sha256(query) == before
    assert run.result["score_state"] == "shadow"
    assert run.result["domain_score"] is None
    assert run.result["source_support"]["primary_sources"] == ["REF-CHEN-SC", "REF-LAMANNO"]
    assert run.result["prediction_sets"]["state_counts"] == {"consensus_supported": 4}
    assert run.result["prediction_sets"]["open_set_state"] == "not_assessed"
    assert run.result["method_outputs"] == {
        "marker_program_evidence": {"release_state": "shadow"},
        "source_specific_correlation": {"release_state": "shadow"},
    }
    assert run.result["assignment_state"]["state"] == "candidate_prediction_set"
    assert run.result["calibration"]["state"] == "not_assessed"
    assert run.result["method_disagreement"]["state_counts"] == {
        "consensus_supported": 4
    }
    assert set(run.result["per_state_release"].values()) <= {"shadow", "unavailable"}
    assert {artifact.kind for artifact in run.artifacts} >= {
        "cell_state_evidence",
        "reference_support",
        "marker_program_evidence",
        "shadow_composition",
        "visualization_svg",
        "visualization_png",
        "manifest",
    }
    support = pd.read_parquet(next(item.path for item in run.artifacts if item.kind == "reference_support"))
    assert set(support["source_id"]) == {"REF-CHEN-SC", "REF-LAMANNO"}
    assert set(support.loc[support["label_level"] == "L1", "label"]) == {
        "L1:Astrocyte",
        "L1:Neuron_DA",
        "L1:Radial_Glia",
    }
    profile_v3_artifact = next(
        item for item in run.artifacts if item.kind == "cell_state_profile_v3"
    )
    profile_v3 = json.loads(profile_v3_artifact.path.read_text(encoding="utf-8"))
    assert profile_v3["input_data_view"] == {
        "view_id": profile_v3["input_data_view"]["view_id"],
        "view_kind": "all_observations",
        "artifact_id": "input-asset:query-product",
        "sha256": _sha256(query),
        "parent_asset_id": "query-product",
        "parent_asset_sha256": _sha256(query),
        "matrix_location": "X",
        "matrix_semantics": "raw_counts",
        "n_observations": 4,
        "observation_ids_sha256": observation_ids_sha256(
            [f"query-{index}" for index in range(4)]
        ),
        "sample_or_preparation_ref": None,
        "selection_spec_ref": None,
        "biological_unit_manifest_ref": None,
        "biological_unit_manifest_sha256": None,
    }
    assert profile_v3["n_observations"] == profile_v3["input_data_view"]["n_observations"]
    assert profile_v3["denominator"] == "selected_data_view"
    assert profile_v3["measurement_spec_version"] == "0.1.0"
    measurement_spec = load_measurement_spec(
        "CELLSTATE-scRNA-shadow-v0.1"
    )
    assert measurement_spec is not None
    expected_measurement_spec_sha256 = hashlib.sha256(
        json.dumps(
            measurement_spec.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
            default=str,
        ).encode("utf-8")
    ).hexdigest()
    assert (
        profile_v3["measurement_spec_sha256"]
        == expected_measurement_spec_sha256
    )
    assert profile_v3["annotation_vocabulary_version"] == "0.1.0"
    assert len(profile_v3["annotation_vocabulary_sha256"]) == 64
    assert profile_v3["reference_manifest_version"] == "0.1.0"
    assert len(profile_v3["reference_manifest_sha256"]) == 64
    assert profile_v3["open_set_state"] == "not_assessed"
    assert profile_v3["calibration_state"] == "not_assessed"
    assert profile_v3["producer_run_ref"] == run.run_id
    assert profile_v3["producer_tool_id"] == "P0-02"
    assert profile_v3["producer_tool_version"] == run.tool_version
    records = profile_v3["composition"]["records"]
    assert {record["label_level"] for record in records} == {"L1"}
    assert {record["denominator"] for record in records} == {
        profile_v3["input_data_view"]["n_observations"]
    }
    assert {
        record["state_evidence_state"]
        for record in records
        if record["view"] in {"source_specific", "consensus_supported_only"}
    } == {"candidate"}
    assert all(
        record["state_evidence_state"] != "assigned" for record in records
    )
    legacy_profile = json.loads(
        next(
            item.path for item in run.artifacts if item.kind == "cell_state_profile"
        ).read_text(encoding="utf-8")
    )
    assert "measurement_spec_version" not in legacy_profile
    assert all(
        "state_evidence_state" not in record
        for record in legacy_profile["composition"]["records"]
    )
    legacy_manifest = json.loads(
        next(item.path for item in run.artifacts if item.kind == "manifest").read_text(
            encoding="utf-8"
        )
    )
    manifest_profile_v3 = next(
        item
        for item in legacy_manifest["artifacts"]
        if item["kind"] == "cell_state_profile_v3"
    )
    assert manifest_profile_v3["sha256"] == profile_v3_artifact.sha256
    assert manifest_profile_v3["size_bytes"] == profile_v3_artifact.path.stat().st_size
    assert legacy_manifest["measurement_spec_sha256"] == (
        expected_measurement_spec_sha256
    )


def test_reference_build_normalizes_neuron_chat_alias(tmp_path: Path, monkeypatch) -> None:
    snapshot = _build_snapshot(tmp_path, monkeypatch, alias=True)

    manifest = validate_reference_snapshot(snapshot)
    chen = next(profile for profile in manifest.profiles if profile.source_id == "REF-CHEN-SC")

    assert "L1:Neuron_ChAT" in chen.labels
    assert DENIED_SOURCE_FAMILIES.issubset(set(manifest.prohibited_source_families))


def test_measurement_specs_share_complete_competitor_reference_denylist() -> None:
    spec_root = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "bridge"
        / "tool_packages"
        / "p0_02_cell_state"
        / "measurement_specs"
    )
    expected_aliases = {"HDNA", "STUDERHDNA", "FETALATLAS", "STUDERFETALATLAS"}

    assert expected_aliases <= DENIED_SOURCE_FAMILIES
    for filename in (
        "cell_state_scrna_shadow_v0.1.yaml",
        "cell_state_snrna_shadow_v0.1.yaml",
    ):
        spec = yaml.safe_load((spec_root / filename).read_text(encoding="utf-8"))
        assert set(spec["exclusion_rules"]["competitor_source_families"]) == set(
            DENIED_SOURCE_FAMILIES
        )


@pytest.mark.parametrize(
    "source_family_id",
    [
        " hdna ",
        "HdNa",
        "CapybaraBrain ",
        "capybara-brain",
        "FETAL_ATLAS ",
        "fetal-atlas",
        "fetal atlas",
        "Studer_Fetal-Atlas ",
    ],
)
def test_competitor_atlas_aliases_are_rejected_from_reference_build(
    tmp_path: Path, monkeypatch, source_family_id: str
) -> None:
    _build_snapshot(tmp_path, monkeypatch)
    catalog = yaml.safe_load((tmp_path / "catalog.yaml").read_text(encoding="utf-8"))
    catalog.pop("prohibited_source_families")
    competitor = dict(catalog["sources"][0])
    competitor.update(
        {
            "source_id": "AAA-COMPETITOR-ALIAS",
            "source_family_id": source_family_id,
            "evidence_family_id": "EF-COMPETITOR-ATLAS",
        }
    )
    catalog["sources"].append(competitor)
    path = tmp_path / "competitor-alias.yaml"
    path.write_text(yaml.safe_dump(catalog, sort_keys=False), encoding="utf-8")

    with pytest.raises(ReferenceError) as error:
        build_reference_snapshot(path, tmp_path / "competitor-alias-snapshot")
    assert error.value.reason_code == "prohibited_reference_source_family"


def test_source_family_canonicalization_does_not_reject_unrelated_prefixes() -> None:
    assert canonicalize_source_family_id(" CapybaraBrain ") == "CAPYBARABRAIN"
    assert canonicalize_source_family_id("capybara-brain") == "CAPYBARABRAIN"
    assert canonicalize_source_family_id("FETAL_ATLAS") == "FETALATLAS"
    assert canonicalize_source_family_id("fetal-atlas ") == "FETALATLAS"
    assert canonicalize_source_family_id("HDNA-independent") == "HDNAINDEPENDENT"
    assert canonicalize_source_family_id("HDNA-independent") not in DENIED_SOURCE_FAMILIES


def test_manifest_prohibited_source_families_are_canonicalized(
    tmp_path: Path, monkeypatch
) -> None:
    _build_snapshot(tmp_path, monkeypatch)
    catalog = yaml.safe_load((tmp_path / "catalog.yaml").read_text(encoding="utf-8"))
    catalog["prohibited_source_families"] = [
        " custom-family ",
        "Studer_Capybara-Brain ",
    ]
    path = tmp_path / "canonical-prohibited-catalog.yaml"
    path.write_text(yaml.safe_dump(catalog, sort_keys=False), encoding="utf-8")

    manifest = build_reference_snapshot(path, tmp_path / "canonical-prohibited-snapshot")

    assert set(manifest.prohibited_source_families) == DENIED_SOURCE_FAMILIES | {
        "CUSTOMFAMILY"
    }


def test_reference_snapshot_is_immutable_after_manifest_creation(tmp_path: Path, monkeypatch) -> None:
    snapshot = _build_snapshot(tmp_path, monkeypatch)

    with pytest.raises(ReferenceError) as error:
        build_reference_snapshot(tmp_path / "catalog.yaml", snapshot)
    assert error.value.reason_code == "reference_snapshot_already_exists"


def test_competitor_source_is_rejected_even_when_catalog_omits_denylist(tmp_path: Path, monkeypatch) -> None:
    _build_snapshot(tmp_path, monkeypatch)
    catalog = yaml.safe_load((tmp_path / "catalog.yaml").read_text(encoding="utf-8"))
    catalog.pop("prohibited_source_families")
    competitor = dict(catalog["sources"][0])
    competitor.update(
        {
            "source_id": "AAA-COMPETITOR",
            "source_family_id": "STUDER",
            "evidence_family_id": "EF-COMPETITOR",
        }
    )
    catalog["sources"].append(competitor)
    path = tmp_path / "competitor-catalog.yaml"
    path.write_text(yaml.safe_dump(catalog, sort_keys=False), encoding="utf-8")

    with pytest.raises(ReferenceError) as error:
        build_reference_snapshot(path, tmp_path / "competitor-snapshot")
    assert error.value.reason_code == "prohibited_reference_source_family"


def test_candidate_reference_requires_explicit_science_mode(tmp_path: Path, monkeypatch) -> None:
    _build_snapshot(tmp_path, monkeypatch)
    query = _write_query(tmp_path / "query.h5ad")
    _configure_qc_catalog(tmp_path, monkeypatch, query)
    monkeypatch.delenv("BRIDGE_ALLOW_CANDIDATE_REFERENCES")

    eligibility = ToolRegistry.load_default().check_eligibility(_request(tmp_path, query))

    assert eligibility.eligible is False
    assert "reference_snapshot_not_frozen" in eligibility.reason_codes


def test_qc_profile_must_bind_the_same_input_hash(tmp_path: Path, monkeypatch) -> None:
    _build_snapshot(tmp_path, monkeypatch)
    original = _write_query(tmp_path / "query-original.h5ad")
    _configure_qc_catalog(tmp_path, monkeypatch, original)
    changed = _write_query(tmp_path / "query-changed.h5ad")
    adata = ad.read_h5ad(changed)
    adata.X[0, 0] = adata.X[0, 0] + 1
    adata.write_h5ad(changed)

    eligibility = ToolRegistry.load_default().check_eligibility(_request(tmp_path, changed))

    assert eligibility.eligible is False
    assert "qc_profile_binding_mismatch" in eligibility.reason_codes


def test_missing_qc_v2_keeps_v01_run_and_reports_handoff_unavailable(
    tmp_path: Path, monkeypatch
) -> None:
    _build_snapshot(tmp_path, monkeypatch)
    query = _write_query(tmp_path / "query.h5ad")
    _configure_qc_catalog(tmp_path, monkeypatch, query, include_v2=False)

    run = ToolRegistry.load_default().run(_request(tmp_path, query))

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert "cell_state_profile_v3" not in {item.kind for item in run.artifacts}
    assert (
        "cell_state_evidence_profile_v3_unavailable:qc_profile_v2_not_resolved"
        in run.warnings
    )
    assert run.result["measurement_spec_id"] == "CELLSTATE-scRNA-shadow-v0.1"


def test_v3_sidecar_does_not_change_legacy_result_or_artifact_bytes(
    tmp_path: Path, monkeypatch
) -> None:
    _build_snapshot(tmp_path, monkeypatch)
    query = _write_query(tmp_path / "query.h5ad")
    _configure_qc_catalog(tmp_path, monkeypatch, query, include_v2=False)
    request = _request(tmp_path, query)

    legacy_only = ToolRegistry.load_default().run(request)
    legacy_hashes = {
        (item.kind, item.path.name): item.sha256
        for item in legacy_only.artifacts
        if item.kind != "manifest"
    }
    _configure_qc_catalog(tmp_path, monkeypatch, query, include_v2=True)
    with_v3 = ToolRegistry.load_default().run(request)
    with_v3_legacy_hashes = {
        (item.kind, item.path.name): item.sha256
        for item in with_v3.artifacts
        if item.kind not in {"cell_state_profile_v3", "manifest"}
    }

    assert legacy_only.result == with_v3.result
    assert legacy_hashes == with_v3_legacy_hashes
    assert {item.kind for item in with_v3.artifacts} - {
        item.kind for item in legacy_only.artifacts
    } == {"cell_state_profile_v3"}


def test_qc_v2_checksum_tampering_fails_closed(tmp_path: Path, monkeypatch) -> None:
    _build_snapshot(tmp_path, monkeypatch)
    query = _write_query(tmp_path / "query.h5ad")
    _, profile_v2_path = _configure_qc_catalog(tmp_path, monkeypatch, query)
    assert profile_v2_path is not None
    profile_v2_path.write_bytes(profile_v2_path.read_bytes() + b"tamper")

    run = ToolRegistry.load_default().run(_request(tmp_path, query))

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["qc_profile_v2_artifact_invalid"]


@pytest.mark.parametrize(
    ("catalog_field", "reason_code"),
    [
        ("path", "qc_profile_modified_during_run"),
        ("v2_path", "qc_profile_v2_modified_during_run"),
    ],
)
def test_qc_profile_replacement_during_run_fails_closed(
    tmp_path: Path,
    monkeypatch,
    catalog_field: str,
    reason_code: str,
) -> None:
    _build_snapshot(tmp_path, monkeypatch)
    query = _write_query(tmp_path / "query.h5ad")
    catalog_path, _ = _configure_qc_catalog(tmp_path, monkeypatch, query)
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    profile_ref = next(iter(catalog["profiles"]))
    artifact_path = Path(catalog["profiles"][profile_ref][catalog_field])
    original_write_outputs = cell_state_executor._write_outputs

    def write_outputs_then_replace_qc(*args, **kwargs):
        result = original_write_outputs(*args, **kwargs)
        artifact_path.write_bytes(artifact_path.read_bytes() + b"replacement")
        return result

    monkeypatch.setattr(
        cell_state_executor,
        "_write_outputs",
        write_outputs_then_replace_qc,
    )

    run = ToolRegistry.load_default().run(_request(tmp_path, query))

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == [reason_code]


def test_qc_v2_observation_digest_mismatch_fails_closed(
    tmp_path: Path, monkeypatch
) -> None:
    _build_snapshot(tmp_path, monkeypatch)
    query = _write_query(tmp_path / "query.h5ad")
    catalog_path, profile_v2_path = _configure_qc_catalog(
        tmp_path, monkeypatch, query
    )
    assert profile_v2_path is not None
    profile_v2 = json.loads(profile_v2_path.read_text(encoding="utf-8"))
    profile_v2["selected_data_view"]["observation_ids_sha256"] = "0" * 64
    profile_v2_path.write_text(
        json.dumps(profile_v2, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    profile_ref = next(iter(catalog["profiles"]))
    catalog["profiles"][profile_ref]["v2_sha256"] = _sha256(profile_v2_path)
    catalog_path.write_text(json.dumps(catalog), encoding="utf-8")

    run = ToolRegistry.load_default().run(_request(tmp_path, query))

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["qc_profile_v2_data_view_mismatch"]


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("artifact_id", "artifact:qc-output:candidate-view"),
        ("parent_asset_id", "unrelated-upload"),
        ("parent_asset_sha256", "0" * 64),
    ],
)
def test_qc_v2_selected_view_must_be_the_exact_input_asset(
    tmp_path: Path,
    monkeypatch,
    field: str,
    invalid_value: str,
) -> None:
    _build_snapshot(tmp_path, monkeypatch)
    query = _write_query(tmp_path / "query.h5ad")
    catalog_path, profile_v2_path = _configure_qc_catalog(
        tmp_path, monkeypatch, query
    )
    assert profile_v2_path is not None
    profile_v2 = json.loads(profile_v2_path.read_text(encoding="utf-8"))
    profile_v2["selected_data_view"][field] = invalid_value
    profile_v2_path.write_text(
        json.dumps(profile_v2, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    profile_ref = next(iter(catalog["profiles"]))
    catalog["profiles"][profile_ref]["v2_sha256"] = _sha256(profile_v2_path)
    catalog_path.write_text(json.dumps(catalog), encoding="utf-8")

    run = ToolRegistry.load_default().run(_request(tmp_path, query))

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["qc_profile_v2_binding_mismatch"]


def test_source_conflict_is_visible_and_not_resolved_by_vote(tmp_path: Path, monkeypatch) -> None:
    _build_snapshot(tmp_path, monkeypatch, conflict=True)
    query = _write_query(tmp_path / "query.h5ad")
    _configure_qc_catalog(tmp_path, monkeypatch, query)

    run = ToolRegistry.load_default().run(_request(tmp_path, query))

    assert run.result["prediction_sets"]["state_counts"] == {"source_conflict": 4}
    evidence = pd.read_parquet(next(item.path for item in run.artifacts if item.kind == "cell_state_evidence"))
    assert evidence["consensus_label"].isna().all()
    assert all(len(json.loads(value)) == 2 for value in evidence["prediction_set"])
    profile_v3 = json.loads(
        next(
            item.path
            for item in run.artifacts
            if item.kind == "cell_state_profile_v3"
        ).read_text(encoding="utf-8")
    )
    conflict = next(
        record
        for record in profile_v3["composition"]["records"]
        if record["view"] == "reconciliation_state"
        and record["label"] == "source_conflict"
    )
    assert conflict["state_evidence_state"] == "unresolved"
    assert not any(
        record["view"] == "consensus_supported_only"
        for record in profile_v3["composition"]["records"]
    )


def test_matching_query_source_family_is_held_out(tmp_path: Path, monkeypatch) -> None:
    _build_snapshot(tmp_path, monkeypatch)
    query = _write_query(tmp_path / "query.h5ad")
    _configure_qc_catalog(tmp_path, monkeypatch, query)
    request = _request(tmp_path, query)
    request.assets[0].metadata["source_family_id"] = " la-manno "

    run = ToolRegistry.load_default().run(request)

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert run.result["source_support"]["primary_sources"] == ["REF-CHEN-SC"]
    assert run.result["source_support"]["held_out_sources"] == ["REF-LAMANNO"]
    assert run.result["prediction_sets"]["state_counts"] == {"single_source_supported": 4}
    assert "reference_source_family_held_out:LAMANNO" in run.warnings
    support = pd.read_parquet(next(item.path for item in run.artifacts if item.kind == "reference_support"))
    assert "REF-LAMANNO" not in set(support["source_id"])


def test_query_source_family_is_required(tmp_path: Path, monkeypatch) -> None:
    _build_snapshot(tmp_path, monkeypatch)
    query = _write_query(tmp_path / "query.h5ad")
    _configure_qc_catalog(tmp_path, monkeypatch, query)
    request = _request(tmp_path, query)
    request.assets[0].metadata.pop("source_family_id")

    eligibility = ToolRegistry.load_default().check_eligibility(request)

    assert eligibility.eligible is False
    assert "source_family_id_required" in eligibility.reason_codes


def test_l2_respects_l1_parent_and_uses_its_own_denominator(tmp_path: Path, monkeypatch) -> None:
    _build_snapshot(tmp_path, monkeypatch)
    query = _write_query(tmp_path / "query-rg.h5ad", labels=["RG_mFP", "RG_mFP"])
    _configure_qc_catalog(tmp_path, monkeypatch, query)

    run = ToolRegistry.load_default().run(_request(tmp_path, query))

    evidence = pd.read_parquet(next(item.path for item in run.artifacts if item.kind == "cell_state_evidence"))
    assert evidence["l2_prediction_set"].notna().all()
    assert all(
        all(label.startswith("L2:RG_") for label in json.loads(value))
        for value in evidence["l2_prediction_set"]
    )
    composition = pd.read_parquet(next(item.path for item in run.artifacts if item.kind == "shadow_composition"))
    assert set(composition["denominator_view"]) == {
        "all input observations",
        "L2-eligible observations",
    }
    denominators = {item.denominator for item in run.visualizations if "composition" in item.component_id}
    assert denominators == {
        "all observations in the declared post-QC input view",
        "L2-eligible observations",
    }


def test_sc_and_sn_measurement_specs_are_separate(tmp_path: Path, monkeypatch) -> None:
    _build_snapshot(tmp_path, monkeypatch)
    query = _write_query(tmp_path / "query-sn.h5ad", assay="snRNA-seq")
    _configure_qc_catalog(tmp_path, monkeypatch, query, assay="snRNA-seq")
    request = _request(tmp_path, query, assay="snRNA-seq")

    eligibility = ToolRegistry.load_default().check_eligibility(request)
    run = ToolRegistry.load_default().run(request)

    assert eligibility.eligible is True
    assert run.execution_state is ExecutionState.SUCCEEDED
    assert run.result["source_support"]["primary_sources"] == ["REF-CHEN-SN"]
    assert run.result["prediction_sets"]["state_counts"] == {"single_source_supported": 4}
    by_name = {measurement.metric_name: measurement for measurement in run.measurements}
    assert by_name["consensus_supported_fraction"].raw_value is None
    assert by_name["consensus_supported_fraction"].evidence_state == "unavailable"
    assert by_name["source_conflict_fraction"].raw_value is None


def test_modality_mismatch_is_rejected_before_execution(tmp_path: Path, monkeypatch) -> None:
    _build_snapshot(tmp_path, monkeypatch)
    query = _write_query(tmp_path / "query.h5ad")
    _configure_qc_catalog(tmp_path, monkeypatch, query)
    request = _request(tmp_path, query).model_copy(
        update={"measurement_spec_ref": "CELLSTATE-snRNA-shadow-v0.1"}
    )

    eligibility = ToolRegistry.load_default().check_eligibility(request)

    assert eligibility.eligible is False
    assert "measurement_spec_assay_mismatch" in eligibility.reason_codes


def test_existing_file_at_output_path_returns_typed_failure_without_overwrite(
    tmp_path: Path, monkeypatch
) -> None:
    _build_snapshot(tmp_path, monkeypatch)
    query = _write_query(tmp_path / "query.h5ad")
    _configure_qc_catalog(tmp_path, monkeypatch, query)
    output_path = tmp_path / "occupied-output"
    output_path.write_text("preserve-me", encoding="utf-8")
    request = _request(tmp_path, query).model_copy(
        update={"output_dir": output_path}
    )

    registry = ToolRegistry.load_default()
    eligibility = registry.check_eligibility(request)
    run = registry.run(request)

    assert eligibility.reason_codes == ["output_path_invalid"]
    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["output_path_invalid"]
    assert output_path.read_text(encoding="utf-8") == "preserve-me"


def test_low_gene_coverage_refuses_without_synthetic_measurement(tmp_path: Path, monkeypatch) -> None:
    _build_snapshot(tmp_path, monkeypatch)
    query = _write_query(tmp_path / "query-small.h5ad", genes=GENES[:20])
    _configure_qc_catalog(tmp_path, monkeypatch, query)

    run = ToolRegistry.load_default().run(_request(tmp_path, query))

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["no_applicable_reference_support"]
    assert run.measurements == []
    assert run.result is None


def test_reference_manifest_detects_checksum_tampering(tmp_path: Path, monkeypatch) -> None:
    snapshot = _build_snapshot(tmp_path, monkeypatch)
    manifest = validate_reference_snapshot(snapshot)
    matrix_file = next(profile.matrix_file for profile in manifest.profiles if profile.matrix_file)
    path = snapshot / matrix_file
    path.write_bytes(path.read_bytes() + b"tamper")

    with pytest.raises(ReferenceError, match="profiles/") as error:
        validate_reference_snapshot(snapshot)
    assert error.value.reason_code == "reference_artifact_checksum_mismatch"


def test_reference_manifest_rejects_duplicate_evidence_family_vote(tmp_path: Path, monkeypatch) -> None:
    snapshot = _build_snapshot(tmp_path, monkeypatch)
    manifest_path = snapshot / "reference_manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    original = next(item for item in payload["profiles"] if item["role"] == "primary")
    duplicate = dict(original)
    duplicate["profile_id"] = f"{original['profile_id']}-duplicate"
    duplicate["source_id"] = f"{original['source_id']}-duplicate"
    payload["profiles"].append(duplicate)
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ReferenceError) as error:
        validate_reference_snapshot(snapshot)
    assert error.value.reason_code == "duplicate_active_evidence_family"


def test_reference_contract_rejects_relative_path_escape(tmp_path: Path, monkeypatch) -> None:
    snapshot = _build_snapshot(tmp_path, monkeypatch)
    payload = json.loads((snapshot / "reference_manifest.json").read_text(encoding="utf-8"))
    active = next(item for item in payload["profiles"] if item["matrix_file"])
    active["matrix_file"] = "../private.npy"

    with pytest.raises(ValidationError, match="relative"):
        ReferenceManifest.model_validate(payload)


def test_identical_request_has_stable_artifact_hashes(tmp_path: Path, monkeypatch) -> None:
    _build_snapshot(tmp_path, monkeypatch)
    query = _write_query(tmp_path / "query.h5ad")
    _configure_qc_catalog(tmp_path, monkeypatch, query)
    request = _request(tmp_path, query)

    first = ToolRegistry.load_default().run(request)
    second = ToolRegistry.load_default().run(request)

    assert first.run_id == second.run_id
    first_hashes = {(item.kind, item.path.name): item.sha256 for item in first.artifacts}
    second_hashes = {(item.kind, item.path.name): item.sha256 for item in second.artifacts}
    assert first_hashes == second_hashes
