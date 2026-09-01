'use client';

import { useApiFetch } from '@/lib/api';
import { authClient } from '@/lib/auth-client';
import Link from 'next/link';
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
    <main className="mx-auto min-h-[calc(100vh-9rem)] w-full max-w-5xl px-5 py-12 sm:px-8 sm:py-16">
      <Link href="/songs" className="text-sm text-zinc-500 transition hover:text-white">← Songs</Link>
      <header className="mt-8 rounded-3xl border border-white/10 bg-gradient-to-br from-emerald-500/10 to-transparent p-7 sm:p-10">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-emerald-300">Canonical Song #{song.id}</p>
        <h1 className="mt-4 text-4xl font-semibold tracking-tight text-white">{song.title}</h1>
        <p className="mt-2 text-lg text-zinc-400">{song.artist || 'Unknown artist'}</p>
        <div className="mt-7 flex flex-wrap gap-3">
          <span className="rounded-full border border-white/10 bg-black/20 px-3 py-1.5 text-sm text-zinc-300">{song.duration ? `${song.duration}s` : 'Unknown duration'}</span>
          <span className="rounded-full border border-white/10 bg-black/20 px-3 py-1.5 text-sm text-zinc-300">{song.classification || 'Not classified'}{accuracy != null && Number.isFinite(accuracy) ? ` · ${(accuracy * 100).toFixed(1)}%` : ''}</span>
        </div>
        {song.file_path && <a href={`/api/songs/${song.id}/artifact`} className="mt-7 inline-flex rounded-xl bg-white px-5 py-2.5 text-sm font-semibold text-zinc-950">Download vocal stem</a>}
      </header>

      <section className="mt-6 rounded-3xl border border-white/10 bg-white/[0.035] p-7 sm:p-9">
        <h2 className="text-lg font-semibold text-white">Transcript</h2>
        <div className="mt-5 whitespace-pre-wrap text-sm leading-7 text-zinc-300">{song.lyrics || 'No transcript is available.'}</div>
      </section>

      {song.fingerprint && (
        <details className="mt-6 rounded-3xl border border-white/10 bg-white/[0.025] p-6">
          <summary className="cursor-pointer text-sm font-medium text-zinc-300">Fingerprint</summary>
          <p className="mt-4 break-all font-mono text-xs leading-5 text-zinc-600">{song.fingerprint}</p>
        </details>
      )}
    </main>
  );
}
