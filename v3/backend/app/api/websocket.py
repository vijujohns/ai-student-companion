"""
Enhanced WebSocket streaming
Supports:
- /ws -> basic test streaming
- /ws/ask -> full RAG streaming with progressive saving & fallback
- /ws/lesson -> lesson step streaming
- /ws/quiz -> quiz question streaming with live feedback

✅ NOW WITH PROPER AUTHENTICATION (no more query params!)
"""

import time
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from ..modules.rag import generate_answer_stream
from ..modules.lesson_plan import get_next_step, update_step_progress
from ..modules.quiz import get_quiz, submit_quiz_answer
from ..modules.history import save_chat
from ..modules.ws_auth import require_websocket_auth, authenticate_websocket, get_requested_subprotocol
from ..core.debug_logger import dlog, dwarn, derror
import asyncio, json, traceback

websocket_router = APIRouter()


async def send_json(ws: WebSocket, data: dict):
    """Utility to send JSON safely."""
    try:
        await ws.send_text(json.dumps(data))
    except Exception as e:
        derror("WS", f"Error sending JSON: {e}", data_type=data.get("type"))
        print(f"❌ Error sending JSON: {e}")


# -------------------------
# Basic test streaming
# -------------------------
@websocket_router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """Basic streaming endpoint — requires authentication."""
    dlog("WS", "Connection attempt /ws", client=ws.client.host if ws.client else "?")
    user = await authenticate_websocket(ws)
    if not user:
        dwarn("WS", "Auth failed /ws")
        await ws.close(code=status.WS_1008_POLICY_VIOLATION, reason="Unauthorized")
        return

    await ws.accept(subprotocol=get_requested_subprotocol(ws))
    dlog("WS", "Accepted /ws", user=user["username"])
    try:
        while True:
            query = await ws.receive_text()
            dlog("WS", "Received query /ws", user=user["username"], query=query[:80])
            from ..modules.rag import generate_answer
            answer = generate_answer(query, user_id=user["username"])
            dlog("WS", "Sending answer /ws", tokens=len(answer.split()))
            for token in answer.split():
                await ws.send_text(token)
                await asyncio.sleep(0.05)
    except WebSocketDisconnect:
        dlog("WS", "Client disconnected /ws", user=user["username"])
        print("⚠️ Client disconnected /ws")
    except Exception:
        derror("WS", "Unexpected error /ws")
        traceback.print_exc()


# -------------------------
# RAG / Ask streaming
# -------------------------
@websocket_router.websocket("/ws/ask")
async def websocket_ask(ws: WebSocket):
    dlog("WS", "Connection attempt /ws/ask",
         client=ws.client.host if ws.client else "?")
    print("🔥 /ws/ask connection request received")

    # ✅ Authenticate WebSocket connection
    user = await authenticate_websocket(ws)
    if not user:
        dwarn("WS", "Auth failed /ws/ask")
        await ws.close(code=status.WS_1008_POLICY_VIOLATION, reason="Unauthorized")
        print("❌ WebSocket auth failed")
        return

    await ws.accept(subprotocol=get_requested_subprotocol(ws))
    dlog("WS", "Accepted /ws/ask", user=user["username"])
    print(f"✅ WebSocket accepted for user: {user['username']}")

    try:
        while True:
            data = await ws.receive_text()

            # -------- Parse Input --------
            t_start = time.perf_counter()
            try:
                payload = json.loads(data)
                query = payload.get("query")
                session_id = payload.get("session_id", "default")
                model_name = payload.get("model_name")
            except Exception:
                query = data
                session_id = "default"
                model_name = None

            dlog("WS", "Query received /ws/ask",
                 user=user["username"],
                 session=session_id,
                 model_requested=model_name or "auto",
                 query=query[:120] if query else None)
            print(f"🧠 Query: {query}")

            # -------- Stream Response --------
            full_response = ""
            token_count = 0
            try:
                async for token in async_stream_wrapper(generate_answer_stream(query, user["username"], session_id, model_name)):
                    full_response += token
                    token_count += 1
                    await send_json(ws, {"type": "chunk", "data": token})
            except Exception as e:
                derror("WS", f"Streaming error /ws/ask: {e}", user=user["username"])
                print(f"❌ Streaming error: {e}")
                traceback.print_exc()
                await send_json(ws, {"type": "error", "data": str(e)})

            # Final save
            save_chat(user["username"], session_id, query, full_response)

            elapsed = (time.perf_counter() - t_start) * 1000
            dlog("WS", "Stream complete /ws/ask",
                 user=user["username"],
                 session=session_id,
                 tokens=token_count,
                 response_chars=len(full_response),
                 elapsed_ms=f"{elapsed:.1f}ms")

            # End signal
            await send_json(ws, {"type": "end"})

    except WebSocketDisconnect:
        dlog("WS", "Client disconnected /ws/ask", user=user["username"])
        print("⚠️ Client disconnected /ws/ask")
    except Exception as e:
        derror("WS", f"WebSocket error /ws/ask: {e}", user=user["username"])
        print(f"❌ WebSocket error /ws/ask: {e}")
        traceback.print_exc()
        await send_json(ws, {"type": "error", "data": str(e)})


async def async_stream_wrapper(gen):
    """
    Wraps a synchronous generator (like generate_answer_stream)
    into an async iterator without blocking the event loop.
    """
    loop = asyncio.get_event_loop()
    for token in gen:
        yield token
        await asyncio.sleep(0)


# -------------------------
# Lesson Streaming
# -------------------------
@websocket_router.websocket("/ws/lesson")
async def ws_lesson(ws: WebSocket):
    dlog("WS", "Connection attempt /ws/lesson",
         client=ws.client.host if ws.client else "?")
    # ✅ Authenticate WebSocket connection
    user = await authenticate_websocket(ws)
    if not user:
        dwarn("WS", "Auth failed /ws/lesson")
        await ws.close(code=status.WS_1008_POLICY_VIOLATION, reason="Unauthorized")
        print("❌ WebSocket auth failed for /ws/lesson")
        return

    await ws.accept(subprotocol=get_requested_subprotocol(ws))
    dlog("WS", "Accepted /ws/lesson", user=user["username"])
    print(f"✅ Lesson WebSocket accepted for user: {user['username']}")

    try:
        data = await ws.receive_text()
        payload = json.loads(data)
        session_id = payload.get("session_id")
        dlog("WS", "Lesson session started", user=user["username"], session=session_id)

        step_count = 0
        while True:
            step = get_next_step(user["username"], session_id)
            if not step or step.get("message") == "Lesson completed":
                dlog("WS", "Lesson complete", user=user["username"],
                     session=session_id, steps_completed=step_count)
                await send_json(ws, {"type": "lesson_complete"})
                break

            step_count += 1
            dlog("WS", "Sending lesson step",
                 user=user["username"], step_id=step.get("id"), step_num=step_count)
            # Stream step info
            await send_json(ws, {"type": "lesson_step", "step": step})

            # Wait for client action
            try:
                step_data = await asyncio.wait_for(ws.receive_text(), timeout=120)
                step_data = json.loads(step_data)
                if step_data.get("action") == "complete_step":
                    dlog("WS", "Step marked complete",
                         user=user["username"], step_id=step.get("id"))
                    update_step_progress(user["username"], session_id, step["id"], "completed")
            except asyncio.TimeoutError:
                dwarn("WS", "Lesson step timeout — continuing",
                      user=user["username"], step_id=step.get("id"))
                print("⚠️ Lesson step timeout, moving to next")
                continue

    except WebSocketDisconnect:
        dlog("WS", "Client disconnected /ws/lesson", user=user["username"])
        print("⚠️ Client disconnected /ws/lesson")
    except Exception as e:
        derror("WS", f"Lesson WS error: {e}", user=user["username"])
        print(f"❌ Lesson WS error: {e}")
        traceback.print_exc()
        await send_json(ws, {"type": "error", "data": str(e)})


# -------------------------
# Quiz Streaming
# -------------------------
@websocket_router.websocket("/ws/quiz")
async def ws_quiz(ws: WebSocket):
    dlog("WS", "Connection attempt /ws/quiz",
         client=ws.client.host if ws.client else "?")
    # ✅ Authenticate WebSocket connection
    user = await authenticate_websocket(ws)
    if not user:
        dwarn("WS", "Auth failed /ws/quiz")
        await ws.close(code=status.WS_1008_POLICY_VIOLATION, reason="Unauthorized")
        print("❌ WebSocket auth failed for /ws/quiz")
        return

    await ws.accept(subprotocol=get_requested_subprotocol(ws))
    dlog("WS", "Accepted /ws/quiz", user=user["username"])
    print(f"✅ Quiz WebSocket accepted for user: {user['username']}")

    try:
        data = await ws.receive_text()
        payload = json.loads(data)
        session_id = payload.get("session_id")
        quiz_id = payload.get("quiz_id")
        dlog("WS", "Quiz session started",
             user=user["username"], session=session_id, quiz_id=quiz_id)

        quiz = get_quiz(user["username"], session_id, quiz_id)
        if not quiz:
            dwarn("WS", "Quiz not found",
                  user=user["username"], quiz_id=quiz_id)
            await send_json(ws, {"type": "error", "data": "Quiz not found"})
            return

        dlog("WS", "Quiz loaded",
             user=user["username"], questions=len(quiz["questions"]))

        for q in quiz["questions"]:
            dlog("WS", "Sending quiz question",
                 user=user["username"], question_id=q.get("id"))
            await send_json(ws, {"type": "question", "question": q})

            try:
                answer_data = await asyncio.wait_for(ws.receive_text(), timeout=120)
                answer_payload = json.loads(answer_data)
                selected_answer = answer_payload.get("answer")
                dlog("WS", "Answer received",
                     user=user["username"], question_id=q.get("id"),
                     answer=selected_answer)

                result = submit_quiz_answer(user["username"], session_id, quiz_id, {q["id"]: selected_answer})
                dlog("WS", "Quiz feedback sent",
                     user=user["username"], question_id=q.get("id"),
                     result=result.get(q["id"]))
                await send_json(ws, {"type": "feedback", "question_id": q["id"], "result": result.get(q["id"])})

            except asyncio.TimeoutError:
                dwarn("WS", "Quiz question timeout",
                      user=user["username"], question_id=q.get("id"))
                print(f"⚠️ Quiz question timeout: {q['id']}")
                await send_json(ws, {"type": "feedback", "question_id": q["id"], "result": None})

        dlog("WS", "Quiz complete", user=user["username"], session=session_id)
        await send_json(ws, {"type": "quiz_complete"})

    except WebSocketDisconnect:
        dlog("WS", "Client disconnected /ws/quiz", user=user["username"])
        print("⚠️ Client disconnected /ws/quiz")
    except Exception as e:
        derror("WS", f"Quiz WS error: {e}", user=user["username"])
        print(f"❌ Quiz WS error: {e}")
        traceback.print_exc()
        await send_json(ws, {"type": "error", "data": str(e)})