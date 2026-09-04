'use client';

import AnalysisForm from '@/components/AnalysisForm';
import { WorkspaceFrame } from '@/components/WorkspaceChrome';
import { authClient } from '@/lib/auth-client';
import Link from 'next/link';

const WORKFLOW = [
  ['01', 'Upload a recording', 'Start with an MP3 or WAV file. Clankr keeps the original attached to the analysis job.'],
  ['02', 'Trace the lyrics', 'Clankr identifies the recording, isolates its vocals, and transcribes the words.'],
  ['03', 'Review the assessment', 'Follow each stage as it runs, then review the lyric analysis and its confidence.'],
];

function LandingPage() {
  return (
    <main className="y2k-landing mx-auto max-w-5xl px-5 py-12 sm:px-8 sm:py-16">
      <section className="y2k-panel-window p-7 sm:p-10" data-window-title="Welcome to Clankr">
        <div className="max-w-3xl">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-violet-300">AI lyric detection workspace</p>
          <h1 className="mt-4 text-4xl font-semibold tracking-tight text-white sm:text-5xl">Understand where a song’s lyrics come from.</h1>
          <p className="mt-5 max-w-2xl text-base leading-7 text-zinc-400">
            Clankr turns a recording into a traceable lyric assessment. It identifies the song, isolates the vocals, transcribes the lyrics, and checks for signs of AI generation.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link href="/sign-up" className="y2k-primary-button inline-flex px-5 py-3 text-sm font-semibold">Sign up</Link>
            <Link href="/sign-in" className="y2k-button-secondary inline-flex px-5 py-3 text-sm font-semibold">Log in</Link>
          </div>
        </div>
      </section>

      <section className="mt-10 border-t border-white/10 pt-8" aria-labelledby="how-clankr-works">
        <p className="text-xs font-semibold uppercase tracking-[0.22em] text-violet-300">How Clankr works</p>
        <h2 id="how-clankr-works" className="mt-3 text-2xl font-semibold text-white">One recording, one clear workflow.</h2>
        <div className="mt-7 grid gap-7 sm:grid-cols-3 sm:gap-8">
          {WORKFLOW.map(([number, title, description]) => (
            <article key={number} className="border-l-2 border-[#3e7eae] pl-4">
              <p className="font-mono text-xs text-violet-300">{number}</p>
              <h3 className="mt-2 text-base font-semibold text-white">{title}</h3>
              <p className="mt-2 text-sm leading-6 text-zinc-400">{description}</p>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}

export default function HomePage() {
  const { data: session, isPending } = authClient.useSession();

  if (isPending) {
    return <main className="flex min-h-[calc(100vh-9rem)] items-center justify-center px-5 text-zinc-400">Loading Clankr…</main>;
  }

  if (!session) return <LandingPage />;

  return (
    <WorkspaceFrame crumb="Full Pipeline">
      <AnalysisForm jobType="full" />
    </WorkspaceFrame>
  );
}
