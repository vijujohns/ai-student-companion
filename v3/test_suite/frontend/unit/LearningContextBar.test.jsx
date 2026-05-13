import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import LearningContextBar from "../../../frontend/src/components/LearningContextBar";

describe("LearningContextBar", () => {
  it("renders selected learning context and readiness state", () => {
    render(
      <LearningContextBar
        fileInputRef={{ current: null }}
        handleUploadFile={vi.fn()}
        isExplorerMode={false}
        selectedClass="Class 9"
        selectedSubject="Mathematics"
        selectedFolder="Algebra"
        selectedContentItem={{ title: "Quadratic Equations" }}
        isViewerVisible={false}
        setIsViewerVisible={vi.fn()}
        openContextModal={vi.fn()}
        contextProcessing={null}
        uploadNotice={null}
        supplementalContextStatus="Knowledge base loaded."
        uploadLimitState={{ blocked: false, used: 0, limit: 0 }}
        pendingUploadsInScope={0}
        hasRequiredStudyContext={true}
        hasViewerContent={true}
      />
    );

    expect(screen.getByText("Current Context")).toBeInTheDocument();
    expect(screen.getByText("Class 9")).toBeInTheDocument();
    expect(screen.getByText("Mathematics")).toBeInTheDocument();
    expect(screen.getByText("Algebra")).toBeInTheDocument();
    expect(screen.getByText("Quadratic Equations")).toBeInTheDocument();
    expect(screen.getByText("Index ready")).toBeInTheDocument();
  });
});
