'use client';

import { authClient } from '@/lib/auth-client';
import { WorkspaceSidebar, WorkspaceWindow } from '@/components/WorkspaceChrome';
import Link from 'next/link';

const TOOLS = [
  {
    href: '/tools/acousti',
    title: 'Acousti',
    description: 'Fingerprint an audio file, identify it, and check the global Song cache.',
  },
  {
    href: '/tools/demucs',
    title: 'Demucs',
    description: 'Separate an audio file and download the isolated vocal stem.',
  },
  {
    href: '/tools/whisper',
    title: 'Whisper',
    description: 'Transcribe an audio file into English text as a standalone job.',
  },
  {
    href: '/tools/classifier',
    title: 'Classifier',
    description: 'Assess pasted lyrics or text for signs of AI generation.',
  },
];

export default function HomePage() {
  const { data: session, isPending } = authClient.useSession();

  if (isPending) {
    return <main className="flex min-h-[calc(100vh-9rem)] items-center justify-center px-5 text-zinc-400">Loading Clankr…</main>;
  }

  if (!session) {
    return (
      <main className="y2k-guest mx-auto flex min-h-[calc(100vh-11rem)] max-w-md items-center px-5 py-16">
        <WorkspaceWindow title="Welcome to Clankr" className="w-full text-center">
          <p className="y2k-kicker">AI lyric detection workspace</p>
          <h1 className="mt-4 text-3xl">Find out whether lyrics may be AI generated.</h1>
          <p className="y2k-window-lead mt-4">
            Clankr identifies a recording, extracts its lyrics, and assesses them for signs of AI generation in one traceable pipeline.
          </p>
          <Link href="/sign-in" className="y2k-primary-button mt-6 inline-flex px-5 py-2 text-sm font-semibold">
            Sign in to start
          </Link>
        </WorkspaceWindow>
      </main>
    );
  }

  return (
    <main className="y2k-workspace mx-auto min-h-[calc(100vh-11rem)] w-full px-5 py-6 sm:px-8 sm:py-8">
      <div className="y2k-breadcrumb"><Link href="/">Home</Link> &gt; Workspace</div>

      <div className="y2k-workspace-grid">
        <WorkspaceSidebar />

        <section className="y2k-workspace-main">
          <WorkspaceWindow title="Full Pipeline">
            <p className="y2k-window-lead">Extract a recording’s lyrics and assess whether they show signs of AI generation.</p>
            <Link href="/projects/new" className="y2k-window-action">
              <strong>Start full pipeline →</strong>
              <span>Upload one recording to identify it, extract its lyrics, and check for AI generation.</span>
            </Link>
          </WorkspaceWindow>

          <WorkspaceWindow title="Standalone Tools">
            <p className="y2k-window-lead">Choose a single tool when you only need one pipeline step.</p>
          </WorkspaceWindow>

          <section className="y2k-window-grid" aria-label="Standalone services">
            {TOOLS.map((tool) => (
              <WorkspaceWindow key={tool.href} title={tool.title}>
                <Link href={tool.href} className="y2k-tool-action">
                  <span>{tool.description}</span>
                  <span className="y2k-tool-cta">Try {tool.title} →</span>
                </Link>
              </WorkspaceWindow>
            ))}
          </section>
        </section>
      </div>
    </main>
  );
}
