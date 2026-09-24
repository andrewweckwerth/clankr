import Link from "next/link";
import AuthPanel from "@/components/AuthPanel";

export default function SignInPage() {
  return (
    <main className="flex min-h-[calc(100vh-9rem)] items-center justify-center px-5 py-16">
      <section className="panel w-full max-w-md rounded-lg border border-white/10 bg-white/[0.04] p-8 text-center sm:p-10">
        <h1 className="text-2xl font-semibold tracking-tight text-white">Sign in to Clankr</h1>
        <p className="mt-4 text-sm leading-6 text-zinc-400">Use Google or your email and password.</p>
        <div className="mt-8">
          <AuthPanel />
        </div>
        <Link href="/" className="mt-8 inline-flex text-sm text-zinc-500 transition hover:text-white">Back to Clankr</Link>
      </section>
    </main>
  );
}
