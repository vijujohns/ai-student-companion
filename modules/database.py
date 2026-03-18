import sqlite3
import os
from config import PROGRESS_DB

def init_progress_db():
    os.makedirs(os.path.dirname(PROGRESS_DB), exist_ok=True)
    conn = sqlite3.connect(PROGRESS_DB)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS progress 
                 (chapter TEXT, subject TEXT, class TEXT, status TEXT, date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

def log_completion(chapter, subject, cls):
    conn = sqlite3.connect(PROGRESS_DB)
    c = conn.cursor()
    c.execute("INSERT INTO progress (chapter, subject, class, status) VALUES (?, ?, ?, 'Completed')", 
              (chapter, subject, cls))
    conn.commit()
    conn.close()

def fetch_progress():
    conn = sqlite3.connect(PROGRESS_DB)
    c = conn.cursor()
    c.execute("SELECT chapter, subject, date FROM progress ORDER BY date DESC")
    rows = c.fetchall()
    conn.close()
    return rows