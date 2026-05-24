import { useCallback, useEffect, useRef, useState } from "react";

export function useViewerLayout({ hasViewerContent }) {
  const [isViewerVisible, setIsViewerVisible] = useState(localStorage.getItem("viewerVisible") !== "false");
  const [viewerWidth, setViewerWidth] = useState(
    Number(localStorage.getItem("viewerWidth")) || Number(localStorage.getItem("pdfWidth")) || 35
  );
  const [isViewerMaximized, setIsViewerMaximized] = useState(localStorage.getItem("viewerMaximized") === "true");
  const [isDraggingViewer, setIsDraggingViewer] = useState(false);

  const workspaceBodyRef = useRef(null);
  const previousViewerWidthRef = useRef(viewerWidth);
  const isDraggingViewerRef = useRef(false);

  const shouldShowViewer = hasViewerContent && isViewerVisible;
  const shouldShowSideViewer = shouldShowViewer && !isViewerMaximized;
  const effectiveViewerWidth = Math.min(82, Math.max(34, viewerWidth));

  useEffect(() => {
    localStorage.setItem("viewerVisible", String(isViewerVisible));
  }, [isViewerVisible]);

  useEffect(() => {
    localStorage.setItem("viewerWidth", String(viewerWidth));
  }, [viewerWidth]);

  useEffect(() => {
    localStorage.setItem("viewerMaximized", String(isViewerMaximized));
  }, [isViewerMaximized]);

  const toggleViewerMaximize = useCallback(() => {
    if (!hasViewerContent) return;
    if (!isViewerMaximized) {
      previousViewerWidthRef.current = viewerWidth;
      setIsViewerMaximized(true);
      return;
    }

    setIsViewerMaximized(false);
    setViewerWidth(previousViewerWidthRef.current || 35);
  }, [hasViewerContent, isViewerMaximized, viewerWidth]);

  const updateViewerWidthFromPointer = useCallback((clientX) => {
    const container = workspaceBodyRef.current;
    if (!container) return;

    const rect = container.getBoundingClientRect();
    if (!rect.width) return;

    const viewerPercent = ((rect.right - clientX) / rect.width) * 100;
    const clamped = Math.min(82, Math.max(34, viewerPercent));
    setViewerWidth(clamped);
  }, []);

  const stopViewerDrag = useCallback(() => {
    if (!isDraggingViewerRef.current) return;
    isDraggingViewerRef.current = false;
    setIsDraggingViewer(false);
  }, []);

  const onViewerDragMove = useCallback(
    (event) => {
      if (!isDraggingViewerRef.current || isViewerMaximized) return;
      updateViewerWidthFromPointer(event.clientX);
    },
    [isViewerMaximized, updateViewerWidthFromPointer]
  );

  const startViewerDrag = useCallback(
    (event) => {
      if (!shouldShowSideViewer || isViewerMaximized) return;
      isDraggingViewerRef.current = true;
      setIsDraggingViewer(true);
      updateViewerWidthFromPointer(event.clientX);
    },
    [isViewerMaximized, shouldShowSideViewer, updateViewerWidthFromPointer]
  );

  useEffect(() => {
    window.addEventListener("mousemove", onViewerDragMove);
    window.addEventListener("mouseup", stopViewerDrag);

    return () => {
      window.removeEventListener("mousemove", onViewerDragMove);
      window.removeEventListener("mouseup", stopViewerDrag);
    };
  }, [onViewerDragMove, stopViewerDrag]);

  useEffect(() => {
    if (!isViewerMaximized) return undefined;

    const closeOnEscape = (event) => {
      if (event.key === "Escape") {
        setIsViewerMaximized(false);
      }
    };

    document.body.classList.add("viewer-modal-open");
    window.addEventListener("keydown", closeOnEscape);

    return () => {
      document.body.classList.remove("viewer-modal-open");
      window.removeEventListener("keydown", closeOnEscape);
    };
  }, [isViewerMaximized]);

  return {
    workspaceBodyRef,
    isViewerVisible,
    setIsViewerVisible,
    viewerWidth,
    isViewerMaximized,
    setIsViewerMaximized,
    isDraggingViewer,
    shouldShowViewer,
    shouldShowSideViewer,
    effectiveViewerWidth,
    toggleViewerMaximize,
    startViewerDrag,
  };
}