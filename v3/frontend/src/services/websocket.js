let ws;

export function sendMessage(msg, onMessage) {
  ws = new WebSocket("ws://localhost:8000/ws");

  ws.onopen = () => ws.send(msg);
  ws.onmessage = (e) => onMessage(e.data);
}