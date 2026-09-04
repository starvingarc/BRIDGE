from __future__ import annotations

import hashlib
import stat
from pathlib import Path

from bridge.tool_packages._configurable_contracts import (
    BiologicalUnitAssignmentArtifact,
    BiologicalUnitManifest,
    ProductCase,
    biological_unit_assignment_reasons,
    observation_ids_sha256,
)
from bridge.tool_packages.p0_06_proliferation_stress_response.method_models import (
    ObservationState,
    ProcessMethodId,
    ProcessMethodInput,
    ProcessMethodSpec,
)
from bridge.tool_packages.p0_06_proliferation_stress_response.models import (
    ProgramSpec,
    program_rule_content_sha256,
)
from bridge.toolkit.contracts import (
    CellStateEvidenceProfileV3,
    InputAsset,
    ToolPackageSpecV2,
)


METHOD_REF_BY_SELECTOR = {
    ProcessMethodId.SCANPY_SCORE_GENES: "METHOD-SCANPY-SCORE-GENES",
    ProcessMethodId.DECOUPLER_ULM: "METHOD-DECOUPLER",
    ProcessMethodId.SCANPY_CELL_CYCLE: (
        "METHOD-SCANPY-SCORE-GENES-CELL-CYCLE"
    ),
    ProcessMethodId.CELL_CYCLE_AGGREGATION: (
        "METHOD-BRIDGE-SAMPLE-STATE-AGGREGATION"
    ),
}


class ExpressionAssetError(RuntimeError):
    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__(reason_code)


def expression_asset_sha256(path: Path) -> str:
    """Hash one regular file and reject replacement during the read."""

    try:
        before = path.lstat()
        if not stat.S_ISREG(before.st_mode) or path.is_symlink():
            raise ExpressionAssetError("expression_asset_not_regular_file")
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        after = path.lstat()
    except FileNotFoundError as exc:
        raise ExpressionAssetError("expression_asset_not_found") from exc
    except OSError as exc:
        raise ExpressionAssetError("expression_asset_not_regular_file") from exc
    if (
        not stat.S_ISREG(after.st_mode)
        or before.st_dev != after.st_dev
        or before.st_ino != after.st_ino
        or before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
    ):
        raise ExpressionAssetError("expression_asset_modified_during_read")
    return digest.hexdigest()


def method_binding_reasons(
    *,
    product_case: ProductCase,
    cell_state: CellStateEvidenceProfileV3,
    program_spec: ProgramSpec,
    method_spec: ProcessMethodSpec,
    method_input: ProcessMethodInput,
    manifest: BiologicalUnitManifest,
    assignment: BiologicalUnitAssignmentArtifact,
    asset: InputAsset,
    asset_sha256: str,
    input_sha256_by_role: dict[str, str],
    tool_spec: ToolPackageSpecV2,
) -> list[str]:
    reasons: set[str] = set()
    view = cell_state.input_data_view
    if not method_spec.active:
        reasons.add("process_method_spec_inactive")
    if any(
        METHOD_REF_BY_SELECTOR[method_id] not in tool_spec.method_ids
        for method_id in method_spec.selected_method_ids
    ):
        reasons.add("process_method_not_registered")

    if (
        asset.asset_id != method_spec.expression_asset_id
        or asset.asset_id != view.artifact_id
    ):
        reasons.add("expression_asset_id_mismatch")
    if (
        asset.checksum is None
        or asset.checksum != asset_sha256
        or asset.checksum != view.sha256
    ):
        reasons.add("expression_asset_checksum_mismatch")
    if (
        asset.assay != product_case.assay
        or cell_state.assay != product_case.assay
    ):
        reasons.add("expression_assay_mismatch")
    if (
        asset.matrix_location != view.matrix_location
        or asset.matrix_semantics != view.matrix_semantics
    ):
        reasons.add("expression_data_view_mismatch")
    if view.matrix_location == "X":
        expected_layer = None
    elif view.matrix_location.startswith("layers/") and len(
        view.matrix_location.removeprefix("layers/")
    ) > 0:
        expected_layer = view.matrix_location.removeprefix("layers/")
    else:
        expected_layer = None
        reasons.add("expression_data_view_location_unsupported")
    if method_spec.expression_layer != expected_layer:
        reasons.add("process_method_expression_layer_mismatch")

    manifest_sha = input_sha256_by_role["biological_unit_manifest"]
    assignment_sha = input_sha256_by_role["biological_unit_assignment"]
    if (
        product_case.biological_unit_manifest_ref != manifest.ref
        or product_case.biological_unit_manifest_sha256 != manifest_sha
        or product_case.independence_scope_ref != manifest.independence_scope_ref
        or sorted(item.ref for item in product_case.independence_group_refs)
        != sorted(item.ref for item in manifest.independence_group_refs)
    ):
        reasons.add("product_case_biological_unit_binding_mismatch")
    if (
        view.biological_unit_manifest_ref != manifest.ref.ref
        or view.biological_unit_manifest_sha256 != manifest_sha
        or view.view_id != manifest.data_view_ref
        or view.sha256 != manifest.selected_artifact_sha256
        or view.n_observations != manifest.n_observations
        or view.observation_ids_sha256 != manifest.observation_ids_sha256
    ):
        reasons.add("data_view_biological_unit_binding_mismatch")
    reasons.update(
        biological_unit_assignment_reasons(
            manifest=manifest,
            artifact=assignment,
            artifact_sha256=assignment_sha,
        )
    )

    product_case_sha = input_sha256_by_role["product_case"]
    cell_state_sha = input_sha256_by_role["cell_state_evidence_profile"]
    if (
        method_input.product_case_ref != product_case.ref.ref
        or method_input.product_case_sha256 != product_case_sha
    ):
        reasons.add("method_input_product_case_mismatch")
    if (
        method_input.cell_state_profile_id != cell_state.profile_id
        or method_input.cell_state_profile_sha256 != cell_state_sha
    ):
        reasons.add("method_input_cell_state_profile_mismatch")
    if (
        method_input.data_view_ref != view.view_id
        or method_input.biological_unit_manifest_ref != manifest.ref.ref
        or method_input.biological_unit_manifest_sha256 != manifest_sha
        or method_input.biological_unit_assignment_sha256 != assignment_sha
    ):
        reasons.add("method_input_data_lineage_mismatch")

    observation_ids = [
        item.observation_id for item in method_input.observation_states
    ]
    calculated_observation_sha = observation_ids_sha256(observation_ids)
    if (
        set(observation_ids)
        != {item.observation_id for item in assignment.assignments}
        or calculated_observation_sha != method_input.observation_ids_sha256
        or calculated_observation_sha != view.observation_ids_sha256
    ):
        reasons.add("method_input_observation_set_mismatch")

    rules = {item.program_id: item for item in program_spec.program_rules}
    allowed_states = {
        state_id for rule in rules.values() for state_id in rule.allowed_state_ids
    }
    if any(
        item.state is ObservationState.CANDIDATE
        and item.state_id not in allowed_states
        for item in method_input.observation_states
    ):
        reasons.add("method_input_state_not_declared")
    for program in method_spec.programs:
        rule = rules.get(program.program_id)
        if (
            rule is None
            or not set(method_spec.selected_analysis_scopes).intersection(
                rule.allowed_analysis_scopes
            )
        ):
            reasons.add("process_program_binding_mismatch")
            continue
        content_sha256 = program_rule_content_sha256(rule)
        if not rule.targets:
            reasons.add("process_program_content_missing")
        elif content_sha256 != rule.gene_set_sha256:
            reasons.add("program_gene_set_content_checksum_mismatch")
        if (
            ProcessMethodId.SCANPY_SCORE_GENES
            in method_spec.selected_method_ids
            and sum(target.weight > 0 for target in rule.targets) < 2
        ):
            reasons.add("scanpy_program_positive_targets_insufficient")
    if method_spec.cell_cycle is not None:
        rule = rules.get(method_spec.cell_cycle.program_id)
        if (
            rule is None
            or not set(method_spec.selected_analysis_scopes).intersection(
                rule.allowed_analysis_scopes
            )
        ):
            reasons.add("cell_cycle_program_binding_mismatch")
        elif not rule.s_genes or not rule.g2m_genes:
            reasons.add("cell_cycle_program_content_missing")
        elif program_rule_content_sha256(rule) != rule.gene_set_sha256:
            reasons.add("cell_cycle_gene_set_content_checksum_mismatch")
    return sorted(reasons)
