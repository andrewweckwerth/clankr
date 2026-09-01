'use client';

import ProcessedSongs from '@/components/ProcessedSongs';
import { authClient } from '@/lib/auth-client';
import Link from 'next/link';

export default function SongsPage() {
  const { data: session, isPending } = authClient.useSession();
  if (isPending) return <main className="mx-auto max-w-6xl px-5 py-16 text-zinc-400">Loading…</main>;
  if (!session) return <main className="mx-auto max-w-xl px-5 py-24 text-center text-white">Sign in to view Songs.</main>;

  return (
    <main className="mx-auto min-h-[calc(100vh-9rem)] w-full max-w-6xl px-5 py-12 sm:px-8 sm:py-16">
      <Link href="/" className="text-sm text-zinc-500 transition hover:text-white">← Workspace</Link>
      <header className="mt-8 max-w-3xl">
        <p className="text-sm font-semibold uppercase tracking-[0.22em] text-emerald-300">Canonical results</p>
        <h1 className="mt-4 text-4xl font-semibold tracking-[-0.035em] text-white">Songs</h1>
        <p className="mt-4 text-base leading-7 text-zinc-400">One shared result per fingerprint, connected to each user through their personal library.</p>
      </header>
      <div className="mt-10">
        <ProcessedSongs />
      </div>
    </main>
  );
}
