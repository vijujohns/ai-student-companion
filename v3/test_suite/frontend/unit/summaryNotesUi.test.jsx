import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import SummaryViewer from '../../../frontend/src/components/SummaryViewer.jsx';
import NotesPanel from '../../../frontend/src/components/NotesPanel.jsx';

beforeEach(() => {
  vi.clearAllMocks();
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => ({ notes: [] }),
  });
  localStorage.clear();
  localStorage.setItem('token', 'demo-token');
  localStorage.setItem('username', 'student');
});

describe('Summary notes UI', () => {
  it('renders a structured summary card with save action', () => {
    render(
      <SummaryViewer
        content={`## 📘 Refraction\n\n### Overview\nLight bends when it passes from one medium to another.\n\n### Key Points\n- Speed changes\n- Direction changes`}
        onSave={vi.fn()}
      />,
    );

    expect(screen.getByText(/refraction/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /save to notes/i })).toBeInTheDocument();
  });

  it('lets the notes panel load and show saved notes', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({
        notes: [
          {
            id: 7,
            title: 'Refraction Revision Notes',
            content: 'Light bends due to change in speed.',
            updated_at: '2026-04-09T10:00:00Z',
          },
        ],
      }),
    });

    render(<NotesPanel isActive />);

    await waitFor(() => {
      expect(screen.getByText(/refraction revision notes/i)).toBeInTheDocument();
    });
  });

  it('supports local editing before saving from the summary viewer', () => {
    const onSave = vi.fn();
    render(<SummaryViewer content={'## 📘 Sound\n\n### Overview\nSound is produced by vibrations.'} onSave={onSave} />);

    fireEvent.click(screen.getByRole('button', { name: /edit notes/i }));
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Updated note text' } });
    fireEvent.click(screen.getByRole('button', { name: /save to notes/i }));

    expect(onSave).toHaveBeenCalledWith(expect.objectContaining({ content: 'Updated note text' }));
  });
});
