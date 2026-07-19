"use client";

import { AlertCircle, Download, Sparkles } from "lucide-react";
import type { Status } from "../lib/fovTypes";

interface ProgressState {
  step: number;
  totalSteps: number;
  message: string;
}

interface Props {
  status: Status;
  progress: ProgressState | null;
  errorMessage: string;
  isDual: boolean;
  onDismissError: () => void;
}

export function GenerationStatus({
  status,
  progress,
  errorMessage,
  isDual,
  onDismissError,
}: Props) {
  if (status === "loading") {
    return (
      <div
        className="mt-6 p-4 bg-accent-50 border border-accent-200 rounded-lg"
        role="status"
        aria-live="polite"
      >
        <div className="flex items-start gap-3">
          <div className="p-2 bg-accent-100 rounded-md shrink-0">
            <Sparkles className="w-5 h-5 text-accent-700 animate-pulse" aria-hidden="true" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-2">
              <p className="text-accent-800 font-medium">
                {progress
                  ? `Steg ${progress.step}/${progress.totalSteps}`
                  : "Våre AI-agenter jobber..."}
              </p>
              {progress && (
                <div className="flex-1 bg-accent-100 rounded-full h-2">
                  <div
                    className="bg-accent-600 h-2 rounded-full transition-all duration-300"
                    style={{
                      width: `${(progress.step / progress.totalSteps) * 100}%`,
                    }}
                  />
                </div>
              )}
            </div>
            <p className="text-stone-500 text-sm">
              {progress
                ? progress.message
                : "Dette kan ta 30-60 sekunder. Vi skriver tekst, lager oppgaver og formaterer PDF-en din."}
            </p>
          </div>
        </div>
      </div>
    );
  }

  if (status === "error") {
    return (
      <div
        className="mt-6 p-4 bg-red-50 border border-red-200 rounded-lg"
        role="alert"
        aria-live="assertive"
      >
        <div className="flex items-start gap-3">
          <div className="p-2 bg-red-100 rounded-md">
            <AlertCircle className="w-5 h-5 text-red-600" aria-hidden="true" />
          </div>
          <div>
            <p className="text-red-800 font-medium">Noe gikk galt</p>
            <p className="text-red-600 text-sm mt-1">{errorMessage}</p>
            <button
              type="button"
              onClick={onDismissError}
              className="text-red-700 text-sm mt-2 hover:text-red-800 underline focus:outline-none focus:ring-2 focus:ring-red-300 rounded"
            >
              Prøv igjen
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (status === "success") {
    return (
      <div
        className="mt-6 p-4 bg-accent-50 border border-accent-200 rounded-lg"
        role="status"
        aria-live="polite"
      >
        <div className="flex items-start gap-3">
          <div className="p-2 bg-accent-100 rounded-md">
            <Download className="w-5 h-5 text-accent-700" aria-hidden="true" />
          </div>
          <div>
            <p className="text-accent-800 font-medium">
              {isDual ? "ZIP-en er klar!" : "PDF-en er klar!"}
            </p>
            <p className="text-stone-500 text-sm mt-1">
              {isDual
                ? "ZIP-arkivet med to PDF-er er lastet ned til datamaskinen din."
                : "Filen er lastet ned til datamaskinen din."}
            </p>
          </div>
        </div>
      </div>
    );
  }

  return null;
}
