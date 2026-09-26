'use client';

import { useApiFetch } from '@/lib/api';
import { authClient } from '@/lib/auth-client';
import SignedOutPanel from '@/components/SignedOutPanel';
import { WorkspaceFrame, WorkspacePanel } from '@/components/WorkspaceChrome';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { Suspense, useCallback } from 'react';
import useSWR from 'swr';
import { PIPELINE_STAGES, stageName, pipelineTimestamp } from '@/lib/pipeline';

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
  processing: 'border-blue-400/30 bg-blue-400/10 text-blue-200',
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
    description: 'A public history of completed jobs, showing their type, status, and processing stage.',
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
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(pipelineTimestamp(value)));
}

function selectedView(value: string | null): JobView {
  if (value === 'all' || value === 'mine') return value;
  return 'active';
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
  const { data, error } = useSWR<JobSummary[]>(!isPending && (session || view !== 'mine') ? [`/api/jobs?view=${view}`, session?.user.id ?? 'public'] : null, ([url]: [string, string]) => fetcher(url), {
    refreshInterval: view === 'active' ? 2000 : 4000,
  });

  if (isPending) return <main className="mx-auto max-w-6xl px-5 py-16 text-zinc-400">Loading…</main>;
  if (!session && view === 'mine') return <SignedOutPanel
    title={details.title}
    label="Job queue"
    heading={`Sign in to view ${view === 'mine' ? 'your jobs' : view === 'all' ? 'completed jobs' : 'the job queue'}`}
    description={details.description}
  />;

  const waiting = data?.filter((job) => job.status === 'queued').length ?? 0;
  const running = data?.filter((job) => job.status === 'processing').length ?? 0;

  return (
    <WorkspaceFrame crumb={details.title}>
      <header>
        <div className="flex flex-wrap items-center justify-between gap-4">
          <h1 className="text-2xl font-semibold">{details.title}</h1>
          <Link href={session ? '/projects/new' : '/sign-in'} className="button-primary px-4 py-2 text-sm">{session ? 'New job' : 'Sign in to submit'}</Link>
        </div>
        <p className="mt-2 text-sm text-zinc-400">{details.description}</p>
        <nav className="view-tabs mt-6" aria-label="Job views">
          <Link href="/jobs?view=active" aria-current={view === 'active' ? 'page' : undefined}>Queue</Link>
          {session && <Link href="/jobs?view=mine" aria-current={view === 'mine' ? 'page' : undefined}>My history</Link>}
          <Link href="/jobs?view=all" aria-current={view === 'all' ? 'page' : undefined}>All completed</Link>
        </nav>
      </header>

      {view === 'active' && data && !error && (
        <section className="mt-2" aria-label="Queue by stage">
          <div className="mb-3 flex flex-wrap justify-between gap-2 text-xs text-zinc-400">
            <p>{running} running · {waiting} queued</p>
            <p>Refreshes every 2 seconds · counts for the {data.length} loaded jobs</p>
          </div>
          <ol className="pipeline-stages">
            {PIPELINE_STAGES.map((stage, index) => {
              const stageJobs = data.filter((job) => job.current_stage === stage.key);
              const queued = stageJobs.filter((job) => job.status === 'queued').length;
              const processing = stageJobs.filter((job) => job.status === 'processing').length;
              return (
                <li key={stage.key} data-status={processing > 0 ? 'processing' : 'idle'}>
                  <p className="stage-number">0{index + 1} · {stage.service}</p>
                  <h2 className="stage-name">{stage.name}</h2>
                  <p className="stage-status">{processing} running</p>
                  <p className={`mt-1 text-sm ${queued > 0 ? 'text-amber-200' : 'text-zinc-500'}`}>{queued} queued</p>
                </li>
              );
            })}
          </ol>
          <p className="mt-3 text-xs text-zinc-500">Queued counts show where work is waiting.{session && ' Open one of your jobs to inspect its stage durations.'}</p>
        </section>
      )}

      {error ? (
        <WorkspacePanel title="Unable to load jobs"><p className="text-red-200">Jobs could not be loaded. Please try again.</p></WorkspacePanel>
      ) : !data ? (
        <p className="py-8 text-zinc-400">Loading jobs…</p>
      ) : data.length === 0 ? (
        <p className="panel px-5 py-10 text-center text-zinc-400">{details.empty}</p>
      ) : (
        <div className="panel overflow-x-auto">
          <table className="jobs-table">
            <caption className="sr-only">{details.title}</caption>
            <thead><tr><th scope="col">Job</th><th scope="col">Type</th><th scope="col">Status</th><th scope="col">Stage</th><th scope="col">Created</th></tr></thead>
            <tbody>
              {data.map((job) => {
                const isOwner = view === 'mine' || job.is_owner === true;
                const title = isOwner ? job.song_title || job.title || `Job #${job.id}` : `Job #${job.id}`;
                return (
                  <tr key={job.id}>
                    <td className="min-w-44 max-w-80">
                      {isOwner ? <Link href={`/jobs/${job.id}`} className="font-medium">{title}</Link> : <span>{title}</span>}
                      <p className="mt-1 text-xs text-zinc-500">#{job.id}{isOwner && job.cache_hit ? ' · cached' : ''}</p>
                      {isOwner && job.error && <p className="mt-1 text-xs text-red-200">{job.error}</p>}
                    </td>
                    <td className="whitespace-nowrap text-zinc-400">{LABELS[job.job_type]}</td>
                    <td><span className={`inline-block rounded border px-2 py-0.5 text-xs ${STATUS_STYLE[job.status] ?? STATUS_STYLE.queued}`}>{job.status}</span></td>
                    <td className="whitespace-nowrap text-zinc-400">{stageName(job.current_stage)}</td>
                    <td className="whitespace-nowrap text-xs text-zinc-500"><time dateTime={job.created_at}>{formatDate(job.created_at)}</time></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </WorkspaceFrame>
  );
}
