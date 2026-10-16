"""Real QC and authenticated research setup shared by lineage tests."""
from web_support import login, h5ad, declare_counts, settle

def call(c, method, path, body=None, status=200):
    response = c.request(method, path, **({"json": body} if body is not None else {}))
    assert response.status_code == status, response.text
    return response.json()

def setup_sample(c, tmp_path):
    login(c)
    rid = call(c, "POST", "/api/researches", {"name": "Synthetic lineage"})["id"]
    base = f"/api/researches/{rid}"
    p = call(c, "POST", base + "/protocols", {"name": "Synthetic protocol", "origin": "lab", "expected_version": 0})
    vurl = base + f"/protocols/{p['id']}/versions/{p['latest']['id']}"
    v = call(c, "PATCH", vurl, {"expected_version": 1, "total_days": 28})
    v = call(c, "POST", vurl + "/confirm", {"expected_version": v["revision"]})
    r = call(c, "POST", base + "/runs", {"expected_version": 0, "protocol_version_id": v["id"], "name": "Round", "state": "planned"})
    response = c.post(base + "/uploads", files={"file": ("synthetic.h5ad", h5ad(tmp_path))})
    assert response.status_code == 200, response.text
    mid = response.json()["id"]
    s = call(c, "POST", base + f"/runs/{r['id']}/samples", {"expected_version": 1, "day": 10, "assay": "scRNA-seq", "material_id": mid})
    return rid, p, v, r, s

def qc(c, rid, mid, sid=None):
    sid = sid or call(c, "POST", "/api/sessions", {"research_id": rid})["id"]
    url = f"/api/sessions/{sid}"
    state = call(c, "POST", url + "/research-materials", {"material_id": mid})
    declare_counts(c, sid, state["uploads"][0]["id"])
    call(c, "POST", url + "/messages", {"text": "scRNA-seq, use X raw counts for QC"})
    plan = settle(c, sid)["plan"]
    call(c, "POST", url + "/approve", {"plan_id": plan["id"], "plan_digest": plan["digest"]})
    settle(c, sid)
    receipt = c.app.state.service.load(sid)["_tool_runs"][-1]
    assert receipt["state"] == "succeeded"
    return sid, receipt["file"].removesuffix(".json")

def register(c, rid, s, sid, receipt, **changes):
    return call(c, "POST", f"/api/researches/{rid}/samples/{s['id']}/analyses",
                {"expected_version": s["revision"], "session_id": sid, "receipt_id": receipt, **changes})
