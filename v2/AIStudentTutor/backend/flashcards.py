def generate_flashcards(text_chunks):
    flashcards = []
    for chunk in text_chunks:
        flashcards.append({
            "question": chunk["text"],
            "answer": "..."  # placeholder
        })
    return flashcards
