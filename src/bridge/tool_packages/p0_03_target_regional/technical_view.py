"""Exact, source-bound projection of saved similarity coefficients (no matrix I/O)."""

from __future__ import annotations

import hashlib
import math
from bridge.tool_packages._structured_runtime import (
    StructuredInputError, read_regular_bytes, strict_json_loads,
)
from bridge.tool_packages.p0_03_target_regional.exploratory_models import (
    ReferenceSimilarityExploratoryInput, ReferenceSimilarityExploratoryResult,
)
from bridge.toolkit.contracts import (
    MeasurementResultV2, MeasurementSpecV3, ReferenceManifest, ToolRunV2,
)


def validate_native_coefficients(result):
    for record in result.measurements:
        for value in (record.spearman, record.cosine):
            if value is not None and (not math.isfinite(value) or not -1 <= value <= 1):
                raise StructuredInputError("saved_similarity_coefficient_invalid")
        if record.margin is not None and (
            not math.isfinite(record.margin) or not 0 <= record.margin <= 2
        ):
            raise StructuredInputError("saved_similarity_margin_invalid")


def read_saved_source(ref):
    """Validate original producer, source files and native record bindings."""
    from bridge.toolkit.registry import ToolRegistry

    def verified(path, sha):
        raw = read_regular_bytes(path)
        if hashlib.sha256(raw).hexdigest() != sha:
            raise StructuredInputError("saved_similarity_source_checksum_mismatch")
        return strict_json_loads(raw)

    producer = ToolRunV2.model_validate(verified(ref.path, ref.sha256))
    if (producer.request.tool_id != "P0-03"
            or producer.execution_state.value not in {"succeeded", "partial"}):
        raise StructuredInputError("saved_similarity_producer_invalid")
    ToolRegistry.load_default().validate_historical_result(producer, producer.request)
    result = ReferenceSimilarityExploratoryResult.model_validate(producer.result)
    validate_native_coefficients(result)
    if result.source_run_ref != f"tool-run:{producer.run_id}@{producer.tool_version}":
        raise StructuredInputError("saved_similarity_producer_binding_mismatch")
    artifacts = [a for a in producer.artifacts if a.kind == "reference_similarity_exploratory_result"]
    if len(artifacts) != 1 or verified(artifacts[0].path, artifacts[0].sha256) != producer.result:
        raise StructuredInputError("saved_similarity_artifact_binding_mismatch")
    refs = {item.role: item for item in producer.request.object_inputs}
    if set(refs) != {"reference_similarity_input", "reference_manifest"}:
        raise StructuredInputError("saved_similarity_original_inputs_required")
    source_ref, manifest_ref = refs["reference_similarity_input"], refs["reference_manifest"]
    source = ReferenceSimilarityExploratoryInput.model_validate(verified(source_ref.path, source_ref.sha256))
    manifest = ReferenceManifest.model_validate(verified(manifest_ref.path, manifest_ref.sha256))
    if (source_ref.sha256 != result.input_sha256
            or manifest_ref.sha256 != result.reference_manifest_sha256
            or result.reference_manifest_ref != f"{manifest.snapshot_id}@{manifest.version}"
            or source.data_view != result.data_view
            or result.n_observations != source.data_view.n_observations
            or result.source_asset_id != source.data_view.parent_asset_id
            or result.source_asset_sha256 != source.data_view.parent_asset_sha256
            or len(producer.request.assets) != 1):
        raise StructuredInputError("saved_similarity_input_binding_mismatch")
    asset = producer.request.assets[0]
    if asset.asset_id != result.source_asset_id or asset.checksum != result.source_asset_sha256:
        raise StructuredInputError("saved_similarity_asset_binding_mismatch")
    profiles = {p.profile_id: p for p in manifest.profiles}
    if set(source.profile_ids) != {r.profile_id for r in result.measurements}:
        raise StructuredInputError("saved_similarity_profile_binding_mismatch")
    identities = set()
    for record in result.measurements:
        profile = profiles.get(record.profile_id)
        identity = (record.profile_id, record.label_level, record.label)
        if (profile is None or identity in identities or profile.assay != asset.assay
                or record.source_id != profile.source_id
                or record.source_family_id != profile.source_family_id
                or record.label_level != profile.label_level
                or record.label not in profile.labels):
            raise StructuredInputError("saved_similarity_label_binding_mismatch")
        identities.add(identity)
    provenance = {
        "derivation": "saved_native_scalar_projection_no_matrix_execution",
        "original_producer_ref": result.source_run_ref,
        "original_receipt_sha256": ref.sha256,
        "original_result_artifact_id": artifacts[0].artifact_id,
        "original_result_sha256": artifacts[0].sha256,
    }
    return producer, result, manifest, provenance


def project_measurements(*, result, manifest, assay, run_id, tool_version, provenance):
    """Preserve every native record and expose its two coefficients separately."""
    validate_native_coefficients(result)
    profiles = {p.profile_id: p for p in manifest.profiles}
    definitions = {}
    for i, record in enumerate(result.measurements):
        profile = profiles[record.profile_id]
        for metric in ("spearman", "cosine"):
            definitions[f"reference_similarity_{i}_{metric}"] = {
                "native_measurement_id": record.measurement_id,
                "native_field": metric, "profile_id": record.profile_id,
                "label": record.label, "label_level": record.label_level,
                "source_id": record.source_id, "source_family_id": record.source_family_id,
                "evidence_family_id": profile.evidence_family_id,
                "reference_matrix_sha256": profile.matrix_sha256,
                "reference_metadata_sha256": profile.metadata_sha256,
                "shared_genes": record.shared_genes,
                "query_gene_fraction": record.query_gene_fraction,
                "reference_gene_fraction": record.reference_gene_fraction,
                "reason_codes": record.reason_codes,
            }
    spec = MeasurementSpecV3(
        measurement_spec_id=f"REFERENCE-SIMILARITY-TECHNICAL-{run_id}", version="0.1.0",
        scientific_question="How similar is this selected RNA view to each original reference label?",
        assay=assay, data_view=result.data_view,
        observation_unit_kind="nucleus" if assay == "snRNA-seq" else "cell",
        applicable_contexts=["native_method_observation"],
        input_contract={**provenance, "native_result_id": result.result_id,
                        "original_producer_ref": result.source_run_ref,
                        "input_sha256": result.input_sha256,
                        "reference_manifest_ref": result.reference_manifest_ref,
                        "reference_manifest_sha256": result.reference_manifest_sha256,
                        "normalization": result.normalization},
        raw_metric_definition=definitions,
        missing_behavior="Unavailable coefficients remain null; never zero-filled",
        uncertainty_method="Descriptive view aggregate; no biological replicate inference",
        tool_refs=["P0-03"], reference_refs=[result.reference_manifest_ref],
    )
    measurements = []
    for i, record in enumerate(result.measurements):
        for metric in ("spearman", "cosine"):
            measurements.append(MeasurementResultV2(
                measurement_id=f"measurement:{run_id}:reference-{i}-{metric}",
                measurement_spec_id=spec.measurement_spec_id, measurement_spec_version=spec.version,
                metric_name=f"reference_similarity_{i}_{metric}",
                raw_value=getattr(record, metric), unit=record.unit,
                source_run_ref=f"tool-run:{run_id}@{tool_version}",
                source_execution_state="succeeded" if result.result_state == "available" else "partial",
                score_state="unavailable",
                evidence_state="inferred" if record.state == "available" else "unavailable",
                provenance_refs=[result.source_run_ref, result.result_id, record.measurement_id,
                                 record.profile_id, result.data_view.view_id,
                                 f"sha256:{result.input_sha256}",
                                 f"sha256:{result.reference_manifest_sha256}"],
            ))
    return spec, measurements
