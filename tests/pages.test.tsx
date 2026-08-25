import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import Home from '@/app/page';
import { AnswerContent, citationSummary } from '@/components/answer-content';
import { AuthCard } from '@/components/auth-card';
import type { Citation } from '@/lib/types';

describe('public experience', () => {
  it('explains the product and sends users to authentication', () => {
    render(<Home />);
    expect(screen.getByRole('heading', { name: /answers you can verify/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /build my library/i })).toHaveAttribute('href', '/auth');
    expect(screen.getByText(/without mixing your data/i)).toBeInTheDocument();
  });

  it('renders a complete private-account sign-in form', () => {
    render(<AuthCard initialMode="login" />);
    fireEvent.change(screen.getByLabelText(/email address/i), { target: { value: 'reader@example.com' } });
    expect(screen.getByLabelText(/email address/i)).toHaveValue('reader@example.com');
    expect(screen.getByLabelText(/password/i)).toHaveAttribute('minlength', '8');
    expect(screen.getByText(/free-tier ai processing/i)).toBeInTheDocument();
  });

  it('renders answer structure and grouped citation markers clearly', () => {
    const citation: Citation = {
      id: 'citation-2',
      label: 2,
      document_id: 'document-1',
      document_name: 'handbook.md',
      page_start: null,
      page_end: null,
      section_path: ['Retrieval'],
      quote: 'Verified evidence',
    };
    const onCitation = vi.fn();

    render(
      <AnswerContent
        content={'Atlas uses two retrieval modes.\n\n* Semantic search [C2, C3]\n* Keyword search'}
        citations={[citation]}
        onCitation={onCitation}
      />,
    );

    expect(screen.getAllByRole('listitem')).toHaveLength(2);
    fireEvent.click(screen.getByRole('button', { name: /open citation c2/i }));
    expect(onCitation).toHaveBeenCalledWith(citation);
    expect(screen.getByTitle(/earlier answer did not save/i)).toHaveTextContent('3');
    expect(citationSummary('Supported [C2].', [citation])).toBe('1 cited source');
    expect(citationSummary('Older grouped marker [C2, C3].', [])).toMatch(/unavailable/i);
  });
});
