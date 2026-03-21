import os
from app.modules.pdf_processor import extract_text
from app.modules.embedding import embed_batch
from app.modules.vector_store import add_embeddings

CHUNK_SIZE = 500
CHUNK_OVERLAP = 100


def chunk_text(text):
    chunks = []
    start = 0

    while start < len(text):
        end = start + CHUNK_SIZE
        chunks.append(text[start:end])
        start += CHUNK_SIZE - CHUNK_OVERLAP

    return chunks


def index_documents(root_path="app/data"):
    all_chunks = []
    all_metadata = []

    print("📂 Scanning curriculum folders...")

    for class_name in os.listdir(root_path):
        class_path = os.path.join(root_path, class_name)
        if not os.path.isdir(class_path):
            continue

        for subject_name in os.listdir(class_path):
            subject_path = os.path.join(class_path, subject_name)
            if not os.path.isdir(subject_path):
                continue

            for chapter_name in os.listdir(subject_path):
                chapter_path = os.path.join(subject_path, chapter_name)
                if not os.path.isdir(chapter_path):
                    continue

                for file_name in os.listdir(chapter_path):
                    if not file_name.lower().endswith(".pdf"):
                        continue

                    file_path = os.path.join(chapter_path, file_name)

                    print(f"📄 Processing: {file_path}")

                    pages = extract_text(file_path)

                    for page_number, page_text in enumerate(pages):
                        if not page_text.strip():
                            continue

                        chunks = chunk_text(page_text)

                        for chunk in chunks:
                            all_chunks.append(chunk)
                            all_metadata.append({
                                "text": chunk,
                                "class": class_name,
                                "subject": subject_name,
                                "chapter": chapter_name,
                                "source": file_name,
                                "page": page_number
                            })

    if not all_chunks:
        raise Exception("No content found to index")

    print(f"🧠 Creating embeddings for {len(all_chunks)} chunks...")
    vectors = embed_batch(all_chunks)

    print("💾 Storing in FAISS...")
    add_embeddings(vectors, all_metadata)

    print("✅ Indexing completed successfully")


def index_all():
    index_documents()