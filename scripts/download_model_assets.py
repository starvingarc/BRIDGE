#!/usr/bin/env python3
"""Download external BRIDGE model assets from the public asset manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


class AssetDownloadError(RuntimeError):
    """Raised when a model asset cannot be planned or downloaded."""


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_manifest(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise AssetDownloadError(f"asset manifest not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise AssetDownloadError(f"asset manifest is not valid JSON: {path}") from exc

    assets = data.get("assets")
    if not isinstance(assets, list) or not assets:
        raise AssetDownloadError("asset manifest must contain a non-empty 'assets' list")
    return data


def _destination(root: Path, raw_destination: str) -> Path:
    destination = Path(raw_destination)
    if destination.is_absolute():
        raise AssetDownloadError(f"asset destination must be repository-relative: {raw_destination}")

    resolved = (root / destination).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise AssetDownloadError(f"asset destination escapes repository root: {raw_destination}") from exc
    return resolved


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download(url: str, destination: Path, display_destination: Path, *, force: bool) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and not force:
        print(f"exists: {display_destination}")
        return

    tmp = destination.with_name(f".{destination.name}.tmp")
    request = urllib.request.Request(url, headers={"User-Agent": "BRIDGE asset downloader"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response, tmp.open("wb") as handle:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
    except urllib.error.HTTPError as exc:
        if tmp.exists():
            tmp.unlink()
        raise AssetDownloadError(f"download failed for {url}: HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        if tmp.exists():
            tmp.unlink()
        raise AssetDownloadError(f"download failed for {url}: {exc.reason}") from exc

    tmp.replace(destination)
    print(f"downloaded: {display_destination}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        default="models/assets.json",
        help="asset manifest path, relative to --root unless absolute",
    )
    parser.add_argument(
        "--root",
        default=str(_repo_root()),
        help="repository root used to resolve asset destinations",
    )
    parser.add_argument("--dry-run", action="store_true", help="print planned downloads only")
    parser.add_argument("--force", action="store_true", help="overwrite existing downloaded files")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    manifest_path = Path(args.manifest)
    if not manifest_path.is_absolute():
        manifest_path = root / manifest_path

    try:
        manifest = _load_manifest(manifest_path)
        for asset in manifest["assets"]:
            asset_id = asset.get("id", "<unnamed>")
            url = asset.get("url")
            raw_destination = asset.get("destination")
            if not url or not raw_destination:
                raise AssetDownloadError(f"asset {asset_id} must define both url and destination")

            destination = _destination(root, raw_destination)
            if args.dry_run:
                print(f"{asset_id}: {url} -> {destination.relative_to(root)}")
                continue

            _download(url, destination, destination.relative_to(root), force=args.force)
            expected_sha256 = asset.get("sha256")
            if expected_sha256:
                actual_sha256 = _sha256(destination)
                if actual_sha256.lower() != expected_sha256.lower():
                    destination.unlink(missing_ok=True)
                    raise AssetDownloadError(
                        f"checksum mismatch for {asset_id}: expected {expected_sha256}, got {actual_sha256}"
                    )
        return 0
    except AssetDownloadError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
