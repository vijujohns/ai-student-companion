import React, { useState, useEffect } from "react";
import { sendMessage } from "../services/websocket";
import VoiceControl from "./VoiceControl";
import { speakText } from "../utils/speech";

export default function ChatPanel() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState([]);
  const [currentStream, setCurrentStream] = useState("");

  const [sessionId, setSessionId] = useState(localStorage.getItem("session_id") || null);
  const [userId] = useState(localStorage.getItem("username") || "default");
  const [userRole, setUserRole] = useState(localStorage.getItem("role") || "user");

  const [autoSpeak, setAutoSpeak] = useState(
    localStorage.getItem("autoSpeak") === "true" || false
  );

  const [sessions, setSessions] = useState([]);

  // 🔹 Knowledge Base States
  const [classes, setClasses] = useState([]);
  const [selectedClass, setSelectedClass] = useState(null);
  const [subjects, setSubjects] = useState([]);
  const [selectedSubject, setSelectedSubject] = useState(null);
  const [folders, setFolders] = useState([]);
  const [selectedFolder, setSelectedFolder] = useState(null);
  const [contents, setContents] = useState([]);
  const [selectedContent, setSelectedContent] = useState(null);

  // 🔹 PDF Blob URL
  const [pdfBlobUrl, setPdfBlobUrl] = useState(null);

  const handleVoice = (text) => setInput(text);

  // Determine if current user is admin
  const isAdmin = userRole === "admin";

  const [adminRunning, setAdminRunning] = useState(false);
  const [adminMessage, setAdminMessage] = useState("");

  // 🔐 LOGOUT
  const handleLogout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("session_id");
    localStorage.removeItem("username");
    localStorage.removeItem("role");
    window.location.reload();
  };

  // ✅ LOAD SESSIONS
  const loadSessions = async () => {
    const token = localStorage.getItem("token");
    if (!token) return;

    try {
      const res = await fetch("http://127.0.0.1:8000/sessions", {
        headers: { Authorization: `Bearer ${token}` },
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
        { headers: { Authorization: `Bearer ${token}` } }
      );
      const data = await res.json();
      const formatted = [];
      data.forEach((item) => {
        formatted.push({ type: "user", text: item.question });
        formatted.push({ type: "ai", text: item.answer });
      });
      setMessages(formatted);
    } catch (err) {
      console.error("❌ Failed to load history:", err);
    }
  };

  useEffect(() => {
    if (sessionId) loadHistory(sessionId);
    loadSessions();
    loadClasses();
  }, []);

  // ✅ NEW CHAT
  const handleNewChat = () => {
    const newSession = Date.now().toString();
    setSessionId(newSession);
    localStorage.setItem("session_id", newSession);
    setMessages([]);
    setSelectedContent(null);
  };

  // ✅ SWITCH SESSION
  const switchSession = (sessionObj) => {
    const session = sessionObj.id;
    setSessionId(session);
    localStorage.setItem("session_id", session);
    loadHistory(session);
    if (sessionObj.selected_content) {
      setSelectedContent(sessionObj.selected_content);
    } else {
      setSelectedContent(null);
    }
  };

  // 🗑️ DELETE SESSION
  const deleteSession = async (sessionToDelete) => {
    const token = localStorage.getItem("token");
    try {
      await fetch(`http://127.0.0.1:8000/sessions/${sessionToDelete.id}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      const updated = sessions.filter((s) => s.id !== sessionToDelete.id);
      setSessions(updated);
      if (sessionId === sessionToDelete.id) {
        if (updated.length > 0) switchSession(updated[0]);
        else {
          setSessionId(null);
          localStorage.removeItem("session_id");
          setMessages([]);
          setSelectedContent(null);
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
      await fetch(`http://127.0.0.1:8000/sessions/${sessionObj.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ title: newTitle }),
      });

      const updated = sessions.map((s) =>
        s.id === sessionObj.id ? { ...s, title: newTitle } : s
      );
      setSessions(updated);
    } catch (err) {
      console.error("❌ Rename failed:", err);
    }
  };

  // 🔹 Knowledge Base Fetchers
  const loadClasses = async () => {
    try {
      const res = await fetch("http://127.0.0.1:8000/classes");
      const data = await res.json();
      setClasses(data);
    } catch (err) {
      console.error("❌ Failed to load classes:", err);
    }
  };

  const loadSubjects = async (cls) => {
    if (!cls) return;
    try {
      const res = await fetch(
        `http://127.0.0.1:8000/subjects?class_name=${encodeURIComponent(cls)}`
      );
      const data = await res.json();
      setSubjects(data);
    } catch (err) {
      console.error("❌ Failed to load subjects:", err);
    }
  };

  const loadFolders = async (cls, subject) => {
    if (!cls || !subject) return;
    try {
      const res = await fetch(
        `http://127.0.0.1:8000/folders?class_name=${encodeURIComponent(cls)}&subject=${encodeURIComponent(subject)}`
      );
      const data = await res.json();
      setFolders(data);
    } catch (err) {
      console.error("❌ Failed to load folders:", err);
    }
  };

  const loadContents = async (cls, subject, folder) => {
    if (!cls || !subject || !folder) return;
    try {
      const res = await fetch(
        `http://127.0.0.1:8000/contents?class_name=${encodeURIComponent(cls)}&subject=${encodeURIComponent(subject)}&folder=${encodeURIComponent(folder)}`
      );
      const data = await res.json();
      setContents(data);
    } catch (err) {
      console.error("❌ Failed to load contents:", err);
    }
  };

  // 🔹 Load PDF securely using token
  useEffect(() => {
    if (!selectedContent) {
      setPdfBlobUrl(null);
      return;
    }
    const token = localStorage.getItem("token");
    fetch(`http://127.0.0.1:8000/pdf?path=${encodeURIComponent(selectedContent)}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => {
        if (!res.ok) throw new Error("Failed to load PDF");
        return res.blob();
      })
      .then((blob) => {
        const url = URL.createObjectURL(blob);
        setPdfBlobUrl(url);
      })
      .catch((err) => {
        console.error("❌ PDF load failed:", err);
        setPdfBlobUrl(null);
      });
  }, [selectedContent]);

  // ✅ SEND MESSAGE
  const handleSend = () => {
    if (!input) return;
    setMessages((prev) => [...prev, { type: "user", text: input }]);
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
        user_id: userId,
        context_id: selectedContent,
      },
      (token) => {
        if (token === "[END]") {
          setMessages((prev) => [...prev, { type: "ai", text: fullResponse }]);
          if (autoSpeak && fullResponse) speakText(fullResponse);
          setCurrentStream("");
          return;
        }
        fullResponse += token;
        setCurrentStream(fullResponse);
      }
    );

    setInput("");

    if (selectedContent) {
      const token = localStorage.getItem("token");
      fetch(`http://127.0.0.1:8000/sessions/${currentSession}/content`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ path: selectedContent }),
      });
    }

    setTimeout(() => loadSessions(), 500);
  };

  // 🔹 ADMIN FUNCTIONS
  // 🔹 REINDEX HANDLER
  const handleReindex = async () => {
    const token = localStorage.getItem("token");
    if (!token) return alert("Token missing");

    setAdminRunning(true);
    setAdminMessage("Reindexing knowledge base...");

    try {
      const res = await fetch("http://127.0.0.1:8000/admin/reindex", {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      setAdminMessage(data.status || "✅ Reindex completed!");
    } catch (err) {
      console.error("❌ Reindex failed:", err);
      setAdminMessage("❌ Reindex failed");
    } finally {
      setAdminRunning(false);
    }
  };

  // 🔹 INCREMENTAL REINDEX HANDLER
  const handleIncrementalReindex = async () => {
    const token = localStorage.getItem("token");
    if (!token) return alert("Token missing");

    setAdminRunning(true);
    setAdminMessage("Incremental reindexing...");

    try {
      const res = await fetch("http://127.0.0.1:8000/admin/reindex-incremental", {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      setAdminMessage(data.status || "✅ Incremental reindex completed!");
    } catch (err) {
      console.error("❌ Incremental reindex failed:", err);
      setAdminMessage("❌ Incremental reindex failed");
    } finally {
      setAdminRunning(false);
    }
  };

  return (
    <div style={{ display: "flex" }}>
      {/* 🧭 SIDEBAR */}
      <div style={{ width: "300px", borderRight: "1px solid #ccc", padding: "10px" }}>
        <button onClick={handleLogout} style={{ marginBottom: "10px" }}>
          🔓 Logout
        </button>
        <div style={{ marginBottom: "10px", fontWeight: "bold" }}>
          User: {userId} ({userRole})
        </div>
        <button onClick={handleNewChat}>+ New Chat</button>
        <div style={{ marginTop: "10px" }}>
          <label>
            <input
              type="checkbox"
              checked={autoSpeak}
              onChange={() => {
                setAutoSpeak((prev) => {
                  localStorage.setItem("autoSpeak", !prev);
                  return !prev;
                });
              }}
            />{" "}
            🔊 Auto Speak
          </label>
        </div>

        {/* 🔹 Knowledge Base Navigation */}
        <div style={{ marginTop: "10px" }}>
          <h4>Knowledge Base</h4>
          <select
            onChange={(e) => {
              setSelectedClass(e.target.value);
              setSelectedSubject(null);
              setSelectedFolder(null);
              setSelectedContent(null);
              loadSubjects(e.target.value);
            }}
          >
            <option value="">Select Class</option>
            {classes.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>

          {subjects.length > 0 && (
            <select
              onChange={(e) => {
                setSelectedSubject(e.target.value);
                setSelectedFolder(null);
                setSelectedContent(null);
                loadFolders(selectedClass, e.target.value);
              }}
            >
              <option value="">Select Subject</option>
              {subjects.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          )}

          {folders.length > 0 && (
            <select
              onChange={(e) => {
                setSelectedFolder(e.target.value);
                setSelectedContent(null);
                loadContents(selectedClass, selectedSubject, e.target.value);
              }}
            >
              <option value="">Select Folder</option>
              {folders.map((f) => (
                <option key={f} value={f}>
                  {f}
                </option>
              ))}
            </select>
          )}

          {contents.length > 0 && (
            <select onChange={(e) => setSelectedContent(e.target.value)}>
              <option value="">Select Content</option>
              {contents.map((c) => (
                <option key={c.path} value={c.path}>
                  {c.title}
                </option>
              ))}
            </select>
          )}
        </div>

        {/* 🔹 Sessions */}
        <div style={{ marginTop: "20px" }}>
          {sessions.map((s) => (
            <div
              key={s.id}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "5px",
                background: s.id === sessionId ? "#ddd" : "transparent",
              }}
            >
              <span onClick={() => switchSession(s)} style={{ cursor: "pointer", flex: 1 }}>
                {s.title || "New Chat"}
              </span>
              <button onClick={() => renameSession(s)}>✏️</button>
              <button onClick={() => deleteSession(s)}>🗑️</button>
            </div>
          ))}
        </div>

        {/* 🔹 Admin Panel */}
        {isAdmin && (
        <div style={{ marginTop: "20px", borderTop: "1px solid #aaa", paddingTop: "10px" }}>
          <h4>Admin Panel</h4>
          <button onClick={handleReindex} disabled={adminRunning}>🔄 Reindex Knowledge Base</button>
          <button onClick={handleIncrementalReindex} disabled={adminRunning}>⚡ Incremental Reindex</button>

          {/* 🔹 Simple visual feedback */}
          {adminRunning && <div style={{ marginTop: "10px", color: "blue" }}>Processing...</div>}
          {adminMessage && <div style={{ marginTop: "10px", color: adminRunning ? "blue" : "green" }}>{adminMessage}</div>}
        </div>
        )}
      </div>

      {/* 💬 MAIN CHAT */}
      <div style={{ flex: 1, padding: "10px" }}>
        <VoiceControl onResult={handleVoice} />
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask something..."
        />
        <button onClick={handleSend}>Send</button>

        {/* 🔹 PDF Viewer */}
        {pdfBlobUrl && (
          <div style={{ marginTop: "20px", border: "1px solid #ccc", padding: "5px" }}>
            <iframe src={pdfBlobUrl} style={{ width: "100%", height: "400px" }} />
          </div>
        )}

        {/* 🔹 Chat Messages */}
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