'use client';

import { useState } from 'react';
import useSWR from 'swr';
import SongModal from './SongModal';

const fetcher = (url: string) => fetch(url).then(res => res.json());

export function useSWRSongs() {
  return useSWR('/api/songs', fetcher, { refreshInterval: 5000 });
}

type Song = {
  id: string | number;
  title?: string;
  artist?: string;
  lyrics?: string;
  classification?: string;
  accuracy?: number | string;
  fingerprint?: string;
  duration?: number;
};

type Props = {
  setSelected: React.Dispatch<React.SetStateAction<number | null>>;
};

export default function ProcessedSongs( {setSelected} : Props) {
  const { data, error } = useSWRSongs();
  //const [selected, setSelected] = useState<Song | null>(null);

  if (error) return <div>Failed to load songs</div>;
  if (!data) return <div>Loading...</div>;

  return (
    <div>
      <h2 className="text-xl font-bold mb-4">Processed Songs</h2>
      <div className="flex flex-col gap-4">
        {data.map((song: Song) => (
          <button
            key={song.id}
            onClick={() => setSelected(Number(song.id))}
            className="text-left p-4 rounded-lg bg-white/10 backdrop-blur border border-white/20 text-white hover:bg-white/20 transition"
          >
            <div className="font-bold text-lg">{song.title || '—'}</div>
            <div className="text-sm text-gray-300">{song.artist || '—'}</div>
            <div className="text-sm italic text-gray-400 mt-1 truncate">
              {song.lyrics || 'No lyrics'}
            </div>
            <div className="text-sm mt-1">
              {song.classification || '—'}{' '}
              {song.accuracy && !isNaN(Number(song.accuracy)) && (
                <span className="ml-1">({Number(song.accuracy).toFixed(2)})</span>
              )}
            </div>
          </button>
        ))}
      </div>

    </div>
  );
}
