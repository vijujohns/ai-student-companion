"""Central registry for supported environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class EnvVar:
    name: str
    default: str
    description: str


class ENV:
    ALLOW_WS_QUERY_TOKEN = "ALLOW_WS_QUERY_TOKEN"
    APP_DB_FILE = "APP_DB_FILE"
    APP_ENV = "APP_ENV"
    AUTH_COOKIE_SAMESITE = "AUTH_COOKIE_SAMESITE"
    AUTH_COOKIE_SECURE = "AUTH_COOKIE_SECURE"
    ACCESS_TOKEN_EXPIRE_MINUTES = "ACCESS_TOKEN_EXPIRE_MINUTES"
    BACKEND_BIND_HOST = "BACKEND_BIND_HOST"
    BACKEND_HOST = "BACKEND_HOST"
    BACKEND_PORT = "BACKEND_PORT"
    BACKEND_PROTOCOL = "BACKEND_PROTOCOL"
    BACKEND_PUBLIC_HOST = "BACKEND_PUBLIC_HOST"
    BACKEND_WS_PROTOCOL = "BACKEND_WS_PROTOCOL"
    DEBUG_LOG_FILE = "DEBUG_LOG_FILE"
    DEBUG_LOGGING = "DEBUG_LOGGING"
    DISABLE_INDEX_JOB_RECOVERY = "DISABLE_INDEX_JOB_RECOVERY"
    ENABLE_DEFAULT_USERS = "ENABLE_DEFAULT_USERS"
    ENABLE_INDIC_TRANS2 = "ENABLE_INDIC_TRANS2"
    FAISS_EMBEDDING_DIM = "FAISS_EMBEDDING_DIM"
    GROQ_API_KEY = "GROQ_API_KEY"
    GROQ_BASE_URL = "GROQ_BASE_URL"
    GROQ_TIMEOUT_SECONDS = "GROQ_TIMEOUT_SECONDS"
    HOST = "HOST"
    INDEX_JOB_WORKERS = "INDEX_JOB_WORKERS"
    INDICTRANS2_EN_INDIC_MODEL = "INDICTRANS2_EN_INDIC_MODEL"
    INDICTRANS2_INDIC_EN_MODEL = "INDICTRANS2_INDIC_EN_MODEL"
    JWT_ALGORITHM = "JWT_ALGORITHM"
    KB_REINDEX_MODE = "KB_REINDEX_MODE"
    MODEL_PROFILE = "MODEL_PROFILE"
    OPENAI_API_KEY = "OPENAI_API_KEY"
    OPENAI_BASE_URL = "OPENAI_BASE_URL"
    OPENAI_TIMEOUT_SECONDS = "OPENAI_TIMEOUT_SECONDS"
    PORT = "PORT"
    PYTEST_CURRENT_TEST = "PYTEST_CURRENT_TEST"
    PYTEST_XDIST_WORKER = "PYTEST_XDIST_WORKER"
    SECRET_KEY = "SECRET_KEY"
    SKIP_KB_REINDEX = "SKIP_KB_REINDEX"
    TOKEN_COOKIE_NAME = "TOKEN_COOKIE_NAME"


ENVIRONMENT_VARIABLES = {
    ENV.ALLOW_WS_QUERY_TOKEN: EnvVar(ENV.ALLOW_WS_QUERY_TOKEN, "false", "Allow deprecated WebSocket token query parameter fallback."),
    ENV.APP_DB_FILE: EnvVar(ENV.APP_DB_FILE, "", "Absolute or relative SQLite database file override."),
    ENV.APP_ENV: EnvVar(ENV.APP_ENV, "dev", "Application environment: dev, test, or prod."),
    ENV.AUTH_COOKIE_SAMESITE: EnvVar(ENV.AUTH_COOKIE_SAMESITE, "lax", "Auth cookie SameSite policy: lax, strict, or none."),
    ENV.AUTH_COOKIE_SECURE: EnvVar(ENV.AUTH_COOKIE_SECURE, "auto", "Whether auth cookies require HTTPS."),
    ENV.ACCESS_TOKEN_EXPIRE_MINUTES: EnvVar(ENV.ACCESS_TOKEN_EXPIRE_MINUTES, "60", "JWT access-token lifetime in minutes."),
    ENV.BACKEND_BIND_HOST: EnvVar(ENV.BACKEND_BIND_HOST, "", "Backend bind-host override."),
    ENV.BACKEND_HOST: EnvVar(ENV.BACKEND_HOST, "", "Legacy/shared backend host override."),
    ENV.BACKEND_PORT: EnvVar(ENV.BACKEND_PORT, "", "Backend port override."),
    ENV.BACKEND_PROTOCOL: EnvVar(ENV.BACKEND_PROTOCOL, "", "Public backend HTTP protocol override."),
    ENV.BACKEND_PUBLIC_HOST: EnvVar(ENV.BACKEND_PUBLIC_HOST, "", "Public backend hostname override."),
    ENV.BACKEND_WS_PROTOCOL: EnvVar(ENV.BACKEND_WS_PROTOCOL, "", "Public backend WebSocket protocol override."),
    ENV.DEBUG_LOG_FILE: EnvVar(ENV.DEBUG_LOG_FILE, "", "Optional debug log file path."),
    ENV.DEBUG_LOGGING: EnvVar(ENV.DEBUG_LOGGING, "false", "Enable verbose debug logging."),
    ENV.DISABLE_INDEX_JOB_RECOVERY: EnvVar(ENV.DISABLE_INDEX_JOB_RECOVERY, "false", "Disable startup indexing-job recovery."),
    ENV.ENABLE_DEFAULT_USERS: EnvVar(ENV.ENABLE_DEFAULT_USERS, "", "Force default seed users outside local/dev environments."),
    ENV.ENABLE_INDIC_TRANS2: EnvVar(ENV.ENABLE_INDIC_TRANS2, "false", "Enable optional IndicTrans2 translation backend."),
    ENV.FAISS_EMBEDDING_DIM: EnvVar(ENV.FAISS_EMBEDDING_DIM, "768", "Fallback FAISS embedding dimension."),
    ENV.GROQ_API_KEY: EnvVar(ENV.GROQ_API_KEY, "", "Groq API key for cloud model calls."),
    ENV.GROQ_BASE_URL: EnvVar(ENV.GROQ_BASE_URL, "https://api.groq.com/openai/v1", "Groq OpenAI-compatible base URL."),
    ENV.GROQ_TIMEOUT_SECONDS: EnvVar(ENV.GROQ_TIMEOUT_SECONDS, "60", "Groq request timeout in seconds."),
    ENV.HOST: EnvVar(ENV.HOST, "", "Generic backend bind-host fallback."),
    ENV.INDEX_JOB_WORKERS: EnvVar(ENV.INDEX_JOB_WORKERS, "2", "Number of background indexing workers."),
    ENV.INDICTRANS2_EN_INDIC_MODEL: EnvVar(ENV.INDICTRANS2_EN_INDIC_MODEL, "ai4bharat/indictrans2-en-indic-1B", "IndicTrans2 English-to-Indic model name."),
    ENV.INDICTRANS2_INDIC_EN_MODEL: EnvVar(ENV.INDICTRANS2_INDIC_EN_MODEL, "ai4bharat/indictrans2-indic-en-1B", "IndicTrans2 Indic-to-English model name."),
    ENV.JWT_ALGORITHM: EnvVar(ENV.JWT_ALGORITHM, "HS256", "JWT signing algorithm."),
    ENV.KB_REINDEX_MODE: EnvVar(ENV.KB_REINDEX_MODE, "skip", "Startup knowledge-base reindex mode: skip, incremental, or full."),
    ENV.MODEL_PROFILE: EnvVar(ENV.MODEL_PROFILE, "", "Active model-profile override."),
    ENV.OPENAI_API_KEY: EnvVar(ENV.OPENAI_API_KEY, "", "OpenAI API key for cloud model calls."),
    ENV.OPENAI_BASE_URL: EnvVar(ENV.OPENAI_BASE_URL, "https://api.openai.com/v1", "OpenAI-compatible base URL."),
    ENV.OPENAI_TIMEOUT_SECONDS: EnvVar(ENV.OPENAI_TIMEOUT_SECONDS, "60", "OpenAI request timeout in seconds."),
    ENV.PORT: EnvVar(ENV.PORT, "", "Generic backend port fallback."),
    ENV.PYTEST_CURRENT_TEST: EnvVar(ENV.PYTEST_CURRENT_TEST, "", "Pytest marker used to infer test environment."),
    ENV.PYTEST_XDIST_WORKER: EnvVar(ENV.PYTEST_XDIST_WORKER, "", "Pytest-xdist worker id for isolated test DB names."),
    ENV.SECRET_KEY: EnvVar(ENV.SECRET_KEY, "change-me-in-production", "JWT signing secret."),
    ENV.SKIP_KB_REINDEX: EnvVar(ENV.SKIP_KB_REINDEX, "false", "Legacy flag forcing startup KB reindex to skip."),
    ENV.TOKEN_COOKIE_NAME: EnvVar(ENV.TOKEN_COOKIE_NAME, "access_token", "Auth cookie name."),
}


def env_str(name: str, default: str = "") -> str:
    return str(os.getenv(name, default) or default)


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default
