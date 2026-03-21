
from PyPDF2 import PdfReader
import pytesseract
from pdf2image import convert_from_path
from app.core.config import CHUNK_SIZE

def extract_text(path):
    try:
        reader = PdfReader(path)
        return " ".join([p.extract_text() or "" for p in reader.pages])
    except:
        images = convert_from_path(path)
        return "".join([pytesseract.image_to_string(i) for i in images])

def chunk(text):
    words = text.split()
    return [" ".join(words[i:i+CHUNK_SIZE]) for i in range(0, len(words), CHUNK_SIZE)]
