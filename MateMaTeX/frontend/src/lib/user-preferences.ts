/**
 * User preferences persisted in localStorage (grade, language level, material type).
 */

export interface UserPreferences {
  grade: string;
  languageLevel: string;
  materialType: string;
}

const STORAGE_KEY = "matematex-preferences";

export const DEFAULT_PREFERENCES: UserPreferences = {
  grade: "10. trinn",
  languageLevel: "standard",
  materialType: "arbeidsark",
};

export function loadPreferences(): UserPreferences {
  if (typeof window === "undefined") {
    return { ...DEFAULT_PREFERENCES };
  }
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...DEFAULT_PREFERENCES };
    const parsed = JSON.parse(raw) as Partial<UserPreferences>;
    return { ...DEFAULT_PREFERENCES, ...parsed };
  } catch {
    return { ...DEFAULT_PREFERENCES };
  }
}

export function savePreferences(partial: Partial<UserPreferences>): UserPreferences {
  const next = { ...loadPreferences(), ...partial };
  if (typeof window !== "undefined") {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  }
  return next;
}

export function materialTypeFromTemplate(templateId: string): string {
  switch (templateId) {
    case "chapter":
      return "kapittel";
    case "exam":
      return "prøve";
    case "worksheet":
    default:
      return "arbeidsark";
  }
}
