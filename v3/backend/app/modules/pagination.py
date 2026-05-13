"""Small pagination helpers for API-backed collections."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple

from fastapi import HTTPException

DEFAULT_LIMIT = 50
MAX_LIMIT = 100


def normalize_pagination(limit: Optional[int] = None, offset: Optional[int] = None) -> Tuple[int, int]:
    try:
        normalized_limit = DEFAULT_LIMIT if limit is None else int(limit)
        normalized_offset = 0 if offset is None else int(offset)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Pagination values must be integers")

    if normalized_limit < 1 or normalized_limit > MAX_LIMIT:
        raise HTTPException(status_code=400, detail=f"limit must be between 1 and {MAX_LIMIT}")
    if normalized_offset < 0:
        raise HTTPException(status_code=400, detail="offset must be greater than or equal to 0")

    return normalized_limit, normalized_offset


def paginate_items(items: Iterable[Dict[str, Any]], limit: Optional[int] = None, offset: Optional[int] = None) -> Dict[str, Any]:
    normalized_limit, normalized_offset = normalize_pagination(limit, offset)
    all_items: List[Dict[str, Any]] = list(items or [])
    page_items = all_items[normalized_offset:normalized_offset + normalized_limit]
    total = len(all_items)
    next_offset = normalized_offset + normalized_limit if normalized_offset + normalized_limit < total else None
    return {
        "items": page_items,
        "pagination": {
            "limit": normalized_limit,
            "offset": normalized_offset,
            "count": len(page_items),
            "total": total,
            "next_offset": next_offset,
            "has_more": next_offset is not None,
        },
    }
