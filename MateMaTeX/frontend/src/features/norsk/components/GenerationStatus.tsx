"use client";

import { AlertCircle, Download, Sparkles } from "lucide-react";
import type {
  GenerationProgress,
  GenerationStatus as GenerationStatusValue,
  RecoveryAction,
} from "../lib/generationMachine";

interface Props {
  status: GenerationStatusValue;
  progress: GenerationProgress | null;
  errorMessage: string;
  requestId: string | null;
  failedStepName: string | null;
  availableActions: RecoveryAction[];
  isDual: boolean;
  onRetry: () => void;
  onCancel: () => void;
  onRetryImage: () => void;
  onContinueWithoutImage: () => void;
  onChooseCommons: () => void;
  onUploadImage: () => void;
}

function SupportReference({ requestId }: { requestId: string | null }) {
  if (!requestId) return null;
  return <p className="text-xs text-stone-500 mt-2">Referanse til support: <code>{requestId}</code></p>;
}

export function GenerationStatus({
  status,
  progress,
  errorMessage,
  requestId,
  failedStepName,
  availableActions,
  isDual,
  onRetry,
  onCancel,
  onRetryImage,
  onContinueWithoutImage,
  onChooseCommons,
  onUploadImage,
}: Props) {
  if (status === "generating") {
    const stepLabel = progress?.stepName
      ? `Steg ${progress.step}/${progress.totalSteps} · ${progress.stepName}`
      : progress
        ? `Steg ${progress.step}/${progress.totalSteps}`
        : "Våre AI-agenter jobber …";
    return (
      <div className="mt-6 p-4 bg-accent-50 border border-accent-200 rounded-lg" role="status" aria-live="polite">
        <div className="flex items-start gap-3">
          <div className="p-2 bg-accent-100 rounded-md shrink-0">
            <Sparkles className="w-5 h-5 text-accent-700 animate-pulse" aria-hidden="true" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-2">
              <p className="text-accent-800 font-medium">{stepLabel}</p>
              {progress && (
                <div className="flex-1 bg-accent-100 rounded-full h-2">
                  <div
                    className="bg-accent-600 h-2 rounded-full transition-all duration-300"
                    style={{ width: `${Math.max(0, Math.min(100, (progress.step / progress.totalSteps) * 100))}%` }}
                  />
                </div>
              )}
            </div>
            <p className="text-stone-600 text-sm">{progress?.message || "Starter kontrollert generering …"}</p>
            <button type="button" onClick={onCancel} className="text-stone-600 text-sm mt-3 underline">Avbryt</button>
          </div>
        </div>
      </div>
    );
  }

  if (status === "needs_user_action") {
    const has = (action: RecoveryAction) => availableActions.includes(action);
    return (
      <div className="mt-6 p-4 bg-amber-50 border border-amber-200 rounded-lg" role="alert" aria-live="assertive">
        <p className="text-amber-900 font-medium">Bildebehandlingen trenger et valg</p>
        {failedStepName && <p className="text-xs text-amber-800 mt-1">Steg: {failedStepName}</p>}
        <p className="text-amber-800 text-sm mt-1">{errorMessage}</p>
        <SupportReference requestId={requestId} />
        <div className="flex flex-wrap gap-2 mt-3">
          {has("retry_image") && <button type="button" onClick={onRetryImage} className="btn-secondary px-3 py-2 text-sm">Prøv bildet på nytt</button>}
          {has("continue_without_image") && <button type="button" onClick={onContinueWithoutImage} className="btn-secondary px-3 py-2 text-sm">Fortsett uten bilde</button>}
          {has("choose_commons") && <button type="button" onClick={onChooseCommons} className="btn-secondary px-3 py-2 text-sm">Velg frie bilder</button>}
          {has("upload_image") && <button type="button" onClick={onUploadImage} className="btn-secondary px-3 py-2 text-sm">Last opp eget bilde</button>}
          <button type="button" onClick={onCancel} className="px-3 py-2 text-sm text-stone-600 underline">Avbryt</button>
        </div>
      </div>
    );
  }

  if (status === "failed" || status === "cancelled" || status === "needs_teacher_review") {
    const teacherReview = status === "needs_teacher_review";
    const cancelled = status === "cancelled";
    return (
      <div
        className={`mt-6 p-4 rounded-lg border ${teacherReview ? "bg-amber-50 border-amber-200" : cancelled ? "bg-stone-50 border-stone-200" : "bg-red-50 border-red-200"}`}
        role={teacherReview || cancelled ? "status" : "alert"}
        aria-live={teacherReview || cancelled ? "polite" : "assertive"}
      >
        <div className="flex items-start gap-3">
          <div className={`p-2 rounded-md ${teacherReview ? "bg-amber-100" : "bg-red-100"}`}>
            <AlertCircle className={`w-5 h-5 ${teacherReview ? "text-amber-700" : "text-red-600"}`} aria-hidden="true" />
          </div>
          <div>
            <p className="font-medium text-stone-900">
              {teacherReview ? "Lærergjennomgang kreves" : cancelled ? "Genereringen er avbrutt" : "Genereringen stoppet"}
            </p>
            {failedStepName && <p className="text-xs text-stone-600 mt-1">Steg: {failedStepName}</p>}
            {errorMessage && <p className="text-stone-700 text-sm mt-1">{errorMessage}</p>}
            <SupportReference requestId={requestId} />
            {!teacherReview && (
              <div className="flex gap-3 mt-3">
                <button type="button" onClick={onRetry} className="text-red-700 text-sm underline">Prøv igjen</button>
                {!cancelled && <button type="button" onClick={onCancel} className="text-stone-600 text-sm underline">Avbryt</button>}
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  if (status === "completed") {
    return (
      <div className="mt-6 p-4 bg-accent-50 border border-accent-200 rounded-lg" role="status" aria-live="polite">
        <div className="flex items-start gap-3">
          <div className="p-2 bg-accent-100 rounded-md"><Download className="w-5 h-5 text-accent-700" aria-hidden="true" /></div>
          <div>
            <p className="text-accent-800 font-medium">{isDual ? "ZIP-forhåndsvisningen er klar" : "PDF-forhåndsvisningen er klar"}</p>
            <p className="text-stone-500 text-sm mt-1">Kontroller filen, og velg deretter godkjent nedlasting.</p>
          </div>
        </div>
      </div>
    );
  }

  return null;
}
