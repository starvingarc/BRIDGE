from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class ConfigValidationError(ValueError):
    """Raised when the workflow YAML config is invalid."""


class WorkflowValidationError(RuntimeError):
    """Raised when a workflow cannot run with the provided config or artifacts."""


@dataclass(frozen=True)
class DatasetConfig:
    id: str
    prefix: str


@dataclass(frozen=True)
class PathsConfig:
    config_dir: Path
    reference_h5ad: Path | None
    query_h5ad: Path | None
    whole_brain_ref_model_dir: Path | None
    prescreen_output_dir: Path | None
    ref_model_dir: Path | None
    identity_output_dir: Path
    cls_output_dir: Path
    report_output_dir: Path
    ref_sceniclike_h5ad: Path | None
    regulons_json: Path | None


@dataclass(frozen=True)
class RuntimeConfig:
    seed: int = 0
    n_jobs: int = 1


@dataclass(frozen=True)
class PrescreenWorkflowConfig:
    rg_label: str = "Radial Glia"
    counts_layer: str = "counts"
    train_query: bool = False
    max_epochs: int = 0
    plan_kwargs: dict[str, Any] | None = None
    early_stopping: bool = False
    early_stopping_patience: int = 10
    inplace_subset_query_vars: bool = True
    set_X_to_counts: bool = True


@dataclass(frozen=True)
class IdentityWorkflowConfig:
    target_class: str
    counts_layer: str
    ref_label_key: str
    max_epochs: int
    plan_kwargs: dict[str, Any]
    early_stopping: bool
    early_stopping_patience: int
    ensemble_size: int
    target_precision: float
    std_quantile: float
    u_min: float
    entropy_threshold: float
    inplace_subset_query_vars: bool = True
    set_X_to_counts: bool = True


@dataclass(frozen=True)
class CLSWorkflowConfig:
    enabled_components: list[str]
    batch_key: str
    candidate_flag_prefix: str
    ref_label_key: str
    a: dict[str, Any]
    b: dict[str, Any]
    c: dict[str, Any]
    d: dict[str, Any]
    e: dict[str, Any]
    f: dict[str, Any]


@dataclass(frozen=True)
class ReportWorkflowConfig:
    summary_filename: str
    manifest_filename: str
    cls_weights: dict[str, float] | None = None


@dataclass(frozen=True)
class BridgeRunConfig:
    version: str
    config_path: Path
    dataset: DatasetConfig
    paths: PathsConfig
    runtime: RuntimeConfig
    prescreen: PrescreenWorkflowConfig
    identity: IdentityWorkflowConfig
    cls: CLSWorkflowConfig
    report: ReportWorkflowConfig


@dataclass(frozen=True)
class BridgeConfigBatch:
    config_list_path: Path
    config_paths: list[Path]


REQUIRED_TOP_LEVEL = {"version", "dataset", "paths", "runtime", "identity", "cls", "report"}
ALLOWED_COMPONENTS = {"A", "B", "C", "D", "E", "F"}


def _require_mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigValidationError(f"Config section '{name}' must be a mapping.")
    return value


def _require_key(mapping: dict[str, Any], key: str, section: str) -> Any:
    if key not in mapping:
        raise ConfigValidationError(f"Missing required key '{section}.{key}'.")
    return mapping[key]


def _resolve_path(base_dir: Path, raw_value: Any, field_name: str) -> Path | None:
    if raw_value is None:
        return None
    if not isinstance(raw_value, str) or not raw_value.strip():
        raise ConfigValidationError(f"Path field '{field_name}' must be a non-empty string or null.")
    path = Path(raw_value)
    if not path.is_absolute():
        path = (base_dir / path).resolve()
    return path


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ConfigValidationError("Top-level YAML content must be a mapping.")
    return data


def load_config(path: str | Path) -> BridgeRunConfig:
    config_path = Path(path).resolve()
    if not config_path.exists():
        raise ConfigValidationError(f"Config file not found: {config_path}")

    data = _load_yaml(config_path)
    missing_sections = REQUIRED_TOP_LEVEL.difference(data.keys())
    if missing_sections:
        missing = ", ".join(sorted(missing_sections))
        raise ConfigValidationError(f"Missing required top-level sections: {missing}")

    dataset = _require_mapping(data["dataset"], "dataset")
    paths = _require_mapping(data["paths"], "paths")
    runtime = _require_mapping(data["runtime"], "runtime")
    prescreen = _require_mapping(data.get("prescreen", {}), "prescreen")
    identity = _require_mapping(data["identity"], "identity")
    cls = _require_mapping(data["cls"], "cls")
    report = _require_mapping(data["report"], "report")

    dataset_cfg = DatasetConfig(
        id=str(_require_key(dataset, "id", "dataset")),
        prefix=str(_require_key(dataset, "prefix", "dataset")),
    )

    base_dir = config_path.parent
    paths_cfg = PathsConfig(
        config_dir=base_dir,
        reference_h5ad=_resolve_path(base_dir, _require_key(paths, "reference_h5ad", "paths"), "paths.reference_h5ad"),
        query_h5ad=_resolve_path(base_dir, _require_key(paths, "query_h5ad", "paths"), "paths.query_h5ad"),
        whole_brain_ref_model_dir=_resolve_path(
            base_dir, paths.get("whole_brain_ref_model_dir"), "paths.whole_brain_ref_model_dir"
        ),
        prescreen_output_dir=_resolve_path(base_dir, paths.get("prescreen_output_dir"), "paths.prescreen_output_dir"),
        ref_model_dir=_resolve_path(base_dir, _require_key(paths, "ref_model_dir", "paths"), "paths.ref_model_dir"),
        identity_output_dir=_resolve_path(base_dir, _require_key(paths, "identity_output_dir", "paths"), "paths.identity_output_dir"),
        cls_output_dir=_resolve_path(base_dir, _require_key(paths, "cls_output_dir", "paths"), "paths.cls_output_dir"),
        report_output_dir=_resolve_path(base_dir, _require_key(paths, "report_output_dir", "paths"), "paths.report_output_dir"),
        ref_sceniclike_h5ad=_resolve_path(base_dir, paths.get("ref_sceniclike_h5ad"), "paths.ref_sceniclike_h5ad"),
        regulons_json=_resolve_path(base_dir, paths.get("regulons_json"), "paths.regulons_json"),
    )

    runtime_cfg = RuntimeConfig(
        seed=int(runtime.get("seed", 0)),
        n_jobs=int(runtime.get("n_jobs", 1)),
    )

    prescreen_plan_kwargs = prescreen.get("plan_kwargs")
    if prescreen_plan_kwargs is not None and not isinstance(prescreen_plan_kwargs, dict):
        raise ConfigValidationError("Config key 'prescreen.plan_kwargs' must be a mapping when provided.")
    prescreen_cfg = PrescreenWorkflowConfig(
        rg_label=str(prescreen.get("rg_label", "Radial Glia")),
        counts_layer=str(prescreen.get("counts_layer", "counts")),
        train_query=bool(prescreen.get("train_query", False)),
        max_epochs=int(prescreen.get("max_epochs", 0)),
        plan_kwargs=dict(prescreen_plan_kwargs) if prescreen_plan_kwargs else None,
        early_stopping=bool(prescreen.get("early_stopping", False)),
        early_stopping_patience=int(prescreen.get("early_stopping_patience", 10)),
        inplace_subset_query_vars=bool(prescreen.get("inplace_subset_query_vars", True)),
        set_X_to_counts=bool(prescreen.get("set_X_to_counts", True)),
    )

    identity_cfg = IdentityWorkflowConfig(
        target_class=str(_require_key(identity, "target_class", "identity")),
        counts_layer=str(_require_key(identity, "counts_layer", "identity")),
        ref_label_key=str(_require_key(identity, "ref_label_key", "identity")),
        max_epochs=int(_require_key(identity, "max_epochs", "identity")),
        plan_kwargs=dict(_require_key(identity, "plan_kwargs", "identity")),
        early_stopping=bool(_require_key(identity, "early_stopping", "identity")),
        early_stopping_patience=int(_require_key(identity, "early_stopping_patience", "identity")),
        ensemble_size=int(_require_key(identity, "ensemble_size", "identity")),
        target_precision=float(_require_key(identity, "target_precision", "identity")),
        std_quantile=float(_require_key(identity, "std_quantile", "identity")),
        u_min=float(_require_key(identity, "u_min", "identity")),
        entropy_threshold=float(_require_key(identity, "entropy_threshold", "identity")),
        inplace_subset_query_vars=bool(identity.get("inplace_subset_query_vars", True)),
        set_X_to_counts=bool(identity.get("set_X_to_counts", True)),
    )

    enabled_components_raw = _require_key(cls, "enabled_components", "cls")
    if not isinstance(enabled_components_raw, list):
        raise ConfigValidationError("Config key 'cls.enabled_components' must be a list.")
    enabled_components = [str(comp).upper() for comp in enabled_components_raw]
    unknown = sorted(set(enabled_components).difference(ALLOWED_COMPONENTS))
    if unknown:
        raise ConfigValidationError(f"Unknown enabled CLS components: {', '.join(unknown)}")
    if not enabled_components:
        raise ConfigValidationError("Config key 'cls.enabled_components' must not be empty.")

    for section_name in ["a", "b", "c", "d", "e", "f"]:
        _require_mapping(_require_key(cls, section_name, "cls"), f"cls.{section_name}")

    cls_cfg = CLSWorkflowConfig(
        enabled_components=enabled_components,
        batch_key=str(_require_key(cls, "batch_key", "cls")),
        candidate_flag_prefix=str(_require_key(cls, "candidate_flag_prefix", "cls")),
        ref_label_key=str(_require_key(cls, "ref_label_key", "cls")),
        a=dict(cls["a"]),
        b=dict(cls["b"]),
        c=dict(cls["c"]),
        d=dict(cls["d"]),
        e=dict(cls["e"]),
        f=dict(cls["f"]),
    )

    cls_weights = report.get("cls_weights")
    if cls_weights is not None and not isinstance(cls_weights, dict):
        raise ConfigValidationError("Config key 'report.cls_weights' must be a mapping when provided.")
    report_cfg = ReportWorkflowConfig(
        summary_filename=str(_require_key(report, "summary_filename", "report")),
        manifest_filename=str(_require_key(report, "manifest_filename", "report")),
        cls_weights={str(k).upper(): float(v) for k, v in cls_weights.items()} if cls_weights else None,
    )

    return BridgeRunConfig(
        version=str(data["version"]),
        config_path=config_path,
        dataset=dataset_cfg,
        paths=paths_cfg,
        runtime=runtime_cfg,
        prescreen=prescreen_cfg,
        identity=identity_cfg,
        cls=cls_cfg,
        report=report_cfg,
    )


def load_config_list(path: str | Path) -> BridgeConfigBatch:
    config_list_path = Path(path).resolve()
    if not config_list_path.exists():
        raise ConfigValidationError(f"Config-list file not found: {config_list_path}")
    data = _load_yaml(config_list_path)
    if "configs" not in data:
        raise ConfigValidationError("Config-list YAML must contain top-level key 'configs'.")
    configs = data["configs"]
    if not isinstance(configs, list) or not configs:
        raise ConfigValidationError("Config-list 'configs' must be a non-empty list.")
    base_dir = config_list_path.parent
    config_paths: list[Path] = []
    for idx, raw_path in enumerate(configs, start=1):
        resolved = _resolve_path(base_dir, raw_path, f"configs[{idx}]")
        if resolved is None or not resolved.exists():
            raise ConfigValidationError(f"Config-list entry does not exist: {raw_path}")
        config_paths.append(resolved)
    return BridgeConfigBatch(config_list_path=config_list_path, config_paths=config_paths)
