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
    <main className="min-h-screen bg-bg flex items-center justify-center px-4">
      <div className="w-full max-w-md surface-card p-8">
        <div className="flex justify-center mb-6">
          <div className="p-3 bg-accent-700 rounded-xl">
            <KeyRound className="w-8 h-8 text-white" />
          </div>
        </div>
        <h1 className="text-2xl font-semibold text-center text-stone-900 mb-2">Norsklæring</h1>
        <p className="text-stone-500 text-sm text-center mb-6">
          Skriv inn passord for å generere leksjoner.
        </p>
        <form onSubmit={onSubmit} className="space-y-4">
          <input
            type="password"
            autoComplete="current-password"
            value={loginPasswordInput}
            onChange={(e) => setLoginPasswordInput(e.target.value)}
            placeholder="Passord"
            className="input-field"
            disabled={loginSubmitting}
          />
          {loginError && <p className="text-sm text-red-600">{loginError}</p>}
          <button
            type="submit"
            disabled={loginSubmitting || !loginPasswordInput.trim()}
            className="btn-primary w-full py-3"
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
