import os
from pathlib import Path
from fpdf import FPDF
from PIL import Image, ImageDraw, ImageFont

# Base project directory
BASE_DIR = "AIStudentTutor"

# Folder structure
folders = [
    f"{BASE_DIR}/knowledge_base/Class-10/Math/Textbooks",
    f"{BASE_DIR}/knowledge_base/Class-10/Math/Notes",
    f"{BASE_DIR}/knowledge_base/Class-10/Math/QuestionPapers",
    f"{BASE_DIR}/knowledge_base/Class-10/Physics/Textbooks",
    f"{BASE_DIR}/knowledge_base/Class-10/Physics/Notes",
    f"{BASE_DIR}/knowledge_base/Class-11/Hindi/Textbooks",
    f"{BASE_DIR}/backend",
    f"{BASE_DIR}/frontend",
    f"{BASE_DIR}/data/faiss_index",
    f"{BASE_DIR}/data/embeddings",
    f"{BASE_DIR}/data/saved_results",
    f"{BASE_DIR}/utils",
]

# Files and their initial content (same as previous script)
# Files and their initial content
files_content = {
    f"{BASE_DIR}/main.py": """from frontend.gui import launch_gui

if __name__ == "__main__":
    launch_gui()
""",

    f"{BASE_DIR}/requirements.txt": """PyQt5
pdfplumber
sentence-transformers
faiss-cpu
torch
transformers
googletrans==4.0.0rc1
Pillow
""",

    f"{BASE_DIR}/README.md": """# AI Student Tutor

## Setup
1. Install dependencies:
    pip install -r requirements.txt
2. Launch the system:
    python main.py
3. Place PDFs in `knowledge_base/` as per Class → Subject → Chapter structure.

## Features
- Multi-class, multi-subject, chapter-level content
- PDF ingestion (text + images)
- FAISS vector store for text + image embeddings
- RAG-based query answering
- Step-by-step solution for Math/Physics/Chemistry
- Multilingual support: English/Hindi/Sanskrit
- Flashcards, quizzes, summaries
- Progress tracking
- Model selection
- Placeholder content generation (images/videos)
""",

    # Backend
    f"{BASE_DIR}/backend/__init__.py": "",
    f"{BASE_DIR}/backend/pdf_ingestion.py": """import pdfplumber
from utils.metadata_utils import generate_metadata

def extract_pdf(file_path, class_name, subject, chapter, type_):
    text_chunks = []
    images = []

    with pdfplumber.open(file_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            for j, line in enumerate(text.split("\\n")):
                chunk_id = f"{class_name}_{subject}_{chapter}_{i}_{j}"
                metadata = generate_metadata(class_name, subject, chapter, type_, chunk_id)
                text_chunks.append({ "text": line, "metadata": metadata })

            for img_idx, img in enumerate(page.images):
                images.append({ "image_obj": img, "metadata": metadata })

    return text_chunks, images
""",

    f"{BASE_DIR}/backend/embeddings.py": """from sentence_transformers import SentenceTransformer
from transformers import BlipProcessor, BlipForConditionalGeneration
import torch

text_model = SentenceTransformer('all-MiniLM-L6-v2')
processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
image_model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")

def embed_text(text_list):
    return text_model.encode(text_list, convert_to_tensor=True)

def embed_image(image):
    pixel_values = processor(images=image, return_tensors="pt").pixel_values
    with torch.no_grad():
        features = image_model(pixel_values=pixel_values)
    return features.last_hidden_state.mean(dim=1)
""",

    f"{BASE_DIR}/backend/faiss_store.py": """import faiss
import numpy as np
import os

class FaissStore:
    def __init__(self, dim, index_file="data/faiss_index/index.faiss"):
        self.dim = dim
        self.index_file = index_file
        self.index = faiss.IndexFlatL2(dim)
        if os.path.exists(index_file):
            self.index = faiss.read_index(index_file)

    def add_embeddings(self, embeddings):
        self.index.add(np.array(embeddings).astype('float32'))

    def save(self):
        faiss.write_index(self.index, self.index_file)

    def search(self, query_emb, top_k=5):
        D, I = self.index.search(np.array([query_emb]).astype('float32'), top_k)
        return I, D
""",

    f"{BASE_DIR}/backend/rag_orchestrator.py": """from backend.faiss_store import FaissStore
from backend.embeddings import embed_text
from backend.step_by_step import solve_problem
from backend.multilingual import translate_text

class RAGOrchestrator:
    def __init__(self, faiss_store):
        self.store = faiss_store

    def query(self, question, class_name, subject, chapter, language="English", step_by_step=False):
        q_emb = embed_text([question])[0]
        idx, scores = self.store.search(q_emb)
        retrieved_texts = [f"Chunk {i}" for i in idx]  # placeholder
        answer = " ".join(retrieved_texts)

        if step_by_step and subject in ["Math", "Physics", "Chemistry"]:
            answer = solve_problem(question, retrieved_texts)

        if language != "English":
            answer = translate_text(answer, target_lang=language)

        return answer
""",

    f"{BASE_DIR}/backend/step_by_step.py": """def solve_problem(question, context_chunks):
    solution_steps = [
        "Step 1: Understand the problem",
        "Step 2: Extract known values",
        "Step 3: Apply formulas",
        "Step 4: Solve equations",
        "Step 5: Final answer"
    ]
    return "\\n".join(solution_steps)
""",

    f"{BASE_DIR}/backend/multilingual.py": """from googletrans import Translator

translator = Translator()

def detect_language(text):
    return translator.detect(text).lang

def translate_text(text, target_lang="en"):
    return translator.translate(text, dest=target_lang).text
""",

    f"{BASE_DIR}/backend/flashcards.py": """def generate_flashcards(text_chunks):
    flashcards = []
    for chunk in text_chunks:
        flashcards.append({
            "question": chunk["text"],
            "answer": "..."  # placeholder
        })
    return flashcards
""",

    f"{BASE_DIR}/backend/quiz_generator.py": """def generate_quiz(text_chunks):
    quiz = []
    for chunk in text_chunks[:5]:
        quiz.append({
            "question": chunk["text"],
            "options": ["Option A", "Option B", "Option C", "Option D"],
            "answer": "Option A"
        })
    return quiz
""",

    f"{BASE_DIR}/backend/content_generator.py": """def generate_image_content(prompt):
    return "image_placeholder.png"

def generate_video_content(prompt):
    return "video_placeholder.mp4"
""",

    f"{BASE_DIR}/backend/progress_tracker.py": """import json
import os

SAVE_FILE = "data/saved_results/progress.json"

def load_progress():
    if os.path.exists(SAVE_FILE):
        with open(SAVE_FILE, "r") as f:
            return json.load(f)
    return {}

def save_progress(student_id, progress):
    data = load_progress()
    data[student_id] = progress
    with open(SAVE_FILE, "w") as f:
        json.dump(data, f, indent=4)
""",

    f"{BASE_DIR}/backend/model_manager.py": """class ModelManager:
    def __init__(self):
        self.available_models = ["LLaMA-7B", "Math-specialized", "Hindi-specialized"]

    def get_models(self):
        return self.available_models

    def select_model(self, model_name):
        if model_name in self.available_models:
            return model_name
        return None
""",

    # Frontend
    f"{BASE_DIR}/frontend/__init__.py": "",
    f"{BASE_DIR}/frontend/gui.py": """import sys
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QTextEdit, QLabel, QComboBox

def launch_gui():
    app = QApplication(sys.argv)
    window = QWidget()
    window.setWindowTitle("AI Student Tutor")

    layout = QVBoxLayout()

    layout.addWidget(QLabel("Select Class"))
    class_dropdown = QComboBox()
    class_dropdown.addItems(["Class-10", "Class-11"])
    layout.addWidget(class_dropdown)

    layout.addWidget(QLabel("Select Subject"))
    subject_dropdown = QComboBox()
    subject_dropdown.addItems(["Math", "Physics", "Hindi"])
    layout.addWidget(subject_dropdown)

    layout.addWidget(QLabel("Enter Question"))
    question_input = QTextEdit()
    layout.addWidget(question_input)

    answer_display = QTextEdit()
    layout.addWidget(answer_display)

    def on_ask():
        answer_display.setText("Answer will appear here...")

    ask_btn = QPushButton("Ask")
    ask_btn.clicked.connect(on_ask)
    layout.addWidget(ask_btn)

    window.setLayout(layout)
    window.show()
    sys.exit(app.exec_())
""",

    f"{BASE_DIR}/frontend/pdf_viewer.py": """# Placeholder for PDF viewer
""",
    f"{BASE_DIR}/frontend/answer_panel.py": """# Placeholder for answer panel
""",
    f"{BASE_DIR}/frontend/flashcard_panel.py": """# Placeholder for flashcard panel
""",
    f"{BASE_DIR}/frontend/quiz_panel.py": """# Placeholder for quiz panel
""",
    f"{BASE_DIR}/frontend/progress_dashboard.py": """# Placeholder for progress dashboard
""",

    # Utils
    f"{BASE_DIR}/utils/__init__.py": "",
    f"{BASE_DIR}/utils/file_utils.py": """import os

def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)
""",
    f"{BASE_DIR}/utils/metadata_utils.py": """def generate_metadata(class_name, subject, chapter, type_, chunk_id):
    return {
        "class": class_name,
        "subject": subject,
        "chapter": chapter,
        "type": type_,
        "chunk_id": chunk_id,
        "language": "English",
        "step_by_step": subject in ["Math", "Physics", "Chemistry"]
    }
""",
    f"{BASE_DIR}/utils/logger.py": """import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AIStudentTutor")
"""
}

# Create folders
for folder in folders:
    os.makedirs(folder, exist_ok=True)

# Create files with content
for file_path, content in files_content.items():
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

print(f"Folder structure and code files created under '{BASE_DIR}'.")

# -----------------------------
# Create sample PDFs
# -----------------------------
def create_sample_pdf(file_path, text="Sample content for testing AI Student Tutor PDF ingestion."):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.multi_cell(0, 10, text)
    pdf.output(file_path)
    print(f"Sample PDF created: {file_path}")

# Paths for sample PDFs
sample_pdfs = [
    f"{BASE_DIR}/knowledge_base/Class-10/Math/Textbooks/Chapter1.pdf",
    f"{BASE_DIR}/knowledge_base/Class-10/Math/Notes/Week1.pdf",
    f"{BASE_DIR}/knowledge_base/Class-10/Math/QuestionPapers/2023_Midterm.pdf",
    f"{BASE_DIR}/knowledge_base/Class-10/Physics/Textbooks/Chapter1.pdf",
    f"{BASE_DIR}/knowledge_base/Class-10/Physics/Notes/Week1.pdf",
    f"{BASE_DIR}/knowledge_base/Class-11/Hindi/Textbooks/Chapter1.pdf",
]

for pdf_path in sample_pdfs:
    create_sample_pdf(pdf_path)

# -----------------------------
# Create placeholder images
# -----------------------------
def create_placeholder_image(file_path, text="Placeholder Image", size=(200, 200)):
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new('RGB', size, color=(200, 200, 200))
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 15)
    except:
        font = ImageFont.load_default()
    
    # Use textbbox to get text size
    bbox = d.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    x = (size[0] - text_width) / 2
    y = (size[1] - text_height) / 2
    d.text((x, y), text, fill=(0, 0, 0), font=font)
    img.save(file_path)
    print(f"Placeholder image created: {file_path}")

    
sample_images = [
    f"{BASE_DIR}/knowledge_base/Class-10/Math/Textbooks/image1.png",
    f"{BASE_DIR}/knowledge_base/Class-10/Physics/Textbooks/image1.png",
    f"{BASE_DIR}/knowledge_base/Class-11/Hindi/Textbooks/image1.png",
]

for img_path in sample_images:
    create_placeholder_image(img_path)

print("Sample PDFs and placeholder images created successfully!")