"""Cross-session version selection never implies scientific comparison approval."""
import json
from fastapi.testclient import TestClient
from account_support import create_test_app
from web_support import client, login
from sample_analysis_support import call, setup_sample, qc, register


def pair(c, tmp_path):
    rid, _, _, _, sample = setup_sample(c, tmp_path)
    analyses = []
    for _ in range(2):
        sid, receipt = qc(c, rid, sample["material_id"])
        analyses.append(register(c, rid, sample, sid, receipt))
    members = [{"analysis_id": a["id"], "snapshot_sha256": a["snapshot_sha256"], "role": role}
               for a, role in zip(analyses, ("baseline", "comparator"))]
    return rid, sample, analyses, members


def test_confirmed_cross_session_selection_persists_exact_old_versions(client, tmp_path):
    rid, sample, analyses, members = pair(client, tmp_path)
    base = f"/api/researches/{rid}"
    before = call(client, "GET", base + "/workbench")
    service = client.app.state.service
    before_execution = {a["session_id"]: service.load(a["session_id"])["_tool_runs"] for a in analyses}
    cohort = call(client, "POST", base + "/analysis-cohorts",
                  {"expected_version": 0, "members": members})
    assert cohort["members"] == members
    assert cohort["status"] == "pending"
    assert cohort["summary"]["sample_count"] == 1
    assert cohort["summary"]["analysis_count"] == 2
    assert cohort["summary"]["independent_unit_count"] is None
    assert "multiple_analyses_same_sample" in cohort["reason_codes"]
    assert cohort["execution_available"] is False
    assert all(x["category"] == "background_only" for x in cohort["entries"])
    endpoint = base + "/analysis-cohorts/" + cohort["id"]
    payload = {"expected_version": cohort["revision"], "digest": cohort["digest"]}
    confirmed = call(client, "POST", endpoint + "/confirm", payload)
    assert confirmed["status"] == "confirmed"
    assert confirmed["confirmed_at"]
    assert confirmed["execution_available"] is False
    # Exact replay is safe after a lost response; no new revision or decision.
    assert call(client, "POST", endpoint + "/confirm", payload) == confirmed
    for sid, runs in before_execution.items():
        state = service.load(sid)
        assert state["_tool_runs"] == runs
        assert not state.get("_conditional_history")
    third_sid, receipt = qc(client, rid, sample["material_id"])
    third = register(client, rid, sample, third_sid, receipt)
    assert third["version"] == 3
    assert call(client, "GET", endpoint) == confirmed
    service = client.app.state.service
    with TestClient(create_test_app(service.settings)) as restarted:
        login(restarted)
        assert call(restarted, "GET", endpoint) == confirmed
    assert call(client, "GET", base + "/analysis-cohorts") == {"cohorts": [confirmed]}
    assert call(client, "GET", base + "/workbench") == before
    assert str(service.root) not in json.dumps(confirmed)


def test_changed_sources_block_confirmation_and_preserve_confirmed_decision(client, tmp_path):
    rid, _, analyses, members = pair(client, tmp_path)
    base = f"/api/researches/{rid}/analysis-cohorts"
    pending = call(client, "POST", base, {"expected_version": 0, "members": members})
    approved = call(client, "POST", base, {"expected_version": 0, "members": members})
    decision = {"expected_version": 1, "digest": approved["digest"]}
    confirmed = call(client, "POST", base + "/" + approved["id"] + "/confirm", decision)
    call(client, "DELETE", "/api/sessions/" + analyses[0]["session_id"], {})
    path = base + "/" + pending["id"]
    error = call(client, "POST", path + "/confirm",
                 {"expected_version": 1, "digest": pending["digest"]}, status=409)
    assert error["detail"] == "cohort_source_unavailable"
    assert call(client, "GET", path)["status"] == "pending"
    historical = call(client, "GET", base + "/" + approved["id"])
    assert historical["status"] == "confirmed"
    assert historical["confirmed_at"] == confirmed["confirmed_at"]
    assert historical["availability"]["status"] == "unavailable"
    assert historical["entries"][0]["category"] == "excluded"
    assert historical["execution_available"] is False
    assert historical["members"] == members


def test_members_cannot_be_forged_or_silently_rebound(client, tmp_path):
    rid, _, analyses, members = pair(client, tmp_path)
    url = f"/api/researches/{rid}/analysis-cohorts"
    forged = [dict(members[0], snapshot_sha256="0" * 64), members[1]]
    response = call(client, "POST", url, {"expected_version": 0, "members": forged}, status=409)
    assert response["detail"] == "cohort_analysis_changed"
    for altered in (
        [members[0], members[0]],
        [dict(m, role="comparator") for m in members],
        [dict(m, role="baseline") for m in members],
    ):
        call(client, "POST", url, {"expected_version": 0, "members": altered}, status=422)
    call(client, "POST", url, {"expected_version": 9, "members": members}, status=409)
    call(client, "POST", url, {"expected_version": 0, "members": members, "execution_available": True}, status=422)
    assert call(client, "GET", url) == {"cohorts": []}
    cohort = call(client, "POST", url, {"expected_version": 0, "members": members})
    endpoint = url + "/" + cohort["id"] + "/confirm"
    call(client, "POST", endpoint, {"expected_version": 1, "digest": "0" * 64}, status=409)
    call(client, "POST", endpoint, {"expected_version": 9, "digest": cohort["digest"]}, status=409)
    assert call(client, "GET", url + "/" + cohort["id"])["status"] == "pending"


def test_cohort_access_and_member_lookups_respect_research_ownership(client, tmp_path):
    from bridge.web.accounts import NOTICE_VERSION
    rid, _, _, members = pair(client, tmp_path)
    base = f"/api/researches/{rid}/analysis-cohorts"
    cohort = call(client, "POST", base, {"expected_version": 0, "members": members})
    other = call(client, "POST", "/api/researches", {"name": "Other research"})["id"]
    call(client, "POST", f"/api/researches/{other}/analysis-cohorts",
         {"expected_version": 0, "members": members}, status=404)
    client.cookies.clear()
    call(client, "POST", "/api/register", {"username": "other-cohort-reader", "password": "synthetic strong password",
                                            "notice_version": NOTICE_VERSION})
    for method, path, payload in (
        ("GET", base, None),
        ("GET", base + "/" + cohort["id"], None),
        ("POST", base, {"expected_version": 0, "members": members}),
        ("POST", base + "/" + cohort["id"] + "/confirm", {"expected_version": 1, "digest": cohort["digest"]}),
    ):
        call(client, method, path, payload, status=404)


def test_concurrent_confirmation_is_one_durable_decision(client, tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    rid, _, _, members = pair(client, tmp_path)
    base = f"/api/researches/{rid}/analysis-cohorts"
    draft = call(client, "POST", base, {"expected_version": 0, "members": members})
    endpoint = base + "/" + draft["id"] + "/confirm"
    payload = {"expected_version": 1, "digest": draft["digest"]}
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: call(client, "POST", endpoint, payload), range(2)))
    assert results[0] == results[1]
    assert results[0]["revision"] == 2
    assert len(call(client, "GET", base)["cohorts"]) == 1


def test_corrupt_cohort_store_is_not_overwritten_or_treated_as_empty(client, tmp_path):
    login(client)
    rid = call(client, "POST", "/api/researches", {"name": "Synthetic corruption"})["id"]
    path = client.app.state.service.researches.directory(rid) / "analysis-cohorts.json"
    original = '{"schema_version":999,"cohorts":{}}'
    path.write_text(original)
    call(client, "GET", f"/api/researches/{rid}/analysis-cohorts", status=409)
    assert path.read_text() == original
