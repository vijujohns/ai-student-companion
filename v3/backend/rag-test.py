"""
Test script for RAG pipeline with caching
"""
import sys
import os

# Add modules path
sys.path.append(os.path.join(os.path.dirname(__file__), "app", "modules"))

from app.modules.rag import generate_answer

context = "Python is used for web development and AI."
query = "What Python libraries can I use for web development?"
answer = generate_answer(query, user_id="test_user", session_id="test_session")
print(answer)