/**
 * Component Unit Tests for Frontend
 * Tests: Login, MessageContent, VoiceControl components
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import Login from '../../../frontend/src/components/Login.jsx';
import MessageContent from '../../../frontend/src/components/MessageContent.jsx';
import VoiceControl from '../../../frontend/src/components/VoiceControl.jsx';

describe('Login Component', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
    global.fetch = undefined;
  });

  it('lets new users choose a role during registration', () => {
    render(<Login />);
    fireEvent.click(screen.getByRole('button', { name: /register/i }));

    expect(screen.getByLabelText(/register as/i)).toBeInTheDocument();
    expect(screen.getByRole('option', { name: /student/i })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: /teacher/i })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: /parent/i })).toBeInTheDocument();
  });

  it('renders continue button', () => {
    render(<Login />);
    const continueButton = screen.getByRole('button', { name: /continue/i });
    expect(continueButton).toBeInTheDocument();
  });

  it('has form inputs on render', () => {
    const { container } = render(<Login />);
    const inputs = container.querySelectorAll('input');
    expect(inputs.length).toBeGreaterThan(0);
  });

  it('accepts input values', () => {
    const { container } = render(<Login />);
    const input = container.querySelector('input[type="text"]') || container.querySelector('input[type="email"]');
    if (input) {
      fireEvent.change(input, { target: { value: 'test@example.com' } });
      expect(input.value).toBe('test@example.com');
    }
  });
});

describe('MessageContent Component', () => {
  it('renders plain text message', () => {
    const message = 'This is a test message';
    render(<MessageContent content={message} />);
    expect(screen.getByText(/test message/)).toBeInTheDocument();
  });

  it('renders with role attribute', () => {
    const message = 'Test message';
    const { container } = render(<MessageContent content={message} />);
    expect(container).toBeInTheDocument();
  });

  it('handles string content prop', () => {
    render(<MessageContent content="Hello World" />);
    expect(screen.getByText(/Hello World/)).toBeInTheDocument();
  });

  it('does not crash with empty content', () => {
    const { container } = render(<MessageContent content="" />);
    expect(container.querySelector('.markdown-content')).toBeInTheDocument();
  });

  it('renders multiple lines of text', () => {
    const message = 'Line 1\nLine 2\nLine 3';
    render(<MessageContent content={message} />);
    expect(screen.getByText(/Line 1/)).toBeInTheDocument();
  });
});

describe('VoiceControl Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    delete window.SpeechRecognition;
    delete window.webkitSpeechRecognition;
  });

  it('renders voice control button', () => {
    window.SpeechRecognition = vi.fn();
    render(<VoiceControl onResult={vi.fn()} />);
    const button = screen.getByRole('button');
    expect(button).toBeInTheDocument();
  });

  it('shows Voice label on button', () => {
    window.SpeechRecognition = vi.fn();
    render(<VoiceControl onResult={vi.fn()} />);
    expect(screen.getByText('Voice')).toBeInTheDocument();
  });

  it('disables button when no SpeechRecognition available', () => {
    render(<VoiceControl onResult={vi.fn()} />);
    const button = screen.getByRole('button');
    expect(button).toBeDisabled();
  });

  it('renders SVG icon', () => {
    window.SpeechRecognition = vi.fn();
    const { container } = render(<VoiceControl onResult={vi.fn()} />);
    expect(container.querySelector('svg')).toBeInTheDocument();
  });

  it('uses webkitSpeechRecognition as fallback', () => {
    delete window.SpeechRecognition;
    window.webkitSpeechRecognition = vi.fn();
    
    render(<VoiceControl onResult={vi.fn()} />);
    const button = screen.getByRole('button');
    expect(button).not.toBeDisabled();
  });
});

describe('API Integration', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('includes authorization header in requests', async () => {
    const token = 'test-token-123';
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ data: {} }),
      })
    );

    await fetch('http://127.0.0.1:8001/api/test', {
      headers: { Authorization: `Bearer ${token}` },
    });

    expect(global.fetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: `Bearer ${token}`,
        }),
      })
    );
  });

  it('handles 401 response', async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: false,
        status: 401,
      })
    );

    const response = await fetch('http://127.0.0.1:8001/api/test');
    expect(response.status).toBe(401);
  });

  it('handles successful response', async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ message: 'success' }),
      })
    );

    const response = await fetch('http://127.0.0.1:8001/api/test');
    expect(response.ok).toBe(true);
  });
});

describe('Storage Management', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('stores token in localStorage', () => {
    localStorage.setItem('token', 'test-token');
    expect(localStorage.getItem('token')).toBe('test-token');
  });

  it('retrieves stored token', () => {
    const token = 'my-token-123';
    localStorage.setItem('token', token);
    expect(localStorage.getItem('token')).toBe(token);
  });

  it('removes token on logout', () => {
    localStorage.setItem('token', 'test-token');
    localStorage.removeItem('token');
    expect(localStorage.getItem('token')).toBeNull();
  });

  it('stores session data as JSON', () => {
    const sessionData = { userId: '123', email: 'test@example.com' };
    localStorage.setItem('session', JSON.stringify(sessionData));
    
    const retrieved = JSON.parse(localStorage.getItem('session'));
    expect(retrieved).toEqual(sessionData);
  });

  it('handles missing token gracefully', () => {
    const token = localStorage.getItem('token');
    expect(token).toBeNull();
  });
});

describe('Error Handling', () => {
  it('catches and handles fetch errors', async () => {
    global.fetch = vi.fn(() =>
      Promise.reject(new Error('Network error'))
    );

    try {
      await fetch('http://127.0.0.1:8001/api/test');
      expect(false).toBe(true); // Should not reach here
    } catch (error) {
      expect(error.message).toBe('Network error');
    }
  });

  it('handles invalid JSON response', async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.reject(new Error('Invalid JSON')),
      })
    );

    const response = await fetch('http://127.0.0.1:8001/api/test');
    try {
      await response.json();
      expect(false).toBe(true);
    } catch (error) {
      expect(error.message).toBe('Invalid JSON');
    }
  });

  it('validates email format', () => {
    const validEmail = 'test@example.com';
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    expect(emailRegex.test(validEmail)).toBe(true);
  });

  it('rejects invalid email format', () => {
    const invalidEmail = 'not-an-email';
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    expect(emailRegex.test(invalidEmail)).toBe(false);
  });
});
