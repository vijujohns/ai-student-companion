import React, { useState } from "react";

export default function Login({ onLogin }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const handleLogin = async () => {
    try {
      const res = await fetch("http://127.0.0.1:8000/login", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ username, password })
      });

      if (!res.ok) {
        alert("Login failed: " + res.statusText);
        return;
      }

      const data = await res.json();

      if (data.access_token) {
        // ✅ Save auth token
        localStorage.setItem("token", data.access_token);

        // ✅ Save username and role for ChatPanel
        localStorage.setItem("username", username);
        localStorage.setItem("role", data.role || "user"); // fallback to 'user' if backend doesn't provide role

        onLogin();
      } else {
        alert("Login failed: Invalid credentials");
      }
    } catch (err) {
      console.error("❌ Login error:", err);
      alert("Login error. See console for details.");
    }
  };

  return (
    <div>
      <h3>Login</h3>
      <input
        placeholder="username"
        value={username}
        onChange={e => setUsername(e.target.value)}
      />
      <input
        placeholder="password"
        type="password"
        value={password}
        onChange={e => setPassword(e.target.value)}
      />
      <button onClick={handleLogin}>Login</button>
    </div>
  );
}