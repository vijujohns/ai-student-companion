import { describe, expect, it } from "vitest";
import { buildKnowledgeBaseStatusMessage, countPendingUploadsInScope } from "../../../frontend/src/utils/kbSelectors";

describe("kbSelectors", () => {
  it("counts pending uploads within selected scope", () => {
    const uploadedFiles = [
      { class_name: "Class 8", subject_name: "English", folder_name: "Unit 1", indexed: false },
      { class_name: "Class 8", subject_name: "English", folder_name: "Unit 2", indexed: false },
      { class_name: "Class 8", subject_name: "English", folder_name: "Unit 1", indexed: true },
    ];

    const pending = countPendingUploadsInScope(uploadedFiles, "Class 8", "English", "Unit 1");
    expect(pending).toBe(1);
  });

  it("prefers explicit KB error message", () => {
    const message = buildKnowledgeBaseStatusMessage({
      kbStatus: {
        error: "Failed to load classes.",
        classesLoading: false,
        subjectsLoading: false,
        foldersLoading: false,
        contentsLoading: false,
      },
      classes: [],
      subjects: [],
      folders: [],
      contents: [],
      selectedClass: null,
      selectedSubject: null,
      selectedFolder: null,
      pendingUploadsInScope: 0,
    });

    expect(message).toBe("Failed to load classes.");
  });

  it("shows indexing hint when uploads are pending", () => {
    const message = buildKnowledgeBaseStatusMessage({
      kbStatus: {
        error: "",
        classesLoading: false,
        subjectsLoading: false,
        foldersLoading: false,
        contentsLoading: false,
      },
      classes: ["Class 8"],
      subjects: ["English"],
      folders: ["Unit 1"],
      contents: [{ content_id: "kb:abc" }],
      selectedClass: "Class 8",
      selectedSubject: "English",
      selectedFolder: "Unit 1",
      pendingUploadsInScope: 2,
    });

    expect(message).toContain("2 uploaded file(s) are still being prepared");
  });
});
