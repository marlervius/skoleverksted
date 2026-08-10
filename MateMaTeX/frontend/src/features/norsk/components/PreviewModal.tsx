"use client";

import {
  BookOpen,
  CheckCircle2,
  FileText,
  GraduationCap,
  Image as ImageIcon,
  Languages,
  Loader2,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import type { CommonsImageCandidate, LessonResponse } from "../lib/fovTypes";
import { TruthPassport } from "@/components/truth-passport";

interface Props {
  previewData: LessonResponse;
  formDisabled: boolean;
  isGenerating: boolean;
  onClose: () => void;
  onGeneratePdf: () => void;
  onSelectImage: (candidate: CommonsImageCandidate | null) => void;
}

export function PreviewModal({
  previewData,
  formDisabled,
  isGenerating,
  onClose,
  onGeneratePdf,
  onSelectImage,
}: Props) {
  const ex = previewData.language_exercises;
  const imageCandidates = previewData.image_candidates ?? [];
  const selectedImageUrl = previewData.image_url ?? null;
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
          {previewData.truth_passport && (
            <TruthPassport passport={previewData.truth_passport} />
          )}
          {(previewData.quarantine?.length ?? 0) > 0 && (
            <section className="rounded-xl border border-amber-300 bg-amber-50 p-4">
              <h3 className="font-semibold text-amber-950">Utelatt i karantene</h3>
              <p className="mt-1 text-sm text-amber-900">
                Disse punktene er ikke med i teksten eller eksporten. Kontroller konsekvensen før godkjenning.
              </p>
              <ul className="mt-3 space-y-2 text-sm text-amber-950">
                {previewData.quarantine!.map((item, index) => (
                  <li key={String(item.claim_id ?? index)} className="rounded border border-amber-200 bg-white p-3">
                    <p className="font-medium">{String(item.original_text ?? "Ukjent påstand")}</p>
                    <p className="mt-1 text-xs">{String(item.reason ?? "Mangler sikker dokumentasjon")}</p>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {imageCandidates.length > 0 && (
            <section className="rounded-xl border border-stone-200 bg-stone-50 p-4 sm:p-5">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <h3 className="flex items-center gap-2 font-semibold text-stone-900">
                    <ImageIcon className="h-4 w-4 text-accent-700" aria-hidden="true" />
                    Velg bilde til PDF-en
                  </h3>
                  <p className="mt-1 max-w-2xl text-sm text-stone-600">
                    Alle forslagene har fri lisens og tilfredsstiller tekniske minstekrav.
                    Bildekritikerens anbefaling er forhåndsvalgt; øvrige forslag må du
                    vurdere faglig før bruk.
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-800">
                  <ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" />
                  Lisens kontrollert
                </div>
              </div>

              <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {imageCandidates.map((candidate) => {
                  const selected = selectedImageUrl === candidate.image_url;
                  return (
                    <article
                      key={candidate.image_url}
                      className={`overflow-hidden rounded-lg border bg-white transition ${
                        selected
                          ? "border-accent-600 ring-2 ring-accent-600/20"
                          : "border-stone-200 hover:border-stone-400"
                      }`}
                    >
                      <button
                        type="button"
                        onClick={() => onSelectImage(candidate)}
                        aria-pressed={selected}
                        className="block w-full text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-accent-600"
                      >
                        <div className="relative h-32 bg-stone-100">
                          {/* eslint-disable-next-line @next/next/no-img-element */}
                          <img
                            src={candidate.thumbnail_url || candidate.image_url}
                            alt={candidate.alt_text || candidate.title}
                            loading="lazy"
                            className="h-full w-full object-cover"
                          />
                          <span
                            className={`absolute left-2 top-2 rounded-full px-2 py-1 text-[11px] font-semibold shadow-sm ${
                              candidate.recommended
                                ? "bg-emerald-700 text-white"
                                : "bg-white/95 text-stone-700"
                            }`}
                          >
                            {candidate.recommended
                              ? "Anbefalt av bildekritikeren"
                              : "Mulig alternativ"}
                          </span>
                          {selected && (
                            <span className="absolute bottom-2 right-2 rounded-full bg-accent-700 px-2 py-1 text-[11px] font-semibold text-white shadow-sm">
                              Valgt
                            </span>
                          )}
                        </div>
                        <div className="p-3">
                          <p className="line-clamp-2 text-sm font-medium text-stone-900">
                            {candidate.title}
                          </p>
                          <p className="mt-1 text-xs text-stone-500">
                            {candidate.license}
                            {candidate.creator ? ` · ${candidate.creator}` : ""}
                          </p>
                        </div>
                      </button>
                      <div className="border-t border-stone-100 px-3 py-2">
                        <a
                          href={candidate.source_page_url}
                          target="_blank"
                          rel="noreferrer"
                          className="text-xs text-stone-500 underline hover:text-stone-800"
                        >
                          Åpne kildesiden
                        </a>
                      </div>
                    </article>
                  );
                })}
              </div>

              <button
                type="button"
                onClick={() => onSelectImage(null)}
                className={`mt-4 rounded-lg border px-4 py-2 text-sm font-medium transition ${
                  !selectedImageUrl
                    ? "border-stone-700 bg-stone-800 text-white"
                    : "border-stone-300 bg-white text-stone-700 hover:bg-stone-100"
                }`}
              >
                Lag PDF uten bilde
              </button>
            </section>
          )}

          {/* Image */}
          {previewData.image_url && previewData.image_url !== "none" && (
            <div className="flex flex-col items-center" aria-live="polite">
              <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-stone-500">
                Valgt bilde
              </p>
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
