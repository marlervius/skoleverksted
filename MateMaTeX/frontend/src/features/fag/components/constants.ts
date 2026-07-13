export const SUBJECTS = [
  { value: "Norsk", label: "Norsk", icon: "📝" },
  { value: "Engelsk", label: "Engelsk", icon: "🇬🇧" },
  { value: "Samfunnsfag", label: "Samfunnsfag", icon: "🏛️" },
  { value: "Naturfag", label: "Naturfag", icon: "🔬" },
  { value: "Matematikk", label: "Matematikk", icon: "📐" },
  { value: "Historie", label: "Historie", icon: "📜" },
  { value: "Geografi", label: "Geografi", icon: "🌍" },
  { value: "Religion", label: "Religion og etikk", icon: "⚖️" },
  { value: "Kroppsøving", label: "Kroppsøving", icon: "🏃" },
];

export const LEVELS = [
  { value: "VG1", label: "VG1", description: "Første året" },
  { value: "VG2", label: "VG2", description: "Andre året" },
  { value: "VG3", label: "VG3", description: "Tredje året" },
  { value: "Yrkesfag", label: "Yrkesfag", description: "Praktiske fag" },
];

export const LANGUAGE_LEVELS = [
  { value: "none", label: "Standard norsk", description: "Ingen tilpasning" },
  { value: "B2", label: "B2 - Øvre mellomnivå", description: "Noe forenklet" },
  { value: "B1", label: "B1 - Mellomnivå", description: "Forenklet språk" },
];

export type Status = "idle" | "loading" | "success" | "error";

export type AppMode = "laeringsark" | "differensiert" | "prove" | "sekvens";

export type LessonOptions = {
  deep_dive: boolean;
  lang_tekst: boolean;
  comprehension_tasks: boolean;
  grammar_tasks: boolean;
  vocabulary_tasks: boolean;
  discussion_tasks: boolean;
  teacher_key: boolean;
  role_play: boolean;
  image_description: boolean;
  writing_frame: boolean;
  cultural_comparison: boolean;
  real_case: boolean;
  faktarapport: boolean;
  differensiering: boolean;
  korrektur: boolean;
  revision: boolean;
  reading_friendly: boolean;
};

export const DEFAULT_OPTIONS: LessonOptions = {
  deep_dive: false,
  lang_tekst: false,
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
  faktarapport: true,
  differensiering: false,
  korrektur: true,
  revision: true,
  reading_friendly: false,
};

/** A saved student group profile for one-click adapted generation. */
export interface StudentProfile {
  id: string;
  label: string;
  languageLevel: string; // "none" | "B1" | "B2"
  readingFriendly: boolean;
  interest: string;
}

export const PROFILES_STORAGE_KEY = "vgs-ki-profiles";

export const APP_MODES: { value: AppMode; label: string; icon: string; description: string }[] = [
  {
    value: "laeringsark",
    label: "Læringsark",
    icon: "📄",
    description: "Fagtekst med oppgaver",
  },
  {
    value: "differensiert",
    label: "Differensiert",
    icon: "🎯",
    description: "Støtte · Standard · Fordypning",
  },
  {
    value: "prove",
    label: "Prøve",
    icon: "✍️",
    description: "Del A · B · C med fasit",
  },
  {
    value: "sekvens",
    label: "Sekvens",
    icon: "📅",
    description: "Ukesplan · læringsløp",
  },
];
