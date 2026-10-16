"""Synthetic upload to approved expression run to source-bound figures."""
import json
import numpy as np

from web_support import client as client, new_session, declare_counts, declare_source, settle, confirm_change
from test_expression_exploration import matrix


def test_approved_expression_flow_and_source_bound_figures(client, tmp_path):
    sid = new_session(client)["id"]
    url = f"/api/sessions/{sid}"
    data = matrix()
    data = data[np.tile(np.arange(data.n_obs), 40)].copy()
    data.obs_names = [f"cell-{i}" for i in range(data.n_obs)]
    data.obsm["X_umap"] = np.random.default_rng(1).normal(size=(data.n_obs, 2))
    data.obs["condition"] = (["control"] * 30 + ["treated"] * 30) * 80
    data.obs["sample"] = data.obs.condition
    path = tmp_path / "expression.h5ad"
    data.write_h5ad(path)
    aid = client.post(url + "/uploads", files={"file": ("expression.h5ad", path.read_bytes())}).json()["uploads"][0]["id"]
    declare_counts(client, sid, aid)
    declare_source(client, sid, aid, "source-family:synthetic-expression")
    selection = dict(tool_id="P0-01", mode_id=None, asset_ids=[aid], object_inputs=[], measurement_spec_ref=None)
    assert client.post(url + "/analysis-inputs", json=selection).status_code == 200
    def run(tool):
        response = client.post(url + "/prepare-analysis", json={"tool_id": tool})
        assert response.status_code == 200, response.json()
        proposal = response.json()["plan"]
        assert proposal, response.json()
        response = client.post(url + "/approve", json={"plan_id": proposal["id"], "plan_digest": proposal["digest"]})
        assert response.status_code == 200, response.json()
        result = settle(client, sid)
        assert result["plan"]["status"] == "completed", result
        return result
    run("P0-01")
    selection.update(tool_id="P0-02", measurement_spec_ref="EXPRESSION-exploration-v0.1",
        expression_analysis={"exploration": {"group_key": "type", "embedding_key": "X_umap", "genes": [f"gene-{i}" for i in range(32)]},
                             "contrast": {"group_key": "type", "group": "A", "condition_key": "condition",
                                          "sample_key": "sample", "reference": "control", "comparison": "treated"}})
    saved = client.post(url + "/analysis-inputs", json=selection)
    assert saved.status_code == 200, saved.json()
    assert next(c for c in saved.json()["capabilities"] if c["tool_id"] == "P0-02")["state"] == "ready"
    result = run("P0-02")
    sets = [a for a in result["artifacts"] if a["name"].startswith("expression_visualization_artifact_set.")]
    assert len(sets) == 1
    from bridge.web.research_context import typed_figure_display
    typed_figure_display(client.app.state.service, client.app.state.service.load(sid), sets[0]["id"])
    preview = client.get(url + "/artifacts/" + sets[0]["id"] + "/preview")
    assert preview.status_code == 200, preview.text
    figures = preview.json()["figures"]
    assert len(figures) == 3
    for figure in figures:
        assert len(figure["renders"]) == 3
        assert client.get(url + "/artifacts/" + figure["table"]["id"]).status_code == 200
    # A realistic color-rich plot exceeds the generic 2 MiB object limit.
    plot_url = url + "/artifacts/" + figures[0]["data"]["id"]
    assert len(client.get(plot_url).content) > 2 * 1024 * 1024
    preview = client.get(plot_url + "/preview")
    assert preview.status_code == 200, preview.text
    umap = preview.json()
    assert umap["schema_ref"] == "bridge://schemas/expression-plot-data/v0.1"
    assert len(umap["records"]) == len(umap["colors"]["分群"])
    assert "input_sha256" not in umap  # Display projection is intentionally bounded.
    assert umap["n_observations"] == data.n_obs
    assert sum(row["count"] for row in umap["composition"]) == data.n_obs
    service = client.app.state.service
    state = service.load(sid)
    binding = state["_artifacts"][figures[0]["data"]["id"]]
    original_sha = binding["source_sha256"]
    binding["source_sha256"] = "0" * 64
    service.sessions.save(state)
    assert client.get(plot_url + "/preview").status_code == 422
    binding["source_sha256"] = original_sha
    service.sessions.save(state)
    request = json.loads(state["_plan"]["steps"][0]["approved_request_json"])
    assert request["parameters"]["contrast"]["sample_key"] == "sample"
    assert request["parameters"]["exploration"]["group_key"] == "type"
    selection["expression_analysis"]["exploration"]["group_key"] = "sample"
    changed = client.post(url + "/analysis-inputs", json=selection)
    assert changed.status_code == 200, changed.json()
    if changed.json().get("pending_input_change"):
        confirm_change(client, sid, changed.json())
    response = client.post(url + "/prepare-analysis", json={"tool_id": "P0-02"}).json()
    assert response.get("plan"), response
    assert response["plan"]["digest"] != result["plan"]["digest"]
