import { afterEach, describe, expect, it, vi } from "vitest";
import {
  awaitRepairJob,
  deleteYearPlan,
  generateYearPlan,
  getChapterRepairJob,
  getPlatformJob,
  isActiveRepairStatus,
  isTerminalRepairStatus,
  projectTasks,
  repairCompendiumChapter,
  repairStatusView,
  type Project,
  type RepairJob,
  type RepairJobStatus,
} from "./platform-api";

const project: Project = {
  id: "p1",
  title: "Klima",
  theme: "Bærekraft",
  subject: "Naturfag",
  level: "VG1",
  description: "",
  competency_goals: [],
  status: "ready",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
  metadata: {
    tasks: [{ id: "t1", module: "fag", title: "Fagtekst", brief: "Lag tekst", href: "/fag", status: "ready" }],
  },
};

describe("projectTasks", () => {
  it("reads typed theme-pack tasks from project metadata", () => {
    expect(projectTasks(project)).toHaveLength(1);
    expect(projectTasks(project)[0].module).toBe("fag");
  });

  it("returns an empty list for ordinary projects", () => {
    expect(projectTasks({ ...project, metadata: {} })).toEqual([]);
  });
});

function repairJob(overrides: Partial<RepairJob> = {}): RepairJob {
  return {
    id: "job-1",
    operation_id: "op-1",
    compendium_id: "c1",
    chapter_id: "ch1",
    chapter_title: "Aktører",
    status: "queued",
    message: "",
    chapter_token: "aaa",
    result_token: "",
    source_revision: "rev-1",
    output_revision: "",
    chapter_status: null,
    repair_summary: null,
    failure_reason: "",
    attempt: 1,
    cancel_requested: false,
    lease_expires_at: "",
    created_at: "2026-08-08T10:00:00Z",
    updated_at: "2026-08-08T10:00:00Z",
    started_at: "",
    finished_at: "",
    ...overrides,
  };
}

function jsonResponse(body: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: { get: () => null },
    json: async () => body,
  } as unknown as Response;
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("repair job status", () => {
  it("treats only queued and running as active", () => {
    expect(isActiveRepairStatus("queued")).toBe(true);
    expect(isActiveRepairStatus("running")).toBe(true);
    const terminal: RepairJobStatus[] = [
      "succeeded",
      "failed_retryable",
      "failed_terminal",
      "cancelled",
      "superseded",
    ];
    expect(terminal.every(isTerminalRepairStatus)).toBe(true);
  });

  it("tells the teacher the page may be left while work continues", () => {
    const view = repairStatusView(repairJob({ status: "running" }));
    expect(view.tone).toBe("busy");
    expect(view.detail).toContain("forlate siden");
    expect(view.canRetry).toBe(false);
  });

  it("names the concrete repair stages instead of showing only a spinner", () => {
    expect(repairStatusView(repairJob({ status: "queued" })).label).toBe("Sjekker fakta og kilder");
    expect(repairStatusView(repairJob({ status: "running" })).label).toContain("plan");
    expect(repairStatusView(repairJob({ status: "succeeded" })).label).toContain("revisjon");
  });

  it("explains that a superseded repair preserved the newer teacher edit", () => {
    const view = repairStatusView(repairJob({ status: "superseded" }));
    expect(view.detail).toContain("nyere teksten din er bevart");
    expect(view.canRetry).toBe(true);
  });

  it("offers a concrete retry only for recoverable failures", () => {
    expect(repairStatusView(repairJob({ status: "failed_retryable" })).canRetry).toBe(true);
    expect(repairStatusView(repairJob({ status: "failed_terminal" })).canRetry).toBe(false);
    expect(repairStatusView(repairJob({ status: "succeeded" })).canRetry).toBe(false);
  });

  it("does not describe a zero-change result as a completed repair", () => {
    const view = repairStatusView(repairJob({
      status: "succeeded",
      repair_summary: {
        before: { verified_claims: 1, total_claims: 2, coverage: 50, unresolved: 1, source_grounding_failures: 1, language_failures: 0 },
        after: { verified_claims: 1, total_claims: 2, coverage: 50, unresolved: 1, source_grounding_failures: 1, language_failures: 0 },
        changes: [],
        found_count: 1,
        repaired_count: 0,
        qualified_count: 0,
        replaced_count: 0,
        removed_count: 0,
        unresolved_count: 1,
        manual_review_count: 0,
        pass_count: 1,
        stop_reason: "no-safe-repair",
      },
    }));
    expect(view.label).toContain("ingen sikre rettelser");
    expect(view.tone).toBe("warn");
  });
});

describe("repair job client", () => {
  it("starts a repair without waiting for the model and keeps the job id", async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse({
        job_id: "job-42",
        operation_id: "op-42",
        compendium_id: "c1",
        chapter_id: "ch1",
        status: "queued",
        status_url: "/api/platform/repair-jobs/job-42",
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const accepted = await repairCompendiumChapter("c1", "ch1", "op-42");

    expect(accepted.job_id).toBe("job-42");
    expect(accepted.status).toBe("queued");
    const [, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(init.method).toBe("POST");
    expect((init.headers as Record<string, string>)["x-operation-id"]).toBe("op-42");
  });

  it("reports no repair rather than an error when a chapter never had one", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse({ detail: "Ingen reparasjon" }, 404)));
    await expect(getChapterRepairJob("c1", "ch1")).resolves.toBeNull();
  });

  it("polls a repair to its terminal status", async () => {
    const responses = [
      repairJob({ status: "queued" }),
      repairJob({ status: "running" }),
      repairJob({ status: "succeeded", chapter_status: "generated" }),
    ];
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse(responses.shift())));
    const seen: RepairJobStatus[] = [];

    const finished = await awaitRepairJob("job-1", {
      intervalMs: 0,
      onUpdate: (job) => seen.push(job.status),
    });

    expect(seen).toEqual(["queued", "running", "succeeded"]);
    expect(finished.status).toBe("succeeded");
  });
});

describe("year plan client", () => {
  it("deletes the selected year plan with an encoded id", async () => {
    const fetchMock = vi.fn(async () => jsonResponse({ deleted: true, id: "plan/1" }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(deleteYearPlan("plan/1")).resolves.toEqual({ deleted: true, id: "plan/1" });

    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toContain("/year-plans/plan%2F1");
    expect(init.method).toBe("DELETE");
  });

  it("registers generation with a stable operation id", async () => {
    const fetchMock = vi.fn(async () => jsonResponse({
      job_id: "year-plan:abc",
      status: "queued",
      status_url: "/api/platform/jobs/year-plan%3Aabc",
      plan_id: null,
    }, 202));
    vi.stubGlobal("fetch", fetchMock);

    const accepted = await generateYearPlan({
      subject: "Matematikk",
      level: "FOV modul 4",
      school_year: "2026-2027",
      lessons_per_week: 4,
      lesson_minutes: 45,
      teaching_weeks: 38,
      number_of_periods: 9,
      competency_goals: [],
      constraints: "",
      use_ai: true,
    }, "operation-42");

    expect(accepted.job_id).toBe("year-plan:abc");
    const [, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(init.method).toBe("POST");
    expect((init.headers as Record<string, string>)["x-operation-id"]).toBe("operation-42");
  });

  it("reads progress through the small job-status endpoint", async () => {
    const fetchMock = vi.fn(async () => jsonResponse({
      id: "year-plan:abc",
      module: "platform",
      kind: "year_plan_generation",
      status: "verifying",
      progress: 50,
      message: "Kontrollerer fakta",
      project_id: null,
      request_summary: {},
      result_summary: {},
      quality_passport: {},
      queue_position: null,
      retryable: true,
      attempt: 1,
      created_at: "2026-08-11T00:00:00Z",
      updated_at: "2026-08-11T00:00:01Z",
    }));
    vi.stubGlobal("fetch", fetchMock);

    const job = await getPlatformJob("year-plan:abc");

    expect(job.status).toBe("verifying");
    const [url] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(String(url)).toContain("year-plan%3Aabc");
  });
});
