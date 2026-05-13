import React from "react";
import {
  DEFAULT_ASSIGNMENT_TEMPLATES,
  formatTemplateTypeLabel,
  formatTemplateCategoryLabel,
} from "../utils/roleHubUtils";

export function AssignmentTemplateLibrary({
  savedAssignmentTemplates = [],
  savedTemplateCategoryFilter = "all",
  showFavoriteTemplatesOnly = false,
  templateImportText = "",
  templateImportStatus = "",
  editingTemplateId = null,
  editingTemplateLabel = "",
  editingTemplateType = "lesson",
  editingTemplateCategory = "general",
  editingTemplateSubject = "",
  editingTemplateNote = "",
  previewTemplateId = null,
  filteredSavedTemplates = [],
  savedTemplateSummary = {},
  onCategoryFilterChange = null,
  onFavoritesToggle = null,
  onApplyTemplate = null,
  onExport = null,
  onImportTextChange = null,
  onImport = null,
  onStartEdit = null,
  onCancelEdit = null,
  onSaveEdit = null,
  onToggleFavorite = null,
  onDelete = null,
  onPreview = null,
  onDuplicate = null,
  onEditLabelChange = null,
  onEditTypeChange = null,
  onEditCategoryChange = null,
  onEditSubjectChange = null,
  onEditNoteChange = null,
}) {
  return (
    <div className="role-hub-panel__note-box" style={{ marginBottom: 12 }}>
      <strong>Assignment Templates</strong>
      <p className="sidebar-note">Start with a reusable class routine and send it to the selected learners.</p>
      <div className="role-hub-panel__note-actions">
        {DEFAULT_ASSIGNMENT_TEMPLATES.map((template) => (
          <button
            key={template.id}
            type="button"
            className="secondary-button"
            onClick={() => onApplyTemplate?.(template)}
          >
            {template.label}
          </button>
        ))}
      </div>

      <div style={{ marginTop: 12 }}>
        <label style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <span>Import template JSON</span>
          <textarea
            aria-label="Import template JSON"
            rows={3}
            value={templateImportText}
            onChange={(event) => onImportTextChange?.(event.target.value)}
            placeholder="Paste shared template JSON here"
          />
        </label>
        <div className="role-hub-panel__note-actions" style={{ marginTop: 8 }}>
          <button
            type="button"
            className="secondary-button"
            onClick={onImport}
            disabled={!templateImportText.trim()}
          >
            Import Shared Templates
          </button>
          {templateImportStatus && <span>{templateImportStatus}</span>}
        </div>
      </div>

      {savedAssignmentTemplates.length > 0 && (
        <div style={{ marginTop: 12 }}>
          <strong>Saved Templates</strong>
          <p className="sidebar-note">Reuse your own saved class routines any time.</p>
          <div className="role-hub-panel__note-actions">
            <span>{savedTemplateSummary.totalCount} saved templates</span>
            <span>{savedTemplateSummary.favoriteCount} favorites</span>
            {savedTemplateSummary.totalCount > 1 || savedTemplateSummary.favoriteCount > 0 ? (
              <>
                <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span>Saved template category</span>
                  <select
                    aria-label="Saved template category"
                    value={savedTemplateCategoryFilter}
                    onChange={(event) => onCategoryFilterChange?.(event.target.value)}
                  >
                    <option value="all">All categories</option>
                    <option value="general">General</option>
                    <option value="stem">STEM</option>
                    <option value="humanities">Humanities</option>
                    <option value="languages">Languages</option>
                    <option value="exam">Exam Prep</option>
                  </select>
                </label>
                <button
                  type="button"
                  className="secondary-button"
                  onClick={onFavoritesToggle}
                >
                  {showFavoriteTemplatesOnly ? "Show All Templates" : "Show Favorites Only"}
                </button>
              </>
            ) : null}
          </div>
          <button
            type="button"
            className="secondary-button"
            onClick={onExport}
            disabled={savedAssignmentTemplates.length === 0}
            style={{ marginTop: 8 }}
          >
            Export Template Library
          </button>

          {filteredSavedTemplates.map((template) => {
            const isEditingTemplate = editingTemplateId === template.id;
            const isPreviewingTemplate = previewTemplateId === template.id;
            return (
              <div key={template.id} className="role-hub-panel__note-box" style={{ marginTop: 8 }}>
                {isEditingTemplate ? (
                  <>
                    <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                      <span>Template name</span>
                      <input
                        aria-label="Template name"
                        type="text"
                        value={editingTemplateLabel}
                        onChange={(event) => onEditLabelChange?.(event.target.value)}
                      />
                    </label>
                    <div className="role-hub-panel__note-actions" style={{ marginTop: 8 }}>
                      <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                        <span>Template type</span>
                        <select
                          aria-label="Template type"
                          value={editingTemplateType}
                          onChange={(event) => onEditTypeChange?.(event.target.value)}
                        >
                          <option value="lesson">Lesson</option>
                          <option value="quiz">Quiz</option>
                          <option value="assessment">Assessment</option>
                          <option value="chat">Chat</option>
                          <option value="flashcards">Flashcards</option>
                        </select>
                      </label>
                      <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                        <span>Edit template category</span>
                        <select
                          aria-label="Edit template category"
                          value={editingTemplateCategory}
                          onChange={(event) => onEditCategoryChange?.(event.target.value)}
                        >
                          <option value="general">General</option>
                          <option value="stem">STEM</option>
                          <option value="humanities">Humanities</option>
                          <option value="languages">Languages</option>
                          <option value="exam">Exam Prep</option>
                        </select>
                      </label>
                    </div>
                    <label style={{ display: "flex", flexDirection: "column", gap: 4, marginTop: 8 }}>
                      <span>Subject</span>
                      <input
                        aria-label="Template subject"
                        type="text"
                        value={editingTemplateSubject}
                        onChange={(event) => onEditSubjectChange?.(event.target.value)}
                      />
                    </label>
                    <label style={{ display: "flex", flexDirection: "column", gap: 4, marginTop: 8 }}>
                      <span>Template note</span>
                      <textarea
                        aria-label="Template note"
                        rows={3}
                        value={editingTemplateNote}
                        onChange={(event) => onEditNoteChange?.(event.target.value)}
                      />
                    </label>
                    <div className="role-hub-panel__note-actions" style={{ marginTop: 8 }}>
                      <button
                        type="button"
                        className="primary-button"
                        onClick={() => onSaveEdit?.(template.id)}
                        disabled={!editingTemplateLabel.trim()}
                      >
                        Save Changes
                      </button>
                      <button
                        type="button"
                        className="secondary-button"
                        onClick={onCancelEdit}
                      >
                        Cancel Edit
                      </button>
                    </div>
                  </>
                ) : (
                  <>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "start" }}>
                      <div>
                        <strong>{template.label}</strong>
                        <p className="sidebar-note">
                          {formatTemplateTypeLabel(template.assignmentType)} · {formatTemplateCategoryLabel(template.category)}
                        </p>
                        {template.subject && <p className="sidebar-note">Subject: {template.subject}</p>}
                      </div>
                      {template.isFavorite && <span className="progress-pill progress-pill--neutral">★ Favorite</span>}
                    </div>
                    {isPreviewingTemplate && <p style={{ marginTop: 8 }}>{template.note}</p>}
                  </>
                )}

                {!isEditingTemplate && (
                  <div className="role-hub-panel__note-actions" style={{ marginTop: 8 }}>
                    <button
                      type="button"
                      className="secondary-button"
                      onClick={() => onApplyTemplate?.(template)}
                    >
                      Use Template
                    </button>
                    <button
                      type="button"
                      className="secondary-button"
                      onClick={() => onPreview?.(template.id)}
                    >
                      {isPreviewingTemplate ? "Hide Details" : "Show Details"}
                    </button>
                    <button
                      type="button"
                      className="secondary-button"
                      onClick={() => onToggleFavorite?.(template.id)}
                    >
                      {template.isFavorite ? "Remove Favorite" : "Add Favorite"}
                    </button>
                    <button
                      type="button"
                      className="secondary-button"
                      onClick={() => onStartEdit?.(template)}
                    >
                      Edit
                    </button>
                    <button
                      type="button"
                      className="secondary-button"
                      onClick={() => onDuplicate?.(template)}
                    >
                      Duplicate
                    </button>
                    <button
                      type="button"
                      className="secondary-button"
                      onClick={() => onDelete?.(template.id)}
                    >
                      Delete
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
