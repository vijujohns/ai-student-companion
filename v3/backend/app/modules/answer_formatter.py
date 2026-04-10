"""Strict answer post-processing and presentation helpers.

This module aggressively cleans raw model output and turns it into compact,
student-friendly study notes without touching retrieval or generation logic.
"""

from __future__ import annotations

import re

from .query_classifier import classify_query as shared_classify_query

_TOKEN_RE = re.compile(r"[A-Za-z0-9']+")
_DEFAULT_SUMMARY = "It gives the key idea clearly."
_MAX_SIMPLE_WORDS = 24
_MAX_BULLET_WORDS = 12
_MAX_LIST_ITEM_WORDS = 18
_MAX_EXAMPLE_WORDS = 18
_MAX_SUMMARY_WORDS = 16


def _split_sentences(text: str) -> list[str]:
    normalized = str(text or "").replace("\r", "\n").replace("...", ". ")
    normalized = re.sub(r"\n+", " ", normalized)
    parts = re.split(r"(?<=[.!?])\s+", normalized)
    return [part.strip(" ,") for part in parts if part and part.strip(" ,")]


def _word_count(text: str) -> int:
    return len(_TOKEN_RE.findall(str(text or "")))


def _limit_words(text: str, max_words: int, *, suffix: str = "") -> str:
    content = re.sub(r"\s+", " ", str(text or "")).strip(" ,")
    if not content or _word_count(content) <= max_words:
        return content

    words = content.split()
    trimmed = " ".join(words[:max_words]).rstrip(" ,;:-")
    return f"{trimmed}{suffix}".strip()


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for item in items:
        cleaned = re.sub(r"\s+", " ", str(item or "")).strip(" ,.;:-")
        key = cleaned.lower()
        if not cleaned or key in seen:
            continue
        seen.add(key)
        deduped.append(cleaned)
    return deduped


def _title_case_phrase(text: str) -> str:
    normalized = " ".join(str(text or "").strip().split())
    if not normalized:
        return "Topic"

    small_words = {"of", "the", "and", "to", "in", "for", "on", "a", "an", "vs", "with"}
    words: list[str] = []
    for index, word in enumerate(normalized.split()):
        lowered = word.lower()
        if word.isupper() and len(word) <= 6:
            words.append(word)
        elif index > 0 and lowered in small_words:
            words.append(lowered)
        else:
            words.append(lowered.capitalize())
    return " ".join(words) or "Topic"


def extract_topic(query: str) -> str:
    normalized = " ".join(str(query or "").strip().split())
    if not normalized:
        return "Topic"

    diary_match = re.match(r"^what did\s+([A-Za-z]+)\s+write in (?:his|her|their) diary\??$", normalized, flags=re.IGNORECASE)
    if diary_match:
        name = _title_case_phrase(diary_match.group(1))
        suffix = "' Diary Entry" if name.endswith("s") else "'s Diary Entry"
        return f"{name}{suffix}"

    normalized = re.sub(r"^(?:please|can you|could you)\s+", "", normalized, flags=re.IGNORECASE)
    patterns = (
        r"^(?:what is|what are|who is|who are|when is|where is|which is|define)\s+(.+)$",
        r"^(?:what did|when did|where did|who wrote|who said|what was the name of)\s+(.+)$",
        r"^(?:explain|describe|summari[sz]e|tell me about|write about)\s+(.+)$",
        r"^(?:list|show|name|give)\s+(.+)$",
        r"^(?:how does|how do|why does|why do|how is|why is)\s+(.+)$",
        r"^(?:compare|difference between|distinguish between|contrast)\s+(.+)$",
    )
    for pattern in patterns:
        match = re.match(pattern, normalized, flags=re.IGNORECASE)
        if match:
            normalized = match.group(1)
            break

    normalized = re.sub(r"\b(?:briefly|in simple words|with example[s]?|short note|short notes)\b", "", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"^(?:the )", "", normalized, flags=re.IGNORECASE)
    normalized = normalized.strip(" ?.!,:;-")
    return _title_case_phrase(normalized) if normalized else "Topic"


def _extract_compare_targets(query: str) -> tuple[str, str] | None:
    normalized = " ".join(str(query or "").strip().split())
    patterns = (
        r"compare\s+(.+?)\s+(?:and|with|vs\.?|versus)\s+(.+)$",
        r"(?:difference between|distinguish between|contrast)\s+(.+?)\s+(?:and|with)\s+(.+)$",
    )
    for pattern in patterns:
        match = re.search(pattern, normalized, flags=re.IGNORECASE)
        if match:
            left = match.group(1).strip(" ?.!,-")
            right = match.group(2).strip(" ?.!,-")
            if left and right:
                return left, right
    return None


def detect_query_intent(query: str) -> str:
    normalized = " ".join(str(query or "").strip().lower().split())
    if not normalized:
        return "qa"

    if any(term in normalized for term in ("compare", "difference between", "distinguish between", "contrast", " versus ", " vs ")):
        return "compare"

    query_type = shared_classify_query(query)
    return {
        "quote": "fact",
        "fact": "fact",
        "definition": "definition",
        "explanation": "explain",
        "list": "list",
        "summary_structured": "summary_structured",
        "math": "explain",
        "general": "qa",
    }.get(query_type, "qa")


def detect_question_type(query: str) -> str:
    return shared_classify_query(query)


def clean_answer(text: str) -> str:
    raw = str(text or "")
    if not raw.strip():
        return ""

    explicit_refusals = (
        "This is not clearly mentioned in the provided material.",
        "This is not clearly mentioned in the selected material. Try selecting a more relevant chapter or ask in Explorer mode.",
        "I don't have enough information in the provided material.",
    )
    normalized_raw = " ".join(raw.strip().split())
    for refusal in explicit_refusals:
        if normalized_raw.lower() == refusal.lower():
            return refusal

    structured_markdown = raw.lstrip().startswith(("#", "- ", "* ", "> ", "|", "• ")) or any(
        token in raw for token in ("\n## ", "\n### ", "\n- ", "\n* ", "\n• ", "\n> ", "\n| ")
    )
    cleaned = raw.replace("\r", "\n")
    aggressive_patterns = (
        r"\bprovided material\b",
        r"\bprovided context\b",
        r"\bbased on the provided (?:context|material)\b[:,]?\s*",
        r"\bi (?:do not|don't) have enough information(?: in the provided material)?\b[.!]?",
        r"\bi could not find this in the provided study material\b[.!]?",
        r"\bchunk\s*\d+\b",
        r"\bin chunk\b",
        r"\bfrom the document\b",
        r"\blet['’]s break (?:it )?down\b[^.?!]*[.?!]?\s*",
        r"\blet['’]s find out\b[^.?!]*[.?!]?\s*",
        r"\bhowever,?\s*i can guide you\b",
        r"\bthe material does not explicitly\b",
        r"\baccording to (?:the )?(?:provided )?(?:context|material|document summary|document|diagram labels)\b[:,]?\s*",
        r"\baccording to\s+(?:the\s+)?\"[^\"]+\"(?:\s+section)?[:,]?\s*",
        r"\bin the provided (?:context|material|document)\b[:,]?\s*",
        r"\bfrom the provided (?:context|material|document)\b[:,]?\s*",
        r"\bin the material\b[:,]?\s*",
        r"\bthe answer is\b[:]?\s*",
        r"\bwe can see that\b[:,]?\s*",
        r"\blet['’]s [^.?!]*(?:find the answer|look at|understand)\b[^.?!]*[.?!]?\s*",
    )
    for pattern in aggressive_patterns:
        cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)

    cleaned = re.sub(r'"[^\"]*(?:summary|notes|reference|context|diagram labels|ocr)[^\"]*"', " ", cleaned, flags=re.IGNORECASE)

    if structured_markdown:
        cleaned = re.sub(r"[ \t]+", " ", cleaned)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        lines: list[str] = []
        seen: set[str] = set()
        for raw_line in cleaned.splitlines():
            line = raw_line.rstrip()
            if not line.strip():
                if lines and lines[-1] != "":
                    lines.append("")
                continue
            normalized = line.replace("provided material", "").replace("provided context", "").strip()
            key = normalized.lower()
            if key in seen and not normalized.startswith(("#", "-", "*", "•", ">", "|")):
                continue
            seen.add(key)
            lines.append(normalized)
        return "\n".join(lines).strip()

    cleaned = re.sub(r"(?<!\n)\s+-\s+(?=[A-Za-z])", ", ", cleaned)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    sentences: list[str] = []
    seen: set[str] = set()
    for sentence in _split_sentences(cleaned):
        normalized = re.sub(r"\s+", " ", sentence).strip(" ,")
        normalized = re.sub(r"^(?:additionally|also|therefore|thus|so|however)[,:\s]+", "", normalized, flags=re.IGNORECASE)
        normalized = normalized.replace("provided material", "").replace("provided context", "")
        normalized = normalized.strip(" ,")
        key = normalized.lower()
        if not normalized or key in seen:
            continue
        seen.add(key)
        if normalized[-1] not in ".!?":
            normalized += "."
        sentences.append(normalized)

    return " ".join(sentences).strip()


def _normalize_bullet_text(text: str) -> str:
    cleaned = clean_answer(text)
    cleaned = re.sub(r"^(?:it|this|they|these)\s+", lambda m: m.group(0).capitalize(), cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^(?:also|additionally|therefore|thus|so|however|because)\b[:,\s]*", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.strip(" .,-")
    if not cleaned:
        return ""
    cleaned = cleaned[0].upper() + cleaned[1:]
    return _limit_words(cleaned, _MAX_BULLET_WORDS)


def _normalize_list_item(text: str) -> str:
    cleaned = clean_answer(text)
    cleaned = cleaned.replace("**", "")
    cleaned = re.sub(r"^[•*\-\d.)\s]+", "", cleaned)
    cleaned = re.sub(r"^(?:for example|example|such as|like)\b[:,\s-]*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^(?:and|or|with|which|that)\b[:,\s-]*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"(:\s*)label\b\s*[,:-]*\s*", r"\1", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\blabel\b\s*[,:-]*\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r":\s*,\s*", ": ", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = cleaned.strip(" .,-")
    if not cleaned:
        return ""
    cleaned = cleaned[0].upper() + cleaned[1:]
    return _limit_words(cleaned, _MAX_LIST_ITEM_WORDS)


def _merge_fragmented_list_items(items: list[str]) -> list[str]:
    merged: list[str] = []
    continuation_prefixes = (
        "measured in ", "related to ", "which ", "that ", "called ", "known as ",
        "cycles per second", "oscillations per second", "distance between", "the time taken",
    )
    merge_with_or = {"soft", "low-pitched", "low pitched", "low", "quiet", "high-pitched", "high pitched"}

    for item in items:
        cleaned = str(item or "").strip()
        if not cleaned:
            continue
        lowered = cleaned.lower()
        if merged:
            prev = merged[-1]
            prev_lower = prev.lower()
            if prev_lower.startswith(("they can be ", "it can be ", "sound can be ")) and any(lowered.startswith(prefix) for prefix in merge_with_or):
                suffix = cleaned[0].lower() + cleaned[1:] if cleaned and cleaned[0].isupper() else cleaned
                merged[-1] = _limit_words(f"{prev.rstrip('.')} or {suffix}", _MAX_LIST_ITEM_WORDS + 6)
                continue
            if any(lowered.startswith(prefix) for prefix in continuation_prefixes):
                suffix = cleaned[0].lower() + cleaned[1:] if cleaned and cleaned[0].isupper() else cleaned
                merged[-1] = _limit_words(f"{prev.rstrip('.')} {suffix}", _MAX_LIST_ITEM_WORDS + 6)
                continue
        merged.append(cleaned)

    return _dedupe_preserve_order(merged)


def _extract_list_items(answer: str) -> list[str]:
    items: list[str] = []
    blocked_prefixes = (
        "in the ", "on the ", "we can ", "we see ", "there are ", "additionally", "also ", "therefore", "for example", "example", "like ", "which ", "measured in "
    )

    text = clean_answer(answer)
    explicit_bullets: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith(("- ", "* ", "• ")):
            normalized_line = _normalize_list_item(line[2:])
            if normalized_line:
                explicit_bullets.append(normalized_line)

    if len(_dedupe_preserve_order(explicit_bullets)) >= 3:
        return _merge_fragmented_list_items(_dedupe_preserve_order(explicit_bullets))[:6]

    for sentence in _split_sentences(text):
        stripped = sentence.strip()
        if ":" in stripped:
            head, tail = stripped.split(":", 1)
            if 0 < len(head.split()) <= 4:
                candidate = _normalize_list_item(f"{head.strip()}: {tail.strip()}")
                if candidate:
                    items.append(candidate)
                continue

        candidates = [sentence.split(":", 1)[1]] if ":" in sentence else [sentence]
        for candidate in candidates:
            normalized = re.sub(r"^[^.?!:]*\b(?:includes?|such as|are|is|has(?: the following)?|consists of|listed as|shows)\b[:\s-]*", "", candidate, flags=re.IGNORECASE)
            normalized = re.sub(r"\s+(?:and|or)\s+", ", ", normalized, flags=re.IGNORECASE)
            if "," not in normalized and ";" not in normalized:
                continue

            for part in re.split(r"[,;•]+", normalized):
                cleaned = re.sub(r"^(?:the|a|an)\s+", "", part.strip(), flags=re.IGNORECASE)
                lowered = cleaned.lower()
                if not cleaned or '"' in cleaned or "'" in cleaned:
                    continue
                if any(lowered.startswith(prefix) for prefix in blocked_prefixes):
                    continue
                if 2 <= len(cleaned.split()) <= 10:
                    normalized_item = _normalize_list_item(cleaned if not cleaned.islower() else _title_case_phrase(cleaned))
                    if normalized_item:
                        items.append(normalized_item)

    combined = _merge_fragmented_list_items(_dedupe_preserve_order([*explicit_bullets, *items]))
    return [item for item in combined[:8] if item]


def _sentence_fragments(sentence: str) -> list[str]:
    working = clean_answer(sentence)
    working = re.sub(r"\s+(?:because|while|whereas|but|so that)\s+", " | ", working, flags=re.IGNORECASE)
    working = re.sub(r",\s+", " | ", working)
    working = re.sub(r"\s+and\s+(?=(?:is|are|was|were|can|helps?|uses?|used|makes?|means|shows?|causes?|allows?|gives?|improves?))", " | ", working, flags=re.IGNORECASE)
    return [part.strip(" ,.-") for part in working.split("|") if part.strip(" ,.-")]


def _generate_bullets(answer: str) -> list[str]:
    bullets = _extract_list_items(answer)
    if len(bullets) >= 3:
        return bullets[:5]

    for sentence in _split_sentences(answer):
        for fragment in _sentence_fragments(sentence):
            normalized = _normalize_bullet_text(fragment)
            if normalized:
                bullets.append(normalized)
            if len(_dedupe_preserve_order(bullets)) >= 5:
                break
        if len(_dedupe_preserve_order(bullets)) >= 5:
            break

    deduped = _dedupe_preserve_order(bullets)
    return deduped[:5]


def _extract_example(answer: str) -> str:
    markers = ("for example", "for instance", "e.g.", "example:")
    for sentence in _split_sentences(answer):
        lowered = sentence.lower()
        if any(marker in lowered for marker in markers):
            return _limit_words(clean_answer(sentence), _MAX_EXAMPLE_WORDS)
    return ""


def _fallback_short_answer(answer: str) -> str:
    cleaned = clean_answer(answer)
    sentences = _split_sentences(cleaned)
    if not sentences:
        return _limit_words(cleaned, 28)

    selected: list[str] = []
    total_words = 0
    for sentence in sentences:
        word_total = _word_count(sentence)
        if selected and total_words + word_total > 36:
            break
        selected.append(sentence)
        total_words += word_total
        if total_words >= 24:
            break
    fallback = " ".join(selected).strip()
    return _limit_words(fallback, 36)


def _build_simple_meaning(topic: str, cleaned: str, bullets: list[str]) -> str:
    sentences = _split_sentences(cleaned)
    if bullets and len(bullets) >= 3:
        preview = ", ".join(item.lower() for item in bullets[:3])
        candidate = f"{topic} includes the main ideas or parts such as {preview}."
        return _limit_words(candidate, _MAX_SIMPLE_WORDS)
    if sentences:
        return _limit_words(sentences[0], _MAX_SIMPLE_WORDS)
    return _limit_words(cleaned, _MAX_SIMPLE_WORDS)


def _build_summary(topic: str, cleaned: str, bullets: list[str]) -> str:
    sentences = _split_sentences(cleaned)
    if sentences:
        return _limit_words(sentences[-1], _MAX_SUMMARY_WORDS)
    if bullets:
        return _limit_words(f"{topic} is best understood through its main points.", _MAX_SUMMARY_WORDS)
    return _DEFAULT_SUMMARY


def _build_list_summary(topic: str, items: list[str]) -> str:
    labels: list[str] = []
    for item in items[:4]:
        candidate = item.split(":", 1)[0] if ":" in item else item
        candidate = re.sub(r"\s*\([^)]*\)$", "", candidate).strip(" .,-")
        if 0 < len(candidate.split()) <= 4:
            labels.append(candidate.lower())

    labels = _dedupe_preserve_order(labels)
    if labels:
        if len(labels) == 1:
            joined = labels[0]
        elif len(labels) == 2:
            joined = f"{labels[0]} and {labels[1]}"
        else:
            joined = f"{', '.join(labels[:-1])}, and {labels[-1]}"
        return _limit_words(f"{topic} mainly includes {joined}.", _MAX_SUMMARY_WORDS)

    if items:
        return _limit_words(f"{topic} is best understood through its main characteristics.", _MAX_SUMMARY_WORDS)
    return _DEFAULT_SUMMARY


def _collect_compare_points(text: str, subject: str) -> list[str]:
    subject_pattern = re.compile(re.escape(subject), flags=re.IGNORECASE)
    points: list[str] = []
    for sentence in _split_sentences(text):
        if subject.lower() not in sentence.lower():
            continue
        trimmed = subject_pattern.sub("", sentence)
        trimmed = re.sub(r"\b(?:while|whereas|however)\b", ",", trimmed, flags=re.IGNORECASE)
        trimmed = re.sub(r"\s+(?:and|but)\s+", ", ", trimmed, flags=re.IGNORECASE)
        for fragment in re.split(r"[,;]+", trimmed):
            cleaned = re.sub(r"^(?:the|a|an)\s+", "", fragment.strip(), flags=re.IGNORECASE)
            cleaned = clean_answer(cleaned)
            if cleaned and cleaned.lower() not in {subject.lower()}:
                points.append(_limit_words(cleaned.rstrip("."), _MAX_BULLET_WORDS + 2))
    return _dedupe_preserve_order(points)[:4]


def _pick_compare_label(left: str, right: str, index: int) -> str:
    filler = {"more", "less", "higher", "lower", "better", "best", "worse", "limited", "improved", "main", "important"}
    skip_tokens = filler.union({"the", "a", "an", "is", "are", "was", "were", "and", "or", "but", "for", "with", "from", "into"})
    left_tokens = [token for token in _TOKEN_RE.findall(str(left or "").lower()) if len(token) > 2 and token not in skip_tokens]
    right_tokens = [token for token in _TOKEN_RE.findall(str(right or "").lower()) if len(token) > 2 and token not in skip_tokens]
    common = [token for token in left_tokens if token in right_tokens]
    if common:
        return _title_case_phrase(common[-1])

    candidate = right_tokens[-1] if right_tokens else left_tokens[-1] if left_tokens else ""
    if candidate.endswith("s") and len(candidate) > 4:
        candidate = candidate[:-1]
    return _title_case_phrase(candidate) if candidate else f"Point {index + 1}"


def format_definition(query: str, answer: str) -> str:
    cleaned = clean_answer(answer)
    if not cleaned:
        return ""
    if cleaned.startswith("## ") and "**Simple" in cleaned:
        return cleaned
    if str(query or "").strip().lower().startswith("how many "):
        return _fallback_short_answer(cleaned)

    topic = extract_topic(query)
    bullets = _generate_bullets(cleaned)[:4]
    example = _extract_example(cleaned)
    simple = _build_simple_meaning(topic, cleaned, bullets)
    summary = _build_summary(topic, cleaned, bullets)

    lines = [
        f"## {topic}",
        "",
        "**Simple meaning:**",
        simple,
    ]
    if bullets:
        lines.extend(["", "### Key Points:", *(f"- {point}" for point in bullets[:4])])
    if example:
        lines.extend(["", "### Example (if applicable):", example])
    lines.extend(["", f"> **In short:** {summary}"])
    return "\n".join(lines).strip()


def format_fact(query: str, answer: str) -> str:
    cleaned = clean_answer(answer)
    if not cleaned:
        return ""
    return _fallback_short_answer(cleaned)


def _extract_summary_topic(query: str) -> str:
    normalized = " ".join(str(query or "").strip().split())
    if not normalized:
        return "Summary"

    patterns = (
        r"^(?:summari[sz]e|summary(?: of)?|overview(?: of)?|notes on|revision notes(?: on)?|study notes(?: on)?|give (?:me )?(?:a )?(?:summary|overview)|(?:give|prepare|make|create)(?: me)? (?:revision )?notes(?: on)?)\s+(.+)$",
    )
    for pattern in patterns:
        match = re.match(pattern, normalized, flags=re.IGNORECASE)
        if match:
            normalized = match.group(1)
            break

    normalized = re.sub(r"\bfor\s+(?:revision|study)\s+notes?\b", "", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\b(?:revision|study)\s+notes?\b", "", normalized, flags=re.IGNORECASE)
    normalized = normalized.strip(" ?.!,:;-")
    return _title_case_phrase(normalized) if normalized else "Summary"


def format_structured_summary(query: str, answer: str) -> str:
    cleaned = clean_answer(answer)
    if not cleaned:
        return ""

    topic = _extract_summary_topic(query)
    if cleaned.startswith("## "):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("## ") and not lines[0].startswith("## 📘"):
            heading_text = lines[0].lstrip("# ").strip() or topic
            lines[0] = f"## 📘 {heading_text}"
        if not any(line.strip().lower() == "### final takeaways" for line in lines):
            takeaway = _build_summary(topic, cleaned, _generate_bullets(cleaned))
            lines.extend(["", "### Final Takeaways", f"- {takeaway}"])
        return "\n".join(lines).strip()

    sentences = _split_sentences(cleaned)
    overview = " ".join(sentences[:2]).strip() or _fallback_short_answer(cleaned)
    bullet_points = _generate_bullets(cleaned)
    if len(bullet_points) < 3:
        for sentence in sentences[2:]:
            normalized = _normalize_bullet_text(sentence)
            if normalized:
                bullet_points.append(normalized)
            if len(_dedupe_preserve_order(bullet_points)) >= 4:
                break
    bullet_points = _dedupe_preserve_order(bullet_points)[:5] or [_fallback_short_answer(cleaned)]

    takeaway_items = _dedupe_preserve_order([
        _build_summary(topic, cleaned, bullet_points),
        *bullet_points[:2],
    ])[:3]

    lines = [
        f"## 📘 {topic}",
        "",
        "### Overview",
        overview,
        "",
        "### Key Points",
        *(f"- {point}" for point in bullet_points),
        "",
        "### Final Takeaways",
        *(f"- {item}" for item in takeaway_items),
    ]
    return "\n".join(lines).strip()


def format_explanation(query: str, answer: str) -> str:
    cleaned = clean_answer(answer)
    if not cleaned:
        return ""
    if (cleaned.startswith("## ") and ("### Key Points:" in cleaned or "**Simple Explanation:**" in cleaned or "**Simple meaning:**" in cleaned)) or (
        "**Simple Explanation" in cleaned and ("\n- " in cleaned or "\n* " in cleaned or "\n• " in cleaned)
    ):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("**") and lines[0].endswith("**"):
            title = lines[0].strip("* ")
            lines[0] = f"## {title}"
            cleaned = "\n".join(lines)
        return cleaned

    topic = extract_topic(query)
    bullets = _generate_bullets(cleaned)
    example = _extract_example(cleaned)
    simple = _build_simple_meaning(topic, cleaned, bullets)
    summary = _build_summary(topic, cleaned, bullets)

    if example:
        bullets = [item for item in bullets if item.lower() != example.lower()]

    if len(bullets) < 3:
        fallback_bits = [simple, summary, _fallback_short_answer(cleaned)]
        for bit in fallback_bits:
            normalized = _normalize_bullet_text(bit)
            if normalized:
                bullets.append(normalized)
            if len(_dedupe_preserve_order(bullets)) >= 3:
                break

    bullets = _dedupe_preserve_order(bullets)[:5]
    if not bullets:
        return _fallback_short_answer(cleaned)

    lines = [
        f"## {topic}",
        "",
        "**Simple meaning:**",
        simple,
        "",
        "### Key Points:",
        *(f"- {point}" for point in bullets[:5]),
    ]
    if example:
        lines.extend(["", "### Example (if applicable):", example])
    lines.extend(["", f"> **In short:** {summary}"])
    return "\n".join(lines).strip()


def format_list(query: str, answer: str) -> str:
    cleaned = clean_answer(answer)
    topic = extract_topic(query)

    bullet_lines = []
    for raw_line in cleaned.splitlines():
        line = raw_line.strip()
        if line.startswith(("- ", "* ", "• ")):
            normalized = _normalize_list_item(line[2:])
            if normalized:
                bullet_lines.append(normalized)

    if bullet_lines:
        items = _merge_fragmented_list_items(_dedupe_preserve_order(bullet_lines))[:6]
        summary = _build_list_summary(topic, items)
        lines = [
            f"## {topic}",
            "",
            *(f"- {item}" for item in items),
            "",
            f"> **In short:** {summary}",
        ]
        return "\n".join(lines).strip()

    if cleaned.startswith("## ") and ("\n- " in cleaned or "\n* " in cleaned or "\n• " in cleaned):
        return cleaned

    items = _extract_list_items(cleaned)
    if not items:
        return _fallback_short_answer(cleaned)

    items = _merge_fragmented_list_items(items)
    summary = _build_list_summary(topic, items)
    lines = [
        f"## {topic}",
        "",
        *(f"- {item}" for item in items[:6]),
        "",
        f"> **In short:** {summary}",
    ]
    return "\n".join(lines).strip()


def format_compare(query: str, answer: str) -> str:
    cleaned = clean_answer(answer)
    targets = _extract_compare_targets(query)
    if not targets:
        return _fallback_short_answer(cleaned)

    left_topic, right_topic = targets
    left_points = _collect_compare_points(cleaned, left_topic)
    right_points = _collect_compare_points(cleaned, right_topic)
    if not left_points and not right_points:
        return _fallback_short_answer(cleaned)

    row_count = max(2, min(max(len(left_points), len(right_points)), 5))
    rows = []
    for index in range(row_count):
        left_value = left_points[index] if index < len(left_points) else "—"
        right_value = right_points[index] if index < len(right_points) else "—"
        label = _pick_compare_label(left_value, right_value, index)
        rows.append((label, left_value or "—", right_value or "—"))

    summary = _build_summary(f"{left_topic} vs {right_topic}", cleaned, left_points + right_points)
    left_title = _title_case_phrase(left_topic)
    right_title = _title_case_phrase(right_topic)
    lines = [
        f"## {left_title} vs {right_title}",
        "",
        f"| Aspect | {left_title} | {right_title} |",
        "|--------|--------|--------|",
        *(f"| {label} | {left} | {right} |" for label, left, right in rows),
        "",
        f"> **In short:** {summary}",
    ]
    return "\n".join(lines).strip()


def format_response(text: str, question_type: str = "general") -> str:
    cleaned = clean_answer(text)
    if not cleaned:
        return ""
    if cleaned.startswith("## "):
        return cleaned

    normalized_type = str(question_type or "general").strip().lower() or "general"
    sentences = _split_sentences(cleaned)

    if normalized_type == "summary_structured":
        return format_structured_summary("Summary", cleaned)

    if normalized_type == "fact":
        return _fallback_short_answer(cleaned)

    if normalized_type == "definition":
        if not sentences:
            return _fallback_short_answer(cleaned)
        primary = " ".join(sentences[:2]).strip()
        example = _extract_example(cleaned)
        if example and example.lower() not in primary.lower():
            return f"{primary}\n\n**Example:** {example}".strip()
        return primary or _fallback_short_answer(cleaned)

    if normalized_type in {"explanation", "explain"}:
        if len(sentences) < 2:
            return _fallback_short_answer(cleaned)

        topic_tokens = _TOKEN_RE.findall(sentences[0])[:5]
        topic = _title_case_phrase(" ".join(topic_tokens)) if topic_tokens else "Answer"
        bullets = _generate_bullets(cleaned)
        example = _extract_example(cleaned)
        simple = _build_simple_meaning(topic, cleaned, bullets)
        summary = _build_summary(topic, cleaned, bullets)
        if example:
            bullets = [item for item in bullets if item.lower() != example.lower()]

        if len(bullets) < 2:
            fallback_bits = [simple, summary, _fallback_short_answer(cleaned)]
            for bit in fallback_bits:
                normalized = _normalize_bullet_text(bit)
                if normalized:
                    bullets.append(normalized)
                if len(_dedupe_preserve_order(bullets)) >= 3:
                    break

        bullets = _dedupe_preserve_order(bullets)[:5]
        if not bullets:
            return _fallback_short_answer(cleaned)

        lines = [
            f"## {topic}",
            "",
            "**Simple Explanation:**",
            simple,
            "",
            "### Key Points:",
            *(f"- {point}" for point in bullets[:5]),
        ]
        if example:
            lines.extend(["", "### Example:", example])
        lines.extend(["", f"> **Summary:** {summary}"])
        return "\n".join(lines).strip()

    if len(sentences) < 2:
        return _fallback_short_answer(cleaned)

    topic_tokens = _TOKEN_RE.findall(sentences[0])[:5]
    topic = _title_case_phrase(" ".join(topic_tokens)) if topic_tokens else "Answer"
    bullets = _generate_bullets(cleaned)
    example = _extract_example(cleaned)
    simple = _build_simple_meaning(topic, cleaned, bullets)
    summary = _build_summary(topic, cleaned, bullets)
    if example:
        bullets = [item for item in bullets if item.lower() != example.lower()]

    if len(bullets) < 2:
        return _fallback_short_answer(cleaned)

    lines = [
        f"## {topic}",
        "",
        "**Simple meaning:**",
        simple,
        "",
        "### Key Points:",
        *(f"- {point}" for point in bullets[:5]),
    ]
    if example:
        lines.extend(["", "### Example (if applicable):", example])
    lines.extend(["", f"> **In short:** {summary}"])
    return "\n".join(lines).strip()


def strict_format_answer(query: str, answer: str) -> str:
    intent = detect_query_intent(query)
    cleaned = clean_answer(answer)
    if not cleaned:
        return ""

    if intent == "compare":
        return format_compare(query, cleaned)
    if intent == "summary_structured":
        return format_structured_summary(query, cleaned)
    if intent == "list":
        return format_list(query, cleaned)
    if intent == "explain":
        return format_explanation(query, cleaned)
    if intent == "fact":
        return format_fact(query, cleaned)
    if intent == "definition":
        return format_definition(query, cleaned)
    return format_response(cleaned, detect_question_type(query))


def format_answer(query: str, answer: str) -> str:
    return strict_format_answer(query, answer)


_extract_topic = extract_topic
