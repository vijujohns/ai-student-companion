import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QComboBox, QTabWidget, QListWidget,
    QFileDialog, QProgressBar, QMessageBox
)
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QUrl

# Backend imports
from backend.pipeline import RAGOrchestrator, build_faiss_index, embed_text_list
from backend.flashcards import generate_flashcards
from backend.quiz_generator import generate_quiz
from backend.multilingual import translate_text
from backend.faiss_store import FaissStore

DIM_TEXT = 384
DIM_IMAGE = 768

# -----------------------------
# FAISS build thread for GUI
# -----------------------------
class FaissBuildThread(QThread):
    progress = pyqtSignal(str)

    def run(self):
        self.progress.emit("Building FAISS index...")
        try:
            build_faiss_index()
            self.progress.emit("FAISS index build completed.")
        except Exception as e:
            self.progress.emit(f"FAISS build error: {e}")

# -----------------------------
# Setup FAISS and RAG
# -----------------------------
if not os.path.exists("data/faiss_index/index.faiss"):
    print("FAISS index not found. Building index...")
    thread = FaissBuildThread()
    thread.start()
    thread.wait()

text_store = FaissStore(dim=DIM_TEXT, index_file="data/faiss_index/index.faiss")
image_store = FaissStore(dim=DIM_IMAGE, index_file="data/faiss_index/image_index.faiss")

rag = RAGOrchestrator(text_store, image_store)

# -----------------------------
# Tutor GUI
# -----------------------------
class TutorGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Student Tutor")
        self.setGeometry(50, 50, 1200, 800)
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        # Status bar
        self.status_label = QLabel("Ready")
        self.layout.addWidget(self.status_label)

        # Selection panel
        self.selection_layout = QHBoxLayout()
        self.layout.addLayout(self.selection_layout)

        self.class_combo = QComboBox()
        self.subject_combo = QComboBox()
        self.chapter_combo = QComboBox()
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Textbooks", "Notes", "QuestionPapers"])

        self.selection_layout.addWidget(QLabel("Class"))
        self.selection_layout.addWidget(self.class_combo)
        self.selection_layout.addWidget(QLabel("Subject"))
        self.selection_layout.addWidget(self.subject_combo)
        self.selection_layout.addWidget(QLabel("Chapter"))
        self.selection_layout.addWidget(self.chapter_combo)
        self.selection_layout.addWidget(QLabel("Type"))
        self.selection_layout.addWidget(self.type_combo)

        self.class_combo.currentIndexChanged.connect(self.load_subjects)
        self.subject_combo.currentIndexChanged.connect(self.load_chapters)

        # Question panel
        self.question_edit = QTextEdit()
        self.question_edit.setPlaceholderText("Enter your question here...")
        self.ask_button = QPushButton("Ask")
        self.ask_button.clicked.connect(self.ask_question)

        self.layout.addWidget(QLabel("Question"))
        self.layout.addWidget(self.question_edit)
        self.layout.addWidget(self.ask_button)

        # Answer display
        self.answer_edit = QTextEdit()
        self.answer_edit.setReadOnly(True)
        self.layout.addWidget(QLabel("Answer"))
        self.layout.addWidget(self.answer_edit)

        # PDF Viewer
        self.pdf_viewer = QWebEngineView()
        self.layout.addWidget(QLabel("PDF Viewer"))
        self.layout.addWidget(self.pdf_viewer)

        # Tabs
        self.tabs = QTabWidget()
        self.flashcard_list = QListWidget()
        self.quiz_list = QListWidget()
        self.progress_list = QListWidget()

        self.tabs.addTab(self.flashcard_list, "Flashcards")
        self.tabs.addTab(self.quiz_list, "Quizzes")
        self.tabs.addTab(self.progress_list, "Progress")
        self.layout.addWidget(self.tabs)

        # Language selection
        self.language_combo = QComboBox()
        self.language_combo.addItems(["English", "Hindi", "Sanskrit"])
        self.selection_layout.addWidget(QLabel("Language"))
        self.selection_layout.addWidget(self.language_combo)

        # Load classes / flashcards / quizzes
        self.load_classes()
        self.load_flashcards()
        self.load_quizzes()

    # -----------------------------
    # Load Classes / Subjects / Chapters
    # -----------------------------
    def load_classes(self):
        kb_path = "knowledge_base"
        if not os.path.exists(kb_path):
            QMessageBox.warning(self, "Warning", "Knowledge base not found!")
            return
        classes = [c for c in os.listdir(kb_path) if os.path.isdir(os.path.join(kb_path, c))]
        self.class_combo.clear()
        self.class_combo.addItems(classes)
        self.load_subjects()

    def load_subjects(self):
        class_name = self.class_combo.currentText()
        class_path = os.path.join("knowledge_base", class_name)
        if os.path.exists(class_path):
            subjects = [s for s in os.listdir(class_path) if os.path.isdir(os.path.join(class_path, s))]
        else:
            subjects = []
        self.subject_combo.clear()
        self.subject_combo.addItems(subjects)
        self.load_chapters()

    def load_chapters(self):
        class_name = self.class_combo.currentText()
        subject_name = self.subject_combo.currentText()
        type_name = self.type_combo.currentText()
        path = os.path.join("knowledge_base", class_name, subject_name, type_name)
        if os.path.exists(path):
            chapters = [f.replace(".pdf", "") for f in os.listdir(path) if f.endswith(".pdf")]
        else:
            chapters = []
        self.chapter_combo.clear()
        self.chapter_combo.addItems(chapters)
        if chapters:
            self.load_pdf(chapters[0])

    # -----------------------------
    # Load PDF
    # -----------------------------
    def load_pdf(self, chapter_name):
        class_name = self.class_combo.currentText()
        subject_name = self.subject_combo.currentText()
        type_name = self.type_combo.currentText()
        pdf_path = os.path.join("knowledge_base", class_name, subject_name, type_name, chapter_name + ".pdf")
        if os.path.exists(pdf_path):
            self.pdf_viewer.load(QUrl.fromLocalFile(os.path.abspath(pdf_path)))
            self.status_label.setText(f"Loaded PDF: {chapter_name}")
        else:
            self.status_label.setText(f"PDF not found: {chapter_name}")

    # -----------------------------
    # Ask question
    # -----------------------------
    def ask_question(self):
        question = self.question_edit.toPlainText()
        language = self.language_combo.currentText()
        if not question.strip():
            self.answer_edit.setText("Please enter a question.")
            return
        self.status_label.setText("Generating answer...")
        QApplication.processEvents()
        answer = rag.query(question, step_by_step=True, language=language)
        self.answer_edit.setText(answer)
        self.status_label.setText("Answer generated.")

    # -----------------------------
    # Flashcards / Quizzes
    # -----------------------------
    def load_flashcards(self):
        self.flashcard_list.clear()
        try:
            flashcards = generate_flashcards()
            for fc in flashcards:
                self.flashcard_list.addItem(fc)
        except Exception as e:
            self.status_label.setText(f"Flashcards load error: {e}")

    def load_quizzes(self):
        self.quiz_list.clear()
        try:
            quiz = generate_quiz()
            for q in quiz:
                self.quiz_list.addItem(q)
        except Exception as e:
            self.status_label.setText(f"Quiz load error: {e}")

# -----------------------------
# Run App
# -----------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    gui = TutorGUI()
    gui.show()
    sys.exit(app.exec_())