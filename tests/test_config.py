from __future__ import annotations
import pytest
import yaml
from pathlib import Path
from argus.core.config import load_config, reset_config_cache
from argus.models.schemas import AppConfig


@pytest.fixture(autouse=True)
def clear_cache():
    reset_config_cache()
    yield
    reset_config_cache()


def test_load_defaults_when_no_file():
    cfg = load_config()
    assert isinstance(cfg, AppConfig)
    assert cfg.aws.region == "us-east-1"


def test_load_from_file(tmp_path):
    config_file = tmp_path / "test_config.yaml"
    config_data = {
        "aws": {"region": "eu-west-1", "profile": "myprofile"},
        "active_schema": "default",
    }
    config_file.write_text(yaml.dump(config_data))
    cfg = load_config(config_file)
    assert cfg.aws.region == "eu-west-1"
    assert cfg.aws.profile == "myprofile"


def test_missing_explicit_config_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "nonexistent.yaml")


def test_naming_schema_loaded(tmp_path):
    config_file = tmp_path / "test_config.yaml"
    config_data = {
        "naming_schemas": {
            "default": {
                "pattern": "{purpose}_{client_id}_{environment}",
                "client_id_regex": r"\d{6}|\d{9}",
                "workgroup_pattern": "{purpose}_{client_id}_{environment}",
            }
        },
        "active_schema": "default",
    }
    config_file.write_text(yaml.dump(config_data))
    cfg = load_config(config_file)
    assert "default" in cfg.naming_schemas
    assert cfg.active_schema == "default"


def test_workgroup_output_locations(tmp_path):
    config_file = tmp_path / "test_config.yaml"
    config_data = {
        "workgroups": {
            "output_locations": {
                "analytics_123456_prod": "s3://bucket/prod/",
            }
        }
    }
    config_file.write_text(yaml.dump(config_data))
    cfg = load_config(config_file)
    assert cfg.workgroups.output_locations["analytics_123456_prod"] == "s3://bucket/prod/"


def test_lambda_mode_persists_overrides_via_session_store(monkeypatch):
    """In Lambda mode, save_config writes the mutable subset to the session
    store and load_config merges it back on subsequent reads."""
    from argus.core import config as cfgmod
    from argus.core import session_store as sess

    monkeypatch.setenv("LAMBDA_RUNTIME", "1")
    monkeypatch.setenv("ARGUS_SESSION_STORE", "memory")
    sess._memory_store.clear()

    # First load builds a fresh AppConfig from env; no overrides yet.
    cfg = cfgmod.load_config()
    assert cfg.workgroups.assignments == {}

    # Save an assignment + an output-location override.
    updated_wg = cfg.workgroups.model_copy(update={
        "assignments": {"analytics_123_prod": "client-123-wg"},
        "output_locations": {"client-123-wg": "s3://bucket/123/"},
    })
    cfgmod.save_config(cfg.model_copy(update={"workgroups": updated_wg}))

    # A subsequent load in the same process must pick up the persisted data.
    reloaded = cfgmod.load_config()
    assert reloaded.workgroups.assignments == {"analytics_123_prod": "client-123-wg"}
    assert reloaded.workgroups.output_locations == {"client-123-wg": "s3://bucket/123/"}

    # And a totally fresh cache (simulating a cold-start in another container)
    # must still see the values because they live in the session store.
    cfgmod.reset_config_cache()
    reloaded2 = cfgmod.load_config()
    assert reloaded2.workgroups.assignments == {"analytics_123_prod": "client-123-wg"}
