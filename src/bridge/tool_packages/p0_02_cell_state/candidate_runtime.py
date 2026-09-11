"""Measured candidate CellTypist channel, separate from legacy signed releases.

A checksum-bound development receipt authorizes diagnostics, never scientific
release. The registered primary fold cannot be changed at query time. Legacy
reference correlation is retained as an explicitly separate auxiliary ToolRun.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any, Literal

import numpy as np
from pydantic import Field, model_validator
from scipy import sparse

from bridge.toolkit.contracts import (
    DataViewBinding, ExecutionState, FrozenModel, MeasurementResult, MeasurementResultV2, MeasurementSpecV2, ScoreState, ToolRun,
)
from .celltypist_runtime import load_model_bundle, predict_celltypist, classify_with_rejection
from .metrics import normalize_query
from .reference import canonicalize_source_family_id, DENIED_SOURCE_FAMILIES, resolve_reference_snapshot
from .scientific_review import load_development_review, development_review_sha256

CANDIDATE_SPEC = "CELLSTATE-scRNA-celltypist-candidate-v0.1"
AUXILIARY_SPEC = "CELLSTATE-scRNA-shadow-v0.1"


class CandidateRuntimeBinding(FrozenModel):
    object_version: Literal["1.0.0"]
    runtime_id: str = Field(min_length=1)
    measurement_spec_ref: Literal["CELLSTATE-scRNA-celltypist-candidate-v0.1"]
    model_bundle_path: Path
    model_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    verification_path: Path
    verification_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    development_review_version: Literal["1.1.0"]
    source_family_ids: list[str] = Field(min_length=1)


class CellStateCandidateProfile(FrozenModel):
    object_version: Literal["1.0.0"] = "1.0.0"
    profile_id: str
    producer_run_ref: str
    producer_tool_id: Literal["P0-02"] = "P0-02"
    producer_tool_version: str
    environment_spec_ref: str
    measurement_spec_ref: Literal["CELLSTATE-scRNA-celltypist-candidate-v0.1"] = CANDIDATE_SPEC
    measurement_spec_sha256: str
    input_data_view: DataViewBinding
    input_sha256: str
    upstream_qc_profile_ref: str
    upstream_qc_profile_sha256: str
    n_observations: int = Field(gt=0)
    n_genes: int = Field(gt=0)
    primary_method: Literal["CellTypist"] = "CellTypist"
    primary_ood: Literal["energy"] = "energy"
    knn_role: Literal["sensitivity_not_independent_vote"] = "sensitivity_not_independent_vote"
    runtime_ref: str
    model_manifest_sha256: str
    model_sha256: str
    calibration: dict[str, Any]
    verification_sha256: str
    development_summary_sha256: str
    development_review_version: Literal["1.1.0"] = "1.1.0"
    development_review_sha256: str
    development_gate_state: Literal["passed", "failed"]
    development_reason_codes: list[str]
    scientific_qualification: Literal["not_established"] = "not_established"
    qualified_state_ids: list[str] = Field(default_factory=list, max_length=0)
    per_state_release: dict[str, Literal["unavailable"]]
    candidate_composition: list[dict[str, Any]]
    feature_coverage: float = Field(ge=0, le=1)
    missing_features: list[str]
    auxiliary_run_ref: str | None
    auxiliary_state: Literal["available", "unavailable"]
    auxiliary_reason_codes: list[str]
    biological_unit_state: Literal["not_estimable"] = "not_estimable"
    target_fraction: None = None
    developmental_window_match: None = None
    score_state: Literal["unavailable"] = "unavailable"
    domain_score: None = None
    limitations: list[str]
    evidence_ids: list[str]

    @model_validator(mode="after")
    def preserve_measured_view_and_candidate_scope(self):
        if self.n_observations != self.input_data_view.n_observations:
            raise ValueError("candidate_profile_view_count_mismatch")
        if self.profile_id != f"cell-state-candidate:{self.producer_run_ref}":
            raise ValueError("candidate_profile_run_identity_mismatch")
        if sum(row["count"] for row in self.candidate_composition) != self.n_observations:
            raise ValueError("candidate_composition_not_denominator_complete")
        for row in self.candidate_composition:
            if (row["denominator"] != self.n_observations or row["count"] < 0
                    or not np.isclose(row["fraction"], row["count"] / self.n_observations, atol=1e-12)):
                raise ValueError("candidate_composition_value_mismatch")
        if set(self.per_state_release) != {row.state_id for row in load_development_review().state_reviews}:
            raise ValueError("candidate_per_state_qualification_incomplete")
        return self


def _read_json(path: Path, reason: str, expected_sha256: str | None = None):
    if not path.is_absolute() or path.is_symlink() or not path.is_file() or path.stat().st_size > 4 * 1024 * 1024:
        raise ValueError(reason)
    raw = path.read_bytes()
    if expected_sha256 is not None and hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("candidate_verification_checksum_mismatch")
    return json.loads(raw, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(reason)))


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def candidate_runtime_binding(runtime_id):
    catalog_path = os.environ.get("BRIDGE_CELLSTATE_CANDIDATE_CATALOG")
    if not catalog_path:
        raise ValueError("candidate_runtime_catalog_required")
    catalog = _read_json(Path(catalog_path), "candidate_runtime_catalog_invalid")
    if not isinstance(runtime_id, str) or runtime_id not in catalog:
        raise ValueError("candidate_runtime_not_registered")
    binding = CandidateRuntimeBinding.model_validate(catalog[runtime_id])
    if binding.runtime_id != runtime_id:
        raise ValueError("candidate_runtime_identity_mismatch")
    fingerprint = hashlib.sha256(json.dumps(binding.model_dump(mode="json"), sort_keys=True,
        separators=(",", ":")).encode()).hexdigest()
    return binding, fingerprint


def load_candidate_runtime(request):
    binding, fingerprint = candidate_runtime_binding(request.parameters.get("candidate_runtime_ref"))
    if binding.measurement_spec_ref != request.measurement_spec_ref:
        raise ValueError("candidate_runtime_measurement_binding_mismatch")
    expected = request.parameters.get("candidate_binding_sha256")
    if expected is not None and expected != fingerprint:
        raise ValueError("candidate_runtime_binding_changed")
    receipt = _read_json(binding.verification_path, "candidate_verification_invalid", binding.verification_sha256)
    if receipt.get("object_version") != "1.0.0" or receipt.get("metric_verification") != "recomputed_from_checksums_bound_predictions":
        raise ValueError("candidate_verified_development_required")
    model, calibration = load_model_bundle(binding.model_bundle_path, expected_sha256=binding.model_manifest_sha256)
    primary = receipt.get("primary_fold")
    expected = receipt.get("models", {}).get(primary)
    if (
        expected != {"model_sha256": model.fingerprint, "model_manifest_sha256": binding.model_manifest_sha256}
        or model.training_provenance.get("fold_id") != primary
        or model.training_provenance.get("development_design_sha256") != receipt.get("development_design_sha256")
    ):
        raise ValueError("candidate_primary_model_binding_mismatch")
    scientific = receipt.get("scientific_decision", {})
    if (
        scientific.get("development_gate_state") not in {"passed", "failed"}
        or scientific.get("scientific_qualification") != "not_established"
        or scientific.get("qualified_state_ids") != []
        or not isinstance(scientific.get("reason_codes"), list)
    ):
        raise ValueError("candidate_development_cannot_authorize_release")
    declared = {canonicalize_source_family_id(value) for value in binding.source_family_ids}
    trained = {canonicalize_source_family_id(value) for value in model.training_provenance.get("source_family_ids", [])}
    if not trained or trained != declared:
        raise ValueError("candidate_training_source_binding_mismatch")
    query = canonicalize_source_family_id(str(request.assets[0].metadata.get("source_family_id", "")))
    if query in trained:
        raise ValueError("candidate_query_source_overlap")
    if query in {canonicalize_source_family_id(x) for x in DENIED_SOURCE_FAMILIES}:
        raise ValueError("candidate_query_source_prohibited")
    return binding, model, calibration, receipt


def reviewed_marker_evidence(query, genes):
    """Gene detection is descriptive; no missing-gene or coexpression inference."""
    review = load_development_review()
    index = {str(gene): i for i, gene in enumerate(genes)}
    n = int(query.shape[0])
    if n < 1 or len(index) != len(genes):
        raise ValueError("candidate_marker_input_invalid")
    all_genes = sorted({gene for row in review.state_reviews for gene in [*row.positive_markers, *row.counter_markers]})
    detection = {}
    for gene in all_genes:
        if gene not in index:
            detection[gene] = {"state": "missing", "count": None, "denominator": None}
        else:
            values = query[:, index[gene]]
            detection[gene] = {"state": "measured", "count": int((values > 0).sum()), "denominator": n}
    return [{
        "state_id": row.state_id, "definition_decision": row.decision,
        "positive_genes": row.positive_markers, "counter_genes": row.counter_markers,
        "source_ids": row.source_ids, "n_observations": n,
        "gene_detection": {gene: detection[gene] for gene in dict.fromkeys([*row.positive_markers, *row.counter_markers])},
        "identity_state": "not_assessed",
        "semantics": "per_gene_detection_not_joint_coexpression_or_identity",
        "development_review_sha256": development_review_sha256(),
    } for row in review.state_reviews]


def run_candidate_cell_state(request, spec, upstream_qc, input_hash, measurement_spec):
    from . import executor as legacy
    from .qc import validate_selected_data_view, validate_upstream_qc_unchanged
    from bridge.tool_packages.p0_01_input_qc.io import read_expression_asset, validate_expression_object, sha256_path

    try:
        binding, model, calibration, receipt = load_candidate_runtime(request)
        if upstream_qc.profile_v2 is None:
            raise ValueError("candidate_typed_qc_data_view_required")
        asset = request.assets[0]
        if asset.matrix_semantics != "raw_counts":
            # Do not assume that arbitrary normalized_expression is log1p(cp10k).
            raise ValueError("candidate_raw_counts_required")
        adata = read_expression_asset(asset)
        validate_expression_object(adata, require_counts=True)
        genes = legacy._declared_gene_names(adata, asset.metadata)
        counts, genes, _ = legacy._collapse_duplicate_gene_counts(adata.X, genes)
        identities = adata.obs_names.astype(str).tolist()
        view = validate_selected_data_view(upstream_qc.profile_v2, identities)
        query = normalize_query(counts, "raw_counts")
        prediction = predict_celltypist(model, query, genes, chunk_size=int(request.parameters.get("chunk_size", 256)))
        assignments = classify_with_rejection(prediction, calibration, identities)
        assignments["qualified_assignment"] = False
        for i, label in enumerate(prediction.classes):
            assignments[f"decision::{label}"] = prediction.decision_scores[:, i]
        marker = reviewed_marker_evidence(query, genes)
        measurement_sha = legacy._semantic_sha256(measurement_spec.model_dump(mode="json"))
        runtime_sha = legacy._semantic_sha256({
            "binding": binding.model_dump(mode="json"), "review_sha256": development_review_sha256(),
            "auxiliary_reference_sha256": _sha(resolve_reference_snapshot(measurement_spec.reference_refs[0]) / "reference_manifest.json"),
        })
        run_id = legacy._run_id(request, spec, input_hash, runtime_sha, measurement_sha, legacy._upstream_qc_binding(upstream_qc))
        # The auxiliary receipt is never retagged as this primary run.
        aux_request = request.model_copy(update={
            "request_id": request.request_id + "-auxiliary-reference",
            "measurement_spec_ref": AUXILIARY_SPEC,
            "parameters": {k: v for k, v in request.parameters.items() if k != "candidate_runtime_ref"},
        })
        cached_aux = request.output_dir.resolve() / run_id / "auxiliary_run.json"
        if cached_aux.exists():
            aux = ToolRun.model_validate(_read_json(cached_aux, "candidate_auxiliary_receipt_invalid"))
            if aux.request != aux_request or aux.tool_version != spec.version:
                raise ValueError("candidate_auxiliary_receipt_binding_mismatch")
            for artifact in aux.artifacts:
                if _sha(artifact.path) != artifact.sha256:
                    raise ValueError("candidate_auxiliary_artifact_changed")
        else:
            aux = legacy.run_cell_state_evidence(aux_request, spec)
        auxiliary_ok = aux.execution_state is ExecutionState.SUCCEEDED
        n = len(assignments)
        composition = []
        grouped = assignments.assign(
            label=assignments.assigned_state.fillna(assignments.assignment_state),
        ).groupby(["label", "assignment_state"], sort=True).size()
        for (label, state), count in grouped.items():
            composition.append({
                "label": label, "assignment_state": state, "count": int(count),
                "denominator": n, "fraction": int(count) / n,
                "denominator_scope": "selected_data_view", "interpretation": "candidate_method_output_only",
            })
        review = load_development_review()
        scientific = receipt["scientific_decision"]
        evidence_ids = [f"evidence:{run_id}:celltypist-candidate", f"evidence:{run_id}:reviewed-gene-detection"]
        profile = CellStateCandidateProfile(
            profile_id=f"cell-state-candidate:{run_id}", producer_run_ref=run_id,
            producer_tool_version=spec.version, environment_spec_ref=spec.environment_spec_id,
            measurement_spec_sha256=measurement_sha, input_data_view=view, input_sha256=input_hash,
            upstream_qc_profile_ref=upstream_qc.profile_v2.profile_id,
            upstream_qc_profile_sha256=upstream_qc.profile_v2_sha256,
            n_observations=n, n_genes=len(genes), runtime_ref=binding.runtime_id,
            model_manifest_sha256=binding.model_manifest_sha256, model_sha256=model.fingerprint,
            calibration=calibration.model_dump(mode="json"), verification_sha256=binding.verification_sha256,
            development_summary_sha256=receipt["summary_sha256"],
            development_review_sha256=development_review_sha256(),
            development_gate_state=scientific["development_gate_state"],
            development_reason_codes=scientific["reason_codes"],
            per_state_release={row.state_id: "unavailable" for row in review.state_reviews},
            candidate_composition=composition, feature_coverage=prediction.feature_coverage,
            missing_features=list(prediction.missing_features),
            auxiliary_run_ref=aux.run_id if auxiliary_ok else None,
            auxiliary_state="available" if auxiliary_ok else "unavailable",
            auxiliary_reason_codes=aux.reason_codes,
            limitations=[
                "development_failed" if scientific["development_gate_state"] == "failed" else "locked_validation_not_completed",
                "source_label_recovery_not_validated_biological_identity",
                "not_independent_of_primary_RNA", "correlation_is_auxiliary_not_a_release_vote",
                "legacy_auxiliary_marker_cards_are_not_current_reviewed_programs",
                "unknown_biological_units_not_independent_replicates",
                "target_lineage_and_developmental_window_mapping_unavailable_not_zero",
            ], evidence_ids=evidence_ids,
        )
        # These values describe the method's own assignments, not product identity.
        # V2 artifacts add source/version bindings to the exact same V1 receipt values.
        measurements = [MeasurementResultV2(
            measurement_id=f"measurement:{run_id}:candidate-retention",
            measurement_spec_id=CANDIDATE_SPEC, measurement_spec_version=measurement_spec.version,
            metric_name="candidate_assignment_fraction",
            raw_value=float(assignments.assigned_state.notna().mean()),
            numerator=int(assignments.assigned_state.notna().sum()), denominator=n,
            unit="fraction", source_run_ref=f"tool-run:{run_id}@{spec.version}",
            source_execution_state="succeeded",
            score_state=ScoreState.SHADOW, evidence_state="measured", provenance_refs=evidence_ids,
        )]
        for row in composition:
            key = legacy._semantic_sha256({"label": row["label"], "assignment_state": row["assignment_state"]})[:16]
            measurements.append(MeasurementResultV2(
                measurement_id=f"measurement:{run_id}:native-composition-{key}",
                measurement_spec_id=CANDIDATE_SPEC, measurement_spec_version=measurement_spec.version,
                metric_name=f"candidate_composition_fraction_{key}", raw_value=row["fraction"],
                numerator=row["count"], denominator=row["denominator"], unit="fraction",
                source_run_ref=f"tool-run:{run_id}@{spec.version}", source_execution_state="succeeded",
                score_state=ScoreState.SHADOW, evidence_state="inferred", provenance_refs=[evidence_ids[0]],
            ))
        native_spec = MeasurementSpecV2(
            **{**measurement_spec.model_dump(mode="json"), "tool_refs": ["P0-02"]},
            analysis_unit_kind="capture",
            independence_group_kind="sample", observation_unit_kind="cell",
            applicable_contexts=["candidate_method_observation"],
        )
        payload = profile.model_dump(mode="json")
        output = request.output_dir.resolve()
        output.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=f".{run_id}-", dir=output)).resolve()
        final = output / run_id
        published = False
        try:
            legacy._write_json(staging / "cell_state_candidate_profile.json", payload)
            assignments.to_parquet(staging / "celltypist_candidate_assignments.parquet", index=False)
            legacy._write_json(staging / "reviewed_marker_programs.json", marker)
            legacy._write_json(staging / "auxiliary_run.json", aux.model_dump(mode="json"))
            staged = [
                legacy._artifact(f"artifact:{run_id}:candidate-profile", "cell_state_candidate_profile", staging / "cell_state_candidate_profile.json", evidence_ids),
                legacy._artifact(f"artifact:{run_id}:candidate-assignments", "celltypist_candidate_assignments", staging / "celltypist_candidate_assignments.parquet", [evidence_ids[0]]),
                legacy._artifact(f"artifact:{run_id}:reviewed-markers", "reviewed_marker_programs", staging / "reviewed_marker_programs.json", [evidence_ids[1]]),
                legacy._artifact(f"artifact:{run_id}:auxiliary-run", "auxiliary_tool_run", staging / "auxiliary_run.json", []),
            ]
            for index, measurement in enumerate(measurements):
                path = staging / f"native_measurement_{index}.json"
                legacy._write_json(path, measurement.model_dump(mode="json"))
                staged.append(legacy._artifact(f"artifact:{run_id}:native-measurement-{index}",
                    "measurement_result_v2", path, measurement.provenance_refs))
            legacy._write_json(staging / "native_measurement_spec.json", native_spec.model_dump(mode="json"))
            staged.append(legacy._artifact(f"artifact:{run_id}:native-measurement-spec",
                "measurement_spec_v2", staging / "native_measurement_spec.json", []))
            relocated = [legacy._relocate_artifact(a, staging, final) for a in staged]
            legacy._write_json(staging / "artifact_manifest.json", {
                "run_id": run_id, "tool_id": "P0-02", "tool_version": spec.version,
                "environment_spec_id": spec.environment_spec_id, "input_hash": input_hash,
                "measurement_spec_ref": CANDIDATE_SPEC, "measurement_spec_sha256": measurement_sha,
                "runtime_binding_sha256": runtime_sha,
                "artifacts": [a.model_dump(mode="json") for a in relocated],
            })
            manifest = legacy._artifact(f"artifact:{run_id}:manifest", "manifest", staging / "artifact_manifest.json", evidence_ids)
            staged.append(manifest)
            relocated.append(legacy._relocate_artifact(manifest, staging, final))
            validate_upstream_qc_unchanged(upstream_qc)
            if sha256_path(asset.path) != input_hash:
                raise ValueError("input_asset_modified_during_run")
            if _sha(binding.verification_path) != binding.verification_sha256:
                raise ValueError("candidate_verification_modified_during_run")
            if final.exists():
                legacy._validate_existing_publication(final, staging, staged)
            else:
                try:
                    staging.rename(final)
                    published = True
                except OSError:
                    if not final.exists():
                        raise
                    legacy._validate_existing_publication(final, staging, staged)
        finally:
            if not published:
                shutil.rmtree(staging, ignore_errors=True)
        return ToolRun(
            run_id=run_id, request=request, implementation_state=spec.implementation_state,
            execution_state=ExecutionState.SUCCEEDED, tool_version=spec.version,
            environment_spec_id=spec.environment_spec_id, input_hash=input_hash,
            measurements=[MeasurementResult.model_validate({key: value for key, value in row.model_dump(mode="json").items()
                if key in MeasurementResult.model_fields}) for row in measurements], artifacts=relocated, result=payload,
            warnings=profile.limitations,
        )
    except (ValueError, OSError, RuntimeError) as exc:
        return legacy._failed_run(request, spec, input_hash, getattr(exc, "reason_code", str(exc)), str(exc))
