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
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 bg-slate-900/80 backdrop-blur-sm">
      <div className="bg-slate-800 border border-slate-700 rounded-2xl w-full max-w-4xl max-h-[90vh] flex flex-col shadow-2xl overflow-hidden animate-in fade-in zoom-in duration-200">
        {/* Header */}
        <div className="flex items-center justify-between p-4 sm:p-6 border-b border-slate-700 bg-slate-800/50">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-500/20 rounded-lg">
              <FileText className="w-5 h-5 text-blue-400" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-white leading-tight">Forhåndsvisning</h2>
              <p className="text-sm text-slate-400">
                {previewData.subject} • {previewData.level} • {previewData.topic}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-white hover:bg-slate-700 rounded-lg transition-colors"
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
                alt={previewData.topic}
                className="max-h-64 object-contain rounded-lg border border-slate-700 shadow-md"
                onError={(e) => {
                  e.currentTarget.style.display = "none";
                  const parent = e.currentTarget.parentElement;
                  if (parent) {
                    const msg = document.createElement("p");
                    msg.className = "text-xs text-red-400 mt-2";
                    msg.textContent =
                      "Kunne ikke laste inn forhåndsvisning av bildet (men det vil sannsynligvis fungere i PDF-en).";
                    parent.appendChild(msg);
                  }
                }}
              />
              <p className="text-xs text-slate-500 mt-2">Bilde fra Wikimedia Commons</p>
            </div>
          )}

          {/* Text */}
          <div>
            <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <BookOpen className="w-4 h-4 text-emerald-400" />
              Tekst
            </h3>
            <pre className="whitespace-pre-wrap font-sans text-sm sm:text-base text-slate-300 bg-slate-900/50 p-6 rounded-xl border border-slate-700/50">
              {previewData.text}
            </pre>
          </div>

          {/* Worksheet */}
          <div>
            <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <GraduationCap className="w-4 h-4 text-amber-400" />
              Oppgaver
            </h3>
            <pre className="whitespace-pre-wrap font-sans text-sm sm:text-base text-slate-300 bg-slate-900/50 p-6 rounded-xl border border-slate-700/50">
              {previewData.worksheet}
            </pre>
          </div>

          {/* Language Exercises */}
          {ex && (
            <div>
              <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                <Languages className="w-4 h-4 text-purple-400" />
                Språkøvelser (CLIL)
              </h3>
              <div className="bg-slate-900/50 p-6 rounded-xl border border-slate-700/50">
                {hasGrammar && (
                  <div className="mb-6">
                    <h4 className="text-emerald-400 font-semibold mb-3 border-b border-slate-700 pb-1">
                      Grammatikk
                    </h4>
                    {ex.grammar_tasks!.map((task: Record<string, unknown>, i) => (
                      <ExerciseBlock key={`g-${i}`} task={task} />
                    ))}
                  </div>
                )}
                {hasVocab && (
                  <div className="mb-6">
                    <h4 className="text-amber-400 font-semibold mb-3 border-b border-slate-700 pb-1">
                      Ordforråd
                    </h4>
                    {ex.vocabulary_tasks!.map((task: Record<string, unknown>, i) => (
                      <ExerciseBlock key={`v-${i}`} task={task} />
                    ))}
                  </div>
                )}
                {hasSyntax && (
                  <div className="mb-2">
                    <h4 className="text-sky-400 font-semibold mb-3 border-b border-slate-700 pb-1">
                      Setningsstruktur
                    </h4>
                    {ex.syntax_tasks!.map((task: Record<string, unknown>, i) => (
                      <ExerciseBlock key={`s-${i}`} task={task} />
                    ))}
                  </div>
                )}
                {!hasAnyExercises && (
                  <p className="text-sm text-slate-400 italic">Ingen språkøvelser ble generert.</p>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Footer Actions */}
        <div className="p-4 sm:p-6 border-t border-slate-700 bg-slate-800/80 backdrop-blur-sm flex flex-col sm:flex-row justify-between items-center gap-4">
          <p className="text-sm text-slate-400 flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            Ser dette bra ut?
          </p>
          <div className="flex w-full sm:w-auto gap-3">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 sm:flex-none px-6 py-2.5 rounded-lg text-slate-300 hover:text-white bg-slate-700/50 hover:bg-slate-700 font-medium transition-colors"
            >
              Avbryt
            </button>
            <button
              type="button"
              onClick={onGeneratePdf}
              disabled={formDisabled}
              className="flex-1 sm:flex-none px-6 py-2.5 rounded-lg text-white bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 font-medium shadow-lg hover:shadow-blue-500/25 transition-all flex items-center justify-center gap-2"
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
      <h5 className="text-white font-medium mb-1">
        {(task.type as string) || "Oppgave"}
      </h5>
      <p className="text-sm text-slate-400 mb-2">{task.instruction as string}</p>
      {items && items.length > 0 && (
        <ul className="list-disc list-inside text-sm text-slate-300 space-y-1 ml-2">
          {items.map((item, i) => (
            <li key={i}>{item}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
