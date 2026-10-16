from __future__ import annotations

import numpy as np
import pytest
import anndata
from datetime import datetime, timezone

from bridge.tool_packages.p0_03_target_regional.exploratory_runtime import _scores_for_profile
from bridge.tool_packages.p0_03_target_regional.exploratory_runtime import _load_whole_view
from bridge.tool_packages.p0_03_target_regional.exploratory_models import ReferenceSimilarityExploratoryInput
from bridge.tool_packages.p0_03_target_regional.method_runtime import TargetRegionalMethodError
from bridge.tool_packages._configurable_contracts import observation_ids_sha256
from bridge.toolkit.contracts import InputAsset


def test_constant_query_is_unavailable_not_zero_correlation():
    records = _scores_for_profile(
        query=np.array([1.0, 1.0, 1.0]),
        query_genes=np.array(["A", "B", "C"]),
        reference=np.array([[1.0, 2.0, 3.0]]),
        metadata={"genes": ["A", "B", "C"], "rows": [{"label": "L1"}]},
        profile_id="PROFILE-TEST", source_id="SOURCE-TEST",
        source_family_id="FAMILY-TEST", label_level="L1",
        minimum_shared_genes=3,
    )
    assert len(records) == 1
    assert records[0].state == "unavailable"
    assert records[0].spearman is None
    assert records[0].cosine is None
    assert records[0].reason_codes == ["constant_query_vector"]


def test_shared_gene_shortfall_is_unavailable_not_negative_evidence():
    records = _scores_for_profile(
        query=np.array([1.0, 2.0, 3.0]),
        query_genes=np.array(["A", "B", "C"]),
        reference=np.array([[1.0, 2.0, 3.0]]),
        metadata={"genes": ["A", "B", "X"], "rows": [{"label": "L1"}]},
        profile_id="PROFILE-TEST", source_id="SOURCE-TEST",
        source_family_id="FAMILY-TEST", label_level="L1",
        minimum_shared_genes=3,
    )
    assert records[0].state == "unavailable"
    assert records[0].reason_codes == ["insufficient_shared_genes"]
    assert records[0].shared_genes == 2


def test_label_scores_and_margin_use_original_reference_labels():
    records = _scores_for_profile(
        query=np.array([1.0, 2.0, 3.0]),
        query_genes=np.array(["A", "B", "C"]),
        reference=np.array([[1.0, 2.0, 3.0], [3.0, 2.0, 1.0]]),
        metadata={"genes": ["A", "B", "C"], "rows": [
            {"label": "state:A"}, {"label": "state:B"}
        ]},
        profile_id="PROFILE-TEST", source_id="SOURCE-TEST",
        source_family_id="FAMILY-TEST", label_level="L1",
        minimum_shared_genes=3,
    )
    by_label = {record.label: record for record in records}
    assert set(by_label) == {"state:A", "state:B"}
    assert by_label["state:A"].spearman == pytest.approx(1.0)
    assert by_label["state:B"].spearman == pytest.approx(-1.0)
    assert by_label["state:A"].top_label == "state:A"
    assert by_label["state:A"].margin == pytest.approx(2.0)


def test_zero_query_and_constant_reference_are_unavailable():
    zero = _scores_for_profile(
        query=np.array([0.0, 0.0, 0.0]),
        query_genes=np.array(["A", "B", "C"]),
        reference=np.array([[1.0, 2.0, 3.0]]),
        metadata={"genes": ["A", "B", "C"], "rows": [{"label": "L1"}]},
        profile_id="PROFILE-TEST", source_id="SOURCE-TEST",
        source_family_id="FAMILY-TEST", label_level="L1",
        minimum_shared_genes=3,
    )
    assert zero[0].reason_codes == ["zero_query_vector"]
    assert zero[0].spearman is None
    constant_reference = _scores_for_profile(
        query=np.array([1.0, 2.0, 3.0]),
        query_genes=np.array(["A", "B", "C"]),
        reference=np.array([[4.0, 4.0, 4.0]]),
        metadata={"genes": ["A", "B", "C"], "rows": [{"label": "L1"}]},
        profile_id="PROFILE-TEST", source_id="SOURCE-TEST",
        source_family_id="FAMILY-TEST", label_level="L1",
        minimum_shared_genes=3,
    )
    assert constant_reference[0].reason_codes == ["constant_reference_vector"]
    assert constant_reference[0].cosine is None


def test_native_measurement_identity_is_bound_to_source_run():
    kwargs = dict(
        query=np.array([1.0, 2.0, 3.0]),
        query_genes=np.array(["A", "B", "C"]),
        reference=np.array([[1.0, 2.0, 3.0]]),
        metadata={"genes": ["A", "B", "C"], "rows": [{"label": "L1"}]},
        profile_id="PROFILE-TEST", source_id="SOURCE-TEST",
        source_family_id="FAMILY-TEST", label_level="L1",
        minimum_shared_genes=3,
    )
    first = _scores_for_profile(**kwargs, run_id="run-aaaa")
    second = _scores_for_profile(**kwargs, run_id="run-bbbb")
    assert first[0].measurement_id != second[0].measurement_id


def test_whole_view_sums_counts_before_cp10k_and_rejects_view_drift(tmp_path):
    path = tmp_path / "query.h5ad"
    adata = anndata.AnnData(X=np.array([[1, 2, 0], [3, 0, 4]], dtype=np.int64))
    adata.obs_names = ["cell-a", "cell-b"]
    adata.var_names = ["A", "B", "C"]
    adata.write_h5ad(path)
    asset = InputAsset(asset_id="asset:test", path=path, format="h5ad",
                       input_level="count_ready", checksum="0" * 64,
                       matrix_location="X", matrix_semantics="raw_counts",
                       assay="scRNA-seq")
    view = dict(view_id="data-view:test", view_kind="all_observations",
                artifact_id="artifact:test", sha256="0" * 64,
                parent_asset_id="asset:test", parent_asset_sha256="0" * 64,
                matrix_location="X", matrix_semantics="raw_counts",
                n_observations=2,
                observation_ids_sha256=observation_ids_sha256(["cell-a", "cell-b"]))
    source = ReferenceSimilarityExploratoryInput(
        object_version="0.1.0", input_id="input:test", data_view=view,
        profile_ids=["PROFILE-TEST"], created_at=datetime.now(timezone.utc))
    query, genes = _load_whole_view(asset, source)
    assert genes.tolist() == ["A", "B", "C"]
    assert query == pytest.approx(np.log1p([4000.0, 2000.0, 4000.0]))
    drifted = source.model_copy(update={"data_view": source.data_view.model_copy(
        update={"observation_ids_sha256": "f" * 64})})
    with pytest.raises(TargetRegionalMethodError, match="expression_view_observation_identity_mismatch"):
        _load_whole_view(asset, drifted)
