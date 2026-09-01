'use client';

import AnalysisForm, { type JobType } from '@/components/AnalysisForm';
import { authClient } from '@/lib/auth-client';
import Link from 'next/link';

type StandaloneJobType = Exclude<JobType, 'full'>;

export default function ToolRunPage({ jobType }: { jobType: StandaloneJobType }) {
  const { data: session, isPending } = authClient.useSession();

  if (isPending) return <main className="mx-auto max-w-6xl px-5 py-16 text-zinc-400">Loading…</main>;
  if (!session) {
    return (
      <main className="mx-auto max-w-xl px-5 py-24 text-center">
        <h1 className="text-3xl font-semibold text-white">Sign in to use this service</h1>
        <Link href="/sign-in" className="mt-6 inline-flex rounded-full bg-white px-5 py-2.5 text-sm font-semibold text-zinc-950">Sign in</Link>
      </main>
    );
  }

  return (
    <main className="mx-auto min-h-[calc(100vh-9rem)] w-full max-w-6xl px-5 py-12 sm:px-8 sm:py-16">
      <Link href="/tools" className="text-sm text-zinc-500 transition hover:text-white">← All standalone services</Link>
      <div className="mt-8">
        <AnalysisForm jobType={jobType} />
      </div>
    </main>
  );
}
