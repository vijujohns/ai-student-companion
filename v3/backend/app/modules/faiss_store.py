"""
FAISS vector store
"""

from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
import os
import pickle
import json

from ..core.config_loader import get_rag_config
from .retrieval_orchestrator import hybrid_rank_results

# Paths
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
DATA_DIR = os.path.join(BASE_DIR, "data")

INDEX_FILE = os.path.join(DATA_DIR, "faiss.index")
DOC_FILE = os.path.join(DATA_DIR, "documents.pkl")
META_FILE = os.path.join(DATA_DIR, "metadata.json")


def _load_embedding_model():
    rag_cfg = get_rag_config()
    configured = str(rag_cfg.get("embedding_model") or "").strip()
    candidates = []
    for name in (configured, "BAAI/bge-base-en-v1.5", "all-MiniLM-L6-v2"):
        if name and name not in candidates:
            candidates.append(name)

    last_error = None
    for model_name in candidates:
        try:
            loaded_model = SentenceTransformer(model_name)
            print(f"✅ Embedding model loaded: {model_name}")
            return loaded_model, model_name
        except Exception as exc:
            last_error = exc
            print(f"⚠️ Failed to load embedding model '{model_name}', trying fallback: {exc}")

    raise RuntimeError("Unable to load any sentence-transformer embedding model") from last_error


# Model
model, EMBEDDING_MODEL_NAME = _load_embedding_model()
embedding_dim = model.get_sentence_embedding_dimension()

# FAISS
index = faiss.IndexFlatL2(embedding_dim)
documents = []   # list of dicts: {text, source}


def add_doc(text, source):
    vec = model.encode([text])
    index.add(np.array(vec))
    documents.append({
        "text": text,
        "source": source
    })


def _rebuild_index_from_documents():
    """Rebuild FAISS index from in-memory documents list."""
    global index
    index = faiss.IndexFlatL2(embedding_dim)
    if not documents:
        return

    texts = []
    for doc in documents:
        if isinstance(doc, dict):
            text = doc.get("text", "")
        else:
            text = str(doc)
        texts.append(text or "")

    if texts:
        vectors = model.encode(texts)
        index.add(np.array(vectors))


def _remove_docs_for_source(source_path: str):
    """Drop all chunks for a source file and rebuild index."""
    global documents
    if not source_path:
        return
    before = len(documents)
    documents = [
        d for d in documents
        if not (isinstance(d, dict) and d.get("source") == source_path)
    ]
    if len(documents) != before:
        _rebuild_index_from_documents()


def _reset_store():
    """Clear all in-memory vectors and documents for a full rebuild."""
    global documents
    documents = []
    _rebuild_index_from_documents()


def search(
    query,
    filter_path=None,
    top_k=4,
    search_k=8,
    task: str = "qa",
    source_types=None,
    return_details: bool = False,
):
    if len(documents) == 0:
        return []

    q = model.encode([query])
    limit = min(len(documents), max(search_k, top_k, 1))
    D, I = index.search(np.array(q), limit)

    ranked = hybrid_rank_results(
        query,
        documents,
        I[0] if len(I) else [],
        D[0] if len(D) else [],
        filter_path=filter_path,
        top_k=top_k,
        task=task,
        source_types=source_types,
    )

    if return_details:
        return ranked
    return [item.get("text", "") for item in ranked if item.get("text")]


def load_metadata():
    if not os.path.exists(META_FILE):
        return {}

    with open(META_FILE, "r") as f:
        return json.load(f)


def save_metadata(meta):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(META_FILE, "w") as f:
        json.dump(meta, f, indent=2)


def save_index():
    os.makedirs(DATA_DIR, exist_ok=True)

    faiss.write_index(index, INDEX_FILE)

    with open(DOC_FILE, "wb") as f:
        pickle.dump(documents, f)

    print("✅ FAISS index saved")


def load_index():
    global index, documents

    if os.path.exists(INDEX_FILE) and os.path.exists(DOC_FILE):
        index = faiss.read_index(INDEX_FILE)

        with open(DOC_FILE, "rb") as f:
            documents = pickle.load(f)

        print("✅ FAISS index loaded from disk")
    else:
        print("⚠️ No existing index found")


# Backward-compat alias retained for older tests/callers that still patch
# app.modules.faiss_store.load_knowledge_base after the orchestration moved to kb_sync.
def load_knowledge_base(force_reindex: bool = False):
    from .kb_sync import load_knowledge_base as _load_knowledge_base

    return _load_knowledge_base(force_reindex=force_reindex)


