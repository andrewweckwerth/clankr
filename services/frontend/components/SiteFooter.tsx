import Link from "next/link";

export default function SiteFooter() {
  return (
    <footer className="border-t border-white/10 bg-black/20">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-5 px-5 py-8 text-sm text-zinc-400 sm:flex-row sm:items-center sm:justify-between sm:px-8">
        <div>
          <Link href="/" className="font-semibold text-white transition hover:text-violet-300">
            clankr
          </Link>
          <p className="mt-1">Traceable audio analysis, one job at a time.</p>
        </div>

        <div className="flex items-center gap-5">
          <Link className="transition hover:text-white" href="/projects/new">
            Full pipeline
          </Link>
          <Link className="transition hover:text-white" href="/tools">
            Tools
          </Link>
          <Link className="transition hover:text-white" href="/jobs">
            Jobs
          </Link>
          <Link className="transition hover:text-white" href="/songs">
            Songs
          </Link>
        </div>
      </div>
    </footer>
  );
}
