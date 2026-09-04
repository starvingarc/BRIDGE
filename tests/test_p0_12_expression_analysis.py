from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import anndata as ad
import numpy as np
import pandas as pd
import pytest
from scipy import sparse

from bridge.tool_packages.p0_12_graft_assessment import (
    analysis as analysis_module,
)
from bridge.tool_packages._structured_runtime import canonical_json_bytes
from bridge.tool_packages.p0_12_graft_assessment.analysis import (
    ANALYSIS_METHOD_IDS,
)
from bridge.tool_packages.p0_12_graft_assessment.analysis_models import (
    GraftExpressionAnalysisResult,
)
from bridge.toolkit.contracts import (
    ExecutionState,
    StructuredInputRef,
    ToolRequestV2,
)
from bridge.toolkit.registry import ToolRegistry


CREATED_AT = "2026-08-27T00:00:00Z"


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_ref(
    root: Path,
    role: str,
    schema_ref: str,
    payload: dict[str, Any],
) -> StructuredInputRef:
    path = root / f"{role}.json"
    path.write_bytes(canonical_json_bytes(payload, indent=2))
    return StructuredInputRef(
        input_id=f"input-{role}",
        role=role,
        schema_ref=schema_ref,
        object_version="0.1.0",
        path=path,
        sha256=_digest(path),
        media_type="application/json",
    )


def _write_h5ad(
    path: Path,
    *,
    invalid_counts: bool = False,
    fractional_counts: bool = False,
    probability_override: float | None = None,
    mixed_grafts: bool = False,
    matrix_semantics: str = "raw_counts",
    omit_sample_id: bool = False,
    unsafe_sample_id: bool = False,
) -> None:
    counts = np.array(
        [
            [10, 2, 1, 0, 3],
            [9, 2, 1, 0, 2],
            [11, 3, 1, 0, 4],
            [10, 2, 2, 0, 3],
            [1, 3, 8, 5, 2],
            [1, 4, 9, 6, 2],
            [2, 3, 7, 5, 3],
            [1, 5, 8, 7, 2],
        ],
        dtype=float,
    )
    if invalid_counts:
        counts[0, 0] = -1
    if fractional_counts:
        counts[0, 0] = 1.5
    state_a = [0.8, 0.7, 0.9, 0.8, 0.2, 0.3, 0.1, 0.2]
    if probability_override is not None:
        state_a[0] = probability_override
    graft_ids = ["demo-graft-1"] * 8
    if mixed_grafts:
        graft_ids[4:] = ["demo-graft-2"] * 4
    obs = pd.DataFrame(
        {
            "sample_id": ["demo-sample-1"] * 4 + ["demo-sample-2"] * 4,
            "graft_id": graft_ids,
            "state_a_probability": state_a,
            "state_b_probability": [
                0.1,
                0.2,
                0.1,
                0.1,
                0.7,
                0.6,
                0.8,
                0.7,
            ],
        },
        index=[f"demo-cell-{index:02d}" for index in range(8)],
    )
    if omit_sample_id:
        obs = obs.drop(columns=["sample_id"])
    elif unsafe_sample_id:
        obs.iloc[0, obs.columns.get_loc("sample_id")] = "unsafe sample"
    expression = counts.copy()
    if matrix_semantics == "log_normalized":
        totals = expression.sum(axis=1, keepdims=True)
        expression = np.log1p(expression / totals * 10_000)
    data = ad.AnnData(
        X=expression,
        obs=obs,
        var=pd.DataFrame(index=[f"GENE{index}" for index in range(1, 6)]),
    )
    data.layers["counts"] = counts
    data.write_h5ad(path)


def _write_compressed_oversize_h5ad(path: Path) -> None:
    size = 1_025
    counts = sparse.csr_matrix((size, size), dtype=np.int8)
    obs = pd.DataFrame(
        {
            "sample_id": np.full(size, "demo-sample-1"),
            "graft_id": np.full(size, "demo-graft-1"),
            "state_a_probability": np.full(size, 0.4),
            "state_b_probability": np.full(size, 0.4),
        },
        index=[f"demo-cell-{index:04d}" for index in range(size)],
    )
    data = ad.AnnData(
        X=counts,
        obs=obs,
        var=pd.DataFrame(
            index=[f"GENE{index}" for index in range(1, size + 1)]
        ),
    )
    data.layers["counts"] = counts
    data.write_h5ad(path, compression="gzip")


def _request(
    tmp_path: Path,
    *,
    invalid_counts: bool = False,
    fractional_counts: bool = False,
    probability_override: float | None = None,
    probability_tolerance: float = 0.000001,
    mixed_grafts: bool = False,
    declared_graft_id: str | None = "demo-graft-1",
    animal_id: str | None = "animal:demo",
    post_transplant_timepoint: str | None = "day-42",
    matrix_semantics: str = "raw_counts",
    reference_aggregation: str | None = None,
    omit_sample_id: bool = False,
    unsafe_sample_id: bool = False,
    reference_organism: str = "NCBITaxon:9606",
    compressed_oversize: bool = False,
    max_matrix_elements: int = 10_000_000,
) -> tuple[ToolRequestV2, Path]:
    input_dir = tmp_path / "inputs"
    input_dir.mkdir(parents=True)
    h5ad_path = input_dir / "demo-graft.h5ad"
    if compressed_oversize:
        _write_compressed_oversize_h5ad(h5ad_path)
    else:
        _write_h5ad(
            h5ad_path,
            invalid_counts=invalid_counts,
            fractional_counts=fractional_counts,
            probability_override=probability_override,
            mixed_grafts=mixed_grafts,
            matrix_semantics=matrix_semantics,
            omit_sample_id=omit_sample_id,
            unsafe_sample_id=unsafe_sample_id,
        )
    case = {
        "object_version": "0.1.0",
        "graft_case_id": "graft-case:demo",
        "assay_id": "assay:demo",
        "specimen_id": "specimen:demo",
        "graft_id": declared_graft_id,
        "animal_id": animal_id,
        "post_transplant_timepoint": post_transplant_timepoint,
        "biological_replicate_id": "replicate:demo",
        "originating_preparation_id": None,
        "linkage_evidence_refs": [],
        "declared_confounder_refs": [],
        "provenance_refs": ["demo:synthetic-graft-case"],
        "created_at": CREATED_AT,
    }
    asset = {
        "object_version": "0.1.0",
        "asset_id": "graft-expression-asset:demo",
        "graft_case_ref": case["graft_case_id"],
        "assay_id": case["assay_id"],
        "path": str(h5ad_path),
        "sha256": _digest(h5ad_path),
        "format": "h5ad",
        "assay": "scRNA-seq",
        "organism": "NCBITaxon:9606",
        "gene_id_namespace": "HGNC.symbol",
        "expression_layer": (
            "counts" if matrix_semantics == "raw_counts" else "X"
        ),
        "matrix_semantics": matrix_semantics,
        "analysis_value_semantics": "log1p_cp10k",
        "gene_symbol_key": None,
        "sample_id_key": "sample_id",
        "graft_id_key": "graft_id",
        "state_probability_columns": {
            "state-a": "state_a_probability",
            "state-b": "state_b_probability",
        },
        "provenance_refs": ["demo:synthetic-expression"],
        "created_at": CREATED_AT,
    }
    analysis_spec = {
        "object_version": "0.1.0",
        "analysis_spec_id": "graft-expression-analysis-spec:demo",
        "reference_panel_ref": "graft-reference-panel:demo",
        "marker_program_collection_ref": "graft-marker-programs:demo",
        "method_ids": ANALYSIS_METHOD_IDS,
        "required_obs_fields": [
            "graft_id",
            "sample_id",
            "state_a_probability",
            "state_b_probability",
        ],
        "minimum_cells": 4,
        "minimum_genes": 4,
        "minimum_reference_genes": 3,
        "minimum_program_genes": 2,
        "probability_tolerance": probability_tolerance,
        "max_file_bytes": 10_000_000,
        "max_matrix_elements": max_matrix_elements,
        "provenance_refs": ["demo:analysis-settings"],
    }
    reference_panel = {
        "object_version": "0.1.0",
        "reference_panel_id": "graft-reference-panel:demo",
        "source_family_id": "source-family:demo-reference",
        "organism": reference_organism,
        "gene_id_namespace": "HGNC.symbol",
        "assay": "scRNA-seq",
        "value_semantics": "log1p_cp10k",
        "profile_aggregation": (
            reference_aggregation
            or (
                "sample_pseudobulk"
                if matrix_semantics == "raw_counts"
                else "sample_mean_log_expression"
            )
        ),
        "profiles": [
            {
                "profile_id": "profile-a",
                "gene_values": {
                    "GENE1": 4.0,
                    "GENE2": 3.0,
                    "GENE3": 2.0,
                    "GENE4": 1.0,
                },
            }
        ],
        "provenance_refs": ["demo:reference-panel"],
        "created_at": CREATED_AT,
    }
    programs = {
        "object_version": "0.1.0",
        "collection_id": "graft-marker-programs:demo",
        "source_family_id": "source-family:demo-marker-programs",
        "organism": "NCBITaxon:9606",
        "gene_id_namespace": "HGNC.symbol",
        "value_semantics": "log1p_cp10k",
        "programs": [
            {"program_id": "program-a", "genes": ["GENE1", "GENE2"]}
        ],
        "provenance_refs": ["demo:marker-programs"],
        "created_at": CREATED_AT,
    }
    payloads = [
        ("graft_case", "bridge://schemas/graft-case/v0.1", case),
        (
            "graft_expression_asset",
            "bridge://schemas/graft-expression-asset/v0.1",
            asset,
        ),
        (
            "graft_expression_analysis_spec",
            "bridge://schemas/graft-expression-analysis-spec/v0.1",
            analysis_spec,
        ),
        (
            "graft_reference_panel",
            "bridge://schemas/graft-reference-panel/v0.1",
            reference_panel,
        ),
        (
            "graft_marker_program_collection",
            "bridge://schemas/graft-marker-program-collection/v0.1",
            programs,
        ),
    ]
    refs = [
        _write_ref(input_dir, role, schema_ref, payload)
        for role, schema_ref, payload in payloads
    ]
    return (
        ToolRequestV2(
            request_id="request-p0-12-expression",
            tool_id="P0-12",
            tool_version="0.4.0",
            output_dir=tmp_path / "output",
            object_inputs=refs,
        ),
        h5ad_path,
    )


def test_expression_analysis_runs_real_h5ad_chain_deterministically(
    tmp_path: Path,
) -> None:
    registry = ToolRegistry.load_default()
    request, h5ad_path = _request(tmp_path)

    assert registry.check_eligibility(request).eligible
    first = registry.run(request)
    second = registry.run(request)
    result = GraftExpressionAnalysisResult.model_validate(first.result)

    assert first.execution_state is ExecutionState.SUCCEEDED
    assert first.run_id == second.run_id
    assert first.result == second.result
    assert result.cell_count == 8
    assert result.gene_count == 5
    assert result.sample_count == 2
    assert result.graft_count == 1
    assert result.graft_id == "demo-graft-1"
    assert result.animal_id == "animal:demo"
    assert result.post_transplant_timepoint == "day-42"
    assert result.sample_unit == "technical_sample"
    assert result.profile_aggregation == "sample_pseudobulk"
    assert result.selected_method_ids == ANALYSIS_METHOD_IDS
    assert result.reference_source_family_id == "source-family:demo-reference"
    assert result.marker_source_family_id == "source-family:demo-marker-programs"
    assert result.analysis_value_semantics == "log1p_cp10k"
    assert result.qc_state == "not_reassessed"
    assert result.composition_denominator == "all_uploaded_rows"
    assert len(result.composition_estimates) == 2
    assert all(
        item.mean_fraction
        == pytest.approx(item.cell_equivalent / item.denominator_cells)
        for item in result.composition_estimates
    )
    assert all(
        item.denominator_cells == result.cell_count
        for item in result.composition_estimates
    )
    assert all(
        item.availability == "available"
        for item in result.reference_support
    )
    assert all(
        item.availability == "available"
        for item in result.program_evidence
    )
    assert result.domain_score is None
    assert str(h5ad_path) not in json.dumps(first.result)
    assert len(first.artifacts) == 16
    assert first.visualizations == []
    assert {item.kind for item in first.artifacts} == {
        "artifact_manifest",
        "graft_expression_analysis_result",
        "graft_assessment_visualization_data",
        "visualization_artifact_set",
        "visualization_render",
        "visualization_table",
    }
    manifest = json.loads(
        next(
            item.path
            for item in first.artifacts
            if item.kind == "artifact_manifest"
        ).read_text()
    )
    assert len(manifest["artifacts"]) == 15
    final_dir = (request.output_dir / first.run_id).resolve()
    actual_files = {path.name for path in final_dir.iterdir() if path.is_file()}
    manifest_by_name = {
        item["filename"]: item for item in manifest["artifacts"]
    }
    runtime_by_name = {item.path.name: item for item in first.artifacts}

    assert set(manifest_by_name) == actual_files - {"artifact_manifest.json"}
    assert set(runtime_by_name) == actual_files
    assert len({item.artifact_id for item in first.artifacts}) == len(
        first.artifacts
    )
    assert len({item.path for item in first.artifacts}) == len(first.artifacts)
    for filename, entry in manifest_by_name.items():
        payload = (final_dir / filename).read_bytes()
        runtime = runtime_by_name[filename]
        assert entry == {
            "filename": filename,
            "kind": runtime.kind,
            "media_type": runtime.media_type,
            "sha256": runtime.sha256,
            "evidence_ids": runtime.evidence_ids,
        }
        assert runtime.path == (final_dir / filename).resolve()
        assert runtime.sha256 == hashlib.sha256(payload).hexdigest()
    manifest_runtime = runtime_by_name["artifact_manifest.json"]
    assert manifest_runtime.path == (final_dir / "artifact_manifest.json")
    assert manifest_runtime.sha256 == hashlib.sha256(
        (final_dir / "artifact_manifest.json").read_bytes()
    ).hexdigest()


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"invalid_counts": True}, "graft_expression_counts_invalid"),
        ({"fractional_counts": True}, "graft_expression_counts_invalid"),
        ({"probability_override": 1.2}, "graft_state_probabilities_invalid"),
        ({"probability_override": -0.1}, "graft_state_probabilities_invalid"),
    ],
)
def test_expression_analysis_invalid_values_fail_closed(
    tmp_path: Path,
    change: dict[str, object],
    reason: str,
) -> None:
    request, _ = _request(tmp_path, **change)

    run = ToolRegistry.load_default().run(request)

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == [reason]
    assert not request.output_dir.exists()


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"mixed_grafts": True}, "graft_observation_unit_mismatch"),
        (
            {"declared_graft_id": "demo-graft-other"},
            "graft_observation_unit_mismatch",
        ),
        ({"declared_graft_id": None}, "graft_id_not_declared"),
        ({"animal_id": None}, "graft_animal_id_not_declared"),
        (
            {"post_transplant_timepoint": None},
            "graft_timepoint_not_declared",
        ),
    ],
)
def test_expression_analysis_requires_one_declared_biological_unit(
    tmp_path: Path,
    change: dict[str, object],
    reason: str,
) -> None:
    request, _ = _request(tmp_path, **change)

    eligibility = ToolRegistry.load_default().check_eligibility(request)

    assert not eligibility.eligible
    assert eligibility.reason_codes == [reason]


def test_probability_tolerance_is_small_and_does_not_clip_values(
    tmp_path: Path,
) -> None:
    registry = ToolRegistry.load_default()
    tolerated, _ = _request(tmp_path / "tolerated", probability_override=0.9000005)

    run = registry.run(tolerated)
    result = GraftExpressionAnalysisResult.model_validate(run.result)
    state_a = next(
        item for item in result.composition_estimates if item.state_id == "state-a"
    )

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert state_a.cell_equivalent == pytest.approx(4.1000005)
    assert "graft_probability_mass_within_tolerance" in result.reason_codes

    excessive_mass, _ = _request(
        tmp_path / "excessive-mass", probability_override=0.900002
    )
    failed = registry.run(excessive_mass)
    assert failed.execution_state is ExecutionState.FAILED
    assert failed.reason_codes == ["graft_state_probabilities_invalid"]

    excessive_tolerance, _ = _request(
        tmp_path / "excessive-tolerance", probability_tolerance=0.1
    )
    ineligible = registry.check_eligibility(excessive_tolerance)
    assert not ineligible.eligible
    assert ineligible.reason_codes == [
        "structured_input_schema_validation_failed"
    ]


def test_log_normalized_profiles_use_explicit_sample_mean_semantics(
    tmp_path: Path,
) -> None:
    registry = ToolRegistry.load_default()
    mismatched, _ = _request(
        tmp_path / "mismatch",
        matrix_semantics="log_normalized",
        reference_aggregation="sample_pseudobulk",
    )
    eligibility = registry.check_eligibility(mismatched)
    assert not eligibility.eligible
    assert eligibility.reason_codes == ["graft_reference_aggregation_mismatch"]

    request, _ = _request(
        tmp_path / "matched", matrix_semantics="log_normalized"
    )
    run = registry.run(request)
    result = GraftExpressionAnalysisResult.model_validate(run.result)

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert result.matrix_semantics == "log_normalized"
    assert result.profile_aggregation == "sample_mean_log_expression"
    assert all(
        item.availability == "available" for item in result.reference_support
    )


def test_expression_analysis_rejects_unsafe_sample_ids(
    tmp_path: Path,
) -> None:
    request, _ = _request(tmp_path, unsafe_sample_id=True)

    run = ToolRegistry.load_default().run(request)

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["graft_sample_labels_invalid"]
    assert not request.output_dir.exists()


def test_reference_context_mismatch_is_ineligible(tmp_path: Path) -> None:
    request, _ = _request(
        tmp_path,
        reference_organism="NCBITaxon:10090",
    )

    eligibility = ToolRegistry.load_default().check_eligibility(request)

    assert not eligibility.eligible
    assert eligibility.reason_codes == ["graft_reference_organism_mismatch"]


def test_compressed_small_h5ad_shape_fails_before_materialization(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = analysis_module.sc.read_h5ad
    read_modes: list[str | None] = []

    def backed_only(path: Path, **kwargs: Any) -> ad.AnnData:
        read_modes.append(kwargs.get("backed"))
        if kwargs.get("backed") != "r":
            raise AssertionError("oversized H5AD was materialized")
        return original(path, **kwargs)

    monkeypatch.setattr(analysis_module.sc, "read_h5ad", backed_only)
    request, h5ad_path = _request(
        tmp_path,
        compressed_oversize=True,
        max_matrix_elements=1_000_000,
    )

    assert h5ad_path.stat().st_size < 1_000_000
    run = ToolRegistry.load_default().run(request)
    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["graft_expression_memory_budget_exceeded"]
    assert read_modes == ["r"]
    assert not request.output_dir.exists()


def test_expression_asset_checksum_and_metadata_fail_closed(
    tmp_path: Path,
) -> None:
    registry = ToolRegistry.load_default()
    request, h5ad_path = _request(tmp_path)
    with h5ad_path.open("ab") as handle:
        handle.write(b"changed")

    eligibility = registry.check_eligibility(request)

    assert not eligibility.eligible
    assert "graft_expression_checksum_mismatch" in eligibility.reason_codes

    missing_request, _ = _request(
        tmp_path / "missing", omit_sample_id=True
    )
    missing = registry.check_eligibility(missing_request)
    assert not missing.eligible
    assert "graft_expression_obs_fields_missing" in missing.reason_codes
