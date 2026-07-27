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
export type CompendiumChapterStatus = "planned" | "generated" | "approved" | "needs_revision";
export type CompendiumImageMode = "none" | "commons" | "ai";

export interface CompendiumSource {
  title: string;
  url: string;
  publisher: string;
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

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${baseUrl()}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(typeof body.detail === "string" ? body.detail : `Plattformfeil (${response.status})`);
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
