'use client';

import { authClient } from '@/lib/auth-client';
import SignedOutPanel from '@/components/SignedOutPanel';
import { WorkspaceFrame, WorkspaceWindow } from '@/components/WorkspaceChrome';
import Link from 'next/link';

const TOOLS = [
  {
    href: '/tools/acousti',
    name: 'Acousti',
    input: 'Audio',
    output: 'Identity and fingerprint',
    description: 'Fingerprint a recording, identify it when possible, and check Clankr’s shared Song cache.',
  },
  {
    href: '/tools/demucs',
    name: 'Demucs',
    input: 'Audio',
    output: 'Vocal stem',
    description: 'Separate a recording into stems and download the isolated vocal track as its own Job result.',
  },
  {
    href: '/tools/whisper',
    name: 'Whisper',
    input: 'Audio',
    output: 'Transcript',
    description: 'Turn an audio file into an English transcript without running the rest of the pipeline.',
  },
  {
    href: '/tools/classifier',
    name: 'Classifier',
    input: 'Text',
    output: 'AI-generation assessment',
    description: 'Assess pasted lyrics or text for signs of AI generation.',
  },
];

export default function ToolsPage() {
  const { data: session, isPending } = authClient.useSession();

  if (isPending) return <main className="mx-auto max-w-6xl px-5 py-16 text-zinc-400">Loading…</main>;
  if (!session) return <SignedOutPanel
    title="Standalone Tools"
    label="Audio tools"
    heading="Sign in to use the tools"
    description="Run identification, vocal separation, transcription, or lyric assessment independently."
  />;

  return (
    <WorkspaceFrame crumb="Standalone Tools">
      <WorkspaceWindow title="Standalone Tools">
        <div className="max-w-3xl">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-cyan-300">Standalone services</p>
          <h1 className="mt-3 text-2xl font-semibold tracking-tight text-white">Use one part of the pipeline.</h1>
          <p className="mt-3 text-sm leading-6 text-zinc-400">Each run creates an independent job and never creates a new canonical Song.</p>
        </div>

      </WorkspaceWindow>

      <section className="y2k-window-grid" aria-label="Standalone services">
        {TOOLS.map((tool) => (
          <WorkspaceWindow key={tool.href} title={tool.name}>
            <Link href={tool.href} className="y2k-tool-action">
              <span>{tool.input} input → {tool.output}</span>
              <p>{tool.description}</p>
              <span className="y2k-tool-cta">Try {tool.name} →</span>
            </Link>
          </WorkspaceWindow>
        ))}
      </section>
    </WorkspaceFrame>
  );
}
