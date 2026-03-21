"""
WebSocket streaming
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.modules.rag import generate_answer
import asyncio
from fastapi import Query


websocket_router = APIRouter()

@websocket_router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    while True:
        query = await ws.receive_text()
        answer = generate_answer(query)

        for token in answer.split():
            await ws.send_text(token)
            await asyncio.sleep(0.05)

"""
WebSocket for streaming responses
"""

@websocket_router.websocket("/ws/ask")
async def websocket_ask(websocket: WebSocket):
    print("🔥 WebSocket connection request received")

    await websocket.accept()
    print("✅ WebSocket accepted")

    try:
        while True:
            data = await websocket.receive_text()

            # Run LLM in thread (non-blocking)
            answer = await asyncio.to_thread(generate_answer, data)

            words = answer.split()
            for word in words:
                await websocket.send_text(word + " ")
                await asyncio.sleep(0.02)

            await websocket.send_text("[END]")

    except WebSocketDisconnect:
        print("⚠️ Client disconnected")