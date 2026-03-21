import pdfplumber
from utils.metadata_utils import generate_metadata

def extract_pdf(file_path, class_name, subject, chapter, type_):
    text_chunks = []
    images = []

    with pdfplumber.open(file_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            for j, line in enumerate(text.split("\n")):
                chunk_id = f"{class_name}_{subject}_{chapter}_{i}_{j}"
                metadata = generate_metadata(class_name, subject, chapter, type_, chunk_id)
                text_chunks.append({ "text": line, "metadata": metadata })

            for img_idx, img in enumerate(page.images):
                images.append({ "image_obj": img, "metadata": metadata })

    return text_chunks, images
