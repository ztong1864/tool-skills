import os
from dataclasses import dataclass
from typing import Any, Dict


try:
    import yaml
except ImportError as exc:
    raise ImportError("PyYAML is required for config loading.") from exc


@dataclass
class PipelineConfig:
    raw: Dict[str, Any]

    @property
    def project_root(self) -> str:
        return self.raw["project_root"]

    @property
    def artifacts_dir(self) -> str:
        return self.raw["data"]["artifacts_dir"]

    @property
    def pdf_artifacts_dir(self) -> str:
        return self.raw["data"]["pdf_artifacts_dir"]

    @property
    def schema_id(self) -> str:
        return self.raw["schema"]["active"]


def load_yaml(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _resolve_path(base_dir: str, path_value: str) -> str:
    if not path_value:
        return path_value
    if os.path.isabs(path_value):
        return os.path.normpath(path_value)
    return os.path.normpath(os.path.abspath(os.path.join(base_dir, path_value)))


def _resolve_config_paths(cfg: Dict[str, Any], base_dir: str) -> Dict[str, Any]:
    resolved = dict(cfg)
    resolved["project_root"] = _resolve_path(base_dir, cfg["project_root"])

    data = dict(cfg.get("data", {}))
    for key in ("pdf_artifacts_dir", "artifacts_dir", "descriptors_template_dir"):
        if key in data:
            data[key] = _resolve_path(base_dir, data[key])
    resolved["data"] = data

    llm = dict(cfg.get("llm", {}))
    if "cache_dir" in llm:
        llm["cache_dir"] = _resolve_path(base_dir, llm["cache_dir"])
    resolved["llm"] = llm

    return resolved


def load_config(default_path: str) -> PipelineConfig:
    cfg = load_yaml(default_path)
    config_dir = os.path.dirname(os.path.abspath(default_path))
    cfg = _resolve_config_paths(cfg, config_dir)
    return PipelineConfig(raw=cfg)


def load_schema_config(config_dir: str, schema_id: str) -> Dict[str, Any]:
    schema_path = os.path.join(config_dir, f"{schema_id}.yaml")
    return load_yaml(schema_path)

