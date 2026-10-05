import type { TruthPassport } from "@/lib/platform-api";

export type Status = "idle" | "loading" | "success" | "error" | "needs_teacher_review";

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

export interface CommonsImageCandidate {
  image_url: string;
  thumbnail_url: string;
  source_page_url: string;
  title: string;
  description?: string;
  creator?: string;
  license: string;
  credit: string;
  caption?: string;
  alt_text?: string;
  rationale?: string;
  recommended: boolean;
  review_status: "recommended" | "teacher_review";
}

export interface ReadabilityIssue {
  code: string;
  sentence: string;
  words: number;
  limit: number;
  message: string;
}

/** Advisory CEFR readability report for the running text (never a release gate). */
export interface ReadabilityReport {
  level: string;
  base_level: string;
  applicable: boolean;
  sentence_count: number;
  word_count: number;
  average_sentence_words: number;
  longest_sentence_words: number;
  limit_words: number | null;
  issue_count: number;
  issues: ReadabilityIssue[];
  truncated: number;
  status: "ok" | "needs_attention" | "not_applicable";
  summary: string;
  auto_simplified?: boolean;
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
  image_candidates?: CommonsImageCandidate[];
  language_exercises?: LanguageExercisesPayload | null;
  truth_passport?: TruthPassport | null;
  quarantine?: Array<Record<string, unknown>>;
  quality_rounds?: Array<Record<string, unknown>>;
  quality_stop_reason?: string;
  readability?: ReadabilityReport | null;
}
