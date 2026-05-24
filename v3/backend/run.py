#!/usr/bin/env python
import argparse
import sys
import os
import socket
from urllib import error as urllib_error
from urllib import request as urllib_request

# Make console output UTF-8 friendly on Windows before importing app modules.
for _stream_name in ("stdout", "stderr"):
    _stream = getattr(sys, _stream_name, None)
    _reconfigure = getattr(_stream, "reconfigure", None)
    if callable(_reconfigure):
        try:
            _reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

# Add the backend directory to Python path so 'app' module can be found
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)

# Now import and run uvicorn
import uvicorn
from app.core.config_loader import get_backend_bind_config
from app.core.env_vars import ENV


def _probe_host_for(bind_host: str) -> str:
    host = str(bind_host or "").strip()
    if host in {"", "0.0.0.0", "::"}:
        return "127.0.0.1"
    return host


def _is_port_in_use(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1.0):
            return True
    except OSError:
        return False


def _is_existing_backend_alive(host: str, port: int) -> bool:
    try:
        with urllib_request.urlopen(f"http://{host}:{port}/openapi.json", timeout=2) as response:
            return int(getattr(response, "status", 0) or 0) == 200
    except (urllib_error.URLError, OSError, ValueError):
        return False


def _normalize_reindex_cli_value(value: str | None) -> str | None:
    if value is None:
        return None

    normalized = str(value or "true").strip().lower()
    mapping = {
        "true": "incremental",
        "1": "incremental",
        "yes": "incremental",
        "on": "incremental",
        "incremental": "incremental",
        "changed": "incremental",
        "full": "full",
        "rebuild": "full",
        "fresh": "full",
        "false": "skip",
        "0": "skip",
        "no": "skip",
        "off": "skip",
        "skip": "skip",
    }
    if normalized not in mapping:
        raise SystemExit("Invalid --reindex value. Use true|false|incremental|full|skip.")
    return mapping[normalized]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument(
        "--reindex",
        nargs="?",
        const="true",
        default=None,
        help="Enable startup indexing only when explicitly requested. Use --reindex=true, --reindex=incremental, or --reindex=full.",
    )
    cli_args, _ = parser.parse_known_args()

    cli_reindex_mode = _normalize_reindex_cli_value(cli_args.reindex)
    if cli_reindex_mode:
        os.environ[ENV.KB_REINDEX_MODE] = cli_reindex_mode
        if cli_reindex_mode == "skip":
            os.environ[ENV.SKIP_KB_REINDEX] = "1"
        else:
            os.environ.pop(ENV.SKIP_KB_REINDEX, None)

    bind_cfg = get_backend_bind_config()
    probe_host = _probe_host_for(bind_cfg["host"])
    probe_port = int(bind_cfg["port"])

    if _is_port_in_use(probe_host, probe_port):
        if _is_existing_backend_alive(probe_host, probe_port):
            print(f"ℹ️ Backend already running at http://{probe_host}:{probe_port} — reusing existing server.")
            raise SystemExit(0)
        print(f"⚠️ Port {probe_port} is already in use on {probe_host}. Stop the existing process or change {ENV.BACKEND_PORT}.")
        raise SystemExit(1)

    uvicorn.run(
        "app.main:app",
        host=bind_cfg["host"],
        port=probe_port,
        reload=False
    )
