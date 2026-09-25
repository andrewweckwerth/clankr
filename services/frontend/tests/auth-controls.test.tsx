import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { expect, test, vi } from 'vitest';
import AuthControls from '@/components/AuthControls';

const { useSession, signOut } = vi.hoisted(() => ({ useSession: vi.fn(), signOut: vi.fn() }));
vi.mock('@/lib/auth-client', () => ({ authClient: { useSession, signOut } }));

test('pending session shows loading without a sign-in action', () => {
  useSession.mockReturnValue({ data: null, isPending: true });
  render(<AuthControls />);
  expect(screen.getByLabelText('Loading account')).toBeInTheDocument();
  expect(screen.queryByRole('link', { name: 'Sign in' })).not.toBeInTheDocument();
});

test('signed-out account links to sign in', () => {
  useSession.mockReturnValue({ data: null, isPending: false });
  render(<AuthControls />);
  expect(screen.getByRole('link', { name: 'Sign in' })).toHaveAttribute('href', '/sign-in');
});

test('signed-in account links to settings and can sign out', async () => {
  useSession.mockReturnValue({ data: { user: { id: 'test-user' } }, isPending: false });
  render(<AuthControls />);
  expect(screen.getByRole('link', { name: 'Account' })).toHaveAttribute('href', '/account');
  await userEvent.setup().click(screen.getByRole('button', { name: 'Sign out' }));
  expect(signOut).toHaveBeenCalledOnce();
});
