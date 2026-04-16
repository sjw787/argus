from __future__ import annotations
import os
from pathlib import Path
from typing import Optional
import yaml
from athena_beaver.models.schemas import AppConfig

_SEARCH_PATHS = [
    Path("athena_beaver.yaml"),
    Path.home() / ".athena_beaver.yaml",
]

_config_cache: Optional[AppConfig] = None
_active_config_path: Optional[Path] = None


def load_config(config_path: Optional[Path] = None) -> AppConfig:
    global _config_cache, _active_config_path
    if _config_cache is not None:
        return _config_cache

    path = _resolve_config_path(config_path)
    _active_config_path = path

    if path is None:
        _config_cache = AppConfig()
        return _config_cache

    with open(path) as f:
        raw = yaml.safe_load(f) or {}

    _config_cache = AppConfig.model_validate(raw)
    return _config_cache


def save_config(config: AppConfig, config_path: Optional[Path] = None) -> None:
    """Persist config to YAML and update the in-memory cache."""
    global _config_cache, _active_config_path
    path = config_path or _active_config_path or _resolve_config_path(None)
    if path is None:
        path = Path("athena_beaver.yaml")

    raw = config.model_dump(exclude_none=True)
    with open(path, "w") as f:
        yaml.dump(raw, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    _config_cache = config
    _active_config_path = path


def reset_config_cache() -> None:
    global _config_cache
    _config_cache = None


def _resolve_config_path(config_path: Optional[Path]) -> Optional[Path]:
    if config_path is not None:
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        return config_path
    for p in _SEARCH_PATHS:
        if p.exists():
            return p
    return None
