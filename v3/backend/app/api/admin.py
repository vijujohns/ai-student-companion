"""
Admin API router module.
"""
from typing import Any, Optional
from fastapi import APIRouter, Body, Depends, HTTPException

from ..modules.adapters import get_default_service_registry
from ..modules.db import get_connection
from ..modules.dependencies import require_role
from ..modules.kb_sync import start_reindex_job, get_reindex_progress
from ..modules.messages import envelope

services = get_default_service_registry()
router = APIRouter(prefix="/admin")


def _start_admin_reindex_job(
    payload: Optional[dict],
    *,
    force_reindex: bool,
    requested_type: str,
):
    target_path = None
    if isinstance(payload, dict):
        target_path = payload.get("path") or payload.get("relative_path") or payload.get("content_id")

    result = start_reindex_job(
        force_reindex=force_reindex,
        requested_type=requested_type,
        target_path=target_path,
    )

    response = {
        "status": result.get("status") or "started",
        "type": result.get("type") or requested_type,
        "job_id": result.get("job_id"),
    }
    if isinstance(result.get("reindex"), dict):
        response["reindex"] = result["reindex"]
    return envelope(response, message_id="MSG-1000")


@router.post("/reindex")
def reindex(payload: Optional[dict] = Body(default=None), user=Depends(require_role("admin"))):
    payload = payload or {}
    requested_type = "file" if isinstance(payload, dict) and (payload.get("path") or payload.get("relative_path") or payload.get("content_id")) else "full"
    return _start_admin_reindex_job(payload, force_reindex=requested_type == "full", requested_type=requested_type)


@router.post("/reindex/full")
def reindex_full(payload: Optional[dict] = Body(default=None), user=Depends(require_role("admin"))):
    return _start_admin_reindex_job(payload, force_reindex=True, requested_type="full")


@router.post("/reindex-incremental")
def incremental_reindex(payload: Optional[dict] = Body(default=None), user=Depends(require_role("admin"))):
    return _start_admin_reindex_job(payload, force_reindex=False, requested_type="incremental")


@router.post("/reindex/incremental")
def incremental_reindex_v2(payload: Optional[dict] = Body(default=None), user=Depends(require_role("admin"))):
    return _start_admin_reindex_job(payload, force_reindex=False, requested_type="incremental")


@router.post("/reindex/file")
def file_reindex(payload: Optional[dict] = Body(default=None), user=Depends(require_role("admin"))):
    payload = payload or {}
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="A file path/content reference is required for file reindex.")

    file_id = payload.get("file_id")
    if file_id is not None:
        result = services.knowledge.queue_reindex(user, scope="file", file_id=int(file_id))
        return envelope(
            {
                "status": "started",
                "type": "file",
                "job_id": result.get("job_id"),
                "queued_files": result.get("queued_files", 0),
            },
            message_id="MSG-1000",
        )

    if not (payload.get("path") or payload.get("relative_path") or payload.get("content_id")):
        raise HTTPException(status_code=400, detail="A file path/content reference is required for file reindex.")
    return _start_admin_reindex_job(payload, force_reindex=False, requested_type="file")


@router.get("/reindex-status")
def admin_reindex_status(user=Depends(require_role("admin"))):
    progress = get_reindex_progress()

    response = {
        "status": progress.get("status") or "idle",
        "type": progress.get("type") or progress.get("mode") or "idle",
        "job_id": progress.get("job_id"),
        "reindex": progress,
    }
    return envelope(response, message_id="MSG-1000")


@router.get("/reindex/status/{job_id}")
def admin_reindex_status_by_job(job_id: str, user=Depends(require_role("admin"))):
    progress = get_reindex_progress(job_id)

    response = {
        "status": progress.get("status") or "idle",
        "type": progress.get("type") or progress.get("mode") or "unknown",
        "job_id": progress.get("job_id") or job_id,
        "reindex": progress,
    }
    return envelope(response, message_id="MSG-1000")


@router.get("/overview")
def admin_overview(user=Depends(require_role("admin"))):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = int(cursor.fetchone()[0] or 0)

    cursor.execute("SELECT COUNT(*) FROM user_class_subscriptions WHERE status='ACTIVE'")
    active_subscriptions = int(cursor.fetchone()[0] or 0)

    cursor.execute("SELECT COUNT(*) FROM indexing_jobs WHERE status='QUEUED'")
    queued_index_jobs = int(cursor.fetchone()[0] or 0)

    cursor.execute("SELECT COUNT(*) FROM indexing_jobs WHERE status='RUNNING'")
    running_index_jobs = int(cursor.fetchone()[0] or 0)

    cursor.execute("SELECT COUNT(*) FROM indexing_jobs WHERE status='FAILED'")
    failed_index_jobs = int(cursor.fetchone()[0] or 0)

    conn.close()

    return envelope(
        {
            "total_users": total_users,
            "active_subscriptions": active_subscriptions,
            "queued_index_jobs": queued_index_jobs,
            "running_index_jobs": running_index_jobs,
            "failed_index_jobs": failed_index_jobs,
        },
        message_id="MSG-1000",
    )
