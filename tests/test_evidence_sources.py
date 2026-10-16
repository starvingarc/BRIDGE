"""Source-selection rules run without a web app, files, workers or a model."""
from copy import deepcopy
from types import SimpleNamespace

import pytest


def receipt(name, *, plan='old', sha=None, tool='P0-06', status='succeeded'):
    return {'file': name, 'sha256': sha or name, 'plan_id': plan,
            'tool_id': tool, 'state': status}


def output(row, **changes):
    return {'source': 'tool_output', 'producer_tool_id': row['tool_id'],
            'receipt_file': row['file'], 'receipt_sha256': row['sha256'],
            'schema_ref': 'profile', **changes}


def sources(records, receipts, *, invalidated=(), runs=None, values=None):
    from bridge.web.evidence_sources import EvidenceSources
    # In-memory adapters replace verified disk reads; selection itself is real.
    return EvidenceSources(records=records, receipts=receipts, invalidated=invalidated,
        read_producer=lambda row: runs[row['file']],
        verify=lambda record: (values or {}).get(record.get('schema_ref'), {}))


def test_assessment_orders_admissions_before_pins_and_excludes_unapproved_history():
    old, current, unrelated = receipt('pinned'), receipt('current', plan='now'), receipt('unrelated')
    records = {'pinned': output(old)}
    original = deepcopy(records)
    index = sources(records, [old, unrelated, current])
    selected = index.assessment_receipts(records, [{'plan_id': 'now', 'tool_id': 'P0-06'}])
    assert [row['file'] for row in selected] == ['current', 'pinned']
    assert records == original


@pytest.mark.parametrize('change', [
    {'receipt_sha256': 'wrong'}, {'producer_tool_id': 'P0-02'}, {'receipt_file': 'other'}])
def test_pin_requires_exact_receipt_identity(change):
    row = receipt('run')
    records = {'profile': output(row, **change)}
    assert sources(records, [row]).assessment_receipts(records, []) == []


@pytest.mark.parametrize('status,invalidated', [('failed', ()), ('succeeded', ('run',))])
def test_unusable_receipts_are_excluded_from_both_interpretation_and_report(status, invalidated):
    row = receipt('run', plan='now', status=status)
    records = {'profile': output(row)}
    index = sources(records, [row], invalidated=invalidated)
    assert index.assessment_receipts(records, [{'plan_id': 'now', 'tool_id': 'P0-06'}]) == []
    assert index.outputs(records, 'P0-06', 'profile') == []


def test_admission_cannot_authorize_another_tool():
    row = receipt('run', plan='now')
    index = sources({}, [row])
    with pytest.raises(ValueError, match='^assessment_producer_mismatch$'):
        index.assessment_receipts({}, [{'plan_id': 'now', 'tool_id': 'P0-02'}])


def test_report_outputs_select_content_bound_receipt_not_same_named_execution():
    old, new = receipt('old'), receipt('new')
    records = {'profile': output(old), 'wrong': output(new, receipt_sha256='wrong')}
    runs = {'old': SimpleNamespace(run_id='same-name', result={'value': 1}),
            'new': SimpleNamespace(run_id='same-name', result={'value': 2})}
    index = sources(records, [old, new], runs=runs, values={'profile': {'value': 1}})
    selected = index.outputs(records, 'P0-06', ('profile', 'other'))
    assert [(key, value, run.result) for key, value, run in selected] == [
        ('profile', {'value': 1}, {'value': 1})]


def test_pool_verification_failure_is_not_silently_dropped():
    from bridge.web.evidence_sources import EvidenceSources
    row = receipt('run', plan='now')
    records = {'profile': output(row)}
    def corrupted(record):
        raise ValueError('input_checksum_mismatch')
    index = EvidenceSources(records=records, receipts=[row], invalidated=(),
        read_producer=lambda row: SimpleNamespace(request=SimpleNamespace(object_inputs=[])),
        verify=corrupted)
    with pytest.raises(ValueError, match='^input_checksum_mismatch$'):
        index.pool({}, [{'plan_id': 'now', 'tool_id': 'P0-06'}])


def test_pinned_graph_restores_only_its_exact_legacy_producer_receipt():
    from types import SimpleNamespace
    from bridge.web.scientific_inputs import digest
    graph = {'source': 'tool_output', 'producer_tool_id': 'P0-09',
             'schema_ref': 'bridge://schemas/case-evidence-graph-manifest/v0.1',
             'receipt_file': 'graph.json', 'receipt_sha256': 'g'}
    bundle = {'sha256': 'b', 'schema_ref': 'bundle-schema', 'path': '/bundle'}
    native = {'source': 'tool_output', 'producer_tool_id': 'P0-06',
              'schema_ref': 'bridge://schemas/exploratory-process-profile/v0.1',
              'receipt_file': 'old.json', 'receipt_sha256': 'old'}
    newer = {**native, 'receipt_file': 'new.json', 'receipt_sha256': 'new'}
    state = {'_input_objects': {'graph': graph, 'bundle': bundle, 'old': native, 'new': newer},
        '_tool_runs': [{'file': name+'.json', 'sha256': sha, 'tool_id': tool, 'state': 'partial'}
                      for name, sha, tool in [('graph', 'g', 'P0-09'), ('old', 'old', 'P0-06'), ('new', 'new', 'P0-06')]],
        '_assessment': {'admissions': []}}
    compiled = {'old': {'execution': 'unavailable'}, 'new': {'execution': 'measured'}}
    catalog = {'object_catalog': [{'node_type': 'ToolRun', 'object_id': 'tool-run:legacy',
        'object_version': '0.11.0', 'content_hash': digest(compiled['old'])}]}
    verify = lambda record: catalog if record is bundle else {}
    def producer(receipt):
        tool = receipt['tool_id']
        if tool == 'P0-09':
            return SimpleNamespace(request=SimpleNamespace(object_inputs=[SimpleNamespace(
                role='compilation_bundle', input_id='bundle', sha256='b', schema_ref='bundle-schema', path='/bundle')]))
        return SimpleNamespace(run_id='legacy', tool_version='0.11.0',
            model_dump=lambda **kwargs: compiled[receipt['sha256']])
    from bridge.web.evidence_sources import EvidenceSources
    def selected(roots):
        return EvidenceSources(records=state['_input_objects'], receipts=state['_tool_runs'],
            invalidated=state.get('_invalidated_receipts', {}), read_producer=producer,
            verify=verify).pool(roots, [])
    roots = {'graph': graph, 'new': newer}
    pool = selected(roots)
    assert pool['old'] == native
    assert pool['new'] == newer
    graph_only = selected({'graph': graph})
    assert 'old' in graph_only and 'new' not in graph_only
    # The graph cannot authorize an arbitrary same-name receipt or revive one
    # that an explicit input change has invalidated.
    state['_invalidated_receipts'] = {'old.json': {}}
    assert 'old' not in selected(roots)


@pytest.mark.parametrize('tool,sha,reason', [
    ('P0-06', 'graph', 'canonical_source_producer_mismatch'),
    ('P0-09', 'different', 'canonical_graph_history_required'),
])
def test_graph_provenance_requires_the_exact_compiler_receipt(tool, sha, reason):
    row = receipt('graph', tool=tool, sha=sha)
    graph = output(receipt('graph', tool='P0-09'),
        schema_ref='bridge://schemas/case-evidence-graph-manifest/v0.1')
    index = sources({'graph': graph}, [row], runs={
        'graph': SimpleNamespace(request=SimpleNamespace(object_inputs=[]))})
    with pytest.raises(ValueError, match='^' + reason + '$'):
        index.pool({'graph': graph}, [])
