"""
Creates full project structure
"""

import os

folders = [
    "backend/app/api",
    "backend/app/core",
    "backend/app/modules",
    "backend/app/db",
    "backend/app/schemas",
    "frontend/src/components",
    "frontend/src/services",
    "frontend/src/pwa",
    "data",
    "knowledge_base",
    "configs"
]

files = [
    "backend/app/main.py",
    "backend/app/api/routes.py",
    "backend/app/api/websocket.py",
    "backend/app/core/config.py",
    "backend/app/core/security.py",
    "backend/app/modules/rag.py",
    "backend/app/modules/faiss_store.py",
    "backend/app/modules/cache.py",
    "backend/app/modules/history.py",
    "backend/app/modules/translation.py",
    "backend/app/modules/quiz.py",
    "backend/app/modules/flashcards.py",
    "backend/app/modules/progress.py",
    "backend/app/modules/model_manager.py",
    "backend/app/db/sqlite_db.py",
    "backend/app/schemas/request.py",
    "backend/app/schemas/response.py",
]

for folder in folders:
    os.makedirs(folder, exist_ok=True)

for file in files:
    open(file, "w").close()

print("Project structure created.")