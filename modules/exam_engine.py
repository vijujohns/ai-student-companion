
import ollama
from config import LLM_MODEL

def generate_exam(topic):
    prompt=f"""
Create a CBSE style exam on {topic}

Include:
5 MCQ
3 Short answer
2 Long answer

Provide answer key.
"""
    r=ollama.chat(
    model=LLM_MODEL,
    messages=[{"role":"user","content":prompt}]
    )
    return r["message"]["content"]
