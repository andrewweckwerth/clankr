import { expect, test } from '@playwright/test';

// Browser tests cover real Next.js rendering, navigation, and polling. All API
// traffic is stubbed here: these do not prove real login or model inference.
test('signed-out tool prompts for sign in', async ({ page }) => {
  await page.route('**/api/**', async (route) => {
    if (new URL(route.request().url()).pathname === '/api/auth/get-session') {
      await route.fulfill({ json: null });
    } else {
      throw new Error(`Unexpected API request: ${route.request().url()}`);
    }
  });
  await page.goto('/tools/classifier');
  await expect(page.getByRole('link', { name: /Sign in/i }).first()).toBeVisible();
  await expect(page.getByRole('textbox', { name: 'Lyrics or text' })).toHaveCount(0);
});

test('text submission navigates to job progress and renders the completed result', async ({ page }) => {
  let jobReads = 0;
  await page.route('**/api/**', async (route) => {
    const request = route.request();
    const pathname = new URL(request.url()).pathname;
    if (pathname === '/api/auth/get-session') {
      await route.fulfill({ json: {
        session: { id: 'session', userId: 'user', token: 'test-token', expiresAt: '2099-01-01T00:00:00Z' },
        user: { id: 'user', name: 'Test User', email: 'test@example.com', emailVerified: true },
      } });
    } else if (pathname === '/api/usage') {
      await route.fulfill({ json: { date: '2026-09-24', limit: 10, used: 0, remaining: 10 } });
    } else if (pathname === '/api/analyze') {
      expect(request.method()).toBe('POST');
      const body = request.postData() ?? '';
      expect(body).toContain('classifier');
      expect(body).toContain('standalone');
      expect(body).toContain('Browser test lyrics');
      await route.fulfill({ json: { success: true, job_id: 42 } });
    } else if (pathname === '/api/jobs/42') {
      const status = ++jobReads === 1 ? 'processing' : 'completed';
      await route.fulfill({ json: {
        id: 42, job_type: 'classifier', status, current_stage: status === 'processing' ? 'classify' : null,
        title: 'Text classification', cache_hit: false, created_at: '2026-09-24T12:00:00',
        classification: status === 'completed' ? 'Human' : null, accuracy: 0.9,
        steps: [{ id: 1, stage: 'classify', status }],
      } });
    } else {
      throw new Error(`Unexpected API request: ${request.url()}`);
    }
  });
  await page.goto('/tools/classifier');
  await page.getByRole('textbox', { name: 'Lyrics or text' }).fill('Browser test lyrics');
  await page.getByRole('button', { name: 'Run classify text' }).click();
  await expect(page).toHaveURL('/jobs/42');
  await expect(page.getByText('processing', { exact: true }).first()).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Result', exact: true })).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText('Human', { exact: true })).toBeVisible();
  await expect(page.getByText('90.0%', { exact: true })).toBeVisible();
});
