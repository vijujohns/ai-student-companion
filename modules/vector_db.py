import os
import faiss
import pickle
import streamlit as st
from sentence_transformers import SentenceTransformer
from config import *
from modules.pdf_loader import load_pdf_chunks

@st.cache_resource
def get_model():
    """Loads and caches the model to prevent 'client closed' errors."""
    return SentenceTransformer(EMBED_MODEL)

def build_database():
    data = []
    pdf_paths = []
    for root, _, files in os.walk(ROOT_FOLDER):
        for f in files:
            if f.endswith(".pdf"):
                pdf_paths.append(os.path.join(root, f))
    
    if not pdf_paths:
        raise Exception(f"No PDFs found in {ROOT_FOLDER}")

    # UI Progress Bar for file loading
    progress_text = "Reading PDFs..."
    my_bar = st.progress(0, text=progress_text)
    
    for i, path in enumerate(pdf_paths):
        data.extend(load_pdf_chunks(path))
        my_bar.progress((i + 1) / len(pdf_paths), text=f"Processed {os.path.basename(path)}")
    
    texts = [d["text"] for d in data]
    model = get_model()
    
    with st.spinner("Generating Search Index (Embeddings)..."):
        embeddings = model.encode(texts, batch_size=32, show_progress_bar=True, convert_to_numpy=True)

    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    faiss.normalize_L2(embeddings)
    index.add(embeddings)

    os.makedirs(VECTOR_FOLDER, exist_ok=True)
    faiss.write_index(index, INDEX_FILE)
    with open(META_FILE, "wb") as f:
        pickle.dump(data, f)

    my_bar.empty()
    return index, data

def load_database():
    if not os.path.exists(INDEX_FILE):
        return build_database()
    index = faiss.read_index(INDEX_FILE)
    with open(META_FILE, "rb") as f:
        data = pickle.load(f)
    return index, data

def search(query, index, data, k=10, filters=None):
    model = get_model()
    q = model.encode([query], convert_to_numpy=True)
    faiss.normalize_L2(q)
    # Search wider (k*10) to ensure filters have enough candidates to work with
    D, I = index.search(q, k * 10) 

    results = []
    for idx in I[0]:
        if idx >= len(data): continue
        item = data[idx]
        
        if filters:
            m = item["metadata"]
            if filters.get("class") and m.get("class") != filters["class"]: continue
            if filters.get("subject") and m.get("subject") != filters["subject"]: continue
            
            # Robust chapter matching (ignores case and .pdf extension)
            if filters.get("chapter") and filters["chapter"] != "All Chapters":
                target = filters["chapter"].lower().replace(".pdf", "")
                source = m.get("file", "").lower().replace(".pdf", "")
                if target != source: continue
        
        results.append(item)
        if len(results) >= k: break
    return results