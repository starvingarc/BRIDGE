"""Versioned descriptive portrait; old developmental result stays unchanged."""
from pydantic import RootModel
from bridge.tool_packages._saved_cell_state_context import NativeCellStateContextProfile
from .models import DevelopmentalCompatibilityResultV3

RESULT_SCHEMA = 'bridge://schemas/developmental-compatibility-result/v0.4'

class DevelopmentalCompatibilityResultV4(RootModel[DevelopmentalCompatibilityResultV3 | NativeCellStateContextProfile]):
    pass

PUBLIC_SCHEMA_MODELS = {RESULT_SCHEMA: DevelopmentalCompatibilityResultV4,
    'bridge://schemas/native-cell-state-context-profile/v0.1': NativeCellStateContextProfile}
