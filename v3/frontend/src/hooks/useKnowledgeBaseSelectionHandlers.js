import { useCallback } from "react";

export function useKnowledgeBaseSelectionHandlers({
  selectedClass,
  selectedSubject,
  setSelectedClass,
  setSelectedSubject,
  setSelectedFolder,
  setSelectedContent,
  setSubjects,
  setFolders,
  setContents,
  setUploadedFiles,
  setUploadNotice,
  loadSubjects,
  loadFolders,
  loadContents,
}) {
  const handleClassChange = useCallback(
    (event) => {
      const value = event.target.value || null;
      setSelectedClass(value);
      setSelectedSubject(null);
      setSelectedFolder(null);
      setSelectedContent(null);
      setSubjects([]);
      setFolders([]);
      setContents([]);
      setUploadedFiles([]);
      if (value) {
        loadSubjects(value);
      }
    },
    [
      loadSubjects,
      setContents,
      setFolders,
      setSelectedClass,
      setSelectedContent,
      setSelectedFolder,
      setSelectedSubject,
      setSubjects,
      setUploadedFiles,
    ]
  );

  const handleSubjectChange = useCallback(
    (event) => {
      const value = event.target.value || null;
      setSelectedSubject(value);
      setSelectedFolder(null);
      setSelectedContent(null);
      setFolders([]);
      setContents([]);
      if (selectedClass && value) {
        loadFolders(selectedClass, value);
      }
    },
    [
      loadFolders,
      selectedClass,
      setContents,
      setFolders,
      setSelectedContent,
      setSelectedFolder,
      setSelectedSubject,
    ]
  );

  const handleFolderChange = useCallback(
    (event) => {
      const value = event.target.value || null;
      setSelectedFolder(value);
      setSelectedContent(null);
      setContents([]);
      setUploadNotice(null);
      if (selectedClass && selectedSubject && value) {
        loadContents(selectedClass, selectedSubject, value);
      }
    },
    [
      loadContents,
      selectedClass,
      selectedSubject,
      setContents,
      setSelectedContent,
      setSelectedFolder,
      setUploadNotice,
    ]
  );

  return {
    handleClassChange,
    handleSubjectChange,
    handleFolderChange,
  };
}