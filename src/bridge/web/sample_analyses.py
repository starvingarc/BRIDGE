"""Immutable sample-to-execution lineage; no scheduler or scientific inference."""
from copy import deepcopy
import hashlib
import json

from fastapi import HTTPException, Request, Query
from typing import Annotated
from pydantic import StringConstraints
from fastapi.responses import Response

from .inputs import verify_checked_file
from .research_object_models import Mutation, ObjectID
from .sessions import ID, now, private_text, read_file, uid, write_file

STORE_BYTES = 4 * 1024 * 1024
ANALYSIS_LIMIT = 512
ERRORS = {
    "analysis_not_found": "找不到该分析记录。",
    "analysis_session_not_found": "找不到该研究中的分析会话。",
    "analysis_source_not_found": "找不到该次执行结果。",
    "analysis_source_unavailable": "该结果的来源暂不可核验。",
    "analysis_sample_input_mismatch": "该次执行的输入未绑定到所选样本的数据。",
    "analysis_source_not_completed": "该次执行尚无可登记的完成结果。",
    "analysis_source_invalidated": "该结果已因输入修订失效，不能登记为新分析。",
    "analysis_result_not_found": "找不到该分析结果文件。",
    "analysis_result_unavailable": "该次执行暂无可供读取的结果文件。",
    "analysis_store_unavailable": "分析历史暂不可读取。",
    "gene_expression_unavailable": "该次分析尚无完整基因表达产物。",
    "gene_expression_response_too_large": "请减少一次读取的基因数量。",
    "analysis_limit": "该研究的分析历史已达到存储上限。",
}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def display_parameters(value):
    """Display-only copy; the exact request is private and bound by its digest."""
    if isinstance(value, dict):
        return {key: display_parameters(item) for key, item in value.items()
                if not any(term in key.lower() for term in
                           ("path", "output_dir", "secret", "token", "password", "credential", "api_key"))}
    if isinstance(value, list):
        return [display_parameters(item) for item in value]
    return private_text(value) if isinstance(value, str) else value


class AnalysisRegistration(Mutation):
    session_id: ObjectID
    receipt_id: ObjectID


class SampleAnalyses:
    def __init__(self, *, researches, objects, sessions, inputs, artifacts, max_upload_bytes, qc_results, cell_cycle_results, cell_atlas_results):
        self.researches, self.objects, self.sessions = researches, objects, sessions
        self.inputs, self.artifacts = inputs, artifacts
        self.lock = sessions.lock
        self.max_upload_bytes = max_upload_bytes
        self.automatic_results = {"sample_qc": qc_results, "sample_cell_cycle": cell_cycle_results,
                                  "sample_cell_atlas": cell_atlas_results}

    def _path(self, owner, rid):
        try:
            self.researches.owned(owner, rid)
        except HTTPException:
            raise HTTPException(404, "research_not_found") from None
        return self.researches.directory(rid) / "analyses.json"

    def _load(self, owner, rid):
        path = self._path(owner, rid)
        try:
            raw = read_file(path, STORE_BYTES)
        except FileNotFoundError:
            if not path.is_symlink():
                return {"schema_version": 1, "analyses": {}}
            raise HTTPException(409, "analysis_store_unavailable") from None
        except (OSError, ValueError):
            raise HTTPException(409, "analysis_store_unavailable") from None
        try:
            state = json.loads(raw)
            if state["schema_version"] != 1 or not isinstance(state["analyses"], dict):
                raise ValueError("invalid_store")
            for aid, record in state["analyses"].items():
                if (not ID.fullmatch(aid) or record["id"] != aid or record["research_id"] != rid
                        or digest(record["snapshot"]) != record["snapshot_sha256"]):
                    raise ValueError("invalid_record")
            return state
        except (KeyError, TypeError, ValueError):
            raise HTTPException(409, "analysis_store_unavailable") from None

    def _save(self, owner, rid, state):
        raw = json.dumps(state, ensure_ascii=False, allow_nan=False).encode()
        if len(state["analyses"]) > ANALYSIS_LIMIT or len(raw) > STORE_BYTES:
            raise HTTPException(409, "analysis_limit")
        write_file(self._path(owner, rid), raw)

    def _sample(self, owner, rid, sample_id):
        sample = self.objects.sample(owner, rid, sample_id)
        run = self.objects.run(owner, rid, sample["run_id"])
        return sample, run

    def _session(self, owner, rid, sid):
        if self.sessions.owner(sid) != owner:
            raise HTTPException(404, "analysis_session_not_found")
        state = self.sessions.load(sid)
        if state.get("research_id") != rid:
            raise HTTPException(404, "analysis_session_not_found")
        return state

    def _receipt(self, state, receipt_id):
        receipt = next((r for r in state["_tool_runs"] if r["file"] == receipt_id + ".json"), None)
        if receipt is None:
            raise HTTPException(404, "analysis_source_not_found")
        if receipt["file"] in state.get("_invalidated_receipts", {}):
            raise HTTPException(409, "analysis_source_invalidated")
        if receipt["state"] not in {"succeeded", "partial"}:
            raise HTTPException(409, "analysis_source_not_completed")
        return receipt

    def _verify_inputs(self, owner, rid, sample, state, run, material):
        sid = state["id"]
        # A single-sample binding cannot silently bless a cohort or object-only run.
        if len(run.request.assets) != 1:
            raise HTTPException(409, "analysis_sample_input_mismatch")
        asset = run.request.assets[0]
        uploads = [u for u in state["uploads"] if u.get("material_id") == material["id"]]
        matching = [u for u in uploads if state["_uploads"][u["id"]]["sha256"] == material["sha256"]]
        direct = any(asset.asset_id == u["id"] and asset.checksum == material["sha256"]
                     and str(asset.path) == str(self.sessions.directory(sid) / "uploads" / (u["id"] + ".h5ad"))
                     for u in matching)
        derived = False
        if not direct and matching and asset.metadata.get("data_view_id"):
            # Match a verified historical QC view, never the latest QC or a name.
            for producer in state["_tool_runs"]:
                if (producer["tool_id"] != "P0-01" or producer["state"] not in {"succeeded", "partial"}
                        or producer["file"] in state.get("_invalidated_receipts", {})):
                    continue
                try:
                    _, outputs = self.inputs.producer_objects(state, producer, "P0-01", {"qc_profile_v2"})
                except (HTTPException, ValueError, OSError, KeyError, TypeError):
                    # An unreadable candidate cannot establish this view's lineage,
                    # but must not invalidate an independently verified producer.
                    continue
                for _, profile in outputs.get("qc_profile_v2", []):
                    view = profile.get("selected_data_view") or {}
                    if (view.get("view_id") == asset.metadata["data_view_id"]
                            and view.get("parent_asset_id") in {u["id"] for u in matching}
                            and view.get("parent_asset_sha256") == material["sha256"]
                            and view.get("sha256") == asset.checksum):
                        derived = True
                        break
                if derived:
                    break
        if not (direct or derived) or asset.assay != sample["assay"]:
            raise HTTPException(409, "analysis_sample_input_mismatch")
        verify_checked_file(self.sessions, state, asset.path, asset.checksum, limit=self.max_upload_bytes)
        with self.researches.checked_material(owner, rid, material["id"]):
            pass
        for ref in getattr(run.request, "object_inputs", []):
            source = state["_input_objects"].get(ref.input_id)
            if source is None or any(source.get(key) != expected for key, expected in {
                "path": str(ref.path), "sha256": ref.sha256, "schema_ref": ref.schema_ref,
                "object_version": ref.object_version}.items()):
                raise ValueError("input_binding_changed")
            self.inputs.verify(state, source)

    def _capture(self, owner, rid, sample, sid, receipt_id):
        state = self._session(owner, rid, sid)
        if state.get("run_id") not in {None, sample["run_id"]}:
            raise HTTPException(409, "analysis_sample_input_mismatch")
        with self.inputs.verification(state):
            receipt = self._receipt(state, receipt_id)
            if not sample["material_id"]:
                raise HTTPException(409, "analysis_sample_input_mismatch")
            material = self.researches.material(owner, rid, sample["material_id"])
            run, _ = self.inputs.producer_objects(state, receipt, receipt["tool_id"], set())
            self._verify_inputs(owner, rid, sample, state, run, material)
            results = []
            for artifact in state.get("artifacts", []):
                aid = artifact["id"]
                canonical = state.get("_canonical_artifacts", {}).get(aid)
                if (not canonical or canonical.get("receipt_file") != receipt["file"]
                        or canonical.get("receipt_sha256") != receipt["sha256"]):
                    continue
                self.inputs.receipt_artifacts(state, canonical)
                projected = self.artifacts.projection(state, aid)
                if projected["access_state"] == "denied":
                    continue
                stored = state["_artifacts"][aid]
                # Validate the display copy without bypassing historical report acknowledgement.
                if projected["access_state"] != "historical_unreviewed" or projected["acknowledged"]:
                    self.artifacts.read(state, aid)
                results.append({"id": uid(), "artifact_id": aid, "source_artifact_id": canonical["artifact_id"],
                                "sha256": canonical["sha256"], "display_sha256": stored["sha256"]})
            if not results:
                raise HTTPException(409, "analysis_result_unavailable")
            return {
                "session_id": sid, "receipt_id": receipt_id, "receipt_sha256": receipt["sha256"],
                "plan_id": receipt.get("plan_id"), "declaration_revision": receipt.get("declaration_start"),
                "tool_run_id": run.run_id, "tool_version": run.tool_version,
                "environment_spec_id": run.environment_spec_id, "execution_state": run.execution_state.value,
                "request": run.request.model_dump(mode="json"),
                "material_id": material["id"], "material_sha256": material["sha256"],
                "results": results,
            }

    def _records(self, owner, rid):
        rows = list(self._load(owner, rid)["analyses"].values()) + self.objects.mapping_analyses(owner, rid)
        try:
            if len({r["id"] for r in rows}) != len(rows):
                raise ValueError("duplicate_analysis")
            for row in rows:
                if (not ID.fullmatch(row["id"]) or row["research_id"] != rid
                        or digest(row["snapshot"]) != row["snapshot_sha256"]):
                    raise ValueError("invalid_analysis")
        except (ValueError, KeyError, TypeError):
            raise HTTPException(409, "analysis_store_unavailable") from None
        return rows

    def _new_record(self, owner, rid, sample, experiment, snapshot):
        rows = self._records(owner, rid)
        if len(rows) >= ANALYSIS_LIMIT:
            raise HTTPException(409, "analysis_limit")
        return {"id": uid(), "research_id": rid, "sample_id": sample["id"], "run_id": experiment["id"],
                "protocol_version_id": experiment["protocol_version_id"], "revision": 1, "created_at": now(),
                "version": 1 + max((r["version"] for r in rows if r["sample_id"] == sample["id"]), default=0),
                "snapshot": snapshot, "snapshot_sha256": digest(snapshot)}

    def _mapping_snapshot(self, owner, rid, sample, assessment, execution):
        """Private source identity; the numerical result remains owned by the assessment."""
        material = self.researches.material(owner, rid, sample["material_id"])
        request = execution.request
        declaration = assessment.get("_mapping_input", sample.get("mapping_input")) or {}
        if (execution.execution_state != "succeeded" or assessment["status"] != "done"
                or request.request_id != assessment["id"] or request.tool_id != "P0-02"
                or execution.run_id != assessment["tool_run_id"] or len(request.assets) != 1
                or request.measurement_spec_ref != "ATLAS-ingest-quick-v0.1"
                or assessment["_material_id"] != material["id"] or execution.input_hash != material["sha256"]):
            raise ValueError("mapping_execution_binding")
        asset = request.assets[0]
        if (asset.asset_id != material["id"] or asset.checksum != material["sha256"]
                or asset.path != self.researches.directory(rid) / "materials" / (material["id"] + ".bin")
                or asset.assay != sample["assay"]
                or asset.matrix_location != declaration.get("matrix_location")
                or asset.matrix_semantics != declaration.get("matrix_semantics")
                or asset.metadata.get("source_family_id") != declaration.get("source_family_id")
                or request.parameters.get("sample_context") != declaration.get("sample_context")):
            raise ValueError("mapping_sample_binding")
        with self.researches.checked_material(owner, rid, material["id"]):
            pass
        artifact = next(a for a in execution.artifacts if a.kind == "quick_atlas_mapping")
        binding = assessment["_result"]
        if (artifact.path != self.researches.directory(rid) / binding["path"]
                or artifact.sha256 != binding["sha256"]):
            raise ValueError("mapping_artifact_binding")
        return {"source_kind": "atlas_mapping", "assessment_id": assessment["id"],
                "session_id": None, "receipt_id": None, "receipt_sha256": assessment["_receipt"]["sha256"],
                "plan_id": None, "declaration_revision": None,
                "tool_run_id": execution.run_id, "tool_version": execution.tool_version,
                "environment_spec_id": execution.environment_spec_id, "execution_state": "succeeded",
                "request": request.model_dump(mode="json"), "material_id": material["id"],
                "material_sha256": material["sha256"],
                "mapping_versions": execution.result["versions"],
                "reference_manifest_sha256": execution.result["reference_manifest_sha256"],
                "mapping_bindings": {"result": binding, "receipt": assessment["_receipt"]},
                "results": [{"id": artifact.artifact_id, "source_artifact_id": artifact.artifact_id,
                             "sha256": artifact.sha256, "display_sha256": None}]}

    def prepare_mapping(self, owner, rid, sample, experiment, assessment, execution):
        """Called under the shared lock before the mapping success/index atomic save."""
        try:
            snapshot = self._mapping_snapshot(owner, rid, sample, assessment, execution)
        except (HTTPException, OSError, ValueError, KeyError, TypeError, StopIteration):
            raise HTTPException(409, "mapping_result_unavailable") from None
        return self._new_record(owner, rid, sample, experiment, snapshot)

    def _mapping_available(self, owner, rid, row):
        snapshot = row["snapshot"]
        sample, experiment, assessment, execution = self.objects.mapping_analysis_source(
            owner, rid, snapshot["assessment_id"])
        current = self._mapping_snapshot(owner, rid, sample, assessment, execution)
        if (digest(current) != row["snapshot_sha256"] or sample["id"] != row["sample_id"]
                or experiment["id"] != row["run_id"]
                or experiment["protocol_version_id"] != row["protocol_version_id"]
                or assessment.get("_analysis", {}).get("id") != row["id"]):
            raise ValueError("mapping_analysis_binding")
        return {"id": assessment["id"], "url": f"/api/researches/{rid}/assessments/{assessment['id']}"}

    def register_qc(self, owner, rid, assessment_id):
        return self._register_automatic(owner, rid, assessment_id, "sample_qc")

    def register_cell_cycle(self, owner, rid, assessment_id):
        return self._register_automatic(owner, rid, assessment_id, "sample_cell_cycle")

    def register_cell_atlas(self, owner, rid, assessment_id):
        return self._register_automatic(owner, rid, assessment_id, "sample_cell_atlas")

    def _register_automatic(self, owner, rid, assessment_id, source_kind):
        """Called after the QC receipt commits; idempotent across worker/restart."""
        with self.lock:
            state = self._load(owner, rid)
            for row in state["analyses"].values():
                source = row["snapshot"]
                if source.get("source_kind") == source_kind and source["assessment_id"] == assessment_id:
                    return
            sample, experiment, snapshot, _, _ = self.automatic_results[source_kind].capture(owner, rid, assessment_id)
            row = self._new_record(owner, rid, sample, experiment, snapshot)
            state["analyses"][row["id"]] = row
            self._save(owner, rid, state)

    def automatic_result(self, owner, rid, aid, result_id):
        with self.lock:
            row = next((r for r in self._records(owner, rid) if r["id"] == aid), None)
            if (row is None or row["snapshot"].get("source_kind") not in self.automatic_results
                    or not any(r["id"] == result_id for r in row["snapshot"]["results"])):
                raise HTTPException(404, "analysis_result_not_found")
            outputs, _ = self.automatic_results[row["snapshot"]["source_kind"]].source(owner, rid, row)
            return outputs[result_id]

    def gene_data(self, owner, rid, aid, *, genes=None, query="", offset=0, limit=50):
        from .sample_gene_expression import catalog, expression
        with self.lock:
            row = next((r for r in self._records(owner, rid) if r["id"] == aid), None)
            if row is None:
                raise HTTPException(404, "analysis_not_found")
            if row["snapshot"].get("source_kind") != "sample_cell_atlas":
                raise HTTPException(404, "gene_expression_unavailable")
            source = self.automatic_results["sample_cell_atlas"]
            if genes is not None:
                return expression(source, owner, rid, row, genes=genes)
            return catalog(source, owner, rid, row, query=query, offset=offset, limit=limit)

    def sources(self, owner, rid, sample_id, sid):
        with self.lock:
            sample, _ = self._sample(owner, rid, sample_id)
            state = self._session(owner, rid, sid)
            sources = []
            for receipt in state["_tool_runs"]:
                receipt_id = receipt["file"].removesuffix(".json")
                reason = None
                try:
                    self._capture(owner, rid, sample, sid, receipt_id)
                except HTTPException as exc:
                    reason = exc.detail
                except (ValueError, OSError, KeyError, TypeError):
                    reason = "analysis_source_unavailable"
                sources.append({"receipt_id": receipt_id, "tool_id": receipt["tool_id"],
                                "execution_state": receipt["state"], "eligible": reason is None,
                                "reason_code": reason})
            return {"sources": sources}

    def register(self, owner, rid, sample_id, body):
        with self.lock:
            sample, run = self._sample(owner, rid, sample_id)
            state = self._load(owner, rid)
            # Repeated delivery of the same exact source is idempotent, not a new analysis.
            for row in state["analyses"].values():
                snapshot = row["snapshot"]
                if (row["sample_id"] == sample_id and snapshot["session_id"] == body.session_id
                        and snapshot["receipt_id"] == body.receipt_id):
                    return self._public(owner, rid, row)
            if sample["revision"] != body.expected_version:
                raise HTTPException(409, "object_version_conflict")
            try:
                snapshot = self._capture(owner, rid, sample, body.session_id, body.receipt_id)
            except (ValueError, OSError, KeyError, TypeError):
                raise HTTPException(409, "analysis_source_unavailable") from None
            row = self._new_record(owner, rid, sample, run, snapshot)
            state["analyses"][row["id"]] = row
            self._save(owner, rid, state)
            return self._public(owner, rid, row)

    def _public(self, owner, rid, row):
        snapshot = row["snapshot"]
        request = snapshot["request"]
        value = {key: row[key] for key in ("id", "research_id", "sample_id", "run_id",
                  "protocol_version_id", "revision", "created_at", "version", "snapshot_sha256")}
        value.update(source_kind=snapshot.get("source_kind", "session_execution"),
                     session_id=snapshot["session_id"], receipt_id=snapshot["receipt_id"],
                     receipt_sha256=snapshot["receipt_sha256"], plan_id=snapshot["plan_id"],
                     declaration_revision=snapshot["declaration_revision"],
                     execution_state=snapshot["execution_state"],
                     tool={"id": request["tool_id"], "version": snapshot["tool_version"],
                           "run_id": snapshot["tool_run_id"], "environment_spec_id": snapshot["environment_spec_id"]},
                     material_id=snapshot["material_id"], material_sha256=snapshot["material_sha256"],
                     measurement_spec_ref=request.get("measurement_spec_ref"),
                     random_seed=request["random_seed"], parameters=display_parameters(request["parameters"]),
                     parameters_sha256=digest(request["parameters"]),
                     input_assets=[{**{k: a.get(k) for k in ("asset_id", "format", "input_level",
                                   "matrix_location", "matrix_semantics", "assay")}, "sha256": a["checksum"],
                                   "data_view_id": a.get("metadata", {}).get("data_view_id")}
                                   for a in request["assets"]],
                     object_inputs=[{k: ref[k] for k in ("input_id", "role", "schema_ref", "object_version", "sha256")}
                                    for ref in request.get("object_inputs", [])])
        results = [{key: result[key] for key in ("id", "source_artifact_id", "sha256", "display_sha256")}
                   for result in snapshot["results"]]
        availability = {"status": "available", "reason_code": None}
        if snapshot.get("source_kind") in self.automatic_results:
            summary = None
            outputs = {}
            try:
                outputs, summary = self.automatic_results[row["snapshot"]["source_kind"]].source(owner, rid, row)
            except (HTTPException, ValueError, OSError, KeyError, TypeError):
                availability = {"status": "unavailable", "reason_code": "analysis_source_unavailable"}
            for result in results:
                result["artifact"] = outputs[result["id"]][0] if outputs else None
            summary_key = {"sample_qc": "qc_summary", "sample_cell_cycle": "cell_cycle_summary",
                           "sample_cell_atlas": "cell_atlas_summary"}[snapshot["source_kind"]]
            value.update(assessment_id=snapshot["assessment_id"], results=results, availability=availability)
            value[summary_key] = summary
            if snapshot["source_kind"] == "sample_cell_atlas" and summary and summary.get("gene_expression", {}).get("state") == "available":
                value["gene_catalog_url"] = f"/api/researches/{rid}/analyses/{row['id']}/genes"
                value["gene_expression_url"] = f"/api/researches/{rid}/analyses/{row['id']}/gene-expression"
            return deepcopy(value)
        if snapshot.get("source_kind") == "atlas_mapping":
            value["parameters"].pop("reference_manifest", None)
            value.update(assessment_id=snapshot["assessment_id"], mapping_versions=snapshot["mapping_versions"],
                         reference_manifest_sha256=snapshot["reference_manifest_sha256"])
            target = None
            try:
                target = self._mapping_available(owner, rid, row)
            except (HTTPException, ValueError, OSError, KeyError, TypeError, StopIteration):
                availability = {"status": "unavailable", "reason_code": "analysis_source_unavailable"}
            for result in results:
                result.update(artifact=None, assessment=target)
            value.update(results=results, availability=availability)
            return deepcopy(value)
        try:
            state = self._session(owner, rid, snapshot["session_id"])
            with self.inputs.verification(state):
                receipt = self._receipt(state, snapshot["receipt_id"])
                if receipt["sha256"] != snapshot["receipt_sha256"]:
                    raise ValueError("receipt_changed")
                run, _ = self.inputs.producer_objects(state, receipt, receipt["tool_id"], set())
                sample, experiment = self._sample(owner, rid, row["sample_id"])
                material = self.researches.material(owner, rid, snapshot["material_id"])
                if (run.request.model_dump(mode="json") != snapshot["request"]
                        or sample["material_id"] != snapshot["material_id"]
                        or material["sha256"] != snapshot["material_sha256"]
                        or experiment["id"] != row["run_id"]
                        or experiment["protocol_version_id"] != row["protocol_version_id"]):
                    raise ValueError("input_binding_changed")
                self._verify_inputs(owner, rid, sample, state, run, material)
                for saved, result in zip(snapshot["results"], results):
                    aid = saved["artifact_id"]
                    canonical = state["_canonical_artifacts"][aid]
                    if (canonical["receipt_file"] != receipt["file"] or canonical["receipt_sha256"] != receipt["sha256"]
                            or canonical["sha256"] != saved["sha256"]
                            or state["_artifacts"][aid]["sha256"] != saved["display_sha256"]):
                        raise ValueError("result_changed")
                    self.inputs.receipt_artifacts(state, canonical)
                    artifact = self.artifacts.projection(state, aid)
                    if artifact["access_state"] == "denied":
                        raise ValueError("result_denied")
                    if artifact["access_state"] != "historical_unreviewed" or artifact["acknowledged"]:
                        self.artifacts.read(state, aid)
                    result["artifact"] = artifact
        except (HTTPException, ValueError, OSError, KeyError, TypeError):
            availability = {"status": "unavailable", "reason_code": "analysis_source_unavailable"}
            for result in results:
                result["artifact"] = None
        value.update(results=results, availability=availability)
        return deepcopy(value)

    def list(self, owner, rid, sample_id):
        with self.lock:
            self._sample(owner, rid, sample_id)
            rows = self._records(owner, rid)
            return {"analyses": [self._public(owner, rid, row) for row in sorted(rows, key=lambda r: r["version"])
                                 if row["sample_id"] == sample_id]}

    def get(self, owner, rid, aid):
        with self.lock:
            row = next((r for r in self._records(owner, rid) if r["id"] == aid), None)
            if row is None:
                raise HTTPException(404, "analysis_not_found")
            return self._public(owner, rid, row)


def install_sample_analysis_http(app, store):
    prefix = "/api/researches/{rid}"

    @app.get(prefix + "/samples/{sample_id}/analysis-sources")
    def sources(rid: str, sample_id: str, session_id: str, request: Request):
        return store.sources(request.state.principal.id, rid, sample_id, session_id)

    @app.get(prefix + "/samples/{sample_id}/analyses")
    def listing(rid: str, sample_id: str, request: Request):
        return store.list(request.state.principal.id, rid, sample_id)

    @app.post(prefix + "/samples/{sample_id}/analyses")
    def register(rid: str, sample_id: str, body: AnalysisRegistration, request: Request):
        return store.register(request.state.principal.id, rid, sample_id, body)

    @app.get(prefix + "/analyses/{aid}")
    def detail(rid: str, aid: str, request: Request):
        return store.get(request.state.principal.id, rid, aid)


    @app.get(prefix + "/analyses/{aid}/genes")
    def genes(rid: str, aid: str, request: Request, response: Response, query: str = Query(default="", max_length=200),
              offset: int = Query(default=0, ge=0), limit: int = Query(default=50, ge=1, le=200)):
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return store.gene_data(request.state.principal.id, rid, aid, query=query, offset=offset, limit=limit)

    @app.get(prefix + "/analyses/{aid}/gene-expression")
    def expression(rid: str, aid: str, request: Request, response: Response,
                   gene: list[Annotated[str, StringConstraints(min_length=1, max_length=200)]] = Query(min_length=1, max_length=32)):
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return store.gene_data(request.state.principal.id, rid, aid, genes=gene)

    @app.get(prefix + "/analyses/{aid}/results/{result_id}")
    def result(rid: str, aid: str, result_id: str, request: Request):
        artifact, raw = store.automatic_result(request.state.principal.id, rid, aid, result_id)
        disposition = "inline" if artifact["kind"] in {"figure", "evidence"} else "attachment"
        return Response(raw, media_type=artifact["media_type"], headers={
            "Content-Disposition": f'{disposition}; filename="{artifact["name"]}"',
            "X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store",
        })

    @app.get(prefix + "/analyses/{aid}/results/{result_id}/preview")
    def preview(rid: str, aid: str, result_id: str, request: Request):
        from .artifacts import (
            ArtifactPreviewTooLarge, PARQUET_STORED_LIMIT, parquet_preview,
        )
        artifact, raw = store.automatic_result(request.state.principal.id, rid, aid, result_id)
        if artifact["kind"] != "table":
            raise HTTPException(415, "artifact_preview_unsupported")
        if len(raw) > PARQUET_STORED_LIMIT:
            raise HTTPException(413, "artifact_preview_too_large")
        try:
            encoded = parquet_preview(raw)
        except ArtifactPreviewTooLarge:
            raise HTTPException(413, "artifact_preview_too_large") from None
        except Exception:
            raise HTTPException(422, "artifact_preview_unavailable") from None
        return Response(encoded, media_type="application/json", headers={
            "X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store",
        })
