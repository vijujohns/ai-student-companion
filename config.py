import os

ROOT_FOLDER = r"D:\CBSE_AI_TUTOR"
VECTOR_FOLDER = "vector_store"

INDEX_FILE = os.path.join(VECTOR_FOLDER, "faiss.index")
META_FILE = os.path.join(VECTOR_FOLDER, "metadata.pkl")
PROGRESS_DB = os.path.join(VECTOR_FOLDER, "study_progress.db")

EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
LLM_MODEL = "mistral"