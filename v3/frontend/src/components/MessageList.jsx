import React, { useEffect, useRef } from 'react';
import { FiGlobe } from 'react-icons/fi';
import MessageContent from './MessageContent';
import SummaryViewer, { looksLikeStructuredSummary } from './SummaryViewer';
import './MessageList.css';

const MessageList = ({
  messages,
  isStreaming,
  currentStream,
  streamStatus,
  preferredLanguage,
  onQuickReply,
  wsError,
  onDismissError,
  sessionId,
  selectedContent,
  onOpenNotes
}) => {
  const messagesEndRef = useRef(null);
  const messagesContainerRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, currentStream]);

  const renderMessage = (msg, index) => {
    const content = msg.translatedContent || msg.text;

    return (
      <div key={index} className={`message-row ${msg.type}`}>
        <div className="message-bubble">
          {msg.type === "ai" && looksLikeStructuredSummary(msg.text) ? (
            <SummaryViewer
              content={content}
              sourceQuery={index > 0 && messages[index - 1]?.type === "user" ? messages[index - 1].text : ""}
              sessionId={sessionId}
              selectedContent={selectedContent}
              onOpenNotes={onOpenNotes}
            />
          ) : (
            <MessageContent content={content} />
          )}

          {msg.type === "ai" && preferredLanguage !== "en" && (
            <button
              type="button"
              className="message-translate-btn"
              onClick={msg.onTranslate}
              disabled={msg.isTranslating}
              aria-label={msg.translatedContent ? "Show original" : `Translate to ${preferredLanguage}`}
              title={msg.translatedContent ? "Show original" : `Translate to ${preferredLanguage}`}
            >
              <FiGlobe aria-hidden="true" />
              <span>{msg.isTranslating ? "…" : msg.translatedContent ? "Original" : "Translate"}</span>
            </button>
          )}

          {msg.type === "ai" && Array.isArray(msg.quickReplies) && msg.quickReplies.length > 0 && (
            <div className="message-quick-replies">
              {msg.quickReplies.map((reply, replyIndex) => {
                const label = String(reply?.label ?? reply?.value ?? reply ?? "").trim();
                const value = String(reply?.value ?? reply?.label ?? reply ?? "").trim();
                if (!label || !value) return null;
                return (
                  <button
                    key={`${index}-${replyIndex}-${value}`}
                    type="button"
                    className="secondary-button message-quick-reply"
                    onClick={() => onQuickReply(value)}
                    disabled={isStreaming}
                  >
                    {label}
                  </button>
                );
              })}
            </div>
          )}

          {(msg.level || msg.messageId) && (
            <div className="message-meta">
              {msg.level && <span>{msg.level}</span>}
              {msg.messageId && <span>{msg.messageId}</span>}
            </div>
          )}
        </div>
      </div>
    );
  };

  const renderEmptyState = () => {
    if (messages.length > 0) return null;

    return (
      <div className="empty-state empty-state--chat">
        <div className="empty-state__icon">💬</div>
        <h3 className="empty-state__title">Start a conversation</h3>
        <p className="empty-state__description">
          Ask questions, request summaries, or work through problems with your AI learning assistant.
        </p>
      </div>
    );
  };

  return (
    <div ref={messagesContainerRef} className="workspace-messages chat-messages">
      {wsError && (
        <div className="ws-error-banner">
          <span>{wsError}</span>
          <button
            type="button"
            className="icon-button icon-button--ghost"
            onClick={onDismissError}
            aria-label="Dismiss"
          >
            ×
          </button>
        </div>
      )}

      {renderEmptyState()}

      {messages.map((msg, index) => renderMessage(msg, index))}

      {isStreaming && (
        <div className="message-row ai">
          <div className="message-bubble">
            {currentStream ? (
              <>
                <div style={{ display: "inline" }}>
                  <MessageContent content={currentStream} />
                  <span className="cursor">▌</span>
                </div>
                {streamStatus && (
                  <div className="stream-status">
                    <span>{streamStatus}</span>
                  </div>
                )}
              </>
            ) : (
              <span className="thinking">
                {streamStatus || "Thinking"}
                <span className="dots"></span>
              </span>
            )}
          </div>
        </div>
      )}

      <div ref={messagesEndRef} />
    </div>
  );
};

export default MessageList;