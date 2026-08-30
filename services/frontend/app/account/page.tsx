'use client';

import Link from "next/link";
import { useEffect, useState } from "react";
import { authClient } from "@/lib/auth-client";

export default function AccountPage() {
  const { data: session, isPending } = authClient.useSession();
  const [linking, setLinking] = useState(false);
  const [accountsPending, setAccountsPending] = useState(true);
  const [googleLinked, setGoogleLinked] = useState(false);
  const [accountsError, setAccountsError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!session) {
      setAccountsPending(false);
      setGoogleLinked(false);
      return;
    }

    let active = true;
    setAccountsPending(true);
    setAccountsError(null);
    void authClient.listAccounts().then((result) => {
      if (!active) return;
      if (result.error) {
        setAccountsError(result.error.message || "Unable to load sign-in methods.");
      } else {
        setGoogleLinked(Boolean(result.data?.some((account) => account.providerId === "google")));
      }
      setAccountsPending(false);
    });

    return () => {
      active = false;
    };
  }, [session]);

  const handleLinkGoogle = async () => {
    setLinking(true);
    setError(null);
    try {
      const result = await authClient.linkSocial({ provider: "google", callbackURL: "/account" });
      if (result.error) setError(result.error.message || "Unable to link Google.");
      else setGoogleLinked(true);
    } catch {
      setError("Unable to link Google right now.");
    } finally {
      setLinking(false);
    }
  };

  if (isPending) {
    return <main className="mx-auto flex min-h-[calc(100vh-9rem)] max-w-2xl items-center justify-center px-5">Loading account…</main>;
  }

  if (!session) {
    return (
      <main className="mx-auto flex min-h-[calc(100vh-9rem)] max-w-2xl flex-col items-center justify-center px-5 text-center">
        <h1 className="text-3xl font-semibold text-white">Sign in to view your account</h1>
        <Link href="/sign-in" className="mt-6 rounded-full bg-white px-5 py-2.5 text-sm font-semibold text-zinc-950 hover:bg-violet-200">Sign in</Link>
      </main>
    );
  }

  return (
    <main className="mx-auto min-h-[calc(100vh-9rem)] w-full max-w-2xl px-5 py-14 sm:px-8">
      <Link href="/" className="text-sm text-zinc-400 transition hover:text-white">← Back to Clankr</Link>
      <section className="mt-8 rounded-3xl border border-white/10 bg-white/[0.04] p-7 sm:p-9">
        <p className="text-sm font-medium uppercase tracking-[0.2em] text-violet-300">Account</p>
        <h1 className="mt-3 text-3xl font-semibold text-white">{session.user.name}</h1>
        <p className="mt-2 text-zinc-400">{session.user.email}</p>

        <div className="mt-8 border-t border-white/10 pt-6">
          <h2 className="font-semibold text-white">Sign-in methods</h2>
          {accountsPending ? (
            <p className="mt-2 text-sm text-zinc-400">Checking linked sign-in methods…</p>
          ) : accountsError ? (
            <p className="mt-2 text-sm text-red-200">Unable to verify linked sign-in methods.</p>
          ) : googleLinked ? (
            <p className="mt-2 text-sm text-emerald-200">Google is linked to this account.</p>
          ) : (
            <>
              <p className="mt-2 text-sm leading-6 text-zinc-400">Link Google so you have another way to get back into this account.</p>
              <button
                type="button"
                onClick={handleLinkGoogle}
                disabled={linking}
                className="mt-5 rounded-full border border-white/15 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {linking ? "Connecting…" : "Link Google"}
              </button>
            </>
          )}
          {error && <p className="mt-3 text-sm text-red-200">{error}</p>}
        </div>
      </section>
    </main>
  );
}
