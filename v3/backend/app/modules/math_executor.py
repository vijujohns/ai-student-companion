"""Compatibility-first math executor for Step 11.

Uses SymPy for symbolic and arithmetic solving when available and falls back to
existing model generation for broader word problems.
"""

from __future__ import annotations

import re
from typing import Optional

try:
    import sympy as sp
    from sympy.parsing.sympy_parser import parse_expr
except Exception:  # pragma: no cover - graceful fallback when SymPy is unavailable
    sp = None
    parse_expr = None

from .model_manager import generate_response

_ALLOWED_EXPR_RE = re.compile(r"^[0-9A-Za-z_+\-*/^().=, ]+$")
_WRAPPER_PATTERNS = [
    re.compile(r"^(?:solve|calculate|evaluate|simplify|factor|expand)\s+", re.IGNORECASE),
    re.compile(r"^(?:what is|find)\s+", re.IGNORECASE),
]


def _strip_wrapper(text: str) -> str:
    cleaned = str(text or "").strip().rstrip("?")
    for pattern in _WRAPPER_PATTERNS:
        cleaned = pattern.sub("", cleaned)
    return cleaned.strip()


def _normalize_expression(text: str) -> str:
    expr = _strip_wrapper(text)
    expr = expr.replace("×", "*").replace("÷", "/").replace("^", "**")
    expr = re.sub(r"\s+", " ", expr)
    return expr.strip()


def _is_safe_expression(expr: str) -> bool:
    return bool(expr) and bool(_ALLOWED_EXPR_RE.fullmatch(expr)) and "__" not in expr


def _build_symbol_map(expr: str) -> dict:
    names = sorted(set(re.findall(r"\b[a-zA-Z]\w*\b", expr)))
    return {name: sp.Symbol(name) for name in names} if sp else {}


def _format_solution(solution) -> str:
    if isinstance(solution, list):
        if not solution:
            return "No exact symbolic solution found."
        first = solution[0]
        if isinstance(first, dict):
            parts = []
            for key, value in first.items():
                rendered = sp.simplify(value) if sp else value
                parts.append(f"{key} = {rendered}")
            return ", ".join(parts)
        return ", ".join(str(item) for item in solution)
    return str(solution)


def execute_math_task(
    *,
    query: str,
    user_id: str,
    session_id: str,
    model_name: Optional[str] = None,
    content_id: Optional[str] = None,
) -> str:
    """Solve a math request using SymPy when possible, with safe fallback."""
    expression = _normalize_expression(query)

    if sp is None or parse_expr is None or not _is_safe_expression(expression):
        return generate_response(
            context="",
            query=f"Solve this math problem carefully and show the final answer clearly: {query}",
            model_name=model_name,
            task="qa",
        )

    symbols = _build_symbol_map(expression)

    try:
        lowered = str(query or "").lower()

        if expression.count("=") == 1 and any(term in lowered for term in ("solve", "equation", "find x", "find y")):
            left_text, right_text = [part.strip() for part in expression.split("=", 1)]
            left = parse_expr(left_text, local_dict=symbols, evaluate=True)
            right = parse_expr(right_text, local_dict=symbols, evaluate=True)
            targets = list(symbols.values()) or [sp.Symbol("x")]
            solved = sp.solve(sp.Eq(left, right), targets if len(targets) > 1 else targets[0], dict=True)
            formatted = _format_solution(solved)
            return f"Math result: {formatted}"

        if lowered.startswith("factor"):
            expr = parse_expr(expression, local_dict=symbols, evaluate=True)
            return f"Math result: {sp.factor(expr)}"

        if lowered.startswith("expand"):
            expr = parse_expr(expression, local_dict=symbols, evaluate=True)
            return f"Math result: {sp.expand(expr)}"

        if lowered.startswith("simplify"):
            expr = parse_expr(expression, local_dict=symbols, evaluate=True)
            return f"Math result: {sp.simplify(expr)}"

        expr = parse_expr(expression, local_dict=symbols, evaluate=True)
        if getattr(expr, "free_symbols", None):
            return f"Math result: {sp.simplify(expr)}"

        simplified = sp.simplify(expr)
        return f"Math result: {simplified}"
    except Exception:
        return generate_response(
            context="",
            query=f"Solve this math problem carefully and show the final answer clearly: {query}",
            model_name=model_name,
            task="qa",
        )
