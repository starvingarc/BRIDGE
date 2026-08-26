from __future__ import annotations

import hashlib
import json
from pathlib import Path

import anndata as ad
import numpy as np
import pandas as pd
import pytest

from bridge.tool_packages.p0_01_input_qc.io import sha256_path
from bridge.tool_packages.p0_03_target_regional.adapter import ROLE_MODELS
from bridge.tool_packages.p0_03_target_regional.method_models import (
    TargetRegionalMethodBundle,
)
from bridge.toolkit.contracts import (
    ExecutionState,
    InputAsset,
    StructuredInputRef,
)
from bridge.toolkit.registry import ToolRegistry
from tests.test_p0_03_target_regional import (
    _canonical_bytes,
    _mutate,
    _request,
)


def _write_reference_profile(
    root: Path,
    *,
    profile_id: str,
    assay: str,
    source_id: str,
    matrix: np.ndarray,
    genes: list[str],
) -> dict:
    matrix_path = root / f"{profile_id}.npy"
    metadata_path = root / f"{profile_id}.metadata.json"
    np.save(matrix_path, matrix, allow_pickle=False)
    labels = [
        "state:alpha",
        "state:alpha",
        "state:beta",
        "state:beta",
        "state:gamma",
        "state:gamma",
    ]
    metadata = {
        "genes": genes,
        "rows": [
            {
                "label": label,
                "n_observations": 10,
                "sample_id": f"reference-{index}",
            }
            for index, label in enumerate(labels)
        ],
    }
    metadata_path.write_bytes(_canonical_bytes(metadata))
    return {
        "profile_id": profile_id,
        "source_id": source_id,
        "source_family_id": f"source-family:{source_id}",
        "evidence_family_id": f"evidence-family:{source_id}",
        "assay": assay,
        "anatomy": "fully-synthetic",
        "developmental_time": "fully-synthetic",
        "label_level": "L1",
        "role": "primary" if assay == "scRNA-seq" else "sensitivity",
        "status": "candidate",
        "n_samples": 6,
        "n_observations": 60,
        "n_genes": len(genes),
        "labels": sorted(set(labels)),
        "matrix_file": matrix_path.name,
        "matrix_sha256": sha256_path(matrix_path),
        "metadata_file": metadata_path.name,
        "metadata_sha256": sha256_path(metadata_path),
        "source_sha256": "a" * 64,
        "feature_selection": {
            "method": "fully_synthetic_fixture",
            "query_independent": True,
            "selected_gene_count": len(genes),
        },
        "exclusions": {},
    }


def _expression_request(tmp_path: Path):
    request = _request(tmp_path)
    objects = request.object_inputs[0].path.parent
    assignment_ref = next(
        item
        for item in request.object_inputs
        if item.role == "biological_unit_assignment"
    )
    assignments = json.loads(assignment_ref.path.read_text(encoding="utf-8"))[
        "assignments"
    ]
    observation_ids = [item["observation_id"] for item in assignments]
    genes = [f"G{index}" for index in range(8)]
    alpha = np.asarray([8.0, 7.0, 6.0, 5.0, 1.0, 0.5, 0.2, 0.1])
    beta = np.asarray([0.3, 0.5, 1.0, 2.0, 5.0, 6.0, 7.0, 8.0])
    gamma = np.asarray([1.0, 4.0, 1.5, 5.0, 2.0, 6.0, 2.5, 7.0])
    reference = np.vstack([alpha, alpha * 0.9, beta, beta * 0.9, gamma, gamma * 0.9])
    profiles = [
        _write_reference_profile(
            objects,
            profile_id="reference-profile:synthetic-sc",
            assay="scRNA-seq",
            source_id="source:synthetic-sc",
            matrix=reference,
            genes=genes,
        ),
        _write_reference_profile(
            objects,
            profile_id="reference-profile:synthetic-sn",
            assay="snRNA-seq",
            source_id="source:synthetic-sn",
            matrix=reference * 0.95,
            genes=genes,
        ),
    ]
    marker_payload = {
        "object_version": "0.1.0",
        "cards": [
            {
                "card_id": "program-card:alpha",
                "version": "1.0.0",
                "state_id": "state:alpha",
                "level": "L1",
                "positive_markers": ["G0", "G1", "G2"],
                "negative_markers": ["G6", "G7"],
                "source_ids": ["source:fully-synthetic"],
                "review_status": "candidate",
                "allowed_use": ["shadow_evidence"],
            }
        ],
    }
    marker_path = objects / "marker_programs.json"
    marker_path.write_bytes(_canonical_bytes(marker_payload))
    request = _mutate(
        request,
        "reference_manifest",
        lambda payload: payload.update(
            {
                "marker_program_file": marker_path.name,
                "marker_program_sha256": sha256_path(marker_path),
                "profiles": profiles,
            }
        ),
    )
    manifest_sha256 = next(
        item.sha256
        for item in request.object_inputs
        if item.role == "reference_manifest"
    )
    request = _mutate(
        request,
        "cell_state_evidence_profile",
        lambda payload: payload.update({"reference_manifest_sha256": manifest_sha256}),
    )
    analysis_units = np.asarray([item["analysis_unit_ref"] for item in assignments])
    expression = np.vstack(
        [
            (
                alpha + (index % 5) * 0.01
                if analysis_unit == "preparation:demo@1.0.0"
                else beta + (index % 5) * 0.01
            )
            for index, analysis_unit in enumerate(analysis_units)
        ]
    )
    asset_path = tmp_path / "expression_view.h5ad"
    ad.AnnData(
        X=expression,
        obs=pd.DataFrame(
            {"analysis_unit_ref": analysis_units},
            index=pd.Index(observation_ids, name="observation_id"),
        ),
        var=pd.DataFrame(
            {"gene_symbol": genes},
            index=pd.Index(genes, name="feature_id"),
        ),
    ).write_h5ad(asset_path)
    profile_ref = next(
        item
        for item in request.object_inputs
        if item.role == "cell_state_evidence_profile"
    )
    profile = json.loads(profile_ref.path.read_text(encoding="utf-8"))
    view = profile["input_data_view"]
    asset = InputAsset(
        asset_id="asset:synthetic-expression-view",
        path=asset_path,
        format="h5ad",
        input_level="analysis_ready",
        checksum=sha256_path(asset_path),
        matrix_location="X",
        matrix_semantics="normalized_expression",
        assay="scRNA-seq",
        metadata={
            "data_view_id": view["view_id"],
            "parent_asset_sha256": view["parent_asset_sha256"],
        },
    )
    method_spec = {
        "object_version": "0.1.0",
        "method_spec_id": "target-regional-method-spec:fully-synthetic",
        "method_spec_version": "1.0.0",
        "status": "candidate",
        "expression_asset_id": asset.asset_id,
        "observation_id_column": None,
        "gene_symbol_column": "gene_symbol",
        "target_reference_profile_ids": [profiles[0]["profile_id"]],
        "regional_reference_profile_ids": [item["profile_id"] for item in profiles],
        "selected_method_ids": [
            "TRG-PBCORR",
            "REG-PBCORR",
            "TRG-NNLS",
            "TRG-DECOUPLER",
            "REG-DECOUPLER",
            "TRG-BOOTSTRAP",
            "REG-CROSSREF",
            "REG-MODALITY",
        ],
        "target_program_card_ids": ["program-card:alpha"],
        "regional_program_card_ids": ["program-card:alpha"],
        "minimum_shared_genes": 4,
        "minimum_program_genes": 2,
        "bootstrap_replicates": 50,
        "bootstrap_confidence_level": 0.9,
    }
    method_path = objects / "target_regional_method_spec.json"
    raw = _canonical_bytes(method_spec)
    method_path.write_bytes(raw)
    method_ref = StructuredInputRef(
        input_id="input-target-regional-methods",
        role="target_regional_method_spec",
        schema_ref=ROLE_MODELS["target_regional_method_spec"][0],
        object_version="0.1.0",
        path=method_path,
        sha256=hashlib.sha256(raw).hexdigest(),
        media_type="application/json",
    )
    return request.model_copy(
        update={
            "assets": [asset],
            "object_inputs": [*request.object_inputs, method_ref],
            "random_seed": 17,
        }
    )


def test_expression_mode_executes_registered_methods(tmp_path: Path) -> None:
    run = ToolRegistry.load_default().run(_expression_request(tmp_path))
    assert run.execution_state is ExecutionState.PARTIAL
    assert run.result["method_artifact"] is not None
    artifact = next(
        item for item in run.artifacts if item.kind == "target_regional_method_bundle"
    )
    bundle = TargetRegionalMethodBundle.model_validate_json(
        artifact.path.read_text(encoding="utf-8")
    )
    assert {item.method_id.value for item in bundle.method_evidence} == {
        "TRG-PBCORR",
        "REG-PBCORR",
        "TRG-NNLS",
        "TRG-DECOUPLER",
        "REG-DECOUPLER",
        "TRG-BOOTSTRAP",
        "REG-CROSSREF",
        "REG-MODALITY",
    }
    assert {item.execution_state.value for item in bundle.method_evidence} == {
        "succeeded",
        "partial",
    }
    assert len(bundle.analysis_unit_refs) == 1
    assert len(bundle.independence_group_refs) == 1
    assert bundle.reference_support
    assert {item.evidence_scope for item in bundle.reference_support} == {
        "target_identity",
        "regional_fidelity",
    }
    evidence_by_id = {item.method_id.value: item for item in bundle.method_evidence}
    assert evidence_by_id["TRG-PBCORR"].reference_profile_ids == [
        "reference-profile:synthetic-sc"
    ]
    assert evidence_by_id["REG-PBCORR"].reference_profile_ids == [
        "reference-profile:synthetic-sc",
        "reference-profile:synthetic-sn",
    ]
    assert bundle.continuous_identity_weights
    assert bundle.program_activity
    assert bundle.bootstrap_intervals[0].interval_state == "descriptive_only"
    assert "one_independent_unit_descriptive_only" in run.reason_codes
    assert bundle.robustness
    assert bundle.domain_score is None
    assert bundle.score_state.value == "shadow"


@pytest.mark.parametrize("remove_asset", [True, False])
def test_expression_mode_requires_method_spec_and_asset(
    tmp_path: Path, remove_asset: bool
) -> None:
    request = _expression_request(tmp_path)
    if remove_asset:
        request = request.model_copy(update={"assets": []})
    else:
        request = request.model_copy(
            update={
                "object_inputs": [
                    item
                    for item in request.object_inputs
                    if item.role != "target_regional_method_spec"
                ]
            }
        )
    eligibility = ToolRegistry.load_default().check_eligibility(request)
    assert not eligibility.eligible
    assert "expression_method_inputs_incomplete" in eligibility.reason_codes


def test_expression_asset_replacement_fails_closed(tmp_path: Path) -> None:
    request = _expression_request(tmp_path)
    with request.assets[0].path.open("ab") as handle:
        handle.write(b"changed")
    run = ToolRegistry.load_default().run(request)
    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["expression_asset_checksum_mismatch"]
