'use client';

import { useApiFetch } from '@/lib/api';
import { authClient } from '@/lib/auth-client';
import SignedOutPanel from '@/components/SignedOutPanel';
import { WorkspaceFrame, WorkspaceWindow } from '@/components/WorkspaceChrome';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { Suspense, useCallback } from 'react';
import useSWR from 'swr';

type JobView = 'mine' | 'all' | 'active';

type JobSummary = {
  id: number;
  job_type: 'full' | 'acousti' | 'demucs' | 'whisper' | 'classifier';
  status: string;
  current_stage: string | null;
  title?: string | null;
  artist?: string | null;
  song_id?: number | null;
  song_title?: string | null;
  cache_hit: boolean;
  error?: string | null;
  created_at: string;
  is_owner?: boolean;
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

const VIEW_DETAILS: Record<JobView, { title: string; kicker: string; description: string; empty: string }> = {
  mine: {
    title: 'My Jobs',
    kicker: 'Processing history',
    description: 'Completed, failed, and cancelled jobs from your workspace stay traceable here.',
    empty: 'No finished jobs in this view yet.',
  },
  all: {
    title: 'All Jobs',
    kicker: 'Completed work',
    description: 'A shared history of completed jobs. Other users’ work is limited to its operational summary.',
    empty: 'No completed jobs have been recorded yet.',
  },
  active: {
    title: 'Job Queue',
    kicker: 'Live job queue',
    description: 'Every job that is queued or processing. This view refreshes automatically as workers claim and finish stages.',
    empty: 'Nothing is queued or processing right now.',
  },
};

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value));
}

function selectedView(value: string | null): JobView {
  if (value === 'all' || value === 'active') return value;
  return 'mine';
}

export default function JobsPage() {
  return (
    <Suspense fallback={<main className="mx-auto max-w-6xl px-5 py-16 text-zinc-400">Loading…</main>}>
      <JobsContent />
    </Suspense>
  );
}

function JobsContent() {
  const { data: session, isPending } = authClient.useSession();
  const searchParams = useSearchParams();
  const view = selectedView(searchParams.get('view'));
  const details = VIEW_DETAILS[view];
  const apiFetch = useApiFetch();
  const fetcher = useCallback(async (url: string) => {
    const response = await apiFetch(url);
    if (!response.ok) throw new Error('Unable to load jobs');
    return response.json();
  }, [apiFetch]);
  const { data, error } = useSWR<JobSummary[]>(session ? `/api/jobs?view=${view}` : null, fetcher, {
    refreshInterval: view === 'active' ? 2000 : 4000,
  });

  if (isPending) return <main className="mx-auto max-w-6xl px-5 py-16 text-zinc-400">Loading…</main>;
  if (!session) return <SignedOutPanel
    title={details.title}
    label="Job queue"
    heading={`Sign in to view ${view === 'mine' ? 'your jobs' : view === 'all' ? 'completed jobs' : 'the job queue'}`}
    description={details.description}
  />;

  return (
    <WorkspaceFrame crumb={details.title}>
      <WorkspaceWindow title={details.title}>
        <p className="text-xs font-semibold uppercase tracking-[0.22em] text-amber-300">{details.kicker}</p>
        <p className="mt-2 text-sm text-zinc-400">{details.description}</p>
      </WorkspaceWindow>

      <section className="y2k-window-stack" aria-label={details.title}>
        {error && (
          <WorkspaceWindow title={details.title}>
            <p className="text-red-200">Jobs could not be loaded.</p>
          </WorkspaceWindow>
        )}
        {!error && !data && (
          <WorkspaceWindow title={details.title}>
            <p className="text-zinc-500">Loading jobs…</p>
          </WorkspaceWindow>
        )}
        {data && data.length === 0 && (
          <WorkspaceWindow title={view === 'mine' ? 'No Jobs' : details.title}>
            <div className="py-8 text-center">
              <p className="text-zinc-400">{details.empty}</p>
              {view === 'mine' && <Link href="/projects/new" className="y2k-button mt-5 inline-flex rounded-full px-5 py-2.5 text-sm font-semibold">Start a pipeline</Link>}
            </div>
          </WorkspaceWindow>
        )}
        {data?.map((job) => {
          const isOwner = view === 'mine' || job.is_owner === true;
          const jobTitle = isOwner ? job.song_title || job.title || LABELS[job.job_type] : `Job #${job.id}`;
          const jobSummary = (
            <div className={`grid gap-3 sm:grid-cols-[1fr_auto] sm:items-center ${isOwner ? 'group' : ''}`}>
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="truncate text-lg font-semibold text-white">{jobTitle}</h2>
                  <span className={`rounded-full border px-2.5 py-1 text-xs font-medium ${STATUS_STYLE[job.status] ?? STATUS_STYLE.queued}`}>{job.status}</span>
                  {isOwner && job.cache_hit && <span className="rounded-full border border-violet-400/30 bg-violet-400/10 px-2.5 py-1 text-xs text-violet-200">cache hit</span>}
                </div>
                <p className="mt-1 text-sm text-zinc-400">
                  {LABELS[job.job_type]}
                  {job.current_stage ? ` · ${job.current_stage}` : ''}
                  {isOwner && job.error ? ` · ${job.error}` : ''}
                </p>
              </div>
              <div className="flex items-center gap-5 text-sm text-zinc-500">
                <time dateTime={job.created_at}>{formatDate(job.created_at)}</time>
                {isOwner && <span className="text-white transition group-hover:translate-x-1" aria-hidden="true">→</span>}
              </div>
            </div>
          );

          return (
            <WorkspaceWindow key={job.id} title={`Job #${job.id}`}>
              {isOwner ? <Link href={`/jobs/${job.id}`} className="y2k-job-link block transition">{jobSummary}</Link> : jobSummary}
            </WorkspaceWindow>
          );
        })}
      </section>
    </WorkspaceFrame>
  );
}
