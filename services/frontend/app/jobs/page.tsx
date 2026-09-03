'use client';

import { useApiFetch } from '@/lib/api';
import { authClient } from '@/lib/auth-client';
import SignedOutPanel from '@/components/SignedOutPanel';
import { WorkspaceFrame, WorkspaceWindow } from '@/components/WorkspaceChrome';
import Link from 'next/link';
import { useCallback } from 'react';
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
  full: 'Full pipeline',
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
  const fetcher = useCallback(async (url: string) => {
    const response = await apiFetch(url);
    if (!response.ok) throw new Error('Unable to load jobs');
    return response.json();
  }, [apiFetch]);
  const { data, error } = useSWR<JobSummary[]>(session ? '/api/jobs' : null, fetcher, { refreshInterval: 4000 });

  if (isPending) return <main className="mx-auto max-w-6xl px-5 py-16 text-zinc-400">Loading…</main>;
  if (!session) return <SignedOutPanel
    title="My Jobs"
    label="Job history"
    heading="Sign in to view your jobs"
    description="Review the status and results of your pipeline and standalone tool runs."
  />;

  return (
    <WorkspaceFrame crumb="My Jobs">
      <WorkspaceWindow title="My Jobs">
        <p className="text-xs font-semibold uppercase tracking-[0.22em] text-amber-300">Processing history</p>
        <p className="mt-2 text-sm text-zinc-400">Every full pipeline and standalone service run in your workspace stays traceable here.</p>
      </WorkspaceWindow>

      <section className="y2k-window-stack" aria-label="Job history">
        {error && (
          <WorkspaceWindow title="Job History">
            <p className="text-red-200">Jobs could not be loaded.</p>
          </WorkspaceWindow>
        )}
        {!error && !data && (
          <WorkspaceWindow title="Job History">
            <p className="text-zinc-500">Loading jobs…</p>
          </WorkspaceWindow>
        )}
        {data && data.length === 0 && (
          <WorkspaceWindow title="No Jobs">
            <div className="py-8 text-center">
              <p className="text-zinc-400">No jobs in this view yet.</p>
              <Link href="/projects/new" className="y2k-button mt-5 inline-flex rounded-full px-5 py-2.5 text-sm font-semibold">Start a pipeline</Link>
            </div>
          </WorkspaceWindow>
        )}
        {data?.map((job) => (
          <WorkspaceWindow key={job.id} title={`Job #${job.id}`}>
            <Link href={`/jobs/${job.id}`} className="y2k-job-link group grid gap-3 transition sm:grid-cols-[1fr_auto] sm:items-center">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="truncate text-lg font-semibold text-white">{job.song_title || job.title || LABELS[job.job_type]}</h2>
                  <span className={`rounded-full border px-2.5 py-1 text-xs font-medium ${STATUS_STYLE[job.status] ?? STATUS_STYLE.queued}`}>{job.status}</span>
                  {job.cache_hit && <span className="rounded-full border border-violet-400/30 bg-violet-400/10 px-2.5 py-1 text-xs text-violet-200">cache hit</span>}
                </div>
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
          </WorkspaceWindow>
        ))}
      </section>
    </WorkspaceFrame>
  );
}
