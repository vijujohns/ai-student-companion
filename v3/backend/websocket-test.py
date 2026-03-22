# ws_test_client.py
"""
Test WebSocket /ws/ask endpoint with streaming and session handling
"""

import asyncio
import websockets
import json

# Backend WebSocket URL
WS_URL = "ws://localhost:8000/ws/ask"

async def test_ws():
    async with websockets.connect(WS_URL) as ws:
        print("✅ Connected to WebSocket")

        # Simulate multiple queries in the same session
        session_id = "test_session"
        user_id = "test_user"

        queries = [
            "Explain recursion in Python",
            "Give an example of Python decorators",
            "What are Python generators?"
        ]

        for q in queries:
            payload = {
                "query": q,
                "session_id": session_id,
                "user_id": user_id
            }
            await ws.send(json.dumps(payload))
            print(f"\n💬 Sent query: {q}")

            print("⏳ Receiving streamed answer:")
            answer = ""
            while True:
                token = await ws.recv()
                if token == "[END]":
                    break
                print(token, end="", flush=True)
                answer += token
            print("\n✅ Answer received\n" + "-"*50)

        print("🔒 Closing WebSocket connection")

if __name__ == "__main__":
    asyncio.run(test_ws())