/**
 * API client for MateMaTeX 2.0.
 *
 * Browser requests go through same-origin `/api/backend/*` proxy (server adds MATE_API_KEY).
 * SSE uses `/api/generate/[jobId]/stream`. PDF preview uses `/api/generate/[jobId]/pdf`.
 */

import type {
  StreamCompletePayload,
  StreamCurrentAgentPayload,
  StreamStepPayload,
} from "@/types/generation";

function getApiBase(): string {
  if (typeof window !== "undefined") {
    return "/api/backend";
  }
  return (
    process.env.BACKEND_INTERNAL_URL ||
    process.env.NEXT_PUBLIC_MATE_API_URL ||
    `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/matematikk`
  ).replace(/\/$/, "");
}

function apiUrl(path: string): string {
  const clean = path.replace(/^\//, "");
  return `${getApiBase()}/${clean}`;
}

let activeStreamClose: (() => void) | null = null;

export function closeActiveStream(): void {
  activeStreamClose?.();
  activeStreamClose = null;
}

// Aborted jobs + live poll signals. Abort must stop every watcher, otherwise a
// job that finishes server-side after the user cancels would still flip the UI
// to a success view.
const abortedJobs = new Set<string>();
const activeWatchSignals = new Set<{ cancelled: boolean }>();

export function isJobAborted(jobId: string): boolean {
  return abortedJobs.has(jobId);
}

function cancelAllWatchers(): void {
  for (const s of activeWatchSignals) s.cancelled = true;
  activeWatchSignals.clear();
}

async function readErrorMessage(res: Response): Promise<string> {
  try {
    const data = await res.json();
    if (typeof data?.detail === "string") return data.detail;
    if (Array.isArray(data?.detail)) {
      return data.detail.map((d: { msg?: string }) => d.msg || "").filter(Boolean).join("; ");
    }
  } catch {
    /* ignore */
  }
  return res.statusText || `HTTP ${res.status}`;
}

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    ...(init?.headers as Record<string, string>),
  };
  if (init?.body && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  const res = await fetch(url, { ...init, headers });
  if (!res.ok) {
    throw new Error(`${res.status}: ${await readErrorMessage(res)}`);
  }
  return res.json() as Promise<T>;
}

function parseStreamData<T>(data: string, label: string): T | null {
  try {
    return JSON.parse(data) as T;
  } catch {
    console.warn(`Invalid SSE ${label} payload`);
    return null;
  }
}

// ---------------------------------------------------------------------------
// Generation
// ---------------------------------------------------------------------------
export interface GenerateRequest {
  grade: string;
  topic: string;
  material_type: string;
  language_level: string;
  num_exercises: number;
  difficulty: string;
  include_theory: boolean;
  include_examples: boolean;
  include_exercises: boolean;
  include_solutions: boolean;
  include_graphs: boolean;
  competency_goals: string[];
  extra_instructions: string;
  pdf_style?: {
    theme: string;
    student_mode?: boolean;
    accessible: boolean;
    dyslexia: boolean;
    high_contrast: boolean;
  };
}

export interface GenerateResponse {
  job_id: string;
  status: string;
  message: string;
  from_cache?: boolean;
}

const TERMINAL_GENERATE_STATUSES = new Set([
  "completed",
  "completed_with_warnings",
  "failed",
]);

export interface GenerationResultApi {
  job_id: string;
  status: string;
  full_document: string;
  pdf_path?: string;
  pdf_available?: boolean;
  math_verification: Record<string, unknown>;
  content_quality?: Record<string, unknown>;
  latex_compilation: Record<string, unknown>;
  layout_report?: Record<string, unknown>;
  steps: Array<Record<string, unknown>>;
  total_duration_seconds: number;
  total_tokens: number;
  error: string;
}

export async function startGeneration(
  request: GenerateRequest
): Promise<GenerateResponse> {
  const res = await fetch(apiUrl("generate"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!res.ok) {
    const msg = await readErrorMessage(res);
    if (res.status === 401) {
      throw new Error("Ingen tilgang (401). Sjekk at MATE_API_KEY er satt på serveren.");
    }
    if (res.status === 429) {
      throw new Error("For mange forespørsler. Vent et minutt og prøv igjen.");
    }
    throw new Error(msg || `Generation failed: ${res.statusText}`);
  }
  return res.json();
}

export function isTerminalGenerateStatus(status: string): boolean {
  return TERMINAL_GENERATE_STATUSES.has(status);
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/** Fetch with timeout — works in browsers without AbortSignal.timeout. */
function fetchWithTimeout(
  url: string,
  init: RequestInit = {},
  timeoutMs = 20_000
): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  const ext = init.signal;
  if (ext) {
    if (ext.aborted) controller.abort();
    else ext.addEventListener("abort", () => controller.abort(), { once: true });
  }
  return fetch(url, { ...init, signal: controller.signal }).finally(() =>
    clearTimeout(timer)
  );
}

export interface JobStatusResponse {
  job_id: string;
  status: string;
  ready: boolean;
  latex_compiled: boolean;
  total_duration_seconds: number;
  error: string;
}

type StatusFetchResult =
  | { kind: "ok"; data: JobStatusResponse }
  | { kind: "not_found" }
  | { kind: "error"; status: number };

async function fetchJobStatus(jobId: string): Promise<StatusFetchResult> {
  try {
    const res = await fetchWithTimeout(apiUrl(`generate/${jobId}/status`), {}, 12_000);
    if (res.status === 404) return { kind: "not_found" };
    if (!res.ok) return { kind: "error", status: res.status };
    const data = (await res.json()) as JobStatusResponse;
    return { kind: "ok", data };
  } catch {
    return { kind: "error", status: 0 };
  }
}

/** Poll interval: fast while the job is likely still running, slower afterwards. */
function pollDelayMs(attempt: number): number {
  return attempt < 90 ? 500 : 1500;
}

const JOB_GONE_MESSAGE =
  "Serveren mistet jobben (ofte etter omstart på Render). " +
  "Genereringen kan ha fullført — sjekk Historikk, eller prøv igjen.";

const POLL_EXHAUSTED_MESSAGE =
  "Fikk ikke bekreftet at jobben var ferdig. " +
  "Sjekk Historikk — materialet kan ligge der hvis genereringen fullførte.";

/** Poll lightweight /status until the job is ready. */
async function pollJobUntilTerminal(
  jobId: string,
  onComplete: (data: StreamCompletePayload) => void,
  signal: { cancelled: boolean },
  onGiveUp?: (message: string) => void
): Promise<boolean> {
  activeWatchSignals.add(signal);
  try {
    return await pollJobLoop(jobId, onComplete, signal, onGiveUp);
  } finally {
    activeWatchSignals.delete(signal);
  }
}

async function pollJobLoop(
  jobId: string,
  onComplete: (data: StreamCompletePayload) => void,
  signal: { cancelled: boolean },
  onGiveUp?: (message: string) => void
): Promise<boolean> {
  let notFoundStreak = 0;
  for (let i = 0; i < 180; i++) {
    if (signal.cancelled || abortedJobs.has(jobId)) return false;
    if (i > 0) {
      await sleep(pollDelayMs(i));
      if (signal.cancelled || abortedJobs.has(jobId)) return false;
    }
    const raw = await fetchJobStatus(jobId);
    if (raw.kind === "not_found") {
      notFoundStreak += 1;
      // After a few 404s the backend likely restarted (/tmp wiped on Render).
      if (notFoundStreak >= 4) {
        onGiveUp?.(JOB_GONE_MESSAGE);
        return false;
      }
      continue;
    }
    notFoundStreak = 0;
    if (raw.kind === "error") continue;
    if (!raw.data.ready) continue;
    const status = String(raw.data.status ?? "");
    if (!TERMINAL_GENERATE_STATUSES.has(status)) continue;
    if (signal.cancelled || abortedJobs.has(jobId)) return false;
    onComplete({
      status: status as StreamCompletePayload["status"],
      total_duration: Number(raw.data.total_duration_seconds ?? 0),
      total_steps: 0,
      math_checks: 0,
      math_correct: 0,
      latex_compiled: Boolean(raw.data.latex_compiled),
      error: raw.data.error ? String(raw.data.error) : null,
    });
    return true;
  }
  onGiveUp?.(POLL_EXHAUSTED_MESSAGE);
  return false;
}

export function streamProgress(
  jobId: string,
  callbacks: {
    onStep?: (step: StreamStepPayload) => void;
    onCurrentAgent?: (agent: string) => void;
    onComplete?: (data: StreamCompletePayload) => void;
    onError?: (error: string) => void;
  }
): () => void {
  closeActiveStream();

  const url =
    typeof window !== "undefined"
      ? `/api/generate/${encodeURIComponent(jobId)}/stream`
      : apiUrl(`generate/${encodeURIComponent(jobId)}/stream`);

  const eventSource = new EventSource(url);
  const signal = { cancelled: false };
  let finished = false;

  const finish = (data: StreamCompletePayload) => {
    if (finished) return;
    finished = true;
    callbacks.onComplete?.(data);
    closeActiveStream();
  };

  eventSource.addEventListener("step", (e: MessageEvent) => {
    const step = parseStreamData<StreamStepPayload>(e.data, "step");
    if (step) callbacks.onStep?.(step);
  });
  eventSource.addEventListener("current_agent", (e: MessageEvent) => {
    const p = parseStreamData<StreamCurrentAgentPayload>(e.data, "current_agent");
    if (p) callbacks.onCurrentAgent?.(p.agent);
  });
  eventSource.addEventListener("complete", (e: MessageEvent) => {
    const data = parseStreamData<StreamCompletePayload>(e.data, "complete");
    if (data) finish(data);
  });
  eventSource.addEventListener("error", (e: Event) => {
    if (finished) return;
    if ("data" in e && (e as MessageEvent).data) {
      try {
        const j = JSON.parse((e as MessageEvent).data) as { message?: string };
        finished = true;
        callbacks.onError?.(j.message || "Feil fra strømmen");
        closeActiveStream();
        return;
      } catch {
        /* fall through */
      }
    }
    if (eventSource.readyState === EventSource.CONNECTING) {
      return;
    }
    eventSource.close();
    const giveUp = (msg: string) => {
      if (finished || signal.cancelled) return;
      finished = true;
      callbacks.onError?.(msg);
      closeActiveStream();
    };
    void (async () => {
      if (finished || signal.cancelled) return;
      await pollJobUntilTerminal(jobId, (data) => finish(data), signal, giveUp);
    })();
  });

  // Backstop polling: SSE delivery is unreliable through serverless proxies and
  // free-tier hosts — the connection can stay "open" while the `complete` event
  // is buffered or dropped, leaving the UI waiting forever even though the job
  // already finished. We poll /status in parallel so completion is never missed.
  void (async () => {
    if (finished || signal.cancelled) return;
    const giveUp = (msg: string) => {
      if (finished || signal.cancelled) return;
      finished = true;
      callbacks.onError?.(msg);
      closeActiveStream();
    };
    await pollJobUntilTerminal(jobId, (data) => finish(data), signal, giveUp);
  })();

  const close = () => {
    signal.cancelled = true;
    eventSource.close();
    if (activeStreamClose === close) {
      activeStreamClose = null;
    }
  };
  activeStreamClose = close;
  return close;
}

export async function abortGeneration(jobId: string): Promise<{ success: boolean; message: string }> {
  abortedJobs.add(jobId);
  cancelAllWatchers();
  closeActiveStream();
  return fetchJson(apiUrl(`generate/${jobId}`), { method: "DELETE" });
}

export async function getResult(
  jobId: string,
  maxAttempts = 15,
  signal?: AbortSignal
): Promise<GenerationResultApi> {
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    if (signal?.aborted) {
      throw new Error("Henting av resultat avbrutt");
    }
    const res = await fetchWithTimeout(
      apiUrl(`generate/${jobId}/result`),
      { signal },
      45_000
    );
    if (res.status === 202) {
      await new Promise((r) => setTimeout(r, Math.min(400 * (attempt + 1), 3000)));
      continue;
    }
    if (!res.ok) {
      throw new Error(`${res.status}: ${await readErrorMessage(res)}`);
    }
    return res.json() as Promise<GenerationResultApi>;
  }
  throw new Error("Resultat ikke klart ennå — prøv igjen om litt");
}

/**
 * Poll /result until the job reaches a terminal status, then invoke onReady.
 * Runs in parallel with SSE so completion is never missed when the stream stalls.
 */
export async function watchGenerationJob(
  jobId: string,
  onReady: (status: JobStatusResponse) => void | Promise<void>,
  signal: { cancelled: boolean },
  onGiveUp?: (message: string) => void
): Promise<boolean> {
  activeWatchSignals.add(signal);
  try {
    let notFoundStreak = 0;
    for (let i = 0; i < 180; i++) {
      if (signal.cancelled || abortedJobs.has(jobId)) return false;
      if (i > 0) {
        await sleep(pollDelayMs(i));
        if (signal.cancelled || abortedJobs.has(jobId)) return false;
      }
      const raw = await fetchJobStatus(jobId);
      if (raw.kind === "not_found") {
        notFoundStreak += 1;
        if (notFoundStreak >= 4) {
          onGiveUp?.(JOB_GONE_MESSAGE);
          return false;
        }
        continue;
      }
      notFoundStreak = 0;
      if (raw.kind === "error") continue;
      if (!raw.data.ready) continue;
      if (!TERMINAL_GENERATE_STATUSES.has(raw.data.status)) continue;
      if (signal.cancelled || abortedJobs.has(jobId)) return false;
      await onReady(raw.data);
      return true;
    }
    onGiveUp?.(POLL_EXHAUSTED_MESSAGE);
    return false;
  } finally {
    activeWatchSignals.delete(signal);
  }
}

export async function fetchJobPdfObjectUrl(jobId: string): Promise<string> {
  const url =
    typeof window !== "undefined"
      ? `/api/generate/${encodeURIComponent(jobId)}/pdf`
      : apiUrl(`generate/${encodeURIComponent(jobId)}/pdf`);
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(await readErrorMessage(res));
  }
  const blob = await res.blob();
  return URL.createObjectURL(blob);
}

export async function downloadJobPdf(
  jobId: string,
  filename = "matematex-lærerkopi.pdf"
): Promise<void> {
  const url =
    typeof window !== "undefined"
      ? `/api/generate/${encodeURIComponent(jobId)}/pdf`
      : apiUrl(`generate/${encodeURIComponent(jobId)}/pdf`);
  const res = await fetch(url);
  if (!res.ok) throw new Error(await readErrorMessage(res));
  const objectUrl = URL.createObjectURL(await res.blob());
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(objectUrl);
}

export interface CostEstimateResponse {
  estimated_input_tokens: number;
  estimated_output_tokens: number;
  estimated_total_tokens: number;
  similar_cached: number;
  cache_available: boolean;
}

export async function estimateCost(
  request: GenerateRequest
): Promise<CostEstimateResponse> {
  return fetchJson<CostEstimateResponse>(apiUrl("estimate"), {
    method: "POST",
    body: JSON.stringify(request),
  });
}

// ---------------------------------------------------------------------------
// Editor
// ---------------------------------------------------------------------------
export async function verifyLatex(latexContent: string): Promise<{
  claims_checked: number;
  claims_correct: number;
  claims_incorrect: number;
  claims_unparseable: number;
  all_correct: boolean;
  summary: string;
  errors: Array<Record<string, unknown>>;
  unparseable_claims: Array<Record<string, unknown>>;
}> {
  return fetchJson(apiUrl("verify-latex"), {
    method: "POST",
    body: JSON.stringify({ latex_content: latexContent }),
  });
}

export async function createGenerationVersion(
  generationId: string,
  latexBody: string,
  changeSummary = "Manuell redigering"
): Promise<{ id: string; version_number: number }> {
  return fetchJson(apiUrl(`generations/${encodeURIComponent(generationId)}/versions`), {
    method: "POST",
    body: JSON.stringify({
      latex_body: latexBody,
      change_summary: changeSummary,
    }),
  });
}

export async function compileLatex(
  latexBody: string,
  filename: string = "preview"
): Promise<{
  success: boolean;
  pdf_base64: string;
  errors: Array<{ line: number; message: string; severity: string }>;
  warnings: Array<{ line: number; message: string; severity: string }>;
  cached: boolean;
}> {
  return fetchJson(apiUrl("editor/compile"), {
    method: "POST",
    body: JSON.stringify({ latex_body: latexBody, filename }),
  });
}

export async function editorAction(
  action: "simplify" | "add-illustration" | "variant" | "add-hint",
  selection: string,
  fullContext: string = "",
  extra: string = ""
): Promise<{
  success: boolean;
  replacement_latex: string;
  explanation: string;
  error: string;
}> {
  return fetchJson(apiUrl(`editor/${action}`), {
    method: "POST",
    body: JSON.stringify({
      latex_selection: selection,
      full_context: fullContext,
      extra_instructions: extra,
    }),
  });
}

// ---------------------------------------------------------------------------
// Exercises
// ---------------------------------------------------------------------------
export interface Exercise {
  id: string;
  title: string;
  number: number;
  latex_content: string;
  solution: string;
  hints: string[];
  difficulty: string;
  exercise_type: string;
  keywords: string[];
  has_figure: boolean;
  sub_parts: string[];
  topic: string;
  grade_level: string;
  source_generation_id: string;
  times_used: number;
  user_rating: number | null;
  created_at: string;
}

export async function listExercises(params?: {
  topic?: string;
  grade_level?: string;
  exercise_type?: string;
  difficulty?: string;
  page?: number;
  page_size?: number;
}): Promise<{ exercises: Exercise[]; total: number; page: number; page_size: number }> {
  const sp = new URLSearchParams();
  if (params?.topic) sp.set("topic", params.topic);
  if (params?.grade_level) sp.set("grade_level", params.grade_level);
  if (params?.exercise_type) sp.set("exercise_type", params.exercise_type);
  if (params?.difficulty) sp.set("difficulty", params.difficulty);
  if (params?.page) sp.set("page", String(params.page));
  if (params?.page_size) sp.set("page_size", String(params.page_size));
  return fetchJson(`${apiUrl("exercises")}?${sp.toString()}`);
}

export async function searchExercises(
  query: string,
  limit: number = 20
): Promise<{ exercises: Exercise[]; total: number }> {
  return fetchJson(`${apiUrl("exercises/search")}?q=${encodeURIComponent(query)}&limit=${limit}`);
}

export async function ingestExercises(
  latexContent: string,
  topic: string = "",
  gradeLevel: string = "",
  generationId: string = ""
): Promise<{ ingested: number; exercise_ids: string[] }> {
  return fetchJson(apiUrl("exercises/ingest"), {
    method: "POST",
    body: JSON.stringify({
      latex_content: latexContent,
      topic,
      grade_level: gradeLevel,
      generation_id: generationId,
    }),
  });
}

export async function updateExercise(
  exerciseId: string,
  patch: {
    title?: string;
    latex_content?: string;
    solution?: string;
    topic?: string;
    grade_level?: string;
  }
): Promise<Exercise> {
  return fetchJson(apiUrl(`exercises/${encodeURIComponent(exerciseId)}`), {
    method: "PUT",
    body: JSON.stringify(patch),
  });
}

export interface M1LevelReport {
  level: string;
  total_points: number;
  green_pct: number;
  fixable_pct: number;
  realistic_ceiling_pct: number;
  red_pct: number;
}

export interface M1Report {
  source: string;
  is_example: boolean;
  levels: M1LevelReport[];
  topics: Array<{ level: string; topic: string; total_points: number; green_pct: number }>;
}

export async function fetchM1Report(): Promise<M1Report> {
  return fetchJson(apiUrl("m1/report"));
}

export async function fetchSharedPdfObjectUrl(token: string): Promise<string> {
  const url =
    typeof window !== "undefined"
      ? `/api/backend/sharing/${encodeURIComponent(token)}/pdf`
      : apiUrl(`sharing/${encodeURIComponent(token)}/pdf`);
  const res = await fetch(url);
  if (!res.ok) throw new Error(await readErrorMessage(res));
  return URL.createObjectURL(await res.blob());
}

export async function findSimilarExercises(exerciseId: string, limit: number = 5): Promise<Exercise[]> {
  return fetchJson(`${apiUrl(`exercises/${exerciseId}/similar`)}?limit=${limit}`);
}

export async function generateVariant(exerciseId: string, instructions: string = ""): Promise<Exercise> {
  return fetchJson(apiUrl(`exercises/${exerciseId}/variant`), {
    method: "POST",
    body: JSON.stringify({ instructions }),
  });
}

export async function exportExercises(
  exerciseIds: string[],
  format: "pdf" | "docx" = "pdf",
  includeSolutions: boolean = true,
  title: string = "Oppgaveark"
): Promise<{ success: boolean; content_base64: string; filename: string; errors: string[] }> {
  return fetchJson(apiUrl("exercises/export"), {
    method: "POST",
    body: JSON.stringify({
      exercise_ids: exerciseIds,
      format,
      include_solutions: includeSolutions,
      title,
    }),
  });
}

// ---------------------------------------------------------------------------
// Differentiation
// ---------------------------------------------------------------------------
export async function differentiate(
  latexContent: string,
  topic: string = "",
  grade: string = ""
): Promise<{
  success: boolean;
  basic_latex: string;
  standard_latex: string;
  advanced_latex: string;
  basic_exercise_count: number;
  standard_exercise_count: number;
  advanced_exercise_count: number;
  basic_quality?: {
    score: number;
    passed: boolean;
    math_verified: boolean;
    issue_count: number;
    summary: string;
  } | null;
  standard_quality?: {
    score: number;
    passed: boolean;
    math_verified: boolean;
    issue_count: number;
    summary: string;
  } | null;
  advanced_quality?: {
    score: number;
    passed: boolean;
    math_verified: boolean;
    issue_count: number;
    summary: string;
  } | null;
  errors: string[];
}> {
  return fetchJson(apiUrl("differentiation/generate"), {
    method: "POST",
    body: JSON.stringify({ latex_content: latexContent, topic, grade }),
  });
}

export async function generateHints(
  exerciseId: string,
  exerciseLatex: string,
  solution: string = ""
): Promise<{ success: boolean; hints: { nudge: string; step: string; near_solution: string }; error: string }> {
  return fetchJson(apiUrl(`exercises/${exerciseId}/hints`), {
    method: "POST",
    body: JSON.stringify({ exercise_latex: exerciseLatex, solution }),
  });
}

// ---------------------------------------------------------------------------
// Export
// ---------------------------------------------------------------------------
export async function exportPdf(params: {
  latex_content: string;
  include_solutions?: boolean;
  include_cover?: boolean;
  cover_school?: string;
  cover_teacher?: string;
  cover_subject?: string;
  cover_topic?: string;
  print_optimized?: boolean;
  theme?: string;
  student_mode?: boolean;
  accessible?: boolean;
  dyslexia?: boolean;
  high_contrast?: boolean;
}): Promise<{ success: boolean; content_base64: string; filename: string; mime_type: string; errors: string[] }> {
  return fetchJson(apiUrl("export/pdf"), { method: "POST", body: JSON.stringify(params) });
}

export async function exportDocx(
  latexContent: string,
  title: string = "Oppgaveark",
  includeSolutions: boolean = true
): Promise<{ success: boolean; content_base64: string; filename: string; mime_type: string; errors: string[] }> {
  return fetchJson(apiUrl("export/docx"), {
    method: "POST",
    body: JSON.stringify({ latex_content: latexContent, title, include_solutions: includeSolutions }),
  });
}

export async function exportPptx(
  latexContent: string,
  title: string = "Matematikk",
  solutionsAs: "speaker_notes" | "hidden_slides" = "speaker_notes"
): Promise<{ success: boolean; content_base64: string; filename: string; mime_type: string; errors: string[] }> {
  return fetchJson(apiUrl("export/pptx"), {
    method: "POST",
    body: JSON.stringify({ latex_content: latexContent, title, solutions_as: solutionsAs }),
  });
}

// ---------------------------------------------------------------------------
// Sharing
// ---------------------------------------------------------------------------
export async function createShare(params: {
  resource_type: string;
  resource_id: string;
  password?: string;
  expires_hours?: number;
  max_views?: number;
}): Promise<{ success: boolean; token: string; share_url: string; expires_at: string | null }> {
  return fetchJson(apiUrl("sharing"), { method: "POST", body: JSON.stringify(params) });
}

export async function getShared(
  token: string,
  password?: string
): Promise<{
  success: boolean;
  resource_type: string;
  content: Record<string, unknown>;
  allow_download: boolean;
  allow_clone: boolean;
}> {
  if (password) {
    return fetchJson(apiUrl(`sharing/${token}/access`), {
      method: "POST",
      body: JSON.stringify({ password }),
    });
  }
  return fetchJson(apiUrl(`sharing/${token}`));
}

export async function cloneShared(
  token: string,
  password?: string
): Promise<{ success: boolean; new_resource_id: string }> {
  return fetchJson(apiUrl(`sharing/${token}/clone`), {
    method: "POST",
    body: JSON.stringify({ password: password || null }),
  });
}

export async function downloadSharedLatex(content: Record<string, unknown>, filename = "delt-materiale.tex") {
  const latex = String(content.full_document || "");
  const blob = new Blob([latex], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

// ---------------------------------------------------------------------------
// School bank
// ---------------------------------------------------------------------------
export interface SchoolExercise {
  id: string;
  title: string;
  topic: string;
  grade_level: string;
  difficulty: string;
  latex_content: string;
  published_by: string;
  published_at: string;
}

export async function listSchoolExercises(params?: {
  topic?: string;
  grade_level?: string;
  page?: number;
  page_size?: number;
}): Promise<{ exercises: SchoolExercise[]; total: number }> {
  const sp = new URLSearchParams();
  if (params?.topic) sp.set("topic", params.topic);
  if (params?.grade_level) sp.set("grade_level", params.grade_level);
  if (params?.page) sp.set("page", String(params.page));
  if (params?.page_size) sp.set("page_size", String(params.page_size));
  return fetchJson(`${apiUrl("school/exercises")}?${sp.toString()}`);
}

export async function publishToSchool(
  exerciseId: string,
  school: string = ""
): Promise<{ published: boolean; exercise_id: string }> {
  return fetchJson(apiUrl(`school/exercises/${exerciseId}/publish`), {
    method: "POST",
    body: JSON.stringify({ exercise_id: exerciseId, school }),
  });
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
export function downloadBase64(
  base64: string,
  filename: string,
  mimeType: string = "application/octet-stream"
) {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  const blob = new Blob([bytes], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
