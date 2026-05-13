import React from "react";
import { FiArrowDown, FiEdit, FiGlobe, FiPlus, FiRefreshCw, FiTrash2 } from "react-icons/fi";

export default function UploadIndexingPanel({
  selectedClass,
  selectedSubject,
  selectedFolder,
  isUploading,
  uploadLimitState,
  fileInputRef,
  refreshIndexedFiles,
  kbStatus,
  handleExplorerModeSelection,
  contextDropActive,
  handleContextDrop,
  setContextDropActive,
  uploadedFiles = [],
  onRenameUploadedFile,
  onDeleteUploadedFile,
}) {
  const uploadFolderLabel = selectedFolder || "Notes";
  const refreshDisabled = !selectedClass || !selectedSubject || kbStatus?.contentsLoading;
  const chooseDisabled = !selectedClass || !selectedSubject || isUploading || uploadLimitState?.blocked;
  const scopedUploadedFiles = uploadedFiles.filter((item) => {
    if (selectedClass && item.class_name !== selectedClass) return false;
    if (selectedSubject && item.subject_name !== selectedSubject) return false;
    if (selectedFolder && item.folder_name !== selectedFolder) return false;
    return true;
  });

  return (
    <section className="subscription-card context-modal__section">
      <h4>2. Add your own notes</h4>
      <div
        className={`context-dropzone ${contextDropActive ? "is-active" : ""}`}
        onDragOver={(event) => {
          event.preventDefault();
          setContextDropActive(true);
        }}
        onDragLeave={() => setContextDropActive(false)}
        onDrop={(event) => {
          event.preventDefault();
          setContextDropActive(false);
          handleContextDrop(event);
        }}
      >
        <FiArrowDown />
        <strong>Drag and drop a PDF here</strong>
        <span>
          We’ll save it to <strong>{uploadFolderLabel}</strong>, prepare it in the background, and let you keep studying.
        </span>
        <button
          type="button"
          className="secondary-button"
          onClick={() => fileInputRef.current?.click()}
          disabled={chooseDisabled}
        >
          <FiPlus />
          <span>{isUploading ? "Uploading..." : "Choose PDF"}</span>
        </button>
        {uploadLimitState?.blocked ? (
          <span className="sidebar-note">
            Upload limit reached ({uploadLimitState.used}/{uploadLimitState.limit}). Upgrade plan to continue.
          </span>
        ) : null}
      </div>

      <div className="context-modal__actions">
        <button
          type="button"
          className="secondary-button"
          onClick={refreshIndexedFiles}
          disabled={refreshDisabled}
        >
          <FiRefreshCw />
          <span>Refresh files</span>
        </button>
        <button type="button" className="secondary-button" onClick={handleExplorerModeSelection}>
          <FiGlobe />
          <span>Proceed in Explorer Mode</span>
        </button>
      </div>

      {scopedUploadedFiles.length > 0 ? (
        <div className="role-hub-panel__list" style={{ marginTop: 12 }}>
          {scopedUploadedFiles.map((file) => (
            <div key={file.content_id} className="role-hub-panel__student">
              <div>
                <strong>{file.title}</strong>
                <span>{file.indexed ? "Indexed" : "Processing"} · {file.folder_name || uploadFolderLabel}</span>
              </div>
              <div className="session-actions">
                <button
                  type="button"
                  className="icon-button icon-button--ghost"
                  onClick={() => onRenameUploadedFile?.(file)}
                  aria-label={`Rename ${file.title}`}
                >
                  <FiEdit />
                </button>
                <button
                  type="button"
                  className="icon-button icon-button--ghost"
                  onClick={() => onDeleteUploadedFile?.(file)}
                  aria-label={`Delete ${file.title}`}
                >
                  <FiTrash2 />
                </button>
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </section>
  );
}
