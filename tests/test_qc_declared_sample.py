"""A declared sample column does not establish biological replication."""
from __future__ import annotations

import pandas as pd
import pytest

from bridge.tool_packages.p0_01_input_qc.io import build_declared_lineage
from bridge.toolkit.contracts import InputAsset


@pytest.mark.parametrize("values,declared,has_sample", [
    (["sample-a", "sample-a"], True, True),
    (["sample-a", "sample-b"], True, False),
    (["sample-a", None], True, False),
    (["sample-a", "sample-a"], False, False),
])
def test_single_declared_sample_is_bound_without_inventing_lineage(tmp_path, values, declared, has_sample):
    asset = InputAsset(asset_id="query", path=tmp_path / "query.h5ad", format="h5ad",
        input_level="count_ready", matrix_location="X", matrix_semantics="raw_counts",
        assay="scRNA-seq", metadata={"sample_id_column": "sample_id"} if declared else {})
    output = build_declared_lineage(asset=asset,
        observations=pd.DataFrame({"sample_id": values}, index=["obs-a", "obs-b"]),
        qc_capture_groups=None, input_hash="a" * 64, run_id="run-query",
        tool_version="0.1.6", input_level="count_ready")
    view = output.selected_data_view
    assert (view.sample_or_preparation_ref is not None) is has_sample
    if has_sample:
        assert view.sample_or_preparation_ref.startswith("sample:declared-")
        assert "sample-a" not in view.sample_or_preparation_ref
    assert view.n_observations == 2
    assert view.biological_unit_manifest_ref is None
    assert view.biological_unit_manifest_sha256 is None
    assert output.manifest is None and output.assignment_artifact is None
    assert output.reason_codes == ("biological_unit_lineage_metadata_missing",)
