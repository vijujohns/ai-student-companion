export function countPendingUploadsInScope(uploadedFiles, selectedClass, selectedSubject, selectedFolder) {
  return uploadedFiles.filter((item) => {
    if (selectedClass && item.class_name !== selectedClass) return false;
    if (selectedSubject && item.subject_name !== selectedSubject) return false;
    if (selectedFolder && item.folder_name !== selectedFolder) return false;
    return !item.indexed;
  }).length;
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