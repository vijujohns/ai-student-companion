import { renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useChatComposerLayout } from "../../../frontend/src/hooks/useChatComposerLayout";

function makeFakeElement(rect = { left: 0, width: 400, height: 60 }) {
  const styles = {};
  return {
    getBoundingClientRect: () => rect,
    style: {
      setProperty: (k, v) => { styles[k] = v; },
      removeProperty: (k) => { delete styles[k]; },
      _data: styles,
    },
  };
}

describe("useChatComposerLayout", () => {
  let MockResizeObserver;

  beforeEach(() => {
    MockResizeObserver = vi.fn(function (cb) {
      this.cb = cb;
      this.observe = vi.fn();
      this.disconnect = vi.fn();
    });
    vi.stubGlobal("ResizeObserver", MockResizeObserver);
    // Synchronous rAF so the immediate calls complete during the test
    vi.stubGlobal("requestAnimationFrame", (cb) => { cb(); return 1; });
    vi.stubGlobal("cancelAnimationFrame", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("does nothing when activeTab is not 'chat'", () => {
    const panel = makeFakeElement();
    const composer = makeFakeElement();
    renderHook(() =>
      useChatComposerLayout({
        panelRef: { current: panel },
        composerRef: { current: composer },
        activeTab: "quiz",
        drawerOpen: false,
        shouldShowSideViewer: false,
        effectiveViewerWidth: 0,
      })
    );
    expect(MockResizeObserver).not.toHaveBeenCalled();
    expect(Object.keys(panel.style._data)).toHaveLength(0);
    expect(Object.keys(composer.style._data)).toHaveLength(0);
  });

  it("sets CSS custom properties when activeTab is 'chat'", () => {
    // panel: left=10, width=500; composer: height=60
    const panel = makeFakeElement({ left: 10, width: 500, height: 100 });
    const composer = makeFakeElement({ left: 0, width: 500, height: 60 });
    renderHook(() =>
      useChatComposerLayout({
        panelRef: { current: panel },
        composerRef: { current: composer },
        activeTab: "chat",
        drawerOpen: false,
        shouldShowSideViewer: false,
        effectiveViewerWidth: 0,
      })
    );
    // --chat-composer-left = round(10 + 16) = 26
    expect(composer.style._data["--chat-composer-left"]).toBe("26px");
    // --chat-composer-width = max(500 - 32, 260) = 468
    expect(composer.style._data["--chat-composer-width"]).toBe("468px");
    // --chat-composer-height = max(ceil(60), 88) = 88
    expect(panel.style._data["--chat-composer-height"]).toBe("88px");
    // ResizeObserver should be created and observe both elements
    expect(MockResizeObserver).toHaveBeenCalledOnce();
    const instance = MockResizeObserver.mock.instances[0];
    expect(instance.observe).toHaveBeenCalledTimes(2);
  });

  it("removes CSS properties and disconnects observer on unmount", () => {
    const panel = makeFakeElement({ left: 0, width: 400, height: 100 });
    const composer = makeFakeElement({ left: 0, width: 400, height: 100 });
    const { unmount } = renderHook(() =>
      useChatComposerLayout({
        panelRef: { current: panel },
        composerRef: { current: composer },
        activeTab: "chat",
        drawerOpen: false,
        shouldShowSideViewer: false,
        effectiveViewerWidth: 0,
      })
    );
    unmount();
    expect(panel.style._data["--chat-composer-height"]).toBeUndefined();
    expect(composer.style._data["--chat-composer-left"]).toBeUndefined();
    expect(composer.style._data["--chat-composer-width"]).toBeUndefined();
    const instance = MockResizeObserver.mock.instances[0];
    expect(instance.disconnect).toHaveBeenCalledOnce();
  });
});
