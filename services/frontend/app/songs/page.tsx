'use client';

import ProcessedSongs from '@/components/ProcessedSongs';
import SignedOutPanel from '@/components/SignedOutPanel';
import { WorkspaceFrame, WorkspaceWindow } from '@/components/WorkspaceChrome';
import { authClient } from '@/lib/auth-client';
import { useSearchParams } from 'next/navigation';
import { Suspense } from 'react';

export default function SongsPage() {
  return (
    <Suspense fallback={<main className="mx-auto max-w-6xl px-5 py-16 text-zinc-400">Loading…</main>}>
      <SongsContent />
    </Suspense>
  );
}

function SongsContent() {
  const { data: session, isPending } = authClient.useSession();
  const searchParams = useSearchParams();
  const view = searchParams.get('view') === 'all' ? 'all' : 'mine';
  const isCatalog = view === 'all';
  if (isPending) return <main className="mx-auto max-w-6xl px-5 py-16 text-zinc-400">Loading…</main>;
  if (!session) return <SignedOutPanel
    title={isCatalog ? 'All Songs' : 'My Songs'}
    label="Song library"
    heading={`Sign in to view ${isCatalog ? 'all songs' : 'your songs'}`}
    description="Review recordings identified by Clankr and lyric assessments from completed pipeline runs."
  />;

  return (
    <WorkspaceFrame crumb={isCatalog ? 'All Songs' : 'My Songs'}>
      <WorkspaceWindow title={isCatalog ? 'All Songs' : 'My Songs'}>
        <header className="max-w-3xl">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-emerald-300">{isCatalog ? 'Canonical catalog' : 'Your library'}</p>
          <p className="mt-3 text-sm leading-6 text-zinc-400">
            {isCatalog
              ? 'Canonical recordings Clankr can reuse by fingerprint without processing them again.'
              : 'Songs claimed through a completed full pipeline or an Acousti cache hit.'}
          </p>
        </header>
      </WorkspaceWindow>
      <ProcessedSongs view={view} />
    </WorkspaceFrame>
  );
}
