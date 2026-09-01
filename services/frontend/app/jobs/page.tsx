'use client';

import { useApiFetch } from '@/lib/api';
import { authClient } from '@/lib/auth-client';
import Link from 'next/link';
import { useCallback, useMemo, useState } from 'react';
import useSWR from 'swr';

type JobSummary = {
  id: number;
  job_type: 'full' | 'acousti' | 'demucs' | 'whisper' | 'classifier';
  status: string;
  current_stage: string | null;
  title: string;
  song_id: number | null;
  song_title?: string | null;
  cache_hit: boolean;
  error?: string | null;
  created_at: string;
};

const LABELS: Record<JobSummary['job_type'], string> = {
  full: 'Full project',
  acousti: 'Acousti',
  demucs: 'Demucs',
  whisper: 'Whisper',
  classifier: 'Classifier',
};

const STATUS_STYLE: Record<string, string> = {
  queued: 'border-zinc-500/30 bg-zinc-500/10 text-zinc-300',
  processing: 'border-amber-400/30 bg-amber-400/10 text-amber-200',
  completed: 'border-emerald-400/30 bg-emerald-400/10 text-emerald-200',
  failed: 'border-red-400/30 bg-red-400/10 text-red-200',
  cancelled: 'border-zinc-500/30 bg-zinc-500/10 text-zinc-400',
};

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value));
}

export default function JobsPage() {
  const { data: session, isPending } = authClient.useSession();
  const apiFetch = useApiFetch();
  const [filter, setFilter] = useState<'all' | 'full' | 'tools'>('all');
  const fetcher = useCallback(async (url: string) => {
    const response = await apiFetch(url);
    if (!response.ok) throw new Error('Unable to load jobs');
    return response.json();
  }, [apiFetch]);
  const { data, error } = useSWR<JobSummary[]>(session ? '/api/jobs' : null, fetcher, { refreshInterval: 4000 });
  const jobs = useMemo(() => (data ?? []).filter((job) => {
    if (filter === 'full') return job.job_type === 'full';
    if (filter === 'tools') return job.job_type !== 'full';
    return true;
  }), [data, filter]);

  if (isPending) return <main className="mx-auto max-w-6xl px-5 py-16 text-zinc-400">Loading…</main>;
  if (!session) {
    return (
      <main className="mx-auto max-w-xl px-5 py-24 text-center">
        <h1 className="text-3xl font-semibold text-white">Sign in to view your jobs</h1>
        <Link href="/sign-in" className="mt-6 inline-flex rounded-full bg-white px-5 py-2.5 text-sm font-semibold text-zinc-950">Sign in</Link>
      </main>
    );
  }

  return (
    <main className="mx-auto min-h-[calc(100vh-9rem)] w-full max-w-6xl px-5 py-12 sm:px-8 sm:py-16">
      <Link href="/" className="text-sm text-zinc-500 transition hover:text-white">← Workspace</Link>
      <div className="mt-8 flex flex-col gap-6 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.22em] text-amber-300">Processing history</p>
          <h1 className="mt-4 text-4xl font-semibold tracking-[-0.035em] text-white">My jobs</h1>
          <p className="mt-3 text-zinc-400">Every full project and standalone service run stays traceable here.</p>
        </div>
        <div className="flex rounded-xl border border-white/10 bg-white/[0.035] p-1">
          {(['all', 'full', 'tools'] as const).map((value) => (
            <button
              key={value}
              type="button"
              onClick={() => setFilter(value)}
              className={`rounded-lg px-4 py-2 text-sm capitalize transition ${filter === value ? 'bg-white text-zinc-950' : 'text-zinc-400 hover:text-white'}`}
            >
              {value}
            </button>
          ))}
        </div>
      </div>

      <section className="mt-9 space-y-3" aria-label="Job history">
        {error && <p className="rounded-2xl border border-red-400/25 bg-red-400/10 p-5 text-red-200">Jobs could not be loaded.</p>}
        {!error && !data && <p className="text-zinc-500">Loading jobs…</p>}
        {data && jobs.length === 0 && (
          <div className="rounded-3xl border border-dashed border-white/10 px-6 py-14 text-center">
            <p className="text-zinc-400">No jobs in this view yet.</p>
            <Link href="/projects/new" className="mt-5 inline-flex rounded-full bg-white px-5 py-2.5 text-sm font-semibold text-zinc-950">Start a project</Link>
          </div>
        )}
        {jobs.map((job) => (
          <Link
            key={job.id}
            href={`/jobs/${job.id}`}
            className="group grid gap-4 rounded-2xl border border-white/10 bg-white/[0.035] p-5 transition hover:border-white/20 hover:bg-white/[0.06] sm:grid-cols-[1fr_auto] sm:items-center"
          >
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs font-semibold uppercase tracking-[0.16em] text-zinc-500">Job #{job.id}</span>
                <span className={`rounded-full border px-2.5 py-1 text-xs font-medium ${STATUS_STYLE[job.status] ?? STATUS_STYLE.queued}`}>{job.status}</span>
                {job.cache_hit && <span className="rounded-full border border-violet-400/30 bg-violet-400/10 px-2.5 py-1 text-xs text-violet-200">cache hit</span>}
              </div>
              <h2 className="mt-3 truncate text-lg font-semibold text-white">{job.song_title || job.title || LABELS[job.job_type]}</h2>
              <p className="mt-1 text-sm text-zinc-400">
                {LABELS[job.job_type]}
                {job.current_stage ? ` · ${job.current_stage}` : ''}
                {job.error ? ` · ${job.error}` : ''}
              </p>
            </div>
            <div className="flex items-center gap-5 text-sm text-zinc-500">
              <time dateTime={job.created_at}>{formatDate(job.created_at)}</time>
              <span className="text-white transition group-hover:translate-x-1" aria-hidden="true">→</span>
            </div>
          </Link>
        ))}
      </section>
    </main>
  );
}
