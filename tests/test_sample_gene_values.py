"""Numerical contract for the complete gene view; fixtures are synthetic."""
import io
import numpy as np
import pandas as pd
import pytest
from anndata import AnnData
from scipy import sparse

from bridge.tool_packages._expression_contracts import ExplorationOptions
from bridge.tool_packages.p0_02_cell_state.expression import explore


@pytest.mark.parametrize("as_sparse", [True, False])
def test_gene_view_retains_normalized_all_genes_without_resampling(as_sparse):
    counts = np.array([[1, 1, 0, 0], [3, 1, 0, 0], [0, 2, 2, 0], [0, 0, 4, 0]])
    data = AnnData(sparse.csr_matrix(counts) if as_sparse else counts,
        obs=pd.DataFrame({"cluster": ["A", "A", "B", "B"]}, index=["c3", "c1", "c4", "c2"]),
        var=pd.DataFrame(index=["g2", "g1", "g3", "zero"]))
    data.obsm["xy"] = np.arange(8).reshape(4, 2).astype(float)
    result = explore(data, ExplorationOptions(group_key="cluster", embedding_key="xy"),
                     semantics="raw_counts", seed=0)
    assert hasattr(result, "expression"), "the same normalized matrix must feed gene viewing"
    from bridge.tool_packages.p0_02_cell_state.expression_store import gene_store_bytes
    import h5py
    with h5py.File(io.BytesIO(gene_store_bytes(result, input_sha256="a"*64)), "r") as store:
        assert store["gene_ids"].asstr()[:].tolist() == ["g2", "g1", "g3", "zero"]
        assert store["observation_ids"].asstr()[:].tolist() == ["c3", "c1", "c4", "c2"]
        assert store["groups"].asstr()[:].tolist() == ["A", "B"]
        assert store["group_counts"][:].tolist() == [2, 2]
        values = sparse.csc_matrix((store["data"][:], store["indices"][:], store["indptr"][:]), shape=(4,4))
        np.testing.assert_allclose(values[:,0].toarray().ravel(), [np.log1p(5000), np.log1p(7500), 0, 0], rtol=1e-6)
        np.testing.assert_allclose(store["mean_log1p"][:,0], [(np.log1p(5000)+np.log1p(7500))/2, 0], rtol=1e-6)
        np.testing.assert_allclose(store["fraction_expressing"][:,0], [1,0])
        np.testing.assert_allclose(store["fraction_expressing"][:,1], [1,.5])
        assert np.all(store["mean_log1p"][:,-1] == 0)
    np.testing.assert_array_equal(data.X.toarray() if sparse.issparse(data.X) else data.X, counts)


def test_single_group_retains_gene_values_without_inventing_markers():
    data = AnnData(sparse.csr_matrix([[1,1,0],[1,2,0],[2,1,0],[2,2,0]]),
        obs=pd.DataFrame({"group": ["A"]*4}, index=["a","b","c","d"]),
        var=pd.DataFrame(index=["G1","G2","ZERO"]))
    data.obsm["xy"] = np.zeros((4,2))
    result = explore(data, ExplorationOptions(group_key="group", embedding_key="xy"),
                     semantics="raw_counts", seed=0)
    assert result.marker_state == "insufficient_groups_or_cells" and result.markers.empty
    assert hasattr(result, "expression"), "unavailable ranking does not remove measured expression"
