"""Verified descriptive cell-cycle outputs from the registered P0-06 tool."""
from bridge.toolkit.contracts import ToolRunV2
from bridge.tool_packages.p0_06_proliferation_stress_response.exploratory_models import (
    ExploratoryProcessInput, ExploratoryProcessProfile,
)
from .sample_qc import SampleToolResults, RECEIPT_LIMIT
from .sample_analyses import display_parameters


class SampleCellCycleResults(SampleToolResults):
    tool_id = "P0-06"
    source_kind = "sample_cell_cycle"
    directory = "cell-cycle"
    run_model = ToolRunV2
    profile_kind = "exploratory_process_profile"
    display_kinds = {
        "exploratory_process_profile": ("evidence", "application/json", ".json"),
        "exploratory_observation_scores": ("table", "application/vnd.apache.parquet", ".parquet"),
    }

    def input_checksum(self, run):
        return run.result.get("expression_asset_sha256")

    def verify_inputs(self, root, attempt, run, declaration):
        request = run.request
        super().verify_inputs(root, attempt, run, declaration)
        if len(request.object_inputs) != 1:
            raise ValueError("cycle_input_count")
        ref = request.object_inputs[0]
        if (ref.path != attempt / "cell-cycle-input.json"
                or ref.role != "exploratory_process_input"
                or ref.schema_ref != "bridge://schemas/exploratory-process-input/v0.1"
                or ref.object_version != "0.1.0"):
            raise ValueError("cycle_input_binding")
        payload = ExploratoryProcessInput.model_validate_json(
            self._read(root, ref.path, RECEIPT_LIMIT, ref.sha256))
        if run.result.get("input_contract") != payload.model_dump(mode="json"):
            raise ValueError("cycle_profile_input_binding")
        asset = request.assets[0]
        view = payload.data_view
        if (payload.source_family_id != declaration["source_family_id"]
                or payload.gene_symbol_column != declaration.get("gene_symbol_column")
                or view.view_kind != "all_observations"
                or view.artifact_id != asset.asset_id or view.sha256 != asset.checksum
                or view.parent_asset_id != asset.asset_id or view.parent_asset_sha256 != asset.checksum
                or view.matrix_location != asset.matrix_location
                or view.matrix_semantics != asset.matrix_semantics):
            raise ValueError("cycle_view_binding")

    def validate_profile(self, run, payload):
        profile = ExploratoryProcessProfile.model_validate(payload)
        if payload != run.result or profile.runtime_mode != "exploratory_process":
            raise ValueError("cycle_profile_binding")
        summary = display_parameters({
            key: payload[key] for key in (
                "cell_cycle", "n_observations", "interpretation_scope",
                "domain_score", "score_state",
            )
        })
        summary.update({key: payload["input_contract"][key] for key in
                        ("resource_ref", "resource_version", "resource_sha256")})
        return summary
