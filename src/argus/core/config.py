from __future__ import annotations
import json
import logging
import os
from pathlib import Path
from typing import Optional
import yaml
from argus.models.schemas import AppConfig

log = logging.getLogger(__name__)

_SEARCH_PATHS = [
    Path("argus.yaml"),
    Path.home() / ".argus.yaml",
]

_config_cache: Optional[AppConfig] = None
_active_config_path: Optional[Path] = None


def _load_from_env() -> Optional[AppConfig]:
    """Try to build AppConfig from environment variables. Returns None if no env vars set."""
    full_json = os.environ.get("ARGUS_CONFIG")
    if full_json:
        return AppConfig.model_validate(json.loads(full_json))

    individual = {
        "ARGUS_REGION": os.environ.get("ARGUS_REGION"),
        "ARGUS_PROFILE": os.environ.get("ARGUS_PROFILE"),
        "ARGUS_OUTPUT_LOCATION": os.environ.get("ARGUS_OUTPUT_LOCATION"),
        "ARGUS_AUTH_MODE": os.environ.get("ARGUS_AUTH_MODE"),
        "ARGUS_SESSION_STORE": os.environ.get("ARGUS_SESSION_STORE"),
    }
    if not any(individual.values()):
        return None

    cfg = AppConfig()
    if individual["ARGUS_REGION"]:
        cfg.aws.region = individual["ARGUS_REGION"]
    if individual["ARGUS_PROFILE"]:
        cfg.aws.profile = individual["ARGUS_PROFILE"]
    if individual["ARGUS_OUTPUT_LOCATION"]:
        cfg.defaults.output_location = individual["ARGUS_OUTPUT_LOCATION"]
    if individual["ARGUS_AUTH_MODE"]:
        cfg.auth_mode = individual["ARGUS_AUTH_MODE"]
    return cfg


def load_config(config_path: Optional[Path] = None) -> AppConfig:
    global _config_cache, _active_config_path
    if _config_cache is not None:
        return _config_cache

    env_cfg = _load_from_env()
    if env_cfg is not None:
        _config_cache = env_cfg
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
    if os.environ.get("LAMBDA_RUNTIME"):
        log.warning("save_config() called in Lambda mode — skipping file write.")
        _config_cache = config
        return

    path = config_path or _active_config_path or _resolve_config_path(None)
    if path is None:
        path = Path("argus.yaml")

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
