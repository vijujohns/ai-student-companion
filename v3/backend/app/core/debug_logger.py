"""
Debug Logger — Brain Teaser
-----------------------------
Controlled entirely by environment variables.
Set DEBUG_LOGGING=true in backend/.env to enable.
Set DEBUG_LOG_FILE=logs/debug.log to also write to a file.

Usage:
    from .core.debug_logger import dlog, is_debug

    dlog("RAG", "Cache HIT", key=cache_key, user=user_id)
"""

import os
import sys
import logging
from dotenv import load_dotenv

load_dotenv()

# ── Config from environment ──────────────────────────────────────────────────
_DEBUG: bool = os.getenv("DEBUG_LOGGING", "false").lower() in ("true", "1", "yes")
_LOG_FILE: str = os.getenv("DEBUG_LOG_FILE", "")

# Never let logging internals crash request handling on Windows consoles.
logging.raiseExceptions = False

# ── Logger setup ─────────────────────────────────────────────────────────────
_logger = logging.getLogger("brain_teaser")
_logger.setLevel(logging.DEBUG if _DEBUG else logging.WARNING)
_logger.propagate = False  # Prevent double-logging via root logger

if not _logger.handlers:
    _fmt = logging.Formatter(
        "[%(asctime)s] [%(levelname)-5s] %(message)s",
        datefmt="%H:%M:%S"
    )

    # Console — always present when debug is on
    _ch = logging.StreamHandler(sys.stdout)
    _ch.setLevel(logging.DEBUG)
    _ch.setFormatter(_fmt)
    _logger.addHandler(_ch)

    # Optional file handler
    if _LOG_FILE:
        log_dir = os.path.dirname(_LOG_FILE)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        _fh = logging.FileHandler(_LOG_FILE, encoding="utf-8")
        _fh.setLevel(logging.DEBUG)
        _fh.setFormatter(_fmt)
        _logger.addHandler(_fh)


# ── Public API ────────────────────────────────────────────────────────────────
def is_debug() -> bool:
    """Return True if debug logging is active."""
    return _DEBUG


def _normalize_log_text(value) -> str:
    text = str(value)
    return text.replace("→", "->").replace("←", "<-")


def _safe_emit(level: str, text: str) -> None:
    safe_text = _normalize_log_text(text)
    try:
        getattr(_logger, level)(safe_text)
    except Exception:
        try:
            fallback = safe_text.encode("ascii", errors="backslashreplace").decode("ascii", errors="ignore")
            sys.__stderr__.write(f"{fallback}\n")
        except Exception:
            pass


def dlog(tag: str, message: str, **extra) -> None:
    """
    Emit a structured debug log line.

    Example:
        dlog("MODEL", "Selected model", model="mistral-7b", task="qa", tokens=400)
    Emits:
        [12:34:56] [DEBUG] [MODEL] Selected model | model='mistral-7b' | task='qa' | tokens=400
    """
    if not _DEBUG:
        return
    suffix = (" | " + " | ".join(f"{k}={_normalize_log_text(v)!r}" for k, v in extra.items())) if extra else ""
    _safe_emit("debug", f"[{tag}] {_normalize_log_text(message)}{suffix}")


def dwarn(tag: str, message: str, **extra) -> None:
    """Emit a structured warning — always visible regardless of DEBUG_LOGGING."""
    suffix = (" | " + " | ".join(f"{k}={_normalize_log_text(v)!r}" for k, v in extra.items())) if extra else ""
    _safe_emit("warning", f"[{tag}] {_normalize_log_text(message)}{suffix}")


def derror(tag: str, message: str, **extra) -> None:
    """Emit a structured error — always visible regardless of DEBUG_LOGGING."""
    suffix = (" | " + " | ".join(f"{k}={_normalize_log_text(v)!r}" for k, v in extra.items())) if extra else ""
    _safe_emit("error", f"[{tag}] {_normalize_log_text(message)}{suffix}")
