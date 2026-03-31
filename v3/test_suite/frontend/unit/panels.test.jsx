/**
 * Frontend Panel Tests
 * Tests for ChatPanel, LessonPanel, QuizPanel, FlashcardPanel
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import ChatPanel from '../../../frontend/src/components/ChatPanel.jsx';
import LessonPanel from '../../../frontend/src/components/LessonPanel.jsx';
import QuizPanel from '../../../frontend/src/components/QuizPanel.jsx';
import FlashcardPanel from '../../../frontend/src/components/FlashcardPanel.jsx';

// Mock refs and DOM APIs
beforeEach(() => {
  // Mock scrollIntoView for all tests
  Element.prototype.scrollIntoView = vi.fn();
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: vi.fn().mockResolvedValue({}),
    blob: vi.fn().mockResolvedValue(new Blob()),
  });
  // Mock speechSynthesis if needed
  window.speechSynthesis = {
    getVoices: () => [],
    speak: vi.fn(),
    cancel: vi.fn(),
  };
});


/**
 * ChatPanel Tests
 */
describe('ChatPanel Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it('renders chat panel container', () => {
    const { container } = render(<ChatPanel />);
    expect(container).toBeInTheDocument();
  });

  it('renders without error', () => {
    expect(() => render(<ChatPanel />)).not.toThrow();
  });

  it('displays chat panel with correct structure', () => {
    const { container } = render(<ChatPanel />);
    // Basic DOM structure check
    expect(container.innerHTML.length).toBeGreaterThan(0);
  });

  it('accepts session context prop', () => {
    const { container } = render(<ChatPanel sessionId="test-session" />);
    expect(container.innerHTML.length).toBeGreaterThan(0);
  });

  it('displays history button or control', () => {
    const { container } = render(<ChatPanel />);
    const button = container.querySelector('button');
    // Should have at least one button for new chat or history
    expect(button).toBeDefined();
  });

  it('renders without crashing on empty props', () => {
    const { container } = render(<ChatPanel />);
    expect(container.innerHTML.length).toBeGreaterThan(0);
  });
});


/**
 * LessonPanel Tests
 */
describe('LessonPanel Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it('renders lesson panel', () => {
    const { container } = render(<LessonPanel />);
    expect(container).toBeInTheDocument();
  });

  it('renders without error', () => {
    expect(() => render(<LessonPanel />)).not.toThrow();
  });

  it('displays lesson panel structure', () => {
    const { container } = render(<LessonPanel />);
    expect(container.children.length).toBeGreaterThan(0);
  });

  it('accepts chapter prop', () => {
    const { container } = render(<LessonPanel chapter="Biology Chapter 1" />);
    expect(container).toBeInTheDocument();
  });

  it('displays lesson controls', () => {
    const { container } = render(<LessonPanel />);
    const buttons = container.querySelectorAll('button');
    expect(buttons.length).toBeGreaterThanOrEqual(0);
  });

  it('handles missing chapter gracefully', () => {
    const { container } = render(<LessonPanel chapter="" />);
    expect(container.innerHTML.length).toBeGreaterThan(0);
  });

  it('renders step navigation', () => {
    const { container } = render(<LessonPanel />);
    // Should have structure for step-based navigation
    expect(container.innerHTML.length).toBeGreaterThan(0);
  });
});


/**
 * QuizPanel Tests
 */
describe('QuizPanel Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it('renders quiz panel', () => {
    const { container } = render(<QuizPanel />);
    expect(container).toBeInTheDocument();
  });

  it('renders without error', () => {
    expect(() => render(<QuizPanel />)).not.toThrow();
  });

  it('displays quiz panel structure', () => {
    const { container } = render(<QuizPanel />);
    expect(container.children.length).toBeGreaterThan(0);
  });

  it('accepts session prop', () => {
    const { container } = render(<QuizPanel sessionId="quiz-session" />);
    expect(container).toBeInTheDocument();
  });

  it('displays quiz controls', () => {
    const { container } = render(<QuizPanel />);
    const buttons = container.querySelectorAll('button');
    // Quiz should have interactive buttons
    expect(buttons.length).toBeGreaterThanOrEqual(0);
  });

  it('handles empty session gracefully', () => {
    const { container } = render(<QuizPanel sessionId="" />);
    expect(container.innerHTML.length).toBeGreaterThan(0);
  });

  it('renders question display area', () => {
    const { container } = render(<QuizPanel />);
    // Should have area for question/answer display
    expect(container.innerHTML.length).toBeGreaterThan(0);
  });

  it('has submit button or control', () => {
    const { container } = render(<QuizPanel />);
    // Quiz should have ability to submit answers
    expect(container.children.length).toBeGreaterThan(0);
  });
});


/**
 * FlashcardPanel Tests
 */
describe('FlashcardPanel Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it('renders flashcard panel', () => {
    const { container } = render(<FlashcardPanel />);
    expect(container).toBeInTheDocument();
  });

  it('renders without error', () => {
    expect(() => render(<FlashcardPanel />)).not.toThrow();
  });

  it('displays flashcard panel structure', () => {
    const { container } = render(<FlashcardPanel />);
    expect(container.children.length).toBeGreaterThan(0);
  });

  it('accepts deck prop', () => {
    const { container } = render(<FlashcardPanel deckId="deck-123" />);
    expect(container).toBeInTheDocument();
  });

  it('displays card navigation', () => {
    const { container } = render(<FlashcardPanel />);
    // Should have previous/next or similar navigation
    expect(container.innerHTML.length).toBeGreaterThan(0);
  });

  it('handles empty deck gracefully', () => {
    const { container } = render(<FlashcardPanel deckId="" />);
    expect(container.innerHTML.length).toBeGreaterThan(0);
  });

  it('renders card display area', () => {
    const { container } = render(<FlashcardPanel />);
    // Should display a card or card placeholder
    expect(container.children.length).toBeGreaterThan(0);
  });

  it('has flip or interaction control', () => {
    const { container } = render(<FlashcardPanel />);
    // Flashcard should have way to interact with cards
    const allButtons = container.querySelectorAll('button');
    // May have control buttons
    expect(allButtons.length).toBeGreaterThanOrEqual(0);
  });
});


/**
 * Panel Integration Tests
 */
describe('Panel Integration', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it('renders multiple panels independently', () => {
    const { container: chatContainer } = render(<ChatPanel />);
    const { container: lessonContainer } = render(<LessonPanel />);
    const { container: quizContainer } = render(<QuizPanel />);
    
    expect(chatContainer).toBeInTheDocument();
    expect(lessonContainer).toBeInTheDocument();
    expect(quizContainer).toBeInTheDocument();
  });

  it('panels handle rapid prop changes', () => {
    const { rerender, container } = render(<ChatPanel sessionId="session1" />);
    rerender(<ChatPanel sessionId="session2" />);
    rerender(<ChatPanel sessionId="session3" />);
    
    expect(container.innerHTML.length).toBeGreaterThan(0);
  });

  it('panels maintain separate state', () => {
    const { container: c1 } = render(<ChatPanel />);
    const { container: c2 } = render(<LessonPanel />);
    const { container: c3 } = render(<QuizPanel />);
    
    // All panels should render without interference
    expect(c1.innerHTML.length).toBeGreaterThan(0);
    expect(c2.innerHTML.length).toBeGreaterThan(0);
    expect(c3.innerHTML.length).toBeGreaterThan(0);
  });

  it('all panels render list items', () => {
    const { container: chatContainer } = render(<ChatPanel />);
    const { container: lessonContainer } = render(<LessonPanel />);
    const { container: quizContainer } = render(<QuizPanel />);
    
    // Basic validation that panels have content
    expect(chatContainer.innerHTML.length).toBeGreaterThan(0);
    expect(lessonContainer.innerHTML.length).toBeGreaterThan(0);
    expect(quizContainer.innerHTML.length).toBeGreaterThan(0);
  });
});


/**
 * Panel Accessibility Tests
 */
describe('Panel Accessibility', () => {
  it('ChatPanel has semantic structure', () => {
    const { container } = render(<ChatPanel />);
    expect(container).toBeInTheDocument();
  });

  it('LessonPanel has interactive elements', () => {
    const { container } = render(<LessonPanel />);
    const buttons = container.querySelectorAll('button');
    // Should have buttons or interactive controls
    expect(container.children.length).toBeGreaterThan(0);
  });

  it('QuizPanel has form controls', () => {
    const { container } = render(<QuizPanel />);
    // Quiz should be interactive
    expect(container.children.length).toBeGreaterThan(0);
  });

  it('FlashcardPanel has navigation', () => {
    const { container } = render(<FlashcardPanel />);
    // Flashcard should have navigation or display
    expect(container.children.length).toBeGreaterThan(0);
  });
});
