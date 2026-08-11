import type { MaterialKind, YearPlan, YearPlanPeriod } from "@/lib/platform-api";

export const MATEMATEX_YEAR_PLAN_LEVELS = [
  { value: "1.-4. trinn", label: "1.–4. trinn" },
  { value: "5.-7. trinn", label: "5.–7. trinn" },
  { value: "8. trinn", label: "8. trinn" },
  { value: "9. trinn", label: "9. trinn" },
  { value: "10. trinn", label: "10. trinn" },
  { value: "VG1 1T", label: "VG1 1T" },
  { value: "VG1 1P", label: "VG1 1P" },
  { value: "VG2 2P", label: "VG2 2P" },
  { value: "VG2 R1", label: "VG2 R1" },
  { value: "VG3 R2", label: "VG3 R2" },
] as const;

const supportedLevels = new Set<string>(MATEMATEX_YEAR_PLAN_LEVELS.map((item) => item.value));

const legacyLevelMap: Record<string, string> = {
  VG1: "VG1 1T",
  VG2: "VG2 R1",
  VG3: "VG3 R2",
};

const materialTypeMap: Partial<Record<MaterialKind, string>> = {
  learning_sheet: "kapittel",
  worksheet: "arbeidsark",
  exercise_sheet: "arbeidsark",
  assessment: "prøve",
  lesson_sequence: "hefte",
  differentiated: "differensiert",
};

const allowedContextKinds = new Set<MaterialKind>(Object.keys(materialTypeMap) as MaterialKind[]);

export interface MathematicsYearPlanContext {
  planId: string;
  periodId: string;
  materialKind: MaterialKind;
  topic: string;
}

export interface MathematicsYearPlanPrefill extends MathematicsYearPlanContext {
  grade: string;
  materialType: string;
  competencyGoals: string[];
  extraInstructions: string;
}

export interface MathematicsMaterialPreset {
  includeTheory: boolean;
  includeExamples: boolean;
  includeExercises: boolean;
  includeSolutions: boolean;
}

export const MATEMATEX_SETTINGS_STEP = 2;

export function isMathematicsSubject(subject: string): boolean {
  return subject.trim().toLocaleLowerCase("nb-NO") === "matematikk";
}

export function mathematicsGradeForLevel(level: string): string {
  const normalized = level.trim();
  if (supportedLevels.has(normalized)) return normalized;
  return legacyLevelMap[normalized.toUpperCase()] || "VG1 1T";
}

export function mathematicsMaterialType(kind: MaterialKind): string {
  return materialTypeMap[kind] || "arbeidsark";
}

export function mathematicsMaterialPreset(kind: MaterialKind): MathematicsMaterialPreset {
  if (kind === "worksheet" || kind === "exercise_sheet" || kind === "assessment") {
    return {
      includeTheory: false,
      includeExamples: false,
      includeExercises: true,
      includeSolutions: true,
    };
  }
  return {
    includeTheory: true,
    includeExamples: true,
    includeExercises: true,
    includeSolutions: true,
  };
}

function periodInstructions(plan: YearPlan, period: YearPlanPeriod): string {
  return [
    `Årsplan: ${plan.title}`,
    `Fag og nivå: ${plan.subject}, ${plan.level}`,
    `Periode: ${period.title} (${period.duration_weeks} uker, ${period.lesson_count} undervisningstimer)`,
    period.overview,
    period.learning_goals.length ? `Læringsmål: ${period.learning_goals.join("; ")}` : "",
    period.key_concepts.length ? `Sentrale begreper: ${period.key_concepts.join(", ")}` : "",
    period.suggested_activities.length ? `Foreslåtte aktiviteter: ${period.suggested_activities.join("; ")}` : "",
    period.assessment ? `Vurdering: ${period.assessment}` : "",
    period.teacher_notes ? `Lærerens notater: ${period.teacher_notes}` : "",
  ].filter(Boolean).join("\n");
}

export function mathematicsGenerationHref(
  plan: YearPlan,
  period: YearPlanPeriod,
  kind: MaterialKind,
): string {
  const topic = period.theme || period.title;
  const query = new URLSearchParams({
    topic,
    grade: mathematicsGradeForLevel(plan.level),
    materialType: mathematicsMaterialType(kind),
    yearPlan: plan.id,
    period: period.id,
    materialKind: kind,
    competencyGoals: JSON.stringify(period.competency_goals),
    extraInstructions: periodInstructions(plan, period),
  });
  return `/matematikk?${query.toString()}`;
}

export function readMathematicsYearPlanContext(
  params: URLSearchParams,
): MathematicsYearPlanContext | null {
  const planId = params.get("yearPlan")?.trim() || "";
  const periodId = params.get("period")?.trim() || "";
  const materialKind = (params.get("materialKind")?.trim() || "") as MaterialKind;
  const topic = params.get("topic")?.trim() || "";
  if (!planId || !periodId || !topic || !allowedContextKinds.has(materialKind)) return null;
  return { planId, periodId, materialKind, topic };
}

export function readCompetencyGoals(params: URLSearchParams): string[] {
  const raw = params.get("competencyGoals");
  if (!raw) return [];
  try {
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed)
      ? parsed.filter((goal): goal is string => typeof goal === "string" && Boolean(goal.trim()))
      : [];
  } catch {
    return [];
  }
}

export function readMathematicsYearPlanPrefill(
  params: URLSearchParams,
): MathematicsYearPlanPrefill | null {
  const context = readMathematicsYearPlanContext(params);
  const grade = params.get("grade")?.trim() || "";
  if (!context || !supportedLevels.has(grade)) return null;
  return {
    ...context,
    grade,
    materialType: mathematicsMaterialType(context.materialKind),
    competencyGoals: readCompetencyGoals(params),
    extraInstructions: params.get("extraInstructions")?.trim() || "",
  };
}
