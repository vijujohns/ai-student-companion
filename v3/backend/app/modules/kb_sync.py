"""
Knowledge-base scan and reindex orchestration.

Separated from faiss_store to avoid a direct static import cycle between
ingestion and vector-store modules.
"""

from __future__ import annotations

import os
import threading
import uuid
from datetime import datetime, UTC
from typing import Optional

from . import faiss_store
from .faiss_store import (
    BASE_DIR,
    _remove_docs_for_source,
    _reset_store,
    documents,
    load_metadata,
    save_index,
    save_metadata,
)
from .ingestion import ingest_pdf

_INDEX_TARGETS = ["concept_index", "summary_index", "qa_index", "formula_index", "image_index", "general_index"]
_REINDEX_PROGRESS_LOCK = threading.RLock()
_REINDEX_PROGRESS = {
    "job_id": None,
    "running": False,
    "status": "idle",
    "mode": "idle",
    "type": "idle",
    "scan_root": "",
    "phase": "Idle",
    "current_file": "",
    "total_files": 0,
    "scanned_files": 0,
    "reindexed_files": 0,
    "skipped_files": 0,
    "removed_files": 0,
    "processed_files": [],
    "skipped_paths": [],
    "removed_paths": [],
    "index_targets": list(_INDEX_TARGETS),
    "errors": [],
    "started_at": None,
    "finished_at": None,
}


def _update_reindex_progress(**changes) -> None:
    with _REINDEX_PROGRESS_LOCK:
        for key, value in changes.items():
            if isinstance(value, list):
                _REINDEX_PROGRESS[key] = list(value)
            else:
                _REINDEX_PROGRESS[key] = value


def get_reindex_progress(job_id: Optional[str] = None) -> dict:
    with _REINDEX_PROGRESS_LOCK:
        snapshot = {
            key: (list(value) if isinstance(value, list) else value)
            for key, value in _REINDEX_PROGRESS.items()
        }

    current_job_id = str(snapshot.get("job_id") or "").strip()
    if job_id and current_job_id and current_job_id != str(job_id).strip():
        return {
            "job_id": str(job_id),
            "running": False,
            "status": "not_found",
            "mode": "unknown",
            "type": "unknown",
            "phase": "No matching reindex job was found.",
            "current_file": "",
            "total_files": 0,
            "scanned_files": 0,
            "reindexed_files": 0,
            "skipped_files": 0,
            "removed_files": 0,
            "processed_files": [],
            "skipped_paths": [],
            "removed_paths": [],
            "index_targets": list(_INDEX_TARGETS),
            "errors": [],
            "started_at": None,
            "finished_at": None,
            "progress_percent": 0,
        }

    snapshot["type"] = str(snapshot.get("type") or snapshot.get("mode") or "idle")
    total_files = int(snapshot.get("total_files") or 0)
    scanned_files = int(snapshot.get("scanned_files") or 0)
    if total_files > 0:
        progress_percent = int(min(100, round((scanned_files / total_files) * 100)))
    elif snapshot.get("status") == "completed":
        progress_percent = 100
    else:
        progress_percent = 0

    snapshot["progress_percent"] = progress_percent
    snapshot["processed_files"] = list(snapshot.get("processed_files") or [])[-6:]
    snapshot["skipped_paths"] = list(snapshot.get("skipped_paths") or [])[-6:]
    snapshot["removed_paths"] = list(snapshot.get("removed_paths") or [])[-6:]
    snapshot["index_targets"] = list(snapshot.get("index_targets") or _INDEX_TARGETS)
    snapshot["errors"] = list(snapshot.get("errors") or [])[-6:]
    return snapshot


def start_reindex_job(
    force_reindex: bool = False,
    target_path: Optional[str] = None,
    requested_type: Optional[str] = None,
) -> dict:
    job_type = str(requested_type or ("file" if target_path else ("full" if force_reindex else "incremental"))).strip().lower()

    with _REINDEX_PROGRESS_LOCK:
        if bool(_REINDEX_PROGRESS.get("running")):
            active_job_id = _REINDEX_PROGRESS.get("job_id")
            return {
                "status": "running",
                "type": str(_REINDEX_PROGRESS.get("type") or _REINDEX_PROGRESS.get("mode") or job_type),
                "job_id": active_job_id,
                "reindex": get_reindex_progress(active_job_id),
            }

        job_id = uuid.uuid4().hex
        _update_reindex_progress(
            job_id=job_id,
            running=True,
            status="queued",
            mode=job_type,
            type=job_type,
            scan_root=os.path.abspath(str(target_path)) if target_path else os.path.join(BASE_DIR, "knowledge_base"),
            phase=f"Queued {job_type} reindex",
            current_file="",
            total_files=0,
            scanned_files=0,
            reindexed_files=0,
            skipped_files=0,
            removed_files=0,
            processed_files=[],
            skipped_paths=[],
            removed_paths=[],
            index_targets=list(_INDEX_TARGETS),
            errors=[],
            started_at=datetime.now(UTC).isoformat(),
            finished_at=None,
        )

    def runner() -> None:
        print(f"🧵 Background {job_type} indexing started (job {job_id})")
        try:
            load_knowledge_base(
                force_reindex=force_reindex,
                target_path=target_path,
                job_id=job_id,
                requested_type=job_type,
            )
            print(f"✅ Background {job_type} indexing completed (job {job_id})")
        except Exception as exc:
            message = f"Background {job_type} reindex failed: {exc}"
            print(f"❌ {message}")
            _update_reindex_progress(
                job_id=job_id,
                running=False,
                status="error",
                mode=job_type,
                type=job_type,
                phase="Reindex failed",
                errors=[message],
                finished_at=datetime.now(UTC).isoformat(),
            )

    threading.Thread(target=runner, daemon=True, name=f"kb-reindex-{job_id[:8]}").start()
    return {
        "status": "started",
        "type": job_type,
        "job_id": job_id,
        "reindex": get_reindex_progress(job_id),
    }


def _display_scan_path(path: str, root: str) -> str:
    try:
        relative = os.path.relpath(path, root)
        if relative and not relative.startswith(".."):
            return relative.replace("\\", "/")
    except Exception:
        pass
    return os.path.basename(path)


def load_knowledge_base(
    force_reindex: bool = False,
    target_path: Optional[str] = None,
    job_id: Optional[str] = None,
    requested_type: Optional[str] = None,
) -> dict:
    kb_path = os.path.join(BASE_DIR, "knowledge_base")
    normalized_target = os.path.abspath(str(target_path)) if target_path else None

    if not normalized_target and not os.path.exists(kb_path):
        print("❌ Knowledge base folder not found")
        resolved_mode = str(requested_type or ("file" if normalized_target else ("full" if force_reindex else "incremental"))).strip().lower()
        result = {
            "job_id": job_id,
            "status": "error",
            "mode": resolved_mode,
            "type": resolved_mode,
            "scan_root": normalized_target or kb_path,
            "phase": "Knowledge base folder not found",
            "current_file": "",
            "total_files": 0,
            "scanned_files": 0,
            "reindexed_files": 0,
            "skipped_files": 0,
            "removed_files": 0,
            "processed_files": [],
            "skipped_paths": [],
            "removed_paths": [],
            "index_targets": list(_INDEX_TARGETS),
            "errors": ["Knowledge base folder not found"],
        }
        _update_reindex_progress(
            running=False,
            started_at=None,
            finished_at=datetime.now(UTC).isoformat(),
            **result,
        )
        return result

    scan_root = normalized_target or kb_path
    print(f"📂 Scanning KB: {scan_root}")

    metadata = load_metadata()
    if not force_reindex and metadata and not faiss_store.documents and not normalized_target:
        print("⚠️ Indexed metadata exists but the loaded chunk list is empty - forcing a one-time full rebuild")
        force_reindex = True

    mode = str(requested_type or ("file" if normalized_target else ("full" if force_reindex else "incremental"))).strip().lower()
    if force_reindex and not normalized_target:
        print("♻️ Starting full reindex")
        _reset_store()
        metadata = {}

    if normalized_target:
        _remove_docs_for_source(normalized_target)

    updated_meta = dict(metadata)
    current_pdf_paths = set()
    stats = {
        "job_id": job_id,
        "status": "running",
        "mode": mode,
        "type": mode,
        "scan_root": scan_root,
        "phase": "Collecting study files",
        "current_file": "",
        "total_files": 0,
        "scanned_files": 0,
        "reindexed_files": 0,
        "skipped_files": 0,
        "removed_files": 0,
        "processed_files": [],
        "skipped_paths": [],
        "removed_paths": [],
        "index_targets": list(_INDEX_TARGETS),
        "errors": [],
    }

    if normalized_target:
        pdf_paths = [normalized_target] if normalized_target.lower().endswith(".pdf") and os.path.exists(normalized_target) else []
    else:
        pdf_paths = []
        for root, _, files in os.walk(kb_path):
            for file in files:
                if file.lower().endswith(".pdf"):
                    pdf_paths.append(os.path.join(root, file))

    stats["total_files"] = len(pdf_paths)
    _update_reindex_progress(
        job_id=job_id,
        running=True,
        status="running",
        mode=mode,
        type=mode,
        scan_root=scan_root,
        phase=f"Preparing {len(pdf_paths)} file(s) for {mode} reindex",
        current_file="",
        total_files=len(pdf_paths),
        scanned_files=0,
        reindexed_files=0,
        skipped_files=0,
        removed_files=0,
        processed_files=[],
        skipped_paths=[],
        removed_paths=[],
        index_targets=list(_INDEX_TARGETS),
        errors=[],
        started_at=datetime.now(UTC).isoformat(),
        finished_at=None,
    )

    report_root = os.path.dirname(normalized_target) if normalized_target else kb_path

    for full_path in pdf_paths:
        stats["scanned_files"] += 1
        current_pdf_paths.add(full_path)
        last_modified = os.path.getmtime(full_path)
        updated_meta[full_path] = last_modified
        display_path = _display_scan_path(full_path, report_root)

        needs_reindex = normalized_target is not None or force_reindex or full_path not in metadata or metadata[full_path] != last_modified
        stats["current_file"] = display_path
        if needs_reindex:
            print(f"🔄 Re-indexing: {os.path.basename(full_path)}")
            _update_reindex_progress(
                running=True,
                status="running",
                phase=f"Processing {display_path}",
                current_file=display_path,
                scanned_files=stats["scanned_files"],
                reindexed_files=stats["reindexed_files"],
                skipped_files=stats["skipped_files"],
                removed_files=stats["removed_files"],
                processed_files=stats["processed_files"],
                skipped_paths=stats["skipped_paths"],
                removed_paths=stats["removed_paths"],
                errors=stats["errors"],
            )
            _remove_docs_for_source(full_path)
            try:
                ingest_pdf(full_path, use_llm_summary=False)
                stats["reindexed_files"] += 1
                stats["processed_files"].append(display_path)
            except Exception as exc:
                message = f"Skipping unreadable PDF during reindex: {full_path} ({exc})"
                print(f"⚠️  {message}")
                stats["errors"].append(message)
        else:
            stats["skipped_files"] += 1
            stats["skipped_paths"].append(display_path)
            _update_reindex_progress(
                running=True,
                status="running",
                phase=f"Skipping unchanged {display_path}",
                current_file=display_path,
                scanned_files=stats["scanned_files"],
                reindexed_files=stats["reindexed_files"],
                skipped_files=stats["skipped_files"],
                removed_files=stats["removed_files"],
                processed_files=stats["processed_files"],
                skipped_paths=stats["skipped_paths"],
                removed_paths=stats["removed_paths"],
                errors=stats["errors"],
            )

        if needs_reindex:
            had_warning = any(display_path in str(item) for item in stats["errors"])
            _update_reindex_progress(
                running=True,
                status="running",
                phase=f"Completed with warnings: {display_path}" if had_warning else f"Completed {display_path}",
                current_file=display_path,
                scanned_files=stats["scanned_files"],
                reindexed_files=stats["reindexed_files"],
                skipped_files=stats["skipped_files"],
                removed_files=stats["removed_files"],
                processed_files=stats["processed_files"],
                skipped_paths=stats["skipped_paths"],
                removed_paths=stats["removed_paths"],
                errors=stats["errors"],
            )

    if not normalized_target and not force_reindex:
        deleted = set(metadata.keys()) - current_pdf_paths
        for path in deleted:
            _remove_docs_for_source(path)
            updated_meta.pop(path, None)
            stats["removed_files"] += 1
            stats["removed_paths"].append(_display_scan_path(path, kb_path))

    stats["phase"] = "Saving rebuilt indexes"
    _update_reindex_progress(
        running=True,
        status="running",
        phase=stats["phase"],
        current_file="",
        scanned_files=stats["scanned_files"],
        reindexed_files=stats["reindexed_files"],
        skipped_files=stats["skipped_files"],
        removed_files=stats["removed_files"],
        processed_files=stats["processed_files"],
        skipped_paths=stats["skipped_paths"],
        removed_paths=stats["removed_paths"],
        errors=stats["errors"],
    )

    save_metadata(updated_meta)
    save_index()

    stats["status"] = "completed"
    stats["phase"] = f"Finished {mode} reindex"
    stats["current_file"] = ""
    _update_reindex_progress(
        running=False,
        finished_at=datetime.now(UTC).isoformat(),
        **stats,
    )

    print(f"✅ Knowledge base updated ({mode})")
    return stats
