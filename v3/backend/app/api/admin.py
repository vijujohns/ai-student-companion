"""
Admin API router module.
"""
import logging
from typing import Any, Optional
from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel

from ..modules.adapters import get_default_service_registry
from ..modules.db import get_connection
from ..modules.dependencies import require_role
from ..modules.kb_sync import start_reindex_job, get_reindex_progress
from ..modules.messages import envelope

services = get_default_service_registry()
router = APIRouter(prefix="/admin")


class ReindexRequest(BaseModel):
    """
    Request model for reindex operations.
    """
    path: Optional[str] = None
    relative_path: Optional[str] = None
    content_id: Optional[str] = None
    file_id: Optional[int] = None


def _determine_reindex_type(payload: Optional[dict]) -> str:
    """
    Determine the reindex type based on the payload.
    
    Args:
        payload: The request payload dictionary.
    
    Returns:
        str: The reindex type ("full", "incremental", or "file").
    """
    if not payload:
        return "full"
    if payload.get("file_id") or payload.get("path") or payload.get("relative_path") or payload.get("content_id"):
        return "file"
    return "incremental"


def _start_admin_reindex_job(
    payload: Optional[dict],
    *,
    force_reindex: bool,
    requested_type: str,
):
    target_path = None
    if isinstance(payload, dict):
        target_path = payload.get("path") or payload.get("relative_path") or payload.get("content_id")

    logging.info(f"Admin reindex started: type={requested_type}, force={force_reindex}, target_path={target_path}")
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
def reindex(payload: Optional[ReindexRequest] = Body(default=None), user=Depends(require_role("admin"))):
    """
    Start a reindex job based on the payload type.
    
    Args:
        payload: Optional ReindexRequest containing reindex parameters.
        user: The authenticated admin user.
    
    Returns:
        Enveloped response with reindex job details.
    """
    payload_dict = payload.dict() if payload else None
    requested_type = _determine_reindex_type(payload_dict)
    return _start_admin_reindex_job(payload_dict, force_reindex=requested_type == "full", requested_type=requested_type)


@router.post("/reindex/full")
def reindex_full(payload: Optional[ReindexRequest] = Body(default=None), user=Depends(require_role("admin"))):
    """
    Start a full reindex job.
    
    Args:
        payload: Optional ReindexRequest containing reindex parameters.
        user: The authenticated admin user.
    
    Returns:
        Enveloped response with reindex job details.
    """
    payload_dict = payload.dict() if payload else None
    return _start_admin_reindex_job(payload_dict, force_reindex=True, requested_type="full")


@router.post("/reindex/incremental")
def incremental_reindex(payload: Optional[ReindexRequest] = Body(default=None), user=Depends(require_role("admin"))):
    """
    Start an incremental reindex job.
    
    Args:
        payload: Optional ReindexRequest containing reindex parameters.
        user: The authenticated admin user.
    
    Returns:
        Enveloped response with reindex job details.
    """
    payload_dict = payload.dict() if payload else None
    return _start_admin_reindex_job(payload_dict, force_reindex=False, requested_type="incremental")


@router.post("/reindex/file")
def file_reindex(payload: ReindexRequest = Body(...), user=Depends(require_role("admin"))):
    """
    Start a file-specific reindex job.
    
    Args:
        payload: ReindexRequest containing file reindex parameters (must include file_id, path, etc.).
        user: The authenticated admin user.
    
    Returns:
        Enveloped response with reindex job details.
    
    Raises:
        HTTPException: If payload is invalid or missing required fields.
    """
    payload_dict = payload.dict()

    file_id = payload.file_id
    if file_id is not None:
        result = services.knowledge.queue_reindex(user, scope="file", file_id=file_id)
        return envelope(
            {
                "status": "started",
                "type": "file",
                "job_id": result.get("job_id"),
                "queued_files": result.get("queued_files", 0),
            },
            message_id="MSG-1000",
        )

    if not (payload.path or payload.relative_path or payload.content_id):
        raise HTTPException(status_code=400, detail="A file path, relative_path, or content_id is required for file reindex.")
    return _start_admin_reindex_job(payload_dict, force_reindex=False, requested_type="file")


@router.get("/reindex-status")
def admin_reindex_status(user=Depends(require_role("admin"))):
    """
    Get the current reindex job status.
    
    Args:
        user: The authenticated admin user.
    
    Returns:
        Enveloped response with reindex status details.
    """
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
    """
    Get the status of a specific reindex job by ID.
    
    Args:
        job_id: The job ID to query.
        user: The authenticated admin user.
    
    Returns:
        Enveloped response with job-specific reindex status details.
    """
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
    """
    Get an overview of system metrics including users, subscriptions, and index jobs.
    
    Args:
        user: The authenticated admin user.
    
    Returns:
        Enveloped response with system overview data.
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    (SELECT COUNT(*) FROM users) AS total_users,
                    (SELECT COUNT(*) FROM user_class_subscriptions WHERE status='ACTIVE') AS active_subscriptions,
                    (SELECT COUNT(*) FROM indexing_jobs WHERE status='QUEUED') AS queued_index_jobs,
                    (SELECT COUNT(*) FROM indexing_jobs WHERE status='RUNNING') AS running_index_jobs,
                    (SELECT COUNT(*) FROM indexing_jobs WHERE status='FAILED') AS failed_index_jobs
            """)
            row = cursor.fetchone()
            return envelope(
                {
                    "total_users": int(row[0] or 0),
                    "active_subscriptions": int(row[1] or 0),
                    "queued_index_jobs": int(row[2] or 0),
                    "running_index_jobs": int(row[3] or 0),
                    "failed_index_jobs": int(row[4] or 0),
                },
                message_id="MSG-1000",
            )
    except Exception as e:
        # Log the error and return a safe default response
        import logging
        logging.error(f"Error fetching admin overview: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while fetching overview.")
