from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import anndata as ad
import numpy as np
import pandas as pd
import pytest

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
    invalid_probabilities: bool = False,
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
    if invalid_probabilities:
        state_a[0] = 1.2
    obs = pd.DataFrame(
        {
            "sample_id": ["demo-sample-1"] * 4 + ["demo-sample-2"] * 4,
            "graft_id": ["demo-graft-1"] * 4 + ["demo-graft-2"] * 4,
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
    data = ad.AnnData(
        X=counts.copy(),
        obs=obs,
        var=pd.DataFrame(index=[f"GENE{index}" for index in range(1, 6)]),
    )
    data.layers["counts"] = counts
    data.write_h5ad(path)


def _request(
    tmp_path: Path,
    *,
    invalid_counts: bool = False,
    fractional_counts: bool = False,
    invalid_probabilities: bool = False,
    omit_sample_id: bool = False,
    unsafe_sample_id: bool = False,
    reference_organism: str = "NCBITaxon:9606",
) -> tuple[ToolRequestV2, Path]:
    input_dir = tmp_path / "inputs"
    input_dir.mkdir(parents=True)
    h5ad_path = input_dir / "demo-graft.h5ad"
    _write_h5ad(
        h5ad_path,
        invalid_counts=invalid_counts,
        fractional_counts=fractional_counts,
        invalid_probabilities=invalid_probabilities,
        omit_sample_id=omit_sample_id,
        unsafe_sample_id=unsafe_sample_id,
    )
    case = {
        "object_version": "0.1.0",
        "graft_case_id": "graft-case:demo",
        "assay_id": "assay:demo",
        "specimen_id": "specimen:demo",
        "animal_id": "animal:demo",
        "post_transplant_timepoint": "day-42",
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
        "expression_layer": "counts",
        "matrix_semantics": "raw_counts",
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
        "probability_tolerance": 0.000001,
        "max_file_bytes": 10_000_000,
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
            tool_version="0.3.0",
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
    assert result.graft_count == 2
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
    assert {item.kind for item in first.artifacts} == {
        "artifact_manifest",
        "graft_expression_analysis_result",
    }


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"invalid_counts": True}, "graft_expression_counts_invalid"),
        ({"fractional_counts": True}, "graft_expression_counts_invalid"),
        (
            {"invalid_probabilities": True},
            "graft_state_probabilities_invalid",
        ),
    ],
)
def test_expression_analysis_invalid_values_fail_closed(
    tmp_path: Path,
    change: dict[str, bool],
    reason: str,
) -> None:
    request, _ = _request(tmp_path, **change)

    run = ToolRegistry.load_default().run(request)

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == [reason]
    assert not request.output_dir.exists()


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
