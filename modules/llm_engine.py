import ollama
import streamlit as st
from config import LLM_MODEL

@st.cache_data(show_spinner=False)
def ask_llm(question, context):
    """
    Forces the AI to extract data, verify it, and then solve using LaTeX.
    """
    prompt = f"""
You are a Mathematics Validator for CBSE Class 8. 

### STEP 1: EXTRACT
Identify the exact numbers and operators from the Textbook Context below. Do not invent numbers.

### STEP 2: VERIFY
Check the BODMAS rules for the expression. 
- Brackets first
- Orders (powers)
- Division/Multiplication (left to right)
- Addition/Subtraction (left to right)

### STEP 3: SOLVE
Show the work using LaTeX: $\\frac{{a}}{{b}}$, $\\times$, and $\\div$.

### TEXTBOOK CONTEXT:
{context}

### STUDENT QUESTION:
{question}

---
Provide the Step-by-Step solution below:
"""
    try:
        r = ollama.chat(model=LLM_MODEL, messages=[{"role": "user", "content": prompt}])
        return r["message"]["content"]
    except Exception as e:
        return f"Error: {str(e)}"