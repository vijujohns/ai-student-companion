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

# Base data directory
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
DATA_DIR = os.path.join(BASE_DIR, "data")
SUMMARY_FILE = os.path.join(DATA_DIR, "pdf_summaries.json")


# ----------------- PDF Extraction -----------------
def extract_text_from_pdf(file_path):
    """
    Extract text from PDF file and clean whitespace
    """
    reader = PdfReader(file_path)
    text = ""

    for page in reader.pages:
        text += page.extract_text() or ""

    # 🔹 Clean text
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# ----------------- Chunking -----------------
def chunk_text(text, chunk_size=500, overlap=100):
    """
    Split text into overlapping chunks (better RAG quality)
    """
    chunks = []
    start = 0
    text_length = len(text)

    while start < text_length:
        end = start + chunk_size
        chunk = text[start:end]

        # Try to end at sentence boundary
        if end < text_length:
            last_period = chunk.rfind(".")
            if last_period > 100:
                chunk = chunk[:last_period + 1]
                end = start + last_period + 1

        chunks.append(chunk.strip())

        # Overlap
        start = end - overlap

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

    from app.modules.model_manager import generate_response

    # 🔹 Step 1: medium chunks (NOT FAISS chunks)
    summary_chunks = chunk_text(text, chunk_size=1500, overlap=200)

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
            summary = generate_response("", prompt, model_name=model_name)
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
    from app.modules.faiss_store import add_doc

    print(f"Ingesting: {file_path}")

    text = extract_text_from_pdf(file_path)
    if not text.strip():
        print("No text found in PDF")
        return

    # Step 1: generate summary using parallel summarization
    summarize_pdf(text, file_path, model_name=model_name)

    # Step 2: chunk text for FAISS
    chunks = chunk_text(text)
    for chunk in chunks:
        add_doc(chunk, source=file_path)

    print(f"✅ Ingested {len(chunks)} chunks + summary successfully")


def safe_summarize(text, pdf_path, model_name=None, chunk_index=None):
    """
    Summarize text safely within model context window.
    """
    from app.modules.model_manager import generate_response

    max_chunk_len = 1500
    text_chunks = [text[i:i+max_chunk_len] for i in range(0, len(text), max_chunk_len)]

    summaries = []
    for idx, chunk in enumerate(text_chunks):
        prompt = f"Summarize this document concisely in English:\n\n{chunk}\n\nSummary:"
        print(f"🔹 Summarizing sub-chunk {idx+1}/{len(text_chunks)} of chunk {chunk_index if chunk_index is not None else 'N/A'}")
        summary = generate_response("", prompt, model_name=model_name)
        summaries.append(summary.strip())

    return " ".join(summaries)


def combine_summaries(summaries, model_name=None):
    from app.modules.model_manager import generate_response

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
                summary = generate_response("", prompt, model_name=model_name)
                new_summaries.append(summary)
            except Exception as e:
                print(f"❌ Combine error: {e}")
                new_summaries.append("")

        summaries = new_summaries

    return summaries[0] if summaries else ""


