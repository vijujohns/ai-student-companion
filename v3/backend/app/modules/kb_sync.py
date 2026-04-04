"""
Knowledge-base scan and reindex orchestration.

Separated from faiss_store to avoid a direct static import cycle between
ingestion and vector-store modules.
"""

from __future__ import annotations

import os

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


def load_knowledge_base(force_reindex: bool = False) -> None:
    kb_path = os.path.join(BASE_DIR, "knowledge_base")

    if not os.path.exists(kb_path):
        print("❌ Knowledge base folder not found")
        return

    print(f"📂 Scanning KB: {kb_path}")

    metadata = load_metadata()
    if not force_reindex and metadata and not documents:
        print("⚠️ Indexed metadata exists but FAISS documents are empty — forcing a full rebuild")
        force_reindex = True

    if force_reindex:
        print("♻️ Starting full reindex")
        _reset_store()
        metadata = {}

    updated_meta = {}
    current_pdf_paths = set()

    for root, _, files in os.walk(kb_path):
        for file in files:
            if not file.lower().endswith(".pdf"):
                continue

            full_path = os.path.join(root, file)
            current_pdf_paths.add(full_path)

            last_modified = os.path.getmtime(full_path)
            updated_meta[full_path] = last_modified

            if force_reindex or full_path not in metadata or metadata[full_path] != last_modified:
                print(f"🔄 Re-indexing: {file}")
                _remove_docs_for_source(full_path)
                try:
                    ingest_pdf(full_path)
                except Exception as exc:
                    # Keep background scan alive even when one PDF is corrupted.
                    print(f"⚠️  Skipping unreadable PDF during reindex: {full_path} ({exc})")

    # Remove deleted PDFs from the in-memory index during incremental updates.
    if not force_reindex:
        deleted = set(metadata.keys()) - current_pdf_paths
        for path in deleted:
            _remove_docs_for_source(path)

    save_metadata(updated_meta)
    save_index()

    mode = "full" if force_reindex else "incremental"
    print(f"✅ Knowledge base updated ({mode})")
