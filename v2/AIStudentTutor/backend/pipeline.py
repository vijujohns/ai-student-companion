import os
import torch
import pdfplumber
import numpy as np
from sentence_transformers import SentenceTransformer
from transformers import BlipProcessor, BlipForConditionalGeneration
from backend.faiss_store import FaissStore
from utils.metadata_utils import generate_metadata
from backend.flashcards import generate_flashcards
from backend.quiz_generator import generate_quiz
from backend.multilingual import translate_text

device = "cpu"

# Models
text_model = SentenceTransformer('all-MiniLM-L6-v2', device=device)
processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
image_model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base").to(device)

# FAISS
DIM_TEXT = 384
DIM_IMAGE = 768
faiss_index_file = "data/faiss_index/index.faiss"

text_store = FaissStore(dim=DIM_TEXT, index_file=faiss_index_file)
image_store = FaissStore(dim=DIM_IMAGE, index_file="data/faiss_index/image_index.faiss")

# ---------------------------
# PDF ingestion
# ---------------------------
def ingest_pdf(file_path, class_name, subject, chapter, type_="Textbook"):
    text_chunks, images = [], []

    with pdfplumber.open(file_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            for j, line in enumerate(text.split("\n")):
                chunk_id = f"{class_name}_{subject}_{chapter}_{type_}_{i}_{j}"
                metadata = generate_metadata(class_name, subject, chapter, type_, chunk_id)
                text_chunks.append({"text": line, "metadata": metadata})

            for img_idx, img in enumerate(page.images):
                chunk_id = f"{class_name}_{subject}_{chapter}_{type_}_{i}_img{img_idx}"
                metadata = generate_metadata(class_name, subject, chapter, type_, chunk_id)
                images.append({"image_obj": page.to_image(resolution=150).original, "metadata": metadata})

    return text_chunks, images

# ---------------------------
# Embeddings
# ---------------------------
def embed_text_list(text_list, batch_size=32):
    embeddings = []
    for i in range(0, len(text_list), batch_size):
        batch = text_list[i:i+batch_size]
        emb = text_model.encode(batch, convert_to_tensor=True)
        embeddings.append(emb.cpu().numpy())
    return np.vstack(embeddings)

def embed_image_list(images):
    embeddings = []
    for item in images:
        pixel_values = processor(images=item["image_obj"], return_tensors="pt").pixel_values
        pixel_values = pixel_values.to(device)
        with torch.no_grad():
            features = image_model(pixel_values=pixel_values)
            emb = features.last_hidden_state.mean(dim=1).cpu().numpy()
            embeddings.append(emb[0])
    return np.array(embeddings)

# ---------------------------
# Build FAISS index
# ---------------------------
def build_faiss_index(knowledge_base_path="knowledge_base"):
    for class_name in os.listdir(knowledge_base_path):
        class_path = os.path.join(knowledge_base_path, class_name)
        if not os.path.isdir(class_path):
            continue
        for subject in os.listdir(class_path):
            subject_path = os.path.join(class_path, subject)
            if not os.path.isdir(subject_path):
                continue
            for chapter_type in os.listdir(subject_path):
                chapter_path = os.path.join(subject_path, chapter_type)
                if not os.path.isdir(chapter_path):
                    continue
                for pdf_file in os.listdir(chapter_path):
                    if pdf_file.lower().endswith(".pdf"):
                        pdf_path = os.path.join(chapter_path, pdf_file)
                        chapter_name = pdf_file.replace(".pdf", "")
                        print(f"Ingesting PDF: {pdf_path}")
                        text_chunks, images = ingest_pdf(pdf_path, class_name, subject, chapter_name, type_=chapter_type)

                        if text_chunks:
                            text_embeddings = embed_text_list([c["text"] for c in text_chunks])
                            text_store.add_embeddings(text_embeddings)
                        if images:
                            img_embeddings = embed_image_list(images)
                            image_store.add_embeddings(img_embeddings)

    text_store.save()
    image_store.save()
    print("FAISS index built successfully!")

# ---------------------------
# RAG Orchestrator
# ---------------------------
class RAGOrchestrator:
    def __init__(self, text_store, image_store):
        self.text_store = text_store
        self.image_store = image_store

    def query(self, question, top_k=5, step_by_step=False, language="English"):
        q_emb = embed_text_list([question])[0]
        idxs, scores = self.text_store.search(q_emb, top_k=top_k)
        retrieved_chunks = [self.text_store.get_text(i) for i in idxs]

        answer = "\n".join(retrieved_chunks)

        if step_by_step:
            steps = [
                "Step 1: Understand the problem",
                "Step 2: Extract known values",
                "Step 3: Apply formulas",
                "Step 4: Solve equations",
                "Step 5: Final answer"
            ]
            answer = "\n".join(steps) + "\n\nContext:\n" + answer

        if language != "English":
            answer = translate_text(answer, target_lang=language)

        return answer

# ---------------------------
# Flashcards & quizzes
# ---------------------------
def generate_chapter_flashcards(knowledge_base_path="knowledge_base"):
    flashcards = []
    for class_name in os.listdir(knowledge_base_path):
        class_path = os.path.join(knowledge_base_path, class_name)
        for subject in os.listdir(class_path):
            subject_path = os.path.join(class_path, subject)
            for chapter_type in os.listdir(subject_path):
                chapter_path = os.path.join(subject_path, chapter_type)
                for pdf_file in os.listdir(chapter_path):
                    if pdf_file.lower().endswith(".pdf"):
                        pdf_path = os.path.join(chapter_path, pdf_file)
                        text_chunks, _ = ingest_pdf(pdf_path, class_name, subject, pdf_file.replace(".pdf", ""), type_=chapter_type)
                        flashcards.extend(generate_flashcards(text_chunks))
    return flashcards

def generate_chapter_quiz(knowledge_base_path="knowledge_base"):
    quiz = []
    for class_name in os.listdir(knowledge_base_path):
        class_path = os.path.join(knowledge_base_path, class_name)
        for subject in os.listdir(class_path):
            subject_path = os.path.join(subject_path, subject)
            for chapter_type in os.listdir(subject_path):
                chapter_path = os.path.join(subject_path, chapter_type)
                for pdf_file in os.listdir(chapter_path):
                    if pdf_file.lower().endswith(".pdf"):
                        pdf_path = os.path.join(chapter_path, pdf_file)
                        text_chunks, _ = ingest_pdf(pdf_path, class_name, subject, pdf_file.replace(".pdf", ""), type_=chapter_type)
                        quiz.extend(generate_quiz(text_chunks))
    return quiz

# ---------------------------
# Main execution
# ---------------------------
if __name__ == "__main__":
    print("Building FAISS index from knowledge base...")
    build_faiss_index()
    print("RAG pipeline ready. You can now use RAGOrchestrator for queries.")