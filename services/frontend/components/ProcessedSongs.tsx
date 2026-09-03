'use client';

import { useApiFetch } from '@/lib/api';
import { WorkspaceWindow } from '@/components/WorkspaceChrome';
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
  url: string;
  emptyMessage: string;
  library?: boolean;
};

function SongList({ title, url, emptyMessage, library = false }: SongListProps) {
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
    <section className="y2k-window-stack">
      {error && (
        <WorkspaceWindow title={title}>
          <p className="text-red-200">Failed to load songs.</p>
        </WorkspaceWindow>
      )}
      {!error && !data && (
        <WorkspaceWindow title={title}>
          <p className="text-zinc-500">Loading songs…</p>
        </WorkspaceWindow>
      )}
      {!error && data?.length === 0 && (
        <WorkspaceWindow title={title}>
          <p className="py-8 text-center text-sm text-zinc-500">{emptyMessage}</p>
        </WorkspaceWindow>
      )}

      {data && data.length > 0 && (
        <div className="y2k-window-grid">
            {data.map((song) => {
              const accuracy = song.accuracy == null ? null : Number(song.accuracy);
              return (
                <WorkspaceWindow key={song.id} title={song.title || 'Untitled'} className="y2k-song-window">
                  <article className="y2k-song-card relative">
                    <Link href={`/songs/${song.id}`} className="group block pr-14">
                      <h3 className="sr-only">{song.title || 'Untitled'}</h3>
                      <p className="mt-1 text-sm text-zinc-400">{song.artist || 'Unknown artist'}</p>
                      <p className="mt-4 line-clamp-2 text-sm italic leading-6 text-zinc-500">{song.lyrics || 'No lyrics'}</p>
                      <p className="mt-4 text-sm text-zinc-300">
                        {song.classification || 'Not classified'}
                        {accuracy != null && Number.isFinite(accuracy) && <span className="ml-1 text-zinc-500">· {(accuracy * 100).toFixed(1)}%</span>}
                      </p>
                      {song.submission_count != null && <p className="mt-2 text-xs text-zinc-600">Submitted {song.submission_count} {song.submission_count === 1 ? 'time' : 'times'}</p>}
                      {!library && <span className="absolute right-0 top-0 text-sm text-zinc-400 transition group-hover:translate-x-1 group-hover:text-emerald-200" aria-hidden="true">→</span>}
                    </Link>
                  {library && (
                    <button
                      type="button"
                      aria-label={`Remove ${song.title || 'song'} from library`}
                      title="Remove from library"
                      disabled={removing === song.id}
                      onClick={() => void removeFromLibrary(song)}
                      className="y2k-button-danger absolute right-0 top-0 px-2 py-1 text-xs disabled:opacity-50"
                    >
                      Remove
                    </button>
                  )}
                  </article>
                </WorkspaceWindow>
              );
            })}
        </div>
      )}
    </section>
  );
}

export default function ProcessedSongs({ view }: { view: 'mine' | 'all' }) {
  return (
    <SongList
      title={view === 'mine' ? 'Your Library' : 'All Songs'}
      url={view === 'mine' ? '/api/songs/mine' : '/api/songs'}
      emptyMessage={view === 'mine' ? 'Your library is empty. Complete a project to add a song.' : 'No canonical songs have been processed yet.'}
      library={view === 'mine'}
    />
  );
}
