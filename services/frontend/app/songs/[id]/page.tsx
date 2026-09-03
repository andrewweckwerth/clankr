'use client';

import { useApiFetch } from '@/lib/api';
import { authClient } from '@/lib/auth-client';
import { WorkspaceFrame } from '@/components/WorkspaceChrome';
import { useParams } from 'next/navigation';
import { useCallback } from 'react';
import useSWR from 'swr';

type Song = {
  id: number;
  title: string;
  artist?: string | null;
  duration?: number | null;
  lyrics?: string | null;
  classification?: string | null;
  accuracy?: number | string | null;
  fingerprint?: string | null;
  file_path?: string | null;
};

export default function SongDetailPage() {
  const params = useParams<{ id: string }>();
  const { data: session, isPending } = authClient.useSession();
  const apiFetch = useApiFetch();
  const fetcher = useCallback(async (url: string) => {
    const response = await apiFetch(url);
    if (!response.ok) throw new Error('Unable to load song');
    return response.json();
  }, [apiFetch]);
  const { data: song, error } = useSWR<Song>(session ? `/api/songs/${params.id}` : null, fetcher);

  if (isPending || (!song && !error)) return <main className="mx-auto max-w-5xl px-5 py-16 text-zinc-400">Loading song…</main>;
  if (!session) return <main className="mx-auto max-w-xl px-5 py-24 text-center text-white">Sign in to view this Song.</main>;
  if (error || !song) return <main className="mx-auto max-w-xl px-5 py-24 text-center text-red-200">This Song could not be found.</main>;

  const accuracy = song.accuracy == null ? null : Number(song.accuracy);

  return (
    <WorkspaceFrame crumb={`Song #${song.id}`}>
      <header className="y2k-panel-window rounded-3xl border border-white/10 bg-gradient-to-br from-emerald-500/10 to-transparent p-7 sm:p-9" data-window-title="Song Details">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-emerald-300">Canonical Song #{song.id}</p>
        <h1 className="mt-4 text-4xl font-semibold tracking-tight text-white">{song.title}</h1>
        <p className="mt-2 text-lg text-zinc-400">{song.artist || 'Unknown artist'}</p>
        <div className="mt-7 flex flex-wrap gap-3">
          <span className="rounded-full border border-white/10 bg-black/20 px-3 py-1.5 text-sm text-zinc-300">{song.duration ? `${song.duration}s` : 'Unknown duration'}</span>
          <span className="rounded-full border border-white/10 bg-black/20 px-3 py-1.5 text-sm text-zinc-300">{song.classification || 'Not classified'}{accuracy != null && Number.isFinite(accuracy) ? ` · ${(accuracy * 100).toFixed(1)}%` : ''}</span>
        </div>
        {song.file_path && <a href={`/api/songs/${song.id}/artifact`} className="y2k-button mt-7 inline-flex rounded-xl px-5 py-2.5 text-sm font-semibold">Download vocal stem</a>}
      </header>

      <section className="y2k-panel-window rounded-3xl border border-white/10 bg-white/[0.035] p-7 sm:p-9" data-window-title="Transcript">
        <h2 className="text-lg font-semibold text-white">Transcript</h2>
        <div className="mt-5 whitespace-pre-wrap text-sm leading-7 text-zinc-300">{song.lyrics || 'No transcript is available.'}</div>
      </section>

      {song.fingerprint && (
        <section className="y2k-panel-window rounded-3xl border border-white/10 bg-white/[0.025] p-7 sm:p-9" data-window-title="Fingerprint">
          <p className="break-all font-mono text-xs leading-5 text-zinc-600">{song.fingerprint}</p>
        </section>
      )}
    </WorkspaceFrame>
  );
}
