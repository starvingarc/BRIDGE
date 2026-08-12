from __future__ import annotations

import json
from importlib.resources import as_file, files
from pathlib import Path

import pytest
import yaml

from bridge.tool_packages.p0_02_cell_state.benchmark_cli import main as benchmark_main
from bridge.tool_packages.p0_02_cell_state.external_source import (
    ExternalSourceAuditError,
    audit_external_source_lineage,
)


def _packaged_lineage_map():
    return files("bridge.tool_packages.p0_02_cell_state.resources").joinpath(
        "external_source_lineage.yaml"
    )


def test_packaged_external_source_lineage_audit_passes(tmp_path: Path) -> None:
    with as_file(_packaged_lineage_map()) as lineage_map:
        first = audit_external_source_lineage(lineage_map, tmp_path / "first.json")
        second = audit_external_source_lineage(lineage_map, tmp_path / "second.json")

    assert first == second
    assert first["status"] == "passed"
    assert first["external_holdout_roots"] == ["GSE192405", "GSE76381"]
    assert first["prohibited_overlap_count"] == 0
    assert first["asset_count"] >= 20
    assert first["candidate_decisions"]["REF-LAMANNO-2016-v1"] == "excluded_from_candidate"
    assert first["candidate_decisions"]["Q-GSE76381-ES-v1"] == "excluded_from_candidate"
    assert first["candidate_decisions"]["Q-GSE76381-IPS-v1"] == "excluded_from_candidate"
    assert (tmp_path / "first.json").read_bytes() == (tmp_path / "second.json").read_bytes()
    assert "/data" not in (tmp_path / "first.json").read_text()


def test_external_source_lineage_audit_rejects_transitive_fit_overlap(tmp_path: Path) -> None:
    with as_file(_packaged_lineage_map()) as lineage_map:
        payload = yaml.safe_load(lineage_map.read_text(encoding="utf-8"))
    lamanno = next(
        asset for asset in payload["assets"] if asset["asset_id"] == "REF-LAMANNO-2016-v1"
    )
    lamanno["candidate_decision"] = "development_reference"
    altered = tmp_path / "altered.yaml"
    altered.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    with pytest.raises(
        ExternalSourceAuditError,
        match="external_source_lineage_overlap:REF-LAMANNO-2016-v1:GSE76381",
    ):
        audit_external_source_lineage(altered, tmp_path / "audit.json")


def test_external_source_lineage_cli_writes_public_audit(tmp_path: Path, capsys) -> None:
    output = tmp_path / "audit.json"
    with as_file(_packaged_lineage_map()) as lineage_map:
        exit_code = benchmark_main(
            [
                "cell-state",
                "audit-external-sources",
                "--lineage-map",
                str(lineage_map),
                "--output",
                str(output),
            ]
        )

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out) == json.loads(output.read_text())
