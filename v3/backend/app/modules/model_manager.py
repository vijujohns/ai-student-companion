"""
Model Manager
Handles local & cloud models for Brain Teaser
"""

import os
import re
import time
import threading
from datetime import datetime, UTC
from typing import Any, Dict, List, Optional
from ..core.config_loader import get_default_model_profile, get_model_config, get_model_profiles_config, get_task_model
from .query_classifier import classify_query as shared_classify_query
from ..core.debug_logger import dlog, derror, dwarn
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
        "temperature": 0.7,
    },
    "groq-llama-fast": {
        "type": "cloud",
        "provider": "groq",
        "model_name": "llama-3.1-8b-instant",
        "max_tokens": 500,
        "temperature": 0.3,
    },
    "groq-llama-quality": {
        "type": "cloud",
        "provider": "groq",
        "model_name": "llama-3.3-70b-versatile",
        "max_tokens": 700,
        "temperature": 0.2,
    },
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
    "groq-cloud": {
        "label": "Groq cloud",
        "description": "Use Groq-hosted Llama models for cloud-based responses across all study tasks.",
        "task_models": {
            "qa": "groq-llama-fast",
            "lesson": "groq-llama-quality",
            "quiz": "groq-llama-fast",
            "flashcards": "groq-llama-fast",
            "summary": "groq-llama-quality",
            "assessment": "groq-llama-fast",
            "math": "groq-llama-quality",
            "translation": "groq-llama-fast",
            "explorer": "groq-llama-fast",
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
def detect_question_type(query: str) -> str:
    return shared_classify_query(query)


def detect_mode(query: str, question_type: Optional[str] = None) -> str:
    normalized = " ".join(str(query or "").strip().lower().split())
    resolved_question_type = str(question_type or detect_question_type(query)).strip().lower() or "general"
    if resolved_question_type in {"fact", "quote", "summary_structured"}:
        return "direct"

    if any(phrase in normalized for phrase in ("just answer", "direct answer", "give me the answer", "final answer")):
        return "direct"
    if any(phrase in normalized for phrase in ("solve", "step by step", "help me", "teach me")):
        return "guided"
    return "direct"


def _qa_prompt_style_rules(question_type: str, mode: str) -> str:
    normalized_type = str(question_type or "general").strip().lower() or "general"
    normalized_mode = str(mode or "direct").strip().lower() or "direct"

    if normalized_mode == "guided" and normalized_type not in {"fact", "quote"}:
        return """
GUIDED TUTOR MODE (MANDATORY):
- Explain step-by-step like a teacher.
- Do NOT give the full answer immediately.
- Break the problem into 3-5 short steps max.
- Ask one small question at each step.
- Give hints before giving the final answer.
- Encourage reasoning.
- End with: 'Now you try a similar problem!'

Use this structure:
Step 1:
- Briefly explain the first move
- Ask a small question

Step 2:
- Build on the previous step
- Ask the next question

Final Step:
- Reveal the full solution clearly
"""

    if normalized_type == "quote":
        return """
QUOTE QUESTION STYLE (MANDATORY):
- Return the exact line or sentence from the context when available.
- Keep the answer to 1-3 lines.
- Do NOT paraphrase unless the quote is incomplete.
- If the exact wording is not clearly present, say exactly: 'This is not clearly mentioned in the provided material.'
"""

    if normalized_type == "fact":
        return """
FACT QUESTION STYLE (MANDATORY):
- Answer in 1-3 lines only.
- Give the direct answer first.
- Quote the exact sentence from the context if available.
- Do NOT add Key Points, Summary, or long explanations.
"""

    if normalized_type == "definition":
        return """
DEFINITION STYLE (MANDATORY):
- Give a short explanation in 2-4 lines.
- Keep it simple and clear.
- Use your own words.
- Add one small example only if it helps.
"""

    if normalized_type == "list":
        return """
LIST QUESTION STYLE (MANDATORY):
- Answer as 4-6 concise bullet points.
- Keep each bullet to one short complete line.
- If useful, use `Term: short explanation` format, for example `Frequency: number of vibrations per second`.
- Do NOT return broken fragments or continuation bullets.
- Include only the most important characteristics, parts, or types.
- Do NOT add unrelated examples unless asked.
- Avoid long paragraphs.
"""

    if normalized_type in {"explanation", "math"}:
        return """
EXPLANATION STYLE (MANDATORY):
- Explain step-by-step like a teacher.
- Use your own words for explanations.
- Use this structure:
  Title
  Simple Explanation (2-4 lines)
  Key Points:
  - bullet points
  Example:
  - practical example if available
  Summary:
  - 1-2 lines
"""

    return """
GENERAL STYLE:
- Give a short, clean, readable answer.
- Use bullets only when they improve clarity.
- Avoid repetition or unrelated details.
"""


def build_structured_summary_prompt(context, query, history, *, has_context: bool = True) -> tuple[str, str]:
    if has_context:
        system_prompt = """
You are an AI Tutor preparing structured revision notes.

STRUCTURED SUMMARY MODE (MANDATORY):
- Use ONLY the provided context.
- Produce clean textbook-style notes, not one long paragraph.
- Start with: `## 📘 <Topic Title>`.
- Then include these sections in order:
  `### Overview`
  `### Key Points`
  `### Section Notes` (use short subheadings when helpful)
  `### Final Takeaways`
- Use a markdown table only if the context contains comparable items.
- Keep the overview to 2-3 short lines.
- Keep bullets concise and revision-friendly.
- Do NOT mention chunk numbers, provided material, or OCR noise.
""".strip()
        user_prompt = f"""
Recent conversation:
{history}

Create a structured revision summary for the topic below using ONLY the provided context.

Context:
{context}

Question:
{query}

Structured Summary:
""".strip()
        return system_prompt, user_prompt

    system_prompt = """
You are an AI Tutor preparing structured revision notes.

STRUCTURED SUMMARY MODE (MANDATORY):
- Answer using reliable general knowledge.
- Produce clean textbook-style notes, not one long paragraph.
- Start with: `## 📘 <Topic Title>`.
- Then include these sections in order:
  `### Overview`
  `### Key Points`
  `### Section Notes` (use short subheadings when helpful)
  `### Final Takeaways`
- Use a markdown table only if the topic naturally compares multiple items.
- Keep the overview to 2-3 short lines.
- Keep bullets concise and revision-friendly.
- Do NOT mention missing context, provided material, or chunk numbers.
""".strip()
    user_prompt = f"""
Recent conversation:
{history}

Create structured revision notes for:
{query}

Structured Summary:
""".strip()
    return system_prompt, user_prompt


def _build_prompt_parts(context, query, history, task, question_type: Optional[str] = None, mode: Optional[str] = None) -> tuple[str, str]:
    normalized_task = str(task or "qa").strip().lower() or "qa"
    has_context = bool(str(context or "").strip())
    resolved_question_type = str(question_type or detect_question_type(query)).strip().lower() or "general"
    resolved_mode = str(mode or detect_mode(query, resolved_question_type)).strip().lower() or "direct"

    if resolved_question_type == "summary_structured":
        return build_structured_summary_prompt(context, query, history, has_context=has_context)

    if normalized_task in {"qa", "lesson"}:
        style_rules = _qa_prompt_style_rules(resolved_question_type, resolved_mode).strip()
        if has_context:
            system_prompt = """
You are an AI Tutor.

Rules:
- Answer ONLY from the provided context.
- Answer ONLY using the provided context.
- Do NOT hallucinate or guess.
- If the answer is not clearly present, say exactly: 'This is not clearly mentioned in the provided material.'
- Do NOT mention chunk numbers.
- Do NOT repeat content.
- Avoid irrelevant information.
- Keep answers clean and readable.
- Ignore boilerplate like Document:, Source:, Page labels, OCR fragments, or chunk headers.
- Do not copy raw chunks verbatim unless the student asks for a quote.
- Use your own words for explanations.
""".strip()
            user_prompt = f"""
Recent conversation:
{history}

Avoid:
- repetition
- long paragraphs
- irrelevant details
- mixing unrelated concepts (example: pie vs π)

{style_rules}

Use ONLY the provided context below.

{context}

Question type: {resolved_question_type}
Tutor mode: {resolved_mode}

Question:
{query}

Answer:
""".strip()
            return system_prompt, user_prompt

        system_prompt = """
You are an AI Tutor.

Rules:
- Answer clearly and helpfully using reliable general knowledge.
- Do NOT mention missing context, chunk numbers, or provided material.
- Do NOT repeat content.
- Avoid irrelevant information.
- Keep answers clean and readable.
- Use your own words for explanations.
""".strip()
        user_prompt = f"""
Recent conversation:
{history}

{style_rules}

Question type: {resolved_question_type}
Tutor mode: {resolved_mode}

Question:
{query}

Answer:
""".strip()
        return system_prompt, user_prompt

    if normalized_task == "summary":
        system_prompt = """
You are summarizing ONLY the provided study material.

STRICT RULES (MUST FOLLOW):
1. Cover all key topics that appear in the context.
2. Be concise and well-organized.
3. Do NOT add outside facts.
4. If the context is insufficient, say EXACTLY:
   "I don't have enough information in the provided material."
""".strip()
        user_prompt = f"""
{context}

Request:
{query}

Summary:
""".strip()
        return system_prompt, user_prompt

    if normalized_task == "quiz":
        system_prompt = """
You are generating quiz content ONLY from the provided study material.

STRICT RULES (MUST FOLLOW):
1. No ambiguous questions.
2. Every answer must match the provided context exactly.
3. Do NOT invent facts outside the context.
4. If the context is insufficient, return the safest possible grounded output.
""".strip()
        user_prompt = f"""
{context}

Instructions:
{query}

Quiz Output:
""".strip()
        return system_prompt, user_prompt

    return "You are a helpful assistant.", f"{history}\nContext:\n{context}\nQuestion:\n{query}\nAnswer:"


def build_prompt(context, query, history, task, question_type: Optional[str] = None, mode: Optional[str] = None):
    system_prompt, user_prompt = _build_prompt_parts(context, query, history, task, question_type=question_type, mode=mode)
    return f"{system_prompt}\n\n{user_prompt}".strip()


def _resolve_generation_params(model_config: Dict[str, Any], query: str, task: str) -> tuple[float, int, str]:
    normalized_task = str(task or "qa").strip().lower() or "qa"
    question_type = detect_question_type(query)
    base_temperature = float(model_config.get("temperature", 0.3) or 0.3)
    base_max_tokens = int(model_config.get("max_tokens", 300) or 300)

    if question_type == "summary_structured":
        return min(base_temperature, 0.15), 600, question_type

    if normalized_task not in {"qa", "lesson", "math"}:
        return base_temperature, base_max_tokens, question_type

    if question_type in {"fact", "quote"}:
        return min(base_temperature, 0.10), min(base_max_tokens, 120), question_type
    if question_type == "definition":
        return min(base_temperature, 0.15), min(base_max_tokens, 180), question_type
    if question_type == "list":
        return min(base_temperature, 0.15), min(max(base_max_tokens, 160), 220), question_type
    if question_type in {"explanation", "math"}:
        return min(base_temperature, 0.20), min(max(base_max_tokens, 220), 320), question_type
    return min(base_temperature, 0.20), min(base_max_tokens, 220), question_type



def _cloud_provider_env_key(provider: str) -> Optional[str]:
    normalized = str(provider or "").strip().lower()
    return {
        "openai": "OPENAI_API_KEY",
        "groq": "GROQ_API_KEY",
    }.get(normalized)


def _build_cloud_runtime_config(model_config: Dict[str, Any]) -> Dict[str, Any]:
    provider = str(model_config.get("provider") or "openai").strip().lower() or "openai"
    api_key_env = _cloud_provider_env_key(provider)
    if not api_key_env:
        raise ValueError(f"Unsupported cloud provider: {provider}")

    defaults = {
        "openai": {
            "base_url": str(os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1").strip(),
            "timeout": float(os.getenv("OPENAI_TIMEOUT_SECONDS", "60")),
        },
        "groq": {
            "base_url": str(os.getenv("GROQ_BASE_URL") or "https://api.groq.com/openai/v1").strip(),
            "timeout": float(os.getenv("GROQ_TIMEOUT_SECONDS", "60")),
        },
    }

    runtime = defaults[provider]
    api_key = str(os.getenv(api_key_env, "") or "").strip()
    return {
        "provider": provider,
        "api_key_env": api_key_env,
        "api_key": api_key,
        "base_url": runtime["base_url"],
        "timeout": runtime["timeout"],
    }


def is_model_available(model_name: str) -> bool:
    if not model_name:
        return False

    model_config = get_model_config(model_name) or list_models().get(model_name, {})
    if not model_config:
        return False

    if model_config.get("type") != "local":
        try:
            return bool(_build_cloud_runtime_config(model_config).get("api_key"))
        except Exception:
            return False

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


def _emit_selection_trace(task: str, model_name: str, model_config: Dict[str, Any], context: str, query: str) -> None:
    normalized_task = str(task or "qa").strip().lower() or "qa"
    provider = str(model_config.get("provider") or "local").strip().lower() or "local"
    context_text = str(context or "").strip()
    query_preview = str(query or "").strip().replace("\n", " ")
    if len(query_preview) > 120:
        query_preview = query_preview[:117] + "..."

    dwarn(
        "MODEL",
        "Model selected for current task",
        task=normalized_task,
        profile=get_active_model_profile_key(),
        model=model_name,
        provider=provider,
        context_mode="grounded" if context_text else "none",
        context_chars=len(context_text),
        query=query_preview or None,
    )


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
    temperature, max_tokens, question_type = _resolve_generation_params(model_config, query, task)
    system_prompt, user_prompt = _build_prompt_parts(context, query, history, task, question_type=question_type)
    prompt = build_prompt(context, query, history, task, question_type=question_type)

    dlog("MODEL", "generate_response",
         model=model_name,
         task=task,
         model_type=model_config.get("type", "?"),
         max_tokens=max_tokens,
         temperature=temperature,
         n_ctx=model_config.get("n_ctx"),
         context_chars=len(context),
         history_chars=len(history),
         prompt_chars=len(prompt),
         prompt_preview=prompt[:200].replace("\n", " "))
    _emit_selection_trace(task, model_name, model_config, context, query)

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
                    max_tokens=max_tokens,
                    temperature=temperature,
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
        provider = str(model_config.get("provider") or "").strip().lower()
        if provider in {"openai", "groq"}:
            if not openai:
                raise ImportError("openai package not installed")

            runtime = _build_cloud_runtime_config(model_config)
            if not runtime["api_key"]:
                derror(
                    "MODEL",
                    f"Cloud provider key missing: {runtime['api_key_env']}",
                    provider=provider,
                    model=model_config["model_name"],
                    task=task,
                )
                return _safe_generation_fallback(task)

            provider_label = "Groq" if provider == "groq" else "OpenAI"
            dlog(
                "MODEL",
                f"Calling {provider_label} cloud model",
                provider=provider,
                model=model_config["model_name"],
                base_url=runtime["base_url"],
                max_tokens=model_config.get("max_tokens", 500),
                temperature=model_config.get("temperature", 0.7),
            )
            t0 = time.perf_counter()
            try:
                client_factory = getattr(openai, "OpenAI", None)
                if callable(client_factory):
                    client = client_factory(api_key=runtime["api_key"], base_url=runtime["base_url"])
                    response = client.chat.completions.create(
                        model=model_config["model_name"],
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        max_tokens=max_tokens,
                        temperature=temperature,
                        timeout=runtime["timeout"],
                    )
                else:
                    openai.api_key = runtime["api_key"]
                    if hasattr(openai, "base_url"):
                        openai.base_url = runtime["base_url"]
                    response = openai.chat.completions.create(
                        model=model_config["model_name"],
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        max_tokens=max_tokens,
                        temperature=temperature,
                        timeout=runtime["timeout"],
                    )
                elapsed = (time.perf_counter() - t0) * 1000
                result = response.choices[0].message.content.strip()
                dlog("MODEL", "Cloud model response",
                     provider=provider,
                     model=model_config["model_name"],
                     elapsed_ms=f"{elapsed:.1f}ms",
                     response_chars=len(result),
                     response_preview=result[:100])
                return result
            except Exception as exc:
                derror("MODEL", f"Cloud generation failed: {exc}", provider=provider, model=model_config["model_name"], task=task)
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
    temperature, max_tokens, question_type = _resolve_generation_params(model_config, query, task)
    prompt = build_prompt(context, query, history, task, question_type=question_type)

    dlog("MODEL", "generate_response_stream",
         model=model_name,
         task=task,
         model_type=model_config.get("type", "?"),
         max_tokens=max_tokens,
         temperature=temperature,
         context_chars=len(context),
         prompt_chars=len(prompt),
         prompt_preview=prompt[:200].replace("\n", " "))
    _emit_selection_trace(task, model_name, model_config, context, query)

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
                    max_tokens=max_tokens,
                    temperature=temperature,
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