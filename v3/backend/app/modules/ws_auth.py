"""
WebSocket authentication utilities
"""

import os
from typing import Optional
from http.cookies import SimpleCookie
from fastapi import WebSocket, status
from .auth import TOKEN_COOKIE_NAME, verify_token


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


ALLOW_WS_QUERY_TOKEN = _env_flag("ALLOW_WS_QUERY_TOKEN", False)


async def get_token_from_websocket(ws: WebSocket) -> Optional[str]:
    """
    Extract JWT token from WebSocket connection.
    Priority:
    1. Authorization header during handshake
    2. Subprotocol (token passed as subprotocol suffix after .)
    3. Query parameter (deprecated, opt-in via ALLOW_WS_QUERY_TOKEN)
    """
    
    # Try to get from headers
    headers = dict(ws.headers)
    auth_header = headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:]
    
    # Try subprotocol (format: "chat.{token}")
    # JWTs contain 3 dots (header.payload.signature), so the full subprotocol
    # is "chat.{header}.{payload}.{signature}" — rejoin everything after first dot.
    subprotocols = headers.get("sec-websocket-protocol", "").split(",")
    for subproto in subprotocols:
        subproto = subproto.strip()
        if subproto.startswith("chat."):
            token_part = subproto[len("chat."):]
            if token_part:
                return token_part

    cookie_header = headers.get("cookie", "")
    if cookie_header:
        cookie = SimpleCookie()
        cookie.load(cookie_header)
        morsel = cookie.get(TOKEN_COOKIE_NAME)
        if morsel and morsel.value:
            return morsel.value
    
    # Legacy fallback: query parameter is disabled by default.
    if ALLOW_WS_QUERY_TOKEN and ws.query_params.get("token"):
        return ws.query_params.get("token")
    
    return None


def get_requested_subprotocol(ws: WebSocket) -> Optional[str]:
    """Return the requested chat.* subprotocol, if present, for handshake echo."""
    headers = dict(ws.headers)
    subprotocols = headers.get("sec-websocket-protocol", "").split(",")
    for subproto in subprotocols:
        candidate = subproto.strip()
        if candidate.startswith("chat."):
            return candidate
    return None


async def authenticate_websocket(ws: WebSocket) -> Optional[dict]:
    """
    Authenticate WebSocket connection and return user info
    Returns user dict on success, None on failure
    """
    token = await get_token_from_websocket(ws)
    
    if not token:
        return None
    
    user = verify_token(token)
    return user


async def require_websocket_auth(ws: WebSocket) -> Optional[dict]:
    """
    Require WebSocket authentication - closes connection if unauthorized
    Returns user dict on success
    """
    user = await authenticate_websocket(ws)
    
    if not user:
        await ws.close(code=status.WS_1008_POLICY_VIOLATION, reason="Unauthorized")
        return None
    
    return user
