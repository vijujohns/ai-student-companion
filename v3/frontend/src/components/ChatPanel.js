import React, { useState } from "react";
import { sendMessage } from "../services/websocket";
import VoiceControl from "./VoiceControl";
import { speakText } from "../utils/speech";

export default function ChatPanel() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState([]);
  const [currentStream, setCurrentStream] = useState("");

  // 🎤 Voice input handler
  const handleVoice = (text) => {
    setInput(text);
  };

  const handleSend = () => {
    if (!input) return;

    // Add user message
    setMessages(prev => [...prev, { type: "user", text: input }]);

    let fullResponse = "";

    // Reset stream buffer
    setCurrentStream("");

    sendMessage(input, (token) => {
      fullResponse += token;

      // Update live streaming text
      setCurrentStream(fullResponse);
    });

    // 🔊 Delay speech slightly to allow streaming to complete
    setTimeout(() => {
      if (fullResponse) {
        speakText(fullResponse);
      }

      // Save final AI message
      setMessages(prev => [
        ...prev,
        { type: "ai", text: fullResponse }
      ]);

      setCurrentStream("");
    }, 1500); // adjust if needed

    setInput("");
  };

  return (
    <div>

      {/* 🎤 Voice Input */}
      <VoiceControl onResult={handleVoice} />

      {/* Input */}
      <input
        value={input}
        onChange={e => setInput(e.target.value)}
        placeholder="Ask something..."
      />

      <button onClick={handleSend}>Send</button>

      {/* Chat Messages */}
      <div style={{ marginTop: "20px" }}>
        {messages.map((msg, i) => (
          <div key={i}>
            <b>{msg.type === "user" ? "You:" : "AI:"}</b> {msg.text}
          </div>
        ))}

        {/* 🔥 Live streaming */}
        {currentStream && (
          <div>
            <b>AI:</b> {currentStream}
          </div>
        )}
      </div>

    </div>
  );
}