from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _run_cli(*args: str):
    env = os.environ.copy()
    src_path = str(ROOT / "src")
    env["PYTHONPATH"] = src_path if not env.get("PYTHONPATH") else src_path + os.pathsep + env["PYTHONPATH"]
    return subprocess.run(
        [sys.executable, "-m", "bridge", *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_cli_help():
    result = _run_cli("--help")
    assert result.returncode == 0
    assert "bridge" in result.stdout


def test_cli_identity_dry_run():
    result = _run_cli("identity", "run", "--config", "configs/bridge.minimal.yaml", "--dry-run")
    assert result.returncode == 0
    assert '"workflow": "identity"' in result.stdout


def test_cli_cls_dry_run():
    result = _run_cli("cls", "run", "--config", "configs/bridge.minimal.yaml", "--dry-run")
    assert result.returncode == 0
    assert '"workflow": "cls"' in result.stdout


def test_cli_report_dry_run():
    result = _run_cli("report", "summarize", "--config", "tests/data/report_fixture.yaml", "--dry-run")
    assert result.returncode == 0
    assert '"workflow": "report"' in result.stdout
