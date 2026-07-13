/**
 * Zustand store for MateMaTeX 2.0 — lightweight state management.
 */

import { create } from "zustand";
import type { ErrorCategory } from "@/lib/map-api-result";
import { categorizeError } from "@/lib/map-api-result";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
export type PdfTheme = "default" | "calm" | "playful" | "highcontrast";

export interface PdfStyle {
  theme: PdfTheme;
  studentMode: boolean;
  accessible: boolean;
  dyslexia: boolean;
  highContrast: boolean;
}

export interface GenerationRequest {
  grade: string;
  topic: string;
  materialType: string;
  languageLevel: string;
  numExercises: number;
  difficulty: string;
  includeTheory: boolean;
  includeExamples: boolean;
  includeExercises: boolean;
  includeSolutions: boolean;
  includeGraphs: boolean;
  competencyGoals: string[];
  extraInstructions: string;
  pdfStyle: PdfStyle;
}

export interface AgentStep {
  agent: string;
  startedAt: string;
  completedAt: string | null;
  durationSeconds: number;
  outputSummary: string;
  error: string;
  retries: number;
}

export interface MathClaimDetail {
  claimId: string;
  latexExpression: string;
  claimType: string;
  context: string;
  isCorrect: boolean | null;
  errorMessage: string;
  expectedResult: string;
  actualResult: string;
}

export interface LayoutIssue {
  kind: string;
  severity: "info" | "warning" | "error";
  detail: string;
  overflowPt: number;
}

export interface LayoutReport {
  score: number;
  issues: LayoutIssue[];
  overfullCount: number;
  underfullCount: number;
  maxOverflowPt: number;
  undefinedReferences: number;
  summary: string;
}

export interface ContentQualityReport {
  passed: boolean;
  score: number;
  semanticScore?: number;
  semanticSummary?: string;
  missingSubtopics: string[];
  issues: Array<{
    code: string;
    severity: "warning" | "error";
    message: string;
  }>;
}

export interface GenerationResult {
  jobId: string;
  status:
    | "pending"
    | "running"
    | "completed"
    | "completed_with_warnings"
    | "failed";
  fullDocument: string;
  pdfUrl: string;
  pdfBase64: string;
  usedLatexFallback: boolean;
  fromCache: boolean;
  differentiatedBasic: string;
  differentiatedAdvanced: string;
  warningReason: string;
  contentQuality?: ContentQualityReport;
  layoutReport?: LayoutReport;
  layoutFixAttempts?: number;
  steps: AgentStep[];
  mathVerification: {
    claimsChecked: number;
    claimsCorrect: number;
    claimsIncorrect: number;
    claimsUnparseable: number;
    allCorrect: boolean;
    summary: string;
    incorrectClaims: MathClaimDetail[];
    unparseableClaims: MathClaimDetail[];
  };
  latexCompiled: boolean;
  totalDuration: number;
  error: string;
  /** Innstillinger brukt ved generering (visning, LK20, «lag lignende») */
  generationMeta?: GenerationRequest;
  errorCategory?: ErrorCategory;
}

// ---------------------------------------------------------------------------
// Store
// ---------------------------------------------------------------------------
interface AppStore {
  // Generation form
  request: GenerationRequest;
  setRequest: (partial: Partial<GenerationRequest>) => void;
  resetRequest: () => void;

  // Generation state
  isGenerating: boolean;
  currentJobId: string | null;
  currentAgent: string | null;
  steps: AgentStep[];
  result: GenerationResult | null;
  /** Siste skjema ved feil — for «Prøv igjen» */
  lastFailedRequest: GenerationRequest | null;

  // Actions
  startGeneration: (jobId?: string) => void;
  setJobId: (jobId: string) => void;
  cancelGeneration: () => void;
  addStep: (step: AgentStep) => void;
  setCurrentAgent: (agent: string | null) => void;
  setResult: (result: GenerationResult | null) => void;
  /**
   * failedRequest: oppgi skjema for «Prøv igjen». null = tøm. undefined = ikke endre lagret.
   */
  setError: (
    error: string,
    failedRequest?: GenerationRequest | null
  ) => void;
  clearLastFailedRequest: () => void;

  // UI
  showLatexEditor: boolean;
  toggleLatexEditor: () => void;
}

const DEFAULT_REQUEST: GenerationRequest = {
  grade: "10. trinn",
  topic: "",
  materialType: "arbeidsark",
  languageLevel: "standard",
  numExercises: 10,
  difficulty: "Middels",
  includeTheory: true,
  includeExamples: true,
  includeExercises: true,
  includeSolutions: true,
  includeGraphs: true,
  competencyGoals: [],
  extraInstructions: "",
  pdfStyle: {
    theme: "default",
    studentMode: false,
    accessible: false,
    dyslexia: false,
    highContrast: false,
  },
};

const emptyMathVerification = (): GenerationResult["mathVerification"] => ({
  claimsChecked: 0,
  claimsCorrect: 0,
  claimsIncorrect: 0,
  claimsUnparseable: 0,
  allCorrect: false,
  summary: "",
  incorrectClaims: [],
  unparseableClaims: [],
});

export const useAppStore = create<AppStore>((set) => ({
  // Form
  request: { ...DEFAULT_REQUEST },
  setRequest: (partial) =>
    set((state) => ({ request: { ...state.request, ...partial } })),
  resetRequest: () => set({ request: { ...DEFAULT_REQUEST } }),

  // Generation state
  isGenerating: false,
  currentJobId: null,
  currentAgent: null,
  steps: [],
  result: null,
  lastFailedRequest: null,

  // Actions
  startGeneration: (jobId?: string) =>
    set({
      isGenerating: true,
      currentJobId: jobId || null,
      currentAgent: null,
      steps: [],
      result: null,
    }),
  setJobId: (jobId: string) => set({ currentJobId: jobId }),
  cancelGeneration: () =>
    set({
      isGenerating: false,
      currentJobId: null,
      currentAgent: null,
      steps: [],
    }),
  addStep: (step) =>
    set((state) => ({ steps: [...state.steps, step] })),
  setCurrentAgent: (agent) => set({ currentAgent: agent }),
  setResult: (result) =>
    set({
      result,
      isGenerating: false,
      currentAgent: null,
      lastFailedRequest: null,
    }),
  setError: (error, failedRequest) =>
    set((state) => ({
      result: {
        jobId: state.currentJobId || "",
        status: "failed",
        fullDocument: "",
        pdfUrl: "",
        pdfBase64: "",
        usedLatexFallback: false,
        warningReason: "",
        fromCache: false,
        differentiatedBasic: "",
        differentiatedAdvanced: "",
        steps: state.steps,
        mathVerification: emptyMathVerification(),
        latexCompiled: false,
        totalDuration: 0,
        error,
        errorCategory: categorizeError(
          error,
          false,
          !error.toLowerCase().includes("avbrutt")
        ),
      },
      isGenerating: false,
      lastFailedRequest:
        failedRequest === undefined
          ? state.lastFailedRequest
          : failedRequest,
    })),
  clearLastFailedRequest: () => set({ lastFailedRequest: null }),

  // UI
  showLatexEditor: false,
  toggleLatexEditor: () =>
    set((state) => ({ showLatexEditor: !state.showLatexEditor })),
}));
