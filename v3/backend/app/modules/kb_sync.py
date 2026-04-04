"""
Knowledge-base scan and reindex orchestration.

Separated from faiss_store to avoid a direct static import cycle between
ingestion and vector-store modules.
"""

from __future__ import annotations

import os
from typing import Optional

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


def load_knowledge_base(force_reindex: bool = False, target_path: Optional[str] = None) -> dict:
    kb_path = os.path.join(BASE_DIR, "knowledge_base")
    normalized_target = os.path.abspath(str(target_path)) if target_path else None

    if not normalized_target and not os.path.exists(kb_path):
        print("❌ Knowledge base folder not found")
        return {
            "status": "error",
            "mode": "full" if force_reindex else "incremental",
            "scanned_files": 0,
            "reindexed_files": 0,
            "skipped_files": 0,
            "removed_files": 0,
            "errors": ["Knowledge base folder not found"],
        }

    scan_root = normalized_target or kb_path
    print(f"📂 Scanning KB: {scan_root}")

    metadata = load_metadata()
    if not force_reindex and metadata and not documents and not normalized_target:
        print("⚠️ Indexed metadata exists but FAISS documents are empty — forcing a full rebuild")
        force_reindex = True

    mode = "selective" if normalized_target else ("full" if force_reindex else "incremental")
    if force_reindex and not normalized_target:
        print("♻️ Starting full reindex")
        _reset_store()
        metadata = {}

    if normalized_target:
        _remove_docs_for_source(normalized_target)

    updated_meta = dict(metadata)
    current_pdf_paths = set()
    stats = {
        "status": "ok",
        "mode": mode,
        "scanned_files": 0,
        "reindexed_files": 0,
        "skipped_files": 0,
        "removed_files": 0,
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

    for full_path in pdf_paths:
        stats["scanned_files"] += 1
        current_pdf_paths.add(full_path)
        last_modified = os.path.getmtime(full_path)
        updated_meta[full_path] = last_modified

        needs_reindex = normalized_target is not None or force_reindex or full_path not in metadata or metadata[full_path] != last_modified
        if needs_reindex:
            print(f"🔄 Re-indexing: {os.path.basename(full_path)}")
            _remove_docs_for_source(full_path)
            try:
                ingest_pdf(full_path)
                stats["reindexed_files"] += 1
            except Exception as exc:
                message = f"Skipping unreadable PDF during reindex: {full_path} ({exc})"
                print(f"⚠️  {message}")
                stats["errors"].append(message)
        else:
            stats["skipped_files"] += 1

    if not normalized_target and not force_reindex:
        deleted = set(metadata.keys()) - current_pdf_paths
        for path in deleted:
            _remove_docs_for_source(path)
            updated_meta.pop(path, None)
            stats["removed_files"] += 1

    save_metadata(updated_meta)
    save_index()

    print(f"✅ Knowledge base updated ({mode})")
    return stats
