from __future__ import annotations

import csv
import gzip
import hashlib
import json
from importlib.resources import files
from pathlib import Path

import anndata as ad
import numpy as np
import pytest
import yaml

from bridge.tool_packages.p0_02_cell_state import birtele
from bridge.tool_packages.p0_02_cell_state.birtele import (
    BIRTELE_FILES,
    BirteleAssetError,
    prepare_birtele_asset,
)
from bridge.tool_packages.p0_02_cell_state.benchmark_cli import main as benchmark_main


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _gene_order_sha256(genes: list[str]) -> str:
    return hashlib.sha256("\n".join(genes).encode()).hexdigest()


def _write_matrix(
    path: Path,
    accession: str,
    *,
    genes: list[str] | None = None,
    values: list[list[object]] | None = None,
) -> None:
    genes = genes or ["TH", "LMX1A"]
    values = values or [[1], [2]]
    with gzip.open(path, "wt", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["", f"{accession}_cell_1"])
        for gene, row in zip(genes, values, strict=True):
            writer.writerow([gene, *row])


def _fixture_source_and_map(tmp_path: Path) -> tuple[Path, Path]:
    source_root = tmp_path / "source"
    source_dir = source_root / "processed_csv"
    source_dir.mkdir(parents=True)
    provenance_files = {
        "GSE192405_RAW.tar": b"processed archive fixture",
        "GSE192405_family.xml.tgz": b"MINiML fixture",
        "develop-149-200504-s1.pdf": b"supplement fixture",
        "TableS1.xlsx": b"table fixture",
    }
    for file_name, content in provenance_files.items():
        (source_root / file_name).write_bytes(content)
    samples = []
    for accession, file_name in BIRTELE_FILES.items():
        path = source_dir / file_name
        _write_matrix(path, accession)
        conflicts = []
        published_source = "human ventral midbrain, 14 days 3D culture"
        characteristics = {
            "tissue": "ventral midbrain",
            "culture_condition": "3D",
            "time": "14 days in culture",
        }
        if accession == "GSM5746445":
            published_source = "human ventral midbrain, 30 days 3D culture"
            characteristics = {
                "tissue": "ventral midbrain",
                "culture_condition": "2D",
                "time": "30 days in culture",
            }
            conflicts = [
                "title says 3D day 14 while GEO source says 3D day 30 and "
                "characteristics say 2D day 30"
            ]
        samples.append(
            {
                "geo_accession": accession,
                "file_name": file_name,
                "sha256": _sha256(path),
                "biosample": f"SAMN-{accession}",
                "published_title": file_name.removesuffix(".csv.gz").split("_", 1)[1],
                "published_source": published_source,
                "published_characteristics": characteristics,
                "specimen_class": "cultured_tissue",
                "biological_unit_id": None,
                "biological_unit_status": "unresolved_public_mapping",
                "technical_subdivision_id": accession,
                "replicate_eligibility": "not_estimable",
                "metadata_conflicts": conflicts,
            }
        )
    sample_map = tmp_path / "sample-map.yaml"
    sample_map.write_text(
        yaml.safe_dump(
            {
                "dataset_id": "GSE192405",
                "version": "1.0",
                "source_archive": {
                    "file_name": "GSE192405_RAW.tar",
                    "sha256": _sha256(source_root / "GSE192405_RAW.tar"),
                    "raw_reads_public": False,
                    "source_url": "https://www.ncbi.nlm.nih.gov/geo/download/?acc=GSE192405",
                },
                "metadata_sources": [
                    {
                        "file_name": "GSE192405_family.xml.tgz",
                        "relative_path": "GSE192405_family.xml.tgz",
                        "kind": "geo_miniml",
                        "sha256": _sha256(source_root / "GSE192405_family.xml.tgz"),
                        "source_url": "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE192405",
                    },
                    {
                        "file_name": "develop-149-200504-s1.pdf",
                        "relative_path": "develop-149-200504-s1.pdf",
                        "kind": "publication_supplement",
                        "sha256": _sha256(source_root / "develop-149-200504-s1.pdf"),
                        "source_url": "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC10114107/supplementaryFiles",
                    },
                    {
                        "file_name": "TableS1.xlsx",
                        "relative_path": "TableS1.xlsx",
                        "kind": "publication_table",
                        "sha256": _sha256(source_root / "TableS1.xlsx"),
                        "source_url": "https://www.biologists.com/DEV_Movies/DEV200504/TableS1.xlsx",
                    },
                ],
                "sample_unit_limitations": [
                    "four uncultured GEO matrices correspond to a publication total reported from three fetuses",
                    "nine cultured GEO matrices cannot be assigned to the three culture donors without inference",
                ],
                "expected_gene_order_sha256": _gene_order_sha256(["TH", "LMX1A"]),
                "samples": samples,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return source_root, sample_map


def test_gene_order_hash_does_not_add_an_unpublished_terminal_newline() -> None:
    assert birtele._gene_order_sha256(["TH", "LMX1A"]) == hashlib.sha256(
        b"TH\nLMX1A"
    ).hexdigest()


def test_prepare_birtele_asset_is_deterministic_and_public_safe(tmp_path: Path) -> None:
    source_root, sample_map = _fixture_source_and_map(tmp_path)
    before = {
        path.relative_to(source_root).as_posix(): _sha256(path)
        for path in source_root.rglob("*")
        if path.is_file()
    }

    first = prepare_birtele_asset(source_root, sample_map, tmp_path / "first")
    second = prepare_birtele_asset(source_root, sample_map, tmp_path / "second")

    assert first == second
    assert _sha256(tmp_path / "first" / "GSE192405.h5ad") == _sha256(
        tmp_path / "second" / "GSE192405.h5ad"
    )
    assert before == {
        path.relative_to(source_root).as_posix(): _sha256(path)
        for path in source_root.rglob("*")
        if path.is_file()
    }

    expected_outputs = {
        "GSE192405.h5ad",
        "conversion_manifest.json",
        "qc_report.json",
        "sample_unit_map.tsv",
        "source_manifest.json",
    }
    assert {path.name for path in (tmp_path / "first").iterdir()} == expected_outputs

    dataset = ad.read_h5ad(tmp_path / "first" / "GSE192405.h5ad")
    assert dataset.shape == (13, 2)
    assert dataset.var_names.tolist() == ["TH", "LMX1A"]
    assert dataset.obs["geo_accession"].tolist() == list(BIRTELE_FILES)
    assert dataset.obs["source_cell_id"].tolist() == [
        f"{accession}_cell_1" for accession in BIRTELE_FILES
    ]
    assert dataset.obs_names.tolist() == [
        f"{accession}::{accession}_cell_1" for accession in BIRTELE_FILES
    ]
    assert np.asarray(dataset.X.toarray()).tolist() == [[1, 2]] * 13
    assert set(dataset.obs["biological_unit_status"]) == {"unresolved_public_mapping"}
    assert set(dataset.obs["replicate_eligibility"]) == {"not_estimable"}
    conflict = dataset.obs.loc[
        "GSM5746445::GSM5746445_cell_1", "metadata_conflicts"
    ]
    assert "title says 3D day 14" in conflict
    assert dataset.obs.loc[
        "GSM5746445::GSM5746445_cell_1", "biological_unit_id"
    ] == ""

    qc = json.loads((tmp_path / "first" / "qc_report.json").read_text())
    assert qc == {
        "all_counts_finite": True,
        "all_counts_integer": True,
        "all_counts_nonnegative": True,
        "dataset_id": "GSE192405",
        "duplicate_cell_count": 0,
        "duplicate_feature_count": 0,
        "gene_order_sha256": _gene_order_sha256(["TH", "LMX1A"]),
        "n_obs": 13,
        "n_samples": 13,
        "n_vars": 2,
        "resolved_biological_unit_count": 0,
        "status": "passed_with_unresolved_sample_units",
        "unresolved_sample_count": 13,
    }
    manifest = json.loads((tmp_path / "first" / "conversion_manifest.json").read_text())
    assert manifest["dataset_id"] == "GSE192405"
    assert manifest["matrix_location"] == "X"
    assert manifest["matrix_semantics"] == "raw_counts"
    assert manifest["output_files"]["GSE192405.h5ad"] == _sha256(
        tmp_path / "first" / "GSE192405.h5ad"
    )
    source_manifest = json.loads((tmp_path / "first" / "source_manifest.json").read_text())
    assert len(source_manifest["metadata_sources"]) == 3
    assert source_manifest["sample_unit_limitations"][0].startswith(
        "four uncultured GEO matrices"
    )
    for name in expected_outputs - {"GSE192405.h5ad"}:
        text = (tmp_path / "first" / name).read_text(encoding="utf-8")
        assert str(tmp_path) not in text
        assert "/data" not in text


def test_packaged_birtele_sample_map_is_complete_and_conservative() -> None:
    resource = files("bridge.tool_packages.p0_02_cell_state.resources").joinpath(
        "birtele_gse192405_samples.yaml"
    )
    payload = yaml.safe_load(resource.read_text(encoding="utf-8"))

    assert payload["dataset_id"] == "GSE192405"
    assert payload["source_archive"]["raw_reads_public"] is False
    assert payload["expected_gene_order_sha256"] == (
        "643be392404f6fc4c10ca6dce2abc3d10b07de0df9ed9e100826f26fe4939cd9"
    )
    assert {sample["geo_accession"] for sample in payload["samples"]} == set(BIRTELE_FILES)
    assert all(sample["biological_unit_id"] is None for sample in payload["samples"])
    assert all(
        sample["biological_unit_status"] == "unresolved_public_mapping"
        for sample in payload["samples"]
    )
    assert all(sample["replicate_eligibility"] == "not_estimable" for sample in payload["samples"])
    conflict = next(
        sample for sample in payload["samples"] if sample["geo_accession"] == "GSM5746445"
    )
    assert len(conflict["metadata_conflicts"]) == 1
    assert "title" in conflict["metadata_conflicts"][0]
    assert len(payload["sample_unit_limitations"]) == 2


def test_prepare_birtele_cli_writes_the_manifest(tmp_path: Path, capsys) -> None:
    source_root, sample_map = _fixture_source_and_map(tmp_path)
    output_dir = tmp_path / "output"

    exit_code = benchmark_main(
        [
            "cell-state",
            "prepare-birtele",
            "--source-dir",
            str(source_root),
            "--sample-map",
            str(sample_map),
            "--output-dir",
            str(output_dir),
        ]
    )

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out) == json.loads(
        (output_dir / "conversion_manifest.json").read_text()
    )


def test_prepare_birtele_asset_requires_exact_sample_set(tmp_path: Path) -> None:
    source_root, sample_map = _fixture_source_and_map(tmp_path)
    payload = yaml.safe_load(sample_map.read_text())
    payload["samples"].pop()
    sample_map.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    with pytest.raises(BirteleAssetError, match="sample_map_accessions_mismatch"):
        prepare_birtele_asset(source_root, sample_map, tmp_path / "output")


def test_prepare_birtele_asset_rejects_gene_order_mismatch(tmp_path: Path) -> None:
    source_root, sample_map = _fixture_source_and_map(tmp_path)
    accession, file_name = list(BIRTELE_FILES.items())[1]
    path = source_root / "processed_csv" / file_name
    _write_matrix(path, accession, genes=["LMX1A", "TH"], values=[[2], [1]])
    payload = yaml.safe_load(sample_map.read_text())
    sample = next(item for item in payload["samples"] if item["geo_accession"] == accession)
    sample["sha256"] = _sha256(path)
    sample_map.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    with pytest.raises(BirteleAssetError, match=f"gene_order_mismatch:{accession}"):
        prepare_birtele_asset(source_root, sample_map, tmp_path / "output")


@pytest.mark.parametrize(
    ("bad_value", "reason"),
    [
        (-1, "negative_count"),
        (1.5, "non_integer_count"),
        ("not-a-number", "non_numeric_count"),
    ],
)
def test_prepare_birtele_asset_rejects_invalid_counts(
    tmp_path: Path, bad_value: object, reason: str
) -> None:
    source_root, sample_map = _fixture_source_and_map(tmp_path)
    accession, file_name = next(iter(BIRTELE_FILES.items()))
    path = source_root / "processed_csv" / file_name
    _write_matrix(path, accession, values=[[bad_value], [2]])
    payload = yaml.safe_load(sample_map.read_text())
    payload["samples"][0]["sha256"] = _sha256(path)
    sample_map.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    with pytest.raises(BirteleAssetError, match=f"{reason}:{accession}"):
        prepare_birtele_asset(source_root, sample_map, tmp_path / "output")


@pytest.mark.parametrize(
    "relative_path",
    [
        "GSE192405_RAW.tar",
        "GSE192405_family.xml.tgz",
        "develop-149-200504-s1.pdf",
        "TableS1.xlsx",
    ],
)
def test_prepare_birtele_asset_rejects_provenance_checksum_mismatch(
    tmp_path: Path, relative_path: str
) -> None:
    source_root, sample_map = _fixture_source_and_map(tmp_path)
    (source_root / relative_path).write_bytes(b"altered")

    with pytest.raises(BirteleAssetError, match="provenance_checksum_mismatch"):
        prepare_birtele_asset(source_root, sample_map, tmp_path / "output")
