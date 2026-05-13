import React, { useState, useRef } from 'react';
import { FaPaperclip, FaPaperPlane, FaTimes, FaVolumeUp, FaVolumeMute, FaStop } from 'react-icons/fa';
import VoiceControl from './VoiceControl';
import LanguagePicker from './LanguagePicker';
import './MessageInput.css';

const MessageInput = ({
  onSendMessage,
  isLoading,
  placeholder = "Type your message...",
  disabled = false,
  voiceControlProps = {},
  languagePickerProps = {},
  autoSpeak = false,
  onToggleAutoSpeak = () => {},
  isStreaming = false,
  onStopStreaming = () => {}
}) => {
  const [message, setMessage] = useState('');
  const [selectedFiles, setSelectedFiles] = useState([]);
  const fileInputRef = useRef(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!message.trim() && selectedFiles.length === 0) return;

    const messageData = {
      content: message.trim(),
      attachments: selectedFiles
    };

    try {
      await onSendMessage(messageData);
      setMessage('');
      setSelectedFiles([]);
    } catch (error) {
      console.error('Failed to send message:', error);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const handleFileSelect = (e) => {
    const files = Array.from(e.target.files);
    const validFiles = files.filter(file => {
      const maxSize = 10 * 1024 * 1024; // 10MB
      if (file.size > maxSize) {
        alert(`File ${file.name} is too large. Maximum size is 10MB.`);
        return false;
      }
      return true;
    });

    setSelectedFiles(prev => [...prev, ...validFiles.map(file => ({
      file,
      name: file.name,
      size: formatFileSize(file.size),
      type: file.type
    }))]);
  };

  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const removeFile = (index) => {
    setSelectedFiles(prev => prev.filter((_, i) => i !== index));
  };

  const isDisabled = disabled || isLoading;

  return (
    <div className="message-input-container">
      {selectedFiles.length > 0 && (
        <div className="file-attachments">
          {selectedFiles.map((file, index) => (
            <div key={index} className="file-attachment">
              <div className="file-meta">
                <span className="file-name">{file.name}</span>
                <span className="file-size">{file.size}</span>
              </div>
              <button
                type="button"
                className="remove-file"
                onClick={() => removeFile(index)}
                disabled={isDisabled}
                aria-label={`Remove ${file.name}`}
              >
                <FaTimes />
              </button>
            </div>
          ))}
        </div>
      )}

      <form onSubmit={handleSubmit} className="message-input-form">
        <div className="input-group">
          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder={placeholder}
            disabled={isDisabled}
            rows={1}
            className="message-textarea"
          />

          <div className="input-actions">
            <button
              type="button"
              className="file-button"
              onClick={() => fileInputRef.current?.click()}
              disabled={isDisabled}
              title="Attach file"
              aria-label="Attach file"
            >
              <FaPaperclip />
            </button>

            <button
              type="submit"
              className="send-button"
              disabled={isDisabled || (!message.trim() && selectedFiles.length === 0)}
              aria-label="Send message"
            >
              {isLoading ? '⏳' : <FaPaperPlane />}
            </button>
          </div>
        </div>

        <div className="message-input-toolbar">
          <div className="toolbar-group toolbar-group--left">
            <VoiceControl {...voiceControlProps} compact />
            <LanguagePicker {...languagePickerProps} compact={false} />
          </div>

          <div className="toolbar-group toolbar-group--right">
            <button
              type="button"
              className={`icon-button toolbar-tool ${autoSpeak ? "toolbar-tool--active" : ""}`}
              onClick={onToggleAutoSpeak}
              title={autoSpeak ? "Turn auto speak off (Ctrl+Shift+S)" : "Turn auto speak on (Ctrl+Shift+S)"}
              aria-label={autoSpeak ? "Turn auto speak off (Ctrl+Shift+S)" : "Turn auto speak on (Ctrl+Shift+S)"}
            >
              {autoSpeak ? <FaVolumeUp /> : <FaVolumeMute />}
            </button>
            {isStreaming && (
              <button
                type="button"
                className="secondary-button toolbar-stop"
                onClick={onStopStreaming}
                title="Stop response"
                aria-label="Stop response"
              >
                <FaStop />
                <span>Stop</span>
              </button>
            )}
          </div>
        </div>

        <input
          ref={fileInputRef}
          type="file"
          multiple
          onChange={handleFileSelect}
          style={{ display: 'none' }}
          accept="image/*,audio/*,video/*,.pdf,.doc,.docx,.txt"
        />
      </form>
    </div>
  );
};

export default MessageInput;