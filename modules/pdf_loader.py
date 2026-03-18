import os
from pdfminer.high_level import extract_text
from config import ROOT_FOLDER

CHUNK_SIZE = 600

def split_text(text):
    chunks = []
    start = 0
    while start < len(text):
        chunks.append(text[start:start + CHUNK_SIZE])
        start += CHUNK_SIZE
    return chunks

def extract_metadata(path):
    # Get relative path from root to identify Class and Subject
    rel_path = os.path.relpath(path, ROOT_FOLDER)
    parts = rel_path.split(os.sep)
    
    # parts[0] is 'Class 8', parts[1] is 'Mathematics' or 'English'
    metadata = {
        "file": os.path.basename(path),
        "path": path,
        "class": parts[0] if len(parts) > 0 else "Unknown",
        "subject": parts[1] if len(parts) > 1 else "General"
    }
    return metadata

def load_pdf_chunks(path):
    try:
        text = extract_text(path)
        if not text:
            return []
        meta = extract_metadata(path)
        chunks = split_text(text)
        return [{"text": c, "metadata": meta} for c in chunks]
    except Exception as e:
        print(f"Error loading {path}: {e}")
        return []