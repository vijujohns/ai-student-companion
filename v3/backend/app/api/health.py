"""
Health and diagnostics API router.
"""
import os
from typing import Any
from fastapi import APIRouter

from ..modules.db import get_connection
from ..modules.messages import envelope
from ..modules import cache
from ..modules import faiss_store
from ..modules.ocr import get_ocr_status
from ..modules.model_manager import (
    CLOUD_MODELS,
    LOCAL_MODELS,
    get_active_model_profile_key,
    get_model_profiles,
    is_model_available,
    list_models,
)

router = APIRouter()


def _health_result(status: str = "ok", **details: Any) -> dict:
    result = {"status": status}
    result.update(details)
    return result


def _safe_health_check(check: callable) -> dict:
    try:
        return check()
    except Exception as exc:
        return _health_result("degraded", error=str(exc))


def _health_check_database() -> dict:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
    finally:
        conn.close()
    return _health_result("ok", reachable=True)


def _health_check_cache() -> dict:
    client = getattr(cache, "r", None)
    if client is None:
        client_type = "uninitialized"
    elif client.__class__.__name__ == "InMemoryCache":
        client_type = "in-memory"
    else:
        client_type = "redis"

    breaker = getattr(cache, "CIRCUIT_BREAKER", {}) or {}
    status = "degraded" if breaker.get("is_open") or client_type in {"in-memory", "uninitialized"} else "ok"
    return _health_result(
        status,
        client_type=client_type,
        redis_host=str(getattr(cache, "REDIS_HOST", "")),
        redis_port=int(getattr(cache, "REDIS_PORT", 0) or 0),
        circuit_open=bool(breaker.get("is_open")),
        failure_count=int(breaker.get("failure_count") or 0),
    )


def _health_check_faiss() -> dict:
    logical_indexes = getattr(faiss_store, "logical_indexes", {}) or {}
    documents = getattr(faiss_store, "documents", []) or []
    return _health_result(
        "ok",
        documents_count=len(documents),
        logical_indexes_count=len(logical_indexes),
        index_file_exists=os.path.exists(getattr(faiss_store, "INDEX_FILE", "")),
        documents_file_exists=os.path.exists(getattr(faiss_store, "DOC_FILE", "")),
        metadata_file_exists=os.path.exists(getattr(faiss_store, "META_FILE", "")),
    )


def _health_check_ocr() -> dict:
    ocr = get_ocr_status()
    return _health_result(
        "ok" if ocr.get("available") else "degraded",
        available=bool(ocr.get("available")),
        engine=str(ocr.get("engine") or "none"),
        message=str(ocr.get("message") or ""),
    )


def _health_check_models() -> dict:
    models = list_models()
    available = [name for name in models if is_model_available(name)]
    profiles = get_model_profiles()
    return _health_result(
        "ok" if available else "degraded",
        active_profile=get_active_model_profile_key(),
        configured_models_count=len(models),
        available_models_count=len(available),
        configured_profiles_count=len(profiles),
        local_models_count=len(LOCAL_MODELS),
        cloud_models_count=len(CLOUD_MODELS),
        available_models=available,
    )


def _runtime_diagnostic_checks() -> dict:
    return {
        "database": _safe_health_check(_health_check_database),
        "cache": _safe_health_check(_health_check_cache),
        "faiss": _safe_health_check(_health_check_faiss),
        "ocr": _safe_health_check(_health_check_ocr),
        "models": _safe_health_check(_health_check_models),
    }


@router.get("/health/runtime")
def runtime_health():
    raw_mode = str(os.getenv("KB_REINDEX_MODE", "skip") or "skip").strip().lower()
    if str(os.getenv("SKIP_KB_REINDEX", "")).strip().lower() in {"1", "true", "yes", "on"}:
        raw_mode = "skip"
    if raw_mode in {"true", "1", "yes", "on", "changed"}:
        raw_mode = "incremental"
    elif raw_mode not in {"incremental", "full", "skip"}:
        raw_mode = "skip"

    checks = _runtime_diagnostic_checks()
    diagnostics_status = "ok" if all(item.get("status") == "ok" for item in checks.values()) else "degraded"

    return envelope(
        {
            "status": "ok",
            "api": "up",
            "ws": "configured",
            "kb_reindex_mode": raw_mode,
            "diagnostics_status": diagnostics_status,
            "checks": checks,
        },
        message_id="MSG-1000",
    )
