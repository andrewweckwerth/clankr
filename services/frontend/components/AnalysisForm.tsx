'use client';

import { useApiFetch } from '@/lib/api';
import { useRouter } from 'next/navigation';
import { useState } from 'react';

export type JobType = 'full' | 'acousti' | 'demucs' | 'whisper' | 'classifier';

const JOB_DETAILS: Record<JobType, { title: string; description: string; input: 'audio' | 'text' }> = {
  full: {
    title: 'Detect AI-generated lyrics',
    description: 'Identify the recording, isolate and transcribe its vocals, then assess whether the lyrics show signs of AI generation.',
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

const FULL_STAGES = [
  ['01', 'Identify', 'Fingerprint the recording and check the global cache'],
  ['02', 'Isolate vocals', 'Demucs extracts the vocal stem for transcription'],
  ['03', 'Transcribe lyrics', 'Whisper turns the vocal stem into text'],
  ['04', 'Assess authorship', 'The classifier checks the lyrics for signs of AI generation'],
];

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
    <div className="y2k-analysis-layout">
      <section className="y2k-panel-window y2k-analysis-summary p-7 sm:p-9" data-window-title={jobType === 'full' ? 'Pipeline Overview' : details.title}>
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-violet-300">
            {jobType === 'full' ? 'AI lyric detection workflow' : 'Standalone tool'}
          </p>
          <h2 className="mt-4 text-3xl font-semibold tracking-tight text-white">{details.title}</h2>
          <p className="mt-3 max-w-lg text-sm leading-6 text-zinc-400">{details.description}</p>

          {jobType === 'full' ? (
            <ol className="mt-6 grid gap-x-8 gap-y-3 sm:grid-cols-2">
              {FULL_STAGES.map(([number, name, description]) => (
                <li key={number} className="flex gap-4">
                  <span className="font-mono text-xs text-violet-300">{number}</span>
                  <div>
                    <p className="text-sm font-medium text-white">{name}</p>
                    <p className="mt-0.5 text-xs leading-5 text-zinc-500">{description}</p>
                  </div>
                </li>
              ))}
            </ol>
          ) : (
            <div className="mt-8 rounded-2xl border border-white/10 bg-black/20 p-4 text-sm leading-6 text-zinc-400">
              This creates a Job, not a new Song. An Acousti cache hit can still add an existing Song to your library.
            </div>
          )}
        </div>
      </section>

      <form onSubmit={handleSubmit} className="y2k-panel-window y2k-analysis-form space-y-5 p-7 sm:p-9" data-window-title={details.input === 'audio' ? 'Upload Audio' : 'Paste Text'}>
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
            <span className="flex min-h-36 cursor-pointer flex-col items-center justify-center rounded-2xl border border-dashed border-white/15 bg-black/20 px-5 text-center transition hover:border-violet-300/50 hover:bg-violet-500/[0.06]">
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

        {error && <p className="rounded-xl border border-red-400/25 bg-red-400/10 px-4 py-3 text-sm text-red-200">{error}</p>}

        <button
          type="submit"
          disabled={submitting}
          className="y2k-button inline-flex w-full items-center justify-center rounded-xl px-5 py-3 text-sm font-semibold disabled:cursor-not-allowed"
        >
          {submitting ? 'Creating job…' : jobType === 'full' ? 'Check lyrics for AI generation' : `Run ${details.title.toLowerCase()}`}
        </button>
      </form>
    </div>
  );
}
