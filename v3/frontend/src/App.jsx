import React, { useEffect, useState } from "react";
import { FiBookOpen, FiLogOut, FiUser } from "react-icons/fi";
import { GiBrain } from "react-icons/gi";
import ChatPanel from "./components/ChatPanel";
import Login from "./components/Login";
import { apiFetch, clearStoredSessionState } from "./services/api";

function App() {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [isBootstrappingAuth, setIsBootstrappingAuth] = useState(true);
  const [sessionExpired, setSessionExpired] = useState(false);
  const [userName, setUserName] = useState(localStorage.getItem("username") || "student");
  const [userRole, setUserRole] = useState(localStorage.getItem("role") || "user");
  const [uiDensity, setUiDensity] = useState(localStorage.getItem("ui_density") || "70");

  const refreshUserIdentity = () => {
    setUserName(localStorage.getItem("username") || "student");
    setUserRole(localStorage.getItem("role") || "user");
  };

  useEffect(() => {
    let isMounted = true;

    const bootstrapSession = async () => {
      try {
        const res = await apiFetch("/auth/session", { skipSessionExpiredEvent: true });
        if (!isMounted) return;

        if (!res.ok) {
          clearStoredSessionState();
          setIsLoggedIn(false);
          setUserName("student");
          setUserRole("user");
          return;
        }

        const data = await res.json();
        localStorage.setItem("username", data.username || "student");
        localStorage.setItem("role", data.role || "user");
        setUserName(data.username || "student");
        setUserRole(data.role || "user");
        setIsLoggedIn(Boolean(data.authenticated));
      } catch {
        if (!isMounted) return;
        clearStoredSessionState();
        setIsLoggedIn(false);
        setUserName("student");
        setUserRole("user");
      } finally {
        if (isMounted) {
          setIsBootstrappingAuth(false);
        }
      }
    };

    bootstrapSession();

    const onExpired = () => {
      setIsLoggedIn(false);
      setSessionExpired(true);
      setUserName("student");
      setUserRole("user");
    };

    window.addEventListener("session:expired", onExpired);
    return () => {
      isMounted = false;
      window.removeEventListener("session:expired", onExpired);
    };
  }, []);

  const handleLogin = () => {
    setSessionExpired(false);
    setIsLoggedIn(true);
    refreshUserIdentity();
  };

  const handleLogout = async () => {
    try {
      await apiFetch("/logout", { method: "POST", skipSessionExpiredEvent: true });
    } catch {
      // Local cleanup still happens if the backend is unavailable.
    }
    clearStoredSessionState();
    setIsLoggedIn(false);
    setSessionExpired(false);
    setUserName("student");
    setUserRole("user");
  };

  const handleDensityChange = (event) => {
    const next = String(event || "70");
    setUiDensity(next);
    localStorage.setItem("ui_density", next);
  };

  return (
    <div className={`app-shell app-shell--density-${uiDensity}`}>
      <div className="app-shell__backdrop" />
      <div className={`app-shell__content ${isLoggedIn ? "app-shell__content--workspace" : ""}`}>
        <header className="app-shell__header">
          <div className="app-shell__brand">
            <span className="app-shell__brand-mark">
              <GiBrain />
            </span>
            <div>
              <h1>Brain Teaser</h1>
              <p>Focused learning, guided conversations, and structured revision.</p>
            </div>
          </div>
          <div className="app-shell__density" role="group" aria-label="UI tightness">
            <span className="app-shell__density-label">Tightness</span>
            <button
              type="button"
              className={`app-shell__density-option ${uiDensity === "100" ? "is-active" : ""}`}
              onClick={() => handleDensityChange("100")}
              aria-pressed={uiDensity === "100"}
            >
              100%
            </button>
            <button
              type="button"
              className={`app-shell__density-option ${uiDensity === "90" ? "is-active" : ""}`}
              onClick={() => handleDensityChange("90")}
              aria-pressed={uiDensity === "90"}
            >
              90%
            </button>
            <button
              type="button"
              className={`app-shell__density-option ${uiDensity === "80" ? "is-active" : ""}`}
              onClick={() => handleDensityChange("80")}
              aria-pressed={uiDensity === "80"}
            >
              80%
            </button>
            <button
              type="button"
              className={`app-shell__density-option ${uiDensity === "70" ? "is-active" : ""}`}
              onClick={() => handleDensityChange("70")}
              aria-pressed={uiDensity === "70"}
            >
              70%
            </button>
          </div>
          <div className="app-shell__header-right">
            {isLoggedIn ? (
              <div className="app-shell__account">
                <div className="app-shell__account-meta">
                  <span className="app-shell__account-avatar">
                    <FiUser />
                  </span>
                  <div>
                    <strong>{userName}</strong>
                    <span>{userRole}</span>
                  </div>
                </div>
                <button type="button" className="app-shell__logout" onClick={handleLogout}>
                  <FiLogOut />
                  <span>Logout</span>
                </button>
              </div>
            ) : (
              <div className="app-shell__badge">
                <FiBookOpen />
                <span>Dark Study Workspace</span>
              </div>
            )}
          </div>
        </header>

        {!isLoggedIn && !isBootstrappingAuth ? (
          <Login onLogin={handleLogin} sessionExpired={sessionExpired} />
        ) : null}
        {isLoggedIn ? (
          <ChatPanel />
        ) : null}
      </div>
    </div>
  );
}

export default App;
