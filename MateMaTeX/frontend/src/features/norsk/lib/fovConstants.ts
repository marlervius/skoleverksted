import type { AccessibilityState, OptionsState } from "./fovTypes";

export const SUBJECTS = [
  { value: "Norsk", label: "Norsk", icon: "📝" },
  { value: "Engelsk", label: "Engelsk", icon: "🇬🇧" },
  { value: "Samfunnsfag", label: "Samfunnsfag", icon: "🏛️" },
  { value: "Naturfag", label: "Naturfag", icon: "🔬" },
  { value: "Matematikk", label: "Matematikk med norskstøtte", icon: "📐" },
  { value: "Utdanningsvalg", label: "Utdanningsvalg", icon: "🎓" },
] as const;

export const LEVELS = [
  { value: "A1.1", label: "A1.1 - Nybegynner tidlig", description: "Svært grunnleggende" },
  { value: "A1.2", label: "A1.2 - Nybegynner sent", description: "Grunnleggende med progresjon" },
  { value: "A2.1", label: "A2.1 - Elementært tidlig", description: "Enkelt språk - basis" },
  { value: "A2.2", label: "A2.2 - Elementært sent", description: "Enkelt språk - avansert" },
  { value: "B1.1", label: "B1.1 - Mellom tidlig", description: "Selvstendig - basis" },
  { value: "B1.2", label: "B1.2 - Mellom sent", description: "Selvstendig - avansert" },
  { value: "B2.1", label: "B2.1 - Øvre mellom tidlig", description: "Avansert - basis" },
  { value: "B2.2", label: "B2.2 - Øvre mellom sent", description: "Avansert - flytende" },
] as const;

/** Stable CEFR order for multi-level ZIP / API payloads. */
export function sortLevelsByCefr(levels: string[]): string[] {
  const order: string[] = LEVELS.map((l) => l.value);
  return [...levels].sort((a, b) => order.indexOf(a) - order.indexOf(b));
}

export const HISTORY_KEY = "fov_history";
export const MAX_HISTORY = 20;
/** sessionStorage key for app password (Bearer token). */
export const APP_PASSWORD_STORAGE_KEY = "fov_app_password";

export const DEFAULT_OPTIONS: OptionsState = {
  deep_dive: false,
  comprehension_tasks: true,
  grammar_tasks: true,
  vocabulary_tasks: true,
  discussion_tasks: true,
  teacher_key: false,
  role_play: false,
  image_description: false,
  writing_frame: false,
  cultural_comparison: false,
  real_case: false,
};

export const DEFAULT_ACCESSIBILITY: AccessibilityState = {
  dyslexia_font: false,
  high_contrast: false,
  large_print: false,
};
