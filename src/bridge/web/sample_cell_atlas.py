"""Verified, reference-free sample UMAP/Leiden produced by registered P0-02."""
import hashlib
import json

from bridge.toolkit.contracts import ToolRun
from bridge.tool_packages._expression_contracts import ExpressionAnalysis, EXPLORATION_SPEC
from .sample_qc import SampleToolResults, RECEIPT_LIMIT, RESULT_LIMIT
from .sample_analyses import display_parameters


class SampleCellAtlasResults(SampleToolResults):
    tool_id = "P0-02"
    source_kind = "sample_cell_atlas"
    directory = "cell-atlas"
    profile_kind = "expression_analysis"
    display_kinds = {
        "expression_cluster_markers": ("table", "application/vnd.apache.parquet", ".parquet"),
        "expression_analysis": ("evidence", "application/json", ".json"),
        "expression_cell_coordinates": ("table", "application/vnd.apache.parquet", ".parquet"),
    }

    def verify_inputs(self, root, attempt, run, declaration):
        super().verify_inputs(root, attempt, run, declaration)
        request = run.request
        options = ExpressionAnalysis.model_validate(request.parameters)
        if (request.measurement_spec_ref != EXPLORATION_SPEC or options.contrast is not None
                or options.exploration.group_key is not None or options.exploration.embedding_key is not None
                or run.result.get("input_data_view", {}).get("view_kind") != "all_observations"):
            raise ValueError("cell_atlas_mode_binding")
        qc_raw = self._read(root, attempt / "qc-run.json", RECEIPT_LIMIT,
                            request.assets[0].metadata.get("qc_receipt_sha256"))
        if request.assets[0].metadata.get("qc_receipt_sha256") != hashlib.sha256(qc_raw).hexdigest():
            raise ValueError("cell_atlas_qc_receipt_binding")
        qc = ToolRun.model_validate_json(qc_raw)
        self.registry.validate_historical_result(qc, qc.request)
        if (qc.execution_state != "succeeded" or qc.request.tool_id != "P0-01"
                or qc.request.request_id != request.request_id.removesuffix("cell-atlas") + "qc"
                or qc.request.output_dir != attempt / "qc" or len(qc.request.assets) != 1
                or qc.input_hash != run.input_hash):
            raise ValueError("cell_atlas_qc_binding")
        expected = request.assets[0].model_dump(mode="json")
        expected["metadata"].pop("qc_profile_ref", None)
        expected["metadata"].pop("qc_receipt_sha256", None)
        if expected != qc.request.assets[0].model_dump(mode="json"):
            raise ValueError("cell_atlas_qc_asset_binding")
        profiles = []
        for artifact in qc.artifacts:
            # These files bind the selected view used by expression exploration.
            if artifact.path.name in {"qc_readiness_profile.json", "qc_readiness_profile_v2.json",
                                      "structured_output_index.json"} or artifact.kind == "qc_profile_v2":
                content = self._read(attempt / "qc", artifact.path, RESULT_LIMIT, artifact.sha256)
                if artifact.kind == "qc_profile_v2":
                    profiles.append(json.loads(content))
        if (len(profiles) != 1
                or profiles[0]["profile_id"] != request.assets[0].metadata.get("qc_profile_ref")
                or profiles[0]["selected_data_view"] != run.result["input_data_view"]):
            raise ValueError("cell_atlas_qc_view_binding")
        if sum(a.kind == "expression_cell_coordinates" for a in run.artifacts) != 1:
            raise ValueError("cell_atlas_table_missing")

    def validate_profile(self, run, payload):
        if (payload != run.result or payload.get("analysis_kind") != "expression_exploration"
                or payload.get("embedding_source") != "scanpy_umap"
                or payload.get("grouping_source") != "exploratory_leiden"
                or payload.get("input_sha256") != run.input_hash
                or payload.get("parameters") != ExpressionAnalysis.model_validate(run.request.parameters).model_dump(mode="json")
                or payload.get("random_seed") != run.request.random_seed
                or payload.get("n_observations") != payload.get("input_data_view", {}).get("n_observations")):
            raise ValueError("cell_atlas_profile_binding")
        summary = display_parameters({key: payload[key] for key in (
            "n_observations", "n_genes", "composition", "embedding_source", "grouping_source",
            "preparation", "parameters", "random_seed", "dependencies", "domain_score", "score_state",
        )})
        summary.update(marker_state=payload.get("marker_state"), marker_inference=payload.get("marker_inference"))
        if "gene_expression" in payload:
            summary["gene_expression"] = display_parameters(payload["gene_expression"])
        return summary
