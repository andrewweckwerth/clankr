import Link from "next/link";
import AuthControls from "@/components/AuthControls";

export default function SiteHeader() {
  return (
    <header className="sticky top-0 z-40 border-b border-white/10 bg-[#0b0b0d]/85 backdrop-blur-xl">
      <nav
        aria-label="Main navigation"
        className="mx-auto flex h-18 w-full max-w-6xl items-center justify-between gap-6 px-5 sm:px-8"
      >
        <Link href="/" className="group flex items-center gap-2.5" aria-label="Clankr home">
          <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-violet-500 text-lg font-black text-white shadow-lg shadow-violet-500/25 transition group-hover:bg-violet-400">
            c
          </span>
          <span className="text-lg font-semibold tracking-tight text-white">clankr</span>
        </Link>

        <div className="hidden items-center gap-7 text-sm text-zinc-400 sm:flex">
          <Link className="transition hover:text-white" href="/#analyze">
            Analyze
          </Link>
          <Link className="transition hover:text-white" href="/#all-songs">
            All songs
          </Link>
          <Link className="transition hover:text-white" href="/#your-songs">
            Your songs
          </Link>
        </div>

        <AuthControls />
      </nav>
    </header>
  );
}
