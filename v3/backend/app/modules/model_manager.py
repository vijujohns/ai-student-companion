"""
Model Manager
Handles local & cloud models for Brain Teaser
"""

import os
import time
import threading
from typing import Dict
from ..core.config_loader import get_task_model, get_model_config
from ..core.debug_logger import dlog, derror

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
        "path": "models/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf",
        "max_tokens": 512,
        "temperature": 0.7,
        "n_ctx": 2048
    },
    "mistral-7b": {
        "type": "local",
        "description": "Mistral 7B Instruct (CPU)",
        "path": "models/mistral-7b-instruct-v0.2.Q4_K_M.gguf",
        "max_tokens": 400,
        "temperature": 0.3,
        "n_ctx": 4096
    }
}

# -------------------------
# Cloud Models
# -------------------------
CLOUD_MODELS = {
    "gpt-3.5-turbo": {
        "type": "cloud",
        "provider": "openai",
        "model_name": "gpt-3.5-turbo",
        "max_tokens": 500,
        "temperature": 0.7
    }
}

# -------------------------
# Model Registry Functions
# -------------------------
def list_models() -> Dict:
    models = {}
    models.update(LOCAL_MODELS)
    models.update(CLOUD_MODELS)
    return models


def get_default_model() -> Dict:
    return LOCAL_MODELS["mistral-7b"]


def select_model(model_name: str) -> Dict:
    return list_models().get(model_name, get_default_model())



# -------------------------
# LLM CACHE (🔥 KEY IMPROVEMENT)
# -------------------------
_llm_cache = {}
_llm_locks = {}
_llm_cache_guard = threading.Lock()


def _resolve_model_path(model_config):
    raw_path = str(model_config.get("path", "")).strip()
    if not raw_path:
        raise ValueError("Model configuration is missing 'path'")

    # Accept both absolute paths and relative paths from config.
    if os.path.isabs(raw_path):
        model_path = raw_path
    else:
        normalized = raw_path.replace("\\", "/")
        # Keep backward compatibility for paths already prefixed with backend/.
        if normalized.startswith("backend/"):
            normalized = normalized[len("backend/"):]
        model_path = os.path.join(BASE_DIR, "backend", normalized)

    model_path = os.path.abspath(model_path)

    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model path does not exist: {model_path}")

    return model_path


def _get_llm_lock(model_path):
    with _llm_cache_guard:
        lock = _llm_locks.get(model_path)
        if lock is None:
            lock = threading.RLock()
            _llm_locks[model_path] = lock
        return lock


def get_llm_instance(model_config):
    model_path = _resolve_model_path(model_config)
    lock = _get_llm_lock(model_path)

    with lock:
        if model_path not in _llm_cache:
            from llama_cpp import Llama
            dlog("MODEL", "Loading LLM into memory (first use)",
                 model_path=model_path,
                 n_ctx=model_config.get("n_ctx", 2048),
                 n_threads=6, n_batch=256)
            print(f"🚀 Loading model: {model_path}")
            llm = Llama(
                model_path=model_path,
                n_ctx=model_config.get("n_ctx", 2048),
                n_threads=6,
                n_batch=256,
                verbose=False
            )
            with _llm_cache_guard:
                _llm_cache[model_path] = llm
            dlog("MODEL", "LLM loaded and cached", model_path=model_path)
        else:
            dlog("MODEL", "LLM instance retrieved from cache", model_path=model_path)

        return _llm_cache[model_path]


# -------------------------
# Prompt Builder
# -------------------------
def build_prompt(context, query, history, task):
    if task == "qa":
        return f"""
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
    else:
        return f"{history}\nContext:\n{context}\nQuestion:\n{query}\nAnswer:"



def decide_model(task: str, query: str, context: str = "") -> str:
    """
    Smart model selection based on task + query complexity
    """

    query_length = len(query.split())
    context_length = len(context)

    # 🔹 Simple / fast tasks → TinyLLaMA
    if task in ["summary"] and context_length < 2000:
        return "tinyllama-1.1b-chat"

    # 🔹 Flashcards / quiz → TinyLLaMA (fast; context is pre-reduced before calling)
    if task in ["flashcards", "quiz"]:
        return "tinyllama-1.1b-chat"

    # 🔹 Short QA → Tiny model (fast)
    if task == "qa" and query_length < 8 and context_length < 400:
        return "tinyllama-1.1b-chat"

    # 🔹 Long context QA → Mistral
    if context_length > 400:
            return "mistral-7b"
 
    # 🔹 Future: very complex → cloud
    if query_length > 20:
        #return "gpt-3.5-turbo"
        return "mistral-7b"

    # 🔹 Default fallback
    return get_task_model(task)
    
# -------------------------
# Unified Response Generator
# -------------------------
def generate_response(context: str, query: str, history: str = "", model_name: str = None, task: str = "qa") -> str:

    if not model_name:
        model_name = decide_model(task, query, context)

    print(f"🧠 Model Selected: {model_name} | Task: {task}")

    model_config = get_model_config(model_name)
    if not model_config:
        raise ValueError(f"Unknown model configuration: {model_name}")
    prompt = build_prompt(context, query, history, task)

    dlog("MODEL", "generate_response",
         model=model_name,
         task=task,
         model_type=model_config.get("type", "?"),
         max_tokens=model_config.get("max_tokens"),
         temperature=model_config.get("temperature"),
         n_ctx=model_config.get("n_ctx"),
         context_chars=len(context),
         history_chars=len(history),
         prompt_chars=len(prompt),
         prompt_preview=prompt[:200].replace("\n", " "))

    # -------- LOCAL --------
    if model_config["type"] == "local":
        model_path = _resolve_model_path(model_config)
        lock = _get_llm_lock(model_path)
        llm = get_llm_instance(model_config)
        t0 = time.perf_counter()
        with lock:
            output = llm(
                prompt,
                max_tokens=model_config.get("max_tokens", 300),
                temperature=model_config.get("temperature", 0.7),
                stop=["Question:", "---------------------", "</s>"]
            )
        elapsed = (time.perf_counter() - t0) * 1000
        result = output["choices"][0]["text"].strip()
        dlog("MODEL", "Local model response",
             model=model_name,
             elapsed_ms=f"{elapsed:.1f}ms",
             response_chars=len(result),
             response_preview=result[:100])
        return result

    # -------- CLOUD --------
    elif model_config["type"] == "cloud":
        if model_config["provider"] == "openai":
            if not openai:
                raise ImportError("openai package not installed")

            openai.api_key = os.getenv("OPENAI_API_KEY")
            dlog("MODEL", "Calling OpenAI cloud model",
                 model=model_config["model_name"],
                 max_tokens=model_config.get("max_tokens", 500),
                 temperature=model_config.get("temperature", 0.7))
            t0 = time.perf_counter()
            response = openai.chat.completions.create(
                model=model_config["model_name"],
                messages=[{"role": "user", "content": prompt}],
                max_tokens=model_config.get("max_tokens", 500),
                temperature=model_config.get("temperature", 0.7)
            )
            elapsed = (time.perf_counter() - t0) * 1000
            result = response.choices[0].message.content.strip()
            dlog("MODEL", "Cloud model response",
                 model=model_config["model_name"],
                 elapsed_ms=f"{elapsed:.1f}ms",
                 response_chars=len(result),
                 response_preview=result[:100])
            return result

    raise ValueError("Unsupported model")


# -------------------------
# Streaming Response
# -------------------------
def generate_response_stream(context: str, query: str, history: str = "", model_name: str = None, task="qa"):

    if not model_name:
        model_name = decide_model(task, query, context)

    print(f"🧠 Model Selected: {model_name} | Task: {task}")

    model_config = get_model_config(model_name)
    if not model_config:
        raise ValueError(f"Unknown model configuration: {model_name}")
    prompt = build_prompt(context, query, history, task)

    dlog("MODEL", "generate_response_stream",
         model=model_name,
         task=task,
         model_type=model_config.get("type", "?"),
         max_tokens=model_config.get("max_tokens"),
         temperature=model_config.get("temperature"),
         context_chars=len(context),
         prompt_chars=len(prompt),
         prompt_preview=prompt[:200].replace("\n", " "))

    if model_config["type"] == "local":
        model_path = _resolve_model_path(model_config)
        lock = _get_llm_lock(model_path)
        llm = get_llm_instance(model_config)

        try:
            t0 = time.perf_counter()
            token_count = 0
            with lock:
                stream = llm(
                    prompt,
                    max_tokens=model_config.get("max_tokens", 300),
                    temperature=model_config.get("temperature", 0.7),
                    stop=["Question:", "---------------------", "</s>"],
                    stream=True
                )

                for chunk in stream:
                    token = chunk["choices"][0].get("text", "")
                    if token:
                        token_count += 1
                        yield token

            elapsed = (time.perf_counter() - t0) * 1000
            dlog("MODEL", "Stream complete",
                 model=model_name,
                 tokens_yielded=token_count,
                 elapsed_ms=f"{elapsed:.1f}ms")

        except Exception as e:
            derror("MODEL", f"Streaming error: {e}", model=model_name)
            yield f"\n[ERROR: {str(e)}]\n"

    elif model_config["type"] == "cloud":
        # Keep stream contract by chunking the cloud fallback response.
        cloud_text = generate_response(context, query, history, model_name, task)
        for token in cloud_text.split():
            yield token + " "
        if cloud_text and not cloud_text.endswith((" ", "\n")):
            yield "\n"

    else:
        raise ValueError(f"Unsupported model type: {model_config.get('type')}")