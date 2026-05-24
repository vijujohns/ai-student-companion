import React, { useState, useRef } from 'react';
import { FaPlus, FaPaperPlane, FaTimes, FaStop } from 'react-icons/fa';
import VoiceControl from './VoiceControl';
import './MessageInput.css';

const MessageInput = ({
  onSendMessage,
  isLoading,
  placeholder = "Type your message...",
  disabled = false,
  voiceControlProps = {},
  isStreaming = false,
  onStopStreaming = () => {},
  onNewChat = () => {},
  value: controlledValue,
  onChangeValue,
}) => {
  const [message, setMessage] = useState(controlledValue ?? '');
  const fileInputRef = useRef(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!message.trim()) return;

    const messageData = {
      content: message.trim(),
    };

    try {
      await onSendMessage(messageData);
      setMessage('');
    } catch (error) {
      console.error('Failed to send message:', error);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  React.useEffect(() => {
    if (controlledValue !== undefined && controlledValue !== message) {
      setMessage(controlledValue);
    }
  }, [controlledValue, message]);

  const updateMessage = (value) => {
    if (onChangeValue) {
      onChangeValue(value);
    }
    setMessage(value);
  };

  const isDisabled = disabled || isLoading;
  const canSend = !isDisabled && message.trim().length > 0;

  return (
    <div className="message-input-container">
      <form onSubmit={handleSubmit} className="message-input-form">
        <div className="input-group">
          <button
            type="button"
            className="new-chat-button message-action-button"
            onClick={onNewChat}
            disabled={isDisabled}
            title="Start new chat session"
            aria-label="Start new chat session"
          >
            <FaPlus />
          </button>

          <textarea
            value={message}
            onChange={(e) => updateMessage(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            disabled={isDisabled}
            rows={1}
            className="message-textarea"
          />

          <div className="input-actions">
            <VoiceControl
              {...voiceControlProps}
              compact
              onResult={(text) => {
                updateMessage(text);
                if (voiceControlProps.onResult) {
                  voiceControlProps.onResult(text);
                }
              }}
            />

            {isStreaming ? (
              <button
                type="button"
                className="stop-button message-action-button"
                onClick={onStopStreaming}
                title="Stop response"
                aria-label="Stop response"
              >
                <FaStop />
              </button>
            ) : (
              <button
                type="submit"
                className={`send-button message-action-button${canSend ? " send-button--ready" : ""}`}
                disabled={!canSend}
                aria-label="Send message"
              >
                <FaPaperPlane />
              </button>
            )}
          </div>
        </div>
      </form>
    </div>
  );
};

export default MessageInput;