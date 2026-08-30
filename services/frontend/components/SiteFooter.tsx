import Link from "next/link";

export default function SiteFooter() {
  return (
    <footer className="border-t border-white/10 bg-black/20">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-5 px-5 py-8 text-sm text-zinc-400 sm:flex-row sm:items-center sm:justify-between sm:px-8">
        <div>
          <Link href="/" className="font-semibold text-white transition hover:text-violet-300">
            clankr
          </Link>
          <p className="mt-1">Understand the lyrics behind the music.</p>
        </div>

        <div className="flex items-center gap-5">
          <Link className="transition hover:text-white" href="/#analyze">
            Analyze a song
          </Link>
          <Link className="transition hover:text-white" href="/#all-songs">
            All songs
          </Link>
          <Link className="transition hover:text-white" href="/#your-songs">
            Your songs
          </Link>
        </div>
      </div>
    </footer>
  );
}
