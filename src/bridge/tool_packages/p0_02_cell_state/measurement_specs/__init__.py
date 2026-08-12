from __future__ import annotations

from importlib.resources import files

import yaml

from bridge.toolkit.contracts import MeasurementSpec


def load_measurement_spec(reference: str | None) -> MeasurementSpec | None:
    if reference is None:
        return None
    for resource in files(__name__).iterdir():
        if resource.name.endswith(".yaml"):
            payload = yaml.safe_load(resource.read_text(encoding="utf-8"))
            if payload["measurement_spec_id"] == reference:
                return MeasurementSpec.model_validate(payload)
    return None
