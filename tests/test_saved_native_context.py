"""Only source refusal contracts; actual saved-input acceptance is private."""
import pytest
import hashlib
from bridge.toolkit.contracts import ToolRequest,ToolRequestV2,ToolRun,StructuredInputRef
from bridge.toolkit.registry import ToolRegistry

def _request(tmp_path):
    source=ToolRun(run_id='run-synthetic',request=ToolRequest(request_id='synthetic',tool_id='P0-03',
        output_dir=tmp_path/'unused'),implementation_state='implemented',execution_state='succeeded',
        tool_version='0.1.0',environment_spec_id='synthetic',result=None)
    path=tmp_path/'source.json';path.write_text(source.model_dump_json())
    ref=StructuredInputRef(input_id='source',role='saved_cell_state_run',schema_ref='bridge://schemas/tool-run/v0.1',
        object_version='0.1.0',path=path,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),media_type='application/json')
    return ToolRequestV2(request_id='synthetic-context',tool_id='P0-05',object_inputs=[ref],output_dir=tmp_path/'out')

def test_unrelated_producer_not_accepted(tmp_path):
    run=ToolRegistry.load_default().run(_request(tmp_path))
    assert run.execution_state.value=='failed'
    assert 'saved_cell_state_producer_invalid' in run.reason_codes
    assert not run.artifacts

def test_receipt_byte_drift_is_rejected(tmp_path):
    request=_request(tmp_path);request.object_inputs[0].path.write_text('{}')
    run=ToolRegistry.load_default().run(request)
    assert run.execution_state.value=='failed'
    assert not run.artifacts


@pytest.mark.parametrize("tool_id", ["P0-05", "P0-03"])
@pytest.mark.parametrize("source_version", [None, "0.8.0"])
def test_saved_fine_state_counts_reach_whole_product_measurements_without_reanalysis(tmp_path, monkeypatch, tool_id, source_version):
    import json
    from test_cell_state_candidate_runtime import _rig

    source_request, _, _ = _rig(tmp_path, monkeypatch)
    view = json.loads(next(tmp_path.rglob('qc_readiness_profile_v2.json')).read_text())['selected_data_view']
    asset = source_request.assets[0]
    source_request = source_request.model_copy(update={'assets': [asset.model_copy(update={
        'checksum': view['sha256'], 'metadata': {**asset.metadata, 'data_view_id': view['view_id']}})]})
    registry = ToolRegistry.load_default()
    source_registry = ToolRegistry([
        spec.model_copy(update={"version": source_version})
        if spec.tool_id == "P0-02" and source_version else spec for spec in registry.list()
    ])
    source_request = source_request.model_copy(update={"tool_version": source_version})
    source = source_registry.run(source_request)
    assert source.execution_state.value == 'succeeded', source.reason_codes
    receipt = tmp_path / 'candidate-run.json'
    receipt.write_text(source.model_dump_json())
    request = ToolRequestV2(request_id='whole-product-context', tool_id=tool_id,
        object_inputs=[StructuredInputRef(input_id='candidate', role='saved_cell_state_run',
            schema_ref='bridge://schemas/tool-run/v0.1', object_version='0.1.0',
            path=receipt, sha256=hashlib.sha256(receipt.read_bytes()).hexdigest(), media_type='application/json')],
        output_dir=tmp_path / 'whole-product-output')
    before = {a.path: hashlib.sha256(a.path.read_bytes()).hexdigest() for a in source.artifacts}
    # Once the producer is saved, context projection must not execute a matrix.
    import bridge.tool_packages.p0_02_cell_state.candidate_runtime as candidate_runtime
    monkeypatch.setattr(candidate_runtime, 'run_candidate_cell_state',
        lambda *a, **kw: (_ for _ in ()).throw(AssertionError('matrix rerun')))
    run = registry.run(request)
    assert run.execution_state.value == 'succeeded', run.reason_codes
    result = run.result
    assert 'whole_product_composition' in result
    rows = result['whole_product_composition']
    assert sum(row['count'] for row in rows) == result['data_view']['n_observations']
    projected = [m for m in run.measurements if m.metric_name.startswith('whole_product_fraction_')]
    assert len(projected) == len(rows)
    assert sum(m.numerator for m in projected) == result['data_view']['n_observations']
    assert all(m.denominator == result['data_view']['n_observations'] for m in projected)
    assert result['target_fraction'] is None and result['non_target_fraction'] is None
    assert result['role_judgement_state'] == 'not_assessed'
    assert set(result['source_definition_decisions'].values()) >= {'parent_only'}
    assert result['hierarchy_artifact_sha256']
    spec = json.loads(next(a.path for a in run.artifacts if a.kind == 'native_measurement_spec').read_text())
    for measurement in projected:
        definition = spec['raw_metric_definition'][measurement.metric_name]
        assert definition['record']['whole_product_denominator'] == measurement.denominator
        assert definition['artifact_sha256'] == result['hierarchy_artifact_sha256']
    assert before == {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in before}
    replay = registry.run(request)
    assert replay == run
