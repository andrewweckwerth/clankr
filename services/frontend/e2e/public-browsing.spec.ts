import { expect, test } from '@playwright/test';

test('visitor browses the queue, completed history, catalog, and full song result', async ({ page }) => {
  const song = { id: 7, title: 'Example song', artist: 'Example artist', lyrics: 'Example transcript', classification: 'Human', accuracy: 0.9, file_path: 'stems/example.wav' };
  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname === '/api/auth/get-session') {
      await route.fulfill({ json: null });
    } else if (url.pathname === '/api/jobs') {
      const completed = url.searchParams.get('view') === 'all';
      expect(['active', 'all']).toContain(url.searchParams.get('view'));
      await route.fulfill({ json: [{ id: 42, job_type: 'full', status: completed ? 'completed' : 'processing', current_stage: completed ? null : 'demucs', created_at: '2026-09-24T12:00:00', is_owner: false }] });
    } else if (url.pathname === '/api/songs') {
      await route.fulfill({ json: [song] });
    } else if (url.pathname === '/api/songs/7') {
      await route.fulfill({ json: song });
    } else if (url.pathname === '/api/songs/7/artifact') {
      await route.fulfill({ contentType: 'audio/wav', headers: { 'Content-Disposition': 'attachment; filename="example.wav"' }, body: 'synthetic-stem' });
    } else {
      throw new Error(`Unexpected guest API request: ${url.pathname}`);
    }
  });
  await page.goto('/jobs');
  await expect(page.getByRole('heading', { name: 'Job Queue', exact: true })).toBeVisible();
  await expect(page.getByRole('cell', { name: 'processing', exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: 'My history', exact: true })).toHaveCount(0);
  await expect(page.getByRole('link', { name: 'Job #42', exact: true })).toHaveCount(0);
  await page.getByRole('link', { name: 'All completed', exact: true }).click();
  await expect(page.getByRole('cell', { name: 'completed', exact: true })).toBeVisible();
  await page.getByRole('navigation', { name: 'Main navigation' }).getByRole('link', { name: 'Songs', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'All Songs', exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: 'My songs', exact: true })).toHaveCount(0);
  await expect(page.getByRole('button', { name: /Remove/ })).toHaveCount(0);
  await page.getByRole('link', { name: /Example song/ }).click();
  await expect(page).toHaveURL('/songs/7');
  await expect(page.getByRole('heading', { name: 'Example song', exact: true, level: 1 })).toBeVisible();
  await expect(page.getByText('Example transcript', { exact: true })).toBeVisible();
  const download = page.waitForEvent('download');
  await page.getByRole('link', { name: 'Download vocal stem' }).click();
  expect((await download).suggestedFilename()).toBe('example.wav');
  await page.goto('/songs?view=mine');
  await expect(page.getByRole('heading', { name: 'Sign in to view your songs' })).toBeVisible();
  await page.goto('/jobs?view=mine');
  await expect(page.getByRole('heading', { name: 'Sign in to view your jobs' })).toBeVisible();
});
