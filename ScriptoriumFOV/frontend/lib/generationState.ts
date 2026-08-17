import type {
  ArtifactMetadata,
  GenerationStatus,
} from "./fovTypes";

export interface GenerationProgress {
  step: number;
  totalSteps: number;
  message: string;
  eventType?: string;
}

export interface GenerationState {
  status: GenerationStatus;
  jobId: string | null;
  requestId: string | null;
  progress: GenerationProgress | null;
  artifact: ArtifactMetadata | null;
  errorMessage: string;
  isDual: boolean;
}

export const initialGenerationState: GenerationState = {
  status: "idle",
  jobId: null,
  requestId: null,
  progress: null,
  artifact: null,
  errorMessage: "",
  isDual: false,
};

type LifecycleStatus =
  | "running"
  | "completed"
  | "needs_teacher_review"
  | "failed"
  | "cancelled";

export type GenerationAction =
  | { type: "started"; jobId: string; isDual?: boolean }
  | {
      type: "status_received";
      jobId: string;
      requestId?: string;
      step: number;
      totalSteps: number;
      message: string;
      eventType?: string;
      jobStatus?: LifecycleStatus;
      artifact?: ArtifactMetadata | null;
    }
  | { type: "failed"; jobId: string; message: string }
  | { type: "local_failed"; message: string }
  | { type: "cancelled"; jobId: string; message?: string }
  | { type: "reset" };

function isTerminal(status: GenerationStatus): boolean {
  return [
    "completed",
    "needs_teacher_review",
    "failed",
    "cancelled",
  ].includes(status);
}

function statusFromPayload(
  action: Extract<GenerationAction, { type: "status_received" }>,
  artifact: ArtifactMetadata | null,
): GenerationStatus {
  if (action.jobStatus === "failed") return "failed";
  if (action.jobStatus === "needs_teacher_review") return "needs_teacher_review";
  if (action.jobStatus === "cancelled") return "cancelled";
  if (action.jobStatus === "completed" && artifact) return "completed";
  if (action.eventType === "artifact_building") return "building_artifact";
  if (action.eventType === "artifact_ready") return "building_artifact";
  if (action.step >= action.totalSteps) return "building_artifact";
  return "generating";
}

export function generationReducer(
  state: GenerationState,
  action: GenerationAction,
): GenerationState {
  if (action.type === "reset") return initialGenerationState;
  if (action.type === "started") {
    return {
      ...initialGenerationState,
      status: "generating",
      jobId: action.jobId,
      isDual: !!action.isDual,
    };
  }
  if (action.type === "local_failed") {
    return {
      ...initialGenerationState,
      status: "failed",
      errorMessage: action.message,
    };
  }
  if (state.jobId !== action.jobId) return state;
  if (action.type === "failed") {
    return {
      ...state,
      status: "failed",
      errorMessage: action.message,
      progress: null,
    };
  }
  if (action.type === "cancelled") {
    return {
      ...state,
      status: "cancelled",
      errorMessage: action.message || "Genereringen ble avbrutt.",
      progress: null,
    };
  }
  if (isTerminal(state.status)) return state;

  const artifact = action.artifact ?? state.artifact;
  const nextStatus = statusFromPayload(action, artifact);
  return {
    ...state,
    requestId: action.requestId ?? state.requestId,
    progress: {
      step: action.step,
      totalSteps: action.totalSteps,
      message: action.message,
      eventType: action.eventType,
    },
    artifact,
    status: nextStatus,
    errorMessage:
      nextStatus === "failed" || nextStatus === "needs_teacher_review" || nextStatus === "cancelled"
        ? action.message
        : "",
  };
}
