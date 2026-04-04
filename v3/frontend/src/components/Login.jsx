import React, { useState } from "react";
import {
  FiAlertCircle,
  FiArrowRight,
  FiCalendar,
  FiCheckCircle,
  FiBookOpen,
  FiLock,
  FiMessageSquare,
  FiRotateCcw,
  FiUserPlus,
  FiUser,
  FiZap,
} from "react-icons/fi";
import { GiBrain } from "react-icons/gi";
import DatePicker from "react-datepicker";
import "react-datepicker/dist/react-datepicker.css";
import { API_BASE_URL, getEnvelopeMessage, messageSummary, parseApiError } from "../services/api";

export default function Login({ onLogin, sessionExpired = false }) {
  const [mode, setMode] = useState("login");

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [registerEmail, setRegisterEmail] = useState("");
  const [registerDob, setRegisterDob] = useState(null);
  const [registerPassword, setRegisterPassword] = useState("");
  const [registerRole, setRegisterRole] = useState("student");

  const [resetEmail, setResetEmail] = useState("");
  const [resetDob, setResetDob] = useState(null);
  const [newPassword, setNewPassword] = useState("");

  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [isLoggingIn, setIsLoggingIn] = useState(false);

  const apiBaseUrl = API_BASE_URL;

  const toErrorText = (payload, fallback) => {
    if (!payload) return fallback;

    const detail = payload.detail ?? payload;

    if (typeof detail === "string") return detail;

    if (Array.isArray(detail)) {
      const messages = detail
        .map((item) => {
          if (typeof item === "string") return item;
          if (item && typeof item.msg === "string") return item.msg;
          return null;
        })
        .filter(Boolean);

      if (messages.length > 0) return messages.join("; ");
    }

    if (typeof detail === "object") {
      if (typeof detail.msg === "string") return detail.msg;
      try {
        return JSON.stringify(detail);
      } catch {
        return fallback;
      }
    }

    return fallback;
  };

  const clearFeedback = () => {
    setError("");
    setSuccess("");
  };

  const switchMode = (nextMode) => {
    clearFeedback();
    setMode(nextMode);
  };

  const handleLogin = async () => {
    if (isLoggingIn) return;
    clearFeedback();

    if (!email.trim() || !password) {
      setError("Enter both email and password to continue.");
      return;
    }

    setIsLoggingIn(true);
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 12000);

    try {
      const res = await fetch(`${apiBaseUrl}/login`, {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
        },
        signal: controller.signal,
        body: JSON.stringify({ email, password }),
      });

      if (!res.ok) {
        setError(await parseApiError(res, "Invalid email or password."));
        return;
      }

      const data = await res.json();

      if (data.access_token) {
        localStorage.removeItem("token");
        localStorage.setItem("username", data.username || email);
        localStorage.setItem("role", data.role || "user");
        onLogin();
        return;
      }

      setError("Login failed: invalid credentials.");
    } catch (err) {
      console.error("❌ Login error:", err);
      if (err?.name === "AbortError") {
        setError(
          `Login request timed out. Backend may still be starting. Verify ${apiBaseUrl} is running and try again.`
        );
      } else {
        setError(`Could not reach the server at ${apiBaseUrl}. Please check backend status and try again.`);
      }
    } finally {
      clearTimeout(timeoutId);
      setIsLoggingIn(false);
    }
  };

  const handleRegister = async () => {
    clearFeedback();

    if (!registerDob) {
      setError("Please select date of birth.");
      return;
    }

    try {
      const res = await fetch(`${apiBaseUrl}/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          first_name: firstName,
          last_name: lastName,
          email: registerEmail,
          dob: registerDob.toISOString().slice(0, 10),
          password: registerPassword,
          role: registerRole,
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        const envelopeMessage = getEnvelopeMessage(data);
        setError(envelopeMessage ? messageSummary(envelopeMessage) : toErrorText(data, "Unable to register user."));
        return;
      }

      setSuccess("Registration successful. You can now login using your email and password.");
      setEmail(registerEmail);
      setPassword("");
      setMode("login");
    } catch (err) {
      console.error("❌ Register error:", err);
      setError(`Could not register right now. Unable to reach ${apiBaseUrl}.`);
    }
  };

  const handleResetPassword = async () => {
    clearFeedback();

    if (!resetDob) {
      setError("Please select date of birth.");
      return;
    }

    try {
      const res = await fetch(`${apiBaseUrl}/reset-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: resetEmail,
          dob: resetDob.toISOString().slice(0, 10),
          new_password: newPassword,
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        const envelopeMessage = getEnvelopeMessage(data);
        setError(envelopeMessage ? messageSummary(envelopeMessage) : toErrorText(data, "Unable to reset password."));
        return;
      }

      setSuccess("Password reset successful. Please login with your new password.");
      setEmail(resetEmail);
      setPassword("");
      setMode("login");
    } catch (err) {
      console.error("❌ Reset password error:", err);
      setError(`Could not reset password right now. Unable to reach ${apiBaseUrl}.`);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter") {
      if (mode === "login") handleLogin();
      if (mode === "register") handleRegister();
      if (mode === "reset") handleResetPassword();
    }
  };

  return (
    <div className="login-shell">
      <section className="login-hero">
        <div>
          <div className="login-hero__eyebrow">
            <GiBrain />
            <span>AI-powered learning workspace</span>
          </div>
          <h2>Study in one focused interface.</h2>
          <p>
            Chat with your material, review lesson guidance, run quizzes, and keep
            your study sessions organized in a single, clean black workspace.
          </p>
        </div>

        <div className="login-hero__grid">
          <div className="login-hero__tile">
            <FiMessageSquare size={18} />
            <h3>Context-aware chat</h3>
            <p>Work against selected source material without breaking your flow.</p>
          </div>
          <div className="login-hero__tile">
            <FiBookOpen size={18} />
            <h3>Structured lessons</h3>
            <p>Move from question-answering into guided learning when needed.</p>
          </div>
          <div className="login-hero__tile">
            <FiZap size={18} />
            <h3>Fast revision</h3>
            <p>Use focused quiz and flashcard flows for short review cycles.</p>
          </div>
          <div className="login-hero__tile">
            <FiLock size={18} />
            <h3>Secure sessions</h3>
            <p>Expired sessions redirect cleanly so users always re-authenticate.</p>
          </div>
        </div>
      </section>

      <section className="login-card">
        <div className="login-card__header">
          <h3>
            {mode === "login" && "Login"}
            {mode === "register" && "Create account"}
            {mode === "reset" && "Reset password"}
          </h3>
          <p>
            {mode === "login" && "Sign in to continue your current study workspace."}
            {mode === "register" && "Register using your profile details and email user ID."}
            {mode === "reset" && "Reset password by verifying your email and date of birth."}
          </p>
        </div>

        <div className="auth-mode-tabs">
          <button
            type="button"
            className={mode === "login" ? "active" : ""}
            onClick={() => switchMode("login")}
          >
            <FiArrowRight />
            <span>Login</span>
          </button>
          <button
            type="button"
            className={mode === "register" ? "active" : ""}
            onClick={() => switchMode("register")}
          >
            <FiUserPlus />
            <span>Register</span>
          </button>
          <button
            type="button"
            className={mode === "reset" ? "active" : ""}
            onClick={() => switchMode("reset")}
          >
            <FiRotateCcw />
            <span>Reset</span>
          </button>
        </div>

        {sessionExpired && (
          <div className="login-alert login-alert--warning">
            <FiAlertCircle />
            <span>Your session has expired. Please log in again.</span>
          </div>
        )}

        {error && !sessionExpired && (
          <div className="login-alert login-alert--error">
            <FiAlertCircle />
            <span>{error}</span>
          </div>
        )}

        {success && (
          <div className="login-alert login-alert--success">
            <FiCheckCircle />
            <span>{success}</span>
          </div>
        )}

        {mode === "login" && (
          <div className="login-form">
            <div className="login-field">
              <label htmlFor="email">Email</label>
              <div className="login-field__input">
                <FiUser />
                <input
                  id="email"
                  placeholder="Email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  onKeyDown={handleKeyDown}
                />
              </div>
            </div>

            <div className="login-field">
              <label htmlFor="password">Password</label>
              <div className="login-field__input">
                <FiLock />
                <input
                  id="password"
                  placeholder="Password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  onKeyDown={handleKeyDown}
                />
              </div>
            </div>

            <button type="button" className="login-submit" onClick={handleLogin} disabled={isLoggingIn}>
              <span>{isLoggingIn ? "Connecting..." : "Continue"}</span>
              <FiArrowRight />
            </button>
          </div>
        )}

        {mode === "register" && (
          <div className="login-form">
            <div className="login-field login-field-grid">
              <div>
                <label htmlFor="firstName">First Name</label>
                <div className="login-field__input">
                  <FiUser />
                  <input
                    id="firstName"
                    placeholder="First Name"
                    value={firstName}
                    onChange={(e) => setFirstName(e.target.value)}
                    onKeyDown={handleKeyDown}
                  />
                </div>
              </div>
              <div>
                <label htmlFor="lastName">Last Name</label>
                <div className="login-field__input">
                  <FiUser />
                  <input
                    id="lastName"
                    placeholder="Last Name"
                    value={lastName}
                    onChange={(e) => setLastName(e.target.value)}
                    onKeyDown={handleKeyDown}
                  />
                </div>
              </div>
            </div>

            <div className="login-field">
              <label htmlFor="registerEmail">Email</label>
              <div className="login-field__input">
                <FiUser />
                <input
                  id="registerEmail"
                  placeholder="Email"
                  value={registerEmail}
                  onChange={(e) => setRegisterEmail(e.target.value)}
                  onKeyDown={handleKeyDown}
                />
              </div>
            </div>

            <div className="login-field">
              <label>Date of Birth</label>
              <div className="login-field__input login-date-input">
                <FiCalendar />
                <DatePicker
                  selected={registerDob}
                  onChange={(date) => setRegisterDob(date)}
                  dateFormat="yyyy-MM-dd"
                  showYearDropdown
                  scrollableYearDropdown
                  yearDropdownItemNumber={100}
                  placeholderText="Select DOB"
                  maxDate={new Date()}
                />
              </div>
            </div>

            <div className="login-field">
              <label htmlFor="registerPassword">Password</label>
              <div className="login-field__input">
                <FiLock />
                <input
                  id="registerPassword"
                  placeholder="Password"
                  type="password"
                  value={registerPassword}
                  onChange={(e) => setRegisterPassword(e.target.value)}
                  onKeyDown={handleKeyDown}
                />
              </div>
            </div>

            <div className="login-field">
              <label htmlFor="registerRole">Register as</label>
              <div className="login-field__input">
                <FiBookOpen />
                <select
                  id="registerRole"
                  aria-label="Register as"
                  value={registerRole}
                  onChange={(e) => setRegisterRole(e.target.value)}
                >
                  <option value="student">Student</option>
                  <option value="teacher">Teacher</option>
                  <option value="parent">Parent</option>
                </select>
              </div>
            </div>

            <button className="login-submit" onClick={handleRegister}>
              <span>Create account</span>
              <FiUserPlus />
            </button>
          </div>
        )}

        {mode === "reset" && (
          <div className="login-form">
            <div className="login-field">
              <label htmlFor="resetEmail">Email</label>
              <div className="login-field__input">
                <FiUser />
                <input
                  id="resetEmail"
                  placeholder="Email"
                  value={resetEmail}
                  onChange={(e) => setResetEmail(e.target.value)}
                  onKeyDown={handleKeyDown}
                />
              </div>
            </div>

            <div className="login-field">
              <label>Date of Birth</label>
              <div className="login-field__input login-date-input">
                <FiCalendar />
                <DatePicker
                  selected={resetDob}
                  onChange={(date) => setResetDob(date)}
                  dateFormat="yyyy-MM-dd"
                  showYearDropdown
                  scrollableYearDropdown
                  yearDropdownItemNumber={100}
                  placeholderText="Select DOB"
                  maxDate={new Date()}
                />
              </div>
            </div>

            <div className="login-field">
              <label htmlFor="newPassword">New Password</label>
              <div className="login-field__input">
                <FiLock />
                <input
                  id="newPassword"
                  placeholder="New Password"
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  onKeyDown={handleKeyDown}
                />
              </div>
            </div>

            <button className="login-submit" onClick={handleResetPassword}>
              <span>Reset password</span>
              <FiRotateCcw />
            </button>
          </div>
        )}

        <div className="login-note">
          Email acts as your unique user ID. Social login (Google/Facebook) can be integrated later.
        </div>
      </section>
    </div>
  );
}
