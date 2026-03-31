"""
FAISS vector store
"""

from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
import os
import pickle
import json

# Paths
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
DATA_DIR = os.path.join(BASE_DIR, "data")

INDEX_FILE = os.path.join(DATA_DIR, "faiss.index")
DOC_FILE = os.path.join(DATA_DIR, "documents.pkl")
META_FILE = os.path.join(DATA_DIR, "metadata.json")

# Model
model = SentenceTransformer("all-MiniLM-L6-v2")
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


def search(query, filter_path=None, top_k=4, search_k=8):
    if len(documents) == 0:
        return ["No documents available"]

    q = model.encode([query])
    D, I = index.search(np.array(q), max(search_k, top_k))

    results = []

    scored_results = []

    for idx, i in enumerate(I[0]):
        if i < len(documents):
            doc = documents[i]

            if isinstance(doc, str):
                text = doc
                source = None
            else:
                text = doc.get("text", "")
                source = doc.get("source")

            # 🔹 Apply filter
            if filter_path and source != filter_path:
                continue

            # 🔥 Combine FAISS score + position score
            distance_score = D[0][idx]
            position_score = idx * 0.1  # earlier = better

            final_score = distance_score + position_score

            scored_results.append((final_score, text))

    # 🔹 Sort by score (lower = better)
    scored_results.sort(key=lambda x: x[0])

    # 🔹 Take top-k best chunks
    results = [text for _, text in scored_results[:top_k]]

    if not results:
        return ["No relevant context found for selected content"]

    return results


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


def load_knowledge_base(force_reindex=False):
    from .ingestion import ingest_pdf  # ✅ lazy import

    kb_path = os.path.join(BASE_DIR, "knowledge_base")

    if not os.path.exists(kb_path):
        print("❌ Knowledge base folder not found")
        return

    print(f"📂 Scanning KB: {kb_path}")

    metadata = load_metadata()
    if force_reindex:
        print("♻️ Starting full reindex")
        _reset_store()
        metadata = {}

    updated_meta = {}

    current_pdf_paths = set()

    for root, _, files in os.walk(kb_path):
        for file in files:
            if file.lower().endswith(".pdf"):
                full_path = os.path.join(root, file)
                current_pdf_paths.add(full_path)

                last_modified = os.path.getmtime(full_path)
                updated_meta[full_path] = last_modified

                if force_reindex or full_path not in metadata or metadata[full_path] != last_modified:
                    print(f"🔄 Re-indexing: {file}")
                    _remove_docs_for_source(full_path)
                    ingest_pdf(full_path)

    # Remove deleted PDFs from the in-memory index during incremental updates.
    if not force_reindex:
        deleted = set(metadata.keys()) - current_pdf_paths
        for path in deleted:
            _remove_docs_for_source(path)

    save_metadata(updated_meta)
    save_index()

    mode = "full" if force_reindex else "incremental"
    print(f"✅ Knowledge base updated ({mode})")