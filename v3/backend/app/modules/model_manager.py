"""
Model Manager
Handles local & cloud models for AI Student Tutor

- Supports local LLaMA models
- Supports cloud models (OpenAI GPT-4 and Azure OpenAI GPT-4)
- Provides a unified `generate_response` function
"""

import os
from typing import Dict

# Optional imports for cloud models
try:
    import openai
except ImportError:
    openai = None

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))

# -------------------------
# Local Models
# -------------------------
LOCAL_MODELS = {
    "tinyllama-1.1b-chat": {
        "type": "local",
        "description": "TinyLLaMA 1.1B Chat (CPU)",
        "path": os.path.join(BASE_DIR, "backend/models/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf"),
        "max_tokens": 300,
        "temperature": 0.7,
        "n_ctx": 2048
    },
    "mistral-7b": {
        "type": "local",
        "description": "Mistral 7B Instruct (CPU)",
        "path": os.path.join(BASE_DIR, "backend/models/mistral-7b-instruct-v0.2.Q4_K_M.gguf"),
        "max_tokens": 400,
        "temperature": 0.3,
        "n_ctx": 4096
    }
}

# -------------------------
# Cloud Models (static for now)
# -------------------------
CLOUD_MODELS = {
    "gpt-3.5-turbo": {
        "type": "cloud",
        "description": "OpenAI GPT-4",
        "provider": "openai",
        "model_name": "gpt-3.5-turbo",
        "max_tokens": 500,
        "temperature": 0.7
    },
    "azure-gpt-4": {
        "type": "cloud",
        "description": "Azure OpenAI GPT-4",
        "provider": "azure",
        "model_name": "gpt-4",
        "max_tokens": 500,
        "temperature": 0.7,
        "endpoint": "https://my-azure-openai.openai.azure.com/"
    }
}

# -------------------------
# Model Registry Functions
# -------------------------
def list_models() -> Dict:
    """Return all available models (local + cloud)"""
    models = {}
    models.update(LOCAL_MODELS)
    models.update(CLOUD_MODELS)
    return models


def get_default_model() -> Dict:
    """Return default model config (TinyLLaMA local)"""
    return LOCAL_MODELS["mistral-7b"]


def select_model(model_name: str) -> Dict:
    """Return model config by name or default"""
    return list_models().get(model_name, get_default_model())


# -------------------------
# Unified Response Generator
# -------------------------
def generate_response(context: str, query: str, history: str = "", model_name: str = None) -> str:
    """
    Generate an answer using the selected model.
    Supports both local LLMs (mistral-7b/TinyLLaMA) and cloud LLMs (OpenAI / Azure).

    Args:
        context (str): The retrieved context from RAG or knowledge base
        query (str): User question
        history (str): Optional conversation history
        model_name (str): Optional model selection, defaults to mistral-7b

    Returns:
        str: Generated answer
    """
    model_config = select_model(model_name) if model_name else get_default_model()

    # ---------------- Local LLaMA ----------------
    if model_config["type"] == "local":
        from llama_cpp import Llama

        llm = Llama(
            model_path=model_config["path"],
            n_ctx=model_config.get("n_ctx", 2048),
            n_threads=4,
            verbose=False
        )

        prompt = f"""
You are an AI tutor helping a student based ONLY on the provided study material.

STRICT RULES (MUST FOLLOW):
1. Answer ONLY using the provided context.
2. Do NOT use outside knowledge if context exists.
3. If the answer is NOT clearly available in the context:
   Say EXACTLY:
   "I could not find this in the provided study material."
   Do NOT attempt to guess or generate an answer.

4. Do NOT generate extra questions.
5. Do NOT continue conversation.
6. Give only ONE clear answer.

FORMAT:
- Keep answer simple and student-friendly.
- Use short paragraphs or bullet points if helpful.

---------------------
Context:
{context}

---------------------
Question:
{query}

---------------------
Answer:
"""
        output = llm(
            prompt,
            max_tokens=model_config.get("max_tokens", 300),
            temperature=model_config.get("temperature", 0.7),
            stop=["Question:", "---------------------", "</s>"]
        )
        return output["choices"][0]["text"].strip()

    # ---------------- Cloud Models ----------------
    elif model_config["type"] == "cloud":
        provider = model_config["provider"]

        # ----- OpenAI GPT-4 -----
        if provider == "openai":
            global openai
            if not openai:
                raise ImportError("openai package not installed")
            import os
            openai.api_key = os.getenv("OPENAI_API_KEY")

            messages = [
                {"role": "user", "content": f"{history}\nContext:\n{context}\nQuestion:\n{query}"}
            ]

            # ✅ Updated for openai>=1.0.0
            response = openai.chat.completions.create(
                model=model_config["model_name"],
                messages=messages,
                max_tokens=model_config.get("max_tokens", 500),
                temperature=model_config.get("temperature", 0.7)
            )
            return response.choices[0].message["content"].strip()

        # ----- Azure GPT-4 -----
        elif provider == "azure":
            import os
            import openai
            openai.api_key = os.getenv("AZURE_API_KEY")
            openai.api_base = model_config["endpoint"]
            openai.api_type = "azure"
            openai.api_version = "2023-03-15-preview"

            messages = [
                {"role": "user", "content": f"{history}\nContext:\n{context}\nQuestion:\n{query}"}
            ]

            response = openai.chat.completions.create(
                engine=model_config["model_name"],  # Azure engine name
                messages=messages,
                max_tokens=model_config.get("max_tokens", 500),
                temperature=model_config.get("temperature", 0.7)
            )
            return response.choices[0].message["content"].strip()

        else:
            raise ValueError(f"Unsupported cloud provider: {provider}")

    else:
        raise ValueError(f"Unsupported model type: {model_config['type']}")


def generate_response_stream(context: str, query: str, history: str = "", model_name: str = None):
    model_config = select_model(model_name) if model_name else get_default_model()

    # ---------------- Local LLaMA Streaming ----------------
    if model_config["type"] == "local":
        from llama_cpp import Llama

        # 🔥 IMPORTANT: reuse model (singleton pattern)
        global _llm_instance
        if "_llm_instance" not in globals():
            _llm_instance = Llama(
                model_path=model_config["path"],
                n_ctx=model_config.get("n_ctx", 2048),
                n_threads=4,
                verbose=False
            )

        llm = _llm_instance

        prompt = f"""
You are an AI tutor helping a student based ONLY on the provided study material.

STRICT RULES (MUST FOLLOW):
1. Answer ONLY using the provided context.
2. Do NOT use outside knowledge if context exists.
3. If the answer is NOT clearly available in the context:
   Say EXACTLY:
   "I could not find this in the provided study material."
   Do NOT attempt to guess or generate an answer.

4. Do NOT generate extra questions.
5. Do NOT continue conversation.
6. Give only ONE clear answer.

FORMAT:
- Keep answer simple and student-friendly.
- Use short paragraphs or bullet points if helpful.

---------------------
Context:
{context}

---------------------
Question:
{query}

---------------------
Answer:
"""

        try:
            stream = llm(
                prompt,
                max_tokens=model_config.get("max_tokens", 300),
                temperature=model_config.get("temperature", 0.7),
                stop=["Question:", "---------------------", "</s>"],
                stream=True
            )

            for chunk in stream:
                if "choices" in chunk:
                    token = chunk["choices"][0].get("text", "")
                    if token:
                        yield token

        except Exception as e:
            yield f"\n[ERROR: {str(e)}]\n"

    # ---------------- Cloud Streaming (Fallback to non-stream) ----------------
    elif model_config["type"] == "cloud":
        # ⚠️ For now fallback to full response (streaming later phase)
        response = generate_response(context, query, history, model_name)
        yield response

    else:
        yield "[ERROR: Unsupported model]"