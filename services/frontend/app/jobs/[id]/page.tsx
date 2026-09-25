'use client';

import { useApiFetch } from '@/lib/api';
import { authClient } from '@/lib/auth-client';
import { WorkspaceFrame } from '@/components/WorkspaceChrome';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { useCallback, useEffect, useState } from 'react';
import useSWR from 'swr';
import { pipelineTimestamp } from '@/lib/pipeline';

type JobStep = {
  id: number;
  stage: string;
  status: string;
  error?: string | null;
  result?: Record<string, unknown> | null;
  started_at?: string | null;
  completed_at?: string | null;
};

type Job = {
  id: number;
  job_type: 'full' | 'acousti' | 'demucs' | 'whisper' | 'classifier';
  status: string;
  current_stage: string | null;
  title: string;
  artist?: string | null;
  lyrics?: string | null;
  classification?: string | null;
  accuracy?: number | string | null;
  fingerprint?: string | null;
  duration?: number | null;
  song_id?: number | null;
  cache_hit: boolean;
  error?: string | null;
  created_at: string;
  completed_at?: string | null;
  steps: JobStep[];
};

const JOB_LABELS: Record<Job['job_type'], string> = {
  full: 'Full pipeline',
  acousti: 'Acousti identification',
  demucs: 'Demucs vocal split',
  whisper: 'Whisper transcription',
  classifier: 'Text classification',
};

const STEP_LABELS: Record<string, string> = {
  identify: 'Identify',
  demucs: 'Separate vocals',
  whisper: 'Transcribe',
  classify: 'Classify',
};

function runDuration(step: JobStep, now: number | null) {
  if (!step.started_at) return null;
  const end = step.completed_at ? pipelineTimestamp(step.completed_at) : step.status === 'processing' ? now : null;
  if (end == null) return null;
  const seconds = Math.max(0, Math.floor((end - pipelineTimestamp(step.started_at)) / 1000));
  if (!Number.isFinite(seconds)) return null;
  return seconds < 60 ? `${seconds}s` : `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
}

const TERMINAL = new Set(['completed', 'failed', 'cancelled']);

// Keep this callback stable: the elapsed-time clock rerenders every second.
// Recreating it would restart SWR's two-second polling timer on every tick.
function jobRefreshInterval(latest: Job | undefined) {
  return latest && TERMINAL.has(latest.status) ? 0 : 2000;
}

export default function JobDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const apiFetch = useApiFetch();
  const { data: session, isPending } = authClient.useSession();
  const [actionError, setActionError] = useState<string | null>(null);
  const [acting, setActing] = useState(false);
  const [now, setNow] = useState<number | null>(null);
  const fetcher = useCallback(async (url: string) => {
    const response = await apiFetch(url);
    if (!response.ok) throw new Error('Unable to load job');
    return response.json();
  }, [apiFetch]);
  const { data: job, error } = useSWR<Job>(session ? `/api/jobs/${params.id}` : null, fetcher, {
    refreshInterval: jobRefreshInterval,
  });

  useEffect(() => {
    if (job?.status !== 'processing') return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [job?.status]);

  const retry = async () => {
    setActing(true);
    setActionError(null);
    try {
      const response = await apiFetch(`/api/jobs/${params.id}/retry`, { method: 'POST' });
      const payload = await response.json().catch(() => null);
      if (!response.ok || !payload?.job_id) throw new Error(payload?.detail || 'Retry failed');
      router.push(`/jobs/${payload.job_id}`);
    } catch (retryError) {
      setActionError(retryError instanceof Error ? retryError.message : 'Retry failed');
    } finally {
      setActing(false);
    }
  };

  const remove = async () => {
    if (!window.confirm('Delete this job and its job-owned files?')) return;
    setActing(true);
    setActionError(null);
    try {
      const response = await apiFetch(`/api/jobs/${params.id}`, { method: 'DELETE' });
      if (!response.ok) throw new Error('The job could not be deleted');
      router.push('/jobs?view=mine');
    } catch (deleteError) {
      setActionError(deleteError instanceof Error ? deleteError.message : 'Delete failed');
      setActing(false);
    }
  };

  if (isPending || (session && !job && !error)) return <main className="mx-auto max-w-5xl px-5 py-16 text-zinc-400">Loading job…</main>;
  if (!session) return <main className="mx-auto max-w-xl px-5 py-24 text-center text-white">Sign in to view this job.</main>;
  if (error || !job) return <main className="mx-auto max-w-xl px-5 py-24 text-center text-red-200">This job could not be found.</main>;

  const accuracy = job.accuracy == null ? null : Number(job.accuracy);

  return (
    <WorkspaceFrame crumb={`Job #${job.id}`}>
      <header className="panel rounded-lg border border-white/10 bg-white/[0.045] p-7 sm:p-9">
        <div className="flex flex-col gap-6 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs font-semibold uppercase tracking-[0.18em] text-zinc-500">Job #{job.id}</span>
              <span className="rounded-full border border-white/10 bg-white/[0.06] px-2.5 py-1 text-xs capitalize text-zinc-300">{job.status}</span>
              {job.cache_hit && <span className="rounded-full border border-violet-400/30 bg-violet-400/10 px-2.5 py-1 text-xs text-violet-200">global cache hit</span>}
            </div>
            <h1 className="mt-4 text-3xl font-semibold tracking-tight text-white">{JOB_LABELS[job.job_type]}</h1>
            <p className="mt-2 text-zinc-400">{job.title}{job.artist ? ` · ${job.artist}` : ''}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            {job.status === 'failed' && (
              <button type="button" onClick={retry} disabled={acting} className="button-primary rounded-md px-4 py-2.5 text-sm font-semibold">Run again</button>
            )}
            {TERMINAL.has(job.status) && (
              <button type="button" onClick={remove} disabled={acting} className="button-danger rounded-md px-4 py-2.5 text-sm font-medium disabled:opacity-60">Delete job</button>
            )}
          </div>
        </div>
        {job.error && <p className="mt-6 rounded-md border border-red-400/25 bg-red-400/10 px-4 py-3 text-sm text-red-200">{job.error}</p>}
        {actionError && <p className="mt-4 text-sm text-red-200">{actionError}</p>}
      </header>

      <section className="panel rounded-lg border border-white/10 bg-white/[0.035] p-7 sm:p-9">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-lg font-semibold text-white">Stage progress</h2>
          <Link href="/jobs?view=active" className="text-sm text-blue-300 hover:underline">View queue →</Link>
        </div>
        <ol className="pipeline-stages mt-5">
          {job.steps.map((step, index) => {
            const skipped = job.cache_hit && step.status === 'cancelled';
            const duration = runDuration(step, now);
            return (
              <li key={step.id} data-status={step.status}>
                <p className="stage-number">0{index + 1}</p>
                <h3 className="stage-name">{STEP_LABELS[step.stage] || step.stage}</h3>
                <p className="stage-status capitalize">{skipped ? 'skipped · cached' : step.status}</p>
                {duration && <p className="mt-2 font-mono text-xs text-zinc-400">{duration} {step.status === 'processing' ? 'elapsed' : 'processing time'}</p>}
                {step.error && <p className="mt-2 text-xs leading-5 text-red-200">{step.error}</p>}
              </li>
            );
          })}
        </ol>
      </section>

      {job.status === 'completed' && (
        <section className="panel rounded-lg border border-white/10 bg-white/[0.035] p-7 sm:p-9">
          <h2 className="text-lg font-semibold text-white">Result</h2>
          {job.song_id ? (
            <div className="mt-5">
              <p className="max-w-2xl text-sm leading-6 text-zinc-400">{job.cache_hit ? 'Clankr found this fingerprint in the global cache and added the existing Song to your library.' : 'The full pipeline completed and created a canonical Song.'}</p>
              <Link href={`/songs/${job.song_id}`} className="button-primary mt-5 inline-flex rounded-md px-5 py-2.5 text-sm font-semibold">Open song result</Link>
            </div>
          ) : job.job_type === 'demucs' ? (
            <div className="mt-5">
              <p className="text-sm text-zinc-400">The isolated vocal stem is ready.</p>
              <a href={`/api/jobs/${job.id}/artifact`} className="button-primary mt-5 inline-flex rounded-md px-5 py-2.5 text-sm font-semibold">Download vocal stem</a>
            </div>
          ) : job.job_type === 'whisper' ? (
            <div className="mt-5 whitespace-pre-wrap rounded-lg border border-white/10 bg-black/20 p-5 text-sm leading-7 text-zinc-200">{job.lyrics || 'No transcript was returned.'}</div>
          ) : job.job_type === 'classifier' ? (
            <div className="mt-5 grid gap-4 sm:grid-cols-2">
              <div className="rounded-lg border border-white/10 bg-black/20 p-5"><p className="text-xs uppercase tracking-[0.18em] text-zinc-500">Classification</p><p className="mt-2 text-2xl font-semibold text-white">{job.classification || 'Unknown'}</p></div>
              <div className="rounded-lg border border-white/10 bg-black/20 p-5"><p className="text-xs uppercase tracking-[0.18em] text-zinc-500">Confidence</p><p className="mt-2 text-2xl font-semibold text-white">{accuracy != null && Number.isFinite(accuracy) ? `${(accuracy * 100).toFixed(1)}%` : 'Unknown'}</p></div>
            </div>
          ) : (
            <div className="mt-5 space-y-4">
              <div className="grid gap-4 sm:grid-cols-3">
                <div className="rounded-lg border border-white/10 bg-black/20 p-4"><p className="text-xs text-zinc-500">Title</p><p className="mt-1 text-white">{job.title || 'Unidentified'}</p></div>
                <div className="rounded-lg border border-white/10 bg-black/20 p-4"><p className="text-xs text-zinc-500">Artist</p><p className="mt-1 text-white">{job.artist || 'Unknown'}</p></div>
                <div className="rounded-lg border border-white/10 bg-black/20 p-4"><p className="text-xs text-zinc-500">Duration</p><p className="mt-1 text-white">{job.duration ? `${job.duration}s` : 'Unknown'}</p></div>
              </div>
              {job.fingerprint && <details className="rounded-lg border border-white/10 bg-black/20 p-4"><summary className="cursor-pointer text-sm text-zinc-300">View fingerprint</summary><p className="mt-3 break-all font-mono text-xs leading-5 text-zinc-500">{job.fingerprint}</p></details>}
            </div>
          )}
        </section>
      )}
    </WorkspaceFrame>
  );
}
