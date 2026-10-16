"""Bounded Europe PMC discovery and abstract reads; no product text or arbitrary URLs."""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from html.parser import HTMLParser
import json
import re
import time

import httpx

from bridge.toolkit.literature import PUBLIC_CONCEPTS, FOCI, LiteratureSource, LiteratureSnapshot, LiteratureMetadata, public_query, publication_status

ENDPOINT = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
MAX_RESPONSE_BYTES = 512_000


def _now():
    return datetime.now(timezone.utc).isoformat()


def _ref(identifier):
    return "literature:epmc-med-" + identifier


def _fetch(query):
    deadline = time.monotonic() + 20
    with httpx.Client(timeout=20, follow_redirects=False) as client:
        with client.stream("GET", ENDPOINT, params={
                "query": query, "format": "json", "resultType": "core", "pageSize": "5"}) as response:
            response.raise_for_status()
            body = bytearray()
            for chunk in response.iter_bytes():
                body.extend(chunk)
                if time.monotonic() > deadline or len(body) > MAX_RESPONSE_BYTES:
                    raise ValueError("literature_response_limit")
    value = json.loads(body)
    if not isinstance(value, dict) or type(value.get("hitCount")) is not int or value["hitCount"] < 0:
        raise ValueError("literature_response_invalid")
    rows = value.get("resultList", {}).get("result")
    if not isinstance(rows, list) or len(rows) > 5:
        raise ValueError("literature_response_invalid")
    return rows, value["hitCount"]


def _metadata(row):
    if not isinstance(row, dict) or row.get("source") != "MED":
        raise ValueError("literature_source_invalid")
    identifier = row.get("id")
    title = row.get("title")
    if (not isinstance(identifier, str) or not re.fullmatch(r"[0-9]{1,12}", identifier)
            or not isinstance(title, str) or not title.strip() or len(title) > 2000):
        raise ValueError("literature_source_invalid")
    doi = row.get("doi")
    if doi is not None and (not isinstance(doi, str) or
            not re.fullmatch(r"10\.[0-9]{4,9}/[^\s<>\"]{1,200}", doi)):
        doi = None
    def bounded(name, limit):
        value = row.get(name)
        return value if isinstance(value, str) and len(value) <= limit else None
    journal = bounded("journalTitle", 500)
    info = row.get("journalInfo")
    if journal is None and isinstance(info, dict) and isinstance(info.get("journal"), dict):
        title_value = info["journal"].get("title")
        journal = title_value if isinstance(title_value, str) and len(title_value) <= 500 else None
    def rows_at(parent, child):
        group = row.get(parent)
        if group is None:
            return None
        values = group.get(child) if isinstance(group, dict) else None
        if not isinstance(values, list) or len(values) > 20:
            raise ValueError("literature_publication_metadata_invalid")
        return values
    publication_types = rows_at("pubTypeList", "pubType")
    correction_rows = rows_at("commentCorrectionList", "commentCorrection")
    corrections = None
    if correction_rows is not None:
        if any(not isinstance(item, dict) for item in correction_rows):
            raise ValueError("literature_correction_invalid")
        corrections = [{key: item.get(key) for key in ("type", "id", "source", "reference", "note")}
                       for item in correction_rows]
    metadata = {"source_ref": _ref(identifier), "provider": "europe_pmc", "provider_id": identifier,
            "pmid": identifier, "doi": doi.lower() if doi else None, "title": title.strip(),
            "year": bounded("pubYear", 4), "authors": bounded("authorString", 4000),
            "journal": journal,
            "url": "https://europepmc.org/article/MED/" + identifier,
            "publication_types": publication_types, "corrections": corrections,
            "publication_status": publication_status(publication_types, corrections)}
    return LiteratureMetadata.model_validate(metadata).model_dump(mode="json")


def search(concept_refs: list[str], focus: str) -> dict:
    query = public_query(concept_refs, focus)
    base = {"provider": "europe_pmc", "query": query, "concept_refs": concept_refs,
            "focus": focus, "retrieved_at": _now(), "sources": [], "hit_count": None}
    try:
        rows, hit_count = _fetch(query)
        seen, sources, malformed = set(), [], False
        for row in rows:
            try:
                item = _metadata(row)
            except ValueError:
                malformed = True
                continue
            key = item["doi"] or item["source_ref"]
            if key not in seen:
                seen.add(key)
                sources.append(item)
        return {**base, "sources": sources, "hit_count": hit_count,
                "state": ("no_results" if hit_count == 0 and not rows else
                          "partial" if malformed or hit_count > len(sources) else "complete")}
    except (httpx.HTTPError, ValueError, TypeError, KeyError, AttributeError):
        return {**base, "state": "unavailable"}


class _AbstractText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
    def handle_data(self, data):
        self.parts.append(data)
    def handle_starttag(self, tag, attrs):
        if tag.lower() in {"p", "br", "div", "section", "title"}:
            self.parts.append(" ")
    def handle_endtag(self, tag):
        if tag.lower() in {"p", "div", "section", "title"}:
            self.parts.append(" ")


def read(discovered: dict) -> dict:
    # The caller supplies a discovery record from its own approved scope.
    identifier = discovered.get("provider_id")
    if (not isinstance(identifier, str) or not re.fullmatch(r"[0-9]{1,12}", identifier)
            or discovered.get("source_ref") != _ref(identifier)):
        raise ValueError("invalid_literature_source_ref")
    try:
        rows, _ = _fetch('SRC:MED AND EXT_ID:' + identifier)
        if len(rows) != 1:
            raise ValueError("literature_source_missing")
        metadata = _metadata(rows[0])
        if metadata["source_ref"] != discovered["source_ref"]:
            raise ValueError("literature_source_mismatch")
        raw = rows[0].get("abstractText")
        abstract = None
        if isinstance(raw, str) and raw.strip() and len(raw) <= 12_000:
            parser = _AbstractText()
            parser.feed(raw)
            abstract = " ".join("".join(parser.parts).split()) or None
        source = {"object_version": "1.0.0", "source_ref": metadata["source_ref"],
                  "url": metadata["url"], "metadata": metadata, "retrieved_at": _now(),
                  "content_level": "abstract" if abstract else "metadata_only",
                  "abstract": abstract,
                  "abstract_sha256": sha256(abstract.encode()).hexdigest() if abstract else None}
        source["content_sha256"] = sha256(json.dumps(source, ensure_ascii=False,
            sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
        source = LiteratureSource.model_validate(source).model_dump(mode="json")
        return {"state": "complete" if abstract else "partial", "source": source}
    except (httpx.HTTPError, ValueError, TypeError, KeyError, AttributeError):
        return {"state": "unavailable", "source": None}


def _state(assessment):
    return assessment.setdefault("literature", {"searches_used": 0, "reads_used": 0,
        "requests": [], "discovered": [], "sources": []})


def model_context(assessment, scope):
    state = assessment.get("literature", {})
    enabled = scope.literature_enabled
    sources = state.get("sources", [])
    consumed = {row["source_ref"] for row in state.get("requests", []) if row["action"] == "read_literature"}
    return {"state": ("disabled" if not enabled else
                      (state.get("requests") or [{"state": "not_searched"}])[-1]["state"]),
            "search_concept_refs": scope.literature_concept_refs if enabled else [],
            "searches_remaining": max(0, scope.max_literature_searches - state.get("searches_used", 0)) if enabled else 0,
            "reads_remaining": max(0, scope.max_literature_reads - state.get("reads_used", 0)) if enabled else 0,
            "readable_source_refs": [row["source_ref"] for row in state.get("discovered", [])
                                     if row["source_ref"] not in consumed] if enabled else [],
            "request_history": [{key: row[key] for key in
                ("action", "concept_refs", "focus", "source_ref", "state") if key in row}
                for row in state.get("requests", [])],
            "discovered": state.get("discovered", []),
            "sources": sources,
            "read_before_explanation": bool(enabled and state.get("discovered")
                and not state.get("reads_used", 0) and scope.max_literature_reads > 0)}


def public_context(assessment, scope):
    state = assessment.get("literature", {})
    return {"enabled": scope.literature_enabled, "concept_refs": scope.literature_concept_refs,
            "max_searches": scope.max_literature_searches, "max_reads": scope.max_literature_reads,
            "searches_used": state.get("searches_used", 0), "reads_used": state.get("reads_used", 0),
            "state": model_context(assessment, scope)["state"],
            "requests": state.get("requests", []), "sources": state.get("sources", [])}


def reserve(assessment, scope, decision):
    from copy import deepcopy
    if not scope.literature_enabled:
        raise ValueError("literature_disabled")
    state = _state(assessment)
    action = decision["action"]
    if action == "search_literature":
        refs, focus = sorted(decision["concept_refs"]), decision["focus"]
        if (not refs or not set(refs) <= set(scope.literature_concept_refs)
                or focus not in FOCI or state["searches_used"] >= scope.max_literature_searches):
            raise ValueError("literature_search_unavailable")
        request = {"action": action, "concept_refs": refs, "focus": focus}
        if any(all(row.get(key) == value for key, value in request.items()) for row in state["requests"]):
            raise ValueError("literature_search_repeated")
        state["searches_used"] += 1
    elif action == "read_literature":
        source = next((row for row in state["discovered"] if row["source_ref"] == decision["source_ref"]), None)
        if (source is None or state["reads_used"] >= scope.max_literature_reads
                or any(row.get("source_ref") == decision["source_ref"] for row in state["requests"])):
            raise ValueError("literature_read_unavailable")
        request = {"action": action, "source_ref": decision["source_ref"], "discovered": deepcopy(source)}
        state["reads_used"] += 1
    else:
        raise ValueError("literature_action_invalid")
    request.update(request_number=len(state["requests"]) + 1, state="reserved")
    state["requests"].append(deepcopy(request))
    return request


def execute(reservation):
    if reservation["action"] == "search_literature":
        return search(reservation["concept_refs"], reservation["focus"])
    return read(reservation["discovered"])


def complete(assessment, reservation, result):
    from copy import deepcopy
    state = _state(assessment)
    number = reservation["request_number"]
    if len(state["requests"]) != number or state["requests"][-1] != reservation:
        raise ValueError("literature_reservation_stale")
    state["requests"][-1].update(state=result["state"], completed_at=_now())
    if reservation["action"] == "search_literature":
        state["requests"][-1].update(query=result["query"], hit_count=result["hit_count"],
            source_refs=[row["source_ref"] for row in result["sources"]])
        seen = {row["doi"] or row["source_ref"] for row in state["discovered"]}
        for source in result["sources"]:
            key = source["doi"] or source["source_ref"]
            if key not in seen:
                state["discovered"].append(deepcopy(source))
                seen.add(key)
    elif result["source"] is not None:
        state["sources"].append(deepcopy(result["source"]))


def freeze(assessment, scope):
    context = public_context(assessment, scope)
    context.pop("state")
    context["requests"] = [{key: value for key, value in row.items() if key != "discovered"}
                           for row in context["requests"]]
    return LiteratureSnapshot.model_validate(context).model_dump(mode="json")
