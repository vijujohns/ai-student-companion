def generate_metadata(class_name, subject, chapter, type_, chunk_id):
    return {
        "class": class_name,
        "subject": subject,
        "chapter": chapter,
        "type": type_,
        "chunk_id": chunk_id,
        "language": "English",
        "step_by_step": subject in ["Math", "Physics", "Chemistry"]
    }
