"""Verified automatic QC sources and display files for sample-owned analyses."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re

from fastapi import HTTPException

from bridge.toolkit.contracts import ToolRun, QCReadinessProfileV2
from .evidence import project_qc_summary
from .sample_analyses import digest, display_parameters
from .sessions import read_file

RESULT_LIMIT = 128 * 1024 * 1024
RECEIPT_LIMIT = 2 * 1024 * 1024
# Only user-facing QC results; no logs, manifests, matrices, or active SVG/HTML.
DISPLAY_KINDS = {
    "qc_profile_v2": ("evidence", "application/json", ".json"),
    "qc_metrics": ("table", "application/vnd.apache.parquet", ".parquet"),
    "visualization_png": ("figure", "image/png", ".png"),
    "qc_visualization_png": ("figure", "image/png", ".png"),
}


class SampleToolResults:
    """Common integrity boundary for automatic, sample-owned tool outputs."""

    tool_id = "P0-01"
    source_kind = "sample_qc"
    directory = "qc"
    run_model = ToolRun
    display_kinds = DISPLAY_KINDS
    profile_kind = "qc_profile_v2"

    def input_checksum(self, run):
        return run.input_hash

    def verify_inputs(self, root, attempt, run, declaration):
        request = run.request
        for key in ("capture_id", "capture_id_column", "gene_symbol_column"):
            if request.assets[0].metadata.get(key) != declaration.get(key):
                raise ValueError("sample_declaration_binding")

    def validate_profile(self, run, payload):
        profile = QCReadinessProfileV2.model_validate(payload)
        if profile.profile_id != "qc-profile:" + run.run_id:
            raise ValueError("qc_profile_binding")
        return project_qc_summary(run, payload)

    def __init__(self, *, researches, objects, registry):
        self.researches, self.objects, self.registry = researches, objects, registry

    @staticmethod
    def _read(root, path, limit, sha256=None):
        path = Path(path)
        relative = path.relative_to(root)
        if ".." in relative.parts or not relative.parts:
            raise ValueError("qc_result_path")
        current = root
        if current.is_symlink():
            raise ValueError("qc_result_symlink")
        for part in relative.parts:
            current /= part
            if current.is_symlink():
                raise ValueError("qc_result_symlink")
        raw = read_file(path, limit)
        if sha256 is not None and hashlib.sha256(raw).hexdigest() != sha256:
            raise ValueError("qc_result_hash")
        return raw

    def failure_reasons(self, owner, rid, aid):
        """Read an exact failed attempt's bounded reason codes, never its raw error text."""
        sample, _, assessment = self.objects.mapping_attempt(owner, rid, aid)
        root = self.researches.directory(rid)
        attempt = root / "atlas-runs" / aid
        try:
            run = self.run_model.model_validate_json(self._read(root, attempt / (self.directory + "-run.json"), RECEIPT_LIMIT))
            self.registry.validate_historical_result(run, run.request)
            request = run.request
            material = self.researches.material(owner, rid, sample["material_id"])
            declaration = assessment.get("_mapping_input", sample.get("mapping_input")) or {}
            if (run.execution_state not in {"failed", "blocked"} or request.tool_id != self.tool_id
                    or request.request_id != aid + "-" + self.directory or len(request.assets) != 1
                    or request.output_dir != attempt / self.directory):
                return []
            asset = request.assets[0]
            if (asset.path != root / "materials" / (material["id"] + ".bin")
                    or asset.asset_id != material["id"] or asset.checksum != material["sha256"]
                    or asset.assay != sample["assay"] or assessment["_material_id"] != material["id"]
                    or asset.matrix_location != declaration.get("matrix_location")
                    or asset.matrix_semantics != declaration.get("matrix_semantics")
                    or asset.metadata.get("source_family_id") != declaration.get("source_family_id")):
                return []
            with self.researches.checked_material(owner, rid, material["id"]):
                pass
            return [code for code in run.reason_codes if re.fullmatch(r"[a-z][a-z0-9_]{0,99}", code)][:8]
        except (HTTPException, OSError, ValueError, KeyError, TypeError):
            return []

    def capture(self, owner, rid, aid):
        try:
            sample, experiment, assessment = self.objects.mapping_attempt(owner, rid, aid)
            if "_mapping_config" not in assessment:
                raise ValueError("qc_attempt_missing")
            root = self.researches.directory(rid)
            attempt = root / "atlas-runs" / aid
            raw = self._read(root, attempt / (self.directory + "-run.json"), RECEIPT_LIMIT)
            run = self.run_model.model_validate_json(raw)
            self.registry.validate_historical_result(run, run.request)
            request = run.request
            material = self.researches.material(owner, rid, sample["material_id"])
            declaration = assessment.get("_mapping_input", sample.get("mapping_input")) or {}
            if (request.tool_id != self.tool_id or request.request_id != aid + "-" + self.directory
                    or run.execution_state not in {"succeeded", "partial"}
                    or len(request.assets) != 1 or self.input_checksum(run) != material["sha256"]
                    or assessment["_material_id"] != material["id"]
                    or request.output_dir != attempt / self.directory):
                raise ValueError("qc_execution_binding")
            asset = request.assets[0]
            if (asset.asset_id != material["id"] or asset.checksum != material["sha256"]
                    or asset.path != root / "materials" / (material["id"] + ".bin")
                    or asset.assay != sample["assay"]
                    or asset.matrix_location != declaration.get("matrix_location")
                    or asset.matrix_semantics != declaration.get("matrix_semantics")
                    or asset.metadata.get("source_family_id") != declaration.get("source_family_id")):
                raise ValueError("qc_input_binding")
            self.verify_inputs(root, attempt, run, declaration)
            with self.researches.checked_material(owner, rid, material["id"]):
                pass
            records, outputs, profiles = [], {}, []
            for artifact in run.artifacts:
                if artifact.kind not in self.display_kinds:
                    continue
                kind, media, suffix = self.display_kinds[artifact.kind]
                if artifact.path.suffix != suffix or artifact.media_type != media:
                    raise ValueError("qc_display_kind")
                content = self._read(attempt / self.directory, artifact.path, RESULT_LIMIT, artifact.sha256)
                if artifact.kind == self.profile_kind:
                    payload = json.loads(content)
                    self.validate_profile(run, payload)
                    profiles.append(payload)
                    content = json.dumps(display_parameters(payload), ensure_ascii=False, allow_nan=False).encode()
                identifier = hashlib.sha256(artifact.artifact_id.encode()).hexdigest()[:32]
                if identifier in outputs:
                    raise ValueError("qc_duplicate_artifact")
                name = re.sub(r"[^A-Za-z0-9_.-]", "_", artifact.path.name)[:100]
                if suffix == ".json":
                    name = name.removesuffix(".json") + ".display-redacted.json"
                records.append({"id": identifier, "source_artifact_id": artifact.artifact_id,
                                "sha256": artifact.sha256, "display_sha256": hashlib.sha256(content).hexdigest()})
                outputs[identifier] = ({"id": identifier, "name": name, "kind": kind,
                    "media_type": media, "tool_id": self.tool_id, "content_class": "user_result",
                    "access_state": "available"}, content)
            if len(profiles) != 1:
                raise ValueError("qc_profile_missing")
            summary = self.validate_profile(run, profiles[0])
            snapshot = {"source_kind": self.source_kind, "assessment_id": aid,
                "session_id": None, "receipt_id": None, "receipt_sha256": hashlib.sha256(raw).hexdigest(),
                "plan_id": None, "declaration_revision": None,
                "tool_run_id": run.run_id, "tool_version": run.tool_version,
                "environment_spec_id": run.environment_spec_id,
                "execution_state": run.execution_state.value,
                "request": request.model_dump(mode="json"), "material_id": material["id"],
                "material_sha256": material["sha256"], "results": records}
            return sample, experiment, snapshot, outputs, summary
        except (HTTPException, OSError, ValueError, KeyError, TypeError):
            raise HTTPException(409, "analysis_source_unavailable") from None

    def source(self, owner, rid, row):
        sample, experiment, snapshot, outputs, summary = self.capture(owner, rid, row["snapshot"]["assessment_id"])
        if (digest(snapshot) != row["snapshot_sha256"] or sample["id"] != row["sample_id"]
                or experiment["id"] != row["run_id"]
                or experiment["protocol_version_id"] != row["protocol_version_id"]):
            raise HTTPException(409, "analysis_source_unavailable")
        for identifier, (metadata, _) in outputs.items():
            metadata["url"] = f"/api/researches/{rid}/analyses/{row['id']}/results/{identifier}"
        return outputs, deepcopy(summary)


class SampleQcResults(SampleToolResults):
    """Original QC profile, count table, and figures."""
