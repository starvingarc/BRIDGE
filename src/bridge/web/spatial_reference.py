"""Read a configured reference's obs/obsm only; never access its expression matrix."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import hashlib
from pathlib import Path
import re
from typing import Literal

from pydantic import Field

from .spatial_link_data import DisplayModel, TypeCrosswalk


class PlaneHypothesis(DisplayModel):
    kind: Literal['near_sagittal_model_landmark']
    offset: float = Field(ge=-0.7, le=0.7)


class ModelAsset(DisplayModel):
    stage: str
    file: str
    sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    attribution: str
    license: str
    plane_hypothesis: PlaneHypothesis | None = None


class ReferenceManifest(DisplayModel):
    version: str
    reference_id: str
    vocabulary_version: str
    data_root: Path
    file: str
    sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    coordinate_key: str
    type_column: str
    capture_column: str | None = None
    types: list[str]
    stage: str
    coordinate_convention: Literal['image_y_down', 'cartesian_y_up'] = 'image_y_down'
    crosswalk: TypeCrosswalk
    model: ModelAsset | None = None


@dataclass(frozen=True)
class SpatialReference:
    manifest: ReferenceManifest
    manifest_sha256: str
    sections: list[dict]
    coordinates: np.ndarray
    type_codes: np.ndarray
    captures: np.ndarray


def configured_path(root: Path, relative: str) -> Path:
    value = Path(relative)
    if value.is_absolute() or '..' in value.parts:
        raise ValueError('spatial_reference_path_invalid')
    resolved = (root / value).resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError('spatial_reference_path_invalid')
    return resolved


def _identity(path: Path) -> tuple:
    value = path.stat()
    return value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns


def verify_file(path: Path, expected: str) -> tuple:
    before = _identity(path)
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            h.update(chunk)
    if h.hexdigest() != expected or before != _identity(path):
        raise ValueError('spatial_reference_checksum_mismatch')
    return before


def load_spatial_reference(manifest_path: Path) -> SpatialReference:
    try:
        if manifest_path.stat().st_size > 1_000_000:
            raise ValueError('spatial_manifest_too_large')
        raw = manifest_path.read_bytes()
        manifest = ReferenceManifest.model_validate_json(raw)
        if manifest.vocabulary_version != manifest.crosswalk.spatial_vocabulary_version:
            raise ValueError('spatial_reference_vocabulary_mismatch')
        path = configured_path(manifest.data_root, manifest.file)
        # A changed inode, size, mtime or ctime forces a full checksum and fresh projection.
        return _load_verified(raw, _identity(path))
    except (OSError, KeyError, TypeError) as exc:
        raise ValueError('spatial_reference_unreadable') from exc


@lru_cache(maxsize=2)
def _load_verified(raw: bytes, identity: tuple) -> SpatialReference:
    import h5py
    import numpy as np
    from anndata.io import read_elem
    manifest = ReferenceManifest.model_validate_json(raw)
    path = configured_path(manifest.data_root, manifest.file)
    if verify_file(path, manifest.sha256) != identity:
        raise ValueError('spatial_reference_changed')
    fields = [manifest.coordinate_key, manifest.type_column]
    if manifest.capture_column:
        fields.append(manifest.capture_column)
    if any(not re.fullmatch(r'[A-Za-z0-9_.-]+', name) for name in fields):
        raise ValueError('spatial_reference_field_invalid')
    if not manifest.types or len(set(manifest.types)) != len(manifest.types):
        raise ValueError('spatial_reference_vocabulary_invalid')
    try:
        with h5py.File(path, 'r') as handle:
            coordinates = np.asarray(read_elem(handle['obsm'][manifest.coordinate_key]), dtype=float)
            labels = np.asarray(read_elem(handle['obs'][manifest.type_column])).astype(str)
            captures = (np.asarray(read_elem(handle['obs'][manifest.capture_column])).astype(str)
                        if manifest.capture_column else np.full(len(labels), 'capture'))
    except (KeyError, TypeError, OSError) as exc:
        raise ValueError('spatial_reference_field_unreadable') from exc
    if (coordinates.shape != (len(labels), 2) or not len(labels)
            or captures.shape != labels.shape or not np.isfinite(coordinates).all()):
        raise ValueError('spatial_reference_coordinates_invalid')
    if not set(labels) <= set(manifest.types):
        raise ValueError('spatial_reference_vocabulary_mismatch')
    vocabulary = {label: i for i, label in enumerate(manifest.types)}
    codes = np.array([vocabulary[label] for label in labels], dtype=np.int32)
    sections = [dict(id='capture-' + hashlib.sha256(label.encode()).hexdigest()[:16], label=label,
                     kind='capture', n_observations=int(np.count_nonzero(captures == label)))
                for label in sorted(set(captures))]
    if identity != _identity(path):
        raise ValueError('spatial_reference_changed')
    for array in (coordinates, codes, captures):
        array.flags.writeable = False
    return SpatialReference(manifest, hashlib.sha256(raw).hexdigest(), sections, coordinates, codes, captures)


def read_spatial_section(reference: SpatialReference, section_id: str) -> dict:
    import numpy as np
    section = next((s for s in reference.sections if s['id'] == section_id), None)
    if section is None:
        raise ValueError('spatial_section_unknown')
    indices = np.flatnonzero(reference.captures == section['label'])
    counts = np.bincount(reference.type_codes[indices], minlength=len(reference.manifest.types))
    return dict(**section, coordinate_convention=reference.manifest.coordinate_convention,
                types=reference.manifest.types,
                points=np.column_stack((reference.coordinates[indices], reference.type_codes[indices])).tolist(),
                counts={label: int(counts[i]) for i, label in enumerate(reference.manifest.types)})
