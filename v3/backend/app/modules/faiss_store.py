"""
FAISS vector store
"""

import faiss
import numpy as np
import os
import pickle
import json
import threading

from ..core.config_loader import get_rag_config
from ..core.env_vars import ENV
from .retrieval_orchestrator import hybrid_rank_results

# Paths
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
DATA_DIR = os.path.join(BASE_DIR, "data")

INDEX_FILE = os.path.join(DATA_DIR, "faiss.index")
DOC_FILE = os.path.join(DATA_DIR, "documents.pkl")
META_FILE = os.path.join(DATA_DIR, "metadata.json")
MULTI_INDEX_FILE = os.path.join(DATA_DIR, "logical_indexes.json")

_DEFAULT_EMBEDDING_DIM = int(os.getenv(ENV.FAISS_EMBEDDING_DIM, "768"))
_MODEL_LOCK = threading.RLock()


def _candidate_embedding_models() -> list[str]:
    rag_cfg = get_rag_config()
    configured = str(rag_cfg.get("embedding_model") or "").strip()
    candidates: list[str] = []
    for name in (configured, "BAAI/bge-base-en-v1.5", "all-MiniLM-L6-v2"):
        if name and name not in candidates:
            candidates.append(name)
    return candidates


class _LazyEmbeddingModel:
    """Delay SentenceTransformer import/loading until first encode call."""

    def __init__(self):
        self._model = None

    def _ensure_loaded(self):
        global EMBEDDING_MODEL_NAME, embedding_dim

        if self._model is not None:
            return self._model

        with _MODEL_LOCK:
            if self._model is not None:
                return self._model

            from sentence_transformers import SentenceTransformer

            last_error = None
            for model_name in _candidate_embedding_models():
                try:
                    loaded_model = SentenceTransformer(model_name)
                    self._model = loaded_model
                    EMBEDDING_MODEL_NAME = model_name
                    embedding_dim = int(loaded_model.get_sentence_embedding_dimension())
                    print(f"✅ Embedding model loaded: {model_name}")
                    return loaded_model
                except Exception as exc:
                    last_error = exc
                    print(f"⚠️ Failed to load embedding model '{model_name}', trying fallback: {exc}")

            raise RuntimeError("Unable to load any sentence-transformer embedding model") from last_error

    def encode(self, *args, **kwargs):
        return self._ensure_loaded().encode(*args, **kwargs)

    def get_sentence_embedding_dimension(self):
        if self._model is not None:
            return self._model.get_sentence_embedding_dimension()
        return embedding_dim

    def __getattr__(self, name):
        return getattr(self._ensure_loaded(), name)


def _as_float32_array(values):
    return np.array(values, dtype="float32")


def _ensure_model_ready():
    model._ensure_loaded()
    _ensure_index_matches_model()


def _ensure_index_matches_model():
    """Keep the in-memory FAISS index aligned with the loaded embedding dimension."""
    global index, embedding_dim

    detected_dim = int(model.get_sentence_embedding_dimension())
    embedding_dim = detected_dim
    if getattr(index, "d", detected_dim) == detected_dim:
        return

    fresh_index = faiss.IndexFlatL2(detected_dim)
    texts = []
    for doc in documents:
        if isinstance(doc, dict):
            texts.append(doc.get("text", "") or "")
        else:
            texts.append(str(doc) or "")

    if texts:
        vectors = model.encode(texts)
        fresh_index.add(_as_float32_array(vectors))

    index = fresh_index


LOGICAL_INDEX_NAMES = (
    "concept_index",
    "summary_index",
    "qa_index",
    "formula_index",
    "image_index",
    "general_index",
)


def _empty_logical_indexes() -> dict[str, list[int]]:
    return {name: [] for name in LOGICAL_INDEX_NAMES}


def _rebuild_logical_indexes() -> None:
    logical_indexes.clear()
    logical_indexes.update(_empty_logical_indexes())
    for doc_index, doc in enumerate(documents):
        if isinstance(doc, dict):
            index_name = doc.get("index_name") or (doc.get("metadata") or {}).get("index_name") or "general_index"
        else:
            index_name = "general_index"
        logical_indexes.setdefault(str(index_name), []).append(doc_index)


# Model + FAISS store
model = _LazyEmbeddingModel()
EMBEDDING_MODEL_NAME = ""
embedding_dim = _DEFAULT_EMBEDDING_DIM
index = faiss.IndexFlatL2(embedding_dim)
documents = []   # list of dicts: {text, source, metadata, index_name}
logical_indexes = _empty_logical_indexes()


def add_doc(text, source, metadata=None, index_name=None):
    _ensure_model_ready()
    vec = model.encode([text])
    index.add(_as_float32_array(vec))
    normalized_metadata = dict(metadata or {})
    logical_name = str(index_name or normalized_metadata.get("index_name") or "general_index").strip() or "general_index"
    normalized_metadata.setdefault("index_name", logical_name)
    documents.append({
        "text": text,
        "source": source,
        "metadata": normalized_metadata,
        "index_name": logical_name,
    })
    logical_indexes.setdefault(logical_name, []).append(len(documents) - 1)


def _rebuild_index_from_documents():
    """Rebuild FAISS index from in-memory documents list."""
    global index
    _ensure_model_ready()
    index = faiss.IndexFlatL2(embedding_dim)
    _rebuild_logical_indexes()
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
        index.add(_as_float32_array(vectors))


def _remove_docs_for_source(source_path: str):
    """Drop all chunks for a source file and rebuild index."""
    if not source_path:
        return
    before = len(documents)
    documents[:] = [
        d for d in documents
        if not (isinstance(d, dict) and d.get("source") == source_path)
    ]
    if len(documents) != before:
        _rebuild_index_from_documents()


def _reset_store():
    """Clear all in-memory vectors and documents for a full rebuild."""
    documents.clear()
    logical_indexes.clear()
    logical_indexes.update(_empty_logical_indexes())
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

    _ensure_model_ready()
    q = model.encode([query])
    limit = min(len(documents), max(search_k, top_k, 1))
    D, I = index.search(_as_float32_array(q), limit)

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

    with open(MULTI_INDEX_FILE, "w") as f:
        json.dump(logical_indexes, f, indent=2)

    print("✅ FAISS index saved")


def load_index():
    global index, embedding_dim

    if os.path.exists(INDEX_FILE) and os.path.exists(DOC_FILE):
        try:
            index = faiss.read_index(INDEX_FILE)
            embedding_dim = int(getattr(index, "d", embedding_dim) or embedding_dim)

            with open(DOC_FILE, "rb") as f:
                loaded_documents = pickle.load(f)

            documents.clear()
            documents.extend(list(loaded_documents or []))

            logical_indexes.clear()
            logical_indexes.update(_empty_logical_indexes())
            if os.path.exists(MULTI_INDEX_FILE):
                with open(MULTI_INDEX_FILE, "r") as f:
                    loaded_logical_indexes = json.load(f)
                if isinstance(loaded_logical_indexes, dict):
                    logical_indexes.update(loaded_logical_indexes)

            _rebuild_logical_indexes()
            print("✅ FAISS index loaded from disk")
            return
        except Exception as exc:
            print(f"⚠️ Failed to load persisted FAISS data ({exc}); continuing with an empty index")

    documents.clear()
    logical_indexes.clear()
    logical_indexes.update(_empty_logical_indexes())
    index = faiss.IndexFlatL2(embedding_dim)
    print("⚠️ No existing index found")


# Backward-compat alias retained for older tests/callers that still patch
# app.modules.faiss_store.load_knowledge_base after the orchestration moved to kb_sync.
def load_knowledge_base(force_reindex: bool = False, target_path: str | None = None):
    from .kb_sync import load_knowledge_base as _load_knowledge_base

    return _load_knowledge_base(force_reindex=force_reindex, target_path=target_path)


