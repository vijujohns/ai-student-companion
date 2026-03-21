import React, { useState } from "react";

const VoiceControl = ({ onResult }) => {
  const [listening, setListening] = useState(false);

  const SpeechRecognition =
    window.SpeechRecognition || window.webkitSpeechRecognition;

  const recognition = new SpeechRecognition();

  recognition.lang = "en-US";
  recognition.continuous = false;

  recognition.onstart = () => {
    setListening(true);
  };

  recognition.onend = () => {
    setListening(false);
  };

  recognition.onresult = (event) => {
    const text = event.results[0][0].transcript;
    onResult(text);
  };

  const startListening = () => {
    recognition.start();
  };

  return (
    <div>
      <button onClick={startListening}>
        {listening ? "🎤 Listening..." : "🎤 Speak"}
      </button>
    </div>
  );
};

export default VoiceControl;