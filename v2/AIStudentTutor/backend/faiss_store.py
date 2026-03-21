import faiss
import numpy as np
import os

class FaissStore:
    def __init__(self, dim, index_file="data/faiss_index/index.faiss"):
        self.dim = dim
        self.index_file = index_file
        self.index = faiss.IndexFlatL2(dim)
        if os.path.exists(index_file):
            self.index = faiss.read_index(index_file)

    def add_embeddings(self, embeddings):
        self.index.add(np.array(embeddings).astype('float32'))

    def save(self):
        faiss.write_index(self.index, self.index_file)

    def search(self, query_emb, top_k=5):
        D, I = self.index.search(np.array([query_emb]).astype('float32'), top_k)
        return I, D
