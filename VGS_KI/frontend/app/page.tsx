"use client";

import { useReducer, useCallback, useRef, useEffect, useState } from "react";
import {
  FileText,
  Loader2,
  Sparkles,
  GraduationCap,
  BookOpen,
  Languages,
  Settings2,
  ShieldCheck,
  ShieldAlert,
  CalendarDays,
  Users,
  X,
  Image as ImageIcon,
  Eye,
  Download,
  CheckCircle2,
  AlertCircle,
} from "lucide-react";

import {
  SUBJECTS,
  LEVELS,
  LANGUAGE_LEVELS,
  APP_MODES,
  PROFILES_STORAGE_KEY,
} from "./components/constants";
import type { LessonOptions, StudentProfile } from "./components/constants";
import { appReducer, initialState } from "./components/useAppReducer";
import { OptionToggle } from "./components/OptionToggle";
import { ProfileManager } from "./components/ProfileManager";
import { StatusMessages } from "./components/StatusMessages";
import { GrepPicker } from "./components/GrepPicker";
import type { CompetencyGoal } from "./components/api";
import {
  generateLesson,
  generateDifferentiated,
  generateProve,
  generateSequence,
  recompileLesson,
  fetchImageCandidates,
  downloadBlob,
  downloadDocx,
  createBlobUrl,
} from "./components/api";

export default function Home() {
  const [state, dispatch] = useReducer(appReducer, initialState);
  const abortControllerRef = useRef<AbortController | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const {
    mode, subject, level, languageLevel, topic, options,
    imageFile, description, showDescriptionTips, sourceText, showSourceText, useNdla, interest,
    profiles, profileResults, batchRunning,
    selectedGoal, includeFasit, antallUker, timerPerUke,
    status, errorMessage, elapsedSeconds, progressMessage,
    previewUrl, previewBlob, previewFilename, rapportBlob, rapportFilename, showPreview,
    basisText, generatedImageUrl, worksheetText, faktarapportText, languageExercises, warnings, sourceGrounded, sourceName, showEditPanel,
    imageCandidates, imageCandidatesLoading,
  } = state;

  const isFormValid = subject && level && topic.trim().length > 0;
  const isDifferensiert = mode === "differensiert";
  const isProve = mode === "prove";
  const isSekvens = mode === "sekvens";

  // ── localStorage session save / restore ─────────────────────────────────────
  const LS_KEY = "vgs_ki_session";
  const SESSION_MAX_AGE_MS = 7 * 24 * 60 * 60 * 1000;

  type SavedSession = {
    topic: string; subject: string; level: string; mode: string;
    basisText: string; worksheetText: string; faktarapportText: string | null;
    imageUrl: string | null; savedAt: number;
    languageExercises?: Record<string, unknown> | null;
    interest?: string;
  };
  const [pendingRestore, setPendingRestore] = useState<SavedSession | null>(null);

  // Load saved session on mount
  useEffect(() => {
    try {
      const raw = localStorage.getItem(LS_KEY);
      if (!raw) return;
      const s: SavedSession = JSON.parse(raw);
      if (s.basisText && s.savedAt && Date.now() - s.savedAt < SESSION_MAX_AGE_MS) {
        setPendingRestore(s);
      }
    } catch { /* ignore parse/quota errors */ }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Save session after successful generation (læringsark only)
  useEffect(() => {
    if (status === "success" && basisText && mode === "laeringsark") {
      try {
        localStorage.setItem(LS_KEY, JSON.stringify({
          topic, subject, level, mode,
          basisText, worksheetText: worksheetText ?? "",
          faktarapportText: faktarapportText ?? null,
          imageUrl: generatedImageUrl ?? null,
          languageExercises: languageExercises ?? null,
          interest: interest || undefined,
          savedAt: Date.now(),
        } satisfies SavedSession));
      } catch { /* ignore quota errors */ }
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status, basisText]);

  const handleRestoreSession = useCallback(() => {
    if (!pendingRestore) return;
    dispatch({
      type: "RESTORE_SESSION",
      topic: pendingRestore.topic,
      subject: pendingRestore.subject,
      level: pendingRestore.level,
      mode: pendingRestore.mode as import("./components/constants").AppMode,
      basisText: pendingRestore.basisText,
      worksheetText: pendingRestore.worksheetText,
      faktarapportText: pendingRestore.faktarapportText,
      imageUrl: pendingRestore.imageUrl,
      languageExercises: pendingRestore.languageExercises ?? null,
      interest: pendingRestore.interest ?? "",
    });
    setPendingRestore(null);
  }, [pendingRestore]);

  const handleDismissRestore = useCallback(() => {
    try { localStorage.removeItem(LS_KEY); } catch { /* ignore */ }
    setPendingRestore(null);
  }, []);

  // ── Student group profiles: load on mount, persist on change ───────────────
  useEffect(() => {
    try {
      const raw = localStorage.getItem(PROFILES_STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed)) dispatch({ type: "SET_PROFILES", profiles: parsed });
      }
    } catch { /* ignore parse errors */ }
  }, []);

  const handleProfilesChange = useCallback((next: StudentProfile[]) => {
    dispatch({ type: "SET_PROFILES", profiles: next });
    try { localStorage.setItem(PROFILES_STORAGE_KEY, JSON.stringify(next)); } catch { /* ignore quota */ }
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      if (abortControllerRef.current) abortControllerRef.current.abort();
      if (previewUrl) window.URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  // Auto-fetch image candidates after successful generation (læringsark only)
  useEffect(() => {
    if (status !== "success" || mode !== "laeringsark" || !topic || !subject) return;
    let cancelled = false;
    dispatch({ type: "IMAGE_CANDIDATES_LOADING" });
    fetchImageCandidates(topic, subject, 5).then((candidates) => {
      if (!cancelled) dispatch({ type: "IMAGE_CANDIDATES_LOADED", candidates });
    });
    return () => { cancelled = true; };
  }, [status, mode, topic, subject]);

  const startTimer = useCallback(() => {
    timerRef.current = setInterval(() => dispatch({ type: "TICK_TIMER" }), 1000);
  }, []);

  const stopTimer = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const handleGoalSelect = useCallback(
    (goal: CompetencyGoal) => {
      if (!goal.kode) {
        dispatch({ type: "SET_GOAL", goal: null });
        return;
      }
      dispatch({ type: "SET_GOAL", goal });
      if (!topic.trim()) {
        dispatch({ type: "SET_TOPIC", topic: goal.tittel });
      }
      const ref = `[LK20: ${goal.kode}]`;
      if (!description.includes(ref)) {
        dispatch({
          type: "SET_DESCRIPTION",
          description: description ? `${description}\n${ref}` : ref,
        });
      }
    },
    [topic, description]
  );

  const handleOptionChange = useCallback(
    (key: keyof LessonOptions, val: boolean) => {
      dispatch({ type: "SET_OPTION", key, val });
    },
    []
  );

  const handleTextLength = useCallback(
    (length: "kort" | "standard" | "lang") => {
      dispatch({ type: "SET_TEXT_LENGTH", length });
    },
    []
  );

  const handleCancel = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    stopTimer();
    dispatch({ type: "GENERATION_CANCEL" });
  }, [stopTimer]);

  const handleDownloadFromPreview = useCallback(() => {
    if (previewBlob) {
      downloadBlob(previewBlob, previewFilename);
    }
  }, [previewBlob, previewFilename]);

  const handleDownloadDocx = useCallback(async () => {
    if (!basisText) return;
    try {
      await downloadDocx({
        text: basisText,
        worksheet: worksheetText ?? "",
        faktarapport: faktarapportText ?? undefined,
        topic,
        subject,
        level,
      });
    } catch (e) {
      dispatch({ type: "GENERATION_ERROR", message: e instanceof Error ? e.message : "Docx-feil" });
    }
  }, [basisText, worksheetText, faktarapportText, topic, subject, level]);

  const handleRegenerate = useCallback(async () => {
    if (!basisText || mode !== "laeringsark") return;
    if (abortControllerRef.current) abortControllerRef.current.abort();
    const controller = new AbortController();
    abortControllerRef.current = controller;
    if (previewUrl) window.URL.revokeObjectURL(previewUrl);
    dispatch({ type: "GENERATION_START" });
    startTimer();
    try {
      const onProgress = (msg: string) =>
        dispatch({ type: "GENERATION_PROGRESS", message: msg });
      const result = await generateLesson({
        topic, subject, level, languageLevel, options,
        imageData: undefined,
        description: description.trim() || undefined,
        sourceText: sourceText.trim() || undefined,
        useNdla,
        interest: interest.trim() || undefined,
        basisText,
        imageUrlOverride: generatedImageUrl || undefined,
        signal: controller.signal, onProgress,
      });
      stopTimer();
      dispatch({
        type: "GENERATION_SUCCESS",
        blob: result.blob,
        url: createBlobUrl(result.blob),
        filename: result.filename,
        basisText: result.basisText ?? basisText,
        imageUrl: result.imageUrl ?? generatedImageUrl ?? undefined,
        worksheetText: result.worksheetText,
        faktarapportText: result.faktarapportText,
        languageExercises: result.languageExercises,
        warnings: [
          ...(result.warnings ?? []),
          ...(result.lintIssues ?? []).map((i) => `Kvalitetssjekk: ${i}`),
        ],
        sourceGrounded: result.sourceGrounded,
        sourceName: result.sourceName,
        rapportBlob: result.rapportBlob,
        rapportFilename: result.rapportFilename,
      });
      setTimeout(() => dispatch({ type: "GENERATION_IDLE" }), 8000);
    } catch (error) {
      stopTimer();
      if (error instanceof DOMException && error.name === "AbortError") {
        dispatch({ type: "GENERATION_CANCEL" });
        return;
      }
      dispatch({
        type: "GENERATION_ERROR",
        message: error instanceof Error ? error.message : "Kunne ikke regenerere. Prøv igjen.",
      });
    } finally {
      abortControllerRef.current = null;
      dispatch({ type: "GENERATION_PROGRESS", message: "" });
    }
  }, [basisText, generatedImageUrl, mode, topic, subject, level, languageLevel, options, description, sourceText, useNdla, interest, previewUrl, startTimer, stopTimer]);

  const handleOppdaterPdf = useCallback(async () => {
    if (!basisText || !worksheetText) return;
    if (abortControllerRef.current) abortControllerRef.current.abort();
    const controller = new AbortController();
    abortControllerRef.current = controller;
    if (previewUrl) window.URL.revokeObjectURL(previewUrl);
    dispatch({ type: "GENERATION_START" });
    startTimer();
    try {
      const result = await recompileLesson({
        text: basisText,
        worksheet: worksheetText,
        faktarapport: faktarapportText || undefined,
        topic,
        subject,
        level,
        languageLevel: languageLevel !== "none" ? languageLevel : undefined,
        options: options as Record<string, boolean>,
        imageUrl: generatedImageUrl || undefined,
        languageExercises: languageExercises || undefined,
        signal: controller.signal,
      });
      stopTimer();
      dispatch({
        type: "GENERATION_SUCCESS",
        blob: result.blob,
        url: createBlobUrl(result.blob),
        filename: result.filename,
        basisText,
        imageUrl: generatedImageUrl || undefined,
        worksheetText,
        faktarapportText: faktarapportText || undefined,
        languageExercises: languageExercises || undefined,
        sourceGrounded: sourceGrounded ?? undefined,
        sourceName: sourceName ?? undefined,
      });
      setTimeout(() => dispatch({ type: "GENERATION_IDLE" }), 8000);
    } catch (error) {
      stopTimer();
      if (error instanceof DOMException && error.name === "AbortError") {
        dispatch({ type: "GENERATION_CANCEL" });
        return;
      }
      dispatch({
        type: "GENERATION_ERROR",
        message: error instanceof Error ? error.message : "Kunne ikke oppdatere PDF. Prøv igjen.",
      });
    } finally {
      abortControllerRef.current = null;
      dispatch({ type: "GENERATION_PROGRESS", message: "" });
    }
  }, [basisText, worksheetText, faktarapportText, languageExercises, sourceGrounded, sourceName, generatedImageUrl, topic, subject, level, languageLevel, options, previewUrl, startTimer, stopTimer]);

  const handleSelectImage = useCallback(async (imageUrl: string) => {
    if (!basisText || !worksheetText) return;
    if (abortControllerRef.current) abortControllerRef.current.abort();
    const controller = new AbortController();
    abortControllerRef.current = controller;
    if (previewUrl) window.URL.revokeObjectURL(previewUrl);
    dispatch({ type: "GENERATION_START" });
    startTimer();
    try {
      const result = await recompileLesson({
        text: basisText,
        worksheet: worksheetText,
        faktarapport: faktarapportText || undefined,
        topic, subject, level,
        languageLevel: languageLevel !== "none" ? languageLevel : undefined,
        options: options as Record<string, boolean>,
        imageUrl,
        languageExercises: languageExercises || undefined,
        signal: controller.signal,
      });
      stopTimer();
      dispatch({
        type: "GENERATION_SUCCESS",
        blob: result.blob,
        url: createBlobUrl(result.blob),
        filename: result.filename,
        basisText,
        imageUrl,
        worksheetText,
        faktarapportText: faktarapportText || undefined,
        languageExercises: languageExercises || undefined,
        sourceGrounded: sourceGrounded ?? undefined,
        sourceName: sourceName ?? undefined,
      });
      setTimeout(() => dispatch({ type: "GENERATION_IDLE" }), 8000);
    } catch (error) {
      stopTimer();
      if (error instanceof DOMException && error.name === "AbortError") {
        dispatch({ type: "GENERATION_CANCEL" });
        return;
      }
      dispatch({
        type: "GENERATION_ERROR",
        message: error instanceof Error ? error.message : "Kunne ikke bytte bilde.",
      });
    } finally {
      abortControllerRef.current = null;
      dispatch({ type: "GENERATION_PROGRESS", message: "" });
    }
  }, [basisText, worksheetText, faktarapportText, languageExercises, sourceGrounded, sourceName, topic, subject, level, languageLevel, options, previewUrl, startTimer, stopTimer]);

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!isFormValid) return;

      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      const controller = new AbortController();
      abortControllerRef.current = controller;

      if (previewUrl) window.URL.revokeObjectURL(previewUrl);
      dispatch({ type: "GENERATION_START" });
      startTimer();

      try {
        let imageData: string | undefined;
        if (imageFile && mode !== "prove") {
          imageData = await new Promise<string>((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(reader.result as string);
            reader.onerror = reject;
            reader.readAsDataURL(imageFile);
          });
        }

        const onProgress = (msg: string) =>
          dispatch({ type: "GENERATION_PROGRESS", message: msg });

        let result;

        if (mode === "differensiert") {
          result = await generateDifferentiated({
            topic, subject, level, languageLevel, options, imageData,
            description: description.trim() || undefined,
            sourceText: sourceText.trim() || undefined,
            useNdla,
            interest: interest.trim() || undefined,
            signal: controller.signal, onProgress,
          });
        } else if (mode === "prove") {
          result = await generateProve({
            topic, subject, level, languageLevel, includeFasit,
            description: description.trim() || undefined,
            sourceText: sourceText.trim() || undefined,
            useNdla,
            signal: controller.signal, onProgress,
          });
        } else if (mode === "sekvens") {
          result = await generateSequence({
            topic, subject, level, antallUker, timerPerUke,
            grepGoals: selectedGoal?.kode ? [selectedGoal.kode] : [],
            description: description.trim() || undefined,
            signal: controller.signal, onProgress,
          });
        } else {
          result = await generateLesson({
            topic, subject, level, languageLevel, options, imageData,
            description: description.trim() || undefined,
            sourceText: sourceText.trim() || undefined,
            useNdla,
            interest: interest.trim() || undefined,
            basisText: undefined,
            imageUrlOverride: undefined,
            signal: controller.signal, onProgress,
          });
        }

        stopTimer();
        dispatch({
          type: "GENERATION_SUCCESS",
          blob: result.blob,
          url: createBlobUrl(result.blob),
          filename: result.filename,
          basisText: result.basisText,
          imageUrl: result.imageUrl,
          worksheetText: result.worksheetText,
          faktarapportText: result.faktarapportText,
          languageExercises: result.languageExercises,
          warnings: [
            ...(result.warnings ?? []),
            ...(result.lintIssues ?? []).map((i) => `Kvalitetssjekk: ${i}`),
          ],
          sourceGrounded: result.sourceGrounded,
          sourceName: result.sourceName,
          rapportBlob: result.rapportBlob,
          rapportFilename: result.rapportFilename,
        });

        setTimeout(() => dispatch({ type: "GENERATION_IDLE" }), 8000);
      } catch (error) {
        stopTimer();

        if (error instanceof DOMException && error.name === "AbortError") {
          dispatch({ type: "GENERATION_CANCEL" });
          return;
        }

        console.error("Error generating document:", error);

        const message =
          error instanceof TypeError && error.message === "Failed to fetch"
            ? "Kunne ikke nå serveren. Sjekk at backend kjører, eller prøv igjen om noen sekunder."
            : error instanceof Error
            ? error.message
            : "Kunne ikke generere dokumentet. Prøv igjen.";

        dispatch({ type: "GENERATION_ERROR", message });
      } finally {
        abortControllerRef.current = null;
        dispatch({ type: "GENERATION_PROGRESS", message: "" });
      }
    },
    [
      isFormValid, mode, topic, subject, level, languageLevel,
      options, imageFile, description, sourceText, useNdla, interest, includeFasit,
      antallUker, timerPerUke, selectedGoal,
      previewUrl, startTimer, stopTimer,
    ]
  );

  // ── Batch generation: one adapted version per student group profile ────────
  const handleGenerateForProfiles = useCallback(async () => {
    if (!isFormValid || profiles.length === 0) return;
    if (abortControllerRef.current) abortControllerRef.current.abort();
    const controller = new AbortController();
    abortControllerRef.current = controller;

    // Free object URLs from any previous batch run
    profileResults.forEach((r) => { if (r.url) window.URL.revokeObjectURL(r.url); });

    dispatch({
      type: "BATCH_START",
      results: profiles.map((p) => ({ profileId: p.id, label: p.label, status: "pending" as const })),
    });
    dispatch({ type: "GENERATION_START" });
    startTimer();

    try {
      for (let i = 0; i < profiles.length; i++) {
        const p = profiles[i];
        dispatch({ type: "BATCH_ITEM_START", profileId: p.id });
        try {
          const result = await generateLesson({
            topic, subject, level,
            languageLevel: p.languageLevel,
            options: { ...options, reading_friendly: p.readingFriendly },
            description: description.trim() || undefined,
            sourceText: sourceText.trim() || undefined,
            useNdla,
            interest: p.interest.trim() || undefined,
            signal: controller.signal,
            onProgress: (msg) =>
              dispatch({ type: "GENERATION_PROGRESS", message: `${p.label} (${i + 1}/${profiles.length}): ${msg}` }),
          });
          const safeLabel = p.label.replace(/[^\wæøåÆØÅ -]/g, "").trim().replace(/\s+/g, "-");
          dispatch({
            type: "BATCH_ITEM_SUCCESS",
            profileId: p.id,
            blob: result.blob,
            url: createBlobUrl(result.blob),
            filename: safeLabel ? `${safeLabel}-${result.filename}` : result.filename,
          });
        } catch (error) {
          // Abort stops the whole batch; other errors only fail this group
          if (error instanceof DOMException && error.name === "AbortError") throw error;
          dispatch({
            type: "BATCH_ITEM_ERROR",
            profileId: p.id,
            message: error instanceof Error ? error.message : "Ukjent feil",
          });
        }
      }
    } catch {
      // Batch aborted — remaining groups stay untouched
    } finally {
      stopTimer();
      abortControllerRef.current = null;
      dispatch({ type: "BATCH_DONE" });
    }
  }, [isFormValid, profiles, profileResults, topic, subject, level, options, description, sourceText, useNdla, startTimer, stopTimer]);

  const generateLabel =
    isProve
      ? "Generer prøve"
      : isDifferensiert
      ? "Generer differensiert PDF"
      : isSekvens
      ? "Generer sekvensplan"
      : "Generer læringsark";

  return (
    <main className="min-h-screen bg-stone-100">
      {/* Skip link */}
      <a
        href="#lesson-form"
        className="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 focus:z-50 focus:px-4 focus:py-2 focus:bg-accent-700 focus:text-white focus:rounded-lg"
      >
        Gå til skjema
      </a>

      {/* PDF Preview Modal */}
      {showPreview && previewUrl && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-stone-900/40 backdrop-blur-sm"
          role="dialog"
          aria-modal="true"
          aria-label="PDF-forhåndsvisning"
        >
          <div className="bg-white border border-stone-200 rounded-xl shadow-pop w-full max-w-4xl h-[90vh] flex flex-col overflow-hidden">
            <div className="flex items-center justify-between px-5 py-3 border-b border-stone-200">
              <div className="flex items-center gap-2">
                <Eye className="w-5 h-5 text-accent-700" aria-hidden="true" />
                <span className="text-stone-900 font-medium text-sm">Forhåndsvisning</span>
                <span className="text-stone-400 text-xs truncate max-w-[200px]">{previewFilename}</span>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={handleDownloadFromPreview}
                  className="btn-primary px-3 py-1.5 text-sm"
                >
                  <Download className="w-4 h-4" aria-hidden="true" />
                  Last ned
                </button>
                <button
                  type="button"
                  onClick={() => dispatch({ type: "CLOSE_PREVIEW" })}
                  className="p-1.5 text-stone-400 hover:text-stone-700 hover:bg-stone-100 rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-stone-300"
                  aria-label="Lukk forhåndsvisning"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>
            <iframe
              src={previewUrl}
              className="flex-1 w-full"
              title="PDF-forhåndsvisning"
            />
          </div>
        </div>
      )}

      {/* Top bar */}
      <header className="sticky top-0 z-30 bg-white/90 backdrop-blur border-b border-stone-200">
        <div className="mx-auto max-w-2xl px-4 h-14 flex items-center gap-2.5">
          <div className="flex items-center justify-center w-8 h-8 rounded-md bg-accent-700 text-white">
            <GraduationCap className="w-5 h-5" aria-hidden="true" />
          </div>
          <span className="font-semibold text-stone-900 tracking-tight">VGS Lærerassistent</span>
          <span className="ml-auto text-xs text-stone-400 hidden sm:block">Tilpasset LK20</span>
        </div>
      </header>

      <div className="mx-auto max-w-2xl px-4 py-8 sm:py-10">
        {/* Page intro */}
        <div className="mb-6">
          <h1 className="text-xl font-semibold text-stone-900 tracking-tight">
            Lag undervisningsmateriell
          </h1>
          <p className="text-stone-500 text-sm mt-1">
            Læringsark, differensierte ark, prøver og sekvensplaner — ferdige PDF-er klare til print.
          </p>
        </div>

        {/* Main Card */}
        <div className="w-full">
          <form onSubmit={handleSubmit} id="lesson-form" aria-label="Generer dokument">
            <div className="surface-card p-6 sm:p-7">

              {/* ── Session restore banner ───────────────────────────────────── */}
              {pendingRestore && status === "idle" && (
                <div className="mb-5 p-3.5 bg-accent-50 border border-accent-200 rounded-lg flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-accent-800">Forrige økt funnet</p>
                    <p className="text-xs text-stone-500 truncate">{pendingRestore.topic} · {pendingRestore.subject}</p>
                  </div>
                  <div className="flex gap-2 flex-shrink-0">
                    <button
                      type="button"
                      onClick={handleRestoreSession}
                      className="px-3 py-1.5 text-xs font-medium bg-accent-700 hover:bg-accent-800 text-white rounded-md transition-colors focus:outline-none focus:ring-2 focus:ring-accent-600/30"
                    >
                      Gjenopprett
                    </button>
                    <button
                      type="button"
                      onClick={handleDismissRestore}
                      className="p-1.5 text-stone-400 hover:text-stone-700 hover:bg-stone-100 rounded-md transition-colors focus:outline-none"
                      aria-label="Forkast forrige økt"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              )}

              {/* ── Mode Selector ────────────────────────────────────────────── */}
              <div className="mb-7">
                <div
                  className="grid grid-cols-4 gap-1 p-1 bg-stone-100 border border-stone-200 rounded-lg"
                  role="tablist"
                  aria-label="Velg dokumenttype"
                >
                  {APP_MODES.map((m) => (
                    <button
                      key={m.value}
                      type="button"
                      role="tab"
                      aria-selected={mode === m.value}
                      onClick={() => dispatch({ type: "SET_MODE", mode: m.value })}
                      disabled={status === "loading"}
                      className={`flex flex-col items-center gap-0.5 py-2 px-1.5 rounded-md text-xs font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-accent-600/30 ${
                        mode === m.value
                          ? "bg-white text-accent-800 shadow-card border border-stone-200"
                          : "text-stone-500 hover:text-stone-800 hover:bg-white/60 border border-transparent"
                      }`}
                    >
                      <span>{m.label}</span>
                      <span className="text-stone-400 text-[10px] font-normal leading-tight hidden sm:block text-center">
                        {m.description}
                      </span>
                    </button>
                  ))}
                </div>

                {isDifferensiert && (
                  <div className="mt-3 px-3.5 py-2.5 bg-stone-50 border border-stone-200 rounded-lg text-xs text-stone-600 leading-relaxed">
                    <span className="font-semibold text-stone-800">Differensiering:</span> Én PDF med tre nivåer — Støtte, Standard og Fordypning — tilpasset opplæringslova §1-3.
                  </div>
                )}
                {isProve && (
                  <div className="mt-3 px-3.5 py-2.5 bg-stone-50 border border-stone-200 rounded-lg text-xs text-stone-600 leading-relaxed">
                    <span className="font-semibold text-stone-800">Prøvegenerator:</span> Komplett prøve med Del A (flervalg), Del B (kortsvar) og Del C (langsvar) med vurderingskriterier.
                  </div>
                )}
                {isSekvens && (
                  <div className="mt-3 px-3.5 py-2.5 bg-stone-50 border border-stone-200 rounded-lg text-xs text-stone-600 leading-relaxed">
                    <span className="font-semibold text-stone-800">Sekvensplanlegger:</span> Komplett læringsløp med timeplaner, Blooms taksonomi-progresjon, formativ vurdering og summativ vurderingsplan.
                  </div>
                )}
              </div>

              {/* ── Subject + Level (two columns) ────────────────────────────── */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-5">
                <div>
                  <label htmlFor="subject-select" className="field-label">
                    <BookOpen className="w-4 h-4 text-accent-600" aria-hidden="true" />
                    Fag
                  </label>
                  <select
                    id="subject-select"
                    value={subject}
                    onChange={(e) => dispatch({ type: "SET_SUBJECT", subject: e.target.value })}
                    className="input-field appearance-none cursor-pointer"
                    disabled={status === "loading"}
                    required
                    aria-required="true"
                  >
                    <option value="">Velg fag...</option>
                    {SUBJECTS.map((s) => (
                      <option key={s.value} value={s.value}>
                        {s.label}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label htmlFor="level-select" className="field-label">
                    <GraduationCap className="w-4 h-4 text-accent-600" aria-hidden="true" />
                    Klasse / Nivå
                  </label>
                  <select
                    id="level-select"
                    value={level}
                    onChange={(e) => dispatch({ type: "SET_LEVEL", level: e.target.value })}
                    className="input-field appearance-none cursor-pointer"
                    disabled={status === "loading"}
                  >
                    {LEVELS.map((l) => (
                      <option key={l.value} value={l.value}>
                        {l.label} – {l.description}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* ── Topic Input ──────────────────────────────────────────────── */}
              <div className="mb-5">
                <label htmlFor="topic-input" className="field-label">
                  <FileText className="w-4 h-4 text-accent-600" aria-hidden="true" />
                  Tema
                </label>
                <input
                  id="topic-input"
                  type="text"
                  value={topic}
                  onChange={(e) => dispatch({ type: "SET_TOPIC", topic: e.target.value })}
                  placeholder="F.eks. Den industrielle revolusjon, Arv og miljø..."
                  className="input-field"
                  disabled={status === "loading"}
                  required
                  aria-required="true"
                />
              </div>

              {/* ── Language Level ───────────────────────────────────────────── */}
              <div className="mb-5">
                <label htmlFor="language-level-select" className="field-label">
                  <Languages className="w-4 h-4 text-accent-600" aria-hidden="true" />
                  Språktilpasning
                  <span className="text-xs text-stone-400 font-normal">(minoritetsspråklige)</span>
                </label>
                <select
                  id="language-level-select"
                  value={languageLevel}
                  onChange={(e) => dispatch({ type: "SET_LANGUAGE_LEVEL", languageLevel: e.target.value })}
                  className="input-field appearance-none cursor-pointer"
                  disabled={status === "loading"}
                >
                  {LANGUAGE_LEVELS.map((l) => (
                    <option key={l.value} value={l.value}>
                      {l.label} – {l.description}
                    </option>
                  ))}
                </select>
                {languageLevel !== "none" && (
                  <p className="text-xs text-stone-500 mt-2" role="note">
                    Faginnholdet forblir på VGS-nivå, men språket forenkles til {languageLevel}-nivå
                  </p>
                )}
              </div>

              {/* ── LK20 Grep Picker ─────────────────────────────────────────── */}
              {subject && (
                <div className="mb-5">
                  <GrepPicker
                    subject={subject}
                    level={level}
                    onSelect={handleGoalSelect}
                    selectedKode={selectedGoal?.kode}
                  />
                </div>
              )}

              {/* ── Detailed Description ─────────────────────────────────────── */}
              <div className="mb-5">
                <div className="flex items-center justify-between mb-2">
                  <label htmlFor="description-input" className="field-label mb-0">
                    <Sparkles className="w-4 h-4 text-accent-600" aria-hidden="true" />
                    Detaljert beskrivelse
                    <span className="text-xs text-stone-400 font-normal">(valgfritt)</span>
                  </label>
                  <button
                    type="button"
                    onClick={() => dispatch({ type: "TOGGLE_DESCRIPTION_TIPS" })}
                    className="text-xs text-accent-700 hover:text-accent-800 transition-colors underline underline-offset-2"
                  >
                    {showDescriptionTips ? "Skjul tips" : "Se tips"}
                  </button>
                </div>

                {showDescriptionTips && (
                  <div className="mb-3 p-4 bg-stone-50 border border-stone-200 rounded-lg text-xs text-stone-500 space-y-1.5">
                    <p className="text-stone-700 font-semibold mb-1">Tips – fortell modellen hva som er viktig:</p>
                    <p>· <span className="text-stone-700">Fokusområder:</span> «Legg vekt på barnearbeid og klasseskiller»</p>
                    <p>· <span className="text-stone-700">Elevbakgrunn:</span> «Klassen har nylig lest om 2. verdenskrig»</p>
                    <p>· <span className="text-stone-700">Vinkling:</span> «Bygg opp med en problemstilling, deretter argumenter»</p>
                    <p>· <span className="text-stone-700">Spesifikke krav:</span> «Inkluder primærkilder som eksempler»</p>
                  </div>
                )}

                <textarea
                  id="description-input"
                  value={description}
                  onChange={(e) => {
                    if (e.target.value.length <= 2000)
                      dispatch({ type: "SET_DESCRIPTION", description: e.target.value });
                  }}
                  placeholder="Skriv detaljerte instruksjoner her..."
                  rows={3}
                  className="input-field resize-none text-sm leading-relaxed"
                  disabled={status === "loading"}
                />
                <div className="flex justify-between mt-1.5">
                  <p className="text-xs text-stone-400">Jo mer du skriver, jo mer tilpasset blir resultatet.</p>
                  <span className={`text-xs font-mono transition-colors ${description.length > 1800 ? "text-amber-600" : "text-stone-400"}`}>
                    {description.length}/2000
                  </span>
                </div>
              </div>

              {/* ── Kildemateriale (læringsark + differensiert + prøve) ──────── */}
              {!isSekvens && (
                <div className="mb-5">
                  <div className="flex items-center justify-between mb-2">
                    <label htmlFor="source-text-input" className="field-label mb-0">
                      <BookOpen className="w-4 h-4 text-accent-600" aria-hidden="true" />
                      Kildemateriale
                      <span className="inline-flex items-center gap-1 text-[10px] font-medium text-accent-800 bg-accent-50 border border-accent-200 rounded-full px-2 py-0.5">
                        <ShieldCheck className="w-3 h-3" aria-hidden="true" />
                        Anbefalt for kontrollerbare fakta
                      </span>
                    </label>
                    <button
                      type="button"
                      onClick={() => dispatch({ type: "TOGGLE_SOURCE_TEXT" })}
                      className="text-xs text-accent-700 hover:text-accent-800 transition-colors underline underline-offset-2"
                    >
                      {showSourceText ? "Skjul" : "Lim inn kilde"}
                    </button>
                  </div>
                  {!showSourceText && (
                    <p className="text-xs text-stone-500 mb-2 -mt-0.5">
                      {isProve
                        ? "Limer du inn en kilde (pensumtekst, lærebokutdrag), bygges prøven og fasiten på den i stedet for modellens hukommelse."
                        : <>Limer du inn en kilde, forankrer modellen teksten i den, merker kontrollerbare påstander med <span className="font-mono">[K]</span>, og faktarapporten kryssjekkes mot kilden.</>}
                    </p>
                  )}

                  {!sourceText.trim() && (
                    <div className="mb-1">
                      <OptionToggle
                        label="Hent kilde fra NDLA automatisk"
                        checked={useNdla}
                        onChange={(val) => dispatch({ type: "SET_USE_NDLA", val })}
                        disabled={status === "loading"}
                        description="Søker i NDLAs åpne læringsressurser og forankrer innholdet i en ekte kilde"
                      />
                    </div>
                  )}

                  {showSourceText && (
                    <>
                      <div className="mb-3 p-3 bg-stone-50 border border-stone-200 rounded-lg text-xs text-stone-500">
                        <p className="text-stone-700 font-semibold mb-1">Faktaforankring</p>
                        <p>
                          {isProve
                            ? "Lim inn pensumteksten eller lærebokutdraget prøven skal bygge på. Spørsmål og fasit holder seg da til kilden."
                            : <>Lim inn tekst fra lærebok, artikkel eller kompendium. Kilden brukes som primærgrunnlag, sentrale påstander merkes med <span className="font-mono">[K]</span> så du kan kontrollere dem, og faktarapporten kryssjekkes mot kilden.</>}
                        </p>
                      </div>
                      <textarea
                        id="source-text-input"
                        value={sourceText}
                        onChange={(e) => {
                          if (e.target.value.length <= 5000)
                            dispatch({ type: "SET_SOURCE_TEXT", sourceText: e.target.value });
                        }}
                        placeholder="Lim inn kildetekst her (lærebok, artikkel, kompendium)..."
                        rows={5}
                        className="input-field resize-none text-sm leading-relaxed"
                        disabled={status === "loading"}
                      />
                      <div className="flex justify-between mt-1.5">
                        <p className="text-xs text-stone-400">Holder seg nær kilden og legger til pedagogisk struktur.</p>
                        <span className={`text-xs font-mono transition-colors ${sourceText.length > 4500 ? "text-amber-600" : "text-stone-400"}`}>
                          {sourceText.length}/5000
                        </span>
                      </div>
                    </>
                  )}
                </div>
              )}

              {/* ── Image Upload (læringsark + differensiert only) ───────────── */}
              {!isProve && !isSekvens && (
                <div className="mb-7">
                  <label htmlFor="image-upload" className="field-label">
                    <ImageIcon className="w-4 h-4 text-accent-600" aria-hidden="true" />
                    Eget bilde (valgfritt)
                  </label>
                  <div className="flex items-center gap-3">
                    <input
                      id="image-upload"
                      type="file"
                      accept="image/jpeg, image/png, image/webp"
                      onChange={(e) => {
                        const file = e.target.files?.[0] || null;
                        if (file && file.size > 5 * 1024 * 1024) {
                          alert("Bildet er for stort. Maks størrelse er 5MB.");
                          e.target.value = "";
                          dispatch({ type: "SET_IMAGE_FILE", file: null });
                          return;
                        }
                        dispatch({ type: "SET_IMAGE_FILE", file });
                      }}
                      className="w-full px-3.5 py-2 bg-white border border-stone-300 rounded-lg text-sm text-stone-600 file:mr-3 file:py-1.5 file:px-3 file:rounded-md file:border-0 file:text-sm file:font-medium file:bg-stone-100 file:text-stone-700 hover:file:bg-stone-200 transition-colors hover:border-stone-400 focus:outline-none focus:ring-2 focus:ring-accent-600/15 cursor-pointer"
                      disabled={status === "loading"}
                    />
                    {imageFile && (
                      <button
                        type="button"
                        onClick={() => {
                          dispatch({ type: "SET_IMAGE_FILE", file: null });
                          const el = document.getElementById("image-upload") as HTMLInputElement;
                          if (el) el.value = "";
                        }}
                        className="p-2 bg-stone-100 rounded-lg text-stone-400 hover:text-stone-700 hover:bg-stone-200 transition-colors"
                        aria-label="Fjern bilde"
                      >
                        <X className="w-5 h-5" />
                      </button>
                    )}
                  </div>
                  <p className="text-xs text-stone-400 mt-2">
                    Maks 5MB (JPG, PNG, WebP). Lar du denne stå tom, finnes et bilde automatisk.
                  </p>
                </div>
              )}

              {/* ── Options (læringsark + differensiert only) ────────────────── */}
              {!isProve && !isSekvens && (
                <>
                  <fieldset className="mb-5 panel">
                    <legend className="flex items-center gap-2 text-sm font-semibold text-stone-800 px-1">
                      <Users className="w-4 h-4 text-accent-600" aria-hidden="true" />
                      Tilpasning til eleven
                    </legend>
                    <p className="text-xs text-stone-500 mb-3 mt-2">
                      Samme faglige nivå — tilpasset inngang for dine elever.
                    </p>
                    <label htmlFor="interest-input" className="block text-xs font-medium text-stone-600 mb-1.5">
                      Elevens interesser <span className="text-stone-400 font-normal">(valgfritt)</span>
                    </label>
                    <input
                      id="interest-input"
                      type="text"
                      value={interest}
                      onChange={(e) => {
                        if (e.target.value.length <= 200)
                          dispatch({ type: "SET_INTEREST", interest: e.target.value });
                      }}
                      placeholder="F.eks. fotball, gaming, musikk, dyr..."
                      className="input-field text-sm"
                      disabled={status === "loading"}
                    />
                    <p className="text-xs text-stone-400 mt-1.5 mb-3">
                      Eksempler og analogier knyttes til interessene — fakta og nivå er uendret.
                    </p>
                    <OptionToggle
                      label="Lesevennlig modus"
                      checked={options.reading_friendly}
                      onChange={(val) => handleOptionChange("reading_friendly", val)}
                      disabled={status === "loading"}
                      description="For lese-/skrivevansker: tydeligere struktur, kortere setninger, mer luft"
                    />

                    {mode === "laeringsark" && (
                      <div className="mt-4 pt-4 border-t border-stone-200">
                        <p className="text-xs font-semibold text-stone-700 mb-1">Elevgrupper</p>
                        <p className="text-xs text-stone-400 mb-2.5">
                          Lagre grupper med ulike behov, og generer en tilpasset versjon av samme tema til hver gruppe — med ett klikk.
                        </p>
                        <ProfileManager
                          profiles={profiles}
                          onChange={handleProfilesChange}
                          disabled={status === "loading"}
                        />
                        {profiles.length > 0 && (
                          <button
                            type="button"
                            onClick={handleGenerateForProfiles}
                            disabled={!isFormValid || status === "loading"}
                            title={!isFormValid ? "Fyll ut fag og tema først" : undefined}
                            className="mt-3 w-full py-2.5 px-4 rounded-lg text-sm font-semibold flex items-center justify-center gap-2 bg-accent-700 hover:bg-accent-800 text-white transition-colors disabled:opacity-40 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-accent-600/30"
                          >
                            <Users className="w-4 h-4" aria-hidden="true" />
                            Generer for alle grupper ({profiles.length})
                          </button>
                        )}
                      </div>
                    )}
                  </fieldset>

                  <fieldset className="mb-5 panel">
                    <legend className="flex items-center gap-2 text-sm font-semibold text-stone-800 px-1">
                      <Settings2 className="w-4 h-4 text-accent-600" aria-hidden="true" />
                      Tilpass innhold
                    </legend>
                    <div className="mb-4 mt-3" role="group" aria-label="Tekstlengde">
                      <p className="text-xs text-stone-500 mb-2 font-medium">Tekstlengde</p>
                      <div className="flex gap-2">
                        {(["kort", "standard", "lang"] as const).map((len) => {
                          const active = len === "lang" ? options.lang_tekst : len === "standard" ? options.deep_dive : !options.deep_dive && !options.lang_tekst;
                          const labels = { kort: "Kort", standard: "Standard", lang: "Lang" };
                          const descs = { kort: "400–600 ord", standard: "800–1000 ord", lang: "1500–2000 ord" };
                          return (
                            <button
                              key={len}
                              type="button"
                              onClick={() => handleTextLength(len)}
                              disabled={status === "loading"}
                              aria-pressed={active}
                              className={`flex-1 flex flex-col items-center py-2 px-1 rounded-md text-xs font-semibold border transition-colors focus:outline-none focus:ring-2 focus:ring-accent-600/30 ${
                                active
                                  ? "bg-accent-50 border-accent-300 text-accent-800"
                                  : "bg-white border-stone-200 text-stone-500 hover:border-stone-300 hover:text-stone-700"
                              }`}
                            >
                              <span>{labels[len]}</span>
                              <span className="text-[10px] font-normal opacity-70 mt-0.5">{descs[len]}</span>
                            </button>
                          );
                        })}
                      </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5" role="group" aria-label="Innholdsvalg">
                      <OptionToggle
                        label="Faktaoppgaver"
                        checked={options.comprehension_tasks}
                        onChange={(val) => handleOptionChange("comprehension_tasks", val)}
                        disabled={status === "loading"}
                      />
                      <OptionToggle
                        label="Fagbegreper"
                        checked={options.grammar_tasks}
                        onChange={(val) => handleOptionChange("grammar_tasks", val)}
                        disabled={status === "loading"}
                      />
                      <OptionToggle
                        label="Ordoppgaver"
                        checked={options.vocabulary_tasks}
                        onChange={(val) => handleOptionChange("vocabulary_tasks", val)}
                        disabled={status === "loading"}
                      />
                      <OptionToggle
                        label="Drøfting"
                        checked={options.discussion_tasks}
                        onChange={(val) => handleOptionChange("discussion_tasks", val)}
                        disabled={status === "loading"}
                      />
                      <OptionToggle
                        label="Inkluder Fasit"
                        checked={options.teacher_key}
                        onChange={(val) => handleOptionChange("teacher_key", val)}
                        disabled={status === "loading"}
                      />
                      <OptionToggle
                        label="Korrekturpasning"
                        checked={options.korrektur}
                        onChange={(val) => handleOptionChange("korrektur", val)}
                        disabled={status === "loading"}
                        description="Automatisk språkvask (norsk)"
                      />
                    </div>
                  </fieldset>

                  <fieldset className="mb-5 panel">
                    <legend className="flex items-center gap-2 text-sm font-semibold text-stone-800 px-1">
                      <Sparkles className="w-4 h-4 text-accent-600" aria-hidden="true" />
                      Avanserte moduler
                    </legend>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5 mt-3" role="group" aria-label="Avanserte moduler">
                      <OptionToggle
                        label="Case-studie"
                        checked={options.role_play}
                        onChange={(val) => handleOptionChange("role_play", val)}
                        disabled={status === "loading"}
                        description="Praktisk scenario"
                      />
                      <OptionToggle
                        label="Visuell analyse"
                        checked={options.image_description}
                        onChange={(val) => handleOptionChange("image_description", val)}
                        disabled={status === "loading"}
                        description="Oppgaver om bildet"
                      />
                      <OptionToggle
                        label="Skriveramme"
                        checked={options.writing_frame}
                        onChange={(val) => handleOptionChange("writing_frame", val)}
                        disabled={status === "loading"}
                        description="Faglig struktur"
                      />
                      <OptionToggle
                        label="Samfunnsblikk"
                        checked={options.cultural_comparison}
                        onChange={(val) => handleOptionChange("cultural_comparison", val)}
                        disabled={status === "loading"}
                        description="Større sammenheng"
                      />
                      <OptionToggle
                        label="Yrkesfaglig case"
                        checked={options.real_case}
                        onChange={(val) => handleOptionChange("real_case", val)}
                        disabled={status === "loading"}
                        description="Relevant for yrkesfag"
                      />
                    </div>
                  </fieldset>

                  <fieldset className="mb-7 panel">
                    <legend className="flex items-center gap-2 text-sm font-semibold text-stone-800 px-1">
                      <ShieldCheck className="w-4 h-4 text-accent-600" aria-hidden="true" />
                      Kvalitetssikring
                    </legend>
                    <p className="text-xs text-stone-500 mb-3 mt-2">
                      Automatiske kontroller som hever kvaliteten på det ferdige dokumentet.
                    </p>
                    <div className="grid grid-cols-1 gap-2.5" role="group" aria-label="Kvalitetssikring">
                      <OptionToggle
                        label="Kvalitetsrevisjon"
                        checked={options.revision}
                        onChange={(val) => handleOptionChange("revision", val)}
                        disabled={status === "loading"}
                        description="En redaktør gjennomgår og skjerper teksten før oppgavene lages — litt lengre genereringstid"
                      />
                      <OptionToggle
                        label="Faktarapport"
                        checked={options.faktarapport}
                        onChange={(val) => handleOptionChange("faktarapport", val)}
                        disabled={status === "loading"}
                        description="Sjekkliste med fakta og forenklinger — kun for læreren, legges til som siste side"
                      />
                    </div>
                  </fieldset>
                </>
              )}

              {/* ── Prove options ─────────────────────────────────────────────── */}
              {isProve && (
                <fieldset className="mb-7 panel">
                  <legend className="flex items-center gap-2 text-sm font-semibold text-stone-800 px-1">
                    <FileText className="w-4 h-4 text-accent-600" aria-hidden="true" />
                    Prøvevalg
                  </legend>
                  <div className="grid grid-cols-1 gap-2.5 mt-3" role="group" aria-label="Prøvevalg">
                    <OptionToggle
                      label="Inkluder fasit"
                      checked={includeFasit}
                      onChange={(val) => dispatch({ type: "SET_INCLUDE_FASIT", val })}
                      disabled={status === "loading"}
                      description="Fasit legges til som siste side (kun for læreren)"
                    />
                  </div>
                  <p className="text-xs text-stone-500 mt-3">
                    Prøven inneholder Del A (flervalg · 2p/spm), Del B (kortsvarsoppgaver · 5–8p) og
                    Del C (langsvarsoppgave · 12–15p) med vurderingskriterier.
                  </p>
                </fieldset>
              )}

              {/* ── Sekvens options ───────────────────────────────────────────── */}
              {isSekvens && (
                <fieldset className="mb-7 panel">
                  <legend className="flex items-center gap-2 text-sm font-semibold text-stone-800 px-1">
                    <CalendarDays className="w-4 h-4 text-accent-600" aria-hidden="true" />
                    Sekvensinnstillinger
                  </legend>

                  <div className="mb-5 mt-3">
                    <label className="block text-sm text-stone-700 font-medium mb-2.5">
                      Antall uker:{" "}
                      <span className="text-accent-700 font-semibold">{antallUker}</span>
                    </label>
                    <div className="flex gap-2">
                      {[2, 3, 4, 5, 6].map((n) => (
                        <button
                          key={n}
                          type="button"
                          onClick={() => dispatch({ type: "SET_ANTALL_UKER", n })}
                          disabled={status === "loading"}
                          className={`flex-1 py-2 rounded-md text-sm font-semibold border transition-colors focus:outline-none focus:ring-2 focus:ring-accent-600/30 ${
                            antallUker === n
                              ? "bg-accent-50 text-accent-800 border-accent-300"
                              : "bg-white text-stone-500 border-stone-200 hover:border-stone-300 hover:text-stone-700"
                          }`}
                          aria-pressed={antallUker === n}
                        >
                          {n}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="mb-5">
                    <label className="block text-sm text-stone-700 font-medium mb-2.5">
                      Timer per uke:{" "}
                      <span className="text-accent-700 font-semibold">{timerPerUke}</span>
                    </label>
                    <div className="flex gap-2">
                      {[1, 2, 3].map((n) => (
                        <button
                          key={n}
                          type="button"
                          onClick={() => dispatch({ type: "SET_TIMER_PER_UKE", n })}
                          disabled={status === "loading"}
                          className={`flex-1 py-2 rounded-md text-sm font-semibold border transition-colors focus:outline-none focus:ring-2 focus:ring-accent-600/30 ${
                            timerPerUke === n
                              ? "bg-accent-50 text-accent-800 border-accent-300"
                              : "bg-white text-stone-500 border-stone-200 hover:border-stone-300 hover:text-stone-700"
                          }`}
                          aria-pressed={timerPerUke === n}
                        >
                          {n} {n === 1 ? "time" : "timer"}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="flex items-center justify-between px-4 py-3 bg-accent-50 border border-accent-200 rounded-lg">
                    <div className="text-xs text-accent-800">
                      <span className="font-semibold">{antallUker} uker × {timerPerUke} timer</span>
                      {" = "}
                      <span className="font-semibold">{antallUker * timerPerUke} undervisningstimer</span>
                    </div>
                    <div className="text-xs text-stone-500">
                      Blooms taksonomi-progresjon
                    </div>
                  </div>

                  <p className="text-xs text-stone-500 mt-3">
                    Sekvensplanen inkluderer læringsmål, aktiviteter (intro/hoveddel/avslutning),
                    formativ vurdering og differensieringstips for hver time.
                  </p>
                </fieldset>
              )}

              {/* ── Submit / Cancel / Success buttons ────────────────────────── */}
              {status === "loading" ? (
                <div className="flex gap-3">
                  <button
                    type="button"
                    disabled
                    className="flex-1 py-3 px-6 rounded-lg font-semibold flex items-center justify-center gap-2.5 bg-stone-200 text-stone-500 cursor-wait"
                    aria-busy="true"
                  >
                    <Loader2 className="w-5 h-5 animate-spin" aria-hidden="true" />
                    <span>Genererer...</span>
                  </button>
                  <button
                    type="button"
                    onClick={handleCancel}
                    className="py-3 px-5 rounded-lg font-medium flex items-center justify-center gap-2 bg-white text-red-700 border border-red-200 hover:bg-red-50 transition-colors focus:outline-none focus:ring-2 focus:ring-red-300"
                    aria-label="Avbryt generering"
                  >
                    <X className="w-5 h-5" aria-hidden="true" />
                    Avbryt
                  </button>
                </div>
              ) : status === "success" && previewBlob ? (
                <div className="flex flex-col gap-2.5">
                  {sourceGrounded === true && (
                    <div className="flex items-start gap-2 p-3 rounded-lg bg-accent-50 border border-accent-200 text-accent-800 text-sm">
                      <ShieldCheck className="w-4 h-4 mt-0.5 shrink-0" aria-hidden="true" />
                      <span>
                        <span className="font-semibold">Kildeforankret{sourceName ? <> i {sourceName}</> : ""}.</span> Påstander merket <span className="font-mono">[K]</span> kan kontrolleres mot kilden, og faktarapporten er kryssjekket mot den.
                      </span>
                    </div>
                  )}
                  {sourceGrounded === false && (
                    <div className="flex items-start gap-2 p-3 rounded-lg bg-amber-50 border border-amber-200 text-amber-800 text-sm">
                      <ShieldAlert className="w-4 h-4 mt-0.5 shrink-0" aria-hidden="true" />
                      <span>
                        <span className="font-semibold">Ikke kildeforankret.</span> Fakta bygger på modellens kunnskap og bør verifiseres. Lim inn kildemateriale, eller la NDLA-søket stå på, så kryssjekkes neste versjon mot en faktisk kilde.
                      </span>
                    </div>
                  )}
                  {warnings.length > 0 && (
                    <div className="p-3 rounded-lg bg-amber-50 border border-amber-200 text-amber-800 text-sm">
                      <p className="font-semibold mb-1">Merknader fra genereringen:</p>
                      <ul className="list-disc list-inside space-y-0.5">
                        {warnings.map((w, i) => (
                          <li key={i}>{w}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  <div className="flex gap-2.5">
                    <button
                      type="button"
                      onClick={() => dispatch({ type: "SHOW_PREVIEW" })}
                      className="btn-secondary flex-1 py-3 px-6"
                    >
                      <Eye className="w-5 h-5" aria-hidden="true" />
                      <span>Vis PDF</span>
                    </button>
                    <button
                      type="button"
                      onClick={handleDownloadFromPreview}
                      className="btn-primary flex-1 py-3 px-6"
                    >
                      <Download className="w-5 h-5" aria-hidden="true" />
                      <span>Last ned PDF</span>
                    </button>
                    {basisText && mode === "laeringsark" && (
                      <button
                        type="button"
                        onClick={handleDownloadDocx}
                        className="btn-secondary py-3 px-4"
                        title="Last ned som Word-dokument (.docx)"
                      >
                        <FileText className="w-5 h-5" aria-hidden="true" />
                        <span className="hidden sm:inline">.docx</span>
                      </button>
                    )}
                  </div>
                  {rapportBlob && (
                    <button
                      type="button"
                      onClick={() => downloadBlob(rapportBlob, rapportFilename)}
                      className="btn-secondary w-full py-2.5 px-4 text-sm"
                      title="Egen PDF til læreren — deles ikke ut til elevene"
                    >
                      <ShieldCheck className="w-4 h-4" aria-hidden="true" />
                      Last ned faktarapport (til læreren)
                    </button>
                  )}
                  {mode === "sekvens" && (
                    <button
                      type="button"
                      onClick={() => dispatch({ type: "SET_MODE", mode: "laeringsark" })}
                      className="w-full py-2.5 px-4 rounded-lg text-sm font-medium flex items-center justify-center gap-2 bg-accent-50 text-accent-800 border border-accent-200 hover:bg-accent-100 transition-colors focus:outline-none focus:ring-2 focus:ring-accent-600/30"
                    >
                      <BookOpen className="w-4 h-4" aria-hidden="true" />
                      Generer læringsmateriell for dette temaet
                    </button>
                  )}
                  {basisText && mode === "laeringsark" && (
                    <div className="flex gap-2.5">
                      <button
                        type="button"
                        onClick={handleRegenerate}
                        className="btn-secondary flex-1 py-2.5 px-4 text-sm"
                        title="Beholder fagteksten — genererer nye oppgaver og faktarapport"
                      >
                        <Sparkles className="w-4 h-4" aria-hidden="true" />
                        Ny versjon (behold tekst)
                      </button>
                      <button
                        type="button"
                        onClick={() => dispatch({ type: "TOGGLE_EDIT_PANEL" })}
                        className="btn-secondary flex-1 py-2.5 px-4 text-sm"
                      >
                        {showEditPanel ? "Skjul redigering" : "Rediger innhold"}
                      </button>
                    </div>
                  )}
                  {/* Image picker strip */}
                  {mode === "laeringsark" && (imageCandidatesLoading || imageCandidates.length > 0) && (
                    <div className="mt-2 panel">
                      <p className="text-xs text-stone-500 mb-2 font-medium flex items-center gap-1.5">
                        <ImageIcon className="w-3.5 h-3.5" aria-hidden="true" />
                        Velg bilde — klikk for å bruke i PDF
                      </p>
                      {imageCandidatesLoading ? (
                        <div className="flex gap-2 items-center text-xs text-stone-400 py-2">
                          <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" />
                          Søker etter bildeforslag...
                        </div>
                      ) : (
                        <div className="flex gap-2 overflow-x-auto pb-1">
                          {imageCandidates.map((img, i) => (
                            <button
                              key={i}
                              type="button"
                              onClick={() => handleSelectImage(img.url)}
                              title={img.attribution}
                              className={`flex-shrink-0 w-20 h-16 rounded-md overflow-hidden border-2 transition-all focus:outline-none focus:ring-2 focus:ring-accent-600/40 ${
                                generatedImageUrl === img.url
                                  ? "border-accent-600 opacity-100"
                                  : "border-stone-200 opacity-80 hover:opacity-100 hover:border-stone-400"
                              }`}
                            >
                              {/* eslint-disable-next-line @next/next/no-img-element */}
                              <img
                                src={img.thumbUrl}
                                alt={img.title}
                                className="w-full h-full object-cover"
                                loading="lazy"
                              />
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {showEditPanel && basisText !== null && worksheetText !== null && (
                    <div className="mt-2 panel space-y-4">
                      <p className="text-xs text-stone-500">Rediger tekst direkte og klikk «Oppdater PDF» — ingen ny AI-generering nødvendig.</p>
                      <div>
                        <label className="block text-xs font-medium text-stone-700 mb-1.5">Fagtekst</label>
                        <textarea
                          value={basisText}
                          onChange={(e) => dispatch({ type: "SET_BASIS_TEXT", text: e.target.value })}
                          rows={8}
                          className="input-field text-sm leading-relaxed resize-y"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-stone-700 mb-1.5">Arbeidsark</label>
                        <textarea
                          value={worksheetText}
                          onChange={(e) => dispatch({ type: "SET_WORKSHEET_TEXT", text: e.target.value })}
                          rows={8}
                          className="input-field text-sm leading-relaxed resize-y"
                        />
                      </div>
                      <button
                        type="button"
                        onClick={handleOppdaterPdf}
                        className="btn-primary w-full py-3 px-4 text-sm"
                      >
                        <Download className="w-4 h-4" aria-hidden="true" />
                        Oppdater PDF med disse endringene
                      </button>
                    </div>
                  )}
                </div>
              ) : (
                <button
                  type="submit"
                  disabled={!isFormValid}
                  aria-label={isFormValid ? generateLabel : "Fyll ut alle feltene for å generere"}
                  className="btn-primary w-full py-3.5 px-6 text-base"
                >
                  <span>{generateLabel}</span>
                </button>
              )}

              {/* Status Messages */}
              <StatusMessages
                status={status}
                errorMessage={errorMessage}
                onRetry={() => dispatch({ type: "GENERATION_IDLE" })}
                elapsedSeconds={elapsedSeconds}
                progressMessage={progressMessage}
              />

              {/* ── Batch results per student group ──────────────────────────── */}
              {profileResults.length > 0 && (
                <div className="mt-4 panel">
                  <p className="text-sm font-semibold text-stone-800 mb-2.5 flex items-center gap-2">
                    <Users className="w-4 h-4 text-accent-600" aria-hidden="true" />
                    Tilpassede versjoner per gruppe
                  </p>
                  <ul className="space-y-1.5">
                    {profileResults.map((r) => (
                      <li
                        key={r.profileId}
                        className="flex items-center gap-2.5 px-3 py-2 bg-white border border-stone-200 rounded-lg text-sm"
                      >
                        {r.status === "loading" ? (
                          <Loader2 className="w-4 h-4 animate-spin text-accent-600 shrink-0" aria-hidden="true" />
                        ) : r.status === "done" ? (
                          <CheckCircle2 className="w-4 h-4 text-accent-700 shrink-0" aria-hidden="true" />
                        ) : r.status === "error" ? (
                          <AlertCircle className="w-4 h-4 text-red-600 shrink-0" aria-hidden="true" />
                        ) : (
                          <span className="w-4 h-4 flex items-center justify-center shrink-0" aria-hidden="true">
                            <span className="w-1.5 h-1.5 rounded-full bg-stone-300" />
                          </span>
                        )}
                        <span className="font-medium text-stone-800 truncate flex-1">{r.label}</span>
                        {r.status === "error" && (
                          <span className="text-xs text-red-600 truncate max-w-[200px]" title={r.errorMessage}>
                            {r.errorMessage}
                          </span>
                        )}
                        {r.status === "done" && r.blob && (
                          <button
                            type="button"
                            onClick={() => downloadBlob(r.blob!, r.filename || "laeringsark.pdf")}
                            className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold bg-accent-700 hover:bg-accent-800 text-white transition-colors focus:outline-none focus:ring-2 focus:ring-accent-600/30"
                          >
                            <Download className="w-3.5 h-3.5" aria-hidden="true" />
                            Last ned
                          </button>
                        )}
                      </li>
                    ))}
                  </ul>
                  {!batchRunning && profileResults.some((r) => r.status === "done") && (
                    <p className="text-xs text-stone-400 mt-2.5">
                      Samme tema, samme faglige nivå — språk, eksempler og struktur tilpasset hver gruppe.
                    </p>
                  )}
                </div>
              )}
            </div>
          </form>

          {/* Capability row */}
          <div className="grid grid-cols-3 gap-3 mt-5">
            <div className="rounded-lg border border-stone-200 bg-white px-4 py-3">
              <h3 className="text-stone-800 font-medium text-sm">LK20-tilpasset</h3>
              <p className="text-stone-400 text-xs mt-0.5">Koblet til Grep</p>
            </div>
            <div className="rounded-lg border border-stone-200 bg-white px-4 py-3">
              <h3 className="text-stone-800 font-medium text-sm">Ferdig PDF</h3>
              <p className="text-stone-400 text-xs mt-0.5">Klar til print</p>
            </div>
            <div className="rounded-lg border border-stone-200 bg-white px-4 py-3">
              <h3 className="text-stone-800 font-medium text-sm">Fire modi</h3>
              <p className="text-stone-400 text-xs mt-0.5">Ark · Diff · Prøve · Sekvens</p>
            </div>
          </div>
        </div>

        {/* Footer */}
        <footer className="mt-10 text-center text-stone-400 text-xs">
          <p>VGS Lærerassistent · Videregående skole</p>
        </footer>
      </div>
    </main>
  );
}
