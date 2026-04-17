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

# Key used in the session_store for Lambda-persisted config overrides.
# Stores the mutable subset of AppConfig (assignments, output_locations) so
# user edits survive Lambda cold starts.
_CONFIG_OVERRIDES_KEY = "config:overrides"


def _is_lambda() -> bool:
    return os.environ.get("LAMBDA_RUNTIME") == "1"


def _load_overrides() -> dict:
    """Load persisted config overrides from the session store (Lambda mode)."""
    if not _is_lambda():
        return {}
    try:
        from argus.core.session_store import get_persistent
        return get_persistent(_CONFIG_OVERRIDES_KEY) or {}
    except Exception as exc:
        log.warning("Failed to load persisted config overrides: %s", exc)
        return {}


def _save_overrides(overrides: dict) -> None:
    """Persist config overrides to the session store (Lambda mode)."""
    if not _is_lambda():
        return
    from argus.core.session_store import put_persistent
    put_persistent(_CONFIG_OVERRIDES_KEY, overrides)


def _apply_overrides(config: AppConfig, overrides: dict) -> AppConfig:
    """Merge persisted overrides onto the base config."""
    if not overrides:
        return config
    wg_override = overrides.get("workgroups") or {}
    if wg_override:
        new_assignments = {**config.workgroups.assignments, **(wg_override.get("assignments") or {})}
        new_outputs = {**config.workgroups.output_locations, **(wg_override.get("output_locations") or {})}
        updated_wg = config.workgroups.model_copy(update={
            "assignments": new_assignments,
            "output_locations": new_outputs,
        })
        config = config.model_copy(update={"workgroups": updated_wg})
    return config


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

    # Lambda: always merge fresh overrides from the session store so other
    # containers' writes are picked up.
    if _is_lambda():
        if _config_cache is None:
            env_cfg = _load_from_env() or AppConfig()
            _config_cache = env_cfg
        return _apply_overrides(_config_cache, _load_overrides())

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
    """Persist config to YAML (local) or DynamoDB (Lambda), and update the cache."""
    global _config_cache, _active_config_path
    if _is_lambda():
        # Lambda: only the mutable subset (workgroup assignments + output
        # locations) is stored. Base config stays env-driven.
        overrides = {
            "workgroups": {
                "assignments": dict(config.workgroups.assignments),
                "output_locations": dict(config.workgroups.output_locations),
            }
        }
        _save_overrides(overrides)
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
