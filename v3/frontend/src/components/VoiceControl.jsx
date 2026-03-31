import React, { useState } from "react";
import { FiMic, FiMicOff } from "react-icons/fi";

const VoiceControl = ({ onResult }) => {
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

  return (
    <button
      type="button"
      className="icon-button"
      onClick={startListening}
      disabled={!SpeechRecognition}
      title={SpeechRecognition ? "Voice input" : "Voice input not supported"}
    >
      {listening ? <FiMicOff /> : <FiMic />}
      <span>{listening ? "Listening" : "Voice"}</span>
    </button>
  );
};

export default VoiceControl;