// pages.tsx
'use client';

import UploadForm from '@/components/UploadForm';
import ProcessedSongs from '@/components/ProcessedSongs';

import { useState } from 'react';
import { mutate } from 'swr';
import JobModal from '@/components/JobModal';
import SongModal from '@/components/SongModal';
import Link from 'next/link';
import { authClient } from '@/lib/auth-client';

export default function HomePage() {
  //const [results, setResults] = useState<any | null>(null);
  //const [queue, setQueue] = useState<string[]>([]);
  const [jobModalOpen, setJobModalOpen] = useState<boolean>(false)
  const [jobId, setJobId] = useState<number | null>(null);

  
  //const [songModal, setSongModalOpen] = useState(false)

  //controls the song modal setting selected to a song id will bring up a modal and null will not show a modal

  const [selected, setSelected] = useState<number | null>(null)
  const { data: session, isPending: sessionPending } = authClient.useSession();

  const handleCompleted = (songId: number | null) => {
    setJobModalOpen(false);
    setSelected(songId)
    void mutate('/api/songs');
    void mutate('/api/songs/mine');
    return 
  }

  return (
    <>
      {sessionPending ? (
        <main className="flex min-h-[calc(100vh-9rem)] items-center justify-center px-5 text-zinc-400">Loading Clankr…</main>
      ) : !session ? (
        <main className="mx-auto flex min-h-[calc(100vh-9rem)] max-w-2xl flex-col items-center justify-center px-5 text-center">
          <p className="text-sm font-medium uppercase tracking-[0.2em] text-violet-300">Clankr</p>
          <h1 className="mt-4 text-4xl font-semibold tracking-tight text-white sm:text-5xl">Detect AI-written lyrics.</h1>
          <p className="mt-5 max-w-lg text-base leading-7 text-zinc-400">Analyze a song, understand its lyrics, and keep your processed songs in one place.</p>
          <Link href="/sign-in" className="mt-8 rounded-full bg-white px-5 py-3 text-sm font-semibold text-zinc-950 transition hover:bg-violet-200">Sign in to analyze</Link>
        </main>
      ) : (
      <main className="mx-auto w-full max-w-6xl space-y-8 p-5 sm:p-8">
        <h1 className="text-2xl font-bold flex items-center justify-center">Clankr - detect ai written lyrics</h1>
        <section id="analyze" className="scroll-mt-24">
          <UploadForm setJobModalOpen={setJobModalOpen} setJobId={setJobId} setSelected={setSelected} />
        </section>
        <section id="songs" className="scroll-mt-24">
          <ProcessedSongs setSelected={setSelected}/>
        </section>
        <JobModal jobModalOpen={jobModalOpen} setJobModalOpen={setJobModalOpen} jobId={jobId} handleCompleted={handleCompleted} />
        <SongModal selected={selected} onClose={() => setSelected(null)}/>
      </main>
      )}
    </>
  );
}
