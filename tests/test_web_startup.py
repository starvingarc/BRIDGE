from __future__ import annotations

import json
import os
from pathlib import Path
import shlex
import socket
import subprocess
import sys
import time

import pytest
from urllib.error import URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
START = ROOT / "start.sh"
PASSWORD = "synthetic-account-password"
LOGIN = {"username": "operator", "password": PASSWORD}
KEY = "test-provider-secret-never-print"


def _initialize_state(state, environment="production", root=None):
    from bridge.web.account_admin import initialize
    root = root or state / "bridge" / ("web" if environment == "production" else environment + "/web")
    initialize(root, "operator", PASSWORD, environment)


def _env(config: Path, *, state: Path | None = None) -> dict[str, str]:
    env = {
        key: value for key, value in os.environ.items()
        if (
            not key.startswith("BRIDGE_WEB_")
            and not key.startswith("BRIDGE_START_")
            and key != "BRIDGE_RUNTIME_ENV"
        )
    }
    env["BRIDGE_START_CONFIG"] = str(config)
    if state is not None:
        env["XDG_STATE_HOME"] = str(state)
    return env


def _config(path: Path, *, port: int = 8765, extra: str = "") -> Path:
    settings = {
        "BRIDGE_START_PYTHON": sys.executable,
        "BRIDGE_WEB_MODEL_BASE_URL": "http://127.0.0.1:9/v1",
        "BRIDGE_WEB_MODEL": "test-model",
        "BRIDGE_WEB_MODEL_API_KEY": KEY,
        "BRIDGE_WEB_PORT": str(port),
    }
    path.write_text(
        "".join(f"{key}={shlex.quote(value)}\n" for key, value in settings.items()) + extra,
        encoding="utf-8",
    )
    path.chmod(0o600)
    return path


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_help_and_missing_private_config(tmp_path: Path) -> None:
    help_result = subprocess.run(
        [str(START), "--help"], cwd=tmp_path, capture_output=True, text=True, timeout=5,
    )
    assert help_result.returncode == 0
    assert "./start.sh" in help_result.stdout
    assert "BRIDGE_START_CONFIG" in help_result.stdout
    assert "--bind-existing-storage" in help_result.stdout

    missing = tmp_path / "not-created.env"
    result = subprocess.run(
        [str(START)], cwd=tmp_path, env=_env(missing),
        capture_output=True, text=True, timeout=5,
    )
    assert result.returncode != 0
    assert "配置" in result.stderr
    assert str(missing) in result.stderr


def test_refuses_config_readable_by_other_users(tmp_path: Path) -> None:
    config = _config(tmp_path / "public.env")
    config.chmod(0o644)
    result = subprocess.run(
        [str(START)], env=_env(config), capture_output=True, text=True, timeout=5,
    )
    assert result.returncode != 0
    assert "600" in result.stderr
    assert PASSWORD not in result.stdout + result.stderr
    assert KEY not in result.stdout + result.stderr


def test_reports_missing_frontend_build(tmp_path, monkeypatch):
    from bridge.web.launcher import run
    monkeypatch.setattr(os, "environ", os.environ.copy())
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    with pytest.raises(ValueError, match="static_unavailable"):
        run(dict(command="serve", env="production", test=False, port=None,
                 bind_existing_storage=False), tmp_path / "checkout")


def test_explicit_port_conflict_fails_without_starting(tmp_path: Path) -> None:
    with socket.socket() as occupied:
        occupied.bind(("127.0.0.1", 0))
        occupied.listen()
        port = occupied.getsockname()[1]
        config = _config(tmp_path / "private.env", port=port)
        state = tmp_path / "state"
        result = subprocess.run(
            [str(START), "--port", str(port)], env=_env(config, state=state),
            capture_output=True, text=True, timeout=10,
        )
    assert result.returncode != 0
    assert "端口" in result.stderr
    assert not (state / "bridge" / "web").exists()


def test_rejects_browser_diagnostics_outside_development_before_starting(
    tmp_path: Path,
) -> None:
    with socket.socket() as occupied:
        occupied.bind(("127.0.0.1", 0))
        occupied.listen()
        port = occupied.getsockname()[1]
        config = _config(
            tmp_path / "private.env",
            port=port,
            extra="BRIDGE_RUNTIME_ENV=acceptance\nBRIDGE_WEB_DIAGNOSTICS=1\n",
        )
        state = tmp_path / "state"
        result = subprocess.run(
            [str(START)], env=_env(config, state=state),
            capture_output=True, text=True, timeout=10,
        )
    assert result.returncode != 0
    assert "development" in result.stderr
    assert not (state / "bridge").exists()


@pytest.mark.parametrize("configured", [True, False])
def test_starts_from_any_directory_with_isolated_storage_and_private_login(tmp_path: Path, configured: bool) -> None:
    port = _free_port()
    legacy = tmp_path / "must-not-use-old-storage"
    config = _config(
        tmp_path / "private.env",
        port=port,
        extra=(
            f"BRIDGE_WEB_STORAGE={shlex.quote(str(legacy))}\n"
            "BRIDGE_RUNTIME_ENV=development\n"
            "BRIDGE_WEB_DIAGNOSTICS=1\n"
        ),
    )
    if not configured:
        config.write_text("\n".join(line for line in config.read_text().splitlines()
                                  if not line.startswith("BRIDGE_WEB_MODEL")) + "\n")
    state = tmp_path / "state"
    _initialize_state(state, "development")
    origin = f"http://127.0.0.1:{port}" if configured else "http://127.0.0.1:5173"
    process = subprocess.Popen(
        [str(START), "--origin", origin], cwd=tmp_path, env=_env(config, state=state),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if process.poll() is not None:
                break
            try:
                with urlopen(Request(base + "/api/health", headers={"Host": origin.split("://")[1]}), timeout=0.5) as response:
                    if json.load(response) == {"status": "ok"}:
                        break
            except (OSError, URLError):
                time.sleep(0.1)
        else:
            raise AssertionError("isolated service did not become healthy")
        assert process.poll() is None
        with urlopen(Request(base + "/", headers={"Host": origin.split("://")[1]}), timeout=3) as response:
            assert b"<html" in response.read().lower()
        request = Request(
            base + "/api/login",
            data=json.dumps(LOGIN).encode(),
            headers={"Content-Type": "application/json", "Origin": origin, "Host": origin.split("://")[1]},
        )
        with urlopen(request, timeout=3) as response:
            assert json.load(response)["authenticated"] is True
        storage = state / "bridge" / "development" / "web"
        assert storage.is_dir()
        assert json.loads(
            (storage / ".bridge-runtime-environment.json").read_text()
        )["runtime_environment"] == "development"
        assert not legacy.exists()
    finally:
        if process.poll() is None:
            process.terminate()
        stdout, stderr = process.communicate(timeout=10)
    assert "BRIDGE " in stdout
    assert "开发" in stdout
    assert base in stdout
    assert PASSWORD not in stdout + stderr
    assert KEY not in stdout + stderr



def test_config_parse_error_does_not_echo_secret(tmp_path: Path) -> None:
    config = tmp_path / "broken.env"
    config.write_text("BRIDGE_WEB_MODEL_API_KEY='SECRET_MUST_NOT_APPEAR\n", encoding="utf-8")
    config.chmod(0o600)
    result = subprocess.run(
        [str(START)], env=_env(config), capture_output=True, text=True, timeout=5,
    )
    assert result.returncode != 0
    assert "配置" in result.stderr
    assert "SECRET_MUST_NOT_APPEAR" not in result.stdout + result.stderr


def test_legacy_storage_cannot_bypass_account_initialization(tmp_path: Path) -> None:
    port = _free_port()
    storage = tmp_path / "legacy-state"
    storage.mkdir(mode=0o700)
    original = storage / "existing-record"
    original.write_bytes(b"unchanged")
    original.chmod(0o600)
    config = _config(
        tmp_path / "legacy.env",
        port=port,
        extra=f"BRIDGE_START_STORAGE={shlex.quote(str(storage))}\n",
    )

    refused = subprocess.Popen(
        [str(START)], env=_env(config),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    deadline = time.monotonic() + 12
    while time.monotonic() < deadline and refused.poll() is None:
        time.sleep(0.1)
    unexpectedly_running = refused.poll() is None
    if unexpectedly_running:
        refused.terminate()
    _, refused_stderr = refused.communicate(timeout=10)
    assert not unexpectedly_running
    assert refused.returncode != 0
    assert "账号存储" in refused_stderr
    assert not (storage / ".bridge-runtime-environment.json").exists()

    result = subprocess.run([str(START), "--bind-existing-storage"], env=_env(config),
                            capture_output=True, text=True, timeout=15)
    assert result.returncode != 0
    assert "账号存储" in result.stderr
    assert original.read_bytes() == b"unchanged"


@pytest.mark.parametrize("same_port", [True, False])
def test_second_launch_cannot_share_session_storage(tmp_path: Path, same_port: bool) -> None:
    port = _free_port()
    other_port = port if same_port else _free_port()
    state = tmp_path / "state"
    _initialize_state(state)
    first_config = _config(tmp_path / "first.env", port=port)
    second_config = _config(tmp_path / "second.env", port=other_port)
    first = subprocess.Popen(
        [str(START)], env=_env(first_config, state=state),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    try:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if first.poll() is not None:
                raise AssertionError("first isolated service exited before second launch")
            try:
                with urlopen(f"http://127.0.0.1:{port}/api/health", timeout=0.5) as response:
                    if json.load(response) == {"status": "ok"}:
                        break
            except (OSError, URLError):
                time.sleep(0.1)
        else:
            raise AssertionError("first isolated service did not become healthy")
        second = subprocess.run(
            [str(START)], env=_env(second_config, state=state),
            capture_output=True, text=True, timeout=10,
        )
        assert second.returncode != 0
        assert "存储" in second.stderr
        assert first.poll() is None
    finally:
        if first.poll() is None:
            first.terminate()
        first.communicate(timeout=10)


def test_storage_preflight_uses_approved_ancestor_pins(tmp_path: Path) -> None:
    foreign = next(
        (path for path in Path.home().parents
         if path.stat().st_uid not in {0, os.geteuid()}),
        None,
    )
    if foreign is None:
        import pytest
        pytest.skip("no controlled non-root ancestor on this host")
    import tempfile
    identity = foreign.stat()
    pins = json.dumps({str(foreign): [identity.st_uid, identity.st_dev, identity.st_ino]})
    port = _free_port()
    config = _config(
        tmp_path / "pinned.env", port=port,
        extra=f"BRIDGE_WEB_TRUSTED_ANCESTORS={shlex.quote(pins)}\n",
    )
    with tempfile.TemporaryDirectory(prefix="bridge-start-test-", dir=Path.home()) as parent:
        subprocess.run([sys.executable, "-m", "bridge.web.account_admin", "--config", str(config),
                        "initialize", "--root", str(Path(parent) / "bridge/web"), "--username", "operator",
                        "--environment", "production", "--password-stdin"], input=PASSWORD,
                       capture_output=True, text=True, check=True, timeout=15, env=_env(config))
        process = subprocess.Popen(
            [str(START)], env=_env(config, state=Path(parent)),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        try:
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    break
                try:
                    with urlopen(f"http://127.0.0.1:{port}/api/health", timeout=0.5) as response:
                        if json.load(response) == {"status": "ok"}:
                            break
                except (OSError, URLError):
                    time.sleep(0.1)
            assert process.poll() is None, "service with approved ancestor pin did not start"
        finally:
            if process.poll() is None:
                process.terminate()
            process.communicate(timeout=10)

@pytest.mark.parametrize("args", [
    ["--help", "unexpected"], ["--bind-existing-storage", "unexpected"],
    ["--config"], ["--test", "--env", "production"],
    ["--bind-existing-storage", "--typo"],
])
def test_rejects_extra_or_conflicting_arguments(tmp_path, args):
    config = _config(tmp_path / "args.env")
    result = subprocess.run([str(START), *args], env=_env(config),
                            capture_output=True, text=True, timeout=10)
    assert result.returncode != 0


@pytest.mark.parametrize("port", ["", "0", "65536", "-1", "1.5", "secret-value"])
def test_cli_rejects_invalid_port_before_storage(tmp_path, port):
    config = _config(tmp_path / "port.env")
    state = tmp_path / "state"
    result = subprocess.run([str(START), "--port", port], env=_env(config, state=state),
                            capture_output=True, text=True, timeout=10)
    assert result.returncode != 0
    assert not state.exists()


def test_config_symlink_is_rejected(tmp_path):
    config = _config(tmp_path / "real.env")
    link = tmp_path / "link.env"
    link.symlink_to(config)
    result = subprocess.run([str(START), "--config", str(link)],
                            env=_env(config), capture_output=True, text=True, timeout=10)
    assert result.returncode != 0
    assert PASSWORD not in result.stdout + result.stderr


def test_version_without_private_configuration(tmp_path):
    result = subprocess.run([str(START), "--print-version"],
                            env=_env(tmp_path / "missing"), capture_output=True,
                            text=True, timeout=10)
    assert result.returncode == 0
    assert "0.3.0" in result.stdout


def _wait_healthy(process, port):
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise AssertionError("service exited: " + process.communicate(timeout=2)[1])
        try:
            with urlopen(f"http://127.0.0.1:{port}/api/health", timeout=0.5) as response:
                if json.load(response) == {"status": "ok"}:
                    return
        except (OSError, URLError):
            time.sleep(0.1)
    raise AssertionError("service did not become healthy")


def test_acceptance_lifecycle_does_not_reuse_or_stop_production(tmp_path):
    production_port, acceptance_port = _free_port(), _free_port()
    production = tmp_path / "production"
    config = _config(tmp_path / "both.env", port=production_port,
                     extra=f"BRIDGE_START_STORAGE={shlex.quote(str(production))}\n")
    _initialize_state(tmp_path / "state", root=production)
    _initialize_state(tmp_path / "state", "acceptance")
    env = _env(config, state=tmp_path / "state")
    processes = []
    try:
        first = subprocess.Popen([str(START)], env=env, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True)
        processes.append(first)
        _wait_healthy(first, production_port)
        second = subprocess.Popen([sys.executable, "-m", "bridge.web", "--test",
                                   "--port", str(acceptance_port)],
                                  env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        processes.append(second)
        _wait_healthy(second, acceptance_port)
        acceptance = tmp_path / "state/bridge/acceptance/web"
        first_pid = json.loads((production / ".bridge-web.pid.json").read_text())
        second_pid = json.loads((acceptance / ".bridge-web.pid.json").read_text())
        assert first_pid["pid"] == first.pid
        assert second_pid["pid"] == second.pid
        assert first_pid["nonce"] != second_pid["nonce"]
        assert (acceptance / ".bridge-web.pid.json").stat().st_mode & 0o777 == 0o600
        status = subprocess.run([str(START), "--test", "status"], env=env,
                                capture_output=True, text=True, timeout=10)
        assert status.returncode == 0, status.stderr
        public = json.loads(status.stdout)
        assert public == dict(pid=second.pid, environment="acceptance", port=acceptance_port, state="running")
        assert second_pid["nonce"] not in status.stdout
        stopped = subprocess.run([str(START), "--test", "stop"], env=env,
                                 capture_output=True, text=True, timeout=15)
        assert stopped.returncode == 0, stopped.stderr
        second.wait(timeout=5)
        assert second.returncode == 0
        assert not (acceptance / ".bridge-web.pid.json").exists()
        _wait_healthy(first, production_port)
        assert production.is_dir()
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
            process.communicate(timeout=10)


def test_test_flag_defaults_ignore_configured_port_and_storage(tmp_path, monkeypatch):
    from bridge.web import launcher
    monkeypatch.setattr(os, "environ", os.environ.copy())
    import socket as socket_module
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("BRIDGE_START_STORAGE", str(tmp_path / "production"))
    monkeypatch.setenv("BRIDGE_WEB_PORT", "12345")
    observed = []
    class ReservedPort:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def setsockopt(self, *args): pass
        def bind(self, address):
            observed.append(address)
            raise OSError("occupied")
    monkeypatch.setattr(socket_module, "socket", ReservedPort)
    with pytest.raises(ValueError, match="port_unavailable"):
        launcher.run(dict(command="serve", test=True, env=None, port=None,
                          bind_existing_storage=False), ROOT)
    assert observed == [("127.0.0.1", 8766)]
    assert os.environ["BRIDGE_WEB_STORAGE"] == str(tmp_path / "state/bridge/acceptance/web")
    assert not (tmp_path / "production").exists()


def test_stop_with_stale_pid_never_signals_an_unrelated_process(tmp_path):
    from bridge.web.launcher import PID_FILE
    from bridge.web.runtime import bind_storage_environment
    storage = tmp_path / "private"
    bind_storage_environment(storage, "production")
    unrelated = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        (storage / PID_FILE).write_text(json.dumps(dict(
            pid=unrelated.pid, environment="production", port=1,
            control_port=_free_port(), nonce="a" * 64)))
        (storage / PID_FILE).chmod(0o600)
        config = _config(tmp_path / "stale.env",
                         extra=f"BRIDGE_START_STORAGE={shlex.quote(str(storage))}\n")
        result = subprocess.run([str(START), "stop"], env=_env(config),
                                capture_output=True, text=True, timeout=10)
        assert result.returncode != 0
        assert unrelated.poll() is None
    finally:
        unrelated.terminate()
        unrelated.wait(timeout=5)


def test_interpreter_priority(tmp_path, monkeypatch):
    from bridge.web.__main__ import select_python
    venv = tmp_path / ".venv/bin/python"
    venv.parent.mkdir(parents=True)
    venv.touch(mode=0o700)
    assert select_python(tmp_path, {"BRIDGE_START_PYTHON": sys.executable}) == sys.executable
    assert select_python(tmp_path, {}) == str(venv)
    venv.unlink()
    assert select_python(None, {}) == sys.executable


def test_config_is_sourced_once_with_export_semantics(tmp_path):
    marker = tmp_path / "loaded"
    config = _config(tmp_path / "once.env", extra=f"echo loaded >> {shlex.quote(str(marker))}\n")
    result = subprocess.run([str(START), "--port", "0"], env=_env(config),
                            capture_output=True, text=True, timeout=10)
    assert result.returncode != 0
    assert marker.read_text() == "loaded\n"


@pytest.mark.parametrize("setting", [
    "BRIDGE_WEB_TOKEN=short",
    "BRIDGE_WEB_MODEL_BASE_URL='https://provider.invalid/?secret=canary'",
    "BRIDGE_WEB_MAX_UPLOAD_BYTES=unlimited",
    "BRIDGE_WEB_SHARE_RESULT_SUMMARIES=true",
    "BRIDGE_RUNTIME_ENV=other",
])
def test_module_and_shell_share_fail_closed_preflight(tmp_path, setting):
    config = _config(tmp_path / "invalid.env", extra=setting + "\n")
    env = _env(config, state=tmp_path / "state")
    results = [subprocess.run([*entry, "--config", str(config)], env=env,
                             capture_output=True, text=True, timeout=10)
               for entry in ([str(START)], [sys.executable, "-m", "bridge.web"])]
    assert all(result.returncode != 0 for result in results)
    assert results[0].stderr == results[1].stderr
    assert not (tmp_path / "state").exists()
    assert all("canary" not in result.stdout + result.stderr for result in results)


def test_explicit_interpreter_environment_overrides_shell_config(tmp_path):
    config = _config(tmp_path / "python.env", extra="BRIDGE_START_PYTHON=/missing/python\n")
    env = _env(config)
    env["BRIDGE_START_PYTHON"] = sys.executable
    result = subprocess.run([str(START), "--port", "0"], env=env,
                            capture_output=True, text=True, timeout=10)
    assert result.returncode != 0
    assert "端口" in result.stderr
    assert "Python" not in result.stderr


def test_control_rejects_wrong_nonce_without_stopping_server(tmp_path):
    from bridge.web.launcher import PID_FILE
    port = _free_port()
    config = _config(tmp_path / "control.env", port=port)
    state = tmp_path / "state"
    _initialize_state(state)
    process = subprocess.Popen([str(START)], env=_env(config, state=state),
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        _wait_healthy(process, port)
        record = json.loads((state / "bridge/web" / PID_FILE).read_text())
        with socket.create_connection(("127.0.0.1", record["control_port"]), timeout=2) as connection:
            connection.sendall(json.dumps(dict(command="stop", nonce="b" * 64)).encode())
            assert connection.recv(4096) == b""
        _wait_healthy(process, port)
    finally:
        process.terminate()
        process.communicate(timeout=10)


@pytest.mark.parametrize("static", [None, "", "."])
def test_installed_entry_requires_explicit_absolute_static_directory(tmp_path, monkeypatch, static):
    from bridge.web import launcher
    monkeypatch.setattr(os, "environ", os.environ.copy())
    monkeypatch.chdir(tmp_path)
    (tmp_path / "index.html").write_text("<html>must not serve working directory</html>")
    if static is None:
        monkeypatch.delenv("BRIDGE_WEB_STATIC_DIR", raising=False)
    else:
        monkeypatch.setenv("BRIDGE_WEB_STATIC_DIR", static)
    monkeypatch.setattr(socket, "socket", lambda: pytest.fail("port preflight reached before static rejection"))
    with pytest.raises(ValueError, match="static_unavailable"):
        launcher.run(dict(command="serve", env="production", test=False, port=None,
                          bind_existing_storage=False), None)


def test_checkout_bootstrap_uses_checkout_with_same_interpreter(tmp_path):
    config = _config(tmp_path / "same-interpreter.env")
    env = _env(config, state=tmp_path / "state")
    env.pop("PYTHONPATH", None)
    result = subprocess.run([sys.executable, str(ROOT / "src/bridge/web/__main__.py"),
                             "--port", "0"], env=env, cwd=tmp_path,
                            capture_output=True, text=True, timeout=10)
    assert result.returncode != 0
    assert "端口" in result.stderr
    assert not (tmp_path / "state").exists()


@pytest.mark.parametrize("environment, explicit_origin", [
    ("production", None), ("acceptance", None),
    ("development", "http://127.0.0.1:5173"),
])
def test_busy_preferred_port_selects_free_port_for_login_and_control(
    tmp_path, environment, explicit_origin,
):
    from bridge.web.launcher import PID_FILE
    with socket.socket() as occupied:
        occupied.bind(("127.0.0.1", 0))
        occupied.listen()
        preferred = occupied.getsockname()[1]
        config = _config(tmp_path / "auto.env", port=preferred,
                         extra=f"BRIDGE_RUNTIME_ENV={environment}\n")
        state = tmp_path / "state"
        _initialize_state(state, environment)
        env = _env(config, state=state)
        args = [str(START)]
        if explicit_origin:
            args += ["--origin", explicit_origin]
        process = subprocess.Popen(args, env=env, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True)
        storage = state / "bridge" / ("web" if environment == "production" else environment + "/web")
        try:
            deadline = time.monotonic() + 20
            while not (storage / PID_FILE).exists():
                assert process.poll() is None, process.communicate(timeout=2)[1]
                assert time.monotonic() < deadline, "instance metadata not published"
                time.sleep(0.1)
            port = json.loads((storage / PID_FILE).read_text())["port"]
            assert port != preferred
            base = f"http://127.0.0.1:{port}"
            origin = explicit_origin or base
            headers = {"Host": origin.split("://")[1], "Origin": origin}
            while True:
                try:
                    with urlopen(Request(base + "/api/health", headers=headers), timeout=0.5) as response:
                        assert json.load(response) == {"status": "ok"}
                    break
                except (OSError, URLError):
                    assert process.poll() is None
                    assert time.monotonic() < deadline
                    time.sleep(0.1)
            request = Request(base + "/api/login", data=json.dumps(LOGIN).encode(),
                              headers={**headers, "Content-Type": "application/json"})
            with urlopen(request, timeout=3) as response:
                assert json.load(response)["authenticated"] is True
            status = subprocess.run([str(START), "status"], env=env,
                                    capture_output=True, text=True, timeout=10)
            assert status.returncode == 0, status.stderr
            assert json.loads(status.stdout) == dict(
                pid=process.pid, environment=environment, port=port, state="running")
            stopped = subprocess.run([str(START), "stop"], env=env,
                                     capture_output=True, text=True, timeout=15)
            assert stopped.returncode == 0, stopped.stderr
            process.wait(timeout=5)
            assert process.returncode == 0
            assert not (storage / PID_FILE).exists()
            # The unrelated listener is still bound after the instance is stopped.
            assert occupied.getsockname()[1] == preferred
        finally:
            if process.poll() is None:
                process.terminate()
            stdout, stderr = process.communicate(timeout=10)
        assert base in stdout
        assert PASSWORD not in stdout + stderr
        assert KEY not in stdout + stderr


def test_account_launcher_keeps_public_origin_and_rejects_test_mode(tmp_path):
    from bridge.web.account_admin import initialize
    root = tmp_path / "account-store"
    password = "synthetic-account-password"
    initialize(root, "operator", password, "acceptance")
    port = _free_port()
    origin = "https://internal.invalid"
    config = _config(tmp_path / "accounts.env", port=port, extra=(
        "BRIDGE_RUNTIME_ENV=acceptance\n"
        f"BRIDGE_START_STORAGE={shlex.quote(str(root))}\n"
        f"BRIDGE_WEB_PUBLIC_ORIGIN={origin}\n"
    ))
    refusal = subprocess.run([str(START), "--test"], env=_env(config, state=tmp_path / "test-state"), capture_output=True, timeout=15)
    assert refusal.returncode != 0
    process = subprocess.Popen([str(START)], env=_env(config), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    headers = {"Host":"internal.invalid", "X-Forwarded-For":"192.168.50.10", "X-Forwarded-Proto":"https", "Origin":origin}
    try:
        deadline = time.monotonic()+20
        while time.monotonic()<deadline:
            assert process.poll() is None
            try:
                with urlopen(Request(f"http://127.0.0.1:{port}/api/auth/config", headers=headers),timeout=.5) as response:
                    assert json.load(response)["mode"] == "accounts"
                break
            except OSError: time.sleep(.1)
        else: raise AssertionError("account service did not start")
        with urlopen(Request(f"http://127.0.0.1:{port}/api/login",data=json.dumps({"username":"operator","password":password}).encode(),
                             headers={**headers,"Content-Type":"application/json"}),timeout=3) as response:
            assert "Secure" in response.headers["Set-Cookie"]
        control = subprocess.run([str(START),"status"],env=_env(config),capture_output=True,text=True,timeout=10)
        assert control.returncode == 0
        assert json.loads(control.stdout)["port"] == port
    finally:
        process.terminate()
        output, errors = process.communicate(timeout=15)
    assert origin in output
    assert password not in output+errors


def test_uninitialized_start_can_be_initialized_and_retried(tmp_path):
    port = _free_port()
    state = tmp_path / "state"
    storage = state / "bridge/web"
    config = _config(tmp_path / "first-start.env", port=port)
    env = _env(config, state=state)
    refused = subprocess.run([str(START)], env=env, capture_output=True, text=True, timeout=15)
    assert refused.returncode != 0 and "账号存储" in refused.stderr
    assert not (storage / ".bridge-runtime-environment.json").exists()
    _initialize_state(state)
    process = subprocess.Popen([str(START)], env=env, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True)
    try:
        _wait_healthy(process, port)
        request = Request(f"http://127.0.0.1:{port}/api/login", data=json.dumps(LOGIN).encode(),
                          headers={"Content-Type": "application/json", "Origin": f"http://127.0.0.1:{port}"})
        with urlopen(request, timeout=3) as response:
            assert json.load(response)["authenticated"] is True
    finally:
        if process.poll() is None:
            process.terminate()
        process.communicate(timeout=10)
