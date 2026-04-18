from __future__ import annotations
import json
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
    }
    config_file.write_text(yaml.dump(config_data))
    cfg = load_config(config_file)
    assert cfg.aws.region == "eu-west-1"
    assert cfg.aws.profile == "myprofile"


def test_missing_explicit_config_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "nonexistent.yaml")


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


# ---------------------------------------------------------------------------
# _load_from_env branches
# ---------------------------------------------------------------------------

def test_load_from_env_full_json(monkeypatch):
    """ARGUS_CONFIG env var loads a full JSON config."""
    payload = json.dumps({"aws": {"region": "ap-southeast-1"}})
    monkeypatch.setenv("ARGUS_CONFIG", payload)
    cfg = load_config()
    assert cfg.aws.region == "ap-southeast-1"


def test_load_from_env_individual_vars(monkeypatch):
    """Individual ARGUS_* env vars are each applied."""
    monkeypatch.setenv("ARGUS_REGION", "ca-central-1")
    monkeypatch.setenv("ARGUS_PROFILE", "myprofile")
    monkeypatch.setenv("ARGUS_OUTPUT_LOCATION", "s3://env-bucket/")
    monkeypatch.setenv("ARGUS_AUTH_MODE", "none")
    cfg = load_config()
    assert cfg.aws.region == "ca-central-1"
    assert cfg.aws.profile == "myprofile"
    assert cfg.defaults.output_location == "s3://env-bucket/"
    assert cfg.auth_mode == "none"


def test_load_config_returns_cached_result(tmp_path):
    """Second call returns the cached config without re-reading the file."""
    config_file = tmp_path / "test_config.yaml"
    config_file.write_text(yaml.dump({"aws": {"region": "eu-north-1"}}))
    cfg1 = load_config(config_file)
    # Overwrite the file — cache should mean the second call still returns original
    config_file.write_text(yaml.dump({"aws": {"region": "us-west-2"}}))
    cfg2 = load_config()
    assert cfg1 is cfg2
    assert cfg2.aws.region == "eu-north-1"


# ---------------------------------------------------------------------------
# Lambda _load_overrides / _save_overrides
# ---------------------------------------------------------------------------

def test_load_overrides_exception_returns_empty(monkeypatch):
    """If the session store raises during override load, _load_overrides returns {}."""
    from argus.core import config as cfgmod

    monkeypatch.setenv("LAMBDA_RUNTIME", "1")
    monkeypatch.setenv("ARGUS_SESSION_STORE", "memory")

    # Make get_persistent raise
    import argus.core.session_store as sess
    original = sess.get_persistent
    sess.get_persistent = lambda key: (_ for _ in ()).throw(RuntimeError("boom"))
    try:
        result = cfgmod._load_overrides()
    finally:
        sess.get_persistent = original
    assert result == {}


def test_save_overrides_noop_outside_lambda(monkeypatch):
    """_save_overrides is a no-op when not running on Lambda."""
    from argus.core import config as cfgmod
    monkeypatch.delenv("LAMBDA_RUNTIME", raising=False)
    # Should not raise even with empty overrides
    cfgmod._save_overrides({"workgroups": {}})


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
