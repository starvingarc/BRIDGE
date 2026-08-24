#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml


SNAPSHOT_ID = "BRIDGE-KNOWLEDGE-20260810-v0.1"
ACTIVE_MODULE_IDS = ("P0-01", "P0-02", "P0-03", "P0-04", "P0-08", "P0-09")
PUBLIC_URL = re.compile(r"^https?://", re.IGNORECASE)
SENTINELS = {"internal_no_public_url", "not_registered_in_source"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--verification", type=Path)
    parser.add_argument("--overrides", type=Path)
    args = parser.parse_args()

    verification_path = args.verification or args.repo / "catalog_seed" / "source_verification.json"
    verification = _load_json(verification_path) if verification_path.exists() else {}
    rows, source_hash = _read_registry(args.registry)
    if len(rows) != 396:
        raise ValueError(f"Expected 396 registry rows, found {len(rows)}")
    raw_distinct_public_url_count = len(
        {
            token
            for row in rows
            for token in _split(row["official_url"])
            if PUBLIC_URL.match(token)
        }
    )
    raw_url_token_count = sum(len(_split(row["official_url"])) for row in rows)
    raw_public_url_assignment_count = sum(
        sum(bool(PUBLIC_URL.match(token)) for token in _split(row["official_url"]))
        for row in rows
    )
    override_path = args.overrides or args.repo / "catalog_seed" / "curation_overrides.yaml"
    overrides = _load_yaml(override_path) if override_path.exists() else {}
    rows = _apply_overrides(rows, overrides)

    methods, bindings, aliases = _normalize_methods(rows)
    sources, canonical_url_token_count, canonical_public_assignments = _normalize_sources(methods, verification)
    _write_catalog(
        args.repo,
        methods,
        bindings,
        aliases,
        sources,
        source_hash,
        raw_url_token_count,
        raw_public_url_assignment_count,
        raw_distinct_public_url_count,
        canonical_url_token_count,
        canonical_public_assignments,
    )
    return 0


def _normalize_methods(rows: list[dict[str, Any]]) -> tuple[list[dict], list[dict], list[dict]]:
    by_name: dict[str, list[tuple[int, dict[str, Any]]]] = defaultdict(list)
    for index, row in enumerate(rows, start=5):
        name = str(row["tool_or_method"]).strip()
        by_name[name].append((index, row))
    slug_names: dict[str, set[str]] = defaultdict(set)
    for name in by_name:
        slug_names[_slug(name)].add(name)

    methods: list[dict] = []
    row_to_method: dict[int, str] = {}
    aliases: list[dict] = []
    for name in sorted(by_name, key=str.casefold):
        groups = _connected_alias_groups(by_name[name])
        multiple = len(groups) > 1
        for group in groups:
            group_rows = [row for _, row in group]
            raw_ids = sorted({token for row in group_rows for token in _split(row["tool_id"])})
            suffix = ""
            if multiple or len(slug_names[_slug(name)]) > 1:
                identity = "|".join([name, *raw_ids])
                suffix = "-" + hashlib.sha256(identity.encode()).hexdigest()[:6].upper()
            method_id = f"METHOD-{_slug(name)}{suffix}"
            source_tokens = sorted({token for row in group_rows for token in _split(row["official_url"])})
            raw_source_token_count = sum(len(_split(row["official_url"])) for row in group_rows)
            public_source_assignment_count = sum(
                sum(bool(PUBLIC_URL.match(token)) for token in _split(row["official_url"]))
                for row in group_rows
            )
            public_urls = [token for token in source_tokens if PUBLIC_URL.match(token)]
            internal = any("internal" in str(row["license"]).lower() for row in group_rows) or "internal_no_public_url" in source_tokens
            competitor_isolated = any(
                "competitor-isolated" in str(row["key_boundary"]).lower()
                or "competitor reproduction" in str(row["role"]).lower()
                or "isolated external baseline" in str(row["role"]).lower()
                for row in group_rows
            )
            evidence_families = sorted({token for row in group_rows for token in _split(row["evidence_family"])})
            license_raw = sorted({str(row["license"]).strip() for row in group_rows if str(row["license"]).strip()})
            scientific_status = sorted({str(row["scientific_status"]).strip() for row in group_rows})
            source_status_raw = sorted({str(row["source_status"]).strip() for row in group_rows})
            modules = sorted({str(row["module_id"]).strip() for row in group_rows})
            method = {
                "method_id": method_id,
                "display_name": name,
                "aliases": raw_ids,
                "modules": modules,
                "capabilities": sorted({str(row["capability"]).strip() for row in group_rows}),
                "roles": sorted({str(row["role"]).strip() for row in group_rows}),
                "input_requirements": sorted({str(row["required_input"]).strip() for row in group_rows}),
                "output_semantics": sorted({str(row["formal_output"]).strip() for row in group_rows}),
                "environment_requirements": sorted({str(row["environment_requirement"]).strip() for row in group_rows}),
                "environment_policy": sorted({str(row["environment_policy"]).strip() for row in group_rows}),
                "scientific_status_raw": scientific_status,
                "source_status_raw": source_status_raw,
                "evidence_family_ids": evidence_families,
                "evidence_family_state": "assigned" if evidence_families else "unassigned",
                "license_raw": license_raw,
                "license_status": _license_status(license_raw, internal),
                "version": _single_curated_value(group_rows, "curated_version") or "unresolved",
                "version_status": "reported" if _single_curated_value(group_rows, "curated_version") else "not_frozen",
                "maintenance_status": _single_curated_value(group_rows, "curated_maintenance_status") or "requires_live_review",
                "compute_requirements": sorted({str(row["environment_requirement"]).strip() for row in group_rows}),
                "curation_notes": sorted(
                    {str(row.get("curation_note", "")).strip() for row in group_rows if str(row.get("curation_note", "")).strip()}
                ),
                "source_tokens": source_tokens,
                "raw_source_token_count": raw_source_token_count,
                "public_source_assignment_count": public_source_assignment_count,
                "source_ids": [],
                "source_status": "internal_no_public_source" if internal and not public_urls else ("not_registered" if not public_urls else "registered"),
                "primary_paper_status": "unresolved",
                "critical_boundaries": sorted({str(row["key_boundary"]).strip() for row in group_rows}),
                "retrieval_policy": "competitor_isolated" if competitor_isolated else "registered_local_snapshot",
                "formal_eligible": False,
                "card_ref": f"bridge://knowledge/methods/{method_id}",
                "provenance_refs": [f"MASTER-20260810:Tools:R{excel_row}" for excel_row, _ in group],
            }
            methods.append(method)
            for excel_row, row in group:
                row_to_method[excel_row] = method_id
                reason = "shared_source_alias" if len(group) > 1 else "canonical_name_unique"
                for raw_id in _split(row["tool_id"]):
                    aliases.append(
                        {
                            "raw_tool_id": raw_id,
                            "method_id": method_id,
                            "reason": reason,
                            "module_id": str(row["module_id"]).strip(),
                            "capability": str(row["capability"]).strip(),
                        }
                    )

    bindings: list[dict] = []
    for ordinal, row in enumerate(rows, start=1):
        excel_row = ordinal + 4
        binding = {
            "registry_entry_id": f"BINDING-{ordinal:04d}",
            "module_id": str(row["module_id"]).strip(),
            "method_id": row_to_method[excel_row],
            "raw_tool_id": str(row["tool_id"]).strip(),
            "raw_tool_name": str(row["tool_or_method"]).strip(),
            "capability": str(row["capability"]).strip(),
            "scientific_status_raw": str(row["scientific_status"]).strip(),
            "source_status_raw": str(row["source_status"]).strip(),
            "evidence_family_raw": str(row["evidence_family"]).strip(),
            "provenance_ref": f"MASTER-20260810:Tools:R{excel_row}",
        }
        bindings.append(binding)
    return methods, bindings, _normalize_aliases(aliases)


def _connected_alias_groups(items: list[tuple[int, dict[str, Any]]]) -> list[list[tuple[int, dict[str, Any]]]]:
    if len(items) == 1:
        return [items]
    url_sets = [{value for value in _split(row["official_url"]) if PUBLIC_URL.match(value)} for _, row in items]
    id_sets = [set(_split(row["tool_id"])) for _, row in items]
    remaining = set(range(len(items)))
    groups: list[list[tuple[int, dict[str, Any]]]] = []
    while remaining:
        stack = [remaining.pop()]
        component: set[int] = set(stack)
        while stack:
            current = stack.pop()
            linked = {
                other
                for other in remaining
                if (url_sets[current] and url_sets[current].intersection(url_sets[other]))
                or id_sets[current].intersection(id_sets[other])
            }
            remaining.difference_update(linked)
            component.update(linked)
            stack.extend(linked)
        groups.append([items[index] for index in sorted(component)])
    return sorted(groups, key=lambda group: group[0][0])


def _normalize_sources(methods: list[dict], verification: dict) -> tuple[list[dict], int, int]:
    source_to_methods: dict[str, set[str]] = defaultdict(set)
    raw_url_token_count = 0
    public_assignments = 0
    for method in methods:
        raw_url_token_count += method["raw_source_token_count"]
        public_assignments += method["public_source_assignment_count"]
        for token in method["source_tokens"]:
            if PUBLIC_URL.match(token):
                source_to_methods[token].add(method["method_id"])

    sources: list[dict] = []
    url_to_id: dict[str, str] = {}
    for url in sorted(source_to_methods):
        source_id = "SOURCE-" + hashlib.sha256(url.encode()).hexdigest()[:16].upper()
        url_to_id[url] = source_id
        verified = verification.get(url, {})
        sources.append(
            {
                "source_id": source_id,
                "url": url,
                "source_type": _source_type(url),
                "title": verified.get("title") or url,
                "verification_status": verified.get("status", "not_checked"),
                "http_status": verified.get("http_status"),
                "resolved_url": verified.get("resolved_url"),
                "verified_at": verified.get("checked_at"),
                "access_policy": "public_metadata",
                "method_ids": sorted(source_to_methods[url]),
            }
        )
    by_id = {method["method_id"]: method for method in methods}
    for url, method_ids in source_to_methods.items():
        for method_id in method_ids:
            by_id[method_id]["source_ids"].append(url_to_id[url])
    source_types = {source["source_id"]: source["source_type"] for source in sources}
    for method in methods:
        method["source_ids"] = sorted(method["source_ids"])
        if any(source_types[source_id] == "primary_paper" for source_id in method["source_ids"]):
            method["primary_paper_status"] = "available"
        elif method["source_status"] == "internal_no_public_source":
            method["primary_paper_status"] = "not_applicable"
    return sources, raw_url_token_count, public_assignments


def _write_catalog(
    repo: Path,
    methods: list[dict],
    bindings: list[dict],
    aliases: list[dict],
    sources: list[dict],
    workbook_hash: str,
    raw_url_token_count: int,
    raw_public_url_assignment_count: int,
    raw_distinct_public_url_count: int,
    canonical_url_token_count: int,
    canonical_public_assignments: int,
) -> None:
    knowledge = repo / "knowledge"
    knowledge.mkdir(parents=True, exist_ok=True)

    source_lookup = {source["source_id"]: source for source in sources}
    documents = [_retrieval_document(method, source_lookup) for method in methods if method["retrieval_policy"] != "competitor_isolated"]
    summary = {
        "binding_count": len(bindings),
        "method_count": len(methods),
        "raw_url_token_count": raw_url_token_count,
        "public_url_assignment_count": raw_public_url_assignment_count,
        "raw_distinct_public_url_count": raw_distinct_public_url_count,
        "canonical_url_token_count": canonical_url_token_count,
        "canonical_public_url_assignment_count": canonical_public_assignments,
        "canonical_public_source_count": len(sources),
        "verified_public_source_count": sum(
            str(source["verification_status"]).startswith("verified") for source in sources
        ),
        "unassigned_evidence_family_count": sum(not item["evidence_family_raw"] for item in bindings),
        "formal_eligible_method_count": sum(bool(item["formal_eligible"]) for item in methods),
    }
    snapshot = {
        "snapshot_id": SNAPSHOT_ID,
        "schema_version": "0.1.0",
        "source_registry": "BRIDGE-P0-toolkit-master-20260810",
        "source_registry_sha256": workbook_hash,
        "summary": summary,
        "methods": methods,
        "sources": sources,
        "bindings": bindings,
        "aliases": aliases,
        "documents": documents,
    }
    canonical = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    snapshot["content_hash"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    (knowledge / "active-methods.md").write_text(
        _active_methods_markdown(repo, methods), encoding="utf-8"
    )

    resources = repo / "src" / "bridge" / "resources"
    resources.mkdir(parents=True, exist_ok=True)
    (resources / "__init__.py").write_text('"""Packaged immutable BRIDGE resources."""\n', encoding="utf-8")
    with (resources / "knowledge_snapshot.json.gz").open("wb") as raw_handle:
        with gzip.GzipFile(fileobj=raw_handle, mode="wb", mtime=0) as gzip_handle:
            with io.TextIOWrapper(gzip_handle, encoding="utf-8") as text_handle:
                json.dump(snapshot, text_handle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _active_methods_markdown(repo: Path, methods: list[dict]) -> str:
    method_lookup = {method["method_id"]: method for method in methods}
    active_modules = ", ".join(ACTIVE_MODULE_IDS)
    sections: list[str] = [
        "# Active BRIDGE Methods",
        "",
        f"This generated shortlist mirrors the methods selected by the active {active_modules} Tool Package specs. The packaged snapshot remains the canonical retrieval artifact.",
    ]
    for module_id in ACTIVE_MODULE_IDS:
        spec_path = (
            repo
            / "src"
            / "bridge"
            / "tool_packages"
            / "specs"
            / f"{module_id.lower().replace('-', '_')}.yaml"
        )
        spec = _load_yaml(spec_path)
        method_ids = list(spec["method_ids"])
        missing = sorted(set(method_ids).difference(method_lookup))
        if missing:
            raise ValueError(f"Unknown active methods for {module_id}: {missing}")
        sections.extend(["", f"## {module_id}: {spec['name']}", ""])
        if not method_ids:
            sections.append("No methods are selected while this package remains a scaffold.")
            continue
        sections.extend(
            f"- `{method_id}` — {method_lookup[method_id]['display_name']} ([catalog record]({method_lookup[method_id]['card_ref']}))"
            for method_id in method_ids
        )
    return "\n".join(sections) + "\n"


def _retrieval_document(method: dict, source_lookup: dict[str, dict]) -> dict:
    source_titles = [source_lookup[source_id]["title"] for source_id in method["source_ids"]]
    text = "\n".join(
        [
            method["display_name"],
            "Modules: " + ", ".join(method["modules"]),
            "Capabilities: " + " | ".join(method["capabilities"]),
            "Roles: " + " | ".join(method["roles"]),
            "Inputs: " + " | ".join(method["input_requirements"]),
            "Outputs: " + " | ".join(method["output_semantics"]),
            "Boundaries: " + " | ".join(method["critical_boundaries"]),
            "Sources: " + " | ".join(source_titles),
        ]
    )
    return {
        "document_id": f"DOC-{method['method_id']}",
        "document_type": "method_card",
        "title": method["display_name"],
        "tool_package_ids": method["modules"],
        "method_ids": [method["method_id"]],
        "source_ids": method["source_ids"],
        "retrieval_text": text,
        "allowed_use": ["catalog", "planning", "explanation"],
    }


def _source_type(url: str) -> str:
    lower = url.lower()
    if "doi.org/" in lower or any(host in lower for host in ("pubmed.ncbi.nlm.nih.gov", "pmc.ncbi.nlm.nih.gov", "nature.com/articles", "sciencedirect.com/science/article", "journals.")):
        return "primary_paper"
    if any(host in lower for host in ("github.com", "gitlab.com", "code.bioconductor.org", "git.bioconductor.org")):
        return "source_repository"
    if "rfc-editor.org" in lower or "w3.org/" in lower:
        return "standard"
    if any(host in lower for host in ("readthedocs", "docs.", "bioconductor.org/packages", "scanpy.readthedocs", "satijalab.org")):
        return "official_documentation"
    return "official_resource"


def _license_status(values: list[str], internal: bool) -> str:
    if internal and not values:
        return "internal"
    joined = " ".join(values).lower()
    if "internal" in joined:
        return "internal"
    if not values:
        return "unresolved"
    if any(token in joined for token in ("pending", "verify", "unresolved", "review")):
        return "review_required"
    return "reported"


def _split(value: Any) -> list[str]:
    return [token.strip() for token in str(value).split("|") if token.strip()]


def _slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", value.upper()).strip("-")
    return slug or "UNNAMED"


def _normalize_aliases(items: list[dict]) -> list[dict]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for item in items:
        key = (item["raw_tool_id"], item["method_id"])
        record = grouped.setdefault(
            key,
            {
                "raw_tool_id": item["raw_tool_id"],
                "method_id": item["method_id"],
                "reasons": set(),
                "module_ids": set(),
                "capabilities": set(),
            },
        )
        record["reasons"].add(item["reason"])
        record["module_ids"].add(item["module_id"])
        record["capabilities"].add(item["capability"])
    methods_per_alias: dict[str, set[str]] = defaultdict(set)
    for raw_tool_id, method_id in grouped:
        methods_per_alias[raw_tool_id].add(method_id)
    result: list[dict] = []
    for (raw_tool_id, method_id), record in grouped.items():
        result.append(
            {
                "raw_tool_id": raw_tool_id,
                "method_id": method_id,
                "resolution": "context_required" if len(methods_per_alias[raw_tool_id]) > 1 else "unique",
                "reasons": sorted(record["reasons"]),
                "module_ids": sorted(record["module_ids"]),
                "capabilities": sorted(record["capabilities"]),
            }
        )
    return sorted(result, key=lambda item: (item["raw_tool_id"], item["method_id"]))


def _load_json(path: Path | None) -> dict:
    if path is None:
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _read_registry(path: Path) -> tuple[list[dict[str, Any]], str]:
    if path.suffix.lower() == ".json":
        payload = _load_json(path)
        rows = payload["rows"] if isinstance(payload, dict) else payload
        source_hash = payload.get("source_workbook_sha256") if isinstance(payload, dict) else None
        return [dict(row) for row in rows], source_hash or _sha256_file(path)
    import pandas as pd

    frame = pd.read_excel(path, sheet_name="Tools", header=3).fillna("")
    return [dict(row) for row in frame.to_dict(orient="records")], _sha256_file(path)


def _load_yaml(path: Path) -> dict:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    return payload or {}


def _apply_overrides(rows: list[dict[str, Any]], payload: dict) -> list[dict[str, Any]]:
    method_overrides = payload.get("methods", {})
    updated: list[dict[str, Any]] = []
    for original in rows:
        row = dict(original)
        override = method_overrides.get(str(row["tool_or_method"]).strip(), {})
        if "official_url" in override:
            row["official_url"] = override["official_url"]
        if "license" in override:
            row["license"] = override["license"]
        if "version" in override:
            row["curated_version"] = override["version"]
        if "maintenance_status" in override:
            row["curated_maintenance_status"] = override["maintenance_status"]
        if "note" in override:
            row["curation_note"] = override["note"]
        row["official_url"] = " | ".join(_normalize_source_token(token) for token in _split(row["official_url"]))
        updated.append(row)
    return updated


def _normalize_source_token(token: str) -> str:
    prefix = "https://code.bioconductor.org/browse/"
    if token.startswith(prefix):
        package = token.removeprefix(prefix).strip("/")
        return f"https://git.bioconductor.org/packages/{package}"
    return token


def _single_curated_value(rows: list[dict[str, Any]], field: str) -> str:
    values = sorted({str(row.get(field, "")).strip() for row in rows if str(row.get(field, "")).strip()})
    if len(values) > 1:
        raise ValueError(f"Conflicting curated values for {field}: {values}")
    return values[0] if values else ""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
