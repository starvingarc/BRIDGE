from copy import deepcopy

import pytest

from bridge.web.spatial_link_data import (
    ProductLinkInput, TypeCrosswalk, build_product_link, ordered_observation_sha256,
)


def source():
    ids = ['cell-0', '2', 'cell-2']
    binding = dict(input_sha256='a' * 64, data_view_ref='view:v1',
                   ordered_observation_sha256=ordered_observation_sha256(ids),
                   producer_ref='run:expression', receipt_sha256='b' * 64)
    return dict(rows=[dict(observation_id=i, x=float(n), y=float(n + 1), cluster='c1')
                      for n, i in enumerate(ids)],
                plot_records=[dict(record_id='2', x=2., y=3., group='c1')],
                assignments=[dict(observation_id=i, assigned_state='A' if n < 2 else None,
                                  assignment_state='candidate' if n < 2 else 'unknown',
                                  qualified_assignment=False) for n, i in enumerate(ids)],
                coordinate_binding=binding,
                assignment_binding={**binding, 'producer_ref': 'run:candidate', 'receipt_sha256': 'c' * 64},
                product_vocabulary_version='product:1', spatial_vocabulary_version='spatial:1')


def crosswalk():
    return dict(version='1', product_vocabulary_version='product:1',
                spatial_vocabulary_version='spatial:1',
                entries=[dict(product_state_id='A', spatial_type_id='X', relation='same_type',
                              review_state='reviewed', basis='Synthetic fixture relation')])


def build(s=None, c=None):
    return build_product_link(ProductLinkInput.model_validate(s or source()),
                              TypeCrosswalk.model_validate(c or crosswalk()))


@pytest.mark.parametrize('key,value', [('input_sha256', 'd' * 64), ('data_view_ref', 'view:other'),
                                      ('ordered_observation_sha256', 'e' * 64)])
def test_rejects_wrong_view_or_order(key, value):
    s = source()
    s['assignment_binding'][key] = value
    with pytest.raises(ValueError, match='binding'):
        build(s)


@pytest.mark.parametrize('change', ['duplicate', 'missing', 'reorder'])
def test_rejects_invalid_observation_identity(change):
    s = source()
    if change == 'duplicate':
        s['assignments'][2]['observation_id'] = 'cell-0'
    elif change == 'missing':
        s['assignments'].pop()
    else:
        s['assignments'].reverse()
    with pytest.raises(ValueError, match='observation'):
        build(s)


def test_resolves_plot_index_through_full_table():
    result = build()
    assert result['records'][0]['type_id'] is None
    assert result['records'][0]['assignment_state'] == 'unknown'
    assert 'observation_id' not in str(result)


def test_mixed_group_preserves_unmatched():
    result = build()
    group = result['clusters'][0]
    assert group['matched_types'] == ['X']
    assert group['total'] == 3 and group['unmatched_count'] == 1
    assert group['composition'][0]['fraction'] == 2 / 3
    assert result['types'][0]['fraction'] == 2 / 3
    assert result['qualified_assignment'] is False


@pytest.mark.parametrize('state', ['pending', 'rejected'])
def test_unreviewed_crosswalk_does_not_match(state):
    c = crosswalk()
    c['entries'][0]['review_state'] = state
    assert build(c=c)['clusters'][0]['matched_types'] == []


def test_stale_crosswalk_rejected_and_broader_relation_preserved():
    c = crosswalk()
    c['product_vocabulary_version'] = 'old'
    with pytest.raises(ValueError, match='vocabulary'):
        build(c=c)
    c = crosswalk()
    c['entries'][0]['relation'] = 'broader_type'
    c['entries'].append(deepcopy(c['entries'][0]))
    result = build(c=c)
    assert result['types'][0]['matched_types'] == ['X']
    assert result['types'][0]['relations'][0]['relation'] == 'broader_type'


def test_plot_must_match_full_table_and_unknown_never_maps():
    s = source()
    s['plot_records'][0]['x'] = 9
    with pytest.raises(ValueError, match='plot'):
        build(s)
    s = source()
    s['assignments'][2]['assigned_state'] = 'A'
    assert build(s)['records'][0]['type_id'] is None


def test_unknown_and_unavailable_keep_separate_full_counts():
    s = source()
    s['assignments'][1].update(assigned_state=None, assignment_state='unavailable')
    result = build(s)
    assert result['unknown_count'] == 2
    assert result['unassigned_counts'] == {'unavailable': 1, 'unknown': 1}
    assert result['clusters'][0]['unmatched_count'] == 2


def test_reference_subtypes_preserve_primary_missing_and_parent_disagreement():
    s = source()
    s['assignments'][0]['assigned_state'] = 'L1:Radial_Glia'
    s['assignments'][1]['assigned_state'] = 'L1:Neuroblast'
    s['reference_subtypes'] = dict(
        source_binding={**s['coordinate_binding'], 'producer_ref': 'run:aux',
                        'source_id': 'synthetic-ref', 'evidence_sha256': 'd' * 64},
        rows=[dict(observation_id=row['observation_id'], source_state_id='L2:RG_mFP',
                   parent_state_id='L1:Radial_Glia') for row in s['rows']])
    result = build(s)
    assert result['reference_subtypes']['resolved_count'] == 1
    groups = {g['id']: g for g in result['reference_subtypes']['groups']}
    assert set(groups) == {'L2:RG_mFP', 'L1:Neuroblast'}
    assert sum(g['total'] for g in groups.values()) + result['unknown_count'] == 3
    assert all(g['matched_types'] == [] for g in groups.values())
    assert result['records'][0]['reference_subtype_id'] is None
    assert result['records'][0]['type_id'] is None
    assert result['unassigned_counts'] == {'unknown': 1}
    for key in ('input_sha256', 'data_view_ref', 'ordered_observation_sha256'):
        bad = deepcopy(s)
        bad['reference_subtypes']['source_binding'][key] = 'e' * 64
        assert 'reference_subtypes' not in build(bad)
    bad = deepcopy(s)
    bad['reference_subtypes']['rows'].reverse()
    assert 'reference_subtypes' not in build(bad)
