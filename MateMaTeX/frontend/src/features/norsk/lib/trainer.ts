import type { Status } from "./fovTypes";

/** Endpoint of the concept trainer (an offline HTML practice app) for a generation. */
export function trainerUrl(apiUrl: string, generationId: string, draft = false): string {
  return `${apiUrl}/download-trainer/${encodeURIComponent(generationId)}${draft ? "?preview=true" : ""}`;
}

interface OfferInput {
  status: Status;
  /** True for two-version and multi-level runs, which produce a ZIP of several sheets. */
  isDual: boolean;
  /** The trainer is built from the sheet's key terms, so it needs the word tasks. */
  vocabularyTasks: boolean;
}

/**
 * The trainer is offered once a single-level sheet exists, either approved-ready
 * ("success") or as a draft for review. The server stays the authority: it
 * answers 409/422 with a readable reason if the sheet cannot yield a trainer.
 */
export function canOfferTrainer({ status, isDual, vocabularyTasks }: OfferInput): boolean {
  return !isDual && vocabularyTasks && (status === "success" || status === "needs_teacher_review");
}
