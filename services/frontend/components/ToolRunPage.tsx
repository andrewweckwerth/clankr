'use client';

import AnalysisForm, { type JobType } from '@/components/AnalysisForm';
import { WorkspaceFrame } from '@/components/WorkspaceChrome';
import { authClient } from '@/lib/auth-client';
import Link from 'next/link';

type StandaloneJobType = Exclude<JobType, 'full'>;

const TOOL_TITLES: Record<StandaloneJobType, string> = {
  acousti: 'Identify a song',
  demucs: 'Split the vocals',
  whisper: 'Transcribe audio',
  classifier: 'Classify text',
};

export default function ToolRunPage({ jobType }: { jobType: StandaloneJobType }) {
  const { data: session, isPending } = authClient.useSession();

  if (isPending) return <main className="mx-auto max-w-6xl px-5 py-16 text-zinc-400">Loading…</main>;
  if (!session) {
    return (
      <main className="mx-auto max-w-xl px-5 py-24 text-center">
        <h1 className="text-3xl font-semibold text-white">Sign in to use this service</h1>
        <Link href="/sign-in" className="y2k-button mt-6 inline-flex rounded-full px-5 py-2.5 text-sm font-semibold">Sign in</Link>
      </main>
    );
  }

  return (
    <WorkspaceFrame crumb={<><Link href="/tools">Standalone Tools</Link> &gt; {TOOL_TITLES[jobType]}</>}>
      <AnalysisForm jobType={jobType} />
    </WorkspaceFrame>
  );
}
