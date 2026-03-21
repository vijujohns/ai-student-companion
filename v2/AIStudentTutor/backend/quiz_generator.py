def generate_quiz(text_chunks):
    quiz = []
    for chunk in text_chunks[:5]:
        quiz.append({
            "question": chunk["text"],
            "options": ["Option A", "Option B", "Option C", "Option D"],
            "answer": "Option A"
        })
    return quiz
