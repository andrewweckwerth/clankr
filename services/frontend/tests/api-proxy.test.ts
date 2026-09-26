// @vitest-environment node
import { beforeEach, expect, test, vi } from 'vitest';
import { NextRequest } from 'next/server';
import { GET, POST, DELETE } from '@/app/api/[...path]/route';

const { getSession, signIdentity } = vi.hoisted(() => ({ getSession: vi.fn(), signIdentity: vi.fn() }));
vi.mock('@/lib/auth', () => ({ auth: { api: { getSession } } }));
vi.mock('@/lib/internal-auth', () => ({ INTERNAL_AUTH_HEADER: 'x-clankr-internal-auth', createInternalAuthHeader: signIdentity }));
vi.mock('@/lib/structured_logging', () => ({ logEvent: vi.fn(), logError: vi.fn() }));

let upstream: ReturnType<typeof vi.fn>;
beforeEach(() => {
  getSession.mockResolvedValue(null);
  signIdentity.mockReturnValue('server-signed');
  upstream = vi.fn().mockImplementation(async () => Response.json([]));
  vi.stubGlobal('fetch', upstream);
});

function request(path: string, method = 'GET') {
  const req = new NextRequest(`http://localhost/api/${path}`, {
    method,
    headers: { cookie: 'session=private', 'x-clankr-internal-auth': 'forged' },
  });
  return [req, { params: Promise.resolve({ path: path.split('?')[0].split('/') }) }] as const;
}

test.each(['songs', 'songs/1', 'songs/1/artifact', 'jobs?view=active', 'jobs?view=all'])('guest can read %s without forwarding a forged identity', async (path) => {
  const response = await GET(...request(path));
  expect(response.status).toBe(200);
  const headers = upstream.mock.calls[0][1].headers as Headers;
  expect(headers.has('x-clankr-internal-auth')).toBe(false);
  expect(headers.has('cookie')).toBe(false);
  expect(response.headers.get('cache-control')).toBe('private, no-store');
});

test.each(['songs/mine', 'songs/1/other', 'jobs', 'jobs?view=mine', 'jobs?view=all&view=mine', 'jobs/1', 'jobs/1/artifact', 'usage'])('guest cannot read %s', async (path) => {
  const response = await GET(...request(path));
  expect(response.status).toBe(401);
  expect(upstream).not.toHaveBeenCalled();
});

test('guest cannot submit, retry, or delete through public routes', async () => {
  for (const path of ['analyze', 'jobs/1/retry', 'songs']) {
    expect((await POST(...request(path, 'POST'))).status).toBe(401);
  }
  expect((await DELETE(...request('songs/1', 'DELETE'))).status).toBe(401);
  expect(upstream).not.toHaveBeenCalled();
});

test('signed-in requests use the verified session identity', async () => {
  const user = { id: 'user', name: 'Andrew', email: 'test@example.com' };
  getSession.mockResolvedValue({ user });
  expect((await GET(...request('jobs?view=mine'))).status).toBe(200);
  expect(signIdentity).toHaveBeenCalledWith(user);
  expect(upstream.mock.calls[0][1].headers.get('x-clankr-internal-auth')).toBe('server-signed');
});
