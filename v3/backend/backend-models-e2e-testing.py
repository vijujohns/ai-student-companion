"""
automated_backend_test.py
Automated tests for AI Student Tutor backend
"""

import asyncio
import json
import sys

from fastapi.testclient import TestClient
from websockets import connect

# Ensure correct import path for your modules
sys.path.append("./app/modules")

from model_manager import list_models, get_default_model, generate_response
from rag import generate_answer
from app.main import app  # FastAPI app

client = TestClient(app)


def test_model_manager():
    print("=== Model Manager Tests ===")
    models = list_models()
    print("Available models:", list(models.keys()))

    default_model = get_default_model()
    print("Default model:", default_model.get("description"))

    # Test TinyLLaMA local response
    print("\nTesting local model response...")
    try:
        answer = generate_response(
            context="Python is a programming language.",
            query="What is Python?",
            history="",
            model_name=None  # default model
        )
        print("Local model answer:", answer[:200], "...")
    except Exception as e:
        print("❌ Local model test failed:", e)

    # Test cloud model (OpenAI) – may fail if quota missing
    for cloud_model in ["gpt-3.5-turbo", "azure-gpt-4"]:
        print(f"\nTesting cloud model {cloud_model}...")
        try:
            answer = generate_response(
                context="Python is a programming language.",
                query="What is Python?",
                history="",
                model_name=cloud_model
            )
            print(f"Cloud model {cloud_model} answer:", answer[:200], "...")
        except Exception as e:
            print(f"⚠️ Skipping cloud model {cloud_model} due to error:", e)


def test_rag_module():
    print("\n=== RAG Module Tests ===")
    try:
        ans = generate_answer(
            query="List some Python libraries for web development.",
            user_id="test_user",
            session_id="test_session"
        )
        print("RAG answer:", ans[:200], "...")
    except Exception as e:
        print("❌ RAG test failed:", e)


def test_api_ask():
    print("\n=== HTTP /ask Endpoint Test ===")
    payload = {"query": "Explain AI in simple terms.", "user_id": "test", "session_id": "sess1"}
    try:
        response = client.post("/ask", json=payload)
        if response.status_code == 200:
            print("✅ /ask response:", response.json().get("answer")[:200], "...")
        else:
            print("❌ /ask failed with status:", response.status_code)
    except Exception as e:
        print("❌ /ask test failed:", e)


async def test_websocket_ask():
    print("\n=== WebSocket /ws/ask Test ===")
    uri = "ws://127.0.0.1:8000/ws/ask"
    try:
        async with connect(uri) as websocket:
            payload = {"query": "Explain AI in simple terms.", "user_id": "ws_test", "session_id": "sess_ws"}
            await websocket.send(json.dumps(payload))

            response_text = ""
            while True:
                msg = await websocket.recv()
                if msg == "[END]":
                    break
                response_text += msg

            print("WebSocket /ws/ask answer:", response_text[:200], "...")
    except Exception as e:
        print("❌ WebSocket test failed:", e)


if __name__ == "__main__":
    # Step 1: Model Manager Tests
    test_model_manager()

    # Step 2: RAG Module Tests
    test_rag_module()

    # Step 3: HTTP /ask endpoint test
    test_api_ask()

    # Step 4: WebSocket test (requires backend running)
    print("\nStarting WebSocket test (ensure backend is running at ws://127.0.0.1:8000)...")
    asyncio.run(test_websocket_ask())

    print("\n=== Backend Tests Completed ===")