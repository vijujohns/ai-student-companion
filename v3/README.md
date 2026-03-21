# AI Tutor

## Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload

## Redis
Install Redis locally and run:
redis-server

## Frontend
cd frontend
npm install
npm start

## Features
- RAG Q&A
- WebSocket streaming
- Redis caching
- JWT auth (extendable)
- Translation fallback
- PWA ready

## Troubleshooting
- Ensure Redis running
- Use Python 3.10+