"use client";

import { AlertCircle, CheckCircle2, Download, Sparkles } from "lucide-react";
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
      <div className="mt-6 p-4 bg-blue-500/10 border border-blue-500/20 rounded-xl">
        <div className="flex items-start gap-3">
          <div className="p-2 bg-blue-500/20 rounded-lg">
            <Sparkles className="w-5 h-5 text-blue-400 animate-pulse" />
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-2">
              <p className="text-blue-300 font-medium">
                {progress
                  ? `Steg ${progress.step}/${progress.totalSteps}`
                  : "Våre AI-agenter jobber..."}
              </p>
              {progress && (
                <div className="flex-1 bg-blue-500/20 rounded-full h-2">
                  <div
                    className="bg-blue-400 h-2 rounded-full transition-all duration-300"
                    style={{
                      width: `${(progress.step / progress.totalSteps) * 100}%`,
                    }}
                  />
                </div>
              )}
            </div>
            <p className="text-blue-400/70 text-sm">
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
      <div className="mt-6 p-4 bg-red-500/10 border border-red-500/20 rounded-xl">
        <div className="flex items-start gap-3">
          <div className="p-2 bg-red-500/20 rounded-lg">
            <AlertCircle className="w-5 h-5 text-red-400" />
          </div>
          <div>
            <p className="text-red-300 font-medium">Noe gikk galt</p>
            <p className="text-red-400/70 text-sm mt-1">{errorMessage}</p>
            <button
              type="button"
              onClick={onDismissError}
              className="text-red-400 text-sm mt-2 hover:text-red-300 underline"
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
      <div className="mt-6 p-4 bg-emerald-500/10 border border-emerald-500/20 rounded-xl">
        <div className="flex items-start gap-3">
          <div className="p-2 bg-emerald-500/20 rounded-lg">
            <Download className="w-5 h-5 text-emerald-400" />
          </div>
          <div>
            <p className="text-emerald-300 font-medium">
              {isDual ? "ZIP-en er klar!" : "PDF-en er klar!"}
            </p>
            <p className="text-emerald-400/70 text-sm mt-1">
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
