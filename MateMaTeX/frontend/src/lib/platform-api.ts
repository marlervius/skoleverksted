import { serviceBackendUrl } from "./backend-url";

export type ProjectStatus = "draft" | "ready" | "generating" | "completed" | "archived";

export interface Project {
  id: string;
  title: string;
  theme: string;
  subject: string;
  level: string;
  description: string;
  competency_goals: string[];
  metadata: Record<string, unknown>;
  status: ProjectStatus;
  created_at: string;
  updated_at: string;
}

export interface QualityCheck {
  code: string;
  label: string;
  status: "passed" | "warning" | "failed" | "not_applicable";
  detail: string;
  deterministic: boolean;
}

export interface QualityPassport {
  version: string;
  generated_at: string;
  module: string;
  title: string;
  overall_status: "passed" | "needs_review" | "failed";
  score: number;
  checks: QualityCheck[];
  sources: string[];
  competency_goals: string[];
  limitations: string[];
  prompt_version: string;
}

export type TruthClaimStatus =
  | "verified"
  | "interpretation"
  | "disputed"
  | "time_sensitive"
  | "unsupported"
  | "verification_failed"
  | "source_unavailable"
  | "not_evaluated";

export interface TruthSource {
  title: string;
  url: string;
  publisher: string;
  source_tier: "primary" | "authoritative" | "editorial" | "other";
  retrieved_at: string;
  origin: "teacher" | "grounding" | "model";
  fetch_status: "provided" | "grounded" | "model_reported" | "fetched" | "source_unavailable";
}

export interface TruthClaim {
  id: string;
  claim: string;
  exact_text: string;
  status: TruthClaimStatus;
  action: "keep" | "qualify" | "remove";
  replacement: string;
  source_urls: string[];
  evidence: string;
  confidence: number;
}

export interface TruthPassport {
  version: string;
  generated_at: string;
  status: "verified" | "needs_review" | "blocked" | "verification_failed" | "source_unavailable" | "not_evaluated";
  topic: string;
  subject: string;
  coverage_percent: number;
  verified_claims: number;
  total_claims: number;
  claims: TruthClaim[];
  sources: TruthSource[];
  removed_claims: string[];
  limitations: string[];
  summary: string;
}

export interface ThemePackTask {
  id: string;
  module: "fag" | "norsk" | "matematikk";
  title: string;
  brief: string;
  href: string;
  status: "ready" | "generated";
}

export interface ThemePack {
  id: string;
  project: Project;
  tasks: ThemePackTask[];
  quality_passport: QualityPassport;
  created_at: string;
}

export interface ThemePackInput {
  title: string;
  theme: string;
  subject: string;
  level: string;
  norwegian_level: string;
  duration_lessons: number;
  description: string;
  source_text: string;
  source_name: string;
  competency_goals: string[];
  include_assessment: boolean;
  include_teacher_guide: boolean;
}

export interface PlatformJob {
  id: string;
  module: "fag" | "norsk" | "matematikk" | "platform";
  kind: string;
  status: string;
  progress: number;
  message: string;
  project_id: string | null;
  request_summary: Record<string, unknown>;
  result_summary: Record<string, unknown>;
  quality_passport: Partial<QualityPassport>;
  queue_position: number | null;
  retryable: boolean;
  attempt: number;
  created_at: string;
  updated_at: string;
}

export type RepairJobStatus =
  | "queued"
  | "running"
  | "succeeded"
  | "failed_retryable"
  | "failed_terminal"
  | "cancelled"
  | "superseded";

export interface RepairJob {
  id: string;
  operation_id: string;
  compendium_id: string;
  chapter_id: string;
  chapter_title: string;
  status: RepairJobStatus;
  message: string;
  chapter_token: string;
  result_token: string;
  source_revision: string;
  output_revision: string;
  chapter_status: string | null;
  repair_summary: RepairSummary | null;
  failure_reason: string;
  attempt: number;
  cancel_requested: boolean;
  lease_expires_at: string;
  created_at: string;
  updated_at: string;
  started_at: string;
  finished_at: string;
}

export interface RepairJobAccepted {
  job_id: string;
  operation_id: string;
  compendium_id: string;
  chapter_id: string;
  status: RepairJobStatus;
  status_url: string;
}

export interface RepairLedgerEntry {
  id: string;
  job_id: string;
  operation_id: string;
  stage: string;
  created_at: string;
  payload: Record<string, unknown>;
}

export type RepairActionKind =
  | "keep"
  | "qualify"
  | "replace"
  | "remove"
  | "source_required"
  | "manual_review";

export interface RepairChange {
  issue_id: string;
  action: RepairActionKind;
  result: "applied" | "unresolved" | "manual_review" | "skipped";
  before: string;
  after: string;
  reason: string;
  source_refs: string[];
}

export interface RepairMetrics {
  verified_claims: number;
  total_claims: number;
  coverage: number;
  unresolved: number;
  source_grounding_failures: number;
  language_failures: number;
}

export interface RepairSummary {
  before: RepairMetrics;
  after: RepairMetrics;
  changes: RepairChange[];
  found_count: number;
  repaired_count: number;
  qualified_count: number;
  replaced_count: number;
  removed_count: number;
  unresolved_count: number;
  manual_review_count: number;
  pass_count: number;
  stop_reason: string;
}

export const REPAIR_POLL_INTERVAL_MS = 3000;

const ACTIVE_REPAIR_STATUSES: RepairJobStatus[] = ["queued", "running"];

export const isActiveRepairStatus = (status: RepairJobStatus) =>
  ACTIVE_REPAIR_STATUSES.includes(status);

export const isTerminalRepairStatus = (status: RepairJobStatus) =>
  !isActiveRepairStatus(status);

/** What the teacher is told, and whether they can do anything about it. */
export function repairStatusView(job: RepairJob): {
  label: string;
  detail: string;
  tone: "busy" | "ok" | "warn" | "info";
  canRetry: boolean;
} {
  switch (job.status) {
    case "queued":
      return {
        label: "Sjekker fakta og kilder",
        detail:
          "Reparasjonen er lagret på serveren. Du kan forlate siden og komme tilbake senere.",
        tone: "busy",
        canRetry: false,
      };
    case "running":
      return {
        label: "Lager plan og retter dokumenterte problemer",
        detail:
          "Serveren undersøker kildene og retter teksten. Du kan forlate siden; arbeidet fortsetter.",
        tone: "busy",
        canRetry: false,
      };
    case "succeeded":
      return {
        label: "Automatisk revisjon ferdig",
        detail: job.message || "Ny tekst og nytt faktapass er lagret. Kontroller endringene før du godkjenner.",
        tone: "ok",
        canRetry: false,
      };
    case "superseded":
      return {
        label: "Din nyere tekst ble beholdt",
        detail:
          "Kapittelet ble redigert mens reparasjonen kjørte. Den nyere teksten din er bevart, "
          + "og reparasjonsresultatet ble forkastet. Start reparasjonen på nytt hvis du fortsatt ønsker den.",
        tone: "info",
        canRetry: true,
      };
    case "cancelled":
      return {
        label: "Reparasjonen ble avbrutt",
        detail: job.message || "Reparasjonen ble avbrutt. Kapittelet er uendret.",
        tone: "info",
        canRetry: true,
      };
    case "failed_terminal":
      return {
        label: "Reparasjonen kan ikke kjøres",
        detail: job.message || "Reparasjonen kan ikke fullføres for dette kapittelet.",
        tone: "warn",
        canRetry: false,
      };
    default:
      return {
        label: "Reparasjonen feilet",
        detail: job.message || "Kapittelet er ikke endret.",
        tone: "warn",
        canRetry: true,
      };
  }
}

export type YearPlanStatus = "draft" | "active" | "completed" | "archived";
export type YearPlanPeriodStatus = "not_started" | "in_progress" | "ready" | "completed" | "needs_revision";
export type MaterialStatus = "draft" | "approved" | "used" | "needs_revision";
export type MaterialKind =
  | "learning_sheet"
  | "worksheet"
  | "lesson_sequence"
  | "assessment"
  | "presentation"
  | "source_task"
  | "differentiated"
  | "compendium"
  | "other";

export interface YearPlanMaterial {
  id: string;
  title: string;
  kind: MaterialKind;
  status: MaterialStatus;
  version: number;
  filename: string;
  mime_type: string;
  size_bytes: number;
  notes: string;
  created_at: string;
  updated_at: string;
}

export interface YearPlanPeriod {
  id: string;
  order: number;
  title: string;
  theme: string;
  week_start: string;
  week_end: string;
  duration_weeks: number;
  lesson_count: number;
  overview: string;
  learning_goals: string[];
  competency_goals: string[];
  key_concepts: string[];
  suggested_activities: string[];
  assessment: string;
  teacher_notes: string;
  status: YearPlanPeriodStatus;
  materials: YearPlanMaterial[];
}

export interface YearPlan {
  id: string;
  title: string;
  subject: string;
  level: string;
  school_year: string;
  lessons_per_week: number;
  lesson_minutes: number;
  teaching_weeks: number;
  competency_goals: string[];
  periods: YearPlanPeriod[];
  notes: string;
  planning_source: "ai" | "fallback" | "manual";
  status: YearPlanStatus;
  created_at: string;
  updated_at: string;
}

export interface YearPlanGenerateInput {
  title?: string;
  subject: string;
  level: string;
  school_year: string;
  lessons_per_week: number;
  lesson_minutes: number;
  teaching_weeks: number;
  number_of_periods: number;
  competency_goals: string[];
  constraints: string;
  use_ai: boolean;
}

export type CompendiumKind =
  | "thematic"
  | "chronological"
  | "reference"
  | "comparative"
  | "source_collection"
  | "appendix";
export type CompendiumStatus = "outline" | "writing" | "review" | "approved" | "archived";
export type CompendiumChapterStatus =
  | "planned"
  | "generated"
  | "approved"
  | "needs_revision"
  | "generation_incomplete"
  | "parse_failure"
  | "language_quality_failed"
  | "source_grounding_failed"
  | "verification_failed";
export type CompendiumImageMode = "none" | "commons" | "ai";

export interface CompendiumSource {
  title: string;
  url: string;
  publisher: string;
  origin: "teacher" | "grounding" | "model";
  fetch_status: "provided" | "grounded" | "model_reported" | "fetched" | "source_unavailable";
}

export interface ScopeContract {
  reference_date: string;
  geography: string;
  inclusion_criteria: string[];
  exclusions: string[];
  completeness_label: "complete" | "documented" | "selected";
  completeness_note: string;
}

export interface CompendiumChapter {
  id: string;
  order: number;
  title: string;
  purpose: string;
  guiding_questions: string[];
  content_markdown: string;
  key_facts: string[];
  glossary: string[];
  sources: CompendiumSource[];
  verification_notes: string[];
  truth_passport: TruthPassport | null;
  content_revision: string;
  revision_summary: string[];
  repair_summary: RepairSummary | null;
  previous_content_markdown: string;
  revision_count: number;
  status: CompendiumChapterStatus;
  updated_at: string;
}

export interface Compendium {
  id: string;
  title: string;
  topic: string;
  subject: string;
  level: string;
  kind: CompendiumKind;
  purpose: string;
  audience: string;
  target_pages: number;
  competency_goals: string[];
  source_brief: string;
  scope_contract: ScopeContract;
  chapters: CompendiumChapter[];
  include_timeline: boolean;
  include_tables: boolean;
  include_glossary: boolean;
  include_reflection_tasks: boolean;
  image_mode: CompendiumImageMode;
  year_plan_id: string | null;
  period_ids: string[];
  planning_source: "ai" | "fallback" | "manual";
  status: CompendiumStatus;
  pdf_filename: string;
  pdf_size_bytes: number;
  docx_filename: string;
  docx_size_bytes: number;
  artifact_version: number;
  approved_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface CompendiumPlanInput {
  title?: string;
  topic: string;
  subject: string;
  level: string;
  kind: CompendiumKind;
  purpose: string;
  audience: string;
  target_pages: number;
  chapter_count: number;
  competency_goals: string[];
  source_brief: string;
  include_timeline: boolean;
  include_tables: boolean;
  include_glossary: boolean;
  include_reflection_tasks: boolean;
  image_mode: CompendiumImageMode;
  year_plan_id?: string | null;
  period_ids: string[];
  use_ai: boolean;
}

const baseUrl = () => serviceBackendUrl(undefined, "api/platform");

export class PlatformApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly requestId: string;
  readonly retryable: boolean;

  constructor(message: string, details: { status: number; code?: string; requestId?: string; retryable?: boolean }) {
    super(message);
    this.name = "PlatformApiError";
    this.status = details.status;
    this.code = details.code || "platform_error";
    this.requestId = details.requestId || "";
    this.retryable = Boolean(details.retryable);
  }
}

function validationDetail(value: unknown): string {
  if (typeof value === "string") return value;
  if (Array.isArray(value)) {
    return value.map((item) => (item && typeof item === "object" && "msg" in item ? String(item.msg) : ""))
      .filter(Boolean)
      .join("; ");
  }
  return "";
}

function friendlyPlatformError(status: number, detail: string): { message: string; code: string; retryable: boolean } {
  if (detail && status !== 500) return { message: detail, code: `http_${status}`, retryable: status === 429 || status >= 500 };
  if (status === 401 || status === 403) return { message: "Du mangler tilgang til denne funksjonen. Kontroller innlogging eller API-oppsett.", code: "access_denied", retryable: false };
  if (status === 404) return { message: "Fant ikke innholdet. Last siden på nytt og prøv igjen.", code: "not_found", retryable: false };
  if (status === 409) return { message: detail || "Handlingen kan ikke utføres ennå. Følg kontrollpunktene på siden først.", code: "conflict", retryable: false };
  if (status === 422) return { message: "Noen felt er ugyldige eller mangler. Kontroller skjemaet og prøv igjen.", code: "validation", retryable: false };
  if (status === 429) return { message: "Tjenesten har mange forespørsler akkurat nå. Vent litt og prøv igjen.", code: "rate_limited", retryable: true };
  if (status >= 500) return { message: "Serveren klarte ikke å fullføre handlingen. Prøv igjen om litt.", code: "server_error", retryable: true };
  return { message: detail || `Plattformfeil (${status})`, code: `http_${status}`, retryable: false };
}

async function requestJson<T>(path: string, init?: RequestInit, timeoutMs = 150_000): Promise<T> {
  let response: Response;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    response = await fetch(`${baseUrl()}${path}`, {
      ...init,
      signal: init?.signal || controller.signal,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new PlatformApiError(
        "Handlingen tok for lang tid og ble avbrutt. Kapittelet er ikke endret; prøv igjen.",
        { status: 408, code: "request_timeout", retryable: true },
      );
    }
    throw new PlatformApiError("Fikk ikke kontakt med serveren. Kontroller nettverket og prøv igjen.", {
      status: 0,
      code: "network_error",
      retryable: true,
    });
  } finally {
    clearTimeout(timeout);
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const friendly = friendlyPlatformError(response.status, validationDetail(body.detail));
    const requestId = response.headers.get("x-request-id") || (typeof body.request_id === "string" ? body.request_id : "");
    const suffix = requestId ? ` (sporings-ID: ${requestId})` : "";
    throw new PlatformApiError(`${friendly.message}${suffix}`, { status: response.status, code: friendly.code, requestId, retryable: friendly.retryable });
  }
  return response.json() as Promise<T>;
}

export const listProjects = (limit = 50) => requestJson<Project[]>(`/projects?limit=${limit}`);
export const getProject = (id: string) => requestJson<Project>(`/projects/${encodeURIComponent(id)}`);
export const listPlatformJobs = (limit = 100, projectId?: string) =>
  requestJson<PlatformJob[]>(`/jobs?limit=${limit}${projectId ? `&project_id=${encodeURIComponent(projectId)}` : ""}`);
export const listQueue = (limit = 100) => requestJson<PlatformJob[]>(`/queue?limit=${limit}`);
export const cancelPlatformJob = (jobId: string) =>
  requestJson<PlatformJob>(`/jobs/${encodeURIComponent(jobId)}/cancel`, { method: "POST" });
export const createThemePack = (input: ThemePackInput) =>
  requestJson<ThemePack>("/theme-packs", { method: "POST", body: JSON.stringify(input) });
export const submitGenerationFeedback = (input: {
  module: PlatformJob["module"];
  artifact_id?: string;
  project_id?: string | null;
  rating: "up" | "down";
  reason?: string;
}) => requestJson<{ id: string }>("/feedback", { method: "POST", body: JSON.stringify(input) });

export const listYearPlans = (limit = 50) =>
  requestJson<YearPlan[]>(`/year-plans?limit=${limit}`);
export const getYearPlan = (id: string) =>
  requestJson<YearPlan>(`/year-plans/${encodeURIComponent(id)}`);
export const generateYearPlan = (input: YearPlanGenerateInput) =>
  requestJson<YearPlan>("/year-plans/generate", {
    method: "POST",
    body: JSON.stringify(input),
  });
export const updateYearPlan = (id: string, input: Partial<YearPlan>) =>
  requestJson<YearPlan>(`/year-plans/${encodeURIComponent(id)}`, {
    method: "PATCH",
    body: JSON.stringify(input),
  });
export const updateYearPlanPeriod = (
  planId: string,
  periodId: string,
  input: Partial<YearPlanPeriod>,
) =>
  requestJson<YearPlan>(
    `/year-plans/${encodeURIComponent(planId)}/periods/${encodeURIComponent(periodId)}`,
    { method: "PATCH", body: JSON.stringify(input) },
  );

export async function saveYearPlanMaterial(input: {
  planId: string;
  periodId: string;
  title: string;
  kind: MaterialKind;
  filename: string;
  blob: Blob;
  status?: MaterialStatus;
  notes?: string;
}): Promise<{ plan: YearPlan; material: YearPlanMaterial }> {
  const query = new URLSearchParams({
    title: input.title,
    kind: input.kind,
    filename: input.filename,
    status: input.status ?? "approved",
    notes: input.notes ?? "",
  });
  const response = await fetch(
    `${baseUrl()}/year-plans/${encodeURIComponent(input.planId)}/periods/${encodeURIComponent(input.periodId)}/materials?${query}`,
    {
      method: "POST",
      headers: { "Content-Type": input.blob.type || "application/pdf" },
      body: input.blob,
    },
  );
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(typeof body.detail === "string" ? body.detail : `Lagringsfeil (${response.status})`);
  }
  return response.json() as Promise<{ plan: YearPlan; material: YearPlanMaterial }>;
}

export const updateYearPlanMaterial = (
  planId: string,
  periodId: string,
  materialId: string,
  input: Partial<YearPlanMaterial>,
) =>
  requestJson<{ plan: YearPlan; material: YearPlanMaterial }>(
    `/year-plans/${encodeURIComponent(planId)}/periods/${encodeURIComponent(periodId)}/materials/${encodeURIComponent(materialId)}`,
    { method: "PATCH", body: JSON.stringify(input) },
  );

export const yearPlanMaterialDownloadUrl = (planId: string, materialId: string) =>
  `${baseUrl()}/year-plans/${encodeURIComponent(planId)}/materials/${encodeURIComponent(materialId)}/download`;

export const listCompendia = (limit = 50) =>
  requestJson<Compendium[]>(`/compendia?limit=${limit}`);
export const getCompendium = (id: string) =>
  requestJson<Compendium>(`/compendia/${encodeURIComponent(id)}`);
export const createCompendiumOutline = (input: CompendiumPlanInput) =>
  requestJson<Compendium>("/compendia/outline", {
    method: "POST",
    body: JSON.stringify(input),
  });
export const updateCompendium = (id: string, input: Partial<Compendium>) =>
  requestJson<Compendium>(`/compendia/${encodeURIComponent(id)}`, {
    method: "PATCH",
    body: JSON.stringify(input),
  });
export const updateCompendiumChapter = (
  compendiumId: string,
  chapterId: string,
  input: Partial<CompendiumChapter>,
) =>
  requestJson<Compendium>(
    `/compendia/${encodeURIComponent(compendiumId)}/chapters/${encodeURIComponent(chapterId)}`,
    { method: "PATCH", body: JSON.stringify(input) },
  );
export const generateCompendiumChapter = (compendiumId: string, chapterId: string) =>
  requestJson<Compendium>(
    `/compendia/${encodeURIComponent(compendiumId)}/chapters/${encodeURIComponent(chapterId)}/generate`,
    { method: "POST" },
  );
/**
 * Starts a repair and returns as soon as the job is durable.
 *
 * The model work happens in a backend worker, so this call must not be given a
 * long client timeout — a slow response here means registration failed, not
 * that the repair is slow.
 */
export const repairCompendiumChapter = (
  compendiumId: string,
  chapterId: string,
  operationId?: string,
) =>
  requestJson<RepairJobAccepted>(
    `/compendia/${encodeURIComponent(compendiumId)}/chapters/${encodeURIComponent(chapterId)}/repair`,
    {
      method: "POST",
      headers: operationId ? { "x-operation-id": operationId } : undefined,
    },
    30_000,
  );

export const getRepairJob = (jobId: string) =>
  requestJson<RepairJob>(`/repair-jobs/${encodeURIComponent(jobId)}`, undefined, 20_000);

export const listRepairJobEvents = (jobId: string) =>
  requestJson<RepairLedgerEntry[]>(
    `/repair-jobs/${encodeURIComponent(jobId)}/events`,
    undefined,
    20_000,
  );

/** Returns the chapter's most recent repair, or null when there never was one. */
export async function getChapterRepairJob(
  compendiumId: string,
  chapterId: string,
): Promise<RepairJob | null> {
  try {
    return await requestJson<RepairJob>(
      `/compendia/${encodeURIComponent(compendiumId)}/chapters/${encodeURIComponent(chapterId)}/repair`,
      undefined,
      20_000,
    );
  } catch (error) {
    if (error instanceof PlatformApiError && error.status === 404) return null;
    throw error;
  }
}

export const cancelRepairJob = (jobId: string) => cancelPlatformJob(jobId);

/** Polls one repair job to a terminal status. Never starts a new repair itself. */
export async function awaitRepairJob(
  jobId: string,
  options: { onUpdate?: (job: RepairJob) => void; intervalMs?: number; signal?: AbortSignal } = {},
): Promise<RepairJob> {
  const interval = options.intervalMs ?? REPAIR_POLL_INTERVAL_MS;
  for (;;) {
    const job = await getRepairJob(jobId);
    options.onUpdate?.(job);
    if (isTerminalRepairStatus(job.status)) return job;
    if (options.signal?.aborted) return job;
    await new Promise((resolve) => setTimeout(resolve, interval));
  }
}
export const compileCompendium = (compendiumId: string) =>
  requestJson<Compendium>(`/compendia/${encodeURIComponent(compendiumId)}/compile`, {
    method: "POST",
  });
export const approveCompendium = (compendiumId: string) =>
  requestJson<Compendium>(`/compendia/${encodeURIComponent(compendiumId)}/approve`, {
    method: "POST",
  });
export const compendiumDownloadUrl = (compendiumId: string, artifactType: "pdf" | "docx") =>
  `${baseUrl()}/compendia/${encodeURIComponent(compendiumId)}/download/${artifactType}`;

export async function downloadThemePackGuide(projectId: string): Promise<void> {
  const response = await fetch(`${baseUrl()}/theme-packs/${encodeURIComponent(projectId)}/teacher-guide`);
  if (!response.ok) throw new Error(`Kunne ikke laste ned lærerveiledningen (${response.status}).`);
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "temapakke-laererveiledning.md";
  anchor.click();
  URL.revokeObjectURL(url);
}

export function projectTasks(project: Project): ThemePackTask[] {
  const tasks = project.metadata?.tasks;
  return Array.isArray(tasks) ? (tasks as ThemePackTask[]) : [];
}

export function formatProjectDate(value: string): string {
  return new Intl.DateTimeFormat("nb-NO", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}
