import { FiBook, FiFileText, FiFolder, FiLayers } from "react-icons/fi";

export function countPendingUploadsInScope(uploadedFiles, selectedClass, selectedSubject, selectedFolder) {
  return uploadedFiles.filter((item) => {
    if (selectedClass && item.class_name !== selectedClass) return false;
    if (selectedSubject && item.subject_name !== selectedSubject) return false;
    if (selectedFolder && item.folder_name !== selectedFolder) return false;
    return !item.indexed;
  }).length;
}

export function getLearningContextPillItems({ selectedClass, selectedSubject, selectedFolder, selectedContentItem }) {
  const items = [];
  if (selectedClass) {
    items.push({ key: "class", label: "Class", value: selectedClass, icon: FiLayers });
  }
  if (selectedSubject) {
    items.push({ key: "subject", label: "Subject", value: selectedSubject, icon: FiBook });
  }
  if (selectedFolder) {
    items.push({ key: "folder", label: "Folder", value: selectedFolder, icon: FiFolder });
  }
  if (selectedContentItem?.title) {
    items.push({ key: "file", label: "File", value: selectedContentItem.title, icon: FiFileText });
  }
  return items;
}

export function getLearningContextReadinessMeta({ pendingUploadsInScope, hasRequiredStudyContext, isExplorerMode }) {
  if (isExplorerMode) {
    return { label: "Explorer mode is open", tone: "info" };
  }
  if (!hasRequiredStudyContext) {
    return { label: "Study context incomplete", tone: "info" };
  }
  if (pendingUploadsInScope > 0) {
    return { label: `${pendingUploadsInScope} file(s) pending indexing`, tone: "warning" };
  }
  return { label: "Index ready", tone: "success" };
}

export function buildKnowledgeBaseStatusMessage({
  kbStatus,
  classes,
  subjects,
  folders,
  contents,
  selectedClass,
  selectedSubject,
  selectedFolder,
  pendingUploadsInScope,
}) {
  if (kbStatus.error) return kbStatus.error;
  if (kbStatus.classesLoading) return "Loading classes...";
  if (kbStatus.subjectsLoading) return "Loading subjects...";
  if (kbStatus.foldersLoading) return "Loading folders...";
  if (kbStatus.contentsLoading) return "Loading files...";
  if (!selectedClass && classes.length === 0) return "No classes available.";
  if (selectedClass && subjects.length === 0) return "No subjects found for selected class.";
  if (selectedSubject && folders.length === 0) return "No folders found for selected subject.";
  if (selectedFolder && contents.length === 0) return "No files found for selected folder.";
  if (pendingUploadsInScope > 0) {
    return `${pendingUploadsInScope} uploaded file(s) are still being prepared and cannot be selected yet.`;
  }
  return "Knowledge base loaded.";
}