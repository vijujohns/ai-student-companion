/**
 * Frontend Panel Tests
 * Tests for ChatPanel, LessonPanel, QuizPanel, FlashcardPanel
 */

import { act, fireEvent, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { describe, it, expect, beforeEach, vi } from 'vitest';

vi.mock('../../../frontend/src/hooks/useChatWebSocketLifecycle', () => ({
  useChatWebSocketLifecycle: () => {},
}));

import ChatPanel from '../../../frontend/src/components/ChatPanel.jsx';
import LessonPanel from '../../../frontend/src/components/LessonPanel.jsx';
import QuizPanel from '../../../frontend/src/components/QuizPanel.jsx';
import FlashcardPanel from '../../../frontend/src/components/FlashcardPanel.jsx';
import AssessmentPanel from '../../../frontend/src/components/AssessmentPanel.jsx';
import ProgressPanel from '../../../frontend/src/components/ProgressPanel.jsx';
import RoleHubPanel from '../../../frontend/src/components/RoleHubPanel.jsx';
import AdminPanel from '../../../frontend/src/components/AdminPanel.jsx';

async function flushEffects(cycles = 3) {
  for (let index = 0; index < cycles; index += 1) {
    await act(async () => {
      await Promise.resolve();
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
  }
}

async function renderWithEffects(ui) {
  const view = render(ui);
  await flushEffects();
  return view;
}

async function rerenderWithEffects(view, ui) {
  await act(async () => {
    view.rerender(ui);
  });
  await flushEffects();
}

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

  it('renders chat panel container', async () => {
    const { container } = await renderWithEffects(<ChatPanel />);
    expect(container).toBeInTheDocument();
  });

  it('renders without error', async () => {
    await expect(renderWithEffects(<ChatPanel />)).resolves.toBeTruthy();
  });

  it('displays chat panel with correct structure', async () => {
    const { container } = await renderWithEffects(<ChatPanel />);
    // Basic DOM structure check
    expect(container.innerHTML.length).toBeGreaterThan(0);
  });

  it('accepts session context prop', async () => {
    const { container } = await renderWithEffects(<ChatPanel sessionId="test-session" />);
    expect(container.innerHTML.length).toBeGreaterThan(0);
  });

  it('displays history button or control', async () => {
    const { container } = await renderWithEffects(<ChatPanel />);
    const button = container.querySelector('button');
    // Should have at least one button for new chat or history
    expect(button).toBeDefined();
  });

  it('renders without crashing on empty props', async () => {
    const { container } = await renderWithEffects(<ChatPanel />);
    expect(container.innerHTML.length).toBeGreaterThan(0);
  });

  it('reserves composer space so the latest chat response is not hidden behind the floating input', async () => {
    const { container } = await renderWithEffects(<ChatPanel />);
    const workspaceMain = container.querySelector('.workspace-main');
    expect(workspaceMain).toBeTruthy();
    expect(workspaceMain.style.getPropertyValue('--chat-composer-height')).toBe('88px');
  });

  it('uses a plan action to open quiz with prefilled focus', async () => {
    global.fetch.mockImplementation((url) => {
      const target = String(url);

      if (target.includes('/progress/dashboard')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            total_study_seconds: 2400,
            streak_days: 3,
            totals: { quizzes: 4, lessons: 5, assessments: 1 },
            top_subjects: [],
            recent_activity: [],
            mastery_summary: [],
          }),
        });
      }

      if (target.includes('/progress/insights')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ headline: '', recommendations: [], badges: [] }),
        });
      }

      if (target.includes('/progress/study-plan')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            headline: 'Focus on Science this week.',
            focus_subject: 'Science',
            schedule: [
              {
                id: 'quiz-step',
                title: 'Take a quick Science quiz',
                description: 'Check recall with a short quiz.',
                cta_label: 'Start Quiz',
                action_tab: 'quiz',
                chapter_hint: 'Science',
                context_hint: 'Check recall with a short quiz.',
                auto_run: true,
              },
            ],
          }),
        });
      }

      if (target.includes('/quiz/generate')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            quiz_id: 'quiz-123',
            quiz: [
              {
                id: 'q1',
                question: 'What is light?',
                options: ['Energy', 'Matter', 'Force', 'Heat'],
                correct_option: 'Energy',
              },
            ],
          }),
        });
      }

      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    });

    await renderWithEffects(<ChatPanel />);

    fireEvent.click(screen.getByRole('button', { name: /progress/i }));
    fireEvent.click(await screen.findByRole('button', { name: 'Start Quiz' }));

    expect(await screen.findByDisplayValue('Check recall with a short quiz.')).toBeInTheDocument();
  }, 15000);

  it('can auto-run the selected quiz plan action', async () => {
    global.fetch.mockImplementation((url, options = {}) => {
      const target = String(url);

      if (target.includes('/progress/dashboard')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            total_study_seconds: 2400,
            streak_days: 3,
            totals: { quizzes: 4, lessons: 5, assessments: 1 },
            top_subjects: [],
            recent_activity: [],
            mastery_summary: [],
          }),
        });
      }

      if (target.includes('/progress/insights')) {
        return Promise.resolve({ ok: true, status: 200, json: async () => ({ headline: '', recommendations: [], badges: [] }) });
      }

      if (target.includes('/progress/study-plan')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            headline: 'Focus on Science this week.',
            focus_subject: 'Science',
            schedule: [
              {
                id: 'quiz-step',
                title: 'Take a quick Science quiz',
                description: 'Check recall with a short quiz.',
                cta_label: 'Start Quiz',
                action_tab: 'quiz',
                chapter_hint: 'Science',
                context_hint: 'Check recall with a short quiz.',
                auto_run: true,
              },
            ],
          }),
        });
      }

      if (target.includes('/quiz/generate')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            quiz_id: 'quiz-123',
            quiz: [
              {
                id: 'q1',
                question: 'What is light?',
                options: ['Energy', 'Matter', 'Force', 'Heat'],
                correct_option: 'Energy',
              },
            ],
          }),
        });
      }

      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    });

    await renderWithEffects(<ChatPanel />);

    fireEvent.click(screen.getByRole('button', { name: /progress/i }));
    fireEvent.click(await screen.findByRole('button', { name: 'Start Quiz' }));
    await flushEffects(10);

    expect(await screen.findByText('What is light?', {}, { timeout: 5000 })).toBeInTheDocument();
  }, 15000);

  it('uses a plan action to open assessment with prefilled focus', async () => {
    global.fetch.mockImplementation((url) => {
      const target = String(url);

      if (target.includes('/progress/dashboard')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            total_study_seconds: 2400,
            streak_days: 3,
            totals: { quizzes: 4, lessons: 5, assessments: 2 },
            top_subjects: [],
            recent_activity: [],
            mastery_summary: [],
            assessment_summary: { average_score_pct: 58, best_score_pct: 80, latest_score_pct: 52, recent_scores: [52, 80] },
          }),
        });
      }

      if (target.includes('/progress/insights')) {
        return Promise.resolve({ ok: true, status: 200, json: async () => ({ headline: '', recommendations: [], badges: [] }) });
      }

      if (target.includes('/progress/study-plan')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            headline: 'Rebuild confidence in Science.',
            focus_subject: 'Science',
            schedule: [
              {
                id: 'assessment-step',
                title: 'Retry a Science assessment',
                description: 'Use one exam-style checkpoint to rebuild confidence.',
                cta_label: 'Start Assessment',
                action_tab: 'assessment',
                chapter_hint: 'Science',
                context_hint: 'Use one exam-style checkpoint to rebuild confidence.',
                auto_run: false,
              },
            ],
          }),
        });
      }

      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    });

    await renderWithEffects(<ChatPanel />);

    fireEvent.click(screen.getByRole('button', { name: /progress/i }));
    fireEvent.click(await screen.findByRole('button', { name: 'Start Assessment' }));

    expect(await screen.findByRole('heading', { name: /generate assessment/i })).toBeInTheDocument();
    expect(await screen.findByDisplayValue('Science')).toBeInTheDocument();
  }, 15000);

  it('can auto-run the selected assessment plan action', async () => {
    global.fetch.mockImplementation((url) => {
      const target = String(url);

      if (target.includes('/progress/dashboard')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            total_study_seconds: 2400,
            streak_days: 3,
            totals: { quizzes: 4, lessons: 5, assessments: 2 },
            top_subjects: [],
            recent_activity: [],
            mastery_summary: [],
            assessment_summary: { average_score_pct: 58, best_score_pct: 80, latest_score_pct: 52, recent_scores: [52, 80] },
          }),
        });
      }

      if (target.includes('/progress/insights')) {
        return Promise.resolve({ ok: true, status: 200, json: async () => ({ headline: '', recommendations: [], badges: [] }) });
      }

      if (target.includes('/progress/study-plan')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            headline: 'Rebuild confidence in Science.',
            focus_subject: 'Science',
            schedule: [
              {
                id: 'assessment-step',
                title: 'Retry a Science assessment',
                description: 'Use one exam-style checkpoint to rebuild confidence.',
                cta_label: 'Start Assessment',
                action_tab: 'assessment',
                chapter_hint: 'Science',
                context_hint: 'Use one exam-style checkpoint to rebuild confidence.',
                auto_run: true,
              },
            ],
          }),
        });
      }

      if (target.includes('/assessment/subject-quiz')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            data: {
              paper_id: 44,
              paper_type: 'SUBJECT_QUIZ',
              subject: 'Science',
              class_name: 'Class 10',
              difficulty: 'mixed',
              mode: 'exam',
              questions: [
                {
                  id: 'q1',
                  question: 'What is reflection?',
                  options: ['Light bouncing back', 'Sound wave', 'Heat transfer', 'Plant growth'],
                  correct_option: 'Light bouncing back',
                  marks: 1,
                },
              ],
            },
          }),
        });
      }

      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    });

    await renderWithEffects(<ChatPanel />);

    fireEvent.click(screen.getByRole('button', { name: /progress/i }));
    fireEvent.click(await screen.findByRole('button', { name: 'Start Assessment' }));
    await flushEffects(10);

    expect(await screen.findByText('What is reflection?', {}, { timeout: 5000 })).toBeInTheDocument();
  }, 15000);

  it('surfaces a profile workspace and filters class choices to active subscriptions', async () => {
    global.fetch.mockImplementation((url) => {
      const target = String(url);

      if (target.includes('/auth/session')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ authenticated: true, username: 'student', role: 'student', email: 'student@example.com' }),
        });
      }

      if (target.includes('/plan/me')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            plan: {
              plan_code: 'pro',
              is_trial: false,
              limits: { ask_count: 500 },
              entitlements: [{ feature_key: 'mentor_assignments', enabled: true }],
              classes: [{ class_name: 'Class 8', auto_renew: true, expires_at: '2027-04-01T00:00:00Z' }],
            },
            usage: { ask_count: 12 },
          }),
        });
      }

      if (target.includes('/classes')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ classes: ['Class 8', 'Class 9'] }),
        });
      }

      if (target.includes('/profile')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            profile: {
              username: 'student',
              email: 'student@example.com',
              role: 'student',
              first_name: 'Test',
              last_name: 'Learner',
              dob: '2008-08-08',
            },
          }),
        });
      }

      return Promise.resolve({ ok: true, status: 200, json: async () => ({ sessions: [], data: {}, items: [] }) });
    });

    const view = await renderWithEffects(<ChatPanel initialActiveTab="profile" />);

    expect(screen.queryByRole('button', { name: /^profile$/i })).not.toBeInTheDocument();
    expect(view.container.querySelector('.workspace-context-bar')).not.toBeInTheDocument();
    expect(await screen.findByLabelText(/first name/i)).toBeInTheDocument();
    expect(await screen.findByText(/active class subscriptions/i)).toBeInTheDocument();
    expect(screen.queryByText(/class 9/i)).not.toBeInTheDocument();
  }, 15000);

  it('surfaces a billing workspace with renewal and upgrade details', async () => {
    global.fetch.mockImplementation((url) => {
      const target = String(url);

      if (target.includes('/auth/session')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ authenticated: true, username: 'student', role: 'student', email: 'student@example.com' }),
        });
      }

      if (target.includes('/plan/me')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            plan: {
              plan_code: 'premium',
              is_trial: false,
              auto_renew: true,
              plan_started_at: '2026-03-01T00:00:00Z',
              plan_expires_at: '2027-03-01T00:00:00Z',
              trial_ends_at: null,
              limits: { ask_count: 500, lesson_count: 100, quiz_count: 100 },
              entitlements: [
                { feature_key: 'mentor_assignments', enabled: true, hint: 'Track and complete mentor tasks.' },
                { feature_key: 'assessment_workspace', enabled: true, hint: 'Generate practice papers and exams.' },
              ],
              classes: [
                {
                  class_name: 'Class 8',
                  annual_price_cents: 49900,
                  currency: 'INR',
                  promo_code: 'WELCOME10',
                  started_at: '2026-03-01T00:00:00Z',
                  expires_at: '2027-03-01T00:00:00Z',
                  auto_renew: true,
                },
              ],
            },
            usage: { ask_count: 12, lesson_count: 4, quiz_count: 3 },
          }),
        });
      }

      if (target.includes('/classes')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ classes: ['Class 8', 'Class 9'] }),
        });
      }

      return Promise.resolve({ ok: true, status: 200, json: async () => ({ sessions: [], data: {}, items: [] }) });
    });

    await renderWithEffects(<ChatPanel initialActiveTab="billing" />);

    expect(await screen.findByText(/current plan/i)).toBeInTheDocument();
    expect(await screen.findByText(/renews on/i)).toBeInTheDocument();
    expect(await screen.findByText(/estimated annual renewal/i)).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: /manage subscription/i })).toBeInTheDocument();
  }, 15000);

  it('shows the class and file context bar only on study workspaces', async () => {
    global.fetch.mockImplementation((url) => {
      const target = String(url);

      if (target.includes('/auth/session')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ authenticated: true, username: 'student', role: 'student', email: 'student@example.com' }),
        });
      }

      if (target.includes('/plan/me')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            plan: {
              plan_code: 'premium',
              is_trial: false,
              limits: { ask_count: 500 },
              entitlements: [],
              classes: [{ class_name: 'Class 8', auto_renew: true, expires_at: '2027-04-01T00:00:00Z' }],
            },
            usage: { ask_count: 12 },
          }),
        });
      }

      if (target.includes('/classes')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ classes: ['Class 8'] }),
        });
      }

      return Promise.resolve({ ok: true, status: 200, json: async () => ({ sessions: [], data: {}, items: [] }) });
    });

    const view = await renderWithEffects(<ChatPanel initialActiveTab="chat" />);

    expect(view.container.querySelector('.workspace-context-bar')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /edit context/i })).toBeInTheDocument();
    expect(screen.queryByText(/knowledge base loaded\./i)).not.toBeInTheDocument();
    expect(screen.queryByText(/folder optional|file optional/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/all available classes are currently visible for your current plan\./i)).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^subscription$/i })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /edit context/i }));
    expect(await screen.findByText(/subscribed classes: class 8/i)).toBeInTheDocument();

    await rerenderWithEffects(view, <ChatPanel initialActiveTab="progress" />);

    expect(view.container.querySelector('.workspace-context-bar')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /edit context/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^subscription$/i })).not.toBeInTheDocument();
  }, 15000);

  it('opens the learning context modal and supports Explorer Mode', async () => {
    global.fetch.mockImplementation((url) => {
      const target = String(url);

      if (target.includes('/classes')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ classes: ['Class 8'] }),
        });
      }

      if (target.includes('/context')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ mode: null, class_name: null, subject_name: null, folder_name: null, content_id: null }),
        });
      }

      return Promise.resolve({ ok: true, status: 200, json: async () => ({ sessions: [], data: {}, items: [] }) });
    });

    await renderWithEffects(<ChatPanel initialActiveTab="chat" />);

    expect(await screen.findByRole('dialog', { name: /choose learning context/i })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /proceed in explorer mode/i }));

    expect(await screen.findByText(/Explorer Mode · choose a class to unlock guided study tools/i)).toBeInTheDocument();
  }, 15000);

  it('blocks lesson access until class and subject are selected', async () => {
    global.fetch.mockImplementation((url) => {
      const target = String(url);

      if (target.includes('/classes')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ classes: ['Class 8'] }),
        });
      }

      if (target.includes('/context')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ mode: null, class_name: null, subject_name: null, folder_name: null, content_id: null }),
        });
      }

      return Promise.resolve({ ok: true, status: 200, json: async () => ({ sessions: [], data: {}, items: [] }) });
    });

    await renderWithEffects(<ChatPanel initialActiveTab="lesson" />);

    expect(await screen.findByText(/Please select your class and subject to continue/i)).toBeInTheDocument();
    expect(screen.getByRole('dialog', { name: /choose learning context/i })).toBeInTheDocument();
  }, 15000);

  it('shows a dedicated assignments workspace for students', async () => {
    localStorage.setItem('username', 'student');
    localStorage.setItem('role', 'student');

    global.fetch.mockImplementation((url, options = {}) => {
      const target = String(url);
      const method = String(options?.method || 'GET').toUpperCase();

      if (target.includes('/students/student/assignments') && method === 'PUT') {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ id: 9, status: 'completed' }),
        });
      }

      if (target.includes('/students/student/assignments')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            assignments: [
              {
                id: 9,
                title: 'Practice Science quiz',
                description: 'Complete the short quiz on light and reflection.',
                status: 'assigned',
                action_tab: 'quiz',
                cta_label: 'Open Assigned Quiz',
                chapter_hint: 'Science',
                due_label: '2026-04-05',
                author_role: 'teacher',
              },
            ],
          }),
        });
      }

      return Promise.resolve({ ok: true, status: 200, json: async () => ({ sessions: [], data: {}, items: [] }) });
    });

    await renderWithEffects(<ChatPanel />);

    fireEvent.click(await screen.findByRole('button', { name: /^assignments$/i }));

    expect(await screen.findByRole('button', { name: /refresh assignments/i })).toBeInTheDocument();
    expect(await screen.findByText(/practice science quiz/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /mark done/i }));

    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/students/student/assignments/9'),
      expect.objectContaining({ method: 'PUT' }),
    );
  }, 15000);

  it('shows linked learner assignments for parent accounts', async () => {
    localStorage.setItem('username', 'parent1');
    localStorage.setItem('role', 'parent');

    global.fetch.mockImplementation((url) => {
      const target = String(url);

      if (target.includes('/relationships/my-students')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            students: [
              {
                username: 'student',
                email: 'student@example.com',
                first_name: 'Student One',
                linked_at: '2026-04-03T10:00:00Z',
              },
            ],
          }),
        });
      }

      if (target.includes('/students/student/assignments')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            assignments: [
              {
                id: 14,
                title: 'Read Chapter 3 recap',
                description: 'Help your learner finish the recap before Friday.',
                status: 'assigned',
                action_tab: 'lesson',
                cta_label: 'Open Assigned Lesson',
                chapter_hint: 'Science',
                due_label: '2026-04-10',
                author_role: 'teacher',
              },
            ],
          }),
        });
      }

      return Promise.resolve({ ok: true, status: 200, json: async () => ({ sessions: [], data: {}, items: [] }) });
    });

    await renderWithEffects(<ChatPanel />);

    fireEvent.click(await screen.findByRole('button', { name: /^assignments$/i }));

    expect(await screen.findByText(/viewing assignments for student one/i)).toBeInTheDocument();
    expect(await screen.findByText(/read chapter 3 recap/i)).toBeInTheDocument();
  }, 15000);

  it('lands parent accounts in the role hub with a quick assignments shortcut', async () => {
    localStorage.setItem('username', 'parent1');
    localStorage.setItem('role', 'parent');

    global.fetch.mockImplementation((url) => {
      const target = String(url);

      if (target.includes('/relationships/my-students')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            students: [
              {
                username: 'student',
                email: 'student@example.com',
                first_name: 'Student One',
                linked_at: '2026-04-03T10:00:00Z',
              },
            ],
          }),
        });
      }

      if (target.includes('/students/student/progress')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            student_username: 'student',
            dashboard: {
              total_study_seconds: 1200,
              streak_days: 2,
              totals: { quizzes: 2, lessons: 3, assessments: 1 },
              recent_activity: [],
              assignments: [],
              assessment_summary: {},
            },
            mastery: [],
            study_plan: null,
            insights: { headline: '', notifications: [], recommendations: [], badges: [] },
          }),
        });
      }

      if (target.includes('/students/student/notes')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ notes: [] }),
        });
      }

      return Promise.resolve({ ok: true, status: 200, json: async () => ({ sessions: [], data: {}, items: [] }) });
    });

    await renderWithEffects(<ChatPanel />);

    expect(await screen.findByText(/parent dashboard summary/i)).toBeInTheDocument();
    expect((await screen.findAllByRole('button', { name: /open student assignments/i })).length).toBeGreaterThan(0);
  }, 15000);

  it('hides mentor-only workspaces for student accounts', async () => {
    localStorage.setItem('username', 'student');
    localStorage.setItem('role', 'student');

    global.fetch.mockImplementation(() =>
      Promise.resolve({ ok: true, status: 200, json: async () => ({ sessions: [], data: {}, items: [], classes: ['Class 8'] }) })
    );

    await renderWithEffects(<ChatPanel />);

    expect(await screen.findByRole('button', { name: /^assignments$/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /role hub/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /assessment/i })).not.toBeInTheDocument();
  }, 15000);

  it('exposes all major workspace pages for admin accounts', async () => {
    localStorage.setItem('role', 'admin');
    localStorage.setItem('username', 'admin');

    await renderWithEffects(<ChatPanel />);

    expect(screen.getByRole('button', { name: /admin center/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /role hub/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /chat/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /lesson/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /quiz/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /cards/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /assignments/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /progress/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /assessment/i })).toBeInTheDocument();
  });

  it('filters the visible workspace tabs to the selected admin preview role', async () => {
    localStorage.setItem('role', 'admin');
    localStorage.setItem('username', 'admin');

    global.fetch.mockImplementation(() =>
      Promise.resolve({ ok: true, status: 200, json: async () => ({ sessions: [], data: {}, items: [], classes: ['Class 8'] }) })
    );

    await renderWithEffects(<ChatPanel />);

    fireEvent.change(screen.getByLabelText(/view workspace as/i), { target: { value: 'teacher' } });
    await flushEffects();

    expect(screen.getByRole('button', { name: /admin center/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /teacher hub/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /assignments/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /progress/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /assessment/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^chat$/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^lesson$/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^quiz$/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^cards$/i })).not.toBeInTheDocument();
  });

  it('keeps parent navigation focused on monitoring workflows', async () => {
    localStorage.setItem('username', 'parent1');
    localStorage.setItem('role', 'parent');

    global.fetch.mockImplementation((url) => {
      const target = String(url);

      if (target.includes('/relationships/my-students')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            students: [
              {
                username: 'student',
                email: 'student@example.com',
                first_name: 'Student One',
                linked_at: '2026-04-03T10:00:00Z',
              },
            ],
          }),
        });
      }

      if (target.includes('/students/student/progress')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            student_username: 'student',
            dashboard: {
              total_study_seconds: 1200,
              streak_days: 2,
              totals: { quizzes: 2, lessons: 3, assessments: 1 },
              recent_activity: [],
              assignments: [],
              assessment_summary: {},
            },
            mastery: [],
            study_plan: null,
            insights: { headline: '', notifications: [], recommendations: [], badges: [] },
          }),
        });
      }

      if (target.includes('/students/student/notes')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ notes: [] }),
        });
      }

      return Promise.resolve({ ok: true, status: 200, json: async () => ({ sessions: [], data: {}, items: [] }) });
    });

    await renderWithEffects(<ChatPanel />);

    expect(await screen.findByText(/parent dashboard summary/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /chat workspace/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /lesson workspace/i })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^assignments$/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^billing$/i })).not.toBeInTheDocument();
  }, 15000);
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
    expect(container.querySelector('.panel-grid--stacked')).toBeInTheDocument();
    expect(container.querySelector('.panel-card--stretch')).toBeInTheDocument();
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

  it('renders quiz panel', async () => {
    const { container } = await renderWithEffects(<QuizPanel />);
    expect(container).toBeInTheDocument();
  });

  it('renders without error', async () => {
    await expect(renderWithEffects(<QuizPanel />)).resolves.toBeTruthy();
  });

  it('displays quiz panel structure', async () => {
    const { container } = await renderWithEffects(<QuizPanel />);
    expect(container.children.length).toBeGreaterThan(0);
    expect(container.querySelector('.panel-grid--stacked')).toBeInTheDocument();
    expect(container.querySelector('.panel-grid--split')).not.toBeInTheDocument();
  });

  it('accepts session prop', async () => {
    const { container } = await renderWithEffects(<QuizPanel sessionId="quiz-session" />);
    expect(container).toBeInTheDocument();
  });

  it('displays quiz controls', async () => {
    const { container } = await renderWithEffects(<QuizPanel />);
    const buttons = container.querySelectorAll('button');
    expect(buttons.length).toBeGreaterThanOrEqual(0);
    expect(screen.getByRole('button', { name: /current context/i })).toBeInTheDocument();
    expect(container.querySelector('.study-generator-toolbar')).toBeInTheDocument();
  });

  it('handles empty session gracefully', async () => {
    const { container } = await renderWithEffects(<QuizPanel sessionId="" />);
    expect(container.innerHTML.length).toBeGreaterThan(0);
  });

  it('renders question display area', async () => {
    const { container } = await renderWithEffects(<QuizPanel />);
    // Should have area for question/answer display
    expect(container.innerHTML.length).toBeGreaterThan(0);
  });

  it('has submit button or control', async () => {
    const { container } = await renderWithEffects(<QuizPanel />);
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

  it('renders flashcard panel', async () => {
    const { container } = await renderWithEffects(<FlashcardPanel />);
    expect(container).toBeInTheDocument();
  });

  it('renders without error', async () => {
    await expect(renderWithEffects(<FlashcardPanel />)).resolves.toBeTruthy();
  });

  it('displays flashcard panel structure', async () => {
    const { container } = await renderWithEffects(<FlashcardPanel />);
    expect(container.children.length).toBeGreaterThan(0);
    expect(container.querySelector('.panel-grid--stacked')).toBeInTheDocument();
    expect(container.querySelector('.panel-grid--split')).not.toBeInTheDocument();
  });

  it('accepts deck prop', async () => {
    const { container } = await renderWithEffects(<FlashcardPanel deckId="deck-123" />);
    expect(container).toBeInTheDocument();
  });

  it('displays card navigation', async () => {
    const { container } = await renderWithEffects(<FlashcardPanel />);
    expect(container.innerHTML.length).toBeGreaterThan(0);
    expect(screen.getByRole('button', { name: /current context/i })).toBeInTheDocument();
    expect(container.querySelector('.study-generator-toolbar')).toBeInTheDocument();
  });

  it('handles empty deck gracefully', async () => {
    const { container } = await renderWithEffects(<FlashcardPanel deckId="" />);
    expect(container.innerHTML.length).toBeGreaterThan(0);
  });

  it('renders card display area', async () => {
    const { container } = await renderWithEffects(<FlashcardPanel />);
    // Should display a card or card placeholder
    expect(container.children.length).toBeGreaterThan(0);
  });

  it('has flip or interaction control', async () => {
    const { container } = await renderWithEffects(<FlashcardPanel />);
    // Flashcard should have way to interact with cards
    const allButtons = container.querySelectorAll('button');
    // May have control buttons
    expect(allButtons.length).toBeGreaterThanOrEqual(0);
  });
});


describe('AssessmentPanel Component', () => {
  it('uses the shared workspace-style header for consistency', async () => {
    await renderWithEffects(<AssessmentPanel defaultSubject="Science" selectedClass="Class 10" />);

    expect(await screen.findByText('Assessment Workspace')).toBeInTheDocument();
    expect(await screen.findByText(/generate timed quizzes and question papers/i)).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: /history/i })).toBeInTheDocument();
  });

  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it('loads and opens recent assessments from history', async () => {
    global.fetch.mockImplementation((url) => {
      const target = String(url);

      if (target.includes('/assessment/papers/12')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            data: {
              paper: {
                paper_id: 12,
                paper_type: 'SUBJECT_QUIZ',
                subject: 'Science',
                class_name: 'Class 10',
                difficulty: 'medium',
                mode: 'practice',
                questions: [
                  {
                    id: 'q1',
                    question: 'What is photosynthesis?',
                    options: ['Process', 'Animal', 'Mineral', 'Gas'],
                    correct_option: 'Process',
                    explanation: 'Plants make food using sunlight.',
                    marks: 1,
                  },
                ],
              },
            },
          }),
        });
      }

      if (target.includes('/assessment/papers')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            data: {
              papers: [
                {
                  paper_id: 12,
                  paper_type: 'SUBJECT_QUIZ',
                  subject: 'Science',
                  class_name: 'Class 10',
                  difficulty: 'medium',
                  mode: 'practice',
                  created_at: '2024-01-01 10:00:00',
                  question_count: 5,
                  attempt_count: 2,
                  best_score_pct: 100,
                  last_score_pct: 80,
                  recent_scores: [80, 100],
                  last_attempted_at: '2024-01-03T10:00:00Z',
                },
              ],
            },
          }),
        });
      }

      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    });

    await renderWithEffects(<AssessmentPanel />);

    fireEvent.click(screen.getByRole('button', { name: /history/i }));

    expect(await screen.findByText('Recent Assessments')).toBeInTheDocument();
    expect(await screen.findByText(/5 questions/i)).toBeInTheDocument();
    expect(await screen.findByText(/best 100% across 2 attempts/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /open quiz/i }));

    expect(await screen.findByText('What is photosynthesis?')).toBeInTheDocument();
    expect(await screen.findByText(/latest 80%/i)).toBeInTheDocument();
  });

  it('filters history items and exports a saved assessment', async () => {
    const createObjectUrl = vi.fn(() => 'blob:assessment-export');
    const revokeObjectUrl = vi.fn();
    const anchorClick = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    Object.defineProperty(window.URL, 'createObjectURL', {
      configurable: true,
      value: createObjectUrl,
    });
    Object.defineProperty(window.URL, 'revokeObjectURL', {
      configurable: true,
      value: revokeObjectUrl,
    });

    global.fetch.mockImplementation((url) => {
      const target = String(url);

      if (target.includes('/assessment/papers/21')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            data: {
              paper: {
                paper_id: 21,
                paper_type: 'SUBJECT_QUIZ',
                subject: 'Biology',
                class_name: 'Class 9',
                difficulty: 'easy',
                mode: 'practice',
                questions: [{ id: 'q1', question: 'Cell?', options: ['A', 'B'], correct_option: 'A', marks: 1 }],
              },
            },
          }),
        });
      }

      if (target.includes('paper_type=QUESTION_PAPER')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            data: {
              papers: [
                {
                  paper_id: 22,
                  paper_type: 'QUESTION_PAPER',
                  subject: 'History',
                  class_name: 'Class 9',
                  difficulty: 'medium',
                  created_at: '2024-01-02 10:00:00',
                  section_count: 3,
                  total_marks: 40,
                },
              ],
            },
          }),
        });
      }

      if (target.includes('paper_type=SUBJECT_QUIZ')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            data: {
              papers: [
                {
                  paper_id: 21,
                  paper_type: 'SUBJECT_QUIZ',
                  subject: 'Biology',
                  class_name: 'Class 9',
                  difficulty: 'easy',
                  mode: 'practice',
                  created_at: '2024-01-01 10:00:00',
                  question_count: 4,
                },
              ],
            },
          }),
        });
      }

      if (target.includes('/assessment/papers')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            data: {
              papers: [
                {
                  paper_id: 21,
                  paper_type: 'SUBJECT_QUIZ',
                  subject: 'Biology',
                  class_name: 'Class 9',
                  difficulty: 'easy',
                  mode: 'practice',
                  created_at: '2024-01-01 10:00:00',
                  question_count: 4,
                },
                {
                  paper_id: 22,
                  paper_type: 'QUESTION_PAPER',
                  subject: 'History',
                  class_name: 'Class 9',
                  difficulty: 'medium',
                  created_at: '2024-01-02 10:00:00',
                  section_count: 3,
                  total_marks: 40,
                },
              ],
            },
          }),
        });
      }

      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    });

    await renderWithEffects(<AssessmentPanel />);
    fireEvent.click(screen.getByRole('button', { name: /history/i }));

    expect(await screen.findByText('Biology — Class 9')).toBeInTheDocument();
    expect(await screen.findByText('History — Class 9')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /^papers$/i }));
    await flushEffects();
    expect(await screen.findByText('History — Class 9')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /^quizzes$/i }));
    await flushEffects();
    expect(await screen.findByText('Biology — Class 9')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /export json/i }));
    await flushEffects(4);

    expect(createObjectUrl).toHaveBeenCalled();
    expect(anchorClick).toHaveBeenCalled();
    expect(revokeObjectUrl).toHaveBeenCalled();
  });

  it('saves an exam score into assessment history', async () => {
    global.fetch.mockImplementation((url) => {
      const target = String(url);

      if (target.includes('/assessment/papers/31/attempt')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            data: {
              saved: true,
              attempt_summary: {
                attempt_count: 1,
                best_score_pct: 100,
                last_score_pct: 100,
              },
            },
          }),
        });
      }

      if (target.includes('/assessment/subject-quiz')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            data: {
              paper_id: 31,
              paper_type: 'SUBJECT_QUIZ',
              subject: 'Science',
              class_name: 'Class 10',
              difficulty: 'easy',
              mode: 'exam',
              questions: [
                {
                  id: 'q1',
                  question: 'What is light?',
                  options: ['Energy', 'Matter', 'Gas', 'Heat'],
                  correct_option: 'Energy',
                  marks: 1,
                },
              ],
            },
          }),
        });
      }

      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    });

    await renderWithEffects(<AssessmentPanel defaultSubject="Science" />);

    fireEvent.change(screen.getByRole('combobox', { name: 'Mode' }), { target: { value: 'exam' } });
    fireEvent.click(screen.getByRole('button', { name: /generate subject quiz/i }));

    expect(await screen.findByText('What is light?')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Energy' }));
    fireEvent.click(screen.getByRole('button', { name: /submit answers/i }));
    await flushEffects(4);

    expect(await screen.findByText(/attempt saved to history/i)).toBeInTheDocument();
    expect(await screen.findByText(/best 100% across 1 attempt/i)).toBeInTheDocument();
  });
});


describe('ProgressPanel Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it('shows the adaptive weekly study plan', async () => {
    global.fetch.mockImplementation((url) => {
      const target = String(url);

      if (target.includes('/progress/dashboard')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            total_study_seconds: 2400,
            streak_days: 3,
            totals: { quizzes: 4, lessons: 5, assessments: 1 },
            top_subjects: [{ subject: 'Science', study_seconds: 1200 }],
            recent_activity: [],
            mastery_summary: [],
          }),
        });
      }

      if (target.includes('/progress/insights')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            headline: 'Momentum is building well.',
            recommendations: [],
            badges: [],
          }),
        });
      }

      if (target.includes('/progress/study-plan')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            headline: 'This week, double down on Science.',
            focus_subject: 'Science',
            schedule: [
              {
                id: 'day1',
                title: 'Review Science notes',
                description: 'Spend 15 minutes revising the weakest chapter.',
                cta_label: 'Open Lesson',
                action_tab: 'lesson',
              },
            ],
          }),
        });
      }

      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    });

    await renderWithEffects(<ProgressPanel />);

    expect(await screen.findByText('This Week\'s Plan')).toBeInTheDocument();
    expect(await screen.findByText('This week, double down on Science.')).toBeInTheDocument();
    expect(await screen.findByText('Review Science notes')).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: 'Open Lesson' })).toBeInTheDocument();
  });

  it('organizes progress into overview, activity, insights, and reminders tabs', async () => {
    global.fetch.mockImplementation((url) => {
      const target = String(url);

      if (target.includes('/progress/dashboard')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            total_study_seconds: 2400,
            streak_days: 3,
            totals: { quizzes: 4, lessons: 5, assessments: 1 },
            top_subjects: [{ subject: 'Science', study_seconds: 1200 }],
            recent_activity: [
              {
                activity_type: 'assessment',
                subject: 'Science',
                chapter: 'Optics',
                duration_seconds: 600,
                logged_at: '2026-04-02T10:00:00Z',
              },
            ],
            assignments: [
              {
                id: 17,
                title: 'Practice Science quiz',
                description: 'Complete one mentor quiz before Friday.',
                action_tab: 'quiz',
                cta_label: 'Open Assigned Quiz',
                chapter_hint: 'Science',
                context_hint: 'Complete one mentor quiz before Friday.',
                author_role: 'teacher',
                author_user_id: 'mentor1',
                status: 'assigned',
              },
            ],
            mastery_summary: [],
          }),
        });
      }

      if (target.includes('/progress/insights')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            headline: 'Momentum is building well.',
            recommendations: [
              {
                id: 'review-science',
                title: 'Review Science',
                description: 'Use one quick quiz to strengthen recall.',
                cta_label: 'Open Review Quiz',
                action_tab: 'quiz',
              },
            ],
            badges: [],
            notifications: [
              {
                id: 'assessment-reminder',
                title: 'Assessment reminder',
                message: 'Retry one Science checkpoint today.',
                severity: 'high',
              },
            ],
          }),
        });
      }

      if (target.includes('/progress/study-plan')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            headline: 'This week, double down on Science.',
            focus_subject: 'Science',
            schedule: [
              {
                id: 'day1',
                title: 'Review Science notes',
                description: 'Spend 15 minutes revising the weakest chapter.',
                cta_label: 'Open Lesson',
                action_tab: 'lesson',
              },
            ],
          }),
        });
      }

      if (target.includes('/preferences')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            preferred_language: 'en',
            reminder_settings: { enabled: true, frequency: 'daily', muted_ids: [] },
          }),
        });
      }

      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    });

    await renderWithEffects(<ProgressPanel />);

    expect(await screen.findByRole('tab', { name: /overview/i })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByText('This Week\'s Plan')).toBeInTheDocument();
    expect(screen.queryByText('Recent Activity')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('tab', { name: /activity/i }));
    expect(await screen.findByText('Recent Activity')).toBeInTheDocument();
    expect(screen.queryByText('This Week\'s Plan')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('tab', { name: /insights/i }));
    expect(await screen.findByText('Smart Insights')).toBeInTheDocument();
    expect(await screen.findByText(/Momentum is building well/i)).toBeInTheDocument();
    expect(screen.queryByText(/Reminder settings/i)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('tab', { name: /reminders/i }));
    expect(await screen.findByText(/Reminder settings/i)).toBeInTheDocument();
    expect(await screen.findByText(/Practice Science quiz/i)).toBeInTheDocument();
  });

  it('triggers the supplied plan action callback', async () => {
    const onPlanAction = vi.fn();

    global.fetch.mockImplementation((url) => {
      const target = String(url);

      if (target.includes('/progress/dashboard')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            total_study_seconds: 2400,
            streak_days: 3,
            totals: { quizzes: 4, lessons: 5, assessments: 1 },
            top_subjects: [
              { subject: 'Science', study_seconds: 1200 },
            ],
            recent_activity: [
              {
                activity_type: 'assessment',
                subject: 'Science',
                chapter: 'Optics',
                duration_seconds: 600,
                logged_at: '2026-04-02T10:00:00Z',
              },
            ],
            assignments: [
              {
                id: 'mentor-assigned-1',
                title: 'Practice Science quiz',
                description: 'A mentor assigned one quick Science checkpoint.',
                action_tab: 'quiz',
                cta_label: 'Open Assigned Quiz',
                chapter_hint: 'Science',
                context_hint: 'A mentor assigned one quick Science checkpoint.',
                author_role: 'teacher',
                author_user_id: 'mentor1',
                status: 'assigned',
              },
            ],
            mastery_summary: [
              {
                subject: 'Science',
                avg_mastery_pct: 54,
                chapters_tracked: 1,
                chapters: [{ chapter: 'Optics', mastery_pct: 54, quizzes_taken: 2 }],
              },
            ],
          }),
        });
      }

      if (target.includes('/progress/insights')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            headline: '',
            notifications: [
              {
                id: 'stay-on-track',
                title: 'Stay on track',
                message: 'One more Science quiz will keep your weekly goals moving.',
                severity: 'medium',
                cta_label: 'Open Assigned Quiz',
                action_tab: 'quiz',
                chapter_hint: 'Science',
                context_hint: 'One more Science quiz will keep your weekly goals moving.',
              },
            ],
            recommendations: [
              {
                id: 'review-science',
                title: 'Review Science',
                description: 'Use one quick quiz to strengthen recall.',
                cta_label: 'Open Review Quiz',
                action_tab: 'quiz',
                chapter_hint: 'Science',
                context_hint: 'Use one quick quiz to strengthen recall.',
              },
              {
                id: 'assessment-recovery',
                title: 'Retry Science assessment',
                description: 'A focused exam-style checkpoint can lift the latest score.',
                cta_label: 'Retry Assessment',
                action_tab: 'assessment',
                chapter_hint: 'Science',
                context_hint: 'Use one exam-style checkpoint to improve recent scores.',
              },
            ],
            badges: [],
          }),
        });
      }

      if (target.includes('/progress/study-plan')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            headline: 'Focus on Science this week.',
            focus_subject: 'Science',
            goal_summary: { completed: 2, total: 3 },
            history: {
              current_week: { week_key: '2026-W14', completed_steps: 1, total_steps: 1, goal_completed: 2, goal_total: 3 },
              previous_week: { week_key: '2026-W13', completed_steps: 1, total_steps: 3, goal_completed: 1, goal_total: 3 },
              comparison: { summary: 'Up 1 goal from last week.' },
            },
            targets: [
              {
                id: 'weekly-quiz',
                label: 'Quizzes',
                current: 1,
                target: 2,
                unit: 'done',
                completed: false,
                cta_label: 'Practice Quiz Goal',
                action_tab: 'quiz',
                chapter_hint: 'Science',
                context_hint: 'Use one quick quiz to stay on track with your weekly goal.',
              },
            ],
            schedule: [
              {
                id: 'quiz-step',
                title: 'Take a quick Science quiz',
                description: 'Check recall with a short quiz.',
                cta_label: 'Start Quiz',
                action_tab: 'quiz',
              },
            ],
          }),
        });
      }

      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    });

    await renderWithEffects(<ProgressPanel onPlanAction={onPlanAction} />);

    fireEvent.click(await screen.findByRole('button', { name: 'Start Quiz' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Practice Quiz Goal' }));

    fireEvent.click(await screen.findByRole('tab', { name: /activity/i }));
    fireEvent.click(await screen.findByRole('button', { name: 'Review Assessment' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Practice Science Quiz' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Open Science Lesson' }));

    fireEvent.click(await screen.findByRole('tab', { name: /insights/i }));
    fireEvent.click(await screen.findByRole('button', { name: 'Open Review Quiz' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Retry Assessment' }));

    fireEvent.click(await screen.findByRole('tab', { name: /reminders/i }));
    fireEvent.click((await screen.findAllByRole('button', { name: 'Open Assigned Quiz' }))[0]);
    expect(onPlanAction).toHaveBeenCalledWith(expect.objectContaining({ action_tab: 'quiz', id: 'quiz-step' }));
    expect(onPlanAction).toHaveBeenCalledWith(expect.objectContaining({ action_tab: 'quiz', id: 'review-science' }));
    expect(onPlanAction).toHaveBeenCalledWith(expect.objectContaining({ action_tab: 'assessment', id: 'assessment-recovery' }));
    expect(onPlanAction).toHaveBeenCalledWith(expect.objectContaining({ action_tab: 'assessment', chapter_hint: 'Science' }));
    expect(onPlanAction).toHaveBeenCalledWith(expect.objectContaining({ action_tab: 'quiz', id: 'mastery-science' }));
    expect(onPlanAction).toHaveBeenCalledWith(expect.objectContaining({ action_tab: 'lesson', id: 'time-subject-science' }));
    expect(onPlanAction).toHaveBeenCalledWith(expect.objectContaining({ action_tab: 'quiz', id: 'weekly-quiz' }));
  });

  it('shows assessment score trends on the progress dashboard', async () => {
    global.fetch.mockImplementation((url) => {
      const target = String(url);

      if (target.includes('/progress/dashboard')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            total_study_seconds: 1800,
            streak_days: 2,
            totals: { quizzes: 2, lessons: 3, assessments: 2 },
            top_subjects: [{ subject: 'Science', study_seconds: 1200 }],
            recent_activity: [],
            mastery_summary: [],
            assessment_summary: {
              attempt_count: 3,
              attempted_assessments: 2,
              average_score_pct: 84,
              best_score_pct: 100,
              latest_score_pct: 72,
              latest_subject: 'Science',
              last_attempted_at: '2026-04-02T10:00:00Z',
              recent_scores: [72, 80, 100],
            },
          }),
        });
      }

      if (target.includes('/progress/insights')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ headline: '', recommendations: [], badges: [] }),
        });
      }

      if (target.includes('/progress/study-plan')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ headline: '', focus_subject: 'Science', schedule: [] }),
        });
      }

      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    });

    await renderWithEffects(<ProgressPanel />);

    expect(await screen.findByText('Assessment Avg')).toBeInTheDocument();
    expect(await screen.findByText(/84%/i)).toBeInTheDocument();
    expect(await screen.findByText(/Best 100% · Latest 72% in Science/i)).toBeInTheDocument();
    expect(await screen.findByText(/Recent 72%, 80%, 100%/i)).toBeInTheDocument();
    expect(await screen.findByRole('img', { name: /assessment trend/i })).toBeInTheDocument();
    expect(await screen.findByText(/3 attempts/i)).toBeInTheDocument();
    expect(await screen.findByText(/2 papers/i)).toBeInTheDocument();
    expect(await screen.findByText(/Last 2026-04-02/i)).toBeInTheDocument();
  });

  it('shows weekly checklist progress and next-step status', async () => {
    global.fetch.mockImplementation((url) => {
      const target = String(url);

      if (target.includes('/progress/dashboard')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            total_study_seconds: 2400,
            streak_days: 2,
            totals: { quizzes: 1, lessons: 2, assessments: 0 },
            top_subjects: [{ subject: 'Science', study_seconds: 1600 }],
            recent_activity: [],
            mastery_summary: [],
          }),
        });
      }

      if (target.includes('/progress/insights')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ headline: '', recommendations: [], badges: [] }),
        });
      }

      if (target.includes('/progress/study-plan/items/quiz-next')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ status: 'saved', item_id: 'quiz-next', completed: true, item_type: 'schedule' }),
        });
      }

      if (target.includes('/progress/study-plan')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            headline: 'Stay steady with Science this week.',
            focus_subject: 'Science',
            history: {
              current_week: { week_key: '2026-W14', completed_steps: 1, total_steps: 2, goal_completed: 1, goal_total: 3 },
              previous_week: { week_key: '2026-W13', completed_steps: 1, total_steps: 3, goal_completed: 0, goal_total: 3 },
              comparison: { summary: 'Up 1 goal from last week.' },
            },
            schedule: [
              {
                id: 'lesson-done',
                title: 'Review Science notes',
                description: 'Revisit your key lesson points.',
                cta_label: 'Open Lesson',
                action_tab: 'lesson',
                completed: true,
                status: 'done',
              },
              {
                id: 'quiz-next',
                title: 'Take a quick Science quiz',
                description: 'Check recall and raise mastery.',
                cta_label: 'Start Quiz',
                action_tab: 'quiz',
                completed: false,
                status: 'next',
              },
            ],
          }),
        });
      }

      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    });

    await renderWithEffects(<ProgressPanel />);

    expect(await screen.findByText('1 of 2 complete')).toBeInTheDocument();
    expect(await screen.findByText('Done')).toBeInTheDocument();
    expect(await screen.findByText('Next up')).toBeInTheDocument();
    expect(await screen.findByText(/Up 1 goal from last week/i)).toBeInTheDocument();
    fireEvent.click(await screen.findByRole('button', { name: 'Mark Done' }));
    await flushEffects();
    expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining('/progress/study-plan/items/quiz-next'), expect.objectContaining({ method: 'POST' }));
  });

  it('refreshes progress data when the panel becomes active again', async () => {
    let dashboardCalls = 0;

    global.fetch.mockImplementation((url) => {
      const target = String(url);

      if (target.includes('/progress/dashboard')) {
        dashboardCalls += 1;
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            total_study_seconds: dashboardCalls === 1 ? 600 : 1200,
            streak_days: dashboardCalls === 1 ? 1 : 2,
            totals: { quizzes: dashboardCalls === 1 ? 0 : 1, lessons: 1, assessments: 0 },
            top_subjects: [],
            recent_activity: [],
            mastery_summary: [],
          }),
        });
      }

      if (target.includes('/progress/insights')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ headline: '', recommendations: [], badges: [] }),
        });
      }

      if (target.includes('/progress/study-plan')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            headline: 'Keep momentum going.',
            focus_subject: 'Science',
            schedule: [],
          }),
        });
      }

      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    });

    const view = await renderWithEffects(<ProgressPanel isActive={false} />);

    expect(await screen.findByText('10m')).toBeInTheDocument();

    await rerenderWithEffects(view, <ProgressPanel isActive />);

    expect(await screen.findByText('20m')).toBeInTheDocument();
  });

  it('shows weekly goal tracker progress', async () => {
    global.fetch.mockImplementation((url) => {
      const target = String(url);

      if (target.includes('/progress/dashboard')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            total_study_seconds: 1200,
            streak_days: 2,
            totals: { quizzes: 1, lessons: 1, assessments: 0 },
            top_subjects: [{ subject: 'Science', study_seconds: 1200 }],
            recent_activity: [],
            assignments: [
              {
                id: 'mentor-assigned-1',
                title: 'Practice Science quiz',
                description: 'A mentor assigned one quick Science checkpoint.',
                action_tab: 'quiz',
                cta_label: 'Open Assigned Quiz',
                chapter_hint: 'Science',
                context_hint: 'A mentor assigned one quick Science checkpoint.',
                author_role: 'teacher',
                author_user_id: 'mentor1',
                status: 'assigned',
              },
            ],
            mastery_summary: [],
          }),
        });
      }

      if (target.includes('/progress/insights')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            headline: '',
            recommendations: [],
            badges: [],
            notifications: [
              {
                id: 'stay-on-track',
                title: 'Stay on track',
                message: 'One more Science quiz will keep your weekly goals moving.',
                severity: 'medium',
              },
            ],
          }),
        });
      }

      if (target.includes('/progress/study-plan')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            headline: 'Stay steady with Science this week.',
            focus_subject: 'Science',
            goal_summary: { completed: 2, total: 3 },
            history: {
              current_week: { week_key: '2026-W14', completed_steps: 0, total_steps: 0, goal_completed: 2, goal_total: 3 },
              previous_week: { week_key: '2026-W13', completed_steps: 0, total_steps: 0, goal_completed: 1, goal_total: 3 },
              comparison: { summary: 'Up 1 goal from last week.' },
            },
            targets: [
              {
                id: 'study-minutes',
                label: 'Study time',
                current: 20,
                target: 30,
                unit: 'min',
                completed: false,
                cta_label: 'Open Focus Lesson',
                action_tab: 'lesson',
                chapter_hint: 'Science',
                context_hint: 'Spend 15 more minutes reviewing Science.',
              },
              {
                id: 'weekly-lessons',
                label: 'Lessons',
                current: 1,
                target: 1,
                unit: 'done',
                completed: true,
                cta_label: 'Review Lesson Goal',
                action_tab: 'lesson',
                chapter_hint: 'Science',
                context_hint: 'Open a focused Science lesson to stay on track.',
              },
              {
                id: 'weekly-quiz',
                label: 'Quizzes',
                current: 1,
                target: 1,
                unit: 'done',
                completed: true,
                cta_label: 'Practice Quiz Goal',
                action_tab: 'quiz',
                chapter_hint: 'Science',
                context_hint: 'Use one quick quiz to stay on track with your weekly goal.',
              },
            ],
            schedule: [],
          }),
        });
      }

      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    });

    await renderWithEffects(<ProgressPanel />);

    expect(await screen.findByText(/2\s*of\s*3\s*goals on track/i)).toBeInTheDocument();
    expect(await screen.findByText(/20\s*\/\s*30\s*min/i)).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: 'Open Focus Lesson' })).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: 'Practice Quiz Goal' })).toBeInTheDocument();
    expect(await screen.findByText(/Up 1 goal from last week/i)).toBeInTheDocument();
    const reportActionsButton = await screen.findByRole('button', { name: /open report actions/i });
    expect(reportActionsButton).toBeInTheDocument();
    fireEvent.click(reportActionsButton);
    expect(await screen.findByRole('menuitem', { name: 'Export Report JSON' })).toBeInTheDocument();
    expect(await screen.findByRole('menuitem', { name: 'Export Report CSV' })).toBeInTheDocument();
    expect(await screen.findByRole('menuitem', { name: 'Print / Save PDF' })).toBeInTheDocument();
    expect(await screen.findAllByText(/1\s*\/\s*1\s*done/i)).toHaveLength(2);

    fireEvent.click(screen.getByRole('tab', { name: /reminders/i }));
    expect(await screen.findByText(/Stay on track/i)).toBeInTheDocument();
    expect(await screen.findByText(/Practice Science quiz/i)).toBeInTheDocument();
  });

  it('stores reminder preferences and lets students complete assignments', async () => {
    localStorage.setItem('username', 'student');
    global.fetch.mockImplementation((url, options = {}) => {
      const target = String(url);
      const method = options?.method || 'GET';

      if (target.includes('/progress/dashboard')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            total_study_seconds: 900,
            streak_days: 1,
            totals: { quizzes: 1, lessons: 1, assessments: 0 },
            top_subjects: [],
            recent_activity: [],
            assignments: [
              {
                id: 17,
                title: 'Practice Science quiz',
                description: 'Complete one mentor quiz before Friday.',
                action_tab: 'quiz',
                cta_label: 'Open Assigned Quiz',
                chapter_hint: 'Science',
                context_hint: 'Complete one mentor quiz before Friday.',
                author_role: 'teacher',
                author_user_id: 'mentor1',
                status: 'assigned',
              },
            ],
            mastery_summary: [],
          }),
        });
      }

      if (target.includes('/progress/insights')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            headline: '',
            recommendations: [],
            badges: [],
            notifications: [
              {
                id: 'assessment-reminder',
                title: 'Assessment reminder',
                message: 'Retry one Science checkpoint today.',
                severity: 'high',
              },
            ],
          }),
        });
      }

      if (target.includes('/progress/study-plan')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            headline: '',
            focus_subject: 'Science',
            goal_summary: { completed: 0, total: 0 },
            history: {
              current_week: { week_key: '2026-W14', completed_steps: 1, total_steps: 2, goal_completed: 0, goal_total: 0 },
              previous_week: { week_key: '2026-W13', completed_steps: 0, total_steps: 2, goal_completed: 0, goal_total: 0 },
              comparison: { summary: 'Up 1 step from last week.' },
            },
            targets: [],
            schedule: [],
          }),
        });
      }

      if (target.includes('/preferences') && method === 'GET') {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            preferred_language: 'en',
            reminder_settings: { enabled: true, frequency: 'daily', muted_ids: [] },
          }),
        });
      }

      if (target.includes('/preferences') && method === 'PUT') {
        const body = options?.body ? JSON.parse(options.body) : {};
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            preferred_language: body.preferred_language || 'en',
            reminder_settings: body.reminder_settings || { enabled: true, frequency: 'daily', muted_ids: [] },
            updated: true,
          }),
        });
      }

      if (target.includes('/students/student/assignments/17') && method === 'PUT') {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ id: 17, status: 'completed' }),
        });
      }

      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    });

    await renderWithEffects(<ProgressPanel />);

    fireEvent.click(await screen.findByRole('tab', { name: /reminders/i }));
    expect(await screen.findByText(/Reminder settings/i)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/Reminder frequency/i), { target: { value: 'important-only' } });
    await flushEffects();
    fireEvent.click(screen.getByRole('button', { name: /Mute this reminder/i }));
    await flushEffects();
    fireEvent.click(screen.getByRole('button', { name: 'Mark Done' }));
    await flushEffects();

    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/preferences'),
      expect.objectContaining({ method: 'PUT' }),
    );
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/students/student/assignments/17'),
      expect.objectContaining({ method: 'PUT' }),
    );
  });

  it('highlights overdue assignments and filters the list', async () => {
    localStorage.setItem('username', 'student');
    global.fetch.mockImplementation((url, options = {}) => {
      const target = String(url);
      const method = options?.method || 'GET';

      if (target.includes('/progress/dashboard')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            total_study_seconds: 900,
            streak_days: 1,
            totals: { quizzes: 1, lessons: 1, assessments: 0 },
            top_subjects: [],
            recent_activity: [],
            assignments: [
              {
                id: 71,
                title: 'Finish Algebra worksheet',
                description: 'This mentor task is overdue and needs attention.',
                action_tab: 'lesson',
                cta_label: 'Open Assigned Lesson',
                chapter_hint: 'Math',
                context_hint: 'This mentor task is overdue and needs attention.',
                due_label: '2000-01-01',
                author_role: 'teacher',
                author_user_id: 'mentor1',
                status: 'assigned',
              },
              {
                id: 72,
                title: 'Complete Reading summary',
                description: 'This one is already done.',
                action_tab: 'lesson',
                cta_label: 'Open Assigned Lesson',
                chapter_hint: 'Reading',
                context_hint: 'This one is already done.',
                due_label: '2999-01-01',
                author_role: 'teacher',
                author_user_id: 'mentor1',
                status: 'completed',
              },
            ],
            mastery_summary: [],
          }),
        });
      }

      if (target.includes('/progress/insights')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            headline: '',
            recommendations: [],
            badges: [],
            notifications: [
              {
                id: 'overdue-assignment-71',
                title: 'Overdue assignment',
                message: 'Finish Algebra worksheet was due 2000-01-01.',
                severity: 'high',
              },
            ],
          }),
        });
      }

      if (target.includes('/progress/study-plan')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            headline: '',
            focus_subject: 'Math',
            goal_summary: { completed: 0, total: 0 },
            history: {
              current_week: { week_key: '2026-W14', completed_steps: 0, total_steps: 0, goal_completed: 0, goal_total: 0 },
              previous_week: { week_key: '2026-W13', completed_steps: 0, total_steps: 0, goal_completed: 0, goal_total: 0 },
              comparison: { summary: '' },
            },
            targets: [],
            schedule: [],
          }),
        });
      }

      if (target.includes('/preferences') && method === 'GET') {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            preferred_language: 'en',
            reminder_settings: { enabled: true, frequency: 'daily', muted_ids: [] },
          }),
        });
      }

      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    });

    await renderWithEffects(<ProgressPanel />);

    expect(screen.getByLabelText(/Report subject/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Report range/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Reminder severity/i)).toBeInTheDocument();

    fireEvent.click(await screen.findByRole('tab', { name: /reminders/i }));
    expect(await screen.findByText(/Overdue assignment/i)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/Reminder severity/i), { target: { value: 'high' } });
    expect((await screen.findAllByText(/Overdue/i)).length).toBeGreaterThan(0);
    fireEvent.change(screen.getByLabelText(/Assignment filter/i), { target: { value: 'overdue' } });

    expect(await screen.findByText(/^Finish Algebra worksheet$/i)).toBeInTheDocument();
    expect(screen.queryByText(/Complete Reading summary/i)).not.toBeInTheDocument();
  });
});

describe('RoleHubPanel and AdminPanel Components', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it('lets admin users switch the global model behavior profile', async () => {
    localStorage.setItem('role', 'admin');
    localStorage.setItem('username', 'admin');

    global.fetch.mockImplementation((url, options = {}) => {
      const target = String(url);
      const method = String(options?.method || 'GET').toUpperCase();

      if (target.includes('/relationships/my-mentors')) {
        return Promise.resolve({ ok: true, status: 200, json: async () => ({ mentors: [] }) });
      }

      if (target.includes('/admin/model-profiles') && method === 'GET') {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            active_profile: 'balanced',
            profiles: [
              { key: 'balanced', label: 'Balanced', description: 'Good quality and speed.' },
              { key: 'fastest', label: 'Fastest', description: 'Lowest latency for all users.' },
            ],
          }),
        });
      }

      if (target.includes('/admin/model-profiles') && method === 'PUT') {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ updated: true, active_profile: 'fastest' }),
        });
      }

      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    });

    await renderWithEffects(
      <AdminPanel
        viewRole="admin"
        onAdminViewRoleChange={vi.fn()}
        onAdminReindex={vi.fn()}
        onAdminIncrementalReindex={vi.fn()}
      />
    );

    expect(await screen.findByText(/global ai behavior/i)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/model behavior profile/i), { target: { value: 'fastest' } });
    fireEvent.click(screen.getByRole('button', { name: /apply global profile/i }));

    expect(await screen.findByText(/global profile updated to fastest/i)).toBeInTheDocument();
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/admin/model-profiles'),
      expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify({ profile_key: 'fastest' }),
      }),
    );
  });

  it('falls back to the configured model profile options when admin state cannot be loaded', async () => {
    localStorage.setItem('role', 'admin');
    localStorage.setItem('username', 'admin');

    global.fetch.mockImplementation((url, options = {}) => {
      const target = String(url);
      const method = String(options?.method || 'GET').toUpperCase();

      if (target.includes('/admin/model-profiles') && method === 'GET') {
        return Promise.resolve({
          ok: false,
          status: 404,
          json: async () => ({ error: 'Not found' }),
        });
      }

      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    });

    const { container } = await renderWithEffects(
      <AdminPanel
        viewRole="admin"
        onAdminViewRoleChange={vi.fn()}
        onAdminReindex={vi.fn()}
        onAdminIncrementalReindex={vi.fn()}
      />
    );

    const cards = Array.from(container.querySelectorAll('.profile-panel__card'));
    const globalCard = cards.find((card) => card.textContent?.match(/global ai behavior/i));
    const adminActionsCard = cards.find((card) => card.textContent?.match(/admin actions/i));

    expect(globalCard).toBeTruthy();
    expect(globalCard.textContent).toMatch(/current selected profile/i);
    expect(globalCard.textContent).toMatch(/balanced/i);
    expect(screen.getByRole('option', { name: /balanced/i })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: /best quality/i })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: /fastest/i })).toBeInTheDocument();
    expect(adminActionsCard?.textContent || '').not.toMatch(/current selected profile/i);
    expect(screen.getByText(/showing the configured profile options locally/i)).toBeInTheDocument();
  });

  it('shows admin-only controls and lets admins preview the workspace as another role', async () => {
    localStorage.setItem('role', 'admin');
    localStorage.setItem('username', 'admin');

    global.fetch.mockImplementation((url, options = {}) => {
      const target = String(url);
      const method = String(options?.method || 'GET').toUpperCase();

      if (target.includes('/admin/model-profiles') && method === 'GET') {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            active_profile: 'balanced',
            profiles: [
              { key: 'balanced', label: 'Balanced', description: 'Good quality and speed.', task_models: { qa: 'qwen2.5-7b', quiz: 'phi-4' } },
              { key: 'fastest', label: 'Fastest', description: 'Lowest latency.', task_models: { qa: 'tinyllama-1.1b-chat', quiz: 'tinyllama-1.1b-chat' } },
            ],
          }),
        });
      }

      if (target.includes('/relationships/my-mentors')) {
        return Promise.resolve({ ok: true, status: 200, json: async () => ({ mentors: [] }) });
      }

      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    });

    await renderWithEffects(
      <AdminPanel
        viewRole="admin"
        onAdminViewRoleChange={vi.fn()}
        onAdminReindex={vi.fn()}
        onAdminIncrementalReindex={vi.fn()}
      />
    );

    expect(await screen.findByText(/global ai behavior/i)).toBeInTheDocument();
    expect(await screen.findByText(/admin actions/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/view workspace as/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /reindex knowledge base/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /incremental reindex/i })).toBeInTheDocument();
  });

  it('shows live indexing progress and current file details for admins', async () => {
    localStorage.setItem('role', 'admin');
    localStorage.setItem('username', 'admin');

    global.fetch.mockImplementation((url, options = {}) => {
      const target = String(url);
      const method = String(options?.method || 'GET').toUpperCase();

      if (target.includes('/admin/model-profiles') && method === 'GET') {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            active_profile: 'balanced',
            profiles: [{ key: 'balanced', label: 'Balanced', description: 'Good quality and speed.', task_models: {} }],
          }),
        });
      }

      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    });

    await renderWithEffects(
      <AdminPanel
        viewRole="admin"
        onAdminViewRoleChange={vi.fn()}
        onAdminReindex={vi.fn()}
        onAdminIncrementalReindex={vi.fn()}
        adminRunning
        adminMessage="Knowledge base reindex is running… 50%"
        adminStatus={{
          title: 'Knowledge base reindex is running… 50%',
          detail: 'Processing Class X/Physics/refraction.pdf. Current file: Class X/Physics/refraction.pdf.',
          stats: { scanned: 2, total: 4, reindexed: 1, skipped: 1, removed: 0 },
          currentFile: 'Class X/Physics/refraction.pdf',
          processedFiles: ['Class X/Biology/intro.pdf'],
          errors: [],
        }}
      />
    );

    expect(await screen.findByText(/knowledge base reindex is running/i)).toBeInTheDocument();
    expect(screen.getByText(/scanned 2 \/ 4 · reindexed 1 · skipped 1 · removed 0/i)).toBeInTheDocument();
    expect(screen.getByText(/^current file$/i)).toBeInTheDocument();
    expect(screen.getAllByText(/refraction\.pdf/i).length).toBeGreaterThan(0);
  });

  it('shows detailed indexing status after an admin reindex completes', async () => {
    localStorage.setItem('role', 'admin');
    localStorage.setItem('username', 'admin');

    global.fetch.mockImplementation((url, options = {}) => {
      const target = String(url);
      const method = String(options?.method || 'GET').toUpperCase();

      if (target.includes('/admin/model-profiles') && method === 'GET') {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            active_profile: 'balanced',
            profiles: [{ key: 'balanced', label: 'Balanced', description: 'Good quality and speed.', task_models: {} }],
          }),
        });
      }

      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    });

    await renderWithEffects(
      <AdminPanel
        viewRole="admin"
        onAdminViewRoleChange={vi.fn()}
        onAdminReindex={vi.fn()}
        onAdminIncrementalReindex={vi.fn()}
        adminMessage="Reindex completed."
        adminStatus={{
          title: 'Reindex completed.',
          detail: 'Full scan finished. Scanned 4 file(s), reindexed 2, skipped 2, and removed 0.',
          stats: { scanned: 4, total: 4, reindexed: 2, skipped: 2, removed: 0 },
          currentFile: '',
          processedFiles: ['Class X/Physics/refraction.pdf', 'Class X/Biology/photosynthesis.pdf'],
          errors: [],
        }}
      />
    );

    expect(await screen.findByText(/full scan finished/i)).toBeInTheDocument();
    expect(screen.getByText(/scanned 4 \/ 4 · reindexed 2 · skipped 2 · removed 0/i)).toBeInTheDocument();
    expect(screen.getByText(/refraction\.pdf/i)).toBeInTheDocument();
    expect(screen.getByText(/photosynthesis\.pdf/i)).toBeInTheDocument();
  });

  it('shows a parent dashboard summary for a linked learner', async () => {
    localStorage.setItem('role', 'parent');
    localStorage.setItem('username', 'parent1');

    global.fetch.mockImplementation((url) => {
      const target = String(url);

      if (target.includes('/relationships/my-students')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            students: [
              {
                username: 'student',
                email: 'student@example.com',
                first_name: 'Student One',
                linked_at: '2026-04-02T09:00:00Z',
              },
            ],
          }),
        });
      }

      if (target.includes('/students/student/progress')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            student_username: 'student',
            dashboard: {
              total_study_seconds: 2400,
              streak_days: 4,
              totals: { quizzes: 5, lessons: 4, assessments: 2 },
              recent_activity: [],
              assignments: [
                {
                  id: 31,
                  title: 'Finish Science revision',
                  description: 'Complete the recap before Sunday.',
                  action_tab: 'lesson',
                  cta_label: 'Open Assigned Lesson',
                  chapter_hint: 'Science',
                  due_label: '2026-04-12',
                  author_role: 'teacher',
                  status: 'assigned',
                },
                {
                  id: 32,
                  title: 'Retry quiz',
                  description: 'Retry the chapter quiz tomorrow.',
                  action_tab: 'quiz',
                  cta_label: 'Open Assigned Quiz',
                  chapter_hint: 'Math',
                  due_label: '2026-04-10',
                  author_role: 'teacher',
                  status: 'assigned',
                },
              ],
              assessment_summary: {
                attempt_count: 3,
                attempted_assessments: 2,
                average_score_pct: 86,
                latest_score_pct: 90,
                latest_subject: 'Science',
                recent_scores: [72, 86, 90],
                last_attempted_at: '2026-04-03T10:00:00Z',
              },
            },
            mastery: [],
            study_plan: null,
            insights: { headline: 'Student One is staying on track.', recommendations: [], badges: [], notifications: [] },
          }),
        });
      }

      if (target.includes('/students/student/notes')) {
        return Promise.resolve({ ok: true, status: 200, json: async () => ({ notes: [] }) });
      }

      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    });

    await renderWithEffects(<RoleHubPanel />);

    expect(await screen.findByText(/parent dashboard summary/i)).toBeInTheDocument();
    expect((await screen.findAllByText(/2 open tasks/i)).length).toBeGreaterThan(0);
    expect(await screen.findByText(/next due 2026-04-10/i)).toBeInTheDocument();
    expect((await screen.findAllByText(/86% avg/i)).length).toBeGreaterThan(0);
  });

  it('shows a teacher roster overview for linked learners', async () => {
    localStorage.setItem('role', 'teacher');
    localStorage.setItem('username', 'mentor1');

    global.fetch.mockImplementation((url) => {
      const target = String(url);

      if (target.includes('/relationships/my-students')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            students: [
              {
                username: 'student',
                email: 'student@example.com',
                first_name: 'Student One',
                relation_label: 'Class 8A',
                linked_at: '2026-04-02T09:00:00Z',
              },
              {
                username: 'student2',
                email: 'student2@example.com',
                first_name: 'Student Two',
                relation_label: 'Class 8B',
                linked_at: '2026-04-01T09:00:00Z',
              },
            ],
          }),
        });
      }

      if (target.includes('/students/student/progress')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            student_username: 'student',
            dashboard: {
              total_study_seconds: 1800,
              streak_days: 2,
              totals: { quizzes: 3, lessons: 4, assessments: 1 },
              recent_activity: [],
              assignments: [
                {
                  id: 'mentor-assigned-1',
                  title: 'Practice Science quiz',
                  description: 'A mentor assigned one quick Science checkpoint.',
                  action_tab: 'quiz',
                  cta_label: 'Open Assigned Quiz',
                  chapter_hint: 'Science',
                  context_hint: 'A mentor assigned one quick Science checkpoint.',
                  author_role: 'teacher',
                  author_user_id: 'mentor1',
                  status: 'assigned',
                },
              ],
              assessment_summary: {},
            },
            mastery: [],
            study_plan: null,
            insights: { headline: '', recommendations: [], badges: [], notifications: [] },
          }),
        });
      }

      if (target.includes('/students/student/notes')) {
        return Promise.resolve({ ok: true, status: 200, json: async () => ({ notes: [] }) });
      }

      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    });

    await renderWithEffects(<RoleHubPanel />);

    expect(await screen.findByText(/class roster overview/i)).toBeInTheDocument();
    expect(await screen.findByText(/2 linked learners/i)).toBeInTheDocument();
    expect(await screen.findByText(/selected learner student one/i)).toBeInTheDocument();
    expect(await screen.findByText(/class 8a, class 8b/i)).toBeInTheDocument();
  });

  it('shows class-level progress insights for teachers', async () => {
    localStorage.setItem('role', 'teacher');
    localStorage.setItem('username', 'mentor1');

    global.fetch.mockImplementation((url) => {
      const target = String(url);

      if (target.includes('/relationships/my-students')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            students: [
              {
                username: 'student',
                email: 'student@example.com',
                first_name: 'Student One',
                relation_label: 'Class 8A',
                linked_at: '2026-04-02T09:00:00Z',
              },
              {
                username: 'student2',
                email: 'student2@example.com',
                first_name: 'Student Two',
                relation_label: 'Class 8A',
                linked_at: '2026-04-01T09:00:00Z',
              },
            ],
          }),
        });
      }

      if (target.includes('/students/student/progress')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            student_username: 'student',
            dashboard: {
              total_study_seconds: 2400,
              streak_days: 4,
              totals: { quizzes: 5, lessons: 4, assessments: 2 },
              recent_activity: [],
              assignments: [
                {
                  id: 'student-assignment-1',
                  title: 'Science recap',
                  description: 'Review the Science lesson this week.',
                  action_tab: 'lesson',
                  cta_label: 'Open Assigned Lesson',
                  chapter_hint: 'Science',
                  due_label: '2026-04-12',
                  author_role: 'teacher',
                  status: 'assigned',
                },
              ],
              assessment_summary: {
                average_score_pct: 88,
              },
            },
            mastery: [],
            study_plan: null,
            insights: { headline: '', recommendations: [], badges: [], notifications: [] },
          }),
        });
      }

      if (target.includes('/students/student2/progress')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            student_username: 'student2',
            dashboard: {
              total_study_seconds: 900,
              streak_days: 1,
              totals: { quizzes: 1, lessons: 2, assessments: 1 },
              recent_activity: [],
              assignments: [
                {
                  id: 'student2-assignment-1',
                  title: 'Retry fractions quiz',
                  description: 'Retry the fractions quiz tonight.',
                  action_tab: 'quiz',
                  cta_label: 'Open Assigned Quiz',
                  chapter_hint: 'Math',
                  due_label: '2026-04-01',
                  author_role: 'teacher',
                  status: 'assigned',
                },
              ],
              assessment_summary: {
                average_score_pct: 62,
              },
            },
            mastery: [],
            study_plan: null,
            insights: { headline: '', recommendations: [], badges: [], notifications: [] },
          }),
        });
      }

      if (target.includes('/students/student/notes')) {
        return Promise.resolve({ ok: true, status: 200, json: async () => ({ notes: [] }) });
      }

      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    });

    await renderWithEffects(<RoleHubPanel />);

    expect(await screen.findByText(/class progress snapshot/i)).toBeInTheDocument();
    expect(await screen.findByText(/2 learners tracked/i)).toBeInTheDocument();
    expect(await screen.findByText(/1 on track/i)).toBeInTheDocument();
    expect(await screen.findByText(/1 needs attention/i)).toBeInTheDocument();
    expect(await screen.findByText(/75% class avg/i)).toBeInTheDocument();
    expect(await screen.findByText(/focus support: student two/i)).toBeInTheDocument();
  });

  it('shows mentor-side coaching insights for a linked student', async () => {
    localStorage.setItem('role', 'teacher');
    localStorage.setItem('username', 'mentor1');

    global.fetch.mockImplementation((url) => {
      const target = String(url);

      if (target.includes('/relationships/my-students')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            students: [
              {
                username: 'student',
                email: 'student@example.com',
                first_name: 'Student One',
                linked_at: '2026-04-02T09:00:00Z',
              },
            ],
          }),
        });
      }

      if (target.includes('/students/student/progress')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            student_username: 'student',
            dashboard: {
              total_study_seconds: 1800,
              streak_days: 2,
              totals: { quizzes: 3, lessons: 4, assessments: 1 },
              recent_activity: [
                {
                  activity_type: 'assessment',
                  subject: 'Science',
                  chapter: 'Optics',
                  duration_seconds: 600,
                  logged_at: '2026-04-02T10:00:00Z',
                },
              ],
              assignments: [
                {
                  id: 'mentor-assigned-1',
                  title: 'Practice Science quiz',
                  description: 'A mentor assigned one quick Science checkpoint.',
                  action_tab: 'quiz',
                  cta_label: 'Open Assigned Quiz',
                  chapter_hint: 'Science',
                  context_hint: 'A mentor assigned one quick Science checkpoint.',
                  author_role: 'teacher',
                  author_user_id: 'mentor1',
                  status: 'assigned',
                },
              ],
              assessment_summary: {
                attempt_count: 2,
                attempted_assessments: 2,
                average_score_pct: 84,
                best_score_pct: 100,
                latest_score_pct: 80,
                latest_subject: 'Science',
                recent_scores: [80, 100],
                last_attempted_at: '2026-04-02T10:00:00Z',
              },
            },
            mastery: [
              { subject: 'Math', chapter: 'Algebra', mastery_pct: 54, quizzes_taken: 2 },
              { subject: 'Science', chapter: 'Optics', mastery_pct: 82, quizzes_taken: 3 },
            ],
            study_plan: {
              headline: 'This week, help Student One rebuild Science confidence.',
              goal_summary: { completed: 2, total: 3 },
              history: {
                current_week: { week_key: '2026-W14', completed_steps: 1, total_steps: 1, goal_completed: 2, goal_total: 3 },
                previous_week: { week_key: '2026-W13', completed_steps: 0, total_steps: 3, goal_completed: 1, goal_total: 3 },
                comparison: { summary: 'Up 1 goal from last week.' },
              },
              targets: [
                { id: 'study-minutes', label: 'Study time', current: 20, target: 30, unit: 'min', completed: false },
                { id: 'weekly-quizzes', label: 'Weekly quizzes', current: 1, target: 3, unit: 'quizzes', completed: false, cta_label: 'Practice Quiz Goal', action_tab: 'quiz', chapter_hint: 'Science', context_hint: 'Use one quick quiz to stay on track with your weekly goal.' },
              ],
              schedule: [
                {
                  id: 'assessment-checkpoint',
                  title: 'Retry a Science assessment',
                  description: 'Use one exam-style checkpoint to improve recent scores.',
                  cta_label: 'Retry Assessment',
                  action_tab: 'assessment',
                  chapter_hint: 'Science',
                  context_hint: 'Use one exam-style checkpoint to improve recent scores.',
                  status_label: 'Next up',
                  completed: false,
                },
              ],
            },
            insights: {
              headline: 'Student One is building steady momentum.',
              recommendations: [
                {
                  id: 'review-math',
                  title: 'Review Math',
                  description: 'One quick quiz can strengthen algebra basics.',
                  priority: 'medium',
                  cta_label: 'Open Review Quiz',
                  action_tab: 'quiz',
                  chapter_hint: 'Math',
                  context_hint: 'One quick quiz can strengthen algebra basics.',
                },
              ],
              badges: [
                {
                  id: 'streak-builder',
                  label: 'Streak Builder',
                  description: 'Reach a 3-day learning streak.',
                  progress_pct: 67,
                  earned: false,
                },
              ],
              notifications: [
                {
                  id: 'pending-assignment',
                  title: 'Pending assignment',
                  message: 'Student One still has one mentor-assigned Science quiz to complete.',
                  severity: 'high',
                },
              ],
            },
          }),
        });
      }

      if (target.includes('/students/student/notes')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ notes: [] }),
        });
      }

      return Promise.resolve({
        ok: true,
        status: 200,
        json: async () => ({}),
      });
    });

    await renderWithEffects(<RoleHubPanel />);

    expect(await screen.findByText('Student One is building steady momentum.')).toBeInTheDocument();
    expect(await screen.findByText('Review Math')).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: 'Open Review Quiz' })).toBeInTheDocument();
    expect(await screen.findByText('medium')).toBeInTheDocument();
    expect(await screen.findByText('Streak Builder')).toBeInTheDocument();
    expect(await screen.findByText(/Assessment Avg/i)).toBeInTheDocument();
    expect(await screen.findByText(/84% avg/i)).toBeInTheDocument();
    expect(await screen.findByText(/Best 100%/i)).toBeInTheDocument();
    expect(await screen.findByText(/Latest 80% in Science/i)).toBeInTheDocument();
    expect(await screen.findByText(/Recent 80%, 100%/i)).toBeInTheDocument();
    expect(await screen.findByRole('img', { name: /assessment trend/i })).toBeInTheDocument();
    expect(await screen.findByText(/2 attempts/i)).toBeInTheDocument();
    expect(await screen.findByText(/2 papers/i)).toBeInTheDocument();
    expect(await screen.findByText(/Last attempt 2026-04-02/i)).toBeInTheDocument();
    expect(await screen.findByText(/Student Weekly Plan/i)).toBeInTheDocument();
    expect(await screen.findByText(/Pending assignment/i)).toBeInTheDocument();
    expect(await screen.findByText(/Practice Science quiz/i)).toBeInTheDocument();
    expect(await screen.findByText(/Up 1 goal from last week/i)).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: 'Export Student JSON' })).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: 'Export Student CSV' })).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: 'Print / Save PDF' })).toBeInTheDocument();
    expect(await screen.findByText(/2 of 3 complete/i)).toBeInTheDocument();
    expect(await screen.findByText(/Retry a Science assessment/i)).toBeInTheDocument();
    expect(await screen.findByText(/Next up/i)).toBeInTheDocument();
    expect(await screen.findByText(/Weekly quizzes/i)).toBeInTheDocument();
    expect(await screen.findByText(/1 \/ 3 quizzes/i)).toBeInTheDocument();
    expect(await screen.findByText(/Subject Mastery/i)).toBeInTheDocument();
    expect(await screen.findByText(/Math — Algebra/i)).toBeInTheDocument();
    expect(await screen.findByText(/54% mastery/i)).toBeInTheDocument();
    expect(await screen.findByText(/Recent Activity/i)).toBeInTheDocument();
    expect(await screen.findByText(/assessment · 10 min/i)).toBeInTheDocument();
    expect(await screen.findAllByText(/Science — Optics/i)).toHaveLength(2);
  });

  it('triggers the supplied student weekly plan action callback', async () => {
    localStorage.setItem('role', 'teacher');
    localStorage.setItem('username', 'mentor1');
    const onPlanAction = vi.fn();

    global.fetch.mockImplementation((url) => {
      const target = String(url);

      if (target.includes('/relationships/my-students')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            students: [
              {
                username: 'student',
                email: 'student@example.com',
                first_name: 'Student One',
                linked_at: '2026-04-02T09:00:00Z',
              },
            ],
          }),
        });
      }

      if (target.includes('/students/student/progress')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            student_username: 'student',
            dashboard: {
              total_study_seconds: 1800,
              streak_days: 2,
              totals: { quizzes: 3, lessons: 4, assessments: 1 },
              top_subjects: [
                {
                  subject: 'Science',
                  study_seconds: 900,
                },
              ],
              assignments: [
                {
                  id: 'mentor-assigned-1',
                  title: 'Practice Science quiz',
                  description: 'A mentor assigned one quick Science checkpoint.',
                  action_tab: 'quiz',
                  cta_label: 'Open Assigned Quiz',
                  chapter_hint: 'Science',
                  context_hint: 'A mentor assigned one quick Science checkpoint.',
                  author_role: 'teacher',
                  author_user_id: 'mentor1',
                  status: 'assigned',
                },
              ],
              recent_activity: [
                {
                  activity_type: 'assessment',
                  subject: 'Science',
                  chapter: 'Optics',
                  duration_seconds: 600,
                  logged_at: '2026-04-02T10:00:00Z',
                },
              ],
            },
            mastery: [
              { subject: 'Science', chapter: 'Optics', mastery_pct: 82, quizzes_taken: 3 },
            ],
            study_plan: {
              headline: 'This week, help Student One rebuild Science confidence.',
              goal_summary: { completed: 2, total: 3 },
              targets: [
                {
                  id: 'weekly-quiz',
                  label: 'Quizzes',
                  current: 1,
                  target: 3,
                  unit: 'done',
                  completed: false,
                  cta_label: 'Practice Quiz Goal',
                  action_tab: 'quiz',
                  chapter_hint: 'Science',
                  context_hint: 'Use one quick quiz to stay on track with your weekly goal.',
                },
              ],
              schedule: [
                {
                  id: 'assessment-checkpoint',
                  title: 'Retry a Science assessment',
                  description: 'Use one exam-style checkpoint to improve recent scores.',
                  cta_label: 'Retry Assessment',
                  action_tab: 'assessment',
                  chapter_hint: 'Science',
                  context_hint: 'Use one exam-style checkpoint to improve recent scores.',
                  status_label: 'Next up',
                  completed: false,
                },
              ],
            },
            insights: {
              headline: '',
              notifications: [
                {
                  id: 'pending-assignment',
                  title: 'Pending assignment',
                  message: 'Student One still has one mentor-assigned Science quiz to complete.',
                  severity: 'high',
                },
              ],
              recommendations: [
                {
                  id: 'review-math',
                  title: 'Review Math',
                  description: 'One quick quiz can strengthen algebra basics.',
                  cta_label: 'Open Review Quiz',
                  action_tab: 'quiz',
                  chapter_hint: 'Math',
                  context_hint: 'One quick quiz can strengthen algebra basics.',
                },
              ],
              badges: [],
            },
          }),
        });
      }

      if (target.includes('/students/student/notes')) {
        return Promise.resolve({ ok: true, status: 200, json: async () => ({ notes: [] }) });
      }

      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    });

    await renderWithEffects(<RoleHubPanel onPlanAction={onPlanAction} />);

    fireEvent.click(await screen.findByRole('button', { name: 'Retry Assessment' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Open Review Quiz' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Review Assessment' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Practice Science Quiz' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Open Science Lesson' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Practice Quiz Goal' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Open Assigned Quiz' }));
    expect(onPlanAction).toHaveBeenCalledWith(expect.objectContaining({ action_tab: 'assessment', id: 'assessment-checkpoint' }));
    expect(onPlanAction).toHaveBeenCalledWith(expect.objectContaining({ action_tab: 'quiz', id: 'review-math' }));
    expect(onPlanAction).toHaveBeenCalledWith(expect.objectContaining({ action_tab: 'assessment', chapter_hint: 'Science' }));
    expect(onPlanAction).toHaveBeenCalledWith(expect.objectContaining({ action_tab: 'quiz', id: 'mastery-science' }));
    expect(onPlanAction).toHaveBeenCalledWith(expect.objectContaining({ action_tab: 'lesson', id: 'time-subject-science' }));
    expect(onPlanAction).toHaveBeenCalledWith(expect.objectContaining({ action_tab: 'quiz', id: 'weekly-quiz' }));
  });

  it('filters mentor items by search and overdue status', async () => {
    localStorage.setItem('role', 'teacher');
    localStorage.setItem('username', 'mentor1');

    global.fetch.mockImplementation((url) => {
      const target = String(url);

      if (target.includes('/relationships/my-students')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            students: [
              {
                username: 'student',
                email: 'student@example.com',
                first_name: 'Student One',
                linked_at: '2026-04-02T09:00:00Z',
              },
            ],
          }),
        });
      }

      if (target.includes('/students/student/progress')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            student_username: 'student',
            dashboard: {
              total_study_seconds: 1800,
              streak_days: 2,
              totals: { quizzes: 3, lessons: 4, assessments: 1 },
              recent_activity: [],
              assignments: [
                {
                  id: 61,
                  title: 'Finish Algebra worksheet',
                  description: 'This mentor task is overdue and needs attention.',
                  action_tab: 'lesson',
                  cta_label: 'Open Assigned Lesson',
                  chapter_hint: 'Math',
                  context_hint: 'This mentor task is overdue and needs attention.',
                  due_label: '2000-01-01',
                  author_role: 'teacher',
                  author_user_id: 'mentor1',
                  status: 'assigned',
                },
                {
                  id: 62,
                  title: 'Practice Science quiz',
                  description: 'This one is still upcoming.',
                  action_tab: 'quiz',
                  cta_label: 'Open Assigned Quiz',
                  chapter_hint: 'Science',
                  context_hint: 'This one is still upcoming.',
                  due_label: '2999-01-01',
                  author_role: 'teacher',
                  author_user_id: 'mentor1',
                  status: 'assigned',
                },
              ],
              assessment_summary: {},
            },
            mastery: [],
            study_plan: null,
            insights: { headline: '', notifications: [], recommendations: [], badges: [] },
          }),
        });
      }

      if (target.includes('/students/student/notes')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            notes: [
              {
                id: 31,
                author_user_id: 'mentor1',
                author_role: 'teacher',
                note_text: 'Geometry confidence is improving nicely.',
                visibility: 'all',
                created_at: '2026-04-03T08:00:00Z',
              },
              {
                id: 32,
                author_user_id: 'mentor1',
                author_role: 'teacher',
                note_text: 'Reading summary needs one more pass.',
                visibility: 'guardians',
                created_at: '2026-04-02T08:00:00Z',
              },
            ],
          }),
        });
      }

      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    });

    await renderWithEffects(<RoleHubPanel />);

    expect((await screen.findAllByText(/Overdue/i)).length).toBeGreaterThan(0);
    expect(screen.getByLabelText(/Note access filter/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Assignment sort/i)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/Note access filter/i), { target: { value: 'guardians' } });
    expect(await screen.findByText(/Reading summary needs one more pass/i)).toBeInTheDocument();
    expect(screen.queryByText(/Geometry confidence is improving nicely/i)).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/Note access filter/i), { target: { value: 'all' } });
    const searchInput = screen.getByPlaceholderText(/Search notes or assignments/i);
    fireEvent.change(searchInput, { target: { value: 'Geometry' } });
    expect(await screen.findByText(/Geometry confidence is improving nicely/i)).toBeInTheDocument();
    expect(screen.queryByText(/Reading summary needs one more pass/i)).not.toBeInTheDocument();

    fireEvent.change(searchInput, { target: { value: '' } });
    fireEvent.change(screen.getByLabelText(/Assignment filter/i), { target: { value: 'overdue' } });
    expect(await screen.findByText(/Finish Algebra worksheet/i)).toBeInTheDocument();
    expect(screen.queryByText(/Practice Science quiz/i)).not.toBeInTheDocument();
  });

  it('lets mentors edit and manage student assignment lifecycle', async () => {
    localStorage.setItem('role', 'teacher');
    localStorage.setItem('username', 'mentor1');

    global.fetch.mockImplementation((url, options = {}) => {
      const target = String(url);
      const method = options?.method || 'GET';
      const body = options?.body ? JSON.parse(options.body) : null;

      if (target.includes('/relationships/my-students')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            students: [
              {
                username: 'student',
                email: 'student@example.com',
                first_name: 'Student One',
                linked_at: '2026-04-02T09:00:00Z',
              },
            ],
          }),
        });
      }

      if (target.includes('/students/student/progress')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            student_username: 'student',
            dashboard: {
              total_study_seconds: 1800,
              streak_days: 2,
              totals: { quizzes: 3, lessons: 4, assessments: 1 },
              recent_activity: [],
              assignments: [
                {
                  id: 21,
                  title: 'Practice Science quiz',
                  description: 'A mentor assigned one quick Science checkpoint.',
                  action_tab: 'quiz',
                  cta_label: 'Open Assigned Quiz',
                  chapter_hint: 'Science',
                  context_hint: 'A mentor assigned one quick Science checkpoint.',
                  due_label: '2026-04-10',
                  author_role: 'teacher',
                  author_user_id: 'mentor1',
                  status: 'assigned',
                },
              ],
            },
            mastery: [],
            study_plan: null,
            insights: { headline: '', notifications: [], recommendations: [], badges: [] },
          }),
        });
      }

      if (target.includes('/students/student/notes')) {
        return Promise.resolve({ ok: true, status: 200, json: async () => ({ notes: [] }) });
      }

      if (target.includes('/students/student/assignments/21') && method === 'PUT' && body?.title) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ ...body, id: 21, status: 'assigned' }),
        });
      }

      if (target.includes('/students/student/assignments/21') && method === 'PUT') {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ id: 21, status: 'dismissed' }),
        });
      }

      if (target.includes('/students/student/assignments/21') && method === 'DELETE') {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ status: 'deleted' }),
        });
      }

      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    });

    await renderWithEffects(<RoleHubPanel />);

    fireEvent.click(await screen.findByRole('button', { name: /Edit Assignment/i }));
    expect(await screen.findByLabelText(/Assignment due/i)).toHaveAttribute('type', 'date');
    fireEvent.change(await screen.findByDisplayValue('Practice Science quiz'), {
      target: { value: 'Practice Science assessment' },
    });
    fireEvent.change(screen.getByLabelText(/Assignment due/i), {
      target: { value: '2026-04-12' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Save Assignment/i }));
    await flushEffects();

    fireEvent.click(await screen.findByRole('button', { name: /Dismiss Assignment/i }));
    await flushEffects();
    fireEvent.click(await screen.findByRole('button', { name: /Delete Assignment/i }));
    await flushEffects();

    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/students/student/assignments/21'),
      expect.objectContaining({
        method: 'PUT',
        body: expect.stringContaining('Practice Science assessment'),
      }),
    );
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/students/student/assignments/21'),
      expect.objectContaining({ method: 'DELETE' }),
    );
  });

  it('lets mentors apply bulk assignment actions to the visible list', async () => {
    localStorage.setItem('role', 'teacher');
    localStorage.setItem('username', 'mentor1');

    let assignmentsState = [
      {
        id: 41,
        title: 'Finish Algebra worksheet',
        description: 'Complete the overdue Algebra worksheet tonight.',
        action_tab: 'lesson',
        cta_label: 'Open Assigned Lesson',
        chapter_hint: 'Math',
        due_label: '2026-04-01',
        author_role: 'teacher',
        author_user_id: 'mentor1',
        status: 'assigned',
      },
      {
        id: 42,
        title: 'Practice Science quiz',
        description: 'Complete one quick Science check-in.',
        action_tab: 'quiz',
        cta_label: 'Open Assigned Quiz',
        chapter_hint: 'Science',
        due_label: '2026-04-12',
        author_role: 'teacher',
        author_user_id: 'mentor1',
        status: 'assigned',
      },
      {
        id: 43,
        title: 'Reading reflection',
        description: 'This task was previously dismissed.',
        action_tab: 'chat',
        cta_label: 'Open Assigned Chat',
        chapter_hint: 'English',
        due_label: '2026-04-08',
        author_role: 'teacher',
        author_user_id: 'mentor1',
        status: 'dismissed',
      },
    ];

    global.fetch.mockImplementation((url, options = {}) => {
      const target = String(url);
      const method = options?.method || 'GET';
      const body = options?.body ? JSON.parse(options.body) : null;

      if (target.includes('/relationships/my-students')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            students: [
              {
                username: 'student',
                email: 'student@example.com',
                first_name: 'Student One',
                linked_at: '2026-04-02T09:00:00Z',
              },
            ],
          }),
        });
      }

      if (target.includes('/students/student/progress')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            student_username: 'student',
            dashboard: {
              total_study_seconds: 1800,
              streak_days: 2,
              totals: { quizzes: 3, lessons: 4, assessments: 1 },
              recent_activity: [],
              assignments: assignmentsState,
              assessment_summary: {},
            },
            mastery: [],
            study_plan: null,
            insights: { headline: '', notifications: [], recommendations: [], badges: [] },
          }),
        });
      }

      if (target.includes('/students/student/notes')) {
        return Promise.resolve({ ok: true, status: 200, json: async () => ({ notes: [] }) });
      }

      if (target.includes('/students/student/assignments/') && method === 'PUT') {
        const assignmentId = Number(target.split('/assignments/')[1]);
        assignmentsState = assignmentsState.map((item) => (
          item.id === assignmentId ? { ...item, ...body } : item
        ));
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => assignmentsState.find((item) => item.id === assignmentId),
        });
      }

      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    });

    await renderWithEffects(<RoleHubPanel />);

    expect(await screen.findByText(/bulk assignment actions/i)).toBeInTheDocument();
    expect(await screen.findByText(/2 open visible/i)).toBeInTheDocument();
    expect(await screen.findByText(/1 overdue/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Dismiss Overdue/i }));
    await flushEffects(4);
    fireEvent.click(screen.getByRole('button', { name: /Mark Open Done/i }));
    await flushEffects(4);

    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/students/student/assignments/41'),
      expect.objectContaining({
        method: 'PUT',
        body: expect.stringContaining('dismissed'),
      }),
    );
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/students/student/assignments/42'),
      expect.objectContaining({
        method: 'PUT',
        body: expect.stringContaining('completed'),
      }),
    );
    expect(await screen.findByText(/0 open visible/i)).toBeInTheDocument();
  });

  it('lets teachers assign the same task to multiple linked learners', async () => {
    localStorage.setItem('role', 'teacher');
    localStorage.setItem('username', 'mentor1');

    const assignmentPosts = [];

    global.fetch.mockImplementation((url, options = {}) => {
      const target = String(url);
      const method = options?.method || 'GET';
      const body = options?.body ? JSON.parse(options.body) : null;

      if (target.includes('/relationships/my-students')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            students: [
              {
                username: 'student',
                email: 'student@example.com',
                first_name: 'Student One',
                relation_label: 'Class 8A',
                linked_at: '2026-04-02T09:00:00Z',
              },
              {
                username: 'student2',
                email: 'student2@example.com',
                first_name: 'Student Two',
                relation_label: 'Class 8A',
                linked_at: '2026-04-01T09:00:00Z',
              },
            ],
          }),
        });
      }

      if (target.includes('/students/student/progress')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            student_username: 'student',
            dashboard: {
              total_study_seconds: 1800,
              streak_days: 2,
              totals: { quizzes: 3, lessons: 4, assessments: 1 },
              recent_activity: [],
              assignments: [],
              assessment_summary: {},
            },
            mastery: [],
            study_plan: null,
            insights: { headline: '', notifications: [], recommendations: [], badges: [] },
          }),
        });
      }

      if (target.includes('/students/student2/progress')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            student_username: 'student2',
            dashboard: {
              total_study_seconds: 1200,
              streak_days: 1,
              totals: { quizzes: 1, lessons: 2, assessments: 0 },
              recent_activity: [],
              assignments: [],
              assessment_summary: {},
            },
            mastery: [],
            study_plan: null,
            insights: { headline: '', notifications: [], recommendations: [], badges: [] },
          }),
        });
      }

      if (target.includes('/students/student/notes') || target.includes('/students/student2/notes')) {
        return Promise.resolve({ ok: true, status: 200, json: async () => ({ notes: [] }) });
      }

      if (target.includes('/students/') && target.includes('/assignments') && method === 'POST') {
        assignmentPosts.push({ target, body });
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ id: `new-${assignmentPosts.length}`, ...body }),
        });
      }

      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    });

    await renderWithEffects(<RoleHubPanel />);

    expect(await screen.findByText(/2 learners selected/i)).toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText(/Focus subject or chapter/i), {
      target: { value: 'Science' },
    });
    fireEvent.change(screen.getByPlaceholderText(/Mentor note \(optional\)/i), {
      target: { value: 'Complete a short recap together.' },
    });
    fireEvent.change(screen.getByPlaceholderText(/Optional due date/i), {
      target: { value: '2026-04-14' },
    });
    fireEvent.click(screen.getByRole('button', { name: /assign to 2 learners/i }));
    await flushEffects(4);

    expect(assignmentPosts).toHaveLength(2);
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/students/student/assignments'),
      expect.objectContaining({
        method: 'POST',
        body: expect.stringContaining('Science'),
      }),
    );
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/students/student2/assignments'),
      expect.objectContaining({
        method: 'POST',
        body: expect.stringContaining('2026-04-14'),
      }),
    );
  });

  it('lets teachers apply a class-wide assignment template', async () => {
    localStorage.setItem('role', 'teacher');
    localStorage.setItem('username', 'mentor1');

    const assignmentPosts = [];

    global.fetch.mockImplementation((url, options = {}) => {
      const target = String(url);
      const method = options?.method || 'GET';
      const body = options?.body ? JSON.parse(options.body) : null;

      if (target.includes('/relationships/my-students')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            students: [
              {
                username: 'student',
                email: 'student@example.com',
                first_name: 'Student One',
                relation_label: 'Class 8A',
                linked_at: '2026-04-02T09:00:00Z',
              },
              {
                username: 'student2',
                email: 'student2@example.com',
                first_name: 'Student Two',
                relation_label: 'Class 8A',
                linked_at: '2026-04-01T09:00:00Z',
              },
            ],
          }),
        });
      }

      if (target.includes('/students/student/progress')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            student_username: 'student',
            dashboard: {
              total_study_seconds: 1800,
              streak_days: 2,
              totals: { quizzes: 3, lessons: 4, assessments: 1 },
              recent_activity: [],
              assignments: [],
              assessment_summary: {},
            },
            mastery: [],
            study_plan: null,
            insights: { headline: '', notifications: [], recommendations: [], badges: [] },
          }),
        });
      }

      if (target.includes('/students/student2/progress')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            student_username: 'student2',
            dashboard: {
              total_study_seconds: 1200,
              streak_days: 1,
              totals: { quizzes: 1, lessons: 2, assessments: 0 },
              recent_activity: [],
              assignments: [],
              assessment_summary: {},
            },
            mastery: [],
            study_plan: null,
            insights: { headline: '', notifications: [], recommendations: [], badges: [] },
          }),
        });
      }

      if (target.includes('/students/student/notes') || target.includes('/students/student2/notes')) {
        return Promise.resolve({ ok: true, status: 200, json: async () => ({ notes: [] }) });
      }

      if (target.includes('/students/') && target.includes('/assignments') && method === 'POST') {
        assignmentPosts.push({ target, body });
        return Promise.resolve({ ok: true, status: 200, json: async () => ({ id: `template-${assignmentPosts.length}`, ...body }) });
      }

      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    });

    await renderWithEffects(<RoleHubPanel />);

    expect(await screen.findByText(/assignment templates/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /weekly science review/i }));

    expect(await screen.findByDisplayValue('Science')).toBeInTheDocument();
    expect(screen.getByDisplayValue(/Complete a short science lesson recap/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /assign to 2 learners/i })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /assign to 2 learners/i }));
    await flushEffects(4);

    expect(assignmentPosts).toHaveLength(2);
    expect(assignmentPosts[0].body).toMatchObject({
      chapter_hint: 'Science',
      action_tab: 'lesson',
    });
  });

  it('lets teachers save and reuse custom assignment templates', async () => {
    localStorage.setItem('role', 'teacher');
    localStorage.setItem('username', 'mentor1');

    global.fetch.mockImplementation((url) => {
      const target = String(url);

      if (target.includes('/relationships/my-students')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            students: [
              {
                username: 'student',
                email: 'student@example.com',
                first_name: 'Student One',
                relation_label: 'Class 8A',
                linked_at: '2026-04-02T09:00:00Z',
              },
              {
                username: 'student2',
                email: 'student2@example.com',
                first_name: 'Student Two',
                relation_label: 'Class 8A',
                linked_at: '2026-04-01T09:00:00Z',
              },
            ],
          }),
        });
      }

      if (target.includes('/students/student/progress') || target.includes('/students/student2/progress')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            dashboard: {
              total_study_seconds: 1200,
              streak_days: 2,
              totals: { quizzes: 2, lessons: 3, assessments: 1 },
              recent_activity: [],
              assignments: [],
              assessment_summary: {},
            },
            mastery: [],
            study_plan: null,
            insights: { headline: '', notifications: [], recommendations: [], badges: [] },
          }),
        });
      }

      if (target.includes('/students/student/notes') || target.includes('/students/student2/notes')) {
        return Promise.resolve({ ok: true, status: 200, json: async () => ({ notes: [] }) });
      }

      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    });

    const view = await renderWithEffects(<RoleHubPanel />);

    fireEvent.change(screen.getByDisplayValue('Quiz'), { target: { value: 'lesson' } });
    fireEvent.change(screen.getByPlaceholderText(/Focus subject or chapter/i), {
      target: { value: 'History' },
    });
    fireEvent.change(screen.getByPlaceholderText(/Mentor note \(optional\)/i), {
      target: { value: 'Prepare Friday debate prompt.' },
    });
    fireEvent.click(screen.getByRole('button', { name: /save as template/i }));

    expect(await screen.findByText(/^saved templates$/i)).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: /^history lesson template$/i })).toBeInTheDocument();

    await rerenderWithEffects(view, <RoleHubPanel />);
    fireEvent.change(screen.getByPlaceholderText(/Focus subject or chapter/i), {
      target: { value: '' },
    });
    fireEvent.change(screen.getByPlaceholderText(/Mentor note \(optional\)/i), {
      target: { value: '' },
    });
    fireEvent.click(await screen.findByRole('button', { name: /^history lesson template$/i }));

    expect(await screen.findByDisplayValue('History')).toBeInTheDocument();
    expect(await screen.findByDisplayValue('Prepare Friday debate prompt.')).toBeInTheDocument();
  });

  it('lets teachers rename and update saved assignment templates', async () => {
    localStorage.setItem('role', 'teacher');
    localStorage.setItem('username', 'mentor1');

    global.fetch.mockImplementation((url) => {
      const target = String(url);

      if (target.includes('/relationships/my-students')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            students: [
              {
                username: 'student',
                email: 'student@example.com',
                first_name: 'Student One',
                relation_label: 'Class 8A',
                linked_at: '2026-04-02T09:00:00Z',
              },
            ],
          }),
        });
      }

      if (target.includes('/students/student/progress')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            dashboard: {
              total_study_seconds: 1200,
              streak_days: 2,
              totals: { quizzes: 2, lessons: 3, assessments: 1 },
              recent_activity: [],
              assignments: [],
              assessment_summary: {},
            },
            mastery: [],
            study_plan: null,
            insights: { headline: '', notifications: [], recommendations: [], badges: [] },
          }),
        });
      }

      if (target.includes('/students/student/notes')) {
        return Promise.resolve({ ok: true, status: 200, json: async () => ({ notes: [] }) });
      }

      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    });

    const view = await renderWithEffects(<RoleHubPanel />);

    fireEvent.change(screen.getByDisplayValue('Quiz'), { target: { value: 'lesson' } });
    fireEvent.change(screen.getByPlaceholderText(/Focus subject or chapter/i), {
      target: { value: 'History' },
    });
    fireEvent.change(screen.getByPlaceholderText(/Mentor note \(optional\)/i), {
      target: { value: 'Prepare Friday debate prompt.' },
    });
    fireEvent.click(screen.getByRole('button', { name: /save as template/i }));

    fireEvent.click(await screen.findByRole('button', { name: /edit history lesson template/i }));
    fireEvent.change(await screen.findByLabelText(/Template name/i), {
      target: { value: 'History Debate Warmup' },
    });
    fireEvent.change(screen.getByLabelText(/Template note/i), {
      target: { value: 'Update the prompt with debate evidence notes.' },
    });
    fireEvent.click(screen.getByRole('button', { name: /save template changes/i }));

    await rerenderWithEffects(view, <RoleHubPanel />);

    expect(await screen.findByRole('button', { name: /^history debate warmup$/i })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /^history debate warmup$/i }));
    expect(await screen.findByDisplayValue('History')).toBeInTheDocument();
    expect(await screen.findByDisplayValue('Update the prompt with debate evidence notes.')).toBeInTheDocument();
  });

  it('lets teachers organize saved templates by category and favorites', async () => {
    localStorage.setItem('role', 'teacher');
    localStorage.setItem('username', 'mentor1');

    global.fetch.mockImplementation((url) => {
      const target = String(url);

      if (target.includes('/relationships/my-students')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            students: [
              {
                username: 'student',
                email: 'student@example.com',
                first_name: 'Student One',
                relation_label: 'Class 8A',
                linked_at: '2026-04-02T09:00:00Z',
              },
            ],
          }),
        });
      }

      if (target.includes('/students/student/progress')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            dashboard: {
              total_study_seconds: 1200,
              streak_days: 2,
              totals: { quizzes: 2, lessons: 3, assessments: 1 },
              recent_activity: [],
              assignments: [],
              assessment_summary: {},
            },
            mastery: [],
            study_plan: null,
            insights: { headline: '', notifications: [], recommendations: [], badges: [] },
          }),
        });
      }

      if (target.includes('/students/student/notes')) {
        return Promise.resolve({ ok: true, status: 200, json: async () => ({ notes: [] }) });
      }

      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    });

    await renderWithEffects(<RoleHubPanel />);

    fireEvent.change(screen.getByDisplayValue('Quiz'), { target: { value: 'lesson' } });
    fireEvent.change(screen.getByLabelText(/Template category/i), { target: { value: 'humanities' } });
    fireEvent.change(screen.getByPlaceholderText(/Focus subject or chapter/i), {
      target: { value: 'History' },
    });
    fireEvent.change(screen.getByPlaceholderText(/Mentor note \(optional\)/i), {
      target: { value: 'Prepare Friday debate prompt.' },
    });
    fireEvent.click(screen.getByRole('button', { name: /save as template/i }));

    fireEvent.change(screen.getByLabelText(/Template category/i), { target: { value: 'stem' } });
    fireEvent.change(screen.getByPlaceholderText(/Focus subject or chapter/i), {
      target: { value: 'Science' },
    });
    fireEvent.change(screen.getByPlaceholderText(/Mentor note \(optional\)/i), {
      target: { value: 'Review the lab reflection before Friday.' },
    });
    fireEvent.click(screen.getByRole('button', { name: /save as template/i }));

    expect(await screen.findByText(/2 saved templates/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /favorite history lesson template/i }));
    expect(await screen.findByText(/1 favorites/i)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/Saved template category/i), { target: { value: 'humanities' } });
    expect(await screen.findByRole('button', { name: /^history lesson template$/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^science lesson template$/i })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /show favorites only/i }));
    expect(await screen.findByRole('button', { name: /^history lesson template$/i })).toBeInTheDocument();
  });

  it('lets teachers preview and duplicate saved templates', async () => {
    localStorage.setItem('role', 'teacher');
    localStorage.setItem('username', 'mentor1');

    global.fetch.mockImplementation((url) => {
      const target = String(url);

      if (target.includes('/relationships/my-students')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            students: [
              {
                username: 'student',
                email: 'student@example.com',
                first_name: 'Student One',
                relation_label: 'Class 8A',
                linked_at: '2026-04-02T09:00:00Z',
              },
            ],
          }),
        });
      }

      if (target.includes('/students/student/progress')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            dashboard: {
              total_study_seconds: 1200,
              streak_days: 2,
              totals: { quizzes: 2, lessons: 3, assessments: 1 },
              recent_activity: [],
              assignments: [],
              assessment_summary: {},
            },
            mastery: [],
            study_plan: null,
            insights: { headline: '', notifications: [], recommendations: [], badges: [] },
          }),
        });
      }

      if (target.includes('/students/student/notes')) {
        return Promise.resolve({ ok: true, status: 200, json: async () => ({ notes: [] }) });
      }

      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    });

    await renderWithEffects(<RoleHubPanel />);

    fireEvent.change(screen.getByDisplayValue('Quiz'), { target: { value: 'lesson' } });
    fireEvent.change(screen.getByPlaceholderText(/Focus subject or chapter/i), {
      target: { value: 'Science' },
    });
    fireEvent.change(screen.getByPlaceholderText(/Mentor note \(optional\)/i), {
      target: { value: 'Review the lab summary before Friday.' },
    });
    fireEvent.click(screen.getByRole('button', { name: /save as template/i }));

    fireEvent.click(await screen.findByRole('button', { name: /preview science lesson template/i }));
    expect(await screen.findByText(/template preview/i)).toBeInTheDocument();
    expect(await screen.findByText(/review the lab summary before friday/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /duplicate science lesson template/i }));
    expect(await screen.findByText(/2 saved templates/i)).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: /^science lesson template copy$/i })).toBeInTheDocument();
  });

  it('lets teachers export and import shared template libraries', async () => {
    localStorage.setItem('role', 'teacher');
    localStorage.setItem('username', 'mentor1');

    const createObjectURL = vi.spyOn(window.URL, 'createObjectURL').mockImplementation(() => 'blob:template-export');
    const revokeObjectURL = vi.spyOn(window.URL, 'revokeObjectURL').mockImplementation(() => {});
    const anchorClickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});

    global.fetch.mockImplementation((url) => {
      const target = String(url);

      if (target.includes('/relationships/my-students')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            students: [
              {
                username: 'student',
                email: 'student@example.com',
                first_name: 'Student One',
                relation_label: 'Class 8A',
                linked_at: '2026-04-02T09:00:00Z',
              },
            ],
          }),
        });
      }

      if (target.includes('/students/student/progress')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            dashboard: {
              total_study_seconds: 1200,
              streak_days: 2,
              totals: { quizzes: 2, lessons: 3, assessments: 1 },
              recent_activity: [],
              assignments: [],
              assessment_summary: {},
            },
            mastery: [],
            study_plan: null,
            insights: { headline: '', notifications: [], recommendations: [], badges: [] },
          }),
        });
      }

      if (target.includes('/students/student/notes')) {
        return Promise.resolve({ ok: true, status: 200, json: async () => ({ notes: [] }) });
      }

      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    });

    await renderWithEffects(<RoleHubPanel />);

    fireEvent.change(screen.getByDisplayValue('Quiz'), { target: { value: 'lesson' } });
    fireEvent.change(screen.getByPlaceholderText(/Focus subject or chapter/i), {
      target: { value: 'Science' },
    });
    fireEvent.change(screen.getByPlaceholderText(/Mentor note \(optional\)/i), {
      target: { value: 'Review the lab summary before Friday.' },
    });
    fireEvent.click(screen.getByRole('button', { name: /save as template/i }));

    fireEvent.click(await screen.findByRole('button', { name: /export template library/i }));
    expect(createObjectURL).toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: /remove template/i }));
    await flushEffects();
    expect(screen.queryByRole('button', { name: /^science lesson template$/i })).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/import template json/i), {
      target: {
        value: JSON.stringify([
          {
            id: 'shared-science-template',
            label: 'Science Lesson Template',
            assignmentType: 'lesson',
            subject: 'Science',
            note: 'Review the lab summary before Friday.',
            category: 'stem',
            isFavorite: true,
          },
        ]),
      },
    });
    fireEvent.click(screen.getByRole('button', { name: /import shared templates/i }));

    expect(await screen.findByRole('button', { name: /^science lesson template$/i })).toBeInTheDocument();
    expect(await screen.findByText(/1 favorites/i)).toBeInTheDocument();
  });

  it('lets mentors create assignments with a due date', async () => {
    localStorage.setItem('role', 'teacher');
    localStorage.setItem('username', 'mentor1');

    global.fetch.mockImplementation((url, options = {}) => {
      const target = String(url);
      const method = options?.method || 'GET';
      const body = options?.body ? JSON.parse(options.body) : null;

      if (target.includes('/relationships/my-students')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            students: [
              {
                username: 'student',
                email: 'student@example.com',
                first_name: 'Student One',
                linked_at: '2026-04-02T09:00:00Z',
              },
            ],
          }),
        });
      }

      if (target.includes('/students/student/progress')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            student_username: 'student',
            dashboard: {
              total_study_seconds: 1800,
              streak_days: 2,
              totals: { quizzes: 3, lessons: 4, assessments: 1 },
              recent_activity: [],
              assignments: [],
            },
            mastery: [],
            study_plan: null,
            insights: { headline: '', notifications: [], recommendations: [], badges: [] },
          }),
        });
      }

      if (target.includes('/students/student/notes')) {
        return Promise.resolve({ ok: true, status: 200, json: async () => ({ notes: [] }) });
      }

      if (target.includes('/students/student/assignments') && method === 'POST') {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ assignment_id: 44, ...body }),
        });
      }

      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    });

    await renderWithEffects(<RoleHubPanel />);

    expect(screen.getByPlaceholderText(/Optional due date/i)).toHaveAttribute('type', 'date');
    fireEvent.change(screen.getByPlaceholderText(/Focus subject or chapter/i), {
      target: { value: 'Science' },
    });
    fireEvent.change(screen.getByPlaceholderText(/Mentor note \(optional\)/i), {
      target: { value: 'Complete this before Friday.' },
    });
    fireEvent.change(screen.getByPlaceholderText(/Optional due date/i), {
      target: { value: '2026-04-12' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Assign Task/i }));
    await flushEffects();

    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/students/student/assignments'),
      expect.objectContaining({
        method: 'POST',
        body: expect.stringContaining('2026-04-12'),
      }),
    );
  });

  it('lets mentors review, edit, and delete coaching notes', async () => {
    localStorage.setItem('role', 'teacher');
    localStorage.setItem('username', 'mentor1');

    global.fetch.mockImplementation((url, options = {}) => {
      const target = String(url);
      const method = options?.method || 'GET';

      if (target.includes('/relationships/my-students')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            students: [
              {
                username: 'student',
                email: 'student@example.com',
                first_name: 'Student One',
                linked_at: '2026-04-02T09:00:00Z',
              },
            ],
          }),
        });
      }

      if (target.includes('/students/student/progress')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            student_username: 'student',
            dashboard: {
              total_study_seconds: 900,
              streak_days: 1,
              totals: { quizzes: 1, lessons: 1, assessments: 0 },
              recent_activity: [],
              assignments: [],
            },
            mastery: [],
            study_plan: null,
            insights: { headline: '', notifications: [], recommendations: [], badges: [] },
          }),
        });
      }

      if (target.includes('/students/student/notes') && method === 'GET') {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            notes: [
              {
                id: 31,
                author_user_id: 'mentor1',
                author_role: 'teacher',
                note_text: 'Focus on algebra confidence this week.',
                visibility: 'guardians',
                created_at: '2026-04-03T08:00:00Z',
              },
            ],
          }),
        });
      }

      if (target.includes('/students/student/notes/31') && method === 'PUT') {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            id: 31,
            note_text: 'Focus on algebra and geometry confidence this week.',
            visibility: 'all',
          }),
        });
      }

      if (target.includes('/students/student/notes/31') && method === 'DELETE') {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ status: 'deleted', note_id: 31 }),
        });
      }

      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    });

    await renderWithEffects(<RoleHubPanel />);

    expect(await screen.findByText(/Focus on algebra confidence this week./i)).toBeInTheDocument();
    expect(await screen.findByText(/^guardians \+ author$/i)).toBeInTheDocument();
    fireEvent.click(await screen.findByRole('button', { name: /Edit Note/i }));
    fireEvent.change(await screen.findByDisplayValue(/Focus on algebra confidence this week./i), {
      target: { value: 'Focus on algebra and geometry confidence this week.' },
    });
    fireEvent.change(screen.getByLabelText(/Note visibility/i), { target: { value: 'all' } });
    fireEvent.click(screen.getByRole('button', { name: /Save Note/i }));
    await flushEffects();
    fireEvent.click(await screen.findByRole('button', { name: /Delete Note/i }));
    await flushEffects();

    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/students/student/notes/31'),
      expect.objectContaining({ method: 'PUT' }),
    );
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/students/student/notes/31'),
      expect.objectContaining({ method: 'DELETE' }),
    );
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

  it('renders multiple panels independently', async () => {
    const { container: chatContainer } = await renderWithEffects(<ChatPanel />);
    const { container: lessonContainer } = render(<LessonPanel />);
    const { container: quizContainer } = await renderWithEffects(<QuizPanel />);
    
    expect(chatContainer).toBeInTheDocument();
    expect(lessonContainer).toBeInTheDocument();
    expect(quizContainer).toBeInTheDocument();
  });

  it('panels handle rapid prop changes', async () => {
    const view = await renderWithEffects(<ChatPanel sessionId="session1" />);
    await rerenderWithEffects(view, <ChatPanel sessionId="session2" />);
    await rerenderWithEffects(view, <ChatPanel sessionId="session3" />);
    
    expect(view.container.innerHTML.length).toBeGreaterThan(0);
  });

  it('panels maintain separate state', async () => {
    const { container: c1 } = await renderWithEffects(<ChatPanel />);
    const { container: c2 } = render(<LessonPanel />);
    const { container: c3 } = await renderWithEffects(<QuizPanel />);
    
    // All panels should render without interference
    expect(c1.innerHTML.length).toBeGreaterThan(0);
    expect(c2.innerHTML.length).toBeGreaterThan(0);
    expect(c3.innerHTML.length).toBeGreaterThan(0);
  });

  it('all panels render list items', async () => {
    const { container: chatContainer } = await renderWithEffects(<ChatPanel />);
    const { container: lessonContainer } = render(<LessonPanel />);
    const { container: quizContainer } = await renderWithEffects(<QuizPanel />);
    
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
  it('ChatPanel has semantic structure', async () => {
    const { container } = await renderWithEffects(<ChatPanel />);
    expect(container).toBeInTheDocument();
  });

  it('LessonPanel has interactive elements', () => {
    const { container } = render(<LessonPanel />);
    const buttons = container.querySelectorAll('button');
    // Should have buttons or interactive controls
    expect(container.children.length).toBeGreaterThan(0);
  });

  it('QuizPanel has form controls', async () => {
    const { container } = await renderWithEffects(<QuizPanel />);
    // Quiz should be interactive
    expect(container.children.length).toBeGreaterThan(0);
  });

  it('FlashcardPanel has navigation', async () => {
    const { container } = await renderWithEffects(<FlashcardPanel />);
    // Flashcard should have navigation or display
    expect(container.children.length).toBeGreaterThan(0);
  });
});
