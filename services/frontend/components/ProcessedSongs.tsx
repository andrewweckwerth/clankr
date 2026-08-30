'use client';

import useSWR from 'swr';
import { useCallback } from 'react';
import { useApiFetch } from '@/lib/api';

type Song = {
  id: string | number;
  title?: string;
  artist?: string;
  lyrics?: string;
  classification?: string;
  accuracy?: number | string;
  submission_count?: number;
};

type Props = {
  setSelected: React.Dispatch<React.SetStateAction<number | null>>;
};

type SongListProps = Props & {
  title: string;
  description: string;
  url: string;
  emptyMessage: string;
};

function SongList({ title, description, url, emptyMessage, setSelected }: SongListProps) {
  const apiFetch = useApiFetch();
  const fetcher = useCallback(async (requestUrl: string): Promise<Song[]> => {
    const response = await apiFetch(requestUrl);
    if (!response.ok) throw new Error(`Unable to load songs (${response.status})`);
    return response.json();
  }, [apiFetch]);
  const { data, error } = useSWR<Song[]>(url, fetcher, { refreshInterval: 5000 });

  return (
    <section className="space-y-4">
      <div>
        <h2 className="text-xl font-bold text-white">{title}</h2>
        <p className="mt-1 text-sm text-zinc-400">{description}</p>
      </div>

      {error && <p className="rounded-xl border border-red-400/25 bg-red-400/10 px-4 py-3 text-sm text-red-200">Failed to load songs.</p>}
      {!error && !data && <p className="text-sm text-zinc-500">Loading songs…</p>}
      {!error && data?.length === 0 && <p className="rounded-2xl border border-dashed border-white/10 px-4 py-8 text-center text-sm text-zinc-500">{emptyMessage}</p>}

      {data && data.length > 0 && (
        <div className="grid gap-4 md:grid-cols-2">
          {data.map((song) => {
            const accuracy = song.accuracy == null ? null : Number(song.accuracy);
            return (
              <button
                key={song.id}
                type="button"
                onClick={() => setSelected(Number(song.id))}
                className="rounded-2xl border border-white/10 bg-white/[0.06] p-4 text-left text-white backdrop-blur transition hover:border-violet-300/40 hover:bg-white/10"
              >
                <div className="text-lg font-bold">{song.title || 'Untitled'}</div>
                <div className="text-sm text-gray-300">{song.artist || 'Unknown artist'}</div>
                <div className="mt-2 truncate text-sm italic text-gray-400">{song.lyrics || 'No lyrics'}</div>
                <div className="mt-2 text-sm text-zinc-300">
                  {song.classification || 'Not classified'}
                  {accuracy != null && Number.isFinite(accuracy) && (
                    <span className="ml-1">({accuracy.toFixed(2)})</span>
                  )}
                </div>
                {song.submission_count != null && (
                  <div className="mt-2 text-xs text-zinc-500">
                    Submitted {song.submission_count} {song.submission_count === 1 ? 'time' : 'times'}
                  </div>
                )}
              </button>
            );
          })}
        </div>
      )}
    </section>
  );
}

export default function ProcessedSongs({ setSelected }: Props) {
  return (
    <div className="space-y-10">
      <div id="all-songs" className="scroll-mt-24">
        <SongList
          title="All processed songs"
          description="The shared catalog of songs Clankr has processed."
          url="/api/songs"
          emptyMessage="No songs have been processed yet."
          setSelected={setSelected}
        />
      </div>
      <div id="your-songs" className="scroll-mt-24 border-t border-white/10 pt-10">
        <SongList
          title="Your processed songs"
          description="Songs you have submitted from this account."
          url="/api/songs/mine"
          emptyMessage="You have not submitted a completed song yet."
          setSelected={setSelected}
        />
      </div>
    </div>
  );
}
