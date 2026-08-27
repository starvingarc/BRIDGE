from __future__ import annotations

from pydantic import RootModel

from bridge.tool_packages.p0_12_graft_assessment.analysis_models import (
    PUBLIC_SCHEMA_MODELS as ANALYSIS_SCHEMA_MODELS,
    GraftExpressionAnalysisResult,
)
from bridge.tool_packages.p0_12_graft_assessment.models import (
    PUBLIC_SCHEMA_MODELS as LEGACY_SCHEMA_MODELS,
    GraftAssessmentResult,
)


class GraftAssessmentRunResult(
    RootModel[GraftAssessmentResult | GraftExpressionAnalysisResult]
):
    pass


PUBLIC_SCHEMA_MODELS = {
    **LEGACY_SCHEMA_MODELS,
    **ANALYSIS_SCHEMA_MODELS,
    (
        "bridge://schemas/graft-assessment-run-result/v0.1"
    ): GraftAssessmentRunResult,
}
