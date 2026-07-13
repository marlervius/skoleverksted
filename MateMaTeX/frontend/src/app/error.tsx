"use client";

import { useEffect } from "react";
import { AlertTriangle } from "lucide-react";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="flex flex-col items-center justify-center min-h-[50vh] text-center px-4">
      <AlertTriangle size={40} className="text-accent-red mb-4 opacity-70" />
      <h1 className="font-display text-2xl mb-2">Noe gikk galt</h1>
      <p className="text-text-secondary text-sm mb-6 max-w-md" role="alert">
        {error.message || "En uventet feil oppstod. Prøv å laste siden på nytt."}
        {error.digest ? ` (${error.digest})` : ""}
      </p>
      <button type="button" onClick={reset} className="btn-primary">
        Prøv igjen
      </button>
    </div>
  );
}
