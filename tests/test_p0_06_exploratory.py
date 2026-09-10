from __future__ import annotations

import hashlib
import json
from pathlib import Path

import anndata as ad
import numpy as np
import pandas as pd
import pytest
from jsonschema import Draft202012Validator

from bridge.toolkit.contracts import (
    InputAsset,
    InputLevel,
    StructuredInputRef,
    ToolRequestV2,
)
from bridge.toolkit.registry import ToolRegistry
from tests.test_p0_06_real_methods import _write_expression

SCHEMA = "bridge://schemas/exploratory-process-input/v0.1"


def _bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _gene_hash(genes):
    return hashlib.sha256(("\n".join(genes) + "\n").encode()).hexdigest()


def _request(tmp_path, *, missing_gene=False):
    path = tmp_path / "synthetic.h5ad"
    obs, genes, sha = _write_expression(path, raw_counts=True)
    s_genes = [f"SPHASE{i}" for i in range(6)]
    if missing_gene:
        s_genes.append("ABSENT")
    g2m_genes = [f"G2MPHASE{i}" for i in range(6)]
    payload = {
        "object_version": "0.1.0",
        "input_id": "exploratory:synthetic",
        "source_family_id": "synthetic-test-only",
        "data_view": {
            "view_id": "view:synthetic-all",
            "view_kind": "all_observations",
            "artifact_id": "asset:synthetic",
            "sha256": sha,
            "parent_asset_id": "asset:synthetic",
            "parent_asset_sha256": sha,
            "matrix_location": "X",
            "matrix_semantics": "raw_counts",
            "n_observations": 96,
            "observation_ids_sha256": hashlib.sha256(_bytes(sorted(obs))).hexdigest(),
        },
        "gene_symbol_column": "gene_symbol",
        "resource_ref": "fixture:synthetic-cycle-genes",
        "resource_version": "1.0.0",
        "resource_sha256": "9" * 64,  # Synthetic source provenance only.
        "s_genes": s_genes,
        "s_genes_sha256": _gene_hash(s_genes),
        "g2m_genes": g2m_genes,
        "g2m_genes_sha256": _gene_hash(g2m_genes),
        "created_at": "2026-09-09T00:00:00Z",
    }
    asset = InputAsset(
        asset_id="asset:synthetic",
        path=path,
        format="h5ad",
        input_level="count_ready",
        checksum=sha,
        matrix_location="X",
        matrix_semantics="raw_counts",
        assay="scRNA-seq",
    )
    return _with_input(
        ToolRequestV2(
            request_id="request:exploratory-test",
            tool_id="P0-06",
            assets=[asset],
            object_inputs=[],
            output_dir=tmp_path / "outputs",
            random_seed=0,
        ),
        payload,
    )


def _with_input(request, payload):
    path = request.assets[0].path.parent / "exploratory.json"
    raw = _bytes(payload)
    path.write_bytes(raw)
    ref = StructuredInputRef(
        input_id="input:exploratory",
        role="exploratory_process_input",
        schema_ref=SCHEMA,
        object_version="0.1.0",
        path=path,
        sha256=hashlib.sha256(raw).hexdigest(),
        media_type="application/json",
    )
    return request.model_copy(update={"object_inputs": [ref]})


def _payload(request):
    return json.loads(request.object_inputs[0].path.read_text())


def test_registered_exploratory_run_preserves_cells_without_invented_review(tmp_path):
    request = _request(tmp_path)
    original = hashlib.sha256(request.assets[0].path.read_bytes()).hexdigest()
    registry = ToolRegistry.load_default()
    eligibility = registry.check_eligibility(request)
    assert eligibility.eligible, eligibility.reason_codes
    run = registry.run(request)
    assert run.execution_state.value == "succeeded", run.reason_codes
    result = run.result
    assert result["runtime_mode"] == "exploratory_process"
    assert result["n_observations"] == 96
    assert result["independence_state"] == "unknown"
    assert result["n_independent_replicates"] is None
    assert result["state_review_status"] == "pending"
    assert result["interpretation_scope"] == "descriptive_only"
    assert result["domain_score"] is None
    assert result["score_state"] == "unavailable"
    assert run.measurements == []
    assert len(result["program_summaries"]) == 4
    assert {x["score_unit"] for x in result["program_summaries"]} == {
        "scanpy_control_adjusted_expression",
        "decoupler_ulm_t_value",
    }
    assert all(x["n_observations"] == 96 for x in result["program_summaries"])
    assert sum(result["cell_cycle"]["phase_counts"].values()) == 96
    assert result["cell_cycle"]["n_observations"] == 96
    assert len(result["executions"]) == 4
    table = next(a for a in run.artifacts if a.kind == "exploratory_observation_scores")
    rows = pd.read_parquet(table.path)
    assert len(rows) == 96 and rows.observation_id.is_unique
    assert set(rows.phase) <= {"G1", "S", "G2M"}
    assert np.isfinite(rows.select_dtypes(include="number")).all().all()
    for a in run.artifacts:
        assert hashlib.sha256(a.path.read_bytes()).hexdigest() == a.sha256
    assert hashlib.sha256(request.assets[0].path.read_bytes()).hexdigest() == original
    Draft202012Validator(registry.resolve_schema(run.result_schema_ref)).validate(
        result
    )


def test_missing_resource_gene_is_not_silently_omitted_or_reported_as_zero(tmp_path):
    request = _request(tmp_path, missing_gene=True)
    run = ToolRegistry.load_default().run(request)
    assert run.execution_state.value == "partial", run.reason_codes
    missing = [x for x in run.result["program_summaries"] if x["program_id"] == "S"]
    assert len(missing) == 2
    assert all(
        x["assessment_state"] == "not_assessed" and x["mean"] is None for x in missing
    )
    assert all(x["missing_genes"] == ["ABSENT"] for x in missing)
    assert run.result["cell_cycle"]["phase_counts"] is None
    assert run.result["cell_cycle"]["s_g2m_fraction"] is None
    assert run.result["cell_cycle"]["n_observations"] == 96


@pytest.mark.parametrize(
    "change,reason",
    [
        ("observation_digest", "expression_observation_set_mismatch"),
        ("observation_count", "expression_observation_set_mismatch"),
        ("asset_id", "expression_data_view_mismatch"),
        ("matrix_location", "expression_data_view_mismatch"),
        ("gene_checksum", "structured_input_schema_invalid"),
        ("duplicate_gene", "structured_input_schema_invalid"),
    ],
)
def test_exploratory_binding_rejects_inconsistent_inputs(tmp_path, change, reason):
    request = _request(tmp_path)
    payload = _payload(request)
    if change == "observation_digest":
        payload["data_view"]["observation_ids_sha256"] = "0" * 64
    elif change == "observation_count":
        payload["data_view"]["n_observations"] = 95
    elif change == "asset_id":
        payload["data_view"]["artifact_id"] = "different"
    elif change == "matrix_location":
        payload["data_view"]["matrix_location"] = "layers/other"
    elif change == "gene_checksum":
        payload["s_genes_sha256"] = "0" * 64
    else:
        payload["s_genes"].append(payload["s_genes"][0])
        payload["s_genes_sha256"] = _gene_hash(payload["s_genes"])
    run = ToolRegistry.load_default().run(_with_input(request, payload))
    assert run.execution_state.value == "failed"
    assert any(reason in r for r in run.reason_codes), run.reason_codes
    assert run.result is None and run.artifacts == []


def test_old_product_mode_still_requires_review_objects(tmp_path):
    request = _request(tmp_path).model_copy(update={"object_inputs": []})
    eligibility = ToolRegistry.load_default().check_eligibility(request)
    assert not eligibility.eligible
    assert "exactly_one_product_definition_card_required" in eligibility.reason_codes
    assert (
        "exactly_one_biological_unit_attestation_receipt_required"
        in eligibility.reason_codes
    )


def test_exploration_rejects_review_objects_instead_of_promoting_them(tmp_path):
    request = _request(tmp_path)
    extra = request.object_inputs[0].model_copy(
        update={"role": "product_definition_card"}
    )
    eligibility = ToolRegistry.load_default().check_eligibility(
        request.model_copy(update={"object_inputs": request.object_inputs + [extra]})
    )
    assert not eligibility.eligible
    assert "unsupported_object_input_role" in eligibility.reason_codes


def test_selected_layer_and_declared_normalized_input_match_raw_count_recipe(tmp_path):
    raw_root, normalized_root = tmp_path / "counts", tmp_path / "normalized"
    raw_root.mkdir()
    normalized_root.mkdir()
    raw_request, normalized_request = _request(raw_root), _request(normalized_root)
    matrix = ad.read_h5ad(normalized_request.assets[0].path)
    counts = matrix.X.copy()
    matrix.layers["selected"] = np.log1p(
        counts * (10000.0 / counts.sum(axis=1))[:, None]
    )
    matrix.raw = matrix.copy()
    matrix.X[:] = -100  # Not the declared matrix; must never be used.
    matrix.write_h5ad(normalized_request.assets[0].path)
    sha = hashlib.sha256(normalized_request.assets[0].path.read_bytes()).hexdigest()
    payload = _payload(normalized_request)
    payload["data_view"].update(
        sha256=sha,
        parent_asset_sha256=sha,
        matrix_location="layers/selected",
        matrix_semantics="normalized_expression",
    )
    asset = normalized_request.assets[0].model_copy(
        update={
            "checksum": sha,
            "matrix_location": "layers/selected",
            "matrix_semantics": "normalized_expression",
            "input_level": InputLevel.ANALYSIS_READY,
        }
    )
    # Revalidate the request enum after constructing the fixture.
    normalized_request = ToolRequestV2.model_validate(
        normalized_request.model_copy(update={"assets": [asset]}).model_dump()
    )
    normalized_request = _with_input(normalized_request, payload)
    registry = ToolRegistry.load_default()
    raw_run, normalized_run = registry.run(raw_request), registry.run(
        normalized_request
    )
    assert (
        raw_run.execution_state.value
        == normalized_run.execution_state.value
        == "succeeded"
    )
    assert (
        raw_run.result["program_summaries"]
        == normalized_run.result["program_summaries"]
    )
    assert raw_run.result["cell_cycle"] == normalized_run.result["cell_cycle"]
    assert (
        normalized_run.result["normalization_recipe"]
        == "declared_normalized_expression"
    )
    assert (
        hashlib.sha256(normalized_request.assets[0].path.read_bytes()).hexdigest()
        == sha
    )


def test_failed_ulm_is_partial_and_does_not_erase_other_measurements(
    tmp_path, monkeypatch
):
    from bridge.tool_packages.p0_06_proliferation_stress_response import exploratory
    from bridge.tool_packages.p0_06_proliferation_stress_response.method_runtime import (
        ProcessMethodError,
    )

    real_require = exploratory._require_module

    def require_module(name):
        if name == "decoupler":
            raise ProcessMethodError("decoupler_runtime_unavailable")
        return real_require(name)

    monkeypatch.setattr(exploratory, "_require_module", require_module)
    run = ToolRegistry.load_default().run(_request(tmp_path))
    assert run.execution_state.value == "partial"
    unavailable = [
        r
        for r in run.result["program_summaries"]
        if r["method_id"] == "PROC-SCORE-DECOUPLER"
    ]
    assert len(unavailable) == 2
    assert all(
        r["mean"] is None and r["reason_codes"] == ["decoupler_runtime_unavailable"]
        for r in unavailable
    )
    assert run.result["cell_cycle"]["assessment_state"] == "available"
    assert sum(run.result["cell_cycle"]["phase_counts"].values()) == 96


@pytest.mark.parametrize(
    "bad_value,expected",
    [
        (-1.0, "raw_count_matrix_invalid"),
        (0.5, "raw_count_matrix_invalid"),
        (float("nan"), "expression_matrix_nonfinite"),
    ],
)
def test_invalid_count_values_fail_without_publishing(tmp_path, bad_value, expected):
    request = _request(tmp_path)
    matrix = ad.read_h5ad(request.assets[0].path)
    matrix.X[0, 0] = bad_value
    matrix.write_h5ad(request.assets[0].path)
    sha = hashlib.sha256(request.assets[0].path.read_bytes()).hexdigest()
    payload = _payload(request)
    payload["data_view"].update(sha256=sha, parent_asset_sha256=sha)
    asset = request.assets[0].model_copy(update={"checksum": sha})
    request = _with_input(request.model_copy(update={"assets": [asset]}), payload)
    run = ToolRegistry.load_default().run(request)
    assert run.execution_state.value == "failed"
    assert expected in run.reason_codes
    assert run.result is None and not run.artifacts


def test_repeated_seed_is_deterministic_and_uses_all_cells(tmp_path):
    request = _request(tmp_path)
    registry = ToolRegistry.load_default()
    first = registry.run(request)
    second = registry.run(
        request.model_copy(update={"output_dir": tmp_path / "second"})
    )
    assert first.result == second.result
    assert first.input_hash == second.input_hash


def test_method_receipt_distinguishes_program_and_cycle_control_sizes(tmp_path):
    run = ToolRegistry.load_default().run(_request(tmp_path))
    params = run.result["method_parameters"]
    assert params["scanpy_ctrl_size"] == 50
    assert params["cell_cycle_ctrl_size"] == 6
    assert params["decoupler_empty"] is False
    assert params["use_raw"] is False


def _duplicate_symbol(request, *, program):
    matrix = ad.read_h5ad(request.assets[0].path)
    # Feature 28 is CONTROL0; retain its distinct original feature ID and counts.
    matrix.var.iloc[28, matrix.var.columns.get_loc("gene_symbol")] = (
        "SPHASE0" if program else "CONTROL1"
    )
    matrix.write_h5ad(request.assets[0].path)
    sha = hashlib.sha256(request.assets[0].path.read_bytes()).hexdigest()
    payload = _payload(request)
    payload["data_view"].update(sha256=sha, parent_asset_sha256=sha)
    asset = request.assets[0].model_copy(update={"checksum": sha})
    return _with_input(request.model_copy(update={"assets": [asset]}), payload)


def test_unique_feature_ids_preserve_duplicate_background_symbols_without_collapsing(
    tmp_path,
):
    request = _duplicate_symbol(_request(tmp_path), program=False)
    sha = request.assets[0].checksum
    run = ToolRegistry.load_default().run(request)
    assert run.execution_state.value == "succeeded", run.reason_codes
    assert run.result["n_observations"] == 96
    assert run.result["n_features"] == 80
    assert run.result["duplicated_background_symbol_count"] == 1
    assert run.result["target_feature_ids"]["SPHASE0"] == "16"
    assert (
        run.result["feature_resolution_policy"]
        == "exact_symbols_to_unique_input_feature_ids"
    )
    assert all(x["observed_gene_count"] == 6 for x in run.result["program_summaries"])
    assert sum(run.result["cell_cycle"]["phase_counts"].values()) == 96
    assert hashlib.sha256(request.assets[0].path.read_bytes()).hexdigest() == sha


def test_ambiguous_program_symbol_is_not_arbitrarily_selected_or_summed(tmp_path):
    request = _duplicate_symbol(_request(tmp_path), program=True)
    run = ToolRegistry.load_default().run(request)
    assert run.execution_state.value == "partial", run.reason_codes
    s = [x for x in run.result["program_summaries"] if x["program_id"] == "S"]
    assert len(s) == 2
    assert all(x["mean"] is None and x["ambiguous_genes"] == ["SPHASE0"] for x in s)
    assert all(x["observed_gene_count"] == 5 and not x["missing_genes"] for x in s)
    assert "SPHASE0" not in run.result["target_feature_ids"]
    assert run.result["cell_cycle"]["phase_counts"] is None
    assert run.result["cell_cycle"]["s_ambiguous_genes"] == ["SPHASE0"]
    g2m = [x for x in run.result["program_summaries"] if x["program_id"] == "G2M"]
    assert all(x["assessment_state"] == "available" for x in g2m)
