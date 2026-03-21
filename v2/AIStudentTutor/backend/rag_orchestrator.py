from backend.faiss_store import FaissStore
from backend.embeddings import embed_text
from backend.step_by_step import solve_problem
from backend.multilingual import translate_text

class RAGOrchestrator:
    def __init__(self, faiss_store):
        self.store = faiss_store

    def query(self, question, class_name, subject, chapter, language="English", step_by_step=False):
        q_emb = embed_text([question])[0]
        idx, scores = self.store.search(q_emb)
        retrieved_texts = [f"Chunk {i}" for i in idx]  # placeholder
        answer = " ".join(retrieved_texts)

        if step_by_step and subject in ["Math", "Physics", "Chemistry"]:
            answer = solve_problem(question, retrieved_texts)

        if language != "English":
            answer = translate_text(answer, target_lang=language)

        return answer
