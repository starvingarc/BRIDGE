"""Loopback preflight and lifecycle shared by checkout, module and wheel entry."""
from contextlib import contextmanager
from dataclasses import replace
import errno
import fcntl
import hmac
import json
import os
from pathlib import Path
import secrets
import socket
import stat
import threading
import time

from bridge import __version__
from bridge.storage.private_paths import configure_trusted_ancestors, ensure_private_directory
from .runtime import (STORAGE_LOCK_FILE,
                      settings_from_environment, validate_runtime_configuration)

PID_FILE = ".bridge-web.pid.json"
DEFAULT_PORTS = {"production": 8765, "acceptance": 8766, "development": 8767}


def public_error(exc):
    messages = {
        "invalid_server_configuration": "启动配置无效；请检查 URL、开关和数值范围；诊断仅限 development",
        "retired_auth_configuration": "旧口令登录已移除；请删除 BRIDGE_WEB_TOKEN 和 BRIDGE_WEB_MULTI_USER，并初始化账号存储",
        "multiuser_storage_not_ready": "账号存储尚未就绪；请先使用 account_admin initialize 初始化独立存储，旧会话不会自动迁移",
        "invalid_port": "端口必须是 1–65535 的整数",
        "port_unavailable": "本机端口不可用；服务未启动",
        "static_unavailable": "缺少 frontend/dist/index.html 构建产物；安装包需配置 BRIDGE_WEB_STATIC_DIR",
        "storage_busy": "会话存储正被另一个 BRIDGE 启动进程使用",
        "retired_storage_binding": "旧存储绑定选项已退役；请初始化独立账号存储，旧会话不会自动迁移",
        "storage_environment_mismatch": "会话存储环境不匹配",
        "instance_unavailable": "未找到可验证的运行实例；未发送进程信号",
        "stop_timeout": "停止请求已接受，但尚未确认退出",
    }
    return messages.get(str(exc), "启动失败：私有配置、存储或实例控制不可用")


@contextmanager
def storage_lock(root):
    fd = os.open(root / STORAGE_LOCK_FILE, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
            raise ValueError("storage_busy")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("storage_busy") from None
        yield
    finally:
        os.close(fd)


def read_instance(root):
    try:
        fd = os.open(root / PID_FILE, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o600 or info.st_size > 4096:
                raise ValueError("instance_unavailable")
            with os.fdopen(fd, "r", closefd=False) as stream:
                value = json.load(stream)
            if (type(value.get("pid")) is not int or value["pid"] <= 0
                or type(value.get("control_port")) is not int or not 1 <= value["control_port"] <= 65535
                or not isinstance(value.get("nonce"), str) or len(value["nonce"]) != 64):
                raise ValueError("instance_unavailable")
            return value
        finally:
            os.close(fd)
    except (OSError, ValueError, AttributeError):
        raise ValueError("instance_unavailable") from None


def control(root, environment, command):
    record = read_instance(root)
    if record.get("environment") != environment:
        raise ValueError("instance_unavailable")
    try:
        with socket.create_connection(("127.0.0.1", record["control_port"]), timeout=2) as connection:
            connection.sendall(json.dumps({"command": command, "nonce": record["nonce"]}).encode() + b"\n")
            reply = json.loads(connection.recv(4096))
        if reply.get("pid") != record["pid"] or not hmac.compare_digest(reply.get("nonce", ""), record["nonce"]):
            raise ValueError("instance_unavailable")
    except (OSError, ValueError, TypeError, AttributeError):
        raise ValueError("instance_unavailable") from None
    if command == "status":
        print(json.dumps({key: reply[key] for key in ("pid", "environment", "port", "state")}))
        return 0
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            with storage_lock(root):
                print("BRIDGE instance stopped")
                return 0
        except ValueError as exc:
            if str(exc) != "storage_busy":
                raise
        time.sleep(0.05)
    raise ValueError("stop_timeout")


@contextmanager
def instance_control(root, environment, port, server):
    # Only a caller holding the storage lock may publish or replace stale metadata.
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(4)
        listener.settimeout(0.2)
        record = dict(pid=os.getpid(), environment=environment, port=port,
                      control_port=listener.getsockname()[1], nonce=secrets.token_hex(32))
        path = root / PID_FILE
        # Never follow an old metadata symlink. Atomic replace owns only this filename.
        temporary = root / (PID_FILE + "." + record["nonce"])
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "w") as stream:
            json.dump(record, stream)
        os.replace(temporary, path)
        done = threading.Event()

        def listen():
            while not done.is_set():
                try:
                    connection, _ = listener.accept()
                except socket.timeout:
                    continue
                except OSError:
                    return
                with connection:
                    connection.settimeout(0.5)
                    try:
                        request = json.loads(connection.recv(4096))
                        if (request.get("command") not in ("status", "stop")
                            or not hmac.compare_digest(request.get("nonce", ""), record["nonce"])):
                            continue
                        reply = {**record, "state": "running" if server.started else "starting"}
                        connection.sendall(json.dumps(reply).encode())
                        if request["command"] == "stop":
                            server.should_exit = True
                    except (OSError, ValueError, TypeError, AttributeError):
                        continue

        thread = threading.Thread(target=listen, name="bridge-web-control", daemon=True)
        thread.start()
        try:
            yield
        finally:
            done.set()
            thread.join(timeout=1)
            # Lock is still held, so another launcher cannot have replaced the record.
            path.unlink(missing_ok=True)


def run(options, checkout):
    environment = "acceptance" if options["test"] else options["env"] or os.environ.get("BRIDGE_RUNTIME_ENV", "production")
    validate_runtime_configuration(environment, False)
    os.environ["BRIDGE_RUNTIME_ENV"] = environment
    state = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state")))
    default_storage = state / "bridge" / ("web" if environment == "production" else environment + "/web")
    root = default_storage if options["test"] else Path(os.environ.get("BRIDGE_START_STORAGE") or default_storage)
    if not root.is_absolute():
        raise ValueError("invalid_server_configuration")
    pins = json.loads(os.environ.get("BRIDGE_WEB_TRUSTED_ANCESTORS", "{}"))
    if not isinstance(pins, dict):
        raise ValueError("invalid_server_configuration")
    if pins:
        configure_trusted_ancestors({Path(path): tuple(identity) for path, identity in pins.items()})
    if options["command"] != "serve":
        if not root.is_dir():
            raise ValueError("instance_unavailable")
        root, _, _ = ensure_private_directory(root)
        return control(root, environment, options["command"])
    if options["bind_existing_storage"]:
        raise ValueError("retired_storage_binding")
    raw_port = options["port"] if options["port"] is not None else (str(DEFAULT_PORTS["acceptance"]) if options["test"]
                                  else os.environ.get("BRIDGE_WEB_PORT", str(DEFAULT_PORTS[environment])))
    if not raw_port.isascii() or not raw_port.isdigit() or len(raw_port) > 5 or not 1 <= int(raw_port) <= 65535:
        raise ValueError("invalid_port")
    port = int(raw_port)
    if not checkout and not Path(os.environ.get("BRIDGE_WEB_STATIC_DIR", "")).is_absolute():
        raise ValueError("static_unavailable")
    static = checkout / "frontend/dist" if checkout else Path(os.environ["BRIDGE_WEB_STATIC_DIR"])
    public_origin = os.environ.get("BRIDGE_WEB_PUBLIC_ORIGIN")
    if public_origin:
        if options["test"] or options.get("origin") or not os.environ.get("BRIDGE_START_STORAGE"):
            raise ValueError("invalid_server_configuration")
    if options.get("origin") and environment != "development":
        raise ValueError("invalid_server_configuration")
    os.environ.update(BRIDGE_WEB_STORAGE=str(root), BRIDGE_WEB_STATIC_DIR=str(static),
                      BRIDGE_WEB_ORIGIN=public_origin or options.get("origin") or f"http://127.0.0.1:{port}", BRIDGE_WEB_PORT=str(port))
    settings = settings_from_environment()
    if not (static / "index.html").is_file() or not (static / "index.html").stat().st_size:
        raise ValueError("static_unavailable")
    import uvicorn
    from .app import create_app
    with socket.socket() as web_socket:
        try:
            web_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                web_socket.bind(("127.0.0.1", port))
            except OSError as exc:
                if exc.errno != errno.EADDRINUSE or options["port"] is not None or public_origin:
                    raise
                # Let the OS choose while retaining the socket through server startup.
                web_socket.bind(("127.0.0.1", 0))
            web_socket.listen(128)
        except OSError:
            raise ValueError("port_unavailable") from None
        port = web_socket.getsockname()[1]
        origin = public_origin or options.get("origin") or f"http://127.0.0.1:{port}"
        os.environ.update(BRIDGE_WEB_PORT=str(port), BRIDGE_WEB_ORIGIN=origin)
        settings = replace(settings, origin=origin)
        root, _, _ = ensure_private_directory(root)
        with storage_lock(root):
            app = create_app(settings)
            server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port,
                                    access_log=False, log_level="warning", proxy_headers=False, reload=False))
            with instance_control(root, environment, port, server):
                label = {"development": "开发", "acceptance": "测试", "production": "生产"}[environment]
                display_url = public_origin or f"http://127.0.0.1:{port}"
                print(f"\nBRIDGE {__version__} · {label}\n  {display_url}\n  Ctrl+C 退出\n", flush=True)
                server.run(sockets=[web_socket])
            return 0 if server.started else 1
