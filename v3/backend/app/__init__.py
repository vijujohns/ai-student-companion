# Brain Teaser Backend Package

import sys


def _ensure_utf8_console() -> None:
    """Best-effort UTF-8 stdout/stderr for Windows terminals and emoji-safe logs."""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


_ensure_utf8_console()
