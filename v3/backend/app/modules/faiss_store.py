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
documents = []


def add_doc(text):
    vec = model.encode([text])
    index.add(np.array(vec))
    documents.append(text)


def search(query):
    if len(documents) == 0:
        return ["No documents available"]

    q = model.encode([query])
    D, I = index.search(np.array(q), 3)

    results = []
    for i in I[0]:
        if i < len(documents):
            results.append(documents[i])

    return results if results else ["No relevant context found"]


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


def load_knowledge_base():
    from app.modules.ingestion import ingest_pdf  # ✅ lazy import

    kb_path = os.path.join(BASE_DIR, "knowledge_base")

    if not os.path.exists(kb_path):
        print("❌ Knowledge base folder not found")
        return

    print(f"📂 Scanning KB: {kb_path}")

    metadata = load_metadata()
    updated_meta = {}

    for root, _, files in os.walk(kb_path):
        for file in files:
            if file.lower().endswith(".pdf"):
                full_path = os.path.join(root, file)

                last_modified = os.path.getmtime(full_path)
                updated_meta[full_path] = last_modified

                if full_path not in metadata or metadata[full_path] != last_modified:
                    print(f"🔄 Re-indexing: {file}")
                    ingest_pdf(full_path)

    save_metadata(updated_meta)
    save_index()

    print("✅ Knowledge base updated")