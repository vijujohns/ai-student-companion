import { useEffect } from "react";

/**
 * Keeps the chat composer's CSS custom properties (position + height) in sync
 * with the live layout of the chat panel and composer DOM nodes.
 *
 * Properties written:
 *   --chat-composer-left   (on composerRef)
 *   --chat-composer-width  (on composerRef)
 *   --chat-composer-height (on panelRef)
 *
 * @param {Object} opts
 * @param {React.RefObject} opts.panelRef       - ref attached to the chat panel container
 * @param {React.RefObject} opts.composerRef    - ref attached to the input composer element
 * @param {string}          opts.activeTab      - current active tab; effect is a no-op unless "chat"
 * @param {boolean}         opts.drawerOpen     - triggers re-layout when nav drawer opens/closes
 * @param {boolean}         opts.shouldShowSideViewer - triggers re-layout when viewer is toggled
 * @param {number}          opts.effectiveViewerWidth  - triggers re-layout when viewer is resized
 */
export function useChatComposerLayout({
  panelRef,
  composerRef,
  activeTab,
  drawerOpen,
  shouldShowSideViewer,
  effectiveViewerWidth,
}) {
  useEffect(() => {
    if (activeTab !== "chat") return undefined;

    const panel = panelRef.current;
    const composer = composerRef.current;
    if (!panel || !composer) return undefined;

    const horizontalInset = 16;

    const updateComposerBounds = () => {
      const rect = panel.getBoundingClientRect();
      const width = Math.max(rect.width - horizontalInset * 2, 260);
      composer.style.setProperty("--chat-composer-left", `${Math.round(rect.left + horizontalInset)}px`);
      composer.style.setProperty("--chat-composer-width", `${Math.round(width)}px`);
    };

    const updateComposerHeight = () => {
      const height = Math.ceil(composer.getBoundingClientRect().height);
      panel.style.setProperty("--chat-composer-height", `${Math.max(height, 88)}px`);
    };

    updateComposerBounds();
    updateComposerHeight();

    let frame = null;
    const scheduleUpdate = () => {
      if (frame !== null) return;
      frame = window.requestAnimationFrame(() => {
        frame = null;
        updateComposerBounds();
        updateComposerHeight();
      });
    };

    let resizeObserver;
    if (typeof ResizeObserver !== "undefined") {
      resizeObserver = new ResizeObserver(scheduleUpdate);
      resizeObserver.observe(panel);
      resizeObserver.observe(composer);
    }

    window.addEventListener("resize", scheduleUpdate);

    return () => {
      if (frame !== null) {
        window.cancelAnimationFrame(frame);
      }
      window.removeEventListener("resize", scheduleUpdate);
      if (resizeObserver) {
        resizeObserver.disconnect();
      }
      panel.style.removeProperty("--chat-composer-height");
      composer.style.removeProperty("--chat-composer-left");
      composer.style.removeProperty("--chat-composer-width");
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, drawerOpen, shouldShowSideViewer, effectiveViewerWidth]);
}
