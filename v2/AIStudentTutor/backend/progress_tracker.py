import json
import os

SAVE_FILE = "data/saved_results/progress.json"

def load_progress():
    if os.path.exists(SAVE_FILE):
        with open(SAVE_FILE, "r") as f:
            return json.load(f)
    return {}

def save_progress(student_id, progress):
    data = load_progress()
    data[student_id] = progress
    with open(SAVE_FILE, "w") as f:
        json.dump(data, f, indent=4)
