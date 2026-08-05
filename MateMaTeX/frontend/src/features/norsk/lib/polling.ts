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
