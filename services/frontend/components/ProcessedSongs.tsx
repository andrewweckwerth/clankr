'use client';

import { useApiFetch } from '@/lib/api';
import Link from 'next/link';
import { useCallback, useState } from 'react';
import useSWR from 'swr';

type Song = {
  id: number;
  title?: string;
  artist?: string;
  lyrics?: string;
  classification?: string;
  accuracy?: number | string;
  submission_count?: number;
};

type SongListProps = {
  title: string;
  description: string;
  url: string;
  emptyMessage: string;
  library?: boolean;
};

function SongList({ title, description, url, emptyMessage, library = false }: SongListProps) {
  const apiFetch = useApiFetch();
  const [removing, setRemoving] = useState<number | null>(null);
  const fetcher = useCallback(async (requestUrl: string): Promise<Song[]> => {
    const response = await apiFetch(requestUrl);
    if (!response.ok) throw new Error(`Unable to load songs (${response.status})`);
    return response.json();
  }, [apiFetch]);
  const { data, error, mutate } = useSWR<Song[]>(url, fetcher, { refreshInterval: 10000 });

  const removeFromLibrary = async (song: Song) => {
    if (!window.confirm(`Remove “${song.title || 'this song'}” from your library?`)) return;
    setRemoving(song.id);
    try {
      const response = await apiFetch(`/api/songs/${song.id}`, { method: 'DELETE' });
      if (response.ok) await mutate();
    } finally {
      setRemoving(null);
    }
  };

  return (
    <section className="space-y-5">
      <div>
        <h2 className="text-2xl font-semibold text-white">{title}</h2>
        <p className="mt-2 text-sm leading-6 text-zinc-400">{description}</p>
      </div>

      {error && <p className="rounded-xl border border-red-400/25 bg-red-400/10 px-4 py-3 text-sm text-red-200">Failed to load songs.</p>}
      {!error && !data && <p className="text-sm text-zinc-500">Loading songs…</p>}
      {!error && data?.length === 0 && <p className="rounded-2xl border border-dashed border-white/10 px-4 py-10 text-center text-sm text-zinc-500">{emptyMessage}</p>}

      {data && data.length > 0 && (
        <div className="grid gap-4 md:grid-cols-2">
          {data.map((song) => {
            const accuracy = song.accuracy == null ? null : Number(song.accuracy);
            return (
              <article key={song.id} className="relative rounded-2xl border border-white/10 bg-white/[0.045] p-5 transition hover:border-emerald-300/30 hover:bg-white/[0.065]">
                <Link href={`/songs/${song.id}`} className="block pr-12">
                  <h3 className="truncate text-lg font-semibold text-white">{song.title || 'Untitled'}</h3>
                  <p className="mt-1 text-sm text-zinc-400">{song.artist || 'Unknown artist'}</p>
                  <p className="mt-4 line-clamp-2 text-sm italic leading-6 text-zinc-500">{song.lyrics || 'No lyrics'}</p>
                  <p className="mt-4 text-sm text-zinc-300">
                    {song.classification || 'Not classified'}
                    {accuracy != null && Number.isFinite(accuracy) && <span className="ml-1 text-zinc-500">· {(accuracy * 100).toFixed(1)}%</span>}
                  </p>
                  {song.submission_count != null && <p className="mt-2 text-xs text-zinc-600">Submitted {song.submission_count} {song.submission_count === 1 ? 'time' : 'times'}</p>}
                </Link>
                {library && (
                  <button
                    type="button"
                    aria-label={`Remove ${song.title || 'song'} from library`}
                    title="Remove from library"
                    disabled={removing === song.id}
                    onClick={() => void removeFromLibrary(song)}
                    className="absolute right-4 top-4 rounded-lg border border-white/10 px-2.5 py-1.5 text-xs text-zinc-500 transition hover:border-red-400/30 hover:text-red-200 disabled:opacity-50"
                  >
                    Remove
                  </button>
                )}
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}

export default function ProcessedSongs() {
  return (
    <div className="space-y-14">
      <SongList
        title="Your library"
        description="Songs claimed through a completed full project or an Acousti cache hit. Removing one only changes your library."
        url="/api/songs/mine"
        emptyMessage="Your library is empty. Complete a project to add a song."
        library
      />
      <div className="border-t border-white/10 pt-12">
        <SongList
          title="Global catalog"
          description="The canonical recordings Clankr can reuse by fingerprint without processing them again."
          url="/api/songs"
          emptyMessage="No canonical songs have been processed yet."
        />
      </div>
    </div>
  );
}
