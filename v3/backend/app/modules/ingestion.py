"""
Handles PDF ingestion → chunking → FAISS storage + summary
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from pypdf import PdfReader
import re
import os
import json
import time

from ..core.config_loader import get_rag_config

# Base data directory
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
DATA_DIR = os.path.join(BASE_DIR, "data")
SUMMARY_FILE = os.path.join(DATA_DIR, "pdf_summaries.json")


# ----------------- PDF Extraction -----------------
def extract_text_from_pdf(file_path):
    """
    Extract text from PDF while preserving paragraph/heading structure as much as possible.
    """
    reader = PdfReader(file_path)
    pages = []

    for page in reader.pages:
        page_text = (page.extract_text() or "").replace("\x00", " ")
        page_text = re.sub(r"[ \t]+\n", "\n", page_text)
        page_text = re.sub(r"\n{3,}", "\n\n", page_text)
        page_text = re.sub(r"[ \t]{2,}", " ", page_text)
        page_text = page_text.strip()
        if page_text:
            pages.append(page_text)

    text = "\n\n".join(pages)
    text = re.sub(r"\s*\n+\s*", " ", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def _get_chunking_config():
    rag_cfg = get_rag_config()

    def _read_int(key, default, minimum, maximum):
        try:
            value = int(rag_cfg.get(key, default))
        except (TypeError, ValueError):
            value = default
        value = max(minimum, value)
        return min(value, maximum)

    return {
        "chunk_size": _read_int("chunk_size", 1000, 300, 4000),
        "chunk_overlap": _read_int("chunk_overlap", 180, 0, 1200),
        "summary_chunk_size": _read_int("summary_chunk_size", 2200, 600, 5000),
        "summary_chunk_overlap": _read_int("summary_chunk_overlap", 250, 0, 1800),
    }


# ----------------- Chunking -----------------
def chunk_text(text, chunk_size=None, overlap=None):
    """
    Split text into overlapping chunks while preferring paragraph and sentence boundaries.
    """
    cfg = _get_chunking_config()
    chunk_size = cfg["chunk_size"] if chunk_size is None else max(300, int(chunk_size or cfg["chunk_size"]))
    overlap = cfg["chunk_overlap"] if overlap is None else max(0, int(overlap or cfg["chunk_overlap"]))
    overlap = min(overlap, max(0, chunk_size - 1))

    cleaned = str(text or "").replace("\r", "\n")
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    if not cleaned:
        return []

    chunks = []
    start = 0
    text_len = len(cleaned)

    while start < text_len:
        end = min(text_len, start + chunk_size)

        if end < text_len:
            lower_bound = max(start + int(chunk_size * 0.6), start + 1)

            paragraph_break = cleaned.rfind("\n\n", lower_bound, end)
            if paragraph_break != -1:
                end = paragraph_break
            else:
                sentence_break = max(
                    cleaned.rfind(". ", lower_bound, end),
                    cleaned.rfind("! ", lower_bound, end),
                    cleaned.rfind("? ", lower_bound, end),
                )
                if sentence_break != -1:
                    end = sentence_break + 1
                else:
                    whitespace_break = cleaned.rfind(" ", lower_bound, end)
                    if whitespace_break != -1:
                        end = whitespace_break

        chunk = cleaned[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= text_len:
            break

        start = max(end - overlap, start + 1)
        while start < text_len and cleaned[start].isspace():
            start += 1

    return chunks


# ----------------- Summary Storage -----------------
def save_summary(pdf_path, summary):
    os.makedirs(DATA_DIR, exist_ok=True)
    summaries = {}
    if os.path.exists(SUMMARY_FILE):
        with open(SUMMARY_FILE, "r") as f:
            summaries = json.load(f)
    summaries[pdf_path] = summary
    with open(SUMMARY_FILE, "w") as f:
        json.dump(summaries, f, indent=2)


def get_summary(pdf_path):
    if os.path.exists(SUMMARY_FILE):
        with open(SUMMARY_FILE, "r") as f:
            summaries = json.load(f)
            return summaries.get(pdf_path, "")
    return ""


# ----------------- PDF Summarization -----------------
def summarize_pdf(text, pdf_path, model_name=None):
    """
    Hierarchical summarization:
    1. Split into medium chunks
    2. Summarize each chunk
    3. Merge summaries
    4. Final summary
    """

    from .model_manager import generate_response

    # 🔹 Step 1: medium chunks (NOT FAISS chunks)
    chunk_cfg = _get_chunking_config()
    summary_chunks = chunk_text(
        text,
        chunk_size=chunk_cfg["summary_chunk_size"],
        overlap=chunk_cfg["summary_chunk_overlap"],
    )

    print(f"📘 Summarizing {len(summary_chunks)} sections...")

    partial_summaries = []

    start_total = time.time()

    for i, chunk in enumerate(summary_chunks):
        section_start = time.time()

        print(f"🔹 Section {i+1}/{len(summary_chunks)} START")

        prompt = f"""
You are summarizing a school textbook chapter.

STRICT RULES:
- Use ONLY information from the text below
- DO NOT add or imagine anything
- DO NOT create new story elements
- Keep summary factual and short

TEXT:
{chunk}

SUMMARY:
"""

        try:
            summary = generate_response("", prompt, model_name=model_name, task="summary")
            partial_summaries.append(summary)

            section_time = time.time() - section_start
            print(f"✅ Section {i+1} DONE in {section_time:.2f}s")

        except Exception as e:
            print(f"❌ Error summarizing section {i}: {e}")

    # 🔹 Step 2: merge summaries
    print("🔹 Generating final summary...")

    final_summary = combine_summaries(partial_summaries, model_name)

    save_summary(pdf_path, final_summary)

    total_time = time.time() - start_total
    print(f"⏱ Total summarization time: {total_time:.2f}s")
    
    return final_summary


# ----------------- Full Ingestion -----------------
def ingest_pdf(file_path, model_name=None):
    """
    Full ingestion pipeline:
    1. Extract text
    2. Summarize (parallel)
    3. Chunk text
    4. Add to FAISS
    """
    from .faiss_store import add_doc

    print(f"Ingesting: {file_path}")

    text = extract_text_from_pdf(file_path)
    if not text.strip():
        print("No text found in PDF")
        return

    # Step 1: generate summary using parallel summarization
    summarize_pdf(text, file_path, model_name=model_name)

    # Step 2: chunk text for FAISS
    chunks = chunk_text(text)
    document_title = os.path.splitext(os.path.basename(file_path))[0]
    source_name = os.path.basename(file_path)
    for index, chunk in enumerate(chunks, start=1):
        enriched_chunk = (
            f"Document: {document_title}\n"
            f"Source: {source_name}\n"
            f"Chunk {index}:\n{chunk}"
        )
        add_doc(enriched_chunk, source=file_path)

    print(f"✅ Ingested {len(chunks)} chunks + summary successfully")


def ingest_image(file_path: str, model_name=None) -> None:
    """
    Image ingestion pipeline using OCR plus lightweight metadata extraction:
    1. Extract OCR text and title/keyword hints
    2. Save a short summary for later study use
    3. Chunk enriched text
    4. Add chunks to FAISS
    """
    from .faiss_store import add_doc
    from .image_pipeline import extract_image_content

    print(f"Ingesting image (OCR): {file_path}")

    image_content = extract_image_content(file_path, model_name=model_name)
    text = str(image_content.get("text") or "").strip()
    summary = str(image_content.get("summary") or "").strip()
    title = str(image_content.get("title") or os.path.splitext(os.path.basename(file_path))[0]).strip()
    modality = str(image_content.get("modality") or "image").strip()
    keywords = image_content.get("keywords") or []

    if summary:
        save_summary(file_path, summary)

    if not text:
        print(f"⚠️  No text extracted from image: {file_path} (OCR unavailable or blank image)")
        return

    chunks = chunk_text(text)
    source_name = os.path.basename(file_path)
    for index, chunk in enumerate(chunks, start=1):
        enriched_chunk = (
            f"Image: {title}\n"
            f"Source: {source_name}\n"
            f"Modality: {modality}\n"
            f"Keywords: {', '.join(map(str, keywords))}\n"
            f"OCR Summary: {summary or 'No summary available.'}\n"
            f"Chunk {index}:\n{chunk}"
        )
        add_doc(enriched_chunk, source=file_path)

    print(f"✅ Ingested {len(chunks)} OCR chunks from image successfully")


def safe_summarize(text, pdf_path, model_name=None, chunk_index=None):
    """
    Summarize text safely within the model context window by splitting long
    inputs into smaller sub-chunks and summarizing each one.
    """
    from .model_manager import generate_response

    max_chunk_len = 1500
    text = (text or "").strip()
    if not text:
        return ""

    text_chunks = [text[i:i + max_chunk_len] for i in range(0, len(text), max_chunk_len)]

    summaries = []
    for idx, chunk in enumerate(text_chunks):
        prompt = f"Summarize this document concisely in English:\n\n{chunk}\n\nSummary:"
        print(
            f"🔹 Summarizing sub-chunk {idx + 1}/{len(text_chunks)} of chunk "
            f"{chunk_index if chunk_index is not None else 'N/A'}"
        )
        summary = generate_response("", prompt, model_name=model_name, task="summary")
        summaries.append((summary or "").strip())

    return " ".join(part for part in summaries if part)


def combine_summaries(summaries, model_name=None):
    from .model_manager import generate_response

    batch_size = 3   # 🔥 SAFE SIZE

    while len(summaries) > 1:
        new_summaries = []

        print(f"🔄 Combining {len(summaries)} summaries...")

        for i in range(0, len(summaries), batch_size):
            batch = summaries[i:i + batch_size]
            combined = "\n".join(batch)

            prompt = f"""
Combine these summaries into one concise summary:

{combined}

Summary:
"""

            try:
                summary = generate_response("", prompt, model_name=model_name, task="summary")
                new_summaries.append(summary)
            except Exception as e:
                print(f"❌ Combine error: {e}")
                new_summaries.append("")

        summaries = new_summaries

    return summaries[0] if summaries else ""


