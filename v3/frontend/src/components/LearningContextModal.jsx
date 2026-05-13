import React from "react";
import { FiBook, FiFileText, FiFolder, FiLayers, FiX, FiCheck } from "react-icons/fi";
import UploadIndexingPanel from "./UploadIndexingPanel";

export default function LearningContextModal({
  selectedClass,
  selectedSubject,
  selectedFolder,
  selectedContent,
  classes,
  visibleClasses,
  subjects,
  folders,
  contents,
  onClassChange,
  onSubjectChange,
  onFolderChange,
  onContentChange,
  loadClasses,
  loadSubjects,
  saveLearningContext,
  contextPrompt,
  isUploading,
  uploadLimitState,
  fileInputRef,
  refreshIndexedFiles,
  kbStatus,
  handleExplorerModeSelection,
  contextDropActive,
  handleContextDrop,
  setContextDropActive,
  uploadedFiles,
  onRenameUploadedFile,
  onDeleteUploadedFile,
  onClose,
  planSummary,
  classAccessSummary,
}) {
  return (
    <div
      className="context-modal"
      role="dialog"
      aria-modal="true"
      aria-label="Choose learning context"
      onClick={onClose}
    >
      <div className="context-modal__content" onClick={(event) => event.stopPropagation()}>
        <div className="subscription-modal__header">
          <div>
            <div className="workspace-panel__eyebrow">
              <FiBook />
              <span>Learning setup</span>
            </div>
            <h3>Choose your learning context</h3>
            <p>{contextPrompt || "Select your class and subject, or continue in Explorer Mode for general learning chat."}</p>
          </div>
          <button
            type="button"
            className="icon-button icon-button--ghost"
            onClick={onClose}
            aria-label="Close learning setup"
          >
            <FiX />
          </button>
        </div>

        <div className="context-modal__grid">
          <section className="subscription-card context-modal__section">
            <h4>1. Pick your study area</h4>
            <div className="context-modal__field-list">
              <div className="workspace-select-wrap">
                <FiLayers />
                <select
                  aria-label="Select class"
                  value={selectedClass || ""}
                  onChange={onClassChange}
                  onFocus={() => {
                    if (classes.length === 0) loadClasses();
                  }}
                >
                  <option value="">Class</option>
                  {visibleClasses.map((item) => (
                    <option key={item} value={item}>
                      {item}
                    </option>
                  ))}
                </select>
              </div>

              <div className="workspace-select-wrap">
                <FiBook />
                <select
                  aria-label="Select subject"
                  value={selectedSubject || ""}
                  onChange={onSubjectChange}
                  disabled={!selectedClass}
                >
                  <option value="">Subject</option>
                  {subjects.map((item) => (
                    <option key={item} value={item}>
                      {item}
                    </option>
                  ))}
                </select>
              </div>

              <div className="workspace-select-wrap">
                <FiFolder />
                <select
                  aria-label="Select folder"
                  value={selectedFolder || ""}
                  onChange={onFolderChange}
                  disabled={!selectedSubject}
                >
                  <option value="">Folder</option>
                  {folders.map((item) => (
                    <option key={item} value={item}>
                      {item}
                    </option>
                  ))}
                </select>
              </div>

              <div className="workspace-select-wrap">
                <FiFileText />
                <select
                  aria-label="Select file"
                  value={selectedContent || ""}
                  onChange={onContentChange}
                  disabled={contents.length === 0}
                >
                  <option value="">File</option>
                  {contents.map((item) => (
                    <option key={item.content_id} value={item.content_id} disabled={item.selectable === false}>
                      {item.selectable === false
                        ? `${item.title} [${item.status_label || "Processing"}]`
                        : item.title}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <p className="sidebar-note">Class and subject are required for guided study tools. Folder and file are optional.</p>
            {planSummary && <p className="sidebar-note">{classAccessSummary}</p>}
          </section>

          <section className="subscription-card context-modal__section">
            <h4>2. Add your own notes</h4>
            <UploadIndexingPanel
              selectedClass={selectedClass}
              selectedSubject={selectedSubject}
              selectedFolder={selectedFolder}
              isUploading={isUploading}
              uploadLimitState={uploadLimitState}
              fileInputRef={fileInputRef}
              refreshIndexedFiles={refreshIndexedFiles}
              kbStatus={kbStatus}
              handleExplorerModeSelection={handleExplorerModeSelection}
              contextDropActive={contextDropActive}
              handleContextDrop={handleContextDrop}
              setContextDropActive={setContextDropActive}
              uploadedFiles={uploadedFiles}
              onRenameUploadedFile={onRenameUploadedFile}
              onDeleteUploadedFile={onDeleteUploadedFile}
            />

            <div className="context-modal__actions">
              <button
                type="button"
                className="primary-button"
                onClick={saveLearningContext}
                disabled={!selectedClass || !selectedSubject}
              >
                <FiCheck />
                <span>Continue with this context</span>
              </button>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
