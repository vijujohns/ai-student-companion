import streamlit as st
import os, base64
from modules.vector_db import load_database, search, build_database
from modules.llm_engine import ask_llm
from config import ROOT_FOLDER

st.set_page_config(page_title="AI Student Companion Pro", layout="wide")

# --- Persistent Database Loading ---
if "db_index" not in st.session_state:
    try:
        st.session_state.db_index, st.session_state.db_data = load_database()
    except:
        st.session_state.db_index, st.session_state.db_data = None, None

def get_pdf_html(path):
    if not path or not os.path.exists(path): return ""
    with open(path, "rb") as f:
        base64_pdf = base64.b64encode(f.read()).decode('utf-8')
    return f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="850px"></iframe>'

# --- Sidebar Configuration ---
with st.sidebar:
    st.title("📂 Study Hub")
    
    classes = sorted([d for d in os.listdir(ROOT_FOLDER) if os.path.isdir(os.path.join(ROOT_FOLDER, d))])
    sel_class = st.selectbox("Class", classes)
    
    subj_path = os.path.join(ROOT_FOLDER, sel_class)
    subjects = sorted([d for d in os.listdir(subj_path) if os.path.isdir(os.path.join(subj_path, d))])
    sel_subj = st.selectbox("Subject", subjects)
    
    # RECURSIVE SEARCH: Finds PDFs in any subfolder like 'Text Books/QR0849'
    target_dir = os.path.join(subj_path, sel_subj)
    pdf_map = {}
    for root, _, files in os.walk(target_dir):
        for f in files:
            if f.endswith(".pdf"):
                pdf_map[f] = os.path.join(root, f)
    
    chapter_list = ["All Chapters"] + sorted(list(pdf_map.keys()))
    sel_chap = st.selectbox("Chapter", chapter_list)
    
    st.divider()
    if st.button("🔄 Rebuild Knowledge Base", use_container_width=True):
        with st.status("Indexing Files...", expanded=True) as status:
            st.session_state.db_index, st.session_state.db_data = build_database()
            status.update(label="Index Complete!", state="complete", expanded=False)
        st.success("Rebuild successful!")

# --- Main Layout ---
col_chat, col_view = st.columns([1, 1])

with col_chat:
    st.subheader("💬 AI Tutor")
    
    # Map button labels to specific AI instructions and search terms
    prompt_map = {
        "Summary": ("Summarise this chapter for me.", "introduction summary main points"),
        "Key Takeaways": ("What are the key takeaways from this chapter?", "concepts summary highlights"),
        "Lesson Plan": ("Create a structured lesson plan for this chapter.", "syllabus objectives topics"),
        "Exercise Help": ("Help me solve the exercise questions with step-by-step logic.", "exercises questions problems"),
        "Real Examples": ("Explain these concepts using real-world examples.", "application daily life examples"),
        "Guided Tutor": ("Act as a tutor and teach me this chapter concept by concept.", "basics definitions introduction")
    }
    
    clicked_action = None
    c1, c2 = st.columns(2)
    for i, (label, values) in enumerate(prompt_map.items()):
        if (c1 if i % 2 == 0 else c2).button(label, use_container_width=True):
            clicked_action = values

    user_input = st.chat_input("Ask a specific question...")
    
    # Determine the query
    final_query, search_key = ("", "")
    if clicked_action:
        final_query, search_key = clicked_action
    elif user_input:
        final_query, search_key = user_input, user_input

    if final_query:
        with st.spinner("AI is studying your textbook..."):
            filters = {"class": sel_class, "subject": sel_subj, "chapter": sel_chap}
            results = search(search_key, st.session_state.db_index, st.session_state.db_data, filters=filters)
            
            if results:
                context = "\n".join([r["text"] for r in results[:12]])
                ans = ask_llm(final_query, context)
                st.markdown(f"### Result")
                st.markdown(ans)
                st.session_state.view_path = results[0]["metadata"]["path"]
            else:
                st.warning("No context found. Try rebuilding the index or choosing 'All Chapters'.")

with col_view:
    st.subheader("📄 Textbook View")
    # Priority: Explicit chapter selection > AI's found context
    path = pdf_map.get(sel_chap) if sel_chap != "All Chapters" else st.session_state.get("view_path")
    if path:
        st.markdown(get_pdf_html(path), unsafe_allow_html=True)
    else:
        st.info("Select a chapter to open the viewer.")