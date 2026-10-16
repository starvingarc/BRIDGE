from dataclasses import replace

import pytest

from web_support import client, new_session, registered_artifact
from test_spatial_link_data import source, crosswalk
from test_spatial_reference import fixture
from bridge.web.spatial_link_data import ProductLinkInput
from bridge.web.spatial_reference import load_spatial_reference
from bridge.web.spatial_context import build_spatial_context


def test_context_version_changes_with_crosswalk(tmp_path):
    import json
    path, value = fixture(tmp_path)
    value['crosswalk'] = crosswalk()
    path.write_text(json.dumps(value))
    first = build_spatial_context(ProductLinkInput.model_validate(source()), load_spatial_reference(path))
    value['crosswalk']['version'] = '2'
    path.write_text(json.dumps(value))
    second = build_spatial_context(ProductLinkInput.model_validate(source()), load_spatial_reference(path))
    assert first['context_id'] != second['context_id']
    assert first['kind'] == 'linked_cell_context'
    assert first['reference']['n_observations'] == 3
    assert 'data_root' not in str(first)
    assert str(tmp_path) not in str(first)


def test_linked_context_requires_access_and_canonical_receipts(client):
    sid = new_session(client)['id']
    artifact = registered_artifact(client, sid, 'expression_umap.json', b'{}')
    url = f'/api/sessions/{sid}/artifacts/{artifact["id"]}/spatial-context'
    # A filename alone never grants a source binding.
    assert client.get(url).status_code == 422
    other = new_session(client)['id']
    assert client.get(url.replace(sid, other)).status_code == 404
    client.cookies.clear()
    assert client.get(url).status_code == 401

def test_assessment_lists_missing_link_inputs_without_running_tools(client, tmp_path):
    from types import SimpleNamespace
    sid = new_session(client)['id']
    service = client.app.state.service
    service.settings = replace(service.settings, spatial_reference_manifest_path=tmp_path / 'configured.json')
    state = service.load(sid)
    scope = SimpleNamespace(binding={'data_view': {'view_id': 'same-view'}})
    allowed = SimpleNamespace(tool_id='P0-02', mode_id=None)
    before = len(state['_tool_runs'])
    assert service.scientific_inputs.spatial_link_gaps(state, scope, allowed) == [
        'spatial_link_candidate_analysis_required', 'spatial_link_expression_analysis_required']
    assert len(state['_tool_runs']) == before


def test_assessment_cell_explorer_rejects_stale_scope_and_other_session(client):
    sid = new_session(client)['id']
    url = f'/api/sessions/{sid}/assessment/cell-explorer'
    query = {'scope_digest': 'a' * 64, 'evidence_alias': 'E-bound-candidate'}
    assert client.get(url, params=query).status_code == 404
    service = client.app.state.service
    state = service.load(sid)
    # A stale digest is rejected before resolving any scientific source.
    state['_assessment'] = {'scope_digest': 'b' * 64}
    service.sessions.save(state)
    assert client.get(url, params=query).status_code == 409
    other = new_session(client)['id']
    assert client.get(url.replace(sid, other), params=query).status_code == 404
    client.cookies.clear()
    assert client.get(url, params=query).status_code == 401


def test_optional_reference_subtype_read_verifies_view_bytes_and_observation_order():
    import hashlib
    import json
    from io import BytesIO
    from types import SimpleNamespace
    import pandas as pd
    from bridge.web.spatial_context import SpatialContexts

    ids = ['a', 'b']
    data = pd.DataFrame({'observation_id':ids,'ref__top_label':['L2:RG_mFP',None],
        'l2_parent_state_id':['L1:Radial_Glia',None],
        'l2_support_state':['single_source_supported']*2,
        'l2_assignment_state':['shadow_candidate']*2,'l2_open_set_state':['not_assessed']*2})
    stream = BytesIO(); data.to_parquet(stream, index=False); raw = stream.getvalue()
    sha = hashlib.sha256(raw).hexdigest()
    assets = [dict(checksum='a'*64,metadata=dict(data_view_id='v',parent_asset_sha256='b'*64,qc_profile_ref='qc'))]
    run = dict(run_id='aux',execution_state='succeeded',tool_version='1',input_hash='a'*64,
        request=dict(tool_id='P0-02',measurement_spec_ref='CELLSTATE-scRNA-shadow-v0.1',assets=assets),
        result=dict(n_observations=2,source_support=dict(coverage=[dict(source_id='ref',label_level='L2',role='refinement',state='available')])),
        artifacts=[dict(kind='cell_state_evidence',path='evidence',sha256=sha)])
    profile = SimpleNamespace(auxiliary_state='available',auxiliary_run_ref='aux',input_sha256='a'*64,
        upstream_qc_profile_ref='qc',input_data_view=SimpleNamespace(view_id='v',parent_asset_sha256='b'*64,n_observations=2))
    receipt = dict(tool_version='1',request=dict(assets=assets))
    artifacts = {'aux':dict(kind='auxiliary_tool_run',sha256='c'*64)}
    def checked(state,path,expected):
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError('hash mismatch')
        return raw
    contexts = SpatialContexts(resolve_source=None,read_artifact=None,checked_bytes=checked,manifest_path=None)
    contexts._related_bytes = lambda *_: json.dumps(run).encode()
    result = contexts._reference_subtypes({}, {}, artifacts, receipt, profile, ids)
    assert result.rows[0].source_state_id == 'L2:RG_mFP'
    assert result.rows[1].source_state_id is None
    assert result.source_binding.evidence_sha256 == sha
    assert contexts._reference_subtypes({}, {}, artifacts, receipt, profile, list(reversed(ids))) is None
    run['artifacts'][0]['sha256'] = 'd'*64
    assert contexts._reference_subtypes({}, {}, artifacts, receipt, profile, ids) is None
    run['artifacts'][0]['sha256'] = sha
    profile.input_data_view.view_id = 'other'
    assert contexts._reference_subtypes({}, {}, artifacts, receipt, profile, ids) is None
    assert contexts._reference_subtypes({}, {}, {}, receipt, profile, ids) is None
