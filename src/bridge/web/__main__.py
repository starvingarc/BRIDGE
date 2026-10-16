"""Private Web CLI and stdlib-only checkout bootstrap."""
import argparse
import ast
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys


def checkout_root():
    root = Path(__file__).resolve().parents[3]
    return root if (root / "pyproject.toml").is_file() else None


def parser():
    result = argparse.ArgumentParser(
        prog="bridge-web", add_help=False,
        description="Private loopback Web service; ./start.sh delegates to this CLI.",
        epilog="Config: --config or BRIDGE_START_CONFIG, otherwise XDG_CONFIG_HOME/bridge/web.env.",
        allow_abbrev=False,
    )
    result.add_argument("command", nargs="?", choices=("serve", "status", "stop"), default="serve")
    result.add_argument("-h", "--help", action="store_true")
    result.add_argument("--print-version", action="store_true")
    result.add_argument("--config")
    result.add_argument("--env", choices=("development", "acceptance", "production"))
    result.add_argument("--test", action="store_true", help="isolated acceptance storage; prefer port 8766, otherwise a free port")
    result.add_argument("--origin", help="development browser origin (for Vite)")
    result.add_argument("--port", help="fixed loopback port (1–65535); fail if occupied")
    result.add_argument("--bind-existing-storage", action="store_true", help="retired; initialize account storage instead")
    return result


def load_config(path):
    """Source a trusted owner-only shell file through its verified descriptor."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        raise ValueError("找不到安全的私有配置：" + str(path)) from None
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o600:
            raise ValueError("配置必须由当前账号拥有、权限为 600，且不是符号链接")
        # All shell output, including xtrace and parse errors, stays private.
        completed = subprocess.run(
            ["/bin/bash", "-c",
             "set -a; source /dev/fd/" + str(fd) +
             " >/dev/null 2>&1; result=$?; set +x; test $result -eq 0 || exit 1; /usr/bin/env -0"],
            pass_fds=(fd,), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=15,
        )
        if completed.returncode:
            raise ValueError("私有配置格式有误；请检查语法")
        return dict(os.fsdecode(item).split("=", 1) for item in completed.stdout.split(b"\0") if b"=" in item)
    except subprocess.TimeoutExpired:
        raise ValueError("私有配置读取超时") from None
    finally:
        os.close(fd)


def select_python(root, environment):
    explicit = environment.get("BRIDGE_START_PYTHON")
    if explicit:
        candidate = shutil.which(explicit) if not os.path.isabs(explicit) else explicit
    elif root and (root / ".venv/bin/python").is_file():
        candidate = str(root / ".venv/bin/python")
    elif sys.version_info[:2] == (3, 12):
        candidate = sys.executable
    else:
        candidate = shutil.which("python3.12")
    if not candidate or not os.access(candidate, os.X_OK):
        raise ValueError("找不到可执行的 Python 3.12；请设置 BRIDGE_START_PYTHON")
    return candidate


def dispatch(options):
    try:
        if sys.version_info[:2] != (3, 12):
            raise ValueError("BRIDGE 需要 Python 3.12；请检查 BRIDGE_START_PYTHON")
        from bridge.web.launcher import run
        return run(options, checkout_root())
    except ImportError:
        print("当前 Python 缺少 BRIDGE Web 依赖；请安装 .[qc,web,evidence,process]", file=sys.stderr)
        return 1
    except (ValueError, TypeError, OSError) as exc:
        # Runtime exceptions can contain configuration values; only closed messages escape.
        from bridge.web.launcher import public_error
        print(public_error(exc), file=sys.stderr)
        return 1


def main(argv=None):
    arguments = parser()
    options = vars(arguments.parse_args(argv))
    if options["test"] and options["env"] not in (None, "acceptance"):
        arguments.error("--test requires --env acceptance")
    if options["help"]:
        arguments.print_help()
        return 0
    root = checkout_root()
    if options["print_version"]:
        # Works before config/dependencies, including the Python 3.8 bootstrap.
        tree = ast.parse((Path(__file__).parents[1] / "__init__.py").read_text())
        version = next(ast.literal_eval(node.value) for node in tree.body
                       if isinstance(node, ast.Assign)
                       and any(isinstance(t, ast.Name) and t.id == "__version__" for t in node.targets))
        print("BRIDGE " + version)
        return 0
    os.umask(0o077)
    try:
        config = Path(options["config"] or os.environ.get("BRIDGE_START_CONFIG") or
                      str(Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "bridge/web.env"))
        explicit_python = os.environ.get("BRIDGE_START_PYTHON")
        environment = load_config(config)
        if explicit_python:
            environment["BRIDGE_START_PYTHON"] = explicit_python
        target = select_python(root, environment)
        check = subprocess.run([target, "-c", "import sys; sys.exit(sys.version_info[:2] != (3, 12))"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
        if check.returncode:
            raise ValueError("BRIDGE 需要 Python 3.12；请检查 BRIDGE_START_PYTHON")
        if root:
            # Same-interpreter dispatch does not reread PYTHONPATH at runtime.
            sys.path.insert(0, str(root / "src"))
            environment["PYTHONPATH"] = str(root / "src") + (
                os.pathsep + environment["PYTHONPATH"] if environment.get("PYTHONPATH") else "")
        # Source exactly once, then exec the selected interpreter with the loaded environment.
        if os.path.abspath(target) != os.path.abspath(sys.executable):
            code = "import json,runpy,sys; entry=runpy.run_path(sys.argv[1]); sys.exit(entry['dispatch'](json.loads(sys.argv[2])))"
            os.execve(target, [target, "-c", code, str(Path(__file__).resolve()), json.dumps(options)], environment)
        os.environ.clear()
        os.environ.update(environment)
        return dispatch(options)
    except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
        print(str(exc) if isinstance(exc, ValueError) else "启动配置或解释器不可用", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
