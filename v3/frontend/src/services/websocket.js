let ws;

export function sendMessage(message, onMessage) {
  const token = localStorage.getItem("token");

  // 🔥 Backward compatible (works with or without login)
  const url = token
    ? `ws://127.0.0.1:8000/ws/ask?token=${token}`
    : `ws://127.0.0.1:8000/ws/ask`;

  ws = new WebSocket(url);

  ws.onopen = () => {
    console.log("✅ WebSocket Connected");
    ws.send(message);
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