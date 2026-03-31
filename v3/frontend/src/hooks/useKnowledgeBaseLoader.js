import { useCallback } from "react";
import {
  dedupeByContentId,
  flattenUploadedTree,
  mapKnowledgeBaseContents,
  mapScopedUploadedContents,
  normalizeStringList,
} from "../utils/contentCatalog";

export function useKnowledgeBaseLoader({
  apiFetch,
  parseApiError,
  setKbStatus,
  setClasses,
  setSubjects,
  setFolders,
  setContents,
  setUploadedFiles,
  setSelectedContent,
}) {
  const loadClasses = useCallback(async () => {
    setKbStatus((prev) => ({ ...prev, classesLoading: true, error: "" }));
    try {
      const res = await apiFetch("/classes");
      if (!res.ok) {
        const errorText = await parseApiError(res, `Failed to load classes (${res.status})`);
        setKbStatus((prev) => ({ ...prev, error: errorText }));
        return;
      }
      const data = await res.json();
      setClasses(normalizeStringList(Array.isArray(data) ? data : data?.classes));
    } catch (err) {
      console.error("❌ Failed to load classes:", err);
      setKbStatus((prev) => ({ ...prev, error: "Failed to load classes." }));
    } finally {
      setKbStatus((prev) => ({ ...prev, classesLoading: false }));
    }
  }, [apiFetch, parseApiError, setClasses, setKbStatus]);

  const loadSubjects = useCallback(
    async (cls) => {
      if (!cls) return;
      setKbStatus((prev) => ({ ...prev, subjectsLoading: true, error: "" }));
      try {
        const res = await apiFetch(`/subjects?class_name=${encodeURIComponent(cls)}`);
        if (!res.ok) {
          const errorText = await parseApiError(res, `Failed to load subjects (${res.status})`);
          setKbStatus((prev) => ({ ...prev, error: errorText }));
          return;
        }
        const data = await res.json();
        setSubjects(normalizeStringList(Array.isArray(data) ? data : data?.subjects));
      } catch (err) {
        console.error("❌ Failed to load subjects:", err);
        setKbStatus((prev) => ({ ...prev, error: "Failed to load subjects." }));
      } finally {
        setKbStatus((prev) => ({ ...prev, subjectsLoading: false }));
      }
    },
    [apiFetch, parseApiError, setKbStatus, setSubjects]
  );

  const loadFolders = useCallback(
    async (cls, subject) => {
      if (!cls || !subject) return;
      setKbStatus((prev) => ({ ...prev, foldersLoading: true, error: "" }));
      try {
        const res = await apiFetch(
          `/folders?class_name=${encodeURIComponent(cls)}&subject=${encodeURIComponent(subject)}`
        );
        if (!res.ok) {
          const errorText = await parseApiError(res, `Failed to load folders (${res.status})`);
          setKbStatus((prev) => ({ ...prev, error: errorText }));
          return;
        }
        const data = await res.json();
        setFolders(normalizeStringList(Array.isArray(data) ? data : data?.folders));
      } catch (err) {
        console.error("❌ Failed to load folders:", err);
        setKbStatus((prev) => ({ ...prev, error: "Failed to load folders." }));
      } finally {
        setKbStatus((prev) => ({ ...prev, foldersLoading: false }));
      }
    },
    [apiFetch, parseApiError, setFolders, setKbStatus]
  );

  const loadContents = useCallback(
    async (cls, subject, folder) => {
      setKbStatus((prev) => ({ ...prev, contentsLoading: true, error: "" }));
      try {
        const merged = [];

        if (cls && subject && folder) {
          const res = await apiFetch(
            `/contents?class_name=${encodeURIComponent(cls)}&subject=${encodeURIComponent(subject)}&folder=${encodeURIComponent(folder)}`
          );
          if (!res.ok) {
            const errorText = await parseApiError(res, `Failed to load files (${res.status})`);
            setKbStatus((prev) => ({ ...prev, error: errorText }));
            return;
          }
          const data = await res.json();
          const contentRows = Array.isArray(data) ? data : Array.isArray(data?.contents) ? data.contents : [];
          if (Array.isArray(contentRows)) {
            merged.push(...mapKnowledgeBaseContents(contentRows));
          }
        }

        const treeRes = await apiFetch("/files/tree");
        if (treeRes.ok) {
          const treeData = await treeRes.json();
          const uploaded = flattenUploadedTree(treeData?.items || []);
          setUploadedFiles(uploaded);

          merged.push(...mapScopedUploadedContents(uploaded, cls, subject, folder));
        }

        const deduped = dedupeByContentId(merged);
        setContents(deduped);
        setSelectedContent((prev) => (prev && deduped.some((item) => item.content_id === prev) ? prev : null));
      } catch (err) {
        console.error("❌ Failed to load contents:", err);
        setKbStatus((prev) => ({ ...prev, error: "Failed to load files." }));
      } finally {
        setKbStatus((prev) => ({ ...prev, contentsLoading: false }));
      }
    },
    [apiFetch, parseApiError, setContents, setKbStatus, setSelectedContent, setUploadedFiles]
  );

  return {
    loadClasses,
    loadSubjects,
    loadFolders,
    loadContents,
  };
}