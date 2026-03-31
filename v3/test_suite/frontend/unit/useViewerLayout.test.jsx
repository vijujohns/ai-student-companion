import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { useViewerLayout } from "../../../frontend/src/hooks/useViewerLayout";

describe("useViewerLayout", () => {
  beforeEach(() => {
    localStorage.clear();
    document.body.classList.remove("viewer-modal-open");
  });

  it("does not show viewer when content is unavailable", () => {
    localStorage.setItem("viewerVisible", "true");

    const { result } = renderHook(() => useViewerLayout({ hasViewerContent: false }));

    expect(result.current.isViewerVisible).toBe(true);
    expect(result.current.shouldShowViewer).toBe(false);
    expect(result.current.shouldShowSideViewer).toBe(false);
  });

  it("toggles maximize state only when content exists", () => {
    const { result: noContent } = renderHook(() => useViewerLayout({ hasViewerContent: false }));

    act(() => {
      noContent.current.toggleViewerMaximize();
    });

    expect(noContent.current.isViewerMaximized).toBe(false);

    const { result } = renderHook(() => useViewerLayout({ hasViewerContent: true }));

    act(() => {
      result.current.toggleViewerMaximize();
    });

    expect(result.current.isViewerMaximized).toBe(true);

    act(() => {
      result.current.toggleViewerMaximize();
    });

    expect(result.current.isViewerMaximized).toBe(false);
  });

  it("initializes width from localStorage", () => {
    localStorage.setItem("viewerWidth", "61");

    const { result } = renderHook(() => useViewerLayout({ hasViewerContent: true }));

    expect(result.current.viewerWidth).toBe(61);
    expect(result.current.effectiveViewerWidth).toBe(61);
  });
});
