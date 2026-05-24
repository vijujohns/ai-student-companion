import json
import os
import re

from dotenv import load_dotenv

from .env_vars import ENV

load_dotenv()

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
CONFIG_DIR = os.path.join(BASE_DIR, "configs")
BASE_CONFIG_FILE = os.path.join(CONFIG_DIR, "settings.base.json")
ENV_CONFIG_FILES = {
    "dev": os.path.join(CONFIG_DIR, "settings.dev.json"),
    "test": os.path.join(CONFIG_DIR, "settings.test.json"),
    "prod": os.path.join(CONFIG_DIR, "settings.prod.json"),
}
PROD_EXAMPLE_CONFIG_FILE = os.path.join(CONFIG_DIR, "settings.prod.example.json")

_config_cache = {}


class ConfigValidationError(ValueError):
    """Raised when merged config files are structurally invalid."""


def _is_mapping(value) -> bool:
    return isinstance(value, dict)


def _is_non_empty_string(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _validate_port(errors: list[str], path: str, value) -> None:
    try:
        port = int(value)
    except (TypeError, ValueError):
        errors.append(f"{path} must be an integer")
        return
    if port < 1 or port > 65535:
        errors.append(f"{path} must be between 1 and 65535")


def _validate_positive_number(errors: list[str], path: str, value, *, allow_zero: bool = False) -> None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        errors.append(f"{path} must be a number")
        return
    if parsed < 0 or (parsed == 0 and not allow_zero):
        comparator = "non-negative" if allow_zero else "positive"
        errors.append(f"{path} must be {comparator}")


def _validate_positive_int(errors: list[str], path: str, value, *, allow_zero: bool = False) -> None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        errors.append(f"{path} must be an integer")
        return
    if parsed < 0 or (parsed == 0 and not allow_zero):
        comparator = "non-negative" if allow_zero else "positive"
        errors.append(f"{path} must be {comparator}")


def _validate_network_config(errors: list[str], config: dict) -> None:
    network = config.get("network")
    if not _is_mapping(network):
        errors.append("network must be an object")
        return

    backend = network.get("backend")
    if not _is_mapping(backend):
        errors.append("network.backend must be an object")
    else:
        if not _is_non_empty_string(backend.get("bind_host")):
            errors.append("network.backend.bind_host must be a non-empty string")
        if "public_host" in backend and not isinstance(backend.get("public_host"), str):
            errors.append("network.backend.public_host must be a string")
        _validate_port(errors, "network.backend.port", backend.get("port"))
        if backend.get("protocol") not in {"http", "https"}:
            errors.append("network.backend.protocol must be 'http' or 'https'")
        if backend.get("ws_protocol") not in {"ws", "wss"}:
            errors.append("network.backend.ws_protocol must be 'ws' or 'wss'")

    frontend = network.get("frontend")
    if not _is_mapping(frontend):
        errors.append("network.frontend must be an object")
    else:
        if not _is_non_empty_string(frontend.get("host")):
            errors.append("network.frontend.host must be a non-empty string")
        _validate_port(errors, "network.frontend.port", frontend.get("port"))
        _validate_port(errors, "network.frontend.preview_port", frontend.get("preview_port"))

    testing = network.get("testing")
    if not _is_mapping(testing):
        errors.append("network.testing must be an object")
    else:
        if not _is_non_empty_string(testing.get("host")):
            errors.append("network.testing.host must be a non-empty string")
        _validate_port(errors, "network.testing.frontend_port", testing.get("frontend_port"))
        _validate_port(errors, "network.testing.backend_port", testing.get("backend_port"))

    redis = network.get("redis")
    if not _is_mapping(redis):
        errors.append("network.redis must be an object")
    else:
        if not _is_non_empty_string(redis.get("host")):
            errors.append("network.redis.host must be a non-empty string")
        _validate_port(errors, "network.redis.port", redis.get("port"))

    cors = network.get("cors")
    if not _is_mapping(cors):
        errors.append("network.cors must be an object")
    else:
        origins = cors.get("origins", [])
        if not isinstance(origins, list) or not all(isinstance(origin, str) for origin in origins):
            errors.append("network.cors.origins must be a list of strings")
        origin_regex = cors.get("origin_regex", "")
        if origin_regex is not None and not isinstance(origin_regex, str):
            errors.append("network.cors.origin_regex must be a string")
        elif origin_regex:
            try:
                re.compile(origin_regex)
            except re.error as exc:
                errors.append(f"network.cors.origin_regex is invalid: {exc}")


def _validate_model_config(errors: list[str], config: dict) -> None:
    models = config.get("models")
    if not _is_mapping(models) or not models:
        errors.append("models must be a non-empty object")
        models = {}

    default_model = config.get("default_model")
    if not _is_non_empty_string(default_model):
        errors.append("default_model must be a non-empty string")
    elif default_model not in models:
        errors.append(f"default_model references unknown model '{default_model}'")

    for model_name, model_cfg in models.items():
        path = f"models.{model_name}"
        if not _is_mapping(model_cfg):
            errors.append(f"{path} must be an object")
            continue
        model_type = model_cfg.get("type")
        if model_type not in {"local", "cloud"}:
            errors.append(f"{path}.type must be 'local' or 'cloud'")
            continue
        _validate_positive_int(errors, f"{path}.max_tokens", model_cfg.get("max_tokens"))
        _validate_positive_number(errors, f"{path}.temperature", model_cfg.get("temperature"), allow_zero=True)
        if model_type == "local":
            if not _is_non_empty_string(model_cfg.get("path")):
                errors.append(f"{path}.path must be a non-empty string")
            _validate_positive_int(errors, f"{path}.n_ctx", model_cfg.get("n_ctx"))
        else:
            if model_cfg.get("provider") not in {"openai", "groq"}:
                errors.append(f"{path}.provider must be 'openai' or 'groq'")
            if not _is_non_empty_string(model_cfg.get("model_name")):
                errors.append(f"{path}.model_name must be a non-empty string")

    tasks = config.get("tasks")
    if not _is_mapping(tasks) or not tasks:
        errors.append("tasks must be a non-empty object")
        tasks = {}
    for task, model_name in tasks.items():
        if not _is_non_empty_string(model_name):
            errors.append(f"tasks.{task} must reference a model name")
        elif model_name not in models:
            errors.append(f"tasks.{task} references unknown model '{model_name}'")

    profiles = config.get("model_profiles")
    if not _is_mapping(profiles) or not profiles:
        errors.append("model_profiles must be a non-empty object")
        profiles = {}
    active_profile = config.get("active_model_profile")
    if not _is_non_empty_string(active_profile):
        errors.append("active_model_profile must be a non-empty string")
    elif active_profile not in profiles:
        errors.append(f"active_model_profile references unknown profile '{active_profile}'")
    for profile_name, profile_cfg in profiles.items():
        path = f"model_profiles.{profile_name}"
        if not _is_mapping(profile_cfg):
            errors.append(f"{path} must be an object")
            continue
        if not _is_non_empty_string(profile_cfg.get("label")):
            errors.append(f"{path}.label must be a non-empty string")
        if "description" in profile_cfg and not isinstance(profile_cfg.get("description"), str):
            errors.append(f"{path}.description must be a string")
        task_models = profile_cfg.get("task_models")
        if not _is_mapping(task_models) or not task_models:
            errors.append(f"{path}.task_models must be a non-empty object")
            continue
        for task, model_name in task_models.items():
            if not _is_non_empty_string(model_name):
                errors.append(f"{path}.task_models.{task} must reference a model name")
            elif model_name not in models:
                errors.append(f"{path}.task_models.{task} references unknown model '{model_name}'")


def _validate_rag_config(errors: list[str], config: dict) -> None:
    rag = config.get("rag")
    if not _is_mapping(rag):
        errors.append("rag must be an object")
        return

    for key in ("top_k", "chunk_size", "summary_chunk_size", "document_top_k"):
        _validate_positive_int(errors, f"rag.{key}", rag.get(key))
    for key in ("chunk_overlap", "summary_chunk_overlap"):
        _validate_positive_int(errors, f"rag.{key}", rag.get(key), allow_zero=True)
    if not _is_non_empty_string(rag.get("embedding_model")):
        errors.append("rag.embedding_model must be a non-empty string")
    if not isinstance(rag.get("strict_mode"), bool):
        errors.append("rag.strict_mode must be a boolean")
    if not isinstance(rag.get("use_precomputed_summaries"), bool):
        errors.append("rag.use_precomputed_summaries must be a boolean")

    formatting = rag.get("formatting")
    if not _is_mapping(formatting):
        errors.append("rag.formatting must be an object")
        return
    formatter_order = formatting.get("formatter_order")
    if not isinstance(formatter_order, list) or not all(_is_non_empty_string(item) for item in formatter_order):
        errors.append("rag.formatting.formatter_order must be a list of non-empty strings")
    intent_patterns = formatting.get("intent_patterns")
    if not _is_mapping(intent_patterns):
        errors.append("rag.formatting.intent_patterns must be an object")
    else:
        for intent, patterns in intent_patterns.items():
            if not isinstance(patterns, list) or not patterns:
                errors.append(f"rag.formatting.intent_patterns.{intent} must be a non-empty list")
                continue
            for index, pattern in enumerate(patterns):
                if not isinstance(pattern, str):
                    errors.append(f"rag.formatting.intent_patterns.{intent}[{index}] must be a string")
                    continue
                try:
                    re.compile(pattern)
                except re.error as exc:
                    errors.append(f"rag.formatting.intent_patterns.{intent}[{index}] is invalid: {exc}")
    cleanup_markers = formatting.get("cleanup_markers")
    if not isinstance(cleanup_markers, list) or not all(isinstance(item, str) for item in cleanup_markers):
        errors.append("rag.formatting.cleanup_markers must be a list of strings")
    labels = formatting.get("labels")
    if not _is_mapping(labels) or not all(isinstance(key, str) and isinstance(value, str) for key, value in labels.items()):
        errors.append("rag.formatting.labels must be an object of strings")
    _validate_positive_int(errors, "rag.formatting.max_points", formatting.get("max_points"))


def validate_config(config: dict) -> dict:
    """Validate merged config and return the original config on success."""
    if not _is_mapping(config):
        raise ConfigValidationError("merged config must contain a JSON object")

    errors: list[str] = []
    _validate_network_config(errors, config)
    _validate_model_config(errors, config)
    _validate_rag_config(errors, config)

    if errors:
        detail = "\n".join(f"- {error}" for error in errors)
        raise ConfigValidationError(f"Invalid merged config:\n{detail}")
    return config


def _read_json_file(path: str) -> dict:
    with open(path, "r", encoding="utf-8-sig") as fh:
        data = json.load(fh)
    if not _is_mapping(data):
        raise ConfigValidationError(f"{os.path.relpath(path, BASE_DIR)} must contain a JSON object")
    return data


def _deep_merge(base: dict, overlay: dict) -> dict:
    merged = dict(base)
    for key, value in overlay.items():
        existing = merged.get(key)
        if _is_mapping(existing) and _is_mapping(value):
            merged[key] = _deep_merge(existing, value)
        else:
            merged[key] = value
    return merged


def _env_config_file(app_env: str) -> str:
    if app_env == "prod" and not os.path.exists(ENV_CONFIG_FILES["prod"]):
        return PROD_EXAMPLE_CONFIG_FILE
    return ENV_CONFIG_FILES.get(app_env, ENV_CONFIG_FILES["dev"])


def _normalize_app_env(raw_value: str, default: str = "dev") -> str:
    raw = str(raw_value or "").strip().lower()
    normalized = {
        "": default,
        "development": "dev",
        "debug": "dev",
        "local": "dev",
        "dev": "dev",
        "production": "prod",
        "live": "prod",
        "prod": "prod",
        "testing": "test",
        "test": "test",
    }.get(raw, raw or default)
    return normalized or default


def load_config(app_env: str | None = None):
    global _config_cache

    normalized_env = get_app_env() if app_env is None else _normalize_app_env(app_env)
    if normalized_env not in _config_cache:
        base_config = _read_json_file(BASE_CONFIG_FILE)
        env_config = _read_json_file(_env_config_file(normalized_env))
        _config_cache[normalized_env] = validate_config(_deep_merge(base_config, env_config))

    return _config_cache[normalized_env]


def get_task_model(task: str):
    config = load_config()
    return config["tasks"].get(task, config["default_model"])


def get_app_env(default: str = "dev") -> str:
    raw = str(os.getenv(ENV.APP_ENV, "") or "").strip().lower()
    if not raw and os.getenv(ENV.PYTEST_CURRENT_TEST):
        return "test"
    return _normalize_app_env(raw, default)


def is_dev() -> bool:
    return get_app_env() == "dev"


def is_prod() -> bool:
    return get_app_env() == "prod"


def get_model_config(model_name: str):
    config = load_config()
    return config["models"].get(model_name, {})


def get_default_model_profile(default: str = "balanced") -> str:
    config = load_config()
    value = config.get("active_model_profile", default)
    text = str(value or default).strip().lower()
    return text or default


def get_model_profiles_config() -> dict:
    config = load_config()
    profiles = config.get("model_profiles", {})
    return profiles if isinstance(profiles, dict) else {}


def get_rag_config() -> dict:
    config = load_config()
    rag_cfg = config.get("rag", {})
    return rag_cfg if isinstance(rag_cfg, dict) else {}


def get_rag_top_k(default: int = 4) -> int:
    rag_cfg = get_rag_config()
    value = rag_cfg.get("top_k", default)
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, parsed)


def get_network_config() -> dict:
    config = load_config()
    network_cfg = config.get("network", {})
    return network_cfg if isinstance(network_cfg, dict) else {}


def _first_non_empty(*values):
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def get_backend_bind_config() -> dict:
    backend_cfg = get_network_config().get("backend", {})
    if not isinstance(backend_cfg, dict):
        raise ValueError("network.backend config must be an object")

    host = _first_non_empty(
        os.getenv(ENV.BACKEND_BIND_HOST),
        os.getenv(ENV.BACKEND_HOST),
        os.getenv(ENV.HOST),
        backend_cfg.get("bind_host"),
    )
    if not host:
        raise ValueError("network.backend.bind_host must be set in merged config")

    port_raw = _first_non_empty(
        os.getenv(ENV.BACKEND_PORT),
        os.getenv(ENV.PORT),
        backend_cfg.get("port"),
    )
    try:
        port = int(port_raw)
    except (TypeError, ValueError):
        raise ValueError("network.backend.port must be a valid integer")

    return {"host": host, "port": max(1, port)}


def get_backend_public_config() -> dict:
    backend_cfg = get_network_config().get("backend", {})
    if not isinstance(backend_cfg, dict):
        raise ValueError("network.backend config must be an object")

    protocol = _first_non_empty(os.getenv(ENV.BACKEND_PROTOCOL), backend_cfg.get("protocol"))
    ws_protocol = _first_non_empty(os.getenv(ENV.BACKEND_WS_PROTOCOL), backend_cfg.get("ws_protocol"))
    if not protocol:
        raise ValueError("network.backend.protocol must be set in merged config")
    if not ws_protocol:
        raise ValueError("network.backend.ws_protocol must be set in merged config")

    port_raw = _first_non_empty(
        os.getenv(ENV.BACKEND_PORT),
        os.getenv(ENV.PORT),
        backend_cfg.get("port"),
    )
    try:
        port = int(port_raw)
    except (TypeError, ValueError):
        raise ValueError("network.backend.port must be a valid integer")

    return {
        "public_host": _first_non_empty(os.getenv(ENV.BACKEND_PUBLIC_HOST), os.getenv(ENV.BACKEND_HOST), backend_cfg.get("public_host")),
        "port": max(1, port),
        "protocol": protocol,
        "ws_protocol": ws_protocol,
    }


def get_frontend_server_config() -> dict:
    frontend_cfg = get_network_config().get("frontend", {})
    if not isinstance(frontend_cfg, dict):
        raise ValueError("network.frontend config must be an object")

    host = str(frontend_cfg.get("host", "")).strip()
    if not host:
        raise ValueError("network.frontend.host must be set in merged config")
    try:
        port = int(frontend_cfg.get("port"))
    except (TypeError, ValueError):
        raise ValueError("network.frontend.port must be a valid integer")
    try:
        preview_port = int(frontend_cfg.get("preview_port"))
    except (TypeError, ValueError):
        raise ValueError("network.frontend.preview_port must be a valid integer")

    return {
        "host": host,
        "port": max(1, port),
        "preview_port": max(1, preview_port),
    }


def get_cors_origins() -> list:
    cors_cfg = get_network_config().get("cors", {})
    if not isinstance(cors_cfg, dict):
        return []

    origins = cors_cfg.get("origins", [])
    if not isinstance(origins, list):
        return []

    return [str(origin).strip() for origin in origins if str(origin).strip()]


def get_cors_origin_regex() -> str | None:
    cors_cfg = get_network_config().get("cors", {})
    if not isinstance(cors_cfg, dict):
        return None

    regex = str(cors_cfg.get("origin_regex", "")).strip()
    return regex or None


def get_redis_config() -> dict:
    redis_cfg = get_network_config().get("redis", {})
    if not isinstance(redis_cfg, dict):
        raise ValueError("network.redis config must be an object")

    host = str(redis_cfg.get("host", "")).strip()
    if not host:
        raise ValueError("network.redis.host must be set in merged config")

    try:
        port = int(redis_cfg.get("port"))
    except (TypeError, ValueError):
        raise ValueError("network.redis.port must be a valid integer")

    return {
        "host": host,
        "port": max(1, port),
    }
