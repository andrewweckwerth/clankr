'use client';

import AnalysisForm from '@/components/AnalysisForm';
import SignedOutPanel from '@/components/SignedOutPanel';
import { WorkspaceFrame } from '@/components/WorkspaceChrome';
import { authClient } from '@/lib/auth-client';

export default function NewProjectPage() {
  const { data: session, isPending } = authClient.useSession();

  if (isPending) return <main className="mx-auto max-w-6xl px-5 py-16 text-zinc-400">Loading…</main>;
  if (!session) return <SignedOutPanel
    title="Full Pipeline"
    label="AI lyric detection"
    heading="Sign in to analyze a recording"
    description="Upload a recording to extract its lyrics and assess them for signs of AI generation."
  />;

  return (
    <WorkspaceFrame crumb="Full Pipeline">
      <AnalysisForm jobType="full" />
    </WorkspaceFrame>
  );
}
