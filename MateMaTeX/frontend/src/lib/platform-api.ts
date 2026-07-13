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
  created_at: string;
  updated_at: string;
}

const baseUrl = () => `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/platform`;

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
export const createThemePack = (input: ThemePackInput) =>
  requestJson<ThemePack>("/theme-packs", { method: "POST", body: JSON.stringify(input) });

export function projectTasks(project: Project): ThemePackTask[] {
  const tasks = project.metadata?.tasks;
  return Array.isArray(tasks) ? (tasks as ThemePackTask[]) : [];
}

export function formatProjectDate(value: string): string {
  return new Intl.DateTimeFormat("nb-NO", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}
