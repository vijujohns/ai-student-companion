import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QTextEdit, QComboBox, QFileDialog, QTabWidget, QListWidget
)
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt

from backend.pipeline import RAGOrchestrator, build_faiss_index
from backend.flashcards import generate_flashcards
from backend.quiz_generator import generate_quiz

# -----------------------------
# Initialize RAG
# -----------------------------
text_store_index = "data/faiss_index/index.faiss"
image_store_index = "data/faiss_index/image_index.faiss"
rag = RAGOrchestrator(None, None)  # Placeholder: we will connect actual FAISS later

# -----------------------------
# Main GUI
# -----------------------------
class TutorGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Student Tutor")
        self.setGeometry(100, 100, 1000, 700)

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        # -----------------
        # Selection Panel
        # -----------------
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

        self.load_classes()

        self.class_combo.currentIndexChanged.connect(self.load_subjects)
        self.subject_combo.currentIndexChanged.connect(self.load_chapters)

        # -----------------
        # Question Panel
        # -----------------
        self.question_edit = QTextEdit()
        self.question_edit.setPlaceholderText("Enter your question here...")
        self.ask_button = QPushButton("Ask")
        self.ask_button.clicked.connect(self.ask_question)

        self.layout.addWidget(QLabel("Question"))
        self.layout.addWidget(self.question_edit)
        self.layout.addWidget(self.ask_button)

        # -----------------
        # Answer Panel
        # -----------------
        self.answer_edit = QTextEdit()
        self.answer_edit.setReadOnly(True)
        self.layout.addWidget(QLabel("Answer"))
        self.layout.addWidget(self.answer_edit)

        # -----------------
        # Tabs: Flashcards / Quizzes / Progress
        # -----------------
        self.tabs = QTabWidget()
        self.flashcard_list = QListWidget()
        self.quiz_list = QListWidget()
        self.progress_list = QListWidget()

        self.tabs.addTab(self.flashcard_list, "Flashcards")
        self.tabs.addTab(self.quiz_list, "Quizzes")
        self.tabs.addTab(self.progress_list, "Progress")
        self.layout.addWidget(self.tabs)

        # -----------------
        # Load initial flashcards & quizzes
        # -----------------
        self.load_flashcards()
        self.load_quizzes()

    # -----------------------------
    # Load Classes / Subjects / Chapters
    # -----------------------------
    def load_classes(self):
        kb_path = "knowledge_base"
        classes = [c for c in os.listdir(kb_path) if os.path.isdir(os.path.join(kb_path, c))]
        self.class_combo.clear()
        self.class_combo.addItems(classes)
        self.load_subjects()

    def load_subjects(self):
        kb_path = os.path.join("knowledge_base", self.class_combo.currentText())
        subjects = [s for s in os.listdir(kb_path) if os.path.isdir(os.path.join(kb_path, s))]
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

    # -----------------------------
    # Ask Question
    # -----------------------------
    def ask_question(self):
        question = self.question_edit.toPlainText()
        if not question.strip():
            self.answer_edit.setText("Please enter a question.")
            return

        # Placeholder RAG response
        answer = rag.query(question, step_by_step=True, language="English")
        self.answer_edit.setText(answer)

    # -----------------------------
    # Load Flashcards & Quizzes
    # -----------------------------
    def load_flashcards(self):
        flashcards = generate_flashcards()  # placeholder: connect real data
        self.flashcard_list.clear()
        for fc in flashcards:
            self.flashcard_list.addItem(fc)

    def load_quizzes(self):
        quiz = generate_quiz()  # placeholder: connect real data
        self.quiz_list.clear()
        for q in quiz:
            self.quiz_list.addItem(q)

# -----------------------------
# Run Application
# -----------------------------
if __name__ == "__main__":
    # Build FAISS if not exists
    if not os.path.exists("data/faiss_index/index.faiss"):
        print("Building FAISS index...")
        build_faiss_index()

    app = QApplication(sys.argv)
    gui = TutorGUI()
    gui.show()
    sys.exit(app.exec_())