"use client";

import { motion } from "framer-motion";
import { useAppStore } from "@/lib/store";
import { agentLabel } from "@/lib/agent-labels";
import { abortGeneration, closeActiveStream } from "@/lib/api";
import {
  GraduationCap,
  PenTool,
  Calculator,
  CheckCircle2,
  Code2,
  Wrench,
  Circle,
  Loader2,
  AlertTriangle,
  XCircle,
} from "lucide-react";

const AGENT_INFO: Record<
  string,
  {
    name: string;
    icon: React.ReactNode;
    description: string;
    color: string;
  }
> = {
  pedagogue: {
    name: "Pedagogen",
    icon: <GraduationCap size={18} />,
    description: "Planlegger innhold basert på LK20...",
    color: "accent-blue",
  },
  author: {
    name: "Forfatteren",
    icon: <PenTool size={18} />,
    description: "Skriver LaTeX med matematikk og illustrasjoner...",
    color: "accent-green",
  },
  math_verifier: {
    name: "Matematikkverifisering",
    icon: <Calculator size={18} />,
    description: "Verifiserer alle beregninger med SymPy...",
    color: "accent-purple",
  },
  editor: {
    name: "Redaktøren",
    icon: <CheckCircle2 size={18} />,
    description: "Kvalitetssikrer innholdet...",
    color: "accent-teal",
  },
  tikz_validator: {
    name: "Figur-kontroll (TikZ)",
    icon: <Code2 size={18} />,
    description: "Sjekker og retter TikZ-figurer...",
    color: "accent-orange",
  },
  table_validator: {
    name: "Tabell-kontroll",
    icon: <Code2 size={18} />,
    description: "Sjekker tabeller i LaTeX...",
    color: "accent-orange",
  },
  latex_validator: {
    name: "LaTeX-kompilering",
    icon: <Code2 size={18} />,
    description: "Kompilerer med pdflatex...",
    color: "accent-orange",
  },
  latex_fixer: {
    name: "LaTeX-fikser",
    icon: <Wrench size={18} />,
    description: "Retter kompileringsfeil...",
    color: "accent-red",
  },
  content_quality: {
    name: "Innholdskontroll",
    icon: <CheckCircle2 size={18} />,
    description: "Sjekker pensumdekning og kapitteldybde...",
    color: "accent-teal",
  },
  final_math_verifier: {
    name: "Endelig fasitkontroll",
    icon: <Calculator size={18} />,
    description: "Verifiserer fasit etter redigering...",
    color: "accent-purple",
  },
  latex_fallback: {
    name: "Forenkling (Fallback)",
    icon: <Wrench size={18} />,
    description: "Fjerner avansert grafikk for å redde dokumentet...",
    color: "accent-red",
  },
  layout: {
    name: "Layout-kontroll",
    icon: <CheckCircle2 size={18} />,
    description: "Vurderer sideoppsett og lesbarhet...",
    color: "accent-teal",
  },
};

const BASE_PIPELINE_ORDER = [
  "pedagogue",
  "author",
  "math_verifier",
  "editor",
  "final_math_verifier",
  "content_quality",
  "tikz_validator",
  "table_validator",
  "latex_validator",
  "layout",
];

export function PipelineProgress() {
  const steps = useAppStore((s) => s.steps);
  const currentAgent = useAppStore((s) => s.currentAgent);
  const currentJobId = useAppStore((s) => s.currentJobId);
  const request = useAppStore((s) => s.request);
  const setError = useAppStore((s) => s.setError);
  const cancelGeneration = useAppStore((s) => s.cancelGeneration);
  const completedAgents = new Set(steps.map((s) => s.agent));

  const handleAbort = async () => {
    if (!currentJobId) return;
    closeActiveStream();
    cancelGeneration();
    // Show the aborted state immediately — the DELETE below also stops all
    // client-side polling so a late server completion can't overwrite it.
    setError("Genereringen ble avbrutt av bruker.", request);
    try {
      await abortGeneration(currentJobId);
    } catch (err: unknown) {
      console.error("Failed to abort:", err);
    }
  };

  // Dynamically add fixer/fallback to the timeline if they are used
  const displayOrder = [...BASE_PIPELINE_ORDER];
  if (completedAgents.has("latex_fixer") || currentAgent === "latex_fixer") {
    displayOrder.push("latex_fixer");
  }
  if (completedAgents.has("latex_fallback") || currentAgent === "latex_fallback") {
    displayOrder.push("latex_fallback");
  }

  // Estimate remaining time
  const completedCount = completedAgents.size;
  const totalAgents = displayOrder.length;
  const avgDuration =
    steps.length > 0
      ? steps.reduce((sum, s) => sum + (s.durationSeconds || 0), 0) /
        steps.length
      : 5;
  const remaining = Math.max(0, (totalAgents - completedCount) * avgDuration);
  const currentInfo = currentAgent
    ? AGENT_INFO[currentAgent] || {
        name: agentLabel(currentAgent),
        icon: <Loader2 size={18} className="animate-spin" />,
        description: "Jobber...",
        color: "accent-blue",
      }
    : null;
  const liveStatus = currentInfo
    ? `${currentInfo.name} jobber: ${currentInfo.description}`
    : completedCount === 0
    ? "Starter generering. Vanligvis 1–3 minutter."
    : remaining > 0
    ? `Omtrent ${Math.round(remaining)} sekunder igjen.`
    : "Fullfører siste steg.";

  return (
    <div className="max-w-reading mx-auto">
      <div
        className="sr-only"
        aria-live="polite"
        aria-atomic="true"
        role="status"
      >
        {liveStatus}
      </div>
      {/* Header */}
      <div className="text-center mb-8">
        <h2 className="font-display text-2xl mb-2">
          AI-teamet jobber
        </h2>
        <p className="text-sm text-text-secondary">
          Oppgaveark/prøve: ofte 1–3 minutter. Kapittel med redaktør: 3–6 minutter.
          Du får resultatet selv om fremdriftsstrømmen avbrytes (~5 min på Vercel).
        </p>
        <p className="text-sm text-text-secondary mt-1">
          {remaining > 0
            ? `~${Math.round(remaining)} sekunder igjen (estimat)`
            : "Snart ferdig..."}
        </p>
        <p className="text-xs text-text-muted mt-4 max-w-md mx-auto leading-relaxed">
          Mens du venter: sjekk at trinn og tema stemmer, forbered mappe for PDF,
          eller les om{" "}
          <a href="/exercises" className="text-accent-blue hover:underline">
            oppgavebanken
          </a>
          .
        </p>
      </div>

      {/* Timeline */}
      <div className="relative max-w-lg mx-auto">
        {/* Vertical line */}
        <div className="absolute left-5 top-0 bottom-0 w-px bg-border" />

        <div className="space-y-1">
          {displayOrder.map((agentKey, index) => {
            const info = AGENT_INFO[agentKey] || {
              name: agentLabel(agentKey),
              description: "Fullført",
              color: "accent-blue",
            };
            const isCompleted = completedAgents.has(agentKey);
            const isCurrent = currentAgent === agentKey;
            const step = steps.find((s) => s.agent === agentKey);
            const hasError = step?.error;
            const retryCount = step?.retries || 0;

            return (
              <motion.div
                key={agentKey}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: index * 0.1 }}
                className="relative flex items-start gap-4 py-3"
              >
                {/* Node */}
                <div className="relative z-10 flex-shrink-0">
                  {isCompleted ? (
                    <motion.div
                      initial={{ scale: 0 }}
                      animate={{ scale: 1 }}
                      className="w-10 h-10 rounded-full bg-accent-green/15 flex items-center justify-center text-accent-green"
                    >
                      <CheckCircle2 size={20} />
                    </motion.div>
                  ) : isCurrent ? (
                    <div className="w-10 h-10 rounded-full bg-accent-blue/15 flex items-center justify-center text-accent-blue animate-pulse-ring">
                      {hasError ? (
                        <AlertTriangle size={18} className="text-accent-orange" />
                      ) : (
                        <motion.div
                          animate={{ rotate: 360 }}
                          transition={{
                            repeat: Infinity,
                            duration: 2,
                            ease: "linear",
                          }}
                        >
                          <Loader2 size={18} />
                        </motion.div>
                      )}
                    </div>
                  ) : (
                    <div className="w-10 h-10 rounded-full bg-surface-elevated flex items-center justify-center text-text-muted">
                      <Circle size={16} />
                    </div>
                  )}
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0 pt-1.5">
                  <div className="flex items-center gap-2">
                    <span
                      className={`text-sm font-medium ${
                        isCompleted || isCurrent
                          ? "text-text-primary"
                          : "text-text-muted"
                      }`}
                    >
                      {info.name}
                    </span>
                    {retryCount > 0 && (
                      <span className="badge bg-accent-orange/15 text-accent-orange">
                        Forsøk {retryCount + 1}/3
                      </span>
                    )}
                    {isCompleted && step?.durationSeconds && (
                      <span className="text-xs text-text-muted">
                        {step.durationSeconds.toFixed(1)}s
                      </span>
                    )}
                  </div>

                  {/* Description / status */}
                  <p className="text-xs text-text-muted mt-0.5 truncate">
                    {isCurrent
                      ? info.description
                      : isCompleted
                      ? step?.outputSummary || "Fullført"
                      : "Venter..."}
                  </p>

                  {/* Error message */}
                  {hasError && isCurrent && (
                    <motion.p
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      className="text-xs text-accent-orange mt-1"
                    >
                      Retter: {step.error}
                    </motion.p>
                  )}
                </div>
              </motion.div>
            );
          })}
        </div>
      </div>

      {/* Retries info */}
      {steps.some((s) => s.retries > 0) && (
        <p className="text-xs text-text-muted text-center mt-6">
          Verifisering kjører — feil rettes automatisk
        </p>
      )}

      {/* Abort Button */}
      <div className="flex justify-center mt-8">
        <button
          onClick={handleAbort}
          className="btn-ghost text-accent-red hover:bg-accent-red/10 flex items-center gap-2"
        >
          <XCircle size={16} />
          Avbryt generering
        </button>
      </div>
    </div>
  );
}
