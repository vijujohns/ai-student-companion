let ws;

export function sendMessage(message, onMessage) {
  const token = localStorage.getItem("token");

  // 🔥 Backward compatible URL (token optional)
  const url = token
    ? `ws://127.0.0.1:8000/ws/ask?token=${token}`
    : `ws://127.0.0.1:8000/ws/ask`;


  if (ws) {
    ws.close();
  }
  
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
    try {
      const msg = JSON.parse(event.data);

      if (msg.type === "chunk") {
        onMessage(msg.data);
      }

      if (msg.type === "end") {
        onMessage("__END__");  // 🔥 unify signal
      }
      
      if (msg.type === "error") {
        console.error("❌ Server Error:", msg.data);
        onMessage("__END__");
      }

    } catch (err) {
      // fallback for old plain text responses
      onMessage(event.data);
    }
  };

  ws.onerror = (error) => {
    console.error("❌ WebSocket Error:", error);
  };

  ws.onclose = () => {
    console.log("🔌 WebSocket Closed");
  };
}

export function closeSocket() {
  if (ws) {
    ws.close();
    ws = null;
    console.log("🛑 WebSocket manually closed");
  }
}