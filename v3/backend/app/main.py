"""
Main FastAPI entry point
"""

import asyncio
import time
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import os
from dotenv import load_dotenv

from .api.routes import router
from .api.websocket import websocket_router
from .api.v1 import create_v1_router

from .modules.faiss_store import load_index
from .modules.kb_sync import load_knowledge_base, start_reindex_job
from .modules.file_management import recover_indexing_jobs
from .modules.db import init_db
from .core.debug_logger import dlog, is_debug
from .core.config_loader import get_app_env, get_cors_origins, get_cors_origin_regex
from .modules.messages import error_envelope, get_message

import sys
sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()


def _route_domain(path: str) -> str:
    if path.startswith("/relationships") or path.startswith("/students") or path.startswith("/collaboration"):
        return "identity-collab"
    if path.startswith("/files") or path in {"/classes", "/subjects", "/folders", "/contents", "/pdf", "/ocr/status"}:
        return "knowledge-ingestion"
    if path.startswith("/progress"):
        return "analytics-progress"
    if path.startswith("/subscription") or path.startswith("/plan"):
        return "commercial"
    if path.startswith("/lesson") or path.startswith("/quiz") or path.startswith("/flashcards") or path.startswith("/artifacts") or path.startswith("/sessions") or path.startswith("/ask") or path.startswith("/notes"):
        return "learning-session"
    if path.startswith("/login") or path.startswith("/register") or path.startswith("/auth") or path.startswith("/profile") or path.startswith("/reset-password"):
        return "identity-auth"
    if path.startswith("/admin"):
        return "admin"
    return "misc"


def _resolve_startup_reindex_mode() -> str:
    """Return the backend startup reindex mode: skip by default, or incremental/full when explicitly requested."""
    raw_mode = str(os.getenv("KB_REINDEX_MODE", "skip") or "skip").strip().lower()
    normalized = {
        "": "skip",
        "false": "skip",
        "0": "skip",
        "off": "skip",
        "none": "skip",
        "disabled": "skip",
        "skip": "skip",
        "true": "incremental",
        "1": "incremental",
        "yes": "incremental",
        "on": "incremental",
        "enabled": "incremental",
        "auto": "incremental",
        "incremental": "incremental",
        "changed": "incremental",
        "missing": "incremental",
        "full": "full",
        "rebuild": "full",
        "fresh": "full",
    }.get(raw_mode, "skip")

    legacy_skip = str(os.getenv("SKIP_KB_REINDEX", "")).strip().lower() in {"1", "true", "yes", "on"}
    if legacy_skip:
        return "skip"
    return normalized


def _schedule_startup_reindex(startup_reindex_mode: str) -> None:
    """Defer the startup reindex job until the app has finished booting."""
    if startup_reindex_mode == "skip":
        print("⏭  KB startup indexing is disabled by default. Use --reindex=true, --reindex=incremental, or --reindex=full to run it.")
        return

    async def _launch() -> None:
        await asyncio.sleep(0.25)
        if startup_reindex_mode == "full":
            print("♻️  Starting full KB re-index in background after startup completes (fresh rebuild of all files)")
        else:
            print("🔎 Starting incremental KB sync in background after startup completes (new/changed/unindexed files only)")
        start_reindex_job(
            force_reindex=startup_reindex_mode == "full",
            requested_type=startup_reindex_mode,
        )

    try:
        asyncio.get_running_loop().create_task(_launch())
    except RuntimeError:
        if startup_reindex_mode == "full":
            print("♻️  Starting full KB re-index in background (fresh rebuild of all files)")
        else:
            print("🔎 Starting incremental KB sync in background (new/changed/unindexed files only)")
        start_reindex_job(
            force_reindex=startup_reindex_mode == "full",
            requested_type=startup_reindex_mode,
        )


# ── Request / Response logging middleware ─────────────────────────────────────
class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs every HTTP request -> response when DEBUG_LOGGING is enabled."""

    async def dispatch(self, request: Request, call_next):
        if not is_debug():
            return await call_next(request)

        start = time.perf_counter()
        method = request.method
        path = request.url.path
        domain = _route_domain(path)
        qp = dict(request.query_params)
        client = request.client.host if request.client else "unknown"
        request_id = getattr(request.state, "request_id", None)

        dlog("API", f"-> {method} {path}",
             domain=domain,
             client=client,
             request_id=request_id,
             query_params=qp if qp else None)

        try:
            response = await call_next(request)
            duration_ms = (time.perf_counter() - start) * 1000
            dlog("API", f"<- {method} {path} {response.status_code}",
                 domain=domain,
                 duration_ms=f"{duration_ms:.1f}ms",
                 client=client,
                 request_id=request_id)
            return response
        except Exception as exc:
            duration_ms = (time.perf_counter() - start) * 1000
            dlog("API", f"<- {method} {path} EXCEPTION",
                 domain=domain,
                 error=str(exc),
                 duration_ms=f"{duration_ms:.1f}ms",
                 request_id=request_id)
            raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    allowed = get_cors_origins()
    allowed_regex = get_cors_origin_regex()
    dlog("STARTUP", "Brain Teaser backend starting",
         debug_logging=is_debug(),
         app_env=get_app_env(),
         cors_origins=allowed,
         cors_origin_regex=allowed_regex)
    print("🚀 Loading FAISS index...")
    load_index()
    dlog("STARTUP", "FAISS index loaded")

    print("🚀 Checking for KB updates...")
    startup_reindex_mode = _resolve_startup_reindex_mode()

    print("🚀 Initializing DB...")
    init_db()
    dlog("STARTUP", "Database initialized")

    recovery_enabled = str(os.getenv("DISABLE_INDEX_JOB_RECOVERY", "")).strip().lower() not in {"1", "true", "yes", "on"}
    if get_app_env() == "test":
        recovery_enabled = False

    if recovery_enabled:
        try:
            recovery = recover_indexing_jobs()
            dlog("STARTUP", "Indexing jobs recovered", recovered=recovery["recovered"], failed=recovery["failed"])
        except Exception as exc:
            dlog("STARTUP", "Indexing job recovery skipped after failure", error=str(exc))
    else:
        dlog("STARTUP", "Indexing job recovery disabled", app_env=get_app_env())

    _schedule_startup_reindex(startup_reindex_mode)

    yield


app = FastAPI(title="AI Tutor", lifespan=lifespan)


@app.middleware("http")
async def add_request_id_header(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# CORS configuration is centralized in configs/settings.json
allowed_origins = get_cors_origins()
allowed_origin_regex = get_cors_origin_regex()
dlog("STARTUP", "CORS configured", origins=allowed_origins, origin_regex=allowed_origin_regex)

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=allowed_origin_regex,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

app.include_router(router)
app.include_router(create_v1_router())
app.include_router(websocket_router)


def _message_id_for_status(status_code: int) -> str:
    if status_code == 400:
        return "MSG-1400"
    if status_code in (401, 403):
        return "MSG-1401"
    if status_code == 404:
        return "MSG-1404"
    if status_code == 429:
        return "MSG-1201"
    if status_code >= 500:
        return "MSG-1500"
    return "MSG-1000"


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail
    message_id = _message_id_for_status(exc.status_code)

    # Preserve explicit message metadata from middleware/dependencies when present.
    if isinstance(detail, dict) and detail.get("message_id"):
        message_id = str(detail.get("message_id"))

    if isinstance(detail, dict):
        fallback = get_message(message_id)
        user_text = detail.get("message") or detail.get("user_text") or fallback["user_text"]
        level = detail.get("level")
        error_detail = detail
    elif isinstance(detail, str):
        fallback = get_message(message_id)
        user_text = detail or fallback["user_text"]
        level = None
        error_detail = detail
    else:
        user_text = None
        level = None
        error_detail = "Request failed"

    return JSONResponse(
        status_code=exc.status_code,
        content=error_envelope(error_detail, message_id=message_id, user_text=user_text, level=level),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    encoded_errors = jsonable_encoder(exc.errors(), custom_encoder={Exception: lambda e: str(e)})
    return JSONResponse(
        status_code=422,
        content=error_envelope(encoded_errors, message_id="MSG-1400"),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    dlog("API", "Unhandled exception", path=request.url.path, error=str(exc))
    return JSONResponse(
        status_code=500,
        content=error_envelope("Internal server error", message_id="MSG-1500"),
    )
