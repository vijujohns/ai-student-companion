from app.modules.vector_store import search, load_index
from app.modules.embedding import embed_text
from app.modules.llm import generate_answer

# ✅ Ensure FAISS loads
load_index()


def query_rag(payload):
    question = payload["question"]

    vec = embed_text(question)

    print("PAYLOAD:", payload)

    results = search(vec, 5, payload)

    if not results:
        return {
            "answer": "No relevant content found.",
            "sources": []
        }

    # ✅ STEP 1: Extract text chunks
    chunks = []
    seen = set()

    for r in results:
        text = r["text"].strip()

    # remove duplicates
    if text not in seen:
        chunks.append(text)
        seen.add(text)


    # ✅ STEP 2: Apply reranking (IMPORTANT FIX)
    ranked_chunks = rerank(question, chunks)

    # ✅ STEP 3: LIMIT CONTEXT SIZE (token safety)
    MAX_CHARS = 1200

    context_chunks = []
    total_len = 0

    for text in ranked_chunks:
        text = text[:300]   # limit each chunk

        # skip noisy instructional text
        if "activity under" in text.lower():
            continue
    
        if total_len + len(text) > MAX_CHARS:
            break

        context_chunks.append(text)
        total_len += len(text)

    context = "\n\n".join(context_chunks)

    # ✅ STRONG PROMPT (to stop hallucination + repetition)
    prompt = f"""
You are a school tutor.

Use ONLY the textbook content below.

If the answer is not clearly present, say: Not found in textbook.

TEXT:
{context}

QUESTION:
{question}

ANSWER (simple, short, correct):
"""

    answer = generate_answer(prompt)

    # ✅ HARD CLEANING
    import re

    # Remove repeated numbering loops
    if re.match(r"^(?:\d+\.\s*){10,}", answer):
        answer = "Not found in textbook"

    # Remove repeated phrases
    answer = re.sub(r"(Question:.*?)+", "", answer, flags=re.IGNORECASE)
    answer = re.sub(r"(Possible rewrite.*?)+", "", answer, flags=re.IGNORECASE)

    # Remove duplicate lines
    lines = answer.split("\n")
    seen = set()
    cleaned_lines = []

    for line in lines:
        if line.strip() and line not in seen:
            cleaned_lines.append(line)
            seen.add(line)

    answer = "\n".join(cleaned_lines).strip()

    # Final fallback
    if len(answer) < 10:
        answer = "Not found in textbook"


    return {
        "answer": answer,
        "sources": results
    }


# ✅ SIMPLE KEYWORD RERANKING
def rerank(question, chunks):
    scored = []

    q_words = set(question.lower().split())

    for c in chunks:
        c_words = set(c.lower().split())

        # keyword overlap
        overlap = len(q_words & c_words)

        # penalize repeated generic words
        penalty = c.lower().count("activity") + c.lower().count("before")

        score = overlap - (0.5 * penalty)

        scored.append((score, c))

    scored.sort(key=lambda x: x[0], reverse=True)

    return [c for score, c in scored[:3]]   # only top 3 (important)