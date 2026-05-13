import React from "react";
import {
  FiBook,
  FiBookOpen,
  FiCheck,
  FiEdit,
  FiEye,
  FiEyeOff,
  FiFileText,
  FiFolder,
  FiGlobe,
  FiLayers,
  FiRefreshCw,
} from "react-icons/fi";
import {
  getLearningContextPillItems,
  getLearningContextReadinessMeta,
} from "../utils/kbSelectors";

export default function LearningContextBar({
  fileInputRef,
  handleUploadFile,
  isExplorerMode,
  selectedClass,
  selectedSubject,
  selectedFolder,
  selectedContentItem,
  isViewerVisible,
  setIsViewerVisible,
  openContextModal,
  contextProcessing,
  uploadNotice,
  supplementalContextStatus,
  uploadLimitState,
  pendingUploadsInScope,
  hasRequiredStudyContext,
  hasViewerContent,
}) {
  const contextPillItems = getLearningContextPillItems({
    selectedClass,
    selectedSubject,
    selectedFolder,
    selectedContentItem,
  });

  const readiness = getLearningContextReadinessMeta({
    pendingUploadsInScope,
    hasRequiredStudyContext,
    isExplorerMode,
  });

  return (
    <div className="workspace-context-bar">
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,application/pdf"
        onChange={handleUploadFile}
        style={{ display: "none" }}
      />

      <div className="workspace-context-status" role="status" aria-live="polite">
        <div className="workspace-context-status-row">
          <div className="workspace-context-summary" aria-label="Selected learning context">
            {isExplorerMode ? (
              <span className="status-pill status-pill--accent workspace-context-pill">
                <FiGlobe />
                <span className="workspace-context-pill__text">General learning only</span>
              </span>
            ) : (
              <>
                {contextPillItems.length > 0 && (
                  <span className="workspace-context-summary__label">Current Context</span>
                )}
                {contextPillItems.map(({ key, icon: Icon, label, value }) => (
                  <span
                    key={key}
                    className="status-pill status-pill--accent workspace-context-pill"
                    title={`${label}: ${value}`}>
                    <Icon />
                    <span className="workspace-context-pill__text">{value}</span>
                  </span>
                ))}
              </>
            )}

            {hasViewerContent && (
              <button
                type="button"
                className="status-pill status-pill--button workspace-context-pill"
                onClick={() => setIsViewerVisible((prev) => !prev)}
                disabled={!selectedContentItem}
                title={isViewerVisible ? "Hide document" : "Show document"}
                aria-label={isViewerVisible ? "Hide document" : "Show document"}
              >
                {isViewerVisible ? <FiEyeOff /> : <FiEye />}
                <span>{isViewerVisible ? "Hide Document" : "Show Document"}</span>
              </button>
            )}

            <span className="status-pill status-pill--accent workspace-context-pill" title={readiness.label}>
              {pendingUploadsInScope > 0 ? <FiRefreshCw /> : <FiCheck />}
              <span className="workspace-context-pill__text">{readiness.label}</span>
            </span>
          </div>

          <div className="workspace-context-actions workspace-context-actions--selectors-row">
            <button
              type="button"
              className="secondary-button"
              onClick={() => openContextModal("Choose your class and subject to personalize the workspace.")}
            >
              <FiEdit />
              <span>Edit Context</span>
            </button>
          </div>
        </div>

        {contextProcessing ? (
          <div className="workspace-context-status-text">
            <div className={`context-processing context-processing--${contextProcessing.tone || "info"}`}>
              <strong>{contextProcessing.title}</strong>
              <span>{contextProcessing.detail}</span>
              <div className="context-processing__bar" aria-hidden="true">
                <span style={{ width: `${Math.max(0, Math.min(100, Number(contextProcessing.progress || 0)))}%` }} />
              </div>
            </div>
          </div>
        ) : uploadNotice ? (
          <div className="workspace-context-status-text">
            <span className={`status-inline status-inline--${String(uploadNotice.level || "INFO").toLowerCase()}`}>
              <strong>{uploadNotice.level || "INFO"}</strong>
              <span>{uploadNotice.messageId || "MSG-1000"}</span>
              <span>{uploadNotice.text}</span>
            </span>
          </div>
        ) : supplementalContextStatus ? (
          <div className="workspace-context-status-text">
            <span>{supplementalContextStatus}</span>
          </div>
        ) : null}

        {uploadLimitState.blocked && (
          <span className="sidebar-note">
            Upload limit reached ({uploadLimitState.used}/{uploadLimitState.limit}). Upgrade plan to continue.
          </span>
        )}
        {!isExplorerMode && !hasRequiredStudyContext && (
          <span className="sidebar-note">Please select your class and subject to continue</span>
        )}
      </div>
    </div>
  );
}
