'use client';

import ProcessedSongs from '@/components/ProcessedSongs';
import SignedOutPanel from '@/components/SignedOutPanel';
import { WorkspaceFrame, WorkspacePanel } from '@/components/WorkspaceChrome';
import { authClient } from '@/lib/auth-client';
import { useSearchParams } from 'next/navigation';
import { Suspense } from 'react';
import Link from 'next/link';

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
  const view = searchParams.get('view') === 'mine' ? 'mine' : 'all';
  const isCatalog = view === 'all';
  if (isPending) return <main className="mx-auto max-w-6xl px-5 py-16 text-zinc-400">Loading…</main>;
  if (!session && !isCatalog) return <SignedOutPanel
    title={isCatalog ? 'All Songs' : 'My Songs'}
    label="Song library"
    heading={`Sign in to view ${isCatalog ? 'all songs' : 'your songs'}`}
    description="Review recordings identified by Clankr and lyric assessments from completed pipeline runs."
  />;

  return (
    <WorkspaceFrame crumb={isCatalog ? 'All Songs' : 'My Songs'}>
      <WorkspacePanel title={isCatalog ? 'All Songs' : 'My Songs'}>
        <header className="max-w-3xl">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-emerald-300">{isCatalog ? 'Public catalog' : 'Your library'}</p>
          <p className="mt-3 text-sm leading-6 text-zinc-400">
            {isCatalog
              ? 'Every completed full-pipeline song is public. Explore transcripts, lyric assessments, and downloadable vocal stems.'
              : 'Songs claimed through a completed full pipeline or an Acousti cache hit.'}
          </p>
        </header>
      </WorkspacePanel>
      <nav className="view-tabs" aria-label="Song views">
        <Link href="/songs" aria-current={isCatalog ? 'page' : undefined}>All songs</Link>
        {session && <Link href="/songs?view=mine" aria-current={!isCatalog ? 'page' : undefined}>My songs</Link>}
      </nav>
      <ProcessedSongs view={view} />
    </WorkspaceFrame>
  );
}
