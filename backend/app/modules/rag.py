from sentence_transformers import SentenceTransformer
import numpy as np
from app.modules.vector_store import load_index
from app.modules.indexing import metadata

model = SentenceTransformer('all-MiniLM-L6-v2')

def retrieve(query, k=5):
    index = load_index()
    q_emb = model.encode([query])
    D, I = index.search(np.array(q_emb), k)
    return [metadata[i] for i in I[0]]

def query_rag(payload):
    context = retrieve(payload["question"])
    return {"answer": str(context[:2])}
