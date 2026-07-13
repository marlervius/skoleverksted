"use client";

import { KeyRound, Loader2 } from "lucide-react";

interface Props {
  loginPasswordInput: string;
  setLoginPasswordInput: (v: string) => void;
  loginError: string | null;
  loginSubmitting: boolean;
  onSubmit: (e: React.FormEvent) => void;
}

export function LoginForm({
  loginPasswordInput,
  setLoginPasswordInput,
  loginError,
  loginSubmitting,
  onSubmit,
}: Props) {
  return (
    <main className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex items-center justify-center px-4">
      <div className="w-full max-w-md bg-slate-800/60 border border-slate-700/50 rounded-3xl p-8 shadow-xl">
        <div className="flex justify-center mb-6">
          <div className="p-3 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-2xl shadow-lg">
            <KeyRound className="w-8 h-8 text-white" />
          </div>
        </div>
        <h1 className="text-2xl font-bold text-center text-white mb-2">Scriptorium</h1>
        <p className="text-slate-400 text-sm text-center mb-6">
          Skriv inn passord for å generere leksjoner.
        </p>
        <form onSubmit={onSubmit} className="space-y-4">
          <input
            type="password"
            autoComplete="current-password"
            value={loginPasswordInput}
            onChange={(e) => setLoginPasswordInput(e.target.value)}
            placeholder="Passord"
            className="w-full px-4 py-3 rounded-xl bg-slate-900/70 border border-slate-600 text-white placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500/50"
            disabled={loginSubmitting}
          />
          {loginError && <p className="text-sm text-red-400">{loginError}</p>}
          <button
            type="submit"
            disabled={loginSubmitting || !loginPasswordInput.trim()}
            className="w-full py-3 rounded-xl font-semibold bg-gradient-to-r from-blue-600 to-indigo-600 text-white disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loginSubmitting ? (
              <span className="flex items-center justify-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin" /> Sjekker…
              </span>
            ) : (
              "Logg inn"
            )}
          </button>
        </form>
      </div>
    </main>
  );
}
