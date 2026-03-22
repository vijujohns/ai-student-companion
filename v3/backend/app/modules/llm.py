"""
Local LLM wrapper using llama.cpp (CPU only)
"""

from llama_cpp import Llama
import os

# Load model once (singleton)
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
MODEL_PATH = os.path.join(BASE_DIR, "backend", "models", "tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf")

llm = Llama(
    model_path=MODEL_PATH,
    n_ctx=2048,
    n_threads=4,   # adjust based on CPU
    verbose=False
)


def generate_response(context: str, query: str, history: str = "") -> str:
    """
    Generate answer using context + query
    """

    prompt = f"""
You are an intelligent AI tutor.

Conversation so far:
{history}

Use the context below to answer the question clearly and concisely.

Context:
{context}

Question:
{query}

Answer:
"""

    output = llm(
        prompt,
        max_tokens=300,
        temperature=0.7,
        stop=["</s>"]
    )

    return output["choices"][0]["text"].strip()