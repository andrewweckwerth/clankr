'use client';

import { useApiFetch } from '@/lib/api';
import { useRouter } from 'next/navigation';
import { useState } from 'react';
import PipelineOverview from '@/components/PipelineOverview';

export type JobType = 'full' | 'acousti' | 'demucs' | 'whisper' | 'classifier';

const JOB_DETAILS: Record<JobType, { title: string; description: string; input: 'audio' | 'text' }> = {
  full: {
    title: 'Run pipeline',
    description: 'Submit audio, follow each processing stage, and inspect the result.',
    input: 'audio',
  },
  acousti: {
    title: 'Identify a song',
    description: 'Generate its fingerprint and look for recording details or an existing Clankr result.',
    input: 'audio',
  },
  demucs: {
    title: 'Split the vocals',
    description: 'Run Demucs by itself and download the isolated vocal stem.',
    input: 'audio',
  },
  whisper: {
    title: 'Transcribe audio',
    description: 'Run Whisper directly on the audio you provide and return its English transcript.',
    input: 'audio',
  },
  classifier: {
    title: 'Classify text',
    description: 'Send pasted lyrics directly to the classifier for an AI or human assessment.',
    input: 'text',
  },
};

function errorMessage(payload: unknown, fallback: string) {
  if (!payload || typeof payload !== 'object') return fallback;
  const record = payload as Record<string, unknown>;
  if (typeof record.error === 'string') return record.error;
  if (typeof record.detail === 'string') return record.detail;
  if (record.detail && typeof record.detail === 'object') {
    const detail = record.detail as Record<string, unknown>;
    if (typeof detail.error === 'string') return detail.error;
  }
  return fallback;
}

export default function AnalysisForm({ jobType }: { jobType: JobType }) {
  const apiFetch = useApiFetch();
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [lyrics, setLyrics] = useState('');
  const [title, setTitle] = useState('');
  const [artist, setArtist] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const details = JOB_DETAILS[jobType];

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    if (details.input === 'audio' && !file) {
      setError('Choose an audio file first.');
      return;
    }
    if (details.input === 'text' && !lyrics.trim()) {
      setError('Paste some text first.');
      return;
    }

    const formData = new FormData();
    formData.set('mode', jobType === 'full' ? 'full' : 'standalone');
    if (jobType !== 'full') formData.set('service', jobType);
    if (file) formData.set('audio', file);
    if (lyrics.trim()) formData.set('lyrics', lyrics.trim());
    if (title.trim()) formData.set('title', title.trim());
    if (artist.trim()) formData.set('artist', artist.trim());

    setSubmitting(true);
    try {
      const response = await apiFetch('/api/analyze', { method: 'POST', body: formData });
      const payload = await response.json().catch(() => null);
      if (!response.ok || !payload?.job_id) {
        setError(errorMessage(payload, 'Clankr could not create this job.'));
        return;
      }
      router.push(`/jobs/${payload.job_id}`);
    } catch {
      setError('Clankr could not reach the processing service.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="panel-stack">
      <section className="panel p-7 sm:p-9">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-zinc-400">
            {jobType === 'full' ? 'Full pipeline' : 'Standalone tool'}
          </p>
          <h1 className="mt-3 text-2xl font-semibold tracking-tight text-white">{details.title}</h1>
          <p className="mt-3 max-w-lg text-sm leading-6 text-zinc-400">{details.description}</p>

          {jobType === 'full' ? (
            <div className="mt-6"><PipelineOverview /></div>
          ) : (
            <div className="mt-8 rounded-lg border border-white/10 bg-black/20 p-4 text-sm leading-6 text-zinc-400">
              This creates a Job, not a new Song. An Acousti cache hit can still add an existing Song to your library.
            </div>
          )}
        </div>
      </section>

      <form onSubmit={handleSubmit} className="panel space-y-5 p-7 sm:p-9">
        {jobType === 'full' && (
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="space-y-2 text-sm text-zinc-300">
              <span>Title <span className="text-zinc-600">(optional)</span></span>
              <input value={title} onChange={(event) => setTitle(event.target.value)} className="auth-input" placeholder="Filled by Acousti when possible" />
            </label>
            <label className="space-y-2 text-sm text-zinc-300">
              <span>Artist <span className="text-zinc-600">(optional)</span></span>
              <input value={artist} onChange={(event) => setArtist(event.target.value)} className="auth-input" placeholder="Filled by Acousti when possible" />
            </label>
          </div>
        )}

        {details.input === 'audio' ? (
          <label className="block space-y-2 text-sm text-zinc-300">
            <span>Audio file</span>
            <span className="flex min-h-36 cursor-pointer flex-col items-center justify-center rounded-lg border border-dashed border-white/15 bg-black/20 px-5 text-center transition hover:border-blue-300/50 focus-within:outline-2 focus-within:outline-blue-300">
              <span className="text-sm font-medium text-white">{file ? file.name : 'Choose an MP3 or WAV file'}</span>
              <span className="mt-1 text-xs text-zinc-500">The original upload stays attached to this job.</span>
              <input
                type="file"
                accept="audio/mpeg,audio/wav,.mp3,.wav"
                onChange={(event) => setFile(event.target.files?.[0] ?? null)}
                className="sr-only"
              />
            </span>
          </label>
        ) : (
          <label className="block space-y-2 text-sm text-zinc-300">
            <span>Lyrics or text</span>
            <textarea
              value={lyrics}
              onChange={(event) => setLyrics(event.target.value)}
              className="auth-input min-h-56 resize-y"
              placeholder="Paste the text you want to classify…"
            />
          </label>
        )}

        {jobType === 'full' && (
          <p className="text-sm leading-6 text-zinc-300">
            Every completed full-pipeline song joins the public catalog. Anyone can view its title, artist, transcript, and classification, and download its vocal stem.
          </p>
        )}

        {error && <p className="rounded-md border border-red-400/25 bg-red-400/10 px-4 py-3 text-sm text-red-200">{error}</p>}

        <button
          type="submit"
          disabled={submitting}
          className="button-primary inline-flex w-full items-center justify-center rounded-md px-5 py-3 text-sm font-semibold disabled:cursor-not-allowed"
        >
          {submitting ? 'Creating job…' : jobType === 'full' ? 'Run pipeline' : `Run ${details.title.toLowerCase()}`}
        </button>
      </form>
    </div>
  );
}
