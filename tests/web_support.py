"""Shared Web test fixtures; this module does not collect tests."""

from __future__ import annotations

import hashlib
import json
import time
from types import SimpleNamespace

import pytest

httpx = pytest.importorskip("httpx")
pytest.importorskip("fastapi")
from fastapi.testclient import TestClient
from bridge.web.app import Settings
from account_support import create_test_app as create_app, login_test_account


def skill_read_response(payload, name="expression-exploration"):
    """The external model double follows the same read-before-action wire contract."""
    if "Research workflow catalog:" not in payload["messages"][0]["content"]:
        return None
    if "tools" in payload:
        message = {"content": None, "tool_calls": [{"type": "function", "function": {
            "name": "load_skill", "arguments": json.dumps({"name": name})}}]}
    else:
        message = {"content": json.dumps({"action": "load_skill", "name": name})}
    return httpx.Response(200, json={"choices": [{"message": message}]})


def confirm_change(client, sid, state):
    change = state["pending_input_change"]
    response = client.post(
        f"/api/sessions/{sid}/input-change/confirm",
        json={"change_id": change["id"], "change_digest": change["digest"]},
    )
    assert response.status_code == 200, response.json()
    return response.json()


def declare_counts(client, sid, aid, *, location="X", assay="scRNA-seq"):
    """Test setup uses the same explicit stage-and-confirm contract as the UI."""
    staged = client.post(
        f"/api/sessions/{sid}/analysis-inputs/assets",
        json={
            "upload_id": aid,
            "assay": assay,
            "matrix_location": location,
            "matrix_semantics": "raw_counts",
            "input_level": "count_ready",
            "metadata": {},
        },
    )
    assert staged.status_code == 200, staged.json()
    return confirm_change(client, sid, staged.json())


def declare_source(client, sid, aid, source):
    staged = client.post(
        f"/api/sessions/{sid}/inputs", json={"upload_id": aid, "source_family_id": source}
    )
    assert staged.status_code == 200, staged.json()
    return confirm_change(client, sid, staged.json())


@pytest.fixture
def client(tmp_path, monkeypatch):
    # Replace only the external provider HTTP boundary. Plans and tools stay real.
    original_client = httpx.Client

    def provider_response(request):
        payload = json.loads(request.content)
        read = skill_read_response(payload)
        if read is not None:
            return read
        context = json.loads(
            payload["messages"][0]["content"].split("Safe execution context: ", 1)[1]
        )
        text = payload["messages"][-1]["content"]
        action = {"action": "reply", "text": "Please clarify the next input."}
        if context["upload_ids"] and any(
            word in text for word in ("counts", "计数", "scRNA-seq", "snRNA-seq")
        ):
            history = " ".join(item["content"] for item in payload["messages"][1:])
            action = {
                "action": "prepare_qc",
                "upload_id": context["upload_ids"][-1],
                "matrix_location": "layers/counts"
                if ("counts 层" in history or "layers/counts" in history)
                else "X",
            }
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(action)}}]})

    monkeypatch.setattr(
        "bridge.web.provider.httpx.Client",
        lambda **kwargs: original_client(
            **({"transport": httpx.MockTransport(provider_response)} | kwargs)
        ),
    )
    config = Settings(
        storage_root=tmp_path / "private",
        model_base_url="https://provider.invalid/v1",
        model="test-model",
        model_api_key="private-key",
        origin="http://testserver",
    )
    app = create_app(config)
    with TestClient(app) as client:
        client.headers["Origin"] = "http://testserver"
        yield client


def login(client):
    login_test_account(client)


def new_session(client):
    login(client)
    return client.post("/api/sessions").json()


def settle(client, sid, timeout=90):
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        value = client.get(f"/api/sessions/{sid}").json()
        if value["status"] not in {"thinking", "running", "stopping"}:
            if value.get("assessment") is not None:
                private = client.app.state.service.load(sid)["_assessment"]
                value["_assessment_state"] = {**value["assessment"], **private}
            return value
        time.sleep(0.05)
    pytest.fail("worker did not finish")


def h5ad(tmp_path, *, layer=False):
    import anndata as ad
    import numpy as np
    import pandas as pd
    from scipy import sparse

    data = ad.AnnData(
        sparse.csr_matrix(np.array([[1, 2, 0], [2, 0, 1], [0, 3, 1], [2, 1, 1]], dtype=np.int64)),
        obs=pd.DataFrame(index=["private-cell-a", "b", "c", "d"]),
        var=pd.DataFrame(index=["MT-ND1", "SOX2", "FOXA2"]),
    )
    if layer:
        data.layers["counts"] = data.X.copy()
    path = tmp_path / "synthetic.h5ad"
    data.write_h5ad(path)
    return path.read_bytes()


def registered_artifact(client, sid, name, data):
    from bridge.storage.private_paths import ensure_private_directory
    from bridge.toolkit.contracts import ArtifactManifest
    from bridge.web.sessions import write_file

    service = client.app.state.service
    source_root = service.directory(sid) / "runs" / "preview-test"
    ensure_private_directory(source_root)
    source = source_root / name
    write_file(source, data)
    sha256 = hashlib.sha256(data).hexdigest()
    state = service.load(sid)
    state["_tool_runs"].append({"file": "preview-test-receipt.json", "sha256": "0" * 64})
    service.artifacts.register(
        state,
        SimpleNamespace(
            artifacts=[
                ArtifactManifest(
                    artifact_id="preview-test:" + name,
                    kind="table",
                    path=source,
                    media_type="application/octet-stream",
                    sha256=sha256,
                )
            ],
            request=SimpleNamespace(tool_id="P0-test"),
        ),
    )
    return service.load(sid)["artifacts"][-1]


def parquet_bytes(tmp_path, name, columns, **write_options):
    import pyarrow as pa
    import pyarrow.parquet as pq

    path = tmp_path / name
    pq.write_table(pa.table(columns), path, **write_options)
    return path.read_bytes()


def decode_evidence_tables(value):
    """Simulate a provider consuming the documented lossless table wire format."""
    if isinstance(value, dict) and set(value) == {"columns", "rows", "missing"}:
        return [{key: decode_evidence_tables(row[j]) for j, key in enumerate(value["columns"])
                 if j not in value["missing"][i]} for i, row in enumerate(value["rows"])]
    if isinstance(value, dict):
        return {key: decode_evidence_tables(item) for key, item in value.items()}
    if isinstance(value, list):
        return [decode_evidence_tables(item) for item in value]
    return value
