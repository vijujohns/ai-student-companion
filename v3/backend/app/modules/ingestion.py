"""
Handles PDF ingestion → chunking → FAISS storage
"""

from pypdf import PdfReader
from tqdm import tqdm


def extract_text_from_pdf(file_path):
    """
    Extract text from PDF file
    """
    reader = PdfReader(file_path)
    text = ""

    for page in reader.pages:
        text += page.extract_text() or ""

    return text


def chunk_text(text, chunk_size=500):
    """
    Split text into smaller chunks
    """
    chunks = []
    start = 0

    while start < len(text):
        chunks.append(text[start:start + chunk_size])
        start += chunk_size

    return chunks


def ingest_pdf(file_path):
    """
    Full ingestion pipeline
    """
    from app.modules.faiss_store import add_doc  # ✅ FIX HERE

    print(f"Ingesting: {file_path}")

    text = extract_text_from_pdf(file_path)

    if not text.strip():
        print("No text found in PDF")
        return

    chunks = chunk_text(text)

    for chunk in chunks:
        add_doc(chunk)

    print(f"Ingested {len(chunks)} chunks successfully")