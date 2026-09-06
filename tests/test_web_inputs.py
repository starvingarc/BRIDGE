from __future__ import annotations

import hashlib
import importlib
import json
from pathlib import Path

import pytest

from bridge.web.inputs import Inputs, Selection, strict_json
from bridge.web.app import write_file
from test_web_service import client, h5ad, new_session, settle


def context_upload(client, tmp_path):
    sid = new_session(client)["id"]
    url = f"/api/sessions/{sid}"
    response = client.post(url + "/uploads", files={"file": ("synthetic.h5ad", h5ad(tmp_path, layer=True))})
    aid = response.json()["uploads"][0]["id"]
    assert client.post(url + "/analysis-inputs/assets", json={
        "upload_id": aid, "assay": "scRNA-seq", "matrix_location": "layers/counts",
        "matrix_semantics": "raw_counts", "input_level": "count_ready", "metadata": {},
    }).status_code == 200
    return sid, aid


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
