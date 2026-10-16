"""Source-bound proposed interpretation; never numerical or scientific qualification."""
import re
from typing import Literal
from pydantic import Field, model_validator
from bridge.toolkit.contracts import FrozenModel

class EvidenceRelation(FrozenModel):
    evidence_alias: str = Field(min_length=1, max_length=240)
    relation: Literal["supports", "limits", "contradicts", "missing_for"]
    rationale: str = Field(min_length=1, max_length=400)
    applicability: str = Field(min_length=1, max_length=300)

def validate_relations(hypothesis):
    refs = set(hypothesis.evidence_aliases) | set(hypothesis.opposing_evidence_aliases)
    missing = set(hypothesis.missing_evidence_aliases)
    seen = set()
    for row in hypothesis.evidence_relations:
        if row.evidence_alias in seen:
            raise ValueError("duplicate_interpretation_relation")
        seen.add(row.evidence_alias)
        if row.evidence_alias not in refs | missing:
            raise ValueError("interpretation_relation_not_cited")
        if (row.relation == "missing_for") != (row.evidence_alias in missing):
            raise ValueError("interpretation_relation_evidence_state_mismatch")
    if seen and seen != refs | missing:
        raise ValueError("interpretation_relation_missing_for_citation")
    return hypothesis

def validate_feature_queries(queries):
    """The wire and stored explanation share exact-identifier syntax."""
    if (len(set(queries)) != len(queries)
            or any(not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", item) for item in queries)):
        raise ValueError("invalid_feature_query")


def bind_hypotheses(hypotheses, aliases):
    """Bind every model-owned reference through one checked mapping."""
    from copy import deepcopy
    result = deepcopy(hypotheses)
    for row in result:
        for field in ("evidence_aliases", "opposing_evidence_aliases", "missing_evidence_aliases"):
            row[field] = [aliases[value] for value in row.get(field, [])]
        for relation in row.get("evidence_relations", []):
            relation["evidence_alias"] = aliases[relation["evidence_alias"]]
    return result


class FeatureCoverageItem(FrozenModel):
    identifier: str = Field(min_length=1, max_length=64)
    state: Literal["present", "not_found", "unknown"]


class FeatureCoverageSnapshot(FrozenModel):
    object_version: Literal["1.0.0"] = "1.0.0"
    upload_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    input_revision: int = Field(ge=0)
    matrix_location: str | None
    identifier_column: str | None
    complete: bool
    feature_count: int | None = Field(default=None, ge=0)
    semantics: Literal["exact_identifier_membership_not_expression_or_biological_absence"] = "exact_identifier_membership_not_expression_or_biological_absence"
    results: list[FeatureCoverageItem] = Field(max_length=96)

    @model_validator(mode="after")
    def unique(self):
        if len({r.identifier for r in self.results}) != len(self.results):
            raise ValueError("duplicate_feature_query")
        if not self.complete and any(r.state == "not_found" for r in self.results):
            raise ValueError("incomplete_feature_absence")
        return self



class InterpretationGraphRef(FrozenModel):
    graph_id: str = Field(min_length=1)
    graph_version: int = Field(ge=1, strict=True)
    graph_manifest_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


def current_explanation(context):
    """An earlier argument cannot acquire a newer input or graph binding."""
    version = context.explanation_versions[-1] if context.explanation_versions else None
    if version is None or str(version.input_revision) != context.input_revision:
        return None
    if version.object_version == "1.2.0":
        ref = version.graph_ref
        if ref is None or any(getattr(ref, key) != getattr(context, key) for key in
                ("graph_id", "graph_version", "graph_manifest_sha256")):
            return None
    return version

def interpretation_graph(context):
    """Deterministic projection of explicit model judgments; no inferred causal edges."""
    import hashlib
    import json
    nodes, edges = {}, []
    def identity(value):
        return "interpretation:" + hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()[:24]
    def node(key, label, kind, **extra):
        identifier = identity(key)
        nodes[identifier] = {"data": dict(id=identifier, label=label, node_type=kind,
            object_id=identifier, object_version="1.0.0", lifecycle_state="proposed",
            evidence_tier="unverified", **extra)}
        return identifier
    def edge(source, target, kind, **extra):
        edges.append({"data": dict(id=identity([source, target, kind]), source=source,
            target=target, edge_type=kind, qualification="unverified", **extra)})
    # Preserve historical versions in the snapshot, display the latest accepted explanation.
    version = current_explanation(context)
    if version is not None and version.object_version == "1.2.0":
        for i, h in enumerate(version.hypotheses):
            key = [version.content_sha256, i]
            target = node(key, h.statement, "ProposedExplanation")
            for r in h.evidence_relations:
                source = node(["citation", r.evidence_alias], r.evidence_alias, "SourceCitation", citation=r.evidence_alias)
                edge(source, target, r.relation, rationale=r.rationale, applicability=r.applicability)
            if h.competing_explanation:
                rival = node([*key, "rival"], h.competing_explanation, "CompetingExplanation")
                edge(rival, target, "alternative_to")
            if h.expected_observation:
                prediction = node([*key, "prediction"], h.expected_observation, "ProposedObservation")
                edge(prediction, target, "tests")
    return dict(object_version="1.0.0", graph_id=context.graph_id, graph_version=context.graph_version,
        graph_manifest_sha256=context.graph_manifest_sha256,
        explanation_sha256=version.content_sha256 if version else None,
        input_revision=context.input_revision, scope_digest=version.scope_digest if version else None,
        qualification="unverified", elements=dict(nodes=list(nodes.values()), edges=edges),
        returned_node_count=len(nodes), returned_edge_count=len(edges), truncated=False,
        omitted_node_count=0, omitted_edge_count=0)
