// pages.tsx
'use client';

import UploadForm from '@/components/UploadForm';
import ProcessedSongs from '@/components/ProcessedSongs';

import { useState } from 'react';
import JobModal from '@/components/JobModal';
import SongModal from '@/components/SongModal';

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

export default function HomePage() {
  //const [results, setResults] = useState<any | null>(null);
  //const [queue, setQueue] = useState<string[]>([]);
  const [jobModalOpen, setJobModalOpen] = useState<boolean>(false)
  const [jobId, setJobId] = useState<number | null>(null);

  
  //const [songModal, setSongModalOpen] = useState(false)

  //controls the song modal setting selected to a song id will bring up a modal and null will not show a modal

  const [selected, setSelected] = useState<number | null>(null)

  const handleCompleted = (songId: number | null) => {
    setJobModalOpen(false);
    setSelected(songId)
    return 
  }

  return (
    <main className="p-8 space-y-8">
      <h1 className="text-2xl font-bold flex items-center justify-center">Clankr - detect ai written lyrics</h1>
      <UploadForm setJobModalOpen={setJobModalOpen} setJobId={setJobId} setSelected={setSelected} />
      <ProcessedSongs setSelected={setSelected}/>
      <JobModal jobModalOpen={jobModalOpen} setJobModalOpen={setJobModalOpen} jobId={jobId} handleCompleted={handleCompleted} />
      <SongModal selected={selected} onClose={() => setSelected(null)}/>
    </main>

  );
}

