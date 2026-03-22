import React, { useState, useEffect } from "react";
import { sendMessage } from "../services/websocket";
import VoiceControl from "./VoiceControl";
import { speakText } from "../utils/speech";

export default function ChatPanel() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState([]);
  const [currentStream, setCurrentStream] = useState("");

  const [sessionId, setSessionId] = useState(
    localStorage.getItem("session_id") || null
  );

  const [userId] = useState(
    localStorage.getItem("username") || "default"
  );

  const [userRole, setUserRole] = useState(
    localStorage.getItem("role") || "user"
  );

  const [autoSpeak, setAutoSpeak] = useState(false);
  const [sessions, setSessions] = useState([]);

  const handleVoice = (text) => setInput(text);

  // 🔐 LOGOUT
  const handleLogout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("session_id");
    localStorage.removeItem("username");
    localStorage.removeItem("role");

    // reload app → goes back to login screen
    window.location.reload();
  };

  // ✅ LOAD SESSIONS
  const loadSessions = async () => {
    const token = localStorage.getItem("token");
    if (!token) return;

    try {
      const res = await fetch("http://127.0.0.1:8000/sessions", {
        headers: {
          Authorization: `Bearer ${token}`
        }
      });

      const data = await res.json();
      setSessions(data);
    } catch (err) {
      console.error("❌ Failed to load sessions:", err);
    }
  };

  // ✅ LOAD HISTORY
  const loadHistory = async (session) => {
    const token = localStorage.getItem("token");
    if (!token || !session) return;

    try {
      const res = await fetch(
        `http://127.0.0.1:8000/history?session_id=${session}`,
        {
          headers: {
            Authorization: `Bearer ${token}`
          }
        }
      );

      const data = await res.json();
      const formatted = [];
      data.forEach(item => {
        formatted.push({ type: "user", text: item.question });
        formatted.push({ type: "ai", text: item.answer });
      });

      setMessages(formatted);
    } catch (err) {
      console.error("❌ Failed to load history:", err);
    }
  };

  useEffect(() => {
    if (sessionId) {
      loadHistory(sessionId);
    }
    loadSessions();
  }, []);

  // ✅ NEW CHAT
  const handleNewChat = () => {
    const newSession = Date.now().toString();
    setSessionId(newSession);
    localStorage.setItem("session_id", newSession);
    setMessages([]);
  };

  // ✅ SWITCH SESSION
  const switchSession = (sessionObj) => {
    const session = sessionObj.id;
    setSessionId(session);
    localStorage.setItem("session_id", session);
    loadHistory(session);
  };

  // 🗑️ DELETE SESSION
  const deleteSession = async (sessionToDelete) => {
    const token = localStorage.getItem("token");

    try {
      await fetch(
        `http://127.0.0.1:8000/sessions/${sessionToDelete.id}`,
        {
          method: "DELETE",
          headers: {
            Authorization: `Bearer ${token}`
          }
        }
      );

      const updated = sessions.filter(s => s.id !== sessionToDelete.id);
      setSessions(updated);

      if (sessionId === sessionToDelete.id) {
        if (updated.length > 0) {
          switchSession(updated[0]);
        } else {
          setSessionId(null);
          localStorage.removeItem("session_id");
          setMessages([]);
        }
      }

    } catch (err) {
      console.error("❌ Delete failed:", err);
    }
  };

  // ✏️ RENAME SESSION
  const renameSession = async (sessionObj) => {
    const newTitle = prompt("Rename chat:", sessionObj.title);
    if (!newTitle) return;

    const token = localStorage.getItem("token");

    try {
      await fetch(
        `http://127.0.0.1:8000/sessions/${sessionObj.id}`,
        {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`
          },
          body: JSON.stringify({ title: newTitle })
        }
      );

      const updated = sessions.map(s =>
        s.id === sessionObj.id ? { ...s, title: newTitle } : s
      );
      setSessions(updated);
    } catch (err) {
      console.error("❌ Rename failed:", err);
    }
  };

  const handleSend = () => {
    if (!input) return;

    setMessages(prev => [...prev, { type: "user", text: input }]);
    let fullResponse = "";
    setCurrentStream("");

    let currentSession = sessionId;
    if (!currentSession) {
      currentSession = Date.now().toString();
      setSessionId(currentSession);
      localStorage.setItem("session_id", currentSession);
    }

    sendMessage(
      {
        query: input,
        session_id: currentSession,
        user_id: userId
      },
      (token) => {
        if (token === "[END]") {
          setMessages(prev => [
            ...prev,
            { type: "ai", text: fullResponse }
          ]);

          if (autoSpeak && fullResponse) {
            speakText(fullResponse);
          }

          setCurrentStream("");
          return;
        }

        fullResponse += token;
        setCurrentStream(fullResponse);
      }
    );

    setInput("");
    setTimeout(() => {
      loadSessions();
    }, 500);
  };

  return (
    <div style={{ display: "flex" }}>

      {/* 🧭 SIDEBAR */}
      <div style={{ width: "240px", borderRight: "1px solid #ccc", padding: "10px" }}>
        
        {/* 🔐 Logout */}
        <button onClick={handleLogout} style={{ marginBottom: "10px" }}>
          🔓 Logout
        </button>

        {/* 👤 User info */}
        <div style={{ marginBottom: "10px", fontWeight: "bold" }}>
          User: {userId} ({userRole})
        </div>

        <button onClick={handleNewChat}>+ New Chat</button>

        <div style={{ marginTop: "10px" }}>
          <label>
            <input
              type="checkbox"
              checked={autoSpeak}
              onChange={() => setAutoSpeak(!autoSpeak)}
            />
            🔊 Auto Speak
          </label>
        </div>

        <div style={{ marginTop: "10px" }}>
          {sessions.map((s) => (
            <div
              key={s.id}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "5px",
                background: s.id === sessionId ? "#ddd" : "transparent"
              }}
            >
              <span
                onClick={() => switchSession(s)}
                style={{ cursor: "pointer", flex: 1 }}
              >
                {s.title || "New Chat"}
              </span>

              <button onClick={() => renameSession(s)}>✏️</button>
              <button onClick={() => deleteSession(s)}>🗑️</button>
            </div>
          ))}
        </div>
      </div>

      {/* 💬 MAIN CHAT */}
      <div style={{ flex: 1, padding: "10px" }}>
        <VoiceControl onResult={handleVoice} />

        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          placeholder="Ask something..."
        />

        <button onClick={handleSend}>Send</button>

        <div style={{ marginTop: "20px" }}>
          {messages.map((msg, i) => (
            <div key={i}>
              <b>{msg.type === "user" ? "You:" : "AI:"}</b> {msg.text}
            </div>
          ))}

          {currentStream && (
            <div>
              <b>AI:</b> {currentStream}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}