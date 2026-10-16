"""Synthetic engineering flow through actual registered QC/expression/candidate tools."""
from dataclasses import replace
import json

import anndata as ad
import numpy as np

from web_support import client, new_session, confirm_change
from test_cell_state_candidate_runtime import _rig
from test_web_intake import stage, stated_facts
from test_web_inputs import approve
from test_spatial_reference import fixture as spatial_fixture


def test_registered_tools_to_linked_context_and_stale_request(client, tmp_path, monkeypatch):
    request, _, _ = _rig(tmp_path, monkeypatch)
    data = ad.read_h5ad(request.assets[0].path)
    data.obs['sample_id'] = 'sample-a'
    data.obs['capture_id'] = 'capture-a'
    data.obs['group'] = ['one', 'one', 'two', 'two']
    data.obsm['X_umap'] = np.array([[0., 0.], [0., 1.], [2., 3.], [2., 4.]])
    path = tmp_path / 'product.h5ad'
    data.write_h5ad(path)
    sid = new_session(client)['id']
    url = f'/api/sessions/{sid}'
    aid = client.post(url + '/uploads', files={'file': ('product.h5ad', path.read_bytes())}).json()['uploads'][0]['id']
    declared = client.post(url + '/analysis-inputs/assets', json=dict(upload_id=aid, assay='scRNA-seq',
        matrix_location='X', matrix_semantics='raw_counts', input_level='count_ready',
        metadata={'sample_id_column': 'sample_id', 'capture_id_column': 'capture_id'}))
    confirm_change(client, sid, declared.json())
    confirm_change(client, sid, stage(client, sid, aid, stated_facts(
        source_family_id='source-family:synthetic-linked', sample_id_column='sample_id', capture_id_column='capture_id')))
    service = client.app.state.service
    service.settings = replace(service.settings,
        cell_state_measurement_spec_ref='CELLSTATE-scRNA-celltypist-candidate-v0.1',
        cell_state_candidate_runtime_ref='fixture-celltypist-v1')
    selection = dict(tool_id='P0-01', mode_id=None, asset_ids=[aid], object_inputs=[], measurement_spec_ref=None)
    assert client.post(url + '/analysis-inputs', json=selection).status_code == 200
    for tool in ['P0-01', 'P0-02']:
        if tool == 'P0-02':
            selection.update(tool_id='P0-02', measurement_spec_ref='CELLSTATE-scRNA-celltypist-candidate-v0.1')
            assert client.post(url + '/analysis-inputs', json=selection).status_code == 200
        response = client.post(url + '/prepare-analysis', json={'tool_id': tool})
        assert response.status_code == 200, response.json()
        assert approve(client, sid, response.json()['plan'])['plan']['status'] == 'completed'
    state = service.load(sid)
    record = next(r for r in state['_input_objects'].values()
                  if r['schema_ref'] == 'bridge://schemas/cell-state-candidate-profile/v1.0')
    profile = service.inputs.verify(state, record)
    selection.update(tool_id='P0-02', measurement_spec_ref='EXPRESSION-exploration-v0.1',
                     expression_analysis={'exploration': {'group_key': 'group', 'embedding_key': 'X_umap'}})
    saved = client.post(url + '/analysis-inputs', json=selection)
    assert saved.status_code == 200, saved.json()
    if saved.json().get('pending_input_change'):
        assert saved.json()['pending_input_change']['impact']['affected'] == []
        confirm_change(client, sid, saved.json())
    proposal = client.post(url + '/prepare-analysis', json={'tool_id': 'P0-02'})
    assert proposal.status_code == 200, proposal.json()
    outcome = approve(client, sid, proposal.json()['plan'])
    assert outcome['plan']['status'] == 'completed', outcome
    umap = next(a for a in outcome['artifacts'] if a['name'].startswith('expression_umap.') and a['media_type'] == 'application/json')
    link_url = url + '/artifacts/' + umap['id'] + '/spatial-context'
    missing = client.get(link_url)
    assert missing.status_code == 200, missing.text
    assert missing.json()['missing_reasons'] == ['spatial_reference_not_configured']
    manifest_path, manifest = spatial_fixture(tmp_path)
    manifest['crosswalk']['product_vocabulary_version'] = ('cell-state-development-review:'
        + profile['development_review_version'] + '@' + profile['development_review_sha256'])
    manifest['crosswalk']['entries'] = [dict(product_state_id=row['label'], spatial_type_id='X',
        relation='broader_type', review_state='reviewed', basis='Synthetic engineering fixture only')
        for row in profile['candidate_composition'] if row['assignment_state'] in {'candidate', 'parent_candidate'}]
    manifest_path.write_text(json.dumps(manifest))
    service.settings = replace(service.settings, spatial_reference_manifest_path=manifest_path)
    response = client.get(link_url)
    assert response.status_code == 200, response.text
    context = response.json()
    assert service.spatial_contexts.source_gaps(service.load(sid), profile['input_data_view']) == []
    assert context['state'] == 'available', context
    assert context['product']['n_observations'] == 4
    assert context['product']['qualified_assignment'] is False
    section_url = link_url + '/sections/' + context['reference']['sections'][0]['id']
    section = client.get(section_url, params={'context_id': context['context_id']})
    assert section.status_code == 200, section.text
    assert section.json()['counts'] == {'X': 1, 'Y': 1}
    assert not any(cell in response.text + section.text for cell in data.obs_names)

    # The composition card may reuse one same-view embedding without making that
    # exploratory receipt part of the scientific assessment or report snapshot.
    from copy import deepcopy
    from test_web_assessment import propose_scope
    scope = propose_scope(client, sid, aid, 'P0-02', None)
    cell_axis = next(axis for axis in scope['portrait'] if axis['id'] == 'cell_state')
    alias = cell_axis['evidence_aliases'][0]
    query = {'scope_digest': scope['scope_digest'], 'evidence_alias': alias}
    display_url = url + '/assessment/cell-explorer'
    before_display = deepcopy(service.load(sid)['_assessment'])
    runs_before_display = len(service.load(sid)['_tool_runs'])
    display_response = client.get(display_url, params=query)
    assert display_response.status_code == 200, display_response.text
    display = display_response.json()
    assert display['state'] == 'available', display
    assert display['umap_artifact_id'] == umap['id']
    assert len(display['binding_token']) == 64
    assert display['candidate_receipt_sha256'] == record['receipt_sha256']
    assert display['candidate_receipt_sha256'] == context['product']['sources'][1]['receipt_sha256']
    assert display['candidate_receipt_sha256'] != context['product']['sources'][0]['receipt_sha256']
    assert client.get(display_url, params=query).json() == display
    assert service.load(sid)['_assessment'] == before_display
    assert len(service.load(sid)['_tool_runs']) == runs_before_display

    original_resolver = service.spatial_contexts.resolve_source
    def no_large_plot_parse(state, artifact_id):
        assert artifact_id != umap['id'], 'The lookup must not parse the large UMAP payload'
        return original_resolver(state, artifact_id)
    with monkeypatch.context() as patch:
        patch.setattr(service.spatial_contexts, 'resolve_source', no_large_plot_parse)
        assert client.get(display_url, params=query).json() == display

    # The resolver owns the exact cross-run view/input match. These already-read
    # receipt projections differ while all counts and source registrations stay
    # unchanged; neither is allowed to supply the composition card's UMAP.
    for field in ('view_id', 'input_sha256'):
        def different_expression_source(state, artifact_id):
            resolved = original_resolver(state, artifact_id)
            if resolved[2]['request'].get('measurement_spec_ref') != 'EXPRESSION-exploration-v0.1':
                return resolved
            binding, artifacts, receipt, payload = deepcopy(resolved)
            if field == 'view_id':
                receipt['result']['input_data_view']['view_id'] = 'other-view-with-same-count'
            else:
                receipt['result']['input_sha256'] = '0' * 64
            return binding, artifacts, receipt, payload
        with monkeypatch.context() as patch:
            patch.setattr(service.spatial_contexts, 'resolve_source', different_expression_source)
            assert client.get(display_url, params=query).json() == {
                'state': 'unavailable', 'reason_code': 'cell_explorer_umap_missing'}


    from fastapi import HTTPException
    original_read = service.spatial_contexts.read_artifact
    def inaccessible_umap(state, artifact_id):
        if artifact_id == umap['id']:
            raise HTTPException(404, 'not_found')
        return original_read(state, artifact_id)
    with monkeypatch.context() as patch:
        patch.setattr(service.spatial_contexts, 'read_artifact', inaccessible_umap)
        assert client.get(display_url, params=query).json() == {
            'state': 'unavailable', 'reason_code': 'cell_explorer_umap_missing'}

    assert client.get(display_url, params={**query, 'scope_digest': '0' * 64}).status_code == 409
    rejected = client.get(display_url, params={**query, 'evidence_alias': 'E-unbound'})
    assert rejected.status_code == 200
    assert rejected.json() == {'state': 'unavailable', 'reason_code': 'cell_explorer_candidate_not_bound'}

    # Exact view and input bindings matter even when an unrelated display has
    # the same point count. Corrupt scope bindings cannot broaden the lookup.
    state = service.load(sid)
    original_scope = deepcopy(state['_assessment'])
    state['_assessment']['scope']['binding']['data_view']['view_id'] = 'another-view'
    service.sessions.save(state)
    assert client.get(display_url, params=query).json()['state'] == 'unavailable'
    state['_assessment'] = original_scope
    service.sessions.save(state)

    expression_binding = state['_canonical_artifacts'][umap['id']]
    state.setdefault('_invalidated_receipts', {})[expression_binding['receipt_file']] = {'reason': 'fixture_invalidated'}
    service.sessions.save(state)
    missing_display = client.get(display_url, params=query).json()
    assert missing_display == {'state': 'unavailable', 'reason_code': 'cell_explorer_umap_missing'}
    del state['_invalidated_receipts'][expression_binding['receipt_file']]
    service.sessions.save(state)

    # Multiple registered display IDs for one canonical source are ambiguous;
    # selecting the last session artifact would incorrectly succeed here.
    duplicate_id = 'f' * 32
    original_artifacts = deepcopy(state['artifacts'])
    duplicate_public = deepcopy(next(item for item in state['artifacts'] if item['id'] == umap['id']))
    duplicate_public['id'] = duplicate_id
    state['artifacts'].append(duplicate_public)
    state['_artifacts'][duplicate_id] = deepcopy(state['_artifacts'][umap['id']])
    state['_canonical_artifacts'][duplicate_id] = deepcopy(expression_binding)
    service.sessions.save(state)
    assert client.get(display_url, params=query).json() == {
        'state': 'unavailable', 'reason_code': 'cell_explorer_umap_ambiguous'}
    state['artifacts'] = original_artifacts
    del state['_artifacts'][duplicate_id]
    del state['_canonical_artifacts'][duplicate_id]
    service.sessions.save(state)
    assert client.get(display_url, params=query).json() == display

    runs_before = len(service.load(sid)['_tool_runs'])
    manifest['crosswalk']['version'] = 'updated'
    manifest_path.write_text(json.dumps(manifest))
    assert client.get(section_url, params={'context_id': context['context_id']}).status_code == 409
    assert len(service.load(sid)['_tool_runs']) == runs_before
    state = service.load(sid)
    receipt_name = state['_canonical_artifacts'][umap['id']]['receipt_file']
    state.setdefault('_invalidated_receipts', {})[receipt_name] = {'reason': 'fixture_invalidated'}
    service.sessions.save(state)
    assert client.get(link_url).status_code == 422
    del state['_invalidated_receipts'][receipt_name]
    service.sessions.save(state)
    # Source corruption remains an error even when requested through a saved URL.
    state = service.load(sid)
    state['_artifacts'][umap['id']]['source_sha256'] = '0' * 64
    service.sessions.save(state)
    assert client.get(link_url).status_code == 422
