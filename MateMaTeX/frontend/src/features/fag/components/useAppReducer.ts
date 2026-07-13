import type { Status, LessonOptions, AppMode, StudentProfile } from "./constants";
import { DEFAULT_OPTIONS } from "./constants";
import type { CompetencyGoal, ImageCandidate } from "./api";

/** Result of one profile's generation in a batch run. */
export interface ProfileResult {
  profileId: string;
  label: string;
  status: "pending" | "loading" | "done" | "error";
  url?: string;
  blob?: Blob;
  filename?: string;
  errorMessage?: string;
}

export interface AppState {
  // Form
  mode: AppMode;
  subject: string;
  level: string;
  languageLevel: string;
  topic: string;
  options: LessonOptions;
  imageFile: File | null;
  description: string;
  showDescriptionTips: boolean;
  sourceText: string;
  showSourceText: boolean;
  useNdla: boolean;
  interest: string;
  profiles: StudentProfile[];
  profileResults: ProfileResult[];
  batchRunning: boolean;
  selectedGoal: CompetencyGoal | null;
  includeFasit: boolean;
  antallUker: number;
  timerPerUke: number;
  // Generation
  status: Status;
  errorMessage: string;
  elapsedSeconds: number;
  progressMessage: string;
  // Result
  previewUrl: string | null;
  previewBlob: Blob | null;
  previewFilename: string;
  rapportBlob: Blob | null;
  rapportFilename: string;
  showPreview: boolean;
  basisText: string | null;
  generatedImageUrl: string | null;
  worksheetText: string | null;
  faktarapportText: string | null;
  languageExercises: Record<string, unknown> | null;
  warnings: string[];
  sourceGrounded: boolean | null;
  sourceName: string | null;
  showEditPanel: boolean;
  imageCandidates: ImageCandidate[];
  imageCandidatesLoading: boolean;
}

export const initialState: AppState = {
  mode: "laeringsark",
  subject: "",
  level: "VG1",
  languageLevel: "none",
  topic: "",
  options: { ...DEFAULT_OPTIONS },
  imageFile: null,
  description: "",
  showDescriptionTips: false,
  sourceText: "",
  showSourceText: false,
  useNdla: true,
  interest: "",
  profiles: [],
  profileResults: [],
  batchRunning: false,
  selectedGoal: null,
  includeFasit: false,
  antallUker: 3,
  timerPerUke: 2,
  status: "idle",
  errorMessage: "",
  elapsedSeconds: 0,
  progressMessage: "",
  previewUrl: null,
  previewBlob: null,
  previewFilename: "dokument.pdf",
  rapportBlob: null,
  rapportFilename: "faktarapport.pdf",
  showPreview: false,
  basisText: null,
  generatedImageUrl: null,
  worksheetText: null,
  faktarapportText: null,
  languageExercises: null,
  warnings: [],
  sourceGrounded: null,
  sourceName: null,
  showEditPanel: false,
  imageCandidates: [],
  imageCandidatesLoading: false,
};

export type AppAction =
  | { type: "SET_MODE"; mode: AppMode }
  | { type: "SET_SUBJECT"; subject: string }
  | { type: "SET_LEVEL"; level: string }
  | { type: "SET_LANGUAGE_LEVEL"; languageLevel: string }
  | { type: "SET_TOPIC"; topic: string }
  | { type: "SET_OPTION"; key: keyof LessonOptions; val: boolean }
  | { type: "SET_TEXT_LENGTH"; length: "kort" | "standard" | "lang" }
  | { type: "SET_IMAGE_FILE"; file: File | null }
  | { type: "SET_DESCRIPTION"; description: string }
  | { type: "TOGGLE_DESCRIPTION_TIPS" }
  | { type: "SET_SOURCE_TEXT"; sourceText: string }
  | { type: "TOGGLE_SOURCE_TEXT" }
  | { type: "SET_USE_NDLA"; val: boolean }
  | { type: "SET_INTEREST"; interest: string }
  | { type: "SET_PROFILES"; profiles: StudentProfile[] }
  | { type: "BATCH_START"; results: ProfileResult[] }
  | { type: "BATCH_ITEM_START"; profileId: string }
  | { type: "BATCH_ITEM_SUCCESS"; profileId: string; blob: Blob; url: string; filename: string }
  | { type: "BATCH_ITEM_ERROR"; profileId: string; message: string }
  | { type: "BATCH_DONE" }
  | { type: "SET_GOAL"; goal: CompetencyGoal | null }
  | { type: "SET_INCLUDE_FASIT"; val: boolean }
  | { type: "SET_ANTALL_UKER"; n: number }
  | { type: "SET_TIMER_PER_UKE"; n: number }
  | { type: "GENERATION_START" }
  | { type: "GENERATION_PROGRESS"; message: string }
  | { type: "GENERATION_SUCCESS"; blob: Blob; url: string; filename: string; basisText?: string; imageUrl?: string; worksheetText?: string; faktarapportText?: string; languageExercises?: Record<string, unknown>; warnings?: string[]; sourceGrounded?: boolean; sourceName?: string; rapportBlob?: Blob; rapportFilename?: string }
  | { type: "SET_BASIS_TEXT"; text: string }
  | { type: "SET_WORKSHEET_TEXT"; text: string }
  | { type: "TOGGLE_EDIT_PANEL" }
  | { type: "IMAGE_CANDIDATES_LOADING" }
  | { type: "IMAGE_CANDIDATES_LOADED"; candidates: ImageCandidate[] }
  | { type: "GENERATION_ERROR"; message: string }
  | { type: "GENERATION_CANCEL" }
  | { type: "GENERATION_IDLE" }
  | { type: "SHOW_PREVIEW" }
  | { type: "CLOSE_PREVIEW" }
  | { type: "TICK_TIMER" }
  | { type: "RESTORE_SESSION"; topic: string; subject: string; level: string; mode: AppMode; basisText: string; worksheetText: string; faktarapportText: string | null; imageUrl: string | null; languageExercises?: Record<string, unknown> | null; interest?: string };

export function appReducer(state: AppState, action: AppAction): AppState {
  switch (action.type) {
    case "SET_MODE":
      return { ...state, mode: action.mode, selectedGoal: null, status: "idle", progressMessage: "" };
    case "SET_SUBJECT":
      return { ...state, subject: action.subject, selectedGoal: null };
    case "SET_LEVEL":
      return { ...state, level: action.level };
    case "SET_LANGUAGE_LEVEL":
      return { ...state, languageLevel: action.languageLevel };
    case "SET_TOPIC":
      return { ...state, topic: action.topic };
    case "SET_OPTION":
      return { ...state, options: { ...state.options, [action.key]: action.val } };
    case "SET_TEXT_LENGTH":
      return {
        ...state,
        options: {
          ...state.options,
          deep_dive: action.length === "standard",
          lang_tekst: action.length === "lang",
        },
      };
    case "SET_IMAGE_FILE":
      return { ...state, imageFile: action.file };
    case "SET_DESCRIPTION":
      return { ...state, description: action.description };
    case "TOGGLE_DESCRIPTION_TIPS":
      return { ...state, showDescriptionTips: !state.showDescriptionTips };
    case "SET_SOURCE_TEXT":
      return { ...state, sourceText: action.sourceText };
    case "TOGGLE_SOURCE_TEXT":
      return { ...state, showSourceText: !state.showSourceText };
    case "SET_USE_NDLA":
      return { ...state, useNdla: action.val };
    case "SET_INTEREST":
      return { ...state, interest: action.interest };
    case "SET_PROFILES":
      return { ...state, profiles: action.profiles };
    case "BATCH_START":
      return { ...state, profileResults: action.results, batchRunning: true };
    case "BATCH_ITEM_START":
      return {
        ...state,
        profileResults: state.profileResults.map((r) =>
          r.profileId === action.profileId ? { ...r, status: "loading" } : r
        ),
      };
    case "BATCH_ITEM_SUCCESS":
      return {
        ...state,
        profileResults: state.profileResults.map((r) =>
          r.profileId === action.profileId
            ? { ...r, status: "done", blob: action.blob, url: action.url, filename: action.filename }
            : r
        ),
      };
    case "BATCH_ITEM_ERROR":
      return {
        ...state,
        profileResults: state.profileResults.map((r) =>
          r.profileId === action.profileId
            ? { ...r, status: "error", errorMessage: action.message }
            : r
        ),
      };
    case "BATCH_DONE":
      return { ...state, batchRunning: false, status: "idle", progressMessage: "" };
    case "SET_GOAL":
      return { ...state, selectedGoal: action.goal };
    case "SET_INCLUDE_FASIT":
      return { ...state, includeFasit: action.val };
    case "SET_ANTALL_UKER":
      return { ...state, antallUker: action.n };
    case "SET_TIMER_PER_UKE":
      return { ...state, timerPerUke: action.n };
    case "GENERATION_START":
      return {
        ...state,
        status: "loading",
        errorMessage: "",
        progressMessage: "",
        elapsedSeconds: 0,
        showPreview: false,
        previewUrl: null,
        previewBlob: null,
        rapportBlob: null,
      };
    case "GENERATION_PROGRESS":
      return { ...state, progressMessage: action.message };
    case "GENERATION_SUCCESS":
      return {
        ...state,
        status: "success",
        previewBlob: action.blob,
        previewUrl: action.url,
        previewFilename: action.filename,
        rapportBlob: action.rapportBlob ?? null,
        rapportFilename: action.rapportFilename ?? "faktarapport.pdf",
        showPreview: true,
        progressMessage: "",
        basisText: action.basisText ?? state.basisText,
        generatedImageUrl: action.imageUrl ?? state.generatedImageUrl,
        worksheetText: action.worksheetText ?? state.worksheetText,
        faktarapportText: action.faktarapportText ?? state.faktarapportText,
        languageExercises: action.languageExercises ?? state.languageExercises,
        warnings: action.warnings ?? [],
        sourceGrounded: action.sourceGrounded ?? null,
        sourceName: action.sourceName ?? null,
        showEditPanel: false,
      };
    case "SET_BASIS_TEXT":
      return { ...state, basisText: action.text };
    case "SET_WORKSHEET_TEXT":
      return { ...state, worksheetText: action.text };
    case "TOGGLE_EDIT_PANEL":
      return { ...state, showEditPanel: !state.showEditPanel };
    case "IMAGE_CANDIDATES_LOADING":
      return { ...state, imageCandidatesLoading: true, imageCandidates: [] };
    case "IMAGE_CANDIDATES_LOADED":
      return { ...state, imageCandidatesLoading: false, imageCandidates: action.candidates };
    case "GENERATION_ERROR":
      return { ...state, status: "error", errorMessage: action.message, progressMessage: "" };
    case "GENERATION_CANCEL":
      return { ...state, status: "idle", progressMessage: "" };
    case "GENERATION_IDLE":
      return { ...state, status: "idle" };
    case "SHOW_PREVIEW":
      return { ...state, showPreview: true };
    case "CLOSE_PREVIEW":
      return { ...state, showPreview: false };
    case "TICK_TIMER":
      return { ...state, elapsedSeconds: state.elapsedSeconds + 1 };
    case "RESTORE_SESSION":
      return {
        ...state,
        topic: action.topic,
        subject: action.subject,
        level: action.level,
        mode: action.mode,
        basisText: action.basisText,
        worksheetText: action.worksheetText,
        faktarapportText: action.faktarapportText,
        generatedImageUrl: action.imageUrl,
        languageExercises: action.languageExercises ?? null,
        interest: action.interest ?? "",
        showEditPanel: true,
        status: "idle",
      };
    default:
      return state;
  }
}
