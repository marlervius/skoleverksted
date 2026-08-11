import { describe, expect, it } from "vitest";
import type { MaterialKind, YearPlan, YearPlanPeriod } from "@/lib/platform-api";
import {
  isMathematicsSubject,
  mathematicsGenerationHref,
  mathematicsGradeForLevel,
  mathematicsMaterialPreset,
  mathematicsMaterialType,
  MATEMATEX_SETTINGS_STEP,
  readCompetencyGoals,
  readMathematicsYearPlanContext,
  readMathematicsYearPlanPrefill,
} from "./mathematics-year-plan";

const period: YearPlanPeriod = {
  id: "period-2",
  order: 2,
  title: "Andre periode",
  theme: "Derivasjon",
  week_start: "2026-W40",
  week_end: "2026-W43",
  duration_weeks: 4,
  lesson_count: 12,
  overview: "Elevene utforsker endringsrate.",
  learning_goals: ["Derivere polynomer"],
  competency_goals: ["utforske og forstå derivasjon"],
  key_concepts: ["stigningstall", "grenseverdi"],
  suggested_activities: ["Arbeid i par"],
  assessment: "Kort prøve",
  teacher_notes: "",
  status: "not_started",
  materials: [],
};

const plan: YearPlan = {
  id: "plan-1",
  title: "Matematikk VG2",
  subject: "Matematikk",
  level: "VG2",
  school_year: "2026-2027",
  lessons_per_week: 4,
  lesson_minutes: 45,
  teaching_weeks: 38,
  competency_goals: period.competency_goals,
  periods: [period],
  notes: "",
  planning_source: "manual",
  status: "draft",
  created_at: "2026-08-10T00:00:00Z",
  updated_at: "2026-08-10T00:00:00Z",
};

describe("mathematics year-plan integration", () => {
  it("recognizes mathematics without changing the generic subject module", () => {
    expect(isMathematicsSubject(" Matematikk ")).toBe(true);
    expect(isMathematicsSubject("Historie")).toBe(false);
  });

  it("keeps exact MateMaTeX levels and migrates legacy annual-plan levels", () => {
    expect(mathematicsGradeForLevel("VG1 1P")).toBe("VG1 1P");
    expect(mathematicsGradeForLevel("VG2")).toBe("VG2 R1");
    expect(mathematicsGradeForLevel("VG3")).toBe("VG3 R2");
  });

  it.each<[MaterialKind, string]>([
    ["learning_sheet", "kapittel"],
    ["worksheet", "arbeidsark"],
    ["assessment", "prøve"],
    ["lesson_sequence", "hefte"],
  ])("maps %s to MateMaTeX material type %s", (kind, expected) => {
    expect(mathematicsMaterialType(kind)).toBe(expected);
  });

  it("routes a mathematics period to MateMaTeX with full planning context", () => {
    const href = mathematicsGenerationHref(plan, period, "assessment");
    expect(href.startsWith("/matematikk?")).toBe(true);
    expect(href).not.toContain("/fag?");

    const params = new URLSearchParams(href.split("?")[1]);
    expect(params.get("grade")).toBe("VG2 R1");
    expect(params.get("materialType")).toBe("prøve");
    expect(params.get("yearPlan")).toBe("plan-1");
    expect(params.get("period")).toBe("period-2");
    expect(readCompetencyGoals(params)).toEqual(period.competency_goals);
    expect(params.get("extraInstructions")).toContain("Derivere polynomer");
    expect(params.get("extraInstructions")).toContain("Matematikk VG2");
    expect(params.get("extraInstructions")).toContain("4 uker, 12 undervisningstimer");
    expect(readMathematicsYearPlanContext(params)).toEqual({
      planId: "plan-1",
      periodId: "period-2",
      materialKind: "assessment",
      topic: "Derivasjon",
    });
    expect(readMathematicsYearPlanPrefill(params)).toEqual({
      planId: "plan-1",
      periodId: "period-2",
      materialKind: "assessment",
      topic: "Derivasjon",
      grade: "VG2 R1",
      materialType: "prøve",
      competencyGoals: period.competency_goals,
      extraInstructions: params.get("extraInstructions"),
    });
  });

  it("opens a complete annual-plan handoff on the settings step with authoritative content choices", () => {
    const params = new URLSearchParams(
      mathematicsGenerationHref(plan, period, "learning_sheet").split("?")[1],
    );
    const prefill = readMathematicsYearPlanPrefill(params);

    expect(MATEMATEX_SETTINGS_STEP).toBe(2);
    expect(prefill?.grade).toBe("VG2 R1");
    expect(prefill?.topic).toBe("Derivasjon");
    expect(prefill?.materialType).toBe("kapittel");
    expect(prefill?.competencyGoals).toEqual(period.competency_goals);
    expect(mathematicsMaterialPreset("learning_sheet")).toEqual({
      includeTheory: true,
      includeExamples: true,
      includeExercises: true,
      includeSolutions: true,
    });
  });

  it("does not offer save-back for an incomplete or unknown context", () => {
    expect(readMathematicsYearPlanContext(new URLSearchParams("yearPlan=plan-1"))).toBeNull();
    expect(readMathematicsYearPlanContext(new URLSearchParams(
      "yearPlan=plan-1&period=period-2&topic=Test&materialKind=other",
    ))).toBeNull();
    expect(readMathematicsYearPlanPrefill(new URLSearchParams(
      "yearPlan=plan-1&period=period-2&topic=Test&materialKind=assessment&grade=ukjent",
    ))).toBeNull();
    expect(readCompetencyGoals(new URLSearchParams("competencyGoals=not-json"))).toEqual([]);
  });
});
