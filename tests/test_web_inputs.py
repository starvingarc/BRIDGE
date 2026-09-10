from __future__ import annotations

import hashlib
import importlib
import json
from pathlib import Path

import pytest

from bridge.web.inputs import Inputs, Selection, strict_json
from bridge.web.app import write_file
from test_web_service import (
    client,
    confirm_change,
    declare_source,
    declare_counts,
    h5ad,
    new_session,
    settle,
)


def context_upload(client, tmp_path):
    sid = new_session(client)["id"]
    url = f"/api/sessions/{sid}"
    response = client.post(url + "/uploads", files={"file": ("synthetic.h5ad", h5ad(tmp_path, layer=True))})
    aid = response.json()["uploads"][0]["id"]
    staged = client.post(url + "/analysis-inputs/assets", json={
        "upload_id": aid, "assay": "scRNA-seq", "matrix_location": "layers/counts",
        "matrix_semantics": "raw_counts", "input_level": "count_ready", "metadata": {},
    })
    assert staged.status_code == 200, staged.json()
    confirm_change(client, sid, staged.json())
    return sid, aid


def test_optional_column_mappings_are_confirmed_and_bound_to_requests(client, tmp_path):
    sid, aid = context_upload(client, tmp_path)
    url = f"/api/sessions/{sid}"
    metadata = {
        "sample_id_column": "sample",
        "capture_id_column": "capture",
        "gene_symbol_column": "symbol",
    }
    declaration = dict(upload_id=aid, assay="scRNA-seq", matrix_location="layers/counts",
                       matrix_semantics="raw_counts", input_level="count_ready", metadata=metadata)
    staged = client.post(url + "/analysis-inputs/assets", json=declaration)
    assert staged.status_code == 200, staged.json()
    service = client.app.state.service
    assert service.load(sid)["_asset_declarations"][aid]["metadata"] == {}
    confirm_change(client, sid, staged.json())
    assert service.load(sid)["_asset_declarations"][aid]["metadata"] == metadata
    rejected = client.post(url + "/analysis-inputs/assets",
                          json={**declaration, "metadata": {**metadata, "arbitrary_option": True}})
    assert rejected.status_code == 422
    assert service.load(sid)["_asset_declarations"][aid]["metadata"] == metadata
    assert client.post(url + "/analysis-inputs",
                       json=choice("P0-01", None, assets=[aid])).status_code == 200
    prepared = client.post(url + "/prepare-analysis", json={"tool_id": "P0-01"})
    assert prepared.status_code == 200, prepared.json()
    step = service.load(sid)["_plan"]["steps"][0]
    request = json.loads(step["approved_request_json"])
    assert request["assets"][0]["metadata"] == metadata


def choice(tool, mode, objects=(), assets=()):
    return dict(tool_id=tool, mode_id=mode, asset_ids=list(assets), object_inputs=list(objects), measurement_spec_ref=None)


def upload_request(client, sid, request, mode):
    objects = []
    # Client authoring: bind descriptor references to IDs returned by the input API.
    # This changes only caller-owned request-local identifiers, never server scientific values.
    ordered = sorted(request.object_inputs, key=lambda ref: ref.role in {"domain_gate_input", "compilation_bundle"})
    aliases = {}
    for ref in ordered:
        data = ref.path.read_bytes()
        if ref.role in {"domain_gate_input", "compilation_bundle"}:
            def bind(value, key=""):
                if isinstance(value, dict):
                    return {name: bind(child, name) for name, child in value.items()}
                if isinstance(value, list):
                    return [bind(child, key) for child in value]
                if isinstance(value, str) and (key.endswith("_input_id") or key.endswith("_input_ids")):
                    return aliases.get(value, value)
                return value
            data = json.dumps(bind(json.loads(data)), sort_keys=True).encode()
        response = client.post(f"/api/sessions/{sid}/analysis-inputs/objects",
            params=dict(tool_id=request.tool_id, mode_id=mode, role=ref.role,
                        schema_ref=ref.schema_ref, object_version=ref.object_version),
            files={"file": ("object.json", data, "application/json")})
        assert response.status_code == 200, (ref.role, response.json())
        state = client.app.state.service.load(sid)
        identifier = next(reversed(state["_input_objects"]))
        assert state["_input_objects"][identifier]["sha256"] == hashlib.sha256(data).hexdigest()
        aliases[ref.input_id] = identifier
        objects.append({"role": ref.role, "input_id": identifier})
    return objects


def approve(client, sid, proposal):
    response = client.post(f"/api/sessions/{sid}/approve",
        json={"plan_id": proposal["id"], "plan_digest": proposal["digest"]})
    assert response.status_code == 200, response.json()
    return settle(client, sid)


def selected_p002_context(client, tmp_path, monkeypatch, *, panel):
    from dataclasses import replace
    from test_cell_state import _build_snapshot, _write_query

    sid = new_session(client)["id"]
    url = f"/api/sessions/{sid}"
    data = _write_query(tmp_path / "query.h5ad").read_bytes()
    aid = client.post(
        url + "/uploads",
        files={"file": ("synthetic.h5ad", data)},
    ).json()["uploads"][0]["id"]
    if panel:
        staged = client.post(url + "/analysis-inputs/assets", json={
            "upload_id": aid,
            "assay": "scRNA-seq",
            "matrix_location": "X",
            "matrix_semantics": "raw_counts",
            "input_level": "count_ready",
            "metadata": {"sample_id": "panel-sample"},
        })
        assert staged.status_code == 200, staged.json()
        confirm_change(client, sid, staged.json())
        selected = client.post(
            url + "/analysis-inputs",
            json=choice("P0-01", None, assets=[aid]),
        )
        assert selected.status_code == 200, selected.json()
        qc_proposal = client.post(
            url + "/prepare-analysis",
            json={"tool_id": "P0-01"},
        ).json()["plan"]
    else:
        declare_counts(client, sid, aid)
        client.post(
            url + "/messages",
            json={"text": "scRNA-seq，X 是原始计数，进行 QC"},
        )
        qc_proposal = settle(client, sid)["plan"]
    assert approve(client, sid, qc_proposal)["plan"]["status"] == "completed"
    _build_snapshot(tmp_path, monkeypatch)
    service = client.app.state.service
    service.settings = replace(
        service.settings,
        cell_state_measurement_spec_ref="CELLSTATE-scRNA-shadow-v0.1",
    )
    declare_source(client, sid, aid, "source-family:selected-input")
    selection = {
        **choice("P0-02", None, assets=[aid]),
        "measurement_spec_ref": "CELLSTATE-scRNA-shadow-v0.1",
    }
    return sid, aid, data, selection


def test_selected_p002_panel_declaration_uses_read_only_qc_enrichment(
        client, tmp_path, monkeypatch):
    sid, aid, data, selection = selected_p002_context(
        client, tmp_path, monkeypatch, panel=True
    )
    service = client.app.state.service
    state = service.load(sid)
    original = service.qc_asset(state, aid, register=False)
    before = json.loads(json.dumps({
        "asset": state["_asset_declarations"],
        "qc": state["_qc_declarations"],
        "uploads": state["_uploads"],
        "runs": state["_tool_runs"],
    }))
    catalog_path = service.root / "qc-catalog.json"
    before_catalog = catalog_path.read_bytes() if catalog_path.exists() else None

    saved = client.post(f"/api/sessions/{sid}/analysis-inputs", json=selection)
    assert saved.status_code == 200, saved.json()
    capability = next(
        item for item in saved.json()["capabilities"]
        if item["tool_id"] == "P0-02"
    )
    assert capability["state"] == "ready"
    current = service.load(sid)
    effective = service.inputs.selected_asset(current, "P0-02", aid)
    assert effective.asset_id == aid
    assert effective.checksum == hashlib.sha256(data).hexdigest()
    assert effective.assay == original.assay == "scRNA-seq"
    assert effective.matrix_location == original.matrix_location == "X"
    assert effective.metadata["sample_id"] == "panel-sample"
    assert effective.metadata["source_family_id"] == "source-family:selected-input"
    assert effective.metadata["parent_asset_sha256"] == effective.checksum
    assert service.qc_asset(current, aid, register=False) == original
    assert current["_asset_declarations"] == before["asset"]
    assert current["_qc_declarations"] == before["qc"]
    assert current["_uploads"] == before["uploads"]
    assert current["_tool_runs"] == before["runs"]
    assert (
        catalog_path.read_bytes() if catalog_path.exists() else None
    ) == before_catalog


def test_selected_p002_ignores_corrupt_qc_receipt_for_other_upload(
        client, tmp_path, monkeypatch):
    sid, earlier, _, selection = selected_p002_context(
        client, tmp_path, monkeypatch, panel=False
    )
    service = client.app.state.service
    url = f"/api/sessions/{sid}"
    later = client.post(
        url + "/uploads",
        files={"file": ("later.h5ad", h5ad(tmp_path, layer=True))},
    ).json()["uploads"][-1]["id"]
    staged = client.post(url + "/analysis-inputs/assets", json={
        "upload_id": later,
        "assay": "scRNA-seq",
        "matrix_location": "layers/counts",
        "matrix_semantics": "raw_counts",
        "input_level": "count_ready",
        "metadata": {},
    })
    assert staged.status_code == 200, staged.json()
    confirm_change(client, sid, staged.json())
    selected = client.post(
        url + "/analysis-inputs",
        json=choice("P0-01", None, assets=[later]),
    )
    assert selected.status_code == 200, selected.json()
    qc_proposal = client.post(
        url + "/prepare-analysis",
        json={"tool_id": "P0-01"},
    ).json()["plan"]
    assert approve(client, sid, qc_proposal)["plan"]["status"] == "completed"
    declare_source(client, sid, later, "source-family:later-qc")

    earlier_selection = client.post(url + "/analysis-inputs", json=selection)
    assert earlier_selection.status_code == 200, earlier_selection.json()
    assert next(
        item for item in earlier_selection.json()["capabilities"]
        if item["tool_id"] == "P0-02"
    )["state"] == "ready"
    state = service.load(sid)
    assert [item["state"] for item in state["_tool_runs"]] == [
        "succeeded",
        "succeeded",
    ]
    later_receipt = state["_tool_runs"][-1]
    later_receipt_path = (
        service.directory(sid) / "receipts" / later_receipt["file"]
    )
    write_file(later_receipt_path, later_receipt_path.read_bytes() + b" ")

    earlier_capability = next(
        item for item in client.get(url).json()["capabilities"]
        if item["tool_id"] == "P0-02"
    )
    assert earlier_capability["state"] == "ready"
    assert service.inputs.selected_asset(
        service.load(sid), "P0-02", earlier
    ).asset_id == earlier

    corrupted = client.post(
        url + "/analysis-inputs",
        json={**selection, "asset_ids": [later]},
    )
    assert corrupted.status_code == 200, corrupted.json()
    later_capability = next(
        item for item in corrupted.json()["capabilities"]
        if item["tool_id"] == "P0-02"
    )
    assert later_capability["state"] == "needs_input"
    assert later_capability["reason_codes"] == [
        "qc_artifact_integrity_mismatch"
    ]


def test_selected_p002_binds_explicit_earlier_upload_and_requires_committed_source(
        client, tmp_path, monkeypatch):
    sid, aid, _, selection = selected_p002_context(
        client, tmp_path, monkeypatch, panel=False
    )
    service = client.app.state.service
    url = f"/api/sessions/{sid}"
    later = client.post(
        url + "/uploads",
        files={"file": ("later.h5ad", h5ad(tmp_path, layer=True))},
    ).json()["uploads"][-1]["id"]
    declare_source(client, sid, later, "source-family:later-no-qc")
    missing = client.post(
        url + "/analysis-inputs",
        json={**selection, "asset_ids": [later]},
    )
    assert missing.status_code == 200, missing.json()
    missing_capability = next(
        item for item in missing.json()["capabilities"]
        if item["tool_id"] == "P0-02"
    )
    assert missing_capability["state"] == "needs_input"
    assert missing_capability["reason_codes"] == ["completed_qc_required"]

    earlier = client.post(url + "/analysis-inputs", json=selection)
    assert earlier.status_code == 200, earlier.json()
    earlier_capability = next(
        item for item in earlier.json()["capabilities"]
        if item["tool_id"] == "P0-02"
    )
    assert earlier_capability["state"] == "ready"
    state = service.load(sid)
    runs = list(state["_tool_runs"])
    state["_qc_declarations"][aid]["metadata"]["source_family_id"] = (
        "stale-declaration-source"
    )
    state["_uploads"][aid].pop("source_family_id")
    service.save(state)
    no_source = next(
        item for item in client.get(url).json()["capabilities"]
        if item["tool_id"] == "P0-02"
    )
    assert no_source["state"] == "needs_input"
    assert no_source["reason_codes"] == ["source_family_id_required"]
    assert service.load(sid)["_tool_runs"] == runs


@pytest.mark.parametrize(
    ("tamper", "reason"),
    [
        ("receipt", "qc_artifact_integrity_mismatch"),
        ("artifact", "qc_artifact_integrity_mismatch"),
        ("declaration", "qc_declaration_retracted"),
    ],
)
def test_selected_p002_readiness_rejects_changed_qc_proof_without_catalog_write(
        client, tmp_path, monkeypatch, tamper, reason):
    sid, aid, _, selection = selected_p002_context(
        client, tmp_path, monkeypatch, panel=False
    )
    service = client.app.state.service
    url = f"/api/sessions/{sid}"
    saved = client.post(url + "/analysis-inputs", json=selection)
    assert saved.status_code == 200, saved.json()
    state = service.load(sid)
    catalog_path = service.root / "qc-catalog.json"
    before_catalog = catalog_path.read_bytes() if catalog_path.exists() else None
    receipt = state["_tool_runs"][-1]
    receipt_path = service.directory(sid) / "receipts" / receipt["file"]
    if tamper == "receipt":
        write_file(receipt_path, receipt_path.read_bytes() + b" ")
    elif tamper == "artifact":
        run = json.loads(receipt_path.read_bytes())
        artifact = next(
            item for item in run["artifacts"]
            if Path(item["path"]).name == "qc_readiness_profile.json"
        )
        path = Path(artifact["path"])
        write_file(path, path.read_bytes() + b" ")
    else:
        state["_uploads"][aid]["declaration_start"] += 1
        service.save(state)

    capability = next(
        item for item in client.get(url).json()["capabilities"]
        if item["tool_id"] == "P0-02"
    )
    assert capability["state"] == "needs_input"
    assert capability["reason_codes"] == [reason]
    assert (
        catalog_path.read_bytes() if catalog_path.exists() else None
    ) == before_catalog


@pytest.mark.parametrize("data", [
    b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}', b'{"x":1e999}',
    b'[]', b'null', b'{"x":' + b'[' * 33 + b'0' + b']' * 33 + b'}',
])
def test_strict_json_rejects_unsafe_objects(data):
    with pytest.raises(ValueError):
        strict_json(data)


def test_catalog_and_incomplete_selections_are_private(client, tmp_path):
    sid, aid = context_upload(client, tmp_path)
    url = f"/api/sessions/{sid}"
    response = client.get(url + "/analysis-inputs")
    assert response.status_code == 200, response.json()
    data = response.json()
    assert len(data["tools"]) == 12
    assert {item["label"] for item in data["objects"]} >= {"gate_rule_spec", "claim_policy_spec", "statement_registry"}
    text = json.dumps(data)
    assert str(tmp_path) not in text and "sha256" not in json.dumps(data["objects"])
    for tool in data["tools"]:
        modes = tool["input_contract"]["object_input_modes"]
        for mode in modes or [None]:
            body = choice(tool["tool_id"], mode["mode_id"] if mode else None)
            assert client.post(url + "/analysis-inputs", json=body).status_code == 200
    assert all(item["state"] != "not_connected" for item in client.get(url).json()["capabilities"])
    from dataclasses import replace
    service = client.app.state.service
    service.settings = replace(service.settings, cell_state_measurement_spec_ref=str(tmp_path / "private-spec.json"))
    catalog = client.get(url + "/analysis-inputs").json()
    assert catalog["measurement_specs"] == []
    assert str(tmp_path) not in json.dumps(catalog)


def test_selection_rejects_modes_roles_ids_cardinality_and_extra_envelope(client, tmp_path):
    sid, aid = context_upload(client, tmp_path)
    url = f"/api/sessions/{sid}/analysis-inputs"
    for body in [
        choice("P0-12", "invented"),
        choice("P0-12", "not_provided", assets=[aid]),
        choice("P0-12", "graft_assessment", objects=[{"role": "graft_case", "input_id": "0"*32}]),
        {**choice("P0-12", "not_provided"), "parameters": {"approve": True}},
        {**choice("P0-12", "not_provided"), "measurement_spec_ref": "unregistered"},
    ]:
        assert client.post(url, json=body).status_code == 422


@pytest.mark.parametrize("tool,mode,module,factory", [
    ("P0-05", "legacy_aggregation", "test_p0_05_off_target_control", "_request"),
    ("P0-05", "hard_count_accounting", "test_p0_05_hard_count_accounting", "_hard_count_request"),
    ("P0-06", "legacy_aggregation", "test_p0_06_proliferation_stress_response", "_request"),
    ("P0-07", "legacy_comparison", "test_p0_07_product_comparison_stability", "_write_request"),
    ("P0-08", "default", "test_p0_08_evidence_sufficiency", "_fixture_request"),
    ("P0-09", "case_initial", "test_p0_09_evidence_compiler", "_request"),
    ("P0-11", "report_export", "test_p0_11_public_safe_export", "_tool_request"),
    ("P0-12", "graft_assessment", "test_p0_12_graft_assessment", "_request"),
])
def test_real_fixture_request_plan_approval_execution(client, tmp_path, tool, mode, module, factory):
    # Only source fixture construction is reused; planner, eligibility, runner and receipts are real.
    source = importlib.import_module(module)
    root = tmp_path / "supplied"
    if tool != "P0-11":
        root.mkdir()
    request = getattr(source, factory)(root, source._payloads()) if tool == "P0-07" else getattr(source, factory)(root)
    if tool == "P0-07":
        request = request[1]
    sid, _ = context_upload(client, tmp_path)
    objects = upload_request(client, sid, request, mode)
    url = f"/api/sessions/{sid}"
    saved = client.post(url + "/analysis-inputs", json=choice(tool, mode, objects))
    assert saved.status_code == 200, saved.json()
    prepared = client.post(url + "/prepare-analysis", json={"tool_id": tool}).json()
    assert prepared["status"] == "awaiting_approval", prepared
    state = client.app.state.service.load(sid)
    assert prepared["plan"]["steps"][0]["status"] == "pending", state["_plan"]["steps"][0]["reason_codes"]
    planned = json.loads(state["_plan"]["steps"][0]["approved_request_json"])
    assert planned["assets"] == []
    assert planned["random_seed"] == 0
    assert prepared["plan"]["steps"][0]["status"] == "pending", state["_plan"]
    result = approve(client, sid, prepared["plan"])
    assert result["plan"]["status"] in {"completed", "partial"}, result
    state = client.app.state.service.load(sid)
    assert state["_tool_runs"][-1]["tool_id"] == tool
    assert state["_tool_runs"][-1]["state"] in {"succeeded", "partial"}
    assert state["_canonical_artifacts"]


def _register_source_receipt(service, state, request, suffix, tool_id="P0-02"):
    from bridge.toolkit.contracts import ArtifactManifest, ToolRequest, ToolRun

    refs = {item.role: item for item in request.object_inputs}
    source = json.loads(
        refs["process_method_input"].path.read_bytes()
    )["source_observations"]
    run_root = service.directory(state["id"]) / "runs" / ("p002-source-" + suffix)
    manifest_path = run_root / "artifact_manifest.json"
    evidence_path = run_root / "cell_state_evidence.parquet"
    write_file(manifest_path, Path(source["artifact_manifest_path"]).read_bytes())
    write_file(evidence_path, Path(source["evidence_path"]).read_bytes())
    artifacts = [
        ArtifactManifest(
            artifact_id=f"artifact:{source['producer_run_ref']}:manifest",
            kind="manifest",
            path=manifest_path,
            media_type="application/json",
            sha256=hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        ),
        ArtifactManifest(
            artifact_id=source["evidence_artifact_id"],
            kind="cell_state_evidence",
            path=evidence_path,
            media_type="application/vnd.apache.parquet",
            sha256=hashlib.sha256(evidence_path.read_bytes()).hexdigest(),
        ),
    ]
    outcome = ToolRun(
        run_id=source["producer_run_ref"],
        request=ToolRequest(
            request_id="p002-source-" + suffix,
            tool_id=tool_id,
            tool_version=source["producer_tool_version"],
            output_dir=run_root,
        ),
        implementation_state="implemented",
        execution_state="succeeded",
        tool_version=source["producer_tool_version"],
        environment_spec_id="environment:synthetic-web-binding-fixture",
        artifacts=artifacts,
        result={"score_state": "shadow", "domain_score": None},
    )
    receipt_bytes = outcome.model_dump_json().encode()
    receipt_file = "p002-source-" + suffix + ".json"
    write_file(service.directory(state["id"]) / "receipts" / receipt_file, receipt_bytes)
    receipt = {
        "file": receipt_file,
        "sha256": hashlib.sha256(receipt_bytes).hexdigest(),
        "tool_id": tool_id,
        "state": "succeeded",
        "plan_id": "fixture-plan-" + suffix,
        "declaration_start": None,
    }
    state["_tool_runs"].append(receipt)
    service.inputs.register_outputs(state, outcome, receipt)
    canonical = {
        record["artifact_id"]: identifier
        for identifier, record in state["_canonical_artifacts"].items()
        if record["receipt_file"] == receipt_file
    }
    return {
        "manifest": canonical[artifacts[0].artifact_id],
        "evidence": canonical[artifacts[1].artifact_id],
        "manifest_sha256": artifacts[0].sha256,
        "evidence_sha256": artifacts[1].sha256,
    }


def test_source_bound_p006_accepts_only_one_p002_canonical_receipt(
    client, tmp_path
):
    from test_p0_06_source_bound_observations import _source_bound_request

    source_root = tmp_path / "p006-source"
    source_root.mkdir()
    request = _source_bound_request(source_root)
    from bridge.toolkit.contracts import ExecutionState
    from bridge.toolkit.registry import ToolRegistry

    fixture_run = ToolRegistry.load_default().run(request)
    assert fixture_run.execution_state is ExecutionState.SUCCEEDED
    sid, asset_id = context_upload(client, tmp_path)
    url = f"/api/sessions/{sid}"
    service = client.app.state.service
    state = service.load(sid)
    first = _register_source_receipt(service, state, request, "first")
    second = _register_source_receipt(service, state, request, "second")
    wrong_producer = _register_source_receipt(
        service, state, request, "wrong-producer", tool_id="P0-05"
    )
    service.save(state)

    process_ref = next(
        item for item in request.object_inputs if item.role == "process_method_input"
    )
    original = json.loads(process_ref.path.read_bytes())
    source = original["source_observations"]
    original_source_metadata = {
        key: value
        for key, value in source.items()
        if key
        not in {
            "artifact_manifest_path",
            "artifact_manifest_sha256",
            "evidence_path",
            "evidence_sha256",
        }
    }
    source = {
        "artifact_manifest_sha256": None,
        "artifact_manifest_path": "artifact:" + first["manifest"],
        **original_source_metadata,
        "evidence_sha256": "",
        "evidence_path": "artifact:" + first["evidence"],
    }
    payload = {**original, "source_observations": source}

    def add(value, **metadata):
        return service.inputs.add_object(
            state,
            tool_id=metadata.get("tool_id", "P0-06"),
            mode_id=metadata.get("mode_id", "method_runtime_source_bound"),
            role=metadata.get("role", "process_method_input"),
            schema_ref=metadata.get(
                "schema_ref", "bridge://schemas/process-method-input/v0.2"
            ),
            object_version=metadata.get("object_version", "0.2.0"),
            data=json.dumps(value).encode(),
        )

    for metadata in [
        {"role": "process_method_spec"},
        {
            "mode_id": "method_runtime",
            "schema_ref": "bridge://schemas/process-method-input/v0.1",
            "object_version": "0.1.0",
        },
        {"mode_id": "legacy_aggregation"},
    ]:
        with pytest.raises(ValueError):
            add(payload, **metadata)

    for bad_locator in [
        original["source_observations"]["evidence_path"],
        "https://example.org/evidence.parquet",
        "upload:" + asset_id,
    ]:
        changed = json.loads(json.dumps(payload))
        changed["source_observations"]["evidence_path"] = bad_locator
        with pytest.raises(ValueError, match="opaque|artifact"):
            add(changed)

    for checksum_field in [
        "artifact_manifest_sha256",
        "evidence_sha256",
    ]:
        for checksum in ["0" * 64, "__missing__"]:
            changed = json.loads(json.dumps(payload))
            if checksum == "__missing__":
                changed["source_observations"].pop(checksum_field)
            else:
                changed["source_observations"][checksum_field] = checksum
            with pytest.raises(ValueError, match="checksum"):
                add(changed)
        for checksum in [[], {}]:
            changed = json.loads(json.dumps(payload))
            changed["source_observations"][checksum_field] = checksum
            before = set(service.load(sid)["_input_objects"])
            invalid = client.post(
                url + "/analysis-inputs/objects",
                params={
                    "tool_id": "P0-06",
                    "mode_id": "method_runtime_source_bound",
                    "role": "process_method_input",
                    "schema_ref": "bridge://schemas/process-method-input/v0.2",
                    "object_version": "0.2.0",
                },
                files={
                    "file": (
                        "process.json",
                        json.dumps(changed).encode(),
                    )
                },
            )
            assert invalid.status_code == 422, invalid.json()
            assert set(service.load(sid)["_input_objects"]) == before

    swapped = json.loads(json.dumps(payload))
    swapped["source_observations"]["evidence_path"] = (
        "artifact:" + first["manifest"]
    )
    swapped["source_observations"]["evidence_sha256"] = first["manifest_sha256"]
    with pytest.raises(ValueError, match="kind"):
        add(swapped)

    other = service.load(new_session(client)["id"])
    with pytest.raises(ValueError, match="artifact"):
        service.inputs.add_object(
            other,
            tool_id="P0-06",
            mode_id="method_runtime_source_bound",
            role="process_method_input",
            schema_ref="bridge://schemas/process-method-input/v0.2",
            object_version="0.2.0",
            data=json.dumps(payload).encode(),
        )

    mixed = json.loads(json.dumps(payload))
    mixed["source_observations"]["evidence_path"] = "artifact:" + second["evidence"]
    mixed["source_observations"]["evidence_sha256"] = second["evidence_sha256"]
    with pytest.raises(ValueError, match="receipt"):
        add(mixed)

    non_p002 = json.loads(json.dumps(payload))
    non_p002["source_observations"]["artifact_manifest_path"] = (
        "artifact:" + wrong_producer["manifest"]
    )
    non_p002["source_observations"]["artifact_manifest_sha256"] = wrong_producer[
        "manifest_sha256"
    ]
    non_p002["source_observations"]["evidence_path"] = (
        "artifact:" + wrong_producer["evidence"]
    )
    non_p002["source_observations"]["evidence_sha256"] = wrong_producer[
        "evidence_sha256"
    ]
    with pytest.raises(ValueError, match="producer"):
        add(non_p002)

    response = client.post(
        url + "/analysis-inputs/objects",
        params={
            "tool_id": "P0-06",
            "mode_id": "method_runtime_source_bound",
            "role": "process_method_input",
            "schema_ref": "bridge://schemas/process-method-input/v0.2",
            "object_version": "0.2.0",
        },
        files={"file": ("process.json", json.dumps(payload).encode())},
    )
    assert response.status_code == 200, response.json()
    state = service.load(sid)
    process_id = next(reversed(state["_input_objects"]))
    bound = service.inputs.verify(state, state["_input_objects"][process_id])
    assert {
        key: value
        for key, value in bound["source_observations"].items()
        if key
        not in {
            "artifact_manifest_path",
            "artifact_manifest_sha256",
            "evidence_path",
            "evidence_sha256",
        }
    } == original_source_metadata
    assert bound["source_observations"]["artifact_manifest_sha256"] == first[
        "manifest_sha256"
    ]
    assert (
        bound["source_observations"]["evidence_sha256"] == first["evidence_sha256"]
    )

    current = service.load(sid)
    record = current["_input_objects"][process_id]
    assert len(record["dependencies"]) == 2
    for dependency in record["dependencies"]:
        path = Path(dependency["path"])
        original_bytes = path.read_bytes()
        write_file(path, original_bytes + b" ")
        with pytest.raises(ValueError, match="integrity"):
            service.inputs.verify(current, record)
        write_file(path, original_bytes)
    receipt_path = (
        service.directory(sid)
        / "receipts"
        / record["dependencies"][0]["receipt_file"]
    )
    receipt_bytes = receipt_path.read_bytes()
    write_file(receipt_path, receipt_bytes + b" ")
    with pytest.raises(ValueError, match="integrity"):
        service.inputs.verify(current, record)
    write_file(receipt_path, receipt_bytes)


def test_explicit_no_graft_reapproval_and_mutation_rejects_stale_plan(client, tmp_path):
    sid, aid = context_upload(client, tmp_path)
    url = f"/api/sessions/{sid}"
    selection = choice("P0-12", "not_provided")
    client.post(url + "/analysis-inputs", json=selection)
    first = client.post(url + "/prepare-analysis", json={"tool_id": "P0-12"}).json()["plan"]
    assert first and "not_provided" in first["summary"]
    client.post(url + "/analysis-inputs", json=selection)
    assert client.post(url + "/approve", json={"plan_id": first["id"], "plan_digest": first["digest"]}).status_code == 409
    second = client.post(url + "/prepare-analysis", json={"tool_id": "P0-12"}).json()["plan"]
    assert second["id"] != first["id"]
    assert approve(client, sid, second)["plan"]["status"] == "completed"


def test_canonical_output_integrity_session_and_display_separation(client, tmp_path):
    sid, _ = context_upload(client, tmp_path)
    url = f"/api/sessions/{sid}"
    client.post(url + "/analysis-inputs", json=choice("P0-12", "not_provided"))
    plan = client.post(url + "/prepare-analysis", json={"tool_id": "P0-12"}).json()["plan"]
    assert approve(client, sid, plan)["plan"]["status"] == "completed"
    service = client.app.state.service
    state = service.load(sid)
    # All artifacts, even non-reusable JSON, have canonical same-session audit bindings.
    aid, canonical = next(iter(state["_canonical_artifacts"].items()))
    service.inputs.receipt_artifacts(state, canonical)
    other = service.load(new_session(client)["id"])
    with pytest.raises(ValueError, match="receipt"):
        service.inputs.receipt_artifacts(other, canonical)
    path = Path(canonical["path"])
    write_file(path, path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="integrity"):
        service.inputs.receipt_artifacts(state, canonical)


def test_nested_files_bind_only_opaque_session_ids(client, tmp_path):
    sid, aid = context_upload(client, tmp_path)
    service = client.app.state.service
    state = service.load(sid)
    digest = state["_uploads"][aid]["sha256"]
    payload, deps = service.inputs.bind_nested(state, {"path": "upload:" + aid, "sha256": digest})
    assert payload["path"].endswith(aid + ".h5ad") and deps[0]["sha256"] == digest
    for locator in ["/etc/passwd", "../file", "https://example.org/data.h5ad", "upload:" + "0"*32, "artifact:" + "0"*32]:
        with pytest.raises(ValueError):
            service.inputs.bind_nested(state, {"path": locator, "sha256": digest})
    with pytest.raises(ValueError, match="checksum"):
        service.inputs.bind_nested(state, {"path": "upload:" + aid, "sha256": "0"*64})
    assert service.inputs.bind_nested(state, {"source_refs": ["https://doi.org/10.test/article"]})[0]["source_refs"]
    with pytest.raises(ValueError, match="unsupported_file_binding:matrix_file"):
        service.inputs.bind_nested(state, {"matrix_file": "relative.npy"})




def test_p009_query_input_discovery_and_schema_enforce_read_only_roles(client, tmp_path):
    sid = new_session(client)["id"]
    service = client.app.state.service
    state = service.load(sid)
    catalog = client.get(f"/api/sessions/{sid}/analysis-inputs").json()
    tool = next(item for item in catalog["tools"] if item["tool_id"] == "P0-09")
    modes = {mode["mode_id"]: mode for mode in tool["input_contract"]["object_input_modes"]}
    for kind in ("case", "comparison"):
        mode = f"{kind}_query"
        assert [role["role"] for role in modes[mode]["roles"]] == ["evidence_graph_manifest", "evidence_graph_query"]
        with pytest.raises(ValueError, match="canonical_graph"):
            service.inputs.add_object(
                state, tool_id="P0-09", mode_id=mode, role="evidence_graph_manifest",
                schema_ref=f"bridge://schemas/{kind}-evidence-graph-manifest/v0.1",
                object_version="1", data=b"{}",
            )
        with pytest.raises(ValueError):
            service.inputs.role("P0-09", mode, "compilation_bundle",
                                "bridge://schemas/evidence-compilation-bundle/v0.1", "0.1.0")
    params = dict(tool_id="P0-09", mode_id="case_query", role="evidence_graph_query",
                  schema_ref="bridge://schemas/evidence-graph-query/v0.1", object_version="0.1.0")
    payload = dict(object_version="0.1.0", query_name="get_claim_evidence",
                   claim_id="claim:target-identity", evidence_tiers=["formal", "shadow", "exploratory"])
    url = f"/api/sessions/{sid}/analysis-inputs/objects"
    response = client.post(url, params=params, files={"file": ("query.json", json.dumps(payload).encode(), "application/json")})
    assert response.status_code == 200, response.json()
    invalid = client.post(url, params=params, files={"file": ("query.json", json.dumps({**payload, "limit": "1"}).encode(), "application/json")})
    assert invalid.status_code == 422
    assert str(tmp_path) not in json.dumps(response.json())


def test_graph_upload_and_wrong_role_schema_version_rejected(client, tmp_path):
    sid, _ = context_upload(client, tmp_path)
    service = client.app.state.service
    state = service.load(sid)
    with pytest.raises(ValueError, match="canonical_graph"):
        service.inputs.add_object(state, tool_id="P0-10", mode_id="default", role="evidence_graph_manifest",
            schema_ref="bridge://schemas/case-evidence-graph-manifest/v0.1", object_version="1", data=b"{}")
    for role, schema, version in [
        ("invented", "bridge://schemas/graft-case/v0.1", "0.1.0"),
        ("graft_case", "bridge://schemas/product-case/v0.1", "0.1.0"),
        ("graft_case", "bridge://schemas/graft-case/v0.1", "9"),
    ]:
        with pytest.raises(ValueError):
            service.inputs.role("P0-12", "graft_assessment", role, schema, version)


def test_object_mutation_before_execute_is_rejected(client, tmp_path):
    from test_p0_12_graft_assessment import _request
    root = tmp_path / "supplied"
    root.mkdir()
    sid, _ = context_upload(client, tmp_path)
    objects = upload_request(client, sid, _request(root), "graft_assessment")
    url = f"/api/sessions/{sid}"
    client.post(url + "/analysis-inputs", json=choice("P0-12", "graft_assessment", objects))
    plan = client.post(url + "/prepare-analysis", json={"tool_id": "P0-12"}).json()["plan"]
    state = client.app.state.service.load(sid)
    path = Path(state["_input_objects"][objects[0]["input_id"]]["path"])
    write_file(path, path.read_bytes() + b" ")
    assert approve(client, sid, plan)["status"] == "failed"
    assert not client.app.state.service.load(sid)["_tool_runs"]


def test_real_expression_graft_opaque_h5ad_binding(client, tmp_path):
    from test_p0_12_expression_analysis import _request
    request, path = _request(tmp_path / "graft")
    sid, _ = context_upload(client, tmp_path)
    url = f"/api/sessions/{sid}"
    uploaded = client.post(url + "/uploads", files={"file": ("graft.h5ad", path.read_bytes())}).json()["uploads"][-1]["id"]
    objects = []
    for ref in request.object_inputs:
        payload = json.loads(ref.path.read_bytes())
        if ref.role == "graft_expression_asset":
            payload["path"] = "upload:" + uploaded
        response = client.post(url + "/analysis-inputs/objects", params={
            "tool_id": "P0-12", "mode_id": "expression_analysis", "role": ref.role,
            "schema_ref": ref.schema_ref, "object_version": ref.object_version,
        }, files={"file": ("object.json", json.dumps(payload).encode())})
        assert response.status_code == 200, (ref.role, response.json())
        state = client.app.state.service.load(sid)
        objects.append({"role": ref.role, "input_id": next(reversed(state["_input_objects"]))})
    assert client.post(url + "/analysis-inputs", json=choice("P0-12", "expression_analysis", objects)).status_code == 200
    proposal = client.post(url + "/prepare-analysis", json={"tool_id": "P0-12"}).json()
    assert proposal["status"] == "awaiting_approval", proposal
    result = approve(client, sid, proposal["plan"])
    assert result["plan"]["status"] == "completed", result


@pytest.mark.parametrize("tool,module", [
    ("P0-03", "test_p0_03_target_regional"),
    ("P0-04", "test_p0_04_developmental_compatibility"),
])
def test_configured_reference_objects_real_http_execution(client, tmp_path, monkeypatch, tool, module):
    from dataclasses import replace
    from bridge.tool_packages.p0_02_cell_state.measurement_specs import load_measurement_spec
    from bridge.tool_packages.p0_02_cell_state.reference import DENIED_SOURCE_FAMILIES
    source = importlib.import_module(module)
    spec = load_measurement_spec("CELLSTATE-scRNA-shadow-v0.1")
    values = source._base_payloads()
    values["measurement_spec"]["reference_refs"] = [spec.reference_refs[0] + "@1.0.0"]
    values["reference_manifest"].update(
        snapshot_id=spec.reference_refs[0], marker_program_sha256=hashlib.sha256(b"{}").hexdigest(),
        measurement_spec_ids=[*values["reference_manifest"]["measurement_spec_ids"], spec.measurement_spec_id],
        prohibited_source_families=sorted(DENIED_SOURCE_FAMILIES))
    supplied = tmp_path / "supplied"
    supplied.mkdir()
    request = source._request(supplied, values)
    reference_root = tmp_path / "references"
    snapshot = reference_root / spec.reference_refs[0]
    snapshot.mkdir(parents=True, mode=0o700)
    for ref in request.object_inputs:
        if ref.role in {"reference_manifest", "annotation_vocabulary"}:
            write_file(snapshot / (ref.role + ".json"), ref.path.read_bytes())
    write_file(snapshot / "marker_programs.json", b"{}")
    monkeypatch.setenv("BRIDGE_REFERENCE_ROOT", str(reference_root))
    monkeypatch.setenv("BRIDGE_ALLOW_CANDIDATE_REFERENCES", "1")
    sid, _ = context_upload(client, tmp_path)
    service = client.app.state.service
    service.settings = replace(service.settings, cell_state_measurement_spec_ref=spec.measurement_spec_id)
    url = f"/api/sessions/{sid}"
    catalog = client.get(url + "/analysis-inputs").json()
    resources = {item["label"]: item["id"] for item in catalog["objects"] if item["source"] == "system_resource"}
    assert set(resources) == {"reference_manifest", "annotation_vocabulary"}, catalog
    local_request = request.model_copy(update={"object_inputs": [
        ref for ref in request.object_inputs if ref.role not in resources]})
    objects = upload_request(client, sid, local_request, "default")
    objects.extend({"role": role, "input_id": identifier} for role, identifier in resources.items())
    response = client.post(url + "/analysis-inputs", json=choice(tool, "default", objects))
    assert response.status_code == 200, response.json()
    prepared = client.post(url + "/prepare-analysis", json={"tool_id": tool}).json()
    assert prepared["status"] == "awaiting_approval", prepared
    assert prepared["plan"]["steps"][0]["status"] == "pending", service.load(sid)["_plan"]
    result = approve(client, sid, prepared["plan"])
    assert result["plan"]["status"] == "completed", result
    # Existing plan/input binding rejects a changed sibling, even if the selected
    # scientific object's own bytes did not change.
    record = service.load(sid)["_input_objects"][resources["reference_manifest"]]
    write_file(snapshot / "marker_programs.json", b'{"changed":true}')
    with pytest.raises(ValueError):
        service.inputs.verify(service.load(sid), record)


def test_canonical_graph_to_claim_verifier_and_cross_session_fence(client, tmp_path):
    from test_p0_09_evidence_compiler import _request
    from test_p0_10_claim_verifier import _report_payload, report_content_hash
    supplied = tmp_path / "supplied"
    supplied.mkdir()
    sid, _ = context_upload(client, tmp_path)
    url = f"/api/sessions/{sid}"
    objects = upload_request(client, sid, _request(supplied), "case_initial")
    client.post(url + "/analysis-inputs", json=choice("P0-09", "case_initial", objects))
    first = client.post(url + "/prepare-analysis", json={"tool_id": "P0-09"}).json()["plan"]
    assert approve(client, sid, first)["plan"]["status"] == "completed"
    catalog = client.get(url + "/analysis-inputs").json()
    graph = next(item for item in catalog["objects"] if item["schema_ref"] == "bridge://schemas/case-evidence-graph-manifest/v0.1")
    service = client.app.state.service
    state = service.load(sid)
    record = state["_input_objects"][graph["id"]]
    assert record["source"] == "tool_output" and "/runs/" in record["path"]
    manifest = service.inputs.verify(state, record)
    evidence = json.loads((Path(record["path"]).parent / manifest["evidence_records"]["filename"]).read_bytes())
    # A supplied synthetic draft deliberately retains unsupported claims so the
    # actual verifier, not the Web layer, owns the claim rejection.
    report = _report_payload()
    report["evidence_record_set_ref"] = evidence["record_set_id"] + "@" + evidence["record_set_version"]
    report["content_hash"] = report_content_hash(report)
    response = client.post(url + "/analysis-inputs/objects", params={
        "tool_id": "P0-10", "mode_id": "default", "role": "report_draft",
        "schema_ref": "bridge://schemas/report-draft/v0.1", "object_version": "0.1.0",
    }, files={"file": ("report.json", json.dumps(report).encode())})
    assert response.status_code == 200, response.json()
    report_id = next(reversed(service.load(sid)["_input_objects"]))
    selected = [{"role": "report_draft", "input_id": report_id},
                {"role": "evidence_graph_manifest", "input_id": graph["id"]}]
    for role in ["claim_policy_spec", "statement_registry"]:
        selected.append({"role": role, "input_id": next(item["id"] for item in catalog["objects"] if item["label"] == role)})
    assert client.post(url + "/analysis-inputs", json=choice("P0-10", "default", selected)).status_code == 200
    proposal = client.post(url + "/prepare-analysis", json={"tool_id": "P0-10"}).json()
    assert proposal["plan"]["steps"][0]["status"] == "pending", service.load(sid)["_plan"]
    assert approve(client, sid, proposal["plan"])["plan"]["status"] == "completed"
    other = new_session(client)["id"]
    assert client.post(f"/api/sessions/{other}/analysis-inputs", json=choice("P0-10", "default", selected)).status_code == 422
    sibling = Path(record["path"]).parent / manifest["evidence_records"]["filename"]
    write_file(sibling, sibling.read_bytes() + b" ")
    with pytest.raises(ValueError, match="integrity"):
        service.inputs.verify(service.load(sid), record)


def test_size_and_registration_limits_and_symlink_binding(client, tmp_path):
    from test_p0_12_graft_assessment import _objects
    from bridge.web.inputs import OBJECT_LIMIT
    with pytest.raises(ValueError, match="size"):
        strict_json(b" " * (OBJECT_LIMIT + 1))
    sid, aid = context_upload(client, tmp_path)
    service = client.app.state.service
    state = service.load(sid)
    service.inputs.package_options(state)
    record = next(iter(state["_input_objects"].values()))
    state["_input_objects"].update({f"{index:032x}": record for index in range(128)})
    with pytest.raises(ValueError, match="count"):
        service.inputs.add_object(state, tool_id="P0-12", mode_id="graft_assessment", role="graft_case",
            schema_ref="bridge://schemas/graft-case/v0.1", object_version="0.1.0", data=json.dumps(_objects()[0]).encode())
    upload = service.directory(sid) / "uploads" / (aid + ".h5ad")
    original = upload.with_suffix(".original")
    upload.rename(original)
    upload.symlink_to(original)
    with pytest.raises(ValueError, match="symlink"):
        service.inputs.bind_nested(state, {"path": "upload:" + aid, "sha256": state["_uploads"][aid]["sha256"]})


@pytest.mark.parametrize("version", ["0.1.0", "0.2.0"])
def test_schema_and_declared_profile_versions_are_coupled_at_upload(client, tmp_path, version):
    from test_p0_09_evidence_compiler import _profile, _v2_profile
    sid, _ = context_upload(client, tmp_path)
    value = _profile()
    if version == "0.2.0":
        value = _v2_profile(value)
    params = {"tool_id": "P0-09", "mode_id": "case_initial", "role": "evidence_sufficiency_profile",
              "schema_ref": "bridge://schemas/evidence-sufficiency-profile/v" + version.rsplit(".", 1)[0],
              "object_version": version}
    url = f"/api/sessions/{sid}/analysis-inputs/objects"
    assert client.post(url, params=params, files={"file": ("profile.json", json.dumps(value).encode())}).status_code == 200
    wrong = "0.2.0" if version == "0.1.0" else "0.1.0"
    assert client.post(url, params={**params, "object_version": wrong},
        files={"file": ("profile.json", json.dumps(value).encode())}).status_code == 422
    service = client.app.state.service
    with pytest.raises(ValueError, match="input_version_mismatch"):
        service.inputs.validate_object(value, params["schema_ref"], wrong)


def test_version_field_free_canonical_qc_output_uses_role_version(client, tmp_path):
    sid, aid = context_upload(client, tmp_path)
    url = f"/api/sessions/{sid}"
    client.post(url + "/analysis-inputs", json=choice("P0-01", None, assets=[aid]))
    plan = client.post(url + "/prepare-analysis", json={"tool_id": "P0-01"}).json()["plan"]
    assert approve(client, sid, plan)["plan"]["status"] == "completed"
    catalog = client.get(url + "/analysis-inputs").json()
    qc = next(item for item in catalog["objects"] if item["source"] == "tool_output" and
              item["schema_ref"] == "bridge://schemas/qc-readiness-profile/v0.2")
    assert qc["object_version"] == "0.2.0"
    service = client.app.state.service
    state = service.load(sid)
    value = service.inputs.verify(state, state["_input_objects"][qc["id"]])
    assert "object_version" not in value and "version" not in value
    assert service.inputs.object_version(value, qc["schema_ref"]) == "0.2.0"


def test_real_canonical_sufficiency_to_compiler_v2_and_append(client, tmp_path):
    import test_p0_08_evidence_sufficiency as sufficiency
    import test_p0_09_evidence_compiler as compiler
    supplied = tmp_path / "supplied"
    supplied.mkdir()
    family = "evidence-family:transcriptomic"
    request = sufficiency._fixture_request(supplied, validation=sufficiency._validation(evidence_family_id=family),
        prior=sufficiency._prior(evidence_family_id=family), sensitivity=sufficiency._sensitivity(evidence_family_id=family))
    sid, _ = context_upload(client, tmp_path)
    url = f"/api/sessions/{sid}"
    service = client.app.state.service
    catalog = client.get(url + "/analysis-inputs").json()
    gate = next(item for item in catalog["objects"] if item["label"] == "gate_rule_spec")
    objects = upload_request(client, sid, request.model_copy(update={"object_inputs": [
        ref for ref in request.object_inputs if ref.role != "gate_rule_spec"]}), "default")
    objects.append({"role": "gate_rule_spec", "input_id": gate["id"]})
    assert client.post(url + "/analysis-inputs", json=choice("P0-08", "default", objects)).status_code == 200
    plan = client.post(url + "/prepare-analysis", json={"tool_id": "P0-08"}).json()["plan"]
    assert approve(client, sid, plan)["plan"]["status"] == "completed"
    catalog = client.get(url + "/analysis-inputs").json()
    output8 = next(item for item in catalog["objects"] if item["source"] == "tool_output" and
        item["schema_ref"] == "bridge://schemas/evidence-sufficiency-run-result/v0.2")
    assert output8["object_version"] == "0.2.0"
    assert any(item["source"] == "tool_output" and item["schema_ref"] ==
        "bridge://schemas/evidence-sufficiency-profile/v0.2" and item["object_version"] == "0.2.0"
        for item in catalog["objects"])
    state = service.load(sid)
    record8 = state["_input_objects"][output8["id"]]
    result8 = service.inputs.verify(state, record8)
    profile = result8["profiles"][0]
    candidate = compiler._candidate(family_id=family, references=profile["snapshot_refs"])
    candidate.update(product_case_ref=profile["product_case_ref"],
        measurement_result_ref=profile["measurement_result_refs"][0], measurement_spec_ref=profile["measurement_spec_ref"],
        sufficiency_profile_input_id=output8["id"])
    bundle = compiler._bundle(candidates=[candidate])
    bundle["product_case_ref"] = profile["product_case_ref"]
    for index, reference in [(0, profile["product_case_ref"]), (2, profile["measurement_result_refs"][0]),
                             (3, profile["measurement_spec_ref"])]:
        bundle["object_catalog"][index].update(reference)
    bundle["object_catalog"][5]["object_id"] = profile["snapshot_refs"][0].split("@")[0]
    bundle["object_catalog"] = bundle["object_catalog"][:6]
    families = compiler._family_registry()
    families["families"][0]["evidence_family_id"] = family

    def prepare_compiler(mode, current_bundle, base_choices=(), manifest_path=None):
        source = compiler._request(supplied, bundle=current_bundle, family_registry=families,
            request_id=mode, sufficiency_runs=[(output8["id"], result8)], base_manifest_path=manifest_path)
        supplied_only = source.model_copy(update={"object_inputs": [
            ref for ref in source.object_inputs if ref.role not in
            {"evidence_sufficiency_run_result", "base_graph_manifest", "base_evidence_record_set", "base_evidence_requirement_set"}]})
        selected = upload_request(client, sid, supplied_only, mode)
        selected.extend([{"role": "evidence_sufficiency_run_result", "input_id": output8["id"]}, *base_choices])
        assert client.post(url + "/analysis-inputs", json=choice("P0-09", mode, selected)).status_code == 200
        proposed = client.post(url + "/prepare-analysis", json={"tool_id": "P0-09"}).json()
        assert proposed["plan"]["steps"][0]["status"] == "pending", service.load(sid)["_plan"]["steps"][0]["reason_codes"]
        planned = json.loads(service.load(sid)["_plan"]["steps"][0]["approved_request_json"])
        canonical8 = next(ref for ref in planned["object_inputs"] if ref["role"] == "evidence_sufficiency_run_result")
        assert canonical8["path"] == record8["path"] and canonical8["sha256"] == record8["sha256"]
        return proposed["plan"]

    assert approve(client, sid, prepare_compiler("case_initial_v2", bundle))["plan"]["status"] == "completed"
    catalog = client.get(url + "/analysis-inputs").json()
    schemas = {"base_graph_manifest": "case-evidence-graph-manifest",
               "base_evidence_record_set": "evidence-record-set",
               "base_evidence_requirement_set": "evidence-requirement-set"}
    base = {role: next(item for item in catalog["objects"] if item["source"] == "tool_output" and
            item["schema_ref"] == "bridge://schemas/" + name + "/v0.1") for role, name in schemas.items()}
    assert base["base_graph_manifest"]["object_version"] == "1"
    assert base["base_evidence_record_set"]["object_version"] == "0.1.0"
    assert base["base_evidence_requirement_set"]["object_version"] == "0.1.0"
    state = service.load(sid)
    records = {role: state["_input_objects"][item["id"]] for role, item in base.items()}
    graph = service.inputs.verify(state, records["base_graph_manifest"])
    evidence = service.inputs.verify(state, records["base_evidence_record_set"])
    requirements = service.inputs.verify(state, records["base_evidence_requirement_set"])
    append = json.loads(json.dumps(bundle))
    append.update(prior_evidence_records=evidence["records"], prior_requirements=requirements["requirements"],
        base_graph_ref={"graph_id": graph["graph_id"], "graph_version": graph["graph_version"],
            "manifest_sha256": records["base_graph_manifest"]["sha256"],
            "manifest_input_id": base["base_graph_manifest"]["id"],
            "record_set_input_id": base["base_evidence_record_set"]["id"],
            "requirement_set_input_id": base["base_evidence_requirement_set"]["id"]})
    proposal = prepare_compiler("case_append_v2", append,
        [{"role": role, "input_id": item["id"]} for role, item in base.items()],
        Path(records["base_graph_manifest"]["path"]))
    assert approve(client, sid, proposal)["plan"]["status"] == "completed"
    catalog = client.get(url + "/analysis-inputs").json()
    assert any(item["source"] == "tool_output" and item["schema_ref"] ==
        "bridge://schemas/case-evidence-graph-manifest/v0.1" and item["object_version"] == "2"
        for item in catalog["objects"])
    # Replanning still verifies the original complete producer bundle.
    sibling = Path(records["base_evidence_requirement_set"]["path"])
    write_file(sibling, sibling.read_bytes() + b" ")
    with pytest.raises(ValueError, match="integrity"):
        service.inputs.verify(service.load(sid), records["base_graph_manifest"])
