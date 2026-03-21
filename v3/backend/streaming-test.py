import asyncio
import websockets

async def test():
    uri = "ws://127.0.0.1:8000/ws/ask"

    async with websockets.connect(uri) as ws:
        print("✅ Connected to server")

        await ws.send("What is tsunami?")
        print("📤 Query sent")

        while True:
            try:
                msg = await ws.recv()

                if msg == "[END]":
                    print("\n✅ Completed")
                    break

                print(msg, end="", flush=True)

            except websockets.exceptions.ConnectionClosed:
                print("\n❌ Connection closed unexpectedly")
                break

asyncio.run(test())