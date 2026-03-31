"""
Main FastAPI entry point
"""

import time
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

from .modules.faiss_store import load_index, load_knowledge_base
from .modules.file_management import recover_indexing_jobs
from .modules.db import init_db
from .core.debug_logger import dlog, is_debug
from .core.config_loader import get_cors_origins, get_cors_origin_regex
from .modules.messages import get_message

import sys
sys.stdout.reconfigure(encoding='utf-8')

import threading

load_dotenv()


# ── Request / Response logging middleware ─────────────────────────────────────
class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs every HTTP request → response when DEBUG_LOGGING is enabled."""

    async def dispatch(self, request: Request, call_next):
        if not is_debug():
            return await call_next(request)

        start = time.perf_counter()
        method = request.method
        path = request.url.path
        qp = dict(request.query_params)
        client = request.client.host if request.client else "unknown"

        dlog("API", f"→ {method} {path}",
             client=client,
             query_params=qp if qp else None)

        try:
            response = await call_next(request)
            duration_ms = (time.perf_counter() - start) * 1000
            dlog("API", f"← {method} {path} {response.status_code}",
                 duration_ms=f"{duration_ms:.1f}ms",
                 client=client)
            return response
        except Exception as exc:
            duration_ms = (time.perf_counter() - start) * 1000
            dlog("API", f"← {method} {path} EXCEPTION",
                 error=str(exc),
                 duration_ms=f"{duration_ms:.1f}ms")
            raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    allowed = get_cors_origins()
    allowed_regex = get_cors_origin_regex()
    dlog("STARTUP", "Brain Teaser backend starting",
         debug_logging=is_debug(),
         cors_origins=allowed,
         cors_origin_regex=allowed_regex)
    print("🚀 Loading FAISS index...")
    load_index()
    dlog("STARTUP", "FAISS index loaded")

    print("🚀 Checking for KB updates...")
    if not os.getenv("SKIP_KB_REINDEX"):
        threading.Thread(target=load_knowledge_base, daemon=True).start()
    else:
        print("⏭  KB re-indexing skipped (SKIP_KB_REINDEX set)")

    print("🚀 Initializing DB...")
    init_db()
    dlog("STARTUP", "Database initialized")

    recovery = recover_indexing_jobs()
    dlog("STARTUP", "Indexing jobs recovered", recovered=recovery["recovered"], failed=recovery["failed"])

    yield


app = FastAPI(title="AI Tutor", lifespan=lifespan)

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

    meta = get_message(message_id)

    if isinstance(detail, dict):
        user_text = detail.get("message") or detail.get("user_text") or meta["user_text"]
        error_detail = detail
    elif isinstance(detail, str):
        user_text = detail or meta["user_text"]
        error_detail = detail
    else:
        user_text = meta["user_text"]
        error_detail = "Request failed"

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "message": {
                "message_id": meta["message_id"],
                "level": meta["level"],
                "user_text": user_text,
            },
            "error": error_detail,
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    meta = get_message("MSG-1400")
    encoded_errors = jsonable_encoder(exc.errors(), custom_encoder={Exception: lambda e: str(e)})
    return JSONResponse(
        status_code=422,
        content={
            "message": meta,
            "error": encoded_errors,
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    meta = get_message("MSG-1500")
    dlog("API", "Unhandled exception", path=request.url.path, error=str(exc))
    return JSONResponse(
        status_code=500,
        content={
            "message": meta,
            "error": "Internal server error",
        },
    )
