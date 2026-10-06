"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { KeyRound, Loader2 } from "lucide-react";
import {
  ACCESS_REQUIRED_EVENT,
  AccessLoginError,
  clearAccessToken,
  fetchAccessStatus,
  installAccessInterceptor,
  isPublicPath,
  loginWithCode,
} from "@/lib/access";

type Phase = "checking" | "locked" | "problem" | "open";

/**
 * Holds the whole app behind the pilot's shared access code. When a token
 * expires mid-session the sign-in screen is laid over the app instead of
 * replacing it, so work that is on screen is not thrown away.
 */
export function AccessGate({ children }: { children: React.ReactNode }) {
  const pathname = usePathname() ?? "/";
  const isPublic = isPublicPath(pathname);
  const [phase, setPhase] = useState<Phase>("checking");
  const [everOpen, setEverOpen] = useState(false);
  const [problem, setProblem] = useState("");

  const check = useCallback(async () => {
    setPhase("checking");
    installAccessInterceptor();
    try {
      const status = await fetchAccessStatus();
      if (!status.configured) {
        setProblem("Tilgang er ikke satt opp på serveren ennå. Si fra til den som drifter Skoleverksted.");
        setPhase("problem");
      } else if (!status.required || status.authenticated) {
        setEverOpen(true);
        setPhase("open");
      } else {
        clearAccessToken();
        setPhase("locked");
      }
    } catch {
      setProblem("Fikk ikke kontakt med serveren. Kontroller nettverket og prøv igjen.");
      setPhase("problem");
    }
  }, []);

  useEffect(() => {
    if (!isPublic) void check();
  }, [isPublic, check]);

  useEffect(() => {
    const onRequired = () => setPhase("locked");
    window.addEventListener(ACCESS_REQUIRED_EVENT, onRequired);
    return () => window.removeEventListener(ACCESS_REQUIRED_EVENT, onRequired);
  }, []);

  const showApp = isPublic || everOpen || phase === "open";
  const overlay = !isPublic && phase !== "open";

  return (
    <>
      {showApp && children}
      {overlay && (
        <div className="fixed inset-0 z-[100] overflow-y-auto bg-bg">
          {phase === "locked" && (
            <SignIn
              onSignedIn={() => {
                setEverOpen(true);
                setPhase("open");
              }}
            />
          )}
          {phase === "problem" && <Problem message={problem} onRetry={() => void check()} />}
          {phase === "checking" && !everOpen && (
            <div className="flex min-h-screen items-center justify-center">
              <Loader2 className="h-10 w-10 animate-spin text-accent-600" aria-label="Laster" />
            </div>
          )}
        </div>
      )}
    </>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <main className="flex min-h-screen items-center justify-center px-4">
      <div className="surface-card w-full max-w-md p-8">
        <div className="mb-6 flex justify-center">
          <div className="rounded-xl bg-accent-700 p-3">
            <KeyRound className="h-8 w-8 text-white" />
          </div>
        </div>
        <h1 className="mb-2 text-center text-2xl font-semibold text-stone-900">Skoleverksted</h1>
        {children}
        <p className="mt-6 text-center text-xs text-stone-500">
          <Link href="/personvern" className="underline hover:text-stone-700">
            Personvern
          </Link>
        </p>
      </div>
    </main>
  );
}

function SignIn({ onSignedIn }: { onSignedIn: () => void }) {
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!code.trim()) return;
    setError(null);
    setSubmitting(true);
    try {
      await loginWithCode(code.trim());
      setCode("");
      onSignedIn();
    } catch (failure) {
      setError(failure instanceof AccessLoginError ? failure.message : "Kunne ikke logge inn.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Shell>
      <p className="mb-6 text-center text-sm text-stone-500">
        Skoleverksted er i lukket pilot. Skriv inn tilgangskoden du har fått.
      </p>
      <form onSubmit={submit} className="space-y-4">
        <label className="field-label" htmlFor="access-code">
          Tilgangskode
        </label>
        <input
          id="access-code"
          type="password"
          autoComplete="current-password"
          autoFocus
          value={code}
          onChange={(event) => setCode(event.target.value)}
          placeholder="Tilgangskode"
          className="input-field"
          disabled={submitting}
        />
        {error && (
          <p role="alert" className="text-sm text-red-600">
            {error}
          </p>
        )}
        <button type="submit" disabled={submitting || !code.trim()} className="btn-primary w-full py-3">
          {submitting ? (
            <span className="flex items-center justify-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin" /> Sjekker…
            </span>
          ) : (
            "Logg inn"
          )}
        </button>
      </form>
    </Shell>
  );
}

function Problem({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <Shell>
      <p role="alert" className="mb-6 text-center text-sm text-stone-600">
        {message}
      </p>
      <button type="button" onClick={onRetry} className="btn-primary w-full py-3">
        Prøv igjen
      </button>
    </Shell>
  );
}
