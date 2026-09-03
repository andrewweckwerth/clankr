import Link from "next/link";
import AuthControls from "@/components/AuthControls";

export default function SiteHeader() {
  return (
    <header className="y2k-header sticky top-0 z-40 border-b border-white/10">
      <div className="y2k-topbar mx-auto flex w-full max-w-6xl items-center justify-between gap-6 px-5 sm:px-8">
        <Link href="/" className="group flex items-center gap-2.5" aria-label="Clankr home">
          <span className="y2k-logo-mark flex h-8 w-8 items-center justify-center rounded-xl bg-[#28496f] text-lg font-black text-white shadow-lg shadow-[#28496f]/25 transition group-hover:bg-[#3d6799]">
            c
          </span>
          <span className="y2k-logo-word text-lg font-semibold tracking-tight text-white">clankr</span>
        </Link>

        <AuthControls />
      </div>

      <nav aria-label="Main navigation" className="y2k-nav-band">
        <div className="y2k-nav y2k-nav-links mx-auto flex w-full max-w-6xl items-center gap-0 overflow-x-auto px-5 sm:px-8">
          <Link className="transition hover:text-white" href="/projects/new">
            Full pipeline
          </Link>
          <Link className="transition hover:text-white" href="/tools">
            Tools
          </Link>
          <Link className="transition hover:text-white" href="/jobs">
            My Jobs
          </Link>
          <Link className="transition hover:text-white" href="/songs">
            Songs
          </Link>
        </div>
      </nav>
    </header>
  );
}
