"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronLeft, ChevronRight, Sparkles, LayoutTemplate } from "lucide-react";
import { useAppStore } from "@/lib/store";
import type { PdfTheme } from "@/lib/store";
import {
  startGeneration,
  streamProgress,
  getResult,
  estimateCost,
  closeActiveStream,
  isTerminalGenerateStatus,
  isJobAborted,
  watchGenerationJob,
  type CostEstimateResponse,
  type JobStatusResponse,
} from "@/lib/api";
import { mapApiResultToGenerationResult, isSuccessfulStatus } from "@/lib/map-api-result";
import { appendHistory } from "@/lib/generation-history";
import { searchGoals, type CompetencyGoal } from "@/data/lk20-goals";
import {
  loadPreferences,
  materialTypeFromTemplate,
} from "@/lib/user-preferences";

/* -----------------------------------------------------------------------
   Data
   ----------------------------------------------------------------------- */
/** Grunnlov §5 — smalt lanseringsnivå (kan utvides via env). */
const LAUNCH_GRADES = (
  process.env.NEXT_PUBLIC_LAUNCH_GRADES || "VG1 1T,VG2 R1"
)
  .split(",")
  .map((g) => g.trim())
  .filter(Boolean);

const GRADES = [
  { value: "1.-4. trinn", label: "1.–4. trinn", sub: "Barneskole" },
  { value: "5.-7. trinn", label: "5.–7. trinn", sub: "Mellomtrinn" },
  { value: "8. trinn", label: "8. trinn", sub: "Ungdomsskole" },
  { value: "9. trinn", label: "9. trinn", sub: "Ungdomsskole" },
  { value: "10. trinn", label: "10. trinn", sub: "Ungdomsskole" },
  { value: "VG1 1T", label: "VG1 1T", sub: "Studieforberedende" },
  { value: "VG1 1P", label: "VG1 1P", sub: "Praktisk" },
  { value: "VG2 2P", label: "VG2 2P", sub: "Praktisk" },
  { value: "VG2 R1", label: "VG2 R1", sub: "Realfag" },
  { value: "VG3 R2", label: "VG3 R2", sub: "Realfag" },
];

const TOPICS: Record<string, string[]> = {
  "1.-4. trinn": ["Tall og telling", "Addisjon", "Subtraksjon", "Multiplikasjon", "Geometriske figurer", "Måling"],
  "5.-7. trinn": ["Brøk", "Desimaltall", "Prosent", "Areal og omkrets", "Statistikk", "Negative tall"],
  "8. trinn": ["Algebra", "Lineære likninger", "Brøk og prosent", "Geometri", "Statistikk", "Funksjoner"],
  "9. trinn": ["Lineære funksjoner", "Likningssett", "Pytagoras", "Sannsynlighet", "Potenser", "Tall og algebra"],
  "10. trinn": ["Funksjoner", "Likninger", "Geometri", "Trigonometri", "Sannsynlighet", "Økonomi"],
  "VG1 1T": ["Algebra", "Likninger og ulikheter", "Funksjoner", "Geometri", "Sannsynlighet"],
  "VG1 1P": ["Prosent og økonomi", "Lineære funksjoner", "Geometri", "Statistikk"],
  "VG2 2P": ["Funksjoner", "Statistikk", "Sannsynlighet", "Modellering"],
  "VG2 R1": ["Algebra", "Funksjoner", "Derivasjon", "Vektorer", "Kombinatorikk"],
  "VG3 R2": ["Integrasjon", "Differensiallikninger", "Romgeometri", "Vektorer i rommet"],
};

const MATERIAL_TYPES = [
  { value: "arbeidsark", label: "Oppgaveark", desc: "Sett med oppgaver og løsninger", icon: "📝" },
  { value: "kapittel", label: "Fullt kapittel", desc: "Teori, eksempler og oppgaver", icon: "📖" },
  { value: "prøve", label: "Eksamen", desc: "Prøve med poengskjema", icon: "📋" },
  { value: "differensiert", label: "Differensiert", desc: "Grunnleggende, standard og avansert i ett dokument", icon: "🔀" },
];

const LANGUAGE_LEVELS = [
  { value: "standard", label: "Standard norsk" },
  { value: "b2", label: "Forenklet (B2)" },
  { value: "b1", label: "Enklere (B1)" },
];

const THEME_OPTIONS: { value: PdfTheme; label: string; icon: string }[] = [
  { value: "default", label: "Klassisk", icon: "🔵" },
  { value: "calm", label: "Rolig", icon: "🌿" },
  { value: "playful", label: "Leken", icon: "🎨" },
  { value: "highcontrast", label: "Kontrast", icon: "⬛" },
];

const slideVariants = {
  enter: (direction: number) => ({
    x: direction > 0 ? 80 : -80,
    opacity: 0,
  }),
  center: { x: 0, opacity: 1 },
  exit: (direction: number) => ({
    x: direction > 0 ? -80 : 80,
    opacity: 0,
  }),
};

function MaterialPreviewMock({ active }: { active: string }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-6" aria-hidden="true">
      {MATERIAL_TYPES.map((t) => (
        <div
          key={t.value}
          className={`rounded-xl border p-3 text-left transition-all ${
            active === t.value
              ? "border-accent-blue bg-accent-blue/5 ring-1 ring-accent-blue/30"
              : "border-border bg-surface-elevated/50 opacity-70"
          }`}
        >
          <div className="text-xs font-medium mb-2 flex items-center gap-1">
            <span>{t.icon}</span> {t.label}
          </div>
          <div className="space-y-1">
            <div className="h-1.5 bg-border rounded w-4/5" />
            <div className="h-1.5 bg-border rounded w-full" />
            <div className="h-1.5 bg-border rounded w-3/5" />
            {t.value === "kapittel" && (
              <>
                <div className="h-8 bg-accent-blue/10 rounded mt-2" />
                <div className="h-1.5 bg-border rounded w-full mt-1" />
              </>
            )}
            {(t.value === "arbeidsark" || t.value === "differensiert") && (
              <div className="grid grid-cols-2 gap-1 mt-2">
                <div className="h-6 bg-accent-green/10 rounded" />
                <div className="h-6 bg-accent-green/10 rounded" />
              </div>
            )}
            {t.value === "prøve" && (
              <div className="h-10 bg-accent-orange/10 rounded mt-2 flex items-end p-1 gap-0.5">
                <div className="flex-1 h-3 bg-border/80 rounded-sm" />
                <div className="flex-1 h-4 bg-border rounded-sm" />
                <div className="flex-1 h-2 bg-border/60 rounded-sm" />
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

function toggleGoal(list: string[], code: string): string[] {
  return list.includes(code) ? list.filter((c) => c !== code) : [...list, code];
}

/* -----------------------------------------------------------------------
   Component
   ----------------------------------------------------------------------- */
export function GenerationWizard() {
  const request = useAppStore((s) => s.request);
  const setRequest = useAppStore((s) => s.setRequest);
  const startGen = useAppStore((s) => s.startGeneration);
  const setJobId = useAppStore((s) => s.setJobId);
  const addStep = useAppStore((s) => s.addStep);
  const setCurrentAgent = useAppStore((s) => s.setCurrentAgent);
  const setResult = useAppStore((s) => s.setResult);
  const setError = useAppStore((s) => s.setError);

  const [step, setStep] = useState(0);
  const [direction, setDirection] = useState(0);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [goalSearch, setGoalSearch] = useState("");
  const activeJobRef = useRef<string | null>(null);
  const streamCloseRef = useRef<(() => void) | null>(null);
  const [costEstimate, setCostEstimate] = useState<CostEstimateResponse | null>(
    null
  );
  const [estimateLoading, setEstimateLoading] = useState(false);
  const [showAllGrades, setShowAllGrades] = useState(false);

  const visibleGrades = useMemo(() => {
    if (showAllGrades || LAUNCH_GRADES.length === 0) return GRADES;
    const launch = new Set(LAUNCH_GRADES);
    const filtered = GRADES.filter((g) => launch.has(g.value));
    return filtered.length > 0 ? filtered : GRADES;
  }, [showAllGrades]);

  useEffect(() => {
    const prefs = loadPreferences();
    const params = new URLSearchParams(window.location.search);
    const template = params.get("template");
    const materialTypeParam = params.get("materialType");
    const defaultGrade =
      prefs.grade ||
      (LAUNCH_GRADES.length > 0 ? LAUNCH_GRADES[0] : GRADES[0]?.value) ||
      "VG1 1T";
    setRequest({
      grade: defaultGrade,
      languageLevel: prefs.languageLevel,
      materialType: template
        ? materialTypeFromTemplate(template)
        : materialTypeParam || prefs.materialType,
    });
  }, [setRequest]);

  useEffect(() => {
    return () => {
      streamCloseRef.current?.();
      closeActiveStream();
    };
  }, []);

  const totalSteps = 3;

  const filteredGoals: CompetencyGoal[] = useMemo(
    () => searchGoals(request.grade, goalSearch),
    [request.grade, goalSearch]
  );

  const goNext = () => {
    if (step < totalSteps - 1) {
      setDirection(1);
      setStep(step + 1);
    }
  };
  const goPrev = () => {
    if (step > 0) {
      setDirection(-1);
      setStep(step - 1);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    const tag = (e.target as HTMLElement)?.tagName;
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
    if (e.key === "ArrowRight" || e.key === "ArrowDown") {
      e.preventDefault();
      goNext();
    } else if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
      e.preventDefault();
      goPrev();
    }
  };

  const canGenerate = request.topic.trim().length > 0;

  useEffect(() => {
    if (step !== totalSteps - 1 || !canGenerate) {
      setCostEstimate(null);
      return;
    }
    let cancelled = false;
    setEstimateLoading(true);
    estimateCost({
      grade: request.grade,
      topic: request.topic,
      material_type: request.materialType,
      language_level: request.languageLevel,
      num_exercises: request.numExercises,
      difficulty: request.difficulty,
      include_theory: request.includeTheory,
      include_examples: request.includeExamples,
      include_exercises: request.includeExercises,
      include_solutions: request.includeSolutions,
      include_graphs: request.includeGraphs,
      competency_goals: request.competencyGoals,
      extra_instructions: request.extraInstructions,
    })
      .then((data) => {
        if (!cancelled) setCostEstimate(data);
      })
      .catch(() => {
        if (!cancelled) setCostEstimate(null);
      })
      .finally(() => {
        if (!cancelled) setEstimateLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [step, canGenerate, request]);

  const handleGenerate = async () => {
    if (!canGenerate) return;

    streamCloseRef.current?.();
    closeActiveStream();
    startGen();
    const snapshot = { ...useAppStore.getState().request };

    try {
      const resp = await startGeneration({
        grade: request.grade,
        topic: request.topic,
        material_type: request.materialType,
        language_level: request.languageLevel,
        num_exercises: request.numExercises,
        difficulty: request.difficulty,
        include_theory: request.includeTheory,
        include_examples: request.includeExamples,
        include_exercises: request.includeExercises,
        include_solutions: request.includeSolutions,
        include_graphs: request.includeGraphs,
        competency_goals: request.competencyGoals,
        extra_instructions: request.extraInstructions,
        pdf_style: {
          theme: request.pdfStyle.theme,
          student_mode: request.pdfStyle.studentMode,
          accessible: request.pdfStyle.accessible,
          dyslexia: request.pdfStyle.dyslexia,
          high_contrast: request.pdfStyle.highContrast,
        },
      });

      const job_id = resp.job_id;
      activeJobRef.current = job_id;
      setJobId(job_id);

      const finishWithResult = async () => {
        const raw = await getResult(job_id);
        if (activeJobRef.current !== job_id) return;
        const mapped = mapApiResultToGenerationResult(raw, snapshot);
        setResult(mapped);
        if (isSuccessfulStatus(mapped.status)) {
          appendHistory({
            jobId: job_id,
            createdAt: new Date().toISOString(),
            topic: snapshot.topic,
            grade: snapshot.grade,
            materialType: snapshot.materialType,
            favorite: false,
            status:
              mapped.status === "completed" ||
              mapped.status === "completed_with_warnings" ||
              mapped.status === "failed"
                ? mapped.status
                : undefined,
            warningReason: mapped.warningReason,
            request: { ...snapshot },
          });
        }
      };

      // Cache hit / instant completion: backend returns terminal status in POST
      // response — fetch result directly instead of waiting on SSE.
      if (isTerminalGenerateStatus(resp.status)) {
        if (resp.status === "failed") {
          setError(resp.message || "Generering feilet", snapshot);
          return;
        }
        try {
          await finishWithResult();
          return;
        } catch (e: unknown) {
          const msg = e instanceof Error ? e.message : "Kunne ikke hente resultat";
          setError(msg, snapshot);
          return;
        }
      }

      let resultLoaded = false;
      let loadingResult = false;

      const loadResultOnce = async (statusHint?: string) => {
        if (resultLoaded || loadingResult || activeJobRef.current !== job_id) return;
        if (isJobAborted(job_id)) return;
        loadingResult = true;
        if (statusHint && statusHint !== "failed") {
          setCurrentAgent("Henter ferdig materiale");
        }
        try {
          await finishWithResult();
          resultLoaded = true;
        } catch (e: unknown) {
          const msg = e instanceof Error ? e.message : "Kunne ikke hente resultat";
          setError(msg, snapshot);
        } finally {
          loadingResult = false;
          streamCloseRef.current?.();
          closeActiveStream();
        }
      };

      const pollSignal = { cancelled: false };

      streamCloseRef.current = () => {
        pollSignal.cancelled = true;
        closeActiveStream();
      };

      streamProgress(job_id, {
        onStep: (s) =>
          addStep({
            agent: s.agent,
            startedAt: s.started_at,
            completedAt: s.completed_at,
            durationSeconds: s.duration_seconds,
            outputSummary: s.output_summary,
            error: s.error,
            retries: s.retries,
          }),
        onCurrentAgent: (a) => setCurrentAgent(a),
        onComplete: async (data) => {
          if (activeJobRef.current !== job_id) return;
          if (data.status === "failed") {
            setError(data.error || "Generering feilet", snapshot);
            return;
          }
          await loadResultOnce(data.status);
        },
        onError: (err) => {
          if (activeJobRef.current !== job_id || resultLoaded) return;
          // Same recovery as poll give-up — job may exist on /result only.
          void (async () => {
            try {
              await finishWithResult();
              resultLoaded = true;
            } catch {
              setError(err, snapshot);
            }
          })();
        },
      });

      const handlePollGiveUp = (msg: string) => {
        if (activeJobRef.current !== job_id || resultLoaded) return;
        // Last resort: /status may 404 after a Render restart while /result still works.
        void (async () => {
          try {
            await finishWithResult();
            resultLoaded = true;
          } catch {
            setError(msg, snapshot);
          }
        })();
      };

      // Independent poll on tiny /status — never rely on SSE or heavy /result.
      void watchGenerationJob(
        job_id,
        async (st: JobStatusResponse) => {
          if (st.status === "failed") {
            setError(st.error || "Generering feilet", snapshot);
            return;
          }
          await loadResultOnce(st.status);
        },
        pollSignal,
        handlePollGiveUp
      );
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Noe gikk galt";
      setError(msg, snapshot);
    }
  };

  return (
    <div
      className="max-w-reading mx-auto outline-none focus-visible:ring-2 focus-visible:ring-accent-blue/40 rounded-xl"
      onKeyDown={handleKeyDown}
      tabIndex={0}
      role="region"
      aria-label="Genereringsveiviser"
    >
      <div
        className="flex items-center justify-center gap-2 mb-8"
        role="tablist"
        aria-label="Trinn i veiviseren"
      >
        {["Trinn", "Emne", "Innstillinger"].map((label, i) => (
          <div key={label} className="flex items-center gap-2">
            <button
              type="button"
              role="tab"
              aria-selected={i === step}
              aria-current={i === step ? "step" : undefined}
              onClick={() => {
                setDirection(i > step ? 1 : -1);
                setStep(i);
              }}
              className={`flex items-center gap-2 text-sm transition-colors ${
                i === step
                  ? "text-accent-blue font-medium"
                  : i < step
                  ? "text-text-primary"
                  : "text-text-muted"
              }`}
            >
              <span
                className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-medium ${
                  i === step
                    ? "bg-accent-blue text-white"
                    : i < step
                    ? "bg-accent-green/20 text-accent-green"
                    : "bg-surface-elevated text-text-muted"
                }`}
              >
                {i < step ? "✓" : i + 1}
              </span>
              <span className="hidden sm:inline">{label}</span>
            </button>
            {i < totalSteps - 1 && <div className="w-8 h-px bg-border" />}
          </div>
        ))}
      </div>

      <div className="overflow-hidden relative min-h-[320px]">
        <AnimatePresence initial={false} custom={direction} mode="wait">
          {step === 0 && (
            <motion.div
              key="step-grade"
              custom={direction}
              variants={slideVariants}
              initial="enter"
              animate="center"
              exit="exit"
              transition={{ duration: 0.25, ease: "easeInOut" }}
            >
              <h2 className="font-display text-2xl mb-2 text-center">
                Hvilket trinn?
              </h2>
              <p className="text-text-secondary text-sm text-center mb-6">
                {LAUNCH_GRADES.length > 0 && !showAllGrades
                  ? "Lansert for VGS-matte (1T og R1). Flere trinn kommer etter behov."
                  : "Velg klassetrinnet for materialet"}
              </p>

              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
                {visibleGrades.map((g, i) => (
                  <motion.button
                    type="button"
                    key={g.value}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.04 }}
                    onClick={() => {
                      setRequest({ grade: g.value });
                      goNext();
                    }}
                    className={`card-interactive !p-4 text-center ${
                      request.grade === g.value
                        ? "!border-accent-blue bg-accent-blue/5"
                        : ""
                    }`}
                  >
                    <div className="text-lg font-semibold mb-0.5">
                      {g.label}
                    </div>
                    <div className="text-[11px] text-text-muted">{g.sub}</div>
                    {request.grade === g.value && (
                      <motion.div
                        layoutId="grade-check"
                        className="absolute top-2 right-2 w-5 h-5 rounded-full bg-accent-blue flex items-center justify-center text-white text-xs"
                      >
                        ✓
                      </motion.div>
                    )}
                  </motion.button>
                ))}
              </div>
              {LAUNCH_GRADES.length > 0 && LAUNCH_GRADES.length < GRADES.length && (
                <button
                  type="button"
                  onClick={() => setShowAllGrades((v) => !v)}
                  className="mt-4 mx-auto block text-xs text-text-muted hover:text-accent-blue transition-colors"
                >
                  {showAllGrades
                    ? "Vis kun lanseringsnivå (1T / R1)"
                    : "Vis alle trinn (barneskole, ungdomsskole, VGS)"}
                </button>
              )}
            </motion.div>
          )}

          {step === 1 && (
            <motion.div
              key="step-topic"
              custom={direction}
              variants={slideVariants}
              initial="enter"
              animate="center"
              exit="exit"
              transition={{ duration: 0.25, ease: "easeInOut" }}
            >
              <h2 className="font-display text-2xl mb-2 text-center">
                Hvilket emne?
              </h2>
              <p className="text-text-secondary text-sm text-center mb-6">
                Skriv presist tema — eller velg et forslag under
              </p>

              <div className="max-w-lg mx-auto mb-6">
                <label className="text-xs text-text-muted block mb-1.5 text-center">
                  Tema (anbefalt)
                </label>
                <input
                  type="text"
                  value={request.topic}
                  onChange={(e) => setRequest({ topic: e.target.value })}
                  placeholder="F.eks. «Proporsjonalitet i hverdagsøkonomi» eller «Pytagoras i bygg»"
                  className="input text-center w-full"
                  autoFocus
                  aria-label="Skriv matematisk tema"
                />
              </div>

              <p className="text-center text-xs text-text-muted mb-3">
                Vanlige emner for {request.grade}
              </p>
              <div className="flex flex-wrap justify-center gap-2 mb-4">
                {(TOPICS[request.grade] || []).map((topic, i) => (
                  <motion.button
                    type="button"
                    key={topic}
                    initial={{ opacity: 0, scale: 0.9 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: i * 0.04 }}
                    onClick={() => setRequest({ topic })}
                    className={`badge text-sm !py-1.5 !px-3 cursor-pointer transition-all ${
                      request.topic === topic
                        ? "bg-accent-blue text-white"
                        : "bg-surface-elevated text-text-secondary hover:bg-accent-blue/10 hover:text-accent-blue"
                    }`}
                  >
                    {topic}
                  </motion.button>
                ))}
              </div>

              <p className="text-center text-xs">
                <a
                  href="/templates"
                  className="text-accent-blue hover:underline inline-flex items-center gap-1 justify-center"
                >
                  <LayoutTemplate size={12} />
                  Se eksempel på utforming (maler)
                </a>
              </p>
            </motion.div>
          )}

          {step === 2 && (
            <motion.div
              key="step-settings"
              custom={direction}
              variants={slideVariants}
              initial="enter"
              animate="center"
              exit="exit"
              transition={{ duration: 0.25, ease: "easeInOut" }}
            >
              <h2 className="font-display text-2xl mb-2 text-center">
                Type og innstillinger
              </h2>
              <p className="text-text-secondary text-sm text-center mb-4">
                Forhåndsvisning av struktur — ferdig PDF får profesjonell typografi
              </p>

              <MaterialPreviewMock active={request.materialType} />

              <p className="text-xs text-text-muted text-center mb-2">
                Velg materialetype
              </p>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
                {MATERIAL_TYPES.map((type) => (
                  <button
                    type="button"
                    key={type.value}
                    onClick={() => setRequest({ materialType: type.value })}
                    className={`card-interactive !p-4 text-center relative ${
                      request.materialType === type.value
                        ? "!border-accent-blue bg-accent-blue/5"
                        : ""
                    }`}
                  >
                    <div className="text-2xl mb-1">{type.icon}</div>
                    <div className="text-sm font-medium">{type.label}</div>
                    <div className="text-[10px] text-text-muted mt-0.5">
                      {type.desc}
                    </div>
                  </button>
                ))}
              </div>

              <div className="card mb-6">
                <h3 className="text-sm font-medium mb-1">
                  LK20 — kompetansemål (valgfritt)
                </h3>
                <p className="text-xs text-text-muted mb-3">
                  Utvalgte mål for {request.grade}. Søk i feltet under og klikk for å legge til.
                </p>
                <input
                  type="search"
                  value={goalSearch}
                  onChange={(e) => setGoalSearch(e.target.value)}
                  placeholder="Søk etter kode eller nøkkelord..."
                  className="input mb-3"
                  aria-label="Søk kompetansemål"
                />
                <div className="max-h-36 overflow-y-auto space-y-1 mb-3 border border-border rounded-lg p-2">
                  {filteredGoals.map((g) => {
                    const on = request.competencyGoals.includes(g.code);
                    return (
                      <button
                        type="button"
                        key={g.code}
                        onClick={() =>
                          setRequest({
                            competencyGoals: toggleGoal(
                              request.competencyGoals,
                              g.code
                            ),
                          })
                        }
                        className={`w-full text-left text-xs rounded-md px-2 py-1.5 transition-colors ${
                          on
                            ? "bg-accent-blue/15 text-accent-blue"
                            : "hover:bg-surface-elevated text-text-secondary"
                        }`}
                      >
                        <span className="font-mono text-[10px] opacity-80">
                          {g.code}
                        </span>{" "}
                        {g.text}
                      </button>
                    );
                  })}
                </div>
                {request.competencyGoals.length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {request.competencyGoals.map((code) => (
                      <button
                        type="button"
                        key={code}
                        onClick={() =>
                          setRequest({
                            competencyGoals: request.competencyGoals.filter(
                              (c) => c !== code
                            ),
                          })
                        }
                        className="badge text-[10px] !py-0.5 bg-accent-blue/10 text-accent-blue"
                      >
                        {code} ×
                      </button>
                    ))}
                  </div>
                )}
              </div>

              <button
                type="button"
                onClick={() => setShowAdvanced(!showAdvanced)}
                className="text-xs text-text-muted hover:text-text-secondary flex items-center gap-1 mx-auto mb-3 transition-colors"
              >
                <motion.span
                  animate={{ rotate: showAdvanced ? 90 : 0 }}
                  transition={{ duration: 0.15 }}
                >
                  ▸
                </motion.span>
                Avanserte innstillinger
              </button>

              <AnimatePresence>
                {showAdvanced && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    exit={{ opacity: 0, height: 0 }}
                    className="space-y-4 overflow-hidden"
                  >
                    <div className="card">
                      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                        {[
                          { key: "includeTheory" as const, label: "Teori" },
                          { key: "includeExamples" as const, label: "Eksempler" },
                          { key: "includeExercises" as const, label: "Oppgaver" },
                          { key: "includeSolutions" as const, label: "Løsninger" },
                          { key: "includeGraphs" as const, label: "Grafer" },
                        ].map(({ key, label }) => (
                          <label
                            key={key}
                            className="flex items-center gap-2 text-sm cursor-pointer text-text-secondary hover:text-text-primary transition-colors"
                          >
                            <input
                              type="checkbox"
                              checked={request[key]}
                              onChange={(e) =>
                                setRequest({ [key]: e.target.checked })
                              }
                              className="rounded border-border"
                            />
                            {label}
                          </label>
                        ))}
                      </div>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                      <div className="card !p-3">
                        <label className="text-xs text-text-muted mb-1 block">
                          Antall oppgaver: {request.numExercises}
                        </label>
                        <input
                          type="range"
                          min={1}
                          max={30}
                          value={request.numExercises}
                          onChange={(e) =>
                            setRequest({
                              numExercises: parseInt(e.target.value),
                            })
                          }
                          className="w-full accent-accent-blue"
                        />
                      </div>
                      <div className="card !p-3">
                        <label className="text-xs text-text-muted mb-1 block">
                          Vanskelighetsgrad
                        </label>
                        <select
                          value={request.difficulty}
                          onChange={(e) =>
                            setRequest({ difficulty: e.target.value })
                          }
                          className="input !py-1.5"
                        >
                          <option value="Lett">Lett</option>
                          <option value="Middels">Middels</option>
                          <option value="Vanskelig">Vanskelig</option>
                        </select>
                      </div>
                      <div className="card !p-3">
                        <label className="text-xs text-text-muted mb-1 block">
                          Språknivå
                        </label>
                        <select
                          value={request.languageLevel}
                          onChange={(e) =>
                            setRequest({ languageLevel: e.target.value })
                          }
                          className="input !py-1.5"
                        >
                          {LANGUAGE_LEVELS.map((l) => (
                            <option key={l.value} value={l.value}>
                              {l.label}
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>

                    <div className="card !p-3">
                      <label className="text-xs text-text-muted mb-1 block">
                        Spesielle instruksjoner (valgfritt)
                      </label>
                      <textarea
                        value={request.extraInstructions}
                        onChange={(e) =>
                          setRequest({ extraInstructions: e.target.value })
                        }
                        placeholder="f.eks. 'Bruk kontekster fra sport', 'Inkluder bevisoppgaver'"
                        rows={2}
                        className="input resize-none"
                      />
                    </div>

                    <div className="card !p-3 space-y-3">
                      <label className="text-xs text-text-muted block">
                        Design & universell utforming
                      </label>
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                        {THEME_OPTIONS.map((t) => (
                          <button
                            key={t.value}
                            type="button"
                            onClick={() =>
                              setRequest({
                                pdfStyle: { ...request.pdfStyle, theme: t.value },
                              })
                            }
                            className={`rounded-lg border px-2 py-2 text-xs transition-colors ${
                              request.pdfStyle.theme === t.value
                                ? "border-accent-blue bg-accent-blue/10 text-text-primary"
                                : "border-border text-text-secondary hover:text-text-primary"
                            }`}
                          >
                            <span className="mr-1">{t.icon}</span>
                            {t.label}
                          </button>
                        ))}
                      </div>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                        {[
                          { key: "studentMode" as const, label: "Elevkopi (svarlinjer i oppgaver)" },
                          { key: "dyslexia" as const, label: "Dyslektikervennlig" },
                          { key: "highContrast" as const, label: "Høy kontrast" },
                          { key: "accessible" as const, label: "Norsk PDF-språk (skjermleser)" },
                        ].map(({ key, label }) => (
                          <label
                            key={key}
                            className="flex items-center gap-2 text-sm cursor-pointer text-text-secondary hover:text-text-primary transition-colors"
                          >
                            <input
                              type="checkbox"
                              checked={request.pdfStyle[key]}
                              onChange={(e) =>
                                setRequest({
                                  pdfStyle: {
                                    ...request.pdfStyle,
                                    [key]: e.target.checked,
                                  },
                                })
                              }
                              className="rounded border-border"
                            />
                            {label}
                          </label>
                        ))}
                      </div>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <div className="flex items-center justify-between mt-8">
        <button
          type="button"
          onClick={goPrev}
          disabled={step === 0}
          className="btn-ghost disabled:opacity-30"
        >
          <ChevronLeft size={16} />
          Tilbake
        </button>

        {step < totalSteps - 1 ? (
          <button type="button" onClick={goNext} className="btn-primary">
            Neste
            <ChevronRight size={16} />
          </button>
        ) : (
          <div className="flex flex-col items-end gap-2">
            {estimateLoading && (
              <p className="text-xs text-text-muted">Estimerer kostnad…</p>
            )}
            {costEstimate && !estimateLoading && (
              <p className="text-xs text-text-muted text-right max-w-xs">
                Ca. {costEstimate.estimated_total_tokens.toLocaleString("nb-NO")}{" "}
                tokens
                {costEstimate.cache_available
                  ? ` · ${costEstimate.similar_cached} lignende i hurtigbuffer (kan bli raskere)`
                  : ""}
              </p>
            )}
            <button
              type="button"
              onClick={handleGenerate}
              disabled={!canGenerate}
              className="btn-primary !px-8 shadow-lg shadow-accent-blue/20 disabled:opacity-40 disabled:shadow-none"
            >
              <Sparkles size={16} />
              Generer materiale
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
