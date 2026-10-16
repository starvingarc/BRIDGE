"""Versioned native accounting; existing role-based results stay unchanged."""
from typing import Literal

from pydantic import Field, RootModel, model_validator
from bridge.tool_packages.p0_02_cell_state.hierarchical_composition import HierarchicalCompositionRecord
from bridge.tool_packages._saved_cell_state_context import NativeCellStateContextProfile
from .models import OffTargetControlProfileV2, OffTargetHardCountProfileV1, OffTargetHardCountProfileV2, OffTargetHardCountProfileV3

RESULT_SCHEMA = 'bridge://schemas/off-target-control-result/v0.4'

class OffTargetControlResultV2(RootModel[OffTargetControlProfileV2 | OffTargetHardCountProfileV1 | NativeCellStateContextProfile]):
    pass

class OffTargetControlResultV3(RootModel[OffTargetControlProfileV2 | OffTargetHardCountProfileV1 | OffTargetHardCountProfileV2 | NativeCellStateContextProfile]):
    pass

class NativeWholeProductContextProfile(NativeCellStateContextProfile):
    """Candidate hierarchy counts, never a substitute for reviewed product roles."""

    object_version: Literal['0.2.0'] = '0.2.0'
    tool_id: Literal['P0-05'] = 'P0-05'
    whole_product_composition: list[HierarchicalCompositionRecord] = Field(min_length=1)
    hierarchy_profile_ref: str = Field(min_length=1)
    hierarchy_artifact_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    hierarchy_view_binding: Literal['selected_data_view', 'historical_asset_checked_against_selected_view']
    source_review_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    source_definition_decisions: dict[str, Literal['evaluate', 'parent_only', 'unavailable']]

    @model_validator(mode='after')
    def whole_product_counts_are_conserved(self):
        rows = self.whole_product_composition
        if any(row.count is None or row.whole_product_denominator != self.data_view.n_observations for row in rows):
            raise ValueError('whole_product_selected_view_required')
        if len({row.record_id for row in rows}) != len(rows):
            raise ValueError('whole_product_duplicate_record')
        parents = {row.parent_state_id for row in rows if row.level == 'L2'}
        if any(row.state_id in parents for row in rows if row.state_id is not None):
            raise ValueError('whole_product_parent_child_overlap')
        if sum(row.count for row in rows) != self.data_view.n_observations:
            raise ValueError('whole_product_counts_not_conserved')
        return self


class OffTargetControlResultV4(RootModel[OffTargetControlProfileV2 | OffTargetHardCountProfileV3 | NativeWholeProductContextProfile]):
    pass


PUBLIC_SCHEMA_MODELS = {
    'bridge://schemas/off-target-control-result/v0.2': OffTargetControlResultV2,
    'bridge://schemas/off-target-control-result/v0.3': OffTargetControlResultV3,
    'bridge://schemas/native-cell-state-context-profile/v0.2': NativeWholeProductContextProfile,
    RESULT_SCHEMA: OffTargetControlResultV4,
}
