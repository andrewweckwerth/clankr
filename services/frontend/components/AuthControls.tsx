'use client';

import Link from "next/link";
import { authClient } from "@/lib/auth-client";

export default function AuthControls() {
  const { data: session, isPending } = authClient.useSession();

  if (isPending) {
    return <span className="h-9 w-20 animate-pulse rounded-full bg-white/10" aria-label="Loading account" />;
  }

  if (!session) {
    return (
      <Link
        href="/sign-in"
        className="rounded-full border border-white/15 bg-white px-4 py-2 text-sm font-semibold text-zinc-950 transition hover:bg-violet-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400 focus-visible:ring-offset-2 focus-visible:ring-offset-[#0b0b0d]"
      >
        Sign in
      </Link>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <Link
        href="/account"
        className="hidden max-w-36 truncate text-sm text-zinc-300 transition hover:text-white sm:block"
        title="Account settings"
      >
        {session.user.name}
      </Link>
      <button
        type="button"
        onClick={() => void authClient.signOut()}
        className="rounded-full border border-white/15 px-4 py-2 text-sm font-semibold text-white transition hover:bg-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400"
      >
        Sign out
      </button>
    </div>
  );
}
