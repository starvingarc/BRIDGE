from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Literal

import anndata as ad
import numpy as np
import pandas as pd
import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from scipy import sparse


BIRTELE_FILES: dict[str, str] = {
    "GSM5746439": "GSM5746439_hVM2015aggrd14.csv.gz",
    "GSM5746440": "GSM5746440_hVM2096aggrd30.csv.gz",
    "GSM5746441": "GSM5746441_hVM2096d14.csv.gz",
    "GSM5746442": "GSM5746442_hVM2096d30.csv.gz",
    "GSM5746443": "GSM5746443_hVM2Dday147weeks.csv.gz",
    "GSM5746444": "GSM5746444_hVM2Dday307weeks.csv.gz",
    "GSM5746445": "GSM5746445_hVM3Dday147weeks.csv.gz",
    "GSM5746446": "GSM5746446_MP01-hVM-11-5wks.csv.gz",
    "GSM5746447": "GSM5746447_MP02-hVM-10-5wks.csv.gz",
    "GSM5746448": "GSM5746448_MP03-hVM-8wks.csv.gz",
    "GSM5746449": "GSM5746449_MP04-hVM-7wks-aggr-d14.csv.gz",
    "GSM5746450": "GSM5746450_MP05-hVM-7wks-aggr-d30.csv.gz",
    "GSM5746451": "GSM5746451_MP06-hVM-6wks.csv.gz",
}

CONVERTER_VERSION = "0.1.0"
_CHUNK_SIZE = 256
_TSV_FIELDS = (
    "geo_accession",
    "biosample",
    "file_name",
    "published_title",
    "published_source",
    "specimen_class",
    "published_tissue",
    "published_culture_condition",
    "published_time",
    "published_age",
    "biological_unit_id",
    "biological_unit_status",
    "technical_subdivision_id",
    "replicate_eligibility",
    "metadata_conflicts",
)


class BirteleAssetError(ValueError):
    pass


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _SourceArchive(_StrictModel):
    file_name: Literal["GSE192405_RAW.tar"]
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    raw_reads_public: Literal[False]
    source_url: str


class _MetadataSource(_StrictModel):
    file_name: str
    kind: Literal["geo_miniml", "publication_table", "publication_supplement"]
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_url: str


class _PublishedCharacteristics(_StrictModel):
    tissue: str
    culture_condition: str | None = None
    time: str | None = None
    age: str | None = None


class _SampleRecord(_StrictModel):
    geo_accession: str = Field(pattern=r"^GSM[0-9]+$")
    file_name: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    biosample: str
    published_title: str
    published_source: str
    published_characteristics: _PublishedCharacteristics
    specimen_class: Literal["primary_tissue", "cultured_tissue"]
    biological_unit_id: str | None
    biological_unit_status: Literal["resolved", "unresolved_public_mapping"]
    technical_subdivision_id: str
    replicate_eligibility: Literal["eligible", "descriptive_only", "not_estimable"]
    metadata_conflicts: list[str]

    @model_validator(mode="after")
    def _unit_status_is_consistent(self) -> _SampleRecord:
        if self.biological_unit_status == "resolved" and not self.biological_unit_id:
            raise ValueError("resolved biological unit requires biological_unit_id")
        if self.biological_unit_status == "unresolved_public_mapping" and self.biological_unit_id:
            raise ValueError("unresolved biological unit cannot have biological_unit_id")
        return self


class _SampleMap(_StrictModel):
    dataset_id: Literal["GSE192405"]
    version: str
    source_archive: _SourceArchive
    metadata_sources: list[_MetadataSource] = Field(min_length=1)
    sample_unit_limitations: list[str] = Field(min_length=1)
    expected_gene_order_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    samples: list[_SampleRecord]


def prepare_birtele_asset(
    source_dir: Path,
    sample_map_path: Path,
    output_dir: Path,
) -> dict[str, object]:
    """Convert the fixed GSE192405 processed matrices without inferring donors."""
    sample_map = _load_sample_map(sample_map_path)
    samples = _ordered_samples(sample_map)
    _validate_source_files(source_dir, samples)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise BirteleAssetError("output_dir_not_empty")
    output_dir.mkdir(parents=True, exist_ok=True)

    matrices: list[sparse.csr_matrix] = []
    observation_rows: list[dict[str, str]] = []
    observation_ids: list[str] = []
    source_cell_ids: set[str] = set()
    canonical_genes: list[str] | None = None

    for sample in samples:
        matrix, genes, cell_ids = _read_sample_matrix(source_dir / sample.file_name, sample)
        gene_hash = _gene_order_sha256(genes)
        if canonical_genes is None:
            canonical_genes = genes
            if gene_hash != sample_map.expected_gene_order_sha256:
                raise BirteleAssetError(f"gene_order_hash_mismatch:{sample.geo_accession}")
        elif genes != canonical_genes:
            raise BirteleAssetError(f"gene_order_mismatch:{sample.geo_accession}")
        duplicate_source_cells = source_cell_ids.intersection(cell_ids)
        if duplicate_source_cells:
            raise BirteleAssetError(f"duplicate_cell_id:{sample.geo_accession}")
        source_cell_ids.update(cell_ids)
        matrices.append(matrix)
        for cell_id in cell_ids:
            observation_ids.append(f"{sample.geo_accession}::{cell_id}")
            observation_rows.append(_observation_row(sample, cell_id))

    if canonical_genes is None:
        raise BirteleAssetError("empty_dataset")
    if len(set(canonical_genes)) != len(canonical_genes):
        raise BirteleAssetError("duplicate_feature_id")

    combined = sparse.vstack(matrices, format="csr", dtype=np.int32)
    observations = pd.DataFrame(observation_rows, index=observation_ids, dtype=object)
    observations.index.name = "observation_id"
    features = pd.DataFrame(index=pd.Index(canonical_genes, name="feature_id"))
    dataset = ad.AnnData(X=combined, obs=observations, var=features)
    dataset.uns = {
        "dataset_id": "GSE192405",
        "matrix_location": "X",
        "matrix_semantics": "raw_counts",
        "raw_reads_public": False,
        "sample_map_version": sample_map.version,
        "sample_unit_boundary": (
            "GEO samples are technical subdivisions; unresolved biological units are not replicates"
        ),
    }

    sample_map_output = output_dir / "sample_unit_map.tsv"
    source_manifest_output = output_dir / "source_manifest.json"
    qc_output = output_dir / "qc_report.json"
    h5ad_output = output_dir / "GSE192405.h5ad"
    _write_sample_map(sample_map_output, samples)
    _write_json(source_manifest_output, _source_manifest(sample_map, samples))
    qc = _qc_report(sample_map, samples, combined, canonical_genes, observation_ids)
    _write_json(qc_output, qc)
    dataset.write_h5ad(
        h5ad_output,
        compression="gzip",
        convert_strings_to_categoricals=False,
    )

    manifest: dict[str, object] = {
        "converter_version": CONVERTER_VERSION,
        "dataset_id": "GSE192405",
        "input_sample_map_sha256": _sha256(sample_map_path),
        "matrix_location": "X",
        "matrix_semantics": "raw_counts",
        "n_obs": int(combined.shape[0]),
        "n_samples": len(samples),
        "n_vars": int(combined.shape[1]),
        "output_files": {
            path.name: _sha256(path)
            for path in (h5ad_output, qc_output, sample_map_output, source_manifest_output)
        },
        "sample_unit_status": (
            "unresolved" if any(sample.biological_unit_id is None for sample in samples) else "resolved"
        ),
    }
    _write_json(output_dir / "conversion_manifest.json", manifest)
    return manifest


def _load_sample_map(path: Path) -> _SampleMap:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        return _SampleMap.model_validate(payload)
    except (OSError, ValidationError, ValueError, yaml.YAMLError) as exc:
        raise BirteleAssetError(f"invalid_sample_map:{type(exc).__name__}") from exc


def _ordered_samples(sample_map: _SampleMap) -> list[_SampleRecord]:
    records = {sample.geo_accession: sample for sample in sample_map.samples}
    if len(records) != len(sample_map.samples) or set(records) != set(BIRTELE_FILES):
        raise BirteleAssetError("sample_map_accessions_mismatch")
    ordered = [records[accession] for accession in BIRTELE_FILES]
    for sample in ordered:
        if sample.file_name != BIRTELE_FILES[sample.geo_accession]:
            raise BirteleAssetError(f"sample_file_mismatch:{sample.geo_accession}")
    return ordered


def _validate_source_files(source_dir: Path, samples: list[_SampleRecord]) -> None:
    if not source_dir.is_dir():
        raise BirteleAssetError("source_dir_missing")
    actual = {path.name for path in source_dir.glob("*.csv.gz")}
    if actual != set(BIRTELE_FILES.values()):
        raise BirteleAssetError("source_file_set_mismatch")
    for sample in samples:
        if _sha256(source_dir / sample.file_name) != sample.sha256:
            raise BirteleAssetError(f"source_checksum_mismatch:{sample.geo_accession}")


def _read_sample_matrix(
    path: Path,
    sample: _SampleRecord,
) -> tuple[sparse.csr_matrix, list[str], list[str]]:
    gene_blocks: list[str] = []
    matrix_blocks: list[sparse.csr_matrix] = []
    cell_ids: list[str] | None = None
    try:
        chunks = pd.read_csv(path, index_col=0, chunksize=_CHUNK_SIZE)
        for chunk in chunks:
            current_cells = [str(value) for value in chunk.columns]
            if cell_ids is None:
                cell_ids = current_cells
                if not cell_ids or len(set(cell_ids)) != len(cell_ids):
                    raise BirteleAssetError(f"invalid_cell_ids:{sample.geo_accession}")
            elif current_cells != cell_ids:
                raise BirteleAssetError(f"cell_order_mismatch:{sample.geo_accession}")
            genes = [str(value) for value in chunk.index]
            if any(not gene for gene in genes):
                raise BirteleAssetError(f"invalid_feature_id:{sample.geo_accession}")
            gene_blocks.extend(genes)
            try:
                values = chunk.to_numpy(dtype=np.float64)
            except (TypeError, ValueError) as exc:
                raise BirteleAssetError(f"non_numeric_count:{sample.geo_accession}") from exc
            if not np.isfinite(values).all():
                raise BirteleAssetError(f"non_finite_count:{sample.geo_accession}")
            if (values < 0).any():
                raise BirteleAssetError(f"negative_count:{sample.geo_accession}")
            if not np.equal(values, np.floor(values)).all():
                raise BirteleAssetError(f"non_integer_count:{sample.geo_accession}")
            if values.size and values.max() > np.iinfo(np.int32).max:
                raise BirteleAssetError(f"count_overflow:{sample.geo_accession}")
            matrix_blocks.append(sparse.csr_matrix(values.astype(np.int32, copy=False).T))
    except BirteleAssetError:
        raise
    except (OSError, UnicodeError, pd.errors.ParserError) as exc:
        raise BirteleAssetError(f"matrix_read_failed:{sample.geo_accession}") from exc
    if cell_ids is None or not matrix_blocks:
        raise BirteleAssetError(f"empty_matrix:{sample.geo_accession}")
    if len(set(gene_blocks)) != len(gene_blocks):
        raise BirteleAssetError(f"duplicate_feature_id:{sample.geo_accession}")
    return sparse.hstack(matrix_blocks, format="csr", dtype=np.int32), gene_blocks, cell_ids


def _observation_row(sample: _SampleRecord, cell_id: str) -> dict[str, str]:
    characteristics = sample.published_characteristics
    return {
        "source_cell_id": cell_id,
        "geo_accession": sample.geo_accession,
        "biosample": sample.biosample,
        "published_title": sample.published_title,
        "published_source": sample.published_source,
        "specimen_class": sample.specimen_class,
        "published_tissue": characteristics.tissue,
        "published_culture_condition": characteristics.culture_condition or "",
        "published_time": characteristics.time or "",
        "published_age": characteristics.age or "",
        "biological_unit_id": sample.biological_unit_id or "",
        "biological_unit_status": sample.biological_unit_status,
        "technical_subdivision_id": sample.technical_subdivision_id,
        "replicate_eligibility": sample.replicate_eligibility,
        "metadata_conflicts": " | ".join(sample.metadata_conflicts),
    }


def _write_sample_map(path: Path, samples: list[_SampleRecord]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=_TSV_FIELDS, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for sample in samples:
            characteristics = sample.published_characteristics
            writer.writerow(
                {
                    "geo_accession": sample.geo_accession,
                    "biosample": sample.biosample,
                    "file_name": sample.file_name,
                    "published_title": sample.published_title,
                    "published_source": sample.published_source,
                    "specimen_class": sample.specimen_class,
                    "published_tissue": characteristics.tissue,
                    "published_culture_condition": characteristics.culture_condition or "",
                    "published_time": characteristics.time or "",
                    "published_age": characteristics.age or "",
                    "biological_unit_id": sample.biological_unit_id or "",
                    "biological_unit_status": sample.biological_unit_status,
                    "technical_subdivision_id": sample.technical_subdivision_id,
                    "replicate_eligibility": sample.replicate_eligibility,
                    "metadata_conflicts": " | ".join(sample.metadata_conflicts),
                }
            )


def _source_manifest(sample_map: _SampleMap, samples: list[_SampleRecord]) -> dict[str, object]:
    return {
        "dataset_id": "GSE192405",
        "raw_reads_public": False,
        "metadata_sources": [source.model_dump(mode="json") for source in sample_map.metadata_sources],
        "sample_unit_limitations": sample_map.sample_unit_limitations,
        "source_archive": sample_map.source_archive.model_dump(mode="json"),
        "source_files": [
            {
                "geo_accession": sample.geo_accession,
                "relative_path": f"processed_csv/{sample.file_name}",
                "sha256": sample.sha256,
            }
            for sample in samples
        ],
    }


def _qc_report(
    sample_map: _SampleMap,
    samples: list[_SampleRecord],
    matrix: sparse.csr_matrix,
    genes: list[str],
    observation_ids: list[str],
) -> dict[str, object]:
    unresolved = sum(sample.biological_unit_id is None for sample in samples)
    resolved_units = {sample.biological_unit_id for sample in samples if sample.biological_unit_id}
    return {
        "all_counts_finite": True,
        "all_counts_integer": True,
        "all_counts_nonnegative": True,
        "dataset_id": "GSE192405",
        "duplicate_cell_count": len(observation_ids) - len(set(observation_ids)),
        "duplicate_feature_count": len(genes) - len(set(genes)),
        "gene_order_sha256": sample_map.expected_gene_order_sha256,
        "n_obs": int(matrix.shape[0]),
        "n_samples": len(samples),
        "n_vars": int(matrix.shape[1]),
        "resolved_biological_unit_count": len(resolved_units),
        "status": "passed_with_unresolved_sample_units" if unresolved else "passed",
        "unresolved_sample_count": unresolved,
    }


def _gene_order_sha256(genes: list[str]) -> str:
    return hashlib.sha256("\n".join(genes).encode()).hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
