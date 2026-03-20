import faiss
import numpy as np
import pickle
import os

INDEX_PATH = "app/data/faiss.index"
META_PATH = "app/data/meta.pkl"

index = None
metadata_store = []


# 🔹 LOAD INDEX (FIXED)
def load_index():
    global index, metadata_store

    if os.path.exists(INDEX_PATH):
        index = faiss.read_index(INDEX_PATH)
    else:
        index = None

    if os.path.exists(META_PATH):
        with open(META_PATH, "rb") as f:
            metadata_store = pickle.load(f)
    else:
        metadata_store = []

    # 🔥 SAFETY CHECK
    if index and len(metadata_store) != index.ntotal:
        print("⚠️ Metadata and index mismatch. Resetting...")
        index = None
        metadata_store = []


# 🔹 SAVE INDEX
def save_index():
    global index, metadata_store

    if index:
        faiss.write_index(index, INDEX_PATH)

    with open(META_PATH, "wb") as f:
        pickle.dump(metadata_store, f)


# 🔹 ADD EMBEDDINGS
def add_embeddings(vectors, metadatas):
    global index, metadata_store

    vectors = np.array(vectors).astype("float32")

    if index is None:
        dim = vectors.shape[1]
        index = faiss.IndexFlatL2(dim)

    index.add(vectors)
    metadata_store.extend(metadatas)

    save_index()


# 🔹 SEARCH (PRODUCTION FIXED)
def search(query_vector, k=5, filter_payload=None):
    global index, metadata_store

    if index is None:
        load_index()

    if index is None or len(metadata_store) == 0:
        raise Exception("Index not ready. Run /index first.")

    import numpy as np

    query_vector = np.array([query_vector]).astype("float32")
    D, I = index.search(query_vector, k)

    results = []

    for idx in I[0]:
        if idx >= len(metadata_store):
            continue

        meta = metadata_store[idx]

        # ✅ Apply filter ONLY if values exist
        if filter_payload:
            if filter_payload.get("class") and meta.get("class") != filter_payload.get("class"):
                continue
            if filter_payload.get("subject") and meta.get("subject") != filter_payload.get("subject"):
                continue
            if filter_payload.get("chapter") and meta.get("chapter") != filter_payload.get("chapter"):
                continue

        results.append(meta)

    return results