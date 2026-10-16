"""Source-bound spatial displays; reads never schedule or run scientific tools."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pandas as pd

from .scientific_inputs import digest
from .sessions import private_text
from .spatial_link_data import ProductLinkInput, ReferenceSubtypeInput, build_product_link, ordered_observation_sha256
from .spatial_reference import SpatialReference, load_spatial_reference


def build_spatial_context(product_source: ProductLinkInput, reference: SpatialReference) -> dict:
    product = build_product_link(product_source, reference.manifest.crosswalk)
    manifest = reference.manifest
    if any(row.spatial_type_id not in manifest.types for row in manifest.crosswalk.entries):
        raise ValueError('crosswalk_spatial_type_unknown')
    context_id = digest([product_source.model_dump(mode='json'), reference.manifest_sha256])
    return dict(kind='linked_cell_context', version='1.0', context_id=context_id,
                state='available', missing_reasons=[], product=product,
                reference=dict(id=manifest.reference_id, version=manifest.version, stage=manifest.stage,
                    sha256=manifest.sha256, manifest_sha256=reference.manifest_sha256,
                    vocabulary_version=manifest.vocabulary_version,
                    n_observations=len(reference.coordinates), sections=reference.sections,
                    types=manifest.types, model_available=manifest.model is not None,
                    model_stage=manifest.model.stage if manifest.model else None,
                    model_attribution=manifest.model.attribution if manifest.model else None,
                    model_license=manifest.model.license if manifest.model else None,
                    plane_hypothesis=(manifest.model.plane_hypothesis.model_dump()
                        if manifest.model and manifest.model.plane_hypothesis else None)),
                crosswalk=manifest.crosswalk.model_dump(mode='json'))


class SpatialContexts:
    """Receive only artifact access and source-resolution capabilities at assembly."""

    def __init__(self, *, resolve_source, read_artifact, checked_bytes, manifest_path):
        self.resolve_source = resolve_source
        self.read_artifact = read_artifact
        self.checked_bytes = checked_bytes
        self.manifest_path = manifest_path

    def _source(self, state, aid):
        self.read_artifact(state, aid)
        return self.resolve_source(state, aid)

    def _related_bytes(self, state, anchor, artifact):
        matches = [aid for aid, row in state.get('_canonical_artifacts', {}).items()
                   if aid in state.get('_artifacts', {}) and row['artifact_id'] == artifact['artifact_id']
                   and all(row[k] == anchor[k] for k in ('receipt_file', 'receipt_sha256'))
                   and row['sha256'] == artifact['sha256']]
        if len(matches) != 1:
            raise ValueError('spatial_related_artifact_ambiguous')
        self.read_artifact(state, matches[0])
        return self.checked_bytes(state, artifact['path'], artifact['sha256'])


    def _reference_subtypes(self, state, anchor, artifacts, receipt, profile, ids):
        """Read optional reference labels; primary identities remain unchanged."""
        from fastapi import HTTPException
        from .inputs import strict_json

        try:
            if profile.auxiliary_state != 'available':
                return None
            auxiliary = [row for row in artifacts.values() if row['kind'] == 'auxiliary_tool_run']
            if len(auxiliary) != 1:
                return None
            artifact = auxiliary[0]
            run = strict_json(self._related_bytes(state, anchor, artifact))
            view = profile.input_data_view
            assets = run['request']['assets']
            if (run['run_id'] != profile.auxiliary_run_ref
                    or run['execution_state'] != 'succeeded'
                    or run['tool_version'] != receipt['tool_version']
                    or run['request']['tool_id'] != 'P0-02'
                    or run['request']['measurement_spec_ref'] != 'CELLSTATE-scRNA-shadow-v0.1'
                    or run['input_hash'] != profile.input_sha256
                    or assets != receipt['request']['assets'] or len(assets) != 1
                    or assets[0]['checksum'] != profile.input_sha256
                    or assets[0]['metadata']['data_view_id'] != view.view_id
                    or assets[0]['metadata']['parent_asset_sha256'] != view.parent_asset_sha256
                    or assets[0]['metadata']['qc_profile_ref'] != profile.upstream_qc_profile_ref
                    or run['result']['n_observations'] != len(ids)
                    or view.n_observations != len(ids)):
                return None
            sources = [row['source_id'] for row in run['result']['source_support']['coverage']
                       if row['label_level'] == 'L2' and row['role'] == 'refinement'
                       and row['state'] == 'available']
            evidence = [row for row in run['artifacts'] if row['kind'] == 'cell_state_evidence']
            if len(sources) != 1 or len(evidence) != 1:
                return None
            table = evidence[0]
            column = sources[0] + '__top_label'
            frame = pd.read_parquet(BytesIO(self.checked_bytes(state, table['path'], table['sha256'])),
                columns=['observation_id', column, 'l2_parent_state_id', 'l2_support_state',
                         'l2_assignment_state', 'l2_open_set_state'])
            frame = frame.astype(object).where(pd.notna(frame), None)
            if frame.observation_id.tolist() != ids:
                return None
            rows = []
            for row in frame.to_dict('records'):
                eligible = (row['l2_support_state'] == 'single_source_supported'
                            and row['l2_assignment_state'] == 'shadow_candidate'
                            and row['l2_open_set_state'] == 'not_assessed'
                            and isinstance(row[column], str) and isinstance(row['l2_parent_state_id'], str))
                rows.append(dict(observation_id=row['observation_id'],
                    source_state_id=row[column] if eligible else None,
                    parent_state_id=row['l2_parent_state_id'] if eligible else None))
            return ReferenceSubtypeInput.model_validate(dict(rows=rows, source_binding=dict(
                input_sha256=profile.input_sha256, data_view_ref=view.view_id,
                ordered_observation_sha256=ordered_observation_sha256(ids),
                producer_ref='run:' + run['run_id'], receipt_sha256=artifact['sha256'],
                source_id=sources[0], evidence_sha256=table['sha256'])))
        except (ValueError, KeyError, TypeError, OSError, HTTPException):
            return None

    def assessment_explorer(self, state, assessment, *, scope_digest, evidence_alias):
        """Resolve a display-only UMAP from the assessment's exact candidate source.

        This read does not admit expression evidence, change the scientific
        snapshot, or parse the large UMAP payload. The existing spatial-context
        endpoint still verifies the complete coordinate/assignment join.
        """
        from fastapi import HTTPException
        from bridge.tool_packages._expression_contracts import EXPLORATION_SPEC
        from bridge.tool_packages.p0_02_cell_state.candidate_runtime import CellStateCandidateProfile
        from bridge.tool_packages.p0_02_cell_state.expression_figures import ExpressionFigureSet
        from bridge.toolkit.visualization import FigureRegistry

        def unavailable(reason):
            return dict(state='unavailable', reason_code=reason)

        current = state.get('_assessment')
        if not current or current.get('scope_digest') != scope_digest or not assessment or assessment.get('scope_digest') != scope_digest:
            raise ValueError('cell_explorer_scope_changed')
        axis = next((row for row in assessment.get('portrait', []) if row['id'] == 'cell_state'), {})
        evidence = next((row for row in assessment.get('evidence', []) if row['alias'] == evidence_alias), None)
        if (evidence_alias not in axis.get('evidence_aliases', []) or not evidence
                or evidence.get('state') != 'available' or evidence.get('tool_id') != 'P0-02'
                or evidence.get('summary', {}).get('analysis_scope') != 'candidate_method_observation'):
            return unavailable('cell_explorer_candidate_not_bound')
        view = current['scope']['binding'].get('data_view')
        if not view:
            return unavailable('cell_explorer_candidate_not_bound')
        candidates = {}
        for aid in evidence.get('artifact_ids', []):
            if state.get('_artifacts', {}).get(aid, {}).get('source_kind') != 'cell_state_candidate_profile':
                continue
            try:
                binding, artifacts, receipt, payload = self._source(state, aid)
                profile = CellStateCandidateProfile.model_validate(payload)
                if (artifacts[binding['artifact_id']]['kind'] != 'cell_state_candidate_profile'
                        or receipt['request']['tool_id'] != 'P0-02'
                        or payload != receipt['result'] or profile.producer_run_ref != receipt['run_id']
                        or profile.producer_tool_version != receipt['tool_version']
                        or binding['receipt_sha256'] != evidence.get('provenance', {}).get('receipt_sha256')
                        or evidence_alias != 'E-' + binding['receipt_sha256'][:16]
                        or profile.input_data_view.model_dump(mode='json') != view
                        or profile.input_sha256 != view['sha256']
                        or receipt.get('input_hash') != profile.input_sha256):
                    return unavailable('cell_explorer_candidate_not_bound')
                candidates[(binding['receipt_sha256'], binding['sha256'])] = binding
            except (ValueError, KeyError, TypeError, OSError, HTTPException):
                return unavailable('cell_explorer_candidate_not_bound')
        if len(candidates) != 1:
            return unavailable('cell_explorer_candidate_not_bound')
        candidate = next(iter(candidates.values()))
        matches = {}
        registry = FigureRegistry.load_default()
        for set_id, exposed in state.get('_artifacts', {}).items():
            if exposed.get('source_kind') != 'visualization_artifact_set':
                continue
            anchor = state.get('_canonical_artifacts', {}).get(set_id)
            if not anchor or anchor['receipt_file'] in state.get('_invalidated_receipts', {}):
                continue
            try:
                binding, artifacts, receipt, payload = self._source(state, set_id)
            except (ValueError, KeyError, TypeError, OSError, HTTPException):
                continue
            result = receipt.get('result') or {}
            request = receipt.get('request') or {}
            if (request.get('tool_id') != 'P0-02'
                    or request.get('measurement_spec_ref') != EXPLORATION_SPEC
                    or receipt.get('execution_state') != 'succeeded'
                    or result.get('analysis_kind') != 'expression_exploration'
                    or result.get('input_data_view') != view
                    or result.get('input_sha256') != view['sha256']):
                continue
            try:
                assets = request.get('assets', [])
                if (len(assets) != 1 or assets[0].get('checksum') != view['sha256']
                        or assets[0].get('metadata', {}).get('data_view_id') != view['view_id']
                        or receipt.get('input_hash') != view['sha256']
                        or result.get('object_version') != '0.1.0'
                        or result.get('n_observations') != view['n_observations']
                        or artifacts[binding['artifact_id']]['kind'] != 'visualization_artifact_set'):
                    raise ValueError('expression_binding_mismatch')
                figures = ExpressionFigureSet.model_validate(payload)
                umaps = [figure for figure in figures.visualizations
                         if figure.component_id == 'bridge.expression.umap']
                if len(umaps) != 1:
                    raise ValueError('expression_umap_ambiguous')
                figure = umaps[0]
                registry.validate_artifact(figure)
                if (figure.producer_run_ref != 'run:' + receipt['run_id']
                        or figure.producer_tool_version != receipt['tool_version']):
                    raise ValueError('expression_producer_mismatch')
                data = artifacts[figure.data_binding.artifact_id]
                if (data['kind'] != 'expression_plot_data'
                        or data['sha256'] != figure.data_binding.sha256):
                    raise ValueError('expression_data_binding_mismatch')
                registered = [aid for aid, row in state.get('_canonical_artifacts', {}).items()
                    if aid in state.get('_artifacts', {}) and row['artifact_id'] == data['artifact_id']
                    and all(row[key] == binding[key] for key in ('receipt_file', 'receipt_sha256'))
                    and row['sha256'] == data['sha256']
                    and state['_artifacts'][aid].get('source_artifact_id') == data['artifact_id']
                    and state['_artifacts'][aid].get('source_sha256') == data['sha256']]
                if not registered:
                    return unavailable('cell_explorer_umap_invalid')
                if len(registered) != 1:
                    return unavailable('cell_explorer_umap_ambiguous')
                aid = registered[0]
                self.read_artifact(state, aid)  # Enforce the existing artifact access policy.
                matches[(binding['receipt_sha256'], data['artifact_id'], data['sha256'])] = (
                    aid, binding['receipt_sha256'], data['sha256'])
            except HTTPException:
                continue
            except (ValueError, KeyError, TypeError, OSError):
                return unavailable('cell_explorer_umap_invalid')
        if not matches:
            return unavailable('cell_explorer_umap_missing')
        if len(matches) != 1:
            return unavailable('cell_explorer_umap_ambiguous')
        aid, receipt_sha256, data_sha256 = next(iter(matches.values()))
        token = digest([scope_digest, evidence_alias, candidate['receipt_sha256'],
                        candidate['sha256'], receipt_sha256, data_sha256])
        return dict(state='available', umap_artifact_id=aid, binding_token=token,
                    candidate_receipt_sha256=candidate['receipt_sha256'])

    def source_gaps(self, state, view) -> list[str]:
        """Advertise missing prerequisites to the existing planner without dispatch."""
        found = set()
        for aid, exposed in state.get('_artifacts', {}).items():
            kind = exposed.get('source_kind')
            if kind not in {'cell_state_candidate_profile', 'expression_plot_data'}:
                continue
            binding = state.get('_canonical_artifacts', {}).get(aid)
            if not binding or binding['receipt_file'] in state.get('_invalidated_receipts', {}):
                continue
            _, artifacts, receipt, payload = self._source(state, aid)
            if (artifacts[binding['artifact_id']]['kind'] != kind
                    or receipt['request']['tool_id'] != 'P0-02'
                    or receipt.get('result', {}).get('input_data_view') != view):
                continue
            if kind == 'cell_state_candidate_profile' and payload == receipt['result']:
                found.add('candidate')
            elif kind == 'expression_plot_data' and payload.get('kind') == 'umap':
                found.add('expression')
        return ['spatial_link_' + kind + '_analysis_required'
                for kind in ('candidate', 'expression') if kind not in found]

    def read(self, state, aid) -> tuple[dict, SpatialReference | None]:
        from bridge.tool_packages.p0_02_cell_state.expression_figures import ExpressionPlotData
        from bridge.tool_packages.p0_02_cell_state.candidate_runtime import CellStateCandidateProfile
        from bridge.toolkit.visualization import VisualizationArtifactV2, FigureRegistry
        from .inputs import strict_json

        binding, artifacts, receipt, payload = self._source(state, aid)
        if (artifacts[binding['artifact_id']]['kind'] != 'expression_plot_data'
                or receipt['request']['tool_id'] != 'P0-02'
                or receipt['request']['measurement_spec_ref'] != 'EXPRESSION-exploration-v0.1'):
            raise ValueError('spatial_expression_source_required')
        plot = ExpressionPlotData.model_validate(payload)
        result = receipt['result']
        view = result['input_data_view']
        if (plot.kind != 'umap' or plot.input_sha256 != result['input_sha256']
                or plot.data_view_ref != view['view_id'] or plot.n_observations != view['n_observations']):
            raise ValueError('spatial_expression_binding_mismatch')
        def missing(reason):
            return (dict(kind='linked_cell_context', version='1.0', state='unavailable',
                         context_id=digest([binding['sha256'], binding['receipt_sha256'], reason]),
                         product=None, reference=None, crosswalk=None, missing_reasons=[reason]), None)
        path = self.manifest_path()
        if path is None:
            return missing('spatial_reference_not_configured')
        reference = load_spatial_reference(Path(path))
        profiles = []
        for candidate_id, exposed in state.get('_artifacts', {}).items():
            if exposed.get('source_kind') != 'cell_state_candidate_profile':
                continue
            candidate_binding = state.get('_canonical_artifacts', {}).get(candidate_id)
            if candidate_binding and candidate_binding['receipt_file'] in state.get('_invalidated_receipts', {}):
                continue
            cb, ca, cr, cp = self._source(state, candidate_id)
            profile = CellStateCandidateProfile.model_validate(cp)
            if (cp != cr['result'] or ca[cb['artifact_id']]['kind'] != 'cell_state_candidate_profile'
                    or cr['request']['tool_id'] != 'P0-02' or profile.producer_run_ref != cr['run_id']):
                raise ValueError('spatial_candidate_receipt_mismatch')
            if profile.input_data_view.model_dump(mode='json') == view and profile.input_sha256 == plot.input_sha256:
                profiles.append((cb, ca, cr, profile))
        if not profiles:
            return missing('same_view_candidate_assignments_missing')
        if len(profiles) != 1:
            return missing('same_view_candidate_assignments_ambiguous')
        cb, ca, cr, profile = profiles[0]
        # Resolve the full table through the declared visualization, never its filename.
        sets = [a for a in artifacts.values() if a['kind'] == 'visualization_artifact_set']
        if len(sets) != 1:
            raise ValueError('spatial_figure_set_ambiguous')
        figure_set = strict_json(self._related_bytes(state, binding, sets[0]))
        views = [VisualizationArtifactV2.model_validate(v) for v in figure_set['visualizations']
                 if v['data_binding']['artifact_id'] == binding['artifact_id']]
        if len(views) != 1:
            raise ValueError('spatial_figure_binding_ambiguous')
        figure = views[0]
        FigureRegistry.load_default().validate_artifact(figure)
        if (figure.producer_run_ref != 'run:' + receipt['run_id']
                or figure.data_binding.sha256 != binding['sha256']):
            raise ValueError('spatial_figure_binding_mismatch')
        table = artifacts.get(figure.accessibility.table_artifact_id)
        if table is None or table['kind'] != 'expression_table':
            raise ValueError('spatial_full_table_missing')
        rows = pd.read_csv(BytesIO(self._related_bytes(state, binding, table)), sep='\t',
                           dtype={'observation_id': str, 'group': str}, keep_default_na=False,
                           float_precision='round_trip')
        if len(rows) != plot.n_observations:
            raise ValueError('spatial_full_table_count_mismatch')
        assignment_artifacts = [a for a in ca.values() if a['kind'] == 'celltypist_candidate_assignments']
        if len(assignment_artifacts) != 1:
            raise ValueError('spatial_assignment_artifact_ambiguous')
        assignments = pd.read_parquet(BytesIO(self._related_bytes(state, cb, assignment_artifacts[0])),
            columns=['observation_id', 'assigned_state', 'assignment_state', 'qualified_assignment'])
        assignments = assignments.astype(object).where(pd.notna(assignments), None)
        def source_binding(anchor, run, ids):
            return dict(input_sha256=run['result']['input_sha256'], data_view_ref=run['result']['input_data_view']['view_id'],
                        ordered_observation_sha256=ordered_observation_sha256(ids),
                        producer_ref='run:' + run['run_id'], receipt_sha256=anchor['receipt_sha256'])
        source = ProductLinkInput.model_validate(dict(
            rows=rows.rename(columns={'umap_1': 'x', 'umap_2': 'y', 'group': 'cluster'}).to_dict('records'),
            plot_records=[dict(record_id=p.record_id, x=p.x, y=p.y, group=p.group) for p in plot.records],
            assignments=assignments.to_dict('records'),
            coordinate_binding=source_binding(binding, receipt, rows.observation_id.tolist()),
            assignment_binding=source_binding(cb, cr, assignments.observation_id.tolist()),
            product_vocabulary_version='cell-state-development-review:' + profile.development_review_version + '@' + profile.development_review_sha256,
            spatial_vocabulary_version=reference.manifest.vocabulary_version,
            reference_subtypes=self._reference_subtypes(state, cb, ca, cr, profile, rows.observation_id.tolist())))
        display = build_spatial_context(source, reference)
        # Display text follows the existing private-artifact projection rule.
        def redact(value):
            if isinstance(value, str):
                return private_text(value)
            if isinstance(value, list):
                return [redact(v) for v in value]
            if isinstance(value, dict):
                return {k: redact(v) for k, v in value.items()}
            return value
        return redact(display), reference
