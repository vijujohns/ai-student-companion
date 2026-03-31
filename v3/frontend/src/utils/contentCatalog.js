export function normalizeStringList(payload) {
  if (Array.isArray(payload)) return payload.filter((item) => typeof item === "string");
  if (payload && Array.isArray(payload.items)) {
    return payload.items.filter((item) => typeof item === "string");
  }
  if (payload && Array.isArray(payload.data)) {
    return payload.data.filter((item) => typeof item === "string");
  }
  return [];
}

export function flattenUploadedTree(items) {
  const flattened = [];
  if (!Array.isArray(items)) return flattened;

  items.forEach((classNode) => {
    const className = classNode?.class_name;
    const subjectsList = Array.isArray(classNode?.subjects) ? classNode.subjects : [];

    subjectsList.forEach((subjectNode) => {
      const subjectName = subjectNode?.subject;
      const foldersList = Array.isArray(subjectNode?.folders) ? subjectNode.folders : [];

      foldersList.forEach((folderNode) => {
        const folderName = folderNode?.folder;
        const filesList = Array.isArray(folderNode?.files) ? folderNode.files : [];

        filesList.forEach((fileNode) => {
          const contentId = fileNode?.content_id || fileNode?.path;
          if (!contentId) return;
          flattened.push({
            file_id: fileNode.file_id,
            class_name: className,
            subject_name: subjectName,
            folder_name: folderName,
            title: fileNode.title || "Uploaded PDF",
            content_id: contentId,
            indexed: Boolean(fileNode.indexed),
            selectable: Boolean(fileNode.selectable),
            message_id: fileNode.message_id || "MSG-1302",
          });
        });
      });
    });
  });

  return flattened;
}

export function mapKnowledgeBaseContents(contentRows) {
  if (!Array.isArray(contentRows)) return [];
  return contentRows
    .map((item) => ({ ...item, content_id: item?.content_id || item?.path }))
    .filter((item) => item?.content_id)
    .map((item) => ({
      title: item.title || "Document",
      content_id: item.content_id,
      indexed: true,
      source: "knowledge_base",
    }));
}

export function mapScopedUploadedContents(uploaded, cls, subject, folder) {
  const scopedUploaded = uploaded.filter((item) => {
    if (cls && item.class_name !== cls) return false;
    if (subject && item.subject_name !== subject) return false;
    if (folder && item.folder_name !== folder) return false;
    return true;
  });

  return scopedUploaded.map((item) => ({
    title: `${item.title} (Uploaded)`,
    content_id: item.content_id,
    indexed: Boolean(item.indexed),
    selectable: Boolean(item.selectable),
    source: "uploaded",
    file_id: item.file_id,
    message_id: item.message_id,
    status_label: item.indexed ? "Indexed" : item.message_id === "MSG-1306" ? "Failed" : "Processing",
  }));
}

export function dedupeByContentId(items) {
  const deduped = [];
  const seen = new Set();

  items.forEach((item) => {
    if (!item?.content_id || seen.has(item.content_id)) return;
    seen.add(item.content_id);
    deduped.push(item);
  });

  return deduped;
}
