import os
from typing import Optional
from urllib.parse import unquote

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from ..modules.dependencies import get_current_user
from ..modules.messages import envelope
from ..modules.file_management import upload_pdf, resolve_content_reference, get_files_tree, get_index_status
from ..modules.policy import release_usage
from ..schemas.request import UploadedFileRenameRequest
from ..schemas.response import (
    FileTreeResponse,
    IndexStatusResponse,
    ContentsResponse,
    ClassListResponse,
    SubjectsResponse,
    FoldersResponse,
)
from .common import _consume_quota_or_raise, services

router = APIRouter()


def _kb_dir() -> str:
    return os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")), "knowledge_base")


@router.post("/files/upload")
async def upload_file(
    class_name: str = Form(...),
    subject_name: str = Form(...),
    folder_name: str = Form(...),
    display_name: str = Form(...),
    upload: UploadFile = File(...),
    user=Depends(get_current_user),
):
    _consume_quota_or_raise(user, "upload")
    try:
        result = upload_pdf(
            user=user,
            upload=upload,
            class_name=class_name,
            subject_name=subject_name,
            folder_name=folder_name,
            display_name=display_name,
        )
    except Exception:
        release_usage(user["username"], "upload")
        raise
    return envelope(result, message_id="MSG-1301")


@router.get("/files/tree", response_model=FileTreeResponse)
def files_tree(user=Depends(get_current_user)):
    return envelope({"items": services.knowledge.file_tree(user)}, message_id="MSG-1000")


@router.get("/files/index-status", response_model=IndexStatusResponse)
def files_index_status(file_id: Optional[int] = None, user=Depends(get_current_user)):
    return envelope({"items": services.knowledge.index_status(user, file_id=file_id)}, message_id="MSG-1000")


@router.post("/files/reindex")
def files_reindex(scope: str = Form("changed"), file_id: Optional[int] = Form(None), user=Depends(get_current_user)):
    result = services.knowledge.queue_reindex(user, scope=scope, file_id=file_id)
    return envelope(result, message_id="MSG-1305")


@router.put("/files/{file_id}")
def rename_file(file_id: int, request: UploadedFileRenameRequest, user=Depends(get_current_user)):
    result = services.knowledge.rename_uploaded_file(user, file_id=file_id, display_name=request.display_name)
    return envelope(result, message_id="MSG-1000")


@router.delete("/files/{file_id}")
def delete_file(file_id: int, user=Depends(get_current_user)):
    result = services.knowledge.delete_uploaded_file(user, file_id=file_id)
    return envelope(result, message_id="MSG-1000")


@router.get("/pdf")
def serve_pdf(content_id: Optional[str] = None, path: Optional[str] = None, user=Depends(get_current_user)):
    reference = unquote(content_id or path or "")
    if not reference:
        raise HTTPException(status_code=400, detail="Content reference is required")

    try:
        resolved = resolve_content_reference(user, reference)
    except HTTPException as exc:
        if path and not content_id and exc.status_code == 400:
            raise HTTPException(status_code=403, detail="Access denied")
        raise

    full_path = resolved["path"] if resolved else None
    if not full_path or not os.path.isfile(full_path):
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(full_path, media_type="application/pdf")


@router.get("/classes", response_model=ClassListResponse)
def get_classes(user=Depends(get_current_user)):
    return envelope({"classes": services.knowledge.list_classes()}, message_id="MSG-1000")


@router.get("/subjects", response_model=SubjectsResponse)
def get_subjects(class_name: str, user=Depends(get_current_user)):
    try:
        subjects = services.knowledge.list_subjects(class_name)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid path component")
    return envelope({"subjects": subjects}, message_id="MSG-1000")


@router.get("/folders", response_model=FoldersResponse)
def get_folders(class_name: str, subject: str, user=Depends(get_current_user)):
    try:
        folders = services.knowledge.list_folders(class_name, subject)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid path component")
    return envelope({"folders": folders}, message_id="MSG-1000")


@router.get("/contents", response_model=ContentsResponse)
def get_contents(class_name: str, subject: str, folder: str, user=Depends(get_current_user)):
    try:
        contents = services.knowledge.list_contents(class_name, subject, folder)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid path component")
    return envelope({"contents": contents}, message_id="MSG-1000")
