from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
from app.modules.ingestion import documents

model = SentenceTransformer('all-MiniLM-L6-v2')
index = None
metadata = []

def index_documents():
    global index
    texts = [d["text"] for d in documents]
    embeddings = model.encode(texts)

    dim = embeddings.shape[1]
    index = faiss.IndexFlatL2(dim)
    index.add(np.array(embeddings))

    for d in documents:
        metadata.append(d)
