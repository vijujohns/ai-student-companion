"""
Main FastAPI entry point
"""

from fastapi import FastAPI
from app.api.routes import router
from app.api.websocket import websocket_router

from app.modules.faiss_store import load_index, load_knowledge_base
from app.modules.db import init_db

import threading

app = FastAPI(title="AI Tutor")

app.include_router(router)
app.include_router(websocket_router)


@app.on_event("startup")
def startup_event():
    print("🚀 Loading FAISS index...")
    load_index()

    print("🚀 Checking for KB updates...")
    threading.Thread(target=load_knowledge_base).start()

    print("🚀 Initializing DB...")
    init_db()
