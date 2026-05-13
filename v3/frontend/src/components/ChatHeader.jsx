import React from 'react';
import { FaPlus, FaFileExport } from 'react-icons/fa';
import './ChatHeader.css';

const ChatHeader = ({
  sessionTitle = "AI Learning Assistant",
  sessionId,
  onNewChat,
  onExport,
  isOnline = true
}) => {
  return (
    <div className="chat-header">
      <div className="header-left">
        <h3 className="session-title">{sessionTitle}</h3>
        {sessionId && (
          <span className="session-id">Session #{sessionId}</span>
        )}
      </div>

      <div className="header-right">
        <div className={`status-indicator ${isOnline ? 'online' : 'offline'}`}>
          <span className="status-dot"></span>
          <span className="status-text">
            {isOnline ? 'Online' : 'Offline'}
          </span>
        </div>

        <div className="header-actions">
          <button
            type="button"
            className="header-button"
            onClick={onNewChat}
            title="Start new chat"
            aria-label="Start new chat"
          >
            <FaPlus />
          </button>

          <button
            type="button"
            className="header-button"
            onClick={onExport}
            title="Export conversation"
            aria-label="Export conversation"
          >
            <FaFileExport />
          </button>
        </div>
      </div>
    </div>
  );
};

export default ChatHeader;