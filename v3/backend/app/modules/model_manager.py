"""
Model Manager
Handles local & cloud models for Brain Teaser
"""

import os
import time
import threading
from datetime import datetime, UTC
from typing import Any, Dict, List, Optional
from ..core.config_loader import get_default_model_profile, get_model_config, get_model_profiles_config, get_task_model
from ..core.debug_logger import dlog, derror
from .db import get_connection

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
        "n_ctx": 2048,
    },
    "mistral-7b": {
        "type": "local",
        "description": "Mistral 7B Instruct (CPU)",
        "path": "models/mistral-7b-instruct-v0.2.Q4_K_M.gguf",
        "max_tokens": 400,
        "temperature": 0.3,
        "n_ctx": 4096,
    },
    "qwen2.5-7b": {
        "type": "local",
        "description": "Qwen 2.5 7B Instruct (CPU)",
        "path": "models/Qwen2.5-7B-Instruct-Q4_K_M.gguf",
        "max_tokens": 450,
        "temperature": 0.25,
        "n_ctx": 4096,
    },
    "phi-4": {
        "type": "local",
        "description": "Phi-4 Instruct (CPU)",
        "path": "models/phi-4-Q4_K_M.gguf",
        "max_tokens": 450,
        "temperature": 0.2,
        "n_ctx": 4096,
    },
    "meta-llama-3-8b": {
        "type": "local",
        "description": "Meta Llama 3 8B Instruct (CPU)",
        "path": "models/Meta-Llama-3-8B-Instruct-Q4_K_M.gguf",
        "max_tokens": 450,
        "temperature": 0.2,
        "n_ctx": 4096,
    },
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
    return LOCAL_MODELS.get("qwen2.5-7b", LOCAL_MODELS["mistral-7b"])


def select_model(model_name: str) -> Dict:
    return list_models().get(model_name, get_default_model())


DEFAULT_MODEL_PROFILES: Dict[str, Dict[str, Any]] = {
    "balanced": {
        "label": "Balanced",
        "description": "Recommended mix of quality and speed for day-to-day use.",
        "task_models": {
            "qa": "qwen2.5-7b",
            "lesson": "qwen2.5-7b",
            "quiz": "phi-4",
            "flashcards": "qwen2.5-7b",
            "summary": "mistral-7b",
        },
    },
    "best-quality": {
        "label": "Best quality",
        "description": "Use stronger reasoning and explanation models whenever possible.",
        "task_models": {
            "qa": "meta-llama-3-8b",
            "lesson": "meta-llama-3-8b",
            "quiz": "phi-4",
            "flashcards": "qwen2.5-7b",
            "summary": "mistral-7b",
        },
    },
    "fastest": {
        "label": "Fastest",
        "description": "Favor the lowest-latency local responses for all users.",
        "task_models": {
            "qa": "tinyllama-1.1b-chat",
            "lesson": "mistral-7b",
            "quiz": "tinyllama-1.1b-chat",
            "flashcards": "tinyllama-1.1b-chat",
            "summary": "tinyllama-1.1b-chat",
        },
    },
    "single-model": {
        "label": "Single-model simplicity",
        "description": "Keep behavior consistent by using one main model for almost every task.",
        "task_models": {
            "qa": "qwen2.5-7b",
            "lesson": "qwen2.5-7b",
            "quiz": "qwen2.5-7b",
            "flashcards": "qwen2.5-7b",
            "summary": "mistral-7b",
        },
    },
    "safe-fallback": {
        "label": "Safe fallback",
        "description": "Use the most proven local model path for stable behavior.",
        "task_models": {
            "qa": "mistral-7b",
            "lesson": "mistral-7b",
            "quiz": "mistral-7b",
            "flashcards": "mistral-7b",
            "summary": "mistral-7b",
        },
    },
}

_MODEL_PROFILE_CACHE = {"key": None, "ts": 0.0}
_MODEL_PROFILE_CACHE_TTL = 5.0


def _get_model_profiles_map() -> Dict[str, Dict[str, Any]]:
    configured_profiles = get_model_profiles_config()
    if isinstance(configured_profiles, dict) and configured_profiles:
        return configured_profiles
    return DEFAULT_MODEL_PROFILES


def list_model_profile_keys() -> List[str]:
    return list(_get_model_profiles_map().keys())


def get_model_profiles() -> List[Dict[str, Any]]:
    profiles: List[Dict[str, Any]] = []
    for key, entry in _get_model_profiles_map().items():
        item = entry if isinstance(entry, dict) else {}
        profiles.append(
            {
                "key": key,
                "label": str(item.get("label") or key.replace("-", " ").title()),
                "description": str(item.get("description") or ""),
                "task_models": item.get("task_models") or {},
            }
        )
    return profiles


def normalize_model_profile_key(profile_key: Optional[str]) -> str:
    profiles = _get_model_profiles_map()
    requested = str(profile_key or "").strip().lower()
    if requested in profiles:
        return requested

    configured_default = str(get_default_model_profile("balanced") or "balanced").strip().lower()
    if configured_default in profiles:
        return configured_default

    return next(iter(profiles.keys()), "balanced")


def _read_app_setting(setting_key: str) -> Optional[str]:
    try:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT setting_value FROM app_settings WHERE setting_key=? LIMIT 1",
                (setting_key,),
            )
            row = cursor.fetchone()
        finally:
            conn.close()
    except Exception:
        return None

    return str(row[0]).strip() if row and row[0] is not None else None


def get_active_model_profile_key(force_refresh: bool = False) -> str:
    now = time.time()
    cached_key = _MODEL_PROFILE_CACHE.get("key")
    cached_ts = float(_MODEL_PROFILE_CACHE.get("ts") or 0.0)
    if not force_refresh and cached_key and (now - cached_ts) < _MODEL_PROFILE_CACHE_TTL:
        return str(cached_key)

    raw_value = _read_app_setting("active_model_profile") or os.getenv("MODEL_PROFILE") or get_default_model_profile("balanced")
    normalized = normalize_model_profile_key(raw_value)
    _MODEL_PROFILE_CACHE["key"] = normalized
    _MODEL_PROFILE_CACHE["ts"] = now
    return normalized


def set_active_model_profile_key(profile_key: str, updated_by: str = "admin") -> Dict[str, Any]:
    normalized = normalize_model_profile_key(profile_key)
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS app_settings (
                setting_key TEXT PRIMARY KEY,
                setting_value TEXT NOT NULL,
                updated_by TEXT DEFAULT 'system',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            """
            INSERT INTO app_settings (setting_key, setting_value, updated_by, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(setting_key) DO UPDATE SET
                setting_value=excluded.setting_value,
                updated_by=excluded.updated_by,
                updated_at=excluded.updated_at
            """,
            ("active_model_profile", normalized, updated_by, datetime.now(UTC).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()

    _MODEL_PROFILE_CACHE["key"] = normalized
    _MODEL_PROFILE_CACHE["ts"] = time.time()
    return {
        "active_profile": normalized,
        "profile": next((item for item in get_model_profiles() if item.get("key") == normalized), None),
    }


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
    normalized_task = str(task or "qa").strip().lower() or "qa"

    if normalized_task in {"qa", "lesson"}:
        return f"""
You are an AI tutor helping a student based ONLY on the provided study material.

STRICT RULES (MUST FOLLOW):
1. Answer ONLY from the provided context.
2. Do NOT use outside knowledge or guess.
3. If the answer is not present in the context, say EXACTLY:
   "I don't have enough information in the provided material."
4. Explain step-by-step like a teacher, using short examples from the context when available.
5. Keep the answer clear, grounded, and student-friendly.
6. When helpful, cite the section used, for example `(Chunk 2)`.

{context}

Question:
{query}

Answer:
"""

    if normalized_task == "summary":
        return f"""
You are summarizing ONLY the provided study material.

STRICT RULES (MUST FOLLOW):
1. Cover all key topics that appear in the context.
2. Be concise and well-organized.
3. Do NOT add outside facts.
4. If the context is insufficient, say EXACTLY:
   "I don't have enough information in the provided material."

{context}

Request:
{query}

Summary:
"""

    if normalized_task == "quiz":
        return f"""
You are generating quiz content ONLY from the provided study material.

STRICT RULES (MUST FOLLOW):
1. No ambiguous questions.
2. Every answer must match the provided context exactly.
3. Do NOT invent facts outside the context.
4. If the context is insufficient, return the safest possible grounded output.

{context}

Instructions:
{query}

Quiz Output:
"""

    return f"{history}\nContext:\n{context}\nQuestion:\n{query}\nAnswer:"



def is_model_available(model_name: str) -> bool:
    if not model_name:
        return False

    model_config = get_model_config(model_name) or list_models().get(model_name, {})
    if not model_config:
        return False

    if model_config.get("type") != "local":
        return True

    try:
        _resolve_model_path(model_config)
        return True
    except Exception:
        return False


def _task_fallback_candidates(task: str) -> List[str]:
    normalized_task = str(task or "qa").strip().lower() or "qa"
    fallback_by_task = {
        "qa": ["qwen2.5-7b", "mistral-7b", "meta-llama-3-8b", "tinyllama-1.1b-chat"],
        "lesson": ["qwen2.5-7b", "meta-llama-3-8b", "mistral-7b", "tinyllama-1.1b-chat"],
        "quiz": ["phi-4", "mistral-7b", "qwen2.5-7b", "tinyllama-1.1b-chat"],
        "flashcards": ["qwen2.5-7b", "mistral-7b", "tinyllama-1.1b-chat"],
        "summary": ["mistral-7b", "qwen2.5-7b", "tinyllama-1.1b-chat"],
    }
    return fallback_by_task.get(normalized_task, fallback_by_task["qa"])


def _pick_available_model(candidates: List[str]) -> str:
    seen = set()
    for candidate in [str(item or "").strip() for item in candidates if str(item or "").strip()]:
        if candidate in seen:
            continue
        seen.add(candidate)
        if is_model_available(candidate):
            return candidate
    return "mistral-7b"


def resolve_model_name(model_name: Optional[str], task: str, query: str, context: str = "") -> str:
    normalized_task = str(task or "qa").strip().lower() or "qa"
    if model_name:
        requested = str(model_name).strip()
        selected = _pick_available_model([requested, *_task_fallback_candidates(normalized_task), get_task_model(normalized_task)])
        if selected != requested:
            dlog("MODEL", "Requested model unavailable; using fallback", requested=requested, selected=selected, task=normalized_task)
        return selected
    return decide_model(normalized_task, query, context)


def decide_model(task: str, query: str, context: str = "") -> str:
    """Choose the model according to the active global admin-selected profile."""
    normalized_task = str(task or "qa").strip().lower() or "qa"
    query_length = len(str(query or "").split())
    context_length = len(str(context or ""))

    active_profile = get_active_model_profile_key()
    profile_config = _get_model_profiles_map().get(active_profile, DEFAULT_MODEL_PROFILES["balanced"])
    task_models = profile_config.get("task_models") or {}
    preferred_model = str(task_models.get(normalized_task) or get_task_model(normalized_task)).strip()

    if normalized_task == "qa" and active_profile == "fastest" and query_length <= 6 and context_length < 600:
        preferred_model = "tinyllama-1.1b-chat"

    selected_model = _pick_available_model(
        [preferred_model, *_task_fallback_candidates(normalized_task), get_task_model(normalized_task), get_task_model("qa")]
    )

    dlog(
        "MODEL",
        "Selected model profile",
        profile=active_profile,
        task=normalized_task,
        preferred=preferred_model,
        selected=selected_model,
        query_words=query_length,
        context_chars=context_length,
    )
    return selected_model
    
# -------------------------
# Unified Response Generator
# -------------------------
def _safe_generation_fallback(task: str = "qa") -> str:
    normalized_task = str(task or "qa").strip().lower() or "qa"
    if normalized_task == "quiz":
        return '{"questions":[{"question":"Practice question 1","options":["A","B","C","D"],"correct_answer":"A","explanation":"A safe fallback response was returned because generation was temporarily unavailable."}]}'
    if normalized_task == "summary":
        return "I couldn't generate a grounded summary right now. Please try again."
    return "I couldn't generate a response right now. Please try again."


def generate_response(context: str, query: str, history: str = "", model_name: str = None, task: str = "qa") -> str:

    model_name = resolve_model_name(model_name, task, query, context)

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
        try:
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
        except Exception as exc:
            derror("MODEL", f"Local generation failed: {exc}", model=model_name, task=task)
            return _safe_generation_fallback(task)

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
            try:
                response = openai.chat.completions.create(
                    model=model_config["model_name"],
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=model_config.get("max_tokens", 500),
                    temperature=model_config.get("temperature", 0.7),
                    timeout=float(os.getenv("OPENAI_TIMEOUT_SECONDS", "60")),
                )
                elapsed = (time.perf_counter() - t0) * 1000
                result = response.choices[0].message.content.strip()
                dlog("MODEL", "Cloud model response",
                     model=model_config["model_name"],
                     elapsed_ms=f"{elapsed:.1f}ms",
                     response_chars=len(result),
                     response_preview=result[:100])
                return result
            except Exception as exc:
                derror("MODEL", f"Cloud generation failed: {exc}", model=model_config["model_name"], task=task)
                return _safe_generation_fallback(task)

    raise ValueError("Unsupported model")


# -------------------------
# Streaming Response
# -------------------------
def generate_response_stream(context: str, query: str, history: str = "", model_name: str = None, task="qa"):

    model_name = resolve_model_name(model_name, task, query, context)

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
            yield _safe_generation_fallback(task)

    elif model_config["type"] == "cloud":
        # Keep stream contract by chunking the cloud fallback response.
        cloud_text = generate_response(context, query, history, model_name, task)
        for token in cloud_text.split():
            yield token + " "
        if cloud_text and not cloud_text.endswith((" ", "\n")):
            yield "\n"

    else:
        raise ValueError(f"Unsupported model type: {model_config.get('type')}")