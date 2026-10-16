"""Expression request contract, independent of computation and publication.

Web input binding and tool validation share these defaults and constraints.
Execution modules consume the same models; importing them must not execute analysis.
"""
from __future__ import annotations

from typing import Literal
from pydantic import Field
from bridge.toolkit.contracts import FrozenModel

EXPLORATION_SPEC = 'EXPRESSION-exploration-v0.1'


class ExplorationOptions(FrozenModel):
    """Selected-view exploration; null grouping/embedding requests fresh computation."""
    group_key: str | None = Field(default=None, min_length=1, max_length=100)
    color_keys: list[str] = Field(default_factory=list, max_length=8)
    genes: list[str] = Field(default_factory=list, max_length=32)
    embedding_key: str | None = Field(default=None, min_length=1, max_length=100)
    normalized_scale: Literal['log1p'] | None = None
    n_hvg: int = Field(default=2000, ge=20, le=5000)
    n_pcs: int = Field(default=30, ge=2, le=100)
    n_neighbors: int = Field(default=30, ge=2, le=100)
    min_dist: float = Field(default=0.5, ge=0, le=1)
    resolution: float = Field(default=0.5, gt=0, le=5)
    max_points: int = Field(default=5000, ge=20, le=20000)
    marker_genes: int = Field(default=50, ge=1, le=500)
    threads: int = Field(default=2, ge=1, le=8)


class Contrast(FrozenModel):
    """Within-population comparison; sample independence is a caller declaration."""
    group_key: str = Field(min_length=1, max_length=100)
    group: str = Field(min_length=1, max_length=200)
    sample_key: str = Field(min_length=1, max_length=100)
    condition_key: str = Field(min_length=1, max_length=100)
    reference: str = Field(min_length=1, max_length=200)
    comparison: str = Field(min_length=1, max_length=200)
    batch_key: str | None = Field(default=None, min_length=1, max_length=100)
    independent_samples_confirmed: bool = False
    min_cells: int = Field(default=10, ge=2, le=1000)
    min_total_counts: int = Field(default=10, ge=1, le=1000)


class ExpressionAnalysis(FrozenModel):
    exploration: ExplorationOptions = Field(default_factory=ExplorationOptions)
    contrast: Contrast | None = None
