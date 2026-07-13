"use client";

import React from "react";
import { Sparkles, AlertCircle, CheckCircle2 } from "lucide-react";
import type { Status } from "./constants";

interface StatusMessagesProps {
  status: Status;
  errorMessage: string;
  onRetry: () => void;
  elapsedSeconds: number;
  progressMessage?: string;
}

// All possible steps (order matters — matches what the backend emits)
const ALL_PROGRESS_STEPS = [
  "Genererer fagtekst og søker etter bilde...",
  "Analyserer og strukturerer innhold...",
  "Henter og optimaliserer bilde...",
  "Kompilerer PDF...",
];

// Build the visible step list dynamically based on which messages have appeared
function buildVisibleSteps(current: string): string[] {
  const idx = ALL_PROGRESS_STEPS.indexOf(current);
  if (idx === -1) return ALL_PROGRESS_STEPS;
  // Show at least all steps up to and including current
  return ALL_PROGRESS_STEPS;
}

function stepIndex(msg: string): number {
  return ALL_PROGRESS_STEPS.findIndex((s) => s === msg);
}

export const StatusMessages = React.memo(function StatusMessages({
  status,
  errorMessage,
  onRetry,
  elapsedSeconds,
  progressMessage,
}: StatusMessagesProps) {
  if (status === "loading") {
    const currentStep = progressMessage ? stepIndex(progressMessage) : -1;
    const visibleSteps = buildVisibleSteps(progressMessage || "");

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
            <p className="text-accent-800 font-medium">
              {progressMessage || "Kobler til modellen..."}
            </p>

            {/* Step progress dots */}
            <div className="flex items-center gap-1.5 mt-3">
              {visibleSteps.map((step, i) => (
                <div key={step} className="flex items-center gap-1.5">
                  {i < currentStep ? (
                    <CheckCircle2 className="w-4 h-4 text-accent-600 shrink-0" aria-hidden="true" />
                  ) : i === currentStep ? (
                    <div className="w-3 h-3 rounded-full bg-accent-600 animate-pulse shrink-0" />
                  ) : (
                    <div className="w-3 h-3 rounded-full bg-stone-300 shrink-0" />
                  )}
                  {i < visibleSteps.length - 1 && (
                    <div
                      className={`h-px w-4 ${i < currentStep ? "bg-accent-400" : "bg-stone-300"}`}
                    />
                  )}
                </div>
              ))}
            </div>

            <p className="text-stone-400 text-xs mt-2 font-mono">
              {elapsedSeconds > 0 ? `${elapsedSeconds}s` : "Starter..."}
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
              onClick={onRetry}
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
            <CheckCircle2 className="w-5 h-5 text-accent-700" aria-hidden="true" />
          </div>
          <div>
            <p className="text-accent-800 font-medium">PDF-en er klar</p>
            <p className="text-stone-500 text-sm mt-1">
              Filen er lastet ned til datamaskinen din.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return null;
});
