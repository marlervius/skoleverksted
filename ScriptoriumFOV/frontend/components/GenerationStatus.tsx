"use client";

import { AlertCircle, CheckCircle2, Download, Eye, Loader2, Sparkles } from "lucide-react";
import type { ArtifactMetadata, GenerationStatus } from "../lib/fovTypes";
import type { GenerationProgress } from "../lib/generationState";

interface Props {
  status: GenerationStatus;
  progress: GenerationProgress | null;
  errorMessage: string;
  requestId: string | null;
  jobId: string | null;
  artifact: ArtifactMetadata | null;
  artifactAction: "idle" | "downloading" | "previewing";
  isDual: boolean;
  onDismissError: () => void;
  onDownload: () => void;
  onPreview: () => void;
}

export function GenerationStatus({
  status,
  progress,
  errorMessage,
  requestId,
  jobId,
  artifact,
  artifactAction,
  isDual,
  onDismissError,
  onDownload,
  onPreview,
}: Props) {
  const isWorking = status === "generating" || status === "building_artifact";

  if (isWorking) {
    const isBuilding = status === "building_artifact";
    const progressPercent = progress
      ? Math.min(100, Math.max(0, (progress.step / Math.max(progress.totalSteps, 1)) * 100))
      : 0;
    return (
      <div className="mt-6 rounded-xl border border-blue-500/20 bg-blue-500/10 p-4">
        <div className="flex items-start gap-3">
          <div className="rounded-lg bg-blue-500/20 p-2">
            {isBuilding ? (
              <Loader2 className="h-5 w-5 animate-spin text-blue-400" />
            ) : (
              <Sparkles className="h-5 w-5 animate-pulse text-blue-400" />
            )}
          </div>
          <div className="flex-1">
            <div className="mb-2 flex items-center gap-2">
              <p className="font-medium text-blue-300">
                {isBuilding ? "Bygger og kontrollerer PDF …" : progress ? `Steg ${progress.step}/${progress.totalSteps}` : "Starter generering …"}
              </p>
              {progress && (
                <div className="h-2 flex-1 rounded-full bg-blue-500/20">
                  <div
                    className="h-2 rounded-full bg-blue-400 transition-all duration-300"
                    style={{ width: `${progressPercent}%` }}
                  />
                </div>
              )}
            </div>
            <p className="text-sm text-blue-400/70">
              {isBuilding
                ? "PDF-en bygges, valideres og lagres. Dette er ikke ferdig før artefaktet er bekreftet."
                : progress?.message || "Dette kan ta 30–60 sekunder. Vi skriver tekst, lager oppgaver og formaterer PDF-en din."}
            </p>
          </div>
        </div>
      </div>
    );
  }

  if (status === "completed" && artifact) {
    return (
      <div className="mt-6 rounded-xl border border-emerald-500/20 bg-emerald-500/10 p-4">
        <div className="flex items-start gap-3">
          <div className="rounded-lg bg-emerald-500/20 p-2">
            <CheckCircle2 className="h-5 w-5 text-emerald-400" />
          </div>
          <div className="flex-1">
            <p className="font-medium text-emerald-300">
              {isDual ? "ZIP-en er klar!" : "PDF klar for nedlasting"}
            </p>
            <p className="mt-1 text-sm text-emerald-400/80">
              {artifact.filename} · {Math.max(1, Math.round(artifact.size_bytes / 1024))} KB
            </p>
            {errorMessage && (
              <p className="mt-2 text-sm text-amber-300">{errorMessage}</p>
            )}
            <div className="mt-3 flex flex-wrap gap-2">
              <button
                type="button"
                onClick={onDownload}
                disabled={artifactAction !== "idle"}
                className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-60"
              >
                {artifactAction === "downloading" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
                {isDual ? "Last ned ZIP" : errorMessage ? "Hent PDF på nytt" : "Last ned PDF"}
              </button>
              {!isDual && artifact.preview_url && (
                <button
                  type="button"
                  onClick={onPreview}
                  disabled={artifactAction !== "idle"}
                  className="inline-flex items-center gap-2 rounded-lg bg-slate-700 px-4 py-2 text-sm font-medium text-slate-100 hover:bg-slate-600 disabled:opacity-60"
                >
                  {artifactAction === "previewing" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Eye className="h-4 w-4" />}
                  Forhåndsvis PDF
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (status === "failed" || status === "needs_teacher_review" || status === "cancelled") {
    return (
      <div className="mt-6 rounded-xl border border-red-500/20 bg-red-500/10 p-4">
        <div className="flex items-start gap-3">
          <div className="rounded-lg bg-red-500/20 p-2">
            <AlertCircle className="h-5 w-5 text-red-400" />
          </div>
          <div>
            <p className="font-medium text-red-300">
              {status === "needs_teacher_review" ? "Lærergjennomgang kreves" : status === "cancelled" ? "Genereringen ble avbrutt" : "PDF-en kunne ikke ferdigstilles"}
            </p>
            <p className="mt-1 text-sm text-red-400/80">{errorMessage || "Prøv igjen eller gå tilbake til redigering."}</p>
            <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-400">
              <span>Request-ID: {requestId || "—"}</span>
              <span>Jobb-ID: {jobId || artifact?.job_id || "—"}</span>
            </div>
            <button
              type="button"
              onClick={onDismissError}
              className="mt-3 text-sm text-red-300 underline hover:text-red-200"
            >
              Gå tilbake til redigering
            </button>
          </div>
        </div>
      </div>
    );
  }

  return null;
}
