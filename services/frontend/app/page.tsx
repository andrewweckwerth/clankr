'use client';

import PipelineOverview from '@/components/PipelineOverview';
import { authClient } from '@/lib/auth-client';
import Link from 'next/link';

export default function HomePage() {
  const { data: session, isPending } = authClient.useSession();

  if (isPending) {
    return <main className="mx-auto max-w-7xl px-5 py-12 text-zinc-400">Loading pipeline…</main>;
  }

  return (
    <main className="workspace mx-auto px-5 py-10 sm:px-8">
      <header className="mb-7">
        <h1 className="text-2xl font-semibold">Audio processing pipeline</h1>
        <p className="mt-2 max-w-3xl text-sm text-zinc-400">Clankr is a project for detecting AI-generated lyrics from audio. Run a recording through four stages, then inspect progress, queue activity, and results.</p>
        <div className="project-links mt-4 flex flex-wrap items-center gap-x-6 gap-y-2 text-sm">
          <span className="text-zinc-400">Built by Andrew Weckwerth</span>
          <a href="https://www.linkedin.com/in/andrew-weckwerth/" target="_blank" rel="noreferrer">LinkedIn ↗</a>
          <a href="mailto:andrew.weckwerth@outlook.com">andrew.weckwerth@outlook.com</a>
          <a href="https://github.com/andrewweckwerth/clankr#readme" target="_blank" rel="noreferrer">Read the README on GitHub ↗</a>
        </div>
      </header>
      <PipelineOverview />
      <section className="mt-6 flex flex-wrap items-center justify-between gap-5 border-t border-white/10 pt-6">
        <p className="text-sm text-zinc-400">{session ? 'Open the pipeline to submit a job and inspect its progress.' : 'Browse the public song catalog and job queue. Sign in to submit your own audio.'}</p>
        <div className="flex gap-3">
          {session ? (
            <Link href="/projects/new" className="button-primary px-4 py-2 text-sm">Open pipeline</Link>
          ) : (
            <>
              <Link href="/sign-in" className="button-primary px-4 py-2 text-sm">Sign in</Link>
              <Link href="/sign-up" className="button-secondary px-4 py-2 text-sm">Create account</Link>
            </>
          )}
        </div>
      </section>
    </main>
  );
}
