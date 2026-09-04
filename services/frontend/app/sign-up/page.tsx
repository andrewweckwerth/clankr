import Link from "next/link";
import AuthPanel from "@/components/AuthPanel";

export default function SignUpPage() {
  return (
    <main className="flex min-h-[calc(100vh-9rem)] items-center justify-center px-5 py-16">
      <section className="y2k-panel-window y2k-auth-window w-full max-w-md rounded-3xl border border-white/10 bg-white/[0.04] p-8 text-center shadow-2xl shadow-black/20 sm:p-10" data-window-title="Join Clankr">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-[#326895] text-2xl font-black text-white shadow-lg shadow-[#326895]/25">
          c
        </div>
        <p className="mt-6 text-sm font-medium uppercase tracking-[0.2em] text-violet-300">Start your first analysis</p>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight text-white">Create a Clankr account</h1>
        <p className="mt-4 text-sm leading-6 text-zinc-400">Use Google or an email and password to begin.</p>
        <div className="mt-8">
          <AuthPanel initialMode="sign-up" />
        </div>
        <p className="mt-8 text-sm text-zinc-500">Already have an account? <Link href="/sign-in" className="text-zinc-300 transition hover:text-white">Log in</Link></p>
      </section>
    </main>
  );
}
