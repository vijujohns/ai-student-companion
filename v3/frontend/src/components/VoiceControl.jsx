import React, { useCallback, useEffect, useState } from "react";
import { FiMic, FiMicOff } from "react-icons/fi";

const VoiceControl = ({ onResult, compact = false }) => {
  const [listening, setListening] = useState(false);
  const keyboardShortcut = "Ctrl+Shift+M";

  const startListening = useCallback(() => {
    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.lang = "en-US";
    recognition.continuous = false;

    recognition.onstart = () => setListening(true);
    recognition.onend = () => setListening(false);
    recognition.onresult = (event) => {
      const text = event.results[0][0].transcript;
      onResult(text);
    };

    recognition.start();
  }, [onResult]);

  const SpeechRecognition =
    window.SpeechRecognition || window.webkitSpeechRecognition;
  const tooltip = !SpeechRecognition
    ? "Voice input not supported"
    : listening
      ? `Listening for voice input (${keyboardShortcut})`
      : `Voice input (${keyboardShortcut})`;

  useEffect(() => {
    if (!SpeechRecognition) return;

    const handleKeyDown = (event) => {
      if (event.defaultPrevented) return;
      if (event.key.toLowerCase() !== "m") return;
      if (!event.ctrlKey || !event.shiftKey) return;
      event.preventDefault();
      startListening();
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [SpeechRecognition, startListening]);

  return (
    <button
      type="button"
      className={`icon-button voice-control ${compact ? "voice-control--compact" : ""} ${listening ? "voice-control--listening" : ""}`.trim()}
      onClick={startListening}
      disabled={!SpeechRecognition}
      title={tooltip}
      aria-label={tooltip}
      aria-pressed={listening}
    >
      {listening ? <FiMic /> : <FiMicOff />}
      {!compact && <span>{listening ? "Listening" : "Voice"}</span>}
    </button>
  );
};

export default VoiceControl;