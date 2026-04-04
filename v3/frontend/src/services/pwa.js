export function registerServiceWorker() {
  if (typeof window === "undefined" || !("serviceWorker" in navigator)) {
    return;
  }

  window.addEventListener("load", async () => {
    try {
      await navigator.serviceWorker.register("/sw.js");
    } catch (error) {
      console.warn("Service worker registration failed:", error);
    }
  });
}

export function setupInstallPrompt(onPromptChange) {
  if (typeof window === "undefined") {
    return () => {};
  }

  let deferredPrompt = null;

  const onBeforeInstallPrompt = (event) => {
    event.preventDefault();
    deferredPrompt = event;
    if (typeof onPromptChange === "function") {
      onPromptChange(true);
    }
  };

  const onAppInstalled = () => {
    deferredPrompt = null;
    if (typeof onPromptChange === "function") {
      onPromptChange(false);
    }
  };

  window.addEventListener("beforeinstallprompt", onBeforeInstallPrompt);
  window.addEventListener("appinstalled", onAppInstalled);

  return async () => {
    if (!deferredPrompt) return false;
    await deferredPrompt.prompt();
    const choice = await deferredPrompt.userChoice;
    deferredPrompt = null;
    if (typeof onPromptChange === "function") {
      onPromptChange(false);
    }
    return choice?.outcome === "accepted";
  };
}
