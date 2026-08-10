#!/usr/bin/env python3
from __future__ import annotations

import argparse
import concurrent.futures
import html
import json
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path


TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--urls", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--timeout", type=float, default=12.0)
    args = parser.parse_args()
    urls = json.loads(args.urls.read_text(encoding="utf-8"))
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        records = list(pool.map(lambda url: verify(url, args.timeout), urls))
    payload = {record.pop("url"): record for record in records}
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


def verify(url: str, timeout: float) -> dict:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "BRIDGE-source-verifier/0.1 (+https://github.com/starvingarc/BRIDGE)",
            "Accept": "text/html,application/xhtml+xml,application/json;q=0.8,*/*;q=0.5",
        },
    )
    context = ssl.create_default_context()
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
            body = response.read(196608).decode(response.headers.get_content_charset() or "utf-8", errors="replace")
            match = TITLE.search(body)
            title = _clean_title(match.group(1)) if match else None
            return {
                "url": url,
                "status": "verified",
                "http_status": response.status,
                "resolved_url": response.geturl(),
                "title": title,
                "checked_at": date.today().isoformat(),
            }
    except urllib.error.HTTPError as exc:
        if url.startswith("https://doi.org/"):
            crossref = _verify_doi_with_crossref(url, timeout)
            if crossref is not None:
                return crossref
        return {
            "url": url,
            "status": "http_error",
            "http_status": exc.code,
            "resolved_url": exc.geturl(),
            "title": None,
            "checked_at": date.today().isoformat(),
        }
    except Exception as exc:
        return {
            "url": url,
            "status": "unresolved",
            "http_status": None,
            "resolved_url": None,
            "title": None,
            "checked_at": date.today().isoformat(),
            "error_type": type(exc).__name__,
        }


def _clean_title(value: str) -> str:
    return " ".join(html.unescape(value).split())[:500]


def _verify_doi_with_crossref(url: str, timeout: float) -> dict | None:
    doi = url.removeprefix("https://doi.org/")
    endpoint = "https://api.crossref.org/works/" + urllib.parse.quote(doi, safe="")
    request = urllib.request.Request(
        endpoint,
        headers={
            "User-Agent": "BRIDGE-source-verifier/0.1 (+https://github.com/starvingarc/BRIDGE)",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=ssl.create_default_context()) as response:
            message = json.loads(response.read().decode("utf-8"))["message"]
            titles = message.get("title") or []
            return {
                "url": url,
                "status": "verified_via_crossref",
                "http_status": response.status,
                "resolved_url": url,
                "title": _clean_title(titles[0]) if titles else None,
                "checked_at": date.today().isoformat(),
            }
    except Exception:
        return None


if __name__ == "__main__":
    raise SystemExit(main())
