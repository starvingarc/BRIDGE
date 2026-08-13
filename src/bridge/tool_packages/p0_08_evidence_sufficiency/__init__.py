"""Deterministic P0-08 evidence-sufficiency candidate."""

from bridge.tool_packages.p0_08_evidence_sufficiency.adapter import adapter
from bridge.tool_packages.p0_08_evidence_sufficiency.executor import (
    evaluate_evidence_sufficiency,
)

__all__ = ["adapter", "evaluate_evidence_sufficiency"]
