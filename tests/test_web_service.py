from __future__ import annotations

import json
import time

import pytest
httpx = pytest.importorskip("httpx")
pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from bridge.web.app import Settings, create_app
from bridge.web.provider import parse_action




def test_prepare_analysis_accepts_only_connected_tool_actions():
    for tool_id in ("P0-02", "P0-12"):
        assert parse_action({"content": json.dumps({"action": "prepare_analysis", "tool_id": tool_id})}).tool_id == tool_id
    for tool_id in ("P0-05", "P0-01"):
        with pytest.raises(ValueError):
            parse_action({"content": json.dumps({"action": "prepare_analysis", "tool_id": tool_id})})


def test_private_source_input_is_bound_to_registered_upload(client, tmp_path):
    sid = new_session(client)["id"]
    value = client.post(f"/api/sessions/{sid}/uploads",
        files={"file": ("synthetic.h5ad", h5ad(tmp_path, layer=True))}).json()
    aid = value["uploads"][0]["id"]
    url = f"/api/sessions/{sid}/inputs"
    saved = client.post(url, json={"upload_id": aid, "source_family_id": "source-family:unit-test"})
    assert saved.status_code == 200
    assert saved.json()["uploads"][0]["source_family_id"] == "source-family:unit-test"
    assert client.post(url, json={"upload_id": "0"*32, "source_family_id": "test"}).status_code == 404
    for bad in (" ", "/private/file", "a"*161):
        assert client.post(url, json={"upload_id": aid, "source_family_id": bad}).status_code == 422


@pytest.mark.parametrize("declaration", ["没有移植数据，请记录未提供 graft 数据", "No graft data, please record not provided"])
def test_real_qc_then_no_graft_has_new_approval_and_canonical_receipts(client, tmp_path, monkeypatch, declaration):
    sid = new_session(client)["id"]
    url = f"/api/sessions/{sid}"
    client.post(url + "/uploads", files={"file": ("synthetic.h5ad", h5ad(tmp_path, layer=True))})
    client.post(url + "/messages", json={"text": "scRNA-seq，使用 counts 层进行 QC"})
    first = settle(client, sid)["plan"]
    client.post(url + "/approve", json={"plan_id": first["id"], "plan_digest": first["digest"]})
    done = settle(client, sid)
    service = client.app.state.service
    assert service.load(sid)["_tool_runs"]
    monkeypatch.setattr("bridge.web.app.converse", lambda *args: parse_action({"content": '{"action":"prepare_analysis","tool_id":"P0-12"}'}))
    client.post(url + "/messages", json={"text": declaration})
    proposed = settle(client, sid)
    assert proposed["status"] == "awaiting_approval", proposed
    assert proposed["plan_history"][0]["id"] == first["id"]
    assert proposed["artifacts"] == done["artifacts"]
    state = service.load(sid)
    request = json.loads(state["_plan"]["steps"][0]["approved_request_json"])
    assert request["assets"] == [] and request["object_inputs"] == []
    assert client.post(url + "/approve", json={"plan_id": first["id"], "plan_digest": first["digest"]}).status_code == 409
    second = proposed["plan"]
    client.post(url + "/approve", json={"plan_id": second["id"], "plan_digest": second["digest"]})
    result = settle(client, sid)
    assert result["plan"]["status"] == "completed", result
    assert len(service.load(sid)["_tool_runs"]) == 2


@pytest.mark.parametrize("retraction", [
    "No graft data. This is not scRNA-seq.",
    "没有移植数据。这个不是 scRNA-seq。",
    "No graft data. X is not raw counts.",
])
def test_mixed_no_graft_message_fences_qc_before_neutral_cell_state_request(
        client, tmp_path, monkeypatch, retraction):
    sid = new_session(client)["id"]
    url = f"/api/sessions/{sid}"
    uploaded = client.post(url + "/uploads", files={
        "file": ("synthetic.h5ad", h5ad(tmp_path, layer=True)),
    }).json()
    aid = uploaded["uploads"][0]["id"]
    client.post(url + "/messages", json={
        "text": "scRNA-seq，使用 counts 层进行 QC",
    })
    first = settle(client, sid)["plan"]
    client.post(url + "/approve", json={
        "plan_id": first["id"], "plan_digest": first["digest"],
    })
    assert settle(client, sid)["plan"]["status"] == "completed"
    client.post(url + "/inputs", json={
        "upload_id": aid, "source_family_id": "source-family:unit-test",
    })
    monkeypatch.setattr(client.app.state.service, "cell_state_config_reasons", lambda: [])
    monkeypatch.setattr("bridge.web.app.converse", lambda *args: parse_action({
        "content": '{"action":"prepare_analysis","tool_id":"P0-02"}',
    }))

    client.post(url + "/messages", json={"text": retraction})
    assert settle(client, sid)["error"] == "qc_declaration_retracted"
    client.post(url + "/messages", json={"text": "Continue cell-state analysis."})
    value = settle(client, sid)
    assert value["plan"]["status"] == "completed"
    assert value["error"] == "qc_declaration_retracted"


def test_no_graft_cannot_be_inferred_by_provider(client, tmp_path, monkeypatch):
    sid = new_session(client)["id"]
    url = f"/api/sessions/{sid}"
    client.post(url + "/uploads", files={"file": ("synthetic.h5ad", h5ad(tmp_path))})
    monkeypatch.setattr("bridge.web.app.converse", lambda *args: parse_action({"content": '{"action":"prepare_analysis","tool_id":"P0-12"}'}))
    client.post(url + "/messages", json={"text": "What is graft assessment?"})
    value = settle(client, sid)
    assert value["plan"] is None
    assert value["error"] == "no_graft_declaration_required"




def test_real_qc_cell_state_stage_binds_canonical_data_and_new_approval(client, tmp_path, monkeypatch):
    from dataclasses import replace
    from test_cell_state import _build_snapshot, _write_query
    from bridge.tool_packages.p0_02_cell_state.qc import validate_upstream_qc_bundle
    from bridge.toolkit.contracts import InputAsset
    import hashlib
    import os

    service = client.app.state.service
    sid = new_session(client)["id"]
    url = f"/api/sessions/{sid}"
    data = _write_query(tmp_path / "query.h5ad").read_bytes()
    uploaded = client.post(url + "/uploads", files={"file": ("synthetic.h5ad", data)}).json()
    aid = uploaded["uploads"][0]["id"]
    client.post(url + "/messages", json={"text": "scRNA-seq，X 是原始计数，进行 QC"})
    first = settle(client, sid)["plan"]
    client.post(url + "/approve", json={"plan_id": first["id"], "plan_digest": first["digest"]})
    assert settle(client, sid)["plan"]["status"] == "completed"
    captured = []
    def action(settings, messages, context):
        captured.append(context)
        return parse_action({"content": '{"action":"prepare_analysis","tool_id":"P0-02"}'})
    monkeypatch.setattr("bridge.web.app.converse", action)
    def propose():
        client.post(url + "/messages", json={"text": "继续细胞状态分析"})
        return settle(client, sid)
    assert propose()["error"] == "measurement_spec_not_configured"
    service.settings = replace(service.settings, cell_state_measurement_spec_ref="CELLSTATE-scRNA-shadow-v0.1")
    monkeypatch.delenv("BRIDGE_REFERENCE_ROOT", raising=False)
    assert propose()["error"] == "reference_root_not_configured"
    _build_snapshot(tmp_path, monkeypatch)
    assert propose()["error"] == "source_family_id_required"
    client.post(url + "/inputs", json={"upload_id": aid, "source_family_id": "PRIVATE-UNIT-TEST-SOURCE"})
    proposed = propose()
    assert proposed["status"] == "awaiting_approval", proposed
    assert proposed["plan"]["steps"][0]["status"] == "pending", proposed
    assert "PRIVATE-UNIT-TEST-SOURCE" not in json.dumps(captured)
    state = service.load(sid)
    request = json.loads(state["_plan"]["steps"][0]["approved_request_json"])
    asset = request["assets"][0]
    assert asset["checksum"] == hashlib.sha256(data).hexdigest()
    assert asset["input_level"] == "count_ready"
    assert asset["matrix_location"] == "X" and asset["matrix_semantics"] == "raw_counts"
    assert asset["metadata"]["parent_asset_sha256"] == asset["checksum"]
    assert ".display-redacted" not in json.dumps(request)
    monkeypatch.setenv("BRIDGE_QC_PROFILE_CATALOG", "original-catalog-sentinel")
    with service.qc_catalog():
        upstream = validate_upstream_qc_bundle(InputAsset.model_validate(asset))
        assert upstream.profile.profile_id == asset["metadata"]["qc_profile_ref"]
        assert upstream.profile_v2.selected_data_view.view_id == asset["metadata"]["data_view_id"]
    assert os.environ["BRIDGE_QC_PROFILE_CATALOG"] == "original-catalog-sentinel"
    with pytest.raises(RuntimeError), service.qc_catalog():
        raise RuntimeError("intentional")
    assert os.environ["BRIDGE_QC_PROFILE_CATALOG"] == "original-catalog-sentinel"
    # Fact edits invalidate only mutable proposals, and historical approvals survive.
    second = proposed["plan"]
    edited = client.post(url + "/inputs", json={"upload_id": aid, "source_family_id": "PRIVATE-UNIT-TEST-SOURCE-2"}).json()
    assert edited["plan"] is None and edited["plan_history"][0]["id"] == first["id"]
    assert client.post(url + "/approve", json={"plan_id": second["id"], "plan_digest": second["digest"]}).status_code == 409
    third = propose()["plan"]
    assert third["digest"] != second["digest"]
    client.post(url + "/approve", json={"plan_id": third["id"], "plan_digest": third["digest"]})
    done = settle(client, sid)
    assert done["plan"]["status"] == "completed", done
    assert any(item["tool_id"] == "P0-02" for item in done["artifacts"])
    assert os.environ["BRIDGE_QC_PROFILE_CATALOG"] == "original-catalog-sentinel"
    # Declared assay retractions block reuse without rewriting historical evidence.
    client.post(url + "/messages", json={"text": "This is not scRNA-seq"})
    retracted = settle(client, sid)
    assert retracted["error"] == "qc_declaration_retracted"
    assert retracted["plan"]["status"] == "completed"
    restored_state = service.load(sid)
    restored_state["_uploads"][aid]["declaration_start"] = state["_uploads"][aid]["declaration_start"]
    service.save(restored_state)
    # Downstream construction must not fall back to display copies after deletion.
    upstream.profile_path.unlink()
    assert propose()["error"] == "qc_artifacts_missing"

    capability = next(item for item in client.get(url).json()["capabilities"] if item["tool_id"] == "P0-02")
    assert capability["state"] == "needs_input"
    assert "qc_artifacts_missing" in capability["reason_codes"]



def test_provider_context_reports_ready_stage_and_bounded_tool_history_without_private_values(
        client, tmp_path, monkeypatch):
    sid = new_session(client)["id"]
    url = f"/api/sessions/{sid}"
    uploaded = client.post(url + "/uploads", files={
        "file": ("private-source-name.h5ad", h5ad(tmp_path, layer=True)),
    }).json()
    aid = uploaded["uploads"][0]["id"]
    client.post(url + "/messages", json={
        "text": "scRNA-seq，使用 counts 层进行 QC",
    })
    plan = settle(client, sid)["plan"]
    client.post(url + "/approve", json={
        "plan_id": plan["id"], "plan_digest": plan["digest"],
    })
    assert settle(client, sid)["plan"]["status"] == "completed"
    client.post(url + "/inputs", json={
        "upload_id": aid, "source_family_id": "PRIVATE-ACTUAL-SOURCE-ID",
    })
    service = client.app.state.service
    monkeypatch.setattr(service, "cell_state_config_reasons", lambda: [])
    captured = []
    def action(settings, messages, context):
        captured.append(context)
        return parse_action({"content": '{"action":"reply","text":"bounded"}'})
    monkeypatch.setattr("bridge.web.app.converse", action)

    client.post(url + "/messages", json={
        "text": "来源信息已在数据表单填写。请继续细胞状态分析。",
    })
    settle(client, sid)

    assert len(captured) == 1
    context = captured[0]
    assert set(context) == {
        "status", "upload_ids", "plan_status", "capabilities",
        "tool_execution_history", "results_sent_to_model",
    }
    assert context["status"] == "idle"
    assert context["upload_ids"] == [aid]
    assert context["plan_status"] == "completed"
    assert context["tool_execution_history"] == [{
        "tool_id": "P0-01", "state": "succeeded",
    }]
    p002 = next(item for item in context["capabilities"] if item["tool_id"] == "P0-02")
    assert p002["state"] == "ready" and p002["reason_codes"] == []
    serialized = json.dumps(context)
    for private_value in (
        "PRIVATE-ACTUAL-SOURCE-ID", "private-source-name.h5ad", str(tmp_path),
        service.load(sid)["_uploads"][aid]["sha256"], "private-cell-a",
    ):
        assert private_value not in serialized


def test_legacy_sessions_default_history_and_unconnected_capabilities(client):
    sid = new_session(client)["id"]
    service = client.app.state.service
    state = service.load(sid)
    for key in ("plan_history", "_plan_history", "_tool_runs"):
        state.pop(key)
    service.save(state)
    value = client.get(f"/api/sessions/{sid}").json()
    assert value["plan_history"] == []
    caps = {item["tool_id"]: item for item in value["capabilities"]}
    assert len(caps) == 12
    assert caps["P0-05"]["state"] == "not_connected"
    assert "measurement_spec_not_configured" in caps["P0-02"]["reason_codes"]


def test_partial_run_keeps_real_state_and_artifacts(client, tmp_path, monkeypatch):
    from bridge.runners import ToolExecutionPipeline
    from bridge.toolkit.contracts import ExecutionState
    original = ToolExecutionPipeline.execute_step
    def partial(self, step):
        outcome = original(self, step)
        return outcome.model_copy(update={"execution_state": ExecutionState.PARTIAL})
    monkeypatch.setattr(ToolExecutionPipeline, "execute_step", partial)
    sid = new_session(client)["id"]
    url = f"/api/sessions/{sid}"
    client.post(url + "/uploads", files={"file": ("synthetic.h5ad", h5ad(tmp_path))})
    client.post(url + "/messages", json={"text": "scRNA-seq，X 是原始计数，进行 QC"})
    plan = settle(client, sid)["plan"]
    client.post(url + "/approve", json={"plan_id": plan["id"], "plan_digest": plan["digest"]})
    done = settle(client, sid)
    assert done["plan"]["status"] == "partial"
    assert done["plan"]["steps"][0]["status"] == "partial"
    assert done["artifacts"]




@pytest.mark.parametrize("text", ["No graft data, do not run analysis", "没有移植数据，不要分析", "假设没有移植数据", "If there is no graft data"])
def test_no_graft_negative_or_hypothetical_intent_never_plans(client, tmp_path, monkeypatch, text):
    sid = new_session(client)["id"]
    url = f"/api/sessions/{sid}"
    client.post(url + "/uploads", files={"file": ("synthetic.h5ad", h5ad(tmp_path))})
    client.post(url + "/messages", json={"text": "scRNA-seq，X 是原始计数，进行 QC"})
    assert settle(client, sid)["status"] == "awaiting_approval"
    monkeypatch.setattr("bridge.web.app.converse", lambda *args: parse_action({"content": '{"action":"prepare_analysis","tool_id":"P0-12"}'}))
    client.post(url + "/messages", json={"text": text})
    value = settle(client, sid)
    assert value["plan"] is None
    assert value["error"] == "no_graft_declaration_required"



def test_restart_preserves_completed_plan_during_interrupted_conversation(client):
    sid = new_session(client)["id"]
    store = client.app.state.service
    state = store.load(sid)
    state["status"] = "thinking"
    state["plan"] = {"id": "completed", "status": "completed", "steps": []}
    store.save(state)
    other = create_app(store.settings)
    other.state.service.pool.shutdown()
    assert other.state.service.load(sid)["plan"]["status"] == "completed"


def test_provider_accepts_only_complete_typed_json_actions():
    qc = {"action": "prepare_qc", "upload_id": "a" * 32, "matrix_location": "X"}
    assert parse_action({"content": json.dumps(qc)}).action == "prepare_qc"
    assert parse_action({"content": '{"action":"reply","text":"Please upload a file."}'}).text == "Please upload a file."
    assert parse_action({"content": '{"action":"prepare_analysis","tool_id":"P0-02"}'}).tool_id == "P0-02"
    invalid = [
        {"content": "Please upload a file."},
        {"content": '<｜DSML｜function_calls><｜DSML｜invoke name="prepare_analysis">P0-02</｜DSML｜invoke>'},
        {"content": '{"action":"reply"}'},
        {"content": '{"action":"prepare_qc","upload_id":"a"}'},
        {"content": '{"action":"prepare_analysis"}'},
        {"content": '{"action":"shell","command":"ls"}'},
        {"content": '{"action":"prepare_qc","upload_id":"abc","matrix_location":"../../secret"}'},
        {"content": json.dumps(qc), "tool_calls": [{"function": {"name": "prepare_qc", "arguments": "{}"}}]},
    ]
    for message in invalid:
        with pytest.raises(ValueError):
            parse_action(message)


@pytest.fixture
def client(tmp_path):
    config = Settings(storage_root=tmp_path / "private", token="t" * 32,
                      model_base_url="https://provider.invalid/v1", model="test-model",
                      model_api_key="private-key", origin="http://testserver")
    app = create_app(config)
    with TestClient(app) as client:
        client.headers["Origin"] = "http://testserver"
        yield client


def login(client):
    assert client.post("/api/login", json={"token": "t" * 32}).status_code == 200


def new_session(client):
    login(client)
    return client.post("/api/sessions").json()


def settle(client, sid, timeout=90):
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        value = client.get(f"/api/sessions/{sid}").json()
        if value["status"] not in {"thinking", "running"}:
            return value
        time.sleep(.05)
    pytest.fail("worker did not finish")


def h5ad(tmp_path, *, layer=False):
    import anndata as ad
    import numpy as np
    import pandas as pd
    from scipy import sparse
    data = ad.AnnData(sparse.csr_matrix(np.array([[1, 2, 0], [2, 0, 1], [0, 3, 1], [2, 1, 1]], dtype=np.int64)),
                      obs=pd.DataFrame(index=["private-cell-a", "b", "c", "d"]),
                      var=pd.DataFrame(index=["MT-ND1", "SOX2", "FOXA2"]))
    if layer:
        data.layers["counts"] = data.X.copy()
    path = tmp_path / "synthetic.h5ad"
    data.write_h5ad(path)
    return path.read_bytes()


def test_auth_origin_logout_and_path_boundaries(client):
    assert client.get("/api/health").json() == {"status": "ok"}
    assert client.get("/api/sessions").status_code == 401
    assert client.post("/api/login", json={"token": "wrong"}).status_code == 401
    assert client.post("/api/login", json={"token": "t" * 32}, headers={"Origin": "https://evil.invalid"}).status_code == 403
    login(client)
    cookie = client.cookies.get("bridge_session")
    assert cookie and cookie != "t" * 32
    assert client.get("/api/sessions/" + "a" * 32).status_code == 404
    assert client.get("/api/sessions/%2e%2e%2fsecret").status_code == 404
    assert client.post("/api/logout").status_code == 200
    assert client.get("/api/sessions").status_code == 401


def test_upload_validation_and_private_state(client, tmp_path):
    session = new_session(client)
    url = f"/api/sessions/{session['id']}/uploads"
    assert client.post(url, files={"file": ("../bad.h5ad", b"not hdf5")}).status_code == 400
    response = client.post(url, files={"file": ("private.h5ad", h5ad(tmp_path, layer=True))})
    assert response.status_code == 200
    value = response.json()
    assert value["uploads"][0]["kind"] == "h5ad"
    assert str(tmp_path) not in response.text
    assert "private-cell-a" not in response.text
    assert value["plan"] is None
    assert "counts" in value["messages"][-1]["content"]
    assert client.get(f"/api/sessions/{session['id']}/artifacts/" + "a" * 32).status_code == 404


def test_model_context_and_real_http_error(client, monkeypatch):
    sid = new_session(client)["id"]
    def response(request):
        payload = json.loads(request.content)
        assert "tools" not in payload and "tool_choice" not in payload
        assert payload["response_format"] == {"type": "json_object"}
        assert [item["role"] for item in payload["messages"]].count("system") == 1
        assert payload["messages"][0]["role"] == "system"
        system = payload["messages"][0]["content"]
        assert "Safe execution context:" in system
        assert 'A capability with state "ready" means' in system
        assert "do not ask for its private source value in chat" in system
        assert "use prepare_analysis instead of asking the user to reconfirm QC" in system
        assert payload["messages"][-1] == {"role": "user", "content": "What can you do?"}
        assert "private-key" not in json.dumps(payload)
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"action":"reply","text":"I can help prepare QC."}'}}]})
    original = httpx.Client
    monkeypatch.setattr("bridge.web.provider.httpx.Client", lambda **kwargs: original(transport=httpx.MockTransport(response), **kwargs))
    client.post(f"/api/sessions/{sid}/messages", json={"text": "What can you do?"})
    value = settle(client, sid)
    assert value["messages"][-1]["content"] == "I can help prepare QC."
    monkeypatch.setattr("bridge.web.provider.httpx.Client", lambda **kwargs: original(transport=httpx.MockTransport(lambda request: httpx.Response(502, text="/private/provider/key")), **kwargs))
    client.post(f"/api/sessions/{sid}/messages", json={"text": "Continue"})
    failed = settle(client, sid)
    assert failed["status"] == "failed"
    assert failed["error"] == "provider_unavailable"
    assert "/private/provider/key" not in json.dumps(failed)


def test_real_qc_exact_approval_and_artifacts(client, tmp_path):
    sid = new_session(client)["id"]
    client.post(f"/api/sessions/{sid}/uploads", files={"file": ("synthetic.h5ad", h5ad(tmp_path, layer=True))})
    client.post(f"/api/sessions/{sid}/messages", json={"text": "是，使用 counts 层进行 QC"})
    value = settle(client, sid)
    assert value["status"] == "idle", value
    assert value["plan"] is None
    assert "scRNA-seq" in value["messages"][-1]["content"]
    client.post(f"/api/sessions/{sid}/messages", json={"text": "这是 scRNA-seq 数据"})
    value = settle(client, sid)
    assert value["status"] == "awaiting_approval", value
    plan = value["plan"]
    assert client.post(f"/api/sessions/{sid}/approve", json={"plan_id": plan["id"], "plan_digest": "0" * 64}).status_code == 409
    assert client.post(f"/api/sessions/{sid}/approve", json={"plan_id": plan["id"], "plan_digest": plan["digest"]}).status_code == 200
    done = settle(client, sid)
    assert done["status"] == "idle", done
    assert done["plan"]["status"] == "completed"
    assert done["artifacts"]
    assert any(item["kind"] == "figure" for item in done["artifacts"])
    evidence = [item for item in done["artifacts"] if item["kind"] == "evidence"]
    assert evidence and all(item["name"].endswith(".display-redacted.json") for item in evidence)
    assert all("source_sha256" in client.app.state.service.load(sid)["_artifacts"][item["id"]] for item in evidence)
    assert str(tmp_path) not in json.dumps(done)
    for artifact in done["artifacts"]:
        response = client.get(artifact["url"])
        assert response.status_code == 200
        assert response.headers["x-content-type-options"] == "nosniff"
    assert client.post(f"/api/sessions/{sid}/approve", json={"plan_id": plan["id"], "plan_digest": plan["digest"]}).status_code == 409


def test_restart_interrupts_never_reexecutes(client):
    sid = new_session(client)["id"]
    store = client.app.state.service
    state = store.load(sid)
    state["status"] = "running"
    store.save(state)
    other = create_app(store.settings)
    with TestClient(other) as restarted:
        restarted.headers["Origin"] = "http://testserver"
        login(restarted)
        value = restarted.get(f"/api/sessions/{sid}").json()
        assert value["status"] == "failed"
        assert value["error"] == "interrupted"

def test_unknown_artifacts_are_session_scoped(client, tmp_path):
    first = new_session(client)["id"]
    second = client.post("/api/sessions").json()["id"]
    assert client.get(f"/api/sessions/{second}/artifacts/{first}").status_code == 404
    assert client.get(f"/api/sessions/{first}/artifacts/%2e%2e%2fprivate").status_code == 404


def test_expired_cookie_and_oversized_body_are_rejected(client):
    new_session(client)
    for key in client.app.state.service.cookies:
        client.app.state.service.cookies[key] = 0
    assert client.get("/api/sessions").status_code == 401
    login(client)
    assert client.post("/api/sessions", content=b"x" * 40000).status_code == 413


def test_assay_must_be_declared_for_each_upload(client, tmp_path):
    sid = new_session(client)["id"]
    url = f"/api/sessions/{sid}"
    data = h5ad(tmp_path, layer=True)
    client.post(url + "/uploads", files={"file": ("first.h5ad", data)})
    client.post(url + "/messages", json={"text": "scRNA-seq，使用 counts 层进行 QC"})
    assert settle(client, sid)["status"] == "awaiting_approval"
    client.post(url + "/uploads", files={"file": ("second.h5ad", data)})
    client.post(url + "/messages", json={"text": "使用 counts 层进行 QC"})
    result = settle(client, sid)
    assert result["status"] == "idle"
    assert result["plan"] is None


def test_changed_upload_never_executes_and_error_is_safe(client, tmp_path):
    sid = new_session(client)["id"]
    url = f"/api/sessions/{sid}"
    client.post(url + "/uploads", files={"file": ("synthetic.h5ad", h5ad(tmp_path, layer=True))})
    client.post(url + "/messages", json={"text": "scRNA-seq，使用 counts 层进行 QC"})
    proposal = settle(client, sid)["plan"]
    store = client.app.state.service
    aid = store.load(sid)["uploads"][0]["id"]
    path = store.root / sid / "uploads" / (aid + ".h5ad")
    path.write_bytes(b"changed")
    client.post(url + "/approve", json={"plan_id": proposal["id"], "plan_digest": proposal["digest"]})
    result = settle(client, sid)
    assert result["status"] == "failed"
    assert result["error"] == "execution_failed"
    assert result["artifacts"] == []
    assert str(tmp_path) not in json.dumps(result)


def test_symlink_upload_directory_never_plans(client, tmp_path):
    sid = new_session(client)["id"]
    url = f"/api/sessions/{sid}"
    client.post(url + "/uploads", files={"file": ("synthetic.h5ad", h5ad(tmp_path, layer=True))})
    directory = client.app.state.service.root / sid / "uploads"
    destination = tmp_path / "moved-upload"
    directory.rename(destination)
    directory.symlink_to(destination, target_is_directory=True)
    client.post(url + "/messages", json={"text": "scRNA-seq，使用 counts 层进行 QC"})
    result = settle(client, sid)
    assert result["status"] == "failed"
    assert result["plan"] is None


def test_hdf5_external_links_rejected(client, tmp_path):
    import h5py
    sid = new_session(client)["id"]
    path = tmp_path / "external.h5ad"
    path.write_bytes(h5ad(tmp_path))
    with h5py.File(path, "a") as handle:
        handle["external"] = h5py.ExternalLink("/private/data.h5ad", "/")
    response = client.post(f"/api/sessions/{sid}/uploads", files={"file": ("external.h5ad", path.read_bytes())})
    assert response.status_code == 400
    assert "/private/" not in response.text


def test_provider_cannot_prepare_without_explicit_declaration(client, monkeypatch, tmp_path):
    sid = new_session(client)["id"]
    url = f"/api/sessions/{sid}"
    response = client.post(url + "/uploads", files={"file": ("synthetic.h5ad", h5ad(tmp_path, layer=True))})
    aid = response.json()["uploads"][0]["id"]
    original = httpx.Client
    def provider(request):
        payload = json.loads(request.content)
        encoded = json.dumps(payload)
        assert "private-cell-a" not in encoded
        assert str(tmp_path) not in encoded
        assert "synthetic.h5ad" not in encoded
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({"action": "prepare_qc", "upload_id": aid, "matrix_location": "layers/counts"})}}]})
    monkeypatch.setattr("bridge.web.provider.httpx.Client", lambda **kwargs: original(transport=httpx.MockTransport(provider), **kwargs))
    client.post(url + "/messages", json={"text": "Can you explain this workflow?"})
    value = settle(client, sid)
    assert value["status"] == "idle"
    assert value["plan"] is None

def test_hdf5_external_dataset_rejected(client, tmp_path):
    import h5py
    sid = new_session(client)["id"]
    path = tmp_path / "external-array.h5ad"
    path.write_bytes(h5ad(tmp_path))
    with h5py.File(path, "a") as handle:
        handle.create_dataset("external_array", (10,), dtype="i4", external=[("not-loaded.bin", 0, 40)])
    response = client.post(f"/api/sessions/{sid}/uploads", files={"file": ("external-array.h5ad", path.read_bytes())})
    assert response.status_code == 400

@pytest.mark.parametrize("text", ["counts 层不是原始计数", "scRNA-seq，使用 counts 层？", "不要使用 counts 层进行 QC"])
def test_ambiguous_or_negative_counts_never_prepare(client, tmp_path, monkeypatch, text):
    sid = new_session(client)["id"]
    url = f"/api/sessions/{sid}"
    client.post(url + "/uploads", files={"file": ("synthetic.h5ad", h5ad(tmp_path, layer=True))})
    original = httpx.Client
    monkeypatch.setattr("bridge.web.provider.httpx.Client", lambda **kwargs: original(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json={"choices": [{"message": {"content": "请明确计数语义。"}}]})), **kwargs))
    client.post(url + "/messages", json={"text": text})
    value = settle(client, sid)
    assert value["plan"] is None
    assert "_pending_qc" not in client.app.state.service.load(sid)

def test_underreported_content_length_still_bounds_received_json(client):
    sid = new_session(client)["id"]
    response = client.post(f"/api/sessions/{sid}/messages",
                           content=json.dumps({"text": "x" * 40000}),
                           headers={"Content-Length": "1", "Content-Type": "application/json"})
    assert response.status_code == 413

def test_cancelled_pending_counts_does_not_prepare_on_assay_mention(client, tmp_path, monkeypatch):
    sid = new_session(client)["id"]
    url = f"/api/sessions/{sid}"
    client.post(url + "/uploads", files={"file": ("synthetic.h5ad", h5ad(tmp_path, layer=True))})
    client.post(url + "/messages", json={"text": "使用 counts 层进行 QC"})
    assert settle(client, sid)["plan"] is None
    original = httpx.Client
    monkeypatch.setattr("bridge.web.provider.httpx.Client", lambda **kwargs: original(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json={"choices": [{"message": {"content": "已取消准备计划。"}}]})), **kwargs))
    client.post(url + "/messages", json={"text": "不要 QC，这是 scRNA-seq"})
    assert settle(client, sid)["plan"] is None

@pytest.mark.parametrize("text", [
    "This is not scRNA-seq; X contains raw counts",
    "Do not use X as raw counts; this is scRNA-seq",
    "This isn't scRNA-seq; X contains raw counts",
])
def test_english_negative_matrix_and_assay_never_prepare(client, tmp_path, monkeypatch, text):
    sid = new_session(client)["id"]
    url = f"/api/sessions/{sid}"
    client.post(url + "/uploads", files={"file": ("synthetic.h5ad", h5ad(tmp_path))})
    original = httpx.Client
    monkeypatch.setattr("bridge.web.provider.httpx.Client", lambda **kwargs: original(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json={"choices": [{"message": {"content": "Please clarify your declaration."}}]})), **kwargs))
    client.post(url + "/messages", json={"text": text})
    value = settle(client, sid)
    assert value["plan"] is None
    assert "_pending_qc" not in client.app.state.service.load(sid)


@pytest.mark.parametrize("retraction", ["counts 层不是原始计数", "The counts layer is not raw counts"])
def test_retracted_pending_matrix_requires_fresh_positive_declaration(client, tmp_path, monkeypatch, retraction):
    sid = new_session(client)["id"]
    url = f"/api/sessions/{sid}"
    client.post(url + "/uploads", files={"file": ("synthetic.h5ad", h5ad(tmp_path, layer=True))})
    original = httpx.Client
    monkeypatch.setattr("bridge.web.provider.httpx.Client", lambda **kwargs: original(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json={"choices": [{"message": {"content": "Please provide a fresh declaration."}}]})), **kwargs))
    def say(text):
        client.post(url + "/messages", json={"text": text})
        return settle(client, sid)
    assert say("使用 counts 层进行 QC")["plan"] is None
    assert say(retraction)["plan"] is None
    assert say("实验类型是 scRNA-seq")["plan"] is None
    assert "_pending_qc" not in client.app.state.service.load(sid)
    restored = say("使用 counts 层进行 QC")
    assert restored["status"] == "awaiting_approval"
    assert "scRNA-seq" in restored["plan"]["summary"]
    assert "layers/counts" in restored["plan"]["summary"]


@pytest.mark.parametrize("retraction", ["不是 scRNA-seq", "This is not scRNA-seq"])
def test_retracted_assay_does_not_reuse_older_positive_assay(client, tmp_path, monkeypatch, retraction):
    sid = new_session(client)["id"]
    url = f"/api/sessions/{sid}"
    client.post(url + "/uploads", files={"file": ("synthetic.h5ad", h5ad(tmp_path, layer=True))})
    original = httpx.Client
    monkeypatch.setattr("bridge.web.provider.httpx.Client", lambda **kwargs: original(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json={"choices": [{"message": {"content": "Please provide a fresh declaration."}}]})), **kwargs))
    def say(text):
        client.post(url + "/messages", json={"text": text})
        return settle(client, sid)
    assert say("scRNA-seq，使用 counts 层进行 QC")["status"] == "awaiting_approval"
    assert say(retraction)["plan"] is None
    waiting = say("使用 counts 层进行 QC")
    assert waiting["plan"] is None
    restored = say("实验类型是 snRNA-seq")
    assert restored["status"] == "awaiting_approval"
    assert "snRNA-seq" in restored["plan"]["summary"]
    assert "scRNA-seq" not in restored["plan"]["summary"]

def test_retraction_persists_even_when_provider_fails(client, tmp_path, monkeypatch):
    sid = new_session(client)["id"]
    url = f"/api/sessions/{sid}"
    client.post(url + "/uploads", files={"file": ("synthetic.h5ad", h5ad(tmp_path, layer=True))})
    client.post(url + "/messages", json={"text": "使用 counts 层进行 QC"})
    settle(client, sid)
    original = httpx.Client
    monkeypatch.setattr("bridge.web.provider.httpx.Client", lambda **kwargs: original(transport=httpx.MockTransport(
        lambda request: httpx.Response(502)), **kwargs))
    client.post(url + "/messages", json={"text": "counts 层不是原始计数"})
    assert settle(client, sid)["status"] == "failed"
    assert "_pending_qc" not in client.app.state.service.load(sid)
