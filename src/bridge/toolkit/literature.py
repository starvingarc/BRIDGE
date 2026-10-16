"""Frozen literature provenance for research interpretation, never measurement evidence."""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Annotated, Literal
from pydantic import Field, model_validator

from .contracts import FrozenModel

PUBLIC_CONCEPTS = {
    "human_pluripotent_stem_cell": "human pluripotent stem cell",
    "neural_progenitor": "neural progenitor", "neuron": "neuron",
    "midbrain_dopaminergic_neuron": "midbrain dopaminergic neuron",
    "astrocyte": "astrocyte", "oligodendrocyte": "oligodendrocyte",
}
FOCI = {"identity": "identity OR differentiation", "development": "maturation OR development",
        "proliferation": '"cell cycle" OR proliferation', "stress": "stress OR apoptosis"}
SourceRef = Annotated[str, Field(pattern=r"^literature:epmc-med-[0-9]{1,12}$")]
Hash = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]


def content_hash(value) -> str:
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def public_query(refs, focus):
    if (not refs or len(refs) > 2 or len(set(refs)) != len(refs)
            or not set(refs) <= set(PUBLIC_CONCEPTS) or focus not in FOCI):
        raise ValueError("invalid_public_concept")
    return "SRC:MED AND " + " AND ".join('TITLE_ABS:("' + PUBLIC_CONCEPTS[key] + '")'
        for key in refs) + " AND TITLE_ABS:(" + FOCI[focus] + ")"


class LiteratureCorrection(FrozenModel):
    type: str = Field(min_length=1, max_length=120)
    id: str | None = Field(max_length=100)
    source: str | None = Field(max_length=30)
    reference: str | None = Field(max_length=1000)
    note: str | None = Field(max_length=1000)


def publication_status(publication_types, corrections):
    labels = [*(publication_types or []), *(row["type"] for row in (corrections or []))]
    normalized = ["".join(character for character in label.lower() if character.isalpha()) for label in labels]
    if any("retract" in label or "expressionofconcern" in label for label in normalized):
        return "retraction_or_concern_reported"
    if any("errat" in label or "correct" in label for label in normalized):
        return "correction_reported"
    return "unknown" if publication_types is None or corrections is None else "no_flag_reported"


class LiteratureMetadata(FrozenModel):
    source_ref: SourceRef
    provider: Literal["europe_pmc"]
    provider_id: str = Field(pattern=r"^[0-9]{1,12}$")
    pmid: str = Field(pattern=r"^[0-9]{1,12}$")
    doi: str | None
    title: str = Field(min_length=1, max_length=2000)
    year: str | None = Field(max_length=4)
    authors: str | None = Field(max_length=4000)
    journal: str | None = Field(max_length=500)
    url: str
    publication_types: list[Annotated[str, Field(min_length=1, max_length=120)]] | None = Field(max_length=20)
    corrections: list[LiteratureCorrection] | None = Field(max_length=20)
    publication_status: Literal["unknown", "no_flag_reported", "correction_reported", "retraction_or_concern_reported"]

    @model_validator(mode="after")
    def identity(self):
        corrections = None if self.corrections is None else [row.model_dump() for row in self.corrections]
        if self.publication_status != publication_status(self.publication_types, corrections):
            raise ValueError("literature_publication_status_mismatch")
        if (self.source_ref != "literature:epmc-med-" + self.provider_id
                or self.pmid != self.provider_id
                or self.url != "https://europepmc.org/article/MED/" + self.provider_id):
            raise ValueError("literature_metadata_identity_mismatch")
        return self


class LiteratureSource(FrozenModel):
    object_version: Literal["1.0.0"]
    source_ref: SourceRef
    url: str
    metadata: LiteratureMetadata
    retrieved_at: str = Field(min_length=1, max_length=50)
    content_level: Literal["abstract", "metadata_only"]
    abstract: str | None = Field(max_length=12000)
    abstract_sha256: Hash | None
    content_sha256: Hash

    @model_validator(mode="after")
    def binding(self):
        if self.source_ref != self.metadata.source_ref or self.url != self.metadata.url:
            raise ValueError("literature_source_identity_mismatch")
        if self.content_level == "abstract":
            if not self.abstract or self.abstract_sha256 != sha256(self.abstract.encode()).hexdigest():
                raise ValueError("literature_abstract_hash_mismatch")
        elif self.abstract is not None or self.abstract_sha256 is not None:
            raise ValueError("literature_metadata_has_abstract")
        if self.content_sha256 != content_hash(self.model_dump(mode="json", exclude={"content_sha256"})):
            raise ValueError("literature_source_hash_mismatch")
        return self


class LiteratureUse(FrozenModel):
    source_ref: SourceRef
    rationale: str = Field(min_length=1, max_length=600)
    species: str = Field(min_length=1, max_length=240)
    lineage: str = Field(min_length=1, max_length=240)
    stage: str = Field(min_length=1, max_length=240)
    experimental_context: str = Field(min_length=1, max_length=400)
    qualification: Literal["unverified_applicability"] = "unverified_applicability"


class LiteratureSearch(FrozenModel):
    action: Literal["search_literature"]
    request_number: int = Field(ge=1)
    concept_refs: list[str] = Field(min_length=1, max_length=2)
    focus: str
    state: Literal["reserved", "complete", "partial", "no_results", "unavailable"]
    query: str | None = None
    hit_count: int | None = Field(default=None, ge=0)
    completed_at: str | None = None
    source_refs: list[SourceRef] = Field(default_factory=list, max_length=5)

    @model_validator(mode="after")
    def public_only(self):
        expected = public_query(self.concept_refs, self.focus)
        if self.query is not None and self.query != expected:
            raise ValueError("literature_query_not_public_projection")
        return self


class LiteratureRead(FrozenModel):
    action: Literal["read_literature"]
    request_number: int = Field(ge=1)
    source_ref: SourceRef
    state: Literal["reserved", "complete", "partial", "unavailable"]
    completed_at: str | None = None


class LiteratureSnapshot(FrozenModel):
    enabled: bool
    concept_refs: list[str] = Field(max_length=6)
    max_searches: int = Field(ge=1, le=3)
    max_reads: int = Field(ge=1, le=6)
    searches_used: int = Field(ge=0, le=3)
    reads_used: int = Field(ge=0, le=6)
    requests: list[Annotated[LiteratureSearch | LiteratureRead, Field(discriminator="action")]] = Field(max_length=9)
    sources: list[LiteratureSource] = Field(max_length=6)

    @model_validator(mode="after")
    def source_bindings(self):
        if (len(set(self.concept_refs)) != len(self.concept_refs)
                or not set(self.concept_refs) <= set(PUBLIC_CONCEPTS)
                or self.enabled != bool(self.concept_refs)
                or self.searches_used > self.max_searches or self.reads_used > self.max_reads):
            raise ValueError("literature_consent_invalid")
        searches = [r for r in self.requests if r.action == "search_literature"]
        reads = [r for r in self.requests if r.action == "read_literature"]
        if len(searches) != self.searches_used or len(reads) != self.reads_used:
            raise ValueError("literature_budget_mismatch")
        if not self.enabled and (self.requests or self.sources):
            raise ValueError("literature_disabled_has_results")
        found, completed_reads = set(), set()
        for number, request in enumerate(self.requests, 1):
            if request.request_number != number:
                raise ValueError("literature_request_order_invalid")
            if request.action == "search_literature":
                if not set(request.concept_refs) <= set(self.concept_refs):
                    raise ValueError("literature_search_outside_consent")
                found.update(request.source_refs)
            else:
                if request.source_ref not in found:
                    raise ValueError("literature_read_not_discovered")
                if request.state in {"complete", "partial"}:
                    completed_reads.add(request.source_ref)
        refs = [s.source_ref for s in self.sources]
        keys = [s.metadata.doi or s.source_ref for s in self.sources]
        if len(keys) != len(set(keys)) or set(refs) != completed_reads:
            raise ValueError("literature_read_sources_mismatch")
        return self
