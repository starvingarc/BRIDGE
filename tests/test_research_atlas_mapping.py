"""Research mapping lifecycle and ownership exercise real HTTP and registered tools."""
from dataclasses import replace
import json
import time

import pytest
from fastapi.testclient import TestClient

from account_support import create_test_app, login_test_account
from multiuser_support import multi_clients
from test_research_objects import research, ready_protocol, run, sample, base, request
from quick_atlas_support import reference_data, tree_data, RECIPE
from bridge.web.runtime import Settings

DECLARATION = {"matrix_location": "X", "matrix_semantics": "raw_counts",
               "sample_context": "pre_graft", "source_family_id": "SYNTHETIC-QUERY"}


def resources(tmp_path):
    from bridge.tool_packages.p0_02_cell_state.quick_atlas_reference import freeze_reference
    from bridge.tool_packages.p0_01_input_qc.io import sha256_path
    tree, ids = tree_data()
    manifest = freeze_reference(reference_data(), tree, ids, tmp_path / "reference",
                                reference_id="REF-CHEN-VMB-SC-v1", modality="scRNA",
                                source_records=[{"id": "synthetic", "sha256": "a" * 64}], recipe=RECIPE)
    catalog = tmp_path / "atlas-catalog.json"
    catalog.write_text(json.dumps({"pre_graft": {"manifest": str(manifest), "sha256": sha256_path(manifest)}}))
    return {"quick_atlas_catalog_path": catalog, "workbench_tree_path": manifest.parent / "tree.json"}


def upload(client, rid, tmp_path):
    query = reference_data()[[3, 35, 67]].copy()
    query.obs_names = ["private-rg", "private-da", "private-vascular"]
    path = tmp_path / "query.h5ad"
    query.write_h5ad(path)
    with path.open("rb") as stream:
        result = client.post(base(rid) + "/uploads", files={"file": ("query.h5ad", stream)})
    assert result.status_code == 200, result.text
    return result.json()["id"]


def objects(client):
    rid = research(client)
    _, version = ready_protocol(client, rid)
    r = run(client, rid, version)
    return rid, r


def wait_mapping(client, rid, sid):
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        board = request(client, "GET", base(rid) + "/workbench")
        s = next(s for s in board["samples"] if s["id"] == sid)
        if s["status"] != "mapping":
            return s, board
        time.sleep(0.1)
    pytest.fail("mapping did not settle")


def test_missing_input_stays_attached_and_cross_modality_never_falls_back(tmp_path):
    options = resources(tmp_path)
    with multi_clients(tmp_path / "accounts", **options) as (_, alice, bob, admin):
        rid, r = objects(alice)
        mid = upload(alice, rid, tmp_path)
        s = sample(alice, rid, r, material_id=mid)
        assert s["status"] == "data_attached"
        assert s["assessment_availability"]["code"] == "mapping_input_required"
        assert s["assessment_id"] is None
        for other in (bob, admin):
            response = other.post(base(rid) + f"/samples/{s['id']}/mapping",
                                  json={"expected_version": s["revision"], "mapping_input": DECLARATION})
            assert response.status_code == 404
        # Post-graft cannot use scRNA or the pre-graft reference by default.
        bad = {**DECLARATION, "sample_context": "post_graft"}
        started = request(alice, "POST", base(rid) + f"/samples/{s['id']}/mapping",
                          {"expected_version": s["revision"], "mapping_input": bad})
        assert started["status"] == "data_attached"
        assert started["assessment_id"] is None
        assert started["assessment_availability"]["code"] == "mapping_reference_unavailable"


def test_attach_runs_registered_mapping_then_restores_and_checks_artifacts(tmp_path):
    options = resources(tmp_path)
    settings = Settings(storage_root=tmp_path / "store", origin="http://testserver",
                        model_base_url="https://provider.invalid/v1", model="unused", model_api_key="unused", **options)
    with TestClient(create_test_app(settings)) as client:
        login_test_account(client)
        rid, r = objects(client)
        s = sample(client, rid, r)
        mid = upload(client, rid, tmp_path)
        linked = request(client, "PATCH", base(rid) + f"/samples/{s['id']}",
                         {"material_id": mid, "expected_version": s["revision"], "mapping_input": DECLARATION})
        assert linked["status"] in ("mapping", "done")
        assert linked["assessment_id"]
        final, board = wait_mapping(client, rid, s["id"])
        assert final["status"] == "done", board
        result = request(client, "GET", base(rid) + f"/assessments/{final['assessment_id']}")
        assert result["status"] == "done"
        assert result["n_cells"] == 3 and result["n_tree_cells"] == 2
        assert result["mapped_cells"] == [[-0.8, 0.1, 0.0, 0], [0.8, 0.3, 0.1, 1]]
        assert result["target_fraction"] is None and result["tool_run_id"]
        assert all(x not in json.dumps(result) for x in (str(tmp_path), "private-rg", "query.h5ad"))
        request(client, "POST", base(rid) + f"/samples/{s['id']}/mapping",
                {"expected_version": final["revision"]}, status=409)
        panel_url = base(rid) + f"/assessments/{final['assessment_id']}/marker-expression"
        panel = request(client, "GET", panel_url)
        assert panel["genes"] == result["marker_expression"]["genes"]
        assert panel["tree_version"] == result["versions"]["tree"]
        assert len(panel["sample"]["values"]) == 2
        assert panel["reference"]["tree_cell_indices"] == list(range(6))
        assert all(x not in json.dumps(panel) for x in (str(tmp_path), "private-rg", "ref-0"))
        root = client.app.state.service.researches.directory(rid)
    with TestClient(create_test_app(settings)) as restored:
        login_test_account(restored)
        assert request(restored, "GET", base(rid) + f"/assessments/{final['assessment_id']}") == result
        assert request(restored, "GET", panel_url) == panel
        stored = json.loads((root / "objects.json").read_text())
        receipt_path = root / stored["assessments"][final["assessment_id"]]["_receipt"]["path"]
        receipt = json.loads(receipt_path.read_text())
        from pathlib import Path
        panel_path = Path(next(a["path"] for a in receipt["artifacts"] if a["kind"] == "quick_atlas_marker_expression"))
        original = panel_path.read_bytes()
        panel_path.write_bytes(original + b" ")
        request(restored, "GET", panel_url, status=409)
        # Independent display corruption does not erase the valid mapping summary.
        assert request(restored, "GET", base(rid) + f"/assessments/{final['assessment_id']}") == result
        panel_path.write_bytes(original)
        binding = stored["assessments"][final["assessment_id"]]["_result"]
        artifact = root / binding["path"]
        artifact.write_text(artifact.read_text() + " ")
        request(restored, "GET", base(rid) + f"/assessments/{final['assessment_id']}", status=409)
        request(restored, "GET", base(rid) + "/workbench", status=409)


def test_interrupted_attempt_is_failed_and_retry_keeps_history(tmp_path, monkeypatch):
    from threading import Event
    from bridge.web import atlas_mapping
    options = resources(tmp_path)
    started, release = Event(), Event()
    def interrupted_job(*args, **kwargs):
        started.set()
        assert release.wait(10)
        raise RuntimeError("simulated_worker_failure")
    monkeypatch.setattr(atlas_mapping, "execute_job", interrupted_job)
    settings = Settings(storage_root=tmp_path / "store", origin="http://testserver",
                        model_base_url="https://provider.invalid/v1", model="unused", model_api_key="unused", **options)
    with TestClient(create_test_app(settings)) as client:
        # This probe controls mapping admission; the separately tested agent handoff
        # must not race the single-account task quota after the injected failure.
        monkeypatch.setattr(client.app.state.service.atlas_mapping, "handoff", lambda *args: None)
        login_test_account(client)
        rid, r = objects(client)
        mid = upload(client, rid, tmp_path)
        s = sample(client, rid, r, material_id=mid, mapping_input=DECLARATION)
        try:
            assert started.wait(5)
            assert s["status"] == "mapping"
            current_run = request(client, "GET", base(rid) + "/workbench")["runs"][0]
            busy = sample(client, rid, current_run, material_id=mid, mapping_input=DECLARATION)
            assert busy["status"] == "data_attached" and busy["assessment_id"] is None
            assert busy["assessment_availability"]["code"] == "mapping_worker_busy"
            request(client, "POST", base(rid) + f"/samples/{s['id']}/mapping",
                    {"expected_version": s["revision"]}, status=409)
            # Simulate startup recovery while the old worker is fenced by persisted status.
            client.app.state.service.research_objects.recover_mappings()
        finally:
            release.set()
        final, board = wait_mapping(client, rid, s["id"])
        assert final["status"] == "failed"
        old = request(client, "GET", base(rid) + f"/assessments/{s['assessment_id']}")
        assert old["failure"]["code"] == "mapping_interrupted"
        # A later failed attempt must have a new identity and preserve the first.
        deadline = time.monotonic() + 5
        while client.app.state.service.atlas_mapping.has_pending(s["id"]) and time.monotonic() < deadline:
            time.sleep(0.01)
        # An old failure must not hide why the next attempt cannot start.
        client.app.state.service.settings = replace(settings, quick_atlas_catalog_path=None)
        unconfigured = request(client, "POST", base(rid) + f"/samples/{s['id']}/mapping",
                               {"expected_version": final["revision"]})
        assert unconfigured["assessment_availability"] == {"status": "unavailable", "code": "standard_mapping_not_configured"}
        client.app.state.service.settings = settings
        started.clear()
        release.clear()
        try:
            other = request(client, "POST", base(rid) + f"/samples/{busy['id']}/mapping",
                            {"expected_version": busy["revision"]})
            assert started.wait(5)
            blocked = request(client, "POST", base(rid) + f"/samples/{s['id']}/mapping",
                              {"expected_version": unconfigured["revision"]})
            assert blocked["status"] == "failed" and blocked["assessment_id"] == old["id"]
            assert blocked["assessment_availability"] == {"status": "unavailable", "code": "mapping_worker_busy"}
        finally:
            release.set()
        wait_mapping(client, rid, busy["id"])
        deadline = time.monotonic() + 5
        while client.app.state.service.atlas_mapping.has_pending(busy["id"]) and time.monotonic() < deadline:
            time.sleep(0.01)
        client.app.state.service.settings = replace(settings, quick_atlas_catalog_path=None)
        blocked = request(client, "POST", base(rid) + f"/samples/{s['id']}/mapping",
                          {"expected_version": blocked["revision"]})
        assert blocked["assessment_availability"] == {"status": "unavailable", "code": "standard_mapping_not_configured"}
        assert blocked["assessment_id"] == old["id"]
        client.app.state.service.settings = settings
        retry = request(client, "POST", base(rid) + f"/samples/{s['id']}/mapping",
                        {"expected_version": blocked["revision"]})
        assert retry["assessment_id"] != old["id"]
        wait_mapping(client, rid, s["id"])
        assert request(client, "GET", base(rid) + f"/assessments/{old['id']}") == old


def test_worker_applies_operator_ancestor_pins_before_reading_job(tmp_path):
    import os
    import subprocess
    import sys
    from pathlib import Path
    directory = tmp_path / "operator-approved"
    directory.mkdir(mode=0o700)
    stat = directory.stat()
    # An invalid inode pin must be rejected before any job access, even when
    # the current account would otherwise have filesystem access.
    pins = {str(directory): [stat.st_uid, stat.st_dev, stat.st_ino + 1]}
    env = {**os.environ, "BRIDGE_WEB_TRUSTED_ANCESTORS": json.dumps(pins),
           "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
    run = subprocess.run([sys.executable, "-m", "bridge.web.atlas_worker", str(directory / "absent.json")],
                         env=env, capture_output=True, text=True, timeout=30)
    assert run.returncode != 0
    assert "trusted_ancestor_identity_mismatch" in run.stderr
    assert "FileNotFoundError" not in run.stderr
