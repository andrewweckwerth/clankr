'use client';

import { authClient } from '@/lib/auth-client';
import Link from 'next/link';

const TOOLS = [
  { href: '/tools/acousti', name: 'Acousti', input: 'Audio', output: 'Identity and fingerprint', accent: 'from-cyan-500/20 to-blue-500/5' },
  { href: '/tools/demucs', name: 'Demucs', input: 'Audio', output: 'Vocal stem', accent: 'from-amber-500/20 to-orange-500/5' },
  { href: '/tools/whisper', name: 'Whisper', input: 'Audio', output: 'Transcript', accent: 'from-emerald-500/20 to-teal-500/5' },
  { href: '/tools/classifier', name: 'Classifier', input: 'Text', output: 'AI insight', accent: 'from-rose-500/20 to-pink-500/5' },
];

export default function ToolsPage() {
  const { data: session, isPending } = authClient.useSession();

  if (isPending) return <main className="mx-auto max-w-6xl px-5 py-16 text-zinc-400">Loading…</main>;
  if (!session) {
    return (
      <main className="mx-auto max-w-xl px-5 py-24 text-center">
        <h1 className="text-3xl font-semibold text-white">Sign in to use the tools</h1>
        <Link href="/sign-in" className="mt-6 inline-flex rounded-full bg-white px-5 py-2.5 text-sm font-semibold text-zinc-950">Sign in</Link>
      </main>
    );
  }

  return (
    <main className="mx-auto min-h-[calc(100vh-9rem)] w-full max-w-6xl px-5 py-12 sm:px-8 sm:py-16">
      <Link href="/" className="text-sm text-zinc-500 transition hover:text-white">← Workspace</Link>
      <div className="mt-8 max-w-3xl">
        <p className="text-sm font-semibold uppercase tracking-[0.22em] text-cyan-300">Standalone services</p>
        <h1 className="mt-4 text-4xl font-semibold tracking-[-0.035em] text-white">Use one part of the pipeline.</h1>
        <p className="mt-4 text-base leading-7 text-zinc-400">Each run creates an independent job and never creates a new canonical Song.</p>
      </div>

      <section className="mt-9 grid gap-4 sm:grid-cols-2" aria-label="Standalone services">
        {TOOLS.map((tool) => (
          <Link
            key={tool.href}
            href={tool.href}
            className={`group relative min-h-52 overflow-hidden rounded-3xl border border-white/10 bg-gradient-to-br ${tool.accent} p-7 transition hover:-translate-y-0.5 hover:border-white/20`}
          >
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-zinc-500">{tool.input} → {tool.output}</p>
            <h2 className="mt-5 text-2xl font-semibold text-white">{tool.name}</h2>
            <span className="absolute bottom-7 right-7 text-xl text-white transition group-hover:translate-x-1" aria-hidden="true">→</span>
          </Link>
        ))}
      </section>
    </main>
  );
}
