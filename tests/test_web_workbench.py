from dataclasses import replace
import json

from fastapi.testclient import TestClient

from web_support import client, login

TREE = {"subtypes": ["Progenitor_root", "RG_mFP"], "nodes": [[-1, 0, 0], [-0.9, 0.3, 0.1]], "edges": [[1, 0]],
        "cells": [[-1.0, 0.0, 0.0, 0, 7, 0.0, 1], [-0.9, 0.3, 0.1, 1, 8, 0.05, 1]], "source": "synthetic fixture", "extra": "dropped"}


def configure(client, path):
    login(client)
    service = client.app.state.service
    service.settings = replace(service.settings, workbench_tree_path=path)


def test_tree_unavailable_until_configured(client):
    login(client)
    assert client.get("/api/workbench/devtree").status_code == 404


def test_configured_tree_is_validated_and_projected(client, tmp_path):
    path = tmp_path / "tree.json"
    path.write_text(json.dumps(TREE), encoding="utf-8")
    configure(client, path)
    response = client.get("/api/workbench/devtree")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["subtypes"] == TREE["subtypes"] and len(body["cells"]) == 2
    assert "extra" not in body


def test_malformed_tree_is_rejected(client, tmp_path):
    path = tmp_path / "tree.json"
    bad = dict(TREE, cells=[[0, 0, 0, 5, 7, 0.0, 1]])
    path.write_text(json.dumps(bad), encoding="utf-8")
    configure(client, path)
    assert client.get("/api/workbench/devtree").status_code == 422
    configure(client, tmp_path / "missing.json")
    assert client.get("/api/workbench/devtree").status_code == 422


def test_tree_requires_signed_in_account(client, tmp_path):
    path = tmp_path / "tree.json"
    path.write_text(json.dumps(TREE), encoding="utf-8")
    configure(client, path)
    with TestClient(client.app) as anonymous:
        assert anonymous.get("/api/workbench/devtree").status_code == 401
