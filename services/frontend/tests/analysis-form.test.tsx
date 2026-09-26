import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, expect, test, vi } from 'vitest';
import AnalysisForm from '@/components/AnalysisForm';

const { push } = vi.hoisted(() => ({ push: vi.fn() }));
vi.mock('next/navigation', () => ({ useRouter: () => ({ push }) }));

let fetcher: ReturnType<typeof vi.fn>;
beforeEach(() => {
  fetcher = vi.fn();
  vi.stubGlobal('fetch', fetcher);
});

test.each(['full', 'classifier'] as const)('%s requires its input before sending a request', async (jobType) => {
  const user = userEvent.setup();
  render(<AnalysisForm jobType={jobType} />);
  await user.click(screen.getByRole('button'));
  expect(screen.getByText(jobType === 'full' ? 'Choose an audio file first.' : 'Paste some text first.')).toBeVisible();
  expect(fetcher).not.toHaveBeenCalled();
});

test('text submission sends trimmed lyrics and navigates to the returned job', async () => {
  fetcher.mockResolvedValue(Response.json({ job_id: 42 }));
  const user = userEvent.setup();
  render(<AnalysisForm jobType="classifier" />);
  await user.type(screen.getByRole('textbox', { name: 'Lyrics or text' }), '  test lyrics  ');
  await user.click(screen.getByRole('button'));
  await waitFor(() => expect(push).toHaveBeenCalledWith('/jobs/42'));
  const [url, options] = fetcher.mock.calls[0];
  expect(url).toBe('/api/analyze');
  expect(options.method).toBe('POST');
  expect(options.credentials).toBe('same-origin');
  const form = options.body as FormData;
  expect(Object.fromEntries(form.entries())).toEqual({ mode: 'standalone', service: 'classifier', lyrics: 'test lyrics' });
});

test('full submission sends the upload and optional metadata', async () => {
  fetcher.mockResolvedValue(Response.json({ job_id: 7 }));
  const user = userEvent.setup();
  render(<AnalysisForm jobType="full" />);
  expect(screen.getByText(/Every completed full-pipeline song joins the public catalog/)).toBeVisible();
  const file = new File(['synthetic'], 'input.wav', { type: 'audio/wav' });
  await user.upload(screen.getByLabelText(/Audio file/), file);
  await user.type(screen.getByRole('textbox', { name: /Title/ }), '  Song  ');
  await user.type(screen.getByRole('textbox', { name: /Artist/ }), '  Artist  ');
  await user.click(screen.getByRole('button', { name: 'Run pipeline' }));
  await waitFor(() => expect(push).toHaveBeenCalledWith('/jobs/7'));
  const form = fetcher.mock.calls[0][1].body as FormData;
  expect(form.get('mode')).toBe('full');
  expect(form.has('service')).toBe(false);
  expect(form.get('title')).toBe('Song');
  expect(form.get('artist')).toBe('Artist');
  expect(form.get('audio')).toBe(file);
});

test.each([
  [{ detail: { error: 'Daily analysis limit reached' } }, 429, 'Daily analysis limit reached'],
  [{ error: 'Storage unavailable' }, 500, 'Storage unavailable'],
  [{ success: true }, 200, 'Clankr could not create this job.'],
] as const)('API failure %j leaves the form usable', async (body, status, message) => {
  fetcher.mockResolvedValue(Response.json(body, { status }));
  const user = userEvent.setup();
  render(<AnalysisForm jobType="classifier" />);
  await user.type(screen.getByRole('textbox'), 'text');
  await user.click(screen.getByRole('button'));
  expect(await screen.findByText(message)).toBeVisible();
  expect(screen.getByRole('button')).toBeEnabled();
  expect(push).not.toHaveBeenCalled();
});

test('network failure can be retried', async () => {
  fetcher.mockRejectedValueOnce(new TypeError('offline')).mockResolvedValueOnce(Response.json({ job_id: 9 }));
  const user = userEvent.setup();
  render(<AnalysisForm jobType="classifier" />);
  await user.type(screen.getByRole('textbox'), 'text');
  await user.click(screen.getByRole('button'));
  expect(await screen.findByText('Clankr could not reach the processing service.')).toBeVisible();
  await user.click(screen.getByRole('button'));
  await waitFor(() => expect(push).toHaveBeenCalledWith('/jobs/9'));
});

test('pending submission prevents duplicate requests', async () => {
  let resolve!: (response: Response) => void;
  fetcher.mockReturnValue(new Promise<Response>((done) => { resolve = done; }));
  const user = userEvent.setup();
  render(<AnalysisForm jobType="classifier" />);
  await user.type(screen.getByRole('textbox'), 'text');
  await user.click(screen.getByRole('button'));
  const button = screen.getByRole('button', { name: 'Creating job…' });
  expect(button).toBeDisabled();
  await user.click(button);
  expect(fetcher).toHaveBeenCalledTimes(1);
  await act(async () => resolve(Response.json({ job_id: 8 })));
  expect(push).toHaveBeenCalledWith('/jobs/8');
});
