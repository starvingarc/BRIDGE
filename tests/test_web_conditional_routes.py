from test_web_service import client
from test_web_conditional_inputs import comparison
from test_web_inputs import approve


def test_http_selection_confirmation_and_plan_approval_remain_separate(client, tmp_path):
    service, state, selection, _ = comparison(client, tmp_path)
    sid = state["id"]
    base = f"/api/sessions/{sid}"
    view = client.get(base).json()["conditional_inputs"]
    assert view["comparison"]["entries"][0]["execution_available"]
    response = client.post(base + "/conditional-inputs/propose", json={
        "selection": selection.model_dump(mode="json"), "expected_revision": view["input_revision"]})
    assert response.status_code == 200, response.json()
    draft = response.json()["conditional_inputs"]["selections"][-1]
    body = {"draft_id": draft["id"], "draft_digest": draft["digest"],
            "expected_revision": draft["input_revision"]}
    assert client.post(base + "/conditional-inputs/prepare", json=body).status_code == 409
    response = client.post(base + "/conditional-inputs/confirm", json=body)
    assert response.status_code == 200, response.json()
    confirmed = response.json()["conditional_inputs"]
    assert confirmed["selections"][-1]["status"] == "confirmed"
    assert service.load(sid)["_tool_runs"] == []
    body["expected_revision"] = confirmed["input_revision"]
    response = client.post(base + "/conditional-inputs/prepare", json=body)
    assert response.status_code == 200, response.json()
    assert response.json()["status"] == "awaiting_approval"
    assert service.load(sid)["_tool_runs"] == []
    done = approve(client, sid, response.json()["plan"])
    assert done["plan"]["status"] in {"completed", "partial"}
    assert [r["tool_id"] for r in service.load(sid)["_tool_runs"]] == ["P0-07"]
