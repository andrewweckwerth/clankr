'use client';

import { authClient } from '@/lib/auth-client';
import Link from 'next/link';

const ANALYSIS_OPTIONS = [
  {
    href: '/projects/new',
    step: 'All services',
    title: 'Full Pipeline',
    description: 'Identify, separate, transcribe, and classify one audio upload. Successful runs become Songs.',
    accent: 'from-violet-500/25 to-fuchsia-500/5',
    featured: true,
  },
  {
    href: '/tools/acousti',
    step: 'Audio → song details',
    title: 'Acousti',
    description: 'Fingerprint an audio file, identify it, and check the global Song cache.',
    accent: 'from-cyan-500/20 to-blue-500/5',
  },
  {
    href: '/tools/demucs',
    step: 'Audio → vocal stem',
    title: 'Demucs',
    description: 'Separate an audio file and download the isolated vocal stem.',
    accent: 'from-amber-500/20 to-orange-500/5',
  },
  {
    href: '/tools/whisper',
    step: 'Audio → transcript',
    title: 'Whisper',
    description: 'Transcribe an audio file into English text as a standalone job.',
    accent: 'from-emerald-500/20 to-teal-500/5',
  },
  {
    href: '/tools/classifier',
    step: 'Text → AI insight',
    title: 'Classifier',
    description: 'Analyze pasted lyrics or text for an AI or human assessment.',
    accent: 'from-rose-500/20 to-pink-500/5',
  },
];

export default function HomePage() {
  const { data: session, isPending } = authClient.useSession();

  if (isPending) {
    return <main className="flex min-h-[calc(100vh-9rem)] items-center justify-center px-5 text-zinc-400">Loading Clankr…</main>;
  }

  if (!session) {
    return (
      <main className="relative mx-auto flex min-h-[calc(100vh-9rem)] max-w-5xl flex-col items-center justify-center overflow-hidden px-5 py-20 text-center">
        <div className="pointer-events-none absolute inset-x-24 top-20 h-72 rounded-full bg-violet-600/15 blur-3xl" />
        <p className="relative text-sm font-semibold uppercase tracking-[0.24em] text-violet-300">Audio analysis workspace</p>
        <h1 className="relative mt-5 max-w-4xl text-5xl font-semibold tracking-[-0.04em] text-white sm:text-7xl">
          From a recording to an explainable result.
        </h1>
        <p className="relative mt-6 max-w-2xl text-base leading-7 text-zinc-400 sm:text-lg">
          Clankr combines fingerprinting, vocal isolation, transcription, and lyric classification in one traceable pipeline.
        </p>
        <Link href="/sign-in" className="relative mt-9 rounded-full bg-white px-6 py-3 text-sm font-semibold text-zinc-950 transition hover:bg-violet-200">
          Sign in to start
        </Link>
      </main>
    );
  }

  return (
    <main className="mx-auto min-h-[calc(100vh-9rem)] w-full max-w-6xl px-5 py-12 sm:px-8 sm:py-16">
      <section className="max-w-3xl">
        <p className="text-sm font-semibold uppercase tracking-[0.22em] text-violet-300">New analysis</p>
        <h1 className="mt-4 text-4xl font-semibold tracking-[-0.035em] text-white sm:text-5xl">
          Choose what you want to run.
        </h1>
        <p className="mt-4 max-w-2xl text-base leading-7 text-zinc-400">
          Use the complete workflow or run one service by itself. Every run is saved to My Jobs.
        </p>
      </section>

      <section className="mt-10 grid gap-4 md:grid-cols-2" aria-label="Analysis options">
        {ANALYSIS_OPTIONS.map((option) => (
          <Link
            key={option.href}
            href={option.href}
            className={`group relative overflow-hidden rounded-3xl border border-white/10 bg-gradient-to-br ${option.accent} p-7 transition hover:-translate-y-0.5 hover:border-white/20 sm:p-8 ${option.featured ? 'min-h-64 md:col-span-2' : 'min-h-56'}`}
          >
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-400">{option.step}</p>
            <h2 className={`mt-5 font-semibold text-white ${option.featured ? 'text-3xl sm:text-4xl' : 'text-2xl'}`}>{option.title}</h2>
            <p className="mt-3 max-w-lg text-sm leading-6 text-zinc-400">{option.description}</p>
            <span className="absolute bottom-7 right-7 text-xl text-white transition group-hover:translate-x-1" aria-hidden="true">→</span>
          </Link>
        ))}
      </section>

      <section className="mt-8 flex flex-col gap-3 border-t border-white/10 pt-8 sm:flex-row" aria-label="Account shortcuts">
        <Link href="/jobs" className="rounded-full border border-white/10 px-5 py-2.5 text-center text-sm font-medium text-zinc-300 transition hover:border-white/20 hover:text-white">
          View My Jobs
        </Link>
        <Link href="/songs" className="rounded-full border border-white/10 px-5 py-2.5 text-center text-sm font-medium text-zinc-300 transition hover:border-white/20 hover:text-white">
          View Songs
        </Link>
      </section>
    </main>
  );
}
