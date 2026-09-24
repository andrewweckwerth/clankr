import Link from "next/link";
import AuthPanel from "@/components/AuthPanel";

export default function SignUpPage() {
  return (
    <main className="flex min-h-[calc(100vh-9rem)] items-center justify-center px-5 py-16">
      <section className="panel w-full max-w-md rounded-lg border border-white/10 bg-white/[0.04] p-8 text-center sm:p-10">
        <h1 className="text-2xl font-semibold tracking-tight text-white">Create a Clankr account</h1>
        <p className="mt-4 text-sm leading-6 text-zinc-400">Use Google or an email and password to begin.</p>
        <div className="mt-8">
          <AuthPanel initialMode="sign-up" />
        </div>
        <p className="mt-8 text-sm text-zinc-500">Already have an account? <Link href="/sign-in" className="text-zinc-300 transition hover:text-white">Log in</Link></p>
      </section>
    </main>
  );
}
