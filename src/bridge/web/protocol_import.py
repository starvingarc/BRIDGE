"""Source-linked workbench projection; extraction never confirms a protocol."""
from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Literal
from types import SimpleNamespace

from fastapi import HTTPException
from pydantic import Field

from . import protocol_formalization as formal
from .intake_sources import bounded_passages, protocol_text
from .protocol_compiler import compile_bpl
from .research_object_models import Body, Day, Name, Note, ProtocolContent
from .sessions import uid

IMPORT_VERSION = "research-protocol-import-3"
FORMALIZATION_LIMIT = 16 * 1024 * 1024


@dataclass(frozen=True)
class ProtocolImport:
    name: str
    content: dict
    formalization_id: str
    raw: bytes
    sha256: str


class SourceFields(Body):
    quote: str = Field(min_length=1, max_length=4000)
    source_ids: list[str] = Field(min_length=1, max_length=16)


class SourceDay(SourceFields):
    value: Day


class SourceStage(SourceFields):
    start_day: Day
    end_day: Day


class SourceReagent(SourceFields):
    name: Name
    dose_text: str | None = Field(default=None, max_length=256)
    start_day: Day | None = None
    end_day: Day | None = None


class SourceOperation(SourceFields):
    day: Day | None = None
    kind: Literal["feed", "passage", "sample", "freeze", "other"]
    note: Note


class ImportContent(Body):
    total_days: SourceDay | None = None
    stages: list[SourceStage] = Field(default_factory=list, max_length=4)
    reagents: list[SourceReagent] = Field(default_factory=list, max_length=256)
    operations: list[SourceOperation] = Field(default_factory=list, max_length=512)


class ImportProposal(formal.ProtocolProposal):
    content: ImportContent


INSTRUCTIONS = """
Additionally return content using ImportContent in the supplied schema.
This is a single uploaded protocol, never combine alternative protocols into a recipe.
content is a workbench index of the SAME source-backed BPL steps, not a new protocol.
For every content row supply a verbatim quote and its source_ids.
Copy reagent name and dose_text verbatim from that quote, preserving units.
Each name and dose_text must be ONE CONTIGUOUS substring of its quote.
Do not splice a reagent name together with a supplier/catalog suffix from elsewhere
in its parenthesis. When a parenthesis contains both dose and supplier, either use
the bare reagent name or copy the entire contiguous original name/parenthesis;
never remove the intervening dose and rejoin the remaining pieces.
A reagent quote must include the COMPLETE governing culture clause, including its timing.
For a culture clause with an explicitly written day interval, copy that interval to every
reagent listed in that SAME clause. This is direct extraction, not duration arithmetic.
Do not shorten the quote to a reagent name/dose and then incorrectly mark its written
window as missing. Do not propagate a window across unrelated steps or alternative recipes.
Include every reagent, even if its dose or day window is absent; absent values are null.
Day fields are absolute, explicitly stated protocol day numbers only; never derive them
from relative durations or resolve alternate/ambiguous windows. Such fields are null.
total_days is only an explicitly stated total protocol duration in days, else null.
stages are only explicitly named source stages, in source order, at most four;
do not invent the default four stages. If stage boundaries are unclear, leave stages empty.
Each operation note is copied verbatim from its quote; unknown operation day is null.
Do not return catalog IDs, pathway, reagent kind or claims of confirmation.
Unscheduled operations and questions must still be represented in the BPL steps/questions.
"""


def _check_source(row, sources, *, text_fields=(), day_fields=()):
    if not set(row.source_ids) <= sources.keys():
        raise ValueError("unknown_projection_source")
    if not any(row.quote in sources[sid]["text"] for sid in row.source_ids):
        raise ValueError("unsupported_projection_quote")
    for field in text_fields:
        value = getattr(row, field)
        if value is not None and value not in row.quote:
            raise ValueError("unsupported_projection_text")
    for field in day_fields:
        value = getattr(row, field)
        if value is not None and not re.search(r"(?<![\w.])" + str(value) + r"(?!\w|\.\d)", row.quote):
            raise ValueError("unsupported_projection_day")


def _catalog_matches(path):
    try:
        compounds = json.loads(path.read_text())["compounds"]
        result = {}
        for compound in compounds:
            for name in [compound["name"], *compound.get("aliases", [])]:
                result.setdefault(name.casefold(), set()).add(compound["id"])
        return {name: next(iter(ids)) for name, ids in result.items() if len(ids) == 1}
    except (OSError, ValueError, KeyError, TypeError):
        # Optional catalog is not a reason to lose a textual protocol draft.
        return {}


def project(content, sources, catalog_path):
    result = {"total_days": None, "stages": [], "reagents": [], "operations": [],
              "unconfirmed": ["source_review", "total_days", "stages", "operations"]}
    if content.total_days:
        _check_source(content.total_days, sources, day_fields=("value",))
        result["total_days"] = content.total_days.value
    for index, stage in enumerate(content.stages, 1):
        _check_source(stage, sources, day_fields=("start_day", "end_day"))
        result["stages"].append({"index": index, "start_day": stage.start_day, "end_day": stage.end_day})
    catalog = _catalog_matches(catalog_path)
    for reagent in content.reagents:
        _check_source(reagent, sources, text_fields=("name", "dose_text"), day_fields=("start_day", "end_day"))
        start, end = reagent.start_day, reagent.end_day
        locations = "; ".join(f"{sid}: {sources[sid]['location']}" for sid in reagent.source_ids)
        result["reagents"].append({
            "id": uid(), "name": reagent.name, "short": reagent.name[:80], "pathway": "other",
            "kind": "molecule" if reagent.name.casefold() in catalog else "supplement",
            "dose_text": reagent.dose_text or "", "start_day": start, "end_day": end,
            "catalog_id": catalog.get(reagent.name.casefold()), "source_locator": locations[:500],
            "timing_text": reagent.quote[:2000] if start is None or end is None else "",
            "unconfirmed": ["name", "short", "pathway", "kind", "dose_text", "start_day", "end_day", "source_locator"],
        })
    for operation in content.operations:
        _check_source(operation, sources, text_fields=("note",), day_fields=("day",))
        locations = "; ".join(f"{sid}: {sources[sid]['location']}" for sid in operation.source_ids)
        result["operations"].append({"day": operation.day, "kind": operation.kind, "note": operation.note,
                                     "timing_text": operation.quote[:2000] if operation.day is None else "",
                                     "source_locator": locations[:500]})
    return ProtocolContent.model_validate(result).model_dump(mode="json")


def prepare(researches, owner, rid, mid, settings, catalog_path):
    """Authorize/read before external work; no object-store lock spans model calls."""
    try:
        material = researches.material(owner, rid, mid)
    except HTTPException as exc:
        if exc.status_code == 404:
            raise HTTPException(404, "material_not_found") from None
        raise
    if material["kind"] != "protocol":
        raise HTTPException(422, "protocol_material_required")
    try:
        with researches.checked_material(owner, rid, mid) as stream:
            extracted = bounded_passages(protocol_text(material["name"], stream.read()))
        if not extracted or len(extracted) > 256 or sum(len(p["text"]) for p in extracted) > 96000:
            raise ValueError("source_scope_exceeded")
    except (OSError, ValueError):
        raise HTTPException(422, "protocol_source_invalid") from None
    sources = [{"id": f"S{i}", "kind": "protocol", "label": "方案原文",
                "location": passage["location"], "text": passage["text"]}
               for i, passage in enumerate(extracted, 1)]
    supplied = {"purpose": "protocol_formalization", "sources": sources,
                "sources_truncated": False, "supplements": []}
    try:
        draft = formal.generate(settings, supplied, proposal_model=ImportProposal,
                                proposal_instructions=INSTRUCTIONS)
        compiled = compile_bpl(draft.bpl, settings.protocol_compiler_python)
        if compiled["compiler_state"] == "unavailable":
            raise HTTPException(503, "protocol_compiler_unavailable")
        if compiled["compiler_state"] != "passed" or compiled["syntax_state"] != "passed":
            raise ValueError("compilation_failed")
        mapped = formal.validate_draft(draft, supplied, compiled)
        if not draft.steps or not mapped:
            raise ValueError("incomplete_representation")
        proposal = ImportProposal.model_validate(draft._proposal)
        represented_sources = {sid for step in draft.steps for sid in step.source_ids}
        content = project(proposal.content, {s["id"]: s for s in sources
                                            if s["id"] in represented_sources}, catalog_path)
    except formal.ProtocolResponseError as exc:
        code = str(exc)
        if code == "protocol_provider_unavailable":
            raise HTTPException(502, code) from None
        raise HTTPException(422, "protocol_import_invalid") from None
    except (ValueError, KeyError, TypeError):
        raise HTTPException(422, "protocol_import_invalid") from None
    binding = {"material_id": mid, "protocol_sha256": material["sha256"],
               "extractor_version": formal.EXTRACTOR_VERSION, "projection_version": IMPORT_VERSION,
               "context_sha256": formal._sha(formal._bytes(supplied)),
               "source_hashes": {s["id"]: formal._sha(s["text"].encode()) for s in sources}}
    work = {"context": supplied, "binding": binding, "generation": 1}
    version = formal._make_version(SimpleNamespace(settings=settings), work, draft, compiled, mapped, 1)
    version.pop("_draft", None)
    version["projection"] = proposal.content.model_dump(mode="json")
    version["projected_content"] = content
    version["artifacts"] = {"ast": compiled["ast"], "plan": compiled["plan"]}
    raw = formal._bytes(version)
    if len(raw) > FORMALIZATION_LIMIT:
        raise HTTPException(413, "protocol_formalization_limit")
    return ProtocolImport(material["name"], content, version["id"], raw, formal._sha(raw))
