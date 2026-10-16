"""Bounded research mapping workers; scientific values belong to registered tools."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
from threading import BoundedSemaphore

from fastapi import HTTPException

from bridge.storage.private_paths import ensure_private_directory
from bridge.toolkit.contracts import ToolRun
from bridge.tool_packages.p0_01_input_qc.io import sha256_path
from bridge.tool_packages.p0_02_cell_state.quick_atlas_reference import canonical, digest, read_manifest
from .sessions import read_file, write_file
from .workbench_http import load_tree
from .sample_workflow import issue, state_for


def execute_job(directory, *, qc_completed, cell_cycle_completed, cell_atlas_completed):
    """Publish the committed QC receipt while the isolated mapping keeps running."""
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[2])
    for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMBA_NUM_THREADS"):
        environment[key] = "2"
    command = [sys.executable, "-m", "bridge.web.atlas_worker", str(directory / "job.json")]
    with (directory / "worker.log").open("xb") as log:
        with subprocess.Popen(command, env=environment, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                              start_new_session=True) as process:
            deadline = time.monotonic() + 1800
            published = set()

            def publish():
                for name, callback in (("qc", qc_completed), ("cell-cycle", cell_cycle_completed),
                                       ("cell-atlas", cell_atlas_completed)):
                    if name not in published and (directory / (name + "-run.json")).exists():
                        callback()
                        published.add(name)

            try:
                while True:
                    publish()
                    try:
                        code = process.wait(timeout=min(0.25, max(0.001, deadline - time.monotonic())))
                        break
                    except subprocess.TimeoutExpired:
                        if time.monotonic() >= deadline:
                            raise subprocess.TimeoutExpired(command, 1800)
                publish()
                if code:
                    raise subprocess.CalledProcessError(code, command)
            except BaseException:
                # Kill our whole worker group, including the optional cycle child.
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
                raise


class AtlasMapping:
    def __init__(self, objects, researches, settings, quotas, registry, *, prepare_analysis, register_qc, register_cell_cycle, register_cell_atlas, workflow_issues, handoff):
        self.objects, self.researches = objects, researches
        self.settings, self.quotas, self.registry = settings, quotas, registry
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="bridge-atlas")
        self.capacity = BoundedSemaphore(1)
        self.pending = {}
        self.prepare_analysis = prepare_analysis
        self.register_qc = register_qc
        self.register_cell_cycle = register_cell_cycle
        self.register_cell_atlas = register_cell_atlas
        self.workflow_issues, self.handoff = workflow_issues, handoff

    def attention(self, owner, rid, sample_id, findings, *, attempt_id=None):
        workflow = state_for(findings, attempt_id)
        previous = self.objects.sample(owner, rid, sample_id).get("workflow")
        if previous and previous["attempt_id"] == attempt_id and previous["issues"] == findings and previous["status"] != "running":
            return
        if self.objects.set_sample_workflow(owner, rid, sample_id, workflow, attempt_id=attempt_id) and findings:
            self.handoff(owner, rid, sample_id)

    def shutdown(self):
        self.pool.shutdown(wait=True, cancel_futures=False)

    def has_pending(self, sample_id):
        with self.objects.lock:
            return any(sid == sample_id and not future.done() for future, sid in self.pending.items())

    def configuration(self, sample):
        settings = self.settings()
        declaration = sample.get("mapping_input")
        if not declaration:
            return None, "mapping_input_required"
        if settings.quick_atlas_catalog_path is None:
            return None, "standard_mapping_not_configured"
        try:
            catalog = json.loads(read_file(settings.quick_atlas_catalog_path, 1024 * 1024))
            entry = catalog[declaration["sample_context"]]
            path = Path(entry["manifest"])
            if not path.is_absolute():
                raise ValueError("invalid_reference_path")
            manifest = read_manifest(path, entry["sha256"])
            expected = {"pre_graft": ("scRNA", "scRNA-seq"), "post_graft": ("snRNA", "snRNA-seq")}
            modality, assay = expected[declaration["sample_context"]]
            if manifest["modality"] != modality or sample["assay"] != assay:
                raise ValueError("reference_modality")
            if settings.workbench_tree_path is None or digest(load_tree(settings.workbench_tree_path)) != manifest["tree"]["sha256"]:
                return None, "mapping_tree_mismatch"
            return {"reference_manifest": str(path), "reference_manifest_sha256": entry["sha256"],
                    "sample_context": declaration["sample_context"],
                    "tree_sha256": manifest["tree"]["sha256"]}, None
        except (OSError, ValueError, KeyError, TypeError):
            return None, "mapping_reference_unavailable"

    def schedule(self, owner, rid, sample_id, *, explicit=False, allow_completed=False):
        snapshot = self.objects.mapping_source(owner, rid, sample_id)
        sample = snapshot["sample"]
        if not sample["material_id"]:
            if explicit:
                raise HTTPException(409, "mapping_material_required")
            return self.objects.sample(owner, rid, sample_id)
        previous = snapshot["assessment"]
        # A saved correction survives a busy worker or a process exit before dispatch.
        # Idempotence depends on the attempted declaration, not this HTTP mutation.
        allow_completed = allow_completed or bool(previous and
            previous.get("_mapping_input", sample.get("mapping_input")) != sample.get("mapping_input"))
        if snapshot["assessment"] and (snapshot["assessment"]["status"] == "running" or
                snapshot["assessment"]["status"] == "done" and not allow_completed):
            if explicit:
                raise HTTPException(409, "mapping_already_started")
            return self.objects.sample(owner, rid, sample_id)
        config, reason = self.configuration(sample)
        if explicit and reason:
            # The legacy /mapping endpoint remains a mapping-only retry. The
            # sample lifecycle and /workflow can run basics without a reference.
            self.objects.mapping_blocked(owner, rid, sample_id, reason)
            return self.objects.sample(owner, rid, sample_id)
        if reason == "mapping_input_required":
            self.objects.mapping_blocked(owner, rid, sample_id,
                reason if self.settings().quick_atlas_catalog_path is not None else "standard_mapping_not_configured")
            self.attention(owner, rid, sample_id, [issue(reason)])
            return self.objects.sample(owner, rid, sample_id)
        mapping_reason = reason
        config = config or {"mapping_reason": mapping_reason}
        if not self.capacity.acquire(blocking=False):
            self.objects.mapping_blocked(owner, rid, sample_id, "mapping_worker_busy")
            return self.objects.sample(owner, rid, sample_id)
        reservation = self.quotas.reserve_task(owner)
        entered = False
        aid = None
        try:
            try:
                reservation.__enter__()
                entered = True
            except HTTPException:
                self.objects.mapping_blocked(owner, rid, sample_id, "mapping_worker_busy")
                return self.objects.sample(owner, rid, sample_id)
            with self.researches.checked_material(owner, rid, sample["material_id"]):
                pass
            aid = self.objects.begin_mapping(owner, rid, sample_id, sample["revision"], config,
                                             allow_completed=allow_completed)
            directory, _, _ = ensure_private_directory(self.researches.directory(rid) / "atlas-runs" / aid)
            material = self.researches.material(owner, rid, sample["material_id"])
            source = self.researches.directory(rid) / "materials" / (sample["material_id"] + ".bin")
            declaration = sample["mapping_input"]
            job = {"id": aid, "asset": {
                "asset_id": sample["material_id"], "path": str(source), "format": "h5ad",
                "input_level": "count_ready", "checksum": material["sha256"],
                "matrix_location": declaration["matrix_location"], "matrix_semantics": declaration["matrix_semantics"],
                "assay": sample["assay"], "metadata": {k: declaration[k] for k in
                    ("source_family_id", "capture_id", "capture_id_column", "gene_symbol_column")
                    if declaration.get(k) is not None}},
                "parameters": ({k: config[k] for k in ("reference_manifest", "reference_manifest_sha256", "sample_context")}
                               if not mapping_reason else {})}
            write_file(directory / "job.json", canonical(job))

            def work():
                outcome_reason = mapping_reason
                try:
                    def publish(register):
                        try:
                            register(owner, rid, aid)
                        except HTTPException as exc:
                            if exc.detail != "analysis_source_unavailable":
                                raise
                    execute_job(directory, qc_completed=lambda: publish(self.register_qc),
                                cell_cycle_completed=lambda: publish(self.register_cell_cycle),
                                cell_atlas_completed=lambda: publish(self.register_cell_atlas))
                    if mapping_reason:
                        self.objects.fail_mapping(owner, rid, aid, mapping_reason)
                        return
                    raw = read_file(directory / "mapping-run.json", 2 * 1024 * 1024)
                    run = ToolRun.model_validate_json(raw)
                    self.registry.validate_result(run, run.request)
                    if run.execution_state != "succeeded":
                        reason = next(iter(run.reason_codes), "mapping_execution_failed")
                        if not re.fullmatch(r"[a-z][a-z0-9_]{0,99}", reason):
                            reason = "mapping_execution_failed"
                        outcome_reason = reason
                        self.objects.fail_mapping(owner, rid, aid, reason)
                        return
                    if (run.request.request_id != aid or run.request.tool_id != "P0-02"
                            or run.input_hash != material["sha256"]
                            or run.request.measurement_spec_ref != "ATLAS-ingest-quick-v0.1"
                            or run.request.parameters != job["parameters"]
                            or len(run.request.assets) != 1 or run.request.assets[0].path != source):
                        raise ValueError("mapping_receipt_binding_mismatch")
                    artifact = next(a for a in run.artifacts if a.kind == "quick_atlas_mapping")
                    if not artifact.path.is_relative_to(directory) or artifact.path.is_symlink():
                        raise ValueError("mapping_result_path_invalid")
                    result_raw = read_file(artifact.path, 2 * 1024 * 1024)
                    result = json.loads(result_raw)
                    if (hashlib.sha256(result_raw).hexdigest() != artifact.sha256 or result != run.result
                            or result["input_sha256"] != material["sha256"]
                            or result["versions"]["tree"] != config["tree_sha256"]
                            or result["reference_manifest_sha256"] != config["reference_manifest_sha256"]):
                        raise ValueError("mapping_result_integrity")
                    with self.researches.checked_material(owner, rid, sample["material_id"]):
                        pass
                    if digest(load_tree(self.settings().workbench_tree_path)) != config["tree_sha256"]:
                        raise ValueError("mapping_tree_changed")
                    binding = {"path": str(artifact.path.relative_to(self.researches.directory(rid))),
                               "sha256": artifact.sha256}
                    receipt = {"path": str((directory / "mapping-run.json").relative_to(self.researches.directory(rid))),
                               "sha256": hashlib.sha256(raw).hexdigest()}
                    def prepare(sample, experiment, assessment):
                        return self.prepare_analysis(owner, rid, sample, experiment, assessment, run)
                    self.objects.finish_mapping(owner, rid, aid, run.run_id, binding, receipt,
                                                prepare_analysis=prepare)
                except Exception:
                    outcome_reason = "mapping_execution_failed"
                    self.objects.fail_mapping(owner, rid, aid, outcome_reason)
                finally:
                    reservation.__exit__(None, None, None)
                    self.capacity.release()
                    findings = self.workflow_issues(owner, rid, aid, outcome_reason)
                    self.attention(owner, rid, sample_id, findings, attempt_id=aid)

            future = self.pool.submit(work)
            with self.objects.lock:
                self.pending = {f: sid for f, sid in self.pending.items() if not f.done()}
                self.pending[future] = sample_id
            entered = False  # Worker owns reservation/capacity from this point.
            return self.objects.sample(owner, rid, sample_id)
        except Exception:
            if aid is not None:
                self.objects.fail_mapping(owner, rid, aid, "mapping_execution_failed")
            raise
        finally:
            if entered:
                reservation.__exit__(None, None, None)
                self.capacity.release()
            elif aid is None:
                self.capacity.release()
