from __future__ import annotations

import importlib
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import matplotlib
import pytest

matplotlib.use("Agg")
from matplotlib import pyplot as plt

from bridge.toolkit.contracts import ToolPackageSpecV2, ToolRequestV2
from bridge.toolkit.registry import ToolRegistry


_EXPORT_MODULE = "bridge.tool_packages._figure_export"
_CALLER_MODULES = (
    "bridge.tool_packages.p0_07_product_comparison_stability.visualization",
    "bridge.tool_packages.p0_08_evidence_sufficiency.visualization",
    "bridge.tool_packages.p0_09_evidence_compiler.visualization",
    "bridge.tool_packages.p0_10_claim_verifier.visualization",
)


def _exporter():
    return importlib.import_module(_EXPORT_MODULE).render_figure_payloads


def test_import_does_not_choose_a_pyplot_backend() -> None:
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; "
                "import bridge.tool_packages._figure_export; "
                "assert 'matplotlib.pyplot' not in sys.modules"
            ),
        ],
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr


def test_real_figure_exports_preserve_formats_metadata_and_close() -> None:
    figure, axis = plt.subplots(figsize=(2, 1.5))
    number = figure.number
    axis.plot([0, 1], [1, 0])

    payloads = _exporter()(figure)

    assert {extension: media for extension, (media, _) in payloads.items()} == {
        "svg": "image/svg+xml",
        "png": "image/png",
        "pdf": "application/pdf",
    }
    svg = payloads["svg"][1]
    png = payloads["png"][1]
    pdf = payloads["pdf"][1]
    assert svg.startswith(b'<?xml version="1.0"')
    assert b"<dc:title>BRIDGE</dc:title>" in svg
    assert b"<dc:date>" not in svg
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    assert b"Software\x00BRIDGE" in png
    assert pdf.startswith(b"%PDF-")
    assert b"/Creator (BRIDGE)" in pdf
    assert b"/CreationDate" not in pdf
    assert b"/ModDate" not in pdf
    assert not plt.fignum_exists(number)


def test_real_figure_closes_when_export_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    figure = plt.figure()
    number = figure.number

    def fail_save(*args: object, **kwargs: object) -> None:
        raise RuntimeError("synthetic export failure")

    monkeypatch.setattr(figure, "savefig", fail_save)

    with pytest.raises(RuntimeError, match="synthetic export failure"):
        _exporter()(figure)

    assert not plt.fignum_exists(number)


@pytest.mark.parametrize("module_name", _CALLER_MODULES)
def test_caller_config_identity_includes_shared_export_source(
    module_name: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = importlib.import_module(module_name)
    args = (
        ("component:test", SimpleNamespace(family="Test Font", sha256="f" * 64))
        if module_name.endswith("p0_10_claim_verifier.visualization")
        else ("component:test",)
    )
    monkeypatch.setattr(module, "figure_export_source_sha256", lambda: "a" * 64)
    first = module._config_hash(*args)
    monkeypatch.setattr(module, "figure_export_source_sha256", lambda: "b" * 64)
    second = module._config_hash(*args)

    assert first != second


@pytest.mark.parametrize(
    ("tool_id", "version"),
    (
        ("P0-07", "0.4.1"),
        ("P0-08", "0.5.1"),
        ("P0-09", "0.5.1"),
        ("P0-10", "0.4.3"),
    ),
)
def test_figure_export_patch_versions_are_registered(
    tool_id: str,
    version: str,
) -> None:
    assert ToolRegistry.load_default().describe(tool_id).version == version


def _run_identity(
    tool_id: str,
    request: ToolRequestV2,
    spec: ToolPackageSpecV2,
) -> str:
    if tool_id == "P0-07":
        module = importlib.import_module(
            "bridge.tool_packages.p0_07_product_comparison_stability.adapter"
        )
        digest = module._input_hash(request, spec)
    elif tool_id == "P0-08":
        module = importlib.import_module(
            "bridge.tool_packages.p0_08_evidence_sufficiency.executor"
        )
        digest = module.canonical_input_hash(
            request=request,
            spec=spec,
            objects_by_input_id={},
        )
    elif tool_id == "P0-09":
        module = importlib.import_module(
            "bridge.tool_packages.p0_09_evidence_compiler.compiler"
        )
        digest = module.canonical_input_hash(
            request=request,
            spec=spec,
            objects_by_input_id={},
        )
    else:
        module = importlib.import_module(
            "bridge.tool_packages.p0_10_claim_verifier.adapter"
        )
        digest = module._input_hash(request, spec, "c" * 64)
    return f"run-{digest[:16]}"


@pytest.mark.parametrize(
    ("tool_id", "old_version", "new_version"),
    (
        ("P0-07", "0.4.0", "0.4.1"),
        ("P0-08", "0.5.0", "0.5.1"),
        ("P0-09", "0.4.1", "0.4.2"),
        ("P0-10", "0.4.0", "0.4.1"),
    ),
)
def test_patch_version_separates_run_identity_and_repeats_deterministically(
    tmp_path: Path,
    tool_id: str,
    old_version: str,
    new_version: str,
) -> None:
    current_spec = ToolRegistry.load_default().describe(tool_id)
    old_spec = current_spec.model_copy(update={"version": old_version})
    new_spec = current_spec.model_copy(update={"version": new_version})
    request = ToolRequestV2(
        request_id=f"request-{tool_id.lower()}",
        tool_id=tool_id,
        tool_version=new_version,
        output_dir=tmp_path,
    )
    old_request = request.model_copy(update={"tool_version": old_version})

    old_run_id = _run_identity(tool_id, old_request, old_spec)
    new_run_id = _run_identity(tool_id, request, new_spec)
    repeated_run_id = _run_identity(tool_id, request, new_spec)

    assert new_run_id != old_run_id
    assert tmp_path / new_run_id != tmp_path / old_run_id
    assert repeated_run_id == new_run_id
