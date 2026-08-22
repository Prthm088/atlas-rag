import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import Home from '@/app/page';
import { AuthCard } from '@/components/auth-card';

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

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
});
