from __future__ import annotations
import pytest
import yaml
from pathlib import Path
from athena_beaver.core.config import load_config, reset_config_cache
from athena_beaver.models.schemas import AppConfig


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
