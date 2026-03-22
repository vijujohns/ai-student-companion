import React, { useState } from "react";
import ChatPanel from "./components/ChatPanel";
import Login from "./components/Login";

function App() {
  const [isLoggedIn, setIsLoggedIn] = useState(
    !!localStorage.getItem("token")
  );

  return (
    <div>
      <h2>AI Student Tutor</h2>

      {!isLoggedIn ? (
        <Login onLogin={() => setIsLoggedIn(true)} />
      ) : (
        <ChatPanel />
      )}
    </div>
  );
}

export default App;