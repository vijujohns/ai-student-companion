let ws;

export function sendMessage(message, onMessage) {
  const token = localStorage.getItem("token");

  // 🔥 Backward compatible URL (token optional)
  const url = token
    ? `ws://127.0.0.1:8000/ws/ask?token=${token}`
    : `ws://127.0.0.1:8000/ws/ask`;

  ws = new WebSocket(url);

  ws.onopen = () => {
    console.log("✅ WebSocket Connected");

    try {
      // ✅ NEW: If message is object → send JSON
      if (typeof message === "object") {
        ws.send(JSON.stringify(message));
      } else {
        // 🔁 OLD fallback (plain text)
        ws.send(message);
      }
    } catch (err) {
      console.error("❌ Send Error:", err);
    }
  };

  ws.onmessage = (event) => {
    onMessage(event.data);
  };

  ws.onerror = (error) => {
    console.error("❌ WebSocket Error:", error);
  };

  ws.onclose = () => {
    console.log("🔌 WebSocket Closed");
  };
}