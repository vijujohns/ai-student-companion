import React, { useEffect, useRef, useState } from "react";
import { FiArrowRight, FiBookOpen, FiCreditCard, FiDownload, FiLogOut, FiMenu, FiMoreVertical, FiUser, FiWifi, FiWifiOff } from "react-icons/fi";
import { GiBrain } from "react-icons/gi";
import ChatPanel from "./components/ChatPanel";
import Login from "./components/Login";
import {
  API_BASE_URL,
  apiFetch,
  clearStoredSessionState,
  getOfflinePendingCount,
  startOfflineSyncLoop,
} from "./services/api";
import { setupInstallPrompt } from "./services/pwa";
import { useWorkspaceNavigation } from "./hooks/useWorkspaceNavigation";

function App() {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [isBootstrappingAuth, setIsBootstrappingAuth] = useState(true);
  const [sessionExpired, setSessionExpired] = useState(false);
  const [userName, setUserName] = useState(localStorage.getItem("username") || "student");
  const [userRole, setUserRole] = useState(localStorage.getItem("role") || "user");
  const [uiDensity, setUiDensity] = useState(localStorage.getItem("ui_density") || "70");
  const [isOnline, setIsOnline] = useState(typeof navigator !== "undefined" ? navigator.onLine : true);
  const [pendingSyncCount, setPendingSyncCount] = useState(getOfflinePendingCount());
  const [canInstallApp, setCanInstallApp] = useState(false);
  const [promptInstall, setPromptInstall] = useState(null);
  const [backendStatus, setBackendStatus] = useState("checking");
  const [backendStatusText, setBackendStatusText] = useState("Checking backend");
  const [headerAccountMenuOpen, setHeaderAccountMenuOpen] = useState(false);
  const [externalTabRequest, setExternalTabRequest] = useState(null);
  const [sidebarPopupOpen, setSidebarPopupOpen] = useState(false);
  const accountMenuRef = useRef(null);

  // Workspace navigation state management
  const workspaceNavigation = useWorkspaceNavigation("chat");

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

  useEffect(() => {
    let cancelled = false;

    const probeBackend = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/health/runtime`, {
          method: "GET",
          credentials: "include",
        });

        if (cancelled) return;

        if (!res.ok) {
          setBackendStatus("degraded");
          setBackendStatusText(`Degraded (${res.status})`);
          return;
        }

        const data = await res.json();
        if (cancelled) return;
        const status = String(data?.status || "ok").toLowerCase();
        if (status === "ok") {
          setBackendStatus("healthy");
          setBackendStatusText("Healthy");
        } else {
          setBackendStatus("degraded");
          setBackendStatusText("Degraded");
        }
      } catch {
        if (cancelled) return;
        setBackendStatus("down");
        setBackendStatusText("Down");
      }
    };

    probeBackend();
    const timer = setInterval(probeBackend, 20000);

    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    const onOnline = () => setIsOnline(true);
    const onOffline = () => setIsOnline(false);
    const onQueueUpdated = (event) => {
      const next = event?.detail?.pending;
      setPendingSyncCount(typeof next === "number" ? next : getOfflinePendingCount());
    };
    const onSyncFinished = () => setPendingSyncCount(getOfflinePendingCount());

    window.addEventListener("online", onOnline);
    window.addEventListener("offline", onOffline);
    window.addEventListener("offline:queue-updated", onQueueUpdated);
    window.addEventListener("offline:sync-finished", onSyncFinished);

    const stopSyncLoop = startOfflineSyncLoop();
    const promptFn = setupInstallPrompt(setCanInstallApp);
    setPromptInstall(() => promptFn);

    return () => {
      stopSyncLoop();
      window.removeEventListener("online", onOnline);
      window.removeEventListener("offline", onOffline);
      window.removeEventListener("offline:queue-updated", onQueueUpdated);
      window.removeEventListener("offline:sync-finished", onSyncFinished);
    };
  }, []);

  useEffect(() => {
    if (!headerAccountMenuOpen) return undefined;

    const handlePointerDown = (event) => {
      if (accountMenuRef.current && !accountMenuRef.current.contains(event.target)) {
        setHeaderAccountMenuOpen(false);
      }
    };

    const handleEscape = (event) => {
      if (event.key === "Escape") {
        setHeaderAccountMenuOpen(false);
      }
    };

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleEscape);

    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [headerAccountMenuOpen]);

  const handleLogin = () => {
    setSessionExpired(false);
    setIsLoggedIn(true);
    refreshUserIdentity();
  };

  const handleOpenWorkspaceTab = (tab) => {
    setExternalTabRequest({ tab, requestId: Date.now() });
    setHeaderAccountMenuOpen(false);
  };

  const handleLogout = async () => {
    setHeaderAccountMenuOpen(false);
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

  const handleInstallApp = async () => {
    if (typeof promptInstall !== "function") return;
    const installed = await promptInstall();
    if (installed) setCanInstallApp(false);
  };

  const workspaceStatusLabel = isOnline
    ? pendingSyncCount > 0
      ? `${pendingSyncCount} queued updates syncing`
      : "Online"
    : "Offline mode active";
  const brandSupportText = "Study, practice, and stay on track in one place.";

  return (
    <div className={`app-shell app-shell--density-${uiDensity}`}>
      <a
        className="skip-link"
        href="#main-content"
        title="Skip directly to the main content"
      >
        <FiArrowRight aria-hidden="true" />
        <span>Skip to main content</span>
      </a>
      <div className="app-shell__backdrop" />
      <div className={`app-shell__content ${isLoggedIn ? "app-shell__content--workspace" : ""}`}>
        <header className="app-shell__header" role="banner">
          {isLoggedIn && (
            <button
              type="button"
              className="app-shell__workspace-menu-trigger"
              onClick={() => setSidebarPopupOpen(!sidebarPopupOpen)}
              title="Open workspace menu"
              aria-label="Open workspace menu"
            >
              <FiMenu />
            </button>
          )}
          <div className="app-shell__brand">
            <span className="app-shell__brand-mark">
              <GiBrain />
            </span>
            <div className="app-shell__brand-copy">
              <div className="app-shell__brand-title-row">
                <h1>Brain Teaser</h1>
                <span className="app-shell__brand-subtle">ACADEMY</span>
              </div>
              <p>{brandSupportText}</p>
            </div>
          </div>
          <div className="app-shell__header-right">
            {!isLoggedIn ? (
              <div className={`app-shell__network ${isOnline ? "is-online" : "is-offline"}`} role="status" aria-live="polite">
                <span className="app-shell__network-icon">{isOnline ? <FiWifi /> : <FiWifiOff />}</span>
                <span>{workspaceStatusLabel}</span>
                <span className={`app-shell__backend-chip app-shell__backend-chip--${backendStatus}`}>
                  Backend: {backendStatusText}
                </span>
                {canInstallApp ? (
                  <button type="button" className="app-shell__install" onClick={handleInstallApp}>
                    <FiDownload />
                    <span>Install app</span>
                  </button>
                ) : null}
              </div>
            ) : null}
            {isLoggedIn ? (
              <div className={`app-shell__account ${headerAccountMenuOpen ? "is-open" : ""}`} ref={accountMenuRef}>
                <div className="app-shell__account-meta">
                  <span className="app-shell__account-avatar">
                    <FiUser />
                  </span>
                  <div>
                    <strong>{userName}</strong>
                    <span>{userRole}</span>
                  </div>
                </div>
                <button
                  type="button"
                  className="app-shell__account-trigger"
                  onClick={() => setHeaderAccountMenuOpen((prev) => !prev)}
                  aria-label="Open account menu"
                  aria-controls="account-menu"
                  aria-haspopup="menu"
                  aria-expanded={headerAccountMenuOpen}
                  title="Open account menu"
                >
                  <FiMoreVertical />
                </button>
                {headerAccountMenuOpen ? (
                  <div id="account-menu" className="app-shell__account-menu" role="menu" aria-label="Account menu">
                    <div className="app-shell__account-menu-section">
                      <span className="app-shell__account-menu-section-label">Workspace status</span>
                      <div className="app-shell__account-status-list" role="status" aria-live="polite">
                        <span className={`app-shell__account-status-row ${isOnline ? "is-online" : "is-offline"}`}>
                          <span className="app-shell__network-icon">{isOnline ? <FiWifi /> : <FiWifiOff />}</span>
                          <span>{workspaceStatusLabel}</span>
                        </span>
                        <span className={`app-shell__backend-chip app-shell__backend-chip--${backendStatus}`}>
                          Backend: {backendStatusText}
                        </span>
                      </div>
                      {canInstallApp ? (
                        <button
                          type="button"
                          className="app-shell__account-menu-item"
                          role="menuitem"
                          onClick={handleInstallApp}
                        >
                          <FiDownload />
                          <span>Install app</span>
                        </button>
                      ) : null}
                    </div>
                    <div className="app-shell__account-menu-divider" aria-hidden="true" />
                    <div className="app-shell__account-menu-section">
                      <span className="app-shell__account-menu-section-label">Display density</span>
                      <div className="app-shell__density app-shell__density--menu" role="group" aria-label="Display density">
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
                    </div>
                    <div className="app-shell__account-menu-divider" aria-hidden="true" />
                    <button
                      type="button"
                      className="app-shell__account-menu-item"
                      role="menuitem"
                      onClick={() => handleOpenWorkspaceTab("profile")}
                    >
                      <FiUser />
                      <span>Profile</span>
                    </button>
                    <button
                      type="button"
                      className="app-shell__account-menu-item"
                      role="menuitem"
                      onClick={() => handleOpenWorkspaceTab("billing")}
                    >
                      <FiCreditCard />
                      <span>Billing</span>
                    </button>
                    <button
                      type="button"
                      className="app-shell__account-menu-item app-shell__account-menu-item--danger"
                      role="menuitem"
                      onClick={handleLogout}
                    >
                      <FiLogOut />
                      <span>Logout</span>
                    </button>
                  </div>
                ) : null}
              </div>
            ) : null}
          </div>
        </header>

        <main id="main-content" className="app-shell__main" role="main" aria-label="Application content">
          {!isLoggedIn && !isBootstrappingAuth ? (
            <Login onLogin={handleLogin} sessionExpired={sessionExpired} />
          ) : null}
          {isLoggedIn ? (
            <ChatPanel externalTabRequest={externalTabRequest} workspaceNavigation={workspaceNavigation} sidebarPopupOpen={sidebarPopupOpen} setSidebarPopupOpen={setSidebarPopupOpen} />
          ) : null}
        </main>
      </div>
    </div>
  );
}

export default App;
