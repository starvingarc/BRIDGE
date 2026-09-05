from __future__ import annotations

import json
import time

import pytest
httpx = pytest.importorskip("httpx")
pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from bridge.web.app import Settings, create_app
from bridge.web.provider import parse_action


def test_provider_accepts_real_tool_call_and_content_fallback():
    action = {"action": "prepare_qc", "upload_id": "a" * 32, "matrix_location": "X"}
    assert parse_action({"content": json.dumps(action)}).action == "prepare_qc"
    assert parse_action({"tool_calls": [{"function": {"name": "prepare_qc", "arguments": json.dumps({k: v for k, v in action.items() if k != "action"})}}]}).matrix_location == "X"
    assert parse_action({"content": "Please upload a file."}).text == "Please upload a file."
    with pytest.raises(ValueError):
        parse_action({"content": '{"action":"shell","command":"ls"}'})
    with pytest.raises(ValueError):
        parse_action({"content": '{"action":"prepare_qc","upload_id":"abc","matrix_location":"../../secret"}'})


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
        assert "tool_choice" not in payload
        assert [item["role"] for item in payload["messages"]].count("system") == 1
        assert payload["messages"][0]["role"] == "system"
        assert "Safe execution context:" in payload["messages"][0]["content"]
        assert payload["messages"][-1] == {"role": "user", "content": "What can you do?"}
        assert "private-key" not in json.dumps(payload)
        return httpx.Response(200, json={"choices": [{"message": {"content": "I can help prepare QC."}}]})
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
