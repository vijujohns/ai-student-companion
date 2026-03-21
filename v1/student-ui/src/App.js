import React, { useState } from "react";

function App() {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  const [selectedClass, setSelectedClass] = useState("");
  const [selectedSubject, setSelectedSubject] = useState("");
  const [selectedChapter, setSelectedChapter] = useState("");
  const [loading, setLoading] = useState(false);

  // ✅ Suggested prompts
  const prompts = [
    "Summarize this chapter",
    "Explain the main idea",
    "Give important points",
    "Explain in simple words",
    "Give examples from this chapter"
  ];

  const sendMessage = async (customQuestion) => {
    const q = customQuestion || question;

    if (!q) return;

    const userMessage = { role: "user", text: q };
    setMessages((prev) => [...prev, userMessage]);
    setLoading(true);

    try {
      console.log("PAYLOAD:", {
        question: q,
        class: selectedClass,
        subject: selectedSubject,
        chapter: selectedChapter
      });

      const res = await fetch("http://127.0.0.1:8000/query", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          question: q,
          class: selectedClass,
          subject: selectedSubject,
          chapter: selectedChapter
        })
      });

      const data = await res.json();

      const botMessage = { role: "bot", text: data.answer };

      setMessages((prev) => [...prev, botMessage]);
    } catch (err) {
      console.error(err);
      setMessages((prev) => [
        ...prev,
        { role: "bot", text: "Error connecting to server" }
      ]);
    }

    setLoading(false);
    setQuestion("");
  };

  return (
    <div style={{ padding: "20px", fontFamily: "Arial" }}>
      <h2>🎓 AI Student Companion</h2>

      {/* ✅ Filters */}
      <div style={{ marginBottom: "15px" }}>
        <select
          value={selectedClass}
          onChange={(e) => setSelectedClass(e.target.value)}
        >
          <option value="">Select Class</option>
          <option value="10">Class 10</option>
        </select>

        <select
          value={selectedSubject}
          onChange={(e) => setSelectedSubject(e.target.value)}
          style={{ marginLeft: "10px" }}
        >
          <option value="">Select Subject</option>
          <option value="english">English</option>
        </select>

        <select
          value={selectedChapter}
          onChange={(e) => setSelectedChapter(e.target.value)}
          style={{ marginLeft: "10px" }}
        >
          <option value="">All Chapters</option>
          <option value="chapter1">Chapter 1</option>
        </select>
      </div>

      {/* ✅ Suggested prompts */}
      <div style={{ marginBottom: "10px" }}>
        {prompts.map((p, i) => (
          <button
            key={i}
            onClick={() => sendMessage(p)}
            style={{
              marginRight: "5px",
              marginBottom: "5px",
              padding: "5px 10px",
              cursor: "pointer"
            }}
          >
            {p}
          </button>
        ))}
      </div>

      {/* ✅ Chat window */}
      <div
        style={{
          border: "1px solid #ccc",
          height: "400px",
          overflowY: "scroll",
          padding: "10px",
          marginBottom: "10px",
          background: "#f9f9f9"
        }}
      >
        {messages.map((msg, i) => (
          <div key={i} style={{ marginBottom: "10px" }}>
            <b>{msg.role === "user" ? "You" : "AI"}:</b> {msg.text}
          </div>
        ))}

        {loading && <div><i>AI is typing...</i></div>}
      </div>

      {/* ✅ Input */}
      <input
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        placeholder="Ask your question..."
        style={{ width: "70%", padding: "10px" }}
        onKeyDown={(e) => {
          if (e.key === "Enter") sendMessage();
        }}
      />

      <button
        onClick={() => sendMessage()}
        style={{ padding: "10px", marginLeft: "10px" }}
      >
        Send
      </button>
    </div>
  );
}

export default App;