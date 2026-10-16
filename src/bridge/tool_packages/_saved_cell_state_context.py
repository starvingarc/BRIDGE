"""Checked saved P002 observations used by P003, P004 and P005; never runs a matrix."""
from __future__ import annotations

import hashlib
import math
from datetime import datetime
from typing import Any, Literal
from pydantic import Field, model_validator

from bridge.toolkit.contracts import (
    ArtifactManifest, DataViewBinding, EligibilityResult, FrozenModel,
    MeasurementResultV2, MeasurementSpecV3, ToolRun, ToolRunV2,
)
from bridge.tool_packages._structured_runtime import (
    StructuredInputError, PublicationError, canonical_json_bytes, read_regular_bytes,
    strict_json_loads, publish_json_bundle, failed_v2_run,
)
from bridge.tool_packages.p0_02_cell_state.candidate_runtime import CellStateCandidateProfile
from bridge.tool_packages.p0_02_cell_state.hierarchical_composition import HierarchicalCellStateCompositionDataV1

MODE = 'saved_cell_state_context'
ROLE = 'saved_cell_state_run'


class NativeCountObservation(FrozenModel):
    channel: str
    label: str
    label_level: str
    source_id: str | None
    count: int = Field(ge=0)
    denominator: int = Field(gt=0)
    fraction: float = Field(ge=0, le=1)
    denominator_scope: str
    producer_ref: str
    artifact_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')

    @model_validator(mode='after')
    def count_matches_fraction(self):
        if self.count > self.denominator or not math.isclose(self.fraction,self.count/self.denominator,abs_tol=1e-12):
            raise ValueError('native_count_fraction_mismatch')
        return self


class NativeCellStateContextProfile(FrozenModel):
    object_version: Literal['0.1.0'] = '0.1.0'
    runtime_mode: Literal['saved_cell_state_context'] = MODE
    tool_id: Literal['P0-04','P0-05']
    tool_version: str
    profile_id: str
    data_view: DataViewBinding
    source_receipt_sha256: str
    original_producer_ref: str
    auxiliary_producer_ref: str
    evidence_family_id: str
    primary_composition: list[NativeCountObservation]
    auxiliary_composition: list[NativeCountObservation]
    marker_observations: list[dict[str,Any]]
    reference_state_portrait: dict[str,Any] | None
    original_figure_refs: list[dict[str,str]]
    derivation: Literal['saved_native_context_projection_no_matrix_execution'] = 'saved_native_context_projection_no_matrix_execution'
    expected_window_match: None = None
    target_fraction: None = None
    non_target_fraction: None = None
    role_judgement_state: Literal['not_assessed'] = 'not_assessed'
    independence_state: Literal['unknown'] = 'unknown'
    n_independent_replicates: None = None
    score_state: Literal['unavailable'] = 'unavailable'
    domain_score: None = None
    limitations: list[str]
    created_at: datetime


def _verified(path, sha, seen):
    raw=read_regular_bytes(path)
    if hashlib.sha256(raw).hexdigest()!=sha:
        raise StructuredInputError('saved_cell_state_checksum_mismatch')
    seen.append((path,sha))
    return strict_json_loads(raw)


def _artifact(run, kind, seen):
    matches=[a for a in run.artifacts if a.kind==kind]
    if len(matches)!=1:
        raise StructuredInputError('saved_cell_state_artifact_required')
    a=matches[0]
    return _verified(a.path,a.sha256,seen),a


def load_saved_context(request):
    from bridge.toolkit.registry import ToolRegistry
    refs={r.role:r for r in request.object_inputs}
    seen=[]
    original=ToolRun.model_validate(_verified(refs[ROLE].path,refs[ROLE].sha256,seen))
    if original.request.tool_id!='P0-02' or original.execution_state.value not in {'succeeded','partial'}:
        raise StructuredInputError('saved_cell_state_producer_invalid')
    ToolRegistry.load_default().validate_historical_result(original,original.request)
    profile=CellStateCandidateProfile.model_validate(original.result)
    saved,pa=_artifact(original,'cell_state_candidate_profile',seen)
    if saved!=original.result or profile.producer_run_ref!=original.run_id or profile.producer_tool_version!=original.tool_version:
        raise StructuredInputError('saved_cell_state_producer_binding_mismatch')
    auxiliary,aa=_artifact(original,'auxiliary_tool_run',seen)
    auxiliary=ToolRun.model_validate(auxiliary)
    if (auxiliary.request.tool_id!='P0-02' or auxiliary.run_id!=profile.auxiliary_run_ref
            or auxiliary.execution_state.value not in {'succeeded','partial'}):
        raise StructuredInputError('saved_auxiliary_producer_mismatch')
    ToolRegistry.load_default().validate_historical_result(auxiliary,auxiliary.request)
    aux_profile,ap=_artifact(auxiliary,'cell_state_profile',seen)
    if aux_profile!=auxiliary.result or aux_profile['n_observations']!=profile.n_observations:
        raise StructuredInputError('saved_auxiliary_profile_mismatch')
    view=profile.input_data_view
    for source_run in (original,auxiliary):
        if len(source_run.request.assets)!=1:
            raise StructuredInputError('saved_source_asset_required')
        asset=source_run.request.assets[0]
        if (asset.checksum!=view.sha256 or asset.metadata.get('data_view_id')!=view.view_id
                or asset.matrix_location!=view.matrix_location or asset.matrix_semantics!=view.matrix_semantics):
            raise StructuredInputError('saved_auxiliary_view_mismatch')
    hierarchy,ha=_artifact(auxiliary,'hierarchical_cell_state_composition',seen)
    hierarchy=HierarchicalCellStateCompositionDataV1.model_validate(hierarchy)
    if (hierarchy.whole_product_denominator!=view.n_observations or hierarchy.input_view_sha256!=view.sha256
            or hierarchy.producer_run_ref!='run:'+auxiliary.run_id):
        raise StructuredInputError('saved_hierarchy_view_mismatch')
    historical_view = auxiliary.tool_version in {'0.5.5', '0.6.0', '0.6.1', '0.6.2'}
    if request.tool_id in {"P0-03", "P0-05"} and hierarchy.input_view_ref != view.view_id and not (
        historical_view and hierarchy.input_view_ref == auxiliary.request.assets[0].asset_id
    ):
        raise StructuredInputError('saved_hierarchy_view_mismatch')
    markers,ma=_artifact(original,'reviewed_marker_programs',seen)
    for row in markers:
        if (row['n_observations']!=view.n_observations or row['development_review_sha256']!=profile.development_review_sha256
                or row['semantics']!='per_gene_detection_not_joint_coexpression_or_identity'):
            raise StructuredInputError('saved_marker_context_mismatch')
        for obs in row['gene_detection'].values():
            if obs['state']=='missing':
                if obs['count'] is not None or obs['denominator'] is not None:
                    raise StructuredInputError('saved_marker_missing_not_null')
            elif obs['state']!='measured' or obs['denominator']!=view.n_observations or not 0<=obs['count']<=view.n_observations:
                raise StructuredInputError('saved_marker_count_invalid')
    primary=[NativeCountObservation(channel='primary_celltypist_candidate',label=r['label'],
        label_level='L1',source_id=None,count=r['count'],denominator=r['denominator'],fraction=r['fraction'],
        denominator_scope=r['denominator_scope'],producer_ref='tool-run:'+original.run_id+'@'+original.tool_version,
        artifact_sha256=pa.sha256) for r in profile.candidate_composition]
    auxiliary_rows=[NativeCountObservation(channel='auxiliary_'+r['view'],label=r['label'],label_level=r['label_level'],
        source_id=r['source_id'],count=r['count'],denominator=r['denominator'],fraction=r['fraction'],
        denominator_scope=r['denominator_view'],producer_ref='tool-run:'+auxiliary.run_id+'@'+auxiliary.tool_version,
        artifact_sha256=ap.sha256) for r in aux_profile['composition']['records']]
    # Validate each partition separately; never add methods/sources/levels together.
    groups={}
    for row in auxiliary_rows:
        if row.channel=='auxiliary_consensus_supported_only':
            continue
        groups.setdefault((row.channel,row.source_id,row.label_level,row.denominator),[]).append(row)
    if any(sum(r.count for r in rows)!=key[-1] for key,rows in groups.items()):
        raise StructuredInputError('saved_auxiliary_partition_not_closed')
    portrait=None
    if 'saved_reference_similarity_run' in refs:
        from bridge.tool_packages.p0_03_target_regional.technical_view import read_saved_source
        producer,result,manifest,provenance=read_saved_source(refs['saved_reference_similarity_run'])
        if result.data_view!=view:
            raise StructuredInputError('saved_reference_portrait_view_mismatch')
        portrait=dict(provenance=provenance,native_result=result.model_dump(mode='json'),
            interpretation='reference_state_similarity_not_age_or_expected_window',
            source_contexts=[p.model_dump(mode='json',include={'profile_id','source_id','source_family_id','assay','anatomy','developmental_time','matrix_sha256','metadata_sha256'}) for p in manifest.profiles if p.profile_id in {r.profile_id for r in result.measurements}])
    figures=[dict(artifact_id=a.artifact_id,path=str(a.path),sha256=a.sha256,producer_ref='tool-run:'+auxiliary.run_id+'@'+auxiliary.tool_version)
             for a in auxiliary.artifacts if a.path.suffix in {'.svg','.png','.pdf'}]
    for artifact in auxiliary.artifacts:
        if artifact.path.suffix in {'.svg','.png','.pdf'}:
            if hashlib.sha256(read_regular_bytes(artifact.path)).hexdigest()!=artifact.sha256:
                raise StructuredInputError('saved_figure_checksum_mismatch')
            seen.append((artifact.path,artifact.sha256))
    return original,profile,auxiliary,primary,auxiliary_rows,markers,ma,portrait,figures,seen,hierarchy,ha


def _role_context(request, source, hierarchy, markers, seen):
    """Verify optional role roots before applying them to the checked partition."""
    from bridge.tool_packages._configurable_contracts import StateRoleMap, ProductDefinitionCard
    from bridge.tool_packages.p0_03_target_regional.saved_roles import account_roles
    refs={r.role:r for r in request.object_inputs}
    role_map=definition=None
    if "state_role_map" in refs:
        role_map=StateRoleMap.model_validate(_verified(refs["state_role_map"].path,refs["state_role_map"].sha256,seen))
        definition=ProductDefinitionCard.model_validate(_verified(refs["product_definition_card"].path,refs["product_definition_card"].sha256,seen))
        if role_map.product_definition_ref!=definition.ref or definition.state_role_map_ref!=role_map.ref:
            raise StructuredInputError("saved_role_definition_binding_mismatch")
        if source.request.assets[0].assay not in definition.supported_assays:
            raise StructuredInputError("saved_role_assay_mismatch")
    fields=account_roles([r.model_dump(mode="json") for r in hierarchy.whole_product_records],
        hierarchy.whole_product_denominator,{r["state_id"]:r["definition_decision"] for r in markers},
        {r.state_id:r.model_dump(mode="json") for r in role_map.assignments} if role_map else {},
        role_map is not None and role_map.review_state in {"reviewed","frozen"})
    fields.update(state_role_map_ref=role_map.ref.ref if role_map else None,
        state_role_map_sha256=refs["state_role_map"].sha256 if role_map else None,
        product_definition_ref=definition.ref.ref if definition else None,
        product_definition_sha256=refs["product_definition_card"].sha256 if definition else None)
    return fields


def eligibility(request,spec):
    required={ROLE}
    allowed=required|({'saved_reference_similarity_run'} if request.tool_id=='P0-04' else
                      {'state_role_map','product_definition_card'} if request.tool_id=='P0-03' else set())
    roles=[r.role for r in request.object_inputs]
    reasons=[]
    if request.assets or request.parameters or request.measurement_spec_ref is not None or request.random_seed!=0:
        reasons.append('saved_context_request_contract_invalid')
    if request.tool_version not in {None,spec.version}:
        reasons.append('tool_version_mismatch')
    if len(roles)!=len(set(roles)) or not required.issubset(roles) or not set(roles).issubset(allowed):
        reasons.append('saved_context_source_roles_required')
    if request.tool_id=='P0-03' and (('state_role_map' in roles)!=('product_definition_card' in roles)):
        reasons.append('saved_role_definition_pair_required')
    for ref in request.object_inputs:
        if ref.role in {'state_role_map','product_definition_card'}:
            expected=('bridge://schemas/'+ref.role.replace('_','-')+'/v0.1','0.1.0')
        else:
            expected=('bridge://schemas/tool-run/v0.1','0.1.0') if ref.role==ROLE else ('bridge://schemas/tool-run/v0.2','0.2.0')
        if (ref.schema_ref,ref.object_version)!=expected:
            reasons.append('saved_context_source_schema_mismatch')
    if not reasons:
        try:
            context=load_saved_context(request)
            if request.tool_id=='P0-03':
                original, _, _, _, _, markers, _, _, _, seen, hierarchy, _ = context
                _role_context(request,original,hierarchy,markers,seen)
        except (OSError,KeyError,TypeError,ValueError) as exc:
            reasons.append(exc.reason_code if isinstance(exc,StructuredInputError) else 'saved_context_source_invalid')
    return EligibilityResult(tool_id=request.tool_id,eligible=not reasons,reason_codes=sorted(set(reasons)))


def execute(request,spec):
    eligible=eligibility(request,spec)
    if not eligible.eligible:
        return failed_v2_run(request,spec,eligible.reason_codes,result_schema_ref=spec.result_schema_ref)
    original,source,aux,primary,aux_rows,markers,marker_art,portrait,figures,seen,hierarchy,hierarchy_art=load_saved_context(request)
    fingerprint=hashlib.sha256(canonical_json_bytes({'tool':spec.tool_id,'version':spec.version,
        'inputs':[(r.role,r.sha256) for r in request.object_inputs]})).hexdigest()
    run_id='run-'+fingerprint[:16]
    view=source.input_data_view
    family='evidence-family:query-'+hashlib.sha256(canonical_json_bytes({'sha256':view.parent_asset_sha256})).hexdigest()[:24]
    result_model = NativeCellStateContextProfile
    hierarchy_fields = {}
    if spec.tool_id in {'P0-03','P0-05'}:
        from bridge.tool_packages.p0_05_off_target_control.native_models import NativeWholeProductContextProfile
        result_model = NativeWholeProductContextProfile
        hierarchy_fields = dict(
            whole_product_composition=hierarchy.whole_product_records,
            hierarchy_profile_ref=hierarchy.profile_id,
            hierarchy_artifact_sha256=hierarchy_art.sha256,
            hierarchy_view_binding=('selected_data_view' if hierarchy.input_view_ref == view.view_id
                                    else 'historical_asset_checked_against_selected_view'),
            source_review_sha256=source.development_review_sha256,
            source_definition_decisions={row['state_id']: row['definition_decision'] for row in markers},
        )
    if spec.tool_id == 'P0-03':
        from bridge.tool_packages.p0_03_target_regional.saved_roles import SavedTargetRoleProfile
        result_model = SavedTargetRoleProfile
        hierarchy_fields.update(_role_context(request,original,hierarchy,markers,seen))
    result=result_model(**hierarchy_fields,tool_id=spec.tool_id,tool_version=spec.version,
        profile_id='native-context:'+run_id,data_view=view,source_receipt_sha256=next(r.sha256 for r in request.object_inputs if r.role==ROLE),
        original_producer_ref='tool-run:'+original.run_id+'@'+original.tool_version,
        auxiliary_producer_ref='tool-run:'+aux.run_id+'@'+aux.tool_version,evidence_family_id=family,
        primary_composition=primary,auxiliary_composition=aux_rows,
        marker_observations=markers if spec.tool_id=='P0-04' else [],reference_state_portrait=portrait,
        original_figure_refs=figures,created_at=original.created_at,
        limitations=['source_labels_not_validated_identity','primary_and_auxiliary_not_interchangeable',
            'l2_single_source_parent_only_not_da_commitment','subgroup_denominators_not_whole_view',
            ('no_validated_identity_or_window' if spec.tool_id=='P0-03' else 'no_confirmed_product_role_or_window'),'no_independent_rna_vote','missing_not_zero',
            'reference_state_labels_pool_ages_not_stage_centroids']+
            (['reference_state_portrait_unavailable_no_saved_reference_similarity_run']
             if spec.tool_id=='P0-04' and portrait is None else []))
    definitions={}
    values=[]
    if spec.tool_id in {'P0-03','P0-05'}:
        for row in primary+aux_rows:
            key='native_fraction_'+hashlib.sha256(canonical_json_bytes(row.model_dump(mode='json'))).hexdigest()[:20]
            definitions[key]=row.model_dump(mode='json')
            values.append((key,row.fraction,row.count,row.denominator,row.producer_ref))
        for row in result.whole_product_composition:
            key='whole_product_fraction_'+hashlib.sha256(row.record_id.encode()).hexdigest()[:20]
            definitions[key]={
                'record': row.model_dump(mode='json'),
                'artifact_sha256': result.hierarchy_artifact_sha256,
                'hierarchy_profile_ref': result.hierarchy_profile_ref,
                'source_review_sha256': result.source_review_sha256,
                'definition_decision': result.source_definition_decisions.get(row.state_id, 'unavailable'),
                'interpretation': 'candidate_reference_correspondence_not_product_role',
            }
            values.append((key,row.whole_product_fraction,row.count,row.whole_product_denominator,result.auxiliary_producer_ref))
        if spec.tool_id=='P0-03':
            definitions['target_identity_fraction']={'role_records':[r.model_dump(mode='json') for r in result.role_records],
                'state_role_map_ref':result.state_role_map_ref,'state_role_map_sha256':result.state_role_map_sha256,
                'product_definition_ref':result.product_definition_ref,'product_definition_sha256':result.product_definition_sha256,
                'interpretation':'reviewed_mapping_of_candidate_states_not_validated_identity'}
            values.append(('target_identity_fraction',result.target_fraction,
                result.role_counts['target'] if result.target_fraction is not None else None,
                view.n_observations if result.target_fraction is not None else None,result.auxiliary_producer_ref))
    else:
        genes={}
        for row in markers:
            for gene,obs in row['gene_detection'].items():
                if gene in genes and genes[gene]!=obs:
                    raise StructuredInputError('saved_gene_detection_inconsistent')
                genes[gene]=obs
        for gene,obs in sorted(genes.items()):
            key='native_gene_detection_'+gene
            definitions[key]={'gene':gene,**obs,'artifact_sha256':marker_art.sha256,
                'semantics':'per_gene_detection_not_joint_coexpression_or_identity'}
            count,denominator=obs['count'],obs['denominator']
            values.append((key,None if count is None else count/denominator,count,denominator,result.original_producer_ref))
    native_spec=MeasurementSpecV3(measurement_spec_id='NATIVE-CONTEXT-'+fingerprint[:24],version='0.1.0',
        scientific_question='Which native source observations are available without role or window judgement?',
        assay=original.request.assets[0].assay,status='descriptive_only',data_view=view,
        observation_unit_kind='nucleus' if original.request.assets[0].assay=='snRNA-seq' else 'cell',
        input_contract={'source_receipt_sha256':result.source_receipt_sha256,'original_producer_ref':result.original_producer_ref,
                        'auxiliary_producer_ref':result.auxiliary_producer_ref,'derivation':result.derivation,'evidence_family_id':family},
        applicable_contexts=['native_source_context'],raw_metric_definition=definitions,
        denominator=('Whole-product fractions partition the selected view once; native fractions retain their original denominators. Never sum these channels.'
                     if spec.tool_id in {'P0-03','P0-05'} else 'Each metric preserves its declared original observation denominator; sources and levels are not summed'),
        uncertainty_method='Descriptive only; no independent biological replicate estimate',
        missing_behavior='Missing remains null',tool_refs=[spec.tool_id],reference_refs=[source.runtime_ref])
    measurements=[MeasurementResultV2(measurement_id=f'measurement:{run_id}:{i}',
        measurement_spec_id=native_spec.measurement_spec_id,measurement_spec_version=native_spec.version,
        metric_name=key,raw_value=value,unit='fraction',numerator=numerator,denominator=denominator,
        evidence_state='inferred' if value is not None else 'unavailable',score_state='unavailable',
        source_run_ref='tool-run:'+run_id+'@'+spec.version,source_execution_state='succeeded',
        provenance_refs=[producer,result.profile_id]) for i,(key,value,numerator,denominator,producer) in enumerate(values)]
    payloads={'native_context_profile.json':canonical_json_bytes(result.model_dump(mode='json'),indent=2),
        'native_measurement_spec.json':canonical_json_bytes(native_spec.model_dump(mode='json'),indent=2),
        **{f'native_measurement_{i}.json':canonical_json_bytes(m.model_dump(mode='json'),indent=2) for i,m in enumerate(measurements)}}
    def unchanged(_):
        try:
            return all(hashlib.sha256(read_regular_bytes(p)).hexdigest()==s for p,s in seen) and eligibility(request,spec).eligible
        except (OSError,ValueError):
            return False
    try:
        published=publish_json_bundle(request=request,run_id=run_id,payloads=payloads,inputs_are_unchanged=unchanged)
    except PublicationError as exc:
        return failed_v2_run(request,spec,[exc.reason_code],result_schema_ref=spec.result_schema_ref)
    return ToolRunV2(run_id=run_id,request=request,implementation_state='implemented',execution_state='succeeded',
        tool_version=spec.version,environment_spec_id=spec.environment_spec_id,input_hash=fingerprint,
        created_at=original.created_at,measurements=measurements,result_schema_ref=spec.result_schema_ref,
        result=result.model_dump(mode='json'),artifacts=[ArtifactManifest(artifact_id=f'artifact:{run_id}:{name[:-5]}',
            kind='measurement_result_v2' if name.startswith('native_measurement_') and name!='native_measurement_spec.json' else name[:-5],
            path=published[name],media_type='application/json',sha256=hashlib.sha256(raw).hexdigest(),evidence_ids=[result.profile_id])
            for name,raw in payloads.items()])
