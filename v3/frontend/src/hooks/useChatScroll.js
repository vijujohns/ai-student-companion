import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Manages chat message list scroll behaviour:
 *  - tracks whether the viewport is within 80 px of the bottom
 *  - auto-scrolls the sentinel into view when new content arrives (only if near bottom)
 *  - exposes an imperative `scrollToConversationEnd` for the "scroll down" button
 *
 * @param {Object} opts
 * @param {string} opts.activeTab       - re-attaches scroll listener when tab changes
 * @param {Array}  opts.messages        - triggers auto-scroll check on new messages
 * @param {string} opts.currentStream   - triggers auto-scroll check during streaming
 *
 * @returns {{
 *   chatMessagesRef: React.RefObject,
 *   messagesEndRef: React.RefObject,
 *   isNearBottom: boolean,
 *   scrollToConversationEnd: () => void,
 * }}
 */
export function useChatScroll({ activeTab, messages, currentStream }) {
  const chatMessagesRef = useRef(null);
  const messagesEndRef = useRef(null);
  const [isNearBottom, setIsNearBottom] = useState(true);

  // Track near-bottom state via scroll + resize listeners
  useEffect(() => {
    const container = chatMessagesRef.current;
    if (!container) return undefined;

    const checkNearBottom = () => {
      const distance = container.scrollHeight - container.scrollTop - container.clientHeight;
      setIsNearBottom(distance <= 80);
    };

    checkNearBottom();
    container.addEventListener("scroll", checkNearBottom, { passive: true });
    window.addEventListener("resize", checkNearBottom);

    return () => {
      container.removeEventListener("scroll", checkNearBottom);
      window.removeEventListener("resize", checkNearBottom);
    };
  }, [activeTab]);

  // Auto-scroll sentinel into view on new content when already near bottom
  useEffect(() => {
    if (!isNearBottom) return;
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, currentStream, isNearBottom]);

  const scrollToConversationEnd = useCallback(() => {
    const container = chatMessagesRef.current;
    if (container) {
      container.scrollTo({ top: container.scrollHeight, behavior: "smooth" });
      return;
    }
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, []);

  return { chatMessagesRef, messagesEndRef, isNearBottom, scrollToConversationEnd };
}
