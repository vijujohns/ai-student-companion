"""
Main FastAPI entry point
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware  # ✅ ADDED

from app.api.routes import router
from app.api.websocket import websocket_router

from app.modules.faiss_store import load_index, load_knowledge_base
from app.modules.db import init_db

import threading

app = FastAPI(title="AI Tutor")

# ✅ CORS FIX (required for frontend login & API calls)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # safe for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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