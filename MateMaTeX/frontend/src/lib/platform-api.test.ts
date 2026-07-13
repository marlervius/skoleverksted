import { describe, expect, it } from "vitest";
import { projectTasks, type Project } from "./platform-api";

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
