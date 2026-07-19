"use client";

import {
  BookOpen,
  CheckCircle2,
  FileText,
  GraduationCap,
  Languages,
  Loader2,
  Sparkles,
} from "lucide-react";
import type { LessonResponse } from "../lib/fovTypes";

interface Props {
  previewData: LessonResponse;
  formDisabled: boolean;
  isGenerating: boolean;
  onClose: () => void;
  onGeneratePdf: () => void;
}

export function PreviewModal({
  previewData,
  formDisabled,
  isGenerating,
  onClose,
  onGeneratePdf,
}: Props) {
  const ex = previewData.language_exercises;
  const hasGrammar = (ex?.grammar_tasks?.length ?? 0) > 0;
  const hasVocab = (ex?.vocabulary_tasks?.length ?? 0) > 0;
  const hasSyntax = (ex?.syntax_tasks?.length ?? 0) > 0;
  const hasAnyExercises = hasGrammar || hasVocab || hasSyntax;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 bg-stone-900/40 backdrop-blur-sm">
      <div className="bg-white border border-stone-200 rounded-xl shadow-pop w-full max-w-4xl max-h-[90vh] flex flex-col overflow-hidden animate-in fade-in zoom-in duration-200">
        {/* Header */}
        <div className="flex items-center justify-between p-4 sm:p-6 border-b border-stone-200">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-accent-100 rounded-md">
              <FileText className="w-5 h-5 text-accent-700" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-stone-900 leading-tight">Forhåndsvisning</h2>
              <p className="text-sm text-stone-500">
                {previewData.subject} • {previewData.level} • {previewData.topic}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-stone-400 hover:text-stone-700 hover:bg-stone-100 rounded-lg transition-colors"
          >
            Lukk
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-8">
          {/* Image */}
          {previewData.image_url && previewData.image_url !== "none" && (
            <div className="flex flex-col items-center">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={previewData.image_url}
                alt={previewData.image_caption || previewData.topic}
                className="max-h-64 object-contain rounded-lg border border-stone-200 shadow-card"
                onError={(e) => {
                  e.currentTarget.style.display = "none";
                  const parent = e.currentTarget.parentElement;
                  if (parent) {
                    const msg = document.createElement("p");
                    msg.className = "text-xs text-red-600 mt-2";
                    msg.textContent =
                      "Kunne ikke laste inn forhåndsvisning av bildet (men det vil sannsynligvis fungere i PDF-en).";
                    parent.appendChild(msg);
                  }
                }}
              />
              {previewData.image_caption && (
                <p className="mt-2 text-sm italic text-stone-600">{previewData.image_caption}</p>
              )}
              <p className="mt-1 max-w-2xl text-center text-xs text-stone-400">
                {previewData.image_credit || "Kilde: Wikimedia Commons"}
                {previewData.image_source_page && (
                  <>
                    {" · "}
                    <a
                      href={previewData.image_source_page}
                      target="_blank"
                      rel="noreferrer"
                      className="underline hover:text-stone-600"
                    >
                      kildeside
                    </a>
                  </>
                )}
              </p>
            </div>
          )}
          {previewData.image_mode === "ai" && !previewData.image_url && (
            <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
              KI-illustrasjonen lages først når du velger «Lag PDF», slik at forhåndsvisning ikke utløser et ekstra betalt bildekall.
            </div>
          )}

          {/* Text */}
          <div>
            <h3 className="text-lg font-semibold text-stone-800 mb-4 flex items-center gap-2">
              <BookOpen className="w-4 h-4 text-accent-600" />
              Tekst
            </h3>
            <pre className="whitespace-pre-wrap font-sans text-sm sm:text-base text-stone-700 bg-stone-50 p-6 rounded-lg border border-stone-200">
              {previewData.text}
            </pre>
          </div>

          {/* Worksheet */}
          <div>
            <h3 className="text-lg font-semibold text-stone-800 mb-4 flex items-center gap-2">
              <GraduationCap className="w-4 h-4 text-accent-600" />
              Oppgaver
            </h3>
            <pre className="whitespace-pre-wrap font-sans text-sm sm:text-base text-stone-700 bg-stone-50 p-6 rounded-lg border border-stone-200">
              {previewData.worksheet}
            </pre>
          </div>

          {/* Language Exercises */}
          {ex && (
            <div>
              <h3 className="text-lg font-semibold text-stone-800 mb-4 flex items-center gap-2">
                <Languages className="w-4 h-4 text-accent-600" />
                Språkøvelser (CLIL)
              </h3>
              <div className="bg-stone-50 p-6 rounded-lg border border-stone-200">
                {hasGrammar && (
                  <div className="mb-6">
                    <h4 className="text-accent-800 font-semibold mb-3 border-b border-stone-200 pb-1">
                      Grammatikk
                    </h4>
                    {ex.grammar_tasks!.map((task: Record<string, unknown>, i) => (
                      <ExerciseBlock key={`g-${i}`} task={task} />
                    ))}
                  </div>
                )}
                {hasVocab && (
                  <div className="mb-6">
                    <h4 className="text-accent-800 font-semibold mb-3 border-b border-stone-200 pb-1">
                      Ordforråd
                    </h4>
                    {ex.vocabulary_tasks!.map((task: Record<string, unknown>, i) => (
                      <ExerciseBlock key={`v-${i}`} task={task} />
                    ))}
                  </div>
                )}
                {hasSyntax && (
                  <div className="mb-2">
                    <h4 className="text-accent-800 font-semibold mb-3 border-b border-stone-200 pb-1">
                      Setningsstruktur
                    </h4>
                    {ex.syntax_tasks!.map((task: Record<string, unknown>, i) => (
                      <ExerciseBlock key={`s-${i}`} task={task} />
                    ))}
                  </div>
                )}
                {!hasAnyExercises && (
                  <p className="text-sm text-stone-500 italic">Ingen språkøvelser ble generert.</p>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Footer Actions */}
        <div className="p-4 sm:p-6 border-t border-stone-200 bg-white flex flex-col sm:flex-row justify-between items-center gap-4">
          <p className="text-sm text-stone-500 flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-accent-700" />
            Ser dette bra ut?
          </p>
          <div className="flex w-full sm:w-auto gap-3">
            <button
              type="button"
              onClick={onClose}
              className="btn-secondary flex-1 sm:flex-none px-6 py-2.5"
            >
              Avbryt
            </button>
            <button
              type="button"
              onClick={onGeneratePdf}
              disabled={formDisabled}
              className="btn-primary flex-1 sm:flex-none px-6 py-2.5"
            >
              {isGenerating ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Genererer...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4" />
                  <span>Generer PDF nå</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function ExerciseBlock({ task }: { task: Record<string, unknown> }) {
  const items = task.items as string[] | undefined;
  return (
    <div className="mb-4 last:mb-0 ml-2">
      <h5 className="text-stone-800 font-medium mb-1">
        {(task.type as string) || "Oppgave"}
      </h5>
      <p className="text-sm text-stone-500 mb-2">{task.instruction as string}</p>
      {items && items.length > 0 && (
        <ul className="list-disc list-inside text-sm text-stone-700 space-y-1 ml-2">
          {items.map((item, i) => (
            <li key={i}>{item}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
