"""
WebSocket streaming
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.modules.rag import generate_answer
import asyncio
import json

websocket_router = APIRouter()


@websocket_router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """
    Simple WebSocket endpoint for testing streaming responses.
    Sends back tokens from default model.
    """
    await ws.accept()
    try:
        while True:
            query = await ws.receive_text()
            answer = generate_answer(query)
            
            # Stream each token with small delay
            for token in answer.split():
                await ws.send_text(token)
                await asyncio.sleep(0.05)

    except WebSocketDisconnect:
        print("⚠️ Client disconnected")


@websocket_router.websocket("/ws/ask")
async def websocket_ask(websocket: WebSocket):
    """
    WebSocket endpoint for streaming RAG-based answers.
    Supports:
    - user_id
    - session_id
    - optional model_name (local or cloud)
    """

    print("🔥 WebSocket connection request received")
    await websocket.accept()
    print("✅ WebSocket accepted")

    try:
        while True:
            data = await websocket.receive_text()

            # Parse JSON payload
            try:
                payload = json.loads(data)
                query = payload.get("query")
                session_id = payload.get("session_id", "default")
                user_id = payload.get("user_id", "default")
                model_name = payload.get("model_name")  # NEW: optional model selection
            except:
                # Fallback for old clients sending raw text
                query = data
                session_id = "default"
                user_id = "default"
                model_name = None

            # 🔹 Generate answer using RAG pipeline in a thread
            answer = await asyncio.to_thread(
                generate_answer,
                query=query,
                user_id=user_id,
                session_id=session_id,
                model_name=model_name
            )

            # 🔹 Stream response word by word with slight delay
            for word in answer.split():
                await websocket.send_text(word + " ")
                await asyncio.sleep(0.02)

            # 🔹 Indicate end of message
            await websocket.send_text("[END]")

    except WebSocketDisconnect:
        print("⚠️ Client disconnected")