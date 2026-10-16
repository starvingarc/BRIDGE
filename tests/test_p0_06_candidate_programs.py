"""Synthetic runtime contracts only; not signature or product validation."""
import hashlib
import json
import pytest

from bridge.toolkit.contracts import StructuredInputRef, ToolRequestV2
from bridge.toolkit.registry import ToolRegistry
from tests.test_p0_06_exploratory import _request as cycle_request


def request_for_programs(tmp_path, *, missing=False, policy='observed_subset'):
    original=cycle_request(tmp_path)
    cycle=json.loads(original.object_inputs[0].path.read_bytes())
    genes=[f'SPHASE{i}' for i in range(6)]+(['ABSENT'] if missing else [])
    resource=tmp_path/'synthetic-hallmark.json'
    resource.write_text(json.dumps({'HALLMARK_SYNTHETIC_ONLY':{
        'collection':'H','systematicName':'SYNTHETIC','geneSymbols':genes}}))
    source=dict(object_version='0.2.0', input_id='candidate:synthetic',
        source_family_id='synthetic-only',data_view=cycle['data_view'],
        gene_symbol_column=cycle['gene_symbol_column'],created_at=cycle['created_at'],
        resource=dict(resource_ref='fixture:synthetic-hallmark',resource_version='synthetic-1',
            source_family_id='synthetic-only',path=str(resource),
            sha256=hashlib.sha256(resource.read_bytes()).hexdigest(),
            source_url='https://example.org/synthetic-test-only',license_ref='synthetic-fixture',
            format='msigdb_hallmark_json'),
        programs=[dict(program_id='PROC-SYNTHETIC',source_gene_set='HALLMARK_SYNTHETIC_ONLY')],
        gene_coverage_policy=policy)
    path=tmp_path/'program-input.json'
    raw=json.dumps(source).encode();path.write_bytes(raw)
    ref=StructuredInputRef(input_id='programs',role='exploratory_program_input',
        schema_ref='bridge://schemas/exploratory-process-input/v0.2',object_version='0.2.0',
        path=path,sha256=hashlib.sha256(raw).hexdigest(),media_type='application/json')
    return ToolRequestV2(request_id='synthetic:programs',tool_id='P0-06',assets=original.assets,
        object_inputs=[ref],random_seed=0,output_dir=tmp_path/'program-output')


@pytest.mark.parametrize('missing,policy,expected',[
    (False,'complete_only','available'),(True,'observed_subset','available'),
    (True,'complete_only','not_assessed'),
])
def test_registered_programs_preserve_coverage_and_never_make_activation_fractions(tmp_path,missing,policy,expected):
    request=request_for_programs(tmp_path,missing=missing,policy=policy)
    run=ToolRegistry.load_default().run(request)
    assert run.execution_state.value in {'succeeded','partial'},run.reason_codes
    assert len(run.measurements)==2
    assert run.result['runtime_mode']=='exploratory_programs'
    assert run.result['independence_state']=='unknown'
    assert run.result['n_independent_replicates'] is None
    for row in run.result['program_summaries']:
        assert row['assessment_state']==expected
        assert row['declared_gene_count']==6+int(missing)
        assert row['observed_gene_count']==6
        assert row['missing_genes']==(['ABSENT'] if missing else [])
        assert (row['mean'] is None)==(expected=='not_assessed')
    assert all(m.domain_score is None and m.numerator is None and m.denominator is None for m in run.measurements)
    manifest = next(a for a in run.artifacts if a.kind == 'native_measurement_spec')
    contract = json.loads(manifest.path.read_bytes())
    assert contract['analysis_unit_kind'] == 'whole_view_technical_aggregate'
    assert contract['n_independent_biological_replicates'] is None
    assert 'path' not in contract['input_contract']['resource']
    for artifact in run.artifacts:
        assert hashlib.sha256(artifact.path.read_bytes()).hexdigest() == artifact.sha256
    native = [json.loads(a.path.read_bytes()) for a in run.artifacts if a.kind == 'measurement_result_v2']
    assert [m['raw_value'] for m in native] == [s['mean'] for s in run.result['program_summaries']]


def test_registered_programs_refuse_tampered_resource_before_computation(tmp_path):
    request=request_for_programs(tmp_path)
    (tmp_path/'synthetic-hallmark.json').write_text('{}')
    run=ToolRegistry.load_default().run(request)
    assert run.execution_state.value=='failed'
    assert 'program_resource_checksum_mismatch' in run.reason_codes
    assert not run.artifacts


def test_resource_coverage_policy_is_required(tmp_path):
    request = request_for_programs(tmp_path)
    ref = request.object_inputs[0]
    value = json.loads(ref.path.read_bytes())
    del value['gene_coverage_policy']
    raw = json.dumps(value).encode()
    ref.path.write_bytes(raw)
    request = request.model_copy(update={'object_inputs':[ref.model_copy(update={
        'sha256':hashlib.sha256(raw).hexdigest()})]})
    run = ToolRegistry.load_default().run(request)
    assert run.execution_state.value == 'failed'
    assert not run.artifacts


def directed_request(tmp_path, *, signed=True, policy='observed_subset'):
    request = request_for_programs(tmp_path)
    ref = request.object_inputs[0]
    source = json.loads(ref.path.read_bytes())
    resource = tmp_path / 'synthetic-directed.csv'
    # Deliberately synthetic identifiers: six observed, one absent, one unresolved.
    if signed:
        resource.write_text('ensembl_gene_id,gene_symbol,logFC\n' +
            ''.join(f'SOURCE{i},SPHASE{i},{-2 if i == 0 else 2}\n' for i in range(6)) +
            'SOURCE6,ABSENT,2\nSOURCE7,NA,2\n')
    else:
        resource.write_text('external_gene.x\n' + ''.join(f'SPHASE{i}\n' for i in range(6)))
    source.update(object_version='0.3.0', gene_coverage_policy=policy,
                  programs=[dict(program_id='PROC-SYNTHETIC', source_gene_set='SYNTHETIC')])
    source['resource'].update(path=str(resource), sha256=hashlib.sha256(resource.read_bytes()).hexdigest(),
        format='oflanagan_core_csv' if signed else 'hu_pluripotency_csv')
    raw = json.dumps(source).encode(); ref.path.write_bytes(raw)
    return request.model_copy(update={'object_inputs':[ref.model_copy(update={
        'role':'directed_program_input','schema_ref':'bridge://schemas/exploratory-process-input/v0.3',
        'object_version':'0.3.0','sha256':hashlib.sha256(raw).hexdigest()})]})


@pytest.mark.parametrize('signed,policy', [(True,'observed_subset'),(True,'complete_only'),(False,'observed_subset')])
def test_registered_directed_members_preserve_sign_unresolved_and_method_scope(tmp_path,signed,policy):
    run = ToolRegistry.load_default().run(directed_request(tmp_path,signed=signed,policy=policy))
    assert run.execution_state.value in {'succeeded','partial'}, run.reason_codes
    scanpy, ulm = run.result['program_summaries']
    assert ulm['declared_gene_count'] == (8 if signed else 6)
    assert ulm['observed_gene_count'] == 6
    assert ulm['missing_genes'] == (['ABSENT'] if signed else [])
    assert [m['source_member_id'] for m in ulm['unresolved_members']] == (['SOURCE7'] if signed else [])
    assert ulm['source_members'][0]['direction'] == (-1 if signed else 1)
    assert ulm['assessment_state'] == ('not_assessed' if policy=='complete_only' else 'available')
    if signed:
        assert scanpy['mean'] is None
        assert 'scanpy_signed_signature_not_supported' in scanpy['reason_codes']
        assert scanpy['scored_targets'] == []
    else:
        assert scanpy['mean'] is not None
    if ulm['assessment_state'] == 'available':
        assert len(ulm['scored_targets']) == 6
        assert ulm['scored_targets'][0]['direction'] == (-1 if signed else 1)
    assert run.result['n_independent_replicates'] is None
    assert all(m.domain_score is None for m in run.measurements)


def test_directed_ulm_uses_signs_not_absolute_weights(tmp_path):
    first = tmp_path / 'first'; first.mkdir()
    second = tmp_path / 'second'; second.mkdir()
    request = directed_request(first)
    inverted = directed_request(second)
    ref = inverted.object_inputs[0]
    source = json.loads(ref.path.read_bytes())
    resource = second / 'synthetic-directed.csv'
    import csv
    rows = list(csv.DictReader(resource.open()))
    with resource.open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=['ensembl_gene_id','gene_symbol','logFC'])
        writer.writeheader()
        writer.writerows({**r, 'logFC': -float(r['logFC'])} for r in rows)
    source['resource']['sha256'] = hashlib.sha256(resource.read_bytes()).hexdigest()
    raw = json.dumps(source).encode(); ref.path.write_bytes(raw)
    inverted = inverted.model_copy(update={'object_inputs':[ref.model_copy(update={'sha256':hashlib.sha256(raw).hexdigest()})]})
    registry = ToolRegistry.load_default()
    a, b = registry.run(request), registry.run(inverted)
    assert a.result['program_summaries'][1]['mean'] is not None
    assert b.result['program_summaries'][1]['mean'] == pytest.approx(-a.result['program_summaries'][1]['mean'])
    assert b.result['program_summaries'][1]['scored_targets_sha256'] != a.result['program_summaries'][1]['scored_targets_sha256']


@pytest.mark.parametrize('change', ['duplicate', 'nan', 'zero', 'tamper'])
def test_directed_invalid_resource_fails_closed(tmp_path, change):
    request = directed_request(tmp_path)
    ref = request.object_inputs[0]
    source = json.loads(ref.path.read_bytes())
    resource = tmp_path / 'synthetic-directed.csv'
    raw = resource.read_text()
    if change == 'duplicate':
        raw = raw.replace('SOURCE1,SPHASE1', 'SOURCE1,SPHASE0')
    elif change in {'nan', 'zero'}:
        raw = raw.replace('SPHASE0,-2', 'SPHASE0,' + ('nan' if change == 'nan' else '0'))
    else:
        raw += 'SOURCE8,OTHER,2\n'
    resource.write_text(raw)
    if change != 'tamper':
        source['resource']['sha256'] = hashlib.sha256(resource.read_bytes()).hexdigest()
        encoded = json.dumps(source).encode(); ref.path.write_bytes(encoded)
        request = request.model_copy(update={'object_inputs':[ref.model_copy(update={'sha256':hashlib.sha256(encoded).hexdigest()})]})
    run = ToolRegistry.load_default().run(request)
    assert run.execution_state.value == 'failed'
    assert not run.artifacts
    assert ('program_resource_checksum_mismatch' if change == 'tamper' else 'program_resource_membership_invalid') in run.reason_codes
