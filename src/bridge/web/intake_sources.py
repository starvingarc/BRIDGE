"""Source-bound private intake summaries; no expression matrices enter model context."""
from __future__ import annotations

from collections import Counter
import io
import json
import math
from pathlib import Path
import re
import selectors
import subprocess
import tempfile
import time
import zipfile
from xml.etree import ElementTree

from .inputs import checked_bytes

TEXT_LIMIT = 128_000
PROTOCOL_LIMIT = 25 * 1024 * 1024
ROW_LIMIT = 1_000_000
SEMANTIC = re.compile(r"day|time|harvest|stage|assay|method|protocol|cell.?type|cell.?line|organism|species|treatment|starting|target", re.I)
IDENTITY = re.compile(r"sample|capture|donor|patient|barcode|gene|subject|batch|replicate|culture.?id|library.?id", re.I)


def clean_text(value):
    text = str(value)
    text = re.sub(r"(?i)(?:bearer\s+\S+|(?:api[_-]?key|token|password|secret)\s*[:=]\s*\S+)", "[redacted]", text)
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[email]", text)
    text = re.sub(r"(?:/(?:Users|home|data\d*|tmp|private|mnt)/[^\s,;]+|[A-Z]:\\[^\s]+)", "[private path]", text)
    return re.sub(r"[\x00-\x08\x0b\x0e-\x1f]", "", text)


def scalar(value):
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if hasattr(value, "item"):
        value = value.item()
    if value is None or isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    return None


def column(group, name):
    """Read metadata only, with explicit complete/truncated status."""
    import h5py
    item = group[name]
    if isinstance(item, h5py.Dataset) and item.ndim == 1:
        return [scalar(x) for x in item[:ROW_LIMIT]], item.shape[0] <= ROW_LIMIT
    if isinstance(item, h5py.Group) and "categories" in item and "codes" in item:
        categories = item["categories"]
        if categories.ndim != 1 or categories.shape[0] > ROW_LIMIT:
            return [], False
        values = [scalar(x) for x in categories[:]]
        codes = item["codes"]
        if codes.ndim != 1:
            return [], False
        return [values[int(x)] if 0 <= x < len(values) else None for x in codes[:ROW_LIMIT]], codes.shape[0] <= ROW_LIMIT
    if isinstance(item, h5py.Group) and "values" in item and "mask" in item:
        values = item["values"][:ROW_LIMIT]
        mask = item["mask"][:ROW_LIMIT]
        return [None if m else scalar(x) for x, m in zip(values, mask)], len(values) == item["values"].shape[0]
    return [], False


def identity_values(state, aid, data):
    """Build a complete local mask inventory from the checked upload, never cache it."""
    import h5py
    declared = set()
    records = [
        state.get("_asset_declarations", {}).get(aid, {}).get("metadata", {}),
        state.get("_qc_declarations", {}).get(aid, {}).get("metadata", {}),
        state.get("_intakes", {}).get(aid, {}).get("facts", {}),
        state.get("_intake_autofill", {}).get(aid, {}).get("values", {}),
    ]
    # Changing the analysis selector does not declassify identities in the same upload.
    records.extend(record.get("facts", {}) for record in state.get("_intake_history", [])
                   if record.get("upload_id") == aid)
    for record in records:
        declared.update(record[field] for field in
                        ("sample_id_column", "capture_id_column", "culture_batch_column") if record.get(field))
    masks = set()
    with h5py.File(io.BytesIO(data), "r") as handle:
        obs = handle["obs"]
        index = obs.attrs.get("_index", "_index")
        if isinstance(index, bytes):
            index = index.decode()
        rows, complete = column(obs, index)
        keys = declared | {index} | {key for key in obs if IDENTITY.search(key)}
        if not complete or len(keys) > 256:
            raise ValueError("intake_identity_inventory_incomplete")
        for key in keys:
            if key not in obs:
                raise ValueError("intake_identity_inventory_incomplete")
            values, complete = (rows, True) if key == index else column(obs, key)
            if not complete or len(values) != len(rows):
                raise ValueError("intake_identity_inventory_incomplete")
            masks.update(str(value) for value in values if value is not None and str(value))
            if len(masks) > ROW_LIMIT:
                raise ValueError("intake_identity_inventory_incomplete")
    return sorted(masks, key=len, reverse=True)


def redact_identities(text, identities):
    text = clean_text(text)
    for identity in identities:
        if identity in text:
            text = re.sub(r"(?<!\w)" + re.escape(identity) + r"(?!\w)", "[sample identifier]", text)
    return text


def day_value(value):
    if value is None or isinstance(value, bool):
        return None
    match = re.fullmatch(r"(?:day\s*|d)?(\d{1,4})(?:\.0)?", str(value).strip(), re.I)
    return int(match[1]) if match else None


def metadata(service, state, aid):
    import h5py
    upload = state["_uploads"][aid]
    path = service.directory(state["id"]) / "uploads" / (aid + ".h5ad")
    data = checked_bytes(service, state, path, upload["sha256"], limit=service.settings.upload_limit)
    sources, values, field_sources, samples, masks = [], {}, {}, [], set()
    def add(label, text, **extra):
        source = {"id": f"M{len(sources) + 1}", "kind": "metadata", "label": label,
                  "location": label, "text": clean_text(text), **extra}
        sources.append(source)
        return source["id"]
    def fill(field, value, sid):
        values[field] = value
        field_sources[field] = {"kind": "metadata", "source_ids": [sid], "quote": str(value)}
    with h5py.File(io.BytesIO(data), "r") as handle:
        obs, var = handle["obs"], handle["var"]
        cols = {}
        for key in list(obs)[:256]:
            if key in {"sample_id", "capture_id"} or (SEMANTIC.search(key) and not IDENTITY.search(key)):
                vals, complete = column(obs, key)
                cols[key] = (vals, complete)
                if key in {"sample_id", "capture_id"}:
                    masks.update(str(x) for x in vals if x is not None)
                    sid = add("obs." + key, "Identifier column present; values withheld.")
                    fill(key + "_column", key, sid)
                elif vals:
                    counts = Counter(json.dumps(x, ensure_ascii=False) for x in vals)
                    text = "\n".join(f"{json.loads(k)} ({n} observations)" for k, n in counts.most_common(24))
                    text += f"\nComplete rows: {complete}; distinct values: {len(counts)}; values truncated: {len(counts) > 24}."
                    sid = add("obs." + key, text, complete=complete, uniform=complete and len(counts) == 1)
                    if key in {"culture_day", "differentiation_day", "day"} and complete and vals:
                        days = [day_value(x) for x in vals]
                        if None not in days and len(set(days)) == 1:
                            fill("culture_day", days[0], sid)
        if "gene_symbol" in var:
            sid = add("var.gene_symbol", "Gene symbol column present; gene values withheld.")
            fill("gene_symbol_column", "gene_symbol", sid)
        if "feature_type" in var:
            vals, complete = column(var, "feature_type")
            add("var.feature_type", json.dumps(sorted({clean_text(x)[:160] for x in vals if x is not None})[:24]),
                complete=complete)
        day_cols = [key for key in cols if key in {"culture_day", "differentiation_day", "day"}]
        if "sample_id" in cols and day_cols:
            identifiers, identity_complete = cols["sample_id"]
            days, days_complete = cols[day_cols[0]]
            if identity_complete and days_complete and len(identifiers) == len(days):
                groups = {}
                for sample, day in zip(identifiers, days):
                    group = groups.setdefault(str(sample) if sample is not None else "(missing)", {"days": set(), "missing": 0, "n": 0})
                    parsed = day_value(day)
                    if parsed is None:
                        group["missing"] += 1
                    else:
                        group["days"].add(parsed)
                    group["n"] += 1
                for sample, group in list(groups.items())[:256]:
                    samples.append({"sample_id": sample, "culture_days": sorted(group["days"]),
                                    "missing_days": group["missing"], "n_observations": group["n"],
                                    "sample_summary_complete": len(groups) <= 256})
        def uns(group, prefix="uns", depth=0):
            if depth > 3:
                return
            for key in list(group)[:64]:
                if len(sources) >= 100 or IDENTITY.search(key):
                    continue
                item = group[key]
                label = prefix + "." + key
                if isinstance(item, h5py.Group):
                    uns(item, label, depth + 1)
                elif SEMANTIC.search(key) and isinstance(item, h5py.Dataset) and item.size <= 24:
                    raw = item[()]
                    vals = [scalar(raw)] if item.ndim == 0 else [scalar(x) for x in raw.reshape(-1)]
                    add(label, json.dumps(vals, ensure_ascii=False)[:3000], complete=True)
        if "uns" in handle:
            uns(handle["uns"])
    if len(upload["locations"]) == 1:
        sid = add("matrix locations", json.dumps(upload["locations"]))
        fill("matrix_location", upload["locations"][0], sid)
    return {"values": values, "field_sources": field_sources, "sources": sources,
            "samples": samples, "_identities": sorted(masks)}


def bounded_passages(passages):
    """Keep model citations small and server-owned, with the original page/paragraph."""
    result = []
    for passage in passages:
        text = passage["text"]
        start, segment = 0, 0
        while start < len(text):
            end = min(start + 900, len(text))
            if end < len(text):
                boundary = max(text.rfind("\n\n", start + 350, end), text.rfind(". ", start + 350, end))
                if boundary >= 0:
                    end = boundary + (1 if text[boundary] == "." else 0)
                else:
                    boundary = text.rfind(" ", start + 350, end)
                    if boundary >= 0:
                        end = boundary
            excerpt = text[start:end].strip()
            if excerpt:
                segment += 1
                result.append({"location": passage["location"] + f", segment {segment}", "text": excerpt})
            start = end
    return result


def protocol_text(name: str, content: bytes) -> list[dict]:
    if len(content) > PROTOCOL_LIMIT:
        raise ValueError("protocol_size_limit")
    suffix = Path(name).suffix.lower()
    passages = []
    if suffix in {".txt", ".md"}:
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise ValueError("protocol_utf8_required") from None
        if len(text) > TEXT_LIMIT:
            raise ValueError("protocol_text_limit")
        passages = [{"location": f"paragraph {i}", "text": text.strip()}
                    for i, text in enumerate(re.split(r"\n\s*\n", text), 1) if text.strip()]
    elif suffix == ".docx":
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                infos = archive.infolist()
                if len(infos) > 1000 or sum(x.file_size for x in infos) > 24 * 1024 * 1024:
                    raise ValueError("protocol_archive_limit")
                info = archive.getinfo("word/document.xml")
                if info.file_size > 2 * 1024 * 1024:
                    raise ValueError("protocol_text_limit")
                xml = archive.read(info)
                if b"<!DOCTYPE" in xml.upper() or b"<!ENTITY" in xml.upper():
                    raise ValueError("protocol_xml_unsafe")
                root = ElementTree.fromstring(xml)
                ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
                passages = [{"location": f"paragraph {i}", "text": "".join(p.itertext()).strip()}
                            for i, p in enumerate(root.iter(ns + "p"), 1) if "".join(p.itertext()).strip()]
        except (zipfile.BadZipFile, KeyError, ElementTree.ParseError, RuntimeError):
            raise ValueError("protocol_docx_invalid") from None
    elif suffix == ".pdf":
        with tempfile.TemporaryDirectory(prefix="bridge-protocol-") as directory:
            path = Path(directory) / "protocol.pdf"
            path.write_bytes(content)
            process = subprocess.Popen(["pdftotext", str(path), "-"],
                                       stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            chunks, total, deadline = [], 0, time.monotonic() + 20
            try:
                with selectors.DefaultSelector() as selector:
                    selector.register(process.stdout, selectors.EVENT_READ)
                    while True:
                        if time.monotonic() > deadline:
                            raise ValueError("protocol_pdf_timeout")
                        if not selector.select(timeout=0.1):
                            continue
                        chunk = process.stdout.read1(8192)
                        if not chunk:
                            break
                        total += len(chunk)
                        if total > TEXT_LIMIT * 4:
                            raise ValueError("protocol_text_limit")
                        chunks.append(chunk)
                if process.wait(timeout=1) != 0:
                    raise ValueError("protocol_pdf_invalid")
            finally:
                if process.poll() is None:
                    process.kill()
                process.wait()
                process.stdout.close()
            text = b"".join(chunks).decode("utf-8", errors="replace")
            passages = [{"location": f"page {i}", "text": page.strip()}
                        for i, page in enumerate(text.split("\f"), 1) if page.strip()]
    else:
        raise ValueError("protocol_format_unsupported")
    if not passages:
        raise ValueError("protocol_no_extractable_text")
    if sum(len(x["text"]) for x in passages) > TEXT_LIMIT:
        raise ValueError("protocol_text_limit")
    return passages
