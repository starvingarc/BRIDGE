import hashlib
import json

import anndata as ad
import numpy as np
import pandas as pd
import pytest

from bridge.web.spatial_reference import load_spatial_reference, read_spatial_section


def fixture(tmp_path):
    path = tmp_path / 'reference.h5ad'
    data = ad.AnnData(obs=pd.DataFrame({'cell_type': pd.Categorical(['X', 'Y', 'X']),
                                      'capture': ['one', 'one', 'two']}, index=['a', 'b', 'c']))
    data.obsm['spatial'] = np.array([[1., 3.], [2., 4.], [6., 9.]])
    data.write_h5ad(path)
    value = dict(version='1', reference_id='synthetic', vocabulary_version='spatial:1',
                 data_root=str(tmp_path), file='reference.h5ad', sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                 coordinate_key='spatial', type_column='cell_type', capture_column='capture',
                 types=['X', 'Y'], stage='synthetic stage',
                 crosswalk=dict(version='1', product_vocabulary_version='product:1',
                                spatial_vocabulary_version='spatial:1', entries=[]))
    manifest = tmp_path / 'manifest.json'
    manifest.write_text(json.dumps(value))
    return manifest, value


def test_reference_coordinates_and_full_counts(tmp_path):
    path, _ = fixture(tmp_path)
    ref = load_spatial_reference(path)
    section = read_spatial_section(ref, ref.sections[0]['id'])
    assert section['points'] == [[1., 3., 0], [2., 4., 1]]
    assert section['counts'] == {'X': 1, 'Y': 1}
    assert section['n_observations'] == 2
    assert section['coordinate_convention'] == 'image_y_down'
    assert 'observation_id' not in str(section)


def test_capture_does_not_invent_slice_order(tmp_path):
    path, _ = fixture(tmp_path)
    ref = load_spatial_reference(path)
    assert [s['label'] for s in ref.sections] == ['one', 'two']
    assert all(s['kind'] == 'capture' for s in ref.sections)
    assert not any('slice_order' in s for s in ref.sections)


def test_zero_in_section_differs_from_missing_mapping(tmp_path):
    path, _ = fixture(tmp_path)
    ref = load_spatial_reference(path)
    section = read_spatial_section(ref, ref.sections[1]['id'])
    assert section['counts']['Y'] == 0
    assert ref.manifest.crosswalk.entries == []


@pytest.mark.parametrize('change', ['hash', 'path', 'field', 'vocabulary', 'coordinate'])
def test_rejects_changed_file_and_untrusted_path(tmp_path, change):
    path, value = fixture(tmp_path)
    if change == 'hash':
        value['sha256'] = 'a' * 64
    elif change == 'path':
        value['file'] = '../outside.h5ad'
    elif change == 'field':
        value['type_column'] = 'missing'
    elif change == 'vocabulary':
        value['crosswalk']['spatial_vocabulary_version'] = 'old'
    else:
        import h5py
        with h5py.File(tmp_path / value['file'], 'r+') as f:
            f['obsm/spatial'][0, 0] = float('nan')
        value['sha256'] = hashlib.sha256((tmp_path / value['file']).read_bytes()).hexdigest()
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError):
        load_spatial_reference(path)


def test_section_id_is_not_a_path(tmp_path):
    path, _ = fixture(tmp_path)
    ref = load_spatial_reference(path)
    with pytest.raises(ValueError, match='section'):
        read_spatial_section(ref, '../reference.h5ad')
