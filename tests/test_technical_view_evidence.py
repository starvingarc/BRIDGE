"""Synthetic contract tests, not scientific validation or biological replication."""
import pytest
import hashlib
import json
from types import SimpleNamespace
from pydantic import ValidationError
from jsonschema import Draft202012Validator

from bridge.toolkit.contracts import MeasurementSpecV2, MeasurementSpecV3
from bridge.toolkit.schemas import load_schema
from bridge.tool_packages.p0_08_evidence_sufficiency.models import SourceObjectBinding, SourceObjectBindingV3


def technical_spec_payload():
    return dict(measurement_spec_id='SPEC-SYNTHETIC-TECHNICAL', version='0.1.0',
        scientific_question='Synthetic view coefficient', assay='scRNA-seq',
        input_contract={}, raw_metric_definition={'coefficient':'native coefficient'},
        missing_behavior='Unavailable remains null', data_view=dict(
            view_id='view:synthetic', view_kind='all_observations', artifact_id='asset:synthetic',
            sha256='1'*64, parent_asset_id='asset:synthetic', parent_asset_sha256='1'*64,
            matrix_location='X', matrix_semantics='raw_counts', n_observations=200,
            observation_ids_sha256='2'*64))


def test_technical_view_is_not_a_biological_unit_and_old_contract_stays_closed():
    spec = MeasurementSpecV3(**technical_spec_payload())
    assert spec.analysis_unit_kind == 'whole_view_technical_aggregate'
    assert spec.independence_group_kind is None
    assert spec.n_independent_biological_replicates is None
    assert spec.status == 'descriptive_only'
    Draft202012Validator(load_schema('bridge://schemas/measurement-spec/v0.3')).validate(spec.model_dump(mode='json'))
    with pytest.raises(ValidationError):
        MeasurementSpecV2.model_validate(spec.model_dump(mode='json'))


@pytest.mark.parametrize('change', [
    {'analysis_unit_kind':'capture'}, {'independence_group_kind':'sample'},
    {'n_independent_biological_replicates':200}, {'biological_independence':'independent'},
    {'status':'frozen'}, {'analysis_unit':'sample'},
])
def test_technical_view_refuses_qualification_and_pseudoreplication(change):
    with pytest.raises(ValidationError):
        MeasurementSpecV3(**(technical_spec_payload() | change))


def test_source_binding_acceptance_is_versioned_and_role_specific():
    binding = dict(input_id='technical-spec',role='measurement_spec',
        logical_object_id='SPEC-SYNTHETIC-TECHNICAL',object_version='0.1.0',
        schema_ref='bridge://schemas/measurement-spec/v0.3',source_sha256='3'*64)
    SourceObjectBindingV3(**binding)
    with pytest.raises(ValidationError):
        SourceObjectBinding(**binding)
    with pytest.raises(ValidationError):
        SourceObjectBindingV3(**(binding | {'role':'measurement_result'}))


@pytest.mark.parametrize('value', [float('nan'), float('inf'), -float('inf'), 1.01, -1.01])
def test_native_coefficient_bounds_are_checked_before_projection(value):
    from bridge.tool_packages.p0_03_target_regional.technical_view import validate_native_coefficients
    from bridge.tool_packages._structured_runtime import StructuredInputError
    with pytest.raises(StructuredInputError, match='coefficient'):
        validate_native_coefficients(SimpleNamespace(measurements=[
            SimpleNamespace(spearman=value, cosine=0.0, margin=None)]))


def saved_synthetic_request(tmp_path, *, unavailable=False):
    """A declared synthetic saved receipt, not a scientific runtime fixture."""
    from bridge.toolkit.contracts import ToolRunV2, ToolRequestV2, StructuredInputRef, ArtifactManifest, InputAsset
    from bridge.tool_packages.p0_03_target_regional.exploratory_models import ReferenceSimilarityExploratoryInput, ReferenceSimilarityExploratoryResult
    from bridge.tool_packages._structured_runtime import canonical_json_bytes

    def write(name, value):
        path = tmp_path/name
        raw = canonical_json_bytes(value, indent=2)
        path.write_bytes(raw)
        return path, hashlib.sha256(raw).hexdigest()

    view = technical_spec_payload()['data_view']
    created = '2026-09-23T00:00:00Z'
    source = ReferenceSimilarityExploratoryInput(object_version='0.1.0',input_id='synthetic:input',
        data_view=view,profile_ids=['PROFILE-SYNTHETIC'],created_at=created)
    path,sha = write('input.json', source.model_dump(mode='json'))
    source_ref = StructuredInputRef(input_id='input',role='reference_similarity_input',
        schema_ref='bridge://schemas/reference-similarity-exploratory-input/v0.1',object_version='0.1.0',
        path=path,sha256=sha,media_type='application/json')
    manifest = dict(snapshot_id='REFERENCE-SYNTHETIC',version='0.1.0',status='candidate',
        vocabulary_file='vocab.json',vocabulary_sha256='3'*64,marker_program_file='markers.json',
        marker_program_sha256='4'*64,measurement_spec_ids=[],profiles=[dict(
            profile_id='PROFILE-SYNTHETIC',source_id='SOURCE-SYNTHETIC',source_family_id='FAMILY-SYNTHETIC',
            evidence_family_id='RNA-SYNTHETIC',assay='snRNA-seq',anatomy='synthetic',developmental_time='unknown',
            label_level='L1',role='context',status='candidate',labels=['synthetic label'],
            matrix_file='unused.npy',matrix_sha256='5'*64,metadata_file='unused.json',metadata_sha256='6'*64)])
    path,manifest_sha = write('manifest.json',manifest)
    manifest_ref = StructuredInputRef(input_id='manifest',role='reference_manifest',
        schema_ref='bridge://schemas/reference-manifest/v0.1',object_version='0.1.0',
        path=path,sha256=manifest_sha,media_type='application/json')
    native = ReferenceSimilarityExploratoryResult(
        result_id='reference-similarity:synthetic',tool_version='0.4.2',source_run_ref='tool-run:run-synthetic@0.4.2',
        source_asset_id=view['parent_asset_id'],source_asset_sha256=view['parent_asset_sha256'],
        input_sha256=source_ref.sha256,reference_manifest_ref='REFERENCE-SYNTHETIC@0.1.0',
        reference_manifest_sha256=manifest_sha,data_view=view,n_observations=view['n_observations'],n_query_genes=4,
        result_state='unavailable' if unavailable else 'available',created_at=created,
        measurements=[dict(measurement_id='native:synthetic',profile_id='PROFILE-SYNTHETIC',
            source_id='SOURCE-SYNTHETIC',source_family_id='FAMILY-SYNTHETIC',label_level='L1',label='synthetic label',
            state='unavailable' if unavailable else 'available',spearman=None if unavailable else -0.25,
            cosine=None if unavailable else 0.5,shared_genes=4,query_gene_fraction=1.0,reference_gene_fraction=1.0,
            reason_codes=['insufficient_shared_genes'] if unavailable else [])])
    path,sha = write('native.json',native.model_dump(mode='json'))
    producer = ToolRunV2(run_id='run-synthetic',tool_version='0.4.2',environment_spec_id='ENV-CELLSTATE-PY-v0.1',
        request=ToolRequestV2(request_id='synthetic:original',tool_id='P0-03',tool_version='0.4.2',
            assets=[InputAsset(asset_id=view['parent_asset_id'],path=tmp_path/'never-read.h5ad',format='h5ad',
                checksum=view['parent_asset_sha256'],input_level='count_ready',assay='snRNA-seq',
                matrix_location='X',matrix_semantics='raw_counts')],object_inputs=[source_ref,manifest_ref],
            output_dir=tmp_path/'original',random_seed=0),implementation_state='implemented',
        execution_state='partial' if unavailable else 'succeeded',created_at=created,
        result_schema_ref='bridge://schemas/target-regional-result/v0.1',result=native.model_dump(mode='json'),
        artifacts=[ArtifactManifest(artifact_id='artifact:synthetic:result',kind='reference_similarity_exploratory_result',
            path=path,sha256=sha,media_type='application/json')])
    receipt_path,receipt_sha=write('receipt.json',producer.model_dump(mode='json'))
    return ToolRequestV2(request_id='synthetic:projection',tool_id='P0-03',assets=[],random_seed=0,
        output_dir=tmp_path/'projection',object_inputs=[StructuredInputRef(input_id='saved',role='saved_reference_similarity_run',
            schema_ref='bridge://schemas/tool-run/v0.2',object_version='0.2.0',path=receipt_path,
            sha256=receipt_sha,media_type='application/json')])


@pytest.mark.parametrize('unavailable',[False,True])
def test_saved_projection_uses_sources_and_preserves_nulls_without_matrix_io(tmp_path,unavailable):
    from bridge.toolkit.api import run_tool
    request=saved_synthetic_request(tmp_path,unavailable=unavailable)
    run=run_tool(request)
    assert run.execution_state.value == ('partial' if unavailable else 'succeeded'),run.reason_codes
    assert len(run.measurements)==2
    assert [m.raw_value for m in run.measurements] == ([None,None] if unavailable else [-0.25,0.5])
    artifact=next(a for a in run.artifacts if a.kind=='native_measurement_spec')
    spec=MeasurementSpecV3.model_validate_json(artifact.path.read_bytes())
    assert spec.observation_unit_kind=='nucleus'
    assert spec.input_contract['original_producer_ref']=='tool-run:run-synthetic@0.4.2'
    assert spec.raw_metric_definition['reference_similarity_0_spearman']['label']=='synthetic label'
    assert not (tmp_path/'never-read.h5ad').exists()
    repeated=run_tool(request)
    assert repeated.model_dump(mode='json')==run.model_dump(mode='json')


def test_saved_projection_refuses_changed_native_artifact(tmp_path):
    from bridge.toolkit.api import run_tool
    request=saved_synthetic_request(tmp_path)
    (tmp_path/'native.json').write_text('{}')
    run=run_tool(request)
    assert run.execution_state.value=='failed'
    assert 'saved_similarity_source_checksum_mismatch' in run.reason_codes
    assert not run.artifacts and not run.measurements
