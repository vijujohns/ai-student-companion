import json
import os

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
CONFIG_FILE = os.path.join(BASE_DIR, "configs", "settings.json")

_config_cache = None


def load_config():
    global _config_cache

    if _config_cache is None:
        with open(CONFIG_FILE, "r") as f:
            _config_cache = json.load(f)

    return _config_cache


def get_task_model(task: str):
    config = load_config()
    return config["tasks"].get(task, config["default_model"])


def get_app_env(default: str = "dev") -> str:
    raw = str(os.getenv("APP_ENV", "") or "").strip().lower()
    if not raw and os.getenv("PYTEST_CURRENT_TEST"):
        return "test"

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
        os.getenv("BACKEND_BIND_HOST"),
        os.getenv("BACKEND_HOST"),
        os.getenv("HOST"),
        backend_cfg.get("bind_host"),
    )
    if not host:
        raise ValueError("network.backend.bind_host must be set in configs/settings.json")

    port_raw = _first_non_empty(
        os.getenv("BACKEND_PORT"),
        os.getenv("PORT"),
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

    protocol = _first_non_empty(os.getenv("BACKEND_PROTOCOL"), backend_cfg.get("protocol"))
    ws_protocol = _first_non_empty(os.getenv("BACKEND_WS_PROTOCOL"), backend_cfg.get("ws_protocol"))
    if not protocol:
        raise ValueError("network.backend.protocol must be set in configs/settings.json")
    if not ws_protocol:
        raise ValueError("network.backend.ws_protocol must be set in configs/settings.json")

    port_raw = _first_non_empty(
        os.getenv("BACKEND_PORT"),
        os.getenv("PORT"),
        backend_cfg.get("port"),
    )
    try:
        port = int(port_raw)
    except (TypeError, ValueError):
        raise ValueError("network.backend.port must be a valid integer")

    return {
        "public_host": _first_non_empty(os.getenv("BACKEND_PUBLIC_HOST"), os.getenv("BACKEND_HOST"), backend_cfg.get("public_host")),
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
        raise ValueError("network.frontend.host must be set in configs/settings.json")
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
        raise ValueError("network.redis.host must be set in configs/settings.json")

    try:
        port = int(redis_cfg.get("port"))
    except (TypeError, ValueError):
        raise ValueError("network.redis.port must be a valid integer")

    return {
        "host": host,
        "port": max(1, port),
    }