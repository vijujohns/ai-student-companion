import React, { useState } from "react";
import { sendMessage } from "../services/websocket";

export default function ChatPanel() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState([]);

  const handleSend = () => {
    sendMessage(input, (token) => {
      setMessages(prev => [...prev, token]);
    });
  };

  return (
    <div>
      <input onChange={e => setInput(e.target.value)} />
      <button onClick={handleSend}>Send</button>
      <div>{messages.join(" ")}</div>
    </div>
  );
}