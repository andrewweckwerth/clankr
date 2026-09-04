'use client';

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { authClient } from "@/lib/auth-client";

type AuthMode = "sign-in" | "sign-up";

function errorMessage(error: unknown) {
  if (error && typeof error === "object" && "message" in error && typeof error.message === "string") {
    return error.message;
  }
  return "Something went wrong. Please try again.";
}

export default function AuthPanel({ initialMode = "sign-in" }: { initialMode?: AuthMode }) {
  const router = useRouter();
  const [mode, setMode] = useState<AuthMode>(initialMode);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleGoogle = async () => {
    setPending(true);
    setError(null);
    try {
      const result = await authClient.signIn.social({ provider: "google", callbackURL: "/" });
      if (result.error) setError(errorMessage(result.error));
    } catch (caughtError) {
      setError(errorMessage(caughtError));
    } finally {
      setPending(false);
    }
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setPending(true);
    setError(null);

    const formData = new FormData(event.currentTarget);
    const email = String(formData.get("email") || "").trim();
    const password = String(formData.get("password") || "");

    try {
      if (mode === "sign-in") {
        const result = await authClient.signIn.email({ email, password });
        if (result.error) {
          setError(errorMessage(result.error));
          return;
        }
      } else {
        const confirmPassword = String(formData.get("confirmPassword") || "");

        if (password !== confirmPassword) {
          setError("Passwords do not match.");
          return;
        }

        const result = await authClient.signUp.email({
          name: email.split("@")[0] || "Clankr user",
          email,
          password,
          callbackURL: "/",
        });
        if (result.error) {
          setError(errorMessage(result.error));
          return;
        }
      }

      router.push("/");
      router.refresh();
    } catch (caughtError) {
      setError(errorMessage(caughtError));
    } finally {
      setPending(false);
    }
  };

  return (
    <div className="space-y-6 text-left">
      <button
        type="button"
        onClick={handleGoogle}
        disabled={pending}
        className="y2k-button flex w-full items-center justify-center gap-3 rounded-2xl px-4 py-3 text-sm font-semibold disabled:cursor-not-allowed"
      >
        <span className="text-base font-bold text-blue-600">G</span>
        Continue with Google
      </button>

      <div className="flex items-center gap-3 text-xs uppercase tracking-[0.18em] text-zinc-500">
        <span className="h-px flex-1 bg-white/10" />
        <span>or use email and password</span>
        <span className="h-px flex-1 bg-white/10" />
      </div>

      <div className="grid grid-cols-2 rounded-xl bg-white/[0.05] p-1 text-sm">
        <button
          type="button"
          onClick={() => {
            setMode("sign-in");
            setError(null);
          }}
          className={`rounded-lg border px-3 py-2 font-medium transition ${mode === "sign-in" ? "border-[#75add4] bg-[#285f8b] text-white" : "border-transparent text-zinc-400 hover:border-[#476f93] hover:text-white"}`}
        >
          Sign in
        </button>
        <button
          type="button"
          onClick={() => {
            setMode("sign-up");
            setError(null);
          }}
          className={`rounded-lg border px-3 py-2 font-medium transition ${mode === "sign-up" ? "border-[#75add4] bg-[#285f8b] text-white" : "border-transparent text-zinc-400 hover:border-[#476f93] hover:text-white"}`}
        >
          Create account
        </button>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <label className="block space-y-2 text-sm text-zinc-300">
          Email
          <input name="email" type="email" required autoComplete="email" className="auth-input" />
        </label>
        <label className="block space-y-2 text-sm text-zinc-300">
          Password
          <input name="password" type="password" required minLength={8} autoComplete={mode === "sign-in" ? "current-password" : "new-password"} className="auth-input" />
        </label>

        {mode === "sign-up" && (
          <label className="block space-y-2 text-sm text-zinc-300">
            Confirm password
            <input name="confirmPassword" type="password" required minLength={8} autoComplete="new-password" className="auth-input" />
          </label>
        )}

        {error && <p className="rounded-xl border border-red-400/25 bg-red-400/10 px-3 py-2 text-sm text-red-200">{error}</p>}

        <button
          type="submit"
          disabled={pending}
          className="y2k-button w-full rounded-2xl px-4 py-3 text-sm font-semibold disabled:cursor-not-allowed"
        >
          {pending ? "Please wait…" : mode === "sign-in" ? "Sign in" : "Create account"}
        </button>
      </form>

      {mode === "sign-up" && <p className="text-xs leading-5 text-zinc-500">Password recovery and email verification are not enabled yet.</p>}
    </div>
  );
}
