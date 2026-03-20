from PyPDF2 import PdfReader


def extract_text(pdf_path):
    reader = PdfReader(pdf_path)
    pages = []

    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text)
        else:
            pages.append("")

    return pages