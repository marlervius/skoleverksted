export type Status = "idle" | "loading" | "success" | "error";

export interface OptionsState {
  deep_dive: boolean;
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
}

export interface AccessibilityState {
  dyslexia_font: boolean;
  high_contrast: boolean;
  large_print: boolean;
}

export interface SeriesState {
  lesson_number: number;
  total_lessons: number;
  series_theme: string;
}

export interface HistoryItem {
  id: string;
  topic: string;
  subject: string;
  level: string;
  /** When set (length ≥ 2), user generated a multi-level ZIP for these CEFR levels. */
  multiLevels?: string[] | null;
  timestamp: number;
  options: OptionsState;
  difficultyModifier: number | null;
  specialInstructions: string;
  series: SeriesState | null;
  accessibility: AccessibilityState;
}

/** CLIL / language exercise blocks from the API (preview + PDF). */
export interface LanguageExercisesPayload {
  grammar_tasks?: Array<Record<string, unknown>>;
  vocabulary_tasks?: Array<Record<string, unknown>>;
  syntax_tasks?: Array<Record<string, unknown>>;
}

/** JSON lesson payload from /download-json (matches backend LessonResponse). */
export interface LessonResponse {
  topic: string;
  subject: string;
  level: string;
  text: string;
  worksheet: string;
  image_url?: string | null;
  image_mode?: "none" | "commons" | "ai";
  image_caption?: string;
  image_credit?: string;
  image_source_page?: string | null;
  language_exercises?: LanguageExercisesPayload | null;
}
