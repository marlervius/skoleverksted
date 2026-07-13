/** SSE payloads from GET /generate/{jobId}/stream */

export interface StreamStepPayload {
  agent: string;
  started_at: string;
  completed_at: string | null;
  duration_seconds: number;
  output_summary: string;
  error: string;
  retries: number;
}

export interface StreamCurrentAgentPayload {
  agent: string;
}

export interface StreamCompletePayload {
  status:
    | "pending"
    | "running"
    | "completed"
    | "completed_with_warnings"
    | "failed";
  total_duration: number;
  total_steps: number;
  math_checks: number;
  math_correct: number;
  latex_compiled: boolean;
  error: string | null;
}

export interface StreamErrorPayload {
  message: string;
}
