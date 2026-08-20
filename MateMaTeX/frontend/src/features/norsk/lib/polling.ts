/** Exponential backoff for generation status polling (starts at ~2s, caps ~8s). */
export function nextPollDelayMs(attempt: number): number {
  return Math.min(Math.round(2000 * Math.pow(1.35, attempt)), 8000);
}

/** A step number alone is not enough: intermediate work may use the same step. */
export function isProgressComplete(step: unknown, totalSteps: unknown): boolean {
  const current = Number(step);
  const total = Number(totalSteps);
  return (
    Number.isFinite(current) &&
    Number.isFinite(total) &&
    current > 0 &&
    total > 0 &&
    current >= total
  );
}

/**
 * Read terminal failures from the durable status contract instead of relying
 * only on the numeric step. A failed worker can retain its last progress step
 * while the terminal status is being persisted.
 */
export function progressErrorMessage(progress: unknown): string | null {
  if (!progress || typeof progress !== "object") return null;

  const data = progress as {
    job_status?: unknown;
    status?: unknown;
    step?: unknown;
    message?: unknown;
  };
  const lifecycle = data.job_status ?? data.status;
  const step = Number(data.step);
  const failedByStep = Number.isFinite(step) && step < 0;
  if (lifecycle !== "failed" && lifecycle !== "cancelled" && !failedByStep) {
    return null;
  }

  if (typeof data.message === "string" && data.message.trim()) {
    return data.message;
  }
  return lifecycle === "cancelled"
    ? "Genereringen ble avbrutt."
    : "Noe gikk galt under generering. Prøv igjen litt senere.";
}

/** Return the teacher-review message for a non-exportable terminal job. */
export function progressReviewMessage(progress: unknown): string | null {
  if (!progress || typeof progress !== "object") return null;

  const data = progress as { job_status?: unknown; status?: unknown; message?: unknown };
  const lifecycle = data.job_status ?? data.status;
  if (lifecycle !== "needs_teacher_review") return null;

  return typeof data.message === "string" && data.message.trim()
    ? data.message
    : "Lærergjennomgang kreves før PDF kan godkjennes.";
}
