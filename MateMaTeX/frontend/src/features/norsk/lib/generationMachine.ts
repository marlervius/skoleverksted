export type GenerationStatus =
  | "idle"
  | "generating"
  | "needs_user_action"
  | "needs_teacher_review"
  | "completed"
  | "failed"
  | "cancelled";

export type RecoveryAction =
  | "retry"
  | "retry_image"
  | "continue_without_image"
  | "choose_commons"
  | "upload_image"
  | "open_teacher_review"
  | "cancel";

export interface GenerationProgress {
  step: number;
  totalSteps: number;
  message: string;
  stepName?: string;
}

export interface GenerationState {
  status: GenerationStatus;
  jobId: string | null;
  requestId: string | null;
  progress: GenerationProgress | null;
  errorMessage: string;
  errorCode: string | null;
  failedStepName: string | null;
  availableActions: RecoveryAction[];
  startedAt: number | null;
  isDual: boolean;
}

export const initialGenerationState: GenerationState = {
  status: "idle",
  jobId: null,
  requestId: null,
  progress: null,
  errorMessage: "",
  errorCode: null,
  failedStepName: null,
  availableActions: [],
  startedAt: null,
  isDual: false,
};

export type GenerationAction =
  | {
      type: "started";
      jobId: string;
      requestId?: string;
      totalSteps: number;
      message?: string;
      isDual?: boolean;
      startedAt?: number;
    }
  | {
      type: "progress_received";
      jobId: string;
      requestId?: string;
      step: number;
      totalSteps: number;
      message: string;
      stepName?: string;
    }
  | {
      type: "terminal_received";
      jobId: string;
      status: Exclude<GenerationStatus, "idle" | "generating">;
      message: string;
      requestId?: string;
      stepName?: string;
      errorCode?: string;
      availableActions?: RecoveryAction[];
    }
  | { type: "local_failed"; message: string; requestId?: string; errorCode?: string }
  | { type: "reset" };

export function isGenerating(state: GenerationState): boolean {
  return state.status === "generating";
}

export function getGenerationControls(state: GenerationState, formValid: boolean) {
  const generating = isGenerating(state);
  return {
    primaryLabel: generating ? "Genererer..." : "Generer PDF",
    primaryDisabled: !formValid || generating,
    previewDisabled: !formValid || generating,
  };
}

export function isPollingExpired(startedAt: number, now = Date.now()): boolean {
  return now - startedAt > 6 * 60_000;
}

export function generationReducer(
  state: GenerationState,
  action: GenerationAction,
): GenerationState {
  if (action.type === "reset") return initialGenerationState;
  if (action.type === "local_failed") {
    return {
      ...initialGenerationState,
      status: "failed",
      requestId: action.requestId ?? state.requestId,
      errorMessage: action.message,
      errorCode: action.errorCode ?? "client_error",
      availableActions: ["retry", "cancel"],
    };
  }
  if (action.type === "started") {
    return {
      ...initialGenerationState,
      status: "generating",
      jobId: action.jobId,
      requestId: action.requestId ?? null,
      startedAt: action.startedAt ?? Date.now(),
      isDual: !!action.isDual,
      progress: {
        step: 0,
        totalSteps: action.totalSteps,
        message: action.message ?? "Starter generering …",
      },
    };
  }
  if (state.jobId !== action.jobId) return state;
  if (action.type === "progress_received") {
    if (state.status !== "generating") return state;
    return {
      ...state,
      requestId: action.requestId ?? state.requestId,
      progress: {
        step: action.step,
        totalSteps: action.totalSteps,
        message: action.message,
        stepName: action.stepName,
      },
    };
  }
  return {
    ...state,
    status: action.status,
    requestId: action.requestId ?? state.requestId,
    progress: null,
    errorMessage: action.status === "completed" ? "" : action.message,
    errorCode: action.errorCode ?? null,
    failedStepName: action.stepName ?? null,
    availableActions: action.availableActions ?? (
      action.status === "failed" ? ["retry", "cancel"] : []
    ),
  };
}
