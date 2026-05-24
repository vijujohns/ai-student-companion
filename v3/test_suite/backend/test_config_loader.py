import copy

import pytest

from app.core.config_loader import ConfigValidationError, load_config, validate_config
from app.core.env_vars import ENV, ENVIRONMENT_VARIABLES


def _valid_config():
    return copy.deepcopy(load_config())


def test_validate_current_settings_file():
    assert validate_config(_valid_config())["default_model"]


def test_environment_registry_contains_core_names():
    for name in (ENV.APP_ENV, ENV.KB_REINDEX_MODE, ENV.SECRET_KEY, ENV.GROQ_API_KEY):
        assert name in ENVIRONMENT_VARIABLES

    assert len(ENVIRONMENT_VARIABLES) == len(set(ENVIRONMENT_VARIABLES))


def test_load_config_uses_dev_overlay():
    config = load_config("dev")

    assert config["network"]["backend"]["port"] == 8000
    assert config["network"]["frontend"]["port"] == 3000


def test_load_config_uses_test_overlay():
    config = load_config("test")

    assert config["network"]["backend"]["port"] == 8011
    assert config["network"]["frontend"]["port"] == 4174


def test_load_config_uses_prod_example_overlay_when_prod_overlay_is_absent():
    config = load_config("prod")

    assert config["network"]["backend"]["protocol"] == "https"
    assert config["network"]["backend"]["ws_protocol"] == "wss"


def test_validate_rejects_unknown_task_model():
    config = _valid_config()
    config["tasks"]["qa"] = "missing-model"

    with pytest.raises(ConfigValidationError, match="tasks.qa references unknown model"):
        validate_config(config)


def test_validate_rejects_unknown_active_profile():
    config = _valid_config()
    config["active_model_profile"] = "missing-profile"

    with pytest.raises(ConfigValidationError, match="active_model_profile references unknown profile"):
        validate_config(config)


def test_validate_rejects_invalid_network_port():
    config = _valid_config()
    config["network"]["backend"]["port"] = 70000

    with pytest.raises(ConfigValidationError, match="network.backend.port must be between 1 and 65535"):
        validate_config(config)


def test_validate_rejects_invalid_cors_regex():
    config = _valid_config()
    config["network"]["cors"]["origin_regex"] = "["

    with pytest.raises(ConfigValidationError, match="network.cors.origin_regex is invalid"):
        validate_config(config)


def test_validate_rejects_invalid_rag_pattern():
    config = _valid_config()
    config["rag"]["formatting"]["intent_patterns"]["compare"][0] = "("

    with pytest.raises(ConfigValidationError, match=r"rag\.formatting\.intent_patterns\.compare\[0\] is invalid"):
        validate_config(config)


def test_validate_rejects_missing_local_model_path():
    config = _valid_config()
    del config["models"]["qwen2.5-7b"]["path"]

    with pytest.raises(ConfigValidationError, match=r"models\.qwen2\.5-7b\.path must be a non-empty string"):
        validate_config(config)
