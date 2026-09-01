from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import anndata as ad
import numpy as np
import pytest

from bridge.tool_packages._configurable_contracts import BiologicalUnitManifest
from bridge.tool_packages.p0_06_proliferation_stress_response.method_models import (
    MethodExecutionState,
    ProcessMethodBundle,
    ProcessMethodId,
)
from bridge.tool_packages.p0_06_proliferation_stress_response.visualization_data import (
    CellCycleVisualizationRecord,
    ProliferationStressVisualizationDataV1,
)
from bridge.toolkit.contracts import (
    ExecutionState,
    InputAsset,
    InputLevel,
    StructuredInputRef,
    ToolRequestV2,
)
from bridge.toolkit.registry import ToolRegistry
from tests.p0_biological_units import bind_reviewed_biological_units
from tests.test_p0_06_proliferation_stress_response import (
    CORE_METHOD_IDS,
    CREATED_AT,
    _payloads,
)

ROLE_CONTRACTS = {
    "product_case": ("bridge://schemas/product-case/v0.1", "0.1.0"),
    "product_definition_card": (
        "bridge://schemas/product-definition-card/v0.1",
        "0.1.0",
    ),
    "development_window_spec": (
        "bridge://schemas/development-window-spec/v0.1",
        "0.1.0",
    ),
    "program_spec": ("bridge://schemas/program-spec/v0.1", "0.1.0"),
    "cell_state_evidence_profile": (
        "bridge://schemas/cell-state-evidence-profile/v0.3",
        "0.3.0",
    ),
    "protocol_ir": ("bridge://schemas/protocol-ir/v0.1", "0.1.0"),
    "program_evidence_bundle": (
        "bridge://schemas/program-evidence-bundle/v0.1",
        "0.1.0",
    ),
    "biological_unit_manifest": (
        "bridge://schemas/biological-unit-manifest/v0.1",
        "0.1.0",
    ),
    "biological_unit_assignment": (
        "bridge://schemas/biological-unit-assignment/v0.1",
        "0.1.0",
    ),
    "process_method_spec": (
        "bridge://schemas/process-method-spec/v0.1",
        "0.1.0",
    ),
    "process_method_input": (
        "bridge://schemas/process-method-input/v0.1",
        "0.1.0",
    ),
}


def _canonical_bytes(payload: object) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def _program_content_sha256(
    *,
    targets: list[dict[str, object]] | None = None,
    s_genes: list[str] | None = None,
    g2m_genes: list[str] | None = None,
) -> str:
    payload = (
        {
            "content_type": "weighted_program_targets",
            "targets": sorted(targets or [], key=lambda item: str(item["gene"])),
        }
        if targets is not None
        else {
            "content_type": "cell_cycle_phase_genes",
            "s_genes": sorted(s_genes or []),
            "g2m_genes": sorted(g2m_genes or []),
        }
    )
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def _replace_json_input(
    request: ToolRequestV2, role: str, payload: object
) -> tuple[ToolRequestV2, str]:
    old = next(item for item in request.object_inputs if item.role == role)
    raw = _canonical_bytes(payload)
    old.path.write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    replacement = old.model_copy(update={"sha256": digest})
    refs = [
        replacement if item.role == role else item for item in request.object_inputs
    ]
    return request.model_copy(update={"object_inputs": refs}), digest


def _write_ref(root: Path, role: str, payload: object) -> StructuredInputRef:
    raw = _canonical_bytes(payload)
    path = root / f"{role}.json"
    path.write_bytes(raw)
    schema_ref, version = ROLE_CONTRACTS[role]
    return StructuredInputRef(
        input_id=f"input:{role}",
        role=role,
        schema_ref=schema_ref,
        object_version=version,
        path=path,
        sha256=hashlib.sha256(raw).hexdigest(),
        media_type="application/json",
    )


def _write_expression(path: Path) -> tuple[list[str], list[str], str]:
    observations = [f"demo-cell-{index:03d}" for index in range(96)]
    proliferation = [f"PROLIF{index}" for index in range(8)]
    stress = [f"STRESS{index}" for index in range(8)]
    s_genes = [f"SPHASE{index}" for index in range(6)]
    g2m_genes = [f"G2MPHASE{index}" for index in range(6)]
    genes = (
        proliferation
        + stress
        + s_genes
        + g2m_genes
        + [f"CONTROL{index}" for index in range(52)]
    )
    rng = np.random.default_rng(20260827)
    matrix = np.log1p(rng.poisson(2.0, size=(len(observations), len(genes))))
    for index in range(len(observations)):
        unit = index % 4
        matrix[index, :8] += unit * 0.35
        matrix[index, 8:16] += (3 - unit) * 0.25
        if index % 3 == 0:
            matrix[index, 16:22] += 1.5
        elif index % 3 == 1:
            matrix[index, 22:28] += 1.5
    adata = ad.AnnData(
        X=matrix.astype(np.float64),
        obs={"demo_group": [f"demo-{index % 4}" for index in range(96)]},
        var={"gene_symbol": genes},
    )
    adata.obs_names = observations
    adata.write_h5ad(path)
    return observations, genes, hashlib.sha256(path.read_bytes()).hexdigest()


def _method_request(tmp_path: Path) -> ToolRequestV2:
    values = deepcopy(_payloads())
    object_root = tmp_path / "objects"
    object_root.mkdir()
    expression_path = tmp_path / "demo-process-expression.h5ad"
    observations, genes, asset_sha = _write_expression(expression_path)

    view = {
        "view_id": "data-view:process-demo",
        "view_kind": "qc_selected_observations",
        "artifact_id": "asset:process-demo",
        "sha256": asset_sha,
        "parent_asset_id": "asset:process-demo-parent",
        "parent_asset_sha256": "f" * 64,
        "matrix_location": "X",
        "matrix_semantics": "normalized_expression",
        "n_observations": len(observations),
        "observation_ids_sha256": "0" * 64,
        "sample_or_preparation_ref": "preparation:demo@1.0.0",
        "selection_spec_ref": "selection:process-demo@1.0.0",
    }
    units = [
        (
            f"preparation:process-{index}@1.0.0",
            f"sample:process-{index}@1.0.0",
        )
        for index in range(4)
    ]
    bind_reviewed_biological_units(
        values,
        view,
        slug="process-demo",
        units=units,
        observation_ids=observations,
    )

    cell_state = values["cell_state_evidence_profile"]
    cell_state.update(
        {
            "profile_id": "cell-state-profile:run-process-demo",
            "n_observations": len(observations),
            "n_genes": len(genes),
            "denominator": "selected_data_view",
            "composition": {
                "state": "shadow",
                "records": [
                    {
                        "view": "reconciliation_state",
                        "source_id": None,
                        "label": "state:target",
                        "label_level": "L2",
                        "state_evidence_state": "candidate",
                        "denominator_scope": "selected_data_view",
                        "count": 48,
                        "fraction": 0.5,
                        "denominator": len(observations),
                    },
                    {
                        "view": "reconciliation_state",
                        "source_id": None,
                        "label": "unknown",
                        "label_level": "L2",
                        "state_evidence_state": "unknown",
                        "denominator_scope": "selected_data_view",
                        "count": 48,
                        "fraction": 0.5,
                        "denominator": len(observations),
                    },
                ],
            },
            "measurement_spec_sha256": "1" * 64,
            "annotation_vocabulary_version": "1.0.0",
            "annotation_vocabulary_sha256": "2" * 64,
            "reference_manifest_version": "1.0.0",
            "reference_manifest_sha256": "3" * 64,
            "upstream_qc_profile_ref": "qc-profile:process-demo",
            "upstream_qc_profile_sha256": "4" * 64,
            "input_data_view": view,
            "open_set_state": "not_assessed",
            "calibration_state": "not_assessed",
            "producer_run_ref": "run-process-demo",
            "producer_tool_id": "P0-02",
            "producer_tool_version": "0.5.0",
            "environment_spec_ref": "ENV-CELLSTATE-PY-v0.1",
        }
    )

    program_spec = values["program_spec"]
    program_spec["aggregation_method_ids"] = CORE_METHOD_IDS
    program_spec["program_rules"][0]["allowed_analysis_scopes"] = [
        "whole_product",
        "state_specific",
    ]
    program_spec["program_rules"][0]["allowed_state_ids"] = ["state:target"]
    proliferation_targets = [
        {"gene": f"PROLIF{index}", "weight": 1.0} for index in range(8)
    ]
    program_spec["program_rules"][0]["targets"] = proliferation_targets
    program_spec["program_rules"][0]["gene_set_sha256"] = _program_content_sha256(
        targets=proliferation_targets
    )
    program_spec["program_rules"][1]["allowed_analysis_scopes"] = [
        "whole_product",
        "state_specific",
    ]
    stress_targets = [{"gene": f"STRESS{index}", "weight": 1.0} for index in range(8)]
    program_spec["program_rules"][1]["targets"] = stress_targets
    program_spec["program_rules"][1]["gene_set_sha256"] = _program_content_sha256(
        targets=stress_targets
    )
    s_genes = [f"SPHASE{index}" for index in range(6)]
    g2m_genes = [f"G2MPHASE{index}" for index in range(6)]
    program_spec["program_rules"].append(
        {
            "program_id": "program:cell-cycle",
            "gene_set_ref": "gene-set:cell-cycle-demo",
            "gene_set_sha256": _program_content_sha256(
                s_genes=s_genes,
                g2m_genes=g2m_genes,
            ),
            "s_genes": s_genes,
            "g2m_genes": g2m_genes,
            "allowed_analysis_scopes": ["whole_product", "state_specific"],
            "allowed_state_ids": ["state:target"],
            "allowed_stage_ids": ["stage:target"],
            "allowed_metric_ids": ["metric:program-score"],
            "minimum_gene_coverage": 0.8,
            "allowed_lod_states": ["qualified"],
            "resolvable_lod_states": ["qualified"],
            "review_outcomes": {
                "elevated": "transcriptomic_review_flag",
                "below-rule": "not_detected_above_lod",
            },
            "orthogonal_follow_up_refs": ["assay:orthogonal-review"],
            "provenance_refs": ["provenance:cell-cycle-rule"],
        }
    )

    method_spec = {
        "object_version": "0.1.0",
        "method_spec_id": "process-method-spec:demo",
        "method_spec_version": "1.0.0",
        "status": "candidate",
        "expression_asset_id": view["artifact_id"],
        "expression_layer": None,
        "gene_symbol_column": "gene_symbol",
        "selected_method_ids": [item.value for item in ProcessMethodId],
        "selected_analysis_scopes": ["whole_product", "state_specific"],
        "programs": [
            {"program_id": "program:proliferation"},
            {"program_id": "program:stress"},
        ],
        "cell_cycle": {"program_id": "program:cell-cycle"},
        "scanpy_ctrl_size": 5,
        "scanpy_n_bins": 5,
        "scanpy_ctrl_as_ref": True,
        "decoupler_tmin": 5,
        "minimum_cells_per_summary": 6,
        "lower_quantile": 0.1,
        "upper_quantile": 0.9,
        "active": True,
    }

    refs = {}
    for role in (
        "product_case",
        "product_definition_card",
        "development_window_spec",
        "program_spec",
        "cell_state_evidence_profile",
        "protocol_ir",
        "biological_unit_manifest",
        "biological_unit_assignment",
    ):
        refs[role] = _write_ref(object_root, role, values[role])
    refs["process_method_spec"] = _write_ref(
        object_root, "process_method_spec", method_spec
    )

    bundle = values["program_evidence_bundle"]
    bundle.update(
        {
            "product_case_ref": {
                "object_id": values["product_case"]["product_case_id"],
                "object_version": values["product_case"]["case_version"],
            },
            "product_case_sha256": refs["product_case"].sha256,
            "product_definition_ref": values["product_case"]["product_definition_ref"],
            "product_definition_sha256": refs["product_definition_card"].sha256,
            "development_window_ref": {
                "object_id": values["development_window_spec"]["window_spec_id"],
                "object_version": values["development_window_spec"][
                    "window_spec_version"
                ],
            },
            "development_window_sha256": refs["development_window_spec"].sha256,
            "program_spec_ref": {
                "object_id": program_spec["program_spec_id"],
                "object_version": program_spec["program_spec_version"],
            },
            "program_spec_sha256": refs["program_spec"].sha256,
            "cell_state_profile_ref": cell_state["profile_id"],
            "cell_state_profile_sha256": refs["cell_state_evidence_profile"].sha256,
            "protocol_context_ref": values["protocol_ir"]["protocol_context_id"],
            "protocol_context_sha256": refs["protocol_ir"].sha256,
        }
    )
    refs["program_evidence_bundle"] = _write_ref(
        object_root, "program_evidence_bundle", bundle
    )

    assignments = values["biological_unit_assignment"]["assignments"]
    method_input = {
        "object_version": "0.1.0",
        "method_input_id": "process-method-input:demo",
        "method_input_version": "1.0.0",
        "product_case_ref": "product-case:demo@1.0.0",
        "product_case_sha256": refs["product_case"].sha256,
        "cell_state_profile_id": cell_state["profile_id"],
        "cell_state_profile_sha256": refs["cell_state_evidence_profile"].sha256,
        "data_view_ref": view["view_id"],
        "observation_ids_sha256": view["observation_ids_sha256"],
        "biological_unit_manifest_ref": view["biological_unit_manifest_ref"],
        "biological_unit_manifest_sha256": refs["biological_unit_manifest"].sha256,
        "biological_unit_assignment_sha256": refs["biological_unit_assignment"].sha256,
        "observation_states": [
            {
                "observation_id": item["observation_id"],
                "state_id": "state:target" if index < 48 else None,
                "state": "candidate" if index < 48 else "unknown",
            }
            for index, item in enumerate(assignments)
        ],
        "created_at": CREATED_AT,
    }
    refs["process_method_input"] = _write_ref(
        object_root, "process_method_input", method_input
    )
    return ToolRequestV2(
        request_id="request-p0-06-method-runtime",
        tool_id="P0-06",
        tool_version="0.4.0",
        output_dir=tmp_path / "output",
        assets=[
            InputAsset(
                asset_id=view["artifact_id"],
                path=expression_path,
                format="h5ad",
                input_level=InputLevel.ANALYSIS_READY,
                checksum=asset_sha,
                matrix_location="X",
                matrix_semantics="normalized_expression",
                assay="scRNA-seq",
            )
        ],
        random_seed=17,
        object_inputs=list(refs.values()),
    )


def test_real_method_runtime_executes_and_is_deterministic(tmp_path: Path) -> None:
    registry = ToolRegistry.load_default()
    request = _method_request(tmp_path)

    eligibility = registry.check_eligibility(request)
    assert eligibility.eligible, eligibility.reason_codes
    first = registry.run(request)
    second = registry.run(request)

    assert first.execution_state is ExecutionState.SUCCEEDED
    assert first.run_id == second.run_id
    assert len(first.artifacts) == 17
    path = next(
        item.path for item in first.artifacts if item.kind == "process_method_bundle"
    )
    bundle = ProcessMethodBundle.model_validate_json(path.read_text())
    assert {item.method_id for item in bundle.executions} == set(ProcessMethodId)
    assert all(
        item.execution_state is MethodExecutionState.SUCCEEDED
        for item in bundle.executions
    )
    assert bundle.program_scores
    assert bundle.cell_cycle_summaries
    assert bundle.program_spec_sha256 == next(
        item.sha256 for item in request.object_inputs if item.role == "program_spec"
    )
    assert bundle.evidence_state == "shadow"
    assert bundle.score_state == "unavailable"
    assert bundle.domain_score is None
    data_artifact = next(
        item
        for item in first.artifacts
        if item.kind == "proliferation_stress_visualization_data"
    )
    visual_data = ProliferationStressVisualizationDataV1.model_validate_json(
        data_artifact.path.read_text()
    )
    assert {
        (item.method_id, item.score_unit, item.gene_coverage_basis)
        for item in visual_data.program_score_records
    } == {
        (
            ProcessMethodId.SCANPY_SCORE_GENES,
            "scanpy_control_adjusted_expression",
            "scanpy_positive_weight_targets_only",
        ),
        (
            ProcessMethodId.DECOUPLER_ULM,
            "decoupler_ulm_t_value",
            "decoupler_all_signed_weighted_targets",
        ),
    }
    assert all(
        item.quantile_semantics
        == "selected_view_cell_distribution_not_confidence_interval"
        and item.lower_quantile_probability == visual_data.lower_quantile_probability
        and item.upper_quantile_probability == visual_data.upper_quantile_probability
        for item in visual_data.program_score_records
    )
    for item in visual_data.cell_cycle_records:
        if item.assessment_state == "available":
            assert item.phase_assignment_state == "transcriptionally_assigned"
            assert item.g1_count + item.s_count + item.g2m_count == item.n_observations
            assert (
                item.g1_fraction + item.s_fraction + item.g2m_fraction
                == pytest.approx(1.0)
            )
        else:
            assert item.phase_assignment_state == "not_assessed"
            assert all(
                value is None
                for value in (
                    item.g1_count,
                    item.s_count,
                    item.g2m_count,
                    item.g1_fraction,
                    item.s_fraction,
                    item.g2m_fraction,
                )
            )
    missing = visual_data.cell_cycle_records[0].model_dump(mode="python")
    for field in (
        "mean_s_score",
        "mean_g2m_score",
        "g1_count",
        "s_count",
        "g2m_count",
        "g1_fraction",
        "s_fraction",
        "g2m_fraction",
        "cycling_fraction",
    ):
        missing[field] = None
    missing["assessment_state"] = "not_assessed"
    missing["phase_assignment_state"] = "not_assessed"
    assert CellCycleVisualizationRecord.model_validate(missing).g1_count is None
    missing["g1_count"] = 0
    with pytest.raises(ValueError, match="must stay null"):
        CellCycleVisualizationRecord.model_validate(missing)
    formats = {
        item.media_type
        for item in first.artifacts
        if item.kind == "visualization_render"
    }
    assert formats == {"image/svg+xml", "image/png", "application/pdf"}
    kinds = {
        "proliferation_stress_visualization_data",
        "visualization_table",
        "visualization_render",
        "visualization_artifact_set",
    }
    first_signature = sorted(
        (item.kind, item.path.name, item.media_type, item.sha256)
        for item in first.artifacts
        if item.kind in kinds
    )
    second_signature = sorted(
        (item.kind, item.path.name, item.media_type, item.sha256)
        for item in second.artifacts
        if item.kind in kinds
    )
    assert first_signature == second_signature


def test_method_runtime_rejects_replicate_count_above_manifest(
    tmp_path: Path,
) -> None:
    registry = ToolRegistry.load_default()
    request = _method_request(tmp_path)

    manifest_ref = next(
        item
        for item in request.object_inputs
        if item.role == "biological_unit_manifest"
    )
    manifest = BiologicalUnitManifest.model_validate_json(manifest_ref.path.read_text())
    assert len(manifest.independence_group_refs) == 4

    program_ref = next(
        item for item in request.object_inputs if item.role == "program_spec"
    )
    program_spec = json.loads(program_ref.path.read_text())
    program_spec["attribution_rule"]["minimum_independent_replicates"] = 5
    request, program_sha = _replace_json_input(request, "program_spec", program_spec)

    protocol_ref = next(
        item for item in request.object_inputs if item.role == "protocol_ir"
    )
    protocol = json.loads(protocol_ref.path.read_text())
    protocol["independent_replicate_count"] = 5
    request, protocol_sha = _replace_json_input(request, "protocol_ir", protocol)

    bundle_ref = next(
        item for item in request.object_inputs if item.role == "program_evidence_bundle"
    )
    bundle = json.loads(bundle_ref.path.read_text())
    bundle["program_spec_sha256"] = program_sha
    bundle["protocol_context_sha256"] = protocol_sha
    request, _ = _replace_json_input(request, "program_evidence_bundle", bundle)

    eligibility = registry.check_eligibility(request)

    assert not eligibility.eligible
    assert (
        "protocol_independent_replicate_count_exceeds_manifest"
        in eligibility.reason_codes
    )


@pytest.mark.parametrize(
    ("mutation", "expected_reason"),
    [
        ("gene", "program_gene_set_content_checksum_mismatch"),
        ("weight", "program_gene_set_content_checksum_mismatch"),
        ("phase", "cell_cycle_gene_set_content_checksum_mismatch"),
    ],
)
def test_real_method_runtime_rejects_content_under_stale_program_digest(
    tmp_path: Path,
    mutation: str,
    expected_reason: str,
) -> None:
    registry = ToolRegistry.load_default()
    request = _method_request(tmp_path)
    program_ref = next(
        item for item in request.object_inputs if item.role == "program_spec"
    )
    program_spec = json.loads(program_ref.path.read_text())
    if mutation == "gene":
        program_spec["program_rules"][0]["targets"][0]["gene"] = "PROLIF-CHANGED"
    elif mutation == "weight":
        program_spec["program_rules"][0]["targets"][0]["weight"] = 2.0
    else:
        program_spec["program_rules"][2]["s_genes"][0] = "SPHASE-CHANGED"
    request, program_sha = _replace_json_input(request, "program_spec", program_spec)

    bundle_ref = next(
        item for item in request.object_inputs if item.role == "program_evidence_bundle"
    )
    bundle = json.loads(bundle_ref.path.read_text())
    bundle["program_spec_sha256"] = program_sha
    request, _ = _replace_json_input(request, "program_evidence_bundle", bundle)

    eligibility = registry.check_eligibility(request)

    assert not eligibility.eligible
    assert expected_reason in eligibility.reason_codes


def test_real_method_runtime_rejects_replaced_expression(tmp_path: Path) -> None:
    registry = ToolRegistry.load_default()
    request = _method_request(tmp_path)
    request.assets[0].path.write_bytes(request.assets[0].path.read_bytes() + b"x")

    eligibility = registry.check_eligibility(request)

    assert not eligibility.eligible
    assert "expression_asset_checksum_mismatch" in eligibility.reason_codes
