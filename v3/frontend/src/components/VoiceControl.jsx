import React, { useState } from "react";
import { FiMic, FiMicOff } from "react-icons/fi";

const VoiceControl = ({ onResult, compact = false }) => {
  const [listening, setListening] = useState(false);

  const startListening = () => {
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
  };

  const SpeechRecognition =
    window.SpeechRecognition || window.webkitSpeechRecognition;
  const tooltip = !SpeechRecognition
    ? "Voice input not supported"
    : listening
      ? "Listening for voice input"
      : "Voice input";

  return (
    <button
      type="button"
      className={`icon-button voice-control ${compact ? "voice-control--compact" : ""}`.trim()}
      onClick={startListening}
      disabled={!SpeechRecognition}
      title={tooltip}
      aria-label={tooltip}
    >
      {listening ? <FiMicOff /> : <FiMic />}
      {!compact && <span>{listening ? "Listening" : "Voice"}</span>}
    </button>
  );
};

export default VoiceControl;