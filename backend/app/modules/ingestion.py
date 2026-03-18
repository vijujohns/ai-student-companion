from PyPDF2 import PdfReader
from app.config import CHUNK_SIZE

documents = []

def extract_text(path):
    reader = PdfReader(path)
    return " ".join([p.extract_text() or "" for p in reader.pages])

def chunk(text):
    words = text.split()
    return [" ".join(words[i:i+CHUNK_SIZE]) for i in range(0, len(words), CHUNK_SIZE)]

def process_pdf(path):
    text = extract_text(path)
    chunks = chunk(text)
    for c in chunks:
        documents.append({"text": c, "source": path})
