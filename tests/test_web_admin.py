from multiuser_support import multi_clients, PASSWORD


def test_admin_reads_are_audited_and_cannot_mutate(tmp_path):
    with multi_clients(tmp_path) as (service, alice, bob, admin):
        sid = alice.post("/api/sessions", json={}).json()["id"]
        assert bob.get("/api/admin/users").status_code == 403
        listing = admin.get("/api/admin/sessions").json()["sessions"]
        assert listing[0]["owner_username"] == "alice"
        detail = admin.get("/api/admin/sessions/" + sid)
        assert detail.status_code == 200
        assert detail.json()["owner"]["username"] == "alice"
        assert detail.json()["session"]["id"] == sid
        before = (service.directory(sid) / "session.json").read_bytes()
        for suffix in ("", "/messages", "/approve", "/stop", "/artifacts/" + "a" * 32 + "/acknowledge"):
            result = admin.post("/api/admin/sessions/" + sid + suffix, json={})
            assert result.status_code == 403
        assert (service.directory(sid) / "session.json").read_bytes() == before
        assert admin.get("/api/admin/sessions/" + "f" * 32).status_code == 404
        events = admin.get("/api/admin/audit").json()["events"]
        reads = [event for event in events if event["sid"] == sid and event["action"].startswith("GET")]
        assert reads and reads[0]["outcome"] == "200"
        assert PASSWORD not in str(events) and "shared-secret" not in str(events)
        # Normal users can still alter their own organization flags.
        assert alice.patch("/api/sessions/" + sid, json={"archived": True}).status_code == 200


def test_admin_disable_and_reset_invalidate_logins(tmp_path):
    with multi_clients(tmp_path) as (service, alice, bob, admin):
        alice_id = alice.get("/api/me").json()["user"]["id"]
        bob_id = bob.get("/api/me").json()["user"]["id"]
        assert bob.post("/api/admin/users/" + alice_id + "/disable", json={}).status_code == 403
        reset = admin.post("/api/admin/users/" + alice_id + "/reset-password", json={})
        assert reset.status_code == 200
        assert alice.get("/api/me").status_code == 401
        assert alice.post("/api/login", json={"username": "alice", "password": reset.json()["temporary_password"]}).status_code == 200
        assert alice.get("/api/me").json()["user"]["must_change_password"]
        assert admin.post("/api/admin/users/" + bob_id + "/disable", json={}).status_code == 200
        assert bob.get("/api/me").status_code == 401


def test_admin_download_cannot_bypass_artifact_visibility(tmp_path):
    with multi_clients(tmp_path) as (service, alice, bob, admin):
        sid = alice.post("/api/sessions", json={}).json()["id"]
        assert admin.get("/api/admin/sessions/" + sid + "/diagnostics").status_code == 404
        # An invented artifact is unavailable even to an administrator.
        assert admin.get("/api/admin/sessions/" + sid + "/artifacts/" + "a" * 32).status_code == 404


def test_admin_material_download_checks_owner_and_integrity(tmp_path):
    from web_support import h5ad
    with multi_clients(tmp_path) as (service, alice, bob, admin):
        sid = alice.post("/api/sessions", json={}).json()["id"]
        data = h5ad(tmp_path)
        uploaded = alice.post("/api/sessions/" + sid + "/uploads",
                              files={"file": ("synthetic.h5ad", data)})
        assert uploaded.status_code == 200, uploaded.text
        aid = uploaded.json()["uploads"][0]["id"]
        url = "/api/admin/sessions/" + sid + "/uploads/" + aid
        assert bob.get(url).status_code == 403
        response = admin.get(url)
        assert response.status_code == 200
        assert response.content == data
        (service.directory(sid) / "uploads" / (aid + ".h5ad")).write_bytes(b"changed")
        assert admin.get(url).status_code == 409
        assert bob.put("/api/model-settings", json={"base_url": "https://evil.invalid/v1",
                      "model": "other", "api_key": "new"}).status_code == 403


def test_admin_intake_and_input_readers_do_not_save_session(tmp_path):
    from web_support import h5ad
    with multi_clients(tmp_path) as (service, alice, bob, admin):
        sid = alice.post("/api/sessions", json={}).json()["id"]
        data = alice.post("/api/sessions/" + sid + "/uploads",
                          files={"file": ("synthetic.h5ad", h5ad(tmp_path))}).json()
        aid = data["uploads"][0]["id"]
        path = service.directory(sid) / "session.json"
        original = path.read_bytes()
        def contents():
            return {str(item.relative_to(path.parent)): item.read_bytes()
                    for item in path.parent.rglob("*") if item.is_file()}
        original_tree = contents()
        assert admin.get("/api/admin/sessions/" + sid + "/intake", params={"upload_id": aid}).status_code == 200
        for _ in range(3):
            assert admin.get("/api/admin/sessions/" + sid + "/analysis-inputs").status_code == 200
        assert path.read_bytes() == original
        assert contents() == original_tree


def test_admin_original_protocol_is_registered_and_integrity_checked(tmp_path):
    import hashlib
    from bridge.web.sessions import write_file
    from web_support import h5ad
    with multi_clients(tmp_path) as (service, alice, bob, admin):
        sid = alice.post("/api/sessions", json={}).json()["id"]
        aid = alice.post("/api/sessions/" + sid + "/uploads",
                         files={"file": ("synthetic.h5ad", h5ad(tmp_path))}).json()["uploads"][0]["id"]
        pid = "a" * 32
        body = b"Synthetic protocol for a test."
        state = service.load(sid)
        state["_intake_autofill"][aid]["protocols"].append({"id": pid, "name": "protocol.txt",
                         "size": len(body), "sha256": hashlib.sha256(body).hexdigest()})
        write_file(service.directory(sid) / "intake-protocols" / (pid + ".bin"), body)
        service.sessions.save(state)
        path = "/api/admin/sessions/" + sid + "/protocols/" + pid
        assert admin.get(path).content == body
        assert bob.get(path).status_code == 403
