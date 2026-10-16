from __future__ import annotations

import hashlib


import pytest
from web_support import client as client, new_session, registered_artifact, parquet_bytes


def test_registered_parquet_preview_is_literal_bounded_and_preserves_download(client, tmp_path):
    sid = new_session(client)["id"]
    original = parquet_bytes(
        tmp_path,
        "literal.parquet",
        {"metric": ["observed", "missing"], "value": [7, None]},
    )
    artifact = registered_artifact(client, sid, "literal.parquet", original)

    response = client.get(artifact["url"] + "/preview")

    assert response.status_code == 200
    assert response.json()["columns"] == ["metric", "value"]
    assert response.json()["rows"] == [["observed", 7], ["missing", None]]
    assert response.json()["total_rows"] == 2
    assert response.json()["total_columns"] == 2
    assert response.json()["truncated"] is False
    downloaded = client.get(artifact["url"])
    assert downloaded.content == original
    assert hashlib.sha256(downloaded.content).hexdigest() == hashlib.sha256(original).hexdigest()
    assert downloaded.headers["content-disposition"].startswith("attachment")


def test_parquet_preview_represents_an_empty_valid_table(client, tmp_path):
    import pyarrow as pa

    sid = new_session(client)["id"]
    artifact = registered_artifact(
        client,
        sid,
        "empty.parquet",
        parquet_bytes(
            tmp_path,
            "empty-source.parquet",
            {"metric": pa.array([], type=pa.string())},
        ),
    )
    response = client.get(artifact["url"] + "/preview")
    assert response.status_code == 200
    assert response.json() == {
        "columns": ["metric"],
        "rows": [],
        "total_rows": 0,
        "total_columns": 1,
        "truncated": False,
    }


def test_parquet_preview_keeps_scope_integrity_and_fixed_safe_errors(client, tmp_path):
    from bridge.web.sessions import write_file

    first = new_session(client)["id"]
    artifact = registered_artifact(
        client,
        first,
        "scoped.parquet",
        parquet_bytes(tmp_path, "scoped-source.parquet", {"value": [1]}),
    )
    second = client.post("/api/sessions").json()["id"]
    assert (
        client.get(f"/api/sessions/{second}/artifacts/{artifact['id']}/preview").status_code == 404
    )
    assert (
        client.get(f"/api/sessions/{first}/artifacts/" + "a" * 32 + "/preview").status_code == 404
    )

    service = client.app.state.service
    record = service.load(first)["_artifacts"][artifact["id"]]
    write_file(service.directory(first) / "artifacts" / record["file"], b"changed")
    drift = client.get(artifact["url"] + "/preview")
    assert drift.status_code == 409
    assert drift.json()["error_id"] == "request_failed"
    assert "detail" not in drift.json()

    unsupported = registered_artifact(client, first, "values.csv", b"metric,value\nobserved,7\n")
    unsupported_response = client.get(unsupported["url"] + "/preview")
    assert unsupported_response.status_code == 415
    assert unsupported_response.json()["error_id"] == "request_failed"
    assert "detail" not in unsupported_response.json()

    invalid = registered_artifact(
        client, first, "invalid.parquet", b"not a parquet or private path"
    )
    invalid_response = client.get(invalid["url"] + "/preview")
    assert invalid_response.status_code == 422
    assert invalid_response.json()["error_id"] == "request_failed"
    assert "detail" not in invalid_response.json()
    assert str(tmp_path) not in invalid_response.text


def test_parquet_preview_reports_row_column_and_cell_truncation(client, tmp_path):
    sid = new_session(client)["id"]
    wide = registered_artifact(
        client,
        sid,
        "wide.parquet",
        parquet_bytes(
            tmp_path,
            "wide-source.parquet",
            {f"column_{index}": list(range(101)) for index in range(25)},
        ),
    )
    response = client.get(wide["url"] + "/preview")
    assert response.status_code == 200
    assert response.json()["total_rows"] == 101
    assert response.json()["total_columns"] == 25
    assert len(response.json()["columns"]) == 24
    assert len(response.json()["rows"]) == 100
    assert response.json()["rows"][0] == [0] * 24
    assert response.json()["rows"][-1] == [99] * 24
    assert response.json()["truncated"] is True

    long_text = "x" * 1_050
    text_artifact = registered_artifact(
        client,
        sid,
        "long-text.parquet",
        parquet_bytes(tmp_path, "long-text-source.parquet", {"note": [long_text]}),
    )
    text_response = client.get(text_artifact["url"] + "/preview")
    displayed = text_response.json()["rows"][0][0]
    assert text_response.status_code == 200
    assert len(displayed) == 1_000
    assert displayed.endswith("… [truncated]")
    assert text_response.json()["truncated"] is True


def test_parquet_preview_preserves_scalars_and_rejects_binary_cells(client, tmp_path):
    import pyarrow as pa

    sid = new_session(client)["id"]
    scalar = registered_artifact(
        client,
        sid,
        "scalars.parquet",
        parquet_bytes(
            tmp_path,
            "scalars-source.parquet",
            {
                "number": [float("nan"), float("inf"), float("-inf")],
                "flag": [True, False, None],
            },
        ),
    )
    response = client.get(scalar["url"] + "/preview")
    assert response.status_code == 200
    assert response.json()["rows"] == [
        ["NaN", True],
        ["Infinity", False],
        ["-Infinity", None],
    ]

    binary = registered_artifact(
        client,
        sid,
        "binary.parquet",
        parquet_bytes(
            tmp_path,
            "binary-source.parquet",
            {"payload": pa.array([b"private bytes"], type=pa.binary())},
        ),
    )
    binary_response = client.get(binary["url"] + "/preview")
    assert binary_response.status_code == 422
    assert binary_response.json()["error_id"] == "request_failed"
    assert "detail" not in binary_response.json()


def test_parquet_preview_preserves_safe_boundaries_and_large_integers(client, tmp_path):
    import pyarrow as pa

    sid = new_session(client)["id"]
    artifact = registered_artifact(
        client,
        sid,
        "integers.parquet",
        parquet_bytes(
            tmp_path,
            "integers-source.parquet",
            {
                "signed": pa.array(
                    [
                        -9_007_199_254_740_991,
                        -9_007_199_254_740_992,
                        9_007_199_254_740_991,
                        9_007_199_254_740_993,
                    ],
                    type=pa.int64(),
                ),
                "unsigned": pa.array(
                    [
                        0,
                        9_007_199_254_740_991,
                        9_007_199_254_740_992,
                        18_446_744_073_709_551_615,
                    ],
                    type=pa.uint64(),
                ),
            },
        ),
    )

    response = client.get(artifact["url"] + "/preview")

    assert response.status_code == 200
    assert response.json()["rows"] == [
        [-9_007_199_254_740_991, 0],
        ["-9007199254740992", 9_007_199_254_740_991],
        [9_007_199_254_740_991, "9007199254740992"],
        ["9007199254740993", "18446744073709551615"],
    ]


def test_parquet_preview_preserves_large_integral_float64(client, tmp_path):
    import pyarrow as pa

    sid = new_session(client)["id"]
    artifact = registered_artifact(
        client,
        sid,
        "large-floats.parquet",
        parquet_bytes(
            tmp_path,
            "large-floats-source.parquet",
            {
                "float64": pa.array(
                    [1e20, -1e20, 1.25],
                    type=pa.float64(),
                ),
            },
        ),
    )

    response = client.get(artifact["url"] + "/preview")

    assert response.status_code == 200
    assert response.json()["rows"] == [
        ["1e+20"],
        ["-1e+20"],
        [1.25],
    ]


def test_parquet_decode_releases_service_lock_before_batch_parsing(client, tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
    from threading import Event
    from bridge.web import http as web_app

    preview_sid = new_session(client)["id"]
    control_sid = client.post("/api/sessions").json()["id"]
    artifact = registered_artifact(
        client,
        preview_sid,
        "paused.parquet",
        parquet_bytes(tmp_path, "paused-source.parquet", {"value": [1]}),
    )
    real_preview = web_app.parquet_preview
    entered, release = Event(), Event()

    def paused_preview(data):
        entered.set()
        assert release.wait(10)
        return real_preview(data)

    monkeypatch.setattr(web_app, "parquet_preview", paused_preview)
    control_finished_before_release = False
    control_future = None
    with ThreadPoolExecutor(max_workers=2) as pool:
        preview_future = pool.submit(client.get, artifact["url"] + "/preview")
        try:
            if not entered.wait(5):
                pytest.fail("preview decoder was not entered")
            control_future = pool.submit(client.post, f"/api/sessions/{control_sid}/stop", json={})
            try:
                control_response = control_future.result(timeout=1)
                control_finished_before_release = True
            except FutureTimeout:
                control_response = None
        finally:
            release.set()
        preview_response = preview_future.result(timeout=5)
        if control_future is not None and control_response is None:
            control_response = control_future.result(timeout=5)

    assert control_finished_before_release is True
    assert control_response.status_code == 200
    assert control_response.json()["id"] == control_sid
    assert preview_response.status_code == 200
    assert preview_response.json()["rows"] == [[1]]


def test_parquet_preview_rejects_stored_row_group_and_response_limits(client, tmp_path):
    sid = new_session(client)["id"]
    oversized = registered_artifact(
        client,
        sid,
        "oversized.parquet",
        b"PAR1" + b"0" * (8 * 1024 * 1024) + b"PAR1",
    )
    oversized_response = client.get(oversized["url"] + "/preview")
    assert oversized_response.status_code == 413
    assert oversized_response.json()["error_id"] == "request_failed"
    assert "detail" not in oversized_response.json()

    large_group = registered_artifact(
        client,
        sid,
        "large-group.parquet",
        parquet_bytes(
            tmp_path,
            "large-group-source.parquet",
            {"text": ["x" * (33 * 1024 * 1024)]},
            compression="gzip",
            use_dictionary=False,
        ),
    )
    assert len(client.get(large_group["url"]).content) < 8 * 1024 * 1024
    large_group_response = client.get(large_group["url"] + "/preview")
    assert large_group_response.status_code == 413
    assert large_group_response.json()["error_id"] == "request_failed"
    assert "detail" not in large_group_response.json()

    response_heavy = registered_artifact(
        client,
        sid,
        "response-heavy.parquet",
        parquet_bytes(
            tmp_path,
            "response-heavy-source.parquet",
            {
                "first": [("a" * 998) + f"{index:02d}" for index in range(100)],
                "second": [("b" * 998) + f"{index:02d}" for index in range(100)],
                "third": [("c" * 998) + f"{index:02d}" for index in range(100)],
            },
            compression="gzip",
            use_dictionary=False,
        ),
    )
    response_heavy_response = client.get(response_heavy["url"] + "/preview")
    assert response_heavy_response.status_code == 413
    assert response_heavy_response.json()["error_id"] == "request_failed"
    assert "detail" not in response_heavy_response.json()


def test_unknown_artifacts_are_session_scoped(client, tmp_path):
    first = new_session(client)["id"]
    second = client.post("/api/sessions").json()["id"]
    assert client.get(f"/api/sessions/{second}/artifacts/{first}").status_code == 404
    assert client.get(f"/api/sessions/{first}/artifacts/%2e%2e%2fprivate").status_code == 404
