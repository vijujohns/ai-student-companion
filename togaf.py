from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, Flowable
from reportlab.graphics.shapes import Drawing, Rect, String, Line
from io import BytesIO
from PIL import Image as PILImage, ImageDraw, ImageFont

# -----------------------
# PDF Setup
# -----------------------
pdf_file = "AI_Student_Tutor_Full_Solution_Design.pdf"
doc = SimpleDocTemplate(pdf_file, pagesize=A4,
                        rightMargin=30, leftMargin=30,
                        topMargin=30, bottomMargin=30)
elements = []

# -----------------------
# Styles
# -----------------------
styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name='CustomHeading1', fontSize=18, leading=22, spaceAfter=10, spaceBefore=20, textColor=colors.darkblue))
styles.add(ParagraphStyle(name='CustomHeading2', fontSize=14, leading=18, spaceAfter=8, spaceBefore=12, textColor=colors.darkred))
styles.add(ParagraphStyle(name='CustomNormal', fontSize=11, leading=14, spaceAfter=6))

# -----------------------
# Helper functions
# -----------------------
def add_heading(text, level=1):
    if level == 1:
        elements.append(Paragraph(text, styles['CustomHeading1']))
    else:
        elements.append(Paragraph(text, styles['CustomHeading2']))

def add_paragraph(text):
    elements.append(Paragraph(text, styles['CustomNormal']))

def add_spacer(height=10):
    elements.append(Spacer(1, height))

def add_table(data, col_widths=None):
    table = Table(data, colWidths=col_widths)
    style = TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.lightblue),
        ('TEXTCOLOR',(0,0),(-1,0),colors.white),
        ('ALIGN',(0,0),(-1,-1),'LEFT'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1, -1), 10),
        ('BOTTOMPADDING', (0,0), (-1,0), 8),
        ('BACKGROUND',(0,1),(-1,-1),colors.whitesmoke),
        ('GRID',(0,0),(-1,-1),0.5,colors.grey)
    ])
    table.setStyle(style)
    elements.append(table)

def add_image_from_pil(pil_image, width=450, height=300):
    # Convert PIL image to BytesIO for reportlab
    img_byte_arr = BytesIO()
    pil_image.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    img = Image(img_byte_arr, width=width, height=height)
    elements.append(img)

# -----------------------
# Generate UI Mockup Image (PIL)
# -----------------------
def generate_ui_mockup():
    width, height = 800, 500
    img = PILImage.new('RGB', (width, height), color='white')
    draw = ImageDraw.Draw(img)
    
    # Optional: load a font
    try:
        font = ImageFont.truetype("arial.ttf", 18)
    except:
        font = ImageFont.load_default()
    
    # Draw header
    draw.rectangle([0,0,width,50], fill=(70,130,180))
    draw.text((10,10), "AI Student Tutor - UI Mockup", font=font, fill='white')
    
    # Left menu
    draw.rectangle([10,60,150,height-10], fill=(220,220,220))
    draw.text((20,70), "Class / Subject / Chapter\nMenu\n- Class 10\n- Science\n- Chapter 1", font=font, fill='black')
    
    # PDF Viewer area
    draw.rectangle([170,60,630,350], fill=(245,245,245), outline='black')
    draw.text((180,70), "PDF Viewer / Text Display Area", font=font, fill='black')
    
    # Q&A / Flashcards
    draw.rectangle([170,360,630,490], fill=(230,245,255), outline='black')
    draw.text((180,370), "Q&A / Flashcards / Step-by-step / Video/Image generation", font=font, fill='black')
    
    return img

# -----------------------
# Flowchart Class
# -----------------------
class Flowchart(Flowable):
    def __init__(self, width=500, height=300, boxes=[]):
        Flowable.__init__(self)
        self.width = width
        self.height = height
        self.boxes = boxes

    def draw(self):
        d = Drawing(self.width, self.height)
        for box in self.boxes:
            x, y, w, h, color, label = box
            d.add(Rect(x, y, w, h, strokeColor=colors.darkblue, fillColor=color))
            d.add(String(x+5, y+h/2-5, label, fontSize=10))
        for i in range(len(self.boxes)-1):
            x1, y1, w1, h1, _, _ = self.boxes[i]
            x2, y2, w2, h2, _, _ = self.boxes[i+1]
            d.add(Line(x1+w1, y1+h1/2, x2, y2+h2/2, strokeColor=colors.black))
        d.drawOn(self.canv, 0, 0)

# -----------------------
# Document Content
# -----------------------
add_heading("AI Student Tutor – Solution Design Document", level=1)
add_spacer(20)

# Executive Summary
add_heading("1. Executive Summary")
add_paragraph("Purpose: Develop a modular, multilingual, multimodal AI tutor for students, capable of providing grounded answers, step-by-step explanations, flashcards, quizzes, content generation (videos/images), progress tracking, and modular model selection.")
add_paragraph("Scope: Classes (multi-class), Subjects (multi-subject), Chapters, Features (Q&A, PDF viewer, flashcards, step-by-step, translation, quizzes, videos/images), Deployment: local Windows 11 CPU-based system.")
add_paragraph("Target Audience: Students, educators, and curriculum administrators.")
add_spacer(10)

# Functional Requirements Table
add_heading("2. Functional Requirements")
func_req_data = [
    ["ID","Requirement","Description"],
    ["FR1","Multi-class / subject / chapter support","Student selects class → subject → chapter"],
    ["FR2","PDF ingestion","Import textbooks, notes, question papers with text + images"],
    ["FR3","Text retrieval","Retrieve relevant text chunks per query"],
    ["FR4","Image comprehension","Extract diagrams/images and provide explanations"],
    ["FR5","Multilingual support","Detect Hindi/Sanskrit/English; translate to English"],
    ["FR6","Step-by-step explanations","Sequential guidance for Math, Physics, Chemistry problems"],
    ["FR7","Flashcards generation","Text + image flashcards per chapter"],
    ["FR8","Question paper summary","Topic/difficulty summary for past papers"],
    ["FR9","Knowledge testing","Generate quizzes (MCQ, short answers, fill-in-the-blank)"],
    ["FR10","Content generation","Short videos & image-based study aids"],
    ["FR11","Model selection & modularity","Add new models; student selects model per query"],
    ["FR12","Save & retrieve results","Store answers, flashcards, videos tagged by class/subject/chapter"],
    ["FR13","Progress tracker","Dashboard with chapters completed, quizzes, flashcards reviewed"],
    ["FR14","PDF viewer","Inline display of PDFs with image highlighting"]
]
add_table(func_req_data)

# Non-functional Requirements Table
add_heading("3. Non-Functional Requirements")
nfr_data = [
    ["ID","Requirement","Description"],
    ["NFR1","Performance","Text Q&A <6s; step-by-step <8s; video/image generation <30s"],
    ["NFR2","Scalability","Add classes, subjects, PDFs, or models without code changes"],
    ["NFR3","Availability","Offline-capable local deployment"],
    ["NFR4","Reliability","Persistent storage for FAISS, saved results"],
    ["NFR5","Usability","User-friendly GUI, PDF viewer, progress dashboard"],
    ["NFR6","Maintainability","Modular backend, model-agnostic pipelines"],
    ["NFR7","Security","Local execution; optional access control for student data"],
    ["NFR8","Accuracy","Grounded answers with citations, verified translations, step-by-step correctness"]
]
add_table(nfr_data)
add_spacer(10)

# Architecture Diagram Flowchart
add_heading("4. Architecture Diagram (Vector Flowchart)")
boxes_arch = [
    (50, 200, 120, 50, colors.lightblue, "Knowledge Base"),
    (200, 200, 120, 50, colors.lightgreen, "PDF Ingestion"),
    (350, 200, 120, 50, colors.orange, "Embedding/FAISS"),
    (500, 200, 120, 50, colors.pink, "RAG Orchestrator"),
    (650, 200, 120, 50, colors.yellow, "Backend Modules")
]
elements.append(Flowchart(width=700, height=300, boxes=boxes_arch))
add_spacer(20)

# UI Mockup Image
add_heading("5. UI Mockups")
mockup_img = generate_ui_mockup()
add_image_from_pil(mockup_img, width=450, height=300)

# System / Hardware Requirements Table
add_heading("6. System / Hardware Requirements")
sys_req_data = [
    ["Component","Requirement"],
    ["Hardware","Windows 11, i5 CPU, 16GB RAM, 250GB storage minimum"],
    ["Backend Software","Python 3.10+, FAISS, PyPDF2/pdfplumber, BLIP-2 / OpenCLIP"],
    ["LLM","LLaMA 2 7B Chat Q4_K (CPU quantized), Math-specialized, Hindi/Sanskrit models"],
    ["Frontend Software","PyQt / Tkinter / Electron"],
    ["Optional","GPU for faster video/image generation"]
]
add_table(sys_req_data)

# Optional Enhancements
add_heading("7. Optional Enhancements")
add_paragraph("- Precomputed flashcards & summaries")
add_paragraph("- Highlight images/diagrams in PDF viewer")
add_paragraph("- Asynchronous video/image generation")
add_paragraph("- Admin-configurable model selection per subject/language")
add_paragraph("- Line-by-line translation for Hindi/Sanskrit")
add_paragraph("- Analytics in progress tracker (heatmaps, chapter completion, quiz performance)")

# Key Benefits
add_heading("8. Key Benefits")
add_paragraph("- Modular, extensible architecture")
add_paragraph("- Grounded, accurate answers with citations")
add_paragraph("- Step-by-step guidance for problem-solving subjects")
add_paragraph("- Multilingual support with translation")
add_paragraph("- Flashcards, quizzes, videos, infographics for active learning")
add_paragraph("- Progress tracking & analytics")
add_paragraph("- Offline-capable, suitable for Windows 11 i5 setup")

# Build PDF
doc.build(elements)
print(f"PDF successfully generated: {pdf_file}")